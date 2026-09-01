"""
玻璃特效降级检测 — SecureRedact v1.1.13 PR-V1 §6

参考:
- docs/superpowers/plans/2026-08-30-visual-component-baseline.md
- 前置条件 Task 0.1:在不支持真实玻璃特效的环境(Qt < 6.5 / 软件渲染 / offscreen / minimal)
  提供占位的 rgba 半透明 fallback,保证 UI 在 CI 与低版本环境下不破样式。

公开 API:
- `GLASS_AVAILABLE` — 模块级 bool 常量,指示当前环境是否支持真玻璃特效
- `get_glass_substitution()` — 返回占位颜色映射;`{}` 表示沿用主题 token,
  非空映射用于把 card / dock 背景替换为 rgba 半透明兜底值。
"""

from __future__ import annotations

import os
from typing import Dict, Mapping


def _detect_glass() -> bool:
    """检测当前环境是否支持真玻璃特效。

    返回 False 的场景:
    - Qt 版本 < 6.5(无 QtQuick.Controls 玻璃材质)
    - 显式设置环境变量 QT_QUICK_BACKEND=software
    - QApplication.platformName() 以 "offscreen" 开头或等于 "minimal"
      (CI / headless / smoke test)
    """
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        from PyQt6.QtWidgets import QApplication
    except Exception:
        # 任何导入失败都视作不可用 — 测试/CI 路径下不应强行触发
        return False

    # Qt < 6.5 不支持玻璃材质
    try:
        major, minor, *_ = (int(part) for part in QT_VERSION_STR.split("."))
        if (major, minor) < (6, 5):
            return False
    except (ValueError, AttributeError):
        return False

    # 显式声明使用软件渲染 — 一定不能走真玻璃特效
    if os.environ.get("QT_QUICK_BACKEND", "").lower() == "software":
        return False

    # CI / 无头环境
    try:
        platform_name = QApplication.platformName() or ""
    except Exception:
        return False
    if platform_name.startswith("offscreen") or platform_name == "minimal":
        return False

    return True


GLASS_AVAILABLE: bool = _detect_glass()


_FALLBACK_CARD_BACKGROUND = "rgba(255, 255, 255, 0.92)"
_FALLBACK_DOCK_BACKGROUND = "rgba(247, 248, 250, 0.94)"


def get_glass_substitution() -> Mapping[str, str]:
    """返回玻璃特效不可用时的颜色替换映射。

    - `GLASS_AVAILABLE=True` 时返回 `{}`,调用方继续使用主题 token。
    - 否则返回 `card_background` / `dock_background` 两个键的 rgba 兜底值。
    """
    if GLASS_AVAILABLE:
        return {}
    fallback: Dict[str, str] = {
        "card_background": _FALLBACK_CARD_BACKGROUND,
        "dock_background": _FALLBACK_DOCK_BACKGROUND,
    }
    return fallback


__all__ = ["GLASS_AVAILABLE", "get_glass_substitution"]
