"""
SinglePageCanvas — PDF 单页画布(v1.1.13 行为不变)

PR-B2.0: 从 main.py(原 4092-4336 行)迁出。本文件是 **纯搬运**,逻辑零改动。
- 保留 PyQt6 信号 + 鼠标/滚轮事件处理原样
- 保留 v1.1.11 主窗口引用注入(set_main_window)避免循环依赖
- DEBUG_MODE 在本模块内重新定义(从 env 读取),与 main.py:318 等价

跨类引用:`MainWindow` 通过 `from secureredact.ui.main_window import SinglePageCanvas` 使用。
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QMessageBox,
)

from secureredact.redaction.hit_ref import HitRef


# DEBUG_MODE:与 main.py:318 行为对齐(仅读 env,不读 config.advanced.debug_mode)。
# 配置项默认 False,生产无影响;调试场景若 config 已显式 DEBUG=true 但 env 未设,
# 本模块读 env 拿到 false,造成 DEBUG 输出静默化。后续 PR-B2.x 阶段统一收口。
DEBUG_MODE = os.getenv("PRIVACYGUARD_DEBUG", "False").lower() == "true"


class SinglePageCanvas(QLabel):
    # 保留信号以兼容双页模式
    rect_added = pyqtSignal(int, QRectF)
    rect_removed = pyqtSignal(int, int, bool)
    zoom_request = pyqtSignal(float)
    page_change_request = pyqtSignal(int)  # 翻页请求信号:正值=下一页,负值=上一页

    def __init__(self, page_index=0, parent=None):
        super().__init__(parent)
        # 完全复制 v1.1.11 的初始化
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setAutoFillBackground(True)

        self.page_index = page_index  # 新增:用于双页模式
        self.zoom_scale = 1.0
        self.rects_ocr = []
        self.rects_manual = []
        self.mask_color = QColor(0, 0, 0)

        self.drawing = False
        self.start_point = QPointF()
        self.current_rect = QRectF()
        # v1.1.11: 注入 main_window 引用,供右键菜单读写 HitOverrideStore。
        # 由 MainWindow.setup_ui 在创建后调用 set_main_window 注入,避免循环依赖。
        self.main_window = None

    def set_mask_color(self, color):
        """v1.1.11 方法"""
        self.mask_color = color
        self.update()

    def set_main_window(self, main_window):
        """v1.1.11: 注入 MainWindow 引用,供右键菜单读写 override store."""
        self.main_window = main_window

    def _locate_hit(self, click_pos, *, prefer_manual: bool):
        """v1.1.11: 定位点击位置对应的 HitRef。

        返回 (HitRef, scope_marker) 或 None。
        scope_marker: 'manual' 或 'ocr' — 用于区分 hit 来自手动框还是 OCR 框。
        手动框无 text(画框时不带 OCR 文本),HitRef.text 留空。
        """
        if self.main_window is None:
            return None
        rects = self.rects_manual if prefer_manual else self.rects_ocr
        for r in rects:
            if self.pdf_to_screen(r).contains(click_pos):
                ref = HitRef(
                    doc_hash=self.main_window._current_doc_hash,
                    location=f"page_{self.page_index}",
                    start=int(r.x()),
                    end=int(r.x() + r.width()),
                    text="",
                    source="manual" if prefer_manual else "ocr",
                )
                return (ref, "manual" if prefer_manual else "ocr")
        return None

    def update_content(self, pixmap, scale, ocr_rects, manual_rects):
        """v1.1.11 方法 - 直接引用列表,不复制!"""
        self.setPixmap(pixmap)
        self.zoom_scale = scale
        self.rects_ocr = ocr_rects  # ← v1.1.11 直接引用,不复制
        self.rects_manual = manual_rects  # ← v1.1.11 直接引用,不复制
        self.update()

    # === v1.1.11: 完全回归 v1.1.11 - mousePressEvent 处理左右键 ===
    def mousePressEvent(self, event):
        """v1.1.11 风格:左键画框,右键删除"""
        if not self.pixmap():
            return

        # 左键画框
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.start_point = event.position()
            self.current_rect = QRectF(self.start_point, self.start_point)
            self.update()

        # 右键弹 QMenu (v1.1.11)
        elif event.button() == Qt.MouseButton.RightButton:
            click_pos = event.position()
            if DEBUG_MODE:
                print(f"\n[DEBUG] === 右键点击 === 页面{self.page_index}, 位置({click_pos.x():.2f}, {click_pos.y():.2f})")
                print(f"[DEBUG] 手动框数量: {len(self.rects_manual)}, OCR框数量: {len(self.rects_ocr)}")

            if self.main_window is None:
                return

            # v1.1.11: 优先找手动框 — 命中则 v1.1.11 行为:直接删除
            manual_hit_index = None
            for i, r in enumerate(self.rects_manual):
                if self.pdf_to_screen(r).contains(click_pos):
                    manual_hit_index = i
                    break

            if manual_hit_index is not None:
                # v1.1.11 行为:右键手动框直接删除,不做 store 操作
                del self.rects_manual[manual_hit_index]
                self.update()
                if hasattr(self.main_window, "render_view"):
                    self.main_window.render_view()
                return

            # 非手动框命中,再查 OCR 框
            hit_info = self._locate_hit(click_pos, prefer_manual=False)
            if hit_info is None:
                if DEBUG_MODE:
                    print(f"[DEBUG] ✗ 未点击到任何矩形框")
                return

            ref, scope = hit_info  # ref 是 HitRef, scope 是 'ocr'
            store = self.main_window._override_store

            menu = QMenu(self)
            act_ignore = menu.addAction("忽略此条 (本次)")
            act_confirm = menu.addAction("确认是敏感信息 (本次)")
            menu.addSeparator()
            act_promote = menu.addAction("提升到永久名单")
            act_revert = menu.addAction("撤销已记录的覆盖")
            menu.addSeparator()
            act_cancel = menu.addAction("取消")

            chosen = menu.exec(event.globalPosition().toPoint())
            if chosen == act_ignore:
                store.ignore(ref, scope="session")
            elif chosen == act_confirm:
                store.confirm(ref, scope="session")
            elif chosen == act_promote:
                # 必须先 ignore/confirm 后才能 promote
                if ref.hit_id not in [o.ref.hit_id for o in store.iter_overrides()]:
                    QMessageBox.information(self.main_window, "提示", "请先 ignore 或 confirm 后再提升")
                    return
                store.promote(ref.hit_id)
            elif chosen == act_revert:
                store.revert(ref.hit_id)
            else:
                return  # 用户选取消

            # 重画 canvas
            self.update()
            # 触发过滤重渲染
            if hasattr(self.main_window, "render_view"):
                self.main_window.render_view()

    def pdf_to_screen(self, rect):
        """v1.1.11 实现 - 带小的容错范围"""
        base_rect = QRectF(rect.x()*self.zoom_scale, rect.y()*self.zoom_scale,
                           rect.width()*self.zoom_scale, rect.height()*self.zoom_scale)
        # 扩展 2 像素容错范围,处理点击边界的情况
        return base_rect.adjusted(-2, -2, 2, 2)

    def paintEvent(self, event):
        """v1.1.11 实现"""
        super().paintEvent(event)
        if not self.pixmap(): return

        painter = QPainter(self)

        # 使用当前选中的颜色 (黑或白)
        painter.setBrush(self.mask_color)
        painter.setPen(Qt.PenStyle.NoPen)

        # 1. 绘制 AI 框
        for r in self.rects_ocr:
            sr = self.pdf_to_screen(r)
            painter.drawRect(sr)

        # 2. 绘制 手动框
        for r in self.rects_manual:
            sr = self.pdf_to_screen(r)
            painter.drawRect(sr)

        # 3. 绘制 拖拽框 (始终红色边框,提示用)
        if self.drawing and not self.current_rect.isEmpty():
            pen = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.current_rect)

    def mouseMoveEvent(self, event):
        """v1.1.11 实现"""
        if self.drawing and not self.start_point.isNull():
            current_pos = QPointF(event.position())
            self.current_rect = QRectF(self.start_point, current_pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        """v1.1.11 实现"""
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            if self.current_rect.width() > 5 and self.current_rect.height() > 5:
                real_rect = QRectF(
                    self.current_rect.x()/self.zoom_scale,
                    self.current_rect.y()/self.zoom_scale,
                    self.current_rect.width()/self.zoom_scale,
                    self.current_rect.height()/self.zoom_scale
                )
                # v1.1.11 直接添加到列表(列表是共享引用)
                self.rects_manual.append(real_rect)
            self.current_rect = QRectF()
            self.update()

    # v1.1.11: 增强滚轮事件 - 支持缩放和翻页
    # v1.1.11: 添加滚动阈值,防止 macOS 双指轻触误触发翻页
    SCROLL_THRESHOLD = 10  # 滚动阈值(像素),忽略小于此值的小幅滚动

    def wheelEvent(self, event: QWheelEvent):
        modifiers = QApplication.keyboardModifiers()
        delta = event.angleDelta().y()

        # v1.1.11: 忽略非常小的滚动量(macOS 双指轻触产生的噪声)
        if abs(delta) < self.SCROLL_THRESHOLD:
            # 小幅滚动只传递给父类处理正常滚动,不触发翻页
            super().wheelEvent(event)
            return

        # Ctrl/Cmd + 滚轮:缩放(保持原有功能)
        if modifiers == Qt.KeyboardModifier.ControlModifier or modifiers == Qt.KeyboardModifier.MetaModifier:
            event.accept()
            if delta > 0:
                self.zoom_request.emit(0.1)
            else:
                self.zoom_request.emit(-0.1)
        # Shift + 滚轮:快速翻页(一次2页)
        elif modifiers == Qt.KeyboardModifier.ShiftModifier:
            event.accept()
            if delta < 0:  # 向下滚动 = 下一页
                self.page_change_request.emit(2)
            else:  # 向上滚动 = 上一页
                self.page_change_request.emit(-2)
        # 普通滚轮:触发翻页信号(由 MainWindow 判断滚动条位置)
        else:
            # 发送翻页请求信号,由 MainWindow 处理边缘检测
            if delta < 0:
                self.page_change_request.emit(1)
            else:
                self.page_change_request.emit(-1)
            # 同时传递给父类以支持正常滚动
            super().wheelEvent(event)


__all__ = ["SinglePageCanvas", "DEBUG_MODE"]