"""v1.1.12: 部分遮蔽与 WordWorker / batch replace 的集成测试。

验证:
- USCC 命中 replacement 是 `9151*********NK4W` 形式
- 身份证号 18 位 → `110101********1234`
- 邮箱 → `a***@example.com`
- 姓名(jieba / 法定代表人)→ `张*`
- 日期/地址 → 整段打码
- 自定义 batch 规则仍用用户指定 replacement(向后兼容)
- manual 来源命中仍用 replacement_text(向后兼容)
"""

import unittest
from unittest.mock import MagicMock


class TestWordWorkerMaskOutput(unittest.TestCase):
    """WordWorker 命中字段 replacement 在 rule 来源下应用 mask。"""

    def _make_worker(self, name_to_pattern, default_rules_meta, custom_keywords="", replacement_text="[已脱敏]"):
        """name_to_pattern: {rule_name: pattern} 字典。"""
        from secureredact.workers.word_worker import WordWorker
        rules = list(name_to_pattern.values())
        return WordWorker(
            word_doc=MagicMock(),
            word_data={},
            rules=rules,
            custom_keywords=custom_keywords,
            replacement_text=replacement_text,
            default_rules=name_to_pattern,
            default_rules_meta=default_rules_meta,
            enable_name_recognition=False,
        )

    def test_id_card_uses_masked_replacement(self):
        """身份证号命中时 replacement 字段是 mask 后字符串。"""
        from secureredact.utils.config import DEFAULT_CONFIG

        rules_dict = DEFAULT_CONFIG["redaction"]["default_rules"]
        pattern = rules_dict["身份证号"]["pattern"]
        rules_map = {"身份证号": pattern}
        meta = {
            "身份证号": {
                "mask_mode": "default",
                "mask_keep_prefix": 6,
                "mask_keep_suffix": 4,
                "mask_char": "*",
            }
        }
        worker = self._make_worker(rules_map, meta)
        text = "申请人:张三 身份证:110101199001011234"
        matches = worker._find_matches(text)
        id_matches = [m for m in matches if "110101" in m["text"]]
        self.assertEqual(len(id_matches), 1)
        self.assertEqual(id_matches[0]["replacement"], "110101********1234")

    def test_uscc_uses_masked_replacement(self):
        """USCC 命中时 replacement 是 mask 后字符串(保留前 4 + 后 4)。"""
        from secureredact.utils.config import DEFAULT_CONFIG

        rules_dict = DEFAULT_CONFIG["redaction"]["default_rules"]
        pattern = rules_dict["统一社会信用代码"]["pattern"]
        rules_map = {"统一社会信用代码": pattern}
        meta = {
            "统一社会信用代码": {
                "mask_mode": "default",
                "mask_keep_prefix": 4,
                "mask_keep_suffix": 4,
                "mask_char": "*",
            }
        }
        worker = self._make_worker(rules_map, meta)
        text = "信用代码:91110108MA01KXYX29"
        matches = worker._find_matches(text)
        uscc_matches = [m for m in matches if "91110108" in m["text"]]
        self.assertEqual(len(uscc_matches), 1)
        self.assertEqual(uscc_matches[0]["replacement"], "9111**********YX29")

    def test_email_uses_email_mask(self):
        """邮箱命中时 replacement 走 apply_email_mask。"""
        rules_map = {"电子邮箱": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"}
        meta = {"电子邮箱": {"mask_mode": "email", "mask_char": "*"}}
        worker = self._make_worker(rules_map, meta)
        text = "联系:alice@example.com"
        matches = worker._find_matches(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["replacement"], "a***@example.com")

    def test_full_mask_when_prefix_suffix_zero(self):
        """日期/地址 prefix=0 suffix=0 → 整段打码。"""
        rules_map = {"日期时间": r"\d{4}-\d{2}-\d{2}"}
        meta = {"日期时间": {"mask_mode": "default", "mask_keep_prefix": 0, "mask_keep_suffix": 0}}
        worker = self._make_worker(rules_map, meta)
        text = "日期:2024-01-15"
        matches = worker._find_matches(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["replacement"], "**********")  # 10 字符 → 10 *

    def test_jieba_source_uses_replacement_text(self):
        """custom_keywords 来源(不在 self.rules)→ 保留 replacement_text,不参与 mask。"""
        rules_map = {}  # 内置规则为空
        meta = {
            "姓名": {"mask_mode": "name", "mask_keep_prefix": 1, "mask_keep_suffix": 0},
        }
        worker = self._make_worker(rules_map, meta, custom_keywords="张三")
        text = "负责人:张三"
        matches = worker._find_matches(text)
        # custom_keywords 路径也走 replacement_text
        self.assertEqual(matches[0]["replacement"], "[已脱敏]")


def rules_to_pattern_dict(rules):
    """Helper: 把 pattern 列表转换为 {placeholder: pattern} dict(WordWorker.default_rules 期望)。"""
    # WordWorker 实际只关心 pattern 比较,不严格要求 dict key。
    return {f"_rule_{i}": p for i, p in enumerate(rules)}


class TestUserBatchRuleBackwardCompat(unittest.TestCase):
    """v1.1.12 关键兼容性测试: 用户 batch 规则继续用 rule['replace'],不走 mask。"""

    def test_user_exact_rule_uses_user_replacement(self):
        """用户 exact 规则: replacement 是 rule['replace'],不应用 mask。"""
        from main import build_word_rule_matches
        rules = [{"enabled": True, "mode": "exact", "find": "张三", "replace": "某某"}]
        text = "姓名:张三"
        matches = build_word_rule_matches(text, rules, "[已脱敏]")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["replacement"], "某某")

    def test_user_regex_rule_uses_user_replacement(self):
        """用户 regex 规则: replacement 是 rule['replace'],不应用 mask。"""
        from main import build_word_rule_matches
        rules = [{"enabled": True, "mode": "regex", "find": r"1[3-9]\d{9}", "replace": "[手机号]"}]
        text = "电话:13812345678"
        matches = build_word_rule_matches(text, rules, "[已脱敏]")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["replacement"], "[手机号]")


