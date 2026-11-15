"""onnxruntime 预加载 —— 规避 Windows 上 PyQt6 与 onnxruntime 的 MSVC runtime 冲突。

背景 (P0-7, v1.1.15 打包验证时发现):
    打包产物里同时存在两份 MSVC runtime:
        _internal/msvcp140.dll                (541KB, onnxruntime 能用的那份)
        _internal/PyQt6/Qt6/bin/msvcp140.dll  (576KB, PyQt6 自带的那份)
    PyInstaller 会把 PyQt6/Qt6/bin 加入 DLL 搜索路径, 于是 PyQt6 先加载时绑定的是
    576KB 那份; 随后 onnxruntime 的 onnxruntime_pybind11_state.pyd 初始化失败:
        ImportError: DLL load failed while importing onnxruntime_pybind11_state:
                     动态链接库(DLL)初始化例程失败。
    后果: **OCR 全链路不可用**(PDF 扫描件 / 混合型 PDF / 图片通道全部失效)。

    更隐蔽的是: tests/unit/test_ocr_api.py 把这个 ImportError 当成「rapidocr 未安装」
    静默 skip, 于是 CI 全绿而 OCR 已坏 —— 这正是「CI 绿灯掩盖真实缺陷」的实例。

对策:
    在任何 PyQt6 import 之前先 import onnxruntime, 让 DLL 绑定顺序固定为 onnxruntime
    优先(它先拿到 _internal 里那份 541KB 的 msvcp140), 之后 PyQt6 复用同一个 runtime
    (Qt 向后兼容旧 runtime)。实测两种顺序:
        Qt 先 -> onnxruntime 失败
        ORT 先 -> 两者都正常
    代价: 启动期多约 0.5~1s。

安全约束:
    - 永不抛异常。预加载失败只记录告警, 真正的错误留给实际 OCR 时暴露。
    - 幂等。多次调用只真正加载一次。
    - 可用环境变量 SECUREREDACT_SKIP_ORT_PRELOAD=true 关闭(供无 OCR 依赖的环境用)。
"""

from __future__ import annotations

import os
import sys

_PRELOADED = False


def preload_onnxruntime() -> bool:
    """在任何 PyQt6 import 之前调用, 预加载 onnxruntime 以固定 DLL 绑定顺序。

    Returns:
        True 表示已成功预加载(或此前已加载); False 表示跳过或加载失败。
    """
    global _PRELOADED
    if _PRELOADED:
        return True
    _PRELOADED = True

    if os.environ.get("SECUREREDACT_SKIP_ORT_PRELOAD", "").lower() == "true":
        return False

    try:
        import onnxruntime  # noqa: F401  —— 仅为固定 DLL 加载顺序
        return True
    except Exception as exc:  # noqa: BLE001 — 预加载失败不阻断启动
        print(
            f"[preload] onnxruntime 预加载失败(实际 OCR 时会再次报错): {exc}",
            file=sys.stderr,
        )
        return False


__all__ = ["preload_onnxruntime"]