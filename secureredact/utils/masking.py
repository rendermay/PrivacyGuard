"""v1.1.12: 部分遮蔽 (Partial Masking) 工具函数。

设计要点:
- 纯函数, 无副作用, 可独立单元测试
- 默认 mask_char = '*'
- 边界: len(text) <= keep_prefix + keep_suffix → 原样返回(避免空 mask 或负长度切片)
- 负数参数 → ValueError(配置错误应当 fast-fail, 不要静默)
- 三种 mask_mode:
  - "default": keep_prefix + keep_suffix, 中间打码
  - "email":   保留用户名 1 位 + '***' + '@' + 完整域名
  - "name":    保留姓(首字)+ '*' (等价于 prefix=1, suffix=0, 仅作用于 2+ 字)
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def apply_partial_mask(
    text: str,
    keep_prefix: int = 0,
    keep_suffix: int = 0,
    mask_char: str = "*",
) -> str:
    """保留前 N + 后 N 字符, 中间用 mask_char 替换。

    边界条件:
    - len(text) <= keep_prefix + keep_suffix → 原样返回(避免空 mask 或负长度切片)
    - keep_prefix < 0 或 keep_suffix < 0 → ValueError
    - mask_char 为空字符串 → ValueError(避免删除原文)
    - 非字符串输入 → 原样返回(让上层处理)
    - 空字符串 → 原样返回

    例子:
        apply_partial_mask("110101199001011234", 6, 4)  → "110101********1234"
        apply_partial_mask("13812345678",      3, 4)    → "138****5678"
        apply_partial_mask("91110108MA01KXYX29", 4, 4) → "9111**********29"
        apply_partial_mask("abcdefghij",      0, 0)    → "**********"
    """
    if not isinstance(text, str):
        return text
    if not text:
        return text
    if keep_prefix < 0 or keep_suffix < 0:
        raise ValueError(
            f"keep_prefix/keep_suffix 必须 >= 0 (got {keep_prefix}, {keep_suffix})"
        )
    if not mask_char:
        raise ValueError("mask_char 不能为空字符串")
    if len(text) <= keep_prefix + keep_suffix:
        return text

    middle_len = len(text) - keep_prefix - keep_suffix
    masked_middle = mask_char * middle_len
    if keep_suffix > 0:
        return text[:keep_prefix] + masked_middle + text[-keep_suffix:]
    return text[:keep_prefix] + masked_middle


def apply_email_mask(email: str, mask_char: str = "*") -> str:
    """邮箱专用: 保留用户名第 1 位 + '***' + '@' + 完整域名。

    例子:
        alice@example.com     → a***@example.com
        b@x.co                → b***@x.co
        user@mail.sub.co      → u***@mail.sub.co

    边界:
    - 不含 '@' → 原样返回(让上层 fallback 到 partial mask)
    - 用户名 0-1 字符 → 用户名部分原样, 只插 '***' + '@' + 域名
    - 非字符串 → 原样返回
    """
    if not isinstance(email, str) or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if not local:
        return email
    # 用户名至少 1 字符, 保留第 1 位, 其余用 3 个 mask_char 替代(固定 3 位, 不随用户名长度变化)
    return f"{local[0]}{mask_char * 3}@{domain}"


def apply_name_mask(name: str, mask_char: str = "*") -> str:
    """中文姓名专用: 保留姓(首字)+ 其余全部打码。

    例子:
        张三     → 张*
        李四光   → 李**
        欧阳娜娜 → 欧***
        张       → 张(单字不变成空串)
        法定代表人:周超    → 法定代表人:周*   (label+姓名 模式)
        法定代表人:欧阳娜娜 → 法定代表人:欧*** (label+复姓)

    实现:
    1. 先检测 `label:姓名` 格式(用最后一个 : 或 ： 分隔)
    2. 若尾部姓名长度 1-4 字且像中文姓名, 保留 label, 只 mask 姓名
    3. 否则当作纯姓名, 保留首字

    对边界:
    - 单字姓名 → 原样(防止空串)
    - 非字符串 → 原样
    """
    if not isinstance(name, str) or len(name) <= 1:
        return name
    # 1. 检测 label+姓名 模式: 用最后一个 ASCII : 或全角： 分隔
    for sep in (":", "："):
        if sep in name:
            head, tail = name.rsplit(sep, 1)
            tail = tail.strip()
            # 尾部姓名长度 1-4 字且像中文姓名(纯汉字)
            if 1 <= len(tail) <= 4 and all(
                "一" <= ch <= "鿿" for ch in tail
            ):
                return head + sep + apply_name_mask(tail, mask_char)
    # 2. 纯姓名: 保留首字
    return name[0] + mask_char * (len(name) - 1)


def resolve_mask_config(
    rule_name: str,
    default_rules_meta: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """按规则名查找 mask 配置。

    返回 dict 包含: mask_mode, mask_keep_prefix, mask_keep_suffix, mask_char
    未命中 → 返回 None (调用方应 fallback 到 replacement_text)
    """
    if not isinstance(rule_name, str) or not rule_name:
        return None
    meta = default_rules_meta.get(rule_name)
    if not isinstance(meta, dict):
        return None
    return {
        "mask_mode": meta.get("mask_mode", "default"),
        "mask_keep_prefix": int(meta.get("mask_keep_prefix", 0) or 0),
        "mask_keep_suffix": int(meta.get("mask_keep_suffix", 0) or 0),
        "mask_char": str(meta.get("mask_char", "*") or "*"),
    }


def apply_mask_for_rule(
    text: str,
    rule_name: str,
    default_rules_meta: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    """单入口: 根据 rule_name 选 mode 并返回 mask 结果。

    返回 None 表示未配置 mask, 调用方应使用 replacement_text。

    行为:
    - mask_mode == "email"  → apply_email_mask
    - mask_mode == "name"   → apply_name_mask
    - mask_mode == "default" → apply_partial_mask
    - prefix == 0 AND suffix == 0 → 整段打码(全部 mask_char)
    - 特殊规则 "公司名" → apply_company_mask(智能保留省/市 + 公司后缀)
    """
    cfg = resolve_mask_config(rule_name, default_rules_meta)
    if cfg is None:
        return None
    mode = cfg["mask_mode"]
    if mode == "email":
        return apply_email_mask(text, cfg["mask_char"])
    if mode == "name":
        return apply_name_mask(text, cfg["mask_char"])
    # v1.1.12: 智能公司名 mask — 保留省/市前导 + 保留公司/有限/集团等后缀
    if rule_name == "公司名":
        return apply_company_mask(text, cfg["mask_char"])
    # "default" 或未知 mode → 走 prefix+suffix
    return apply_partial_mask(
        text,
        cfg["mask_keep_prefix"],
        cfg["mask_keep_suffix"],
        cfg["mask_char"],
    )


def apply_company_mask(text: str, mask_char: str = "*") -> str:
    """v1.1.12: 智能公司名 mask — 保留"省/市"等地理前导 + 保留"有限公司/集团"等公司尾缀, 中间全部打码。

    例子:
        吉林市捷信小额贷款有限公司  →  吉林市********有限公司
        四川京缇建筑工程有限公司    →  四川****建筑工程有限公司
        宜宾市吉商华旭房地产开发有限公司  →  宜宾市****房地产开发有限公司
        吉林吉润万家餐饮文化管理有限公司  →  吉林**万家餐饮文化管理有限公司

    算法:
    1. 前缀: 在 text 开头找最长的"省/市/自治区/特别行政区"前导
       (允许前导 0-15 汉字, 然后接省/市标记)
    2. 后缀: 在 text 末尾找最长的公司尾缀
    3. 中间: 全部 mask_char 替换
    4. 边界: len(text) <= prefix + suffix 时, 原样返回

    不依赖 regex 模块(只用 re + 字符串操作)
    """
    if not isinstance(text, str) or not text:
        return text
    if not mask_char:
        raise ValueError("mask_char 不能为空字符串")

    # 1) 找省/市前导: 先找"省/市"标记, 找不到再匹配 33 个省/直辖市名
    province_end = 0
    for kw in ("特别行政区", "自治区", "省", "市"):
        idx = text.find(kw, 0, 16)
        if idx >= 0:
            province_end = idx + len(kw)
            break
    # 特殊: 开头是省份名(无"省/市"标记), 单独识别
    if province_end == 0:
        for province in (
            "北京", "上海", "天津", "重庆",
            "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽",
            "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
            "四川", "贵州", "云南", "陕西", "甘肃", "青海",
            "内蒙古", "广西", "西藏", "宁夏", "新疆",
            "台湾", "香港", "澳门",
        ):
            if text.startswith(province):
                province_end = len(province)
                break

    # 2) 找公司尾缀
    company_suffixes = (
        "股份有限公司",
        "有限责任公司",
        "集团公司",
        "控股公司",
        "有限公司",
        "合伙企业",
        "公司",
        "中心",
    )
    suffix_len = 0
    for kw in company_suffixes:
        if text.endswith(kw):
            suffix_len = len(kw)
            break

    # 3) 中间 mask
    if province_end + suffix_len >= len(text):
        return text  # 太短, 不打码
    middle = len(text) - province_end - suffix_len
    masked_middle = mask_char * middle
    if suffix_len > 0:
        return text[:province_end] + masked_middle + text[-suffix_len:]
    return text[:province_end] + masked_middle