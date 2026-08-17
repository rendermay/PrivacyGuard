# -*- coding: utf-8 -*-
"""OCRWorker.page_result_signal payload 应携带 source 字段.

Wave 2.1 Task 3: page_result_signal 从 list[QRectF] 升级到 list[dict],
每项含 {rect: QRectF, source: str, text: str, rule_name: str}.
Task 4 消费者 (MainWindow._on_ocr_page_result) 依赖 source 区分
manual/ocr/jieba/seal.
"""
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QRectF


class OCRWorkerPayloadTest(unittest.TestCase):

    def test_text_pdf_rule_hits_emitted_as_dicts(self):
        """self.rules 命中应以 dict 形式 emit, source='rule'."""
        from privacyguard.workers.ocr_worker import OCRWorker

        # 模拟 collect_text_pdf_hit_boxes 返回 6-tuple (x, y, w, h, text, rule_name)
        def fake_text_pdf(page, patterns, page_text=None):
            if patterns == ["rule_a"]:
                return [(10.0, 20.0, 30.0, 5.0, "周强", "rule_a")]
            return []

        fake_page = MagicMock()
        fake_page.get_text.return_value = "周强 13812345678"
        # page.rect 用作兜底 image_clip_rects (page_text 非空,不进此分支)
        fake_page.rect.x0 = 0.0
        fake_page.rect.y0 = 0.0
        fake_page.rect.x1 = 100.0
        fake_page.rect.y1 = 100.0

        mock_ocr_engine = MagicMock()

        with patch("privacyguard.workers.ocr_worker.collect_text_pdf_hit_boxes",
                  side_effect=fake_text_pdf), \
            patch("privacyguard.workers.ocr_worker.collect_embedded_image_clip_rects",
                  return_value=[]), \
            patch("privacyguard.workers.ocr_worker.collect_image_block_ocr_hits",
                  return_value=[]):
            worker = OCRWorker(
                pdf_path="/dev/null",
                rules=["rule_a"],
                use_enhance=False,
                custom_keywords="",
                scan_scale=1.0,
                off_x=0,
                off_w=0,
                enable_name_recognition=False,
            )

            captured = []
            worker.page_result_signal.connect(
                lambda idx, hits: captured.append((idx, hits))
            )

            worker._process_page(fake_page, 0, ocr_engine=mock_ocr_engine, scan_scale=1.0)

        self.assertEqual(len(captured), 1, f"应 emit 1 次, 实得 {len(captured)}")
        page_idx, hits = captured[0]
        self.assertEqual(page_idx, 0)
        self.assertGreater(len(hits), 0, "应有至少 1 个 hit")

        # 验证 dict 形状
        hit = hits[0]
        self.assertIn("rect", hit)
        self.assertIn("source", hit)
        self.assertIn("text", hit)
        self.assertIn("rule_name", hit)
        self.assertIsInstance(hit["rect"], QRectF)

        # 验证 self.rules 路径 -> source='rule'
        rule_hits = [h for h in hits if h["source"] == "rule"]
        self.assertEqual(len(rule_hits), 1, "rules 应有 1 个 source='rule' hit")
        self.assertEqual(rule_hits[0]["text"], "周强")
        self.assertEqual(rule_hits[0]["rule_name"], "rule_a")

    def test_custom_keyword_hits_marked_source_ocr(self):
        """self.custom_keywords 命中应 source='ocr' (与 self.rules 区分)."""
        from privacyguard.workers.ocr_worker import OCRWorker

        def fake_text_pdf(page, patterns, page_text=None):
            if patterns == ["custom_phone"]:
                return [(50.0, 60.0, 80.0, 5.0, "13812345678", "custom_phone")]
            return []

        fake_page = MagicMock()
        fake_page.get_text.return_value = "周强 13812345678"
        fake_page.rect.x0 = 0.0
        fake_page.rect.y0 = 0.0
        fake_page.rect.x1 = 100.0
        fake_page.rect.y1 = 100.0

        mock_ocr_engine = MagicMock()

        with patch("privacyguard.workers.ocr_worker.collect_text_pdf_hit_boxes",
                  side_effect=fake_text_pdf), \
            patch("privacyguard.workers.ocr_worker.collect_embedded_image_clip_rects",
                  return_value=[]), \
            patch("privacyguard.workers.ocr_worker.collect_image_block_ocr_hits",
                  return_value=[]):
            worker = OCRWorker(
                pdf_path="/dev/null",
                rules=[],
                use_enhance=False,
                custom_keywords="custom_phone",
                scan_scale=1.0,
                off_x=0,
                off_w=0,
                enable_name_recognition=False,
            )

            captured = []
            worker.page_result_signal.connect(
                lambda idx, hits: captured.append((idx, hits))
            )

            worker._process_page(fake_page, 0, ocr_engine=mock_ocr_engine, scan_scale=1.0)

        self.assertEqual(len(captured), 1)
        _, hits = captured[0]
        ocr_hits = [h for h in hits if h["source"] == "ocr"]
        self.assertEqual(len(ocr_hits), 1, "custom_keywords 应有 1 个 source='ocr' hit")
        self.assertEqual(ocr_hits[0]["text"], "13812345678")
        self.assertEqual(ocr_hits[0]["rule_name"], "custom_phone")


if __name__ == "__main__":
    unittest.main()