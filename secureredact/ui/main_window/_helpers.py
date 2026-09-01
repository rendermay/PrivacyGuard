"""
MainWindow mixin 共享辅助函数/常量 (PR-B5.2 综合迁出)

从 `main.py` 模块级迁出,涵盖 workbench / toolbar / word_preview 三个 mixin 所需的
纯数据变换与文本/JS 片段构造。无副作用、无 UI 依赖,可独立测试。

来源:`main.py:321-333` (常量) + `main.py:434-716` (函数),逐字搬迁,逻辑零改动。

使用方:
    - secureredact.ui.main_window.workbench — `build_workbench_guidance`
    - secureredact.ui.main_window.toolbar   — `build_toolbar_mode_labels`
    - secureredact.ui.main_window.word_preview — `resolve_word_preview_image_suffix`,
      `should_reload_word_panel`, `build_highlight_preview_segments`,
      `build_replaced_preview_segments`, `build_word_panel_update_script`,
      `WORD_PREVIEW_*` 常量
"""
from __future__ import annotations

import json
import re


# === Word 预览相关常量 (main.py:321-333) ===

WORD_PREVIEW_IMAGE_EXTENSION_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
WORD_PREVIEW_BROKEN_IMAGE_DATA_URI = (
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
)
WORD_PREVIEW_BLOCK_SELECTOR = '[data-word-block="1"][data-key]'


# === Word 预览辅助函数 (main.py:434-572) ===

def resolve_word_preview_image_suffix(content_type):
    """根据 Mammoth 图片内容类型推导本地文件后缀。"""
    if not isinstance(content_type, str):
        return ".img"

    normalized = content_type.strip().lower()
    if normalized in WORD_PREVIEW_IMAGE_EXTENSION_MAP:
        return WORD_PREVIEW_IMAGE_EXTENSION_MAP[normalized]

    if "/" not in normalized:
        return ".img"

    subtype = normalized.split("/", 1)[1].split(";", 1)[0].strip()
    subtype = subtype.replace("+xml", "").replace("+zip", "")
    subtype = re.sub(r"[^a-z0-9]+", "", subtype)
    if not subtype:
        return ".img"
    return f".{subtype}"


def build_replaced_preview_segments(text, matches, default_replacement_text="[已脱敏]"):
    """根据匹配区间生成替换后文本分段（用于右侧预览高亮）。"""
    if not isinstance(text, str):
        return [{"type": "text", "value": ""}]
    if not matches:
        return [{"type": "text", "value": text}]

    fallback_text = default_replacement_text if isinstance(default_replacement_text, str) and default_replacement_text else "[已脱敏]"
    segments = []
    cursor = 0

    for match in sorted(matches, key=lambda item: item.get("start", 0)):
        start = match.get("start")
        end = match.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < cursor or start < 0 or end > len(text) or start >= end:
            continue

        if start > cursor:
            segments.append({
                "type": "text",
                "value": text[cursor:start]
            })

        replacement = match.get("replacement", fallback_text)
        if replacement is None:
            replacement = fallback_text
        if not isinstance(replacement, str):
            replacement = str(replacement)

        segments.append({
            "type": "replacement",
            "value": replacement,
            "source": match.get("source", "rule"),
            "mode": match.get("mode", ""),
            "rule_name": match.get("rule_name", "")
        })
        cursor = end

    if cursor < len(text):
        segments.append({
            "type": "text",
            "value": text[cursor:]
        })

    if not segments:
        return [{"type": "text", "value": text}]
    return segments


def build_highlight_preview_segments(text, matches):
    """根据匹配区间生成原文高亮分段（用于左侧预览）。"""
    if not isinstance(text, str):
        return [{"type": "text", "value": ""}]
    if not matches:
        return [{"type": "text", "value": text}]

    segments = []
    cursor = 0
    for match in sorted(matches, key=lambda item: item.get("start", 0)):
        start = match.get("start")
        end = match.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < cursor or start < 0 or end > len(text) or start >= end:
            continue

        if start > cursor:
            segments.append({"type": "text", "value": text[cursor:start]})

        segments.append({
            "type": "highlight",
            "value": text[start:end],
            "source": match.get("source", "manual"),
            "mode": match.get("mode", ""),
            "rule_name": match.get("rule_name", ""),
            "start": start,
            "end": end,
        })
        cursor = end

    if cursor < len(text):
        segments.append({"type": "text", "value": text[cursor:]})

    if not segments:
        return [{"type": "text", "value": text}]
    return segments


