# -*- coding: utf-8 -*-
"""BlackWhiteListStore.is_trim_only 配置读取测试."""
import unittest
from unittest.mock import MagicMock

from secureredact.redaction.black_white_list_store import BlackWhiteListStore


class IsTrimOnlyTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_default_true_without_config(self):
        """未 bind_config 时, 默认 True (v38 起 trim_only 默认开)."""
        store = BlackWhiteListStore.instance()
        self.assertTrue(store.is_trim_only())

    def test_explicit_true_from_config(self):
        config = MagicMock()
        config.get.return_value = True
        BlackWhiteListStore.instance().bind_config(config)
        self.assertTrue(BlackWhiteListStore.instance().is_trim_only())
        config.get.assert_called_with("redaction.whitelist_trim_only", True)

    def test_explicit_false_from_config(self):
        config = MagicMock()
        config.get.return_value = False
        BlackWhiteListStore.instance().bind_config(config)
        self.assertFalse(BlackWhiteListStore.instance().is_trim_only())

    def test_non_bool_falls_back_to_true_with_warn(self):
        config = MagicMock()
        config.get.return_value = "true"  # 字符串, 应回退
        BlackWhiteListStore.instance().bind_config(config)
        with self.assertLogs("secureredact.redaction.black_white_list_store",
                             level="WARNING") as cm:
            self.assertTrue(BlackWhiteListStore.instance().is_trim_only())
        self.assertTrue(any("whitelist_trim_only" in m for m in cm.output))

    def test_set_trim_only_overrides_config(self):
        config = MagicMock()
        config.get.return_value = True
        BlackWhiteListStore.instance().bind_config(config)
        store = BlackWhiteListStore.instance()
        store.set_trim_only(False)
        self.assertFalse(store.is_trim_only())

    def test_reset_singleton_clears_override(self):
        store = BlackWhiteListStore.instance()
        store.set_trim_only(False)
        BlackWhiteListStore.reset_singleton()
        self.assertTrue(BlackWhiteListStore.instance().is_trim_only())


if __name__ == "__main__":
    unittest.main()
