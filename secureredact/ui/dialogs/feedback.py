"""对话框/Worker 模块 — 从 main.py 迁出 (PR-B3/B4)

公共 API 不变。MainWindow 通过 `from main import X` 或对应模块 re-export 导入。
"""
from __future__ import annotations

import sys
import os
import re
import time
import shutil
import threading
import traceback
from pathlib import Path
from io import BytesIO

from PIL import Image
from bs4 import BeautifulSoup

# PyQt6 — 完整集合,覆盖所有 5 个新模块需要
from PyQt6.QtCore import (
    Qt, QSize, QPoint, QPointF, QRect, QRectF, QTimer, QThread, QObject,
    QUrl, QStandardPaths, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QFont, QFontMetrics, QIcon, QImage, QKeySequence,
    QPainter, QPalette, QPen, QPixmap, QStandardItem, QStandardItemModel,
    QTextCursor, QTextDocument, QWheelEvent,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QCompleter,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMenuBar, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QRadioButton, QScrollArea, QScrollBar, QSizePolicy, QSlider, QSpinBox,
    QSplitter, QStackedWidget, QStatusBar, QStyle, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextBrowser, QTextEdit, QToolBar, QToolButton,
    QTreeView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

# 项目内 import(对话框类可能用到的)
from secureredact.utils.security import validate_safe_path, resource_path
from secureredact.utils.exceptions import PrivacyAppError
from secureredact.redaction.hit_ref import HitRef
class FeedbackDialog(QDialog):
    """开发者信息与反馈对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        from secureredact import APP_NAME, VERSION  # PR-C6.3: 延迟导入(原 main.py 顶层常量)
        from secureredact.utils.config import config  # PR-C6.4: config singleton 从 main.py 迁出

        # v1.1.11: 修复 Windows 深色模式下对话框显示问题
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.setWindowTitle("关于与反馈")
        # v1.1.11: 从配置读取窗口尺寸
        if config:
            dialog_width = config.get("app.window.dialog_feedback_width", 480)
            dialog_height = config.get("app.window.dialog_feedback_height", 600)
        else:
            dialog_width, dialog_height = 480, 600
        self.resize(dialog_width, dialog_height)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # 获取当前主题
        self.theme = Theme.LIGHT if not parent or not hasattr(parent, 'is_dark') or not parent.is_dark else Theme.DARK

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # === 标题区域 ===
        title_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_label.setFixedSize(64, 64)
        logo_label.setStyleSheet(f"""
            background: {self.theme['primary']};
            border-radius: 12px;
            color: white;
            font-size: 24px;
            font-weight: bold;
        """)
        logo_label.setText("PG")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(logo_label)

        title_info = QVBoxLayout()
        title_info.setSpacing(4)
        app_name = QLabel(APP_NAME)
        app_name.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {self.theme['text']};")
        version_label = QLabel(f"版本 {VERSION}")
        version_label.setStyleSheet(f"font-size: 12px; color: {self.theme['text_secondary']};")
        title_info.addWidget(app_name)
        title_info.addWidget(version_label)
        title_layout.addLayout(title_info)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # === 分隔线 ===
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet(f"background: {self.theme['border']}; max-height: 1px;")
        layout.addWidget(line1)




        # === 分隔线 ===
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet(f"background: {self.theme['border']}; max-height: 1px;")
        layout.addWidget(line2)

        # === 免责声明 ===
        disclaimer = QTextBrowser()
        disclaimer.setOpenExternalLinks(True)
        disclaimer.setMaximumHeight(160)
        disclaimer.setStyleSheet(f"""
            QTextBrowser {{
                background: {self.theme['surface']};
                border: 1px solid {self.theme['border']};
                border-radius: 8px;
                padding: 12px;
                color: {self.theme['text_secondary']};
                font-size: 11px;
            }}
        """)
        disclaimer.setHtml("""
            <p style="font-weight: bold; margin-bottom: 8px; color: #FF9500;">⚠️ 免责声明</p>
            <ol style="margin-left: 16px; line-height: 1.6;">
                <li>本软件免费仅供学习和个人使用，不构成任何法律建议。</li>
                <li>使用本软件进行文档脱敏处理后，用户需自行核实脱敏结果。</li>
                <li>开发者不对因使用本软件而产生的任何直接或间接损失承担责任。</li>
                <li>本软件不收集任何用户数据，所有处理均在本地完成。</li>
                <li>请勿将本软件用于任何违法用途。</li>
            </ol>
        """)
        layout.addWidget(disclaimer)

        # === 关闭按钮 ===
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme['hover']};
                color: {self.theme['text']};
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {self.theme['pressed']};
            }}
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        # 显示复制成功提示
        if self.parent():
            QMessageBox.information(self.parent(), "复制成功", f"已复制: {text}")
