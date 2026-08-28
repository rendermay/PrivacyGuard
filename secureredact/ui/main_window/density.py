"""
Windows 密度适配 mixin — MainWindow 918 行超大密度计算方法 (PR-B2.6 迁出)

PR-B2.6 目标:MainWindow < 5000 行验收。
`_refresh_windows_density_metrics`(原 918 行)是 v1.1.x 跨工具栏 + 工作台 + 主界面的
密度指标计算核心,物理拆分到独立 mixin 模块(单方法 918 行),
main.py 中对应行数减少。

后续优化方向(本 PR 不做):
- 把 918 行方法拆为多个 helper 函数
- 用 mixin 协作替代直接 self 属性引用
- 引入 density_mode dataclass

依赖 MainWindow 上的属性(原方法大量 self.xxx 引用):
    - self.toolbar / self.toolbar_layout / self.toolbar_*_layout
    - self.workbench_layout / self.workbench_text_layout
    - self.idle_* / self.batch_* / self.merge_* / self.word_* widget 引用
    - self.theme / self.Theme
    - self._display_scale_factor / self._workflow_step_font_size
    - self.app_state / self.density_mode / self.current_ui_mode
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget,
)


class MainWindowDensityMixin:
    """Windows 全局密度指标计算 — 字号 / 间距 / margin / widget 高度。

    单方法 918 行(原 main.py 内完整搬迁,逐字未改)。
    """

    def _refresh_windows_density_metrics(self, density_mode):
        """按 Windows DPI 和当前工具栏密度收口高度、间距与命中区。"""
        if not hasattr(self, "toolbar") or not hasattr(self, "toolbar_layout"):
            return

        scale = self._get_display_scale_factor()
        theme = Theme.LIGHT

        if scale >= 1.5:
            toolbar_height = 68
            button_height = 40
            icon_size = 38
            side_margin = 12
            vertical_margin = 8
            spacing = 7
            workbench_h_margin = 16
            workbench_v_margin = 11
            title_font_size = 17
            subtitle_font_size = 12
            chip_font_size = 12
            meta_font_size = 12
            workflow_font_size = 12
            compare_header_height = 34
            compare_header_font_size = 12
            progress_height = 28
            cancel_width = 72
            batch_result_row_height = 48
        elif scale >= 1.25:
            toolbar_height = 64
            button_height = 38
            icon_size = 36
            side_margin = 14
            vertical_margin = 8
            spacing = 8
            workbench_h_margin = 17
            workbench_v_margin = 11
            title_font_size = 16
            subtitle_font_size = 12
            chip_font_size = 12
            meta_font_size = 12
            workflow_font_size = 11
            compare_header_height = 32
            compare_header_font_size = 12
            progress_height = 26
            cancel_width = 68
            batch_result_row_height = 44
        else:
            toolbar_height = 58
            button_height = 36
            icon_size = 32
            side_margin = 16
            vertical_margin = 7
            spacing = 10
            workbench_h_margin = 18
            workbench_v_margin = 12
            title_font_size = 16
            subtitle_font_size = 11
            chip_font_size = 11
            meta_font_size = 12
            workflow_font_size = 11
            compare_header_height = 30
            compare_header_font_size = 12
            progress_height = 24
            cancel_width = 60
            batch_result_row_height = 40

        current_mode = getattr(self, "current_ui_mode", "idle")

        logical_height = max(760, self.height())
        logical_width = max(1200, self.width())
        is_tall_workspace_window = logical_height >= 980
        is_short_workspace_window = logical_height <= 760
        is_very_wide_workspace_window = logical_width >= 1760
        is_ultra_wide_workspace_window = logical_width >= 2140
        is_cinema_wide_workspace_window = logical_width >= 2460
        is_workspace_mode = current_mode in {"pdf", "word", "batch", "image_merge"}

        if density_mode == "narrow":
            side_margin = max(10, side_margin - 2)
            spacing = max(6, spacing - 1)
            title_font_size = max(15, title_font_size - 1)
        elif density_mode == "compact":
            side_margin = max(11, side_margin - 1)
            spacing = max(7, spacing - 1)

        if scale >= 1.5:
            toolbar_height += 2
            button_height += 2
            progress_height += 2
            batch_result_row_height += 2
        elif scale >= 1.25:
            toolbar_height += 1
            button_height += 1

        if is_tall_workspace_window:
            toolbar_height += 2
            vertical_margin += 1
            spacing += 1
            title_font_size += 1
            subtitle_font_size += 1 if scale >= 1.25 else 0
        elif is_short_workspace_window:
            toolbar_height = max(56, toolbar_height - 2)
            button_height = max(34, button_height - 1)
            vertical_margin = max(6, vertical_margin - 1)
            spacing = max(6, spacing - 1)
            workbench_v_margin = max(10, workbench_v_margin - 1)

        is_pdf_like_mode = current_mode in {"pdf", "image_merge"}

        if current_mode == "idle":
            toolbar_height = max(42, toolbar_height - 10)
            vertical_margin = max(5, vertical_margin - 2)
            spacing = max(6, spacing - 1)
        elif is_pdf_like_mode:
            toolbar_height += 4
            vertical_margin += 1

        self._workflow_step_font_size = workflow_font_size
        self._status_badge_font_size = chip_font_size
        self._toolbar_meta_font_size = meta_font_size
        self._button_density_metrics = {
            "button_font_size": 14 if scale >= 1.5 else 13,
            "button_padding_v": 8 if scale >= 1.5 else 7,
            "button_padding_h": 15 if scale >= 1.5 else 14,
            "icon_font_size": 16 if scale >= 1.25 else 14,
            "icon_padding_v": 5 if scale >= 1.25 else 4,
            "icon_padding_h": 10 if scale >= 1.25 else 8,
            "icon_min": 34 if scale >= 1.5 else (32 if scale >= 1.25 else 28),
        }
        if density_mode == "narrow":
            self._button_density_metrics["button_padding_h"] = max(12, self._button_density_metrics["button_padding_h"] - 2)
        elif density_mode == "compact":
            self._button_density_metrics["button_padding_h"] = max(13, self._button_density_metrics["button_padding_h"] - 1)

        toolbar_bottom_margin = vertical_margin + (4 if is_pdf_like_mode else (2 if current_mode != "idle" else 1))
        toolbar_extra_height = 5 if is_pdf_like_mode else (2 if current_mode != "idle" else 0)
        self.toolbar.setFixedHeight(toolbar_height + toolbar_extra_height)
        self.toolbar_layout.setContentsMargins(side_margin, vertical_margin, side_margin, toolbar_bottom_margin)
        self.toolbar_layout.setSpacing(max(10, spacing + 1))

        group_spacing = max(4, spacing - 4)
        group_margin_h = 0
        group_margin_v = 2 if is_pdf_like_mode else 1
        utility_spacing = group_spacing
        for group_layout in [
            getattr(self, "toolbar_primary_layout", None),
            getattr(self, "toolbar_word_layout", None),
            getattr(self, "toolbar_pdf_layout", None),
            getattr(self, "toolbar_zoom_layout", None),
            getattr(self, "toolbar_nav_layout", None),
        ]:
            if group_layout:
                group_layout.setContentsMargins(group_margin_h, group_margin_v, group_margin_h, group_margin_v)
                group_layout.setSpacing(group_spacing)
        if hasattr(self, "toolbar_utility_layout"):
            self.toolbar_utility_layout.setContentsMargins(0, group_margin_v, 0, group_margin_v)
            self.toolbar_utility_layout.setSpacing(utility_spacing)

        if hasattr(self, "workbench_layout"):
            self.workbench_layout.setContentsMargins(workbench_h_margin, workbench_v_margin, workbench_h_margin, workbench_v_margin)
            self.workbench_layout.setSpacing(6 if density_mode == "wide" else 5)
        if hasattr(self, "context_top_layout"):
            self.context_top_layout.setSpacing(14 if density_mode == "wide" else 10)
        if hasattr(self, "workbench_text_layout"):
            self.workbench_text_layout.setSpacing(4 if density_mode == "wide" else 3)

        workspace_stage_margin = 14 if density_mode == "wide" else (10 if density_mode == "compact" else 8)
        workspace_stage_top_margin = 10 if density_mode == "wide" else (8 if density_mode == "compact" else 6)
        workspace_stage_bottom_margin = 16 if density_mode == "wide" else (14 if density_mode == "compact" else 10)
        preview_shell_padding = 8 if density_mode == "wide" else (6 if density_mode == "compact" else 5)
        preview_content_padding = 10 if density_mode == "wide" else (8 if density_mode == "compact" else 6)
        preview_content_spacing = 12 if density_mode == "wide" else (10 if density_mode == "compact" else 8)
        compare_header_gap = 10 if density_mode == "wide" else 8
        batch_card_padding_h = 28 if density_mode == "wide" else (24 if density_mode == "compact" else 20)
        batch_card_padding_v = 24 if density_mode == "wide" else (20 if density_mode == "compact" else 18)
        batch_detail_padding_h = 18 if density_mode == "wide" else (16 if density_mode == "compact" else 14)
        batch_detail_padding_v = 16 if density_mode == "wide" else (14 if density_mode == "compact" else 12)
        batch_section_gap = 14 if density_mode == "wide" else (12 if density_mode == "compact" else 10)
        batch_minor_gap = 10 if density_mode == "wide" else (8 if density_mode == "compact" else 6)
        if is_workspace_mode:
            workspace_stage_margin = max(4, workspace_stage_margin - 6)
            workspace_stage_bottom_margin = max(8, workspace_stage_bottom_margin - 2)
        if is_very_wide_workspace_window:
            workspace_stage_margin = max(2, workspace_stage_margin - 2)
            batch_card_padding_h = max(20, batch_card_padding_h - 2)
            batch_detail_padding_h = max(14, batch_detail_padding_h - 1)
        if is_ultra_wide_workspace_window:
            workspace_stage_margin = max(2, workspace_stage_margin - 2)
            preview_shell_padding = max(3, preview_shell_padding - 1)
            preview_content_padding = max(4, preview_content_padding - 1)
            batch_card_padding_h = max(18, batch_card_padding_h - 2)
            batch_section_gap = max(10, batch_section_gap - 1)
        if is_cinema_wide_workspace_window:
            workspace_stage_margin = max(1, workspace_stage_margin - 1)
            preview_shell_padding = max(3, preview_shell_padding - 1)
            preview_content_padding = max(4, preview_content_padding - 1)
            batch_card_padding_h = max(16, batch_card_padding_h - 2)
            batch_detail_padding_h = max(12, batch_detail_padding_h - 1)
            batch_section_gap = max(9, batch_section_gap - 1)
        if is_workspace_mode and is_very_wide_workspace_window:
            workbench_h_margin = max(14, workbench_h_margin - 2)
        if is_workspace_mode and is_ultra_wide_workspace_window:
            workbench_h_margin = max(12, workbench_h_margin - 2)
        if is_workspace_mode and is_cinema_wide_workspace_window:
            workbench_h_margin = max(10, workbench_h_margin - 2)
        if getattr(self, "current_ui_mode", "idle") in {"pdf", "word"}:
            workspace_stage_top_margin = max(4, workspace_stage_top_margin - 2)
            preview_shell_padding = max(4, preview_shell_padding - 1)
            preview_content_padding = max(5, preview_content_padding - 2)
        if getattr(self, "current_ui_mode", "idle") == "pdf":
            workspace_stage_top_margin = max(3, workspace_stage_top_margin - 1)
            preview_shell_padding = max(3, preview_shell_padding - 1)
            preview_content_padding = max(4, preview_content_padding - 1)
        if is_tall_workspace_window and getattr(self, "current_ui_mode", "idle") in {"pdf", "word"}:
            workspace_stage_top_margin = max(2, workspace_stage_top_margin - 1)
            workspace_stage_bottom_margin = max(6, workspace_stage_bottom_margin - 2)
            preview_shell_padding = max(3, preview_shell_padding - 1)
            preview_content_padding = max(4, preview_content_padding - 1)
            preview_content_spacing = max(8, preview_content_spacing - 1)
        if is_tall_workspace_window and getattr(self, "current_ui_mode", "idle") == "batch":
            workspace_stage_top_margin = max(4, workspace_stage_top_margin - 1)
            workspace_stage_bottom_margin = max(8, workspace_stage_bottom_margin - 2)
            batch_card_padding_v = max(18, batch_card_padding_v - 2)
            batch_section_gap = max(10, batch_section_gap - 2)
        preview_top_padding = max(4, preview_content_padding - 1)
        if hasattr(self, "pdf_workspace_outer_layout"):
            self.pdf_workspace_outer_layout.setContentsMargins(
                workspace_stage_margin,
                workspace_stage_top_margin,
                workspace_stage_margin,
                workspace_stage_bottom_margin,
            )
        if hasattr(self, "word_compare_outer_layout"):
            self.word_compare_outer_layout.setContentsMargins(
                workspace_stage_margin,
                workspace_stage_top_margin,
                workspace_stage_margin,
                workspace_stage_bottom_margin,
            )
        if hasattr(self, "batch_outer_layout"):
            self.batch_outer_layout.setContentsMargins(
                workspace_stage_margin,
                workspace_stage_top_margin,
                workspace_stage_margin,
                workspace_stage_bottom_margin,
            )
        if hasattr(self, "merge_outer_layout"):
            self.merge_outer_layout.setContentsMargins(
                workspace_stage_margin,
                workspace_stage_top_margin,
                workspace_stage_margin,
                workspace_stage_bottom_margin,
            )
        preview_shell_cap = 2560 if density_mode == "wide" else (2240 if density_mode == "compact" else 1680)
        preview_shell_min = 1040
        if getattr(self, "current_ui_mode", "idle") == "word" and getattr(self, "word_compare_mode", False):
            preview_shell_cap = 2580 if density_mode == "wide" else (2260 if density_mode == "compact" else 1760)
            preview_shell_min = 1420 if density_mode == "wide" else (1220 if density_mode == "compact" else 980)
        elif getattr(self, "current_ui_mode", "idle") == "word" and not getattr(self, "word_compare_mode", False):
            preview_shell_cap = 2580 if density_mode == "wide" else (2220 if density_mode == "compact" else 1700)
            preview_shell_min = 1360 if density_mode == "wide" else (1160 if density_mode == "compact" else 940)
        elif getattr(self, "current_ui_mode", "idle") == "pdf":
            preview_shell_cap = 2600 if density_mode == "wide" else (2280 if density_mode == "compact" else 1760)
        if is_ultra_wide_workspace_window:
            preview_shell_cap += 140
        elif is_very_wide_workspace_window:
            preview_shell_cap += 80
        if is_cinema_wide_workspace_window:
            preview_shell_cap += 220
        preview_shell_width = min(
            preview_shell_cap,
            max(preview_shell_min, logical_width - (workspace_stage_margin * 2) - 8),
        )
        workspace_card_width = min(
            2280 if density_mode == "wide" else (1980 if density_mode == "compact" else 1500),
            max(1040, logical_width - (workspace_stage_margin * 2) - 16),
        )
        if is_ultra_wide_workspace_window:
            workspace_card_width = min(workspace_card_width + 140, logical_width - (workspace_stage_margin * 2) - 8)
        elif is_very_wide_workspace_window:
            workspace_card_width = min(workspace_card_width + 80, logical_width - (workspace_stage_margin * 2) - 8)
        if is_cinema_wide_workspace_window:
            workspace_card_width = min(workspace_card_width + 220, logical_width - (workspace_stage_margin * 2) - 8)
        if hasattr(self, "pdf_workspace_shell"):
            self.pdf_workspace_shell.setMaximumWidth(preview_shell_width)
        if hasattr(self, "pdf_workspace_row_layout"):
            center_stretch = 28 if density_mode == "wide" else (22 if density_mode == "compact" else 16)
            if is_very_wide_workspace_window:
                center_stretch += 4
            if is_ultra_wide_workspace_window:
                center_stretch += 2
            if is_cinema_wide_workspace_window:
                center_stretch += 4
            side_stretch = 0 if is_ultra_wide_workspace_window else 1
            self.pdf_workspace_row_layout.setStretch(0, side_stretch)
            self.pdf_workspace_row_layout.setStretch(1, center_stretch)
            self.pdf_workspace_row_layout.setStretch(2, side_stretch)
        if hasattr(self, "pdf_workspace_shell_layout"):
            self.pdf_workspace_shell_layout.setContentsMargins(
                preview_shell_padding,
                preview_shell_padding,
                preview_shell_padding,
                preview_shell_padding,
            )
        if hasattr(self, "word_workspace_shell"):
            self.word_workspace_shell.setMaximumWidth(preview_shell_width)
        if hasattr(self, "word_workspace_row_layout"):
            center_stretch = 28 if density_mode == "wide" else (22 if density_mode == "compact" else 16)
            if is_very_wide_workspace_window:
                center_stretch += 4
            if is_ultra_wide_workspace_window:
                center_stretch += 2
            if is_cinema_wide_workspace_window:
                center_stretch += 4
            side_stretch = 0 if is_ultra_wide_workspace_window else 1
            self.word_workspace_row_layout.setStretch(0, side_stretch)
            self.word_workspace_row_layout.setStretch(1, center_stretch)
            self.word_workspace_row_layout.setStretch(2, side_stretch)
        if hasattr(self, "word_workspace_shell_layout"):
            self.word_workspace_shell_layout.setContentsMargins(
                preview_shell_padding,
                preview_shell_padding,
                preview_shell_padding,
                preview_shell_padding,
            )
            self.word_workspace_shell_layout.setSpacing(max(4, batch_minor_gap - 3))
        if hasattr(self, "batch_card"):
            self.batch_card.setMaximumWidth(workspace_card_width)
            self.batch_card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding if is_tall_workspace_window else QSizePolicy.Policy.Maximum,
            )
        if hasattr(self, "batch_card_row_layout"):
            center_stretch = 18 if density_mode == "wide" else (14 if density_mode == "compact" else 10)
            if is_very_wide_workspace_window:
                center_stretch += 3
            if is_ultra_wide_workspace_window:
                center_stretch += 1
            if is_cinema_wide_workspace_window:
                center_stretch += 3
            side_stretch = 0 if is_ultra_wide_workspace_window else 1
            self.batch_card_row_layout.setStretch(0, side_stretch)
            self.batch_card_row_layout.setStretch(1, center_stretch)
            self.batch_card_row_layout.setStretch(2, side_stretch)
        if hasattr(self, "batch_card_layout"):
            self.batch_card_layout.setContentsMargins(
                batch_card_padding_h,
                batch_card_padding_v,
                batch_card_padding_h,
                batch_card_padding_v,
            )
            self.batch_card_layout.setSpacing(batch_section_gap)
        batch_left_rail_width = 380 if density_mode == "wide" else (350 if density_mode == "compact" else 16777215)
        if is_cinema_wide_workspace_window and batch_left_rail_width < 16777215:
            batch_left_rail_width = max(340, batch_left_rail_width - 20)
        if hasattr(self, "batch_summary_section"):
            self.batch_summary_section.setMaximumWidth(batch_left_rail_width)
            self.batch_summary_section.setMinimumWidth(0 if density_mode == "narrow" else max(280, batch_left_rail_width - 70))
        if hasattr(self, "batch_log_section"):
            self.batch_log_section.setMaximumWidth(batch_left_rail_width)
            self.batch_log_section.setMinimumWidth(0 if density_mode == "narrow" else max(280, batch_left_rail_width - 70))
        if hasattr(self, "batch_result_section"):
            self.batch_result_section.setMaximumWidth(16777215)
            batch_result_min_width = 0 if density_mode == "narrow" else (840 if density_mode == "wide" else 700)
            if is_cinema_wide_workspace_window and batch_result_min_width:
                batch_result_min_width += 140
            self.batch_result_section.setMinimumWidth(batch_result_min_width)
        if hasattr(self, "merge_card"):
            self.merge_card.setMaximumWidth(workspace_card_width)
            self.merge_card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding if is_tall_workspace_window else QSizePolicy.Policy.Maximum,
            )
        if hasattr(self, "merge_card_layout"):
            self.merge_card_layout.setContentsMargins(
                batch_card_padding_h,
                batch_card_padding_v,
                batch_card_padding_h,
                batch_card_padding_v,
            )
            self.merge_card_layout.setSpacing(batch_section_gap)
        if hasattr(self, "merge_card_row_layout"):
            center_stretch = 14 if density_mode == "wide" else (12 if density_mode == "compact" else 8)
            if is_very_wide_workspace_window:
                center_stretch += 2
            if is_ultra_wide_workspace_window:
                center_stretch += 1
            if is_cinema_wide_workspace_window:
                center_stretch += 3
            side_stretch = 0 if is_ultra_wide_workspace_window else 1
            self.merge_card_row_layout.setStretch(0, side_stretch)
            self.merge_card_row_layout.setStretch(1, center_stretch)
            self.merge_card_row_layout.setStretch(2, side_stretch)
        if hasattr(self, "idle_outer_layout"):
            idle_side_margin = max(14, side_margin + (6 if is_very_wide_workspace_window else 8))
            if is_ultra_wide_workspace_window:
                idle_side_margin = max(12, idle_side_margin - 2)
            self.idle_outer_layout.setContentsMargins(idle_side_margin, 14, idle_side_margin, 26)
        if hasattr(self, "idle_card_layout"):
            idle_card_margin = 28 if density_mode == "wide" else (24 if density_mode == "compact" else 20)
            self.idle_card_layout.setContentsMargins(idle_card_margin, idle_card_margin - 4, idle_card_margin, idle_card_margin - 6)
            self.idle_card_layout.setSpacing(14 if density_mode == "wide" else 11)
        if hasattr(self, "idle_card"):
            idle_card_width = min(
                workspace_card_width,
                1980 if density_mode == "wide" else (1680 if density_mode == "compact" else 1180),
            )
            if is_cinema_wide_workspace_window:
                idle_card_width = min(idle_card_width + 180, workspace_card_width)
            self.idle_card.setMaximumWidth(idle_card_width)
        if hasattr(self, "idle_hero_panel"):
            self.idle_hero_panel.setMaximumWidth(16777215)
        if hasattr(self, "idle_hero_layout"):
            self.idle_hero_layout.setSpacing(12 if density_mode == "wide" else 10)
        if hasattr(self, "idle_flow_panel"):
            self.idle_flow_panel.setMaximumWidth(16777215)
        if hasattr(self, "idle_section_panel"):
            self.idle_section_panel.setMaximumWidth(16777215)
        if hasattr(self, "idle_section_layout"):
            self.idle_section_layout.setSpacing(10 if density_mode == "wide" else 8)
        if hasattr(self, "idle_action_panel_layout"):
            self.idle_action_panel_layout.setContentsMargins(0, 2, 0, 2)
            self.idle_action_panel_layout.setSpacing(10 if density_mode == "wide" else 8)
        if hasattr(self, "idle_title_row_layout"):
            self.idle_title_row_layout.setSpacing(18 if density_mode == "wide" else 12)
        if hasattr(self, "idle_title_tools_layout"):
            self.idle_title_tools_layout.setSpacing(8 if density_mode == "wide" else 6)
        if hasattr(self, "idle_badge_row_layout"):
            self.idle_badge_row_layout.setSpacing(8 if density_mode == "wide" else 6)
        if hasattr(self, "idle_utility_row_layout"):
            self.idle_utility_row_layout.setSpacing(8 if density_mode == "wide" else 6)
        if hasattr(self, "idle_action_buttons_layout"):
            self.idle_action_buttons_layout.setHorizontalSpacing(16 if density_mode == "wide" else 12)
            self.idle_action_buttons_layout.setVerticalSpacing(10 if density_mode == "narrow" else 0)
        if hasattr(self, "idle_flow_layout"):
            self.idle_flow_layout.setContentsMargins(0, 2, 0, 0)
            self.idle_flow_layout.setSpacing(12 if density_mode == "wide" else 9)
        if hasattr(self, "idle_routes_layout"):
            self.idle_routes_layout.setHorizontalSpacing(16 if density_mode == "wide" else 12)
            self.idle_routes_layout.setVerticalSpacing(12 if density_mode == "wide" else 10)
        self._rebuild_idle_action_layout(density_mode)
        self._rebuild_idle_route_layout(density_mode)
        self._rebuild_batch_stage_layout(density_mode)
        self._rebuild_batch_metrics_layout(density_mode)
        self._rebuild_batch_action_layout(density_mode)
        self._rebuild_batch_detail_layout(density_mode)
        self._rebuild_merge_stage_layout(density_mode)
        self._rebuild_merge_metrics_layout(density_mode)
        for route_card in getattr(self, "idle_route_cards", []):
            route_card_height = 126 if density_mode == "wide" else (114 if density_mode == "compact" else 102)
            route_card.setMinimumHeight(route_card_height)
            route_card.setMaximumHeight(route_card_height + 18)
        if hasattr(self, "canvas_layout"):
            self.canvas_layout.setContentsMargins(
                preview_content_padding,
                preview_top_padding,
                preview_content_padding,
                preview_content_padding,
            )
            self.canvas_layout.setSpacing(preview_content_spacing)
        if hasattr(self, "word_compare_layout"):
            self.word_compare_layout.setContentsMargins(0, 0, 0, 0)
            self.word_compare_layout.setSpacing(max(4, preview_content_spacing - 5))
        if hasattr(self, "word_compare_header"):
            self.word_compare_header.setFixedHeight(compare_header_height)
        if hasattr(self, "word_header_layout"):
            self.word_header_layout.setSpacing(compare_header_gap)
            self.word_header_layout.setContentsMargins(0, 0, 0, 1)
        if hasattr(self, "original_panel_layout"):
            self.original_panel_layout.setContentsMargins(0, 0, 0, 0)
        if hasattr(self, "replaced_panel_layout"):
            self.replaced_panel_layout.setContentsMargins(0, 0, 0, 0)
        if hasattr(self, "batch_header_layout"):
            self.batch_header_layout.setContentsMargins(0, 0, 0, 2)
            self.batch_header_layout.setSpacing(batch_section_gap - 2)
        if hasattr(self, "batch_header_text_layout"):
            self.batch_header_text_layout.setSpacing(max(3, batch_minor_gap - 4))
        if hasattr(self, "batch_stage_layout"):
            self.batch_stage_layout.setContentsMargins(0, 0, 0, 0)
            self.batch_stage_layout.setHorizontalSpacing(batch_minor_gap + 2)
            self.batch_stage_layout.setVerticalSpacing(batch_minor_gap + 2)
        if hasattr(self, "batch_metrics_layout"):
            self.batch_metrics_layout.setContentsMargins(0, 0, 0, 0)
            self.batch_metrics_layout.setHorizontalSpacing(batch_minor_gap)
            self.batch_metrics_layout.setVerticalSpacing(batch_minor_gap)
        if hasattr(self, "merge_header_layout"):
            self.merge_header_layout.setContentsMargins(0, 0, 0, 2)
            self.merge_header_layout.setSpacing(batch_section_gap - 2)
        if hasattr(self, "merge_header_text_layout"):
            self.merge_header_text_layout.setSpacing(max(3, batch_minor_gap - 4))
        if hasattr(self, "merge_stage_layout"):
            self.merge_stage_layout.setContentsMargins(0, 0, 0, 0)
            self.merge_stage_layout.setHorizontalSpacing(batch_minor_gap + 2)
            self.merge_stage_layout.setVerticalSpacing(batch_minor_gap + 2)
        if hasattr(self, "merge_metrics_layout"):
            self.merge_metrics_layout.setContentsMargins(0, 0, 0, 0)
            self.merge_metrics_layout.setHorizontalSpacing(batch_minor_gap)
            self.merge_metrics_layout.setVerticalSpacing(batch_minor_gap)
        if hasattr(self, "batch_actions_layout"):
            self.batch_actions_layout.setContentsMargins(0, 2, 0, 0)
            self.batch_actions_layout.setHorizontalSpacing(batch_minor_gap)
            self.batch_actions_layout.setVerticalSpacing(batch_minor_gap)
        if hasattr(self, "batch_summary_section_layout"):
            self.batch_summary_section_layout.setContentsMargins(
                batch_detail_padding_h,
                batch_detail_padding_v,
                batch_detail_padding_h,
                batch_detail_padding_v,
            )
            self.batch_summary_section_layout.setSpacing(batch_minor_gap)
        if hasattr(self, "batch_result_section_layout"):
            self.batch_result_section_layout.setContentsMargins(
                batch_detail_padding_h,
                batch_detail_padding_v,
                batch_detail_padding_h,
                batch_detail_padding_v,
            )
            self.batch_result_section_layout.setSpacing(batch_minor_gap)
        if hasattr(self, "batch_log_section_layout"):
            self.batch_log_section_layout.setContentsMargins(
                batch_detail_padding_h,
                batch_detail_padding_v,
                batch_detail_padding_h,
                batch_detail_padding_v,
            )
            self.batch_log_section_layout.setSpacing(batch_minor_gap)
        if hasattr(self, "batch_result_toolbar"):
            self.batch_result_toolbar.setSpacing(max(6, batch_minor_gap - 1))
            self.batch_result_toolbar.setContentsMargins(0, 1, 0, 2)
            self.batch_result_toolbar.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        if hasattr(self, "batch_result_header_layout"):
            self.batch_result_header_layout.setContentsMargins(0, 0, 0, 0)
            self.batch_result_header_layout.setSpacing(batch_minor_gap + 4)
        if hasattr(self, "batch_summary_browser"):
            self.batch_summary_browser.setMinimumHeight(118 if density_mode == "wide" else (110 if density_mode == "compact" else 104))
            summary_max_height = 172 if density_mode == "wide" else (164 if density_mode == "compact" else 154)
            if is_tall_workspace_window:
                summary_max_height += 16
            self.batch_summary_browser.setMaximumHeight(summary_max_height)
        if hasattr(self, "batch_result_table"):
            result_min_height = 300 if density_mode == "wide" else (250 if density_mode == "compact" else 196)
            if is_tall_workspace_window:
                result_min_height += 40 if density_mode == "wide" else 28
            self.batch_result_table.setMinimumHeight(result_min_height)
            self.batch_result_table.setMaximumHeight(16777215)
            self.batch_result_table.setColumnWidth(0, 88 if density_mode == "wide" else (82 if density_mode == "compact" else 76))
            self.batch_result_table.setColumnWidth(3, 104 if density_mode == "wide" else (96 if density_mode == "compact" else 88))
        if hasattr(self, "batch_log_list"):
            log_min_height = 184 if density_mode == "wide" else (172 if density_mode == "compact" else 156)
            if is_tall_workspace_window:
                log_min_height += 24 if density_mode == "wide" else 18
            self.batch_log_list.setMinimumHeight(log_min_height)
            self.batch_log_list.setMaximumHeight(16777215)
        merge_metric_min_height = 108 if density_mode == "wide" else (100 if density_mode == "compact" else 94)
        for merge_card in getattr(self, "merge_metric_cards", []):
            if merge_card:
                merge_card.setMinimumHeight(merge_metric_min_height)
                merge_card.setMaximumHeight(16777215)

        icon_button_size = button_height
        for icon_btn in [
            getattr(self, "btn_zoom_out", None),
            getattr(self, "btn_zoom_in", None),
            getattr(self, "btn_go_first", None),
            getattr(self, "btn_prev_page", None),
            getattr(self, "btn_next_page", None),
            getattr(self, "btn_go_last", None),
        ]:
            if icon_btn:
                icon_btn.setFixedSize(icon_button_size, icon_button_size)
                icon_btn.setIconSize(QSize(max(14, icon_button_size - 14), max(14, icon_button_size - 14)))

        control_height = button_height
        group_height = control_height + (7 if is_pdf_like_mode else 4)
        for button in [
            getattr(self, "btn_open", None),
            getattr(self, "btn_scan", None),
            getattr(self, "btn_idle_open", None),
            getattr(self, "btn_idle_feedback", None),
            getattr(self, "btn_idle_manual", None),
            getattr(self, "btn_idle_donate", None),
            getattr(self, "btn_compare_toggle", None),
            getattr(self, "rb_black", None),
            getattr(self, "rb_white", None),
            getattr(self, "cb_dual", None),
            getattr(self, "btn_fit", None),
            getattr(self, "btn_fit_utility", None),
            getattr(self, "btn_settings", None),
            getattr(self, "btn_feedback", None),
            getattr(self, "btn_workbench_feedback", None),
            getattr(self, "btn_more", None),
            getattr(self, "btn_save", None),
        ]:
            if button:
                button.setMinimumHeight(control_height)
                button.setMaximumHeight(control_height)

        for label in [
            getattr(self, "lbl_zoom", None),
            getattr(self, "lbl_page", None),
        ]:
            if label:
                label.setMinimumHeight(control_height)
                label.setMaximumHeight(control_height)

        for group in [
            getattr(self, "toolbar_primary_group", None),
            getattr(self, "toolbar_word_group", None),
            getattr(self, "toolbar_pdf_group", None),
            getattr(self, "toolbar_zoom_group", None),
            getattr(self, "toolbar_nav_group", None),
            getattr(self, "toolbar_utility_group", None),
        ]:
            if group:
                group.setMinimumHeight(group_height)
                group.setMaximumHeight(group_height)

        idle_action_width = 220 if density_mode == "wide" else (190 if density_mode == "compact" else 160)
        if hasattr(self, "btn_idle_open"):
            idle_primary_height = control_height + 4
            self.btn_idle_open.setMinimumWidth(idle_action_width)
            self.btn_idle_open.setMaximumWidth(16777215 if density_mode != "narrow" else idle_action_width)
            self.btn_idle_open.setMinimumHeight(idle_primary_height)
            self.btn_idle_open.setMaximumHeight(idle_primary_height)
        if hasattr(self, "idle_start_card"):
            start_min_height = idle_primary_height + (78 if density_mode == "wide" else (72 if density_mode == "compact" else 84))
            self.idle_start_card.setMinimumHeight(start_min_height)
            self.idle_start_card.setMaximumHeight(16777215)
        if hasattr(self, "idle_start_footer_layout"):
            self.idle_start_footer_layout.setSpacing(8 if density_mode == "wide" else 6)
        if hasattr(self, "btn_idle_feedback"):
            idle_secondary_height = control_height + 4
            idle_support_action_width = 120 if density_mode == "wide" else (108 if density_mode == "compact" else 100)
            self.btn_idle_feedback.setMinimumWidth(idle_support_action_width)
            self.btn_idle_feedback.setMaximumWidth(16777215 if density_mode != "narrow" else idle_action_width)
            self.btn_idle_feedback.setMinimumHeight(idle_secondary_height)
            self.btn_idle_feedback.setMaximumHeight(idle_secondary_height)
        for button in [getattr(self, "btn_idle_manual", None), getattr(self, "btn_idle_donate", None)]:
            if button:
                idle_secondary_height = control_height + 4
                idle_support_action_width = 120 if density_mode == "wide" else (108 if density_mode == "compact" else 100)
                button.setMinimumWidth(idle_support_action_width)
                button.setMaximumWidth(16777215 if density_mode != "narrow" else idle_action_width)
                button.setMinimumHeight(idle_secondary_height)
                button.setMaximumHeight(idle_secondary_height)
        if hasattr(self, "idle_support_card"):
            support_min_height = idle_primary_height + (92 if density_mode == "wide" else (88 if density_mode == "compact" else 108))
            self.idle_support_card.setMinimumHeight(support_min_height)
            self.idle_support_card.setMaximumHeight(16777215)

        for label in [getattr(self, "lbl_zoom", None), getattr(self, "lbl_page", None)]:
            if label:
                label.setMinimumHeight(control_height)
                label.setMaximumHeight(control_height)
                label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                label.setStyleSheet(
                    f"""
                    QLabel#toolbarMeta {{
                        color: {theme["text"]};
                        background-color: {theme["hover"]};
                        border: 1px solid {theme["border"]};
                        border-radius: 9px;
                        padding: 4px 10px;
                        font-size: {meta_font_size}px;
                        font-weight: 700;
                        min-width: 54px;
                    }}
                    """
                )
        if hasattr(self, "lbl_batch_result_meta"):
            self.lbl_batch_result_meta.setMinimumHeight(max(28, control_height - 4))
            self.lbl_batch_result_meta.setMaximumHeight(max(28, control_height - 4))
        if hasattr(self, "lbl_batch_result_hint"):
            self.lbl_batch_result_hint.setMinimumHeight(max(28, control_height - 4))
            self.lbl_batch_result_hint.setMaximumHeight(max(28, control_height - 4))
        batch_filter_height = max(30, control_height - 4)
        for button in [
            getattr(self, "btn_batch_filter_all", None),
            getattr(self, "btn_batch_filter_success", None),
            getattr(self, "btn_batch_filter_failed", None),
        ]:
            if button:
                button.setMinimumHeight(batch_filter_height)
                button.setMaximumHeight(batch_filter_height)
                button.setMinimumWidth(86 if density_mode == "wide" else (78 if density_mode == "compact" else 72))
        batch_filter_height = max(28, control_height - 4)
        batch_filter_width = 96 if density_mode == "wide" else (88 if density_mode == "compact" else 80)
        for button in [
            getattr(self, "btn_batch_filter_all", None),
            getattr(self, "btn_batch_filter_success", None),
            getattr(self, "btn_batch_filter_failed", None),
        ]:
            if button:
                button.setMinimumHeight(batch_filter_height)
                button.setMaximumHeight(batch_filter_height)
                button.setMinimumWidth(batch_filter_width)
        batch_action_width = 168 if density_mode == "wide" else (154 if density_mode == "compact" else 140)
        for button in getattr(self, "batch_action_buttons", []):
            if button:
                button.setMinimumWidth(batch_action_width)

        if hasattr(self, "lbl_workbench_title"):
            self.lbl_workbench_title.setStyleSheet(
                f"color: {theme['text']}; font-size: {title_font_size}px; font-weight: 700; background-color: transparent;"
            )
        for label in [getattr(self, "lbl_batch_title", None), getattr(self, "lbl_merge_title", None)]:
            if label:
                label.setStyleSheet(
                    f"color: {theme['text']}; font-size: {title_font_size + 3}px; font-weight: 700; background-color: transparent;"
                )
        for label in [
            getattr(self, "lbl_workbench_subtitle", None),
            getattr(self, "lbl_batch_subtitle", None),
            getattr(self, "lbl_merge_subtitle", None),
        ]:
            if label:
                label.setStyleSheet(
                    f"color: {theme['text_secondary']}; font-size: {subtitle_font_size}px; line-height: 1.7; background-color: transparent;"
                )
        for label in [
            getattr(self, "lbl_batch_meta", None),
            getattr(self, "lbl_batch_current_file", None),
            getattr(self, "lbl_merge_meta", None),
            getattr(self, "lbl_idle_tip", None),
            getattr(self, "lbl_idle_drop_hint", None),
        ]:
            if label:
                label.setStyleSheet(
                    f"color: {theme['text_secondary'] if label in (getattr(self, 'lbl_idle_tip', None), getattr(self, 'lbl_idle_drop_hint', None)) else theme['text']}; font-size: {subtitle_font_size}px; line-height: 1.7; background-color: transparent;"
                )
        if hasattr(self, "lbl_idle_section"):
            self.lbl_idle_section.setStyleSheet(
                f"color: {theme['text']}; font-size: {max(12, title_font_size - 1)}px; font-weight: 700; background-color: transparent;"
            )
        if hasattr(self, "lbl_idle_section_hint"):
            self.lbl_idle_section_hint.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {max(10, subtitle_font_size - 1)}px; font-weight: 600; background-color: transparent;"
            )
        for label in [getattr(self, "lbl_idle_offline_badge", None), getattr(self, "lbl_idle_auto_badge", None)]:
            if label:
                label.setStyleSheet(
                    f"color: {theme['primary']}; background-color: #E9F1FB; border: 1px solid {theme['border']}; border-radius: 9px; padding: 4px 9px; font-size: {max(10, subtitle_font_size - 1)}px; font-weight: 700;"
                )
        if hasattr(self, "lbl_idle_section_hint"):
            self.lbl_idle_section_hint.setVisible(density_mode != "narrow")
        if hasattr(self, "lbl_idle_auto_badge"):
            self.lbl_idle_auto_badge.setVisible(density_mode == "wide")
        if hasattr(self, "lbl_idle_drop_hint"):
            self.lbl_idle_drop_hint.setText(
                "支持直接拖拽到窗口，系统会自动分流" if density_mode == "wide"
                else ("支持直接拖拽到窗口" if density_mode == "compact" else "支持拖拽到窗口")
            )
        if hasattr(self, "lbl_idle_start_title"):
            self.lbl_idle_start_title.setStyleSheet(
                f"color: {theme['text']}; font-size: {max(12, title_font_size - 1)}px; font-weight: 700; background-color: transparent;"
            )
        if hasattr(self, "lbl_idle_start_text"):
            self.lbl_idle_start_text.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {max(10, subtitle_font_size - 1)}px; line-height: 1.6; background-color: transparent;"
            )
        if hasattr(self, "lbl_idle_support_text"):
            self.lbl_idle_support_text.setStyleSheet(
                f"color: {theme['text']}; font-size: {max(11, subtitle_font_size)}px; font-weight: 600; line-height: 1.5; background-color: transparent;"
            )
        if hasattr(self, "lbl_idle_support_meta"):
            self.lbl_idle_support_meta.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {max(10, subtitle_font_size - 1)}px; font-weight: 600; line-height: 1.5; background-color: transparent;"
            )
        if hasattr(self, "lbl_idle_support_email"):
            self.lbl_idle_support_email.setStyleSheet(
                f"color: {theme['primary']}; font-size: {max(10, subtitle_font_size - 1)}px; font-weight: 600; background-color: transparent;"
            )
        if hasattr(self, "lbl_idle_support_note"):
            self.lbl_idle_support_note.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {max(10, subtitle_font_size - 1)}px; line-height: 1.6; background-color: transparent;"
            )
        if hasattr(self, "btn_idle_settings"):
            self.btn_idle_settings.setMinimumHeight(control_height)
            self.btn_idle_settings.setMaximumHeight(control_height)
            self.btn_idle_settings.setMinimumWidth(112 if density_mode == "wide" else 96)
        if hasattr(self, "btn_idle_feedback"):
            self.btn_idle_feedback.setMinimumHeight(control_height)
            self.btn_idle_feedback.setMaximumHeight(control_height)
            self.btn_idle_feedback.setMinimumWidth(112 if density_mode == "wide" else 96)
        if hasattr(self, "btn_idle_manual"):
            self.btn_idle_manual.setMinimumHeight(control_height)
            self.btn_idle_manual.setMaximumHeight(control_height)
            self.btn_idle_manual.setMinimumWidth(112 if density_mode == "wide" else 96)
        if hasattr(self, "btn_idle_donate"):
            self.btn_idle_donate.setMinimumHeight(control_height)
            self.btn_idle_donate.setMaximumHeight(control_height)
            self.btn_idle_donate.setMinimumWidth(112 if density_mode == "wide" else 96)
        if hasattr(self, "btn_workbench_feedback"):
            self.btn_workbench_feedback.setMinimumHeight(control_height)
            self.btn_workbench_feedback.setMaximumHeight(control_height)
            self.btn_workbench_feedback.setMinimumWidth(112 if density_mode == "wide" else 96)
        if hasattr(self, "lbl_workbench_focus"):
            self.lbl_workbench_focus.setStyleSheet(
                f"""
                QLabel#workbenchFocus {{
                    background-color: #E9F1FB;
                    color: {theme["primary"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 14px;
                    padding: 6px 12px;
                    font-size: {chip_font_size}px;
                    font-weight: 700;
                }}
                """
            )
        for label in getattr(self, "workbench_guidance_labels", []):
            label.setStyleSheet(
                f"""
                QLabel#workbenchHintTag {{
                    background-color: #FBFCFE;
                    color: {theme["text"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 10px;
                    padding: 7px 12px;
                    font-size: {chip_font_size}px;
                    font-weight: 700;
                }}
                """
            )
        if hasattr(self, "info_bar"):
            self.info_bar.setStyleSheet(
                f"""
                QLabel#contextMessage {{
                    background-color: {theme["info_bar"]};
                    color: {theme["text_secondary"]};
                    border: 1px solid {theme["border"]};
                    border-radius: 10px;
                    padding: 8px 12px;
                    font-weight: 600;
                    font-size: {subtitle_font_size}px;
                }}
                """
            )
        for label in [getattr(self, "lbl_word_original_header", None), getattr(self, "lbl_word_replaced_header", None)]:
            if label:
                label.setStyleSheet(
                    f"""
                    QLabel#wordCompareLabel {{
                        color: {theme['text_secondary']};
                        background-color: {theme['hover']};
                        border: 1px solid {theme['border']};
                        border-radius: 10px;
                        padding: 3px 10px;
                        font-size: {max(11, compare_header_font_size - 1)}px;
                        font-weight: 600;
                    }}
                    """
                )
        for label in [
            getattr(self, "lbl_batch_log_hint", None),
            getattr(self, "lbl_batch_summary_hint", None),
            getattr(self, "lbl_batch_result_hint", None),
        ]:
            if label:
                label.setStyleSheet(
                    f"color: {theme['text_secondary']}; font-size: {subtitle_font_size}px; font-weight: 700; background-color: transparent;"
                )
        if hasattr(self, "batch_summary_browser"):
            self.batch_summary_browser.setStyleSheet(
                f"""
                QTextBrowser#batchSummaryBrowser {{
                    background-color: #FCFDFF;
                    color: {theme["text"]};
                    border: 1px solid #E4EBF3;
                    border-radius: 15px;
                    padding: 12px;
                    font-size: {subtitle_font_size}px;
                    line-height: 1.7;
                }}
                """
            )
        if hasattr(self, "batch_result_table"):
            self.batch_result_table.setStyleSheet(
                f"""
                QTableWidget#batchResultTable {{
                    background-color: {theme["surface"]};
                    color: {theme["text"]};
                    border: 1px solid #E4EBF3;
                    border-radius: 15px;
                    gridline-color: transparent;
                    padding: 6px;
                    font-size: {subtitle_font_size}px;
                }}
                QTableWidget#batchResultTable::item {{
                    padding: 8px 10px;
                    border-bottom: 1px solid #E9EEF5;
                }}
                QTableWidget#batchResultTable QHeaderView::section {{
                    background-color: #F7FAFD;
                    color: {theme["text_secondary"]};
                    border: none;
                    border-bottom: 1px solid #E4EBF3;
                    padding: 8px 10px;
                    font-size: {max(11, subtitle_font_size - 1)}px;
                    font-weight: 700;
                }}
                """
            )
            self.batch_result_table.verticalHeader().setDefaultSectionSize(batch_result_row_height)
            self.batch_result_table.horizontalHeader().setFixedHeight(batch_result_row_height - 2)
        if hasattr(self, "lbl_batch_result_meta"):
            self.lbl_batch_result_meta.setStyleSheet(
                f"color: {theme['text_secondary']}; font-size: {max(11, subtitle_font_size - 1)}px; font-weight: 600; background-color: transparent;"
            )
        if hasattr(self, "progress"):
            self.progress.setFixedHeight(progress_height)
        if hasattr(self, "btn_cancel_scan"):
            self.btn_cancel_scan.setFixedSize(cancel_width, progress_height)
            self.btn_cancel_scan.setStyleSheet(self._get_button_style("secondary"))

        self._refresh_batch_result_filter_buttons()
        self._refresh_button_density_styles()
        self._rebuild_idle_support_actions_layout(density_mode)
