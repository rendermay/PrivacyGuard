# -*- coding: utf-8 -*-
"""BlackWhiteListStore 单例逻辑测试."""
import unittest
from privacyguard.redaction.black_white_list_store import BlackWhiteListStore


class BlackWhiteListStoreTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_singleton(self):
        a = BlackWhiteListStore.instance()
        b = BlackWhiteListStore.instance()
        self.assertIs(a, b)

    def test_effective_blacklist_default_empty(self):
        s = BlackWhiteListStore.instance()
        self.assertEqual(s.effective_blacklist(), [])

    def test_effective_whitelist_default_empty(self):
        s = BlackWhiteListStore.instance()
        self.assertEqual(s.effective_whitelist(), [])

    def test_reset_singleton_clears_state(self):
        s = BlackWhiteListStore.instance()
        # 先放一个会话条目以验证 reset
        s.add_session_black("盖章")
        BlackWhiteListStore.reset_singleton()
        s2 = BlackWhiteListStore.instance()
        self.assertIsNot(s, s2)
        self.assertEqual(s2.effective_blacklist(), [])

    def test_load_permanent_normal(self):
        s = BlackWhiteListStore.instance()
        s.load_permanent(["盖章", "签字"], ["12345"])
        self.assertIn("盖章", s.effective_blacklist())
        self.assertIn("签字", s.effective_blacklist())
        self.assertEqual(s.effective_whitelist(), ["12345"])

    def test_load_permanent_filters_empty_and_whitespace(self):
        s = BlackWhiteListStore.instance()
        s.load_permanent(["盖章", "", "  ", "\t"], [])
        self.assertEqual(s.effective_blacklist(), ["盖章"])

    def test_load_permanent_warns_on_non_list(self):
        s = BlackWhiteListStore.instance()
        # 不是 list → 回退到空, 不抛异常
        s.load_permanent("not a list", "also not a list")
        self.assertEqual(s.effective_blacklist(), [])
        self.assertEqual(s.effective_whitelist(), [])

    def test_load_permanent_filters_non_string_items(self):
        s = BlackWhiteListStore.instance()
        s.load_permanent(["盖章", 123, None, "签字"], [])
        # 非字符串条目静默跳过
        self.assertEqual(s.effective_blacklist(), ["盖章", "签字"])


if __name__ == "__main__":
    unittest.main()
