"""Phase 3 Word 真脱敏写入 wrapper（D-23 — 沿用 main.py:replace_matches_in_paragraph run-level 替换）。"""


def redact_paragraph(para, matches, fallback_replacement_text: str = '[已脱敏]') -> None:
    """单段落 run-level 替换 wrapper（Wave 1 RED 占位 — Wave 2 Task 实现）。"""
    raise NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现")


def redact_word(doc, key: str, merged_matches: list, fallback_replacement_text: str = '[已脱敏]') -> None:
    """doc + key 形态的真脱敏写入（Wave 1 RED 占位 — Wave 2 Task 实现）。"""
    raise NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现")


__all__ = ['redact_word', 'redact_paragraph']
