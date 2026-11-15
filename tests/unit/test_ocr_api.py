#!/usr/bin/env python3
"""RapidOCR API 冒烟测试（无硬编码路径）。

P0-7 修订: 原实现把**任何** ImportError 都当成「rapidocr_onnxruntime 未安装」而静默
skip —— 而 Windows 上 PyQt6 与 onnxruntime 的 MSVC runtime 冲突恰好也表现为
ImportError(DLL 初始化例程失败)。于是「OCR 全链路已坏」被伪装成「依赖没装」,
CI 全绿而 OCR 不可用。

为什么全部走子进程:
    pytest-qt 插件在**插件加载期**就会 import PyQt6, 也就是 pytest 进程里 Qt
    一定先于任何测试模块被加载 —— 此时 onnxruntime 再怎么预加载也来不及,
    进程内检查必然失败且与被测代码无关。
    因此把 OCR 检查放进**受控的子进程**, 用应用真实的加载顺序
    (入口预加载 onnxruntime -> PyQt6 -> onnxruntime -> RapidOCR) 来验证,
    既能真正检验 DLL 顺序, 又不受 pytest-qt 干扰。

失败分类:
    1. 真的没装(ModuleNotFoundError)  -> skip(合理)
    2. 装了但 DLL 加载失败            -> **失败**(绝不能 skip)
"""

import os
import subprocess
import sys
import unittest


_PROBE_CODE = (
    "import secureredact.main  # 入口模块内部已预加载 onnxruntime(P0-7)\n"
    "from PyQt6.QtWidgets import QApplication\n"
    "app = QApplication([])\n"
    "import onnxruntime\n"
    "from rapidocr_onnxruntime import RapidOCR\n"
    "ocr = RapidOCR()\n"
    "assert ocr is not None\n"
    "assert callable(ocr)\n"
    "public_methods = [m for m in dir(ocr) if not m.startswith('_')]\n"
    "assert len(public_methods) > 0\n"
    "print('RAPIDOCR-OK', onnxruntime.__version__)\n"
)


class TestRapidOCRAPI(unittest.TestCase):
    """OCR 引擎可用性(P0-7: 必须走应用真实的 DLL 加载顺序)。"""

    def _run_probe(self):
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        return subprocess.run(
            [sys.executable, "-c", _PROBE_CODE],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )

    def test_ocr_engine_usable_via_entry_order(self):
        """入口加载顺序下, onnxruntime 与 RapidOCR 必须都可用。"""
        proc = self._run_probe()
        out = (proc.stdout or "") + (proc.stderr or "")

        if "No module named" in out and ("rapidocr" in out or "onnxruntime" in out):
            self.skipTest("rapidocr_onnxruntime 未安装(依赖确实缺失)")

        msg = "OCR 引擎不可用(已安装但加载失败) —— 通常是 Windows 上 PyQt6 与 onnxruntime 的 MSVC runtime 冲突。"
        self.assertEqual(proc.returncode, 0, msg + "\nstdout=" + str(proc.stdout) + "\nstderr=" + str(proc.stderr))
        self.assertIn("RAPIDOCR-OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()