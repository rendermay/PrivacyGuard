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
from typing import FrozenSet, Iterable, List, Optional, Tuple

# ---- 强前缀词: 人名前置称谓/角色 ----
# 紧邻出现在候选名前面 (中间可夹空白/标点)
STRONG_PREFIX_TOKENS: FrozenSet[str] = frozenset({
    # 当事人/诉讼地位
    "原告", "被告", "第三人", "上诉人", "被上诉人", "申请人", "被申请人",
    "起诉人", "反诉人", "申诉人", "被申诉人", "申请执行人", "被执行人",
    "利害关系人", "当事人", "关系人",
    # 合同/债权角色 (v1.1.14: 法律文书高频当事人并列名单)
    # 动机: '甲方与xxx、xxx之间借款合同纠纷' 格式中, 名单内姓名应被识别
    "甲方", "乙方", "丙方", "丁方", "戊方", "己方", "庚方", "辛方", "壬方", "癸方",
    "借款人", "出借人", "贷款人", "债务人", "债权人",
    "保证人", "连带保证人", "一般保证人", "担保人", "反担保人",
    "抵押人", "抵押权人", "出质人", "质权人",
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
# v1.1.14: 加顿号(、)、间隔号(·)、斜杠(/／)、破折号(—–)、连接号(-)、
# 和号(&＆) — 法律文书并列名单标准分隔符是顿号(甲方与李秋实、孙毅之间);
# 不加的话名单里第二个及之后的姓名无法被前缀上下文识别。
_INSIDE_CHARS = set(" \t\n\r　()（）.,，。；;;《》<>\"'""''、·/／—–-&＆")


def _name_has_prefix_context(
    text: str,
    name: str,
    prefix_tokens: FrozenSet[str] = STRONG_PREFIX_TOKENS,
) -> bool:
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
        for prefix in prefix_tokens:
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


def _has_context(
    text: str,
    name: str,
    prefix_tokens: FrozenSet[str] = STRONG_PREFIX_TOKENS,
) -> bool:
    """判断 name 在 text 中是否至少有一处强上下文 (前置/后置/标签)."""
    if not text or not name:
        return False
    if _name_has_label_context(text, name):
        return True
    if _name_has_prefix_context(text, name, prefix_tokens):
        return True
    if _name_has_suffix_context(text, name):
        return True
    return False


# 列举式上下文分隔符 (v1.1.14)
# 用于 '甲方与 A、B、C 之间借款合同纠纷' 类并列名单的传递识别:
# A 由 prefix 紧邻路径识别, B/C 由 '已识别 candidate + 列举符 + candidate' 传递识别
_ENUM_SEPS: Tuple[str, ...] = ("、", "，", ",", ";", "；")
_ENUM_SEPS_SET = frozenset(_ENUM_SEPS)


# 枚举式前缀连接的连接词 (prefix + 连接词 + list + 收尾词)
_ENUM_CONNECTORS: Tuple[str, ...] = ("与", "和", "跟", "同", "及")
_ENUM_TERMINATORS: Tuple[str, ...] = (
    "之间", "于", "跟", "和", "与", "的", "，", ",", "。", ";", "；", "$",
)


def _build_enum_list_re(
    prefix_tokens: FrozenSet[str],
) -> "re.Pattern[str]":
    """构造枚举式 list 匹配模式.

    pattern: (?P<prefix>甲方|乙方|...) (?P<connector>与|和|跟|同|及) (?P<list>...) (?P<terminator>之间|于|...|$)

    - prefix alternation 按 token 长度倒序 (避免 '审判员' 抢 '人民陪审员' 的匹配)
    - 缓存: 同一 prefix_tokens 集合复用编译结果
    """
    if prefix_tokens in _ENUM_LIST_RE_CACHE:
        return _ENUM_LIST_RE_CACHE[prefix_tokens]
    sorted_tokens = sorted(prefix_tokens, key=len, reverse=True)
    alt_prefix = "|".join(re.escape(p) for p in sorted_tokens)
    alt_conn = "|".join(re.escape(c) for c in _ENUM_CONNECTORS)
    # terminator 长度倒序同样重要: '之间' 应先于 '于'/'的' 匹配
    sorted_terms = sorted(_ENUM_TERMINATORS, key=len, reverse=True)
    alt_term = "|".join(re.escape(t) for t in sorted_terms)
    # list 内容: 1-400 字符 (防 DoS), 不含终止符
    # list 末尾必须紧接 terminator (用 lookahead 避免吞掉 terminator 字符)
    pat = re.compile(
        r"(?P<prefix>" + alt_prefix + r")"
        r"\s*(?P<connector>" + alt_conn + r")\s*"
        r"(?P<list>[^。；;！!？?\n]{1,400}?)"
        r"(?=(?P<terminator>" + alt_term + r"))"
    )
    _ENUM_LIST_RE_CACHE[prefix_tokens] = pat
    return pat


_ENUM_LIST_RE_CACHE: dict = {}


def _name_has_enumeration_prefix_context(
    text: str,
    name: str,
    prefix_tokens: FrozenSet[str],
) -> bool:
    """枚举式前缀上下文 (v1.1.14).

    匹配 '甲方/乙方/原告/... 与/和 A、B、C 之间/于/...' 结构中的姓名.
    用于补强: 当前缀词后面跟连接词再跟列表(列表内有名字), 即使名字前面
    不是 prefix 而是其他汉字(公司名), 也能识别.

    严格约束:
    - 必须 prefix 词在前 (prefix_tokens 子集)
    - '与'/'和'/'跟'/'同'/'及' 连接
    - 列表内容长度 1-400 字 (防 DoS)
    - 列表按 _ENUM_SEPS 切分, name 必须精确匹配某元素
      (或某元素以 name 开头/结束, 处理 '李某某'/'徐十三' OCR 容差)
    """
    if not name or not text or not prefix_tokens:
        return False
    pat = _build_enum_list_re(prefix_tokens)
    for m in pat.finditer(text):
        list_content = m.group("list")
        items = [s.strip() for s in re.split(r"[、,，;；]", list_content) if s.strip()]
        if not items:
            continue
        for item in items:
            if item == name:
                return True
            # OCR 容差: '李某某'/'徐十三' 等模糊匹配
            if (len(item) >= len(name)
                    and len(item) <= len(name) + 4
                    and (item.startswith(name) or item.endswith(name))):
                return True
    return False


def _is_enum_adjacent(
    text: str,
    rec_pos: int,
    recognized: str,
    name: str,
) -> bool:
    """name 是否在 'recognized + 列举符 + ... + name' 结构里 (中间仅 _INSIDE_CHARS 或列举符).

    严格约束 (防误识):
    - between 不能为空 (紧贴不算并列)
    - between 必须以列举符开头 (不能是汉字或普通标点)
    - between 中不能有汉字 (除已识别的 candidate, 此处不感知)
    """
    i = rec_pos + len(recognized)
    name_pos = text.find(name, i)
    if name_pos < 0:
        return False
    between = text[i:name_pos]
    if not between:
        return False
    if between[0] not in _ENUM_SEPS_SET:
        return False
    allowed = _INSIDE_CHARS | _ENUM_SEPS_SET
    return all(c in allowed for c in between)


def _build_prefix_tokens(
    extra: Optional[Iterable[str]],
) -> FrozenSet[str]:
    """合并 STRONG_PREFIX_TOKENS 与额外 token, 返回新 frozenset.

    - extra 为 None / 空 → 返回默认 STRONG_PREFIX_TOKENS (避免不必要的 frozenset 构造)
    - extra 为可迭代对象 → 归一化为去空白字符串, 与默认合并
    - 非 str 元素静默跳过 (健壮性: config.json 可能脏数据)
    """
    if not extra:
        return STRONG_PREFIX_TOKENS
    extras: Tuple[str, ...] = tuple(
        t.strip() for t in extra if isinstance(t, str) and t.strip()
    )
    if not extras:
        return STRONG_PREFIX_TOKENS
    return STRONG_PREFIX_TOKENS | frozenset(extras)


def filter_names_by_context(
    text: Optional[str],
    candidates: List[str],
    extra_prefix_tokens: Optional[Iterable[str]] = None,
) -> List[str]:
    """过滤 candidates, 仅保留在 text 中有强上下文的候选.

    - 输入空 / None / 非字符串: 返回 []
    - candidates 非 list: 返回 []
    - 空 candidates: 返回 []
    - 去重: 同一名字仅返回一次
    - 排序: 按首次出现位置升序 (text 中越靠前越先返回); 同一位置保持输入序
    - extra_prefix_tokens (v1.1.14): 额外注入的强前缀词, 通常来自 config.json 的
      redaction.name_context.extra_tokens。接受 None / list / frozenset / tuple
      任一可迭代对象。None / 空 → 使用 STRONG_PREFIX_TOKENS 默认集合。

    上下文识别 (三阶段, 迭代到不动点):
    0. 枚举式前缀 (v1.1.14): '甲方/乙方/原告/... 与 A、B、C 之间/于/...' 结构
       — 适用于并列名单中第一个名字前面不是 prefix 而是公司名等汉字
    1. 强前缀 / 强后缀 / 强标签路径 (现有)
    2. 列举式传递 (v1.1.14): 若 A 已被识别, 且 'A + 列举符(顿号/逗号/分号) +
       中间仅 _INSIDE_CHARS + B' 结构存在, B 也算有上下文。多元素列表
       (甲方与 A、B、C 之间) 通过迭代传递识别。
    """
    if not isinstance(text, str) or not text:
        return []
    if not isinstance(candidates, list):
        return []

    prefix_tokens = _build_prefix_tokens(extra_prefix_tokens)

    seen: set = set()
    # (input_idx, first_pos, name); 按 first_pos 升序排序后输出
    positioned: List[Tuple[int, int, str]] = []

    def _try_add(input_idx: int, name: str) -> bool:
        if name in seen:
            return False
        first_pos = text.find(name)
        if first_pos < 0:
            return False
        seen.add(name)
        positioned.append((input_idx, first_pos, name))
        return True

    # 阶段 0: 枚举式前缀 (v1.1.14) — prefix + 与/和 + list + 之间/于/...
    for input_idx, name in enumerate(candidates):
        if not isinstance(name, str) or not name:
            continue
        if _name_has_enumeration_prefix_context(text, name, prefix_tokens):
            _try_add(input_idx, name)

    # 阶段 1: 现有 prefix/suffix/label 路径
    for input_idx, name in enumerate(candidates):
        if not isinstance(name, str) or not name:
            continue
        if _has_context(text, name, prefix_tokens):
            _try_add(input_idx, name)

    # 阶段 2: 列举式传递 (v1.1.14) — 迭代到不动点
    # 防死循环: positioned 长度恒定增长 (只在 _try_add 成功时改), 自然终止
    changed = True
    while changed:
        changed = False
        for input_idx, name in enumerate(candidates):
            if not isinstance(name, str) or not name:
                continue
            if name in seen:
                continue
            # 检查 name 是否紧邻某个已识别的 candidate (中间仅 _INSIDE_CHARS / 列举符)
            for _, rec_pos, recognized in positioned:
                if rec_pos >= text.find(name):
                    # 已识别 candidate 必须在 name 之前才有效
                    continue
                if _is_enum_adjacent(text, rec_pos, recognized, name):
                    if _try_add(input_idx, name):
                        changed = True
                    break

    positioned.sort(key=lambda t: (t[1], t[0]))
    return [name for _, _, name in positioned]


__all__ = [
    "STRONG_PREFIX_TOKENS",
    "STRONG_SUFFIX_TOKENS",
    "filter_names_by_context",
]