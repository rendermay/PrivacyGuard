"""
v1.1.13 PR-V2 Task 2.3 — tab.qss 回归测试

覆盖范围:
- tab.qss 文件存在且非空
- 涵盖 QTabWidget + QTabBar 选择器
- QTabBar::tab 含 5 状态:hover / :selected / :disabled / :focus(基线:normal 是无伪类默认规则)
- 含 QTabWidget::pane 子控件选择器
- 颜色全部用 {token} 占位符,无 hex 字面量
- 通过 StylesheetLoader 的 substitution 渲染无残留占位符
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from secureredact.ui.styles.loader import _PLACEHOLDER_RE, render_stylesheet
from secureredact.ui.styles.tokens import get_substitution_map


STYLES_DIR = Path(__file__).resolve().parents[2] / "secureredact" / "ui" / "styles"
TAB_QSS_PATH = STYLES_DIR / "tab.qss"


REQUIRED_TAB_PSEUDO_STATES = [
    "QTabBar::tab:hover",
    "QTabBar::tab:selected",
    "QTabBar::tab:disabled",
    "QTabBar::tab:focus",
]

# 视觉基线 lock 颜色 token(必须在 tab.qss 出现的占位符,确保切 light/dark 时同步)
REQUIRED_TOKEN_PLACEHOLDERS = [
    "{surface}",
    "{background}",
    "{border}",
    "{primary}",
    "{text}",
    "{hover}",
    "{pressed}",
]


class TestTabQssFileExists(unittest.TestCase):
    """tab.qss 文件存在性 + 体积下限。"""

    def test_file_exists(self):
        self.assertTrue(
            TAB_QSS_PATH.is_file(),
            f"missing tab.qss at {TAB_QSS_PATH}",
        )

    def test_file_not_empty(self):
        """文件体必须 > 100 字节,避免空白 .qss。"""
        self.assertTrue(TAB_QSS_PATH.is_file())
        self.assertGreater(
            TAB_QSS_PATH.stat().st_size,
            100,
            f"tab.qss too small: {TAB_QSS_PATH.stat().st_size} bytes",
        )


class TestTabQssCoversTabWidgetAndTabBar(unittest.TestCase):
    """tab.qss 必须覆盖 QTabWidget + QTabBar 顶层选择器。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = TAB_QSS_PATH.read_text(encoding="utf-8")

    def test_covers_tab_widget(self):
        self.assertIn(
            "QTabWidget",
            self.content,
            "tab.qss missing QTabWidget selector",
        )

    def test_covers_tab_bar(self):
        self.assertIn(
            "QTabBar",
            self.content,
            "tab.qss missing QTabBar selector",
        )

    def test_has_pane_selector(self):
        """QTabWidget::pane 必须存在(决定 tab 内容区边框/背景)。"""
        self.assertIn(
            "QTabWidget::pane",
            self.content,
            "tab.qss missing QTabWidget::pane selector",
        )


class TestTabQssPseudoStates(unittest.TestCase):
    """QTabBar::tab 必须含 5 状态(基线锁定:normal / hover / selected / disabled / focus)。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = TAB_QSS_PATH.read_text(encoding="utf-8")

    def test_covers_tab_pseudo_states(self):
        """required states: :tab:hover / :tab:selected / :tab:disabled / :tab:focus."""
        for state in REQUIRED_TAB_PSEUDO_STATES:
            self.assertIn(
                state,
                self.content,
                f"tab.qss missing state {state!r}",
            )

    def test_has_tab_normal_block(self):
        """normal 状态是 QTabBar::tab 的默认规则体(无伪类)。"""
        # 用 regex 找 `QTabBar::tab {` 或 `QTabBar::tab\n{`,允许空白
        pattern = re.compile(r"QTabBar::tab\s*\{")
        self.assertRegex(
            self.content,
            pattern,
            "tab.qss missing QTabBar::tab normal rule",
        )


class TestTabQssTokens(unittest.TestCase):
    """颜色必须用 token 占位符,不允许出现 hex 字面量。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = TAB_QSS_PATH.read_text(encoding="utf-8")

    def test_no_hex_literals(self):
        """不允许出现 #RRGGBB 形式 hex 字面量(走 token,light/dark 切换安全)。"""
        # 排除注释行(以 /* 开头)
        non_comment = "\n".join(
            line for line in self.content.splitlines()
            if not line.lstrip().startswith(("/*", "*", "//"))
        )
        hex_matches = re.findall(r"#[0-9A-Fa-f]{6,8}\b", non_comment)
        self.assertEqual(
            hex_matches,
            [],
            f"tab.qss contains hex literals (use tokens): {hex_matches}",
        )

    def test_uses_required_token_placeholders(self):
        """必须引用所有必需 token 占位符(覆盖视觉基线所有状态维度)。"""
        for token in REQUIRED_TOKEN_PLACEHOLDERS:
            self.assertIn(
                token,
                self.content,
                f"tab.qss missing token placeholder {token!r}",
            )


class TestTabQssSubstitution(unittest.TestCase):
    """通过 render_stylesheet 渲染时,所有占位符都应被替换为 token 值。"""

    def test_loads_with_substitution_light(self):
        """light 主题渲染:无残留占位符 + 包含 light 主色。"""
        rendered = render_stylesheet("light", files=("tab.qss",))
        residual = _PLACEHOLDER_RE.findall(rendered)
        self.assertEqual(
            residual,
            [],
            f"residual placeholders after light render: {set(residual)}",
        )
        mapping = get_substitution_map("light")
        # 主色必须出现
        self.assertIn(mapping["primary"], rendered)

    def test_loads_with_substitution_dark(self):
        """dark 主题渲染:无残留占位符 + 包含 dark 主色。"""
        rendered = render_stylesheet("dark", files=("tab.qss",))
        residual = _PLACEHOLDER_RE.findall(rendered)
        self.assertEqual(
            residual,
            [],
            f"residual placeholders after dark render: {set(residual)}",
        )
        mapping = get_substitution_map("dark")
        # dark 主色必须出现,且 light 主色不应出现
        self.assertIn(mapping["primary"], rendered)
        self.assertNotIn(
            get_substitution_map("light")["primary"],
            rendered,
            "light primary leaked into dark render",
        )


if __name__ == "__main__":
    unittest.main()
