"""
v1.1.13 PR-B1 (QSS 集中化) 回归测试

覆盖范围:
- Tokens dataclass 字段完整性 / Light/Dark 字段值与原 theme.py 字典一致
- get_substitution_map() 返回 16 颜色 + 3 字体 共 19 个键
- render_stylesheet() 替换所有占位符,无残留
- _PLACEHOLDER_RE 不误伤 QSS 自身 { ... } 规则体
- secureredact/ui/main_window/theme.py 中 _apply_theme 已大幅瘦身(QSS 字符串数量减少 ≥ 80%)
- DARK 主题内部 API 通(render("dark") 不报错,含 dark 主色)
"""

import re
import unittest
from pathlib import Path
from unittest.mock import patch

import secureredact.ui.styles.glass as glass
from secureredact.ui.styles import (
    DARK,
    FONT_FAMILY,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    LIGHT,
    StylesheetLoader,
    get_substitution_map,
    get_tokens,
    render_stylesheet,
)
from secureredact.ui.styles.loader import _PLACEHOLDER_RE, SCOPES

# PR-C1 起主题 mixin 从 main.py 迁至 secureredact/ui/main_window/theme.py
# (main.py 现为过渡期 shim, 不再承载 QSS / 主题实现)
THEME_PY = (
    Path(__file__).resolve().parents[2]
    / "secureredact"
    / "ui"
    / "main_window"
    / "theme.py"
)


# Tokens 数据集完整 16 字段(Light/Dark 共用)
EXPECTED_TOKEN_KEYS = {
    "background", "surface", "primary", "secondary", "accent",
    "text", "text_secondary", "border", "shadow", "info_bar",
    "scroll_area", "hover", "pressed", "success", "danger", "warning",
}


class TestTokensDataclass(unittest.TestCase):
    """Tokens dataclass 字段集与 LIGHT/DARK 完整性。"""

    def test_tokens_field_count(self):
        """Tokens 应有 16 个语义字段。"""
        self.assertEqual(len(LIGHT.__dataclass_fields__), 16)
        self.assertEqual(len(DARK.__dataclass_fields__), 16)

    def test_tokens_field_keys_match_expected(self):
        """字段键集与原 theme.py LIGHT/DARK 字典完全一致(无新增无缺失)。"""
        self.assertEqual(set(LIGHT.__dataclass_fields__), EXPECTED_TOKEN_KEYS)
        self.assertEqual(set(DARK.__dataclass_fields__), EXPECTED_TOKEN_KEYS)

    def test_light_matches_baseline(self):
        """LIGHT 值与 v1.1.13 基线 theme.py LIGHT 字典逐字一致。"""
        # 直接对照 theme.py 的 14 个 hex + 2 个 rgba(基线锁定,改动需 PR 评审)
        expected = {
            "background": "#F7F8FA",
            "surface": "#FFFFFF",
            "primary": "#0F6CBD",
            "secondary": "#5F6B7A",
            "accent": "#0FA968",
            "text": "#18212F",
            "text_secondary": "#5F6B7A",
            "border": "#E2E8F0",
            "shadow": "rgba(18, 31, 53, 0.10)",
            "info_bar": "#F9FBFD",
            "scroll_area": "#F6F8FB",
            "hover": "#EEF4FB",
            "pressed": "#E3ECF8",
            "success": "#0FA968",
            "danger": "#D64545",
            "warning": "#D9831F",
        }
        for k, v in expected.items():
            self.assertEqual(getattr(LIGHT, k), v, f"LIGHT.{k}")

    def test_dark_matches_baseline(self):
        """DARK 值与 v1.1.13 基线 theme.py DARK 字典逐字一致。"""
        expected = {
            "background": "#151C26",
            "surface": "#1E2836",
            "primary": "#56A8FF",
            "secondary": "#9AA8BA",
            "accent": "#34D399",
            "text": "#F6F8FC",
            "text_secondary": "#AAB5C5",
            "border": "#324255",
            "shadow": "rgba(0,0,0,0.30)",
            "info_bar": "#1E2A3B",
            "scroll_area": "#1A2330",
            "hover": "#263241",
            "pressed": "#314155",
            "success": "#34D399",
            "danger": "#FF6B6B",
            "warning": "#FFB454",
        }
        for k, v in expected.items():
            self.assertEqual(getattr(DARK, k), v, f"DARK.{k}")


