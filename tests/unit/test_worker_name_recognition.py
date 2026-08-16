# -*- coding: utf-8 -*-
"""
Worker 默认 OFF 等价性测试 + enable_name_recognition=True 注入测试.

覆盖 OCRWorker / WordWorker 两个 worker 的 __init__ 路径.
策略: 直接 patch 类继承的 QThread.__init__ 为 noop,避免真实 Qt 初始化.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestOCRWorkerDefaultOff(unittest.TestCase):
    """OCRWorker 默认 OFF 时,__init__ 应快速完成,不触发 jieba 冷启动."""

    def test_default_off_passes_through(self):
        import time
        # patch QThread.__init__ 为 noop;避免 Qt 实例化副作用
        with patch("privacyguard.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.ocr_worker import OCRWorker
            start = time.perf_counter()
            OCRWorker(
                pdf_path=None,
                rules=[r"\d{18}"],
                use_enhance=False,
                custom_keywords="张三",
                scan_scale=1.5,
                off_x=0,
                off_w=0,
                use_char_level_ocr=False,
                seal_detection_enabled=False,
                box_adjust_ratio=0.0,
                enable_name_recognition=False,  # 关键:默认 False
            )
            elapsed = time.perf_counter() - start
        # 默认 OFF 应在 50ms 内完成 (无 jieba 冷启动)
        self.assertLess(elapsed, 0.05,
            f"默认 OFF 初始化耗时 {elapsed*1000:.0f}ms 超过预算 50ms")

    def test_default_off_does_not_set_enable_flag(self):
        with patch("privacyguard.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.ocr_worker import OCRWorker
            worker = OCRWorker(
                pdf_path=None,
                rules=[],
                use_enhance=False,
                custom_keywords="",
                scan_scale=1.5,
                off_x=0,
                off_w=0,
                use_char_level_ocr=False,
                seal_detection_enabled=False,
                box_adjust_ratio=0.0,
            )
            self.assertFalse(worker.enable_name_recognition)


class TestOCRWorkerNameRecognitionOn(unittest.TestCase):
    """OCRWorker enable_name_recognition=True 时,__init__ 不立即跑 jieba.
    jieba 调用推迟到每个 page_text 处理时."""

    def test_flag_propagates_to_self(self):
        with patch("privacyguard.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.ocr_worker import OCRWorker
            worker = OCRWorker(
                pdf_path=None,
                rules=[],
                use_enhance=False,
                custom_keywords="",
                scan_scale=1.5,
                off_x=0,
                off_w=0,
                use_char_level_ocr=False,
                seal_detection_enabled=False,
                box_adjust_ratio=0.0,
                enable_name_recognition=True,
            )
            self.assertTrue(worker.enable_name_recognition)


class TestWordWorkerDefaultOff(unittest.TestCase):
    """WordWorker 默认 OFF 等价性."""

    def test_default_off_passes_through(self):
        import time
        with patch("privacyguard.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.word_worker import WordWorker
            start = time.perf_counter()
            WordWorker(
                word_doc=None,
                word_data={"p0": {"text": "原告周强"}},
                rules=[],
                custom_keywords="",
                replacement_text="[已脱敏]",
            )
            elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.05,
            f"WordWorker 默认 OFF 初始化耗时 {elapsed*1000:.0f}ms 超过预算 50ms")

    def test_default_off_does_not_set_enable_flag(self):
        with patch("privacyguard.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.word_worker import WordWorker
            worker = WordWorker(
                word_doc=None,
                word_data={},
                rules=[],
                custom_keywords="",
                replacement_text="[已脱敏]",
            )
            self.assertFalse(worker.enable_name_recognition)

    def test_flag_propagates_to_self(self):
        with patch("privacyguard.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from privacyguard.workers.word_worker import WordWorker
            worker = WordWorker(
                word_doc=None,
                word_data={},
                rules=[],
                custom_keywords="",
                replacement_text="[已脱敏]",
                enable_name_recognition=True,
            )
            self.assertTrue(worker.enable_name_recognition)


class TestWorkerKeywordDedup(unittest.TestCase):
    """识别的人名与已有 custom_keywords 重复时,识别器内部已去重."""

    def test_dedup_in_recognizer(self):
        from privacyguard.pii.name_recognizer import extract_person_names

        names = extract_person_names("原告：周强，男，汉族。周强已在庭。")
        self.assertEqual(names.count("周强"), 1)


if __name__ == "__main__":
    unittest.main()