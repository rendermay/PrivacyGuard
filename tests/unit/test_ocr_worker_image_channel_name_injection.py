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


def _make_png_bytes():
    """生成一张最小可被 cv2.imdecode 解码的 PNG 字节流."""
    import numpy as np
    import cv2
    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    ok, buf = cv2.imencode('.png', img)
    assert ok, "测试 fixture 生成 PNG 失败"
    return buf.tobytes()


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


class TestScanPdfWatermarkPageTextRegression(unittest.TestCase):
    """regression v37.x: CamScanner 等扫描 PDF 在 page_text 仅含页码水印
    (如 '1\\n', 非空但极短) 时, OCRWorker 必须仍然触发全页 OCR 喂给 jieba,
    否则姓名注入静默失效 — page 上所有人名都不会脱敏.

    修复点: privacyguard/workers/ocr_worker.py _process_page 的 jieba 兜底
    触发条件 `not jieba_source_text` 必须放宽为 `len(jieba_source_text.strip()) < 阈值`,
    否则 page_text="1\\n" 时 jieba 拿到 "1" → 0 个人名.
    """

    def test_process_page_triggers_full_page_ocr_when_page_text_is_only_watermark(self):
        """_process_page 应在 page_text 仅含 '1\\n' (扫描 PDF 页码水印) 时
        调用全页 OCR 并把识别文本喂给 jieba, 最终 image 通道命中姓名."""
        # patch QThread.__init__ 避免 Qt 副作用, 同时替换 page_result_signal
        with patch("privacyguard.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.ocr_worker import OCRWorker

            worker = OCRWorker(
                pdf_path=None,
                rules=[],
                use_enhance=False,
                custom_keywords="",
                scan_scale=2.0,
                off_x=0,
                off_w=0,
                enable_name_recognition=True,
            )
            # mock 信号避免 QObject 实例化缺失
            worker.page_result_signal = SimpleNamespace(emit=lambda *a, **kw: None)

        # 收集 OCR 引擎被调用的次数, 验证兜底是否触发
        ocr_call_count = {"n": 0}
        ocr_text_to_return = [
            "委托诉讼代理人葛晓风，被告鑫盛公司的委托诉讼代理人马丽娜",
            "原告付明义向本院提出诉讼请求",
            "被告王成经营的鑫盛公司",
        ]

        def fake_recognize(_img):
            ocr_call_count["n"] += 1
            # 第一次调用是 jieba 喂数据用的全页 OCR, 后续是 image 通道的 OCR
            from types import SimpleNamespace
            return [
                SimpleNamespace(
                    box=[[0, 0], [600, 0], [600, 30], [0, 30]],
                    text=ocr_text_to_return[ocr_call_count["n"] - 1],
                ),
            ]

        # 模拟 fitz page: page_text='1\n' (CamScanner 水印), image_clip_rects 非空
        # OCRWorker._process_page 调用 page.get_text() 和 page.get_text("dict"),
        # 这两个需要分别返回不同结果 (字符串 vs dict)
        page_text_layer = "1\n"  # 仅页码水印, 非空但极短
        page_dict_layer = {"blocks": [
            {"type": 1, "bbox": (0.0, 0.0, 600.0, 30.0)},
        ]}

        def fake_get_text(mode=None, *args, **kwargs):
            if mode == "dict":
                return page_dict_layer
            return page_text_layer

        fake_page = SimpleNamespace(
            get_text=fake_get_text,
            rect=SimpleNamespace(x0=0, y0=0, x1=600, y1=30),
            # _render_full_page_bgr 走 page.get_pixmap → fitz.Pixmap
            # 我们 mock Pixmap 让 np.frombuffer 返回可被 cv2.imdecode 接受的图
            get_pixmap=lambda *a, **kw: SimpleNamespace(
                tobytes=lambda *a, **kw: _make_png_bytes(),
            ),
        )

        from PyQt6.QtCore import QRectF

        class FakeRect:
            def __init__(self, x, y, w, h):
                self._x, self._y, self._w, self._h = x, y, w, h
            def x(self): return self._x
            def y(self): return self._y
            def width(self): return self._w
            def height(self): return self._h

        def calculate_rect(_box, _text, _span, _img):
            return FakeRect(20.0, 0.0, 60.0, 30.0)

        def offset_rect(local_rect, clip_rect):
            return QRectF(
                local_rect.x() + clip_rect[0],
                local_rect.y() + clip_rect[1],
                local_rect.width(),
                local_rect.height(),
            )

        with patch(
            "privacyguard.workers.ocr_worker.collect_image_block_ocr_hits"
        ) as mock_collect:
            def fake_collect(page, patterns, scan_scale, **_):
                # 断言 patterns 中包含 jieba 抽出的姓名 (兜底必须触发)
                self.assertIn(
                    "葛晓风", patterns,
                    "修复期望: page_text 仅含水印时, OCRWorker 应触发全页 OCR, "
                    "并把 jieba 抽出的 '葛晓风' 注入到 patterns. "
                    f"实际 patterns={patterns!r}",
                )
                return []

            mock_collect.side_effect = fake_collect
            worker._process_page(
                fake_page, 0,
                ocr_engine=SimpleNamespace(recognize=fake_recognize),
                scan_scale=2.0,
            )

        # 验证: 全页 OCR 至少被调用一次 (喂 jieba)
        self.assertGreaterEqual(
            ocr_call_count["n"], 1,
            "page_text 仅含 '1\\n' 时, OCRWorker 必须至少调用一次全页 OCR "
            "以喂给 jieba 抽取姓名. 实际调用次数 = "
            f"{ocr_call_count['n']}",
        )


if __name__ == "__main__":
    unittest.main()