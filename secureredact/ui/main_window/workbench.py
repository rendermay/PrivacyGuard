"""
工作台 + info_bar + 状态徽章 mixin — MainWindow 工作台相关方法 (PR-B2.2 迁出)

提供 17 个工作台/状态徽章/布局方法,作为 `MainWindowWorkbenchMixin`。
`MainWindow` 通过多继承复用本 mixin,行为零改动。

来源:原 `main.py` 中 17 个工作台相关方法(共 ~494 行),逐字搬迁,逻辑零改动。
`_refresh_windows_density_metrics`(918 行)留 MainWindow 本类(跨工具栏 + 工作台密度计算,B2.6 处理)。
"""
from __future__ import annotations

import os  # PR-B5.2: 补 os 引用

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QWidget,
)
from theme import Theme  # PR-B5.2: 补 Theme 引用(原 main.py 模块级)

from ._helpers import build_workbench_guidance  # PR-B5.2: 综合迁出


class MainWindowWorkbenchMixin:
    """工作台上下文条 / info_bar / 状态徽章 / 布局重建 / 工作台引导 / 模式徽章 / Word 对比切换。

    方法签名与实现与原 MainWindow 内一致,直接被 MainWindow 继承使用。
    依赖 MainWindow 上的属性:
        - self.workbench_panel / self.info_bar / self.context_message
        - self.lbl_mode_badge / self.lbl_workbench_*
        - self.idle_* / self.batch_* / self.merge_* widget 引用
        - self.theme / self.Theme
        - self.app_state / self.density_mode
    """

    def _set_status_badge_style(self, label, fg, bg):
        """为轻量状态标签设置统一的胶囊样式。"""
        if not label:
            return
        badge_font_size = getattr(self, "_status_badge_font_size", 12)
        label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {Theme.LIGHT["border"]};
                border-radius: 14px;
                padding: 6px 12px;
                font-size: {badge_font_size}px;
                font-weight: 700;
            }}
            """
        )

    def _set_info_bar_message(self, message):
        """设置顶部临时任务提示；空值时按当前模式决定是否隐藏。"""
        self.info_bar_message = str(message).strip() if message else ""
        self._refresh_info_bar_visibility()

    def _clear_info_bar_message(self):
        """清空顶部临时任务提示。"""
        self.info_bar_message = ""
        self._refresh_info_bar_visibility()

    def _refresh_info_bar_visibility(self):
        """避免顶部提示条与工作台摘要重复。"""
        if not hasattr(self, "info_bar"):
            return

        if self.current_ui_mode == "idle":
            if self.info_bar_message:
                self.info_bar.setText(self.info_bar_message)
                self.info_bar.setVisible(True)
            else:
                self.info_bar.setVisible(False)
            return

        if self.info_bar_message:
            self.info_bar.setText(self.info_bar_message)
            self.info_bar.setVisible(True)
        else:
            self.info_bar.setVisible(False)

    def _rebuild_idle_action_layout(self, density_mode):
        """让首页主动作与支持入口在桌面端双列，窄窗口再收成单列。"""
        if not hasattr(self, "idle_action_buttons_layout"):
            return

        layout = self.idle_action_buttons_layout
        while layout.count():
            layout.takeAt(0)

        if density_mode == "narrow":
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 0)
            layout.addWidget(self.idle_start_card, 0, 0)
            layout.addWidget(self.idle_support_card, 1, 0)
        else:
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 1)
            layout.addWidget(self.idle_start_card, 0, 0)
            layout.addWidget(self.idle_support_card, 0, 1)

    def _rebuild_idle_support_actions_layout(self, density_mode):
        """重排首页支持区动作按钮，宽窗口横排，窄窗口改为 2+1。"""
        if not hasattr(self, "idle_support_actions_layout"):
            return

        layout = self.idle_support_actions_layout
        while layout.count():
            layout.takeAt(0)

        buttons = [
            getattr(self, "btn_idle_feedback", None),
            getattr(self, "btn_idle_manual", None),
            getattr(self, "btn_idle_donate", None),
        ]
        buttons = [button for button in buttons if button]
        if not buttons:
            return

        if density_mode == "narrow":
            for column in range(3):
                layout.setColumnStretch(column, 0)
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 1)
            layout.addWidget(buttons[0], 0, 0)
            if len(buttons) > 1:
                layout.addWidget(buttons[1], 0, 1)
            if len(buttons) > 2:
                layout.addWidget(buttons[2], 1, 0, 1, 2)
        else:
            for column in range(3):
                layout.setColumnStretch(column, 1)
            for index, button in enumerate(buttons):
                layout.addWidget(button, 0, index)

    def _rebuild_idle_route_layout(self, density_mode):
        """重排首页入口卡，保证桌面端严格 2x2 对齐。"""
        if not hasattr(self, "idle_routes_layout"):
            return

        layout = self.idle_routes_layout
        while layout.count():
            layout.takeAt(0)

        if density_mode == "narrow":
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 0)
            for row in range(max(1, len(getattr(self, "idle_route_cards", [])) + 1)):
                layout.setRowStretch(row, 0)
            for index, route_card in enumerate(getattr(self, "idle_route_cards", [])):
                layout.addWidget(route_card, index, 0)
        else:
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 1)
            layout.setRowStretch(0, 0)
            layout.setRowStretch(1, 0)
            for index, route_card in enumerate(getattr(self, "idle_route_cards", [])):
                layout.addWidget(route_card, index // 2, index % 2)

    def _rebuild_batch_action_layout(self, density_mode):
        """重排批量页动作区，宽窗口横排，中窗口两列，窄窗口单列。"""
        if not hasattr(self, "batch_actions_layout"):
            return

        layout = self.batch_actions_layout
        while layout.count():
            layout.takeAt(0)

        buttons = list(getattr(self, "batch_action_buttons", []))
        if not buttons:
            return

        for column in range(max(4, len(buttons))):
            layout.setColumnStretch(column, 0)
        for row in range(max(4, len(buttons))):
            layout.setRowStretch(row, 0)

        if density_mode == "narrow":
            layout.setColumnStretch(0, 1)
            for index, button in enumerate(buttons):
                layout.addWidget(button, index, 0)
        elif density_mode == "compact":
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 1)
            for index, button in enumerate(buttons):
                layout.addWidget(button, index // 2, index % 2)
        else:
            for column in range(len(buttons)):
                layout.setColumnStretch(column, 1)
            for index, button in enumerate(buttons):
                layout.addWidget(button, 0, index)

    def _rebuild_batch_stage_layout(self, density_mode):
        """重排批量页阶段卡，桌面端横排，中窗口两列，窄窗口单列。"""
        if not hasattr(self, "batch_stage_layout"):
            return

        layout = self.batch_stage_layout
        while layout.count():
            layout.takeAt(0)

        cards = list(getattr(self, "batch_stage_cards", []))
        if not cards:
            return

        if density_mode == "narrow":
            columns = 1
        elif density_mode == "compact":
            columns = 2
        else:
            columns = 3

        for column in range(max(columns, len(cards))):
            layout.setColumnStretch(column, 0)
        for row in range(len(cards)):
            layout.setRowStretch(row, 0)

        for index, (frame, _title_label, _note_label) in enumerate(cards):
            row = index // columns
            column = index % columns
            layout.addWidget(frame, row, column)

        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _rebuild_batch_metrics_layout(self, density_mode):
        """重排批量页指标卡，宽窗口四列，中窗口两列，窄窗口单列。"""
        if not hasattr(self, "batch_metrics_layout"):
            return

        layout = self.batch_metrics_layout
        while layout.count():
            layout.takeAt(0)

        cards = list(getattr(self, "batch_metric_cards", []))
        if not cards:
            return

        if density_mode == "narrow":
            columns = 1
        elif density_mode == "compact":
            columns = 2
        else:
            columns = 4

        for column in range(max(columns, len(cards))):
            layout.setColumnStretch(column, 0)
        for row in range(len(cards)):
            layout.setRowStretch(row, 0)

        for index, card in enumerate(cards):
            row = index // columns
            column = index % columns
            layout.addWidget(card, row, column)

        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _rebuild_merge_stage_layout(self, density_mode):
        """重排图片合并阶段卡，桌面端横排，中窗口两列，窄窗口单列。"""
        if not hasattr(self, "merge_stage_layout"):
            return

        layout = self.merge_stage_layout
        while layout.count():
            layout.takeAt(0)

        cards = list(getattr(self, "merge_stage_cards", []))
        if not cards:
            return

        if density_mode == "narrow":
            columns = 1
        elif density_mode == "compact":
            columns = 2
        else:
            columns = 3

        for column in range(max(columns, len(cards))):
            layout.setColumnStretch(column, 0)
        for row in range(len(cards)):
            layout.setRowStretch(row, 0)

        for index, (frame, _title_label, _note_label) in enumerate(cards):
            row = index // columns
            column = index % columns
            layout.addWidget(frame, row, column)

        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _rebuild_merge_metrics_layout(self, density_mode):
        """重排图片合并指标卡，宽窗口三列，中窗口两列，窄窗口单列。"""
        if not hasattr(self, "merge_metrics_layout"):
            return

        layout = self.merge_metrics_layout
        while layout.count():
            layout.takeAt(0)

        cards = list(getattr(self, "merge_metric_cards", []))
        if not cards:
            return

        if density_mode == "narrow":
            columns = 1
        elif density_mode == "compact":
            columns = 2
        else:
            columns = 3

        for column in range(max(columns, len(cards))):
            layout.setColumnStretch(column, 0)
        for row in range(len(cards)):
            layout.setRowStretch(row, 0)

        for index, card in enumerate(cards):
            row = index // columns
            column = index % columns
            layout.addWidget(card, row, column)

        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _rebuild_batch_detail_layout(self, density_mode):
        """重排批量页摘要/结果/日志区，宽窗口双区，窄窗口单列。"""
        if not hasattr(self, "batch_detail_layout"):
            return

        layout = self.batch_detail_layout
        while layout.count():
            layout.takeAt(0)

        summary_section = getattr(self, "batch_summary_section", None)
        result_section = getattr(self, "batch_result_section", None)
        log_section = getattr(self, "batch_log_section", None)
        if not summary_section or not result_section or not log_section:
            return

        for column in range(3):
            layout.setColumnStretch(column, 0)
        for row in range(3):
            layout.setRowStretch(row, 0)

        if density_mode == "narrow":
            layout.setHorizontalSpacing(0)
            layout.setVerticalSpacing(12)
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 0)
            layout.addWidget(summary_section, 0, 0)
            layout.addWidget(result_section, 1, 0)
            layout.addWidget(log_section, 2, 0)
            layout.setRowStretch(0, 0)
            layout.setRowStretch(1, 1)
            layout.setRowStretch(2, 1)
        elif density_mode == "compact":
            layout.setHorizontalSpacing(12)
            layout.setVerticalSpacing(12)
            layout.setColumnStretch(0, 11)
            layout.setColumnStretch(1, 13)
            layout.addWidget(summary_section, 0, 0)
            layout.addWidget(result_section, 0, 1)
            layout.addWidget(log_section, 1, 0, 1, 2)
            layout.setRowStretch(0, 1)
            layout.setRowStretch(1, 1)
        else:
            layout.setHorizontalSpacing(14 if density_mode == "wide" else 12)
            layout.setVerticalSpacing(14 if density_mode == "wide" else 12)
            layout.setColumnStretch(0, 8)
            layout.setColumnStretch(1, 18)
            layout.addWidget(summary_section, 0, 0)
            layout.addWidget(log_section, 1, 0)
            layout.addWidget(result_section, 0, 1, 2, 1)
            layout.setRowStretch(0, 0)
            layout.setRowStretch(1, 1)

    def _refresh_workbench_guidance(self, guidance_items):
        """刷新主工作台顶部的下一步引导标签。当前版本默认隐藏，保持上下文条简洁。"""
        if not hasattr(self, "workbench_guidance_labels"):
            return
        for label in self.workbench_guidance_labels:
            label.hide()

    def _refresh_workbench_context(self):
        """刷新主工作台标题、步骤和下一步提示。"""
        if not hasattr(self, "lbl_workbench_title"):
            return

        mode = self.current_ui_mode
        active_step = 0
        focus_text = "第 1 步"
        focus_fg = Theme.LIGHT["primary"]
        focus_bg = "#E9F1FB"
        guidance_items = build_workbench_guidance("idle")
        show_focus_badge = mode != "idle"
        show_workbench_subtitle = mode != "idle"

        if mode == "pdf" and self.doc:
            total_pages = len(self.doc)
            current_page = (self.current_page + 1) if self.current_page is not None else 0
            has_results = self._has_pdf_redactions()
            active_step = 3 if has_results else 2
            focus_text = "PDF 脱敏"
            show_focus_badge = False
            self.lbl_workbench_title.setText("PDF 脱敏工作台")
            self.lbl_workbench_subtitle.setText(
                f"{os.path.basename(self.file_path or '')} · {current_page} / {total_pages} 页 · 黑 / 白即时切换"
            )
            guidance_items = build_workbench_guidance("pdf", has_results=has_results)
        elif mode == "word" and self.word_doc:
            paragraph_count = len(self.word_doc.paragraphs)
            table_count = len(self.word_doc.tables)
            has_results = self._has_word_redactions() or self._count_enabled_word_rules() > 0
            active_step = 3 if has_results else 2
            focus_text = "Word 替换"
            focus_fg = Theme.LIGHT["success"]
            focus_bg = "#EAF8F1"
            show_focus_badge = False
            compare_status = "已开启" if self.word_compare_mode else "已隐藏"
            self.lbl_workbench_title.setText("Word 替换工作台")
            self.lbl_workbench_subtitle.setText(
                f"{os.path.basename(self.file_path or '')} · 段落 {paragraph_count} · 表格 {table_count} · 对比 {compare_status}"
            )
            guidance_items = build_workbench_guidance("word", has_results=has_results, compare_mode=self.word_compare_mode)
        elif mode == "batch":
            if self.batch_stage == "running":
                active_step = 2
                focus_text = "批量执行中"
                focus_fg = Theme.LIGHT["primary"]
                focus_bg = "#E9F1FB"
                summary_text = (
                    f"已选 {self.batch_total_files or len(self.batch_selected_files)} 个文档 · "
                    f"成功 {self.batch_success_count} · 失败 {self.batch_failed_count}"
                )
            elif self.batch_stage in ("finished", "stopped"):
                active_step = 4
                focus_text = "批量结果"
                focus_fg = Theme.LIGHT["success"] if self.batch_stage == "finished" else Theme.LIGHT["danger"]
                focus_bg = "#EAF8F1" if self.batch_stage == "finished" else "#FDECEC"
                summary_text = (
                    f"已选 {self.batch_total_files or len(self.batch_selected_files)} 个文档 · "
                    f"成功 {self.batch_success_count} · 失败 {self.batch_failed_count}"
                )
            else:
                active_step = 1
                focus_text = "规则确认"
                focus_fg = Theme.LIGHT["warning"]
                focus_bg = "#FFF3E6"
                summary_text = (
                    f"已选 {self.batch_total_files or len(self.batch_selected_files)} 个文档 · "
                    f"启用规则 {self._count_enabled_word_rules()} 条"
                )

            self.lbl_workbench_title.setText("批量 Word 工作台")
            self.lbl_workbench_subtitle.setText(summary_text)
            guidance_items = build_workbench_guidance("batch", batch_stage=self.batch_stage)
        elif mode == "image_merge":
            active_step = 2
            focus_text = "图片合并"
            self.lbl_workbench_title.setText("图片合并为 PDF")
            self.lbl_workbench_subtitle.setText(f"当前待合并图片：{self.image_merge_total_images} 张 · 完成后自动进入 PDF 脱敏模式")
            guidance_items = build_workbench_guidance("image_merge")
        else:
            self.lbl_workbench_title.setText("欢迎使用 SecureRedact")
            self.lbl_workbench_subtitle.setText("拖拽或打开文件即可开始处理。")

        self.lbl_workbench_focus.setText(focus_text)
        self._set_status_badge_style(self.lbl_workbench_focus, focus_fg, focus_bg)
        self.lbl_workbench_focus.setVisible(show_focus_badge)
        self.lbl_workbench_subtitle.setVisible(show_workbench_subtitle)
        self._refresh_workbench_guidance(guidance_items)
        self._refresh_workflow_steps(active_step)
        self._refresh_batch_workspace()
        self._refresh_merge_workspace()

    def _refresh_mode_badge(self):
        """刷新顶部模式标识，让用户一眼知道当前在处理什么。"""
        if not hasattr(self, "lbl_mode_badge"):
            return

        mode_map = {
            "idle": ("等待导入", Theme.LIGHT["secondary"], Theme.LIGHT["hover"]),
            "pdf": ("PDF 脱敏模式", Theme.LIGHT["primary"], "#E9F1FB"),
            "word": ("Word 替换模式", Theme.LIGHT["success"], "#EAF8F1"),
            "batch": ("批量 Word 替换", Theme.LIGHT["warning"], "#FFF3E6"),
            "image_merge": ("图片合并中", Theme.LIGHT["primary"], "#E9F1FB"),
        }
        text, fg, bg = mode_map.get(
            self.current_ui_mode,
            ("等待导入", Theme.LIGHT["secondary"], Theme.LIGHT["hover"]),
        )
        self.lbl_mode_badge.setText(text)
        self.lbl_mode_badge.setStyleSheet(
            f"""
            QLabel#modeBadge {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {Theme.LIGHT["border"]};
                border-radius: 14px;
                padding: 6px 12px;
                font-size: {Theme.FONT_SIZE_SMALL}px;
                font-weight: 700;
            }}
            """
        )

    def _refresh_word_compare_toggle(self):
        """刷新 Word 对比预览按钮状态。"""
        if not hasattr(self, "btn_compare_toggle"):
            return

        if not self.word_doc:
            self.btn_compare_toggle.setEnabled(False)
            self.btn_compare_toggle.setText("对比预览")
            self.btn_compare_toggle.setToolTip("请先打开 Word 文档")
            self._apply_button_variant(self.btn_compare_toggle, "secondary")
            self._refresh_toolbar_responsiveness()
            return

        has_candidates = self._has_word_replacement_candidates()
        self.btn_compare_toggle.setEnabled(has_candidates)
        if not has_candidates:
            self.btn_compare_toggle.setText(
                "对比预览（暂无结果）" if self.toolbar_density_mode == "wide" else "暂无对比"
            )
            self.btn_compare_toggle.setToolTip("设置替换规则或执行智能替换后，可查看对比预览")
            self._apply_button_variant(self.btn_compare_toggle, "secondary")
            self._refresh_toolbar_responsiveness()
            return

        if self.word_compare_user_hidden:
            self.btn_compare_toggle.setText(
                "显示对比预览" if self.toolbar_density_mode == "wide" else "显示对比"
            )
            self.btn_compare_toggle.setToolTip("显示右侧替换后预览")
            self._apply_button_variant(self.btn_compare_toggle, "secondary")
        else:
            self.btn_compare_toggle.setText(
                "隐藏对比预览" if self.toolbar_density_mode == "wide" else "隐藏对比"
            )
            self.btn_compare_toggle.setToolTip("隐藏右侧替换后预览")
            self._apply_button_variant(self.btn_compare_toggle, "primary")
        self._refresh_toolbar_responsiveness()
