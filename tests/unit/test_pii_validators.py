"""Phase 1 PII validators 单元测试（NUM-01 / NUM-02 / NUM-03 覆盖率）。

覆盖矩阵：
- NUM-01 18 位 + 15 位身份证号 GB 11643 mod-11-2 校验
- NUM-02 末位大小写 X 兼容（OCR 小写 x 归一化）
- NUM-03 中国大陆手机号段号白名单 + 14X IoT/卫星排除

B1 second gate（15 位升级后）：行政区划码 2 位前缀 + 真实日历日期。
"""
import unittest

from privacyguard.pii.validators.id_card import (
    compute_check_digit,
    is_real_calendar_date,
    is_valid_admin_division_prefix_2,
    upgrade_15_to_18,
    validate_15,
    validate_18,
)
from privacyguard.pii.validators.phone_segment import (
    PHONE_EXCLUDED_PREFIX_3,
    PHONE_EXCLUDED_PREFIX_4,
    PHONE_PERSONAL_PREFIX_3,
    is_mobile_segment,
)


# GB 11643-1999 标准样本：53010219200508011X
_GB_STD_18 = "53010219200508011X"
_GB_STD_18_INVALID = "530102192005080119"  # 校验位错误

# 真实合法 15 位（420106=湖北宜昌市，1969-09-01 真实日历）
_REAL_15 = "420106690901234"

# 真实合法 18 位（GB 标准样本升级版）
_REAL_18_FROM_15 = "420106196909012345"  # 占位，下面重新计算正确校验位


def _upgrade_with_check(id15: str) -> str:
    """手工升级 15 位并附加校验位（测试 helper）。"""
    body17 = id15[:6] + "19" + id15[6:]
    return body17 + compute_check_digit(body17)


_REAL_18_FROM_15 = _upgrade_with_check(_REAL_15)


class TestIdCardChecksum(unittest.TestCase):
    """NUM-01: 18 位 GB 11643 mod-11-2 校验位正向 + 反向。"""

    def test_valid_18_passes_checksum(self):
        self.assertTrue(validate_18(_GB_STD_18))

    def test_invalid_check_digit_fails(self):
        self.assertFalse(validate_18(_GB_STD_18_INVALID))

    def test_lowercase_x_accepted_via_upper(self):
        """NUM-02: OCR 输出的 'x' 经归一化后通过校验。"""
        self.assertTrue(validate_18(_GB_STD_18.replace("X", "x")))

    def test_corrupted_body_fails(self):
        """前 17 位含非数字必须 False。"""
        self.assertFalse(validate_18("53010A19200508011X"))

    def test_short_id_rejected(self):
        self.assertFalse(validate_18("123"))

    def test_long_id_rejected(self):
        self.assertFalse(validate_18("1" * 19))

    def test_empty_string_rejected(self):
        self.assertFalse(validate_18(""))

    def test_last_char_invalid_rejected(self):
        """NUM-02: 末位非 [0-9Xx] 必须 False。"""
        self.assertFalse(validate_18("53010219200508011Z"))

    def test_15_digit_input_rejected_by_validate_18(self):
        """validate_18 不接受 15 位（15 位由 validate_15 处理）。"""
        self.assertFalse(validate_18(_REAL_15))


class TestIdCardUpgrade15To18(unittest.TestCase):
    """NUM-01: 15 位 → 18 位升级 + 双门（B1）守卫。"""

    def test_15_digit_upgrades_to_valid_18(self):
        upgraded = upgrade_15_to_18(_REAL_15)
        self.assertEqual(len(upgraded), 18)
        self.assertTrue(validate_18(upgraded))

    def test_15_digit_century_prefix_is_19(self):
        upgraded = upgrade_15_to_18("110101800101001")
        # 11=北京，01=市辖区，01=区，800101=1980-01-01，001=序
        self.assertTrue(upgraded.startswith("11010119"))

    def test_non_15_digit_returns_empty(self):
        self.assertEqual(upgrade_15_to_18("123"), "")

    def test_non_digit_15_rejected(self):
        self.assertEqual(upgrade_15_to_18("42010696090123A"), "")

    def test_validate_15_passes_for_valid_upgraded(self):
        self.assertTrue(validate_15(_REAL_15))

    def test_15_digit_invalid_province_prefix_rejected(self):
        """B1: '99' 不在行政区划白名单 → False。"""
        self.assertFalse(validate_15("990106800101001"))

    def test_15_digit_zero_province_prefix_rejected(self):
        """B1: '00' 不在白名单 → False（订单号 / 序列号常见前缀）。"""
        self.assertFalse(validate_15("000106800101001"))

    def test_15_digit_impossible_month_rejected(self):
        """B1: 月份 13 → False（不可能日历日期）。"""
        self.assertFalse(validate_15("420106801301001"))

    def test_15_digit_impossible_day_rejected(self):
        """B1: 日期 32 → False（不可能日历日期）。"""
        self.assertFalse(validate_15("420106800132001"))

    def test_15_digit_feb_30_rejected(self):
        """B1: 2 月 30 日 → False（公历不存在 2-30）。"""
        self.assertFalse(validate_15("420106800230001"))

    def test_is_valid_admin_division_prefix_2_whitelist(self):
        """B1: 行政区划前缀白名单（含 / 不含）。"""
        self.assertTrue(is_valid_admin_division_prefix_2("11"))  # 北京
        self.assertTrue(is_valid_admin_division_prefix_2("82"))  # 澳门
        self.assertFalse(is_valid_admin_division_prefix_2("00"))  # 非法
        self.assertFalse(is_valid_admin_division_prefix_2("90"))  # 非法
        self.assertFalse(is_valid_admin_division_prefix_2("99"))  # 非法

    def test_is_real_calendar_date_boundary(self):
        """B1: 真实日历日期边界（含闰年 / 月份边界 / 2-29 / 4-30）。"""
        self.assertTrue(is_real_calendar_date(85, 1, 1))    # 元旦
        # 1984（yy=84）是闰年，2-29 合法；1985（yy=85）非闰年，2-29 非法
        self.assertTrue(is_real_calendar_date(84, 2, 29))   # 1984 闰年
        self.assertFalse(is_real_calendar_date(85, 2, 29))  # 1985 非闰年
        self.assertFalse(is_real_calendar_date(85, 13, 1))  # 月份超界
        self.assertFalse(is_real_calendar_date(85, 1, 32))  # 日期超界
        # 4 月 30 天 → 4-30 合法
        self.assertTrue(is_real_calendar_date(85, 4, 30))
        # 4 月无 31 → 4-31 非法
        self.assertFalse(is_real_calendar_date(85, 4, 31))
        self.assertFalse(is_real_calendar_date(85, 2, 30))  # 2 月无 30


