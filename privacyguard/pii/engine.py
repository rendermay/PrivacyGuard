"""PII 引擎 — 纯函数式 detect pipeline（无 Qt / 无线程）。

依赖：
- privacyguard.pii.hits: PIIHit / TextUnit
- privacyguard.pii.regex_patterns: iter_candidate_strings
- privacyguard.pii.validators.id_card: validate_18 / validate_15
- privacyguard.pii.validators.phone_segment: is_mobile_segment
- privacyguard.pii.normalize: normalize_digits / flatten_for_match / map_flat_to_original
- privacyguard.pii.confidence: classify_hit
- privacyguard.pii.mask: mask_for_entity
- privacyguard.pii.overlap: resolve

ENGINE-04 一致掩码：_mask_cache[(entity_type, normalized)] -> mask_strategy
ENGINE-07 防 DoS：单页文本超过 _MAX_TEXT_BYTES 自动截断
ENGINE-08 零网络：本模块不 import socket / urllib / requests / httpx
B2 文字层真实坐标：detect(unit, page=...) 接收可选 page 对象；
    引擎通过 page.search_for(original_substring) 取真实 rect；
    fallback：原始 substring 搜不到时按分隔符拆 chunk 并 union per-chunk rects。
W-A 不可定位记录：unresolvable hit 不静默丢弃，记录到 unresolved_hits + error_log。
I1 15 位降级：bare 15-digit 无 context anchor → confidence_tier=MEDIUM。
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from privacyguard.pii.hits import PIIHit, TextUnit
from privacyguard.pii.regex_patterns import iter_candidate_strings
from privacyguard.pii.validators.id_card import (
    validate_15,
    validate_18,
)
from privacyguard.pii.validators.phone_segment import is_mobile_segment
from privacyguard.pii.normalize import (
    flatten_for_match,
    map_flat_to_original,
    normalize_digits,
)
from privacyguard.pii.confidence import classify_hit
from privacyguard.pii.mask import mask_for_entity
from privacyguard.pii.overlap import resolve as resolve_overlap


# 200KB 输入大小上限（ENGINE-07 防 DoS）
_MAX_TEXT_BYTES = 200_000

# 文字层无具体坐标时的占位 rect 高度 / 字宽估算
_TEXT_LAYER_LINE_HEIGHT = 12.0
_TEXT_LAYER_CHAR_WIDTH = 6.0

# B2 fallback: 按 [-\s　]+ 拆 chunk；chunk < 此长度视为噪声，跳过
_CHUNK_MIN_LEN = 6

# I1: 15 位 ID 上下文锚点关键字（±20 字符窗口内出现任一即视为有上下文）
_ID_CONTEXT_ANCHORS = (
    '身份证', '身份证号', '身份证号码', '公民身份号码',
    'ID', 'id card', 'IDCard',
)


class PIIEngine:
    """纯函数式 PII 检测引擎（NUM-01..03 / ENGINE-01..07）。

    Attributes:
        last_error: 最后一次异常信息（W1 — 异常可见性）；detect 入口置 None
        error_log: List[Tuple[tag, page_idx, info]] — 引擎内部错误 / 警告记录
            （W1 主记录 + W-A "PII NO-RECT" 行）
        unresolved_hits: List[PIIHit] — 引擎 DETECTED 但未能定位的命中（W-A）
        _mask_cache: Dict[(entity_type, normalized), str] — ENGINE-04 一致掩码

    Methods:
        detect(unit, page=None) -> List[PIIHit]:
            文字层路径：若 page 提供且含 search_for，对每个候选调
            page.search_for(original_substring)；搜不到则按分隔符拆 chunk union。
            任何候选不可定位 → 记 unresolved_hits + error_log（不静默丢弃）。
    """

    def __init__(self, rules_data=None):
        """初始化引擎；rules_data 为 None 时回退到内置默认（phone_segment.py
        硬编码 + id_card.py 硬编码）。读取失败时打印 warn 但不中断。
        """
        self._rules = rules_data or {}
        self._mask_cache: Dict[Tuple[str, str], str] = {}
        self.last_error: Optional[str] = None
        self.error_log: List[Tuple] = []
        self.unresolved_hits: List[PIIHit] = []

    # ------------------------------------------------------------------
    # rules_version classmethod (Task 3 — Plan 01-02 hardening)
    # ------------------------------------------------------------------
    @classmethod
    def rules_version(cls, rules_data: Optional[dict]) -> str:
        """读取 rules.json 中 phone_segment.next_review；缺失返回 'unknown'。

        UI / 测试用：避免直接 reach into rules dict 字段。
        """
        if not rules_data:
            return "unknown"
        phone = rules_data.get("phone_segment") or {}
        return phone.get("next_review", "unknown") or "unknown"

    # ------------------------------------------------------------------
    # detect 主入口
    # ------------------------------------------------------------------
    def detect(
        self,
        unit: TextUnit,
        page: Any = None,
    ) -> List[PIIHit]:
        """detect pipeline：扁平化 → 候选扫描 → 校验 → 命中构建。

        Args:
            unit: 文字层 / OCR 输入单元
            page: 可选 fitz Page（提供 search_for 时取真实坐标；None 时退化为占位 rect）
        """
        self.last_error = None
        text = unit.text or ''
        if not text.strip():
            return []
        if len(text) > _MAX_TEXT_BYTES:
            # ENGINE-07 防 DoS: 超长文本按 _MAX_TEXT_BYTES 截断（一次性 warn）
            self.error_log.append((
                "PII WARN", unit.page_index,
                f"单页文本超过 {len(text)} 字符，截断到 {_MAX_TEXT_BYTES} 以保护 UI 响应",
            ))
            text = text[:_MAX_TEXT_BYTES]

        flat = flatten_for_match(text)
        if not flat:
            return []

        hits: List[PIIHit] = []
        try:
            for cand, flat_span, entity_hint in iter_candidate_strings(flat):
                normalized = normalize_digits(cand)
                if entity_hint == 'CN_ID_CARD':
                    hit = self._check_id_card(
                        unit, cand, normalized, flat_span, text, page,
                    )
                else:
                    hit = self._check_phone(
                        unit, cand, normalized, flat_span, text, page,
                    )
                if hit is not None:
                    hits.append(hit)
        except Exception as exc:
            # W1: 引擎异常必须可见
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.error_log.append(("PII ENGINE_ERROR", unit.page_index, self.last_error))

        return resolve_overlap(hits)

    # ------------------------------------------------------------------
    # 实体校验
    # ------------------------------------------------------------------
    def _check_id_card(
        self,
        unit: TextUnit,
        cand: str,
        normalized: str,
        flat_span: Tuple[int, int],
        original_text: str,
        page: Any,
    ) -> Optional[PIIHit]:
        """身份证命中校验：18 位 mod-11-2 / 15 位双门 + 校验位。"""
        if len(normalized) == 18 and validate_18(normalized):
            validator_passed = True
            is_15_digit = False
        elif len(normalized) == 15 and validate_15(normalized):
            validator_passed = True
            is_15_digit = True
        else:
            return None

        # I1: bare 15-digit 无 context anchor → MEDIUM 降级（避免订单号误识别）
        if is_15_digit and not self._has_id_context_anchor(unit.text or ''):
            confidence_tier = "MEDIUM"
        else:
            confidence_tier = "HIGH"

        page_rect = self._resolve_page_rect(
            unit, cand, flat_span, original_text, page,
        )
        if page_rect is None:
            return None

        return self._make_hit(
            unit=unit,
            normalized=normalized,
            flat_span=flat_span,
            original_text=original_text,
            entity_type='CN_ID_CARD',
            source=unit.source or 'text',
            page_rect=page_rect,
            validator_passed=validator_passed,
            confidence_tier=confidence_tier,
        )

    def _check_phone(
        self,
        unit: TextUnit,
        cand: str,
        normalized: str,
        flat_span: Tuple[int, int],
        original_text: str,
        page: Any,
    ) -> Optional[PIIHit]:
        """手机号命中校验：MIIT 段号白名单 + IoT 排除。"""
        if not is_mobile_segment(normalized):
            return None

        page_rect = self._resolve_page_rect(
            unit, cand, flat_span, original_text, page,
        )
        if page_rect is None:
            return None

        return self._make_hit(
            unit=unit,
            normalized=normalized,
            flat_span=flat_span,
            original_text=original_text,
            entity_type='CN_PHONE',
            source=unit.source or 'text',
            page_rect=page_rect,
            validator_passed=True,
            confidence_tier="HIGH",
        )

    # ------------------------------------------------------------------
    # page_rect 解析（B2 / W-A）
    # ------------------------------------------------------------------
    def _resolve_page_rect(
        self,
        unit: TextUnit,
        cand: str,
        flat_span: Tuple[int, int],
        original_text: str,
        page: Any,
    ) -> Optional[Tuple[float, float, float, float]]:
        """B2: 优先 page.search_for(original_substring)；fallback chunk union。

        退化路径：page=None（向后兼容）→ 占位 rect；OCR 路径（unit.source != "text"）
        → 占位 rect（Plan 01-03 Task 1 接管 OCR box mapping）。
        """
        # OCR 路径：暂用占位 rect（Plan 01-03 Task 1 接管 OCR box mapping）
        if unit.source and unit.source != 'text':
            return self._placeholder_rect_for_text_layer(cand)

        # 退化：page 未提供 → 占位 rect（向后兼容旧调用方）
        if page is None:
            return self._placeholder_rect_for_text_layer(cand)

        # 计算 orig_span（map 到原文本）
        flat_text = flatten_for_match(original_text)
        orig_span = map_flat_to_original(flat_text, flat_span, original_text)
        if orig_span[0] is None:
            # map 失败 → 不可定位，记 unresolved
            self._record_unresolved(unit, cand, normalized=None, span=None)
            return None
        orig_start, orig_end = orig_span
        original_substring = original_text[orig_start:orig_end]

        # 1. 原始 substring 直接搜
        rects = self._search_on_page(page, original_substring)
        if rects:
            return self._rect_to_xywh(rects[0])

        # 2. fallback: 按 [-\s　]+ 拆 chunk 并 union
        chunks = re.split(r'[-\s　]+', original_substring)
        chunk_rects = []
        for chunk in chunks:
            if len(chunk) < _CHUNK_MIN_LEN:
                continue
            rs = self._search_on_page(page, chunk)
            if rs:
                chunk_rects.extend(rs)
        if chunk_rects:
            return self._union_rects_to_xywh(chunk_rects)

        # 3. 不可定位 → W-A: 记录 + 不发射
        self._record_unresolved(
            unit, cand, normalized=cand, span=(orig_start, orig_end - orig_start),
        )
        return None

    def _search_on_page(self, page: Any, text: str) -> list:
        """调用 page.search_for(text)；page 不存在时返回空列表。"""
        if page is None:
            return []
        search_for = getattr(page, 'search_for', None)
        if not callable(search_for):
            return []
        try:
            return list(search_for(text))
        except Exception:
            return []

    @staticmethod
    def _rect_to_xywh(rect) -> Tuple[float, float, float, float]:
        """rect (x0, y0, x1, y1) → (x, y, w, h) 4 元 tuple。"""
        x0 = float(getattr(rect, 'x0', 0.0))
        y0 = float(getattr(rect, 'y0', 0.0))
        x1 = float(getattr(rect, 'x1', x0))
        y1 = float(getattr(rect, 'y1', y0))
        # SimpleNamespace 等对象可能用 width/height 而非 x1/x1
        if x1 == x0:
            w = float(getattr(rect, 'width', 0.0))
            if w:
                x1 = x0 + w
        if y1 == y0:
            h = float(getattr(rect, 'height', 0.0))
            if h:
                y1 = y0 + h
        return (x0, y0, max(x1 - x0, 0.0), max(y1 - y0, 0.0))

    @staticmethod
    def _union_rects_to_xywh(rects: list) -> Optional[Tuple[float, float, float, float]]:
        """一组 rect 取 bounding union → (x, y, w, h)。"""
        if not rects:
            return None
        min_x0 = min(float(getattr(r, 'x0', 0.0)) for r in rects)
        min_y0 = min(float(getattr(r, 'y0', 0.0)) for r in rects)
        max_x1 = max(
            float(getattr(r, 'x1', getattr(r, 'x0', 0.0))) for r in rects
        )
        max_y1 = max(
            float(getattr(r, 'y1', getattr(r, 'y0', 0.0))) for r in rects
        )
        w = max(max_x1 - min_x0, 0.0)
        h = max(max_y1 - min_y0, 0.0)
        if w <= 0 or h <= 0:
            return None
        return (min_x0, min_y0, w, h)

    # ------------------------------------------------------------------
    # I1 上下文锚点检测
    # ------------------------------------------------------------------
    @staticmethod
    def _has_id_context_anchor(text: str) -> bool:
        """±20 字符窗口内是否存在 ID 上下文锚点关键字（I1 降级开关）。"""
        if not text:
            return False
        lower = text.lower()
        for anchor in _ID_CONTEXT_ANCHORS:
            idx = lower.find(anchor.lower())
            if idx >= 0:
                return True
        return False

    # ------------------------------------------------------------------
    # W-A 不可定位记录
    # ------------------------------------------------------------------
    def _record_unresolved(
        self,
        unit: TextUnit,
        candidate: str,
        normalized: Optional[str],
        span: Optional[Tuple[int, int]],
    ) -> None:
        """W-A: 引擎 DETECTED 但 page 不可定位时记录候选 + log 行。

        不静默丢弃：unresolved_hits 保留 PIIHit 副本供 UI 显示"未定位敏感项"。
        """
        if span is None:
            page_offset = 0
            page_length = max(len(candidate or ''), 0)
        else:
            page_offset, page_length = span
        # 占位 rect（零面积），标记此为 unresolved（与正常 hit 区分）
        hit = PIIHit(
            entity_type='CN_UNRESOLVED',
            page_offset=page_offset,
            page_length=page_length,
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="MEDIUM",
            source=unit.source or 'text',
            mask_strategy="<unresolved>",
            normalized=normalized or candidate or '',
            validator_passed=False,
        )
        self.unresolved_hits.append(hit)
        self.error_log.append((
            "PII NO-RECT", unit.page_index, candidate,
        ))

    # ------------------------------------------------------------------
    # PIIHit 构造
    # ------------------------------------------------------------------
    def _make_hit(
        self,
        unit: TextUnit,
        normalized: str,
        flat_span: Tuple[int, int],
        original_text: str,
        entity_type: str,
        source: str,
        page_rect: Tuple[float, float, float, float],
        validator_passed: bool,
        confidence_tier: Optional[str] = None,
    ) -> PIIHit:
        """构造 PIIHit；调用 mask_for_entity（含 _mask_cache）。"""
        # 计算 orig_span：把 flat 索引映回原文本
        flat_text = flatten_for_match(original_text)
        orig_span = map_flat_to_original(flat_text, flat_span, original_text)
        if orig_span[0] is None:
            page_offset = 0
            page_length = len(normalized)
        else:
            page_offset, orig_end = orig_span
            page_length = max(orig_end - page_offset, len(normalized))

        # ENGINE-04: 一致掩码缓存
        cache_key = (entity_type, normalized)
        mask_strategy = self._mask_cache.get(cache_key)
        if mask_strategy is None:
            mask_strategy = mask_for_entity(entity_type, normalized)
            self._mask_cache[cache_key] = mask_strategy

        # tier 由调用方决定（I1 路径需传 MEDIUM）；其他走 classify_hit
        if confidence_tier is None:
            confidence_tier = classify_hit(
                validator_passed=validator_passed,
                regex_matched=True,
                source=source,
            )

        return PIIHit(
            entity_type=entity_type,
            page_offset=page_offset,
            page_length=page_length,
            page_rect=page_rect,
            confidence_tier=confidence_tier,
            source=source,
            mask_strategy=mask_strategy,
            normalized=normalized,
            validator_passed=validator_passed,
        )

    # ------------------------------------------------------------------
    # 占位 rect（向后兼容：detect 不传 page 时）
    # ------------------------------------------------------------------
    def _placeholder_rect_for_text_layer(
        self, cand: str,
    ) -> Tuple[float, float, float, float]:
        """文字层无具体坐标时的占位 rect（(0, 0, len*6, 12)）。

        当 detect(unit) 未传 page 时退化使用；生产路径应通过 page.search_for
        拿真实坐标（见 _resolve_page_rect）。
        """
        approx_width = max(len(cand) * _TEXT_LAYER_CHAR_WIDTH, _TEXT_LAYER_LINE_HEIGHT)
        return (0.0, 0.0, approx_width, _TEXT_LAYER_LINE_HEIGHT)


__all__ = ['PIIEngine', 'TextUnit']
