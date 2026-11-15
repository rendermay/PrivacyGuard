"""规则冲突消解 —— 同一段文本被多条规则命中时只保留优先级最高的一条。

背景 (P0-5):
    默认规则里「身份证号」「统一社会信用代码」「银行卡号」的字符集高度重叠:
      身份证号         15 位 或 18 位(带出生日期校验)
      统一社会信用代码  17-18 位(数字 + 大写字母, 排除 I/O/Z/S/V)
      银行卡号         13-19 位纯数字
    同一个 18 位数字串(如 110101199001011234)会被 3 条规则同时命中 ->
    命中数翻 3 倍、遮蔽边界不一致、命中统计失真。

策略(零回归风险):
    只对「数字类标识符」规则做冲突消解; 公司名 / 地址 / 邮箱 / 法定代表人 /
    自定义关键词 等规则的命中行为完全不变。

优先级(数字越小越优先):
    身份证号 > 统一社会信用代码 > 银行卡号
      身份证号带出生日期校验, 格式最具体, 一旦命中即可确定;
      USCC 次之(17-18 位, 结构比纯数字串明确);
      银行卡号 13-19 位纯数字最宽泛, 兜底。
"""

from typing import Dict, Iterable, List, Mapping, Optional, Sequence

RULE_CONFLICT_PRIORITY: Dict[str, int] = {
    "身份证号": 10,
    "统一社会信用代码": 20,
    "银行卡号": 30,
}


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """半开区间 [start, end) 是否相交。"""
    return a_start < b_end and b_start < a_end


def resolve_rule_conflicts(
    matches: Sequence[Mapping],
    priority_map: Optional[Mapping[str, int]] = None,
) -> List[Mapping]:
    """消解多条规则对同一段文本的重复命中。

    Args:
        matches: 命中列表, 每项至少包含 rule_name / start / end。
        priority_map: 规则名 -> 优先级(数字越小越优先)。
                     传 None 时用默认的 RULE_CONFLICT_PRIORITY。

    Returns:
        消解后的新列表(不修改入参)。参与消解的规则中, 同一区间(或有
        包含关系)只保留优先级最高的一条; 其他规则的命中原样保留。
    """
    if not matches:
        return list(matches)

    prio: Mapping[str, int] = (
        RULE_CONFLICT_PRIORITY if priority_map is None else priority_map
    )
    if not prio:
        return list(matches)

    conflicting = [
        m
        for m in matches
        if isinstance(m, dict)
        and m.get("rule_name") in prio
        and isinstance(m.get("start"), int)
        and isinstance(m.get("end"), int)
        and m["start"] < m["end"]
    ]
    if len(conflicting) < 2:
        return list(matches)

    # 优先级最高者先占位; 同优先级时更长的命中优先(信息量更大)
    ordered = sorted(
        conflicting,
        key=lambda m: (
            prio[m["rule_name"]],
            -(m["end"] - m["start"]),
            m["start"],
        ),
    )

    kept: List[Mapping] = []
    for m in ordered:
        if any(_overlaps(m["start"], m["end"], k["start"], k["end"]) for k in kept):
            # 与已保留的命中重叠 -> 丢弃(低优先级 / 更宽泛的规则)
            continue
        kept.append(m)

    if len(kept) == len(conflicting):
        return list(matches)

    kept_ids = {id(m) for m in kept}
    result: List[Mapping] = []
    for m in matches:
        if isinstance(m, dict) and m.get("rule_name") in prio:
            if id(m) in kept_ids:
                result.append(m)
        else:
            result.append(m)
    return result


__all__ = ["RULE_CONFLICT_PRIORITY", "resolve_rule_conflicts"]