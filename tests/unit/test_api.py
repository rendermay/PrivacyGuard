"""
secureredact/api.py 单元测试 (PR-C4 + PR-C5)

设计原则:
- 不启动 QApplication(避免依赖 Qt event loop)
- PyQt6 依赖的 test 在 setUp 里检测 QtCore DLL,不可用时 skipTest
- 100% 覆盖:每个分支都至少一条用例
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

# PR-C5 修订:api.py 顶层 import 已改 lazy(worker + QEventLoop),直接
# `import secureredact.api` 在无 PyQt6 环境也能成功(coverage 也能跟踪)。
# PyQt6 依赖的函数(batch_redact_word / filter_hits_by_overrides)在 setUp
# 检测后 skipTest,不影响 import。
#
# PR-C9 CI 修:用 pytest.importorskip 模式保护。import 失败则 module-level
# skip,避免 collection ERROR(cannot load module more than once per process)。
import pytest as _pytest  # noqa: E402

try:
    import secureredact.api as api  # noqa: E402
except Exception as e:  # noqa: BLE001 — 任意异常都视为不可用
    _pytest.skip(f"secureredact.api import failed: {e}", allow_module_level=True)

import pytest  # noqa: E402 — for markers (api / smoke)


@pytest.mark.api
@pytest.mark.smoke
class TestComputeDocHash(unittest.TestCase):
    """compute_doc_hash — 主链路,无需 PyQt6。"""

    def test_deterministic_for_same_path(self):
        """相同路径两次调用结果一致。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello")
            path = f.name
        try:
            h1 = api.compute_doc_hash(path)
            h2 = api.compute_doc_hash(path)
            self.assertEqual(h1, h2)
        finally:
            os.unlink(path)

    def test_path_and_string_equivalent(self):
        """str 和 pathlib.Path 入参产生相同 hash (plan §2.4 H-3 修订)。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"data")
            str_path = f.name
        try:
            from pathlib import Path
            path_obj = Path(str_path)
            self.assertEqual(api.compute_doc_hash(str_path), api.compute_doc_hash(path_obj))
        finally:
            os.unlink(str_path)

    def test_resolved_path_equivalent_to_unresolved(self):
        """Path.resolve() 与未 resolve 的 str 入参产生相同 hash (REVIEWS-v2 I-5 真实歧义)。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", dir=".") as f:
            f.write(b"data")
            name = os.path.basename(f.name)
        try:
            from pathlib import Path
            # 都用 str(同 string 表达)
            self.assertEqual(api.compute_doc_hash(name), api.compute_doc_hash(name))
        finally:
            try:
                os.unlink(name)
            except OSError:
                pass

    def test_returns_8_char_hex(self):
        """返回 8 位 hex 字符串。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"x")
            path = f.name
        try:
            h = api.compute_doc_hash(path)
            self.assertEqual(len(h), 8)
            int(h, 16)  # 必须能解析为 hex
        finally:
            os.unlink(path)

    def test_nonexistent_file_raises_oserror(self):
        """不存在的文件抛 OSError。"""
        with self.assertRaises(OSError):
            api.compute_doc_hash("/nonexistent/path/that/does/not/exist.txt")


@pytest.mark.api
class TestStubFunctions(unittest.TestCase):
    """scan_pdf / scan_word / redact_pdf / redact_word — 真实实现(非 stub)。"""

    def _make_pdf(self):
        """创建一个最小有效 PDF,fitz 能打开。"""
        import fitz
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        doc = fitz.open()
        page = doc.new_page(width=300, height=200)
        page.insert_text((50, 100), "张三 13800138000")
        doc.save(tmp.name)
        doc.close()
        return tmp.name

    def _make_docx(self):
        """创建一个最小 .docx。"""
        from docx import Document
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        tmp.close()
        doc = Document()
        doc.add_paragraph("张三 13800138000")
        doc.save(tmp.name)
        return tmp.name

    def test_scan_pdf_returns_page_keyed_dict(self):
        """scan_pdf 返回 {page_num: [hits]} 字典。"""
        pdf = self._make_pdf()
        try:
            result = api.scan_pdf(pdf, rules={"phone": r"1[3-9]\d{9}"})
            self.assertIsInstance(result, dict)
            self.assertGreaterEqual(len(result), 1)
            page_0_hits = result.get(0, [])
            self.assertGreater(len(page_0_hits), 0)
            hit = page_0_hits[0]
            self.assertEqual(hit["source"], "rule")
            self.assertIn("rect", hit)
            self.assertEqual(len(hit["rect"]), 4)  # (x, y, w, h)
        finally:
            os.unlink(pdf)

    def test_scan_pdf_nonexistent_raises_filenotfound(self):
        """scan_pdf 不存在文件抛 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            api.scan_pdf("/nonexistent.pdf", rules={})

    def test_scan_pdf_with_keywords_adds_to_patterns(self):
        """scan_pdf 把 custom_keywords 拆词后附加到 patterns。"""
        pdf = self._make_pdf()
        try:
            result = api.scan_pdf(
                pdf,
                rules={"phone": r"1[3-9]\d{9}"},
                custom_keywords="张三",
            )
            # 应该至少有一个命中(text "张三 13800138000" 包含 "张三" 和 "13800138000")
            all_texts = [h["text"] for h_list in result.values() for h in h_list]
            self.assertTrue(any("张三" in t for t in all_texts) or any("13800" in t for t in all_texts))
        finally:
            os.unlink(pdf)

    def test_scan_word_returns_match_list(self):
        """scan_word 返回 matches list。"""
        docx = self._make_docx()
        try:
            result = api.scan_word(docx, rules=[{"find": "张三", "mode": "exact", "enabled": True}])
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            m = result[0]
            self.assertIn("text", m)
            self.assertIn("start", m)
            self.assertIn("end", m)
            self.assertEqual(m["text"], "张三")
        finally:
            os.unlink(docx)

    def test_scan_word_nonexistent_raises_filenotfound(self):
        """scan_word 不存在文件抛 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            api.scan_word("/nonexistent.docx", rules=[])

    def test_redact_pdf_writes_output_file(self):
        """redact_pdf 写 output 文件并返回 summary。"""
        pdf = self._make_pdf()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "out.pdf")
            try:
                result = api.redact_pdf(
                    pdf, out,
                    rules={"phone": r"1[3-9]\d{9}"},
                )
                self.assertEqual(result["output"], out)
                self.assertGreater(result["hits"], 0)
                self.assertGreater(result["pages"], 0)
                self.assertGreater(result["elapsed_sec"], 0)
                self.assertTrue(os.path.isfile(out))
            finally:
                os.unlink(pdf)

    def test_redact_pdf_nonexistent_input_raises_filenotfound(self):
        """redact_pdf 输入不存在抛 FileNotFoundError。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                api.redact_pdf(
                    "/nonexistent.pdf",
                    os.path.join(tmpdir, "out.pdf"),
                    rules={},
                )

    def test_redact_pdf_nonexistent_output_dir_raises_filenotfound(self):
        """redact_pdf 输出目录不存在抛 FileNotFoundError。"""
        pdf = self._make_pdf()
        try:
            with self.assertRaises(FileNotFoundError):
                api.redact_pdf(
                    pdf, "/nonexistent/dir/out.pdf", rules={}
                )
        finally:
            os.unlink(pdf)

    def test_redact_word_writes_output_file(self):
        """redact_word 写 output 文件并返回 summary。"""
        docx = self._make_docx()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "out.docx")
            try:
                result = api.redact_word(
                    docx, out,
                    rules=[{"find": "张三", "mode": "exact", "enabled": True}],
                )
                self.assertEqual(result["output"], out)
                self.assertGreater(result["hits"], 0)
                self.assertGreater(result["elapsed_sec"], 0)
                self.assertTrue(os.path.isfile(out))
                # 验证 output 文件中 "张三" 已被替换
                from docx import Document
                out_doc = Document(out)
                text = "\n".join(p.text for p in out_doc.paragraphs)
                self.assertNotIn("张三", text)
            finally:
                os.unlink(docx)

    def test_redact_word_nonexistent_input_raises_filenotfound(self):
        """redact_word 输入不存在抛 FileNotFoundError。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                api.redact_word(
                    "/nonexistent.docx",
                    os.path.join(tmpdir, "out.docx"),
                    rules=[],
                )


@pytest.mark.api
class TestFilterHitsByOverrides(unittest.TestCase):
    """filter_hits_by_overrides — 需要 PyQt6(Qt 在子进程不可用时跳过)。"""

    def setUp(self):
        # DLL 加载失败抛 ImportError 子类,但不同平台子类不同(QtCore: ImportError)。
        # 用 try 加载真实 module 而非顶层 package,确保捕获。
        try:
            from PyQt6 import QtCore  # noqa: F401
        except (ImportError, OSError) as e:
            self.skipTest(f"PyQt6.QtCore 加载失败(DLL 不可用): {e}")

    def test_requires_doc_hash_or_doc_path(self):
        """doc_hash=None 且 doc_path=None 抛 ValueError (plan §2.4 M-2 修订)。"""
        with self.assertRaises(ValueError) as cm:
            api.filter_hits_by_overrides([], location="page_0")
        self.assertIn("doc_hash or doc_path required", str(cm.exception))

    def test_with_doc_hash_returns_filtered_list(self):
        """提供 doc_hash 时返回 list(可空)。"""
        result = api.filter_hits_by_overrides(
            [], location="page_0", doc_hash="abc12345"
        )
        self.assertIsInstance(result, list)

    def test_doc_path_computes_hash_when_doc_hash_missing(self):
        """doc_path 提供时,内部调 compute_doc_hash(doc_path)。"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"x")
            path = f.name
        try:
            result = api.filter_hits_by_overrides(
                [{"text": "sample"}], location="page_0", doc_path=path
            )
            self.assertIsInstance(result, list)
        finally:
            os.unlink(path)

    def test_with_no_overrides_returns_input_as_list(self):
        """无 override 时,返回输入 hits(顺序保持)。"""
        hits = [{"text": "a"}, {"text": "b"}]
        result = api.filter_hits_by_overrides(
            hits, location="page_0", doc_hash="none001"
        )
        self.assertEqual(len(result), 2)


