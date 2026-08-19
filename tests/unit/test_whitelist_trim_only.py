# -*- coding: utf-8 -*-
"""白名单 trim_only 集成测试 — Word + PDF."""
import unittest

from PyQt6.QtCore import QRectF

from secureredact.redaction.black_white_list_store import BlackWhiteListStore
from secureredact.workers.ocr_worker import OCRWorker
from secureredact.workers.word_worker import WordWorker


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

    def test_ocr_channel_resolves_text_then_drops_when_wl_in_resolved(self):
        """v38.0.1 hotfix: image-channel hit (text="") + wl 在反查文本中 → 整条 drop (v37.9.0 行为).

        不再 trim — 避免 sub-rect 错位 (custom_keyword 命中「签名或者盖章」中的「盖章」子串时,
        resolve 拿到整条 token, trim 会把「签名或者」画到「盖章」位置).
        """
        hit = _hit("", source="ocr", x=0, y=0, w=100, h=12)
        out = self._filter(
            [hit],
            trim_only=True,
            resolve_map={id(hit["rect"]): "法定代表人：周超"},
        )
        self.assertEqual(out, [])

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


class OCRFilterImageChannelEmptyTextTest(unittest.TestCase):
    """v38.0.1 hotfix: image-channel / seal hit (原 text 空) 走 v37.9.0 整条剥掉.

    不做 trim — _resolve_text_from_rect 反查可能返回比原 hit rect 更长的 OCR token
    (例如 custom_keyword 命中「签名或者盖章」中的「盖章」子串), 此时 _sub_rect_for_text_span
    用原小 rect 做权重切分会把「签名或者」画到「盖章」位置, 导致错误脱敏.

    ┌────────────────────────────────────────────────────────────────────┐
    │ ⚠️  本测试是 v38.0.1 hotfix 的回归锁 — 删除/修改前必须先实现            │
    │ collect_image_block_ocr_hits 返回 matched 子串 (而非仅 rect), 让     │
    │ hit.text 携带精确 keyword, 避免 resolve 反查歧义.                  │
    │ 详见 OCRWorker._apply_whitelist_filter 顶部 docstring +              │
    │ CHANGELOG.md v38.0.0 「已知限制」段.                                  │
    └────────────────────────────────────────────────────────────────────┘
    """

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _filter(self, rects, wl, trim_only):
        store = BlackWhiteListStore.instance()
        store.load_permanent([], wl)
        store.set_trim_only(trim_only)
        w = _StubOCRWorker()
        w._resolve_text_from_rect = lambda rect, page_idx: "签名或者盖章"
        return w._apply_whitelist_filter(rects, page_idx=0)

    def test_empty_text_resolved_text_contains_wl_dropped_under_trim(self):
        """v38.0.1 hotfix: image-channel hit (text="") + wl 含子串 → 整条 drop, 即使 trim_only=True."""
        hit = _hit("", source="ocr", x=472, y=455, w=28, h=20)
        out = self._filter([hit], wl=["盖章"], trim_only=True)
        self.assertEqual(out, [], "image-channel hit 应被整条 drop, 而不是错误 trim")

    def test_empty_text_resolved_no_wl_kept_under_trim(self):
        """image-channel hit (text="") + resolve 文本不含 wl → 原样保留, 即便 trim_only=True."""
        hit = _hit("", source="ocr", x=100, y=200, w=50, h=12)
        out = self._filter([hit], wl=["不相关"], trim_only=True)
        self.assertEqual(out, [hit])

    def test_text_channel_hit_still_trims_correctly(self):
        """text-channel hit (text 非空) 继续走 trim 行为 (spec 主路径不被影响)."""
        store = BlackWhiteListStore.instance()
        store.load_permanent([], ["法定代表人"])
        store.set_trim_only(True)
        w = _StubOCRWorker()
        hit = _hit("法定代表人：周超", x=0, y=0, w=200, h=12)
        out = w._apply_whitelist_filter([hit], page_idx=0)
        # text 非空 → 走 trim → 保留 「：周超」 子段
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")


if __name__ == "__main__":
    unittest.main()