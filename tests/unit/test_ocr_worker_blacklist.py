# -*- coding: utf-8 -*-
"""OCRWorker 黑名单注入测试."""
import unittest
from unittest.mock import patch, MagicMock

import numpy as np
from PyQt6.QtCore import QRectF

from secureredact.redaction.black_white_list_store import BlackWhiteListStore
from secureredact.workers.ocr_worker import OCRWorker


class _DedupTest(unittest.TestCase):
    """先测纯函数 _dedupe_overlapping."""

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _hit(self, x, y, w, h, text="盖章", source="blacklist"):
        return {"rect": QRectF(x, y, w, h), "source": source, "text": text, "rule_name": "黑名单:盖章"}

    def test_dedupe_overlapping_merges(self):
        # 两个相邻 token 都命中 "盖章", 应合并为一个矩形
        h1 = self._hit(10, 20, 10, 10)
        h2 = self._hit(20, 20, 10, 10)
        out = OCRWorker._dedupe_overlapping([h1, h2])
        self.assertEqual(len(out), 1)
        merged = out[0]["rect"]
        self.assertEqual(merged.x(), 10)
        self.assertEqual(merged.x() + merged.width(), 30)
        self.assertEqual(merged.y(), 20)
        self.assertEqual(merged.y() + merged.height(), 30)

    def test_dedupe_keeps_non_overlapping(self):
        h1 = self._hit(10, 20, 10, 10)
        h2 = self._hit(100, 200, 10, 10)
        out = OCRWorker._dedupe_overlapping([h1, h2])
        self.assertEqual(len(out), 2)

    def test_dedupe_handles_empty(self):
        self.assertEqual(OCRWorker._dedupe_overlapping([]), [])


class _CollectBlacklistTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_empty_blacklist_returns_empty(self):
        w = OCRWorker.__new__(OCRWorker)  # 绕开 QThread __init__
        page = MagicMock()
        out = w._collect_blacklist_hits(page, page_idx=0, blacklist=[], scan_scale=2.0)
        self.assertEqual(out, [])

    @patch("secureredact.workers.ocr_worker.collect_embedded_image_clip_rects")
    def test_blacklist_injects_hit_for_matching_token(self, mock_collect):
        mock_collect.return_value = [(0, 0, 100, 100)]
        # 构造 stub OCR: 返回一个含 "盖章" 的 token
        w = OCRWorker.__new__(OCRWorker)
        # 补齐 brief 中缺失的依赖 stub:
        # 1) _ocr_engine: 实现内 early-exit 守卫需要非 None
        w._ocr_engine = MagicMock()
        # 2) _render_full_page_bgr: MagicMock page 喂给 fitz 会崩, 喂 numpy 数组
        w._render_full_page_bgr = MagicMock(
            return_value=np.zeros((100, 100, 3), dtype=np.uint8)
        )
        w.calculate_sub_rect = MagicMock(return_value=QRectF(10, 20, 30, 10))
        # v1.1.11-hotfix: 实现统一走 _ocr_full_page_tokens 而非 _ocr_clip.
        w._ocr_full_page_tokens = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])
        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=595, y1=842)

        out = w._collect_blacklist_hits(page, page_idx=0, blacklist=["盖章"], scan_scale=2.0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "blacklist")

    @patch("secureredact.workers.ocr_worker.collect_embedded_image_clip_rects")
    def test_no_attribute_error_when_ocr_clip_undefined(self, mock_collect):
        """v1.1.11-hotfix 回归测试: _collect_blacklist_hits 不应依赖不存在的 _ocr_clip.

        历史 bug: 当 clip_rects 只有一个时, 旧实现调用 self._ocr_clip(...), 触发
        AttributeError 被 try/except 静默吞掉, 导致生产中黑名单注入从未生效.
        此测试确保方法不引用 _ocr_clip, 即便该方法不存在也能正常工作.
        """
        # 关键: 不设置 w._ocr_clip, 验证方法体不调用它
        mock_collect.return_value = [(0, 0, 100, 100)]
        w = OCRWorker.__new__(OCRWorker)
        w._ocr_engine = MagicMock()
        w._render_full_page_bgr = MagicMock(
            return_value=np.zeros((100, 100, 3), dtype=np.uint8)
        )
        w.calculate_sub_rect = MagicMock(return_value=QRectF(10, 20, 30, 10))
        # 关键 stub: _ocr_full_page_tokens 是真实 OCR path
        w._ocr_full_page_tokens = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])
        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=595, y1=842)

        out = w._collect_blacklist_hits(
            page, page_idx=0, blacklist=["盖章"], scan_scale=2.0
        )
        # 不抛 AttributeError, 且黑名单命中被注入
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "blacklist")
        self.assertEqual(out[0]["text"], "盖章")
        self.assertEqual(out[0]["text"], "盖章")
        self.assertIn("盖章", out[0]["rule_name"])


if __name__ == "__main__":
    unittest.main()