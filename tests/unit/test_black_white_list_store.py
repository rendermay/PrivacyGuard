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


if __name__ == "__main__":
    unittest.main()
