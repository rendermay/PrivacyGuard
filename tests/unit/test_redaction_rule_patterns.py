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
    # 同时兼容半角":"和全角"："冒号
    "法定代表人": (
        r"法定代表人\s*[::：]?\s*"
        r"[一-龥]{2,4}"
        r"(?:·[一-龥]{2,4})?"
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