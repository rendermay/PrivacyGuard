"""PII 命中数据契约（D-05 / ENGINE-02 锁定字段顺序与命名）。

字段顺序锁：entity_type, page_offset, page_length, page_rect, confidence_tier,
source, mask_strategy。trailing 默认值（confidence_tier / source / mask_strategy
/ normalized / validator_passed）满足 Python dataclass "non-default 不能在 default
之前" 规则（B4 fix）。
"""
from dataclasses import dataclass
from typing import Literal, Tuple


ConfidenceTier = Literal["HIGH", "MEDIUM", "LOW"]


@dataclass(frozen=True)
class PIIHit:
    """D-05 锁定字段命名与顺序（ENGINE-02）。"""

    entity_type: str                                                       # 必填（D-05 1）
    page_offset: int                                                       # 必填（D-05 2，整页文本字符串偏移）
    page_length: int                                                       # 必填（D-05 3）
    page_rect: Tuple[float, float, float, float]                           # 必填（D-05 4：(x, y, w, h)）
    confidence_tier: str = "HIGH"                                          # 默认 "HIGH"（D-05 5）
    source: str = "text"                                                   # 默认 "text"（D-05 6）
    mask_strategy: str = ""                                                # 默认 ""（D-05 7，engine 计算后填入）
    normalized: str = ""                                                   # 默认 ""（ENGINE-04 一致掩码用）
    validator_passed: bool = True                                          # 默认 True


@dataclass(frozen=True)
class TextUnit:
    """Phase 1 单输入单元；Phase 2+ 可扩展为 DocumentLocation。"""

    page_index: int
    text: str
    source: str  # "text" | "image_block" | "full_page_ocr"


# Phase 3 (03-word) — D-21 / BLOCKER 5 单一来源抽离
# 9 类 entity 短码字典（ASCII uppercase），用于候选审阅对话框 / 状态栏 / 数据标签
ENTITY_TYPE_SHORT_CODE: dict = {
    'CN_ID_CARD': 'ID',
    'CN_PHONE': 'PHONE',
    'CN_BANK_CARD': 'BANK',
    'CN_EMAIL': 'EMAIL',
    'CN_USCC': 'USCC',
    'CN_TAXPAYER_ID': 'TAX',
    'CN_TAXPAYER_ID_15': 'TAX15',
    'CN_VAT_INVOICE': 'VAT',
    'CN_BANK_ACCOUNT': 'ACCT',
}


__all__ = ["PIIHit", "TextUnit", "ConfidenceTier", "ENTITY_TYPE_SHORT_CODE"]