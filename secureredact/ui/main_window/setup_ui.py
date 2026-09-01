"""
MainWindow setup_ui mixin — 925 行 UI 编排方法 (PR-B2.7 迁出)

PR-B2.7 目标:推进 main.py < 5000 行验证。
`setup_ui` 是 MainWindow 内最大单方法(925 行),包含工具栏 + 工作台 + 工作区 + 主界面所有
widget 的创建、布局、信号连接。

物理迁移策略(同 PR-B2.6 density 模式):
- 整体逐字搬迁到独立 mixin 模块
- 通过 `MainWindow` 多继承接入
- 跨实例属性引用 `self.xxx` 在 MainWindow 实例上自动解析

后续优化方向(本 PR 不做):
- 拆为多个 `_init_*` 工厂方法
- 抽离 signal connect 路由

依赖 MainWindow 上的属性(由 __init__ 部分初始化):
    - self.theme / self.Theme
    - self.workbench_panel / self.toolbar / self.main_container
    - self.btn_* / self.lbl_* / self.idle_* / self.batch_* / self.merge_*
"""
from __future__ import annotations

from PyQt6.QtWidgets import *  # PR-B5.1: setup_ui 是 925 行超大方法,widget 用量极广,
# 通配符导入避免逐个补 widget 类导致反复修补。后续 B2.6 拆分 setup_ui 后改回显式 import。
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from theme import Theme  # PR-B5.1: 补 Theme 引用


