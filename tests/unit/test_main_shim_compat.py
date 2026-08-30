"""
main.py shim 兼容安全网 (PR-C6 task 0, plan §4.3)

PR-B5.2 / PR-C4 / PR-C5 阶段从 main.py 模块级引用了大量符号。
P3 阶段逐步把这些符号迁到 secureredact/ 对应子包;本测试作为迁移过程
的安全网,确保每个被迁符号在 main.py 中仍可用。

用法:
1. 在 PR-C6 任务 0 添加(已建)
2. 每个迁移 PR 都跑这个测试,确认 main.py 兼容层还在
3. B5 收口时移除本测试

当前清单(plan §4.3 任务 0 例):
  - APP_NAME: feedback.py:50
  - VERSION: feedback.py:50
  - config: feedback.py:50 / image_list.py:49 / handlers.py:381 / theme.py:74
  - WORD_RULE_SCHEMA_VERSION: word_replace_rules.py:257
  - DEFAULT_RULES: handlers.py:381 / settings/dialog.py:65 / :1906
  - DEFAULT_RULES_META: handlers.py:381
  - OCRWorker / WordWorker: handlers.py:381(plan §3.7 明确保留兼容层到 B5)
  - ZOOM_MIN / ZOOM_MAX: pdf_render.py:68, :88

每个迁移 PR 删除对应条目,并跑这条测试。
"""
import unittest

# Qt 不可用时(子进程 Qt DLL 缺失)整个 module skip
# main.py 顶层 import 会拉 PyQt6 链(workers.image_merge),子进程 import 失败
# 会让 test loader 把整个 module 标为 _FailedTest。
try:
    import main  # noqa: F401 — 仅作可用性检测
    _MAIN_AVAILABLE = True
    ImportError  # placeholder
except ImportError as _e:
    _MAIN_AVAILABLE = False
    _SKIP_REASON = f"main.py import 失败(通常 PyQt6 不可用): {_e}"

if not _MAIN_AVAILABLE:
    for _name in list(globals().keys()):
        _cls = globals().get(_name)
        if (
            isinstance(_cls, type)
            and _name.startswith("Test")
            and issubclass(_cls, unittest.TestCase)
        ):
            for _method_name in list(vars(_cls)):
                if _method_name.startswith("test_"):
                    _method = getattr(_cls, _method_name)
                    if callable(_method):
                        setattr(_cls, _method_name, unittest.skip(_SKIP_REASON)(_method))


class TestMainShimCompat(unittest.TestCase):
    """main.py shim 兼容安全网 — 11 符号当前都在 main.py 模块级可用。"""

    def _try_import(self, name):
        """尝试从 main 导入;Qt DLL 缺失时 skipTest 而非 ERROR。"""
        try:
            return __import__("main", fromlist=[name]).__dict__[name]
        except ImportError as e:
            self.skipTest(f"main.py import 失败(通常 PyQt6 不可用): {e}")

    def test_app_name_available(self):
        APP_NAME = self._try_import("APP_NAME")
        self.assertIsInstance(APP_NAME, str)

    def test_version_available(self):
        VERSION = self._try_import("VERSION")
        self.assertIsInstance(VERSION, str)

    def test_config_available(self):
        config = self._try_import("config")
        # config 是 SimpleConfig 单例(可有 None fallback)
        self.assertTrue(config is None or hasattr(config, "get"))

    def test_word_rule_schema_version_available(self):
        WORD_RULE_SCHEMA_VERSION = self._try_import("WORD_RULE_SCHEMA_VERSION")
        self.assertEqual(WORD_RULE_SCHEMA_VERSION, 1)

    def test_default_rules_available(self):
        DEFAULT_RULES = self._try_import("DEFAULT_RULES")
        self.assertIsInstance(DEFAULT_RULES, dict)

    def test_default_rules_meta_available(self):
        DEFAULT_RULES_META = self._try_import("DEFAULT_RULES_META")
        self.assertIsInstance(DEFAULT_RULES_META, dict)

    def test_ocrworker_compat_layer(self):
        """OCRWorker 是 main.py 兼容层,继承自 secureredact.workers 的模块化版本。
        plan §3.7 明确保留到 B5/v1.1.17 收口;本测试防止误删。"""
        OCRWorker = self._try_import("OCRWorker")
        from secureredact.workers.ocr_worker import OCRWorker as ModularOCRWorker
        self.assertTrue(issubclass(OCRWorker, ModularOCRWorker))

    def test_wordworker_compat_layer(self):
        WordWorker = self._try_import("WordWorker")
        from secureredact.workers.word_worker import WordWorker as ModularWordWorker
        self.assertTrue(issubclass(WordWorker, ModularWordWorker))

    def test_zoom_min_available(self):
        ZOOM_MIN = self._try_import("ZOOM_MIN")
        self.assertIsInstance(ZOOM_MIN, (int, float))

    def test_zoom_max_available(self):
        ZOOM_MAX = self._try_import("ZOOM_MAX")
        self.assertIsInstance(ZOOM_MAX, (int, float))


if __name__ == "__main__":
    unittest.main()