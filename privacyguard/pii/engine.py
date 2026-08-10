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
ENGINE-08 零网络：本模块不 import socket / urllib / requests / httpx。
"""
from typing import Dict, List, Optional, Tuple

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


class PIIEngine:
    """纯函数式 PII 检测引擎（NUM-01..03 / ENGINE-01..07）。

    - detect(unit) -> List[PIIHit]: 输入一个 TextUnit，返回所有命中。
    - last_error: Optional[str]: 最后一次异常信息（Phase 1 暂未填充）。
    """

    def __init__(self, rules_data=None):
        """初始化引擎；rules_data 为 None 时回退到内置默认（phone_segment.py
        硬编码 + id_card.py 硬编码）。读取失败时打印 warn 但不中断。
        """
        self._rules = rules_data or {}
        self._mask_cache: Dict[Tuple[str, str], str] = {}
        self.last_error: Optional[str] = None

    def detect(self, unit: TextUnit) -> List[PIIHit]:
        """detect pipeline：扁平化 → 候选扫描 → 校验 → 命中构建。"""
        text = unit.text or ''
        if not text.strip():
            return []
        if len(text) > _MAX_TEXT_BYTES:
            # ENGINE-07 防 DoS: 超长文本按 _MAX_TEXT_BYTES 截断
            text = text[:_MAX_TEXT_BYTES]

        flat = flatten_for_match(text)
        if not flat:
            return []

        hits: List[PIIHit] = []
        for cand, flat_span, entity_hint in iter_candidate_strings(flat):
            normalized = normalize_digits(cand)
            if entity_hint == 'CN_ID_CARD':
                hit = self._check_id_card(unit, cand, normalized, flat_span)
            else:
                hit = self._check_phone(unit, cand, normalized, flat_span)
            if hit is not None:
                hits.append(hit)

        return resolve_overlap(hits)

    def _check_id_card(
        self,
        unit: TextUnit,
        cand: str,
        normalized: str,
        flat_span: Tuple[int, int],
    ) -> Optional[PIIHit]:
        """身份证命中校验：18 位 mod-11-2 / 15 位双门 + 校验位。"""
        if len(normalized) == 18 and validate_18(normalized):
            validator_passed = True
        elif len(normalized) == 15 and validate_15(normalized):
            validator_passed = True
        else:
            return None

        page_rect = self._placeholder_rect_for_text_layer(cand)
        return self._make_hit(
            unit=unit,
            normalized=normalized,
            flat_span=flat_span,
            entity_type='CN_ID_CARD',
            source=unit.source or 'text',
            page_rect=page_rect,
            validator_passed=validator_passed,
        )

    def _check_phone(
        self,
        unit: TextUnit,
        cand: str,
        normalized: str,
        flat_span: Tuple[int, int],
    ) -> Optional[PIIHit]:
        """手机号命中校验：MIIT 段号白名单 + IoT 排除。"""
        if not is_mobile_segment(normalized):
            return None

        page_rect = self._placeholder_rect_for_text_layer(cand)
        return self._make_hit(
            unit=unit,
            normalized=normalized,
            flat_span=flat_span,
            entity_type='CN_PHONE',
            source=unit.source or 'text',
            page_rect=page_rect,
            validator_passed=True,
        )

    def _make_hit(
        self,
        unit: TextUnit,
        normalized: str,
        flat_span: Tuple[int, int],
        entity_type: str,
        source: str,
        page_rect: Tuple[float, float, float, float],
        validator_passed: bool,
    ) -> PIIHit:
        """构造 PIIHit；调用 mask_for_entity（含 _mask_cache）。"""
        # 计算 orig_span：把 flat 索引映回原文本
        flat_text = flatten_for_match(unit.text or '')
        orig_span = map_flat_to_original(flat_text, flat_span, unit.text or '')
        if orig_span is None:
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

        tier = classify_hit(
            validator_passed=validator_passed,
            regex_matched=True,
            source=source,
        )

        return PIIHit(
            entity_type=entity_type,
            page_offset=page_offset,
            page_length=page_length,
            page_rect=page_rect,
            confidence_tier=tier,
            source=source,
            mask_strategy=mask_strategy,
            normalized=normalized,
            validator_passed=validator_passed,
        )

    def _placeholder_rect_for_text_layer(self, cand: str) -> Tuple[float, float, float, float]:
        """文字层无具体坐标时的占位 rect（(0, 0, len*6, 12)）。

        实际 UI / save 路径会基于 page.search_for 二次定位；本占位
        仅用于单测 / pipeline smoke（text-layer path 不依赖精确坐标）。
        """
        approx_width = max(len(cand) * _TEXT_LAYER_CHAR_WIDTH, _TEXT_LAYER_LINE_HEIGHT)
        return (0.0, 0.0, approx_width, _TEXT_LAYER_LINE_HEIGHT)


__all__ = ['PIIEngine', 'TextUnit']