"""
v1.1.13 PR-V2 Task 2.6 / 2.7 — StylesheetLoader 集成回归测试

覆盖范围:
- card_background / dock_background 占位符由 glass.py 自动替换(降级时)
- SCOPES['main'] 包含 6 类组件 .qss
- SCOPES['toolbar'] 在 toolbar.qss 之前加载 button.qss
- SCOPES['workspace'] 在 workspace.qss 之前加载 card.qss
- render_stylesheet("light", scope="main") 全量渲染后无占位符残留
"""

import re
import unittest
from pathlib import Path

from secureredact.ui.styles import StylesheetLoader, render_stylesheet
from secureredact.ui.styles.glass import GLASS_AVAILABLE
from secureredact.ui.styles.loader import SCOPES


class TestCardDockGlassSubstitution(unittest.TestCase):
    """card_background / dock_background 在 glass 不可用时被替换为 rgba 兜底。"""

    def test_card_background_resolves_via_glass(self):
        rendered = render_stylesheet("light", files=["card.qss"])
        if not GLASS_AVAILABLE:
            self.assertNotIn(
                "{card_background}", rendered,
                "card_background should be substituted when glass unavailable",
            )
        else:
            # GLASS_AVAILABLE 时使用主题 token,值仍是具体颜色字面量
            self.assertTrue(
                "rgba" in rendered or "#" in rendered,
                "card_background should resolve to a concrete color value",
            )

    def test_dock_background_resolves_via_glass(self):
        rendered = render_stylesheet("light", files=["dock.qss"])
        if not GLASS_AVAILABLE:
            self.assertNotIn(
                "{dock_background}", rendered,
                "dock_background should be substituted when glass unavailable",
            )
        else:
            self.assertTrue(
                "rgba" in rendered or "#" in rendered,
                "dock_background should resolve to a concrete color value",
            )


class TestScopesContainAllComponents(unittest.TestCase):
    """SCOPES 字典必须包含 6 类组件 .qss 文件。"""

    def test_main_scope_includes_all_components(self):
        expected = {
            "base.qss", "button.qss", "input.qss", "tab.qss",
            "card.qss", "dock.qss", "menu.qss", "workbench.qss",
            "toolbar.qss", "workspace.qss", "progress.qss",
        }
        actual = set(SCOPES["main"])
        missing = expected - actual
        self.assertEqual(missing, set(), f"missing components: {missing}")

    def test_toolbar_scope_loads_button_first(self):
        """toolbar scope 必须先加载 button.qss,再加载 toolbar.qss。"""
        self.assertLess(
            SCOPES["toolbar"].index("button.qss"),
            SCOPES["toolbar"].index("toolbar.qss"),
            "toolbar scope must load button.qss before toolbar.qss",
        )

    def test_workspace_scope_loads_card_first(self):
        """workspace scope 必须先加载 card.qss,再加载 workspace.qss。"""
        self.assertLess(
            SCOPES["workspace"].index("card.qss"),
            SCOPES["workspace"].index("workspace.qss"),
            "workspace scope must load card.qss before workspace.qss",
        )


class TestFullMainScopeRendersClean(unittest.TestCase):
    """全量 main scope 渲染后,所有占位符都应被替换。"""

    def test_full_main_stylesheet_renders_clean(self):
        loader = StylesheetLoader()
        rendered = loader.render("light", scope="main")
        leftover = re.findall(r"\{[a-z_]+\}", rendered)
        self.assertEqual(leftover, [], f"unresolved placeholders: {leftover}")


if __name__ == "__main__":
    unittest.main()