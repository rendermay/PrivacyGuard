"""
card.qss 内容测试 — Plan 2b PR-V2 Task 2.4

参考:
- docs/superpowers/plans/2026-08-30-visual-component-baseline.md
  「Sub-PR 2 → Task 2.4: card.qss — QFrame#xxxCard variants」

注意:
- 本测试**只做文件内容校验**,不调用 render_stylesheet(),
  因为 {card_background} 占位符不在 get_substitution_map() 的默认映射中,
  而 get_glass_substitution() 在 GLASS_AVAILABLE=True 时返回 {},
  完整替换链路要等 Agent 6 (toolbar refactor) 扩展 loader.py 才能验证。
- 集成验证由 Agent 6 负责。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


STYLES_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "secureredact"
    / "ui"
    / "styles"
)
CARD_QSS = STYLES_DIR / "card.qss"


class TestCardQss(unittest.TestCase):
    """card.qss 内容校验 — 文件存在 / 选择器 / 状态 / 占位符 / 无 hex。"""

    def setUp(self) -> None:
        self.content: str = CARD_QSS.read_text(encoding="utf-8")

    def test_file_exists(self) -> None:
        """card.qss 必须存在。"""
        self.assertTrue(CARD_QSS.exists(), f"missing file: {CARD_QSS}")

    def test_covers_qframe(self) -> None:
        """card.qss 必须显式覆盖 QFrame 选择器。"""
        self.assertIn("QFrame", self.content, "card.qss missing QFrame selector")

    def test_covers_card_variants(self) -> None:
        """card.qss 必须覆盖工作区中所有 8 个 QFrame#xxxCard 变体。"""
        required = [
            "#workspaceCard",
            "#batchWorkspaceCard",
            "#mergeWorkspaceCard",
            "#batchDetailSection",
            "#previewWorkspaceCard",
            "#batchStepCard",
            "#batchMetricCard",
            "#routeCard",
        ]
        for variant in required:
            self.assertIn(
                variant,
                self.content,
                f"card.qss missing variant selector {variant}",
            )

    def test_has_states(self) -> None:
        """card.qss 必须包含 :hover / :pressed / :disabled / :focus 四个状态。"""
        for state in (":hover", ":pressed", ":disabled", ":focus"):
            self.assertIn(
                state,
                self.content,
                f"card.qss missing pseudo-state {state}",
            )

    def test_uses_card_background_token(self) -> None:
        """card.qss 必须使用 {card_background} 占位符(由 glass.get_glass_substitution 解析)。"""
        self.assertIn(
            "{card_background}",
            self.content,
            "card.qss missing {card_background} placeholder",
        )

    def test_uses_standard_tokens(self) -> None:
        """card.qss 必须使用 {surface} / {border} / {text} 三个基础 token。"""
        for token in ("{surface}", "{border}", "{text}"):
            self.assertIn(
                token,
                self.content,
                f"card.qss missing standard token {token}",
            )

    def test_no_hex_literals(self) -> None:
        """card.qss 严禁出现 #RRGGBB 字面量 — 所有颜色必须来自 token。"""
        hex_pattern = re.compile(r"#[0-9A-Fa-f]{6}\b")
        matches = hex_pattern.findall(self.content)
        self.assertEqual(
            matches,
            [],
            f"card.qss contains hex literals (must use tokens): {matches}",
        )


if __name__ == "__main__":
    unittest.main()