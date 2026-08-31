"""
SecureRedact 视觉回归基线 — 6 个具体场景 (PR-B2.0 引入)

每个场景一个 `BaselineScreenshotTest` 子类,共享基类提供的抓图 + 像素比对逻辑。

基类:`tests.ui.baseline_screenshots.BaselineScreenshotTest`
基线 PNG 存放:`tests/ui/baselines/<NAME>.png`
实拍图存放:`tests/ui/actual/<NAME>.png`

覆盖场景:
    01_idle_main_window          主窗口空态(拖放引导 + 工具栏默认态)        [B2.0 落实]
    02_single_page_canvas        PDF 单页画布独立 widget                     [B2.0 落实]
    03_pdf_with_hits             打开 PDF 后单页预览 + 命中红框               [B2.x 占位]
    04_word_dual_preview         Word 双栏预览(左原右替)                     [B2.x 占位]
    05_settings_dialog_overview  设置对话框首屏(规则面板)                    [B2.x 占位]
    06_batch_replace_results     批替换完成后的结果表格                      [B2.x 占位]
    (07_word_replace_rules_dialog  Word 替换规则编辑器 — 暂列 B4 范围,本文件未含)

运行方式:
    # 抓取新基线(覆盖现有基线,审定后再入库)
    PRIVACYGUARD_WRITE_BASELINES=1 python -m unittest tests.ui.test_baselines

    # 常规视觉比对
    python -m unittest tests.ui.test_baselines

    # 容差比对(抗字体/抗锯齿差异)
    BASELINE_TOLERANCE=2 python -m unittest tests.ui.test_baselines
"""

from __future__ import annotations

import os
import shutil
import unittest

from PyQt6.QtWidgets import QApplication, QWidget

from tests.ui.baseline_screenshots import (
    ACTUAL_DIR,
    BASELINES_DIR,
    BaselineScreenshotTest,
    _compare_pixmaps,
    DEFAULT_TOLERANCE,
    WRITE_BASELINES,
)
from PyQt6.QtGui import QPixmap


# 强制 offscreen 平台(无显示器环境)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ----------------------------------------------------------------------------
# B2.0 落实的 2 张基线(无文件依赖,可直接抓)
# ----------------------------------------------------------------------------

class TestIdleMainWindow(BaselineScreenshotTest):
    """01 — 主窗口空态。【占位】

    待 MainWindow 完全拆分(PR-B2.1~B2.6)+ OCR 预加载可关闭后,改用
    临时 mock config 抓取空态基线。当前若实例化 MainWindow 会触发
    OCR 引擎预加载,无图形环境会卡死。
    """
    NAME = "01_idle_main_window"

    def build_widget(self) -> QWidget:
        self.skipTest(
            "占位场景 — MainWindow 构造触发 OCR 预加载,在无图形/CI 环境会卡住;"
            "待 PR-B2.6 拆分稳定后,引入 mock config 抓取空态基线"
        )
        raise NotImplementedError  # 满足基类契约


