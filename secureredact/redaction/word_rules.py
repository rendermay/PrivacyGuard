"""
Word 替换规则归一化工具 (PR-C1.1 提取)

原 main.py:425 模块级函数,供 SettingsDialog / MainWindow 共同使用。
独立成模块避免循环依赖与 main.py 模块级 import 副作用。

来源:原 main.py 中 normalize_word_replace_rules(39 行),逐字搬迁,逻辑零改动。
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Union


def normalize_word_replace_rules(rules, default_replacement_text="[已脱敏]"):
    """规范化多字段替换规则（会话级规则，不自动持久化）。"""
    normalized = []
    if not isinstance(rules, list):
        return normalized

    fallback_text = default_replacement_text if isinstance(default_replacement_text, str) and default_replacement_text else "[已脱敏]"
    mode_alias = {
        "exact": "exact",
        "regex": "regex",
        "精确": "exact",
        "正则": "regex"
    }

    for item in rules:
        if not isinstance(item, dict):
            continue
        enabled = bool(item.get("enabled", True))
        raw_mode = str(item.get("mode", "exact")).strip().lower()
        mode = mode_alias.get(raw_mode, "exact")

        find_text = str(item.get("find", "")).strip()
        if not find_text:
            continue

        replace_text = item.get("replace")
        if replace_text is None or str(replace_text) == "":
            replace_text = fallback_text
        else:
            replace_text = str(replace_text)

        normalized.append({
            "enabled": enabled,
            "mode": mode,
            "find": find_text,
            "replace": replace_text
        })

    return normalized


def merge_word_matches_with_priority(text, rules, default_replacement_text,
                                     manual_matches=None, ocr_matches=None):
    """合并规则替换、手动脱敏、OCR 脱敏区间，优先级：规则 > 手动 > OCR。"""
    manual_matches = manual_matches or []
    ocr_matches = ocr_matches or []
    text_len = len(text) if isinstance(text, str) else 0
    fallback_text = default_replacement_text if isinstance(default_replacement_text, str) and default_replacement_text else "[已脱敏]"

    merged = []
    occupied_ranges = []

    def _append_candidates(candidates, source_name):
        for item in candidates:
            start = item.get("start")
            end = item.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            if start < 0 or end > text_len or start >= end:
                continue
            if _range_overlaps(start, end, occupied_ranges):
                continue

            replacement = item.get("replacement", fallback_text)
            if replacement is None:
                replacement = fallback_text
            if not isinstance(replacement, str):
                replacement = str(replacement)

            merged.append({
                "start": start,
                "end": end,
                "text": item.get("text", text[start:end] if isinstance(text, str) else ""),
                "replacement": replacement,
                "source": source_name,
                "mode": item.get("mode", "global"),
                "rule_name": item.get("rule_name", "")
            })
            occupied_ranges.append((start, end))

    _append_candidates(build_word_rule_matches(text, rules, fallback_text), "rule")
    _append_candidates(manual_matches, "manual")
    _append_candidates(ocr_matches, "ocr")
    merged.sort(key=lambda item: item["start"])
    return merged


def build_word_rule_matches(text, rules, default_replacement_text="[已脱敏]"):
    """根据规则查找文本匹配，执行策略：exact 优先于 regex，重叠先到先得。"""
    if not isinstance(text, str) or not text:
        return []

    normalized_rules = normalize_word_replace_rules(rules, default_replacement_text)
    selected = []
    occupied_ranges = []

    for target_mode in ("exact", "regex"):
        for rule_index, rule in enumerate(normalized_rules):
            if not rule.get("enabled", True) or rule.get("mode") != target_mode:
                continue

            pattern = re.escape(rule["find"]) if target_mode == "exact" else rule["find"]
            try:
                compiled = re.compile(pattern)
            except re.error:
                continue

            for matched in compiled.finditer(text):
                start = matched.start()
                end = matched.end()
                if start >= end:
                    continue
                if _range_overlaps(start, end, occupied_ranges):
                    continue

                selected.append({
                    "start": start,
                    "end": end,
                    "text": matched.group(0),
                    "replacement": rule["replace"],
                    "mode": target_mode,
                    "rule_index": rule_index,
                    "source": "rule"
                })
                occupied_ranges.append((start, end))

    selected.sort(key=lambda item: item["start"])
    return selected


def apply_rule_matches_to_text(text, matches):
    """将匹配区间应用到文本（倒序替换避免索引偏移）。"""
    if not isinstance(text, str) or not matches:
        return text

    output = text
    for match in sorted(matches, key=lambda item: item.get("start", 0), reverse=True):
        start = match.get("start")
        end = match.get("end")
        replacement = match.get("replacement", "")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < 0 or end > len(output) or start >= end:
            continue
        if replacement is None:
            replacement = ""
        if not isinstance(replacement, str):
            replacement = str(replacement)
        output = output[:start] + replacement + output[end:]
    return output


def apply_word_rules_to_text(text, rules, default_replacement_text="[已脱敏]"):
    """直接按规则替换文本并返回替换结果。"""
    matches = build_word_rule_matches(text, rules, default_replacement_text)
    return apply_rule_matches_to_text(text, matches)


def _range_overlaps(start, end, ranges):
    """判断区间是否与已有区间重叠。"""
    for s, e in ranges:
        if not (end <= s or start >= e):
            return True
    return False


def replace_matches_in_paragraph(para, matches, text_offset=0, fallback_replacement_text="[已脱敏]"):
    """按匹配区间替换段落文本，避免同词误替换和跨 run 漏替换。"""
    if not matches or not para.runs:
        return

    paragraph_text = ''.join(run.text for run in para.runs)
    if not paragraph_text:
        return

    text_len = len(paragraph_text)
    ranges = []
    seen = set()

    for match in matches:
        start = match.get('start')
        end = match.get('end')
        if not isinstance(start, int) or not isinstance(end, int):
            continue

        local_start = start - text_offset
        local_end = end - text_offset
        if local_start < 0 or local_end > text_len or local_start >= local_end:
            continue

        replacement = match.get('replacement', fallback_replacement_text)
        if replacement is None:
            replacement = fallback_replacement_text
        if not isinstance(replacement, str):
            replacement = str(replacement)

        key = (local_start, local_end, replacement)
        if key in seen:
            continue
        seen.add(key)
        ranges.append({
            'start': local_start,
            'end': local_end,
            'replacement': replacement
        })

    if not ranges:
        return

    ranges.sort(key=lambda item: (item['start'], -(item['end'] - item['start'])))
    filtered = []
    last_end = -1
    for item in ranges:
        if item['start'] < last_end:
            continue
        filtered.append(item)
        last_end = item['end']

    for item in reversed(filtered):
        apply_range_to_runs(para, item['start'], item['end'], item['replacement'])


def apply_range_to_runs(para, start, end, replacement):
    """在段落 run 列表上应用一次区间替换。"""
    if start >= end:
        return
    if not para.runs:
        return

    run_ranges = []
    cursor = 0
    for idx, run in enumerate(para.runs):
        text = run.text or ''
        run_start = cursor
        run_end = cursor + len(text)
        run_ranges.append((idx, run_start, run_end))
        cursor = run_end

    total_len = cursor
    if start < 0 or end > total_len:
        return

    start_run_idx = None
    start_offset = 0
    for idx, run_start, run_end in run_ranges:
        if start < run_end:
            start_run_idx = idx
            start_offset = start - run_start
            break
    if start_run_idx is None:
        start_run_idx = run_ranges[-1][0]
        start_offset = len(para.runs[start_run_idx].text or '')

    end_run_idx = None
    end_offset = 0
    for idx, run_start, run_end in run_ranges:
        if end <= run_end:
            end_run_idx = idx
            end_offset = end - run_start
            break
    if end_run_idx is None:
        end_run_idx = run_ranges[-1][0]
        end_offset = len(para.runs[end_run_idx].text or '')

    start_run = para.runs[start_run_idx]
    end_run = para.runs[end_run_idx]
    start_text = start_run.text or ''
    end_text = end_run.text or ''

    prefix = start_text[:start_offset]
    suffix = end_text[end_offset:]
    start_run.text = prefix + replacement + suffix

    if end_run_idx > start_run_idx:
        for idx in range(start_run_idx + 1, end_run_idx + 1):
            para.runs[idx].text = ''
