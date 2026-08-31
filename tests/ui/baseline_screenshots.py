"""SecureRedact 视觉回归基线 (PR-B0 引入)。

目的:
    通过 QTest/QWidget.grab() 捕获关键 UI 截图,与基线 PNG 做像素级比对,
    防止 QSS / 组件拆分等改动引入不可见回归。

基线存放位置:
    tests/ui/baselines/<name>.png    — 人工审定的"金标准"
    tests/ui/actual/<name>.png       — 失败时落盘的"实拍图",便于本地 diff

覆盖场景(本期 6 帧):
    01_idle_main_window         主窗口空态 (拖放引导 + 工具栏默认态)
    02_pdf_single_page          打开 PDF 后单页预览 + 命中红框
    03_word_dual_preview        Word 双栏预览(左原右替)
    04_settings_dialog_overview 设置对话框首屏(规则面板)
    05_batch_replace_results    批替换完成后的结果表格
    06_word_replace_rules       Word 替换规则编辑器

运行方式:
    # 抓取基线(无基线时首次跑会失败并提示"missing baseline")
    PRIVACYGUARD_WRITE_BASELINES=1 python -m unittest tests.ui.baseline_screenshots

    # 视觉比对(常规 CI 跑这个)
    python -m unittest tests.ui.baseline_screenshots

    # 容差比对(DPI/字体渲染差异) — 通过 BASELINE_TOLERANCE 控制,默认 0 (严格)
    BASELINE_TOLERANCE=2 python -m unittest tests.ui.baseline_screenshots

注意:
    - 必须有图形环境(Windows 桌面 / X11 / macOS);CI 上需 Xvfb 或等效
    - 当前截图通过 QWidget.grab() 在内存中渲染,不依赖真实显示器
    - 渲染会受 Qt 字体回退影响,生产 CI 锁定镜像版本
"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QWidget


# ----------------------------------------------------------------------------
# 路径与开关
# ----------------------------------------------------------------------------

TESTS_UI_DIR = Path(__file__).resolve().parent
BASELINES_DIR = TESTS_UI_DIR / "baselines"
ACTUAL_DIR = TESTS_UI_DIR / "actual"

# 标准窗口尺寸(对应 1920x1080 桌面常用值,做 1.0x 截屏)
DEFAULT_CAPTURE_SIZE = QSize(1440, 900)

# 容差:每通道最大差值和(0 = 严格像素比对)
# 由于 Qt 字体/抗锯齿差异,跨平台 CI 通常需要 2~4
DEFAULT_TOLERANCE = int(os.environ.get("BASELINE_TOLERANCE", "0"))

# 写基线模式:PRIVACYGUARD_WRITE_BASELINES=1 时将实拍图覆盖基线
WRITE_BASELINES = os.environ.get("PRIVACYGUARD_WRITE_BASELINES", "").lower() in (
    "1", "true", "yes",
)


# ----------------------------------------------------------------------------
# 像素比对
# ----------------------------------------------------------------------------

def _compare_pixmaps(actual: QPixmap, expected: QPixmap, tolerance: int) -> tuple[bool, str]:
    """逐像素比较两张 QPixmap。

    Args:
        actual: 实拍图
        expected: 基线图
        tolerance: 每通道像素差和的容差

    Returns:
        (是否通过, 差异说明)
    """
    if actual.size() != expected.size():
        return False, (
            f"size mismatch: actual={actual.size().width()}x{actual.size().height()} "
            f"expected={expected.size().width()}x{expected.size().height()}"
        )

    actual_img = actual.toImage()
    expected_img = expected.toImage()

    width = actual_img.width()
    height = actual_img.height()
    diff_pixels = 0
    max_channel_diff = 0

    for y in range(height):
        for x in range(width):
            a_pixel = actual_img.pixel(x, y)
            e_pixel = expected_img.pixel(x, y)
            # QImage.pixel() 返回 ARGB (0xAARRGGBB)
            a_r, a_g, a_b = (a_pixel >> 16) & 0xFF, (a_pixel >> 8) & 0xFF, a_pixel & 0xFF
            e_r, e_g, e_b = (e_pixel >> 16) & 0xFF, (e_pixel >> 8) & 0xFF, e_pixel & 0xFF
            channel_diff = abs(a_r - e_r) + abs(a_g - e_g) + abs(a_b - e_b)
            if channel_diff > 0:
                diff_pixels += 1
                max_channel_diff = max(max_channel_diff, channel_diff)

    if diff_pixels == 0:
        return True, ""

    total_diff_ratio = diff_pixels / (width * height)
    if max_channel_diff <= tolerance:
        return True, (
            f"within tolerance: {diff_pixels} pixels differ "
            f"(max channel diff {max_channel_diff} <= tolerance {tolerance})"
        )

    return False, (
        f"{diff_pixels}/{width * height} pixels differ "
        f"({total_diff_ratio:.2%}), max channel diff={max_channel_diff}, "
        f"tolerance={tolerance}"
    )


# ----------------------------------------------------------------------------
# 测试用例基类
# ----------------------------------------------------------------------------

class BaselineScreenshotTest(unittest.TestCase):
    """视觉基线测试基类。

    子类必须重写:
        - NAME: str             基线文件名(不含 .png)
        - build_widget()        返回待截图的 QWidget 实例

    可选重写:
        - capture_size:         QSize,默认 DEFAULT_CAPTURE_SIZE
        - settle_ms:            int,渲染稳定等待毫秒,默认 200

    注意:
        基类本身被 unittest 收集时会自动 skip (NAME="" 触发),
        不会污染测试结果。子类必须设置 NAME 才能真正跑基线比对。
    """

    NAME: str = ""
    capture_size: QSize = DEFAULT_CAPTURE_SIZE
    settle_ms: int = 200

    def build_widget(self) -> QWidget:
        """构建并返回待截图的 QWidget。子类必须重写。"""
        raise NotImplementedError(f"{type(self).__name__}.build_widget()")

    # -- 渲染 --
    def _render(self, widget: QWidget) -> QPixmap:
        """渲染 widget 到 QPixmap。

        采用 time.sleep + processEvents 同步等待策略:
        - show() 之后 processEvents 让 widget 进入可视状态
        - time.sleep(settle_ms) 让 Qt 完成布局/字体度量/样式表应用
        - grab() 是同步渲染,立即返回当前帧
        - 避免依赖 QEventLoop.exec()/QTimer 在 offscreen 平台的兼容性问题
        """
        import time
        widget.resize(self.capture_size)
        widget.show()
        QApplication.processEvents()
        time.sleep(self.settle_ms / 1000.0)
        QApplication.processEvents()

        pixmap = widget.grab()
        widget.close()
        QApplication.processEvents()
        return pixmap

    # -- 测试主流程 --
    def test_baseline_match(self):
        # 基类 NAME="" → 自动 skip,不被收集为有效测试
        if not self.NAME:
            self.skipTest(
                f"{type(self).__name__}.NAME is empty; "
                "this is the abstract base class, not a runnable test"
            )
            return

        # 基线目录准备
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        ACTUAL_DIR.mkdir(parents=True, exist_ok=True)

        baseline_path = BASELINES_DIR / f"{self.NAME}.png"
        actual_path = ACTUAL_DIR / f"{self.NAME}.png"

        # 构建并截屏
        widget = self.build_widget()
        self.assertIsInstance(widget, QWidget)
        actual_pixmap = self._render(widget)

        # 总是保存 actual,便于本地对比
        actual_pixmap.save(str(actual_path), "PNG")

        # 写基线模式
        if WRITE_BASELINES:
            shutil.copy(actual_path, baseline_path)
            self.skipTest(
                f"WROTE baseline {baseline_path.name} "
                f"(PRIVACYGUARD_WRITE_BASELINES=1, no comparison)"
            )

        # 基线缺失:首次运行友好提示
        if not baseline_path.exists():
            self.fail(
                f"Baseline missing: {baseline_path}\n"
                f"实拍图已落盘: {actual_path}\n"
                f"如确认基线正确,请执行:\n"
                f"  PRIVACYGUARD_WRITE_BASELINES=1 python -m unittest "
                f"tests.ui.baseline_screenshots.{type(self).__name__}"
            )

        # 像素比对
        expected_pixmap = QPixmap(str(baseline_path))
        self.assertFalse(expected_pixmap.isNull(), f"基线图损坏: {baseline_path}")

        passed, message = _compare_pixmaps(actual_pixmap, expected_pixmap, DEFAULT_TOLERANCE)
        if not passed:
            self.fail(
                f"Visual regression in '{self.NAME}': {message}\n"
                f"  actual: {actual_path}\n"
                f"  baseline: {baseline_path}\n"
                f"  如确认新截图正确,执行 PRIVACYGUARD_WRITE_BASELINES=1 更新基线"
            )
        if message:
            print(f"[BASELINE] {self.NAME}: {message}")


# ----------------------------------------------------------------------------
# QApplication 单例 fixture(给后续具体子类用)
# ----------------------------------------------------------------------------

class _QAppMixin:
    """混入 setUpClass/tearDownClass,确保 QApplication 只创建一次。"""

    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            # offscreen 平台插件允许在无显示器环境渲染
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            cls._qt_app = QApplication([])
        else:
            cls._qt_app = QApplication.instance()

    @classmethod
    def tearDownClass(cls):
        # 不主动 quit,让其他用例复用
        pass