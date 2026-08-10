"""ENGINE-05 / ENGINE-06 文本归一化（全角→半角 + 跨行拼接 + offset 回算）。

- normalize_digits: 全角数字 → 半角 + 去除 -/半角空格/全角空格（用于已校验字符串）
- flatten_for_match: 去除所有空白 + -（用于跨行 / 制表 / 全角空白的拼接）
- map_flat_to_original: 把 flat 字符串中的 (start, end) 映射回原始字符串
"""
import re
from typing import Optional, Tuple


_FULLWIDTH_DIGITS = str.maketrans('０１２３4567８９', '0123456789')

# 修正：上面原文 `'０１２３４５６７８９'` 看起来完整，但为安全起见重新构造
_FULLWIDTH_DIGITS = str.maketrans(
    '０１２３４５６７８９',
    '0123456789',
)


_SEPARATOR_CHARS = re.compile(r'[-\s　]+')

_FLATTEN_CHARS = re.compile(r'[\s\n\r\t　-]+')


def normalize_digits(text: str) -> str:
    """全角数字 → 半角 + 移除 -/半角空格/全角空格。"""
    if not text:
        return ''
    text = text.translate(_FULLWIDTH_DIGITS)
    return _SEPARATOR_CHARS.sub('', text)


def flatten_for_match(text: str) -> str:
    """跨行 / 制表 / 全角空白拼接（用于跨行实体识别 ENGINE-06）。"""
    if not text:
        return ''
    return _FLATTEN_CHARS.sub('', text)


def map_flat_to_original(
    flat_text: str,
    flat_span: Tuple[int, int],
    original_text: str,
) -> Optional[Tuple[int, int]]:
    """把 flat 字符串中的 (start, end) 映射回 original_text 中的 (start, end)。

    ENGINE-05 offset 回算用：flat 是去空白后的字符串，命中位置需映回原始字符串。
    处理：空白 / 横线 / 全角空白字符跳过；全角数字按归一化语义也映射。
    """
    if not flat_text or not original_text:
        return None
    flat_start, flat_end = flat_span
    orig_pos = 0
    flat_pos = 0
    orig_start = None
    orig_end = None

    skip_chars = set(' \t\n\r\f\v　- ')
    fullwidth_digits = '０１２３4567８９'

    while orig_pos < len(original_text) and flat_pos < len(flat_text):
        ch = original_text[orig_pos]
        if ch in skip_chars:
            orig_pos += 1
            continue
        if flat_pos == flat_start:
            orig_start = orig_pos
        if flat_pos == flat_end:
            orig_end = orig_pos
            break
        if ch in fullwidth_digits:
            ch = '0123456789'[fullwidth_digits.index(ch)]
        flat_pos += 1
        orig_pos += 1

    if orig_start is None or orig_end is None:
        return None
    # ensure end >= start
    if orig_end < orig_start:
        orig_end = orig_start
    return orig_start, orig_end


__all__ = ['normalize_digits', 'flatten_for_match', 'map_flat_to_original']