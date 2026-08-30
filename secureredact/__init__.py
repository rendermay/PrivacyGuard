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
]


# PR-C6.1:WORD_RULE_SCHEMA_VERSION 从 main.py 顶层迁出(plan §4.4 优先级 3 UI 常量末批,
# 实际因为纯常量 = 1,迁移风险极低,提前到 P3 第一批)
WORD_RULE_SCHEMA_VERSION = 1

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
