"""PII 命中 partial mask 生成（D-05 mask_strategy 字段）。

- partial_mask_id_card: 前 6 + 后 4 保留，中间 * (e.g. "110101********8811")
- partial_mask_phone: 前 3 + 后 4 保留 (e.g. "138****5678")
- mask_for_entity: 按 entity_type 分派
"""


def partial_mask_id_card(normalized18: str) -> str:
    """身份证部分掩码（前 6 + 后 4）；长度非 18 时返回全掩。"""
    if not normalized18 or len(normalized18) != 18:
        return '*' * len(normalized18)
    return normalized18[:6] + '*' * 8 + normalized18[14:]


def partial_mask_phone(normalized11: str) -> str:
    """手机号部分掩码（前 3 + 后 4）；长度非 11 时返回全掩。"""
    if not normalized11 or len(normalized11) != 11:
        return '*' * len(normalized11)
    return normalized11[:3] + '*' * 4 + normalized11[7:]


def mask_for_entity(entity_type: str, normalized_text: str) -> str:
    """按 entity_type 分派掩码策略。"""
    if entity_type == "CN_ID_CARD":
        return partial_mask_id_card(normalized_text)
    if entity_type == "CN_PHONE":
        return partial_mask_phone(normalized_text)
    return '*' * len(normalized_text)


__all__ = ['partial_mask_id_card', 'partial_mask_phone', 'mask_for_entity']