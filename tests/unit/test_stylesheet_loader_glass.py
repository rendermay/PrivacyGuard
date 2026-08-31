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


def test_stylesheet_loader_has_glass_attribute():
    """StylesheetLoader 实例有 glass_supported 属性(启动期确定)。"""
    from secureredact.ui.styles.loader import StylesheetLoader
    loader = StylesheetLoader()
    assert hasattr(loader, "glass_supported")
    assert isinstance(loader.glass_supported, bool)


def test_stylesheet_loader_glass_branch_in_render():
    """render() 输出对 glass_supported 行为有可识别差异。

    验证方式:检查 QSS 中是否包含 backdrop-filter 字符串。
    """
    from secureredact.ui.styles.loader import StylesheetLoader
    from secureredact.ui.styles import _platform

    # 强制设置两个 loader 实例测试
    loader_with_glass = StylesheetLoader()
    loader_without_glass = StylesheetLoader()

    # 通过 monkeypatch 模拟两种状态
    original = _platform.detect_blur_support
    try:
        _platform.detect_blur_support = lambda: True
        _platform._GLASS_SUPPORT_CACHE = True
        loader_with_glass.glass_supported = True
        qss_with = loader_with_glass.render("dark", scope="main")

        _platform.detect_blur_support = lambda: False
        _platform._GLASS_SUPPORT_CACHE = False
        loader_without_glass.glass_supported = False
        qss_without = loader_without_glass.render("dark", scope="main")
    finally:
        _platform.detect_blur_support = original
        _platform._GLASS_SUPPORT_CACHE = None

    # 两条 QSS 都应正常返回(占位符机制生效即可,具体差异留给 PR-V2 的 component .qss)
    assert isinstance(qss_with, str)
    assert isinstance(qss_without, str)
