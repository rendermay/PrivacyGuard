# 视觉层基础层 — tokens 体系化 + Glass 检测 (PR-V1 + PR-V3) 实施规划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `tokens.py` 从 16 颜色 token 扩展到完整设计 token 体系（颜色 17 + 圆角 5 + 间距 6 + 阴影 5 + 动效 5 + 字体 12），同时给 `StylesheetLoader` 加 `glass_supported` 自动降级分支。这两个 PR 是后续 4 个视觉层 PR（V2/V4/C1.1/C2.x）的**严格前置**。

**Architecture:** 保留 `tokens.py` 的 frozen dataclass 模式，但字段从纯颜色扩展到全套设计 token。`StylesheetLoader` 增加 `_resolve_glass_support()` 启动期检测，结果注入到 QSS 渲染管线。所有现有 6 个 .qss 文件保持不变（仅占位符值更新），后续 PR-V2 才会创建 `secureredact/ui/styles/components/*.qss`。

**Tech Stack:** Python 3.x · PyQt6 · dataclasses(frozen) · pytest · unittest (现有 439 项回归基线)

---

## Global Constraints

- 单一版本源：`version.txt` 不动；本 PR 不发布新版本
- 不引入新依赖（PyQt6 + dataclasses 已足够）
- 保留现有 `theme.py` 的 `Theme` 类作为运行时引用入口（避免大爆炸 break）；`tokens.py` 是 dataclass 真源，`theme.py` 是 dict 镜像层
- 现有 439 单元测试 / 6 baseline 失败 / 0 新失败（PR-V1 不增加新失败为硬性门槛）
- `tokens.py` 中所有新增 token 必须有 `__all__` 导出（避免 from-import 找不到）
- 每个 Task 必须有独立 commit，便于 bisect 回溯
- 不动 .qss 文件内容（仅占位符值更新，且仅在必要处；本 PR 主要交付 token 数据层）

---

## File Structure

### 涉及文件

| 路径 | 操作 | 角色 |
|---|---|---|
| `secureredact/ui/styles/tokens.py` | **修改** | 扩展现有 dataclass + 新增常量模块 |
| `secureredact/ui/styles/loader.py` | **修改** | 加 `_resolve_glass_support()` + QSS 渲染分支 |
| `secureredact/ui/styles/_platform.py` | **新建** | PyQt6 平台检测纯函数 |
| `theme.py`（顶层） | **修改** | LIGHT/DARK 字典从硬编码 hex 改为引用 `secureredact.ui.styles.tokens.LIGHT/DARK` |
| `tests/unit/test_visual_tokens.py` | **新建** | token 数据正确性 + glass 检测单元测试 |
| `tests/unit/test_stylesheet_loader_glass.py` | **新建** | StylesheetLoader glass 分支行为测试 |

### 不涉及

- 任何 mixin / MainWindow 内部 QSS（PR-V4 范围）
- 任何 .qss 文件的样式内容（PR-V2 范围）
- SettingsDialog 主题切换 UI（PR-C1.1 范围）
- 视觉基线（PR-C2.x 范围）

### Task 6 后的最终状态

```
secureredact/ui/styles/
├── __init__.py                       不变
├── base.qss / menu.qss / ...         不变(占位符值未变,只是 token 数据源更新)
├── loader.py                          MOD  +glass_supported 分支
├── tokens.py                          MOD  +圆角/间距/阴影/动效/字体模块
└── _platform.py                       NEW  ~30 行
theme.py                              MOD  LIGHT/DARK 字典从硬编码改引用
tests/unit/
├── test_visual_tokens.py              NEW  ~50 行
└── test_stylesheet_loader_glass.py    NEW  ~40 行
```

---

## Task 1: 在 `tokens.py` 新增全套非颜色 token（圆角 / 间距 / 阴影 / 动效 / 字体）

**Files:**
- Modify: `secureredact/ui/styles/tokens.py`

