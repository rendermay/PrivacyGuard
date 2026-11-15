"""P0-5 回归: 规则冲突消解 —— 同一段文本被多条规则命中时只保留优先级最高的一条。

背景:
    「身份证号」「统一社会信用代码」「银行卡号」三条规则的字符集高度重叠:
      身份证号         15 位 或 18 位(带出生日期校验)
      统一社会信用代码  17-18 位(数字 + 大写字母, 排除 I/O/Z/S/V)
      银行卡号         13-19 位纯数字
    同一个 18 位数字串(如 110101199001011234)会被 3 条规则同时命中,
    导致命中数翻 3 倍、遮蔽边界不一致、命中统计失真。
"""
import unittest

from secureredact.redaction.conflict_resolver import (
    RULE_CONFLICT_PRIORITY,
    resolve_rule_conflicts,
)


def _m(rule_name, start, end, text=""):
    return {
        "rule_name": rule_name,
        "start": start,
        "end": end,
        "text": text,
        "replacement": "*",
        "source": "rule",
    }


class TestResolveRuleConflicts(unittest.TestCase):

    def test_priority_order(self):
        """优先级顺序必须是 身份证号 > USCC > 银行卡号。"""
        self.assertLess(RULE_CONFLICT_PRIORITY["身份证号"],
                        RULE_CONFLICT_PRIORITY["统一社会信用代码"])
        self.assertLess(RULE_CONFLICT_PRIORITY["统一社会信用代码"],
                        RULE_CONFLICT_PRIORITY["银行卡号"])

    def test_same_span_keeps_highest_priority(self):
        """同一区间被 3 条规则命中时只保留 身份证号。"""
        matches = [
            _m("银行卡号", 5, 23),
            _m("统一社会信用代码", 5, 23),
            _m("身份证号", 5, 23),
        ]
        out = resolve_rule_conflicts(matches)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["rule_name"], "身份证号")

    def test_overlapping_span_keeps_highest_priority(self):
        """包含关系的命中同样只保留优先级最高的一条。"""
        matches = [
            _m("银行卡号", 5, 23),
            _m("身份证号", 5, 20),
        ]
        out = resolve_rule_conflicts(matches)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["rule_name"], "身份证号")

    def test_non_participating_rules_untouched(self):
        """不参与消解的规则(邮箱/公司名等)命中必须原样保留。"""
        matches = [
            _m("身份证号", 5, 23),
            _m("银行卡号", 5, 23),
            _m("电子邮箱", 30, 45),
            _m("公司名", 50, 60),
        ]
        out = resolve_rule_conflicts(matches)
        names = [m["rule_name"] for m in out]
        self.assertIn("电子邮箱", names)
        self.assertIn("公司名", names)
        self.assertIn("身份证号", names)
        self.assertNotIn("银行卡号", names)
        self.assertEqual(len(out), 3)

    def test_disjoint_matches_all_kept(self):
        """互不重叠的命中必须全部保留。"""
        matches = [
            _m("身份证号", 0, 18),
            _m("银行卡号", 30, 45),
        ]
        out = resolve_rule_conflicts(matches)
        self.assertEqual(len(out), 2)

    def test_empty_and_single_inputs(self):
        """空输入 / 单条输入必须安全返回。"""
        self.assertEqual(resolve_rule_conflicts([]), [])
        one = [_m("身份证号", 0, 18)]
        self.assertEqual(len(resolve_rule_conflicts(one)), 1)

    def test_does_not_mutate_input(self):
        """不得修改入参列表。"""
        matches = [_m("身份证号", 5, 23), _m("银行卡号", 5, 23)]
        before = list(matches)
        resolve_rule_conflicts(matches)
        self.assertEqual(matches, before)


class TestWordWorkerConflictIntegration(unittest.TestCase):
    """WordWorker 端到端: 18 位身份证号只应命中 1 条规则。"""

    def test_id_card_matched_by_exactly_one_rule(self):
        from secureredact.redaction.rules_loader import (
            DEFAULT_RULES,
            DEFAULT_RULES_META,
        )
        from secureredact.workers.word_worker import WordWorker

        class _FakeDoc:
            paragraphs = []

        worker = WordWorker(
            _FakeDoc(),
            {},
            list(DEFAULT_RULES.values()),
            "",
            "[已脱敏]",
            default_rules=DEFAULT_RULES,
            default_rules_meta=DEFAULT_RULES_META,
        )

        matches = worker._find_matches("身份证号：110101199001011234")
        self.assertEqual(len(matches), 1, f"应只命中 1 条规则, 实际 {matches}")
        self.assertEqual(matches[0]["rule_name"], "身份证号")
        self.assertEqual(matches[0]["text"], "110101199001011234")

    def test_phone_number_unaffected(self):
        """手机号不参与冲突消解, 行为保持不变。"""
        from secureredact.redaction.rules_loader import (
            DEFAULT_RULES,
            DEFAULT_RULES_META,
        )
        from secureredact.workers.word_worker import WordWorker

        class _FakeDoc:
            paragraphs = []

        worker = WordWorker(
            _FakeDoc(),
            {},
            list(DEFAULT_RULES.values()),
            "",
            "[已脱敏]",
            default_rules=DEFAULT_RULES,
            default_rules_meta=DEFAULT_RULES_META,
        )

        matches = worker._find_matches("电话：13812345678")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["rule_name"], "手机号码")


if __name__ == "__main__":
    unittest.main()