"""
默认脱敏规则加载器 (PR-C6.5 从 main.py:166-238 迁出)

提供:
- DEFAULT_RULES: 规则名 → 正则 pattern 字典
- DEFAULT_RULES_META: 规则名 → mask 配置(mask_mode / mask_keep_prefix / mask_keep_suffix / mask_char)
- _v113_apply_rule_overrides(): v1.1.13 强制代码层默认(不依赖磁盘 config.json 漂移)

加载流程(模块级执行,加载时即完成):
  1. DEFAULT_RULES = {} / DEFAULT_RULES_META = {} 初始化
  2. _v113_apply_rule_overrides 函数定义(必须在 populate 前可调用)
  3. if config:从 config.get_redaction_rules() 读;else:硬编码 11 条默认规则
  4. populate 后调 _v113_apply_rule_overrides() 强制覆盖"日期时间"禁用 + 法定代表人 pattern

迁移说明(PR-C6.5):从 main.py:166-238 整块复制而来,行为零改动。
"""
from __future__ import annotations

from typing import Any, Dict

from secureredact.utils.config import config  # PR-C6.4:全局 config singleton


# === 默认规则库 + Mask 元数据 ===
# v1.1.11: 从配置读取,支持新旧两种格式
# v1.1.12: 同时构建 DEFAULT_RULES_META,提供每条规则的 mask_mode / mask_keep_prefix / mask_keep_suffix / mask_char
DEFAULT_RULES: Dict[str, str] = {}
DEFAULT_RULES_META: Dict[str, Dict[str, Any]] = {}


def _v113_apply_rule_overrides():
    """v1.1.13 强制代码层默认 — 不依赖磁盘 config.json 漂移.

    修复场景: 即使磁盘 config.json 中 '日期时间.enabled=true' 或
    '法定代表人.pattern' 被改回旧版, 代码层仍强制以下行为:
      1) '日期时间' 规则强制禁用 (用户决策: 选 B 不脱敏, 过度脱敏风险高于收益)
      2) '法定代表人' pattern 强制覆盖为带正向 lookahead 的版本,
         防止贪婪匹配把 '继续主张'/'继承' 等普通动词当人名 mask
    """
    DEFAULT_RULES.pop("日期时间", None)
    DEFAULT_RULES_META.pop("日期时间", None)
    DEFAULT_RULES["法定代表人"] = (
        r"法定代表人\s*[::：]?\s*[一-龥]{2,4}(?:·[一-龥]{2,4})?"
        r"(?=[的之及与和按于在跟同向对为由被让等,，。；;）)\]】\s]|$)"
    )


if config:
    _rules_from_config = config.get_redaction_rules()
    for name, rule in _rules_from_config.items():
        if isinstance(rule, dict):
            DEFAULT_RULES[name] = rule.get("pattern", "")
            DEFAULT_RULES_META[name] = {
                "mask_mode": rule.get("mask_mode", "default"),
                "mask_keep_prefix": int(rule.get("mask_keep_prefix", 0) or 0),
                "mask_keep_suffix": int(rule.get("mask_keep_suffix", 0) or 0),
                "mask_char": str(rule.get("mask_char", "*") or "*"),
            }
        else:
            # 旧格式兼容: 仅 pattern 字符串, 无 mask 信息
            DEFAULT_RULES[name] = str(rule)
            DEFAULT_RULES_META[name] = {}
    # v1.1.13: 强制代码层默认 — 不依赖磁盘 config.json 漂移
    _v113_apply_rule_overrides()
else:
    DEFAULT_RULES.update({
        "身份证号": r"(?<!\d)([1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]|\d{15})(?!\d)",
        "手机号码": r"(?<!\d)(1[3-9]\d{9})(?!\d)",
        "日期时间": r"\d{4}[年\-\.]\d{1,2}[月\-\.]\d{1,2}[日]?",
        "电子邮箱": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "银行卡号": r"(?<!\d)([1-9]\d{12,18})(?!\d)",
        "印章": "__SEAL_DETECTION__",  # v1.1.11: 印章检测特殊标记
        # v1.1.11: 扩展规则 — 起诉讼书场景下常见漏脱敏字段
        "地址（含门牌号）": r"(?:[一-龥]{0,15}?)(?:省|市|自治区|特别行政区)[一-龥\d\s,()（）\-\w]{4,60}?\d+\s*号",
        "固定电话": r"(?<!\d)0[\w]{2,3}[-\s]?[\w]{7,8}(?!\d)",
        "法定代表人": r"法定代表人\s*[::：]?\s*[一-龥]{2,4}(?:·[一-龥]{2,4})?(?=[的之及与和按于在跟同向对为由被让等,，。；;）)\]】\s]|$)",
        # v1.1.12: 统一社会信用代码 - 仅 Word 路径生效,通过 pdf_excluded_rules 隔离 PDF
        # 首字符数字,后续 16-17 位 GB 32100-2015 字符集(排除 I/O/Z/S/V)
        "统一社会信用代码": r"(?<![A-Z0-9])([0-9][0-9A-HJ-NPQRTUWXY]{16,17})(?![A-Za-z0-9])",
        # v1.1.12: 公司名 - 中文公司/企业名称, jieba 不能识别所有公司字号
        "公司名": r"[一-龥]{2,40}(?:有限公司|股份有限公司|有限责任公司|集团公司|控股公司|合伙企业|公司|中心)",
    })
    DEFAULT_RULES_META.update({
        "身份证号": {"mask_mode": "default", "mask_keep_prefix": 6, "mask_keep_suffix": 4, "mask_char": "*"},
        "手机号码": {"mask_mode": "default", "mask_keep_prefix": 3, "mask_keep_suffix": 4, "mask_char": "*"},
        "日期时间": {"mask_mode": "default", "mask_keep_prefix": 0, "mask_keep_suffix": 0, "mask_char": "*"},
        "电子邮箱": {"mask_mode": "email",   "mask_keep_prefix": 0, "mask_keep_suffix": 0, "mask_char": "*"},
        "银行卡号": {"mask_mode": "default", "mask_keep_prefix": 4, "mask_keep_suffix": 4, "mask_char": "*"},
        "印章":     {"mask_mode": "default", "mask_keep_prefix": 0, "mask_keep_suffix": 0, "mask_char": "*"},
        "地址（含门牌号）": {"mask_mode": "default", "mask_keep_prefix": 8, "mask_keep_suffix": 2, "mask_char": "*"},
        "固定电话": {"mask_mode": "default", "mask_keep_prefix": 0, "mask_keep_suffix": 4, "mask_char": "*"},
        "法定代表人": {"mask_mode": "name",    "mask_keep_prefix": 1, "mask_keep_suffix": 0, "mask_char": "*"},
        "统一社会信用代码": {"mask_mode": "default", "mask_keep_prefix": 4, "mask_keep_suffix": 4, "mask_char": "*"},
        "公司名": {"mask_mode": "default", "mask_keep_prefix": 0, "mask_keep_suffix": 0, "mask_char": "*"},
    })
    # v1.1.13: 强制代码层默认 — 不依赖磁盘 config.json 漂移
    _v113_apply_rule_overrides()


__all__ = ["DEFAULT_RULES", "DEFAULT_RULES_META", "_v113_apply_rule_overrides"]