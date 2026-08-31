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