class TestSinglePageCanvas(BaselineScreenshotTest):
    """02 — PDF 单页画布(独立 widget,无 MainWindow 依赖)。【B2.0 落实】

    场景:刚创建 SinglePageCanvas,未加载任何 pixmap。

    绕过基类 `_render()`(其事件循环在 offscreen 平台不稳),采用:
    resize + processEvents + sleep + grab 的同步流程。
    """
    NAME = "02_single_page_canvas"
    capture_size = __import__("PyQt6.QtCore", fromlist=["QSize"]).QSize(900, 1200)
    settle_ms = 300

    def build_widget(self) -> QWidget:
        from secureredact.ui.main_window import SinglePageCanvas
        return SinglePageCanvas(page_index=0)

    def test_baseline_match(self):
        """重写基类测试,绕开 _render() 事件循环依赖。"""
        import time
        # 基类 NAME 仍走基类的 skip 逻辑
        if not self.NAME:
            self.skipTest("abstract base")
            return
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        ACTUAL_DIR.mkdir(parents=True, exist_ok=True)
        baseline_path = BASELINES_DIR / f"{self.NAME}.png"
        actual_path = ACTUAL_DIR / f"{self.NAME}.png"

        widget = self.build_widget()
        widget.resize(self.capture_size)
        QApplication.processEvents()
        time.sleep(self.settle_ms / 1000.0)
        QApplication.processEvents()
        actual_pixmap = widget.grab()
        widget.close()
        QApplication.processEvents()

        actual_pixmap.save(str(actual_path), "PNG")

        if WRITE_BASELINES:
            shutil.copy(actual_path, baseline_path)
            self.skipTest(f"WROTE baseline {baseline_path.name}")

        if not baseline_path.exists():
            self.fail(
                f"Baseline missing: {baseline_path}\n"
                f"实拍图已落盘: {actual_path}\n"
                f"如确认基线正确,请执行:\n"
                f"  PRIVACYGUARD_WRITE_BASELINES=1 python -m unittest "
                f"tests.ui.test_baselines.{type(self).__name__}"
            )

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
# B2.x 占位的 4 张基线 — 暂用 skipTest,等 widget 拆分稳定后落实
# ----------------------------------------------------------------------------

class TestPdfWithHits(BaselineScreenshotTest):
    """03 — 打开 PDF 后单页预览 + 命中红框。【占位】"""
    NAME = "03_pdf_with_hits"

    def build_widget(self) -> QWidget:
        self.skipTest(
            "占位场景 — 需 MainWindow 完全拆分 + OCR 命中注入稳定后落实(PR-B2.3/B2.4)"
        )
        raise NotImplementedError  # 满足基类契约


class TestWordDualPreview(BaselineScreenshotTest):
    """04 — Word 双栏预览(左原右替)。【占位】"""
    NAME = "04_word_dual_preview"

    def build_widget(self) -> QWidget:
        self.skipTest(
            "占位场景 — 需 Word 双栏逻辑迁出到 secureredact.ui.main_window.word_preview 后落实(PR-B2.3)"
        )
        raise NotImplementedError


class TestSettingsDialogOverview(BaselineScreenshotTest):
    """05 — 设置对话框首屏(规则面板)。【占位】

    SettingsDialog 深度依赖 main.py 模块级常量(DEFAULT_RULES / DEFAULT_RULES_META / 等),
    本 PR-C2 范围无法独立实例化。留待后续 PR-C3.x 单独处理 SettingsDialog 模块依赖清理。
    """
    NAME = "05_settings_dialog_overview"

    def build_widget(self) -> QWidget:
        self.skipTest(
            "占位场景 — SettingsDialog __init__ 依赖 main.py 中 DEFAULT_RULES / DEFAULT_RULES_META 等 "
            "30+ 模块级常量,需独立 PR-C3.x 处理才能实例化"
        )
        raise NotImplementedError


class TestBatchReplaceResults(BaselineScreenshotTest):
    """06 — 批替换完成后的结果表格。【占位】"""
    NAME = "06_batch_replace_results"

    def build_widget(self) -> QWidget:
        self.skipTest(
            "占位场景 — 需批量替换逻辑迁出到 secureredact.ui.main_window.batch_replace 后落实(PR-B2.5)"
        )
        raise NotImplementedError


# ----------------------------------------------------------------------------
# 6 个子类继承自 BaselineScreenshotTest → unittest.TestCase,
# unittest discover 会自动发现并运行,无需自定义 load_tests。
# ----------------------------------------------------------------------------

# 在模块加载时即创建 QApplication(必须在导入 PyQt6 之后、widget 实例化之前),
# 否则 unittest 在测试方法内首次 QApplication.processEvents() 会触发隐式创建,
# 引发 offscreen 平台初始化竞态。
if QApplication.instance() is None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _qapp_for_module = QApplication([])


if __name__ == "__main__":
    unittest.main()