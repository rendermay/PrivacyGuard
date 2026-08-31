"""
平台检测模块 — PR-V3 Task 3 引入。

仅做平台能力检测,不引入任何业务逻辑。
启动期调用一次,结果缓存到 `_GLASS_SUPPORT_CACHE` 全局变量。
"""
from __future__ import annotations

# 缓存:启动期 detect_blur_support() 调用一次后,后续直接读取缓存
_GLASS_SUPPORT_CACHE: bool | None = None


def _qt_major_version() -> int:
    """返回当前 Qt 主版本号。失败时返回 0（保守降级）。"""
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        return int(QT_VERSION_STR.split('.')[0])
    except Exception:
        return 0


def _resolve_qpa_platform() -> str:
    """检测当前 QPA 平台名(无 Qt 环境返回 '')。

    Returns:
        'windows' | 'cocoa' | 'xcb' | 'wayland' | ''
    """
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            # 极端 case: 无 QApplication 实例
            return ""
        return app.platformName().lower()
    except Exception:
        return ""


def detect_blur_support() -> bool:
    """启动期检测 backdrop-filter 支持。

    Returns:
        True:  启用 Glass (backdrop-filter: blur(8px))
        False: 降级到半透明纯色 + 加阴影

    降级触发条件(任一):
        - Qt < 6(主版本 ≤ 5)
        - QPA 平台不在 {'windows', 'cocoa', 'xcb'} 内
        - 检测过程异常(任意 import / 调用失败)
    """
    global _GLASS_SUPPORT_CACHE
    if _GLASS_SUPPORT_CACHE is not None:
        return _GLASS_SUPPORT_CACHE

    try:
        if _qt_major_version() < 6:
            _GLASS_SUPPORT_CACHE = False
            return False
        platform = _resolve_qpa_platform()
        _GLASS_SUPPORT_CACHE = platform in ("windows", "cocoa", "xcb")
    except Exception:
        _GLASS_SUPPORT_CACHE = False

    return _GLASS_SUPPORT_CACHE


__all__ = ["detect_blur_support", "_resolve_qpa_platform", "_qt_major_version"]
