# -*- coding: utf-8 -*-
"""白名单片段级豁免的纯文本拆分逻辑.

v38: 用于 worker filter 阶段, 把 hit 文本按白名单子串位置切成保留片段.
"""
from __future__ import annotations

from typing import List, Tuple


def _split_text_by_whitelist(
    text: str,
    whitelist: List[str],
) -> List[Tuple[int, int, str]]:
    """按白名单子串位置把 text 切成若干保留片段.

    Args:
        text: hit 原文
        whitelist: 当前生效的白名单条目 (substring 匹配)

    Returns:
        [(start_offset, end_offset, text_span), ...]
        - offset 是 Python str 索引 (左闭右开)
        - 全段被白名单覆盖 → []
        - text 不含任何 wl → [(0, len(text), text)]
        - 空 text + 空 whitelist → [(0, 0, "")]
        - 空 text + 非空 whitelist → []

    Notes:
        - 空字符串 / 纯空格 wl 条目跳过 (store 层已 sanitize, 此处再次防御)
        - 收集阶段允许同一 wl 内重叠匹配 (idx = pos + 1)
        - 合并阶段: 跨条目 / 跨位置重叠时, 若新区间起点与已合并区间起点对齐
          则扩展; 若新区间起点严格落在已合并区间内部则忽略, 避免链式扩展
          把后段保留片段吞掉 (典型场景: ["aa","aaa"] 匹配 "aaaa" → 仅 (0,3)).
        - 单条目多次出现 → 每处都豁免
    """
    if not isinstance(text, str):
        return []
    if not isinstance(whitelist, list):
        return [(0, len(text), text)]

    if not whitelist:
        return [(0, len(text), text)]

    # 非空 whitelist + 空 text: 无任何命中 → 无保留片段
    if not text:
        return []

    # 1) 收集所有 wl 命中区间 (允许 wl 内重叠)
    spans: List[Tuple[int, int]] = []
    for wl in whitelist:
        if not isinstance(wl, str):
            continue
        wl = wl.strip()
        if not wl:
            continue
        idx = 0
        while True:
            pos = text.find(wl, idx)
            if pos < 0:
                break
            spans.append((pos, pos + len(wl)))
            idx = pos + 1  # 允许重叠检测

    if not spans:
        return [(0, len(text), text)]

    # 2) 合并区间: 起点对齐的区间合并; 起点严格落在已有区间内的忽略.
    spans.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in spans:
        if not merged:
            merged.append((s, e))
            continue
        prev_s, prev_e = merged[-1]
        if s > prev_e:
            # 完全在后 → 新建一段
            merged.append((s, e))
        elif s < prev_s:
            # sort 后理论上不应发生, 防御性添加
            merged.append((s, e))
        elif s == prev_s:
            # 起点对齐 → 取更长的尾端
            merged[-1] = (prev_s, max(prev_e, e))
        elif s < prev_e:
            # 起点严格落在已合并区间内部 → 跳过, 防止链式扩展
            continue
        else:  # s == prev_e
            # 紧邻 → 拼接
            merged[-1] = (prev_s, e)

    # 3) 取反集
    kept: List[Tuple[int, int, str]] = []
    cursor = 0
    n = len(text)
    for s, e in merged:
        if s > cursor:
            kept.append((cursor, s, text[cursor:s]))
        cursor = max(cursor, e)
    if cursor < n:
        kept.append((cursor, n, text[cursor:n]))

    return kept
