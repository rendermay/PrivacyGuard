# -*- coding: utf-8 -*-
"""MainWindow PDF 端 page_data + filtered_hits 接入测试.

Wave 2.2 Task 4:
- _receive_page_hits 替代 _on_ocr_page_result,接受 dict 列表
- page_data[page_idx]['ocr'] 现在存 dict 列表
- 过滤走 HitOverrideStore.filtered_hits
- 不依赖 QApplication 真正启动
"""
import unittest

from PyQt6.QtCore import QRectF

from privacyguard.redaction.hit_ref import HitRef
from privacyguard.redaction.override_store import HitOverrideStore


class PDFSourceFieldTest(unittest.TestCase):

    def setUp(self):
        # 每次测试重置 store 单例,避免污染
        HitOverrideStore.reset_singleton()

    def tearDown(self):
        HitOverrideStore.reset_singleton()

    def _make_module(self):
        """返回 main 模块对象,触发模块加载(需要时只测模块级函数)。"""
        import importlib
        return importlib.import_module("main")

    def test_page_data_stores_dict_list(self):
        """_receive_page_hits 应把 raw dict 列表存进 page_data[idx]['ocr']."""
        from main import MainWindow

        store = HitOverrideStore.instance()
        rect = QRectF(10, 20, 30, 5)
        raw_hits = [
            {"rect": rect, "source": "jieba", "text": "周强", "rule_name": "姓名"},
            {"rect": QRectF(50, 60, 25, 5), "source": "ocr", "text": "13800000000",
             "rule_name": "手机号码"},
        ]
        # 模拟 _receive_page_hits 的副作用:raw 全量存 page_data
        page_data = {0: {"ocr": list(raw_hits), "manual": []}}

        # _filter_hits_to_rects 应无 ignore 时返回所有 rect
        kept_rects = MainWindow._filter_hits_to_rects(
            page_data[0]["ocr"],
            store=store,
            location="page_0",
            doc_hash="a1b2c3d4",
        )
        self.assertEqual(len(kept_rects), 2)
        self.assertEqual(kept_rects[0], rect)
        self.assertEqual(kept_rects[1], QRectF(50, 60, 25, 5))

    def test_filtered_hits_drops_ignored(self):
        """当 store 中已 ignore(周强) 时,_filter_hits_to_rects 应剔除。"""
        from main import MainWindow

        store = HitOverrideStore.instance()
        ref = HitRef("a1b2c3d4", "page_0", 10, 12, "周强", "jieba")
        store.ignore(ref, scope="session")

        raw_hits = [
            {"rect": QRectF(10, 20, 30, 5), "source": "jieba", "text": "周强",
             "rule_name": "姓名", "start": 10, "end": 12},
            {"rect": QRectF(50, 60, 25, 5), "source": "ocr", "text": "李四",
             "rule_name": "姓名", "start": 20, "end": 22},
        ]
        page_data = {0: {"ocr": list(raw_hits), "manual": []}}
        # page_data 应保留 raw 全部(便于撤销后再次出现)
        self.assertEqual(len(page_data[0]["ocr"]), 2)

        kept_rects = MainWindow._filter_hits_to_rects(
            page_data[0]["ocr"],
            store=store,
            location="page_0",
            doc_hash="a1b2c3d4",
        )
        self.assertEqual(len(kept_rects), 1, f"应仅剩李四;实得 {len(kept_rects)} 个")
        self.assertEqual(kept_rects[0], QRectF(50, 60, 25, 5))

    def test_filtered_hits_keeps_manual(self):
        """manual rect 应永远保留,即使 start/end 与被 ignore 重叠。"""
        from main import MainWindow

        store = HitOverrideStore.instance()
        # ignore 一个 jieba hit
        ref = HitRef("a1b2c3d4", "page_0", 10, 12, "周强", "jieba")
        store.ignore(ref, scope="session")

        # manual 同样 start/end,应被保留
        raw_hits = [
            {"rect": QRectF(10, 20, 30, 5), "source": "manual", "text": "周强",
             "rule_name": "manual", "start": 10, "end": 12},
        ]
        kept_rects = MainWindow._filter_hits_to_rects(
            raw_hits,
            store=store,
            location="page_0",
            doc_hash="a1b2c3d4",
        )
        self.assertEqual(len(kept_rects), 1, "manual 不应被 filter 剔除")
        self.assertEqual(kept_rects[0], QRectF(10, 20, 30, 5))


if __name__ == "__main__":
    unittest.main()