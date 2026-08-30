# ⚠️ v1.1.13+ (PR-B0) deprecation notice
# ====================================================================
# 本文件已转为 thin shim,真正的运行时入口在 `secureredact/main.py`。
#
# 禁止继续往本文件添加新业务代码。所有新功能请写到 `secureredact/` 对应子包。
# 阶段 B 重构路线图:详见 `frontend-refactor-plan.md`(OpenDesign 工作目录)
#                   与 `docs/refactor/b0-report.md`(项目内)。
# PR-B5 收口时本文件将被彻底移除,所有打包入口同步切换到 `secureredact.main:main`。
#
# 过渡期启动方式:
#     python -m secureredact.main    # 新入口(推荐)
#     python main.py                  # 兼容 shim(过渡期,PR-B5 后停用)
# ====================================================================

import sys
import os
import fitz  # PyMuPDF
import re
import cv2
import numpy as np
import time
import shutil
import threading  # v1.1.11: 线程锁支持
import atexit  # v1.1.11: 用于确保临时文件清理
import tempfile  # v1.1.11: 临时文件管理
import traceback  # v1.1.11: 异常追踪
from pathlib import Path
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from secureredact.ocr.mixed_pdf import (
    collect_embedded_image_clip_rects,
    collect_image_block_ocr_hits,
)
from secureredact.ocr.text_pdf import collect_text_pdf_hit_boxes
from secureredact.utils.security import validate_safe_path, resource_path
from secureredact.utils.config import config  # PR-C6.4: 全局 config singleton 从 main.py 顶层迁出
from secureredact.redaction.rules_loader import (  # PR-C6.5: DEFAULT_RULES / META 从 main.py 迁出
    DEFAULT_RULES, DEFAULT_RULES_META, _v113_apply_rule_overrides,
)
from secureredact.utils.exceptions import (
    PrivacyAppError,
    ConversionError,
    FileFormatError,
    SecurityError,
    MemoryLimitError,
    WorkerCancelledError,
)
from secureredact.utils.temp_manager import TempFileManager
from secureredact.workers.image_merge import ImageMergeWorker
from secureredact.workers.word_worker import WordWorker as _ModularWordWorker
from secureredact.workers.ocr_worker import OCRWorker as _ModularOCRWorker
from secureredact.utils.doc_converter import convert_doc_to_docx as _shared_convert_doc_to_docx
from secureredact.redaction.hit_ref import HitRef  # v1.1.11: 人工干预
from secureredact.ui.utils.density import (  # PR-B5.1 re-export
    resolve_workspace_density_mode, resolve_settings_density_mode, _shift_density_mode,
)
from secureredact.redaction.word_rules import (normalize_word_replace_rules, merge_word_matches_with_priority, build_word_rule_matches, apply_rule_matches_to_text, apply_word_rules_to_text, _range_overlaps, replace_matches_in_paragraph, apply_range_to_runs)  # PR-C1.1 re-export
from secureredact.ui.main_window.word_preview import PREVIEW_FONT_STACK  # PR-C1.1 shared constant
from secureredact.ui.main_window._helpers import (  # PR-B5.2 re-export
    build_replaced_preview_segments, build_word_panel_update_script,
)
from secureredact.ui.settings.dialog import SettingsDialog  # PR-B3 re-export
from secureredact.ui.dialogs.word_replace_rules import WordReplaceRulesDialog  # PR-B4 re-export
from secureredact.ui.dialogs.image_list import ImageListDialog  # PR-B4 re-export
from secureredact.ui.dialogs.feedback import FeedbackDialog  # PR-B4 re-export
from secureredact.workers.word_batch_replace_worker import WordBatchReplaceWorker  # PR-B4 re-export
from secureredact.ui.main_window import SinglePageCanvas, WebViewBridge  # PR-B2.0 re-export
from secureredact.ui.main_window.toolbar import MainWindowToolbarMixin  # PR-B2.1
from secureredact.ui.main_window.workbench import MainWindowWorkbenchMixin  # PR-B2.2
from secureredact.ui.main_window.word_preview import MainWindowWordPreviewMixin  # PR-B2.3
from secureredact.ui.main_window.pdf_render import MainWindowPdfRenderMixin  # PR-B2.4
from secureredact.ui.main_window.batch_replace import MainWindowBatchReplaceMixin  # PR-B2.5
from secureredact.ui.main_window.density import MainWindowDensityMixin  # PR-B2.6
from secureredact.ui.main_window.setup_ui import MainWindowSetupMixin  # PR-B2.7
from secureredact.ui.main_window.handlers import MainWindowHandlersMixin  # PR-B2.8
from secureredact.ui.main_window.theme import MainWindowThemeMixin  # PR-C1
from secureredact.ui.main_window.window import MainWindow  # PR-C9 Task 3: 主体已迁出, 保留 re-export 以兼容
from secureredact.redaction.override_store import HitOverrideStore  # v1.1.11: override store 单例
from secureredact.redaction.doc_hash import compute_doc_hash  # v1.1.11: 文档 hash
from secureredact.redaction.black_white_list_store import BlackWhiteListStore  # v1.1.11: 黑/白名单 store

