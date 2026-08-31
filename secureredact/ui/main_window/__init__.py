"""
secureredact.ui.main_window — MainWindow 与主界面子模块

公开 API:
- `MainWindow` — 主窗口类(PR-XXX 引入,9 层 mixin + QMainWindow)
- `SinglePageCanvas` — PDF 单页画布
- `WebViewBridge` — Python ↔ JS 通信桥(Word 双栏预览)
- `identifiers` — 所有 setObjectName 字面量集中常量
"""

from . import identifiers
from .canvas import DEBUG_MODE, SinglePageCanvas
from .webview_bridge import WebViewBridge
from .window import MainWindow  # PR-XXX: MainWindow 主体迁入后暴露

__all__ = [
    "MainWindow",
    "SinglePageCanvas",
    "WebViewBridge",
    "identifiers",
    "DEBUG_MODE",
]