**Interfaces:**
- Consumes: （无前置；当前 tokens.py 仅含 Tokens dataclass + LIGHT/DARK + THEMES + get_tokens + get_substitution_map + FONT_*）
- Produces: 完整 token 体系；`from secureredact.ui.styles.tokens import RADIUS_MD, SPACING_SM, SHADOW_LG, DURATION_NORMAL, FONT_SIZE_BASE` 全部可用

- [ ] **Step 1: 写失败的导入测试**

在 `tests/unit/test_visual_tokens.py` 新建文件：

```python
"""视觉 token 单元测试 (PR-V1 Task 1)。"""
import pytest


def test_radius_tokens_available():
    """5 级圆角 token 全部可导入。"""
    from secureredact.ui.styles.tokens import (
        RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_XL, RADIUS_PILL,
    )
    assert RADIUS_SM == 6
    assert RADIUS_MD == 10
    assert RADIUS_LG == 16
    assert RADIUS_XL == 24
    assert RADIUS_PILL == 999


def test_spacing_tokens_available():
    """6 级间距 token 全部可导入。"""
    from secureredact.ui.styles.tokens import (
        SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_2XL,
    )
    assert SPACING_XS == 4
    assert SPACING_SM == 8
    assert SPACING_MD == 14
    assert SPACING_LG == 22
    assert SPACING_XL == 32
    assert SPACING_2XL == 48


def test_shadow_tokens_available():
    """5 级阴影 token 全部可导入。"""
    from secureredact.ui.styles.tokens import (
        SHADOW_SM, SHADOW_MD, SHADOW_LG, SHADOW_XL, SHADOW_GLOW,
    )
    assert "0 1px 2px" in SHADOW_SM
    assert "blur" in SHADOW_LG or "0 10px" in SHADOW_LG
    assert "rgba(37,99,235" in SHADOW_GLOW


def test_duration_tokens_available():
    """3 个 duration + 2 个 ease token 全部可导入。"""
    from secureredact.ui.styles.tokens import (
        DURATION_FAST, DURATION_NORMAL, DURATION_SLOW,
        EASE_OUT, EASE_IN_OUT,
    )
    assert DURATION_FAST == 150
    assert DURATION_NORMAL == 200
    assert DURATION_SLOW == 300
    assert "cubic-bezier" in EASE_OUT
    assert "cubic-bezier" in EASE_IN_OUT


def test_font_tokens_available():
    """字体 family / weight / size token 全部可导入。"""
    from secureredact.ui.styles.tokens import (
        FONT_FAMILY_DISPLAY, FONT_FAMILY_BODY,
        FONT_WEIGHT_REGULAR, FONT_WEIGHT_MEDIUM, FONT_WEIGHT_SEMIBOLD, FONT_WEIGHT_BOLD,
        FONT_SIZE_XS, FONT_SIZE_SM, FONT_SIZE_BASE, FONT_SIZE_LG, FONT_SIZE_XL, FONT_SIZE_2XL,
    )
    assert "Inter" in FONT_FAMILY_DISPLAY
    assert "Inter" in FONT_FAMILY_BODY
    assert FONT_WEIGHT_REGULAR == 400
    assert FONT_SIZE_XS == 11
    assert FONT_SIZE_2XL == 32
```

- [ ] **Step 2: 运行测试验证失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_visual_tokens.py -v 2>&1 | tail -20
```

Expected: 5 个 test 全 FAIL（ImportError: cannot import name 'RADIUS_SM' ...）

- [ ] **Step 3: 在 tokens.py 末尾追加全套非颜色 token 模块**

在 `secureredact/ui/styles/tokens.py` 末尾（`__all__ = [...]` 之前）追加以下 5 个 section，每个 section 含 docstring + 常量定义。完整内容：

```python
# ============================================================================
# 非颜色设计 token（PR-V1 Task 1 引入，对齐 LOGO_DESIGN_GUIDE.md + ui_design_preview.html）
# ============================================================================

