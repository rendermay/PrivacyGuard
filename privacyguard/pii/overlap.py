"""PII 命中去重 + 跨 recognizer 优先级解析（ENGINE-04）。"""
from typing import Dict, List

from privacyguard.pii.hits import PIIHit


def resolve(hits: List[PIIHit]) -> List[PIIHit]:
    """同 (page_offset, page_length) 范围内只保留一份。

    Phase 1 单 recognizer：同位置只可能来自同一正则路径；保留
    validator_passed=True 的命中（移除 validator_failed=False 的 MEDIUM 重复）。

    返回按 (page_offset, page_length) 排序。
    """
    if not hits:
        return []
    by_pos: Dict[tuple, PIIHit] = {}
    for hit in hits:
        key = (hit.page_offset, hit.page_length)
        existing = by_pos.get(key)
        if existing is None:
            by_pos[key] = hit
            continue
        # 同位置：保留 validator_passed=True 的；都没有则保留先到
        if hit.validator_passed and not existing.validator_passed:
            by_pos[key] = hit
    return sorted(by_pos.values(), key=lambda h: (h.page_offset, h.page_length))


__all__ = ['resolve']