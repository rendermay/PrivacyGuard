"""
Plan 2b PR-V2 Task 2.5 — dock.qss 集中化测试

参考:
- docs/superpowers/plans/2026-08-30-visual-component-baseline.md
  「Sub-PR 2 → Task 2.5: dock.qss (QDockWidget 5 状态)」

覆盖范围:
- 文件存在 + 非空
- 必须出现 QDockWidget + QDockWidget::title 选择器
- title bar 必须覆盖 5 个状态:hover / pressed / disabled / focus(normal 用裸选择器)
- 必须使用 {dock_background} 占位符(由 loader 在 Glass 不可用时替换)
- 必须使用 3 个核心 token:surface / border / text
- 不允许出现裸 hex 字面量(只允许 {token} 占位符)

NOTE:
- 任务说明:本任务仅做文件内容测试,不做渲染回归测试。
- {dock_background} 在 render_stylesheet 中不会被替换(因为它不在 get_substitution_map 返回的
  mapping 中) — 该占位符由 StylesheetLoader 在 PR-V4 阶段合并 Glass substitution 后替换;
  本测试只验证文件源码内容正确,token 替换一致性由 Agent 6 单独验证。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


DOCK_QSS = (
    Path(__file__).resolve().parents[2]
    / "secureredact"
    / "ui"
    / "styles"
    / "dock.qss"
)


class TestDockQss(unittest.TestCase):
    def test_file_exists(self) -> None:
        """dock.qss 必须存在且非空。"""
        self.assertTrue(DOCK_QSS.exists(), f"missing: {DOCK_QSS}")
        self.assertGreater(DOCK_QSS.stat().st_size, 0, "dock.qss is empty")

    def test_covers_qdockwidget(self) -> None:
        """必须出现 QDockWidget 选择器。"""
        content = DOCK_QSS.read_text(encoding="utf-8")
        self.assertIn("QDockWidget", content, "dock.qss must declare QDockWidget selector")

    def test_covers_title_bar(self) -> None:
        """必须出现 QDockWidget::title 子选择器。"""
        content = DOCK_QSS.read_text(encoding="utf-8")
        self.assertIn(
            "QDockWidget::title",
            content,
            "dock.qss must declare QDockWidget::title selector",
        )

    def test_covers_title_states(self) -> None:
        """title bar 必须覆盖 5 个状态:hover / pressed / disabled / focus(normal 用裸选择器)。"""
        content = DOCK_QSS.read_text(encoding="utf-8")
        required = [
            "::title:hover",
            "::title:pressed",
            "::title:disabled",
            "::title:focus",
        ]
        for state in required:
            with self.subTest(state=state):
                self.assertIn(
                    state,
                    content,
                    f"dock.qss missing title state {state}",
                )

    def test_uses_dock_background_token(self) -> None:
        """必须引用 {dock_background} 占位符。"""
        content = DOCK_QSS.read_text(encoding="utf-8")
        self.assertIn(
            "{dock_background}",
            content,
            "dock.qss must reference {dock_background} token",
        )

    def test_uses_standard_tokens(self) -> None:
        """必须引用 3 个核心 token:surface / border / text。"""
        content = DOCK_QSS.read_text(encoding="utf-8")
        for token in ("{surface}", "{border}", "{text}"):
            with self.subTest(token=token):
                self.assertIn(
                    token,
                    content,
                    f"dock.qss missing required token {token}",
                )

    def test_no_hex_literals(self) -> None:
        """不允许出现裸 hex 字面量(只允许 {token} 占位符)。"""
        content = DOCK_QSS.read_text(encoding="utf-8")
        match = re.search(r"#[0-9A-Fa-f]{3,8}\b", content)
        self.assertIsNone(
            match,
            f"dock.qss contains hex literal (must use {{token}} placeholders instead): "
            f"{match.group(0)!r}" if match is not None else
            "dock.qss contains hex literal (must use {token} placeholders instead)",
        )


if __name__ == "__main__":
    unittest.main()