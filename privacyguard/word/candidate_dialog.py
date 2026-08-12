"""Phase 3 Word 候选审阅对话框（UX-01 / UX-02 极简版 — Wave 2 占位骨架，Wave 3 完整实施）。

承载 Word 文档 PII 候选的人工审阅流程：实体类型 / 来源筛选 + 50 条分页 + 4 CTAs
（接受 / 拒绝 / 全部接受 / 全部拒绝）。
"""
from typing import List, Optional

from PyQt6.QtCore import Qt
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


class WordCandidateDialog(QDialog):
    """Phase 3 Word 候选审阅极简版（D-11 / D-25 / UX-01 / UX-02 — Wave 2 占位，Wave 3 完整实施）。

    Wave 2 占位：仅 setWindowTitle + resize + 占位 label。
    Wave 3 实施：实体类型 / 来源筛选 + 50 条分页 + 4 CTAs（接受 / 拒绝 / 全部接受 / 全部拒绝）。
    """

    PAGE_SIZE = 50

    def __init__(self, word_data: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.word_data = word_data or {}
        self._all_hits: List[dict] = []
        self._page = 0
        self.setWindowTitle('Word 候选审阅')
        self.resize(700, 600)
        self._init_ui()

    def _init_ui(self):
        """Wave 2 占位：仅占位 label。Wave 3 实施实体类型 / 来源筛选 + 50 条分页 + 4 CTAs。"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Word 候选审阅 —— Wave 3 完整 UI 行为待实施'))


__all__ = ['WordCandidateDialog', 'ENTITY_TYPE_LABEL']
