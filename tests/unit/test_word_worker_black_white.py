# -*- coding: utf-8 -*-
"""WordWorker 黑/白名单测试."""
import unittest

from secureredact.redaction.black_white_list_store import BlackWhiteListStore
from secureredact.workers.word_worker import WordWorker


class _WordFilterTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()
    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_filter_whitelist_strips_matched(self):
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        w = WordWorker.__new__(WordWorker)
        hits = [
            {"start": 0, "end": 2, "text": "盖章", "source": "rule"},
            {"start": 5, "end": 7, "text": "周强", "source": "jieba"},
        ]
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "周强")

    def test_filter_whitelist_preserves_manual(self):
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        w = WordWorker.__new__(WordWorker)
        hits = [{"start": 0, "end": 2, "text": "盖章", "source": "manual"}]
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)

    def test_filter_whitelist_empty_returns_all(self):
        w = WordWorker.__new__(WordWorker)
        hits = [{"start": 0, "end": 2, "text": "盖章", "source": "rule"}]
        out = w._filter_whitelist(hits)
        self.assertEqual(out, hits)

    def test_trim_only_keeps_only_non_whitelisted_substring(self):
        """v38: trim_only=True 时, 整段 Word 命中被切成非白名单位置的子 match."""
        from secureredact.redaction.black_white_list_store import BlackWhiteListStore
        BlackWhiteListStore.reset_singleton()
        store = BlackWhiteListStore.instance()
        store.load_permanent([], ["法定代表人"])
        store.set_trim_only(True)
        from secureredact.workers.word_worker import WordWorker
        w = WordWorker.__new__(WordWorker)
        hits = [{
            "pattern": "test", "rule_name": "test",
            "start": 0, "end": 8, "text": "法定代表人：周超",
            "replacement": "***", "source": "rule",
        }]
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")
        self.assertEqual(out[0]["start"], 5)
        self.assertEqual(out[0]["end"], 8)


class _WordBlacklistInjectTest(unittest.TestCase):
    """直接测试纯函数: 给定 text + blacklist → 命中列表."""

    def setUp(self):
        BlackWhiteListStore.reset_singleton()
    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_single_match(self):
        BlackWhiteListStore.instance().load_permanent(["盖章"], [])
        text = "签名或者盖章。"
        hits = WordWorker._scan_blacklist_in_text(text, ["盖章"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["text"], "盖章")
        self.assertEqual(hits[0]["start"], 4)
        self.assertEqual(hits[0]["end"], 6)

    def test_multiple_matches(self):
        BlackWhiteListStore.instance().load_permanent(["吉"], [])
        text = "吉林吉铁吉"
        hits = WordWorker._scan_blacklist_in_text(text, ["吉"])
        self.assertEqual(len(hits), 3)

    def test_no_match(self):
        text = "无关文字"
        hits = WordWorker._scan_blacklist_in_text(text, ["盖章"])
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()