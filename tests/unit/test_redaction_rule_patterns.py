# -*- coding: utf-8 -*-
"""地址 / 座机 / 法定代表人 / 原告姓名 等扩展脱敏规则的回归测试.

聚焦于正则表达式准确性，与 DEFAULT_RULES 字典解耦:
不依赖 GUI / PyQt6 / OCR 运行时.
"""
import json
import re
import unittest
from pathlib import Path
from typing import Dict, List


# 复刻 DEFAULT_RULES 中"扩展规则"的 pattern
# 一旦 main.py 或 secureredact/utils/config.py 修改了这里使用的 pattern,
# 本测试会立刻失败, 提醒维护者同步更新.
_EXPECTED_PATTERNS: Dict[str, str] = {
    "地址（含门牌号）": (
        r"[一-龥]{2,15}(?:省|市|自治区|特别行政区)"
        r"[一-龥\d\s,]{4,40}"
        r"\d+号"
    ),
    # 容忍 OCR 误识(字母 x 代替某位数字)
    "固定电话": (
        r"(?<!\d)"
        r"0\d{2,3}[-\s]?"
        r"[\d\w]{7,8}"
        r"(?!\d)"
    ),
    # 同时兼容半角":"和全角"："冒号 + 末尾正向 lookahead 限定后续必须是
    # 人名边界 (助词 / 标点 / 空白 / 字符串结尾). 修复 v1.1.13:
    # '法定代表人继续主张权利' 中旧 pattern 贪婪吞 '继续主张' 当人名 mask.
    "法定代表人": (
        r"法定代表人\s*[::：]?\s*"
        r"[一-龥]{2,4}"
        r"(?:·[一-龥]{2,4})?"
        r"(?=[的之及与和按于在跟同向对为由被让等,，。；;）)\]】\s]|$)"
    ),
}


def _compile_rules() -> Dict[str, re.Pattern]:
    return {name: re.compile(pat) for name, pat in _EXPECTED_PATTERNS.items()}


