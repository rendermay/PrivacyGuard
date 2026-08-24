# -*- coding: utf-8 -*-
"""姓名上下文匹配 — 区分真名 vs jieba nr 误报 (v1.1.12).

设计思路 (方案 B 双轨制):
- 强前缀词 (原告/被告/经理/审判员/证人/...): 人名前置, 紧邻出现
- 强后缀词 (先生/女士/同志/经理/教授/...): 人名后置, 紧邻出现
- 强标签模式: 角色词 + (冒号/全角冒号) + 名字  (如 "原告：周强")

API:
- filter_names_by_context(text, candidates) -> List[str]
  返回在原文中**至少有一处上下文匹配**的候选. 保持去重保序.

匹配语义:
- 紧邻: 中间可夹空白/常见标点, 但不可夹汉字 (避免跨段匹配)
- 子串匹配在 token 文本级别 (避免重复字符串扫描)

可扩展性:
- 词表由本模块默认提供; 可由 BlackWhiteListStore / config.json 注入额外词表
"""
from __future__ import annotations

import re
from typing import FrozenSet, List, Optional, Tuple

# ---- 强前缀词: 人名前置称谓/角色 ----
# 紧邻出现在候选名前面 (中间可夹空白/标点)
STRONG_PREFIX_TOKENS: FrozenSet[str] = frozenset({
    # 当事人/诉讼地位
    "原告", "被告", "第三人", "上诉人", "被上诉人", "申请人", "被申请人",
    "起诉人", "反诉人", "申诉人", "被申诉人", "申请执行人", "被执行人",
    "利害关系人", "当事人", "关系人",
    # 法定/委托代理身份
    "法定代表人", "法定代理人", "委托代理人", "诉讼代理人", "指定代理人",
    "委托诉讼代理人", "辩护人",
    # 司法角色
    "审判长", "审判员", "人民陪审员", "陪审员", "书记员",
    "证人", "鉴定人", "翻译人", "记录人", "律师", "辩护律师",
    # 公职/职务
    "检察官", "公诉人", "法官", "公证人",
    "经理", "董事", "总裁", "董事长", "局长", "处长", "科长", "主任",
    "书记", "院长", "校长", "队长", "馆长", "主席", "部长", "市长",
    "省长", "县长", "镇长", "村长", "行长", "监事", "财务总监",
    # 称谓
    "老师", "教授", "博士", "医生",
})

# ---- 强后缀词: 人名后置称谓/头衔 ----
# 紧邻出现在候选名后面 (中间可夹空白/标点)
STRONG_SUFFIX_TOKENS: FrozenSet[str] = frozenset({
    "先生", "女士", "同志",
    "律师", "教授", "老师", "博士", "医生",
    "经理", "董事", "总裁", "局长", "主任", "书记", "院长", "校长",
    "审判长", "审判员", "陪审员", "书记员", "检察官", "法官",
})

# ---- 强标签模式: 角色词 + (冒号/全角冒号) + 名字 ----
# 捕获 (role_token, name_candidate) 元组列表
_LABEL_PATTERN = re.compile(
    r"(原告|被告|第三人|上诉人|被上诉人|申请人|被申请人|起诉人|"
    r"反诉人|申诉人|被申诉人|法定代表人|法定代理人|委托代理人|"
    r"诉讼代理人|辩护人|证人|鉴定人|翻译人|记录人|经理|董事|"
    r"董事长|局长|书记|院长|校长|检察官|法官)\s*"
    r"[::：]\s*"
    r"([^\s,，。；;）)\]<>《》]+)"
)

# 紧邻允许的"夹层"字符 (空白 + 常见中文标点, 不含汉字)
_INSIDE_CHARS = set(" \t\n\r　()（）.,，。；;;《》<>\"'""''")


def _name_has_prefix_context(text: str, name: str) -> bool:
    """判断 name 在 text 中是否至少有一处被强前缀词前置."""
    if not name:
        return False
    idx = 0
    while True:
        pos = text.find(name, idx)
        if pos < 0:
            return False
        # name 前面找最近的非空白/标点边界
        before = text[:pos]
        # 在 before 中找最长后缀, 跳过 _INSIDE_CHARS, 看是否以强前缀词结尾
        end = len(before)
        while end > 0 and before[end - 1] in _INSIDE_CHARS:
            end -= 1
        if end == 0:
            idx = pos + 1
            continue
        # 在 before[0:end] 中找最长强前缀词结尾
        for prefix in STRONG_PREFIX_TOKENS:
            plen = len(prefix)
            if end >= plen and before[end - plen:end] == prefix:
                return True
        idx = pos + 1


def _name_has_suffix_context(text: str, name: str) -> bool:
    """判断 name 在 text 中是否至少有一处后接强后缀词."""
    if not name:
        return False
    idx = 0
    while True:
        pos = text.find(name, idx)
        if pos < 0:
            return False
        after_start = pos + len(name)
        after = text[after_start:]
        start = 0
        while start < len(after) and after[start] in _INSIDE_CHARS:
            start += 1
        if start >= len(after):
            idx = pos + 1
            continue
        # 在 after[start:] 中找最长强后缀词开头
        for suffix in STRONG_SUFFIX_TOKENS:
            slen = len(suffix)
            if after[start:start + slen] == suffix:
                return True
        idx = pos + 1


def _name_has_label_context(text: str, name: str) -> bool:
    """判断 name 是否被强标签模式 (原告: name) 触发."""
    for _, captured_name in _LABEL_PATTERN.findall(text):
        if captured_name == name or name in captured_name:
            return True
    return False


def _has_context(text: str, name: str) -> bool:
    """判断 name 在 text 中是否至少有一处强上下文 (前置/后置/标签)."""
    if not text or not name:
        return False
    if _name_has_label_context(text, name):
        return True
    if _name_has_prefix_context(text, name):
        return True
    if _name_has_suffix_context(text, name):
        return True
    return False


def filter_names_by_context(
    text: Optional[str],
    candidates: List[str],
) -> List[str]:
    """过滤 candidates, 仅保留在 text 中有强上下文的候选.

    - 输入空 / None / 非字符串: 返回 []
    - candidates 非 list: 返回 []
    - 空 candidates: 返回 []
    - 去重: 同一名字仅返回一次
    - 排序: 按首次出现位置升序 (text 中越靠前越先返回); 同一位置保持输入序
    """
    if not isinstance(text, str) or not text:
        return []
    if not isinstance(candidates, list):
        return []

    seen: set = set()
    positioned: List[Tuple[int, int, str]] = []  # (input_idx, first_pos, name)
    for input_idx, name in enumerate(candidates):
        if not isinstance(name, str) or not name:
            continue
        if name in seen:
            continue
        if _has_context(text, name):
            seen.add(name)
            first_pos = text.find(name)
            positioned.append((input_idx, first_pos, name))
    # 按 first_pos 升序, 同一位置按 input_idx
    positioned.sort(key=lambda t: (t[1], t[0]))
    return [name for _, _, name in positioned]


__all__ = [
    "STRONG_PREFIX_TOKENS",
    "STRONG_SUFFIX_TOKENS",
    "filter_names_by_context",
]