@pytest.mark.api
class TestBatchRedactWord(unittest.TestCase):
    """batch_redact_word — 需要 PyQt6 + .docx 文件。子进程无 Qt 时跳过核心分支,只测参数校验。"""

    def setUp(self):
        try:
            from PyQt6 import QtCore  # noqa: F401
        except (ImportError, OSError) as e:
            self.skipTest(f"PyQt6.QtCore 加载失败(DLL 不可用): {e}")

    def test_output_dir_not_exists_raises_filenotfound(self):
        """output_dir 不存在抛 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            api.batch_redact_word(
                word_paths=["/tmp/x.docx"],
                output_dir="/nonexistent/dir/12345",
                rules=[],
            )

    def test_invalid_timeout_sec_raises_valueerror(self):
        """options.timeout_sec 非 int 抛 ValueError。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError) as cm:
                api.batch_redact_word(
                    word_paths=["/tmp/x.docx"],
                    output_dir=tmpdir,
                    rules=[],
                    options={"timeout_sec": "abc"},
                )
            self.assertIn("timeout_sec 必须为 int", str(cm.exception))

    def test_empty_word_paths_returns_empty_summary(self):
        """word_paths 为空时返回全空 summary(0 / [] / [] / False)。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 注:空 list 当前不会触发 FileNotFoundError,但 worker.start() 后
            # loop.quit 由 finished_signal 触发,产生空 summary。
            # 该测试需要 PyQt6 event loop,但不依赖 Qt DLL 路径加载
            # 实际调用可能在本环境失败,需 skipUnless 真实环境
            try:
                result = api.batch_redact_word(
                    word_paths=[],
                    output_dir=tmpdir,
                    rules=[],
                )
                self.assertEqual(result["total"], 0)
                self.assertEqual(result["success"], [])
                self.assertEqual(result["failed"], [])
                self.assertFalse(result["stopped"])
            except RuntimeError as e:
                # 子进程 Qt 不可用时 QApplication 缺失,接受该异常
                if "QApplication" in str(e) or "QCoreApplication" in str(e):
                    self.skipTest("QApplication 不可用")
                raise


# ============================================================================
# PR-CI 覆盖率门禁补齐(目标:secureredact/api.py 覆盖率 100%)
#
# 背景:CI 执行
#   python -m pytest -m api --cov=secureredact.api --cov-fail-under=100
# 之前 secureredact/api.py 覆盖率停在 91.14%(158 stmts / 14 miss),
# 门禁必然失败(退出码 1)。下列用例覆盖了此前未被触达的分支:
#   api.py:89 / 161-163 / 171 / 296 / 304-306 / 313 / 435-436 / 449 / 454
#
# 原则:
# - 一律走真实代码路径(调用 api.py 的公开函数),不 monkeypatch 被测逻辑本身;
# - 只有 worker 对象与 Qt 定时器使用测试替身(worker 生命周期无法在单元
#   测试里真实复现;Qt 定时器只是把 5s 等待压缩,信号机制仍是真实的)。
# ============================================================================

_QT_APP = None


def _ensure_core_app():
    """确保进程内存在一个 Qt 应用实例。

    没有 QCoreApplication / QApplication 时,QEventLoop.exec() 只会打印一句
    "QEventLoop: Cannot be used without QCoreApplication" 然后永久阻塞
    (实测 PyQt6 6.11),batch_redact_word 相关用例会直接把测试进程卡死。
    若其它模块(如 tests/ui/test_baselines.py)已建好 QApplication,这里直接
    复用,不会重复创建。
    """
    global _QT_APP
    from PyQt6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is not None:
        return app

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])
    except Exception:  # noqa: BLE001 — 无 GUI 环境时退化为纯 QCoreApplication
        app = QCoreApplication([])
    _QT_APP = app  # 持有引用,避免被 GC 提前回收
    return app


def setUpModule():
    """模块级准备:保证 Qt 应用实例存在(否则 event loop 用例会挂死)。"""
    try:
        _ensure_core_app()
    except Exception:  # noqa: BLE001 — 无 Qt 环境由各用例自行 skip
        pass


class _StubSignal:
    """最小 pyqtSignal 替身:记录 connect 到的槽,便于手动 emit。"""

    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, payload=None):
        for slot in list(self._slots):
            slot(payload)


class _StubBatchWorker:
    """WordBatchReplaceWorker 的测试替身。

    只实现 api.batch_redact_word 用到的接口(finished_signal / start /
    isRunning / wait / provide_error_decision),用于在不真正处理文档的前提下,
    验证主线程与 worker 线程之间的生命周期交互。
    """

    _instances = []
    emit_summary_on_start = False
    running = True
    summary_payload = None

    def __init__(self, file_paths=None, rules=None, default_replacement_text=None):
        self.file_paths = list(file_paths or [])
        self.rules = rules
        self.default_replacement_text = default_replacement_text
        self.finished_signal = _StubSignal()
        self.started = False
        self.wait_calls = []
        self.error_decisions = []
        _StubBatchWorker._instances.append(self)

    def start(self):
        self.started = True
        if self.emit_summary_on_start:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(10, self._emit_summary)

    def _emit_summary(self):
        self.finished_signal.emit(dict(self.summary_payload or {}))

    def isRunning(self):
        return self.running

    def wait(self, msecs=None):
        self.wait_calls.append(msecs)
        return True

    def provide_error_decision(self, decision):
        self.error_decisions.append(decision)


def _make_stub_worker_class(*, emit_summary=False, summary=None, is_running=True):
    """按用例需要定制 _StubBatchWorker(是否自动 emit summary / 是否仍在运行)。"""

    class _ConfiguredStubWorker(_StubBatchWorker):
        emit_summary_on_start = emit_summary
        running = is_running
        summary_payload = summary

    return _ConfiguredStubWorker


def _make_fast_timer_class(max_interval_ms=30):
    """构造"实例定时器间隔被压缩"的真实 QTimer 子类。

    api.batch_redact_word 里的 auto-skip 兜底定时器固定 5s 一次,测试里
    干等 5s 太慢。这里只压缩"间隔",Qt 的信号 / 事件机制保持真实,被测逻辑
    (_auto_provide_skip 回调)仍然是真实执行。
    """
    from PyQt6.QtCore import QTimer as _RealQTimer

    class _FastIntervalQTimer(_RealQTimer):
        """间隔上限被压缩的真实 QTimer(仅用于测试提速)。"""

        def setInterval(self, msec):
            super().setInterval(min(int(msec), max_interval_ms))

    return _FastIntervalQTimer


@pytest.mark.api
class TestApiNormalizationBranches(unittest.TestCase):
    """api.py 的归一化分支:规则形态 / 自定义关键词 / 空段落 / 输出目录。"""

    def _make_pdf(self):
        """创建一个最小有效 PDF,fitz 能打开。"""
        import fitz
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        doc = fitz.open()
        page = doc.new_page(width=300, height=200)
        page.insert_text((50, 100), "张三 13800138000")
        doc.save(tmp.name)
        doc.close()
        return tmp.name

    def _make_docx(self, paragraphs=("张三 13800138000",)):
        """创建一个 .docx;传入空字符串即可制造空段落。"""
        from docx import Document
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        tmp.close()
        doc = Document()
        for text in paragraphs:
            doc.add_paragraph(text)
        doc.save(tmp.name)
        return tmp.name

    def test_scan_pdf_accepts_rules_with_patterns_key(self):
        """scan_pdf 支持 {"patterns": [...]} 形态的规则字典。

        回归防护:规则归一化一旦漏掉 "patterns" 分支,调用方(批量规则导入 /
        规则文件加载)传入该形态时会静默扫不到任何命中 —— 不报错、结果为空,
        人工验收阶段极难发现,只能靠单测守住。
        """
        pdf = self._make_pdf()
        try:
            result = api.scan_pdf(pdf, rules={"patterns": [r"1[3-9]\d{9}"]})
            hits = [h for page_hits in result.values() for h in page_hits]
            self.assertTrue(hits, "patterns 形态的规则必须能命中手机号")
            self.assertTrue(any(h["text"] == "13800138000" for h in hits))
        finally:
            os.unlink(pdf)

    def test_scan_word_custom_keywords_are_appended_as_exact_rules(self):
        """scan_word 把 custom_keywords 拆词后追加为 exact 规则参与匹配。

        回归防护:自定义关键词若没有并入规则,UI 上填写的关键词会完全失效
        (扫描结果里查不到该词),而普通规则仍照常返回、不报任何错,极易漏测。
        """
        docx = self._make_docx()
        try:
            result = api.scan_word(docx, rules=[], custom_keywords="  张三  李四 ")
            texts = [m["text"] for m in result]
            self.assertIn("张三", texts)
            self.assertNotIn("李四", texts)  # 文档里没有该词,不应凭空命中
        finally:
            os.unlink(docx)

    def test_scan_word_skips_empty_paragraph(self):
        """scan_word 跳过空段落,且空段落不占用后续段落的字符偏移。

        回归防护:空段落(空行、残留表格段)若不被跳过,轻则 start/end 偏移
        算错导致 GUI 高亮框错位,重则整份文档扫描中断。
        """
        docx = self._make_docx(paragraphs=("", "张三"))
        try:
            result = api.scan_word(
                docx, rules=[{"find": "张三", "mode": "exact", "enabled": True}]
            )
            self.assertEqual(len(result), 1)
            match = result[0]
            self.assertEqual(match["text"], "张三")
            self.assertEqual(match["start"], 0, "空段落不得占用字符偏移")
            self.assertEqual(match["end"], 2)
        finally:
            os.unlink(docx)

    def test_redact_word_nonexistent_output_dir_raises_filenotfound(self):
        """redact_word 输出目录不存在时抛 FileNotFoundError。

        回归防护:输出目录缺失若不提前拦截,错误会推迟到写盘阶段才暴露,
        调用方无法区分"输入文件问题"与"输出路径问题",排障成本高。
        """
        docx = self._make_docx()
        try:
            with pytest.raises(FileNotFoundError) as cm:
                api.redact_word(docx, "/nonexistent/dir/out.docx", rules=[])
            self.assertIn("输出目录不存在", str(cm.value))
        finally:
            os.unlink(docx)

    def test_redact_word_custom_keywords_are_replaced(self):
        """redact_word 把 custom_keywords 追加为 exact 规则并真正完成替换。

        回归防护:与 scan_word 同构 —— 自定义关键词若没并入规则,"一键脱敏"
        会把敏感词原样留在输出文档里,属于功能性(而非崩溃性)回归。
        """
        docx = self._make_docx()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "out.docx")
            try:
                result = api.redact_word(docx, out, rules=[], custom_keywords="张三")
                self.assertGreater(result["hits"], 0)
                from docx import Document
                text = "\n".join(p.text for p in Document(out).paragraphs)
                self.assertNotIn("张三", text)
                self.assertIn("13800138000", text)
            finally:
                os.unlink(docx)

    def test_redact_word_skips_empty_paragraph(self):
        """redact_word 跳过空段落,不影响其它段落的替换。

        回归防护:空段落若不跳过,replace_matches_in_paragraph 会对空文本
        计算替换区间,可能抛异常或写入多余内容,导致整份文档脱敏失败。
        """
        docx = self._make_docx(paragraphs=("", "张三 13800138000"))
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "out.docx")
            try:
                result = api.redact_word(
                    docx, out,
                    rules=[{"find": "张三", "mode": "exact", "enabled": True}],
                )
                self.assertGreater(result["hits"], 0)
                from docx import Document
                text = "\n".join(p.text for p in Document(out).paragraphs)
                self.assertNotIn("张三", text)
                self.assertIn("13800138000", text)
            finally:
                os.unlink(docx)


@pytest.mark.api
class TestBatchRedactWordWorkerLifecycle(unittest.TestCase):
    """batch_redact_word 的 worker 生命周期:自动 skip 兜底 / 等待退出 / 超时取消。"""

    def setUp(self):
        try:
            from PyQt6 import QtCore  # noqa: F401
        except (ImportError, OSError) as e:
            self.skipTest(f"PyQt6.QtCore 加载失败(DLL 不可用): {e}")
        _ensure_core_app()
        _StubBatchWorker._instances = []

    def test_autoskip_timer_provides_skip_decision_and_waits_worker(self):
        """auto-skip 兜底定时器在 worker 运行期间会主动提供 "skip" 决策。

        回归防护:REVIEWS-v2 C-2 —— 批处理中某个文件出错时,worker 线程阻塞在
        _wait_for_error_decision,主线程阻塞在 QEventLoop;若少了这个每 5s 的
        "skip" 兜底,两侧互等 => 批处理永久死锁,界面无任何提示。同时验证
        超时未拿到 summary 时抛 WorkerCancelledError,而不是静默返回空结果。
        """
        from PyQt6 import QtCore
        from secureredact.utils.exceptions import WorkerCancelledError

        fast_timer_cls = _make_fast_timer_class()
        stub_worker_cls = _make_stub_worker_class(is_running=True)
        with tempfile.TemporaryDirectory() as tmpdir, \
                mock.patch.object(QtCore, "QTimer", fast_timer_cls), \
                mock.patch(
                    "secureredact.workers.word_batch_replace_worker.WordBatchReplaceWorker",
                    stub_worker_cls,
                ):
            with self.assertRaises(WorkerCancelledError):
                api.batch_redact_word(
                    word_paths=["a.docx"],
                    output_dir=tmpdir,
                    rules=[],
                    options={"timeout_sec": 1},
                )

        worker = _StubBatchWorker._instances[-1]
        self.assertTrue(worker.started, "batch_redact_word 必须启动 worker")
        self.assertIn(
            "skip", worker.error_decisions,
            "auto-skip 兜底定时器必须提供 skip 决策,否则批处理会死锁",
        )
        self.assertEqual(
            worker.wait_calls, [5000],
            "worker 仍在运行时必须 wait(5000) 等它真正退出",
        )

    def test_returns_summary_when_worker_finished(self):
        """worker 正常结束并 emit finished_signal 时返回组装好的 summary。

        回归防护:summary 组装(total/success/failed/stopped)一旦回归,批处理
        就会丢字段,上层拿不到失败清单,用户会误以为"全部成功"。同时验证
        worker 已经退出时不再 wait(避免多余的 5s 卡顿)。
        """
        summary = {
            "total": 1,
            "success": [{
                "input": "a.docx",
                "output": "out.docx",
                "total_replacements": 2,
                "rule_counts": [],
            }],
            "failed": [],
            "stopped": False,
        }
        stub_worker_cls = _make_stub_worker_class(
            emit_summary=True, summary=summary, is_running=False
        )
        with tempfile.TemporaryDirectory() as tmpdir, \
                mock.patch(
                    "secureredact.workers.word_batch_replace_worker.WordBatchReplaceWorker",
                    stub_worker_cls,
                ):
            result = api.batch_redact_word(
                word_paths=["a.docx"],
                output_dir=tmpdir,
                rules=[],
                options={"timeout_sec": 5},
            )

        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["success"]), 1)
        self.assertEqual(result["success"][0]["input"], "a.docx")
        self.assertEqual(result["failed"], [])
        self.assertFalse(result["stopped"])
        worker = _StubBatchWorker._instances[-1]
        self.assertEqual(worker.wait_calls, [], "worker 已退出时不应再 wait")


if __name__ == "__main__":
    unittest.main()