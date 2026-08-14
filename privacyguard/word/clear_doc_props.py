"""Phase 3 Word 文档属性清除（D-08 / D-24 — 与 Phase 2 SAFE-03 clear_pdf_metadata 对称）。

D-08 锁：
- 5 个 core 字符串字段全部 ""（不写 "Anonymous" / "Redacted" 占位 —— D-15 锁）
- revision 单独处理为整数 1（D-08 / D-24 锁）
- app_properties 走 hasattr + try/except 防御（python-docx v0.8.10 以下版本只读 / 不可用）
- 不触碰 core_properties.creation_date / modified / Template / TotalTime 等保留字段
"""
from typing import Final


# D-08 锁 — 5 个 core 字符串字段
CORE_PROPS_TO_CLEAR: Final = ('title', 'author', 'subject', 'keywords', 'last_modified_by')
# 2 个 app 字符串字段
APP_PROPS_TO_CLEAR: Final = ('company', 'manager')


def clear_word_doc_props(doc) -> None:
    """清除 docx 文档的敏感属性。

    5 个 core 字符串字段置 "" + revision 置 1 + 2 个 app 字段置 ""。
    """
    core = doc.core_properties
    for prop_name in CORE_PROPS_TO_CLEAR:
        if prop_name == 'title':
            core.title = ''
        elif prop_name == 'author':
            core.author = ''
        elif prop_name == 'subject':
            core.subject = ''
        elif prop_name == 'keywords':
            core.keywords = ''
        elif prop_name == 'last_modified_by':
            core.last_modified_by = ''

    # revision 字段必须整数 1（D-08 / D-24 锁）
    if hasattr(core, 'revision'):
        core.revision = 1

    # app_properties 部分版本只读 / 不可用；走 hasattr + try/except 防御
    app = getattr(doc, 'app_properties', None)
    if app is not None:
        for prop_name in APP_PROPS_TO_CLEAR:
            if hasattr(app, prop_name):
                try:
                    setattr(app, prop_name, '')
                except (AttributeError, ValueError):
                    # python-docx v0.8.10 以下版本只读防御
                    pass


__all__ = ['clear_word_doc_props', 'CORE_PROPS_TO_CLEAR', 'APP_PROPS_TO_CLEAR']
