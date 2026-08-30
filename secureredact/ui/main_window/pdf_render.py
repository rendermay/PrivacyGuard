"""
PDF 渲染编排 mixin — MainWindow PDF 渲染逻辑 (PR-B2.4 迁出)

提供 13 个 PDF 渲染核心方法,作为 `MainWindowPdfRenderMixin`。
`MainWindow` 通过多继承复用本 mixin,行为零改动。

来源:原 `main.py` 中 13 个 PDF 渲染相关方法(共 ~365 行),逐字搬迁,逻辑零改动。

依赖 MainWindow 上的属性:
    - self.current_page / self.doc / self.current_doc_hash
    - self.file_path / self.pdf_workspace_outer_layout
    - self.single_page_canvas / self.canvas_pages
    - self.zoom_scale / self.theme / self.Theme
"""
from __future__ import annotations

import fitz  # PyMuPDF

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget,
)


class MainWindowPdfRenderMixin:
    """PDF 单页 / 双页渲染 + canvas 安全更新 + 缩放 / 翻页 / 命中接收。

    方法签名与实现与原 MainWindow 内一致,直接被 MainWindow 继承使用。
    """

    def _is_canvas_valid(self, canvas):
        """v1.1.11: 检查 canvas 的 C++ 对象是否仍然有效"""
        if canvas is None:
            return False
        try:
            # 尝试访问一个简单的属性来验证对象是否有效
            _ = canvas.size()
            return True
        except RuntimeError:
            # C++ 对象已被删除
            return False

    def _safe_canvas_update(self, canvas, pixmap, scale, ocr_rects, manual_rects):
        """v1.1.11: 安全地更新 canvas 内容"""
        if not self._is_canvas_valid(canvas):
            print(f"[警告] canvas 无效，跳过更新")
            return False
        try:
            canvas.update_content(pixmap, scale, ocr_rects, manual_rects)
            return True
        except RuntimeError as e:
            print(f"[错误] 更新 canvas 时出错: {e}")
            return False

    def _safe_canvas_set_mask_color(self, canvas, color):
        """v1.1.11: 安全地设置 canvas 遮罩颜色"""
        if not self._is_canvas_valid(canvas):
            return False
        try:
            canvas.set_mask_color(color)
            return True
        except RuntimeError as e:
            print(f"[错误] 设置 canvas 颜色时出错: {e}")
            return False

    def handle_zoom_request(self, delta):
        from main import ZOOM_MIN, ZOOM_MAX  # PR-B5.2: 延迟导入
        new_zoom = self.zoom_level + delta
        if new_zoom < ZOOM_MIN: new_zoom = ZOOM_MIN
        if new_zoom > ZOOM_MAX: new_zoom = ZOOM_MAX
        self.zoom_level = new_zoom
        self.render_view()

    def update_canvas_color(self):
        if self.rb_black.isChecked(): self.current_color = QColor(0,0,0)
        else: self.current_color = QColor(255,255,255)
        self.render_view()

    def clamp_zoom(self, zoom, allow_below_min=False):
        """
        将缩放值限制在有效范围内 (v1.1.11)

        Args:
            zoom: 缩放值
            allow_below_min: 是否允许低于 ZOOM_MIN (用于自适应模式)
        """
        from main import ZOOM_MIN, ZOOM_MAX  # PR-B5.2: 延迟导入
        if allow_below_min:
            # 自适应模式：允许更小的缩放比例以完整显示页面
            return min(ZOOM_MAX, zoom)
        else:
            # 手动模式：保持正常限制，防止过小
            return max(ZOOM_MIN, min(ZOOM_MAX, zoom))

    def fit_page(self):
        """完整适应页面 - 根据窗口和页面尺寸动态计算缩放比例"""
        if not self.doc or self.current_page is None:
            return

        # 获取画布可用尺寸（减去边距）
        canvas_width = self.scroll.width() - 40  # 40px 边距
        canvas_height = self.scroll.height() - 40

        # 获取当前页面的实际尺寸（点单位）
        page = self.doc[self.current_page]
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        # 分别计算宽度和高度的缩放比例
        zoom_w = canvas_width / page_width
        zoom_h = canvas_height / page_height

        # 取较小值确保页面完整显示在窗口中
        self.zoom_level = min(zoom_w, zoom_h)

        # 限制在最大最小范围内 (v1.1.11: 允许突破 ZOOM_MIN 以完整显示)
        self.zoom_level = self.clamp_zoom(self.zoom_level, allow_below_min=True)

        # 重新渲染
        self.render_view()

    def render_view(self):
        if not self.doc: return
        # v1.1.11: 添加 canvas 有效性检查
        if not self._is_canvas_valid(self.canvas_left):
            print("[警告] canvas_left 无效，跳过渲染")
            return
        self._render_single_page(self.canvas_left, self.current_page)
        if self.dual_view:
            if self.current_page + 1 < len(self.doc):
                if self._is_canvas_valid(self.canvas_right):
                    self._render_single_page(self.canvas_right, self.current_page + 1)
                    self.canvas_right.show()
            else:
                if self._is_canvas_valid(self.canvas_right):
                    self.canvas_right.hide()

        total = len(self.doc)
        display = f"{self.current_page + 1}"
        if self.dual_view and self.current_page + 1 < total:
            display += f"-{self.current_page + 2}"
        self.lbl_page.setText(f"{display} / {total}")
        self.lbl_zoom.setText(f"{int(self.zoom_level * 100)}%")
        self._refresh_toolbar_responsiveness()
        self._refresh_workbench_context()

    def _render_single_page(self, canvas, page_idx):
        """v1.1.11 风格渲染 - 直接传递列表引用
        v1.1.11: 添加异常处理防止 canvas 被删除后崩溃
        v1.1.11: 同步 canvas.page_index — 保证 PDFCanvas.mousePressEvent 中
        _locate_hit 用 f"page_{page_index}" 与 _rects_for_page 命中同一 hit_id
        """
        # 检查 canvas 有效性
        if not self._is_canvas_valid(canvas):
            return

        try:
            page = self.doc[page_idx]
            pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom_level, self.zoom_level))
            img_fmt = QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, img_fmt).copy()
            data = self.page_data[page_idx]
            # v1.1.11: 用 _rects_for_page 走 store 过滤后再喂 canvas
            ocr_rects = self._rects_for_page(page_idx)
            self._safe_canvas_update(canvas, QPixmap.fromImage(qimg), self.zoom_level,
                                     ocr_rects, data['manual'])
            self._safe_canvas_set_mask_color(canvas, self.current_color)
            # v1.1.11: 关键修复 — canvas.page_index 必须随渲染同步,否则
            # PDFCanvas.mousePressEvent 中 _locate_hit 构造 HitRef 用错 location,
            # 与 _rects_for_page 过滤时的 hit_id 不匹配 → 黑块无法消失
            canvas.page_index = page_idx
        except RuntimeError as e:
            print(f"[错误] 渲染页面 {page_idx} 时出错: {e}")
        except Exception as e:
            print(f"[错误] 渲染页面 {page_idx} 时发生意外错误: {e}")

    def change_page(self, delta):
        if not self.doc: return
        step = 2 if self.dual_view else 1
        new_page = self.current_page + (delta * step)
        if new_page < 0: new_page = 0
        if new_page >= len(self.doc): return
        self.current_page = new_page
        self.render_view()
        self.scroll.verticalScrollBar().setValue(0)

    def handle_page_change_request(self, delta):
        """处理滚轮翻页请求（v1.1.11 新增）

        Args:
            delta: 翻页数量，正值=向后翻页，负值=向前翻页
                   1/-1 = 普通滚轮（需检测边缘）
                   2/-2 = Shift+滚轮（快速翻页）
        """
        if not self.doc:
            return

        # 快速翻页（Shift+滚轮）：直接翻页，不检测边缘
        if abs(delta) >= 2:
            self.change_page(1 if delta > 0 else -1)
            return

        # 普通滚轮：检测滚动条位置，只在边缘时翻页
        scroll_bar = self.scroll.verticalScrollBar()
        at_top = scroll_bar.value() <= scroll_bar.minimum() + 10
        at_bottom = scroll_bar.value() >= scroll_bar.maximum() - 10

        # 向上滚动且在顶部 → 上一页
        if delta < 0 and at_top and self.current_page > 0:
            self.change_page(-1)
            # 翻页后滚动到底部，便于连续向上翻页
            QApplication.processEvents()
            scroll_bar.setValue(scroll_bar.maximum())
        # 向下滚动且在底部 → 下一页
        elif delta > 0 and at_bottom and self.current_page < len(self.doc) - 1:
            self.change_page(1)
            # 翻页后滚动到顶部
            scroll_bar.setValue(0)

    def _receive_page_hits(self, page_idx: int, hits: list) -> None:
        """v1.1.11: 接收 OCRWorker 逐页 hit dict 列表,过滤后存 page_data + 渲染。

        参数:
            page_idx: 页码(0-based)
            hits: list[dict],每个 dict 含 rect(QRectF)/source(str)/text(str)/rule_name(str)

        行为:
            1. raw 全量写入 page_data[idx]['ocr'](便于 revert 后再次出现)
            2. store.filtered_hits 过滤(manual 永远保留,ignore 命中剔除)
            3. 若本页当前正在显示(canvas_left = current_page 或 dual 时 right=current_page+1),
               调用 render_view() 走 _rects_for_page 自动喂过滤后的 QRectF
        """
        self._ocr_processed_pages.add(page_idx)
        self.page_data.setdefault(page_idx, {"ocr": [], "manual": []})
        self.page_data[page_idx]["ocr"] = list(hits)

        # 触发 canvas 刷新(只在当前显示页时)
        if self.doc is None:
            return
        displayed_pages = {self.current_page}
        if self.dual_view and self.current_page + 1 < len(self.doc):
            displayed_pages.add(self.current_page + 1)
        if page_idx in displayed_pages:
            self.render_view()

    def _rects_for_page(self, page_idx: int) -> list:
        """v1.1.11: 返回过滤后的 QRectF 列表,供 canvas 渲染与 PDF 导出共用。

        filtered_hits:
          - manual 永远保留
          - ignore 命中剔除
          - confirm / 未操作 保留

        返回 list[QRectF],不可用于写回 — 仅供渲染与导出。
        """
        return self._filter_hits_to_rects(
            self.page_data.get(page_idx, {}).get("ocr", []),
            store=self._override_store,
            location=f"page_{page_idx}",
            doc_hash=self._current_doc_hash,
        )
