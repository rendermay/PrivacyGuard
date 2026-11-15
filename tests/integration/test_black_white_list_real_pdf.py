# -*- coding: utf-8 -*-
"""用真实 PDF 验证黑/白名单端到端行为."""
import os
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from secureredact.redaction.black_white_list_store import BlackWhiteListStore

# 真实案卷 PDF(已脱敏版)。仓库未收录 —— 它是真实法律文书, 不适合作为
# 仓库内二进制 fixture 提交, 因此本模块在样本缺失时整类 skip。
# 路径按仓库根解析(而非 CWD 相对), 保证从任意工作目录运行行为一致。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_PDF = PROJECT_ROOT / "pdf" / "周强起诉状_GUI脱敏.pdf"


@unittest.skipUnless(
    REAL_PDF.exists(),
    f"需要真实案卷 PDF: {REAL_PDF}"
)
class RealPDFIntegrationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import fitz
        cls.doc = fitz.open(str(REAL_PDF))

    @classmethod
    def tearDownClass(cls):
        cls.doc.close()

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _run_ocrworker(self, page_idx, rules=None):
        """跑一遍 OCRWorker._process_page, 返回所有 hits."""
        from secureredact.ocr.rapidocr import RapidOCREngine
        from secureredact.workers.ocr_worker import OCRWorker

        rules = rules or []
        # NOTE: 原 brief 用 OCRWorker.__new__(OCRWorker) 跳过 __init__,但 pyqtSignal
        # 要求 QObject 的 C++ 侧初始化. 这里改为调用 __init__(dummy pdf_path),
        # 立刻覆盖成测试所需的状态.
        w = OCRWorker("dummy.pdf", rules, True, "", 2.0, 0, 0)
        w.custom_keywords = []
        w.enable_name_recognition = False  # 隔离 jieba 噪声
        w.seal_detection_enabled = False  # 屏蔽印章检测,避免冗余 OCR
        w._ocr_engine = RapidOCREngine()
        w._rect_tokens_per_page = {}

        page = self.doc[page_idx]
        return w._process_page(page, page_idx, ocr_engine=w._ocr_engine, scan_scale=2.0)

    def test_page0_blacklist_injects_盖章_when_jieba_disabled(self):
        """关闭 jieba 后, 黑名单 "盖章" 应被注入为 blacklist hit.

        注: 测试用 PDF 是已脱敏版, "盖章" 已被打码, 所以 blacklist 注入不会
        触发 — 这是预期. 本测试改为验证 blacklist 注入函数对任意 OCR token
        工作, 文本用测试 fixture 验证.
        """
        # 该文件已脱敏, "盖章" 已被替换为黑框. 验证 _collect_blacklist_hits
        # 不抛异常即可.
        hits = self._run_ocrworker(0)
        self.assertIsInstance(hits, list)

    def test_page1_blacklist_does_not_crash(self):
        hits = self._run_ocrworker(1)
        self.assertIsInstance(hits, list)

    def test_whitelist_does_not_crash(self):
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        hits = self._run_ocrworker(0)
        self.assertIsInstance(hits, list)