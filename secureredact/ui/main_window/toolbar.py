"""
工具栏 mixin — MainWindow 工具栏 + 密度自适应方法 (PR-B2.1 迁出)

提供 13 个工具栏相关方法,作为 `MainWindowToolbarMixin`。
`MainWindow` 通过多继承 (`class MainWindow(MainWindowToolbarMixin, QMainWindow):`)
复用本 mixin,实现文件物理拆分但行为零改动。

来源:原 `main.py` 中 13 个工具栏相关方法(共 507 行),逐字搬迁,逻辑零改动。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QStyle,
    QToolBar, QToolButton, QVBoxLayout, QWidget,
)
from theme import Theme  # PR-B5.1: 补 Theme 引用
# PR-B5.1: toolbar 方法链引用 main.py 模块级函数
# 用 `import main` 而非 `from main import`,避免循环 import。
# 调用时用 main.resolve_workspace_density_mode(...) 形式。
from secureredact.ui.utils.density import (  # PR-B5.1
    resolve_workspace_density_mode, resolve_settings_density_mode, _shift_density_mode,
)
from ._helpers import build_toolbar_mode_labels  # PR-B5.2: 综合迁出


class MainWindowToolbarMixin:
    """工具栏创建 / 响应式 / 密度自适应 / 按钮变体。

    方法签名与实现与原 MainWindow 内一致,直接被 MainWindow 继承使用。
    依赖 MainWindow 上的属性(由 MainWindow.__init__ / setup_ui 创建):
        - self.toolbar / self.toolbar_groups / self.btn_*
        - self.app_state / self.density_mode
        - self.theme / self.Theme(主题常量)
        - self._get_button_style 自身方法(实例方法,本 mixin 内定义)
    """

    def _refresh_toolbar_more_button_style(self):
        """刷新更多按钮样式，保持响应式和隐藏菜单箭头逻辑一致。"""
        if not hasattr(self, "btn_more"):
            return
        self.btn_more.setStyleSheet(
            self._get_button_style("secondary") +
            """
            QPushButton#toolbarMoreButton {
                padding-right: 16px;
            }
            QPushButton#toolbarMoreButton::menu-indicator {
                image: none;
                width: 0px;
                height: 0px;
            }
            """
        )

    def _apply_native_toolbar_icons(self):
        """为导航按钮应用 Qt 原生图标，提升 Windows 下的一致性。"""
        if not hasattr(self, "btn_go_first"):
            return

        style = self.style()
        icon_map = [
            (self.btn_go_first, QStyle.StandardPixmap.SP_MediaSkipBackward),
            (self.btn_prev_page, QStyle.StandardPixmap.SP_ArrowBack),
            (self.btn_next_page, QStyle.StandardPixmap.SP_ArrowForward),
            (self.btn_go_last, QStyle.StandardPixmap.SP_MediaSkipForward),
        ]
        for button, standard_icon in icon_map:
            button.setIcon(style.standardIcon(standard_icon))
            button.setText("")

    def _refresh_toolbar_group_visibility(self):
        """按当前模式和响应式显隐，收口工具栏分组容器。"""
        group_map = [
            (getattr(self, "toolbar_primary_group", None), [getattr(self, "btn_open", None), getattr(self, "btn_scan", None)]),
            (getattr(self, "toolbar_word_group", None), [getattr(self, "btn_settings", None), getattr(self, "btn_compare_toggle", None)]),
            (getattr(self, "toolbar_pdf_group", None), [getattr(self, "rb_black", None), getattr(self, "rb_white", None), getattr(self, "cb_dual", None)]),
            (getattr(self, "toolbar_zoom_group", None), [getattr(self, "btn_zoom_out", None), getattr(self, "lbl_zoom", None), getattr(self, "btn_zoom_in", None)]),
            (getattr(self, "toolbar_nav_group", None), [getattr(self, "btn_go_first", None), getattr(self, "btn_prev_page", None), getattr(self, "lbl_page", None), getattr(self, "btn_next_page", None), getattr(self, "btn_go_last", None)]),
            (getattr(self, "toolbar_utility_group", None), [getattr(self, "btn_fit_utility", None), getattr(self, "btn_feedback", None), getattr(self, "btn_more", None), getattr(self, "btn_save", None)]),
        ]

        for group, widgets in group_map:
            if not group:
                continue
            group.setVisible(any(widget and not widget.isHidden() for widget in widgets))

    def _set_toolbar_widget_width(self, widget, min_width=0, extra=28):
        """根据当前文案为工具栏控件设置稳定宽度，避免文字被硬挤压。"""
        if not widget or not hasattr(widget, "fontMetrics"):
            return

        text = widget.text() if hasattr(widget, "text") else ""
        metrics = widget.fontMetrics()
        text_width = metrics.horizontalAdvance(text) + extra
        hint_width = 0
        try:
            widget.ensurePolished()
            hint_width = widget.sizeHint().width()
        except Exception:
            hint_width = 0

        if widget.objectName() == "toolbarMoreButton":
            hint_width += 12

        width = max(text_width, hint_width)
        width = max(width, min_width)
        widget.setMinimumWidth(width)
        widget.setMaximumWidth(width)

    def _set_toolbar_group_width(self, group, width=None):
        """为工具栏分组设置统一外宽；传 None 时恢复内容驱动宽度。"""
        if not group:
            return
        if width is None:
            group.setMinimumWidth(0)
            group.setMaximumWidth(16777215)
            return
        group.setMinimumWidth(width)
        group.setMaximumWidth(width)

    def _refresh_toolbar_overflow_menu(self, is_pdf, is_word, density_mode):
        """把低频动作收进更多菜单，避免窄窗口时挤爆工具栏。"""
        if not hasattr(self, "toolbar_more_menu"):
            return

        self.toolbar_more_menu.clear()
        has_item = False

        if is_word and not self.btn_compare_toggle.isVisible():
            compare_text = "打开对比预览"
            if self.word_doc and self._has_word_replacement_candidates():
                compare_text = "显示对比预览" if self.word_compare_user_hidden else "隐藏对比预览"
            compare_action = self.toolbar_more_menu.addAction(compare_text, self.toggle_word_compare_preview)
            compare_action.setEnabled(bool(self.word_doc) and self._has_word_replacement_candidates())
            has_item = True

        if is_pdf and not getattr(self, "btn_fit_utility", None).isVisible():
            self.toolbar_more_menu.addAction("适应页面", self.fit_page)
            has_item = True

        if is_pdf and density_mode == "narrow":
            if has_item:
                self.toolbar_more_menu.addSeparator()
            self.toolbar_more_menu.addAction("跳到第一页", self.go_first)
            self.toolbar_more_menu.addAction("跳到最后一页", self.go_last)
            has_item = True

        self.btn_more.setVisible(has_item)

    def _show_toolbar_more_menu(self):
        """在按钮下方手动弹出更多菜单，避免系统菜单箭头把按钮布局挤坏。"""
        if not hasattr(self, "toolbar_more_menu") or self.toolbar_more_menu.isEmpty():
            return
        source_btn = self.sender()
        if not isinstance(source_btn, QPushButton):
            source_btn = getattr(self, "btn_more", None)
        if not source_btn or not source_btn.isVisible():
            return

        popup_pos = source_btn.mapToGlobal(source_btn.rect().bottomLeft())
        self.toolbar_more_menu.popup(popup_pos)

    def _toggle_dual_toolbar(self, checked=False):
        """工具栏双页按钮入口，保持按钮状态和画布状态同步。"""
        checked = bool(checked)
        if hasattr(self, "cb_dual") and self.cb_dual.isChecked() != checked:
            self.cb_dual.setChecked(checked)
        self.toggle_dual_view(checked)
        self._refresh_toolbar_responsiveness()
        self._refresh_workbench_context()

    def _refresh_toolbar_responsiveness(self):
        """根据窗口宽度做工具栏响应式降级，保证缩放时仍可读。"""
        if not hasattr(self, "toolbar"):
            return

        width = self.width() or self.toolbar.width()
        # Qt 返回的是逻辑像素宽度，这里不再额外按屏幕缩放除一次，
        # 否则 Retina / Windows 高缩放下会被过早判成窄布局。
        effective_width = width
        scale = self._get_display_scale_factor()
        density_height = self.height() if scale > 1.0 else 0
        mode = self.current_ui_mode
        is_idle = mode == "idle"
        is_pdf = mode == "pdf"
        is_word = mode == "word"
        is_image_merge = mode == "image_merge"
        has_mode_results = self._has_pdf_redactions() if is_pdf else (self._has_word_replacement_candidates() if is_word else False)
        enabled_word_rules = self._count_enabled_word_rules() if is_word else 0

        density_mode = resolve_workspace_density_mode(mode, effective_width, density_height, scale)

        self.toolbar_density_mode = density_mode
        self._refresh_windows_density_metrics(density_mode)
        label_config = build_toolbar_mode_labels(
            mode,
            density_mode,
            has_results=has_mode_results,
            enabled_word_rules=enabled_word_rules,
        )

        self.btn_open.setText(label_config["open_text"])
        self.btn_scan.setText(label_config["scan_text"])
        self.btn_open.setToolTip(label_config["open_tooltip"])
        self.btn_scan.setToolTip(label_config["scan_tooltip"])

        black_text = "黑遮罩" if density_mode == "wide" else ("黑遮" if density_mode == "compact" else "黑")
        white_text = "白遮罩" if density_mode == "wide" else ("白遮" if density_mode == "compact" else "白")
        dual_text = "双页" if density_mode != "narrow" else "双"
        fit_text = "适应页面" if density_mode != "narrow" else "适应"
        self.rb_black.setText(black_text)
        self.rb_white.setText(white_text)
        self.cb_dual.setText(dual_text)
        self.btn_fit.setText(fit_text)
        self.btn_fit_utility.setText(fit_text)
        self.btn_settings.setText("高级设置")
        self.btn_feedback.setText("使用/反馈")
        self.btn_workbench_feedback.setText("使用/反馈")
        self.btn_save.setText(label_config["save_text"])
        self.btn_more.setText("更多")
        self.rb_black.setToolTip("使用黑色遮罩涂抹")
        self.rb_white.setToolTip("使用白色遮罩涂抹")
        self.cb_dual.setToolTip("切换单双页预览")
        self.btn_fit.setToolTip("按窗口大小适应页面")
        self.btn_fit_utility.setToolTip("按窗口大小适应页面")
        self.btn_settings.setToolTip("打开高级设置")
        self.btn_feedback.setToolTip("查看使用说明或提交反馈")
        self.btn_workbench_feedback.setToolTip("查看使用说明或提交反馈")
        self.btn_save.setToolTip(label_config["save_tooltip"])
        self.btn_more.setToolTip("显示收纳的操作")

        self.btn_settings.setVisible(not is_idle)
        self.btn_feedback.setVisible((not is_idle) and not (is_pdf or is_image_merge))
        self.btn_workbench_feedback.setVisible(is_pdf or is_image_merge)
        self.btn_fit.setVisible(False)
        self.btn_fit_utility.setVisible(is_pdf)
        self.btn_compare_toggle.setVisible(is_word and density_mode != "narrow")

        if is_pdf and density_mode == "narrow":
            self.btn_go_first.hide()
            self.btn_go_last.hide()
        else:
            self.btn_go_first.setVisible(is_pdf)
            self.btn_go_last.setVisible(is_pdf)

        self._refresh_toolbar_overflow_menu(is_pdf, is_word, density_mode)

        if density_mode == "wide":
            text_button_floor = 82
            utility_button_floor = 98
            compare_button_floor = 104
            more_button_floor = 76
        elif density_mode == "compact":
            text_button_floor = 74
            utility_button_floor = 90
            compare_button_floor = 94
            more_button_floor = 70
        else:
            text_button_floor = 68
            utility_button_floor = 82
            compare_button_floor = 84
            more_button_floor = 64

        if scale >= 1.5:
            text_button_floor += 8
            utility_button_floor += 10
            compare_button_floor += 10
            more_button_floor += 8
        elif scale >= 1.25:
            text_button_floor += 4
            utility_button_floor += 6
            compare_button_floor += 6
            more_button_floor += 4

        for button in [self.btn_open, self.btn_scan, self.btn_settings, self.btn_compare_toggle,
                       self.btn_fit_utility, self.btn_feedback, self.btn_more, self.btn_save]:
            if button.isVisible():
                if button in (self.btn_feedback, self.btn_fit_utility):
                    min_width = utility_button_floor
                    extra = 40
                elif button is self.btn_settings:
                    min_width = utility_button_floor
                    extra = 34
                elif button is self.btn_compare_toggle:
                    min_width = compare_button_floor
                    extra = 34
                elif button is self.btn_more:
                    min_width = more_button_floor
                    extra = 34
                else:
                    min_width = text_button_floor
                    extra = 30
                self._set_toolbar_widget_width(button, min_width=min_width, extra=extra)

        for toggle in [self.rb_black, self.rb_white, self.cb_dual]:
            if toggle.isVisible():
                self._set_toolbar_widget_width(toggle, min_width=52, extra=28)

        if self.lbl_zoom.isVisible():
            self._set_toolbar_widget_width(self.lbl_zoom, min_width=58, extra=20)
        if self.lbl_page.isVisible():
            self._set_toolbar_widget_width(self.lbl_page, min_width=58, extra=22)

        toolbar_meta_widths = []
        for label in [self.lbl_zoom, self.lbl_page]:
            if label.isVisible():
                toolbar_meta_widths.append(label.minimumWidth())
        if toolbar_meta_widths:
            shared_toolbar_meta_width = max(toolbar_meta_widths)
            for label in [self.lbl_zoom, self.lbl_page]:
                if label.isVisible():
                    label.setMinimumWidth(shared_toolbar_meta_width)
                    label.setMaximumWidth(shared_toolbar_meta_width)

        zoom_group = getattr(self, "toolbar_zoom_group", None)
        nav_group = getattr(self, "toolbar_nav_group", None)
        if is_pdf and zoom_group and nav_group:
            try:
                zoom_group.ensurePolished()
                nav_group.ensurePolished()
                shared_group_width = max(zoom_group.sizeHint().width(), nav_group.sizeHint().width())
            except Exception:
                shared_group_width = None
            if shared_group_width:
                self._set_toolbar_group_width(zoom_group, shared_group_width)
                self._set_toolbar_group_width(nav_group, shared_group_width)
        else:
            self._set_toolbar_group_width(zoom_group, None)
            self._set_toolbar_group_width(nav_group, None)

        self._refresh_toolbar_group_visibility()

    def _apply_button_variant(self, btn, style_type):
        """根据当前主题为已创建按钮切换样式。"""
        if not btn:
            return
        btn.setProperty("btn_style", style_type)
        btn.setStyleSheet(self._get_button_style(style_type))

    def _create_toolbar_group(self, object_name="toolbarGroup"):
        """创建工具栏分组容器，降低一整排独立按钮的视觉噪音。"""
        group = QFrame()
        group.setObjectName(object_name)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        return group, layout

    def _create_toolbar_divider(self):
        divider = QFrame()
        divider.setObjectName("toolbarDivider")
        divider.setFixedWidth(1)
        divider.setMinimumHeight(24)
        return divider

    def _get_button_style(self, style_type):
        """获取按钮样式（浅色主题）"""
        theme = Theme.LIGHT
        metrics = getattr(self, "_button_density_metrics", {}) or {}
        button_font_size = metrics.get("button_font_size", 13)
        button_padding_v = metrics.get("button_padding_v", 7)
        button_padding_h = metrics.get("button_padding_h", 14)
        icon_font_size = metrics.get("icon_font_size", 14)
        icon_padding_v = metrics.get("icon_padding_v", 4)
        icon_padding_h = metrics.get("icon_padding_h", 8)
        icon_min = metrics.get("icon_min", 28)

        styles = {
            "primary": f"""
                QPushButton {{
                    background-color: {theme["primary"]};
                    color: white;
                    border: none;
                    border-radius: {Theme.BUTTON_RADIUS}px;
                    padding: {button_padding_v}px {button_padding_h}px;
                    min-height: 0px;
                    font-weight: 600;
                    font-size: {button_font_size}px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.adjust_color(theme["primary"], -15)};
                }}
                QPushButton:pressed {{
                    background-color: {Theme.adjust_color(theme["primary"], -25)};
                }}
                QPushButton:disabled {{
                    background-color: {theme["border"]};
                    color: {theme["text_secondary"]};
                }}
            """,
            "secondary": f"""
                QPushButton {{
                    background-color: #FBFCFE;
                    color: {theme["text"]};
                    border: 1px solid {theme["border"]};
                    border-radius: {Theme.BUTTON_RADIUS}px;
                    padding: {button_padding_v}px {button_padding_h}px;
                    min-height: 0px;
                    font-size: {button_font_size}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {theme["hover"]};
                    border-color: {theme["primary"]};
                }}
                QPushButton:disabled {{
                    background-color: #F5F7FA;
                    color: {theme["text_secondary"]};
                    border-color: {theme["border"]};
                }}
            """,
            "idle_primary": f"""
                QPushButton {{
                    background-color: {theme["primary"]};
                    color: white;
                    border: none;
                    border-radius: 14px;
                    padding: {button_padding_v + 2}px {button_padding_h + 6}px;
                    min-height: 0px;
                    font-size: {max(button_font_size, 14)}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {Theme.adjust_color(theme["primary"], -12)};
                }}
                QPushButton:pressed {{
                    background-color: {Theme.adjust_color(theme["primary"], -22)};
                }}
                QPushButton:disabled {{
                    background-color: {theme["border"]};
                    color: {theme["text_secondary"]};
                }}
            """,
            "idle_secondary": f"""
                QPushButton {{
                    background-color: #F5F8FC;
                    color: {theme["text"]};
                    border: 1px solid #D7E2EE;
                    border-radius: 14px;
                    padding: {button_padding_v + 2}px {button_padding_h + 4}px;
                    min-height: 0px;
                    font-size: {max(button_font_size, 14)}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: #EEF4FA;
                    border-color: #C9D9EA;
                }}
                QPushButton:pressed {{
                    background-color: #E6EEF7;
                    border-color: #C1D2E4;
                }}
                QPushButton:disabled {{
                    background-color: #F5F7FA;
                    color: {theme["text_secondary"]};
                    border-color: {theme["border"]};
                }}
            """,
            "success": f"""
                QPushButton {{
                    background-color: {theme["success"]};
                    color: white;
                    border: none;
                    border-radius: {Theme.BUTTON_RADIUS}px;
                    padding: {button_padding_v}px {button_padding_h}px;
                    min-height: 0px;
                    font-weight: 600;
                    font-size: {button_font_size}px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.adjust_color(theme["success"], -15)};
                }}
                QPushButton:pressed {{
                    background-color: {Theme.adjust_color(theme["success"], -25)};
                }}
                QPushButton:disabled {{
                    background-color: {theme["border"]};
                    color: {theme["text_secondary"]};
                }}
            """,
            "danger": f"""
                QPushButton {{
                    background-color: {theme["danger"]};
                    color: white;
                    border: none;
                    border-radius: {Theme.BUTTON_RADIUS}px;
                    padding: {button_padding_v + 1}px {button_padding_h + 2}px;
                    font-weight: 600;
                    font-size: {max(button_font_size, Theme.FONT_SIZE_NORMAL)}px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.adjust_color(theme["danger"], -15)};
                }}
                QPushButton:pressed {{
                    background-color: {Theme.adjust_color(theme["danger"], -25)};
                }}
            """,
            "icon": f"""
                QPushButton {{
                    background-color: #FBFCFE;
                    color: {theme["text"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 8px;
                    padding: {icon_padding_v}px {icon_padding_h}px;
                    min-width: {icon_min}px;
                    min-height: {icon_min}px;
                    font-size: {icon_font_size}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {theme["hover"]};
                    border-color: {theme["primary"]};
                }}
                QPushButton:pressed {{
                    background-color: {theme["pressed"]};
                }}
                QPushButton:disabled {{
                    background-color: #F5F7FA;
                    color: {theme["text_secondary"]};
                    border-color: {theme["border"]};
                }}
            """,
            "toggle": f"""
                QPushButton {{
                    background-color: #FBFCFE;
                    color: {theme["text"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 9px;
                    padding: {button_padding_v}px {button_padding_h}px;
                    min-height: 0px;
                    font-size: {button_font_size}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {theme["hover"]};
                    border-color: {theme["primary"]};
                }}
                QPushButton:checked {{
                    background-color: #E9F1FB;
                    color: {theme["primary"]};
                    border-color: #B8D0EA;
                }}
                QPushButton:pressed {{
                    background-color: {theme["pressed"]};
                }}
                QPushButton:disabled {{
                    background-color: #F5F7FA;
                    color: {theme["text_secondary"]};
                    border-color: {theme["border"]};
                }}
            """,
        }

        return styles.get(style_type, styles["primary"])
