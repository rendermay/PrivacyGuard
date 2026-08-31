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
class ImageListDialog(QDialog):
    """图片排序对话框 - 支持拖拽调整图片顺序"""
    def __init__(self, image_paths, parent=None):
        from secureredact.utils.config import config  # PR-C6.4: config singleton 从 main.py 迁出
        super().__init__(parent)

        # v1.1.11: 修复 Windows 深色模式下对话框显示问题
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.setWindowTitle("调整图片顺序")
        # v1.1.11: 从配置读取窗口尺寸
        if config:
            dialog_width = config.get("app.window.dialog_image_list_width", 600)
            dialog_height = config.get("app.window.dialog_image_list_height", 500)
        else:
            dialog_width, dialog_height = 600, 500
        self.resize(dialog_width, dialog_height)
        self.image_paths = image_paths

        layout = QVBoxLayout(self)

        # 说明标签
        info_label = QLabel("拖拽缩略图调整图片顺序，完成后点击「确认合并」")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 缩略图列表（支持拖拽）
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(120, 120))
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        # 添加缩略图
        for path in image_paths:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            # 生成缩略图
            try:
                pixmap = QPixmap(path).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio)
                item.setIcon(QIcon(pixmap))
            except (OSError, IOError, ValueError) as e:
                # 如果缩略图生成失败，使用默认图标
                print(f"[ImageMergeDialog] 缩略图生成失败: {path}: {e}")
                pass
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确认合并")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        # v1.1.11: 应用对话框主题样式
        self._apply_dialog_theme()

    def _apply_dialog_theme(self):
        """应用对话框浅色主题样式（v1.1.11: 修复 Windows 深色模式显示问题）"""
        from theme import Theme
        theme = Theme.LIGHT

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme["background"]};
            }}
            QWidget {{
                background-color: {theme["background"]};
                color: {theme["text"]};
            }}
            QLabel {{
                color: {theme["text"]};
                background-color: transparent;
            }}
            QListWidget {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
            QListWidget::item {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                padding: 8px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background-color: {theme["primary"]};
                color: white;
            }}
            QPushButton {{
                background-color: {theme["primary"]};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {theme["primary"]};
                opacity: 0.9;
            }}
        """)

    def get_ordered_paths(self):
        """获取排序后的图片路径"""
        paths = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths
