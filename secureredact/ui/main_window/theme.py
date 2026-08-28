"""
主题切换 mixin — MainWindow DARK/LIGHT 主题切换 (PR-C1 引入)

提供公共方法:
- `_apply_theme(name)`:应用主题 (light / dark / system)
- `set_theme(name)`:public API,切换主题并持久化
- `theme_name`:当前主题属性

依赖 MainWindow 上的属性(由 __init__ 初始化):
    - self.theme_name: str  当前主题("light"/"dark"/"system")
    - self.app_state / self.SimpleConfig: 配置持久化
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication


class MainWindowThemeMixin:
    """DARK/LIGHT 主题切换入口。

    实际样式应用委托给 StylesheetLoader(PR-B1 引入)。
    主题状态持久化到 config.json(app.theme 字段)。
    """

    INITIAL_THEME_NAME = "light"  # 启动默认值(若 config 中无)

    def _resolve_system_theme(self):
        """'system' 模式:读取系统外观偏好。Returns: 'light' 或 'dark'"""
        qapp = QApplication.instance()
        if qapp is None:
            return "light"
        try:
            style_hint = qapp.styleHints()
            scheme = style_hint.colorScheme()
            return "dark" if scheme == Qt.ColorScheme.Dark else "light"
        except AttributeError:
            palette = qapp.palette()
            bg = palette.color(QPalette.ColorRole.Window)
            return "dark" if bg.lightness() < 128 else "light"

    def _apply_theme(self, name=None):
        """根据 name 应用主题。name: "light"/"dark"/"system" """
        from secureredact.ui.styles import StylesheetLoader, get_substitution_map

        if name is None:
            name = getattr(self, "theme_name", self.INITIAL_THEME_NAME)
        if name not in ("light", "dark", "system"):
            name = "light"

        effective = self._resolve_system_theme() if name == "system" else name

        loader = StylesheetLoader()
        loader.apply(self, effective, scope="main")

        # 滚动区域使用 theme["scroll_area"] token
        if hasattr(self, "scroll") and hasattr(self, "scroll_style"):
            self.scroll.setStyleSheet(
                self.scroll_style.format(get_substitution_map(effective)["scroll_area"])
            )

        # 触发部分 widget 刷新(状态徽章/上下文条/info_bar)
        for refresh in ("_refresh_mode_badge", "_refresh_workbench_context", "_refresh_info_bar_visibility"):
            if hasattr(self, refresh):
                try:
                    getattr(self, refresh)()
                except Exception:
                    pass

        self.theme_name = name

    def set_theme(self, name):
        """public API:切换主题并持久化到 config.json。"""
        if name not in ("light", "dark", "system"):
            return
        self._apply_theme(name)
        config = getattr(self, "config", None)
        if config is not None and hasattr(config, "set"):
            config.set("app.theme", name, persist=True)


__all__ = ["MainWindowThemeMixin"]
