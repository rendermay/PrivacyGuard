# -*- coding: utf-8 -*-
"""
中文姓名启发式识别器单元测试 (X3 方案).

覆盖法律文书高频姓名样例;与 worker/UI 解耦,直接调用识别器 API.
"""
import time
import unittest

from secureredact.pii.name_recognizer import ChineseNameRecognizer, extract_person_names


class TestChineseNameRecognizer(unittest.TestCase):
    """姓名识别器核心单元测试 — TDD 基线."""

    def setUp(self) -> None:
        # 每个用例独立实例,避免单例缓存污染
        self.recognizer = ChineseNameRecognizer()

    # ---- 应当命中的正例 ----

    def test_plaintiff_with_fullwidth_colon(self):
        names = self.recognizer.extract("原告：周强，男，汉族。")
        self.assertIn("周强", names)

    def test_legal_rep(self):
        names = self.recognizer.extract("法定代表人：曹炳志")
        self.assertIn("曹炳志", names)

    def test_plaintiff_in_narrative(self):
        # "周强" 紧跟汉字"在",纯正则无法命中,jieba 启发式应能命中
        names = self.recognizer.extract("著作权人周强在贵州省版权局完成作品登记。")
        self.assertIn("周强", names)

    def test_plaintiff_in_court_statement(self):
        names = self.recognizer.extract("本院认为张三的诉求成立。")
        self.assertIn("张三", names)

    def test_plaintiff_with_title_suffix(self):
        names = self.recognizer.extract("起诉人：李四先生")
        self.assertIn("李四", names)

    def test_manager_with_title_prefix(self):
        names = self.recognizer.extract("经理张磊负责审批。")
        self.assertIn("张磊", names)

    # ---- 应当不命中的反例 ----

    def test_does_not_match_directional_words(self):
        # "东西南北" 是方位词,不应被判为人名
        names = self.recognizer.extract("东西南北方向明确")
        self.assertEqual(
            [n for n in names if n in {"东", "南", "西", "北"}], []
        )

    def test_does_not_match_country_name(self):
        # "中国" 起始字"中"不是姓氏,不应被判为人名
        names = self.recognizer.extract("中国的银行系统稳健")
        self.assertNotIn("中国", names)

    def test_does_not_match_company_keywords(self):
        # "本公司" 不是人名
        names = self.recognizer.extract("本公司将于本周发布报告")
        self.assertNotIn("本公司", names)

    # ---- 边界 ----

    def test_empty_text(self):
        self.assertEqual(self.recognizer.extract(""), [])

    def test_pure_digits(self):
        self.assertEqual(self.recognizer.extract("12345"), [])

    def test_ocr_garbled_name_does_not_force_match(self):
        # OCR 噪声场景: 含字母 x 的"姓名" 不应被启发式强行匹配
        # (此用例不强制要求任何结果,只确保不抛异常且返回 list)
        result = self.recognizer.extract("刘x妹")
        self.assertIsInstance(result, list)

    # ---- 姓氏集合完整性 (regression: v1.1.11 漏"付") ----

    def test_recognizes_fu_surname(self):
        # regression: SURNAME_SET 历史上漏了"付",导致"付明义"这类姓名被漏识别
        names = self.recognizer.extract("原告付明义向本院提出诉讼请求：")
        self.assertIn("付明义", names)

    def test_recognizes_standalone_fu_name(self):
        # 单独"付明义"也应识别
        names = self.recognizer.extract("付明义")
        self.assertIn("付明义", names)


class TestExtractPersonNamesConvenience(unittest.TestCase):
    """便捷函数 extract_person_names(text) 应等价于单例方法."""

    def test_convenience_function(self):
        names = extract_person_names("原告：周强，男，汉族。")
        self.assertIn("周强", names)

    def test_convenience_handles_empty(self):
        self.assertEqual(extract_person_names(""), [])

    def test_convenience_recognizes_fu(self):
        # regression: 漏"付"姓 — 见 TestChineseNameRecognizer.test_recognizes_fu_surname
        names = extract_person_names("原告付明义向本院提出诉讼请求：")
        self.assertIn("付明义", names)

    def test_convenience_accepts_whitelist_kwarg(self):
        # 新签名: extract_person_names(text, whitelist=...) 向后兼容,默认 None
        # 不传 whitelist 时,识别结果与旧签名一致
        names = extract_person_names("原告：周强，男，汉族。", whitelist=None)
        self.assertIn("周强", names)
        # 显式传空 list 行为亦同 None
        names_empty = extract_person_names("原告：周强，男，汉族。", whitelist=[])
        self.assertIn("周强", names_empty)