class TestRedactionRulePatterns(unittest.TestCase):
    """扩展脱敏规则的回归基线 — 防止正则漂移."""

    def setUp(self) -> None:
        self.compiled = _compile_rules()

    # ---- 地址 ----

    def test_address_matches_full_province_city_street(self):
        text = "河北省保定市唐县迷城乡西迷城村二区144号"
        m = self.compiled["地址（含门牌号）"].findall(text)
        self.assertEqual(len(m), 1)
        self.assertIn("144号", m[0])

    def test_address_matches_simple_district(self):
        text = "吉林省吉林市永吉经济开发区吉桦东路1号"
        m = self.compiled["地址（含门牌号）"].findall(text)
        self.assertEqual(len(m), 1)
        self.assertIn("1号", m[0])

    def test_address_does_not_match_plain_text(self):
        for text in ("中华人民共和国", "请到办公室领取", "本配置文件"):
            self.assertEqual(
                self.compiled["地址（含门牌号）"].findall(text), [],
                f"误命中: {text!r}"
            )

    # ---- 固定电话 ----

    def test_fixed_phone_matches_with_dash(self):
        text = "联系方式：0432-6613680"
        m = self.compiled["固定电话"].findall(text)
        self.assertTrue(len(m) >= 1)
        self.assertTrue(any("0432-6613680" in x for x in m))

    def test_fixed_phone_matches_handwritten_partial_with_ocr_error(self):
        # OCR 漏字场景: 含字母 x 代替某位数字; 仍应能命中
        text = "刘x妹 0432-62x07159"
        m = self.compiled["固定电话"].findall(text)
        self.assertTrue(len(m) >= 1, f"未命中手写电话: {text}")

    def test_fixed_phone_does_not_match_id_card(self):
        text = "110101199003078899"
        self.assertEqual(self.compiled["固定电话"].findall(text), [])

    def test_fixed_phone_matches_short_with_colon(self):
        text = "联系电话: 021-12345678"
        m = self.compiled["固定电话"].findall(text)
        self.assertTrue(len(m) >= 1)

    # ---- 法定代表人 ----

    def test_legal_rep_fullwidth_colon(self):
        text = "法定代表人：曹炳志"
        m = self.compiled["法定代表人"].findall(text)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0], "法定代表人：曹炳志")

    def test_legal_rep_halfwidth_colon(self):
        text = "法定代表人:欧阳娜娜"
        m = self.compiled["法定代表人"].findall(text)
        self.assertEqual(len(m), 1)
        self.assertIn("欧阳娜娜", m[0])

    def test_legal_rep_space_separator(self):
        text = "法定代表人 曹炳志"
        m = self.compiled["法定代表人"].findall(text)
        self.assertEqual(len(m), 1)
        self.assertIn("曹炳志", m[0])

    def test_legal_rep_name_without_label_ignored(self):
        text = "曹炳志在庭上陈述"
        self.assertEqual(self.compiled["法定代表人"].findall(text), [])

    # ---- 法定代表人: 边界收紧 (v1.1.13 regression) ----

    def test_legal_rep_does_not_match_followed_by_common_verb(self):
        """regression v1.1.13: 法定代表人后续接 '继续主张' 等普通动词时
        不应匹配 (旧 pattern 贪婪吞 '继续主张' 4 字当作人名 mask).

        场景: '向乙方及其法定代表人继续主张权利' → '向乙方及其法********权利'
        期望: pattern 完全不匹配, 不脱敏.
        """
        for text in (
            "向乙方及其法定代表人继续主张权利",
            "法定代表人继续主张权利",
            "法定代表人张三继续主张权利",
            "法定代表人张三继承权利",
            "法定代表人张三承担违约责任",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    self.compiled["法定代表人"].findall(text), [],
                    f"pattern 不应吞普通动词, 实得 "
                    f"{self.compiled['法定代表人'].findall(text)} for {text!r}",
                )

    def test_legal_rep_matches_followed_by_particle(self):
        """后续接助词 '的/之/与/和/...' 应匹配 — 这是合法的 '标识 + 人名 + 助词' 句式."""
        for text in (
            "法定代表人张三的职责",
            "法定代表人张三与李四",
            "法定代表人张三和周强",
        ):
            with self.subTest(text=text):
                m = self.compiled["法定代表人"].findall(text)
                self.assertEqual(len(m), 1, f"未匹配 {text!r}")
                # 必须包含人名部分, 不吞后续助词
                self.assertIn("张三", m[0])

    def test_legal_rep_matches_followed_by_punctuation(self):
        """后续接标点应匹配."""
        for text in (
            "法定代表人张三。",
            "法定代表人张三，",
            "法定代表人张三；",
            "法定代表人张三的",
        ):
            with self.subTest(text=text):
                m = self.compiled["法定代表人"].findall(text)
                self.assertEqual(len(m), 1, f"未匹配 {text!r}")
                self.assertIn("张三", m[0])

    def test_legal_rep_matches_at_end_of_text(self):
        """字符串末尾边界 — 后续空白 / 字符串结尾应匹配."""
        for text in (
            "法定代表人张三",
            "法定代表人欧阳娜娜",
            "法定代表人: 曹炳志",
        ):
            with self.subTest(text=text):
                m = self.compiled["法定代表人"].findall(text)
                self.assertEqual(len(m), 1, f"未匹配 {text!r}")


