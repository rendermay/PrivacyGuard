# -*- coding: utf-8 -*-
"""config.json 加载 blacklist/whitelist 默认值的兜底测试."""
import unittest
from secureredact.utils.config import DEFAULT_CONFIG


class ConfigDefaultsTest(unittest.TestCase):

    def test_default_blacklist_is_list(self):
        self.assertIsInstance(DEFAULT_CONFIG["redaction"].get("blacklist"), list)
        self.assertEqual(DEFAULT_CONFIG["redaction"]["blacklist"], [])

    def test_default_whitelist_is_list(self):
        self.assertIsInstance(DEFAULT_CONFIG["redaction"].get("whitelist"), list)
        self.assertEqual(DEFAULT_CONFIG["redaction"]["whitelist"], [])


if __name__ == "__main__":
    unittest.main()