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
