"""v1.1.12: 部分遮蔽工具函数单元测试。"""

import unittest

from secureredact.utils.masking import (
    apply_email_mask,
    apply_mask_for_rule,
    apply_name_mask,
    apply_partial_mask,
    resolve_mask_config,
)


class TestApplyPartialMask(unittest.TestCase):
    """apply_partial_mask: 保留前 N + 后 N, 中间打码。"""

    def test_id_card_6_4(self):
        self.assertEqual(
            apply_partial_mask("110101199001011234", 6, 4),
            "110101********1234",
        )

    def test_mobile_3_4(self):
        self.assertEqual(
            apply_partial_mask("13812345678", 3, 4),
            "138****5678",
        )

    def test_bank_card_4_4(self):
        self.assertEqual(
            apply_partial_mask("6222600012345678", 4, 4),
            "6222********5678",
        )

    def test_landline_0_4(self):
        """固定电话 11 位: 保留后 4, 中间 7 位打码。"""
        self.assertEqual(
            apply_partial_mask("01012345678", 0, 4),
            "*******5678",
        )

    def test_uscc_4_4(self):
        """USCC 18 位: 保留前 4 + 后 4, 中间 10 位打码。

        text = '91110108MA01KXYX29'
          idx:0='9', 1='1', 2='1', 3='1', 4='0', 5='1', 6='0', 7='8',
              8='M', 9='A', 10='0', 11='1', 12='K', 13='X',
              14='Y', 15='X', 16='2', 17='9'
        text[:4] = '9111', text[-4:] = 'YX29'
        """
        self.assertEqual(
            apply_partial_mask("91110108MA01KXYX29", 4, 4),
            "9111**********YX29",
        )

    def test_uscc_real_sample_17_chars(self):
        """抵账协议真实 17 位样本(规则兼容旧组织机构代码)。
        保留前 4 + 后 4, 中间 9 位打码。"""
        self.assertEqual(
            apply_partial_mask("9151152MA6ARBNK4W", 4, 4),
            "9151*********NK4W",
        )

    def test_zero_zero_full_mask(self):
        """prefix=0 suffix=0 → 整段打码。"""
        self.assertEqual(
            apply_partial_mask("2024-01-15", 0, 0),
            "**********",
        )

    def test_full_mask_count_matches(self):
        self.assertEqual(
            apply_partial_mask("abcdefghij", 0, 0),
            "**********",
        )

    def test_boundary_text_too_short(self):
        """len(text) < prefix + suffix → 原样返回。"""
        self.assertEqual(apply_partial_mask("1234567", 4, 4), "1234567")

    def test_boundary_exact_length(self):
        """len(text) == prefix + suffix → 原样返回。"""
        self.assertEqual(apply_partial_mask("12345678", 4, 4), "12345678")

    def test_suffix_zero_path(self):
        """suffix=0 → 不调用负索引切片,避免 text[-0:] 返回全部。"""
        self.assertEqual(
            apply_partial_mask("abcdefgh", 4, 0),
            "abcd****",
        )

    def test_prefix_zero_suffix_only(self):
        self.assertEqual(
            apply_partial_mask("abcdefgh", 0, 3),
            "*****fgh",
        )

    def test_negative_prefix_raises(self):
        with self.assertRaises(ValueError):
            apply_partial_mask("hello", -1, 2)

    def test_negative_suffix_raises(self):
        with self.assertRaises(ValueError):
            apply_partial_mask("hello", 2, -1)

    def test_empty_mask_char_raises(self):
        with self.assertRaises(ValueError):
            apply_partial_mask("hello", 1, 1, mask_char="")

    def test_empty_text(self):
        self.assertEqual(apply_partial_mask("", 2, 2), "")

    def test_non_string_returns_as_is(self):
        self.assertEqual(apply_partial_mask(None, 2, 2), None)
        self.assertEqual(apply_partial_mask(12345, 2, 2), 12345)

    def test_custom_mask_char(self):
        self.assertEqual(
            apply_partial_mask("12345678", 2, 2, mask_char="#"),
            "12####78",
        )

    def test_unicode_text(self):
        """Unicode 文本按字符索引,不按字节。"""
        self.assertEqual(
            apply_partial_mask("张三李四", 1, 1),
            "张**四",
        )


