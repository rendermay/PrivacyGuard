"""PrivacyGuard PII 验证器子包（NUM-01/02/03 纯函数实现）。"""
from importlib import import_module


__all__ = [
    'validate_18_id',
    'validate_15_id',
    'upgrade_15_to_18',
    'compute_check_digit',
    'is_mobile_segment',
    'PHONE_PERSONAL_PREFIX_3',
    'PHONE_EXCLUDED_PREFIX_3',
    'PHONE_EXCLUDED_PREFIX_4',
]


_LAZY_IMPORTS = {
    'validate_18_id':           ('privacyguard.pii.validators.id_card', 'validate_18'),
    'validate_15_id':           ('privacyguard.pii.validators.id_card', 'validate_15'),
    'upgrade_15_to_18':         ('privacyguard.pii.validators.id_card', 'upgrade_15_to_18'),
    'compute_check_digit':      ('privacyguard.pii.validators.id_card', 'compute_check_digit'),
    'is_mobile_segment':        ('privacyguard.pii.validators.phone_segment', 'is_mobile_segment'),
    'PHONE_PERSONAL_PREFIX_3':  ('privacyguard.pii.validators.phone_segment', 'PHONE_PERSONAL_PREFIX_3'),
    'PHONE_EXCLUDED_PREFIX_3':  ('privacyguard.pii.validators.phone_segment', 'PHONE_EXCLUDED_PREFIX_3'),
    'PHONE_EXCLUDED_PREFIX_4':  ('privacyguard.pii.validators.phone_segment', 'PHONE_EXCLUDED_PREFIX_4'),
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