"""
密度模式 helper — 从 main.py 迁出 (PR-B5.1)

原 main.py 模块级函数,供 toolbar.py / workbench.py / setup_ui.py 共同使用。
独立成模块避免循环 import(main.py 与 mixin 互依赖)。

来源:原 main.py 中 3 个函数,逐字搬迁,逻辑零改动。
"""
from __future__ import annotations

from theme import Theme  # PR-B5.1: 补 Theme 引用


def resolve_workspace_density_mode(mode, width, height=0, scale=1.0):
    """解析主工作区工具栏密度档位，兼顾 Windows DPI 与窗口高度。"""
    width = max(int(width or 0), 1)
    height = max(int(height or 0), 0)
    scale = max(1.0, float(scale or 1.0))

    if mode == "pdf":
        wide_threshold = 1500
        compact_threshold = 1260
    elif mode == "word":
        wide_threshold = 1220
        compact_threshold = 980
    else:
        wide_threshold = 1080
        compact_threshold = 860

    if scale >= 1.5:
        wide_threshold += 90
        compact_threshold += 60
    elif scale >= 1.25:
        wide_threshold += 50
        compact_threshold += 30

    if height:
        if height >= 980:
            wide_threshold -= 50
            compact_threshold -= 30
        elif height <= 760:
            wide_threshold += 70
            compact_threshold += 40

    wide_threshold = max(compact_threshold + 80, wide_threshold)
    compact_threshold = max(720, min(compact_threshold, wide_threshold - 80))

    if width >= wide_threshold:
        return "wide"
    if width >= compact_threshold:
        return "compact"
    return "narrow"


def resolve_settings_density_mode(width, height=0, scale=1.0):
    """解析高级设置页密度档位，优先为 Windows 高 DPI 和不同窗口高度收口。"""
    width = max(int(width or 0), 1)
    height = max(int(height or 0), 0)
    scale = max(1.0, float(scale or 1.0))
    order = ["narrow", "compact", "roomy", "wide"]

    if width >= 1700:
        density_mode = "wide"
    elif width >= 1450:
        density_mode = "roomy"
    elif width >= 1260:
        density_mode = "compact"
    else:
        density_mode = "narrow"

    if scale >= 1.5:
        density_mode = _shift_density_mode(density_mode, order, -1)
        if width < 1360:
            density_mode = "narrow"
    elif scale >= 1.25 and density_mode == "wide" and width < 1760:
        density_mode = "roomy"

    if height:
        if height <= 820:
            density_mode = _shift_density_mode(density_mode, order, -1)
        elif height >= 980:
            if density_mode == "compact" and width >= 1380:
                density_mode = "roomy"
            elif density_mode == "roomy" and width >= 1600:
                density_mode = "wide"

    return density_mode


def _shift_density_mode(mode, order, step):
    """在既定密度序列里前后移动一档。"""
    if mode not in order:
        return mode
    index = order.index(mode)
    target = max(0, min(len(order) - 1, index + step))
    return order[target]