class MainWindowSetupMixin:
    """MainWindow UI 整体编排 — 工具栏 + 工作台 + 工作区 + 状态徽 + 信号连接。

    单方法 925 行(原 main.py 内完整搬迁,逐字未改)。
    """

    def setup_ui(self):
        # PR-B5.1: 跨 mixin 类引用 + main 模块级函数(密度/工具等) re-export 兼容
        # 必须在方法体顶部,不能用 `from main import ...` 模块级语句(循环 import)
        from main import (  # type: ignore[attr-defined]
            SinglePageCanvas, WebViewBridge,
            resolve_workspace_density_mode, resolve_settings_density_mode,
            _shift_density_mode,  # 密度模式 helper
        )
        # PR-B5.1: QtWebEngineWidgets 延迟导入(需 QApplication 已创建)
        # 当前 Python 3.13 + Qt6 环境下部分系统无法 import,使用 QWidget 占位
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            QWebEngineView = None  # type: ignore[assignment,misc]
        # 统一上下文条：文档上下文 + 临时任务提示
        self.default_info_bar_text = "📝 支持直接拖拽导入，系统会按文件类型自动进入 PDF 脱敏、Word 替换、批量 Word 或图片合并。"
        self.workbench_panel = QFrame()
        self.workbench_panel.setObjectName("workbenchPanel")
        workbench_layout = QVBoxLayout(self.workbench_panel)
        workbench_layout.setContentsMargins(16, 10, 16, 10)
        workbench_layout.setSpacing(4)
        self.workbench_layout = workbench_layout

        context_top_layout = QHBoxLayout()
        context_top_layout.setSpacing(14)
        context_top_layout.setContentsMargins(0, 0, 0, 0)
        self.context_top_layout = context_top_layout
        workbench_text = QVBoxLayout()
        workbench_text.setContentsMargins(0, 0, 0, 0)
        workbench_text.setSpacing(4)
        self.workbench_text_layout = workbench_text

        self.lbl_workbench_title = QLabel("欢迎使用 SecureRedact")
        self.lbl_workbench_title.setObjectName("workbenchTitle")
        self.lbl_workbench_subtitle = QLabel("拖拽或打开文件即可开始处理。")
        self.lbl_workbench_subtitle.setObjectName("workbenchSubtitle")
        self.lbl_workbench_subtitle.setWordWrap(True)
        workbench_text.addWidget(self.lbl_workbench_title)
        workbench_text.addWidget(self.lbl_workbench_subtitle)

        self.lbl_workbench_focus = QLabel("开始")
        self.lbl_workbench_focus.setObjectName("workbenchFocus")
        self.btn_workbench_feedback = self.create_btn("使用/反馈", self.show_feedback, style="secondary")
        self.btn_workbench_feedback.hide()

        context_top_layout.addLayout(workbench_text, stretch=1)
        context_top_layout.addWidget(self.btn_workbench_feedback, alignment=Qt.AlignmentFlag.AlignVCenter)
        context_top_layout.addWidget(self.lbl_workbench_focus, alignment=Qt.AlignmentFlag.AlignVCenter)
        workbench_layout.addLayout(context_top_layout)

        workbench_guidance_layout = QGridLayout()
        workbench_guidance_layout.setHorizontalSpacing(8)
        workbench_guidance_layout.setVerticalSpacing(8)
        workbench_guidance_layout.setContentsMargins(0, 0, 0, 0)
        workbench_guidance_layout.setColumnStretch(0, 1)
        workbench_guidance_layout.setColumnStretch(1, 1)
        self.workbench_guidance_layout = workbench_guidance_layout
        self.workbench_guidance_labels = []
        for index in range(4):
            guidance_label = QLabel("")
            guidance_label.setObjectName("workbenchHintTag")
            guidance_label.setWordWrap(True)
            guidance_label.hide()
            row = index // 2
            col = index % 2
            workbench_guidance_layout.addWidget(guidance_label, row, col)
            self.workbench_guidance_labels.append(guidance_label)
        workbench_layout.addLayout(workbench_guidance_layout)

        self.info_bar = QLabel(self.default_info_bar_text)
        self.info_bar.setObjectName("contextMessage")
        self.info_bar.setWordWrap(True)
        self.info_bar.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        workbench_layout.addWidget(self.info_bar)

        # 工具栏
        toolbar = QFrame()
        toolbar.setObjectName("toolbarRoot")
        toolbar.setFixedHeight(54)
        self.toolbar = toolbar  # 保存引用

        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 7, 16, 7)
        tb_layout.setSpacing(10)
        self.toolbar_layout = tb_layout

        self.toolbar_primary_group, self.toolbar_primary_layout = self._create_toolbar_group("toolbarGroupStrong")
        tb_layout.addWidget(self.toolbar_primary_group)
        self.btn_open = self.create_btn("打开", self.open_pdf)
        self.toolbar_primary_layout.addWidget(self.btn_open)
        self.btn_scan = self.create_btn("智能脱敏", self.start_ocr, enabled=False, style="success")
        self.toolbar_primary_layout.addWidget(self.btn_scan)

        self.toolbar_word_group, self.toolbar_word_layout = self._create_toolbar_group()
        tb_layout.addWidget(self.toolbar_word_group)
        self.btn_settings = self.create_btn("高级设置", self.open_settings, style="secondary")
        self.toolbar_word_layout.addWidget(self.btn_settings)
        self.btn_compare_toggle = self.create_btn("对比预览", self.toggle_word_compare_preview, style="secondary")
        self.toolbar_word_layout.addWidget(self.btn_compare_toggle)

        self.toolbar_pdf_group, self.toolbar_pdf_layout = self._create_toolbar_group()
        tb_layout.addWidget(self.toolbar_pdf_group)
        self.rb_black = self.create_btn("黑遮罩", self.update_canvas_color, style="toggle")
        self.rb_black.setObjectName("toolbarToggleButton")
        self.rb_black.setCheckable(True)
        self.rb_black.setChecked(True)
        self.rb_white = self.create_btn("白遮罩", self.update_canvas_color, style="toggle")
        self.rb_white.setObjectName("toolbarToggleButton")
        self.rb_white.setCheckable(True)
        self.bg_color = QButtonGroup(self)
        self.bg_color.setExclusive(True)
        self.bg_color.addButton(self.rb_black)
        self.bg_color.addButton(self.rb_white)
        self.toolbar_pdf_layout.addWidget(self.rb_black)
        self.toolbar_pdf_layout.addWidget(self.rb_white)

        self.cb_dual = self.create_btn("双页", self._toggle_dual_toolbar, style="toggle")
        self.cb_dual.setObjectName("toolbarToggleButton")
        self.cb_dual.setCheckable(True)
        self.toolbar_pdf_layout.addWidget(self.cb_dual)

        self.btn_fit = self.create_btn("适应", self.fit_page, style="secondary")
        self.toolbar_pdf_layout.addWidget(self.btn_fit)
        self.btn_fit.hide()

        tb_layout.addStretch()

        self.toolbar_zoom_group, self.toolbar_zoom_layout = self._create_toolbar_group()
        tb_layout.addWidget(self.toolbar_zoom_group)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setObjectName("toolbarMeta")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_zoom_out = self.create_btn("-", self.zoom_out, style="icon", tooltip="缩小预览")
        self.toolbar_zoom_layout.addWidget(self.btn_zoom_out)
        self.toolbar_zoom_layout.addWidget(self.lbl_zoom)
        self.btn_zoom_in = self.create_btn("+", self.zoom_in, style="icon", tooltip="放大预览")
        self.toolbar_zoom_layout.addWidget(self.btn_zoom_in)

        self.toolbar_nav_group, self.toolbar_nav_layout = self._create_toolbar_group()
        tb_layout.addWidget(self.toolbar_nav_group)
        self.btn_go_first = self.create_btn("", self.go_first, style="icon", tooltip="跳到第一页")
        self.toolbar_nav_layout.addWidget(self.btn_go_first)
        self.btn_prev_page = self.create_btn("", lambda: self.change_page(-1), style="icon", tooltip="上一页")
        self.toolbar_nav_layout.addWidget(self.btn_prev_page)
        self.lbl_page = QLabel("0 / 0")
        self.lbl_page.setObjectName("toolbarMeta")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toolbar_nav_layout.addWidget(self.lbl_page)
        self.btn_next_page = self.create_btn("", lambda: self.change_page(1 if not self.dual_view else 2), style="icon", tooltip="下一页")
        self.toolbar_nav_layout.addWidget(self.btn_next_page)
        self.btn_go_last = self.create_btn("", self.go_last, style="icon", tooltip="跳到最后一页")
        self.toolbar_nav_layout.addWidget(self.btn_go_last)

        self.toolbar_utility_group, self.toolbar_utility_layout = self._create_toolbar_group("toolbarUtilityGroup")
        tb_layout.addWidget(self.toolbar_utility_group)
        self.btn_fit_utility = self.create_btn("适应页面", self.fit_page, style="secondary")
        self.btn_fit_utility.hide()
        self.toolbar_utility_layout.addWidget(self.btn_fit_utility)
        self.btn_feedback = self.create_btn("使用/反馈", self.show_feedback, style="secondary")
        self.toolbar_utility_layout.addWidget(self.btn_feedback)
        self.btn_more = self.create_btn("更多", self._show_toolbar_more_menu, style="secondary")
        self.btn_more.setObjectName("toolbarMoreButton")
        self.toolbar_more_menu = QMenu(self)
        self.btn_more.hide()
        self.toolbar_utility_layout.addWidget(self.btn_more)
        self.btn_save = self.create_btn("导出", self.save_pdf, enabled=False)
        self.toolbar_utility_layout.addWidget(self.btn_save)
        self._apply_native_toolbar_icons()

        main = QWidget()
        main.setObjectName("appRoot")
        self.setCentralWidget(main)
        layout = QVBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.workbench_panel)
        layout.addWidget(toolbar)

        # 滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_style = (
            f"background-color: {{0}}; "
            f"border-radius: {Theme.BORDER_RADIUS}px; "
            f"border: none;"
        )

        # v1.1.11: 使用固定的 canvas_container，通过隐藏/显示实现单/双页切换
        self.canvas_left = SinglePageCanvas(0)
        self.canvas_right = SinglePageCanvas(1)
        # v1.1.11: 注入 main_window 引用,供 canvas 右键菜单访问 override store
        self.canvas_left.set_main_window(self)
        self.canvas_right.set_main_window(self)

        # 容器始终作为 scroll 的 widget
        self.canvas_container = QWidget()
        self.pdf_workspace_outer_layout = QVBoxLayout(self.canvas_container)
        self.pdf_workspace_outer_layout.setContentsMargins(14, 10, 14, 16)
        self.pdf_workspace_outer_layout.setSpacing(0)
        self.pdf_workspace_shell = QFrame()
        self.pdf_workspace_shell.setObjectName("previewWorkspaceCard")
        self.pdf_workspace_shell.setMaximumWidth(1940)
        self.pdf_workspace_shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pdf_workspace_shell_layout = QVBoxLayout(self.pdf_workspace_shell)
        pdf_workspace_shell_layout.setContentsMargins(8, 8, 8, 8)
        pdf_workspace_shell_layout.setSpacing(0)
        self.pdf_workspace_shell_layout = pdf_workspace_shell_layout
        self.pdf_stage_content = QWidget()
        self.pdf_stage_content.setObjectName("previewStage")
        self.canvas_layout = QHBoxLayout(self.pdf_stage_content)
        self.canvas_layout.setContentsMargins(10, 10, 10, 10)
        self.canvas_layout.setSpacing(12)
        self.canvas_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.canvas_left.setObjectName("pdfPageCanvas")
        self.canvas_right.setObjectName("pdfPageCanvas")
        self.canvas_layout.addWidget(self.canvas_left)
        self.canvas_layout.addWidget(self.canvas_right)
        pdf_workspace_shell_layout.addWidget(self.pdf_stage_content)
        pdf_workspace_row_layout = QHBoxLayout()
        pdf_workspace_row_layout.setContentsMargins(0, 0, 0, 0)
        pdf_workspace_row_layout.setSpacing(0)
        pdf_workspace_row_layout.addStretch(1)
        pdf_workspace_row_layout.addWidget(self.pdf_workspace_shell, 18)
        pdf_workspace_row_layout.addStretch(1)
        self.pdf_workspace_row_layout = pdf_workspace_row_layout
        self.pdf_workspace_outer_layout.addLayout(pdf_workspace_row_layout, 1)

        # 信号连接
        self.canvas_left.rect_added.connect(self.on_rect_added)
        self.canvas_left.rect_removed.connect(self.on_rect_removed)
        self.canvas_left.zoom_request.connect(self.handle_zoom_request)
        self.canvas_left.page_change_request.connect(self.handle_page_change_request)

        self.canvas_right.rect_added.connect(self.on_rect_added)
        self.canvas_right.rect_removed.connect(self.on_rect_removed)
        self.canvas_right.zoom_request.connect(self.handle_zoom_request)
        self.canvas_right.page_change_request.connect(self.handle_page_change_request)

        # 设置 canvas 大小策略
        for canvas in [self.canvas_left, self.canvas_right]:
            canvas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # 预先创建 Word 预览视图（左：原文，右：替换后）
        # PR-B5.1: QtWebEngineView 在某些环境(无 OpenGL/QtWebEngineWidgets)不可用,fallback 到 QWidget
        try:
            self.word_preview = QWebEngineView() if QWebEngineView else QWidget()
            self.word_preview_replaced = QWebEngineView() if QWebEngineView else QWidget()
            self.word_preview_replaced.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.word_preview.loadFinished.connect(self._on_word_preview_load_finished)
            self.word_preview_replaced.loadFinished.connect(self._on_word_replaced_load_finished)
        except (AttributeError, TypeError):
            self.word_preview = QWidget()
            self.word_preview_replaced = QWidget()

        self.idle_workspace_container = QWidget()
        idle_outer_layout = QVBoxLayout(self.idle_workspace_container)
        idle_outer_layout.setContentsMargins(30, 20, 30, 30)
        idle_outer_layout.setSpacing(0)
        self.idle_outer_layout = idle_outer_layout

        idle_card = QFrame()
        idle_card.setObjectName("workspaceCard")
        idle_card.setMaximumWidth(1320)
        idle_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.idle_card = idle_card
        idle_card_layout = QVBoxLayout(idle_card)
        idle_card_layout.setContentsMargins(28, 26, 28, 26)
        idle_card_layout.setSpacing(16)
        self.idle_card_layout = idle_card_layout

        idle_hero_panel = QFrame()
        idle_hero_panel.setObjectName("idleHeroPanel")
        idle_hero_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        idle_hero_layout = QVBoxLayout(idle_hero_panel)
        idle_hero_layout.setContentsMargins(0, 0, 0, 0)
        idle_hero_layout.setSpacing(12)
        self.idle_hero_panel = idle_hero_panel
        self.idle_hero_layout = idle_hero_layout

        idle_title_row_layout = QHBoxLayout()
        idle_title_row_layout.setContentsMargins(0, 0, 0, 0)
        idle_title_row_layout.setSpacing(18)
        self.idle_title_row_layout = idle_title_row_layout

        idle_headline_layout = QVBoxLayout()
        idle_headline_layout.setContentsMargins(0, 0, 0, 0)
        idle_headline_layout.setSpacing(6)
        self.idle_headline_layout = idle_headline_layout

        idle_title = QLabel("选择开始方式")
        idle_title.setObjectName("workspaceTitle")
        idle_subtitle = QLabel("打开或拖拽文件，系统会自动进入对应模式。")
        idle_subtitle.setObjectName("workspaceSubtitle")
        idle_subtitle.setWordWrap(True)
        idle_headline_layout.addWidget(idle_title)
        idle_headline_layout.addWidget(idle_subtitle)

        idle_title_tools_layout = QVBoxLayout()
        idle_title_tools_layout.setContentsMargins(0, 0, 0, 0)
        idle_title_tools_layout.setSpacing(8)
        self.idle_title_tools_layout = idle_title_tools_layout

        idle_badge_row_layout = QHBoxLayout()
        idle_badge_row_layout.setContentsMargins(0, 0, 0, 0)
        idle_badge_row_layout.setSpacing(8)
        self.idle_badge_row_layout = idle_badge_row_layout
        self.lbl_idle_offline_badge = QLabel("本地离线")
        self.lbl_idle_offline_badge.setObjectName("idleHeroBadge")
        self.lbl_idle_auto_badge = QLabel("自动分流")
        self.lbl_idle_auto_badge.setObjectName("idleHeroBadge")
        idle_badge_row_layout.addStretch()
        idle_badge_row_layout.addWidget(self.lbl_idle_offline_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        idle_badge_row_layout.addWidget(self.lbl_idle_auto_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        idle_title_tools_layout.addLayout(idle_badge_row_layout)
        idle_title_tools_layout.addStretch(1)

        idle_title_row_layout.addLayout(idle_headline_layout, stretch=1)
        idle_title_row_layout.addLayout(idle_title_tools_layout)
        idle_hero_layout.addLayout(idle_title_row_layout)

        idle_action_panel = QFrame()
        idle_action_panel.setObjectName("idleActionPanel")
        idle_action_panel_layout = QVBoxLayout(idle_action_panel)
        idle_action_panel_layout.setContentsMargins(0, 0, 0, 0)
        idle_action_panel_layout.setSpacing(8)
        self.idle_action_panel = idle_action_panel
        self.idle_action_panel_layout = idle_action_panel_layout

        self.idle_start_card = QFrame()
        self.idle_start_card.setObjectName("idleStartCard")
        idle_start_layout = QVBoxLayout(self.idle_start_card)
        idle_start_layout.setContentsMargins(18, 16, 18, 16)
        idle_start_layout.setSpacing(8)
        self.idle_start_layout = idle_start_layout
        self.lbl_idle_start_title = QLabel("开始处理")
        self.lbl_idle_start_title.setObjectName("idleStartTitle")
        self.lbl_idle_start_text = QLabel("选择文件或直接拖拽到窗口，系统会自动进入对应模式。")
        self.lbl_idle_start_text.setObjectName("idleStartText")
        self.lbl_idle_start_text.setWordWrap(True)
        self.btn_idle_open = self.create_btn("选择文件", self.open_pdf)
        self.btn_idle_open.setObjectName("idlePrimaryActionButton")
        self.btn_idle_open.setProperty("btn_style", "idle_primary")
        self.btn_idle_open.setStyleSheet(self._get_button_style("idle_primary"))
        self.lbl_idle_drop_hint = QLabel("支持直接拖拽到窗口")
        self.lbl_idle_drop_hint.setObjectName("idleDropHint")
        self.lbl_idle_drop_hint.setWordWrap(True)
        self.idle_start_footer = QWidget()
        self.idle_start_footer_layout = QVBoxLayout(self.idle_start_footer)
        self.idle_start_footer_layout.setContentsMargins(0, 0, 0, 0)
        self.idle_start_footer_layout.setSpacing(8)
        self.idle_start_footer_layout.addWidget(self.lbl_idle_drop_hint)
        self.idle_start_footer_layout.addWidget(self.btn_idle_open, alignment=Qt.AlignmentFlag.AlignLeft)
        idle_start_layout.addWidget(self.lbl_idle_start_title)
        idle_start_layout.addWidget(self.lbl_idle_start_text)
        idle_start_layout.addStretch(1)
        idle_start_layout.addWidget(self.idle_start_footer)

        idle_action_panel_layout.addWidget(self.idle_start_card)
        idle_hero_layout.addWidget(idle_action_panel)
        idle_card_layout.addWidget(idle_hero_panel)

        idle_flow_panel = QFrame()
        idle_flow_panel.setObjectName("idleFlowPanel")
        idle_flow_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        idle_flow_layout = QHBoxLayout(idle_flow_panel)
        idle_flow_layout.setContentsMargins(0, 2, 0, 0)
        idle_flow_layout.setSpacing(10)
        self.idle_flow_panel = idle_flow_panel
        self.idle_flow_layout = idle_flow_layout

        self.lbl_idle_tip = QLabel("推荐流程")
        self.lbl_idle_tip.setObjectName("idleFlowTitle")
        idle_flow_layout.addWidget(self.lbl_idle_tip)

        workflow_layout = QHBoxLayout()
        workflow_layout.setSpacing(8)
        self.workflow_layout = workflow_layout
        self.workflow_step_labels = []
        for step_text in ["1 导入", "2 规则", "3 处理", "4 复核", "5 导出"]:
            step_label = QLabel(step_text)
            step_label.setObjectName("workflowStep")
            self.workflow_step_labels.append(step_label)
            workflow_layout.addWidget(step_label)
        workflow_layout.addStretch()
        idle_flow_layout.addLayout(workflow_layout, stretch=1)
        idle_card_layout.addWidget(idle_flow_panel)
        idle_card_layout.addSpacing(2)

        idle_section_panel = QFrame()
        idle_section_panel.setObjectName("idleSectionPanel")
        idle_section_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        idle_section_layout = QVBoxLayout(idle_section_panel)
        idle_section_layout.setContentsMargins(0, 0, 0, 0)
        idle_section_layout.setSpacing(10)
        self.idle_section_panel = idle_section_panel
        self.idle_section_layout = idle_section_layout

        idle_section_header_layout = QHBoxLayout()
        idle_section_header_layout.setContentsMargins(0, 0, 0, 0)
        idle_section_header_layout.setSpacing(8)
        self.idle_section_header_layout = idle_section_header_layout

        self.lbl_idle_section = QLabel("四大功能")
        self.lbl_idle_section.setObjectName("idleSectionLabel")
        self.lbl_idle_section_hint = QLabel("按文件类型自动进入")
        self.lbl_idle_section_hint.setObjectName("idleSectionHint")
        idle_section_header_layout.addWidget(self.lbl_idle_section)
        idle_section_header_layout.addStretch()
        idle_section_header_layout.addWidget(self.lbl_idle_section_hint)
        idle_section_layout.addLayout(idle_section_header_layout)

        route_specs = [
            ("PDF 脱敏", "单文档", "打开 PDF，智能脱敏或手动画框。", "pdf"),
            ("Word 替换", "单文档", "打开 Word，替换并对比预览。", "word"),
            ("批量 Word", "批量处理", "导入多份 Word，确认规则后批量执行。", "batch"),
            ("图片合并 PDF", "图片工具", "导入图片，排序后生成 PDF。", "image"),
        ]

        idle_routes_container = QWidget()
        idle_routes_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        idle_routes_layout = QGridLayout(idle_routes_container)
        idle_routes_layout.setContentsMargins(0, 0, 0, 0)
        idle_routes_layout.setHorizontalSpacing(16)
        idle_routes_layout.setVerticalSpacing(16)
        idle_routes_layout.setColumnStretch(0, 1)
        idle_routes_layout.setColumnStretch(1, 1)
        self.idle_routes_container = idle_routes_container
        self.idle_routes_layout = idle_routes_layout
        self.idle_route_cards = []
        for index, (title_text, meta_text, desc_text, accent_key) in enumerate(route_specs):
            route_card = QFrame()
            route_card.setObjectName("routeCard")
            route_card.setProperty("routeTone", accent_key)
            route_card.setMinimumHeight(84)
            route_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.idle_route_cards.append(route_card)
            route_card_layout = QVBoxLayout(route_card)
            route_card_layout.setContentsMargins(14, 10, 14, 10)
            route_card_layout.setSpacing(4)
            route_accent = QFrame()
            route_accent.setObjectName("routeCardAccent")
            route_accent.setProperty("routeAccent", accent_key)
            route_accent.setFixedHeight(4)
            route_head_layout = QHBoxLayout()
            route_head_layout.setContentsMargins(0, 0, 0, 0)
            route_head_layout.setSpacing(8)
            route_title = QLabel(title_text)
            route_title.setObjectName("routeCardTitle")
            route_meta = QLabel(meta_text)
            route_meta.setObjectName("routeCardMeta")
            route_meta.setProperty("routeTone", accent_key)
            route_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
            route_desc = QLabel(desc_text)
            route_desc.setObjectName("routeCardText")
            route_desc.setWordWrap(True)
            route_desc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            route_card_layout.addWidget(route_accent)
            route_head_layout.addWidget(route_title)
            route_head_layout.addStretch()
            route_head_layout.addWidget(route_meta, alignment=Qt.AlignmentFlag.AlignTop)
            route_card_layout.addLayout(route_head_layout)
            route_card_layout.addWidget(route_desc)
            idle_routes_layout.addWidget(route_card, index // 2, index % 2)
        idle_section_layout.addWidget(idle_routes_container, 0)
        idle_card_layout.addWidget(idle_section_panel)

        idle_card_row_layout = QHBoxLayout()
        idle_card_row_layout.setContentsMargins(0, 0, 0, 0)
        idle_card_row_layout.setSpacing(0)
        idle_card_row_layout.addStretch(1)
        idle_card_row_layout.addWidget(idle_card, 12)
        idle_card_row_layout.addStretch(1)
        self.idle_card_row_layout = idle_card_row_layout
        idle_outer_layout.addLayout(idle_card_row_layout, 1)

        self.batch_workspace_container = QWidget()
        batch_outer_layout = QVBoxLayout(self.batch_workspace_container)
        batch_outer_layout.setContentsMargins(26, 24, 26, 28)
        batch_outer_layout.setSpacing(0)
        self.batch_outer_layout = batch_outer_layout

        batch_card = QFrame()
        batch_card.setObjectName("batchWorkspaceCard")
        batch_card.setMaximumWidth(1500)
        batch_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.batch_card = batch_card
        batch_card_layout = QVBoxLayout(batch_card)
        batch_card_layout.setContentsMargins(28, 24, 28, 24)
        batch_card_layout.setSpacing(14)
        self.batch_card_layout = batch_card_layout

        batch_header_layout = QHBoxLayout()
        batch_header_layout.setSpacing(12)
        self.batch_header_layout = batch_header_layout
        batch_header_text = QVBoxLayout()
        batch_header_text.setSpacing(4)
        self.batch_header_text_layout = batch_header_text
        self.lbl_batch_title = QLabel("批量 Word 工作台")
        self.lbl_batch_title.setObjectName("batchTitle")
        self.lbl_batch_subtitle = QLabel("先确认文档替换规则，再执行批量替换。处理中可以停止，已完成文件会保留。")
        self.lbl_batch_subtitle.setObjectName("batchSubtitle")
        self.lbl_batch_subtitle.setWordWrap(True)
        batch_header_text.addWidget(self.lbl_batch_title)
        batch_header_text.addWidget(self.lbl_batch_subtitle)
        self.lbl_batch_stage_badge = QLabel("等待开始")
        self.lbl_batch_stage_badge.setObjectName("batchStageBadge")
        batch_header_layout.addLayout(batch_header_text, stretch=1)
        batch_header_layout.addWidget(self.lbl_batch_stage_badge, alignment=Qt.AlignmentFlag.AlignTop)
        batch_card_layout.addLayout(batch_header_layout)

        self.lbl_batch_meta = QLabel("批量模式会优先进入规则确认，再进入执行。")
        self.lbl_batch_meta.setObjectName("batchMeta")
        self.lbl_batch_meta.setWordWrap(True)
        batch_card_layout.addWidget(self.lbl_batch_meta)

        batch_stage_layout = QGridLayout()
        batch_stage_layout.setContentsMargins(0, 0, 0, 0)
        batch_stage_layout.setHorizontalSpacing(12)
        batch_stage_layout.setVerticalSpacing(12)
        self.batch_stage_layout = batch_stage_layout
        self.batch_stage_cards = []
        for title_text, note_text in [
            ("1 规则确认", "先核对文档数量、统一替换文本和 Word 规则。"),
            ("2 执行替换", "系统逐个处理文档，支持跳过异常文件。"),
            ("3 查看结果", "处理结束后集中查看成功、失败和输出结果。"),
        ]:
            step_card = QFrame()
            step_card.setObjectName("batchStepCard")
            step_layout = QVBoxLayout(step_card)
            step_layout.setContentsMargins(14, 12, 14, 12)
            step_layout.setSpacing(4)
            step_title = QLabel(title_text)
            step_title.setObjectName("batchStepTitle")
            step_note = QLabel(note_text)
            step_note.setObjectName("batchStepNote")
            step_note.setWordWrap(True)
            step_layout.addWidget(step_title)
            step_layout.addWidget(step_note)
            self.batch_stage_cards.append((step_card, step_title, step_note))
        self._rebuild_batch_stage_layout("wide")
        batch_card_layout.addLayout(batch_stage_layout)

        batch_metrics_layout = QGridLayout()
        batch_metrics_layout.setContentsMargins(0, 0, 0, 0)
        batch_metrics_layout.setHorizontalSpacing(10)
        batch_metrics_layout.setVerticalSpacing(10)
        self.batch_metrics_layout = batch_metrics_layout
        self.batch_metric_cards = []
        self.lbl_batch_metric_files = None
        self.lbl_batch_metric_files_note = None
        self.lbl_batch_metric_rules = None
        self.lbl_batch_metric_rules_note = None
        self.lbl_batch_metric_progress = None
        self.lbl_batch_metric_progress_note = None
        self.lbl_batch_metric_result = None
        self.lbl_batch_metric_result_note = None
        for key, title_text in [
            ("files", "已选文档"),
            ("rules", "启用规则"),
            ("progress", "当前进度"),
            ("result", "执行结果"),
        ]:
            metric_card, metric_value, metric_note = self._create_batch_metric_card(title_text)
            setattr(self, f"lbl_batch_metric_{key}", metric_value)
            setattr(self, f"lbl_batch_metric_{key}_note", metric_note)
            self.batch_metric_cards.append(metric_card)
        self._rebuild_batch_metrics_layout("wide")
        batch_card_layout.addLayout(batch_metrics_layout)

        batch_actions_layout = QGridLayout()
        batch_actions_layout.setContentsMargins(0, 2, 0, 0)
        batch_actions_layout.setHorizontalSpacing(10)
        batch_actions_layout.setVerticalSpacing(10)
        self.batch_actions_layout = batch_actions_layout
        self.btn_batch_edit_rules = self.create_btn("重新设置规则", self._reopen_batch_rule_setup, style="secondary")
        self.btn_batch_pick_files = self.create_btn("重新选择文档", self._start_batch_replace_from_workspace, style="secondary")
        self.btn_batch_retry_failed = self.create_btn("仅重试失败文档", self._retry_failed_batch_files, style="secondary")
        self.btn_batch_open_output = self.create_btn("打开输出位置", self._open_batch_output_location, style="secondary")
        self.batch_action_buttons = [
            self.btn_batch_edit_rules,
            self.btn_batch_pick_files,
            self.btn_batch_retry_failed,
            self.btn_batch_open_output,
        ]
        self._rebuild_batch_action_layout("wide")
        batch_card_layout.addLayout(batch_actions_layout)

        self.lbl_batch_current_file = QLabel("当前文件：尚未开始")
        self.lbl_batch_current_file.setObjectName("batchCurrentFile")
        self.lbl_batch_current_file.setWordWrap(True)
        batch_card_layout.addWidget(self.lbl_batch_current_file)

        batch_detail_layout = QGridLayout()
        batch_detail_layout.setContentsMargins(0, 0, 0, 0)
        batch_detail_layout.setHorizontalSpacing(14)
        batch_detail_layout.setVerticalSpacing(14)
        self.batch_detail_layout = batch_detail_layout

        self.batch_summary_section = QFrame()
        self.batch_summary_section.setObjectName("batchDetailSection")
        self.batch_summary_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        batch_summary_section_layout = QVBoxLayout(self.batch_summary_section)
        batch_summary_section_layout.setContentsMargins(0, 0, 0, 0)
        batch_summary_section_layout.setSpacing(8)
        self.batch_summary_section_layout = batch_summary_section_layout
        self.lbl_batch_summary_hint = QLabel("本轮摘要")
        self.lbl_batch_summary_hint.setObjectName("batchSectionLabel")
        batch_summary_section_layout.addWidget(self.lbl_batch_summary_hint)

        self.batch_summary_browser = QTextBrowser()
        self.batch_summary_browser.setObjectName("batchSummaryBrowser")
        self.batch_summary_browser.setOpenExternalLinks(False)
        self.batch_summary_browser.setMinimumHeight(148)
        self.batch_summary_browser.setMaximumHeight(220)
        self.batch_summary_browser.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        batch_summary_section_layout.addWidget(self.batch_summary_browser)

        self.batch_result_section = QFrame()
        self.batch_result_section.setObjectName("batchDetailSection")
        self.batch_result_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        batch_result_section_layout = QVBoxLayout(self.batch_result_section)
        batch_result_section_layout.setContentsMargins(0, 0, 0, 0)
        batch_result_section_layout.setSpacing(8)
        self.batch_result_section_layout = batch_result_section_layout
        self.lbl_batch_result_hint = QLabel("结果清单")
        self.lbl_batch_result_hint.setObjectName("batchSectionLabel")

        batch_result_toolbar = QHBoxLayout()
        batch_result_toolbar.setSpacing(8)
        batch_result_toolbar.setContentsMargins(0, 0, 0, 0)
        batch_result_toolbar.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.batch_result_toolbar = batch_result_toolbar
        self.lbl_batch_result_meta = QLabel("结果计数：等待本轮结果")
        self.lbl_batch_result_meta.setObjectName("batchResultMeta")
        self.lbl_batch_result_meta.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        batch_result_toolbar.addWidget(self.lbl_batch_result_meta, stretch=1)
        self.btn_batch_filter_all = QPushButton("全部")
        self.btn_batch_filter_success = QPushButton("仅成功")
        self.btn_batch_filter_failed = QPushButton("仅失败")
        for filter_mode, button in [
            ("all", self.btn_batch_filter_all),
            ("success", self.btn_batch_filter_success),
            ("failed", self.btn_batch_filter_failed),
        ]:
            button.setObjectName("batchFilterButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoDefault(False)
            button.setDefault(False)
            button.clicked.connect(lambda _checked=False, mode=filter_mode: self._set_batch_result_filter_mode(mode))
            batch_result_toolbar.addWidget(button)
        batch_result_header_layout = QHBoxLayout()
        batch_result_header_layout.setContentsMargins(0, 0, 0, 0)
        batch_result_header_layout.setSpacing(12)
        batch_result_header_layout.addWidget(self.lbl_batch_result_hint, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
        batch_result_header_layout.addLayout(batch_result_toolbar, stretch=2)
        self.batch_result_header_layout = batch_result_header_layout
        batch_result_section_layout.addLayout(batch_result_header_layout)

        self.batch_result_table = QTableWidget(0, 4)
        self.batch_result_table.setObjectName("batchResultTable")
        self.batch_result_table.setHorizontalHeaderLabels(["状态", "输入文档", "结果说明", "操作"])
        self.batch_result_table.verticalHeader().setVisible(False)
        self.batch_result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.batch_result_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.batch_result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.batch_result_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.batch_result_table.setAlternatingRowColors(False)
        self.batch_result_table.setShowGrid(False)
        self.batch_result_table.setWordWrap(True)
        self.batch_result_table.setMinimumHeight(196)
        self.batch_result_table.setMaximumHeight(280)
        batch_header = self.batch_result_table.horizontalHeader()
        batch_header.setHighlightSections(False)
        batch_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        batch_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        batch_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        batch_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        if self.batch_result_table.horizontalHeaderItem(0):
            self.batch_result_table.horizontalHeaderItem(0).setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
        if self.batch_result_table.horizontalHeaderItem(3):
            self.batch_result_table.horizontalHeaderItem(3).setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
        self.batch_result_table.cellDoubleClicked.connect(self._open_batch_result_row)
        batch_result_section_layout.addWidget(self.batch_result_table)

        self.batch_log_section = QFrame()
        self.batch_log_section.setObjectName("batchDetailSection")
        self.batch_log_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        batch_log_section_layout = QVBoxLayout(self.batch_log_section)
        batch_log_section_layout.setContentsMargins(0, 0, 0, 0)
        batch_log_section_layout.setSpacing(8)
        self.batch_log_section_layout = batch_log_section_layout
        self.lbl_batch_log_hint = QLabel("处理动态")
        self.lbl_batch_log_hint.setObjectName("batchSectionLabel")
        batch_log_section_layout.addWidget(self.lbl_batch_log_hint)

        self.batch_log_list = QListWidget()
        self.batch_log_list.setObjectName("batchLogList")
        self.batch_log_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.batch_log_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.batch_log_list.setAlternatingRowColors(False)
        self.batch_log_list.setMinimumHeight(260)
        batch_log_section_layout.addWidget(self.batch_log_list)

        self._rebuild_batch_detail_layout("wide")
        batch_card_layout.addLayout(batch_detail_layout, stretch=1)

        batch_card_row_layout = QHBoxLayout()
        batch_card_row_layout.setContentsMargins(0, 0, 0, 0)
        batch_card_row_layout.setSpacing(0)
        batch_card_row_layout.addStretch(1)
        batch_card_row_layout.addWidget(batch_card, 10)
        batch_card_row_layout.addStretch(1)
        self.batch_card_row_layout = batch_card_row_layout
        batch_outer_layout.addLayout(batch_card_row_layout)
        batch_outer_layout.addStretch(1)

        self.merge_workspace_container = QWidget()
        merge_outer_layout = QVBoxLayout(self.merge_workspace_container)
        merge_outer_layout.setContentsMargins(26, 24, 26, 28)
        merge_outer_layout.setSpacing(0)
        self.merge_outer_layout = merge_outer_layout

        merge_card = QFrame()
        merge_card.setObjectName("mergeWorkspaceCard")
        merge_card.setMaximumWidth(1500)
        merge_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.merge_card = merge_card
        merge_card_layout = QVBoxLayout(merge_card)
        merge_card_layout.setContentsMargins(28, 24, 28, 24)
        merge_card_layout.setSpacing(14)
        self.merge_card_layout = merge_card_layout
        merge_header_layout = QHBoxLayout()
        merge_header_layout.setSpacing(12)
        self.merge_header_layout = merge_header_layout
        merge_header_text = QVBoxLayout()
        merge_header_text.setSpacing(4)
        self.merge_header_text_layout = merge_header_text
        self.lbl_merge_title = QLabel("图片正在合并为 PDF")
        self.lbl_merge_title.setObjectName("workspaceTitle")
        self.lbl_merge_subtitle = QLabel("系统会先按当前顺序生成 PDF，完成后自动进入 PDF 脱敏工作台。")
        self.lbl_merge_subtitle.setObjectName("workspaceSubtitle")
        self.lbl_merge_subtitle.setWordWrap(True)
        merge_header_text.addWidget(self.lbl_merge_title)
        merge_header_text.addWidget(self.lbl_merge_subtitle)
        self.lbl_merge_stage_badge = QLabel("等待开始")
        self.lbl_merge_stage_badge.setObjectName("batchStageBadge")
        merge_header_layout.addLayout(merge_header_text, stretch=1)
        merge_header_layout.addWidget(self.lbl_merge_stage_badge, alignment=Qt.AlignmentFlag.AlignTop)
        self.lbl_merge_meta = QLabel("当前还没有开始合并。")
        self.lbl_merge_meta.setObjectName("workspaceHint")
        self.lbl_merge_meta.setWordWrap(True)
        merge_card_layout.addLayout(merge_header_layout)
        merge_card_layout.addWidget(self.lbl_merge_meta)

        merge_stage_layout = QGridLayout()
        merge_stage_layout.setContentsMargins(0, 0, 0, 0)
        merge_stage_layout.setHorizontalSpacing(12)
        merge_stage_layout.setVerticalSpacing(12)
        self.merge_stage_layout = merge_stage_layout
        self.merge_stage_cards = []
        for title_text, note_text in [
            ("1 整理顺序", "按当前拖入顺序准备图片，确认后开始生成 PDF。"),
            ("2 合并 PDF", "系统将图片依次写入 PDF，并同步显示当前进度。"),
            ("3 进入工作台", "合并完成后自动打开生成的 PDF，继续进入脱敏工作台。"),
        ]:
            step_card = QFrame()
            step_card.setObjectName("batchStepCard")
            step_layout = QVBoxLayout(step_card)
            step_layout.setContentsMargins(14, 12, 14, 12)
            step_layout.setSpacing(4)
            step_title = QLabel(title_text)
            step_title.setObjectName("batchStepTitle")
            step_note = QLabel(note_text)
            step_note.setObjectName("batchStepNote")
            step_note.setWordWrap(True)
            step_layout.addWidget(step_title)
            step_layout.addWidget(step_note)
            self.merge_stage_cards.append((step_card, step_title, step_note))
        self._rebuild_merge_stage_layout("wide")
        merge_card_layout.addLayout(merge_stage_layout)

        merge_metrics_layout = QGridLayout()
        merge_metrics_layout.setContentsMargins(0, 0, 0, 0)
        merge_metrics_layout.setHorizontalSpacing(10)
        merge_metrics_layout.setVerticalSpacing(10)
        self.merge_metrics_layout = merge_metrics_layout
        self.merge_metric_cards = []
        self.lbl_merge_metric_images = None
        self.lbl_merge_metric_images_note = None
        self.lbl_merge_metric_status = None
        self.lbl_merge_metric_status_note = None
        self.lbl_merge_metric_next = None
        self.lbl_merge_metric_next_note = None
        for key, title_text in [
            ("images", "待合并图片"),
            ("status", "当前状态"),
            ("next", "后续动作"),
        ]:
            metric_card, metric_value, metric_note = self._create_batch_metric_card(title_text)
            setattr(self, f"lbl_merge_metric_{key}", metric_value)
            setattr(self, f"lbl_merge_metric_{key}_note", metric_note)
            self.merge_metric_cards.append(metric_card)
        self._rebuild_merge_metrics_layout("wide")
        merge_card_layout.addLayout(merge_metrics_layout)
        merge_card_row_layout = QHBoxLayout()
        merge_card_row_layout.setContentsMargins(0, 0, 0, 0)
        merge_card_row_layout.setSpacing(0)
        merge_card_row_layout.addStretch(1)
        merge_card_row_layout.addWidget(merge_card, 10)
        merge_card_row_layout.addStretch(1)
        self.merge_card_row_layout = merge_card_row_layout
        merge_outer_layout.addLayout(merge_card_row_layout)
        merge_outer_layout.addStretch(1)

        self.word_compare_container = QWidget()
        word_compare_outer_layout = QVBoxLayout(self.word_compare_container)
        word_compare_outer_layout.setContentsMargins(14, 10, 14, 16)
        word_compare_outer_layout.setSpacing(0)
        self.word_compare_outer_layout = word_compare_outer_layout

        self.word_workspace_shell = QFrame()
        self.word_workspace_shell.setObjectName("previewWorkspaceCard")
        self.word_workspace_shell.setMaximumWidth(1940)
        self.word_workspace_shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        word_workspace_shell_layout = QVBoxLayout(self.word_workspace_shell)
        word_workspace_shell_layout.setContentsMargins(8, 8, 8, 8)
        word_workspace_shell_layout.setSpacing(6)
        self.word_workspace_shell_layout = word_workspace_shell_layout

        self.word_compare_header = QFrame()
        self.word_compare_header.setObjectName("wordCompareHeader")
        self.word_compare_header.setFixedHeight(28)
        word_header_layout = QHBoxLayout(self.word_compare_header)
        word_header_layout.setContentsMargins(0, 0, 0, 0)
        word_header_layout.setSpacing(12)
        self.word_header_layout = word_header_layout

        self.lbl_word_original_header = QLabel("原文预览")
        self.lbl_word_original_header.setObjectName("wordCompareLabel")
        self.lbl_word_original_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_header_divider = QFrame()
        self.word_header_divider.setFrameShape(QFrame.Shape.NoFrame)
        self.word_header_divider.setFixedWidth(12)
        self.lbl_word_replaced_header = QLabel("替换后预览")
        self.lbl_word_replaced_header.setObjectName("wordCompareLabel")
        self.lbl_word_replaced_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        word_header_layout.addWidget(self.lbl_word_original_header, stretch=1)
        word_header_layout.addWidget(self.word_header_divider)
        word_header_layout.addWidget(self.lbl_word_replaced_header, stretch=1)
        word_workspace_shell_layout.addWidget(self.word_compare_header)

        self.word_compare_content = QWidget()
        self.word_compare_content.setObjectName("previewStage")
        word_compare_layout = QHBoxLayout(self.word_compare_content)
        word_compare_layout.setContentsMargins(0, 0, 0, 0)
        word_compare_layout.setSpacing(8)
        self.word_compare_layout = word_compare_layout

        self.word_preview_original_panel = QWidget()
        self.word_preview_original_panel.setObjectName("wordPreviewShell")
        self.word_preview_original_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        original_panel_layout = QVBoxLayout(self.word_preview_original_panel)
        original_panel_layout.setContentsMargins(1, 1, 1, 1)
        original_panel_layout.setSpacing(0)
        self.original_panel_layout = original_panel_layout
        original_panel_layout.addWidget(self.word_preview)

        self.word_preview_replaced_panel = QWidget()
        self.word_preview_replaced_panel.setObjectName("wordPreviewShell")
        self.word_preview_replaced_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        replaced_panel_layout = QVBoxLayout(self.word_preview_replaced_panel)
        replaced_panel_layout.setContentsMargins(1, 1, 1, 1)
        replaced_panel_layout.setSpacing(0)
        self.replaced_panel_layout = replaced_panel_layout
        replaced_panel_layout.addWidget(self.word_preview_replaced)

        word_compare_layout.addWidget(self.word_preview_original_panel, stretch=1)
        word_compare_layout.addWidget(self.word_preview_replaced_panel, stretch=1)
        word_workspace_shell_layout.addWidget(self.word_compare_content, stretch=1)
        word_workspace_row_layout = QHBoxLayout()
        word_workspace_row_layout.setContentsMargins(0, 0, 0, 0)
        word_workspace_row_layout.setSpacing(0)
        word_workspace_row_layout.addStretch(1)
        word_workspace_row_layout.addWidget(self.word_workspace_shell, 18)
        word_workspace_row_layout.addStretch(1)
        self.word_workspace_row_layout = word_workspace_row_layout
        word_compare_outer_layout.addLayout(word_workspace_row_layout, 1)

        # 创建主容器，包含 canvas_container 和 word_compare_container
        self.main_container = QWidget()
        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.addWidget(self.idle_workspace_container)
        self.main_layout.addWidget(self.batch_workspace_container)
        self.main_layout.addWidget(self.merge_workspace_container)
        self.main_layout.addWidget(self.canvas_container)
        self.main_layout.addWidget(self.word_compare_container)

        # 默认隐藏 Word 预览容器
        self.batch_workspace_container.hide()
        self.merge_workspace_container.hide()
        self.word_compare_container.hide()
        self.word_preview_replaced_panel.hide()
        self.word_preview.hide()
        self.word_preview_replaced.hide()

        # 设置 container 为固定的 widget
        self.scroll.setWidget(self.main_container)
        # 默认单页模式：隐藏右页
        self.canvas_right.hide()

        layout.addWidget(self.scroll)

        # 进度条和取消按钮区域（v1.1.11: 添加取消按钮）
        self.progress_shell = QWidget()
        progress_layout = QHBoxLayout(self.progress_shell)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(24)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        progress_layout.addWidget(self.progress, stretch=1)

        # 取消扫描按钮（初始隐藏）
        self.btn_cancel_scan = QPushButton("取消")
        self.btn_cancel_scan.setFixedSize(60, 24)
        self.btn_cancel_scan.setToolTip("停止扫描并保留已扫描结果")
        self.btn_cancel_scan.clicked.connect(self.cancel_ocr_scan)
        self.btn_cancel_scan.setVisible(False)  # 初始隐藏
        progress_layout.addWidget(self.btn_cancel_scan)

        layout.addWidget(self.progress_shell)

        # 应用浅色主题样式
        self._apply_light_theme()
        self._sync_ui_mode()