# v1.1.11: 延迟导入 OCR 模块，便于错误处理
RapidOCR = None
OCR_INIT_ERROR = None

def init_ocr_engine():
    """v1.1.11: 安全初始化 OCR 引擎，捕获所有可能的错误"""
    global RapidOCR, OCR_INIT_ERROR
    if RapidOCR is not None:
        return True

    try:
        from rapidocr_onnxruntime import RapidOCR as _RapidOCR
        RapidOCR = _RapidOCR
        # 预热：创建一个测试实例验证 DLL 加载
        _ = _RapidOCR()
        print("[OCR] 引擎初始化成功")
        return True
    except ImportError as e:
        OCR_INIT_ERROR = f"OCR 模块未安装: {e}\n请运行: pip install rapidocr-onnxruntime"
        print(f"[OCR ERROR] {OCR_INIT_ERROR}")
        return False
    except OSError as e:
        OCR_INIT_ERROR = f"OCR DLL 加载失败: {e}\n可能缺少 Visual C++ 运行库"
        print(f"[OCR ERROR] {OCR_INIT_ERROR}")
        return False
    except Exception as e:
        OCR_INIT_ERROR = f"OCR 初始化失败: {type(e).__name__}: {e}"
        print(f"[OCR ERROR] {OCR_INIT_ERROR}")
        traceback.print_exc()
        return False

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QBoxLayout, QGridLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QScrollArea, QMessageBox, QProgressBar, QFrame,
                             QDialog, QCheckBox, QGroupBox, QTextEdit, QSpinBox,
                             QRadioButton, QButtonGroup, QComboBox, QSizePolicy,
                             QTextBrowser, QLineEdit, QListWidget, QListWidgetItem,
                             QAbstractItemView, QSlider, QTableWidget, QMenu,
                             QTableWidgetItem, QHeaderView, QStyle,
                             QDockWidget)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QWheelEvent, QCursor, QIcon, QDesktopServices
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF, QSettings, QMutex, QMutexLocker, QObject, pyqtSlot, QSize, QTimer, QUrl
# PR-C1.1: QtWebEngineWidgets 延迟加载(避免模块级 import 阻断单元测试)
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None  # type: ignore[assignment,misc]
from PyQt6.QtWebChannel import QWebChannel
from PyQt6 import sip

# 导入主题系统
from theme import Theme

# v1.1.11: 简化配置系统 - 直接从 JSON 文件加载
import json


def read_app_version():
    """从统一版本文件读取基础版本号。"""
    version_file = Path(__file__).resolve().parent / "version.txt"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "1.1.12"