class TestIdCaseInsensitiveX(unittest.TestCase):
    """NUM-02: 末位 X / OCR 小写 x 全路径兼容。"""

    def test_uppercase_X_passes(self):
        self.assertTrue(validate_18(_GB_STD_18))

    def test_lowercase_x_passes(self):
        self.assertTrue(validate_18(_GB_STD_18.replace("X", "x")))

    def test_invalid_letter_rejected(self):
        self.assertFalse(validate_18("53010219200508011Y"))


class TestIdCardDefensive(unittest.TestCase):
    """NUM-01: 防御性输入（None / 非字符串 / 异常类型）。"""

    def test_none_rejected(self):
        self.assertFalse(validate_18(None))  # type: ignore[arg-type]

    def test_int_rejected(self):
        self.assertFalse(validate_18(123456789012345678))  # type: ignore[arg-type]


class TestPhoneSegment(unittest.TestCase):
    """NUM-03: 中国大陆手机号段号白名单正向覆盖。"""

    def test_personal_segment_recognized(self):
        # 至少覆盖 30 个号段；每个接 8 位随机数字
        personal_prefixes = sorted(PHONE_PERSONAL_PREFIX_3)
        self.assertGreaterEqual(
            len(personal_prefixes),
            30,
            f"personal_prefix_3 仅有 {len(personal_prefixes)} 段，需 ≥30 段覆盖",
        )
        # 每个白名单前缀 + "12345678" 必须 True
        for prefix in personal_prefixes:
            phone = prefix + "12345678"
            self.assertTrue(
                is_mobile_segment(phone),
                f"个人号段 {prefix} 未被识别: {phone}",
            )


class TestIotExclusion(unittest.TestCase):
    """NUM-03: IoT / 数据卡 / 卫星段必须被排除。"""

    def test_iot_segment_excluded(self):
        for prefix in ("140", "141", "144", "145", "146", "147", "148", "149"):
            self.assertFalse(is_mobile_segment(prefix + "12345678"),
                             f"IoT 段 {prefix} 未被排除")

    def test_satellite_prefix_1349_excluded(self):
        self.assertFalse(is_mobile_segment("13491234567"))

    def test_satellite_prefix_1740_excluded(self):
        self.assertFalse(is_mobile_segment("17401234567"))

    def test_satellite_prefix_1741_excluded(self):
        self.assertFalse(is_mobile_segment("17411234567"))

    def test_data_card_prefix_145_excluded(self):
        self.assertFalse(is_mobile_segment("14512345678"))

    def test_non_leading_one_rejected(self):
        self.assertFalse(is_mobile_segment("23812345678"))

    def test_short_phone_rejected(self):
        self.assertFalse(is_mobile_segment("1381234567"))

    def test_long_phone_rejected(self):
        self.assertFalse(is_mobile_segment("138123456789"))

    def test_non_digit_phone_rejected(self):
        self.assertFalse(is_mobile_segment("1381234567A"))

    def test_empty_string_rejected(self):
        self.assertFalse(is_mobile_segment(""))


class TestPhoneSegmentDefensive(unittest.TestCase):
    """NUM-03: 防御性输入。"""

    def test_none_rejected(self):
        self.assertFalse(is_mobile_segment(None))  # type: ignore[arg-type]


class TestPhoneSegmentTables(unittest.TestCase):
    """NUM-03: 段号表常量完整性（IoT / 卫星前缀必须存在于 excluded sets）。"""

    def test_iot_3_digit_prefixes_present(self):
        for p in ("140", "141", "144", "145", "146", "147", "148", "149"):
            self.assertIn(p, PHONE_EXCLUDED_PREFIX_3,
                          f"IoT 段 {p} 必须在 PHONE_EXCLUDED_PREFIX_3")

    def test_satellite_4_digit_prefixes_present(self):
        for p in ("1349", "1440", "1740", "1741"):
            self.assertIn(p, PHONE_EXCLUDED_PREFIX_4,
                          f"卫星段 {p} 必须在 PHONE_EXCLUDED_PREFIX_4")


if __name__ == "__main__":
    unittest.main()
