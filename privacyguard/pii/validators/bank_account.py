"""银行账号校验（FIN-04 + D-08 必查上下文锥点）。

- 9-21 位纯数字（含横线 / 空格剥离后）
- 必加上下文锥点（账号 / 账户 / 银行账号 / 招行 / 中行 / 建行 /
  工商银行 / 农行 / 邮储 / 交通银行 等）±20 字符
- 无上下文锥点不产生 candidate（reject 在 engine 层强制）
"""
from typing import Final


# BANK_ACCOUNT 上下文锥点白名单（4 generic + 5 big-5 + 7 股份制 + 1 城商行 = 17）
# Claude's Discretion 锁定：D-08 严格模式，必查锥点
BANK_ACCOUNT_CONTEXTS: Final = frozenset({
    # 4 generic
    "账号", "账户", "银行账号", "银行账户",
    # 5 big-5（工/农/中/建/邮）
    "工商银行", "农行", "中行", "建行", "邮储",
    # 7 股份制商业银行
    "招行", "交通银行", "中信", "浦发", "兴业", "民生", "平安",
    # 1 城商行
    "上海银行",
})


def validate_bank_account(account: str) -> bool:
    """9-21 位银行账号纯数字格式校验（含横线 / 空格剥离）。

    不含上下文锥点检查 — 锥点由 engine._check_bank_account 强制调用 has_bank_account_context。
    防御性：非字符串 / 非数字 / 长度不在 9-21 范围 → False。

    Args:
        account: 候选账号字符串

    Returns:
        True 当且仅当剥离后是 9-21 位纯数字。
    """
    if not isinstance(account, str):
        return False
    stripped = account.replace(" ", "").replace("-", "")
    return stripped.isdigit() and 9 <= len(stripped) <= 21


def has_bank_account_context(text: str, target: str, window: int = 20) -> bool:
    """target ±window 字符内是否存在银行账号上下文锥点（D-08 必查）。

    Args:
        text: 完整页面文本
        target: 待测候选字符串（账号本身）
        window: 锥点判定窗口半径（默认 20 字符，±20 字符）

    Returns:
        True 当且仅当 text 内 target 附近存在 BANK_ACCOUNT_CONTEXTS 任一锥点。
    """
    if not text or not target:
        return False
    idx = text.find(target)
    if idx < 0:
        return False
    lo = max(0, idx - window)
    hi = min(len(text), idx + len(target) + window)
    window_text = text[lo:hi]
    return any(ctx in window_text for ctx in BANK_ACCOUNT_CONTEXTS)


__all__ = [
    "validate_bank_account",
    "has_bank_account_context",
    "BANK_ACCOUNT_CONTEXTS",
]