# === 核心防崩溃设置 ===
cv2.setNumThreads(0)
os.environ["OMP_NUM_THREADS"] = "1"

# === 软件配置 ===
# v1.1.11: 从配置读取，失败时使用硬编码后备
APP_NAME = config.get("app.name", "SecureRedact 信息脱敏助手") if config else "SecureRedact 信息脱敏助手"
APP_VERSION = read_app_version()
VERSION = APP_VERSION
# === 默认规则库 + Mask 元数据 ===
# v1.1.11: 从配置读取，失败时使用硬编码后备
MIN_RECT_WIDTH = config.get("ocr.min_rect_width", 5) if config else 5
PROGRESS_UPDATE_INTERVAL = config.get("ocr.progress_update_interval", 0.05) if config else 0.05
ZOOM_MIN = config.get("ocr.zoom_min", 0.5) if config else 0.5
ZOOM_MAX = config.get("ocr.zoom_max", 4.0) if config else 4.0
DEBUG_MODE = os.getenv('PRIVACYGUARD_DEBUG', 'False').lower() == 'true' if not config else config.get("advanced.debug_mode", False)

# === 默认规则库 + Mask 元数据 ===
# v1.1.11: 从配置读取,支持新旧两种格式


# === 设置对话框 ===


# === 图片排序对话框 ===

# === 配置常量 ===

# === 反馈对话框 ===


# === 单页画布 (完全复制 v1.1.11 的 PDFCanvas 实现) ===


# === OCR 线程 ===
# v1.1.11: 改为使用模块化 OCRWorker，自动注入 box_adjust_ratio
class OCRWorker(_ModularOCRWorker):
    """OCR 处理线程（兼容层：自动注入 config 中的 box_adjust_ratio + enable_name_recognition）"""

    def __init__(self, pdf_path, rules, use_enhance, custom_keywords, scan_scale, off_x, off_w,
                 use_char_level_ocr: bool = False, seal_detection_enabled: bool = False,
                 enable_name_recognition: bool = False,
                 name_context_extra_tokens=None):
        box_adjust_ratio = config.get("ocr.box_adjust_ratio", 0.0) if config else 0.0
        super().__init__(pdf_path, rules, use_enhance, custom_keywords, scan_scale, off_x, off_w,
                         use_char_level_ocr=use_char_level_ocr,
                         seal_detection_enabled=seal_detection_enabled,
                         box_adjust_ratio=box_adjust_ratio,
                         enable_name_recognition=enable_name_recognition,
                         name_context_extra_tokens=name_context_extra_tokens)

# === WebView Bridge：Python 与 JavaScript 通信 ===

# === Word 文档处理线程 ===
# v1.1.11: 改为使用模块化 WordWorker,补充 default_rules 参数
# v1.1.12: 兼容层透传 default_rules + default_rules_meta,支持 partial masking
class WordWorker(_ModularWordWorker):
    """Word 文档智能脱敏线程(兼容层: 自动注入 DEFAULT_RULES + enable_name_recognition)

    v1.1.12: 透传 default_rules_meta 到模块化 WordWorker,让 mask 配置生效。
    兼容层对外仍然只暴露原始 6 个参数,新增 kwargs 默认值与模块化层一致。
    """

    def __init__(self, word_doc, word_data, rules, custom_keywords, replacement_text,
                 enable_name_recognition: bool = False,
                 default_rules=None,
                 default_rules_meta=None):
        super().__init__(word_doc, word_data, rules, custom_keywords,
                         replacement_text,
                         default_rules=default_rules if default_rules is not None else DEFAULT_RULES,
                         enable_name_recognition=enable_name_recognition,
                         default_rules_meta=default_rules_meta if default_rules_meta is not None else DEFAULT_RULES_META)

from secureredact.ui.main_window._js_constants import _INTERACTIVE_JS_CODE  # PR-C9 Task 2 C2-fix: 抽出到独立模块

