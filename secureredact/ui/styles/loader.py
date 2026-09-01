"""
QSS 加载器 — 把 .qss 文件 + token 占位符合并渲染成 Qt 可用的样式表。

设计要点:
- 占位符采用正则替换 `\\{([a-z_][a-z0-9_]*)\\}` → token 值。
  选用全小写 + 下划线命名空间的正则,确保**不会误伤 QSS 自身的 `{...}` CSS 规则体**
  (QSS 规则体内部标识符均为大写,如 `QMainWindow` `QPushButton#xxx` `QMenu::item`)。
- `apply(widget, theme_name, scope=...)` 是公共入口;scope 对应一组 .qss 文件。
- 默认 scope 命名:
  - `main`     self 上完整样式(base + menu + workspace + progress)
  - `workbench` workbench_panel 专用样式
  - `toolbar`   toolbar + mode_badge 专用样式
  - `workspace` main_container 专用样式(目前与 main 共享;B2 拆分 MainWindow 时改)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

from .tokens import get_substitution_map


STYLES_DIR = Path(__file__).resolve().parent


# === 各 scope 对应的 .qss 文件(按从基底到具象的顺序加载) ===

SCOPES: dict[str, tuple[str, ...]] = {
    "main": (
        "base.qss",
        "menu.qss",
        "workbench.qss",
        "toolbar.qss",
        "workspace.qss",
        "progress.qss",
    ),
    "workbench": ("workbench.qss",),
    "toolbar": ("toolbar.qss",),
    "workspace": ("workspace.qss",),
    "progress": ("progress.qss",),
}


# 仅匹配 [a-z_][a-z0-9_]*,避免与 QSS 大写选择器冲突
_PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def _load_qss(filename: str) -> str:
    """读取单个 .qss 文件(UTF-8)。"""
    path = STYLES_DIR / filename
    return path.read_text(encoding="utf-8")


def _substitute(text: str, theme_name: str) -> str:
    """把 {token} 占位符替换为对应主题的实际值,未识别的占位符保留原样。"""
    mapping = get_substitution_map(theme_name)
    return _PLACEHOLDER_RE.sub(
        lambda m: mapping.get(m.group(1), m.group(0)),
        text,
    )


def render_stylesheet(
    theme_name: str = "light",
    files: Sequence[str] | None = None,
) -> str:
    """合并多个 .qss 文件 + 做 token 替换,返回完整 QSS 字符串。

    Args:
        theme_name: "light" / "dark",默认 "light"。
        files: 自定义 .qss 文件序列(用于测试或扩展)。

    Returns:
        完整 QSS 字符串(可直接传给 widget.setStyleSheet)。
    """
    if files is None:
        files = SCOPES["main"]
    mapping = get_substitution_map(theme_name)
    parts = [_load_qss(f) for f in files]
    combined = "\n\n".join(parts)
    return _PLACEHOLDER_RE.sub(
        lambda m: mapping.get(m.group(1), m.group(0)),
        combined,
    )


class StylesheetLoader:
    """QSS 加载器。提供 render() / apply() 两个公开方法。"""

    def __init__(self, default_theme: str = "light") -> None:
        self.default_theme = default_theme

    def render(
        self,
        theme_name: str | None = None,
        scope: str = "main",
        custom_files: Sequence[str] | None = None,
    ) -> str:
        """按 scope 渲染 QSS 字符串,scope 不识别时回退到 'main'。"""
        if custom_files is not None:
            files = tuple(custom_files)
        else:
            files = SCOPES.get(scope, SCOPES["main"])
        return render_stylesheet(theme_name or self.default_theme, files)

    def apply(
        self,
        widget,
        theme_name: str | None = None,
        scope: str = "main",
    ) -> None:
        """把渲染好的 QSS 直接应用到 widget 上。"""
        widget.setStyleSheet(self.render(theme_name, scope))


# 默认 loader 实例,调用方可直接 `from .loader import loader`
loader = StylesheetLoader()


__all__ = [
    "SCOPES",
    "StylesheetLoader",
    "loader",
    "render_stylesheet",
]