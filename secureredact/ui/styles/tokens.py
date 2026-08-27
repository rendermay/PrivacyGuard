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
    """16 个语义 token,Light/Dark 共用键集。"""

    background: str
    surface: str
    primary: str
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
      - 16 个颜色 token 全部展开
      - 字体/字号常量:font_family / font_size_small / font_size_normal
    """
    tokens = get_tokens(theme_name)
    mapping: Dict[str, str] = asdict(tokens)
    mapping["font_family"] = FONT_FAMILY
    mapping["font_size_small"] = str(FONT_SIZE_SMALL)
    mapping["font_size_normal"] = str(FONT_SIZE_NORMAL)
    return mapping


__all__ = [
    "Tokens",
    "LIGHT",
    "DARK",
    "FONT_FAMILY",
    "FONT_SIZE_SMALL",
    "FONT_SIZE_NORMAL",
    "THEMES",
    "get_tokens",
    "get_substitution_map",
]