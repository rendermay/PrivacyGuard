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
        w = _StubOCRWorker()
        # stub 提供 _resolve_text_from_rect
        w._resolve_text_from_rect = lambda rect, page_idx: "签名或者盖章"
        rects = [_hit("", source="ocr")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()