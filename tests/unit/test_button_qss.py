"""
Plan 2b PR-V2 Task 2.1 — button.qss 集中化测试

参考:
- docs/superpowers/plans/2026-08-30-visual-component-baseline.md
  「Sub-PR 2 → Task 2.1: button.qss (QPushButton + QToolButton, 5 状态)」

覆盖范围:
- 文件存在 + 非空
- 必须同时覆盖 QPushButton 和 QToolButton
- 必须包含 5 个状态伪类:hover / :pressed / :disabled / :focus / :checked
- 不允许出现裸 hex 字面量(只允许 {token} 占位符)
- 必须使用 6 个核心 token:primary / text / surface / border / hover / pressed
- 通过 render_stylesheet("light", files=["button.qss"]) 渲染,无未替换的小写占位符残留
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from secureredact.ui.styles.loader import _PLACEHOLDER_RE, render_stylesheet


BUTTON_QSS = (
    Path(__file__).resolve().parents[2]
    / "secureredact"
    / "ui"
    / "styles"
    / "button.qss"
)


class TestButtonQss(unittest.TestCase):
    def test_file_exists(self) -> None:
        """button.qss 必须存在且非空。"""
        self.assertTrue(BUTTON_QSS.exists(), f"missing: {BUTTON_QSS}")
        self.assertGreater(BUTTON_QSS.stat().st_size, 0, "button.qss is empty")

    def test_has_pushbutton_selector(self) -> None:
        """必须出现 QPushButton 选择器。"""
        content = BUTTON_QSS.read_text(encoding="utf-8")
        self.assertIn("QPushButton", content)

    def test_has_toolbutton_selector(self) -> None:
        """必须出现 QToolButton 选择器。"""
        content = BUTTON_QSS.read_text(encoding="utf-8")
        self.assertIn("QToolButton", content)

    def test_has_5_states(self) -> None:
        """必须覆盖 hover / pressed / disabled / focus / checked 5 个状态。"""
        content = BUTTON_QSS.read_text(encoding="utf-8")
        for state in (":hover", ":pressed", ":disabled", ":focus", ":checked"):
            with self.subTest(state=state):
                self.assertIn(state, content, f"missing state {state}")

    def test_no_hex_literals(self) -> None:
        """不允许出现裸 hex 字面量(只允许花括号 token 占位符)。
        info_bar / shadow 等 token 已是 hex/rgba 字符串,这里检查 .qss 源码本身。
        """
        content = BUTTON_QSS.read_text(encoding="utf-8")
        match = re.search(r"#[0-9A-Fa-f]{3,8}\b", content)
        self.assertIsNone(
            match,
            "button.qss contains hex literal "
            "(must use token placeholders instead)",
        )

    def test_has_required_token_placeholders(self) -> None:
        """必须引用 6 个核心 token:primary / text / surface / border / hover / pressed。"""
        content = BUTTON_QSS.read_text(encoding="utf-8")
        for token in ("{primary}", "{text}", "{surface}", "{border}", "{hover}", "{pressed}"):
            with self.subTest(token=token):
                self.assertIn(token, content, f"missing required token placeholder {token}")

    def test_loads_with_substitution(self) -> None:
        """通过 render_stylesheet("light", files=["button.qss"]) 渲染,
        不得残留任何未替换的小写占位符。
        """
        rendered = render_stylesheet("light", files=["button.qss"])
        leftover = _PLACEHOLDER_RE.findall(rendered)
        self.assertEqual(
            leftover,
            [],
            f"rendered QSS has unresolved placeholders: {leftover}",
        )


if __name__ == "__main__":
    unittest.main()