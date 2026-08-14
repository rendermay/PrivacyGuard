"""PrivacyGuard Word 文档处理子系统（v38.x Phase 3 — FMT-02）。

承载 Word → PII 引擎 TextUnit 适配、QThread worker、真脱敏 wrapper、
Word 文档属性清除、候选审阅对话框。

所有子模块经 _LAZY_IMPORTS + __getattr__ 懒加载（OPS-03）；
禁止包级 eager import python-docx / mammoth / privacyguard.pii.engine。
"""
from importlib import import_module


__all__ = [
    'WordAdapter',
    'redact_word',
    'clear_word_doc_props',
    'WordPIIWorker',
    'WordCandidateDialog',
]


_LAZY_IMPORTS = {
    'WordAdapter': ('privacyguard.word.adapter', 'WordAdapter'),
    'redact_word': ('privacyguard.word.redact', 'redact_word'),
    'clear_word_doc_props': ('privacyguard.word.clear_doc_props', 'clear_word_doc_props'),
    'WordPIIWorker': ('privacyguard.word.worker', 'WordPIIWorker'),
    'WordCandidateDialog': ('privacyguard.word.candidate_dialog', 'WordCandidateDialog'),
}


def __getattr__(name):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
