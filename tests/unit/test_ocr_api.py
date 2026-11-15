#!/usr/bin/env python3
"""RapidOCR API 冒烟测试（无硬编码路径）。

P0-7 修订: 原实现把**任何** ImportError 都当成「rapidocr_onnxruntime 未安装」而静默
skip —— 而 Windows 上 PyQt6 与 onnxruntime 的 MSVC runtime 冲突恰好也表现为
ImportError(DLL 初始化例程失败)。于是「OCR 全链路已坏」被伪装成「依赖没装」,
CI 全绿而 OCR 不可用。

现在:
    1. 测试模块导入时先走应用同款的 onnxruntime 预加载(见 secureredact/ocr/preload.py)
    2. 区分三种情况: 真没装(ModuleNotFoundError) -> skip / 装了但 DLL 加载失败 -> **失败**
    3. 子进程回归用例: 走真实入口模块的加载顺序, 确认「先 ORT 后 Qt」稳定可用
       (若有人把入口里的预加载删掉, 该用例会立刻变红)
"""

import subprocess
import sys
import unittest

# P0-7: 与应用入口同款 —— 任何 PyQt6 import 之前先固定 onnxruntime 的 DLL 绑定顺序
from secureredact.ocr.preload import preload_onnxruntime  # noqa: E402

preload_onnxruntime()


class TestRapidOCRAPI(unittest.TestCase):

    def _import_rapidocr(self):
        """导入 RapidOCR; 区分「未安装」与「DLL 加载失败」。"""
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ModuleNotFoundError as exc:
            self.skipTest(f"rapidocr_onnxruntime 未安装: {exc}")
        except ImportError as exc:
            # 装了但加载不了 —— 绝不能 skip, 必须让 CI 红
            self.fail(
                "rapidocr_onnxruntime 导入失败(已安装但 DLL 加载异常): "
                f"{exc}\n"
                "这通常是 Windows 上 PyQt6 与 onnxruntime 的 MSVC runtime 冲突 —— "
                "请确认入口在 import PyQt6 之前调用了 "
                "secureredact.ocr.preload.preload_onnxruntime()。"
            )
        return RapidOCR

    def test_import_and_init(self):
        RapidOCR = self._import_rapidocr()
        ocr = RapidOCR()
        self.assertIsNotNone(ocr)
        self.assertTrue(callable(ocr))

    def test_public_methods_available(self):
        RapidOCR = self._import_rapidocr()
        ocr = RapidOCR()
        public_methods = [m for m in dir(ocr) if not m.startswith("_")]
        # 至少应该暴露可调用接口
        self.assertGreater(len(public_methods), 0)


class TestOnnxRuntimeAfterEntry(unittest.TestCase):
    """P0-7 回归: 走真实入口模块的加载顺序后, onnxruntime 必须仍可用。

    Windows 上 PyQt6 自带一份较新的 msvcp140.dll; 若先加载 PyQt6 再加载
    onnxruntime, 后者的原生扩展会因 runtime 版本冲突初始化失败:
        ImportError: DLL load failed while importing onnxruntime_pybind11_state
    应用入口通过 secureredact.ocr.preload 预加载来固定顺序; 本用例用**子进程**
    隔离验证真实入口, 若入口里的预加载被删掉, 本用例会立刻变红。
    """

    def test_onnxruntime_loads_after_entry_import(self):
        import os

        code = (
            "import secureredact.main  # 入口模块内部已预加载 onnxruntime(P0-7)\n"
            "from PyQt6.QtWidgets import QApplication\n"
            "app = QApplication([])\n"
            "import onnxruntime\n"
            "print('ORT-AFTER-ENTRY-OK', onnxruntime.__version__)\n"
        )
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        self.assertEqual(
            proc.returncode,
            0,
            "走真实入口后 onnxruntime 仍导入失败 —— DLL runtime 冲突未被 preload 修复:\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}",
        )
        self.assertIn("ORT-AFTER-ENTRY-OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()