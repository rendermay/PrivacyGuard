"""PrivacyGuard PII 自动识别子系统（v38.x Phase 1）。

懒加载入口：禁止在 `import privacyguard` 时拉起 privacyguard.pii.* 子模块。
新增 PII 子模块必须在 _LAZY_IMPORTS 注册；严禁顶层 `from privacyguard.pii.x import ...`。
"""
from importlib import import_module


__all__ = [
    'PIIEngine',
    'PIIHit',
    'TextUnit',
    'validate_18_id',
    'validate_15_id',
    'upgrade_15_to_18',
    'compute_check_digit',
    'is_mobile_segment',
    'apply_pii_redactions',
    'collect_pii_rects',
    'PHONE_PERSONAL_PREFIX_3',
    'PHONE_EXCLUDED_PREFIX_3',
    'PHONE_EXCLUDED_PREFIX_4',
]


_LAZY_IMPORTS = {
    'PIIEngine':                 ('privacyguard.pii.engine', 'PIIEngine'),
    'PIIHit':                    ('privacyguard.pii.hits', 'PIIHit'),
    'TextUnit':                  ('privacyguard.pii.hits', 'TextUnit'),
    'validate_18_id':            ('privacyguard.pii.validators', 'validate_18_id'),
    'validate_15_id':            ('privacyguard.pii.validators', 'validate_15_id'),
    'upgrade_15_to_18':          ('privacyguard.pii.validators', 'upgrade_15_to_18'),
    'compute_check_digit':       ('privacyguard.pii.validators', 'compute_check_digit'),
    'is_mobile_segment':         ('privacyguard.pii.validators', 'is_mobile_segment'),
    'PHONE_PERSONAL_PREFIX_3':   ('privacyguard.pii.validators', 'PHONE_PERSONAL_PREFIX_3'),
    'PHONE_EXCLUDED_PREFIX_3':   ('privacyguard.pii.validators', 'PHONE_EXCLUDED_PREFIX_3'),
    'PHONE_EXCLUDED_PREFIX_4':   ('privacyguard.pii.validators', 'PHONE_EXCLUDED_PREFIX_4'),
    'apply_pii_redactions':      ('privacyguard.pii.pdf_adapter', 'apply_pii_redactions'),
    'collect_pii_rects':         ('privacyguard.pii.pdf_adapter', 'collect_pii_rects'),
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