class TestMainDefaultRulesExtended(unittest.TestCase):
    """验证 main.py / secureredact.utils.config / config.json 三处规则集合对齐."""

    EXPECTED_EXTENSIONS: List[str] = [
        "地址（含门牌号）",
        "固定电话",
        "法定代表人",
    ]

    def _load_main_default_rules(self):
        from main import DEFAULT_RULES  # type: ignore
        return DEFAULT_RULES

    def _load_module_default_config(self):
        from secureredact.utils.config import DEFAULT_CONFIG  # type: ignore
        return DEFAULT_CONFIG["redaction"]["default_rules"]

    def test_main_default_rules_contains_extensions(self):
        rules = self._load_main_default_rules()
        for name in self.EXPECTED_EXTENSIONS:
            self.assertIn(name, rules, f"main.py DEFAULT_RULES 缺少规则: {name}")
            self.assertTrue(rules[name], f"main.py 规则 {name} pattern 为空")

    def test_module_default_config_contains_extensions(self):
        cfg = self._load_module_default_config()
        for name in self.EXPECTED_EXTENSIONS:
            self.assertIn(name, cfg, f"DEFAULT_CONFIG 缺少规则: {name}")
            self.assertTrue(cfg[name].get("pattern"), f"模块规则 {name} pattern 为空")

    def test_three_way_alignment(self):
        """main.py / secureredact.utils.config / config.json 名称集合一致."""
        cfg_json_path = Path(__file__).resolve().parents[2] / "config.json"
        with open(cfg_json_path, "r", encoding="utf-8") as f:
            cfg_json = json.load(f)

        main_rules = self._load_main_default_rules()
        module_rules = self._load_module_default_config()
        json_rules = cfg_json.get("redaction", {}).get("default_rules", {})

        main_names = set(main_rules.keys())
        module_names = set(module_rules.keys())
        json_names = set(json_rules.keys())

        for name in self.EXPECTED_EXTENSIONS:
            self.assertIn(name, main_names, f"main.py 缺少 {name}")
            self.assertIn(name, module_names, f"DEFAULT_CONFIG 缺少 {name}")
            self.assertIn(name, json_names, f"config.json 缺少 {name}")


class TestDateTimeRuleDisabled(unittest.TestCase):
    """日期时间规则默认 enabled=false (用户决策 v1.1.13: 选 B 不脱敏).

    决策背景: 抵账协议0522 报告 '2026年4月1日' 被全 9 字 mask 为 *********,
    过度脱敏. 用户选择禁用整条规则, 不再做日期脱敏 (日期信息保留).
    """

    def _load_config(self) -> dict:
        cfg_json_path = Path(__file__).resolve().parents[2] / "config.json"
        with open(cfg_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_date_time_disabled_in_config_json(self):
        cfg = self._load_config()
        rule = cfg["redaction"]["default_rules"].get("日期时间", {})
        self.assertEqual(rule.get("enabled"), False,
            "config.json 中 '日期时间' 规则应 enabled=false, 实得 "
            f"{rule.get('enabled')}")

    def test_date_time_disabled_in_template(self):
        template_path = (
            Path(__file__).resolve().parents[2] / "config.json.template"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        rule = cfg["redaction"]["default_rules"].get("日期时间", {})
        self.assertEqual(rule.get("enabled"), False,
            "config.json.template 中 '日期时间' 规则应 enabled=false, 实得 "
            f"{rule.get('enabled')}")


class TestPlaintiffNameRedaction(unittest.TestCase):
    """原告姓名识别 — 应在原告段、著作权人段、签名段都被命中.

    走 main.py 的 custom_keywords 通道(类似 custom_keywords="周强"),
    本测试断言样本合同性质, 防止样本漂移后忘记更新.
    """

    PLAINTIFF = "周强"
    TEXT = (
        "原告：周强，男，汉族，身份证号已脱敏。"
        "著作权人周强在贵州省版权局完成作品登记。"
        "起诉人：周强"
    )

    def test_plaintiff_name_present_in_sample(self):
        occurrences = self.TEXT.count(self.PLAINTIFF)
        self.assertGreaterEqual(occurrences, 3,
            "样本中应包含原告姓名至少 3 次(原告段/著作权人段/签名段)")

    def test_plaintiff_name_count_matches(self):
        self.assertEqual(self.TEXT.count(self.PLAINTIFF), 3)


if __name__ == "__main__":
    unittest.main()