class TestApplyEmailMask(unittest.TestCase):
    """apply_email_mask: 用户名 1 位 + *** + @ + 域名。"""

    def test_normal_email(self):
        self.assertEqual(apply_email_mask("alice@example.com"), "a***@example.com")

    def test_short_local_one_char(self):
        self.assertEqual(apply_email_mask("b@example.com"), "b***@example.com")

    def test_no_at_sign_returns_as_is(self):
        """不含 @ → 原样,让上层 fallback。"""
        self.assertEqual(apply_email_mask("notanemail"), "notanemail")

    def test_empty_local(self):
        """@example.com (空 local) → 原样。"""
        self.assertEqual(apply_email_mask("@example.com"), "@example.com")

    def test_subdomain_preserved(self):
        self.assertEqual(
            apply_email_mask("user@mail.sub.example.co"),
            "u***@mail.sub.example.co",
        )

    def test_long_local(self):
        self.assertEqual(
            apply_email_mask("longusername@example.com"),
            "l***@example.com",
        )

    def test_custom_mask_char(self):
        self.assertEqual(
            apply_email_mask("alice@example.com", mask_char="#"),
            "a###@example.com",
        )

    def test_non_string_returns_as_is(self):
        self.assertEqual(apply_email_mask(None), None)


class TestApplyNameMask(unittest.TestCase):
    """apply_name_mask: 姓保留 + 其余全打码。"""

    def test_two_char_name(self):
        self.assertEqual(apply_name_mask("张三"), "张*")

    def test_three_char_name(self):
        self.assertEqual(apply_name_mask("李四光"), "李**")

    def test_four_char_name(self):
        self.assertEqual(apply_name_mask("欧阳娜娜"), "欧***")

    def test_single_char_unchanged(self):
        """单字不变成空串。"""
        self.assertEqual(apply_name_mask("张"), "张")

    def test_empty(self):
        self.assertEqual(apply_name_mask(""), "")

    def test_english_name(self):
        """英文姓名仍按"保留首字+其余打码"语义。"""
        self.assertEqual(apply_name_mask("Tom"), "T**")

    def test_label_with_ascii_colon(self):
        """label + 姓名 模式(ASCII 冒号)→ 只 mask 姓名, label 保留。"""
        self.assertEqual(apply_name_mask("法定代表人:周超"), "法定代表人:周*")
        self.assertEqual(apply_name_mask("法定代表人:欧阳娜娜"), "法定代表人:欧***")

    def test_label_with_fullwidth_colon(self):
        """label + 姓名 模式(全角冒号)→ 只 mask 姓名, label 保留。"""
        self.assertEqual(apply_name_mask("法定代表人：周超"), "法定代表人：周*")
        self.assertEqual(apply_name_mask("法定代表人：欧阳娜娜"), "法定代表人：欧***")

    def test_label_with_other_prefix(self):
        """其他 label 格式也支持(如"姓名:")。"""
        self.assertEqual(apply_name_mask("姓名:张三"), "姓名:张*")
        self.assertEqual(apply_name_mask("甲方代表:李四光"), "甲方代表:李**")

    def test_label_with_too_long_tail_keeps_old_behavior(self):
        """尾部超过 4 字(不像姓名)→ 走纯姓名逻辑(保留首字)。"""
        # "Label:ABCDE" 11 字符, 保留首字 + 10 个 *
        self.assertEqual(apply_name_mask("Label:ABCDE"), "L" + "*" * 10)

    def test_custom_mask_char(self):
        self.assertEqual(apply_name_mask("张三", mask_char="#"), "张#")

    def test_non_string_returns_as_is(self):
        self.assertEqual(apply_name_mask(None), None)


