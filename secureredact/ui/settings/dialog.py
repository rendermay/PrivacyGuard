"""对话框/Worker 模块 — 从 main.py 迁出 (PR-B3/B4)

公共 API 不变。MainWindow 通过 `from main import X` 或对应模块 re-export 导入。
"""
from __future__ import annotations

import sys
import os
import re
import time
import shutil
import threading
import traceback
from pathlib import Path
from io import BytesIO

from PIL import Image
from bs4 import BeautifulSoup

from ._helpers import (  # PR-B5.2: 综合迁出
    build_settings_hero_tags,
    build_settings_nav_labels,
    format_signed_percent,
)
from secureredact.ui.utils.density import resolve_settings_density_mode  # PR-B5.2: 补 density helper 引用
from theme import Theme  # PR-B5.2: 补 Theme 引用

# PyQt6 — 完整集合,覆盖所有 5 个新模块需要
from PyQt6.QtCore import (
    Qt, QSize, QPoint, QPointF, QRect, QRectF, QTimer, QThread, QObject,
    QUrl, QStandardPaths, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QFont, QFontMetrics, QIcon, QImage, QKeySequence,
    QPainter, QPalette, QPen, QPixmap, QStandardItem, QStandardItemModel,
    QTextCursor, QTextDocument, QWheelEvent,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QCompleter,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMenuBar, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QRadioButton, QScrollArea, QScrollBar, QSizePolicy, QSlider, QSpinBox,
    QSplitter, QStackedWidget, QStatusBar, QStyle, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextBrowser, QTextEdit, QToolBar, QToolButton,
    QTreeView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

# 项目内 import(对话框类可能用到的)
from secureredact.utils.security import validate_safe_path, resource_path
from secureredact.utils.exceptions import PrivacyAppError
from secureredact.redaction.hit_ref import HitRef
from secureredact.redaction.word_rules import normalize_word_replace_rules  # PR-C1.1 extraction
class SettingsDialog(QDialog):
    """设置对话框 - v1.1.11: 支持配置持久化"""

    def __init__(self, parent=None, current_rules=None, use_enhance=False, custom_keywords="",
                 scan_level=2.0, offset_x=0, offset_w=0, replacement_text="[已脱敏]",
                 word_replace_rules=None,
                 config_manager=None,
                 enable_name_recognition=False,
                 current_blacklist=None,
                 current_whitelist=None):
        from main import DEFAULT_RULES, config  # PR-B5.2: 延迟导入, 避免 main.py 加载时循环
        super().__init__(parent)
        self.config = config_manager

        # v1.1.11: 修复 Windows 深色模式下对话框显示问题
        # 设置窗口标志，确保对话框在深色系统主题下使用浅色样式
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # v1.1.11: 从配置读取窗口尺寸，并结合当前屏幕做自适应约束
        if self.config:
            dialog_width = self.config.get("app.window.dialog_settings_width", 550)
            dialog_height = self.config.get("app.window.dialog_settings_height", 700)
        else:
            dialog_width, dialog_height = 550, 700

        self.setWindowTitle("高级设置")
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            max_w = min(max(760, int(available.width() * 0.92)), available.width())
            max_h = min(max(620, int(available.height() * 0.90)), available.height())
            preferred_w = min(max_w, 1180)
            preferred_h = min(max_h, 900)
            min_w = min(900, max_w)
            min_h = min(680, max_h)
            width = max(min(min(max(dialog_width, 960), preferred_w), max_w), min_w)
            height = max(min(min(max(dialog_height, 760), preferred_h), max_h), min_h)
            self.resize(width, height)
            self.setMinimumSize(min_w, min_h)
            self.setMaximumSize(max_w, max_h)
        else:
            self.resize(980, 760)
            self.setMinimumSize(820, 620)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setSizeGripEnabled(True)
        self._settings_bound_window_handle = None

        # v1.1.11: 应用对话框主题样式
        self._apply_dialog_theme()

        self.selected_rules = []
        self.use_enhance = use_enhance
        self.custom_keywords = custom_keywords
        self.scan_level = scan_level
        self.offset_x = offset_x
        self.offset_w = offset_w
        self.replacement_text = replacement_text if isinstance(replacement_text, str) and replacement_text else "[已脱敏]"
        self.word_replace_rules = normalize_word_replace_rules(word_replace_rules or [], self.replacement_text)
        self.default_replacement_text = "[已脱敏]"
        self.recommended_rule_names = ["身份证号", "手机号码"]
        # v1.1.11: 中文姓名启发式识别开关(默认 False,向后兼容)
        self.enable_name_recognition = bool(enable_name_recognition)
        # v1.1.11: 黑/白名单(来自 config.json 的 redaction.blacklist/whitelist)
        self._initial_blacklist = list(current_blacklist or [])
        self._initial_whitelist = list(current_whitelist or [])

        # v1.1.11: 从配置读取范围和标签
        if self.config:
            offset_config = self.config.get("redaction.offset", {})
            x_range = offset_config.get("x_range", [-20, 20])
            w_range = offset_config.get("w_range", [-20, 20])
            scan_config = self.config.get("redaction.scan", {})
            available_levels = scan_config.get("available_levels", [1.5, 2.0, 3.0])
            level_labels = scan_config.get("level_labels", {
                "1.5": "标准 (1.5x)",
                "2.0": "高精 (2.0x 推荐)",
                "3.0": "超精 (3.0x 最慢)"
            })
        else:
            x_range = [-20, 20]
            w_range = [-20, 20]
            available_levels = [1.5, 2.0, 3.0]
            level_labels = {
                "1.5": "标准 (1.5x)",
                "2.0": "高精 (2.0x 推荐)",
                "3.0": "超精 (3.0x 最慢)"
            }

        self.x_range = x_range
        self.w_range = w_range
        self.available_levels = available_levels
        self.level_labels = level_labels

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(18, 16, 18, 18)
        outer_layout.setSpacing(14)

        hero = QFrame(self)
        hero.setObjectName("settingsHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(6)
        self.settings_hero_layout = hero_layout
        hero_title = QLabel("高级设置中心")
        hero_title.setObjectName("settingsTitle")
        self.settings_hero_title = hero_title
        hero_subtitle = QLabel("这里保存长期配置。PDF 的黑 / 白、单双页、缩放等即时操作，仍然放在主工作台里。")
        hero_subtitle.setObjectName("settingsSubtitle")
        hero_subtitle.setWordWrap(True)
        self.settings_hero_subtitle = hero_subtitle
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_subtitle)
        hero_tag_layout = QHBoxLayout()
        hero_tag_layout.setSpacing(8)
        self.settings_hero_tag_layout = hero_tag_layout
        self.lbl_settings_common_tag = QLabel("常用设置：通用规则 / 关键词 / Word 替换")
        self.lbl_settings_common_tag.setObjectName("settingsHeroTag")
        self.lbl_settings_advanced_tag = QLabel("高级微调：扫描 / 覆盖 / OCR 检测框")
        self.lbl_settings_advanced_tag.setObjectName("settingsHeroTag")
        hero_tag_layout.addWidget(self.lbl_settings_common_tag)
        hero_tag_layout.addWidget(self.lbl_settings_advanced_tag)
        hero_tag_layout.addStretch()
        hero_layout.addLayout(hero_tag_layout)
        outer_layout.addWidget(hero)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(18)
        self.settings_body_layout = body_layout
        outer_layout.addLayout(body_layout, stretch=1)

        sidebar = QFrame(self)
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(236)
        self.settings_sidebar = sidebar
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)
        self.settings_sidebar_layout = sidebar_layout

        nav_hint = QLabel("设置导航")
        nav_hint.setObjectName("settingsHint")
        self.settings_nav_hint = nav_hint
        sidebar_layout.addWidget(nav_hint)
        nav_subtitle = QLabel("点击左侧即可快速跳转到对应模块。")
        nav_subtitle.setObjectName("settingsSidebarSubtle")
        nav_subtitle.setWordWrap(True)
        self.settings_nav_subtitle = nav_subtitle
        sidebar_layout.addWidget(nav_subtitle)
        sidebar_layout.addWidget(self._create_settings_divider())

        self.settings_nav = QListWidget()
        self.settings_nav.setObjectName("settingsNav")
        self.settings_nav.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._settings_nav_base_titles = ["1 通用规则", "2 自定义关键词", "3 黑名单", "4 白名单", "5 扫描与微调", "6 OCR 检测框"]
        for title in self._settings_nav_base_titles:
            self.settings_nav.addItem(title)
        sidebar_layout.addWidget(self.settings_nav, stretch=1)

        sidebar_meta_card = QFrame()
        sidebar_meta_card.setObjectName("settingsSidebarMetaCard")
        self.settings_sidebar_meta_card = sidebar_meta_card
        sidebar_meta_layout = QVBoxLayout(sidebar_meta_card)
        sidebar_meta_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_meta_layout.setSpacing(10)
        sidebar_note = QLabel("建议：第一次使用只改规则和关键词；OCR 微调只在识别偏移时再调整。")
        sidebar_note.setWordWrap(True)
        sidebar_note.setObjectName("settingsSidebarNote")
        self.settings_sidebar_note = sidebar_note
        sidebar_meta_layout.addWidget(sidebar_note)
        sidebar_meta_layout.addWidget(self._create_settings_divider())
        self.settings_sidebar_status = QLabel("")
        self.settings_sidebar_status.setWordWrap(True)
        self.settings_sidebar_status.setObjectName("settingsSidebarStatus")
        sidebar_meta_layout.addWidget(self.settings_sidebar_status)
        sidebar_layout.addWidget(sidebar_meta_card)
        body_layout.addWidget(sidebar)

        content_scroll = QScrollArea(self)
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll = content_scroll

        content_widget = QWidget()
        self.content_widget = content_widget
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        overview_card = QFrame()
        overview_card.setObjectName("settingsOverview")
        self.settings_overview_card = overview_card
        overview_layout = QVBoxLayout(overview_card)
        overview_layout.setContentsMargins(18, 16, 18, 16)
        overview_layout.setSpacing(12)
        self.settings_overview_layout = overview_layout
        overview_title = QLabel("当前配置概览")
        overview_title.setObjectName("settingsOverviewTitle")
        self.settings_overview_title = overview_title
        overview_text = QLabel("先看这里，就能快速知道当前默认规则、关键词、Word 替换和 OCR 微调处于什么状态。")
        overview_text.setObjectName("settingsOverviewText")
        overview_text.setWordWrap(True)
        self.settings_overview_text = overview_text
        overview_layout.addWidget(overview_title)
        overview_layout.addWidget(overview_text)

        overview_metrics_layout = QGridLayout()
        overview_metrics_layout.setHorizontalSpacing(10)
        overview_metrics_layout.setVerticalSpacing(10)
        self.settings_overview_metrics_layout = overview_metrics_layout
        self.lbl_metric_rules = None
        self.lbl_metric_keywords = None
        self.lbl_metric_word_rules = None
        self.lbl_metric_ocr = None
        self.settings_metric_cards = []
        for key, title in [
            ("rules", "通用规则"),
            ("keywords", "自定义关键词"),
            ("word_rules", "Word 规则"),
            ("ocr", "OCR 调节"),
        ]:
            metric_card, metric_value = self._create_settings_metric_card(title)
            setattr(self, f"lbl_metric_{key}", metric_value)
            self.settings_metric_cards.append(metric_card)
            overview_metrics_layout.addWidget(metric_card, 0, len(self.settings_metric_cards) - 1)
        overview_layout.addLayout(overview_metrics_layout)

        overview_actions_layout = QGridLayout()
        overview_actions_layout.setHorizontalSpacing(8)
        overview_actions_layout.setVerticalSpacing(8)
        self.settings_overview_actions_layout = overview_actions_layout
        self._settings_quick_jump_titles = [
            ("去看通用规则", "通用规则"),
            ("去看关键词", "关键词"),
            ("去看扫描微调", "扫描微调"),
            ("去看 OCR", "OCR"),
        ]
        self.settings_quick_jump_buttons = []
        for row, (title, _short_title) in enumerate(self._settings_quick_jump_titles):
            jump_btn = QPushButton(title)
            jump_btn.setObjectName("settingsQuickJumpButton")
            jump_btn.clicked.connect(lambda _checked=False, target_row=row: self.settings_nav.setCurrentRow(target_row))
            jump_btn.setMinimumHeight(32)
            self.settings_quick_jump_buttons.append(jump_btn)
            overview_actions_layout.addWidget(jump_btn, 0, row)
        overview_layout.addLayout(overview_actions_layout)
        layout.addWidget(overview_card)

        # 1. 规则
        box_rules = QFrame()
        box_rules.setObjectName("settingsSectionCard")
        v_box = QVBoxLayout(box_rules)
        v_box.setContentsMargins(16, 16, 16, 16)
        v_box.setSpacing(12)
        rules_lead = QLabel("勾选后的规则会作为默认智能识别规则。第一次使用建议至少保留身份证号和手机号。")
        rules_lead.setObjectName("settingsSectionLead")
        rules_lead.setWordWrap(True)
        self.lbl_rules_summary = QLabel("")
        self.lbl_rules_summary.setObjectName("settingsSectionSummary")
        self.lbl_rules_summary.setWordWrap(True)
        v_box.addWidget(self._create_settings_section_header("1. 通用规则", rules_lead, self.lbl_rules_summary))
        rules_actions = QHBoxLayout()
        rules_actions.setSpacing(8)
        rules_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        btn_rules_recommended = QPushButton("恢复推荐勾选")
        btn_rules_recommended.setObjectName("settingsInlineButton")
        btn_rules_recommended.clicked.connect(self._apply_recommended_rules)
        rules_actions.addWidget(btn_rules_recommended)
        btn_rules_all = QPushButton("全部勾选")
        btn_rules_all.setObjectName("settingsInlineButton")
        btn_rules_all.clicked.connect(self._select_all_rules)
        rules_actions.addWidget(btn_rules_all)
        btn_rules_clear = QPushButton("全部清空")
        btn_rules_clear.setObjectName("settingsInlineButton")
        btn_rules_clear.clicked.connect(self._clear_all_rules)
        rules_actions.addWidget(btn_rules_clear)
        rules_actions.addStretch()
        v_box.addLayout(rules_actions)
        rules_columns = QHBoxLayout()
        rules_columns.setSpacing(24)
        rules_left_col = QVBoxLayout()
        rules_left_col.setSpacing(6)
        rules_right_col = QVBoxLayout()
        rules_right_col.setSpacing(6)
        self.checks = {}
        # v1.1.12: 读取 PDF 排除规则列表,用于在规则面板给"仅 Word"规则加标识
        try:
            pdf_excluded_names_ui = config.get("redaction.pdf_excluded_rules", []) if config else []
        except Exception:
            pdf_excluded_names_ui = []
        if not isinstance(pdf_excluded_names_ui, list):
            pdf_excluded_names_ui = []
        pdf_excluded_set = set(pdf_excluded_names_ui)
        rule_items = list(DEFAULT_RULES.items())
        split_index = (len(rule_items) + 1) // 2
        for index, (name, pattern) in enumerate(rule_items):
            # v1.1.12: 若规则在 PDF 排除列表中,UI 名称追加 "📝 仅 Word" 标识
            display_name = f"{name}  📝 仅 Word" if name in pdf_excluded_set else name
            cb = QCheckBox(display_name)
            if current_rules and pattern in current_rules: cb.setChecked(True)
            elif not current_rules and name in ["身份证号", "手机号码", "地址（含门牌号）", "固定电话", "法定代表人"]: cb.setChecked(True)
            self.checks[name] = cb
            cb.toggled.connect(self._refresh_rule_summary)
            if index < split_index:
                rules_left_col.addWidget(cb)
            else:
                rules_right_col.addWidget(cb)
        rules_left_col.addStretch()
        rules_right_col.addStretch()
        rules_columns.addLayout(rules_left_col, stretch=1)
        rules_columns.addLayout(rules_right_col, stretch=1)
        v_box.addLayout(rules_columns)
        layout.addWidget(box_rules)

        # 2. 关键词 + 统一替换文本 + Word 替换规则入口
        box_custom = QFrame()
        box_custom.setObjectName("settingsSectionCard")
        v_custom = QVBoxLayout(box_custom)
        v_custom.setContentsMargins(16, 16, 16, 16)
        v_custom.setSpacing(12)
        custom_lead = QLabel("这里适合录入姓名、单位、案号等固定内容；Word 替换规则适合更精细的定向替换。")
        custom_lead.setObjectName("settingsSectionLead")
        custom_lead.setWordWrap(True)
        self.lbl_custom_summary = QLabel("")
        self.lbl_custom_summary.setObjectName("settingsSectionSummary")
        self.lbl_custom_summary.setWordWrap(True)
        v_custom.addWidget(self._create_settings_section_header("2. 自定义关键词", custom_lead, self.lbl_custom_summary))
        custom_row = QGridLayout()
        custom_row.setHorizontalSpacing(28)
        custom_row.setVerticalSpacing(14)
        self.settings_custom_row = custom_row

        left_panel_widget = QFrame()
        left_panel_widget.setObjectName("settingsFieldCard")
        self.settings_left_field_card = left_panel_widget
        left_panel_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_panel = QVBoxLayout(left_panel_widget)
        left_panel.setContentsMargins(16, 16, 16, 16)
        left_panel.setSpacing(10)
        left_title = QLabel("关键词列表")
        left_title.setObjectName("settingsFieldTitle")
        left_note = QLabel("按行输入固定敏感词。适合姓名、机构、案号等直接命中的内容。")
        left_note.setObjectName("settingsFieldNote")
        left_note.setWordWrap(True)
        left_panel.addWidget(left_title)
        left_panel.addWidget(left_note)
        left_panel.addWidget(self._create_settings_divider())
        custom_actions = QHBoxLayout()
        custom_actions.setSpacing(8)
        custom_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        btn_clear_keywords = QPushButton("清空关键词")
        btn_clear_keywords.setObjectName("settingsInlineButton")
        btn_clear_keywords.clicked.connect(self._clear_custom_keywords)
        custom_actions.addWidget(btn_clear_keywords)
        custom_actions.addStretch()
        left_panel.addLayout(custom_actions)
        # v1.1.11: 中文姓名启发式识别开关
        self.cb_name_recognition = QCheckBox("启用中文姓名启发式识别 (jieba)")
        self.cb_name_recognition.setObjectName("settingsInlineCheckbox")
        self.cb_name_recognition.setChecked(self.enable_name_recognition)
        self.cb_name_recognition.setToolTip(
            "开启后,工具会调用 jieba 词性标注提取文本中的中文姓名,"
            "追加到 OCR/Word 命中规则。\n"
            "适用于法律文书等含姓名角色的场景;非中文或纯文本场景建议关闭。"
        )
        left_panel.addWidget(self.cb_name_recognition)
        self.txt_custom = QTextEdit()
        self.txt_custom.setPlaceholderText("例如：法院 张三 (支持多行)")
        self.txt_custom.setPlainText(custom_keywords)
        self.txt_custom.setMinimumHeight(120)
        self.txt_custom.setMaximumHeight(190)
        self.txt_custom.textChanged.connect(self._refresh_custom_summary)
        left_panel.addWidget(self.txt_custom)
        custom_row.addWidget(left_panel_widget, 0, 0)

        right_panel_widget = QFrame()
        right_panel_widget.setObjectName("settingsFieldCard")
        right_panel_widget.setMinimumWidth(320)
        self.settings_right_field_card = right_panel_widget
        right_panel_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_panel = QVBoxLayout(right_panel_widget)
        right_panel.setContentsMargins(16, 16, 16, 16)
        right_panel.setSpacing(10)
        right_title = QLabel("Word 替换规则")
        right_title.setObjectName("settingsFieldTitle")
        right_note = QLabel("这里适合维护更精细的 exact / regex 替换规则，批量 Word 会直接复用。")
        right_note.setObjectName("settingsFieldNote")
        right_note.setWordWrap(True)
        right_panel.addWidget(right_title)
        right_panel.addWidget(right_note)
        right_panel.addWidget(self._create_settings_divider())
        replacement_row = QHBoxLayout()
        replacement_row.setSpacing(8)
        replacement_row.addWidget(self._create_settings_form_label("统一替换文本:", 102))
        self.input_replacement_text = QLineEdit(self.replacement_text)
        self.input_replacement_text.setPlaceholderText("[已脱敏]")
        self.input_replacement_text.setMinimumWidth(240)
        self.input_replacement_text.textChanged.connect(self._refresh_custom_summary)
        replacement_row.addWidget(self.input_replacement_text)
        right_panel.addLayout(replacement_row)
        replacement_actions = QHBoxLayout()
        replacement_actions.setSpacing(8)
        replacement_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        btn_reset_replacement = QPushButton("恢复默认替换词")
        btn_reset_replacement.setObjectName("settingsInlineButton")
        btn_reset_replacement.clicked.connect(self._reset_replacement_text)
        replacement_actions.addWidget(btn_reset_replacement)
        replacement_actions.addStretch()
        right_panel.addLayout(replacement_actions)

        right_panel.addSpacing(8)
        right_panel.addWidget(self._create_settings_form_label("Word 替换规则:", 120))
        self.btn_edit_word_rules = QPushButton("打开替换规则设置")
        self.btn_edit_word_rules.clicked.connect(self._open_word_rules_editor)
        self.btn_edit_word_rules.setMinimumHeight(34)
        right_panel.addWidget(self.btn_edit_word_rules)

        self.lbl_word_rule_count = QLabel("")
        self.lbl_word_rule_count.setObjectName("settingsFieldNote")
        self.lbl_word_rule_count.setWordWrap(True)
        right_panel.addWidget(self.lbl_word_rule_count)
        word_rules_hint = QLabel("批量 Word 替换会直接复用这里的规则结构，不需要另外维护一套。")
        word_rules_hint.setWordWrap(True)
        word_rules_hint.setObjectName("settingsFieldNote")
        right_panel.addWidget(word_rules_hint)
        right_panel.addStretch()

        custom_row.addWidget(right_panel_widget, 0, 1)
        v_custom.addLayout(custom_row)
        layout.addWidget(box_custom)

        # v1.1.11: 2.5 黑名单 (强制脱敏, 优先级最低 / 实际生效低于规则)
        box_black = QFrame()
        box_black.setObjectName("settingsSectionCard")
        v_black = QVBoxLayout(box_black)
        v_black.setContentsMargins(16, 16, 16, 16)
        v_black.setSpacing(12)
        black_lead = QLabel("每行一条子串,强制进入脱敏命中。即使通用规则和关键词都没命中,只要文本里包含这里的内容就会被遮盖。")
        black_lead.setObjectName("settingsSectionLead")
        black_lead.setWordWrap(True)
        self.lbl_black_summary = QLabel("")
        self.lbl_black_summary.setObjectName("settingsSectionSummary")
        self.lbl_black_summary.setWordWrap(True)
        v_black.addWidget(self._create_settings_section_header(
            "3. 黑名单 (强制脱敏)", black_lead, self.lbl_black_summary))
        black_actions = QHBoxLayout()
        black_actions.setSpacing(8)
        black_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        btn_clear_black = QPushButton("清空黑名单")
        btn_clear_black.setObjectName("settingsInlineButton")
        btn_clear_black.clicked.connect(self._clear_blacklist)
        black_actions.addWidget(btn_clear_black)
        black_actions.addStretch()
        v_black.addLayout(black_actions)
        black_card = QFrame()
        black_card.setObjectName("settingsFieldCard")
        black_card_layout = QVBoxLayout(black_card)
        black_card_layout.setContentsMargins(16, 16, 16, 16)
        black_card_layout.setSpacing(10)
        black_card_title = QLabel("黑名单条目")
        black_card_title.setObjectName("settingsFieldTitle")
        black_card_note = QLabel("子串匹配 (不需完整词)。每行一条,实时生效,关闭对话框也会保留。")
        black_card_note.setObjectName("settingsFieldNote")
        black_card_note.setWordWrap(True)
        black_card_layout.addWidget(black_card_title)
        black_card_layout.addWidget(black_card_note)
        black_card_layout.addWidget(self._create_settings_divider())
        self.txt_blacklist = QTextEdit()
        self.txt_blacklist.setPlaceholderText("例如: 盖章 / 内部资料 / 签字")
        self.txt_blacklist.setPlainText("\n".join(self._initial_blacklist))
        self.txt_blacklist.setMinimumHeight(120)
        self.txt_blacklist.setMaximumHeight(190)
        self.txt_blacklist.textChanged.connect(self._on_black_white_changed)
        black_card_layout.addWidget(self.txt_blacklist)
        v_black.addWidget(black_card)
        layout.addWidget(box_black)

        # v1.1.11: 2.6 白名单 (永不脱敏, 优先级最高)
        box_white = QFrame()
        box_white.setObjectName("settingsSectionCard")
        v_white = QVBoxLayout(box_white)
        v_white.setContentsMargins(16, 16, 16, 16)
        v_white.setSpacing(12)
        white_lead = QLabel("每行一条子串,即使被规则或黑名单命中也不会被脱敏。注意: 这里的\"永不脱敏\"会覆盖其它所有机制。")
        white_lead.setObjectName("settingsSectionLead")
        white_lead.setWordWrap(True)
        self.lbl_white_summary = QLabel("")
        self.lbl_white_summary.setObjectName("settingsSectionSummary")
        self.lbl_white_summary.setWordWrap(True)
        v_white.addWidget(self._create_settings_section_header(
            "4. 白名单 (永不脱敏)", white_lead, self.lbl_white_summary))
        white_actions = QHBoxLayout()
        white_actions.setSpacing(8)
        white_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        btn_clear_white = QPushButton("清空白名单")
        btn_clear_white.setObjectName("settingsInlineButton")
        btn_clear_white.clicked.connect(self._clear_whitelist)
        white_actions.addWidget(btn_clear_white)
        white_actions.addStretch()
        v_white.addLayout(white_actions)
        white_card = QFrame()
        white_card.setObjectName("settingsFieldCard")
        white_card_layout = QVBoxLayout(white_card)
        white_card_layout.setContentsMargins(16, 16, 16, 16)
        white_card_layout.setSpacing(10)
        white_card_title = QLabel("白名单条目")
        white_card_title.setObjectName("settingsFieldTitle")
        white_card_note = QLabel("子串匹配 (不需完整词)。每行一条,实时生效。")
        white_card_note.setObjectName("settingsFieldNote")
        white_card_note.setWordWrap(True)
        white_card_layout.addWidget(white_card_title)
        white_card_layout.addWidget(white_card_note)
        white_card_layout.addWidget(self._create_settings_divider())
        self.txt_whitelist = QTextEdit()
        self.txt_whitelist.setPlaceholderText("例如: 公司全称 / 产品代号")
        self.txt_whitelist.setPlainText("\n".join(self._initial_whitelist))
        self.txt_whitelist.setMinimumHeight(120)
        self.txt_whitelist.setMaximumHeight(190)
        self.txt_whitelist.textChanged.connect(self._on_black_white_changed)
        white_card_layout.addWidget(self.txt_whitelist)
        v_white.addWidget(white_card)
        layout.addWidget(box_white)

        # 3. 精度与微调
        box_enhance = QFrame()
        box_enhance.setObjectName("settingsSectionCard")
        v_enhance = QVBoxLayout(box_enhance)
        v_enhance.setContentsMargins(16, 16, 16, 16)
        v_enhance.setSpacing(12)
        precision_lead = QLabel("只有当扫描偏移、覆盖范围不理想时再调整这里；默认设置更适合大多数文档。")
        precision_lead.setObjectName("settingsSectionLead")
        precision_lead.setWordWrap(True)
        self.lbl_precision_summary = QLabel("")
        self.lbl_precision_summary.setObjectName("settingsSectionSummary")
        self.lbl_precision_summary.setWordWrap(True)
        v_enhance.addWidget(self._create_settings_section_header("3. 精度与微调", precision_lead, self.lbl_precision_summary))
        precision_actions = QHBoxLayout()
        precision_actions.setSpacing(8)
        precision_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        btn_reset_precision = QPushButton("恢复推荐值")
        btn_reset_precision.setObjectName("settingsInlineButton")
        btn_reset_precision.clicked.connect(self._reset_precision_defaults)
        precision_actions.addWidget(btn_reset_precision)
        precision_actions.addStretch()
        v_enhance.addLayout(precision_actions)

        precision_cards = QGridLayout()
        precision_cards.setHorizontalSpacing(16)
        precision_cards.setVerticalSpacing(14)
        self.settings_precision_cards_layout = precision_cards

        scan_card = QFrame()
        scan_card.setObjectName("settingsFieldCard")
        self.settings_scan_card = scan_card
        scan_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scan_card_layout = QVBoxLayout(scan_card)
        scan_card_layout.setContentsMargins(16, 16, 16, 16)
        scan_card_layout.setSpacing(10)
        scan_title = QLabel("扫描模式")
        scan_title.setObjectName("settingsFieldTitle")
        scan_note = QLabel("正常情况下保持默认即可。模式越高越细，但速度也会更慢。")
        scan_note.setObjectName("settingsFieldNote")
        scan_note.setWordWrap(True)
        scan_card_layout.addWidget(scan_title)
        scan_card_layout.addWidget(scan_note)
        scan_card_layout.addWidget(self._create_settings_divider())
        h_precision = QHBoxLayout()
        h_precision.addWidget(self._create_settings_form_label("当前模式:", 86))
        self.combo_precision = QComboBox()
        # v1.1.11: 从配置动态添加扫描级别选项
        for level in self.available_levels:
            label = self.level_labels.get(str(level), f"{level}x")
            self.combo_precision.addItem(label, level)
        idx = self.combo_precision.findData(scan_level)
        self.combo_precision.setCurrentIndex(idx if idx >=0 else 1)
        self.combo_precision.currentIndexChanged.connect(self._refresh_precision_summary)
        h_precision.addWidget(self.combo_precision)
        scan_card_layout.addLayout(h_precision)
        scan_card_layout.addStretch()
        precision_cards.addWidget(scan_card, 0, 0)

        calibrate_card = QFrame()
        calibrate_card.setObjectName("settingsFieldCard")
        self.settings_calibrate_card = calibrate_card
        calibrate_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        calibrate_card_layout = QVBoxLayout(calibrate_card)
        calibrate_card_layout.setContentsMargins(16, 16, 16, 16)
        calibrate_card_layout.setSpacing(10)
        calibrate_title = QLabel("覆盖微调")
        calibrate_title.setObjectName("settingsFieldTitle")
        calibrate_note = QLabel("只有在遮罩范围明显偏左、偏宽时再调，默认值更适合多数 PDF。")
        calibrate_note.setObjectName("settingsFieldNote")
        calibrate_note.setWordWrap(True)
        calibrate_card_layout.addWidget(calibrate_title)
        calibrate_card_layout.addWidget(calibrate_note)
        calibrate_card_layout.addWidget(self._create_settings_divider())
        h_calibrate = QHBoxLayout()
        v_cal_1 = QVBoxLayout()
        label_offset_x = QLabel("向左修正(px):")
        label_offset_x.setObjectName("settingsFieldLabel")
        v_cal_1.addWidget(label_offset_x)
        self.spin_offset_x = QSpinBox()
        self.spin_offset_x.setRange(x_range[0], x_range[1])
        self.spin_offset_x.setValue(offset_x)
        self.spin_offset_x.valueChanged.connect(self._refresh_precision_summary)
        v_cal_1.addWidget(self.spin_offset_x)

        v_cal_2 = QVBoxLayout()
        label_offset_w = QLabel("宽度收缩(px):")
        label_offset_w.setObjectName("settingsFieldLabel")
        v_cal_2.addWidget(label_offset_w)
        self.spin_offset_w = QSpinBox()
        self.spin_offset_w.setRange(w_range[0], w_range[1])
        self.spin_offset_w.setValue(offset_w)
        self.spin_offset_w.valueChanged.connect(self._refresh_precision_summary)
        v_cal_2.addWidget(self.spin_offset_w)

        h_calibrate.addLayout(v_cal_1)
        h_calibrate.addLayout(v_cal_2)
        calibrate_card_layout.addLayout(h_calibrate)
        calibrate_tip = QLabel("提示：对扫描区域 / 嵌入图片区域生效")
        calibrate_tip.setObjectName("settingsFieldNote")
        calibrate_tip.setWordWrap(True)
        calibrate_card_layout.addWidget(calibrate_tip)

        self.cb_enhance = QCheckBox("开启图像增强 (仅针对手写体)")
        self.cb_enhance.setChecked(use_enhance)
        self.cb_enhance.toggled.connect(self._refresh_precision_summary)
        calibrate_card_layout.addWidget(self.cb_enhance)
        calibrate_card_layout.addStretch()
        precision_cards.addWidget(calibrate_card, 0, 1)

        v_enhance.addLayout(precision_cards)
        layout.addWidget(box_enhance)

        # v1.1.11: 4. OCR 检测框调节（移除引擎选择，只保留 RapidOCR）
        box_ocr = QFrame()
        box_ocr.setObjectName("settingsSectionCard")
        v_ocr = QVBoxLayout(box_ocr)
        v_ocr.setContentsMargins(16, 16, 16, 16)
        v_ocr.setSpacing(12)
        ocr_lead = QLabel("检测框只在 OCR 结果偏大或偏小时再调。负值扩大框，正值收缩框，0 表示保持原样。")
        ocr_lead.setObjectName("settingsSectionLead")
        ocr_lead.setWordWrap(True)
        self.lbl_ocr_summary = QLabel("")
        self.lbl_ocr_summary.setObjectName("settingsSectionSummary")
        self.lbl_ocr_summary.setWordWrap(True)
        v_ocr.addWidget(self._create_settings_section_header("4. OCR 检测框调节", ocr_lead, self.lbl_ocr_summary))
        ocr_actions = QHBoxLayout()
        ocr_actions.setSpacing(8)
        ocr_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        btn_reset_ocr = QPushButton("恢复 0%")
        btn_reset_ocr.setObjectName("settingsInlineButton")
        btn_reset_ocr.clicked.connect(self._reset_ocr_adjustment)
        ocr_actions.addWidget(btn_reset_ocr)
        ocr_actions.addStretch()
        v_ocr.addLayout(ocr_actions)

        adjust_card = QFrame()
        adjust_card.setObjectName("settingsFieldCard")
        self.settings_adjust_card = adjust_card
        adjust_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        adjust_card_layout = QVBoxLayout(adjust_card)
        adjust_card_layout.setContentsMargins(16, 16, 16, 16)
        adjust_card_layout.setSpacing(10)
        adjust_title = QLabel("检测框调节")
        adjust_title.setObjectName("settingsFieldTitle")
        adjust_note = QLabel("当 OCR 框偏大或偏小时再调。负值扩大，正值收缩。")
        adjust_note.setObjectName("settingsFieldNote")
        adjust_note.setWordWrap(True)
        adjust_card_layout.addWidget(adjust_title)
        adjust_card_layout.addWidget(adjust_note)
        adjust_card_layout.addWidget(self._create_settings_divider())

        # v1.1.11: 检测框大小调节（支持负值扩大、正值收缩）
        h_adjust = QHBoxLayout()
        h_adjust.addWidget(self._create_settings_form_label("检测框调节:", 96))

        # 读取当前配置值（新配置名）
        adjust_ratio = config.get("ocr.box_adjust_ratio", 0.0) if config else 0.0

        self.slider_adjust = QSlider(Qt.Orientation.Horizontal)
        self.slider_adjust.setRange(-30, 50)  # -30% 到 +50%
        self.slider_adjust.setValue(int(adjust_ratio * 100))
        self.slider_adjust.valueChanged.connect(self._on_adjust_changed)
        h_adjust.addWidget(self.slider_adjust)

        self.label_adjust_value = QLabel(f"{int(adjust_ratio * 100)}%")
        self.label_adjust_value.setMinimumWidth(40)
        h_adjust.addWidget(self.label_adjust_value)

        adjust_card_layout.addLayout(h_adjust)

        adjust_info = QLabel("提示：负值扩大，正值收缩，0保持原样（默认0%）")
        adjust_info.setObjectName("settingsFieldNote")
        adjust_info.setWordWrap(True)
        adjust_card_layout.addWidget(adjust_info)

        # 说明标签
        info_text = (
            "\n引擎说明：\n"
            "• RapidOCR：默认 OCR 引擎，速度快，适合大文档批量处理\n"
        )

        info = QLabel(info_text)
        info.setObjectName("settingsFieldNote")
        info.setWordWrap(True)
        adjust_card_layout.addWidget(info)
        v_ocr.addWidget(adjust_card)
        layout.addWidget(box_ocr)

        # v1.1.11: 5. 永久 override 维护
        box_overrides = QFrame()
        box_overrides.setObjectName("settingsSectionCard")
        v_overrides = QVBoxLayout(box_overrides)
        v_overrides.setContentsMargins(16, 16, 16, 16)
        v_overrides.setSpacing(12)
        ov_lead = QLabel("维护永久 ignore / confirm 条目。永久 override 会跨会话生效,建议定期清理过期记录。")
        ov_lead.setObjectName("settingsSectionLead")
        ov_lead.setWordWrap(True)
        self.lbl_overrides_summary = QLabel("")
        self.lbl_overrides_summary.setObjectName("settingsSectionSummary")
        self.lbl_overrides_summary.setWordWrap(True)
        v_overrides.addWidget(
            self._create_settings_section_header(
                "5. 永久 override 名单", ov_lead, self.lbl_overrides_summary
            )
        )
        ov_actions = QHBoxLayout()
        ov_actions.setSpacing(8)
        ov_actions.addWidget(self._create_settings_action_hint("快捷操作"))
        clean_btn = QPushButton("清理 30 天前失效的 permanent overrides")
        clean_btn.setObjectName("settingsInlineButton")
        clean_btn.clicked.connect(self._on_clean_stale_overrides)
        ov_actions.addWidget(clean_btn)
        ov_actions.addStretch()
        v_overrides.addLayout(ov_actions)
        ov_card = QFrame()
        ov_card.setObjectName("settingsFieldCard")
        ov_card_layout = QVBoxLayout(ov_card)
        ov_card_layout.setContentsMargins(16, 16, 16, 16)
        ov_card_layout.setSpacing(8)
        ov_card_title = QLabel("Permanent 列表")
        ov_card_title.setObjectName("settingsFieldTitle")
        ov_card_note = QLabel("永久条目存于 config.json 的 redaction.overrides.permanent,共 N 条。")
        ov_card_note.setObjectName("settingsFieldNote")
        ov_card_note.setWordWrap(True)
        ov_card_layout.addWidget(ov_card_title)
        ov_card_layout.addWidget(ov_card_note)
        v_overrides.addWidget(ov_card)
        layout.addWidget(box_overrides)

        layout.addStretch(1)
        content_scroll.setWidget(content_widget)
        body_layout.addWidget(content_scroll, stretch=1)

        footer = QFrame(self)
        footer.setObjectName("settingsFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 14, 18, 14)
        footer_layout.setSpacing(12)
        self.settings_footer_layout = footer_layout

        footer_note = QLabel("修改完成后点击“保存设置”，取消不会影响当前已生效配置。")
        footer_note.setObjectName("settingsFooterNote")
        footer_note.setWordWrap(True)
        self.settings_footer_note = footer_note
        footer_layout.addWidget(footer_note, stretch=1)

        footer_actions = QHBoxLayout()
        footer_actions.setSpacing(10)
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("settingsSecondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setMinimumHeight(40)
        btn_cancel.setMinimumWidth(116)
        self.btn_settings_cancel = btn_cancel
        footer_actions.addWidget(btn_cancel)

        btn_ok = QPushButton("保存设置")
        btn_ok.setObjectName("settingsPrimaryButton")
        btn_ok.clicked.connect(self.save_settings)
        btn_ok.setMinimumHeight(40)
        btn_ok.setMinimumWidth(164)
        self.btn_settings_save = btn_ok
        footer_actions.addWidget(btn_ok)
        footer_layout.addLayout(footer_actions)
        outer_layout.addWidget(footer)
        self._settings_sections = [box_rules, box_custom, box_black, box_white, box_enhance, box_ocr, box_overrides]
        self._settings_nav_syncing = False
        self.settings_nav.currentRowChanged.connect(self._scroll_to_settings_section)
        self.content_scroll.verticalScrollBar().valueChanged.connect(self._sync_settings_nav_from_scroll)
        self.settings_nav.setCurrentRow(0)
        self._refresh_word_rule_summary()
        self._refresh_rule_summary()
        self._refresh_precision_summary()
        self._refresh_ocr_summary()
        self._refresh_overrides_summary()
        self._refresh_settings_layout_density()

    def _on_adjust_changed(self, value):
        """v1.1.11: 检测框调节滑块值变化回调"""
        self.label_adjust_value.setText(f"{value}%")
        self._refresh_ocr_summary()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_settings_layout_density()

    def showEvent(self, event):
        super().showEvent(event)
        self._bind_settings_window_handle_signals()
        QTimer.singleShot(0, self._refresh_settings_layout_density)

    def _get_settings_display_scale_factor(self):
        """返回设置窗口当前屏幕缩放，仅在 Windows 下生效。"""
        import platform

        if platform.system() != "Windows":
            return 1.0

        screen = None
        try:
            handle = self.windowHandle()
            if handle:
                screen = handle.screen()
        except Exception:
            screen = None

        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return 1.0

        try:
            scale = screen.logicalDotsPerInch() / 96.0
        except Exception:
            scale = 1.0

        return max(1.0, min(scale, 2.0))

    def _bind_settings_window_handle_signals(self):
        """绑定设置窗口跨屏信号，保证 DPI 切换后密度立即刷新。"""
        try:
            handle = self.windowHandle()
        except Exception:
            handle = None

        if handle is None or handle is self._settings_bound_window_handle:
            return

        try:
            handle.screenChanged.connect(self._on_settings_screen_changed)
        except Exception:
            pass
        self._settings_bound_window_handle = handle

    def _on_settings_screen_changed(self, _screen):
        """设置窗口切换屏幕后刷新密度。"""
        QTimer.singleShot(0, self._refresh_settings_layout_density)

    def _create_settings_metric_card(self, title):
        """创建设置页顶部概览指标卡。"""
        card = QFrame()
        card.setObjectName("settingsMetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("settingsMetricLabel")
        value_label = QLabel("--")
        value_label.setObjectName("settingsMetricValue")
        value_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch()
        return card, value_label

    def _rebuild_settings_grid(self, layout, widgets, columns, stretches=None):
        """按列数重排设置页网格布局。"""
        if not layout:
            return
        while layout.count():
            layout.takeAt(0)

        max_slots = max(len(widgets), 4)
        for column in range(max_slots):
            layout.setColumnStretch(column, 0)
        for row in range(max_slots):
            layout.setRowStretch(row, 0)

        columns = max(1, columns)
        for index, widget in enumerate(widgets):
            row = index // columns
            column = index % columns
            layout.addWidget(widget, row, column)

        if stretches:
            for column, stretch in enumerate(stretches):
                layout.setColumnStretch(column, stretch)
        else:
            for column in range(columns):
                layout.setColumnStretch(column, 1)

    def _refresh_settings_layout_density(self):
        """按当前窗口宽度微调设置页整体比例。"""
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        scale = self._get_settings_display_scale_factor()
        density_mode = resolve_settings_density_mode(width, height, scale)
        is_tall_window = height >= 980
        is_short_window = height <= 820
        is_very_wide_window = width >= 1620
        is_ultra_wide_window = width >= 1920
        is_cinema_wide_window = width >= 2140

        if density_mode == "wide":
            sidebar_width = 264
            body_spacing = 22
            hero_margins = (22, 18, 22, 18)
            overview_margins = (22, 18, 22, 18)
            footer_margins = (22, 14, 22, 14)
            hero_tag_spacing = 10
            metric_spacing = 12
            action_spacing = 10
            custom_spacing = 24
            precision_spacing = 18
            jump_min_width = 134
            quick_jump_compact = False
            overview_metric_columns = 4
            overview_action_columns = 4
            custom_columns = 2
            precision_columns = 2
            custom_stretches = (3, 2)
            precision_stretches = (1, 1)
            right_panel_max_width = 680
            right_panel_min_width = 430
            left_card_min_height = 348
            right_card_min_height = 348
            precision_card_min_height = 238
            adjust_card_min_height = 234
            cancel_min_width = 122
            save_min_width = 172
        elif density_mode == "roomy":
            sidebar_width = 248
            body_spacing = 18
            hero_margins = (18, 16, 18, 16)
            overview_margins = (18, 16, 18, 16)
            footer_margins = (18, 14, 18, 14)
            hero_tag_spacing = 8
            metric_spacing = 10
            action_spacing = 8
            custom_spacing = 22
            precision_spacing = 16
            jump_min_width = 124
            quick_jump_compact = False
            overview_metric_columns = 4
            overview_action_columns = 4
            custom_columns = 2
            precision_columns = 2
            custom_stretches = (3, 2)
            precision_stretches = (1, 1)
            right_panel_max_width = 620
            right_panel_min_width = 392
            left_card_min_height = 330
            right_card_min_height = 330
            precision_card_min_height = 224
            adjust_card_min_height = 220
            cancel_min_width = 116
            save_min_width = 164
        elif density_mode == "compact":
            sidebar_width = 232
            body_spacing = 16
            hero_margins = (16, 15, 16, 15)
            overview_margins = (16, 15, 16, 15)
            footer_margins = (16, 12, 16, 12)
            hero_tag_spacing = 8
            metric_spacing = 8
            action_spacing = 8
            custom_spacing = 18
            precision_spacing = 14
            jump_min_width = 114
            quick_jump_compact = False
            overview_metric_columns = 2
            overview_action_columns = 2
            custom_columns = 2
            precision_columns = 1
            custom_stretches = (7, 5)
            precision_stretches = (1,)
            right_panel_max_width = 540
            right_panel_min_width = 344
            left_card_min_height = 302
            right_card_min_height = 302
            precision_card_min_height = 208
            adjust_card_min_height = 204
            cancel_min_width = 112
            save_min_width = 156
        else:
            sidebar_width = 220
            body_spacing = 14
            hero_margins = (14, 14, 14, 14)
            overview_margins = (14, 14, 14, 14)
            footer_margins = (14, 12, 14, 12)
            hero_tag_spacing = 6
            metric_spacing = 8
            action_spacing = 6
            custom_spacing = 14
            precision_spacing = 12
            jump_min_width = 102
            quick_jump_compact = True
            overview_metric_columns = 2
            overview_action_columns = 2
            custom_columns = 1
            precision_columns = 1
            custom_stretches = (1,)
            precision_stretches = (1,)
            right_panel_max_width = 9999
            right_panel_min_width = 0
            left_card_min_height = 270
            right_card_min_height = 270
            precision_card_min_height = 194
            adjust_card_min_height = 194
            cancel_min_width = 108
            save_min_width = 148

        if scale >= 1.5:
            body_spacing += 2
            hero_tag_spacing += 1
            metric_spacing += 2
            action_spacing += 2
            custom_spacing += 2
            precision_spacing += 2
            jump_min_width += 6
            cancel_min_width += 8
            save_min_width += 10
            left_card_min_height += 14
            right_card_min_height += 14
            precision_card_min_height += 10
            adjust_card_min_height += 10
        elif scale >= 1.25:
            jump_min_width += 4
            cancel_min_width += 6
            save_min_width += 8
            left_card_min_height += 8
            right_card_min_height += 8
            precision_card_min_height += 6
            adjust_card_min_height += 6

        if is_tall_window:
            left_card_min_height += 18
            right_card_min_height += 18
            precision_card_min_height += 10
            adjust_card_min_height += 10
            hero_margins = (
                hero_margins[0] + 2,
                hero_margins[1] + 2,
                hero_margins[2] + 2,
                hero_margins[3] + 2,
            )
            overview_margins = (
                overview_margins[0] + 2,
                overview_margins[1] + 2,
                overview_margins[2] + 2,
                overview_margins[3] + 2,
            )
        elif is_short_window:
            body_spacing = max(12, body_spacing - 2)
            hero_tag_spacing = max(6, hero_tag_spacing - 1)
            metric_spacing = max(8, metric_spacing - 2)
            action_spacing = max(6, action_spacing - 2)
            custom_spacing = max(14, custom_spacing - 2)
            precision_spacing = max(12, precision_spacing - 2)
            left_card_min_height = max(270, left_card_min_height - 18)
            right_card_min_height = max(270, right_card_min_height - 18)
            precision_card_min_height = max(194, precision_card_min_height - 10)
            adjust_card_min_height = max(194, adjust_card_min_height - 10)
            footer_margins = (
                footer_margins[0],
                max(10, footer_margins[1] - 2),
                footer_margins[2],
                max(10, footer_margins[3] - 2),
            )

        if is_very_wide_window:
            sidebar_width += 10
            body_spacing += 2
            custom_spacing += 2
            precision_spacing += 2
            right_panel_max_width += 60 if right_panel_max_width < 9000 else 0
            right_panel_min_width += 24 if right_panel_min_width else 0
            left_card_min_height += 10
            right_card_min_height += 10
            precision_card_min_height += 8
            adjust_card_min_height += 8
            hero_margins = (
                hero_margins[0] + 2,
                hero_margins[1] + 2,
                hero_margins[2] + 2,
                hero_margins[3] + 2,
            )
            overview_margins = (
                overview_margins[0] + 2,
                overview_margins[1] + 2,
                overview_margins[2] + 2,
                overview_margins[3] + 2,
            )

        if is_ultra_wide_window:
            sidebar_width += 8
            body_spacing += 2
            hero_tag_spacing += 1
            metric_spacing += 2
            action_spacing += 2
            custom_spacing += 2
            precision_spacing += 2
            jump_min_width += 6
            right_panel_max_width += 80 if right_panel_max_width < 9000 else 0
            right_panel_min_width += 28 if right_panel_min_width else 0
            left_card_min_height += 10
            right_card_min_height += 10

        if is_cinema_wide_window:
            sidebar_width += 10
            body_spacing += 2
            hero_tag_spacing += 1
            metric_spacing += 2
            action_spacing += 2
            custom_spacing += 2
            precision_spacing += 2
            jump_min_width += 8
            right_panel_max_width += 120 if right_panel_max_width < 9000 else 0
            right_panel_min_width += 36 if right_panel_min_width else 0
            left_card_min_height += 10
            right_card_min_height += 10
            precision_card_min_height += 8
            adjust_card_min_height += 8
            hero_margins = (
                hero_margins[0] + 4,
                hero_margins[1] + 2,
                hero_margins[2] + 4,
                hero_margins[3] + 2,
            )
            overview_margins = (
                overview_margins[0] + 4,
                overview_margins[1] + 2,
                overview_margins[2] + 4,
                overview_margins[3] + 2,
            )

        quick_jump_height = 34 if scale >= 1.25 else 32
        footer_button_height = 42 if scale >= 1.25 else 40

        if hasattr(self, "settings_sidebar"):
            self.settings_sidebar.setFixedWidth(sidebar_width)
        if hasattr(self, "settings_body_layout"):
            self.settings_body_layout.setSpacing(body_spacing)
        if hasattr(self, "settings_hero_layout"):
            self.settings_hero_layout.setContentsMargins(*hero_margins)
        if hasattr(self, "settings_hero_tag_layout"):
            self.settings_hero_tag_layout.setSpacing(hero_tag_spacing)
        if hasattr(self, "settings_overview_layout"):
            self.settings_overview_layout.setContentsMargins(*overview_margins)
        if hasattr(self, "settings_overview_metrics_layout"):
            self.settings_overview_metrics_layout.setHorizontalSpacing(metric_spacing)
            self.settings_overview_metrics_layout.setVerticalSpacing(metric_spacing)
            self._rebuild_settings_grid(
                self.settings_overview_metrics_layout,
                self.settings_metric_cards,
                overview_metric_columns,
            )
        if hasattr(self, "settings_overview_actions_layout"):
            self.settings_overview_actions_layout.setHorizontalSpacing(action_spacing)
            self.settings_overview_actions_layout.setVerticalSpacing(action_spacing)
            self._rebuild_settings_grid(
                self.settings_overview_actions_layout,
                self.settings_quick_jump_buttons,
                overview_action_columns,
            )
        if hasattr(self, "settings_footer_layout"):
            self.settings_footer_layout.setContentsMargins(*footer_margins)
        for index, button in enumerate(getattr(self, "settings_quick_jump_buttons", [])):
            button.setMinimumWidth(jump_min_width)
            button.setMinimumHeight(quick_jump_height)
            button.setMaximumHeight(quick_jump_height)
            if hasattr(self, "_settings_quick_jump_titles") and index < len(self._settings_quick_jump_titles):
                full_title, short_title = self._settings_quick_jump_titles[index]
                button.setText(short_title if quick_jump_compact else full_title)
        if hasattr(self, "btn_settings_cancel"):
            self.btn_settings_cancel.setMinimumWidth(cancel_min_width)
            self.btn_settings_cancel.setMinimumHeight(footer_button_height)
            self.btn_settings_cancel.setMaximumHeight(footer_button_height)
        if hasattr(self, "btn_settings_save"):
            self.btn_settings_save.setMinimumWidth(save_min_width)
            self.btn_settings_save.setMinimumHeight(footer_button_height)
            self.btn_settings_save.setMaximumHeight(footer_button_height)
        if hasattr(self, "settings_overview_text"):
            overview_text_width = 920 if density_mode == "wide" else 860 if density_mode == "roomy" else 760 if density_mode == "compact" else 680
            if is_very_wide_window:
                overview_text_width += 80
            if is_ultra_wide_window:
                overview_text_width += 80
            if is_cinema_wide_window:
                overview_text_width += 120
            self.settings_overview_text.setMaximumWidth(overview_text_width)
        if hasattr(self, "settings_hero_subtitle"):
            hero_subtitle_width = 1000 if density_mode == "wide" else 930 if density_mode == "roomy" else 840 if density_mode == "compact" else 720
            if is_very_wide_window:
                hero_subtitle_width += 100
            if is_ultra_wide_window:
                hero_subtitle_width += 100
            if is_cinema_wide_window:
                hero_subtitle_width += 140
            self.settings_hero_subtitle.setMaximumWidth(hero_subtitle_width)
        if hasattr(self, "settings_custom_row"):
            self.settings_custom_row.setHorizontalSpacing(custom_spacing)
            self.settings_custom_row.setVerticalSpacing(max(12, custom_spacing - 8))
            self._rebuild_settings_grid(
                self.settings_custom_row,
                [self.settings_left_field_card, self.settings_right_field_card],
                custom_columns,
                custom_stretches,
            )
        if hasattr(self, "settings_precision_cards_layout"):
            self.settings_precision_cards_layout.setHorizontalSpacing(precision_spacing)
            self.settings_precision_cards_layout.setVerticalSpacing(max(12, precision_spacing - 2))
            self._rebuild_settings_grid(
                self.settings_precision_cards_layout,
                [self.settings_scan_card, self.settings_calibrate_card],
                precision_columns,
                precision_stretches,
            )
        if hasattr(self, "settings_right_field_card"):
            self.settings_right_field_card.setMaximumWidth(right_panel_max_width)
            self.settings_right_field_card.setMinimumWidth(right_panel_min_width)
            self.settings_right_field_card.setMinimumHeight(right_card_min_height)
        if hasattr(self, "settings_left_field_card"):
            self.settings_left_field_card.setMinimumHeight(left_card_min_height)
        if hasattr(self, "settings_scan_card"):
            self.settings_scan_card.setMinimumHeight(precision_card_min_height)
        if hasattr(self, "settings_calibrate_card"):
            self.settings_calibrate_card.setMinimumHeight(precision_card_min_height)
        if hasattr(self, "settings_adjust_card"):
            self.settings_adjust_card.setMinimumHeight(adjust_card_min_height)
        self._apply_settings_density_styles(density_mode, scale, is_short_window)

    def _create_settings_section_title(self, title):
        """创建设置模块卡片内标题。"""
        title_label = QLabel(title)
        title_label.setObjectName("settingsSectionTitle")
        return title_label

    def _create_settings_section_header(self, title, lead_label, summary_label):
        """创建设置模块卡片内部统一头部。"""
        header = QFrame()
        header.setObjectName("settingsSectionHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._create_settings_section_title(title))
        layout.addWidget(lead_label)
        layout.addWidget(summary_label)
        return header

    def _create_settings_action_hint(self, text):
        """创建设置分区内的轻量操作提示。"""
        hint = QLabel(text)
        hint.setObjectName("settingsActionHint")
        return hint

    def _create_settings_form_label(self, text, width=96):
        """创建设置子卡中的统一表单标签。"""
        label = QLabel(text)
        label.setObjectName("settingsFieldLabel")
        label.setFixedWidth(width)
        return label

    def _create_settings_divider(self):
        """创建设置子卡内的轻量分隔线。"""
        divider = QFrame()
        divider.setObjectName("settingsFieldDivider")
        divider.setMinimumHeight(1)
        divider.setMaximumHeight(1)
        return divider

    def _apply_settings_density_styles(self, density_mode, scale, is_short_window):
        """按当前设置页密度统一标题、说明、导航与按钮字级。"""
        theme = Theme.LIGHT
        if density_mode == "wide":
            hero_title_size = 21
            hero_subtitle_size = 13
            hero_tag_size = 12
            overview_title_size = 17
            overview_text_size = 12
            section_title_size = 16
            lead_size = 12
            summary_size = 12
            field_title_size = 13
            field_label_size = 12
            field_note_size = 12
            hint_size = 11
            nav_font_size = 12
            nav_padding_v = 12
            nav_padding_h = 14
            nav_margin_v = 3
            metric_label_size = 11
            metric_value_size = 17
            quick_jump_font_size = 12
            footer_note_size = 12
        elif density_mode == "roomy":
            hero_title_size = 20
            hero_subtitle_size = 12
            hero_tag_size = 11
            overview_title_size = 16
            overview_text_size = 11
            section_title_size = 15
            lead_size = 11
            summary_size = 11
            field_title_size = 12
            field_label_size = 11
            field_note_size = 11
            hint_size = 11
            nav_font_size = 12
            nav_padding_v = 11
            nav_padding_h = 13
            nav_margin_v = 2
            metric_label_size = 11
            metric_value_size = 16
            quick_jump_font_size = 12
            footer_note_size = 11
        elif density_mode == "compact":
            hero_title_size = 19
            hero_subtitle_size = 12
            hero_tag_size = 11
            overview_title_size = 15
            overview_text_size = 11
            section_title_size = 15
            lead_size = 11
            summary_size = 11
            field_title_size = 12
            field_label_size = 11
            field_note_size = 11
            hint_size = 10
            nav_font_size = 11
            nav_padding_v = 10
            nav_padding_h = 12
            nav_margin_v = 2
            metric_label_size = 11
            metric_value_size = 15
            quick_jump_font_size = 11
            footer_note_size = 11
        else:
            hero_title_size = 18
            hero_subtitle_size = 11
            hero_tag_size = 10
            overview_title_size = 15
            overview_text_size = 11
            section_title_size = 14
            lead_size = 11
            summary_size = 11
            field_title_size = 12
            field_label_size = 11
            field_note_size = 11
            hint_size = 10
            nav_font_size = 11
            nav_padding_v = 10
            nav_padding_h = 11
            nav_margin_v = 2
            metric_label_size = 10
            metric_value_size = 15
            quick_jump_font_size = 11
            footer_note_size = 11

        if scale >= 1.5:
            hero_title_size += 1
            hero_subtitle_size += 1
            overview_title_size += 1
            section_title_size += 1
            lead_size += 1
            summary_size += 1
            field_title_size += 1
            field_label_size += 1
            field_note_size += 1
            nav_font_size += 1
            metric_value_size += 1
            quick_jump_font_size += 1
            footer_note_size += 1
            nav_padding_v += 1
            nav_padding_h += 1
        elif scale >= 1.25:
            hero_subtitle_size += 1
            overview_text_size += 1
            lead_size += 1
            summary_size += 1
            field_note_size += 1
            nav_padding_h += 1

        if is_short_window:
            hero_title_size = max(18, hero_title_size - 1)
            hero_subtitle_size = max(11, hero_subtitle_size - 1)
            section_title_size = max(14, section_title_size - 1)
            lead_size = max(11, lead_size - 1)
            summary_size = max(11, summary_size - 1)
            nav_padding_v = max(9, nav_padding_v - 1)
            nav_margin_v = 1

        if hasattr(self, "settings_hero_title"):
            self.settings_hero_title.setStyleSheet(
                f"color: {theme['text']}; font-size: {hero_title_size}px; font-weight: 700;"
            )
        if hasattr(self, "settings_hero_subtitle"):
            self.settings_hero_subtitle.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {hero_subtitle_size}px; line-height: 1.6;"
            )
        for label in [getattr(self, "lbl_settings_common_tag", None), getattr(self, "lbl_settings_advanced_tag", None)]:
            if label:
                label.setStyleSheet(
                    f"color: {theme['primary']}; background-color: #E9F1FB; border: 1px solid {theme['border']}; "
                    f"border-radius: 10px; padding: 6px 10px; font-size: {hero_tag_size}px; font-weight: 700;"
                )
        if hasattr(self, "settings_overview_title"):
            self.settings_overview_title.setStyleSheet(
                f"color: {theme['text']}; font-size: {overview_title_size}px; font-weight: 700;"
            )
        if hasattr(self, "settings_overview_text"):
            self.settings_overview_text.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {overview_text_size}px; line-height: 1.6;"
            )
        if hasattr(self, "settings_nav_hint"):
            self.settings_nav_hint.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {hint_size}px; font-weight: 700; letter-spacing: 0.05em;"
            )
        if hasattr(self, "settings_nav_subtitle"):
            self.settings_nav_subtitle.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {field_note_size}px; line-height: 1.6;"
            )
        if hasattr(self, "settings_sidebar_note"):
            self.settings_sidebar_note.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {field_note_size}px; line-height: 1.6;"
            )
        if hasattr(self, "settings_sidebar_status"):
            self.settings_sidebar_status.setStyleSheet(
                f"color: {theme['text_secondary']}; background-color: #F8FBFE; border: 1px solid {theme['border']}; "
                f"border-radius: 10px; padding: 8px 10px; font-size: {field_note_size}px; line-height: 1.6; font-weight: 600;"
            )
        if hasattr(self, "settings_footer_note"):
            self.settings_footer_note.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {footer_note_size}px; line-height: 1.6; padding-right: 8px;"
            )
        if hasattr(self, "settings_nav"):
            self.settings_nav.setStyleSheet(
                f"""
                QListWidget#settingsNav {{
                    background-color: transparent;
                    border: none;
                    outline: none;
                    padding: 0;
                }}
                QListWidget#settingsNav::item {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 10px;
                    padding: {nav_padding_v}px {nav_padding_h}px;
                    margin: {nav_margin_v}px 0;
                    color: {theme["text"]};
                    font-size: {nav_font_size}px;
                    font-weight: 600;
                }}
                QListWidget#settingsNav::item:selected {{
                    background-color: {theme["hover"]};
                    border-color: {theme["border"]};
                    color: {theme["primary"]};
                }}
                QListWidget#settingsNav::item:hover {{
                    background-color: {theme["hover"]};
                }}
                """
            )
        for label in self.findChildren(QLabel, "settingsMetricLabel"):
            label.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {metric_label_size}px; font-weight: 700;"
            )
        for label in self.findChildren(QLabel, "settingsMetricValue"):
            label.setStyleSheet(
                f"color: {theme['text']}; font-size: {metric_value_size}px; font-weight: 700;"
            )
        for label in self.findChildren(QLabel, "settingsSectionTitle"):
            label.setStyleSheet(
                f"color: {theme['primary']}; font-size: {section_title_size}px; font-weight: 700; background-color: transparent;"
            )
        for label in self.findChildren(QLabel, "settingsSectionLead"):
            label.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {lead_size}px; line-height: 1.7;"
            )
        for label in self.findChildren(QLabel, "settingsSectionSummary"):
            label.setStyleSheet(
                f"color: {theme['text_secondary']}; background-color: #F8FBFE; border: 1px solid {theme['border']}; "
                f"border-radius: 10px; padding: 8px 12px; font-size: {summary_size}px; font-weight: 600; line-height: 1.6;"
            )
        for label in self.findChildren(QLabel, "settingsFieldTitle"):
            label.setStyleSheet(
                f"color: {theme['text']}; font-size: {field_title_size}px; font-weight: 700;"
            )
        for label in self.findChildren(QLabel, "settingsFieldLabel"):
            label.setStyleSheet(
                f"color: {theme['text']}; font-size: {field_label_size}px; font-weight: 600;"
            )
        for label in self.findChildren(QLabel, "settingsFieldNote"):
            label.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {field_note_size}px; line-height: 1.6;"
            )
        for label in self.findChildren(QLabel, "settingsActionHint"):
            label.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {hint_size}px; font-weight: 700; letter-spacing: 0.04em;"
            )
        for button in getattr(self, "settings_quick_jump_buttons", []):
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: #FBFCFE;
                    color: {theme["text"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 10px;
                    padding: 8px 14px;
                    font-size: {quick_jump_font_size}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {theme["hover"]};
                    border-color: {theme["primary"]};
                    color: {theme["primary"]};
                }}
                """
            )

    def _set_rule_checkbox_states(self, enabled_names):
        """批量更新规则勾选状态，避免多次触发联动刷新。"""
        enabled_names = set(enabled_names)
        for checkbox in self.checks.values():
            checkbox.blockSignals(True)
        try:
            for name, checkbox in self.checks.items():
                checkbox.setChecked(name in enabled_names)
        finally:
            for checkbox in self.checks.values():
                checkbox.blockSignals(False)
        self._refresh_rule_summary()

    def _apply_recommended_rules(self):
        """恢复首次使用推荐的通用规则勾选。"""
        self._set_rule_checkbox_states(self.recommended_rule_names)

    def _select_all_rules(self):
        """勾选全部通用规则。"""
        self._set_rule_checkbox_states(self.checks.keys())

    def _clear_all_rules(self):
        """清空所有通用规则勾选。"""
        self._set_rule_checkbox_states([])

    def _clear_custom_keywords(self):
        """清空自定义关键词文本框。"""
        self.txt_custom.clear()

    def _clear_blacklist(self):
        """清空黑名单文本框。"""
        self.txt_blacklist.clear()

    def _clear_whitelist(self):
        """清空白名单文本框。"""
        self.txt_whitelist.clear()

    @staticmethod
    def _parse_lines(text):
        """按行解析文本, 去空 / 去空白 / 去重保序.

        用于黑/白名单的文本编辑框 → store 列表转换.
        """
        if not isinstance(text, str):
            return []
        seen = set()
        out = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                out.append(stripped)
        return out

    def _on_black_white_changed(self):
        """v1.1.11: 黑/白名单文本变化时回写 store + config.json.

        通过公开 API BlackWhiteListStore.update_permanent 写入,
        会话层独立保留, 与 _initial_blacklist / _initial_whitelist 无关.
        """
        try:
            black = self._parse_lines(self.txt_blacklist.toPlainText())
            white = self._parse_lines(self.txt_whitelist.toPlainText())
            store = BlackWhiteListStore.instance()
            store.update_permanent(black, white)
            store.save_permanent()
            if hasattr(self, "lbl_black_summary"):
                self.lbl_black_summary.setText(f"当前条目: {len(black)} 条 (已写入 config.json)")
            if hasattr(self, "lbl_white_summary"):
                self.lbl_white_summary.setText(f"当前条目: {len(white)} 条 (已写入 config.json)")
            self._refresh_settings_sidebar()
        except Exception as exc:
            print(f"[Settings] 黑/白名单回写失败: {exc}")

    def _reset_replacement_text(self):
        """恢复默认统一替换文本。"""
        self.input_replacement_text.setText(self.default_replacement_text)

    def _reset_precision_defaults(self):
        """恢复推荐的扫描与微调设置。"""
        default_index = self.combo_precision.findData(2.0)
        if default_index >= 0:
            self.combo_precision.setCurrentIndex(default_index)
        self.spin_offset_x.setValue(0)
        self.spin_offset_w.setValue(0)
        self.cb_enhance.setChecked(False)
        self._refresh_precision_summary()

    def _reset_ocr_adjustment(self):
        """恢复 OCR 检测框默认调节值。"""
        self.slider_adjust.setValue(0)
        self._refresh_ocr_summary()

    def _scroll_to_settings_section(self, row):
        """左侧导航切换到对应设置区块。"""
        if getattr(self, "_settings_nav_syncing", False):
            return
        if row < 0 or row >= len(getattr(self, "_settings_sections", [])):
            return
        target = self._settings_sections[row]
        if not target or not hasattr(self, "content_scroll"):
            return
        self.content_scroll.verticalScrollBar().setValue(max(0, target.pos().y() - 8))

    def _sync_settings_nav_from_scroll(self, value):
        """滚动右侧内容时，同步高亮左侧设置导航。"""
        sections = getattr(self, "_settings_sections", [])
        if not sections or not hasattr(self, "settings_nav"):
            return

        active_row = 0
        threshold = value + 24
        for index, section in enumerate(sections):
            if section and section.pos().y() <= threshold:
                active_row = index
            else:
                break

        if self.settings_nav.currentRow() == active_row:
            return

        self._settings_nav_syncing = True
        self.settings_nav.blockSignals(True)
        self.settings_nav.setCurrentRow(active_row)
        self.settings_nav.blockSignals(False)
        self._settings_nav_syncing = False

    def _refresh_settings_overview(self):
        """刷新设置页顶部配置概览。"""
        if not all(hasattr(self, attr) for attr in [
            "lbl_metric_rules", "lbl_metric_keywords", "lbl_metric_word_rules", "lbl_metric_ocr"
        ]):
            return

        enabled_rules = len([name for name, cb in self.checks.items() if cb.isChecked()]) if hasattr(self, "checks") else 0
        total_rules = len(self.checks) if hasattr(self, "checks") else 0
        keywords = [line.strip() for line in self.txt_custom.toPlainText().splitlines() if line.strip()] if hasattr(self, "txt_custom") else []
        enabled_word_rules = len([r for r in self.word_replace_rules if r.get("enabled", True) and r.get("find")]) if hasattr(self, "word_replace_rules") else 0
        total_word_rules = len(self.word_replace_rules) if hasattr(self, "word_replace_rules") else 0
        adjust_value = self.slider_adjust.value() if hasattr(self, "slider_adjust") else 0
        scan_label = self.combo_precision.currentText().strip() if hasattr(self, "combo_precision") else "-"
        precision_is_default = True
        if hasattr(self, "combo_precision") and hasattr(self, "spin_offset_x") and hasattr(self, "spin_offset_w") and hasattr(self, "cb_enhance"):
            precision_is_default = (
                self.combo_precision.currentData() == 2.0
                and self.spin_offset_x.value() == 0
                and self.spin_offset_w.value() == 0
                and not self.cb_enhance.isChecked()
            )

        self.lbl_metric_rules.setText(f"{enabled_rules} / {total_rules} 已启用")
        self.lbl_metric_keywords.setText(f"{len(keywords)} 条关键词")
        self.lbl_metric_word_rules.setText(f"{enabled_word_rules} / {total_word_rules} 条规则")
        self.lbl_metric_ocr.setText(f"{adjust_value}% · {scan_label}")
        if hasattr(self, "lbl_settings_common_tag") and hasattr(self, "lbl_settings_advanced_tag"):
            common_tag, advanced_tag = build_settings_hero_tags(
                enabled_rules,
                len(keywords),
                enabled_word_rules,
                precision_is_default,
                adjust_value,
                scan_label,
            )
            self.lbl_settings_common_tag.setText(common_tag)
            self.lbl_settings_common_tag.setToolTip(common_tag)
            self.lbl_settings_advanced_tag.setText(advanced_tag)
            self.lbl_settings_advanced_tag.setToolTip(advanced_tag)
        self._refresh_settings_sidebar()

    def _refresh_settings_sidebar(self):
        """刷新左侧导航和侧栏摘要。"""
        if not hasattr(self, "settings_nav"):
            return

        enabled_rules = len([name for name, cb in self.checks.items() if cb.isChecked()]) if hasattr(self, "checks") else 0
        keyword_count = len([line.strip() for line in self.txt_custom.toPlainText().splitlines() if line.strip()]) if hasattr(self, "txt_custom") else 0
        blacklist_count = len([line.strip() for line in self.txt_blacklist.toPlainText().splitlines() if line.strip()]) if hasattr(self, "txt_blacklist") else 0
        whitelist_count = len([line.strip() for line in self.txt_whitelist.toPlainText().splitlines() if line.strip()]) if hasattr(self, "txt_whitelist") else 0
        precision_is_default = True
        if hasattr(self, "combo_precision") and hasattr(self, "spin_offset_x") and hasattr(self, "spin_offset_w") and hasattr(self, "cb_enhance"):
            precision_is_default = (
                self.combo_precision.currentData() == 2.0
                and self.spin_offset_x.value() == 0
                and self.spin_offset_w.value() == 0
                and not self.cb_enhance.isChecked()
            )
        adjust_value = self.slider_adjust.value() if hasattr(self, "slider_adjust") else 0

        nav_labels = build_settings_nav_labels(enabled_rules, keyword_count, precision_is_default, adjust_value, blacklist_count, whitelist_count)
        for index, text in enumerate(nav_labels):
            item = self.settings_nav.item(index)
            if item and item.text() != text:
                item.setText(text)

        if hasattr(self, "settings_sidebar_status"):
            advanced_text = "扫描保持默认" if precision_is_default else "扫描参数已微调"
            self.settings_sidebar_status.setText(
                f"常用区：规则 {enabled_rules} 项、关键词 {keyword_count} 条。\n"
                f"高级区：{advanced_text} · OCR {format_signed_percent(adjust_value)}。"
            )

    def _refresh_word_rule_summary(self):
        enabled_count = len([r for r in self.word_replace_rules if r.get("enabled", True) and r.get("find")])
        total_count = len(self.word_replace_rules)
        self.lbl_word_rule_count.setText(
            f"当前规则：{enabled_count} 条启用 / {total_count} 条总计\n"
            "点击“打开替换规则设置”可进入原有替换规则弹窗。"
        )
        self._refresh_custom_summary()

    def _refresh_rule_summary(self):
        enabled_names = [name for name, cb in self.checks.items() if cb.isChecked()]
        enabled_count = len(enabled_names)
        preview = "、".join(enabled_names[:3]) if enabled_names else "当前未启用任何通用规则"
        if enabled_count > 3:
            preview = f"{preview} 等 {enabled_count} 项"
        self.lbl_rules_summary.setText(f"当前启用：{preview}")
        self._refresh_settings_overview()

    def _refresh_custom_summary(self):
        keyword_lines = [line.strip() for line in self.txt_custom.toPlainText().splitlines() if line.strip()]
        keyword_count = len(keyword_lines)
        replacement_preview = self.input_replacement_text.text().strip() or "[已脱敏]"
        enabled_rule_count = len([r for r in self.word_replace_rules if r.get("enabled", True) and r.get("find")])
        self.lbl_custom_summary.setText(
            f"自定义关键词 {keyword_count} 条 · 统一替换文本：{replacement_preview} · Word 规则：{enabled_rule_count} 条启用"
        )
        self._refresh_settings_overview()

    def _refresh_precision_summary(self):
        current_label = self.combo_precision.currentText().strip()
        enhance_text = "已开启图像增强" if self.cb_enhance.isChecked() else "图像增强关闭"
        self.lbl_precision_summary.setText(
            f"当前扫描模式：{current_label} · 向左修正 {self.spin_offset_x.value()} px · 宽度收缩 {self.spin_offset_w.value()} px · {enhance_text}"
        )
        self._refresh_settings_overview()

    def _refresh_ocr_summary(self):
        adjust_value = self.slider_adjust.value()
        if adjust_value < 0:
            trend = "扩大检测框"
        elif adjust_value > 0:
            trend = "收缩检测框"
        else:
            trend = "保持原始检测框"
        self.lbl_ocr_summary.setText(f"当前检测框调节：{adjust_value}% · {trend}")
        self._refresh_settings_overview()

    def _refresh_overrides_summary(self):
        """v1.1.11: 读取 config 中的 permanent overrides 数量,刷新概述."""
        if not self.config:
            self.lbl_overrides_summary.setText("当前未挂载配置管理器,无法统计。")
            return
        items = self.config.get("redaction.overrides.permanent", []) or []
        total = len(items) if isinstance(items, list) else 0
        ignore_n = sum(1 for it in items if isinstance(it, dict) and it.get("action") == "ignore")
        confirm_n = sum(1 for it in items if isinstance(it, dict) and it.get("action") == "confirm")
        self.lbl_overrides_summary.setText(
            f"当前 permanent 列表: 共 {total} 条(ignore {ignore_n} / confirm {confirm_n})"
        )
        self._refresh_settings_overview()

    def _on_clean_stale_overrides(self):
        """v1.1.11: 清理 30 天前 promoted 的 permanent override."""
        if not self.config:
            QMessageBox.warning(self, "提示", "未挂载配置管理器,无法清理。")
            return
        from secureredact.redaction.override_store import clean_stale_permanent
        items = self.config.get("redaction.overrides.permanent", []) or []
        if not isinstance(items, list):
            QMessageBox.warning(self, "提示", "permanent 字段格式异常,无法清理。")
            return
        before = len(items)
        cleaned = clean_stale_permanent(items, max_age_days=30)
        removed = before - len(cleaned)
        self.config.set("redaction.overrides.permanent", cleaned)
        try:
            self.config.save()
        except Exception as exc:
            QMessageBox.warning(self, "失败", f"保存配置失败: {exc}")
            return
        # 同步内存中的 store
        mw = self.parent()
        if mw is not None and hasattr(mw, "_override_store"):
            try:
                mw._override_store.replace_permanent(cleaned)
            except Exception:
                pass
        self._refresh_overrides_summary()
        QMessageBox.information(
            self,
            "完成",
            f"已清理 {removed} 条失效 permanent override(剩余 {len(cleaned)} 条)。",
        )

    def _open_word_rules_editor(self):
        default_text = self.input_replacement_text.text().strip() or "[已脱敏]"
        dlg = WordReplaceRulesDialog(
            self,
            rules=self.word_replace_rules,
            default_replacement_text=default_text,
            title="Word 替换规则设置",
            apply_text="应用规则"
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self.word_replace_rules = dlg.rules
        self.input_replacement_text.setText(dlg.default_replacement_text)
        self._refresh_word_rule_summary()

    def save_settings(self):
        from main import DEFAULT_RULES  # PR-B5.2: 延迟导入, 避免循环
        self.selected_rules = [DEFAULT_RULES[name] for name, cb in self.checks.items() if cb.isChecked()]
        # v1.1.11: 添加调试输出
        print(f"[Settings] 保存的规则: {self.selected_rules}")
        print(f"[Settings] 勾选的规则名称: {[name for name, cb in self.checks.items() if cb.isChecked()]}")
        self.use_enhance = self.cb_enhance.isChecked()
        self.custom_keywords = self.txt_custom.toPlainText().strip()
        self.scan_level = self.combo_precision.currentData()
        self.offset_x = self.spin_offset_x.value()
        self.offset_w = self.spin_offset_w.value()
        self.replacement_text = self.input_replacement_text.text().strip() or "[已脱敏]"
        self.word_replace_rules = normalize_word_replace_rules(self.word_replace_rules, self.replacement_text)

        # v1.1.11: 保存检测框调节比例
        self.box_adjust_ratio = self.slider_adjust.value() / 100.0

        # v1.1.11: 中文姓名启发式识别开关
        self.enable_name_recognition = self.cb_name_recognition.isChecked()

        # v1.1.11: 保存到配置文件
        if self.config:
            try:
                self.config.set("redaction.scan.default_level", self.scan_level, persist=False)
                self.config.set("redaction.offset.default_x", self.offset_x, persist=False)
                self.config.set("redaction.offset.default_w", self.offset_w, persist=False)
                # v1.1.11: 移除 OCR 引擎选择，只保留 RapidOCR
                # v1.1.11: 保存检测框调节比例（新配置名）
                self.config.set("redaction.custom_keywords", self.custom_keywords, persist=False)
                self.config.set("redaction.replacement_text", self.replacement_text, persist=False)
                self.config.set("ocr.box_adjust_ratio", self.box_adjust_ratio, persist=False)
                # v1.1.11: 姓名识别开关持久化
                self.config.set("redaction.enable_name_recognition",
                                self.enable_name_recognition, persist=False)
                self.config.save()
            except Exception as e:
                print(f"[设置] 保存配置失败: {e}")

        self.accept()

    def _apply_dialog_theme(self):
        """应用对话框浅色主题样式（v1.1.11: 修复 Windows 深色模式显示问题）"""
        from theme import Theme
        theme = Theme.LIGHT

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme["background"]};
                font-family: {Theme.FONT_FAMILY};
            }}
            QWidget {{
                background-color: {theme["background"]};
                color: {theme["text"]};
                font-family: {Theme.FONT_FAMILY};
            }}
            QFrame#settingsHero {{
                background-color: {theme["surface"]};
                border: 1px solid {theme["border"]};
                border-radius: 18px;
            }}
            QFrame#settingsOverview {{
                background-color: {theme["surface"]};
                border: 1px solid {theme["border"]};
                border-radius: 18px;
            }}
            QFrame#settingsMetricCard {{
                background-color: #F8FBFE;
                border: 1px solid {theme["border"]};
                border-radius: 12px;
            }}
            QLabel#settingsTitle {{
                color: {theme["text"]};
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#settingsOverviewTitle {{
                color: {theme["text"]};
                font-size: 16px;
                font-weight: 700;
            }}
            QLabel#settingsOverviewText {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                line-height: 1.6;
            }}
            QLabel#settingsMetricLabel {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                font-weight: 700;
            }}
            QLabel#settingsMetricValue {{
                color: {theme["text"]};
                font-size: 16px;
                font-weight: 700;
            }}
            QPushButton#settingsQuickJumpButton {{
                background-color: #FBFCFE;
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#settingsQuickJumpButton:hover {{
                background-color: {theme["hover"]};
                border-color: {theme["primary"]};
                color: {theme["primary"]};
            }}
            QLabel#settingsSubtitle {{
                color: {theme["text_secondary"]};
                font-size: 12px;
                line-height: 1.6;
            }}
            QLabel#settingsHeroTag {{
                color: {theme["primary"]};
                background-color: #E9F1FB;
                border: 1px solid {theme["border"]};
                border-radius: 10px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
            QFrame#settingsSidebar {{
                background-color: {theme["surface"]};
                border: 1px solid {theme["border"]};
                border-radius: 18px;
            }}
            QFrame#settingsSidebarMetaCard {{
                background-color: #FBFCFE;
                border: 1px solid {theme["border"]};
                border-radius: 14px;
            }}
            QFrame#settingsFooter {{
                background-color: {theme["surface"]};
                border: 1px solid {theme["border"]};
                border-radius: 16px;
            }}
            QFrame#settingsFieldCard, QWidget#settingsInnerPanel {{
                background-color: #FBFCFE;
                border: 1px solid {theme["border"]};
                border-radius: 14px;
            }}
            QLabel#settingsHint {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.05em;
            }}
            QLabel#settingsSidebarNote {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                line-height: 1.6;
            }}
            QLabel#settingsSidebarSubtle {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                line-height: 1.6;
            }}
            QLabel#settingsSidebarStatus {{
                color: {theme["text_secondary"]};
                background-color: #F8FBFE;
                border: 1px solid {theme["border"]};
                border-radius: 10px;
                padding: 8px 10px;
                font-size: 11px;
                line-height: 1.6;
                font-weight: 600;
            }}
            QLabel#settingsFooterNote {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                line-height: 1.6;
                padding-right: 8px;
            }}
            QLabel#settingsFieldTitle {{
                color: {theme["text"]};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#settingsFieldLabel {{
                color: {theme["text"]};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#settingsFieldNote {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                line-height: 1.6;
            }}
            QFrame#settingsFieldDivider {{
                background-color: {theme["border"]};
                border: none;
            }}
            QLabel#settingsSectionLead {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                line-height: 1.7;
            }}
            QLabel#settingsSectionSummary {{
                color: {theme["text_secondary"]};
                background-color: #F8FBFE;
                border: 1px solid {theme["border"]};
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 600;
                line-height: 1.6;
            }}
            QListWidget#settingsNav {{
                background-color: transparent;
                border: none;
                outline: none;
                padding: 0;
            }}
            QListWidget#settingsNav::item {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 10px;
                padding: 10px 12px;
                margin: 2px 0;
                color: {theme["text"]};
                font-weight: 600;
            }}
            QListWidget#settingsNav::item:selected {{
                background-color: {theme["hover"]};
                border-color: {theme["border"]};
                color: {theme["primary"]};
            }}
            QListWidget#settingsNav::item:hover {{
                background-color: {theme["hover"]};
            }}
            QFrame#settingsSectionCard {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 16px;
            }}
            QFrame#settingsSectionHeader {{
                background-color: transparent;
                border: none;
            }}
            QLabel#settingsSectionTitle {{
                color: {theme["primary"]};
                font-size: 15px;
                font-weight: 700;
                background-color: transparent;
            }}
            QLabel {{
                color: {theme["text"]};
                background-color: transparent;
            }}
            QCheckBox {{
                color: {theme["text"]};
                background-color: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QTextEdit {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
            QLineEdit {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 22px;
            }}
            QComboBox {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 6px;
                min-width: 100px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                selection-background-color: {theme["primary"]};
            }}
            QSpinBox {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 6px;
            }}
            QSlider {{
                background-color: transparent;
            }}
            QSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background-color: {theme["border"]};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {theme["primary"]};
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QPushButton {{
                background-color: {theme["primary"]};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {theme["primary"]};
                opacity: 0.9;
            }}
            QPushButton:pressed {{
                background-color: {theme["pressed"]};
            }}
            QPushButton#settingsSecondaryButton {{
                background-color: #FBFCFE;
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                padding: 10px 18px;
            }}
            QPushButton#settingsSecondaryButton:hover {{
                background-color: {theme["hover"]};
                border-color: {theme["primary"]};
            }}
            QLabel#settingsActionHint {{
                color: {theme["text_secondary"]};
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton#settingsInlineButton {{
                background-color: #FBFCFE;
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 9px;
                padding: 7px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#settingsInlineButton:hover {{
                background-color: {theme["hover"]};
                border-color: {theme["primary"]};
                color: {theme["primary"]};
            }}
        """)
