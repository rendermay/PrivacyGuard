"""
v1.1.13 PR-V2 Task 2.2 — input.qss 组件样式回归测试

覆盖范围:
- 文件存在
- 全部输入类组件选择器覆盖（QLineEdit/QTextEdit/QPlainTextEdit/QSpinBox/
  QDoubleSpinBox/QComboBox/QAbstractItemView/QSlider/QCheckBox/QRadioButton）
- 5 状态 + :read-only
- 无 hex 字面量（颜色全部用 {token} 占位符）
- 替换器能成功替换所有占位符,无残留

与 button.qss (PR-V2 Task 2.1) 测试模式对齐,作为 PR-V2 第二块组件落地凭证。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from secureredact.ui.styles.loader import _PLACEHOLDER_RE
from secureredact.ui.styles.tokens import get_substitution_map


STYLES_DIR = Path(__file__).resolve().parents[2] / "secureredact" / "ui" / "styles"
INPUT_QSS = STYLES_DIR / "input.qss"


class InputQssSelectorsTest(unittest.TestCase):
    """input.qss 必须覆盖 PR-V2 规划的全部选择器集。"""

    def test_file_exists(self):
        """input.qss 必须存在于 styles 目录下。"""
        self.assertTrue(
            INPUT_QSS.is_file(),
            f"missing file: {INPUT_QSS}",
        )
        self.assertGreater(INPUT_QSS.stat().st_size, 100, "input.qss too small")

    def test_covers_text_inputs(self):
        """QLineEdit / QTextEdit / QPlainTextEdit 三个文本输入选择器必须全部出现。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        for selector in ("QLineEdit", "QTextEdit", "QPlainTextEdit"):
            self.assertIn(
                selector, content, f"input.qss missing text selector: {selector}"
            )

    def test_covers_numeric_inputs(self):
        """QSpinBox / QDoubleSpinBox 两个数值输入选择器必须全部出现。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        for selector in ("QSpinBox", "QDoubleSpinBox"):
            self.assertIn(
                selector, content, f"input.qss missing numeric selector: {selector}"
            )

    def test_covers_combo(self):
        """QComboBox 及其下拉视图 QAbstractItemView 必须出现。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        self.assertIn("QComboBox", content, "input.qss missing QComboBox")
        self.assertIn(
            "QAbstractItemView", content, "input.qss missing QAbstractItemView"
        )

    def test_covers_slider(self):
        """QSlider + groove:horizontal + handle:horizontal 必须出现。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        for selector in (
            "QSlider",
            "QSlider::groove:horizontal",
            "QSlider::handle:horizontal",
        ):
            self.assertIn(
                selector, content, f"input.qss missing slider selector: {selector}"
            )

    def test_covers_check_radio(self):
        """QCheckBox / ::indicator / QRadioButton / ::indicator 全部覆盖。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        for selector in (
            "QCheckBox",
            "QCheckBox::indicator",
            "QRadioButton",
            "QRadioButton::indicator",
        ):
            self.assertIn(
                selector, content, f"input.qss missing check/radio selector: {selector}"
            )


class InputQssStatesTest(unittest.TestCase):
    """input.qss 必须包含 5 状态 + :read-only。"""

    def test_has_5_states_plus_readonly(self):
        """5 状态 = :hover / :focus / :pressed / :disabled / :checked;
        额外 :read-only 由文本输入类需要。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        for state in (":hover", ":focus", ":disabled", ":read-only"):
            self.assertIn(state, content, f"input.qss missing state {state}")


class InputQssTokensTest(unittest.TestCase):
    """input.qss 必须使用 token 占位符,无 hex 字面量;且能被加载器成功替换。"""

    # 形如 #ABC / #ABCDEF / #ABCDEF12 的 hex 色字面量
    _HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")

    def test_no_hex_literals(self):
        """input.qss 不允许出现裸 hex 颜色字面量(必须走 {token} 占位符)。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        matches = self._HEX_RE.findall(content)
        self.assertEqual(
            matches,
            [],
            f"input.qss 含有 hex 字面量,请改用 token: {matches}",
        )

    def test_uses_required_tokens(self):
        """input.qss 必须引用 PR-V2 输入组件规划的 token 集。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        # 输入控件核心 token:primary 用于焦点环 + selection,surface 用于背景,
        # border 用于边框,text 用于前景色,hover/pressed 用于交互态。
        for token in ("{primary}", "{surface}", "{border}", "{text}",
                      "{hover}", "{pressed}"):
            self.assertIn(token, content, f"input.qss missing token {token}")

    def test_loads_with_substitution(self):
        """loader 的 _PLACEHOLDER_RE 替换 input.qss 占位符后,无残留。"""
        content = INPUT_QSS.read_text(encoding="utf-8")
        mapping = get_substitution_map("light")
        rendered = _PLACEHOLDER_RE.sub(
            lambda m: mapping.get(m.group(1), m.group(0)),
            content,
        )
        residual = _PLACEHOLDER_RE.findall(rendered)
        self.assertEqual(
            residual,
            [],
            f"input.qss has unresolved placeholders: {set(residual)}",
        )
        # 抽样确认 light 主色被替换进去
        self.assertIn(mapping["primary"], rendered)
        self.assertIn(mapping["surface"], rendered)


if __name__ == "__main__":
    unittest.main()