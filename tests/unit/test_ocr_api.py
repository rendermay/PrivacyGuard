#!/usr/bin/env python3
"""RapidOCR API 冒烟测试（无硬编码路径）。

P0-7 修订: 原实现把**任何** ImportError 都当成「rapidocr_onnxruntime 未安装」而静默
skip —— 而 Windows 上 PyQt6 与 onnxruntime 的 MSVC runtime 冲突恰好也表现为
ImportError(DLL 初始化例程失败)。于是「OCR 全链路已坏」被伪装成「依赖没装」,
CI 全绿而 OCR 不可用。

现在区分三种情况:
    1. 真的没装(ModuleNotFoundError) -> skip(合理)
    2. 装了但 DLL 加载失败(ImportError 且非 ModuleNotFoundError) -> **失败**
    3. 正常 -> 跑断言
并新增子进程回归用例, 确保「Qt 先加载 -> onnxruntime 仍可用」这一前置条件被守住。
"""

import subprocess
import sys
import unittest


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


class TestOnnxRuntimeAfterQt(unittest.TestCase):
    """P0-7 回归: 先加载 PyQt6 再加载 onnxruntime 必须仍然可用。

    Windows 上 PyQt6 自带一份较新的 msvcp140.dll, 若先加载 PyQt6 再加载
    onnxruntime, 后者的原生扩展会因 runtime 版本冲突初始化失败:
        ImportError: DLL load failed while importing onnxruntime_pybind11_state
    本用例用**子进程**隔离验证, 避免本进程已加载 onnxruntime 造成假绿。
    """

    def test_onnxruntime_loads_after_qt(self):
        import os

        code = (
            "from PyQt6.QtWidgets import QApplication\n"
            "app = QApplication([])\n"
            "import onnxruntime\n"
            "print('ORT-AFTER-QT-OK', onnxruntime.__version__)\n"
        )
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
        )
        self.assertEqual(
            proc.returncode,
            0,
            "先加载 PyQt6 后 onnxruntime 导入失败 —— DLL runtime 冲突:\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}",
        )
        self.assertIn("ORT-AFTER-QT-OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()