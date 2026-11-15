# -*- coding: utf-8 -*-
"""config.json 加载 blacklist/whitelist 默认值的兜底测试."""
import unittest
from secureredact.utils.config import DEFAULT_CONFIG


class ConfigDefaultsTest(unittest.TestCase):

    def test_default_blacklist_is_list(self):
        self.assertIsInstance(DEFAULT_CONFIG["redaction"].get("blacklist"), list)
        self.assertEqual(DEFAULT_CONFIG["redaction"]["blacklist"], [])

    def test_default_whitelist_is_list(self):
        """默认白名单应为 list,且每项都是非空字符串。

        注: 默认白名单含合同角色词(甲方/乙方/丙方/丁方/戊方、盖章 等)是
        **产品有意为之** —— 这些词在法律文书中高频出现且属于脱敏噪声,
        故由产品内置为默认白名单。因此这里只断言结构(是 list + 每项为
        非空字符串),**不锁定具体条目内容**,避免产品后续调整白名单时
        测试再次脆化。
        """
        whitelist = DEFAULT_CONFIG["redaction"].get("whitelist")
        self.assertIsInstance(whitelist, list)
        for item in whitelist:
            self.assertIsInstance(item, str)
            self.assertTrue(item.strip(), f"白名单条目不应为空字符串: {item!r}")


if __name__ == "__main__":
    unittest.main()