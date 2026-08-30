"""SecureRedact 运行时入口 (v1.1.13,PR-B0 引入)。

职责:
    1. 启动 QApplication
    2. 安装全局异常钩子与线程异常钩子
    3. (可选) 预加载 OCR 引擎
    4. 设置应用图标
    5. 创建并展示主窗口

阶段 B 历史:
    - PR-B0 (本期): 本模块独立,MainWindow 仍由 main.py 提供(懒加载)
    - PR-B2: MainWindow 迁入 secureredact/ui/main_window/,本模块去掉懒加载
    - PR-B5: main.py 完全停用,仅本模块作为唯一启动入口

启动方式:
    python -m secureredact.main        # 新入口(推荐)
    python main.py                     # 兼容 shim(阶段 B5 收口时移除)
    pyinstaller SecureRedact_verify.spec   # 打包入口 (PR-B5 时切换到此模块)

环境变量:
    PRIVACYGUARD_PRELOAD_OCR=true      # 启动期预加载 OCR 引擎(可选,用于早期检测问题)
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional, Sequence


# ----------------------------------------------------------------------------
# 异常钩子
# ----------------------------------------------------------------------------

def _install_uncaught_exception_hook() -> None:
    """安装全局 + 线程异常钩子(原 main.py 行为)。

    行为:
        - 未捕获异常 → 打印到 stderr + 尝试弹 QMessageBox → 走默认钩子
        - 线程异常 → 仅打印到 stderr(QMessageBox 必须在主线程)

    静默/吞错策略: 永不静默。所有未捕获异常必须可见。
    """
    def _exception_hook(exc_type, exc_value, exc_traceback):
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"[FATAL ERROR] 未捕获的异常:\n{error_msg}", file=sys.stderr)
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "程序错误",
                    f"程序遇到未预期的错误:\n\n{exc_type.__name__}: {exc_value}\n\n"
                    "请将此错误信息反馈给开发者。",
                )
        except Exception:
            # 弹框失败也不能再抛 — 已是最末级 fallback
            pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def _thread_exception_hook(args):
        error_msg = ''.join(traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_traceback
        ))
        print(f"[THREAD ERROR] 线程异常:\n{error_msg}", file=sys.stderr)

    sys.excepthook = _exception_hook
    threading.excepthook = _thread_exception_hook


# ----------------------------------------------------------------------------
# 应用图标
# ----------------------------------------------------------------------------

def _set_window_icon(app) -> None:
    """设置应用图标(256x256 PNG)。图标缺失不阻断启动。"""
    from PyQt6.QtGui import QIcon
    icon_path = (
        Path(__file__).resolve().parent.parent
        / 'assets' / 'logo' / 'export' / '256' / 'logo_default_256.png'
    )
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        print(f"[INFO] 应用图标已加载: {icon_path}")
    else:
        print(f"[WARN] 应用图标未找到: {icon_path}")


# ----------------------------------------------------------------------------
# OCR 预加载
# ----------------------------------------------------------------------------

def _maybe_preload_ocr() -> None:
    """PRIVACYGUARD_PRELOAD_OCR=true 时启动期预加载 OCR 引擎。

    失败不阻断启动 — 仅记录警告。这是 v1.1.11 起保留的可选启动行为,
    主要用于早期暴露 OCR 依赖问题,默认关闭。
    """
    if os.getenv('PRIVACYGUARD_PRELOAD_OCR', '').lower() != 'true':
        return
    print("[INFO] 预加载 OCR 引擎...")
    try:
        # main.init_ocr_engine 仍由 main.py 提供 (PR-B2 才会迁出)
        from main import init_ocr_engine  # type: ignore[import-not-found]
        init_ocr_engine()
    except ImportError as exc:
        print(f"[WARN] OCR 预加载失败 (main.py 不可达): {exc}", file=sys.stderr)
    except Exception as exc:
        # 任何 OCR 错误也不能阻断 GUI 启动
        print(f"[WARN] OCR 预加载失败: {exc}", file=sys.stderr)


# ----------------------------------------------------------------------------
# 主入口
# ----------------------------------------------------------------------------

def _create_main_window():
    """懒加载 MainWindow。

    PR-B0~B1 阶段: MainWindow 仍在 main.py(兼容旧路径)
    PR-B2 起: 改 import 路径到 secureredact.ui.main_window.window

    统一在本函数内集中切换,避免散落在调用方。
    """
    from secureredact.ui.main_window import MainWindow
    return MainWindow


def main(argv: Optional[Sequence[str]] = None) -> int:
    """SecureRedact 运行时入口函数。

    Args:
        argv: 命令行参数列表;None 时使用 sys.argv。
              主要为单元测试与视觉基线测试提供注入点。

    Returns:
        int: QApplication.exec() 返回的退出码。
    """
    if argv is None:
        argv = sys.argv

    _install_uncaught_exception_hook()
    _maybe_preload_ocr()

    from PyQt6.QtWidgets import QApplication

    app = QApplication(list(argv))
    _set_window_icon(app)

    MainWindow = _create_main_window()
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())