def build_word_panel_update_script(block_updates):
    """构建仅更新正文块的 Word 预览增量刷新脚本。"""
    payload = json.dumps(block_updates or {}, ensure_ascii=False)
    return f"""
        (function() {{
            const updates = {payload};
            const elements = document.querySelectorAll('{WORD_PREVIEW_BLOCK_SELECTOR}');
            elements.forEach(function(el) {{
                const key = el.dataset.key;
                if (Object.prototype.hasOwnProperty.call(updates, key)) {{
                    const nextHtml = updates[key];
                    if (el.innerHTML !== nextHtml) {{
                        el.innerHTML = nextHtml;
                    }}
                }}
            }});
        }})();
    """


def should_reload_word_panel(source_changed, loaded_source_path, current_file_path, panel_ready):
    """判断 Word 预览面板是否需要重新加载完整文档。"""
    if source_changed:
        return True
    if not panel_ready:
        return True
    return loaded_source_path != current_file_path


# === 工作台 / 工具栏辅助函数 (main.py:584-716, 拆分) ===

def build_workbench_guidance(mode, batch_stage="rule_setup", has_results=False, compare_mode=False):
    """按当前模式生成顶部工作台的下一步引导标签。"""
    if mode == "pdf":
        first_step = "下一步：人工复核并导出" if has_results else "下一步：先点智能脱敏"
        return [
            first_step,
            "黑 / 白遮罩可立即切换",
            "支持手动画框补充脱敏",
        ]
    if mode == "word":
        compare_tip = "当前可隐藏对比预览" if compare_mode else "需要时可打开对比预览"
        first_step = "下一步：先检查替换规则" if not has_results else "下一步：复核替换结果"
        return [
            first_step,
            "原文预览与替换预览分开显示",
            compare_tip,
        ]
    if mode == "batch":
        if batch_stage == "running":
            return [
                "当前：正在批量替换文档",
                "可随时停止并保留已完成结果",
                "完成后可筛选成功 / 失败清单",
            ]
        if batch_stage in ("finished", "stopped"):
            return [
                "下一步：先看失败文档和原因",
                "可仅重试失败文档",
                "双击结果可打开输出或定位原文件",
            ]
        return [
            "下一步：确认规则后再开始执行",
            "这一步不会改动任何原文件",
            "建议至少启用一条 Word 替换规则",
        ]
    if mode == "image_merge":
        return [
            "下一步：确认图片顺序后开始合并",
            "支持多张图片自动合成为 PDF",
            "合并完成后会直接进入 PDF 脱敏",
        ]
    return [
        "支持拖拽导入，系统会自动分流",
        "PDF 走脱敏，Word 走替换",
        "多个 Word 会先进入批量规则确认",
        "多张图片可直接合并为 PDF",
    ]


def build_toolbar_mode_labels(mode, density_mode, has_results=False, enabled_word_rules=0):
    """构建工具栏在不同模式下的主动作文案。"""
    compact = density_mode != "wide"

    if mode == "pdf":
        if has_results:
            scan_text = "重脱" if compact else "重新脱敏"
            scan_tooltip = "重新执行 PDF 智能脱敏扫描"
        else:
            scan_text = "脱敏" if compact else "智能脱敏"
            scan_tooltip = "执行 PDF 智能脱敏扫描"
        save_text = "导出" if compact else "导出 PDF"
        save_tooltip = "导出当前 PDF 脱敏结果"
    elif mode == "word":
        if has_results:
            scan_text = "重替" if compact else "重新替换"
            scan_tooltip = "重新执行 Word 智能替换扫描"
        else:
            scan_text = "替换" if compact else "智能替换"
            scan_tooltip = "执行 Word 智能替换扫描"
        save_text = "导出" if compact else "导出 Word"
        save_tooltip = "导出当前 Word 替换结果"
    else:
        scan_text = "脱敏" if compact else "智能脱敏"
        save_text = "导出"
        scan_tooltip = "执行智能脱敏扫描"
        save_tooltip = "导出处理结果"

    if enabled_word_rules > 0:
        word_rules_text = f"规则 {enabled_word_rules}" if compact else f"替换规则 {enabled_word_rules}"
        word_rules_tooltip = f"打开 Word 替换规则（当前启用 {enabled_word_rules} 条）"
    else:
        word_rules_text = "规则" if compact else "替换规则"
        word_rules_tooltip = "打开 Word 替换规则"

    return {
        "open_text": "打开",
        "open_tooltip": "打开 PDF、Word 或图片文件",
        "scan_text": scan_text,
        "scan_tooltip": scan_tooltip,
        "save_text": save_text,
        "save_tooltip": save_tooltip,
        "word_rules_text": word_rules_text,
        "word_rules_tooltip": word_rules_tooltip,
    }