class TestThemeMapping(unittest.TestCase):
    """get_substitution_map / get_tokens 接口契约。"""

    def test_get_tokens_light_returns_light_dataclass(self):
        self.assertIs(get_tokens("light"), LIGHT)

    def test_get_tokens_dark_returns_dark_dataclass(self):
        self.assertIs(get_tokens("dark"), DARK)

    def test_get_tokens_unknown_falls_back_to_light(self):
        """未知主题名默认 light(基线兼容,严禁抛错)。"""
        self.assertIs(get_tokens("not_a_theme"), LIGHT)

    def test_substitution_map_has_19_keys(self):
        """19 个键 = 16 颜色 + 3 字体。"""
        m = get_substitution_map("light")
        self.assertEqual(len(m), 19)
        # 颜色键全在
        for k in EXPECTED_TOKEN_KEYS:
            self.assertIn(k, m)
        # 字体键全在
        self.assertIn("font_family", m)
        self.assertIn("font_size_small", m)
        self.assertIn("font_size_normal", m)

    def test_substitution_map_font_values(self):
        """字体常量值正确。"""
        m = get_substitution_map("light")
        self.assertEqual(m["font_family"], FONT_FAMILY)
        self.assertEqual(m["font_size_small"], str(FONT_SIZE_SMALL))
        self.assertEqual(m["font_size_normal"], str(FONT_SIZE_NORMAL))

    def test_substitution_map_dark_overrides_light(self):
        """get_substitution_map("dark") 颜色键值与 LIGHT 不同(主色 primary)。"""
        light_m = get_substitution_map("light")
        dark_m = get_substitution_map("dark")
        self.assertNotEqual(light_m["primary"], dark_m["primary"])
        self.assertEqual(light_m["primary"], "#0F6CBD")
        self.assertEqual(dark_m["primary"], "#56A8FF")


class TestRenderStylesheet(unittest.TestCase):
    """render_stylesheet 渲染正确性。"""

    # 说明: glass.GLASS_AVAILABLE 是**导入期求值**的模块级全局,取值依赖
    # "导入 glass 的那一刻是否已存在 QApplication 实例":
    #   - 已有实例 → platformName() 返回 'offscreen' → 判定玻璃不可用(降级)
    #   - 无实例   → platformName() 返回 'windows'   → 判定玻璃可用
    # 这让 QSS 渲染结果依赖 import 顺序(历史上手工全量跑时因先前有 GUI 测试
    # 创建过 QApplication 而恰好走到降级分支)。此处显式固定该前置条件,
    # 消除顺序依赖 —— 断言强度不变, 只是把原本隐式的前提显式化。
    def _render_fallback(self, theme_name: str) -> str:
        """在玻璃降级模式(CI / headless 实际走的路径)下渲染样式表。"""
        with patch.object(glass, "GLASS_AVAILABLE", False):
            return render_stylesheet(theme_name)

    def test_render_light_no_residual_tokens(self):
        """light 主题:渲染后无任何 [a-z_]+ 形态的占位符残留。"""
        qss = self._render_fallback("light")
        # 我们的占位符正则: [a-z_][a-z0-9_]*,且不在 CSS 规则体内部(规则体里都是大写选择器)
        residual = _PLACEHOLDER_RE.findall(qss)
        self.assertEqual(residual, [], f"residual placeholders: {set(residual)}")

    def test_render_dark_no_residual_tokens(self):
        """dark 主题:同上,无残留占位符。"""
        qss = self._render_fallback("dark")
        residual = _PLACEHOLDER_RE.findall(qss)
        self.assertEqual(residual, [], f"residual placeholders: {set(residual)}")

    def test_render_with_glass_available_has_no_residual_tokens(self):
        """
        [P0-5 FIXED] Glass-available mode (desktop) must also leave no
        residual placeholder in the final stylesheet.

        Regression: get_glass_substitution() returns {} when
        GLASS_AVAILABLE=True, and card_background / dock_background are
        not among the 19 theme tokens -- so the final QSS used to keep a
        literal {card_background} placeholder, which Qt cannot parse ->
        card / dock panel backgrounds were lost.

        Fix: loader._build_mapping() setdefault-falls-back the two
        placeholders to theme tokens; glass._detect_glass() now requires a
        real QApplication instance so headless envs are not misdetected.
"""
        with patch.object(glass, "GLASS_AVAILABLE", True):
            qss = render_stylesheet("light")
        residual = _PLACEHOLDER_RE.findall(qss)
        self.assertEqual(residual, [], f"residual placeholders: {set(residual)}")

    def test_render_light_contains_all_token_values(self):
        """light 主题:渲染结果包含全部 16 个 token 实际值(抽样主色/边框/文字)。"""
        qss = render_stylesheet("light")
        light_m = get_substitution_map("light")
        for key in ("primary", "surface", "border", "text", "text_secondary",
                     "background", "hover", "info_bar", "warning"):
            self.assertIn(light_m[key], qss, f"missing {key}={light_m[key]}")

    def test_render_dark_contains_dark_primary(self):
        """dark 主题:渲染结果包含 dark 主色 #56A8FF(防 LIGHT 残留)。"""
        qss = render_stylesheet("dark")
        self.assertIn("#56A8FF", qss)
        self.assertNotIn("#0F6CBD", qss, "dark 渲染结果里不应有 light primary")

    def test_render_light_dark_differ_only_in_colors(self):
        """同一 scope 下,light 与 dark 渲染输出仅颜色值不同(QSS 结构应一致)。"""
        light_qss = render_stylesheet("light")
        dark_qss = render_stylesheet("dark")
        # 行数应一致
        self.assertEqual(light_qss.count("\n"), dark_qss.count("\n"))
        # 长度差异应小于 5%(颜色字面量差异)
        ratio = abs(len(light_qss) - len(dark_qss)) / max(len(light_qss), len(dark_qss))
        self.assertLess(ratio, 0.05)


