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
        with patch("secureredact.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.ocr_worker import OCRWorker
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
        with patch("secureredact.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.ocr_worker import OCRWorker
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
        with patch("secureredact.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.ocr_worker import OCRWorker
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
        with patch("secureredact.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.word_worker import WordWorker
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
        with patch("secureredact.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.word_worker import WordWorker
            worker = WordWorker(
                word_doc=None,
                word_data={},
                rules=[],
                custom_keywords="",
                replacement_text="[已脱敏]",
            )
            self.assertFalse(worker.enable_name_recognition)

    def test_flag_propagates_to_self(self):
        with patch("secureredact.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.word_worker import WordWorker
            worker = WordWorker(
                word_doc=None,
                word_data={},
                rules=[],
                custom_keywords="",
                replacement_text="[已脱敏]",
                enable_name_recognition=True,
            )
            self.assertTrue(worker.enable_name_recognition)


class TestWorkerNameContextExtraTokens(unittest.TestCase):
    """v1.1.14: Worker 接收 name_context_extra_tokens 参数并透传给
    extract_person_names. 动机: 接通 config.json 的
    redaction.name_context.extra_tokens 配置项。

    注意: 复用同文件前序测试的 patch 模式 (patch 小写子模块路径),
    依赖套件中前序测试已触发子模块 import (走 sys.modules 缓存).
    为单文件 / 单测命令下也能运行, setUp 显式尝试 import 并在
    PyQt6 缺失时 skip 整个 class。
    """

    @classmethod
    def setUpClass(cls):
        # 子模块 eager-import: 触发 secureredact.workers.__init__ 的 lazy __getattr__
        # 只暴露 OCRWorker/WordWorker 大写名, 小写 ocr_worker/word_worker 走 patch
        # 解析会 AttributeError。导入失败 (PyQt6 DLL 缺失) 时整体 skip。
        try:
            import secureredact.workers.ocr_worker  # noqa: F401
            import secureredact.workers.word_worker  # noqa: F401
        except ImportError as _exc:
            raise unittest.SkipTest(
                f"PyQt6 unavailable, skip Worker extra_tokens 集成测试: {_exc}"
            )

    def test_word_worker_stores_extra_tokens(self):
        with patch("secureredact.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.word_worker import WordWorker
            worker = WordWorker(
                word_doc=None,
                word_data={},
                rules=[],
                custom_keywords="",
                replacement_text="[已脱敏]",
                enable_name_recognition=True,
                name_context_extra_tokens=["数据处理者", "委托人"],
            )
            self.assertEqual(
                worker.name_context_extra_tokens,
                ["数据处理者", "委托人"],
            )

    def test_word_worker_default_empty_list(self):
        """默认 name_context_extra_tokens 应为空 list, 向后兼容."""
        with patch("secureredact.workers.word_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.word_worker import WordWorker
            worker = WordWorker(
                word_doc=None,
                word_data={},
                rules=[],
                custom_keywords="",
                replacement_text="[已脱敏]",
            )
            self.assertEqual(worker.name_context_extra_tokens, [])

    def test_ocr_worker_stores_extra_tokens(self):
        with patch("secureredact.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.ocr_worker import OCRWorker
            worker = OCRWorker(
                pdf_path=None,
                rules=[],
                use_enhance=False,
                custom_keywords="",
                scan_scale=1.5,
                off_x=0,
                off_w=0,
                enable_name_recognition=True,
                name_context_extra_tokens=["抵押人", "抵押权人"],
            )
            self.assertEqual(
                worker.name_context_extra_tokens,
                ["抵押人", "抵押权人"],
            )

    def test_ocr_worker_default_empty_list(self):
        with patch("secureredact.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            from secureredact.workers.ocr_worker import OCRWorker
            worker = OCRWorker(
                pdf_path=None,
                rules=[],
                use_enhance=False,
                custom_keywords="",
                scan_scale=1.5,
                off_x=0,
                off_w=0,
            )
            self.assertEqual(worker.name_context_extra_tokens, [])


class TestWorkerKeywordDedup(unittest.TestCase):
    """识别的人名与已有 custom_keywords 重复时,识别器内部已去重."""

    def test_dedup_in_recognizer(self):
        from secureredact.pii.name_recognizer import extract_person_names

        names = extract_person_names("原告：周强，男，汉族。周强已在庭。")
        self.assertEqual(names.count("周强"), 1)


if __name__ == "__main__":
    unittest.main()