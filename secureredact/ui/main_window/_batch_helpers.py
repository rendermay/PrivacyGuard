"""
批量 Word 替换结果表 / 摘要 / 筛选辅助函数 (PR-B5.2 迁出)

从 `main.py` 模块级函数迁出,作为 `MainWindowBatchReplaceMixin` 的纯数据变换工具。
无副作用、无 UI 依赖,可独立测试。

来源:`main.py:623-765`,逐字搬迁,逻辑零改动。
"""
from __future__ import annotations

import os

from secureredact.redaction.word_rules import normalize_word_replace_rules


def build_batch_result_rows(summary):
    """将批量替换 summary 转成结果表格行。"""
    if not isinstance(summary, dict):
        return []

    rows = []
    failed_items = summary.get("failed", []) if isinstance(summary.get("failed", []), list) else []
    success_items = summary.get("success", []) if isinstance(summary.get("success", []), list) else []

    for item in failed_items:
        if not isinstance(item, dict):
            continue
        input_path = str(item.get("input", "") or "")
        rows.append({
            "status": "失败",
            "status_key": "failed",
            "document": os.path.basename(input_path) if input_path else "未知文档",
            "detail": str(item.get("error", "") or "处理失败"),
            "action": "双击定位原文件",
            "open_path": input_path,
            "fallback_dir": os.path.dirname(input_path) if input_path else "",
        })

    for item in success_items:
        if not isinstance(item, dict):
            continue
        input_path = str(item.get("input", "") or "")
        output_path = str(item.get("output", "") or "")
        rows.append({
            "status": "成功",
            "status_key": "success",
            "document": os.path.basename(input_path) if input_path else "未知文档",
            "detail": os.path.basename(output_path) if output_path else "已生成输出文件",
            "action": "双击打开输出",
            "open_path": output_path,
            "fallback_dir": os.path.dirname(output_path) if output_path else "",
        })

    return rows


def summarize_batch_result_rows(rows):
    """汇总批量结果行数量。"""
    summary = {"total": 0, "success": 0, "failed": 0}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        summary["total"] += 1
        status_key = row.get("status_key")
        if status_key == "success":
            summary["success"] += 1
        elif status_key == "failed":
            summary["failed"] += 1
    return summary


def build_batch_filter_labels(summary_counts, show_counts=False):
    """构建批量结果筛选按钮文案。"""
    counts = summary_counts if isinstance(summary_counts, dict) else {}
    total = max(0, int(counts.get("total", 0) or 0))
    success = max(0, int(counts.get("success", 0) or 0))
    failed = max(0, int(counts.get("failed", 0) or 0))
    if not show_counts:
        return {"all": "全部", "success": "成功", "failed": "失败"}
    return {
        "all": f"全部 {total}",
        "success": f"成功 {success}",
        "failed": f"失败 {failed}",
    }


def filter_batch_result_rows(rows, filter_mode):
    """按筛选模式过滤批量结果行。"""
    if filter_mode not in {"all", "success", "failed"}:
        filter_mode = "all"

    filtered = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if filter_mode == "all":
            filtered.append(row)
        elif row.get("status_key") == filter_mode:
            filtered.append(row)
    return filtered


def build_batch_rule_summary_lines(rules, success_items, default_replacement_text="[已脱敏]"):
    """按规则生成批量替换摘要明细。"""
    normalized_rules = normalize_word_replace_rules(rules, default_replacement_text)
    if not normalized_rules:
        return []

    def _extract_rule_count(item, target_rule_index):
        if not isinstance(item, dict):
            return 0

        counts = item.get("rule_counts", [])
        if isinstance(counts, dict):
            try:
                return max(0, int(counts.get(str(target_rule_index), counts.get(target_rule_index, 0)) or 0))
            except (TypeError, ValueError):
                return 0

        if not isinstance(counts, list):
            return 0

        for entry in counts:
            if not isinstance(entry, dict):
                continue
            try:
                rule_index = int(entry.get("rule_index", -1))
                count = int(entry.get("count", 0) or 0)
            except (TypeError, ValueError):
                continue
            if rule_index == target_rule_index:
                return max(0, count)
        return 0

    lines = []
    for rule_index, rule in enumerate(normalized_rules, start=1):
        doc_parts = []
        replacement_text = rule.get("replace") or default_replacement_text

        for item in success_items or []:
            count = _extract_rule_count(item, rule_index - 1)
            if count <= 0:
                continue
            input_name = os.path.basename(str(item.get("input", "") or "")) or "未知文档"
            doc_parts.append(f"{input_name} 成功替换 {count} 条")

        if doc_parts:
            lines.append(
                f"{rule_index}、“{rule.get('find', '')}”替换为“{replacement_text}”，"
                + "，".join(doc_parts)
                + "；"
            )
        else:
            lines.append(
                f"{rule_index}、“{rule.get('find', '')}”替换为“{replacement_text}”，本轮未命中；"
            )

    return lines