"""
secureredact.ui.main_window.window — MainWindow 类容器

PR-XXX 引入。本模块承载 MainWindow 主类的物理定义,
与 9 个 mixin(toolbar/workbench/word_preview/pdf_render/batch_replace/
density/setup_ui/handlers/theme) 平行放置。

历史:
- PR-B0~B2.x: MainWindow 在 main.py(同源兼容 shim)
- PR-B5:     main.py 末尾 __main__ shim 移除
- PR-XXX(本 PR): MainWindow 类整体迁入本模块

公开 API:
- `MainWindow` — 主窗口类,9 层 mixin + QMainWindow 多继承
"""

from __future__ import annotations

# 9 个 mixin 的 import 由 MainWindow 类迁入时一并带上(本文件暂时为空,
# 占位以验证模块路径可达性)。完整的 mixin import 列表见 main.py:69-77。