class TestRegexPrecision(unittest.TestCase):
    """正则 _PLACEHOLDER_RE 不误伤 QSS 自身 { ... } CSS 规则体。"""

    def test_regex_does_not_match_qt_selectors(self):
        """QSS 选择器(QMainWindow / QFrame#workbenchPanel 等)不应被识别为占位符。"""
        samples = [
            "QMainWindow {",
            "QFrame#workbenchPanel {",
            "QMenu::item {",
            "QMenu::item:selected {",
            "QProgressBar::chunk {",
            "QLabel#routeCardMeta[routeTone=\"pdf\"] {",
        ]
        for s in samples:
            m = _PLACEHOLDER_RE.search(s)
            self.assertIsNone(m, f"误匹配: {s!r} → {m}")

    def test_regex_matches_lowercase_underscore_tokens(self):
        """占位符应当被识别:全小写+下划线+数字命名。"""
        for token in ("background", "primary", "font_family", "font_size_small",
                      "info_bar", "text_secondary"):
            sample = f"color: {{{token}}};"
            m = _PLACEHOLDER_RE.search(sample)
            self.assertIsNotNone(m)
            self.assertEqual(m.group(1), token)

    def test_regex_rejects_uppercase_or_hyphenated(self):
        """大写或连字符命名不应被误识别为占位符(QSS 里有 QFRAME-name 等风险?)。"""
        for bad in ("QMain", "QSS-bg", "Q-FRAME", "BACKGROUND"):
            sample = f"color: {{{bad}}};"
            m = _PLACEHOLDER_RE.search(sample)
            self.assertIsNone(m, f"误匹配大写/连字符 token: {bad}")


