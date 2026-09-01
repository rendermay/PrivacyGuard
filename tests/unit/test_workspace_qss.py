"""
v1.1.13 PR-V2 Task 2.7 — workspace.qss 拆分回归测试

覆盖范围:
- 文件存在
- 已迁出 card.qss 的 QFrame#xxxCard 选择器在 workspace.qss 中必须全部消失
- workspace.qss 仍保留 workspace 专属选择器:routeCardAccent / batchResultTable / batchLogList / batchSummaryBrowser 等
- 通过 render_stylesheet("light", scope="workspace") 渲染后,所有占位符都应被替换
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from secureredact.ui.styles import StylesheetLoader


STYLES_DIR = (
    Path(__file__).resolve().parents[2] / "secureredact" / "ui" / "styles"
)
WORKSPACE_QSS_PATH = STYLES_DIR / "workspace.qss"


# 已迁出到 card.qss 的卡片变体 — 在 workspace.qss 中严禁再次出现
FORBIDDEN_CARD_SELECTORS = (
    "QFrame#workspaceCard",
    "QFrame#batchWorkspaceCard",
    "QFrame#mergeWorkspaceCard",
    "QFrame#batchDetailSection",
    "QFrame#previewWorkspaceCard",
    "QFrame#batchStepCard",
    "QFrame#batchMetricCard",
)


class TestWorkspaceQssFileExists(unittest.TestCase):
    """workspace.qss 文件存在性 + 体积下限。"""

    def test_file_exists(self) -> None:
        self.assertTrue(
            WORKSPACE_QSS_PATH.is_file(),
            f"missing workspace.qss at {WORKSPACE_QSS_PATH}",
        )

    def test_file_not_empty(self) -> None:
        """文件体必须 > 100 字节,避免空白 .qss。"""
        self.assertTrue(WORKSPACE_QSS_PATH.is_file())
        self.assertGreater(
            WORKSPACE_QSS_PATH.stat().st_size,
            100,
            f"workspace.qss too small: {WORKSPACE_QSS_PATH.stat().st_size} bytes",
        )


class TestWorkspaceQssNoCardSelectors(unittest.TestCase):
    """workspace.qss 严禁再出现已迁出 card.qss 的 QFrame#xxxCard 选择器。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content: str = WORKSPACE_QSS_PATH.read_text(encoding="utf-8")

    def test_no_card_selectors_in_workspace(self) -> None:
        """卡片变体(workspaceCard / batchWorkspaceCard / mergeWorkspaceCard /
        batchDetailSection / previewWorkspaceCard / batchStepCard /
        batchMetricCard)必须已迁出 workspace.qss。"""
        for selector in FORBIDDEN_CARD_SELECTORS:
            self.assertNotIn(
                selector,
                self.content,
                (
                    f"workspace.qss must not contain {selector!r}; "
                    f"it is owned by card.qss"
                ),
            )

    def test_no_idle_card_selectors_in_workspace(self) -> None:
        """idleStartCard / idleSupportCard 是卡片变体,必须已迁出。"""
        for selector in ("QFrame#idleStartCard", "QFrame#idleSupportCard"):
            self.assertNotIn(
                selector,
                self.content,
                (
                    f"workspace.qss must not contain {selector!r}; "
                    f"it is owned by card.qss"
                ),
            )


class TestWorkspaceQssKeepsNonCard(unittest.TestCase):
    """workspace.qss 保留 workspace 专属非卡片选择器。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content: str = WORKSPACE_QSS_PATH.read_text(encoding="utf-8")

    def test_no_route_card_in_workspace(self) -> None:
        """routeCard(连同 routeTone 变体)已迁出 card.qss,workspace.qss 不得再含其选择器。

        注意:仅检查严格的 ``QFrame#routeCard {`` / ``QFrame#routeCard[`` 模式,
        避免误伤需要保留的 ``QFrame#routeCardAccent`` 系列。
        """
        # 严格的正则:要求后跟空白+ '{' 或 '[' 才算作实际选择器
        pattern = re.compile(r"QFrame#routeCard(?:\s*\{|\[)")
        matches = pattern.findall(self.content)
        self.assertEqual(
            matches,
            [],
            (
                f"workspace.qss must not contain QFrame#routeCard rules "
                f"(it is owned by card.qss); found: {matches}"
            ),
        )

    def test_route_card_accent_kept_in_workspace(self) -> None:
        """routeCardAccent + routeAccent 变体是 workspace 专属样式,必须保留。"""
        self.assertIn(
            "QFrame#routeCardAccent",
            self.content,
            "workspace.qss must keep QFrame#routeCardAccent selector",
        )
        for tone in ("pdf", "word", "batch", "image"):
            self.assertIn(
                f'QFrame#routeCardAccent[routeAccent="{tone}"]',
                self.content,
                (
                    f"workspace.qss must keep "
                    f"QFrame#routeCardAccent[routeAccent={tone!r}] variant"
                ),
            )

    def test_route_card_meta_tone_kept_in_workspace(self) -> None:
        """routeCardMeta 的 routeTone 配色变体是 workspace 专属,必须保留。"""
        for tone in ("pdf", "word", "batch", "image"):
            self.assertIn(
                f'QLabel#routeCardMeta[routeTone="{tone}"]',
                self.content,
                (
                    f"workspace.qss must keep "
                    f"QLabel#routeCardMeta[routeTone={tone!r}] variant"
                ),
            )

    def test_batch_result_table_kept_in_workspace(self) -> None:
        """batchResultTable 是 workspace 专属组件,必须保留。"""
        self.assertIn(
            "QTableWidget#batchResultTable",
            self.content,
            "workspace.qss must keep QTableWidget#batchResultTable selector",
        )

    def test_batch_log_list_kept_in_workspace(self) -> None:
        """batchLogList 是 workspace 专属组件,必须保留。"""
        self.assertIn(
            "QListWidget#batchLogList",
            self.content,
            "workspace.qss must keep QListWidget#batchLogList selector",
        )

    def test_batch_summary_browser_kept_in_workspace(self) -> None:
        """batchSummaryBrowser 是 workspace 专属组件,必须保留。"""
        self.assertIn(
            "QTextBrowser#batchSummaryBrowser",
            self.content,
            "workspace.qss must keep QTextBrowser#batchSummaryBrowser selector",
        )

    def test_idle_transparent_panels_kept(self) -> None:
        """idle 透明 panel 容器(非卡片)必须保留。"""
        for panel in (
            "QFrame#idleHeroPanel",
            "QFrame#idleSectionPanel",
            "QFrame#idleFlowPanel",
            "QFrame#idleActionPanel",
        ):
            self.assertIn(
                panel,
                self.content,
                f"workspace.qss must keep transparent panel selector {panel}",
            )


class TestWorkspaceQssRendersClean(unittest.TestCase):
    """workspace scope 渲染后,所有占位符都应被替换为 token 值。"""

    def test_full_workspace_renders_clean(self) -> None:
        loader = StylesheetLoader()
        rendered = loader.render("light", scope="workspace")
        leftover = re.findall(r"\{[a-z_]+\}", rendered)
        self.assertEqual(
            leftover,
            [],
            f"unresolved placeholders: {leftover}",
        )

    def test_workspace_dark_renders_clean(self) -> None:
        """dark 主题渲染 workspace scope 也无残留占位符。"""
        loader = StylesheetLoader()
        rendered = loader.render("dark", scope="workspace")
        leftover = re.findall(r"\{[a-z_]+\}", rendered)
        self.assertEqual(
            leftover,
            [],
            f"unresolved placeholders in dark: {leftover}",
        )


if __name__ == "__main__":
    unittest.main()