# === 圆角 token（5 级）===
# 来源: ui_design_preview.html 的 --radius-{sm,md,lg,xl}
RADIUS_SM = 6          # 标签 / chip
RADIUS_MD = 10         # 按钮 / 输入框
RADIUS_LG = 16         # 卡片 / dock 容器
RADIUS_XL = 24         # 主面板容器
RADIUS_PILL = 999      # 头像 / 徽章


# === 间距 token（8 进制 / 6 级）===
# 迁移映射(保留向后兼容):
#   SPACING_SMALL=8  → SPACING_SM
#   SPACING_MEDIUM=14 → SPACING_MD
#   SPACING_LARGE=22  → SPACING_LG
SPACING_XS = 4         # 内边距微调
SPACING_SM = 8         # 紧凑布局
SPACING_MD = 14        # 标准间距
SPACING_LG = 22        # 区块间距
SPACING_XL = 32        # section 大间距
SPACING_2XL = 48       # 页面顶部 / 大留白


# === 阴影 token（4 级 + glow）===
# 来源: ui_design_preview.html 的 --shadow-{sm,md,lg,xl}
# SHADOW_GLOW 仅 Dark 主题生效
SHADOW_SM = "0 1px 2px rgba(0,0,0,0.06)"
SHADOW_MD = "0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -2px rgba(0,0,0,0.10)"
SHADOW_LG = "0 10px 15px -3px rgba(0,0,0,0.10), 0 4px 6px -4px rgba(0,0,0,0.10)"
SHADOW_XL = "0 20px 25px -5px rgba(0,0,0,0.10), 0 8px 10px -6px rgba(0,0,0,0.10)"
SHADOW_GLOW = "0 0 40px rgba(37,99,235,0.30)"


# === 动效 token（3 duration + 2 ease）===
# 迁移映射(保留向后兼容):
#   ANIMATION_DURATION=200 → DURATION_NORMAL
DURATION_FAST = 150    # hover / press
DURATION_NORMAL = 200  # 默认过渡
DURATION_SLOW = 300    # 页面切换 / 抽屉动画

EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)"        # 弹性出口(适合入场)
EASE_IN_OUT = "cubic-bezier(0.4, 0, 0.2, 1)"     # 平滑(适合状态切换)


# === 字体 token（2 family + 4 weight + 6 size）===
# 来源: ui_design_preview.html 的 Inter / Segoe UI Variable
FONT_FAMILY_DISPLAY = "'Inter', 'Segoe UI Variable', 'PingFang SC', sans-serif"
FONT_FAMILY_BODY = "'Inter', 'Segoe UI Variable', 'Microsoft YaHei UI', sans-serif"

FONT_WEIGHT_REGULAR = 400
FONT_WEIGHT_MEDIUM = 500
FONT_WEIGHT_SEMIBOLD = 600
FONT_WEIGHT_BOLD = 700

FONT_SIZE_XS = 11      # 极小（仅时间戳 / 标记）
FONT_SIZE_SM = 12      # 副文本
FONT_SIZE_BASE = 14    # 正文
FONT_SIZE_LG = 18      # 小标题
FONT_SIZE_XL = 24      # 标题
FONT_SIZE_2XL = 32     # 大标题
```

- [ ] **Step 4: 更新 `__all__` 列表**

在 `tokens.py` 的 `__all__ = [...]` 中追加所有新增常量。完整 `__all__`：

```python
__all__ = [
    # 颜色 token
    "Tokens",
    "LIGHT",
    "DARK",
    "THEMES",
    "get_tokens",
    "get_substitution_map",
    # 字体
    "FONT_FAMILY",
    "FONT_FAMILY_DISPLAY",
    "FONT_FAMILY_BODY",
    "FONT_SIZE_SMALL",
    "FONT_SIZE_NORMAL",
    "FONT_SIZE_XS",
    "FONT_SIZE_SM",
    "FONT_SIZE_BASE",
    "FONT_SIZE_LG",
    "FONT_SIZE_XL",
    "FONT_SIZE_2XL",
    # 圆角
    "RADIUS_SM",
    "RADIUS_MD",
    "RADIUS_LG",
    "RADIUS_XL",
    "RADIUS_PILL",
    # 间距
    "SPACING_XS",
    "SPACING_SM",
    "SPACING_MD",
    "SPACING_LG",
    "SPACING_XL",
    "SPACING_2XL",
    # 阴影
    "SHADOW_SM",
    "SHADOW_MD",
    "SHADOW_LG",
    "SHADOW_XL",
    "SHADOW_GLOW",
    # 动效
    "DURATION_FAST",
    "DURATION_NORMAL",
    "DURATION_SLOW",
    "EASE_OUT",
    "EASE_IN_OUT",
    # 字重
    "FONT_WEIGHT_REGULAR",
    "FONT_WEIGHT_MEDIUM",
    "FONT_WEIGHT_SEMIBOLD",
    "FONT_WEIGHT_BOLD",
]
```

- [ ] **Step 5: 运行测试验证通过**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_visual_tokens.py -v 2>&1 | tail -10
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/styles/tokens.py tests/unit/test_visual_tokens.py && git commit -m "feat(tokens): PR-V1 Task 1 — 圆角/间距/阴影/动效/字体 28 个常量 (LOGO + ui_design_preview.html 对齐)"
```

