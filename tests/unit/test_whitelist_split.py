# -*- coding: utf-8 -*-
"""_split_text_by_whitelist 单元测试."""
import unittest

from secureredact.redaction.whitelist_split import _split_text_by_whitelist


class SplitTextByWhitelistTest(unittest.TestCase):

    def test_empty_text_returns_single_empty_span(self):
        self.assertEqual(_split_text_by_whitelist("", []), [(0, 0, "")])

    def test_empty_whitelist_returns_full_span(self):
        self.assertEqual(_split_text_by_whitelist("abc", []), [(0, 3, "abc")])

    def test_empty_text_with_whitelist_returns_empty(self):
        # text 为空, 白名单非空 → 无保留片段
        self.assertEqual(_split_text_by_whitelist("", ["abc"]), [])

    def test_no_match_returns_full_span(self):
        self.assertEqual(
            _split_text_by_whitelist("abc", ["xyz"]),
            [(0, 3, "abc")],
        )

    def test_wl_in_middle_keeps_both_sides(self):
        # "aaaXbbb" + ["X"] → [("aaa", 0, 3), ("bbb", 4, 7)]
        self.assertEqual(
            _split_text_by_whitelist("aaaXbbb", ["X"]),
            [(0, 3, "aaa"), (4, 7, "bbb")],
        )

    def test_wl_at_start(self):
        # "Xbbb" + ["X"] → [("bbb", 1, 4)]
        self.assertEqual(_split_text_by_whitelist("Xbbb", ["X"]), [(1, 4, "bbb")])

    def test_wl_at_end(self):
        # "aaaX" + ["X"] → [("aaa", 0, 3)]
        self.assertEqual(_split_text_by_whitelist("aaaX", ["X"]), [(0, 3, "aaa")])

    def test_wl_covers_full_text(self):
        # "aaa" + ["aaa"] → []
        self.assertEqual(_split_text_by_whitelist("aaa", ["aaa"]), [])

    def test_multiple_non_overlapping_wl(self):
        # "abc" + ["a", "c"] → [("b", 1, 2)]
        self.assertEqual(_split_text_by_whitelist("abc", ["a", "c"]), [(1, 2, "b")])

    def test_overlapping_wl_merged(self):
        # "aaaa" + ["aa", "aaa"] → 所有位置 0-3 都被至少一个 wl 覆盖,
        # 标准并集合并得 [(0,4)], 取反集为空 []. 原先期望 [(3,4,"a")] 是
        # 基于"起点严格内部→跳过"的非标准合并规则, 已纠正为 union-merge 语义.
        self.assertEqual(
            _split_text_by_whitelist("aaaa", ["aa", "aaa"]),
            [],
        )

    def test_wl_appearing_multiple_times(self):
        # "XaXaX" + ["X"] → [("a", 1, 2), ("a", 3, 4)]
        self.assertEqual(
            _split_text_by_whitelist("XaXaX", ["X"]),
            [(1, 2, "a"), (3, 4, "a")],
        )

    def test_chinese_text_with_cjk_substring(self):
        # "法定代表人：周超" + ["法定代表人"] → [("：周超", 5, 8)]
        self.assertEqual(
            _split_text_by_whitelist("法定代表人：周超", ["法定代表人"]),
            [(5, 8, "：周超")],
        )

    def test_empty_string_in_whitelist_ignored(self):
        # 空串白名单条目视为无匹配
        self.assertEqual(
            _split_text_by_whitelist("abc", ["", "b"]),
            [(0, 1, "a"), (2, 3, "c")],
        )


if __name__ == "__main__":
    unittest.main()
