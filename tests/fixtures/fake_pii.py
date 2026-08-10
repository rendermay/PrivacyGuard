"""合成 PII 生成器（OPS-05 严禁真实数据；random + mod-11-2 校验循环）。

Phase 1 不引入 Faker 依赖（环境探测结论：Faker 未在 requirements.txt），
改用 random.randint + 校验循环；与 Faker 兼容的接口形态。

模块加载策略：仅导入 stdlib；privacyguard.pii.validators.id_card 走懒加载
（保持隐私包在不触发时不被加载）。
"""
import random


# 行政区划码 2 位前缀白名单（与 privacyguard.pii.validators.id_card._VALID_ADMIN_PREFIX_2 同步）
_VALID_PROVINCE_PREFIX = (
    '11', '12', '13', '14', '15',
    '21', '22', '23',
    '31', '32', '33', '34', '35', '36', '37',
    '41', '42', '43', '44', '45', '46',
    '50', '51', '52', '53', '54',
    '61', '62', '63', '64', '65',
    '71', '81', '82',
)


def _is_leap_year(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _days_in_month(year: int, month: int) -> int:
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    if month == 2:
        return 29 if _is_leap_year(year) else 28
    return 0


def _compute_check_digit(body17: str) -> str:
    """合成阶段独立计算 GB 11643 mod-11-2 校验位；不依赖 privacyguard.pii 包。"""
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    mapping = ('1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2')
    return mapping[sum(int(body17[i]) * weights[i] for i in range(17)) % 11]


def fake_id_card(year_lo: int = 90) -> str:
    """生成一个通过 mod-11-2 校验 + 日期合法 + 行政区划前缀合法的 18 位伪身份证号。

    year_lo: 出生年份后 2 位下限（默认 90 = 1990 年）；上限为 99。
    """
    while True:
        province = random.choice(_VALID_PROVINCE_PREFIX)
        city = ''.join(random.choice('0123456789') for _ in range(4))
        year_full = 1900 + random.randint(year_lo, 99)
        month = random.randint(1, 12)
        day = random.randint(1, _days_in_month(year_full, month))
        seq = ''.join(random.choice('0123456789') for _ in range(3))
        body17 = (
            province + city
            + f'{year_full:04d}'
            + f'{month:02d}{day:02d}'
            + seq
        )
        if len(body17) != 17:
            continue
        full = body17 + _compute_check_digit(body17)
        # 二次验证
        from privacyguard.pii.validators.id_card import validate_18
        if validate_18(full):
            return full


def fake_phone(seg: str = '138') -> str:
    """生成一个通过 is_mobile_segment 的伪手机号。"""
    return seg + ''.join(random.choice('0123456789') for _ in range(8))


def fake_phone_invalid() -> str:
    """生成一个 14X 物联网段（应被 is_mobile_segment 排除）。"""
    return '140' + ''.join(random.choice('0123456789') for _ in range(8))


def fake_phone_lowercase_tail() -> str:
    """占位辅助函数：保留扩展位，未来用于 NUM-02 小写 x 测试。"""
    raise NotImplementedError("OCR 小写 x 路径在 01-01 之外验证")