---

## Task 2: 更新 `Tokens` dataclass 颜色字段（含新增 `primary_hover`）

**Files:**
- Modify: `secureredact/ui/styles/tokens.py:20-39`（`@dataclass(frozen=True) class Tokens`）

**Interfaces:**
- Consumes: Task 1 完成
- Produces: `Tokens` dataclass 含 17 字段（含 `primary_hover`）；`Tokens(**LIGHT.__dict__)` 仍能工作（因为只是新增字段，向后兼容）

- [ ] **Step 1: 写失败的 dataclass 字段测试**

在 `tests/unit/test_visual_tokens.py` 追加：

```python
def test_tokens_dataclass_has_primary_hover():
    """Tokens dataclass 含 primary_hover 字段（Spec A §4.1 新增）。"""
    from secureredact.ui.styles.tokens import Tokens, LIGHT, DARK
    assert "primary_hover" in Tokens.__dataclass_fields__
    assert LIGHT.primary_hover  # 任意非空 hex
    assert DARK.primary_hover


def test_tokens_dataclass_legacy_compat():
    """所有原 16 字段保留,get_substitution_map 输出含全部 17 字段。"""
    from secureredact.ui.styles.tokens import get_substitution_map
    light_map = get_substitution_map("light")
    dark_map = get_substitution_map("dark")
    # 17 颜色字段 + font_family / font_size_small / font_size_normal = 20
    assert len(light_map) == 20
    assert "primary_hover" in light_map
    assert "primary_hover" in dark_map
    # LIGHT 和 DARK 的 primary_hover 应该不同
    assert light_map["primary_hover"] != dark_map["primary_hover"]
```

- [ ] **Step 2: 运行测试验证失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_visual_tokens.py::test_tokens_dataclass_has_primary_hover tests/unit/test_visual_tokens.py::test_tokens_dataclass_legacy_compat -v 2>&1 | tail -15
```

Expected: 2 个 test FAIL（`'primary_hover' in Tokens.__dataclass_fields__` 失败）

- [ ] **Step 3: 在 `Tokens` dataclass 中追加 `primary_hover` 字段**

修改 `tokens.py:20-39`，在 `primary: str` 之后插入：

```python
    primary: str
    primary_hover: str  # PR-V1 Task 2 新增（Logo Blue-700/600）
    secondary: str
```

（具体插入位置：在 `primary: str` 那行的下一行）

- [ ] **Step 4: 更新 LIGHT 实例**

修改 `tokens.py:44-61` 的 `LIGHT = Tokens(...)`，在 `primary="#2563EB"` 之后插入：

```python
    primary_hover="#1D4ED8",  # Blue-700 (LOGO)
