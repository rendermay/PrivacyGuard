"""
secureredact.ui.main_window — MainWindow 与主界面子模块

PR-B2.0 引入。本子包目标:
- 把 `MainWindow` 与主界面依赖的 widget 类拆分到独立模块
- 当前阶段(B2.0):仅迁出独立 widget 类(`SinglePageCanvas` / `WebViewBridge`)
- 后续 PR-B2.1~B2.6:逐步把 MainWindow 内部方法迁出(工具栏 / 工作台 / Word 双栏 /
  PDF 渲染 / 批量替换 / 事件路由)

公开 API(本 PR):
- `SinglePageCanvas` — PDF 单页画布
- `WebViewBridge` — Python ↔ JS 通信桥(Word 双栏预览)
- `identifiers` — 所有 setObjectName 字面量集中常量
"""

from . import identifiers
from .canvas import DEBUG_MODE, SinglePageCanvas
from .webview_bridge import WebViewBridge

__all__ = [
    "SinglePageCanvas",
    "WebViewBridge",
    "identifiers",
    "DEBUG_MODE",
]