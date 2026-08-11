"""PrivacyGuard PII 自动识别子系统（v38.x Phase 1）。

本包承载隐私信息自动识别的核心能力：
- 身份证号（中国大陆 18 位 GB 11643 + 15 位历史号）
- 手机号（中国大陆 MIIT 号段白名单 + IoT/卫星排除）
- 文字层 + 图片块 + 整页 OCR 三路径接入（Plan 01-03 Task 1 接管 OCR）
- 真脱敏（PyMuPDF add_redact_annot + apply_redactions(IMAGE_PIXELS)）
- 纯本地识别（ENGINE-08 零网络）

懒加载入口：禁止在 `import privacyguard` 时拉起 privacyguard.pii.* 子模块。
新增 PII 子模块必须在 _LAZY_IMPORTS 注册；严禁顶层 `from privacyguard.pii.x import ...`。
"""
from importlib import import_module


# 默认规则版本（rules.json 缺失 / 解析失败时的 fallback）
RULES_VERSION_DEFAULT = "2026-Q1"


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
    'RULES_VERSION_DEFAULT',
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