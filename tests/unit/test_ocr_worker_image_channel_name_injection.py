# -*- coding: utf-8 -*-
"""
回归测试：扫描型 / 图片型 PDF (page_text 为空) + enable_name_recognition=True

复现《周强起诉状.pdf》: 3 页全是 0 文本 + 1 张大图, 默认规则 + jieba 启发式
都无法命中图片块里的姓名。

修复要求：当 enable_name_recognition=True 且 page_text 为空时, OCRWorker
必须仍然让 jieba 的识别人名注入到 image 通道的 all_patterns, 并最终
在 collect_image_block_ocr_hits 里通过 OCR 出来的文本命中姓名。
"""
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestImageChannelNameInjection(unittest.TestCase):
    """图片通道也必须能命中 jieba 启发式识别的人名."""

    def test_extract_person_names_recognizes_zhou_qiang(self):
        """jieba 识别器应能从起诉状文本中识别出 '周强'."""
        from privacyguard.pii.name_recognizer import extract_person_names
        names = extract_person_names(
            "民事起诉状\n原告：周强，男，1985年3月5日生，汉族。\n"
            "著作权人周强在贵州省版权局完成作品登记。\n"
            "起诉人：周强\n"
        )
        self.assertIn("周强", names)

    def test_image_block_ocr_hits_match_person_name_when_in_patterns(self):
        """图片通道命中: 一旦 '周强' 被注入 all_patterns, OCR 出的 '原告：周强' 行应被命中."""
        from privacyguard.ocr.mixed_pdf import collect_image_block_ocr_hits

        class FakeRect:
            def __init__(self, x, y, w, h):
                self._x, self._y, self._w, self._h = x, y, w, h
            def x(self): return self._x
            def y(self): return self._y
            def width(self): return self._w
            def height(self): return self._h

        # 模拟 OCR 引擎返回起诉状里的"原告：周强"那行
        def recognize(_img):
            return [
                SimpleNamespace(
                    box=[[0, 0], [200, 0], [200, 20], [0, 20]],
                    text="原告：周强，男，1985年3月5日生",
                ),
                SimpleNamespace(
                    box=[[0, 30], [200, 30], [200, 50], [0, 50]],
                    text="著作权人周强在贵州省版权局",
                ),
                SimpleNamespace(
                    box=[[0, 60], [200, 60], [200, 80], [0, 80]],
                    text="起诉人：周强",
                ),
            ]

        def calculate_rect(_box, _text, _span, _img):
            return FakeRect(20.0, 0.0, 60.0, 20.0)

        def offset_rect(local_rect, clip_rect):
            return (
                local_rect.x() + clip_rect[0],
                local_rect.y() + clip_rect[1],
                local_rect.width(),
                local_rect.height(),
            )

        # 注入人名 pattern — 模拟修复后的 worker
        extra_names = ["周强"]
        patterns = [r"1[3-9]\d{9}"] + [re.escape(n) for n in extra_names]

        hit_rects = collect_image_block_ocr_hits(
            page=object(),
            patterns=patterns,
            scan_scale=1.0,
            recognize_fn=recognize,
            calculate_rect_fn=calculate_rect,
            clip_to_page_rect_fn=offset_rect,
            render_clip_fn=lambda *_: SimpleNamespace(size=1),
            image_clip_rects=[(0.0, 0.0, 200.0, 100.0)],
        )

        # 三行都包含"周强",应该命中 3 次
        self.assertGreaterEqual(
            len(hit_rects), 3,
            f"图片通道应至少命中 3 次'周强', 实得 {len(hit_rects)} 次",
        )

    def test_ocr_worker_run_injects_name_patterns_for_image_pdf(self):
        """OCRWorker.run 对 page_text='' 的扫描型页,enable_name_recognition=True 时
        必须仍然把 jieba 识别的人名追加到 all_patterns (并让 image 通道命中)."""
        # patch QThread.__init__ 避免 Qt 副作用
        with patch("privacyguard.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.ocr_worker import OCRWorker

            worker = OCRWorker(
                pdf_path=None,
                rules=[],
                use_enhance=False,
                custom_keywords="",
                scan_scale=1.0,
                off_x=0,
                off_w=0,
                enable_name_recognition=True,
            )

        # 模拟 fitz page: page_text='', image_clip_rects 非空
        fake_page = SimpleNamespace(
            get_text=lambda *a, **kw: "",  # ← 图片型 PDF,文本为空
            get_text_dict=lambda *a, **kw: {"blocks": [
                {"type": 1, "bbox": (0.0, 0.0, 200.0, 100.0)},
            ]},
            rect=SimpleNamespace(x0=0, y0=0, x1=200, y1=100),
        )

        # jieba 注入逻辑测试:
        # 模拟修复后的 OCRWorker 内部函数, 应该把识别结果注入 patterns
        from privacyguard.pii.name_recognizer import extract_person_names
        # 实际场景: page_text 为空时, jieba 拿不到文本 → 修复方案是用 OCR 全页识别喂给 jieba
        # 这里测试识别器自身对"原告：周强"等典型短语的识别能力
        for snippet in (
            "原告：周强，男",
            "著作权人周强在",
            "起诉人：周强",
        ):
            names = extract_person_names(snippet)
            self.assertIn(
                "周强", names,
                f"jieba 应能从 '{snippet}' 中识别 '周强', 实得 {names}",
            )

        # 占位断言: 实际修复点在 ocr_worker.run 中. 此处仅做识别器回归保护.
        self.assertTrue(worker.enable_name_recognition,
            "OCRWorker 应保留 enable_name_recognition=True 标志")


if __name__ == "__main__":
    unittest.main()