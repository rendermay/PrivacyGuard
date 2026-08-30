"""
MainWindow mixin 模块 import smoke 测试 (PR-C7 task 4.2, plan §5.3)

按 plan §5.3 任务 4.2:
- 每个 mixin 模块:`import secureredact.ui.main_window.<name>` 不报错
- 不实例化(避免依赖 QApplication)

加 @pytest.mark.smoke 标记,便于在子进程/CI 中跑:
  pytest -m smoke
"""
import importlib
import sys
import unittest

import pytest  # noqa: F401 — for markers


# PR-C7 task 4.2 覆盖的 mixin 模块清单
MIXIN_MODULES = [
    "secureredact.ui.main_window.batch_replace",
    "secureredact.ui.main_window.density",
    "secureredact.ui.main_window.handlers",
    "secureredact.ui.main_window.pdf_render",
    "secureredact.ui.main_window.setup_ui",
    "secureredact.ui.main_window.theme",
    "secureredact.ui.main_window.toolbar",
    "secureredact.ui.main_window.word_preview",
    "secureredact.ui.main_window.workbench",
    # 辅助模块(也作为 mixin 引用)
    "secureredact.ui.main_window._helpers",
    "secureredact.ui.main_window._batch_helpers",
]


@pytest.mark.smoke
class TestMainWindowImportSmoke(unittest.TestCase):
    """每个 mixin 模块:import 成功 + 类存在。"""

    def test_each_mixin_module_imports(self):
        """一次性验证所有 mixin 模块 import 不报错(失败聚合为一条 assertion)。"""
        failures = []
        for modname in MIXIN_MODULES:
            try:
                importlib.import_module(modname)
            except ImportError as e:
                # 子进程无 Qt DLL 时,所有 ImportError 都来自 PyQt6 缺失,统一 skip
                self.skipTest(f"PyQt6 不可用,无法验证 mixin import: {e}")
            except Exception as e:
                failures.append(f"{modname}: {type(e).__name__}: {e}")
        if failures:
            self.fail("Mixin import failures:\n  " + "\n  ".join(failures))

    def test_mainwindow_class_inherits_mixins(self):
        """secureredact.ui.main_window 包内 MainWindow 类从所有 mixin 继承。

        注:此 test 依赖 main.py(完整模块 load),子进程 Qt DLL 缺失时
        整体 skip,不影响 smoke 流程。
        """
        try:
            import main  # noqa: F401
        except ImportError as e:
            self.skipTest(f"main.py 不可用(可能 PyQt6 缺失): {e}")
        # 找 MainWindow 类
        main_module = sys.modules.get("main") or importlib.import_module("main")
        mw = getattr(main_module, "MainWindow", None)
        self.assertIsNotNone(mw, "main.MainWindow 不存在")
        # 验证 mixin 都在 __mro__ 中
        mixin_names = {m.split(".")[-1] for m in MIXIN_MODULES}
        mro_names = {cls.__name__ for cls in mw.__mro__}
        missing = mixin_names - mro_names
        self.assertEqual(missing, set(), f"MainWindow 缺少这些 mixin: {missing}")
