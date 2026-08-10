import builtins
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class TestPrivacyGuardImports(unittest.TestCase):

    def test_import_privacyguard_without_rapidocr_runtime(self):
        cached = {
            name: module
            for name, module in list(sys.modules.items())
            if name == "privacyguard" or name.startswith("privacyguard.")
        }
        for name in list(cached):
            sys.modules.pop(name, None)

        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("rapidocr_onnxruntime"):
                raise ImportError("blocked for import smoke test")
            return original_import(name, globals, locals, fromlist, level)

        try:
            with patch("builtins.__import__", side_effect=guarded_import):
                module = importlib.import_module("privacyguard")
        finally:
            for name in list(sys.modules):
                if name == "privacyguard" or name.startswith("privacyguard."):
                    sys.modules.pop(name, None)
            sys.modules.update(cached)

        self.assertTrue(hasattr(module, "validate_safe_path"))
        expected_version = (Path(__file__).resolve().parents[2] / "version.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(module.__version__, expected_version)

    def _snapshot_privacyguard_modules(self):
        """Snapshot privacyguard.* modules for restoration after a test."""
        return {
            name: module
            for name, module in list(sys.modules.items())
            if name == "privacyguard" or name.startswith("privacyguard.")
        }

    def _restore_privacyguard_modules(self, cached):
        for name in list(sys.modules):
            if name == "privacyguard" or name.startswith("privacyguard."):
                sys.modules.pop(name, None)
        sys.modules.update(cached)

    def test_import_privacyguard_does_not_load_pii_engine(self):
        """OPS-03: import privacyguard 不应触发 privacyguard.pii.engine 模块加载。"""
        cached = self._snapshot_privacyguard_modules()
        for name in list(cached):
            sys.modules.pop(name, None)
        try:
            module = importlib.import_module("privacyguard")
            # 触发 _LAZY_IMPORTS 中已有的导出（不应触发 pii.engine）
            _ = module.validate_safe_path
            self.assertNotIn(
                "privacyguard.pii.engine",
                sys.modules,
                "import privacyguard 不得触发 privacyguard.pii.engine",
            )
        finally:
            self._restore_privacyguard_modules(cached)

    def test_pii_engine_loads_on_demand(self):
        """OPS-03: 主动访问 PIIEngine 触发隐私包懒加载。"""
        cached = self._snapshot_privacyguard_modules()
        for name in list(cached):
            sys.modules.pop(name, None)
        try:
            module = importlib.import_module("privacyguard")
            self.assertNotIn("privacyguard.pii.engine", sys.modules)
            # 访问 PIIEngine 触发 _LAZY_IMPORTS
            _ = module.PIIEngine
            self.assertIn(
                "privacyguard.pii.engine",
                sys.modules,
                "访问 privacyguard.PIIEngine 后 privacyguard.pii.engine 应被加载",
            )
        finally:
            self._restore_privacyguard_modules(cached)

    def test_pii_engine_lazy_under_rapidocr_block(self):
        """PII 引擎不得触发 rapidocr_onnxruntime 依赖加载。"""
        cached = self._snapshot_privacyguard_modules()
        for name in list(cached):
            sys.modules.pop(name, None)
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("rapidocr_onnxruntime"):
                raise ImportError("blocked for import smoke test")
            return original_import(name, globals, locals, fromlist, level)

        try:
            with patch("builtins.__import__", side_effect=guarded_import):
                module = importlib.import_module("privacyguard")
                # PII 引擎不应触发 rapidocr 导入
                _ = module.PIIEngine
                self.assertIn("privacyguard.pii.engine", sys.modules)
        finally:
            self._restore_privacyguard_modules(cached)