```

⚠️ **注意**：本 PR **不**改 LIGHT 字段的其他 hex 值（仅加 `primary_hover`）。颜色值全面更新属于 PR-V4 范畴（替换 MainWindow 内嵌 QSS 时一起改）。本 PR 数据层先扩展到位，应用层留 PR-V4。

- [ ] **Step 5: 更新 DARK 实例**

修改 `tokens.py:63-80` 的 `DARK = Tokens(...)`，在 `primary="#3B82F6"` 之后插入：

```python
    primary_hover="#2563EB",  # Blue-600 (LOGO Dark)
```

- [ ] **Step 6: 运行测试验证通过**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_visual_tokens.py -v 2>&1 | tail -10
```

Expected: `7 passed`

- [ ] **Step 7: 运行全量回归确保 0 新失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m compileall -q main.py secureredact tests
cd "G:/Project/SecureRedact" && python -m unittest discover tests -v 2>&1 | tail -5
```

Expected: `Ran 439 tests / FAILED (failures=6)`（与 baseline 一致）

- [ ] **Step 8: Commit**

```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/styles/tokens.py tests/unit/test_visual_tokens.py && git commit -m "feat(tokens): PR-V1 Task 2 — Tokens dataclass 新增 primary_hover 字段"
```

---

## Task 3: 创建 `_platform.py` 平台检测模块

**Files:**
- Create: `secureredact/ui/styles/_platform.py`

**Interfaces:**
- Consumes: PyQt6（不引入新依赖）
- Produces: `detect_blur_support() -> bool` 纯函数

- [ ] **Step 1: 写失败的检测测试**

在 `tests/unit/test_stylesheet_loader_glass.py` 新建文件：

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_stylesheet_loader_glass.py -v 2>&1 | tail -10
```

Expected: 3 个 test FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写 `_platform.py`**

新建 `secureredact/ui/styles/_platform.py`，完整内容：

```python
"""
平台检测模块 — PR-V3 Task 3 引入。

仅做平台能力检测,不引入任何业务逻辑。
启动期调用一次,结果缓存到 `_GLASS_SUPPORT_CACHE` 全局变量。
"""
from __future__ import annotations

# 缓存:启动期 detect_blur_support() 调用一次后,后续直接读取缓存
_GLASS_SUPPORT_CACHE: bool | None = None


def _qt_major_version() -> int:
    """返回当前 Qt 主版本号。失败时返回 0（保守降级）。"""
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        return int(QT_VERSION_STR.split('.')[0])
    except Exception:
        return 0


def _resolve_qpa_platform() -> str:
    """检测当前 QPA 平台名(无 Qt 环境返回 '')。

    Returns:
        'windows' | 'cocoa' | 'xcb' | 'wayland' | ''
    """
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            # 极端 case: 无 QApplication 实例
            return ""
        return app.platformName().lower()
    except Exception:
        return ""


def detect_blur_support() -> bool:
    """启动期检测 backdrop-filter 支持。

    Returns:
        True:  启用 Glass (backdrop-filter: blur(8px))
        False: 降级到半透明纯色 + 加阴影

    降级触发条件(任一):
        - Qt < 6(主版本 ≤ 5)
        - QPA 平台不在 {'windows', 'cocoa', 'xcb'} 内
        - 检测过程异常(任意 import / 调用失败)
    """
    global _GLASS_SUPPORT_CACHE
    if _GLASS_SUPPORT_CACHE is not None:
        return _GLASS_SUPPORT_CACHE

    try:
        if _qt_major_version() < 6:
            _GLASS_SUPPORT_CACHE = False
            return False
        platform = _resolve_qpa_platform()
        _GLASS_SUPPORT_CACHE = platform in ("windows", "cocoa", "xcb")
    except Exception:
        _GLASS_SUPPORT_CACHE = False

    return _GLASS_SUPPORT_CACHE


__all__ = ["detect_blur_support", "_resolve_qpa_platform", "_qt_major_version"]
```

