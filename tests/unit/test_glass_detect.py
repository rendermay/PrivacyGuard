"""
玻璃特效降级检测模块测试 — Plan 2b Task 0.1

参考:
- docs/superpowers/plans/2026-08-30-visual-component-baseline.md
  「前置条件 Task 0.1:新建 secureredact/ui/styles/glass.py」
"""

from __future__ import annotations

import unittest
from typing import Mapping

import secureredact.ui.styles.glass as glass


class TestGlassDetect(unittest.TestCase):
    def test_module_exposes_bool(self) -> None:
        """GLASS_AVAILABLE 必须为 bool。"""
        self.assertIsInstance(glass.GLASS_AVAILABLE, bool)

    def test_substitution_returns_required_keys(self) -> None:
        """get_glass_substitution() 必须返回包含 card_background / dock_background 的映射,
        且值是 #hex 或 rgba 字符串。"""
        mapping: Mapping[str, str] = glass.get_glass_substitution()
        self.assertIn("card_background", mapping)
        self.assertIn("dock_background", mapping)
        for value in mapping.values():
            self.assertTrue(
                value.startswith("#") or "rgba" in value,
                f"value {value!r} must start with '#' or contain 'rgba'",
            )


if __name__ == "__main__":
    unittest.main()