class TestRecognizerResilience(unittest.TestCase):
    """异常安全: 识别器在异常输入下不应抛异常."""

    def setUp(self) -> None:
        self.recognizer = ChineseNameRecognizer()

    def test_none_input(self):
        # 即便输入 None,识别器也应安全处理
        try:
            result = self.recognizer.extract(None)  # type: ignore[arg-type]
            self.assertIsInstance(result, list)
        except (TypeError, ValueError):
            # 抛出显式异常也是可接受的契约
            pass

    def test_very_long_text_no_exception(self):
        # 10000 字长文本不应抛异常,返回 list
        text = "原告周强在庭上陈述。" * 1000
        result = self.recognizer.extract(text)
        self.assertIsInstance(result, list)


class TestRecognizerPerformanceBudget(unittest.TestCase):
    """性能预算 — Wave 1 软约束."""

    def setUp(self) -> None:
        self.recognizer = ChineseNameRecognizer()

    def test_1000_chars_under_500ms(self):
        text = "原告：周强在贵州省贵阳市起诉张三和李四,王五作为委托代理人参加诉讼。\n" * 30
        text = text[:1000]
        start = time.perf_counter()
        for _ in range(5):
            self.recognizer.extract(text)
        elapsed = (time.perf_counter() - start) / 5
        self.assertLess(elapsed, 0.5,
            f"姓名识别平均耗时 {elapsed*1000:.1f}ms 超过预算 500ms")


class TestRecognizerWhitelistFiltering(unittest.TestCase):
    """白名单邻接过滤 — 防 jieba 把 '丁方经' 切成 nr 人名.

    设计动机 (v1.1.11 regression):
      - 合同角色词 '甲方/乙方/丙方/丁方/戊方' 是白名单条目
      - jieba.posseg.cut 倾向把 '丁方经平等自愿' 切成 ['丁方经', ...] 且标 nr
      - '丁' 在 SURNAME_SET 中,首字校验通过,识别为 '丁方经' 人名
      - 脱敏后 '丁方' 由白名单片段级豁免保留,'经' 被脱敏,产生 '丁方丁**' 视觉错误
    修复: 候选 token 文本若包含任一非空白名单子串 → 不当作人名返回.
    """

    def setUp(self) -> None:
        self.recognizer = ChineseNameRecognizer()

    def test_ding_fang_jing_not_recognized_when_whitelisted(self):
        """核心 regression — 抵账协议0522 报告场景."""
        text = "现甲、乙、丙、丁方经平等自愿、协商一致，达成如下协议，以资共同信守。"
        names = self.recognizer.extract(
            text,
            whitelist=["甲方", "乙方", "丙方", "丁方", "戊方"],
        )
        self.assertNotIn("丁方经", names)
        self.assertEqual([n for n in names if "丁方" in n], [])

    def test_no_whitelist_old_behavior_unchanged(self):
        """不传 whitelist 时,识别行为与旧实现一致 — 不能误伤既有正例."""
        text = "现甲、乙、丙、丁方经平等自愿、协商一致，达成如下协议，以资共同信守。"
        names = self.recognizer.extract(text)
        # 没有 whitelist 时,旧行为就是把 '丁方经' 当人名 (jieba 切词不变)
        self.assertIn("丁方经", names)

    def test_whitelist_with_other_names_still_works(self):
        """白名单过滤只豁免 '含白名单子串' 的 token,正常姓名照常识别."""
        text = "原告周强与丁方代理人李四在庭上陈述。"
        names = self.recognizer.extract(
            text,
            whitelist=["丁方"],
        )
        self.assertIn("周强", names)
        self.assertIn("李四", names)
        # 不应包含 '丁方代理人' 等被白名单豁免的伪人名
        self.assertEqual([n for n in names if "丁方" in n], [])

    def test_whitelist_substring_only_filter_not_block_normal_text(self):
        """空 whitelist / 全空白 whitelist → 不过滤,保留识别能力."""
        text = "原告周强在贵州省版权局完成作品登记。"
        names = self.recognizer.extract(text, whitelist=[])
        self.assertIn("周强", names)
        names_blank = self.recognizer.extract(text, whitelist=[" ", ""])
        self.assertIn("周强", names_blank)

    def test_convenience_function_filters_with_whitelist(self):
        """便捷函数同样支持 whitelist 参数."""
        text = "现甲、乙、丙、丁方经平等自愿、协商一致。"
        names = extract_person_names(
            text,
            whitelist=["甲方", "乙方", "丙方", "丁方", "戊方"],
        )
        self.assertNotIn("丁方经", names)

    def test_other_party_word_wei_fang_also_filtered(self):
        """'戊方经' 同理豁免 — 保证方案通用,不止 '丁方'."""
        text = "现戊方经办人确认签字。"
        names = self.recognizer.extract(text, whitelist=["戊方"])
        # 即便识别到 '戊方经',只要含 '戊方' 子串即豁免
        self.assertEqual([n for n in names if "戊方" in n], [])