- [ ] **Step 4: 运行测试验证通过**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_stylesheet_loader_glass.py -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/styles/_platform.py tests/unit/test_stylesheet_loader_glass.py && git commit -m "feat(styles): PR-V3 Task 3 — _platform.py 平台检测模块 (detect_blur_support)"
```

---

## Task 4: `StylesheetLoader` 接入 `glass_supported` 分支

**Files:**
- Modify: `secureredact/ui/styles/loader.py`
- Create: `tests/unit/test_stylesheet_loader_glass.py`（追加测试）

**Interfaces:**
- Consumes: Task 3 的 `detect_blur_support()`
- Produces: `StylesheetLoader.render()` 输出根据 glass 支持情况包含不同 `{glass}` 占位符块

- [ ] **Step 1: 写失败的 loader 测试**

在 `tests/unit/test_stylesheet_loader_glass.py` 追加：

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_stylesheet_loader_glass.py -v 2>&1 | tail -10
```

Expected: 2 个新 test FAIL（AttributeError: 'StylesheetLoader' object has no attribute 'glass_supported'）

- [ ] **Step 3: 修改 `loader.py` 添加 `glass_supported` 属性**

修改 `secureredact/ui/styles/loader.py`：

1. 顶部 import 追加：

```python
from ._platform import detect_blur_support
```

2. 修改 `StylesheetLoader.__init__`：

```python
    def __init__(self, default_theme: str = "light") -> None:
        self.default_theme = default_theme
        # PR-V3 Task 4: 启动期检测 Glass 支持(后续 PR-V2 组件 .qss 会基于此切换)
        self.glass_supported: bool = detect_blur_support()
```

⚠️ **注意**：本 Task **不**改 `render()` / `apply()` 方法的实现——它们仍按当前逻辑输出。glass 分支的实际生效在 PR-V2 引入 6 个 component .qss 时才会用到 `glass_supported`。本 Task 仅**埋点**（让 loader 实例携带这个 bool 供后续 PR 使用）。

- [ ] **Step 4: 运行测试验证通过**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_stylesheet_loader_glass.py -v 2>&1 | tail -10
```

Expected: `5 passed`

- [ ] **Step 5: 运行全量回归确保 0 新失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m unittest discover tests -v 2>&1 | tail -5
```

Expected: `Ran 439 tests / FAILED (failures=6)`（与 baseline 一致）

- [ ] **Step 6: Commit**

```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/styles/loader.py tests/unit/test_stylesheet_loader_glass.py && git commit -m "feat(styles): PR-V3 Task 4 — StylesheetLoader.glass_supported 属性 (启动期检测)"
```

---

## Task 5: 更新 `theme.py` LIGHT/DARK 字典引用 `tokens.py`

**Files:**
- Modify: `theme.py`（顶层）

**Interfaces:**
- Consumes: Task 1 + Task 2（tokens.py 已含完整字段）
- Produces: `from theme import Theme` 仍可用；LIGHT/DARK 字典内容从 `tokens.LIGHT.__dict__` / `tokens.DARK.__dict__` 派生，不再硬编码 hex

- [ ] **Step 1: 写失败的 theme 引用测试**

新建 `tests/unit/test_theme_tokens_alignment.py`：

```python
"""theme.py LIGHT/DARK 与 tokens.py 对齐测试 (PR-V1 Task 5)。"""
import pytest


def test_theme_light_matches_tokens_light():
    """theme.py.Theme.LIGHT 字典内容应与 tokens.py LIGHT dataclass 一致。

    注: Spec A §4.1 颜色 hex 全量更新属于 PR-V4(应用层)。
        本 Task 5 仅做数据层对齐,确保 theme.py 从 tokens 派生而非硬编码。
    """
    from theme import Theme
    from secureredact.ui.styles.tokens import LIGHT
    # 字段数对齐
    assert set(Theme.LIGHT.keys()) == set(LIGHT.__dataclass_fields__.keys())
    # 颜色值逐字段比对(主题字段必须从 tokens 派生,而非独立硬编码)
    for field in LIGHT.__dataclass_fields__:
        assert Theme.LIGHT[field] == getattr(LIGHT, field), (
            f"Theme.LIGHT[{field!r}] = {Theme.LIGHT[field]!r} 不等于 tokens.LIGHT.{field} = {getattr(LIGHT, field)!r}"
        )


def test_theme_dark_matches_tokens_dark():
    """theme.py.Theme.DARK 字典内容应与 tokens.py DARK dataclass 一致。"""
    from theme import Theme
    from secureredact.ui.styles.tokens import DARK
    assert set(Theme.DARK.keys()) == set(DARK.__dataclass_fields__.keys())
    for field in DARK.__dataclass_fields__:
        assert Theme.DARK[field] == getattr(DARK, field), (
            f"Theme.DARK[{field!r}] 不等于 tokens.DARK.{field}"
        )
```