class TestThemeQssReduction(unittest.TestCase):
    """主题 mixin 中 QSS 集中化收益断言。

    PR-C1 起主题 mixin 从 main.py 迁至 secureredact/ui/main_window/theme.py,
    方法由 _apply_light_theme(self) 统一为 _apply_theme(self, name=None)
    (同时支持 light / dark / system 三种主题);PR-B0 后 main.py 仅为过渡期
    shim, 不再承载主题实现。

    断言锚点随之更新 —— 断言强度不变, 只是指向真实实现所在文件。
    (原锚点在 main.py 中定位不到方法, 导致断言静默退化)
    """

    def _apply_theme_body(self) -> str:
        """提取 theme.py 中 _apply_theme 方法体源码(用于静态断言)。"""
        source = THEME_PY.read_text(encoding="utf-8")
        # 锁定函数体起止
        start = source.find("    def _apply_theme(self, name=None):")
        self.assertNotEqual(
            start, -1,
            "secureredact/ui/main_window/theme.py 应定义 "
            "_apply_theme(self, name=None)")
        end = source.find("    def set_theme(self, name):", start)
        self.assertNotEqual(
            end, -1,
            "theme.py 中 _apply_theme 之后应定义 set_theme(self, name)")
        return source[start:end]

    def test_apply_theme_under_80_lines(self):
        """_apply_theme 函数体行数 < 80(原 main.py 中 _apply_light_theme 有 615 行)。"""
        body = self._apply_theme_body()
        line_count = body.count("\n")
        self.assertLess(line_count, 80, f"_apply_theme 函数体 {line_count} 行,期望 < 80")

    def test_apply_theme_no_long_fstring_blocks(self):
        """原主题方法中的大块 f-string(QSS)不应再出现。"""
        body = self._apply_theme_body()
        # 标志性字符串:原 600+ 行 QSS 包含这些
        for marker in (
            'QFrame#workbenchPanel {{',
            'QFrame#workspaceCard {{',
            'QProgressBar::chunk {{',
        ):
            self.assertNotIn(marker, body, f"原 QSS 块未迁移: {marker!r}")

    def test_apply_theme_calls_loader(self):
        """_apply_theme 必须通过 StylesheetLoader 应用样式(scope="main")。"""
        body = self._apply_theme_body()
        self.assertIn("StylesheetLoader", body)
        self.assertIn('"light"', body)
        self.assertIn('scope="main"', body)
        # 额外:必须真的用当前窗口实例调用 loader.apply(self, ...)
        self.assertIn("loader.apply(self,", body,
            "_apply_theme 必须调用 loader.apply(self, ...) 应用样式")


class TestStylesheetsDirectory(unittest.TestCase):
    """styles 目录下 6 个 .qss 文件存在且非空。"""

    def test_all_six_qss_files_exist(self):
        styles_dir = Path(__file__).resolve().parents[2] / "secureredact" / "ui" / "styles"
        for filename in ("base.qss", "button.qss", "input.qss", "tab.qss",
                          "card.qss", "dock.qss", "menu.qss", "workbench.qss",
                          "toolbar.qss", "workspace.qss", "progress.qss"):
            path = styles_dir / filename
            self.assertTrue(path.is_file(), f"missing: {path}")
            self.assertGreater(path.stat().st_size, 100, f"{filename} too small")

    def test_workspace_qss_is_the_largest(self):
        """workspace.qss 应是最大文件(包含原 main_container 390 行 QSS)。"""
        styles_dir = Path(__file__).resolve().parents[2] / "secureredact" / "ui" / "styles"
        sizes = {f.name: (styles_dir / f.name).stat().st_size
                 for f in styles_dir.glob("*.qss")}
        largest = max(sizes, key=sizes.get)
        self.assertEqual(largest, "workspace.qss", f"sizes={sizes}")


class TestScopesConfiguration(unittest.TestCase):
    """SCOPES 配置完整性。"""

    def test_scopes_has_main_scope(self):
        self.assertIn("main", SCOPES)

    def test_scopes_main_includes_all_files(self):
        """main scope 应包含全部 11 个 .qss 文件(基线完整性,PR-V2 扩展后)。"""
        main_files = SCOPES["main"]
        self.assertEqual(len(main_files), 11)
        for expected in (
            "base.qss", "button.qss", "input.qss", "tab.qss",
            "card.qss", "dock.qss", "menu.qss", "workbench.qss",
            "toolbar.qss", "workspace.qss", "progress.qss",
        ):
            self.assertIn(expected, main_files)


class TestDarkThemeInternalAPI(unittest.TestCase):
    """DARK 主题内部 API 通(规划要求 B1 阶段不暴露 UI,但 API 已通)。"""

    def test_dark_render_succeeds(self):
        """render_stylesheet("dark") 不抛异常,且输出非空。"""
        qss = render_stylesheet("dark")
        self.assertGreater(len(qss), 1000)

    def test_dark_loader_render_succeeds(self):
        """StylesheetLoader.render("dark") 与 render_stylesheet("dark") 一致。"""
        loader = StylesheetLoader()
        loader_dark = loader.render("dark", scope="main")
        fn_dark = render_stylesheet("dark")
        self.assertEqual(loader_dark, fn_dark)

    def test_dark_theme_distinct_from_light(self):
        """dark 与 light 渲染输出长度相近但内容不同(防错把 light 当 dark)。"""
        light_qss = render_stylesheet("light")
        dark_qss = render_stylesheet("dark")
        self.assertNotEqual(light_qss, dark_qss)
        # 但结构性差异(背景色等)
        self.assertIn("#F7F8FA", light_qss)
        self.assertIn("#151C26", dark_qss)


if __name__ == "__main__":
    unittest.main()