class TestRecognizerAmountWordImmunity(unittest.TestCase):
    """人民币大写金额结构性免疫 — 防 jieba 把 '陆佰柒' 切成 nr 人名.

    设计动机 (v1.1.11 regression):
      - '陆佰柒拾壹万零壹佰贰拾叁元叁角叁分' 是典型人民币大写金额
      - jieba.posseg.cut 倾向切成 ['陆佰柒', '拾', '壹万', ...] 且把 '陆佰柒' 标 nr
      - '陆' 在 SURNAME_SET 中,首字校验通过 → 误识别为 '陆佰柒' 人名
      - 脱敏后变成 '陆**拾壹万…', 法定的金额串被破坏
    修复: 大写金额字表结构性免疫 — 凡是 token 文本剔标点后所有汉字都属于
    大写金额字表 (零壹贰叁肆伍陆柒捌玖 + 拾佰仟万亿 + 元角分整正负),
    一律不当作人名. 无需用户配置,默认开启.
    """

    def setUp(self) -> None:
        self.recognizer = ChineseNameRecognizer()

    def test_amount_within_parens_after_label(self):
        """核心 regression — 抵账协议利息条款场景."""
        text = "本息合计6710123.33元（大写：陆佰柒拾壹万零壹佰贰拾叁元叁角叁分）"
        names = self.recognizer.extract(text)
        self.assertNotIn("陆佰柒", names,
            "人民币大写金额片段 '陆佰柒' 不应被识别为人名")

    def test_standalone_amount_snippet(self):
        """仅大写金额片段也应豁免."""
        text = "陆佰柒拾壹万零壹佰贰拾叁元叁角叁分"
        names = self.recognizer.extract(text)
        self.assertEqual([n for n in names if n in {"陆佰柒", "陆佰", "佰柒"}], [],
            "大写金额片段内部不应被切出假人名")

    def test_amount_immunity_does_not_block_normal_names_starting_with_lu(self):
        """'陆' 姓的正常姓名仍能识别 — 大写金额免疫不应误伤."""
        # '陆伟强' 中的 '伟' '强' 不在 AMOUNT_CHARS,不会触发豁免
        names = self.recognizer.extract("原告陆伟强在庭上陈述。")
        self.assertIn("陆伟强", names,
            "姓 '陆' 的真名 '陆伟强' 必须仍能识别 (非大写金额字)")

    def test_amount_immunity_does_not_block_zhou_qiang(self):
        """常规姓名回归保护."""
        names = self.recognizer.extract("原告：周强，男，汉族。")
        self.assertIn("周强", names)

    def test_amount_immunity_does_not_block_ding_ming_yi(self):
        """'丁明义' (含 '丁' 姓但非金额字) 必须仍能识别 — 避免被金额免疫误伤.

        注: '丁明一' 这种名字因 jieba 会把 '一' 单独切走 (m 数字标记),
        不会作为整体 nr token 出现, 故不可作测试用例.
        '明' '义' 均不在 AMOUNT_CHARS, 因此本测试同时验证: 免疫规则不会
        误伤姓氏含 SURNAME 字 ('丁') 但其余字非金额字的真名.
        """
        names = self.recognizer.extract("原告丁明义向本院提出诉讼请求。")
        self.assertIn("丁明义", names)

    def test_amount_with_simplified_yuan_unit(self):
        """'圆' (简) 与 '元' (繁) 都属于大写金额字表."""
        # jieba 可能切成 '壹圆' 或 '壹元' 作为单独 token
        text = "壹圆贰角伍分"
        names = self.recognizer.extract(text)
        # 任一含金额字的 token 都不应被当作人名
        self.assertEqual([n for n in names if any(c in "零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整正负" for c in n)
                          and not any(c in n for c in "赵钱孙李周吴郑王")], [],
            "大写金额字不应被识别为人名")

    def test_amount_only_punctuation_or_empty_no_crash(self):
        """空字符串 / 纯标点不应触发金额免疫误判."""
        names = self.recognizer.extract("")
        self.assertEqual(names, [])
        names2 = self.recognizer.extract("（）：，,。")
        self.assertEqual(names2, [])

    def test_real_amount_with_label_keyword_context(self):
        """'大写:' 关键字 + 大写金额: 整段识别器命中应为空."""
        text = "（大写：壹佰贰拾叁万肆仟伍佰陆拾柒元捌角玖分）"
        names = self.recognizer.extract(text)
        self.assertEqual(names, [],
            f"括号内大写金额不应产生任何假人名, 实得 {names}")


