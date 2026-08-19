# -*- coding: utf-8 -*-
"""白名单 trim_only 集成测试 — Word + PDF."""
import unittest

from PyQt6.QtCore import QRectF

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.ocr_worker import OCRWorker
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


class _StubOCRWorker(OCRWorker):
    """绕开 QThread, 只调用被测方法."""
    def __init__(self):
        pass

    def _apply_whitelist_filter(self, rects, page_idx=0):
        return OCRWorker._apply_whitelist_filter(self, rects, page_idx)


def _hit(text, source="rule", x=0, y=0, w=100, h=12):
    return {"rect": QRectF(x, y, w, h), "source": source, "text": text, "rule_name": "test"}


class OCRFilterWhitelistTrimTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _filter(self, rects, trim_only, wl=("法定代表人",), resolve_map=None):
        store = BlackWhiteListStore.instance()
        store.load_permanent([], list(wl))
        store.set_trim_only(trim_only)
        w = _StubOCRWorker()
        if resolve_map is not None:
            w._resolve_text_from_rect = lambda rect, page_idx: resolve_map.get(id(rect), "")
        return w._apply_whitelist_filter(rects, page_idx=0)

    def test_text_channel_trim_only_true_emits_sub_rect(self):
        rects = [_hit("法定代表人：周超", x=0, y=0, w=100, h=12)]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")
        # 子矩形 x 应在原矩形内, 宽度约为原 (3/8)
        sub = out[0]["rect"]
        self.assertGreaterEqual(sub.x(), 0)
        self.assertLess(sub.x() + sub.width(), 100.1)
        self.assertAlmostEqual(sub.width(), 100 * 3 / 8, delta=5)

    def test_text_channel_trim_only_false_drops_whole_hit(self):
        rects = [_hit("法定代表人：周超")]
        out = self._filter(rects, trim_only=False)
        self.assertEqual(out, [])

    def test_text_channel_no_match_passes_through(self):
        rects = [_hit("周强")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, rects)

    def test_text_channel_manual_passes_through(self):
        rects = [_hit("法定代表人：周超", source="manual")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, rects)

    def test_text_channel_empty_kept_span_drops_hit(self):
        # 白名单覆盖整段 → spans=[] → 整条剥掉
        rects = [_hit("法定代表人")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, [])

    def test_ocr_channel_resolves_text_then_trims(self):
        # OCR 通道 hit.text="", 通过 _resolve_text_from_rect 查回
        hit = _hit("", source="ocr", x=0, y=0, w=100, h=12)
        out = self._filter(
            [hit],
            trim_only=True,
            resolve_map={id(hit["rect"]): "法定代表人：周超"},
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")

    def test_multi_line_text_in_kept_span_falls_back(self):
        # 保留片段含换行 → 保守回退 → 该片段丢弃
        # 构造一个 hit, 其 text 含换行且 wl 在第一行
        rects = [_hit("法定代表人\n周超")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, [])

    def test_sub_rect_for_text_span_basic(self):
        # 直接验证 _sub_rect_for_text_span 静态方法
        rect = QRectF(0, 0, 100, 12)
        sub = OCRWorker._sub_rect_for_text_span(rect, "abcdef", 2, 4)
        self.assertIsNotNone(sub)
        # CJK 全算 1.0 权重, 比例 2/6 和 2/6
        self.assertAlmostEqual(sub.x(), 100 * 2 / 6, delta=0.01)
        self.assertAlmostEqual(sub.width(), 100 * 2 / 6, delta=0.01)

    def test_sub_rect_for_text_span_cjk_weight(self):
        # CJK 字符权重 1.0, 其它 0.55
        rect = QRectF(0, 0, 100, 12)
        # "法定代表人周超" 全 CJK, 7 字符, kept [5, 7] = "周超"
        # prefix_weight = 5 (全 1.0), match_weight = 2, total = 7
        sub = OCRWorker._sub_rect_for_text_span(rect, "法定代表人周超", 5, 7)
        self.assertIsNotNone(sub)
        self.assertAlmostEqual(sub.x(), 100 * 5 / 7, delta=0.01)
        self.assertAlmostEqual(sub.width(), 100 * 2 / 7, delta=0.01)

    def test_sub_rect_for_text_span_mixed_width(self):
        # 中英文混排, ASCII 字符权重 0.55
        rect = QRectF(0, 0, 100, 12)
        # "a法定代表人" → weights [0.55, 1.0, 1.0, 1.0, 1.0, 1.0] total=5.55
        # kept [1, 4] = "法定代", weights [1,1,1] sum=3
        # prefix_weight = 0.55
        sub = OCRWorker._sub_rect_for_text_span(rect, "a法定代表人", 1, 4)
        self.assertIsNotNone(sub)
        self.assertAlmostEqual(sub.x(), 100 * 0.55 / 5.55, delta=0.1)
        self.assertAlmostEqual(sub.width(), 100 * 3 / 5.55, delta=0.1)

    def test_sub_rect_returns_none_on_multiline_kept(self):
        rect = QRectF(0, 0, 100, 12)
        self.assertIsNone(
            OCRWorker._sub_rect_for_text_span(rect, "ab\ncd", 0, 4)
        )

    def test_sub_rect_returns_none_on_invalid_args(self):
        rect = QRectF(0, 0, 100, 12)
        self.assertIsNone(OCRWorker._sub_rect_for_text_span(None, "abc", 0, 1))
        self.assertIsNone(OCRWorker._sub_rect_for_text_span(rect, "", 0, 0))
        self.assertIsNone(OCRWorker._sub_rect_for_text_span(rect, "abc", 2, 2))


if __name__ == "__main__":
    unittest.main()