"""Phase 3 Word 候选审阅对话框（UX-01 / UX-02 极简版 — Wave 3 完整实施）。

承载 Word 文档 PII 候选的人工审阅流程：
- 实体类型 / 来源双维度筛选
- 50 条分页（PAGE_SIZE = 50, D-25 锁）
- 4 CTAs（确认选中的 N 项 / 全选当前页 / 清空当前选择 / 关闭）
- hit identity 四元组 (entity_type, key, page_offset, page_length) 跨翻页持久化（per BLOCKER 4）
- 行 label normalized[:30] + '...' 截断（per Visuals §PII Highlight §long-text 锁）
- confirmed 信号 payload = list[dict{key, hit, source}]（per D-18 契约）
"""
from dataclasses import asdict
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE, PIIHit


# 9 类 entity 中文显示标签（D-21 锁 + Visuals §Copywriting 一致）
ENTITY_TYPE_LABEL: dict = {
    'CN_ID_CARD': '身份证号',
    'CN_PHONE': '手机号',
    'CN_BANK_CARD': '银行卡号',
    'CN_EMAIL': '电子邮箱',
    'CN_USCC': '统一社会信用代码',
    'CN_TAXPAYER_ID': '纳税人识别号（18 位）',
    'CN_TAXPAYER_ID_15': '纳税人识别号（15 位）',
    'CN_VAT_INVOICE': '增值税发票号',
    'CN_BANK_ACCOUNT': '银行账号',
}


# 单页显示条数（D-25 锁 + 03-RESEARCH.md Pitfall 4 性能预算 < 50ms）
PAGE_SIZE = 50


