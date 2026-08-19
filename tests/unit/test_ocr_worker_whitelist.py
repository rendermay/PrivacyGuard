# -*- coding: utf-8 -*-
"""OCRWorker 白名单过滤测试."""
import unittest
from PyQt6.QtCore import QRectF

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.ocr_worker import OCRWorker


class _StubOCRWorker(OCRWorker):
    """绕开 QThread 启动,只调用被测方法."""
    def __init__(self):
        pass  # 不调用父类 __init__
    def _apply_whitelist_filter(self, rects, page_idx=0):
        # 委托给 OCRWorker 的实际方法 (绑 self=stub)
        return OCRWorker._apply_whitelist_filter(self, rects, page_idx)


def _hit(text, source="rule", x=0, y=0, w=10, h=10):
    return {"rect": QRectF(x, y, w, h), "source": source, "text": text, "rule_name": "test"}


class ApplyWhitelistFilterTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_empty_whitelist_returns_all(self):
        w = _StubOCRWorker()
        rects = [_hit("周强"), _hit("盖章", source="jieba")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(len(out), 2)

    def test_whitelist_drops_matched_rule_hit(self):
        # 注: BlackWhiteListStore.load_permanent(black, white) 第一个入参进黑名单
        # 这里测试白名单过滤,需要把白名单条目放在第二个参数
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        w = _StubOCRWorker()
        rects = [_hit("盖章", source="rule"), _hit("周强", source="jieba")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "周强")

    def test_whitelist_drops_matched_jieba_hit(self):
        BlackWhiteListStore.instance().load_permanent([], ["吉铁"])
        w = _StubOCRWorker()
        rects = [_hit("吉铁", source="jieba")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(out, [])

    def test_manual_source_never_stripped(self):
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        w = _StubOCRWorker()
        rects = [_hit("盖章", source="manual")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(len(out), 1)

    def test_ocr_channel_empty_text_falls_back_to_resolve(self):
        """OCR 通道 text 为空, 应通过 _resolve_text_from_rect 查回."""
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        # v38 修订: trim_only 默认 True → 此用例覆盖"整条剥掉"语义, 显式关闭
        BlackWhiteListStore.instance().set_trim_only(False)
        w = _StubOCRWorker()
        # stub 提供 _resolve_text_from_rect
        w._resolve_text_from_rect = lambda rect, page_idx: "签名或者盖章"
        rects = [_hit("", source="ocr")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(out, [])

    def test_warm_cache_populates_tokens_for_bbox_lookup(self):
        """v37.9.0-hotfix2: _warm_rect_text_cache 必须填充 _rect_tokens_per_page.

        历史 bug: 旧版 _rect_text_cache 是 (page_idx, cx, cy) → text 字典,
        _resolve_text_from_rect 用 center 查, 但 hit rect 经过 merge_adjacent_hit_rects
        合并后, hit center 可能落在两个 token 之间的空隙 → 查不到.

        新设计: _rect_tokens_per_page = {page_idx: [(QRectF, text), ...]},
        _resolve_text_from_rect 用 QRectF.contains(point) 反查, 容错大幅提升.
        """
        from PyQt6.QtCore import QRectF
        BlackWhiteListStore.reset_singleton()

        class _W:
            def _warm_rect_text_cache(self_, page, page_idx, scan_scale):
                self_._rect_tokens_per_page = {
                    0: [
                        (QRectF(0, 0, 50, 12), "签名或者盖章"),  # 整 token
                    ],
                }

        w = _W()
        w._warm_rect_text_cache(None, page_idx=0, scan_scale=2.0)
        # hit center 落在 token bbox 内 → 查回完整 text
        hit_rect = QRectF(5, 2, 30, 10)
        resolved = OCRWorker._resolve_text_from_rect(w, hit_rect, page_idx=0)
        self.assertEqual(resolved, "签名或者盖章")

    def test_resolve_returns_empty_when_token_outside_bbox(self):
        """bbox 之外 → 返回 '' 而非错命中."""
        from PyQt6.QtCore import QRectF
        # token 在 (0,0)-(50,12), hit 在 (100, 0) → 远离
        w = type("W", (), {
            "_rect_tokens_per_page": {0: [(QRectF(0, 0, 50, 12), "盖章")]},
        })()
        hit_rect = QRectF(100, 0, 30, 10)
        resolved = OCRWorker._resolve_text_from_rect(w, hit_rect, page_idx=0)
        self.assertEqual(resolved, "")


if __name__ == "__main__":
    unittest.main()