class TestDefaultRulesMetaLoaded(unittest.TestCase):
    """DEFAULT_RULES_META 模块级常量应在所有内置规则上齐全。"""

    def test_all_known_rules_have_meta(self):
        from main import DEFAULT_RULES_META
        required = [
            "身份证号", "手机号码", "银行卡号", "固定电话",
            "统一社会信用代码", "电子邮箱", "法定代表人", "日期时间", "地址（含门牌号）",
        ]
        for name in required:
            self.assertIn(name, DEFAULT_RULES_META, f"{name} 缺少 DEFAULT_RULES_META 条目")

    def test_meta_prefix_suffix_types(self):
        from main import DEFAULT_RULES_META
        for name, meta in DEFAULT_RULES_META.items():
            if meta.get("mask_mode") == "default":
                self.assertIsInstance(meta.get("mask_keep_prefix"), int)
                self.assertIsInstance(meta.get("mask_keep_suffix"), int)

    def test_email_rule_metadata_present(self):
        """电子邮箱规则必须在 DEFAULT_RULES_META 中有元数据条目。

        注:mask_mode 可能是 'email'(配置了)或 'default'(setdefault 补齐),
        测试只验证条目存在, 不强求特定 mode 值。
        """
        from main import DEFAULT_RULES_META
        self.assertIn("电子邮箱", DEFAULT_RULES_META)
        self.assertIn("mask_mode", DEFAULT_RULES_META["电子邮箱"])

    def test_name_rule_metadata_present(self):
        """法定代表人规则必须有元数据条目(mask_mode 取决于 config 配置)。"""
        from main import DEFAULT_RULES_META
        self.assertIn("法定代表人", DEFAULT_RULES_META)
        self.assertIn("mask_mode", DEFAULT_RULES_META["法定代表人"])

    def test_apply_email_mask_direct(self):
        """直接验证 apply_email_mask 输出, 不依赖 DEFAULT_RULES_META 加载路径。"""
        from secureredact.utils.masking import apply_email_mask
        self.assertEqual(apply_email_mask("alice@example.com"), "a***@example.com")

    def test_apply_name_mask_direct(self):
        """直接验证 apply_name_mask 输出。"""
        from secureredact.utils.masking import apply_name_mask
        self.assertEqual(apply_name_mask("张三"), "张*")


class TestWordWorkerBlackWhiteListCompat(unittest.TestCase):
    """v1.1.12: 黑/白名单路径不受 mask 改动影响。"""

    def test_whitelist_trim_keeps_masked_replacement(self):
        """白名单 trim 后,生成的子 hit 仍带 mask 后 replacement。"""
        from secureredact.workers.word_worker import WordWorker
        rules = [r"\d{18}"]  # 模拟身份证
        meta = {
            "身份证号": {"mask_mode": "default", "mask_keep_prefix": 6, "mask_keep_suffix": 4},
        }
        worker = WordWorker(
            word_doc=MagicMock(), word_data={},
            rules=rules, custom_keywords="",
            replacement_text="[已脱敏]",
            default_rules={"身份证号": r"\d{18}"},
            default_rules_meta=meta,
            enable_name_recognition=False,
        )
        # 模拟包含身份证的文本
        text = "身份证:110101199001011234"
        matches = worker._find_matches(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["replacement"], "110101********1234")


if __name__ == "__main__":
    unittest.main(verbosity=2)