class WordCandidateDialog(QDialog):
    """Phase 3 Word 候选审阅极简版（D-11 / D-25 / UX-01 / UX-02 — Wave 3 完整 UI 行为）。"""

    PAGE_SIZE = 50

    # confirmed 信号 payload: list[dict{key, hit_dict, source}] —— main.py:_on_word_candidate_dialog_accept 接收
    confirmed = pyqtSignal(list)

    def __init__(self, word_data: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.word_data = word_data or {}
        self._all_hits: List[dict] = []
        # self._selection: hit_identity 四元组 → 是否选中（per BLOCKER 4 跨翻页持久化）
        self._selection: dict = {}
        self._page = 0
        self.setWindowTitle('Word 候选审阅')
        self.resize(700, 600)
        self._build_hit_list()
        self._init_selection()  # 默认全部 True（per D-25 锁）
        self._init_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # Hit identity（per BLOCKER 4 —— 4 元组稳定标识）
    # ------------------------------------------------------------------
    @staticmethod
    def _hit_identity(entry: dict) -> tuple:
        """per BLOCKER 4：stable hit identity = (entity_type, key, page_offset, page_length) 四元组。

        entry = {'key': ..., 'hit': PIIHit|dict, 'source': ..., 'normalized': ...}
        返回四元组 tuple 用于 self._selection dict 持久化 + 跨翻页 checkbox 状态恢复。
        """
        hit = entry.get('hit') or {}
        if isinstance(hit, PIIHit):
            return (
                hit.entity_type,
                entry.get('key', ''),
                hit.page_offset,
                hit.page_length,
            )
        # hit 是 dict 形态（main.py 写回的 confirmed channel）
        return (
            hit.get('entity_type', ''),
            entry.get('key', ''),
            hit.get('page_offset', 0),
            hit.get('page_length', 0),
        )

    @staticmethod
    def _hit_to_dict(hit) -> dict:
        """防御性 hit → dict 转换（PIIHit 实例走 asdict；dict 直接返回）。"""
        if isinstance(hit, dict):
            return dict(hit)
        if isinstance(hit, PIIHit):
            return asdict(hit)
        return {}

    @staticmethod
    def _hit_entity_type(hit) -> str:
        """防御性 hit.entity_type 读取（PIIHit 与 dict 两形态）。"""
        if isinstance(hit, PIIHit):
            return hit.entity_type
        if isinstance(hit, dict):
            return hit.get('entity_type', '') or ''
        return ''

    # ------------------------------------------------------------------
    # 数据收集 + 默认选中
    # ------------------------------------------------------------------
    def _build_hit_list(self):
        """遍历 self.word_data 三通道 (pii / ocr / manual) 收集全部 hit。

        防御性 isinstance check：hit 可能是 PIIHit dataclass 实例或 dict；
        - PIIHit → asdict() 转换为 dict + 保留 normalized 字符串
        - dict → 保留 normalized 字段（缺失则 ''）
        """
        for key, data in self.word_data.items():
            if not isinstance(data, dict):
                continue
            for src in ('pii', 'ocr', 'manual'):
                items = data.get(src) or []
                for hit in items:
                    if isinstance(hit, PIIHit):
                        hit_dict = asdict(hit)
                        normalized = hit.normalized or ''
                    elif isinstance(hit, dict):
                        hit_dict = dict(hit)
                        normalized = (
                            hit_dict.get('normalized')
                            or hit_dict.get('text')
                            or ''
                        )
                    else:
                        continue
                    self._all_hits.append({
                        'key': key,
                        'hit': hit_dict,
                        'source': src,
                        'normalized': normalized,
                    })

    def _init_selection(self):
        """初始化时所有 hit 默认选中（per D-25 锁）；用户可手动 uncheck。"""
        for entry in self._all_hits:
            self._selection[self._hit_identity(entry)] = True

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _init_ui(self):
        """完整 UI 行为：顶部筛选工具栏 + 候选列表 + 翻页栏 + 4 CTAs。"""
        layout = QVBoxLayout(self)

        # 顶部筛选工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel('实体类型：'))
        self.entity_filter = QComboBox()
        self.entity_filter.addItem('全部', '')
        for et in ENTITY_TYPE_LABEL:
            self.entity_filter.addItem(ENTITY_TYPE_LABEL[et], et)
        self.entity_filter.currentIndexChanged.connect(self._refresh)
        toolbar.addWidget(self.entity_filter)

        toolbar.addWidget(QLabel('来源：'))
        self.source_filter = QComboBox()
        self.source_filter.addItem('全部', '')
        for src_label, src_value in (
            ('PII', 'pii'),
            ('OCR', 'ocr'),
            ('手动', 'manual'),
        ):
            self.source_filter.addItem(src_label, src_value)
        self.source_filter.currentIndexChanged.connect(self._refresh)
        toolbar.addWidget(self.source_filter)

        toolbar.addStretch(1)
        self.selected_count_label = QLabel('0 项已选')
        toolbar.addWidget(self.selected_count_label)
        layout.addLayout(toolbar)

        # 候选列表
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(520)
        self.list_widget.setMaximumHeight(640)
        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

        # 空态文案（过滤后 0 条但 _all_hits 非空时显示）
        self.empty_label = QLabel('当前筛选下无候选，请放宽实体类型或来源筛选。')
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        # 翻页栏
        pager = QHBoxLayout()
        self.btn_prev = QPushButton('上一页')
        self.btn_prev.clicked.connect(self._prev_page)
        pager.addWidget(self.btn_prev)
        self.btn_next = QPushButton('下一页')
        self.btn_next.clicked.connect(self._next_page)
        pager.addWidget(self.btn_next)
        self.page_label = QLabel('第 1 / 1 页（共 0 条）')
        pager.addWidget(self.page_label)
        pager.addStretch(1)
        self.btn_close = QPushButton('关闭')
        self.btn_close.clicked.connect(self.reject)
        pager.addWidget(self.btn_close)
        layout.addLayout(pager)

        # CTA 栏（4 CTAs — D-11 锁）
        cta = QHBoxLayout()
        cta.addStretch(1)
        self.btn_clear_selection = QPushButton('清空当前选择')
        self.btn_clear_selection.clicked.connect(self._on_clear_selection)
        cta.addWidget(self.btn_clear_selection)
        self.btn_select_all = QPushButton('全选当前页')
        self.btn_select_all.clicked.connect(self._on_select_all)
        cta.addWidget(self.btn_select_all)
        self.btn_confirm = QPushButton('确认选中的 0 项')
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        cta.addWidget(self.btn_confirm)
        layout.addLayout(cta)

    # ------------------------------------------------------------------
    # 筛选 + 渲染
    # ------------------------------------------------------------------
    def _filtered_hits(self) -> List[dict]:
        """按 entity_type + source 双维度过滤（per UX-02 + D-25）。"""
        et = self.entity_filter.currentData() if hasattr(self, 'entity_filter') else ''
        src = self.source_filter.currentData() if hasattr(self, 'source_filter') else ''
        out = []
        for entry in self._all_hits:
            hit = entry.get('hit') or {}
            entity_type = self._hit_entity_type(hit)
            if et and entity_type != et:
                continue
            if src and entry.get('source') != src:
                continue
            out.append(entry)
        return out

    def _refresh(self):
        """单次 _refresh 遍历 ≤ 50 条（PAGE_SIZE = 50）；性能预算 < 50ms（per 03-RESEARCH Pitfall 4）。"""
        # 临时屏蔽 itemChanged 信号以避免 _refresh 自身修改 checkbox 状态触发回调
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            filtered = self._filtered_hits()
            total = len(filtered)
            total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
            if self._page >= total_pages:
                self._page = total_pages - 1
            if self._page < 0:
                self._page = 0
            start = self._page * self.PAGE_SIZE
            end = min(start + self.PAGE_SIZE, total)

            for entry in filtered[start:end]:
                hit = entry.get('hit') or {}
                entity_type = self._hit_entity_type(hit)
                label_text = ENTITY_TYPE_LABEL.get(entity_type, entity_type)
                short_code = ENTITY_TYPE_SHORT_CODE.get(entity_type, entity_type)
                normalized = entry.get('normalized') or ''
                # 行 label normalized[:30] + '...' 截断（per Visuals §PII Highlight §long-text 锁）
                if len(normalized) > 30:
                    display_text = normalized[:30] + '...'
                else:
                    display_text = normalized
                row_text = (
                    f"[{entry['source']}] {short_code} · {label_text} · "
                    f"{display_text} @ {entry.get('key', '')}"
                )
                item = QListWidgetItem(row_text)
                item.setData(Qt.ItemDataRole.UserRole, entry)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                # per BLOCKER 4：从 self._selection 恢复 checkbox 状态（跨翻页持久化）
                hit_id = self._hit_identity(entry)
                checked = self._selection.get(hit_id, True)
                item.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
                self.list_widget.addItem(item)

            self.page_label.setText(
                f'第 {self._page + 1} / {total_pages} 页（共 {total} 条）'
            )
            self.btn_prev.setEnabled(self._page > 0)
            self.btn_next.setEnabled(self._page < total_pages - 1)
            self.empty_label.setVisible(total == 0)
            self.btn_confirm.setEnabled(total > 0)
        finally:
            self.list_widget.blockSignals(False)
        self._update_selected_count()

    def _update_selected_count(self):
        """更新已选数量 label + 主 CTA 文本。"""
        checked = sum(
            1 for entry in self._all_hits
            if self._selection.get(self._hit_identity(entry), True)
        )
        self.selected_count_label.setText(f'{checked} 项已选')
        self.btn_confirm.setText(f'确认选中的 {checked} 项')

    # ------------------------------------------------------------------
    # 翻页
    # ------------------------------------------------------------------
    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._refresh()

    def _next_page(self):
        filtered = self._filtered_hits()
        total_pages = max(1, (len(filtered) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self._page < total_pages - 1:
            self._page += 1
            self._refresh()

    # ------------------------------------------------------------------
    # CTA handlers
    # ------------------------------------------------------------------
    def _on_select_all(self):
        """全选当前页（写入 self._selection + 同步 checkbox UI）。"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            hit_id = self._hit_identity(entry)
            self._selection[hit_id] = True
            item.setCheckState(Qt.CheckState.Checked)
        self._update_selected_count()

    def _on_clear_selection(self):
        """清空当前页选择（写入 self._selection + 同步 checkbox UI）。"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            hit_id = self._hit_identity(entry)
            self._selection[hit_id] = False
            item.setCheckState(Qt.CheckState.Unchecked)
        self._update_selected_count()

    def _sync_selection_from_list(self):
        """把当前页 list_widget 的 checkbox 状态同步回 self._selection（per BLOCKER 4）。

        当测试通过 setCheckState 修改 checkbox 但 _on_item_changed 信号未触发时
        （PyQt 测试场景常见），调用此方法确保 self._selection 与 list_widget 一致。
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry is None:
                continue
            hit_id = self._hit_identity(entry)
            self._selection[hit_id] = (
                item.checkState() == Qt.CheckState.Checked
            )

    def _on_item_changed(self, item):
        """itemChanged 信号回调：checkbox 状态变化时同步进 self._selection（per BLOCKER 4）。"""
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        hit_id = self._hit_identity(entry)
        self._selection[hit_id] = (item.checkState() == Qt.CheckState.Checked)
        self._update_selected_count()

    def _on_confirm_clicked(self):
        """点击 '确认选中的 N 项'：遍历 self._all_hits 全量（非当前页 —— per BLOCKER 4），
        按 self._selection 收集确认的 hit → emit confirmed signal → accept dialog。
        payload 形态：list[dict{key, hit_dict, source}]（per D-18 契约）。
        """
        payload = []
        for entry in self._all_hits:
            hit_id = self._hit_identity(entry)
            if not self._selection.get(hit_id, True):
                continue
            hit_dict = self._hit_to_dict(entry.get('hit'))
            payload.append({
                'key': entry.get('key', ''),
                'hit': hit_dict,
                'source': entry.get('source', 'pii'),
            })
        self.confirmed.emit(payload)
        self.accept()


__all__ = ['WordCandidateDialog', 'ENTITY_TYPE_LABEL', 'PAGE_SIZE']