class TestResolveMaskConfig(unittest.TestCase):
    """resolve_mask_config: 按规则名查 meta 表。"""

    META = {
        "身份证号": {
            "mask_mode": "default",
            "mask_keep_prefix": 6,
            "mask_keep_suffix": 4,
        },
        "电子邮箱": {"mask_mode": "email"},
        "法定代表人": {"mask_mode": "name", "mask_keep_prefix": 1},
    }

    def test_returns_full_config_with_defaults(self):
        cfg = resolve_mask_config("身份证号", self.META)
        self.assertEqual(cfg["mask_mode"], "default")
        self.assertEqual(cfg["mask_keep_prefix"], 6)
        self.assertEqual(cfg["mask_keep_suffix"], 4)
        self.assertEqual(cfg["mask_char"], "*")  # 默认

    def test_returns_none_for_unknown_rule(self):
        self.assertIsNone(resolve_mask_config("未知规则", self.META))

    def test_returns_none_for_empty_name(self):
        self.assertIsNone(resolve_mask_config("", self.META))

    def test_returns_none_for_non_string(self):
        self.assertIsNone(resolve_mask_config(None, self.META))
        self.assertIsNone(resolve_mask_config(123, self.META))

    def test_handles_missing_meta_fields_with_defaults(self):
        """meta 条目缺字段 → 补默认值, 不抛异常。"""
        cfg = resolve_mask_config("电子邮箱", {"电子邮箱": {}})
        self.assertEqual(cfg["mask_mode"], "default")
        self.assertEqual(cfg["mask_keep_prefix"], 0)
        self.assertEqual(cfg["mask_keep_suffix"], 0)
        self.assertEqual(cfg["mask_char"], "*")

    def test_int_coercion_from_string(self):
        """meta 里字段可能是字符串(从 config.json 读), 应当强转为 int。"""
        meta = {"测试": {"mask_keep_prefix": "6", "mask_keep_suffix": "4"}}
        cfg = resolve_mask_config("测试", meta)
        self.assertIsInstance(cfg["mask_keep_prefix"], int)
        self.assertEqual(cfg["mask_keep_prefix"], 6)

    def test_returns_none_for_non_dict_meta(self):
        self.assertIsNone(
            resolve_mask_config("测试", {"测试": "not a dict"})
        )


class TestApplyMaskForRule(unittest.TestCase):
    """apply_mask_for_rule: 单入口, 根据 mode 分派。"""

    META = {
        "身份证号": {
            "mask_mode": "default",
            "mask_keep_prefix": 6,
            "mask_keep_suffix": 4,
        },
        "手机号码": {
            "mask_mode": "default",
            "mask_keep_prefix": 3,
            "mask_keep_suffix": 4,
        },
        "电子邮箱": {"mask_mode": "email"},
        "法定代表人": {"mask_mode": "name", "mask_keep_prefix": 1},
        "统一社会信用代码": {
            "mask_mode": "default",
            "mask_keep_prefix": 4,
            "mask_keep_suffix": 4,
        },
    }

    def test_id_card_rule(self):
        result = apply_mask_for_rule(
            "110101199001011234", "身份证号", self.META
        )
        self.assertEqual(result, "110101********1234")

    def test_mobile_rule(self):
        result = apply_mask_for_rule("13812345678", "手机号码", self.META)
        self.assertEqual(result, "138****5678")

    def test_email_rule(self):
        result = apply_mask_for_rule(
            "alice@example.com", "电子邮箱", self.META
        )
        self.assertEqual(result, "a***@example.com")

    def test_name_rule(self):
        result = apply_mask_for_rule("张三", "法定代表人", self.META)
        self.assertEqual(result, "张*")

    def test_uscc_rule(self):
        result = apply_mask_for_rule(
            "91110108MA01KXYX29", "统一社会信用代码", self.META
        )
        self.assertEqual(result, "9111**********YX29")

    def test_uscc_rule_17_chars(self):
        """17 位样本: 保留前 4 + 后 4, 中间 9 位打码。"""
        result = apply_mask_for_rule(
            "9151152MA6ARBNK4W", "统一社会信用代码", self.META
        )
        self.assertEqual(result, "9151*********NK4W")

    def test_unknown_rule_returns_none(self):
        """未配置 mask → 返回 None, 调用方 fallback 到 replacement_text。"""
        self.assertIsNone(
            apply_mask_for_rule("hello", "未知", self.META)
        )

    def test_zero_zero_means_full_mask(self):
        """prefix=0 + suffix=0 → 整段打码(全 *)。"""
        meta = {"日期时间": {"mask_mode": "default", "mask_keep_prefix": 0, "mask_keep_suffix": 0}}
        result = apply_mask_for_rule("2024-01-15", "日期时间", meta)
        self.assertEqual(result, "**********")


if __name__ == "__main__":
    unittest.main(verbosity=2)