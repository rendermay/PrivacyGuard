"""
SecureRedact 工具模块

v1.1.11: 模块化拆分
v1.1.11: 添加配置系统
v1.1.11: 修复 PyInstaller 打包时的相对导入问题
"""

# 使用绝对导入（修复 PyInstaller 打包问题）
from secureredact.utils.exceptions import (
    PrivacyAppError,
    ConversionError,
    FileFormatError,
    SecurityError,
    MemoryLimitError,
    WorkerCancelledError
)

from secureredact.utils.temp_manager import TempFileManager

from secureredact.utils.security import validate_safe_path, resource_path

from secureredact.utils.config import (
    ConfigManager,
    ConfigError,
    ConfigValidationError,
    ConfigNotFoundError,
    DEFAULT_CONFIG,
    get_config,
    get_config_value
)

__all__ = [
    # 异常类
    'PrivacyAppError',
    'ConversionError',
    'FileFormatError',
    'SecurityError',
    'MemoryLimitError',
    'WorkerCancelledError',
    # 配置相关
    'ConfigManager',
    'ConfigError',
    'ConfigValidationError',
    'ConfigNotFoundError',
    'DEFAULT_CONFIG',
    'get_config',
    'get_config_value',
    # 工具类
    'TempFileManager',
    # 工具函数
    'validate_safe_path',
    'resource_path',
]
