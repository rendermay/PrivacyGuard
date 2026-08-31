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
