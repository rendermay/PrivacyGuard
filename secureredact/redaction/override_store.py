# -*- coding: utf-8 -*-
"""HitOverrideStore 单例: 会话级 + 永久级双层 override 管理."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Iterator, List, Optional

from secureredact.redaction.hit_ref import HitRef, Override, VALID_ACTIONS, VALID_SCOPES

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean_stale_permanent(items, *, max_age_days: int = 30, today: Optional[str] = None) -> list:
    """清理 max_age_days 天前 promoted 的永久 override.

    Args:
        items: dump_permanent 输出格式的 list
        max_age_days: 阈值，默认 30 天
        today: 测试用，ISO 格式；None 则用 datetime.now()
    """
    if today is None:
        today_iso = datetime.now().isoformat(timespec="seconds")
    else:
        today_iso = today
    today_dt = datetime.fromisoformat(today_iso)
    cutoff = today_dt - timedelta(days=max_age_days)
    kept = []
    for item in items:
        promoted_at = item.get("promoted_at")
        if not promoted_at:
            kept.append(item)
            continue
        try:
            promoted_dt = datetime.fromisoformat(promoted_at)
        except ValueError:
            kept.append(item)
            continue
        if promoted_dt >= cutoff:
            kept.append(item)
    return kept


class HitOverrideStore:
    """单例 store.

    用法:
        store = HitOverrideStore.instance()
        store.ignore(HitRef(...), scope="session")
        if store.is_ignored(ref): ...
        kept = store.filtered_hits(raw_hits, location="page_1", doc_hash=...)
    """

    _instance: Optional["HitOverrideStore"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        # keyed by hit_id
        self._overrides: Dict[str, Override] = {}
        self._lock = threading.Lock()
        # v1.1.11: 可选 SimpleConfig 引用，由调用方在 init 后注入
        self._config = None  # type: ignore[assignment]

    @classmethod
    def instance(cls) -> "HitOverrideStore":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """仅供测试使用."""
        with cls._instance_lock:
            cls._instance = None

    # ---- 写入 ----

    def ignore(self, ref: HitRef, *, scope: str = "session") -> None:
        self._write(Override(ref=ref, action="ignore", scope=scope,
                             promoted_at=_now_iso() if scope == "permanent" else None))

    def confirm(self, ref: HitRef, *, scope: str = "session") -> None:
        self._write(Override(ref=ref, action="confirm", scope=scope,
                             promoted_at=_now_iso() if scope == "permanent" else None))

    def revert(self, hit_id: str) -> None:
        with self._lock:
            self._overrides.pop(hit_id, None)

    def promote(self, hit_id: str) -> None:
        with self._lock:
            ov = self._overrides.get(hit_id)
            if ov is None:
                logger.warning("promote: hit_id 不存在 %s", hit_id)
                return
            if ov.scope == "permanent":
                return  # 已是 permanent
            self._overrides[hit_id] = Override(
                ref=ov.ref, action=ov.action, scope="permanent",
                promoted_at=_now_iso(),
            )

    def _write(self, ov: Override) -> None:
        with self._lock:
            self._overrides[ov.ref.hit_id] = ov

    # ---- 查询 ----

    def is_ignored(self, ref: HitRef) -> bool:
        return self._lookup(ref.hit_id, "ignore")

    def is_confirmed(self, ref: HitRef) -> bool:
        return self._lookup(ref.hit_id, "confirm")

    def _lookup(self, hit_id: str, action: str) -> bool:
        with self._lock:
            ov = self._overrides.get(hit_id)
            if ov is None:
                return False
            return ov.action == action

    def iter_overrides(self, scope: Optional[str] = None) -> Iterator[Override]:
        with self._lock:
            items = list(self._overrides.values())
        if scope is None:
            yield from items
        else:
            yield from (o for o in items if o.scope == scope)

    # ---- 过滤 ----

    def filtered_hits(self, hits: List[dict], *, location: str, doc_hash: str) -> List[dict]:
        """过滤掉已 ignore 的非 manual hit,保留 confirm 与 manual."""
        kept = []
        for hit in hits:
            source = hit.get("source", "ocr")
            # manual 永远保留
            if source == "manual":
                kept.append(hit)
                continue
            ref = self._hit_to_ref(hit, location=location, doc_hash=doc_hash)
            if ref is None:
                # 无法构造 ref,保留(不误伤)
                kept.append(hit)
                continue
            if self.is_ignored(ref):
                continue
            kept.append(hit)
        return kept

    @staticmethod
    def _hit_to_ref(hit: dict, *, location: str, doc_hash: str) -> Optional[HitRef]:
        """从 hit dict 构造 HitRef。

        start/end 来源优先级:
          1. hit["rect"] QRectF 字段(若存在) — 与 _locate_hit 同一坐标来源,保证
             ignore 的 hit_id 能在 filtered_hits 命中同一 hit
          2. hit["start"] / hit["end"](显式 int 字段,Word 端用)
          3. fallback 0 / 0
        """
        try:
            rect = hit.get("rect")
            if rect is not None and hasattr(rect, "x") and hasattr(rect, "width"):
                start = int(rect.x())
                end = int(rect.x() + rect.width())
            else:
                start = int(hit.get("start", 0))
                end = int(hit.get("end", start))
            return HitRef(
                doc_hash=doc_hash,
                location=location,
                start=start,
                end=end,
                text=str(hit.get("text", "")),
                source=str(hit.get("source", "ocr")),
            )
        except Exception as exc:
            logger.warning("构造 HitRef 失败: %s", exc)
            return None

    # ---- 持久化 ----

    def dump_permanent(self) -> List[dict]:
        """输出可写回 config.json 的永久 override 列表."""
        out = []
        with self._lock:
            for ov in self._overrides.values():
                if ov.scope != "permanent":
                    continue
                out.append({
                    "hit_id": ov.ref.hit_id,
                    "doc_hash": ov.ref.doc_hash,
                    "location": ov.ref.location,
                    "start": ov.ref.start,
                    "end": ov.ref.end,
                    "text": ov.ref.text,
                    "source": ov.ref.source,
                    "action": ov.action,
                    "scope": ov.scope,
                    "promoted_at": ov.promoted_at,
                })
        return out

    def load_permanent(self, items: List[dict]) -> None:
        """从 config.json 读永久 overrides,损坏条目静默跳过."""
        if not isinstance(items, list):
            logger.warning("load_permanent: 期望 list,得到 %s", type(items).__name__)
            return
        with self._lock:
            for raw in items:
                try:
                    ov = self._restore_one(raw)
                except Exception as exc:
                    logger.warning("load_permanent: 跳过损坏条目: %s; data=%s", exc, raw)
                    continue
                self._overrides[ov.ref.hit_id] = ov

    def replace_permanent(self, items: List[dict]) -> None:
        """全量替换永久 overrides。

        与 ``load_permanent`` (仅新增/覆盖) 不同,本方法会先移除所有现有的
        permanent 条目,再按 ``items`` 重建。用于"清理失效"等需要保持内存与
        config.json 一致的场景。
        """
        if not isinstance(items, list):
            logger.warning("replace_permanent: 期望 list,得到 %s", type(items).__name__)
            return
        with self._lock:
            # 移除现有 permanent 条目
            stale_hits = [
                hit_id for hit_id, ov in self._overrides.items()
                if ov.scope == "permanent"
            ]
            for hit_id in stale_hits:
                del self._overrides[hit_id]
            # 装载新 items
            for raw in items:
                try:
                    ov = self._restore_one(raw)
                except Exception as exc:
                    logger.warning("replace_permanent: 跳过损坏条目: %s; data=%s", exc, raw)
                    continue
                self._overrides[ov.ref.hit_id] = ov

    @staticmethod
    def _restore_one(raw: dict) -> Override:
        ref = HitRef(
            doc_hash=raw["doc_hash"],
            location=raw["location"],
            start=int(raw["start"]),
            end=int(raw["end"]),
            text=raw.get("text", ""),
            source=raw["source"],
        )
        return Override(
            ref=ref,
            action=raw["action"],
            scope=raw["scope"],
            promoted_at=raw.get("promoted_at"),
        )

    # ---- v1.1.11: 与 SimpleConfig 双向绑定 ----

    def bind_config(self, config) -> None:
        """由 MainWindow 在 init 时注入 SimpleConfig 引用。

        之后 save_permanent() 会自动把 dump_permanent() 写回
        ``redaction.overrides.permanent`` 并落盘。
        """
        self._config = config

    def save_permanent(self) -> None:
        """写回 SimpleConfig.

        若未 bind_config 则静默跳过（避免污染测试态）。
        """
        if self._config is None:
            return
        items = self.dump_permanent()
        try:
            self._config.set("redaction.overrides.permanent", items, persist=False)
            self._config.save()
        except Exception as exc:
            logger.warning("save_permanent 失败: %s", exc)