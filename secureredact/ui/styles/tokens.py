"""
设计 token — SecureRedact v1.1.13 (Name Context Injection) 重构基线

来源:原 `theme.py` 字典(91 行)。
本模块把 LIGHT/DARK 字典升级为不可变 dataclass,新增 `get_substitution_map()`
用于 .qss 模板的 `{token_name}` 占位符替换。

约束:
- 仅 LIGHT/DARK 配色字典被迁入,布局常量/字体常量仍由 theme.py 保留供运行时使用
  (B1 阶段不破现有 import);B2 阶段 MainWindow 拆分时再统一收口
- 不引入 Pydantic 等额外依赖(unittest 已在用,PyQt6 已是必需)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Mapping


@dataclass(frozen=True)
class Tokens:
    """17 个语义 token,Light/Dark 共用键集(primary_hover 在 PR-V1 Task 2 新增)。"""

    background: str
    surface: str
    primary: str
    primary_hover: str  # PR-V1 Task 2 新增（Logo Blue-700/600）
    secondary: str
    accent: str
    text: str
    text_secondary: str
    border: str
    shadow: str
    info_bar: str
    scroll_area: str
    hover: str
    pressed: str
    success: str
    danger: str
    warning: str


# === 配色字典(与 theme.py LIGHT/DARK 完全一致,v1.1.13 基线) ===

LIGHT = Tokens(
    background="#F7F8FA",
    surface="#FFFFFF",
    primary="#0F6CBD",
    primary_hover="#1D4ED8",  # Blue-700 (LOGO)
    secondary="#5F6B7A",
    accent="#0FA968",
    text="#18212F",
    text_secondary="#5F6B7A",
    border="#E2E8F0",
    shadow="rgba(18, 31, 53, 0.10)",
    info_bar="#F9FBFD",
    scroll_area="#F6F8FB",
    hover="#EEF4FB",
    pressed="#E3ECF8",
    success="#0FA968",
    danger="#D64545",
    warning="#D9831F",
)

DARK = Tokens(
    background="#151C26",
    surface="#1E2836",
    primary="#56A8FF",
    primary_hover="#2563EB",  # Blue-600 (LOGO Dark)
    secondary="#9AA8BA",
    accent="#34D399",
    text="#F6F8FC",
    text_secondary="#AAB5C5",
    border="#324255",
    shadow="rgba(0,0,0,0.30)",
    info_bar="#1E2A3B",
    scroll_area="#1A2330",
    hover="#263241",
    pressed="#314155",
    success="#34D399",
    danger="#FF6B6B",
    warning="#FFB454",
)


# === 字体/字号常量(供 .qss 占位符替换) ===

FONT_FAMILY = "'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', Arial, sans-serif"
FONT_SIZE_SMALL = 12
FONT_SIZE_NORMAL = 14


# === 主题注册表 ===

THEMES: Dict[str, Tokens] = {"light": LIGHT, "dark": DARK}


def get_tokens(theme_name: str = "light") -> Tokens:
    """按名称取 token dataclass;未知名称默认 light(基线兼容)。"""
    return THEMES.get(theme_name, LIGHT)


def get_substitution_map(theme_name: str = "light") -> Mapping[str, str]:
    """返回 token 名字 → 实际值的 dict,供 .qss 模板替换。

    字段集:
      - 17 个颜色 token 全部展开(primary_hover PR-V1 Task 2 新增)
      - 字体/字号常量:font_family / font_size_small / font_size_normal
    """
    tokens = get_tokens(theme_name)
    mapping: Dict[str, str] = asdict(tokens)
    mapping["font_family"] = FONT_FAMILY
    mapping["font_size_small"] = str(FONT_SIZE_SMALL)
    mapping["font_size_normal"] = str(FONT_SIZE_NORMAL)
    return mapping


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