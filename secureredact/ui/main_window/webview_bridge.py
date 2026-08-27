"""
WebViewBridge — Python ↔ JavaScript 通信桥(Word 双栏预览用)

PR-B2.0: 从 main.py(原 4351-4575 行)迁出。本文件是 **纯搬运**,逻辑零改动。

职责:
- 接收 JS 调用:add_manual_redaction / remove_manual_redaction / ignore_ocr_hit /
  confirm_ocr_hit / promote_override / revert_override / handle_ocr_hit_contextmenu
- 维护滚动同步状态(_scroll_position / _pending_scroll_restore)
- 与 MainWindow 实例双向耦合:通过 main_window.word_data / _override_store /
  render_word_preview / _sync_word_compare_scroll 调用

跨类引用:`MainWindow` 通过 `from secureredact.ui.main_window import WebViewBridge` 使用。
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QObject, QPoint, pyqtSlot
from PyQt6.QtWidgets import QMenu, QMessageBox


class WebViewBridge(QObject):
    """Python 与 JavaScript 通信的桥梁"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._scroll_position = 0  # 保存的滚动位置
        self._pending_scroll_restore = False  # 是否有待恢复的滚动位置

    @pyqtSlot(str, int, int, str)
    def add_manual_redaction(self, key, start, end, selected_text):
        """添加精确手动脱敏(仅选中区域)

        Args:
            key: word_data 中的键(如 paragraph_0)
            start: 起始位置
            end: 结束位置
            selected_text: 被选中的文本
        """
        if key in self.main_window.word_data:
            # 检查重叠
            for existing in self.main_window.word_data[key]['manual']:
                if not (end <= existing['start'] or start >= existing['end']):
                    # 存在重叠,显示提示
                    QMessageBox.warning(self.main_window, "无法添加", "该区域与已有脱敏区域重叠")
                    return

            self.main_window.word_data[key]['manual'].append({
                'start': start,
                'end': end,
                'text': selected_text,
                'replacement': self.main_window.replacement_text,
                'mode': 'exact'  # 精确模式:只高亮选中区域
            })
            self.main_window.render_word_preview()
        else:
            # 添加调试日志
            print(f"警告: 键 '{key}' 不在 word_data 中")
            QMessageBox.warning(self.main_window, "添加失败", f"无法定位文本区域 (键: {key})")

    @pyqtSlot(str, str)
    def add_manual_redaction_global(self, key, selected_text):
        """添加全局手动脱敏(整篇相同文本)

        Args:
            key: 当前选中的 key(用于定位上下文)
            selected_text: 选中的文本
        """
        # 遍历所有 word_data,为每个包含该文本的位置添加脱敏
        for k, data in self.main_window.word_data.items():
            text = data['text']
            if not text:
                continue

            # 查找所有匹配位置
            pattern = re.escape(selected_text)
            for match in re.finditer(pattern, text):
                start = match.start()
                end = match.end()

                # 检查是否与已有脱敏重叠
                overlap = False
                for existing in data['manual']:
                    if not (end <= existing['start'] or start >= existing['end']):
                        overlap = True
                        break

                if not overlap:
                    data['manual'].append({
                        'start': start,
                        'end': end,
                        'text': selected_text,
                        'replacement': self.main_window.replacement_text,
                        'mode': 'global'  # 全局模式:高亮所有相同文本
                    })

        self.main_window.render_word_preview()

    @pyqtSlot(str, int, int)
    def remove_manual_redaction(self, key, start, end):
        """删除手动脱敏

        Args:
            key: word_data 中的键
            start: 起始位置
            end: 结束位置
        """
        if key in self.main_window.word_data:
            manual_list = self.main_window.word_data[key]['manual']
            # 查找要删除的项
            target_item = None
            for i, item in enumerate(manual_list):
                if item['start'] == start and item['end'] == end:
                    target_item = item
                    # 检查是否是全局模式
                    if item.get('mode') == 'global':
                        # 全局模式:删除所有相同文本的脱敏
                        text_to_remove = item['text']
                        self.remove_global_redaction(text_to_remove)
                    else:
                        # 精确模式:只删除当前项
                        manual_list.pop(i)
                        self.main_window.render_word_preview()
                    return

    def remove_global_redaction(self, text):
        """删除所有全局模式的脱敏(批量撤销)

        Args:
            text: 要删除的文本
        """
        count = 0
        for key, data in self.main_window.word_data.items():
            manual_list = data['manual']
            # 从后往前删除,避免索引问题
            for i in range(len(manual_list) - 1, -1, -1):
                item = manual_list[i]
                if item.get('mode') == 'global' and item['text'] == text:
                    manual_list.pop(i)
                    count += 1

        if count > 0:
            print(f"[撤销] 删除了 {count} 个全局脱敏: {text}")
            self.main_window.render_word_preview()

    # === v1.1.11: HitOverrideStore 4 槽 + contextmenu 入口 ===
    @pyqtSlot(str, str, str, str)
    def ignore_ocr_hit(self, key, source, text, hit_id):
        """JS 调用:忽略某条 OCR / jieba hit (session 级别)."""
        from secureredact.redaction.hit_ref import HitRef
        try:
            doc_hash, location, start_s, end_s, src = hit_id.split("|", 4)
            ref = HitRef(
                doc_hash=doc_hash, location=location,
                start=int(start_s), end=int(end_s),
                text=text, source=src,
            )
        except Exception as exc:
            print(f"[Bridge] ignore_ocr_hit 解析 hit_id 失败: {exc}")
            return
        self.main_window._override_store.ignore(ref, scope="session")
        self.main_window.render_word_preview()

    @pyqtSlot(str, str, str, str)
    def confirm_ocr_hit(self, key, source, text, hit_id):
        """JS 调用:确认某条 OCR / jieba hit 为敏感信息 (session 级别)."""
        from secureredact.redaction.hit_ref import HitRef
        try:
            doc_hash, location, start_s, end_s, src = hit_id.split("|", 4)
            ref = HitRef(doc_hash, location,
                         int(start_s), int(end_s), text, src)
        except Exception as exc:
            print(f"[Bridge] confirm_ocr_hit 解析 hit_id 失败: {exc}")
            return
        self.main_window._override_store.confirm(ref, scope="session")
        self.main_window.render_word_preview()

    @pyqtSlot(str)
    def promote_override(self, hit_id):
        """JS 调用:把已记录的 session override 提升为 permanent."""
        store = self.main_window._override_store
        store.promote(hit_id)
        # v1.1.11: 提升后立即落盘
        store.save_permanent()

    @pyqtSlot(str)
    def revert_override(self, hit_id):
        """JS 调用:撤销某条已记录的 override."""
        self.main_window._override_store.revert(hit_id)
        # v1.1.11: 若该 hit 是 permanent, 撤销后需落盘
        self.main_window._override_store.save_permanent()
        self.main_window.render_word_preview()

    @pyqtSlot(str, str, str, str, int, int)
    def handle_ocr_hit_contextmenu(self, key, source, text, hit_id, x, y):
        """JS 触发右键:弹 QMenu 把用户选择转给 ignore/confirm/promote/revert."""
        menu = QMenu(self.main_window)
        act_ig = menu.addAction("忽略此条 (本次)")
        act_cf = menu.addAction("确认是敏感信息 (本次)")
        menu.addSeparator()
        act_pm = menu.addAction("提升到永久名单")
        act_rv = menu.addAction("撤销")
        act_cancel = menu.addAction("取消")
        chosen = menu.exec(QPoint(int(x), int(y)))
        if chosen == act_ig:
            self.ignore_ocr_hit(key, source, text, hit_id)
        elif chosen == act_cf:
            self.confirm_ocr_hit(key, source, text, hit_id)
        elif chosen == act_pm:
            self.promote_override(hit_id)
        elif chosen == act_rv:
            self.revert_override(hit_id)

    def get_scroll_position(self):
        """获取当前保存的滚动位置"""
        return self._scroll_position

    def set_scroll_position(self, position):
        """设置要恢复的滚动位置"""
        self._scroll_position = position
        self._pending_scroll_restore = True

    def clear_pending_scroll_restore(self):
        """清除待恢复标志"""
        self._pending_scroll_restore = False

    def has_pending_scroll_restore(self):
        """检查是否有待恢复的滚动位置"""
        return self._pending_scroll_restore

    @pyqtSlot(str, float)
    def report_word_preview_scroll(self, panel_id, ratio):
        """接收 Word 双栏预览滚动比例并同步到另一侧。"""
        try:
            panel = str(panel_id or "").strip().lower()
            ratio_value = float(ratio)
        except (TypeError, ValueError):
            return
        self.main_window._sync_word_compare_scroll(panel, ratio_value)


__all__ = ["WebViewBridge"]