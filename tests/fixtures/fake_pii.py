"""合成 PII 生成器（OPS-05 严禁真实数据；random + mod-11-2 校验循环）。

Phase 1 不引入 Faker 依赖（环境探测结论：Faker 未在 requirements.txt），
改用 random.randint + 校验循环；与 Faker 兼容的接口形态。

模块加载策略：仅导入 stdlib；privacyguard.pii.validators.id_card 走懒加载
（保持隐私包在不触发时不被加载）。
"""
import random


def _compute_check_digit(body17: str) -> str:
    """在合成阶段独立计算 GB 11643 mod-11-2 校验位；不依赖 privacyguard.pii 包。

    与 privacyguard.pii.validators.id_card.compute_check_digit 等价，但放在
    fixtures 目录以保证 fake_* 在缺包时仍可用。
    """
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    mapping = ('1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2')
    return mapping[sum(int(body17[i]) * weights[i] for i in range(17)) % 11]


def fake_id_card() -> str:
    """生成一个通过 mod-11-2 校验的 18 位伪身份证号。

    返回值保证通过 GB 11643 校验，但不保证对应真实行政区划 / 出生日期。
    """
    while True:
        body17 = ''.join(random.choice('0123456789') for _ in range(17))
        if body17[0] == '0':
            continue
        check = _compute_check_digit(body17)
        candidate = body17 + check
        if candidate[17].upper() == _compute_check_digit(body17):
            return candidate


def fake_phone(seg: str = '138') -> str:
    """生成一个通过 is_mobile_segment 的伪手机号。

    seg 默认 '138'（移动），需在 PHONE_PERSONAL_PREFIX_3 白名单内。
    """
    return seg + ''.join(random.choice('0123456789') for _ in range(8))


def fake_phone_invalid() -> str:
    """生成一个 14X 物联网段（应被 is_mobile_segment 排除）。"""
    return '140' + ''.join(random.choice('0123456789') for _ in range(8))


def fake_phone_lowercase_tail() -> str:
    """占位辅助函数：保留扩展位，未来用于 NUM-02 小写 x 测试。"""
    raise NotImplementedError("OCR 小写 x 路径在 01-01 之外验证")