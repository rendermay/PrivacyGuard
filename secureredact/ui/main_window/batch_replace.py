"""
批量替换编排 mixin — MainWindow 批量 Word 替换逻辑 (PR-B2.5 迁出)

提供 25 个批量替换相关方法,作为 `MainWindowBatchReplaceMixin`。
`MainWindow` 通过多继承复用本 mixin,行为零改动。

来源:原 `main.py` 中 25 个批量替换相关方法(共 ~731 行),逐字搬迁,逻辑零改动。

依赖 MainWindow 上的属性:
    - self.batch_stage_cards / self.batch_metric_cards / self.batch_step_cards
    - self.batch_workspace_card / self.batch_log_list / self.batch_summary_browser
    - self.batch_stage_layout / self.batch_metric_layout / self.batch_detail_layout
    - self.batch_word_files / self.batch_replace_worker
    - self.theme / self.Theme
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget,
)


class MainWindowBatchReplaceMixin:
    """批量 Word 替换 / 步骤卡 / 指标卡 / 进度追踪 / 结果过滤 / 失败重试。

    方法签名与实现与原 MainWindow 内一致,直接被 MainWindow 继承使用。
    """

    def _create_batch_metric_card(self, title):
        """创建批量 Word 工作台指标卡。"""
        card = QFrame()
        card.setObjectName("batchMetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("batchMetricTitle")
        value_label = QLabel("--")
        value_label.setObjectName("batchMetricValue")
        value_label.setWordWrap(True)
        note_label = QLabel("")
        note_label.setObjectName("batchMetricNote")
        note_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(note_label)
        layout.addStretch()
        return card, value_label, note_label

    def _set_batch_step_style(self, frame, title_label, note_label, state, accent_fg=None, accent_bg=None):
        """按当前批量阶段刷新流程卡片样式。"""
        color_map = {
            "pending": (Theme.LIGHT["text_secondary"], "#FBFCFE", Theme.LIGHT["border"]),
            "active": (Theme.LIGHT["primary"], "#E9F1FB", Theme.LIGHT["primary"]),
            "done": (Theme.LIGHT["success"], "#EAF8F1", Theme.LIGHT["success"]),
        }
        fg, bg, border = color_map.get(state, color_map["pending"])
        if accent_fg and accent_bg and state == "active":
            fg = accent_fg
            bg = accent_bg
            border = accent_fg

        frame.setStyleSheet(
            f"""
            QFrame#batchStepCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            """
        )
        title_label.setStyleSheet(
            f"""
            QLabel#batchStepTitle {{
                color: {fg};
                font-size: 12px;
                font-weight: 700;
                background-color: transparent;
            }}
            """
        )
        note_label.setStyleSheet(
            f"""
            QLabel#batchStepNote {{
                color: {Theme.LIGHT["text_secondary"]};
                font-size: 11px;
                line-height: 1.6;
                background-color: transparent;
            }}
            """
        )

    def _build_batch_summary_text(self, total_selected, replacement_preview):
        """构建批量 Word 工作台摘要文本。"""
        rule_count = self._count_enabled_word_rules()
        processed = min(self.batch_processed_files, total_selected) if total_selected else 0
        status_text = "已停止" if self.batch_stage == "stopped" else "已完成"

        if self.batch_stage == "rule_setup":
            lines = [
                "当前还在规则确认阶段，这一步不会改动任何原文件。",
                f"已载入文档：{total_selected} 个",
                f"当前启用 Word 规则：{rule_count} 条",
                f"统一替换文本：{replacement_preview}",
                "",
                "建议先确认：",
                "1. 文档数量是否正确",
                "2. 统一替换文本是否符合当前案卷习惯",
                "3. 是否至少启用了一条 Word 替换规则",
            ]
            return "\n".join(lines)

        if self.batch_stage == "running":
            current_file = self.batch_current_file or "正在准备下一个文档"
            lines = [
                "系统正在逐个处理 Word 文档。",
                f"当前进度：{processed}/{total_selected}",
                f"当前文件：{current_file}",
                f"已成功：{self.batch_success_count} 个",
                f"已失败：{self.batch_failed_count} 个",
                "",
                "如果遇到异常文件，可以在弹窗里选择跳过当前文件，或停止本轮任务。",
            ]
            return "\n".join(lines)

        if self.batch_stage in ("finished", "stopped"):
            lines = [
                f"本轮批量替换{status_text}。",
                f"总文档数：{total_selected}",
                f"成功：{self.batch_success_count} 个",
                f"失败：{self.batch_failed_count} 个",
                f"统一替换文本：{replacement_preview}",
            ]

            summary = self.batch_last_summary or {}
            success_items = summary.get("success", []) if isinstance(summary, dict) else []
            failed_items = summary.get("failed", []) if isinstance(summary, dict) else []
            summary_rules = summary.get("rules", self.word_replace_rules) if isinstance(summary, dict) else self.word_replace_rules

            rule_lines = build_batch_rule_summary_lines(summary_rules, success_items, replacement_preview)
            if rule_lines:
                lines.append("")
                lines.append("本次替换规则：")
                lines.extend(rule_lines)

            if success_items:
                lines.append("")
                lines.append("最近成功输出（最多 5 条）：")
                for item in success_items[:5]:
                    output_path = item.get("output", "")
                    lines.append(f"- {os.path.basename(output_path) if output_path else '已生成输出文件'}")

            if failed_items:
                lines.append("")
                lines.append("失败详情（最多 5 条）：")
                for item in failed_items[:5]:
                    input_name = os.path.basename(item.get("input", ""))
                    error_text = item.get("error", "")
                    lines.append(f"- {input_name}: {error_text}")

            return "\n".join(lines)

        lines = [
            "批量 Word 工作台适合把同一套替换规则一次应用到多个 Word 文档。",
            "系统会先进入规则确认，再开始批量执行，最后集中展示结果。",
            f"统一替换文本：{replacement_preview}",
        ]
        return "\n".join(lines)

    def _reset_batch_session_state(self):
        """重置批量 Word 工作台状态。"""
        self.batch_stage = "idle"
        self.batch_selected_files = []
        self.batch_total_files = 0
        self.batch_processed_files = 0
        self.batch_success_count = 0
        self.batch_failed_count = 0
        self.batch_current_file = ""
        self.batch_last_summary = None
        self.batch_result_filter_mode = "all"
        if hasattr(self, "batch_log_list"):
            self.batch_log_list.clear()

    def _append_batch_log(self, text, level="info"):
        """向批量工作台追加一条最近动态。"""
        if not hasattr(self, "batch_log_list") or not text:
            return

        color_map = {
            "info": Theme.LIGHT["text"],
            "success": Theme.LIGHT["success"],
            "warning": Theme.LIGHT["warning"],
            "error": Theme.LIGHT["danger"],
        }

        item = QListWidgetItem(text)
        item.setForeground(QColor(color_map.get(level, Theme.LIGHT["text"])))
        self.batch_log_list.insertItem(0, item)
        while self.batch_log_list.count() > 30:
            self.batch_log_list.takeItem(self.batch_log_list.count() - 1)

    def _reopen_batch_rule_setup(self):
        """用当前已选文档重新进入批量规则确认。"""
        file_paths = list(self.batch_selected_files) if self.batch_selected_files else None
        self.start_batch_replace(file_paths=file_paths)

    def _start_batch_replace_from_workspace(self):
        """从批量工作台重新选择文件。"""
        self.start_batch_replace()

    def _get_batch_failed_inputs(self):
        """提取本轮批量替换失败的输入文件。"""
        summary = self.batch_last_summary if isinstance(self.batch_last_summary, dict) else {}
        failed_items = summary.get("failed", []) if isinstance(summary, dict) else []
        return [item.get("input") for item in failed_items if isinstance(item, dict) and item.get("input")]

    def _get_batch_success_outputs(self):
        """提取本轮批量替换成功输出文件。"""
        summary = self.batch_last_summary if isinstance(self.batch_last_summary, dict) else {}
        success_items = summary.get("success", []) if isinstance(summary, dict) else []
        return [item.get("output") for item in success_items if isinstance(item, dict) and item.get("output")]

    def _retry_failed_batch_files(self):
        """仅重试本轮失败的批量 Word 文档。"""
        failed_files = self._get_batch_failed_inputs()
        if not failed_files:
            QMessageBox.information(self, "提示", "当前没有可重试的失败文档。")
            return
        self.start_batch_replace(file_paths=failed_files)

    def _open_batch_output_location(self):
        """打开本轮批量替换的输出位置。"""
        output_files = self._get_batch_success_outputs()
        if not output_files:
            QMessageBox.information(self, "提示", "当前还没有可打开的输出文件。")
            return

        first_output = output_files[0]
        target_dir = os.path.dirname(first_output) or os.path.dirname(os.path.abspath(first_output))
        if not target_dir or not os.path.isdir(target_dir):
            QMessageBox.warning(self, "提示", "输出目录不存在，可能已被移动或删除。")
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir)):
            QMessageBox.warning(self, "提示", "无法打开输出目录，请手动前往对应路径查看。")

    def _get_batch_filter_button_style(self, active=False):
        """返回批量结果筛选按钮样式。"""
        theme = Theme.LIGHT
        metrics = getattr(self, "_button_density_metrics", {}) or {}
        font_size = metrics.get("button_font_size", 13) - 1
        padding_v = max(5, metrics.get("button_padding_v", 7) - 2)
        padding_h = max(10, metrics.get("button_padding_h", 14) - 2)
        border_radius = 11

        if active:
            return f"""
                QPushButton {{
                    background-color: #EAF2FC;
                    color: {theme["primary"]};
                    border: 1px solid #B9D3F2;
                    border-radius: {border_radius}px;
                    padding: {padding_v}px {padding_h}px;
                    font-size: {font_size}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: #E3EEF9;
                    border-color: #AFCBEC;
                }}
                QPushButton:disabled {{
                    background-color: #F0F4F9;
                    color: {theme["text_secondary"]};
                    border-color: {theme["border"]};
                }}
            """

        return f"""
            QPushButton {{
                background-color: #FCFDFF;
                color: {theme["text"]};
                border: 1px solid #E2EAF3;
                border-radius: {border_radius}px;
                padding: {padding_v}px {padding_h}px;
                font-size: {font_size}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #F6FAFE;
                border-color: #C7D8EA;
            }}
            QPushButton:disabled {{
                background-color: #F5F7FA;
                color: {theme["text_secondary"]};
                border-color: {theme["border"]};
            }}
        """

    def _refresh_batch_result_filter_buttons(self):
        """刷新批量结果筛选按钮样式与可用性。"""
        all_rows = build_batch_result_rows(self.batch_last_summary) if self.batch_stage in ("finished", "stopped") else []
        counts = summarize_batch_result_rows(all_rows)
        labels = build_batch_filter_labels(counts, show_counts=self.batch_stage in ("finished", "stopped"))
        buttons = [
            ("all", getattr(self, "btn_batch_filter_all", None)),
            ("success", getattr(self, "btn_batch_filter_success", None)),
            ("failed", getattr(self, "btn_batch_filter_failed", None)),
        ]
        enable_filters = self.batch_stage in ("finished", "stopped") and bool(all_rows)
        for mode, button in buttons:
            if not button:
                continue
            button.setText(labels.get(mode, button.text()))
            button.setEnabled(enable_filters)
            button.setCursor(Qt.CursorShape.PointingHandCursor if enable_filters else Qt.CursorShape.ArrowCursor)
            button.setStyleSheet(self._get_batch_filter_button_style(active=self.batch_result_filter_mode == mode))

    def _set_batch_result_filter_mode(self, mode):
        """切换批量结果筛选模式。"""
        if mode not in {"all", "success", "failed"}:
            mode = "all"
        self.batch_result_filter_mode = mode
        self._refresh_batch_result_filter_buttons()
        self._populate_batch_result_table()

    def _populate_batch_result_table(self):
        """将本轮批量结果表格化展示。"""
        if not hasattr(self, "batch_result_table"):
            return

        table = self.batch_result_table
        all_rows = []
        if self.batch_stage in ("finished", "stopped"):
            all_rows = build_batch_result_rows(self.batch_last_summary)

        result_counts = summarize_batch_result_rows(all_rows)
        if hasattr(self, "lbl_batch_result_meta"):
            if self.batch_stage in ("finished", "stopped"):
                self.lbl_batch_result_meta.setText(
                    f"结果计数：共 {result_counts['total']} 条 · 成功 {result_counts['success']} · 失败 {result_counts['failed']}"
                )
            else:
                self.lbl_batch_result_meta.setText("结果计数：等待本轮结果")
        self._refresh_batch_result_filter_buttons()

        rows = filter_batch_result_rows(all_rows, self.batch_result_filter_mode)

        if not rows:
            placeholder_map = {
                "rule_setup": ("等待开始", "当前还在规则确认阶段", "开始执行后这里会列出每个文档的结果", "先确认规则"),
                "running": ("执行中", "系统正在批量处理文档", "本轮结束后这里会集中列出成功与失败明细", "处理中"),
                "finished": ("已完成", "当前没有可展示的结果行", "如果这轮没有生成结果，请检查日志和弹窗", "查看日志"),
                "stopped": ("已停止", "当前没有可展示的结果行", "可以重试失败文档，或者重新选择文件再执行", "查看日志"),
                "idle": ("待执行", "尚未进入批量模式", "选择多个 Word 文档后，这里会展示完整结果清单", "等待开始"),
            }
            if self.batch_stage in ("finished", "stopped") and all_rows:
                status, document, detail, action = (
                    "筛选为空",
                    "当前筛选条件下没有结果",
                    "你可以切回“全部”，或者改看成功 / 失败结果。",
                    "切换筛选",
                )
            else:
                status, document, detail, action = placeholder_map.get(self.batch_stage, placeholder_map["idle"])
            rows = [{
                "status": status,
                "status_key": "placeholder",
                "document": document,
                "detail": detail,
                "action": action,
                "open_path": "",
                "fallback_dir": "",
            }]

        table.clearContents()
        table.setRowCount(len(rows))

        status_colors = {
            "success": Theme.LIGHT["success"],
            "failed": Theme.LIGHT["danger"],
            "placeholder": Theme.LIGHT["text_secondary"],
        }
        status_backgrounds = {
            "success": "#EAF8F1",
            "failed": "#FDECEC",
            "placeholder": "#F4F7FB",
        }

        for row_index, row_data in enumerate(rows):
            status_item = QTableWidgetItem(row_data.get("status", ""))
            status_item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
            status_item.setForeground(QColor(status_colors.get(row_data.get("status_key"), Theme.LIGHT["text"])))
            status_item.setBackground(QColor(status_backgrounds.get(row_data.get("status_key"), "#FBFCFE")))
            status_font = status_item.font()
            status_font.setBold(True)
            status_item.setFont(status_font)
            status_item.setData(Qt.ItemDataRole.UserRole, row_data)

            document_item = QTableWidgetItem(row_data.get("document", ""))
            document_item.setToolTip(row_data.get("open_path", "") or row_data.get("document", ""))

            detail_item = QTableWidgetItem(row_data.get("detail", ""))
            detail_tooltip = row_data.get("detail", "")
            if row_data.get("open_path"):
                detail_tooltip = f"{detail_tooltip}\n{row_data.get('open_path')}"
            detail_item.setToolTip(detail_tooltip.strip())

            action_item = QTableWidgetItem(row_data.get("action", ""))
            action_item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))

            if row_data.get("status_key") == "placeholder":
                placeholder_flags = Qt.ItemFlag.ItemIsEnabled
                for item in [status_item, document_item, detail_item, action_item]:
                    item.setFlags(placeholder_flags)

            table.setItem(row_index, 0, status_item)
            table.setItem(row_index, 1, document_item)
            table.setItem(row_index, 2, detail_item)
            table.setItem(row_index, 3, action_item)

        table.resizeRowsToContents()

    def _open_batch_result_row(self, row, _column):
        """双击批量结果行：成功打开输出，失败定位源文档。"""
        if not hasattr(self, "batch_result_table"):
            return

        row_item = self.batch_result_table.item(row, 0)
        row_data = row_item.data(Qt.ItemDataRole.UserRole) if row_item else None
        if not isinstance(row_data, dict) or row_data.get("status_key") == "placeholder":
            return

        open_path = row_data.get("open_path", "")
        fallback_dir = row_data.get("fallback_dir", "")
        document_name = row_data.get("document", "所选文档")

        if open_path and os.path.exists(open_path):
            if QDesktopServices.openUrl(QUrl.fromLocalFile(open_path)):
                return
        if fallback_dir and os.path.isdir(fallback_dir):
            if QDesktopServices.openUrl(QUrl.fromLocalFile(fallback_dir)):
                return

        QMessageBox.warning(self, "提示", f"无法打开 {document_name} 对应的结果路径，请检查文件是否仍然存在。")

    def _refresh_batch_workspace(self):
        """刷新批量 Word 工作台文案。"""
        if not hasattr(self, "lbl_batch_title"):
            return

        stage_map = {
            "idle": ("批量 Word 工作台", "等待开始", Theme.LIGHT["secondary"], Theme.LIGHT["hover"]),
            "rule_setup": ("批量 Word 文档替换规则模式", "规则确认中", Theme.LIGHT["warning"], "#FFF3E6"),
            "running": ("批量 Word 替换执行模式", "执行中", Theme.LIGHT["primary"], "#E9F1FB"),
            "finished": ("批量 Word 替换结果", "已完成", Theme.LIGHT["success"], "#EAF8F1"),
            "stopped": ("批量 Word 替换结果", "已停止", Theme.LIGHT["danger"], "#FDECEC"),
        }
        title, badge_text, badge_fg, badge_bg = stage_map.get(
            self.batch_stage,
            stage_map["idle"],
        )

        self.lbl_batch_title.setText(title)
        self._set_status_badge_style(self.lbl_batch_stage_badge, badge_fg, badge_bg)
        self.lbl_batch_stage_badge.setText(badge_text)

        total_selected = self.batch_total_files or len(self.batch_selected_files)
        rule_count = self._count_enabled_word_rules()
        replacement_preview = self.replacement_text if isinstance(self.replacement_text, str) and self.replacement_text else "[已脱敏]"
        processed = min(self.batch_processed_files, total_selected) if total_selected else 0
        failed_inputs = self._get_batch_failed_inputs()
        success_outputs = self._get_batch_success_outputs()
        summary_parts = []

        if total_selected:
            summary_parts.append(f"已选文档 {total_selected} 个")
        if rule_count:
            summary_parts.append(f"启用规则 {rule_count} 条")
        summary_parts.append(f"统一替换文本：{replacement_preview}")

        if self.batch_stage == "rule_setup":
            subtitle = "先确认文档替换规则，再开始批量替换。这个阶段不会改动原文件。"
        elif self.batch_stage == "running":
            subtitle = "系统正在逐个处理文档。遇到问题时可以跳过当前文件，或者直接停止任务。"
        elif self.batch_stage in ("finished", "stopped"):
            subtitle = "这一轮批量任务已经结束。你可以查看结果摘要，也可以直接重新选择文件再跑一轮。"
            summary_parts.append(f"成功 {self.batch_success_count} 个")
            summary_parts.append(f"失败 {self.batch_failed_count} 个")
        else:
            subtitle = "批量模式会先进入规则确认，再进入执行。适合多个 Word 文档使用同一套替换规则。"

        self.lbl_batch_subtitle.setText(subtitle)
        self.lbl_batch_meta.setText(" · ".join(summary_parts))

        stage_index_map = {
            "idle": 0,
            "rule_setup": 0,
            "running": 1,
            "finished": 2,
            "stopped": 2,
        }
        active_index = stage_index_map.get(self.batch_stage, 0)
        active_fg = Theme.LIGHT["danger"] if self.batch_stage == "stopped" else None
        active_bg = "#FDECEC" if self.batch_stage == "stopped" else None
        if hasattr(self, "batch_stage_cards"):
            for index, (frame, title_label, note_label) in enumerate(self.batch_stage_cards):
                if index < active_index:
                    state = "done"
                elif index == active_index:
                    state = "active"
                else:
                    state = "pending"
                self._set_batch_step_style(frame, title_label, note_label, state, accent_fg=active_fg, accent_bg=active_bg)

        if hasattr(self, "lbl_batch_metric_files"):
            self.lbl_batch_metric_files.setText(f"{total_selected}" if total_selected else "--")
            self.lbl_batch_metric_files_note.setText("本轮已载入的 Word 文档数量")
        if hasattr(self, "lbl_batch_metric_rules"):
            self.lbl_batch_metric_rules.setText(f"{rule_count}" if rule_count else "--")
            self.lbl_batch_metric_rules_note.setText(f"统一替换文本：{replacement_preview}")
        if hasattr(self, "lbl_batch_metric_progress"):
            progress_value = f"{processed}/{total_selected}" if total_selected else "--"
            progress_note = "规则确认完成后开始执行"
            if self.batch_stage == "running":
                progress_note = f"成功 {self.batch_success_count} · 失败 {self.batch_failed_count}"
            elif self.batch_stage in ("finished", "stopped"):
                progress_note = f"{badge_text} · 全部文件已结束本轮处理"
            self.lbl_batch_metric_progress.setText(progress_value)
            self.lbl_batch_metric_progress_note.setText(progress_note)
        if hasattr(self, "lbl_batch_metric_result"):
            if self.batch_stage in ("finished", "stopped", "running"):
                result_value = f"{self.batch_success_count} / {self.batch_failed_count}"
                result_note = "成功 / 失败"
            else:
                result_value = "待执行"
                result_note = "开始后这里会汇总结果"
            self.lbl_batch_metric_result.setText(result_value)
            self.lbl_batch_metric_result_note.setText(result_note)

        if self.batch_current_file:
            self.lbl_batch_current_file.setText(f"当前文件：{self.batch_current_file}")
        elif total_selected:
            self.lbl_batch_current_file.setText("当前文件：等待开始处理")
        else:
            self.lbl_batch_current_file.setText("当前文件：尚未选择批量文档")

        if hasattr(self, "batch_summary_browser"):
            self.batch_summary_browser.setPlainText(self._build_batch_summary_text(total_selected, replacement_preview))
        if hasattr(self, "lbl_batch_result_hint"):
            if self.batch_stage in ("finished", "stopped"):
                self.lbl_batch_result_hint.setText("结果清单（双击成功行可打开输出，双击失败行可定位原文件）")
            elif self.batch_stage == "running":
                self.lbl_batch_result_hint.setText("结果清单（处理中，完成后这里会列出每个文档）")
            else:
                self.lbl_batch_result_hint.setText("结果清单")
        self._populate_batch_result_table()

        self.btn_batch_edit_rules.setEnabled(bool(self.batch_selected_files) and self.active_task_type != "batch_replace")
        self.btn_batch_pick_files.setEnabled(self.active_task_type != "batch_replace")
        show_result_actions = self.batch_stage in ("finished", "stopped")
        self.btn_batch_retry_failed.setVisible(show_result_actions)
        self.btn_batch_open_output.setVisible(show_result_actions)
        self.btn_batch_retry_failed.setEnabled(bool(failed_inputs) and self.active_task_type != "batch_replace")
        self.btn_batch_open_output.setEnabled(bool(success_outputs) and self.active_task_type != "batch_replace")

    def open_word_replace_rules(self):
        """打开 Word 多字段替换规则设置。"""
        if not self.word_doc:
            QMessageBox.information(self, "提示", "请先打开 Word 文档。")
            return

        dlg = WordReplaceRulesDialog(
            self,
            rules=self.word_replace_rules,
            default_replacement_text=self.replacement_text,
            title="Word 替换规则设置",
            apply_text="应用规则"
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self.word_replace_rules = dlg.rules
        self.replacement_text = dlg.default_replacement_text

        if not self._has_word_replacement_candidates():
            self.word_compare_user_hidden = False
            self._set_word_compare_mode(False)
            self.render_word_preview()
            QMessageBox.information(self, "提示", "当前无可预览的替换结果，已恢复单栏预览。")
            return

        self.render_word_preview()
        self._refresh_word_compare_toggle()
        self._refresh_workbench_context()
        self._set_info_bar_message("🧩 替换后预览已同步展示：规则替换 + 智能脱敏 + 手动脱敏")

    def _has_enabled_word_replace_rules(self):
        normalized = normalize_word_replace_rules(self.word_replace_rules, self.replacement_text)
        return any(item.get("enabled", True) and item.get("find") for item in normalized)

    def start_batch_replace(self, file_paths=None):
        """启动 Word 批量替换（支持 .docx + .doc）。"""
        if self.active_worker is not None and self.active_worker.isRunning():
            QMessageBox.warning(self, "提示", "当前有任务正在执行，请稍候。")
            return

        files = list(file_paths or [])
        if not files:
            app = QApplication.instance()
            original_style = app.styleSheet()
            app.setStyleSheet(self._get_file_dialog_style())
            try:
                files, _ = QFileDialog.getOpenFileNames(
                    self,
                    "选择要批量替换的 Word 文件",
                    "",
                    "Word 文档 (*.docx *.doc)"
                )
            finally:
                app.setStyleSheet(original_style)

        if not files:
            return

        self.batch_selected_files = list(files)
        self.batch_total_files = len(files)
        self.batch_processed_files = 0
        self.batch_success_count = 0
        self.batch_failed_count = 0
        self.batch_current_file = ""
        self.batch_last_summary = None
        self.batch_stage = "rule_setup"
        if hasattr(self, "batch_log_list"):
            self.batch_log_list.clear()
        self._append_batch_log(f"已载入 {len(files)} 个 Word 文档，等待确认批量替换规则。", "info")
        self._clear_info_bar_message()
        self._set_ui_mode("batch")
        rules_dlg = WordReplaceRulesDialog(
            self,
            rules=self.word_replace_rules,
            default_replacement_text=self.replacement_text,
            title="Word 批量替换规则设置",
            apply_text="开始批量替换"
        )
        if rules_dlg.exec() != QDialog.DialogCode.Accepted:
            self._clear_info_bar_message()
            self._reset_batch_session_state()
            self._sync_ui_mode()
            return

        self.word_replace_rules = rules_dlg.rules
        self.replacement_text = rules_dlg.default_replacement_text
        normalized_rules = normalize_word_replace_rules(self.word_replace_rules, self.replacement_text)
        if not any(item.get("enabled", True) and item.get("find") for item in normalized_rules):
            QMessageBox.warning(self, "提示", "请至少启用一条 Word 替换规则后再开始批量替换。")
            self.batch_stage = "rule_setup"
            self._append_batch_log("当前未启用任何规则，批量替换尚未开始。", "warning")
            self._set_ui_mode("batch")
            return

        self.progress.setValue(0)
        self.btn_cancel_scan.setVisible(True)
        self.btn_cancel_scan.setEnabled(True)
        self._set_info_bar_message(f"📚 批量替换准备中... 共 {len(files)} 个文件")
        self.batch_stage = "running"
        self._append_batch_log(
            f"开始执行批量替换：共 {len(files)} 个文件，启用 {self._count_enabled_word_rules()} 条规则。",
            "info"
        )

        self.batch_worker = WordBatchReplaceWorker(files, normalized_rules, self.replacement_text)
        self.active_worker = self.batch_worker
        self.active_task_type = "batch_replace"
        self._sync_ui_mode()

        self.batch_worker.progress_signal.connect(self._on_batch_replace_progress)
        self.batch_worker.file_done_signal.connect(self._on_batch_replace_file_done)
        self.batch_worker.file_error_signal.connect(self._on_batch_replace_file_error)
        self.batch_worker.finished_signal.connect(self._on_batch_replace_finished)
        self.batch_worker.start()

    def _on_batch_replace_progress(self, processed, total, current_file):
        percent = int(processed / total * 100) if total > 0 else 0
        self.batch_processed_files = processed
        self.batch_total_files = total
        self.batch_current_file = os.path.basename(current_file) if current_file else ""
        self.progress.setValue(percent)
        self._set_info_bar_message(f"📚 批量替换进行中: {processed}/{total} - {current_file}")
        self._refresh_workbench_context()

    def _on_batch_replace_file_done(self, input_path, output_path):
        self.batch_success_count += 1
        self.batch_current_file = os.path.basename(input_path)
        self._append_batch_log(
            f"已完成：{os.path.basename(input_path)} -> {os.path.basename(output_path)}",
            "success"
        )
        self._refresh_workbench_context()
        print(f"[BatchReplace] 完成: {input_path} -> {output_path}")

    def _on_batch_replace_file_error(self, index, input_path, error_msg):
        if not self.batch_worker:
            return

        self.batch_failed_count += 1
        self.batch_current_file = os.path.basename(input_path)
        self._append_batch_log(
            f"处理失败：{os.path.basename(input_path)} - {error_msg}",
            "error"
        )
        self._refresh_workbench_context()

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("批量替换出错")
        msg.setText(
            f"文件处理失败（{index + 1}）：\n{os.path.basename(input_path)}\n\n"
            f"错误：{error_msg}\n\n"
            "是否跳过该文件继续处理？"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Abort)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        yes_btn = msg.button(QMessageBox.StandardButton.Yes)
        abort_btn = msg.button(QMessageBox.StandardButton.Abort)
        if yes_btn:
            yes_btn.setText("跳过继续")
        if abort_btn:
            abort_btn.setText("停止任务")

        choice = msg.exec()
        decision = "skip" if choice == QMessageBox.StandardButton.Yes else "stop"
        if decision == "skip":
            self._append_batch_log(f"已跳过：{os.path.basename(input_path)}，继续处理后续文档。", "warning")
        else:
            self._append_batch_log("用户选择停止批量任务，正在安全结束当前流程。", "warning")
        self.batch_worker.provide_error_decision(decision)

    def _on_batch_replace_finished(self, summary):
        self.active_worker = None
        self.batch_worker = None
        self.active_task_type = None
        self.btn_cancel_scan.setVisible(False)
        self.btn_cancel_scan.setEnabled(True)
        self.progress.setValue(0)

        total = int(summary.get("total", 0))
        success = summary.get("success", [])
        failed = summary.get("failed", [])
        stopped = bool(summary.get("stopped", False))
        success_count = len(success)
        failed_count = len(failed)
        self.batch_total_files = total
        self.batch_processed_files = total
        self.batch_success_count = success_count
        self.batch_failed_count = failed_count
        self.batch_last_summary = summary
        self.batch_current_file = ""
        self.batch_stage = "stopped" if stopped else "finished"

        status_text = "已停止" if stopped else "已完成"
        self._set_info_bar_message(f"📚 批量替换{status_text}: 成功 {success_count} / 失败 {failed_count}")
        self._append_batch_log(
            f"批量替换{status_text}：成功 {success_count} 个，失败 {failed_count} 个。",
            "warning" if stopped else "success"
        )
        self._sync_ui_mode()

        lines = [
            f"批量替换{status_text}",
            f"总文件数: {total}",
            f"成功: {success_count}",
            f"失败: {failed_count}"
        ]

        if success:
            lines.append("")
            lines.append("成功输出（最多显示 10 条）:")
            for item in success[:10]:
                lines.append(f"- {item.get('output', '')}")
            if len(success) > 10:
                lines.append(f"... 其余 {len(success) - 10} 条已省略")

        if failed:
            lines.append("")
            lines.append("失败详情（最多显示 10 条）:")
            for item in failed[:10]:
                lines.append(f"- {os.path.basename(item.get('input', ''))}: {item.get('error', '')}")
            if len(failed) > 10:
                lines.append(f"... 其余 {len(failed) - 10} 条已省略")

        QMessageBox.information(self, "批量替换结果", "\n".join(lines))

    def _on_word_replaced_load_finished(self, ok):
        self._word_replaced_ready = bool(ok)
        self._word_replaced_loaded_source_path = self._word_replaced_target_source_path if ok else None
        if ok and self._pending_word_replaced_blocks:
            self._apply_word_panel_updates(self.word_preview_replaced, self._pending_word_replaced_blocks)
        if ok:
            self._configure_word_scroll_sync_panel(self.word_preview_replaced, "replaced")
            self._refresh_word_scroll_sync_timer()
            QTimer.singleShot(0, self._sync_word_compare_scroll_from_original)
