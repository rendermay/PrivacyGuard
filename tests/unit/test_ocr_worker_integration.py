# -*- coding: utf-8 -*-
"""OCRWorker 集成: _process_page 中 white/black list 串联."""
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PyQt6.QtCore import QRectF

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.ocr_worker import OCRWorker


class _ProcessPageListTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_whitelist_strips_before_blacklist_injects(self):
        """黑名单含 "盖章"、白名单也含 "盖章" → 不应有 blacklist hit 注入."""
        BlackWhiteListStore.instance().load_permanent(["盖章"], ["盖章"])

        # 构造 stub OCRWorker, 不真正 OCR
        w = OCRWorker.__new__(OCRWorker)
        w.calculate_sub_rect = MagicMock(return_value=QRectF(10, 20, 30, 10))
        w._ocr_full_page_tokens = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])
        w._ocr_engine = MagicMock()
        # Heads-up fix: 原 brief 没 stub 这两个, 但实现内会调用 → 异常路径返回 [],
        # 与 len(blacklist_hits)==1 不符. 加上 stub 保证 OCR 走完整路径.
        w._render_full_page_bgr = MagicMock(
            return_value=np.zeros((100, 100, 3), dtype=np.uint8)
        )
        w._ocr_clip = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])

        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=595, y1=842)

        blacklist_hits = w._collect_blacklist_hits(
            page, page_idx=0, blacklist=["盖章"], scan_scale=2.0
        )
        # _collect_blacklist_hits 本身不剥 whitelist — 由 _process_page 串联
        self.assertEqual(len(blacklist_hits), 1)

        # 模拟串联: blacklist 注入后再过一次 whitelist 过滤
        out = w._apply_whitelist_filter(blacklist_hits, page_idx=0)
        # whitelist 包含 "盖章" → blacklist 注入被剥掉
        self.assertEqual(out, [])

    def test_blacklist_injects_when_whitelist_empty(self):
        """白名单为空 → blacklist 注入应保留."""
        BlackWhiteListStore.instance().load_permanent(["盖章"], [])

        w = OCRWorker.__new__(OCRWorker)
        w.calculate_sub_rect = MagicMock(return_value=QRectF(10, 20, 30, 10))
        w._ocr_full_page_tokens = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])
        w._ocr_engine = MagicMock()
        # Heads-up fix: 补齐依赖
        w._render_full_page_bgr = MagicMock(
            return_value=np.zeros((100, 100, 3), dtype=np.uint8)
        )
        w._ocr_clip = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])

        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=595, y1=842)

        hits = w._collect_blacklist_hits(
            page, page_idx=0, blacklist=["盖章"], scan_scale=2.0
        )
        out = w._apply_whitelist_filter(hits, page_idx=0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "blacklist")


if __name__ == "__main__":
    unittest.main()