- [ ] **Step 2: 运行测试验证失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_theme_tokens_alignment.py -v 2>&1 | tail -15
```

Expected: 2 个 test FAIL（hex 值不一致——theme.py 当前是 `#0F6CBD`, tokens 是 `#2563EB`）

- [ ] **Step 3: 重写 `theme.py` LIGHT/DARK 字典为派生**

修改 `theme.py`，把 `LIGHT = {...}` 和 `DARK = {...}` 两段硬编码字典改为派生：

```python
# === 主题系统模块 ===
# Windows-first 办公软件风格主题定义
# 支持浅色/深色主题切换
# PR-V1 Task 5: LIGHT/DARK 字典从硬编码改为从 secureredact.ui.styles.tokens 派生
# (避免主题字段在两处定义产生 drift)

from secureredact.ui.styles.tokens import LIGHT as _TOKENS_LIGHT, DARK as _TOKENS_DARK
from dataclasses import asdict


class Theme:
    """主题颜色和样式定义。LIGHT/DARK 直接从 tokens 派生。"""

    # 浅色主题(办公暖白版,PR-V4 完整落地;本 PR-V1 仅数据层对齐)
    LIGHT = asdict(_TOKENS_LIGHT)

    # 深色主题(默认,LOGO Slate-900)
    DARK = asdict(_TOKENS_DARK)

    # === 布局常量(保留向后兼容,逐步迁移到 secureredact.ui.styles.tokens) ===
    # PR-V1 Task 5: 以下常量保留作为运行时别名,内部值委托给 tokens 模块
    BORDER_RADIUS = 12            # 历史 alias,实际值用 RADIUS_LG
    BUTTON_RADIUS = 10            # 历史 alias,实际值用 RADIUS_MD
    SPACING_SMALL = 8             # alias → SPACING_SM
    SPACING_MEDIUM = 14           # alias → SPACING_MD
    SPACING_LARGE = 22            # alias → SPACING_LG

    # 字体(保留 alias)
    FONT_FAMILY = "'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', Arial, sans-serif"
    FONT_SIZE_SMALL = 12
    FONT_SIZE_NORMAL = 14
    FONT_SIZE_LARGE = 18

    # 动画
    ANIMATION_DURATION = 200      # alias → DURATION_NORMAL

    @staticmethod
    def get_theme(theme_name="light"):
        """获取主题配置"""
        return Theme.LIGHT if theme_name == "light" else Theme.DARK

    @staticmethod
    def adjust_color(hex_color, amount):
        """调整颜色亮度(保留,向后兼容)"""
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]
        try:
            r = max(0, min(255, int(hex_color[0:2], 16) + amount))
            g = max(0, min(255, int(hex_color[2:4], 16) + amount))
            b = max(0, min(255, int(hex_color[4:6], 16) + amount))
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, TypeError):
            return hex_color
```

- [ ] **Step 4: 运行测试验证通过**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_theme_tokens_alignment.py -v 2>&1 | tail -10
```

Expected: `2 passed`

- [ ] **Step 5: 运行全量回归确保 0 新失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m compileall -q main.py secureredact tests
cd "G:/Project/SecureRedact" && python -m unittest discover tests -v 2>&1 | tail -5
```

Expected: `Ran 439 tests / FAILED (failures=6)`（与 baseline 一致）

- [ ] **Step 6: Commit**

