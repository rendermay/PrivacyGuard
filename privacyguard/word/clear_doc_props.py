"""Phase 3 Word 文档属性清除（D-08 / D-24 — 与 Phase 2 SAFE-03 clear_pdf_metadata 对称）。"""
from typing import Final


# D-08 锁 — 5 个 core 字符串字段 + 2 个 app 字符串字段 + revision=1
CORE_PROPS_TO_CLEAR: Final = ('title', 'author', 'subject', 'keywords', 'last_modified_by')
APP_PROPS_TO_CLEAR: Final = ('company', 'manager')


def clear_word_doc_props(doc) -> None:
    """清除 docx 文档的敏感属性（Wave 1 RED 占位 — Wave 2 Task 实现）。"""
    raise NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现")


__all__ = ['clear_word_doc_props', 'CORE_PROPS_TO_CLEAR', 'APP_PROPS_TO_CLEAR']