class TestRecognizerLegalDocumentTerms(unittest.TestCase):
    """法律文书高频术语黑名单 — 防 jieba 把 '许可证' 切成 nr 人名.

    设计动机 (v1.1.11 regression):
      - '许' 在 SURNAME_SET 中, jieba 把 '规划许可证' 切成 ['规划', '许可证']
        且 '许可证' 标 nr → 误识别为 '许可证' 人名
      - 注入脱敏规则后 (mask_keep_prefix=1, mask_char='*'), 输出 '规划许**'
      - 法律术语 '许可证' 不可能作人名, 必须识别器层面兜底
    修复: EXCLUDE_WORDS 新增 '法律文书高频术语' 子类, 凡是 token 文本恰好
    等于这些术语, 一律跳过. 与 SURNAME_SET 触发的同源问题统一治理.
    """

    def setUp(self) -> None:
        self.recognizer = ChineseNameRecognizer()

    def test_xuke_zheng_not_recognized(self):
        """核心 regression — 抵账协议场景."""
        text = (
            "丙方系四川省宜宾市金*湖镇阳*逸景小区（以下简称 \"抵债小区\"）的"
            "合法开发商，已依法取得该小区的《国有土地使用证》《建设用地规划许可证》"
            "《建设工程规划许可证》《建筑工程施工许可证》《商品房预售许可证》"
            "（或《商品房现售备案证明》）等全部合法开发、销售手续"
        )
        names = self.recognizer.extract(text)
        self.assertNotIn("许可证", names,
            "法律术语 '许可证' 不应被 jieba 启发式误识别为人名")
        # 此外, 整个文本不应产生任何姓 '许' 的假人名
        self.assertEqual([n for n in names if n.startswith("许")], [])

    def test_xuke_zheng_standalone(self):
        """单独 '许可证' 也不应被识别."""
        names = self.recognizer.extract("建设用地规划许可证")
        self.assertEqual(names, [],
            f"独立 '许可证' 不应产生人名, 实得 {names}")

    def test_normal_names_still_recognized(self):
        """加法律术语黑名单不应影响正常姓名识别."""
        names = self.recognizer.extract("原告：周强，男，汉族。")
        self.assertIn("周强", names)

    def test_zheng_ren_zhang_san_recognizes_only_name(self):
        """'证人张三' 场景: '证人' 是称谓 (jieba 标 n 不受影响),
        '张三' 仍应被识别."""
        names = self.recognizer.extract("证人张三在庭上作证。")
        self.assertIn("张三", names)
        # '证人' 不是人名,不应被识别
        self.assertNotIn("证人", names)

    def test_other_high_freq_certificate_terms_also_immune(self):
        """覆盖同源词: '登记证' '所有权证' '抵押证' — 即使未来 jieba
        行为变化也应免疫. 当前 jieba 把这些切成 n, 但加黑名单确保稳态."""
        # 这里用 extract_person_names, 不传 whitelist — 默认行为
        # 我们断言: 这些 token 都不应被识别为人名
        for term in ("许可证", "登记证", "所有权证", "抵押证"):
            with self.subTest(term=term):
                names = self.recognizer.extract(f"持有{term}")
                self.assertNotIn(term, names,
                    f"法律术语 '{term}' 不应被识别为人名, 实得 {names}")


if __name__ == "__main__":
    unittest.main()
