"""
SecureRedact 信息脱敏助手

v1.1.12: 部分遮蔽 (Partial Masking) + USCC Word-Only 隔离
v1.1.11: 模块化重构版本 + 白名单片段级豁免
v1.1.11: 修复 PyInstaller 打包时的相对导入问题
"""

from importlib import import_module
from pathlib import Path


def _read_version():
    version_file = Path(__file__).resolve().parent.parent / "version.txt"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "1.1.12"


__version__ = _read_version()
__app_name__ = "SecureRedact 信息脱敏助手"

# 导出工具模块（使用绝对导入，修复 PyInstaller 打包问题）
from secureredact.utils import (
    PrivacyAppError,
    ConversionError,
    FileFormatError,
    SecurityError,
    MemoryLimitError,
    WorkerCancelledError,
    TempFileManager,
    validate_safe_path,
    resource_path,
)

# PR-C4 业务 API 层(plan §2.3 任务 1.3)
# 注意:这会触发 api.py 顶层 import PyQt6,因为 batch_redact_word 同步化依赖
# QEventLoop/QTimer。CLI 用户需要 Qt DLL 在 PATH 上(同 `python main.py` 启动条件)。
try:
    from secureredact.api import (  # noqa: E402 — 必须在异常/工具之后导入
        compute_doc_hash,
        scan_pdf,
        scan_word,
        redact_pdf,
        redact_word,
        filter_hits_by_overrides,
        batch_redact_word,
    )
except ImportError:
    # PyQt6 不可用时(子进程 / 纯 stdlib 单元测试环境)跳过 API 暴露,
    # 让 import secureredact 仍然成功。调用方按需 from secureredact.api import ... 自行处理。
    compute_doc_hash = None  # type: ignore[assignment]
    scan_pdf = None  # type: ignore[assignment]
    scan_word = None  # type: ignore[assignment]
    redact_pdf = None  # type: ignore[assignment]
    redact_word = None  # type: ignore[assignment]
    filter_hits_by_overrides = None  # type: ignore[assignment]
    batch_redact_word = None  # type: ignore[assignment]

__all__ = [
    '__version__',
    '__app_name__',
    # 异常类
    'PrivacyAppError',
    'ConversionError',
    'FileFormatError',
    'SecurityError',
    'MemoryLimitError',
    'WorkerCancelledError',
    # 工具类
    'TempFileManager',
    # 工具函数
    'validate_safe_path',
    'resource_path',
    # Workers
    'ImageMergeWorker',
    'OCRWorker',
    'WordWorker',
    # OCR 模块
    'OCREngineManager',
    'OCRResult',
    'CharInfo',
    # PR-C4 业务 API 层
    'compute_doc_hash',
    'scan_pdf',
    'scan_word',
    'redact_pdf',
    'redact_word',
    'filter_hits_by_overrides',
    'batch_redact_word',
    # PR-C6.1 迁出的纯常量
    'WORD_RULE_SCHEMA_VERSION',
    # PR-C6.2 迁出的 UI 内部常量(原 config.get 默认值)
    'ZOOM_MIN',
    'ZOOM_MAX',
    # PR-C6.3 迁出的 UI 常量
    'APP_NAME',
    'VERSION',
]


# PR-C6.1:WORD_RULE_SCHEMA_VERSION 从 main.py 顶层迁出(plan §4.4 优先级 3 UI 常量末批,
# 实际因为纯常量 = 1,迁移风险极低,提前到 P3 第一批)
WORD_RULE_SCHEMA_VERSION = 1

# PR-C6.2:ZOOM_MIN / ZOOM_MAX 从 main.py 顶层迁出。
# 原 main.py 用 config.get("ocr.zoom_min", 0.5) / config.get("ocr.zoom_max", 4.0),
# 此处接受失去运行时可配置性(plan §4.3 任务 N — UI 内部常量末批)。
# 如需恢复可配置,后续可在 secureredact/utils/runtime_config.py 提供 SimpleConfig
# singleton 后再切回 config 派生。
ZOOM_MIN = 0.5
ZOOM_MAX = 4.0

# PR-C6.3:APP_NAME / VERSION 从 main.py 顶层迁出。
# APP_NAME 原 main.py 派生: config.get("app.name", "SecureRedact 信息脱敏助手")
# VERSION 原 main.py 派生: VERSION = APP_VERSION, APP_VERSION = read_app_version()
# 此处 APP_NAME 硬编码(默认值与原 config 一致),
# VERSION 走 read_app_version()(读 version.txt,已存在 secureredact.__version__ 来源)。
APP_NAME = "SecureRedact 信息脱敏助手"


def VERSION():
    """应用版本号(动态从 version.txt 读取,与 secureredact.__version__ 同源)。

    注:封装为函数而非直接赋字符串,确保运行时最新版本被读取
    (原 main.py read_app_version() 行为)。
    """
    return _read_version()

_LAZY_IMPORTS = {
    'ImageMergeWorker': ('secureredact.workers', 'ImageMergeWorker'),
    'OCRWorker': ('secureredact.workers', 'OCRWorker'),
    'WordWorker': ('secureredact.workers', 'WordWorker'),
    'OCREngineManager': ('secureredact.ocr', 'OCREngineManager'),
    'OCRResult': ('secureredact.ocr', 'OCRResult'),
    'CharInfo': ('secureredact.ocr', 'CharInfo'),
}


def __getattr__(name):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
