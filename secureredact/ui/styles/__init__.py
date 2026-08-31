"""
secureredact.ui.styles — 设计 token 与 QSS 集中化模块

PR-B1 (QSS 集中化) 引入。负责:
- 把原 `theme.py` 字典升级为不可变 Tokens dataclass
- 提供 LIGHT/DARK 双主题的 token 替换映射
- 渲染 `*.qss` 文件 + token 占位符合并为 Qt 可用样式表

公开 API:
- `Tokens` / `LIGHT` / `DARK` — 颜色 token
- `get_substitution_map(theme_name)` — 占位符替换字典
- `StylesheetLoader` / `loader` — QSS 加载器
- `render_stylesheet(theme_name, files)` — 一次性渲染字符串
"""

from .loader import StylesheetLoader, loader, render_stylesheet
from .tokens import (
    DARK,
    FONT_FAMILY,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    LIGHT,
    Tokens,
    get_substitution_map,
    get_tokens,
)

__all__ = [
    "Tokens",
    "LIGHT",
    "DARK",
    "FONT_FAMILY",
    "FONT_SIZE_SMALL",
    "FONT_SIZE_NORMAL",
    "get_tokens",
    "get_substitution_map",
    "StylesheetLoader",
    "loader",
    "render_stylesheet",
]