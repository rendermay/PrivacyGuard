"""
设置对话框共享辅助函数 (PR-B5.2 综合迁出)

从 `main.py` 模块级迁出,供 `secureredact.ui.settings.dialog.SettingsDialog` 直接调用。
纯函数,无副作用、无 UI 依赖,可独立测试。

来源:`main.py:584-620`,逐字搬迁,逻辑零改动。
"""
from __future__ import annotations


def format_signed_percent(value):
    """将百分比格式化为适合界面展示的文案。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    return f"{number:+d}%" if number else "0%"


def build_settings_nav_labels(enabled_rules, keyword_count, precision_is_default, ocr_adjust_value, blacklist_count=0, whitelist_count=0):
    """构建设置中心左侧导航标签。"""
    return [
        f"1 通用规则 · {max(0, int(enabled_rules))}项启用",
        f"2 自定义关键词 · {max(0, int(keyword_count))}条",
        f"3 黑名单 · {max(0, int(blacklist_count))}条",
        f"4 白名单 · {max(0, int(whitelist_count))}条",
        f"5 扫描与微调 · {'默认' if precision_is_default else '已微调'}",
        f"6 OCR 检测框 · {format_signed_percent(ocr_adjust_value)}",
    ]


def build_settings_hero_tags(enabled_rules, keyword_count, enabled_word_rules, precision_is_default, ocr_adjust_value, scan_label):
    """构建设置页顶部的动态摘要标签。"""
    common_tag = (
        f"常用：规则 {max(0, int(enabled_rules))} 项 · "
        f"关键词 {max(0, int(keyword_count))} 条 · "
        f"Word {max(0, int(enabled_word_rules))} 条"
    )
    if precision_is_default:
        advanced_tag = f"高级：扫描推荐值 · OCR {format_signed_percent(ocr_adjust_value)}"
    else:
        normalized_scan_label = str(scan_label or "-").strip() or "-"
        advanced_tag = (
            f"高级：{normalized_scan_label} · "
            f"OCR {format_signed_percent(ocr_adjust_value)} · 已微调"
        )
    return common_tag, advanced_tag