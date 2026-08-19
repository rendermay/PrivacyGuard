# -*- coding: utf-8 -*-
"""白名单 trim_only 集成测试 — Word + PDF."""
import unittest

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.word_worker import WordWorker


def _match(text, source="rule", start=0, end=None, pattern="x"):
    if end is None:
        end = start + len(text)
    return {
        "pattern": pattern,
        "rule_name": "test",
        "start": start,
        "end": end,
        "text": text,
        "replacement": "***",
        "source": source,
    }


class WordFilterWhitelistTrimTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _filter(self, hits, trim_only):
        store = BlackWhiteListStore.instance()
        store.load_permanent([], ["法定代表人"])
        store.set_trim_only(trim_only)
        w = WordWorker.__new__(WordWorker)  # 绕开 QThread
        return w._filter_whitelist(hits)

    def test_trim_only_true_splits_hit_into_kept_span(self):
        hits = [_match("法定代表人：周超", start=0, end=8)]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")
        self.assertEqual(out[0]["start"], 5)
        self.assertEqual(out[0]["end"], 8)

    def test_trim_only_false_drops_whole_hit(self):
        hits = [_match("法定代表人：周超", start=0, end=8)]
        out = self._filter(hits, trim_only=False)
        self.assertEqual(out, [])

    def test_no_match_passes_through(self):
        hits = [_match("周强", start=0, end=2)]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(out, hits)

    def test_manual_source_passes_through(self):
        hits = [_match("法定代表人：周超", start=0, end=8, source="manual")]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(out, hits)

    def test_empty_kept_span_filtered(self):
        # 白名单覆盖整段 → kept span 列表为空 → 整条剥掉
        hits = [_match("法定代表人", start=0, end=5)]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(out, [])

    def test_multi_span_emit_each(self):
        # "盖章并签名" + wl=["盖章", "签名"] → 两段都被剥, 仅保留 "并"
        hits = [_match("盖章并签名", start=0, end=5)]
        store = BlackWhiteListStore.instance()
        store.load_permanent([], ["盖章", "签名"])
        store.set_trim_only(True)
        w = WordWorker.__new__(WordWorker)
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "并")
        self.assertEqual(out[0]["start"], 2)
        self.assertEqual(out[0]["end"], 3)

    def test_relative_start_offset_preserved(self):
        # hit 在段落中的 start=10, 保留片段是 [12, 14]
        hits = [_match("周超", start=12, end=14)]
        store = BlackWhiteListStore.instance()
        store.load_permanent([], [])  # 无白名单
        store.set_trim_only(True)
        w = WordWorker.__new__(WordWorker)
        out = w._filter_whitelist(hits)
        self.assertEqual(out[0]["start"], 12)
        self.assertEqual(out[0]["end"], 14)


if __name__ == "__main__":
    unittest.main()