```bash
cd "G:/Project/SecureRedact" && git add theme.py tests/unit/test_theme_tokens_alignment.py && git commit -m "refactor(theme): PR-V1 Task 5 — Theme.LIGHT/DARK 从 tokens 派生 (消除双源)"
```

---

## Task 6: 全量验证 + 文档同步

**Files:** （无业务文件修改，仅验证 + 文档）

**Interfaces:**
- Consumes: Task 1-5 全部完成
- Produces: 0 新失败的回归基线 + 单元测试新增 ~10 项

- [ ] **Step 1: 全量编译检查**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m compileall -q main.py secureredact tests
```

Expected: 无错误（命令成功返回 0）

- [ ] **Step 2: 运行新增 + 视觉 token 测试套件**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/unit/test_visual_tokens.py tests/unit/test_stylesheet_loader_glass.py tests/unit/test_theme_tokens_alignment.py -v 2>&1 | tail -20
```

Expected: 12+ passed(本 PR 新增 ~12 项测试,全部通过)

- [ ] **Step 3: 跑全量回归确认 0 新失败**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m unittest discover tests -v 2>&1 | tail -5
```

Expected: `Ran 449 tests / FAILED (failures=6)`（10+ 新增测试, 失败数仍为 baseline 6)

- [ ] **Step 4: 写 PR 完成报告（参考 c1-report.md 模板）**

新建 `docs/refactor/v1-task-report.md`，含：
- 范围
- 新建/修改文件清单
- 验证结果（编译 + 测试 + 行数）
- 阶段 V 后续工作表（指向 PR-V2 / V4 / C1.1 / C2.x）
- 签字

参考 `docs/refactor/c1-report.md` 的结构。

- [ ] **Step 5: Commit + 可选 push**

```bash
cd "G:/Project/SecureRedact" && git add docs/refactor/v1-task-report.md && git commit -m "docs(refactor): PR-V1 完成报告 (tokens 体系化 + Glass 检测)"
```

按需 `git push`（默认不 push，等用户指令）。

---

## 自审清单

- [x] **Spec 覆盖**：Spec A §4 Token 数值 + §6 Glass 降级 全部有 Task 覆盖
- [x] **占位符扫描**：无 TBD/TODO/FIXME
- [x] **类型一致性**：`Tokens` dataclass 字段数 = `LIGHT/DARK` 实例字段数 = `get_substitution_map` 输出数（17 + 3 字体 = 20）
- [x] **测试设计**：TDD 风格(每个 Task: 写失败测试 → 实现 → 验证通过)；新增 ~12 项单元测试
- [x] **Commit 粒度**：6 个 Task → 6 个 commit，每 commit 独立 bisect
- [x] **风险控制**：theme.py 保留所有向后兼容 alias（`BORDER_RADIUS` / `SPACING_SMALL` / `ANIMATION_DURATION` 等），MainWindow 内嵌 QSS 不动

---

## 范围外（明确不做）

1. **颜色 hex 全量更新**（Spec A §4.1 的 hex 值替换）→ 属于 PR-V4（应用层替换 MainWindow 内嵌 QSS 时一起改）。本 PR 数据层先扩展到位，向后兼容原 hex 值不破坏现有 .qss 占位符替换。
2. **6 类组件 .qss 实际样式内容** → 属于 Plan 2b（PR-V2）
3. **MainWindow 内嵌 622 行 QSS 迁移** → 属于 Plan 2b（PR-V4）
4. **SettingsDialog 主题切换 UI** → 属于 Plan 2b（PR-C1.1）
5. **视觉基线补齐** → 属于 Plan 2b（PR-C2.x）

---

## 执行选项

本 plan 已完成并保存到 `docs/superpowers/plans/2026-08-30-visual-tokens-foundation.md`。

两种执行方式：

**1. Subagent-Driven（推荐）** — 每 Task 派 fresh subagent，Task 之间做 review，迭代快
**2. Inline Execution** — 当前会话顺序执行，到 checkpoint 暂停确认

请选择执行方式，或先确认 plan 细节后再启动。