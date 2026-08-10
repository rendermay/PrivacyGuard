"""身份证 / 手机号预编译正则（worker 多次复用）。

正则与 validators 协同：18 位 / 15 位身份证、11 位 1 开头手机号。
具体段号判定走 `privacyguard.pii.validators.phone_segment.is_mobile_segment`。
"""
import re
from typing import Final, Iterator, Tuple


# 18 位（年份限制 19xx / 20xx；月份 / 日期合法性；末位 [0-9Xx]）
_ID_18_RE: Final = re.compile(
    r"(?<!\d)([1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])(?!\d)"
)
# 15 位（旧号，升级到 18 位后再校验）
_ID_15_RE: Final = re.compile(r"(?<!\d)([1-9]\d{14})(?!\d)")
# 11 位 1 开头的疑似手机号（具体段号判定走 validators.phone_segment）
_PHONE_11_RE: Final = re.compile(r"(?<!\d)(1\d{10})(?!\d)")


def iter_candidate_strings(text: str) -> Iterator[Tuple[str, Tuple[int, int], str]]:
    """按 18 → 15 → 手机号顺序产出候选字符串（去重交给 engine.resolve）。

    产出 (candidate_text, (start, end), entity_hint) 元组。
    """
    for m in _ID_18_RE.finditer(text):
        yield m.group(0), m.span(), "CN_ID_CARD"
    for m in _ID_15_RE.finditer(text):
        yield m.group(0), m.span(), "CN_ID_CARD"
    for m in _PHONE_11_RE.finditer(text):
        yield m.group(0), m.span(), "CN_PHONE"


__all__ = ['iter_candidate_strings']