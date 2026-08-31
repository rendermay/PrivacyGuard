"""StylesheetLoader glass 分支单元测试 (PR-V3 Task 3)。"""
import pytest


def test_detect_blur_support_returns_bool():
    """detect_blur_support() 返回 bool。"""
    # 在无 Qt 环境或 headless 测试环境也可能 False,只要返回 bool
    from secureredact.ui.styles._platform import detect_blur_support
    result = detect_blur_support()
    assert isinstance(result, bool)


def test_resolve_qpa_platform_returns_string():
    """_resolve_qpa_platform() 返回字符串(在测试环境可能为空)。"""
    from secureredact.ui.styles._platform import _resolve_qpa_platform
    result = _resolve_qpa_platform()
    assert isinstance(result, str)


def test_qt_version_parsing():
    """_qt_major_version() 返回 int。"""
    from secureredact.ui.styles._platform import _qt_major_version
    result = _qt_major_version()
    assert isinstance(result, int)
    assert result >= 5  # 至少 Qt 5
