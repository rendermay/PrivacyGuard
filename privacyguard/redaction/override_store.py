# -*- coding: utf-8 -*-
"""HitOverrideStore 单例: 会话级 + 永久级双层 override 管理."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Dict, Iterator, List, Optional

from privacyguard.redaction.hit_ref import HitRef, Override, VALID_ACTIONS, VALID_SCOPES

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
        try:
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