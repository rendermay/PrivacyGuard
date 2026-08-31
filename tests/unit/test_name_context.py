# -*- coding: utf-8 -*-
"""
姓名上下文匹配器单元测试 (v1.1.12 方案 B).

覆盖:
- 强标签模式 (原告:周强 / 法定代表人：曹炳志)
- 强前缀词 (经理张磊 / 审判员张三)
- 强后缀词 (周强先生 / 李四女士)
- 负例: 裸 nr (本院认为张三) 不应被识别为有上下文
- 边界: 空输入 / 空 candidates / 多处上下文 / 重名
- 集成: 上下文过滤与识别器主流程对接
"""
import unittest

from secureredact.pii.name_context import (
    STRONG_PREFIX_TOKENS,
    STRONG_SUFFIX_TOKENS,
    filter_names_by_context,
)


class TestLabelPatternMatching(unittest.TestCase):
    """强标签模式: 角色词 + (冒号/全角冒号) + 名字."""

    def test_fullwidth_colon(self):
        names = filter_names_by_context(
            "原告：周强，男，汉族。",
            ["周强"],
        )
        self.assertEqual(names, ["周强"])

    def test_halfwidth_colon(self):
        names = filter_names_by_context(
            "原告:周强,男,汉族。",
            ["周强"],
        )
        self.assertEqual(names, ["周强"])

    def test_legal_rep_label(self):
        names = filter_names_by_context(
            "法定代表人：曹炳志",
            ["曹炳志"],
        )
        self.assertEqual(names, ["曹炳志"])

    def test_witness_label(self):
        names = filter_names_by_context(
            "证人：张三在庭上作证。",
            ["张三"],
        )
        self.assertEqual(names, ["张三"])

    def test_label_candidates_not_matched_filtered_out(self):
        """'许可证' 不在标签模式触发的位置上 → 应被过滤掉."""
        names = filter_names_by_context(
            "已依法取得《建设用地规划许可证》",
            ["许可证"],
        )
        self.assertEqual(names, [],
            "强标签不应误命中 '许可证' (因前面不是角色词)")


class TestPrefixContextMatching(unittest.TestCase):
    """强前缀词: 候选名前面紧邻角色/称谓."""

    def test_manager_prefix(self):
        names = filter_names_by_context(
            "经理张磊负责审批。",
            ["张磊"],
        )
        self.assertEqual(names, ["张磊"])

    def test_prosecutor_prefix(self):
        names = filter_names_by_context(
            "检察官李四提起公诉。",
            ["李四"],
        )
        self.assertEqual(names, ["李四"])

    def test_judge_prefix(self):
        names = filter_names_by_context(
            "审判员王五主持庭审。",
            ["王五"],
        )
        self.assertEqual(names, ["王五"])

    def test_prefix_with_whitespace_padding(self):
        names = filter_names_by_context(
            "经理  张磊负责审批。",  # 经理和张磊之间有 2 个空格
            ["张磊"],
        )
        self.assertEqual(names, ["张磊"])

    def test_prefix_not_in_other_position(self):
        """'原告认为' 是程序词, 不是 '认为' 的强前缀 → '原告' 自身不应被识别."""
        # 这里 candidates 是 "原告", 但没有上下文 → 过滤
        names = filter_names_by_context(
            "原告认为张三的诉求成立。",
            ["原告"],
        )
        # "原告" 自身在 EXCLUDE_WORDS 中, 但 filter_names_by_context
    # 不感知黑名单 — 仅看上下文. 但 "原告" 前面也没有任何强前缀
    # → 没有上下文 → 应被过滤掉.
        self.assertEqual(names, [])


class TestSuffixContextMatching(unittest.TestCase):
    """强后缀词: 候选名后面紧邻称谓/头衔."""

    def test_mister_suffix(self):
        names = filter_names_by_context(
            "起诉人：李四先生",
            ["李四"],
        )
        self.assertEqual(names, ["李四"])

    def test_madam_suffix(self):
        names = filter_names_by_context(
            "原告王芳女士提出诉讼。",
            ["王芳"],
        )
        self.assertEqual(names, ["王芳"])

    def test_comrade_suffix(self):
        names = filter_names_by_context(
            "证人赵刚同志作证完毕。",
            ["赵刚"],
        )
        self.assertEqual(names, ["赵刚"])

    def test_suffix_must_be_immediate(self):
        """'张三' 与 '先生' 之间夹了其他汉字 → 上下文失效."""
        names = filter_names_by_context(
            "张三在公司任职先生。",  # "任职先生" — '张三' 与 '先生' 不紧邻
            ["张三"],
        )
        self.assertEqual(names, [],
            "'先生' 与 '张三' 间夹汉字应不算后缀上下文")


class TestNegativeCases(unittest.TestCase):
    """反例: 不应有上下文的候选被过滤掉."""

    def test_bare_nr_without_context_filtered(self):
        """'本院认为张三的诉求成立' — '张三' 无强上下文 → 应过滤."""
        names = filter_names_by_context(
            "本院认为张三的诉求成立。",
            ["张三"],
        )
        self.assertEqual(names, [],
            "裸 nr 文本无强上下文, '张三' 应被过滤掉")

    def test_zhu_zuo_quan_ren_filtered(self):
        """'著作权人周强在贵州省版权局完成作品登记。'
        — '著作权人' 不是强前缀, '周强' 后面无强后缀, 也无强标签
        → 应被过滤掉."""
        names = filter_names_by_context(
            "著作权人周强在贵州省版权局完成作品登记。",
            ["周强"],
        )
        self.assertEqual(names, [],
            "'著作权人' 非强前缀, '周强' 不应被识别为有上下文")

    def test_amount_fragment_filtered(self):
        """'陆佰柒' 即使被 jieba 误识为人名, 上下文匹配器也应过滤掉."""
        names = filter_names_by_context(
            "本息合计 6710123.33 元（大写：陆佰柒拾壹万零壹佰贰拾叁元叁角叁分）",
            ["陆佰柒"],
        )
        self.assertEqual(names, [])

    def test_xuke_zheng_filtered(self):
        """'许可证' 无上下文, 应被过滤."""
        names = filter_names_by_context(
            "已依法取得《建设用地规划许可证》",
            ["许可证"],
        )
        self.assertEqual(names, [])

    def test_ding_fang_jing_filtered(self):
        """'丁方经' 是合同角色词粘连, 无上下文, 应被过滤."""
        names = filter_names_by_context(
            "现甲、乙、丙、丁方经平等自愿、协商一致。",
            ["丁方经"],
        )
        self.assertEqual(names, [])


class TestEdgeCases(unittest.TestCase):
    """边界条件."""

    def test_empty_text(self):
        names = filter_names_by_context("", ["周强"])
        self.assertEqual(names, [])

    def test_none_text(self):
        names = filter_names_by_context(None, ["周强"])  # type: ignore[arg-type]
        self.assertEqual(names, [])

    def test_empty_candidates(self):
        names = filter_names_by_context("原告：周强", [])
        self.assertEqual(names, [])

    def test_none_candidates(self):
        names = filter_names_by_context("原告：周强", None)  # type: ignore[arg-type]
        self.assertEqual(names, [])

    def test_dedup_preserves_order(self):
        """同一名字多次出现 → 仅返回一次, 顺序保持."""
        names = filter_names_by_context(
            "原告：周强。被告：周强作为证人。",  # 周强 出现两次
            ["周强", "张三", "周强"],  # candidates 里也重复
        )
        self.assertEqual(names, ["周强"])

    def test_multi_match_first_kept(self):
        """多个候选, 有上下文的按出现顺序保留."""
        names = filter_names_by_context(
            "原告：周强。经理张三。被告：李四先生",
            ["李四", "周强", "张三", "王五"],
        )
        self.assertEqual(names, ["周强", "张三", "李四"],
            f"有上下文的候选应按 candidates 顺序保留, 实得 {names}")

    def test_non_string_name_in_candidates_skipped(self):
        names = filter_names_by_context(
            "原告：周强",
            [None, "", "周强", 123],  # type: ignore[list-item]
        )
        self.assertEqual(names, ["周强"])


class TestPartyRolePrefix(unittest.TestCase):
    """v1.1.14: 扩展 STRONG_PREFIX_TOKENS — 法律文书高频合同角色词.

    动机: '甲方与xxx、xxx...之间借款合同纠纷' 格式在抵账协议/判决书/
    调解书中极常见;这些并列名单中的姓名属于当事人,理应被识别.
    """

    def test_jia_fang_prefix(self):
        """甲方前缀 + 列举名单.例:'甲方与李秋实、孙毅之间借款合同纠纷一案'."""
        text = (
            "甲方与吉林省甲公司、吉林市乙公司、吉林市丙公司、"
            "李秋实、孙毅、李洪赢、王勇、柏艳波、吕阳、"
            "孙英楠、孙颖之间借款合同纠纷一案。"
        )
        names = filter_names_by_context(
            text,
            ["李秋实", "孙毅", "李洪赢", "王勇", "柏艳波",
             "吕阳", "孙英楠", "孙颖"],
        )
        self.assertEqual(
            names,
            ["李秋实", "孙毅", "李洪赢", "王勇", "柏艳波",
             "吕阳", "孙英楠", "孙颖"],
            f"甲方前缀应识别全部名单中姓名, 实得 {names}",
        )

    def test_yi_fang_prefix(self):
        """乙方前缀: '乙方xxx、xxx...'."""
        text = "乙方张磊、李四共同出资设立丙公司。"
        names = filter_names_by_context(text, ["张磊", "李四"])
        self.assertEqual(names, ["张磊", "李四"])

    def test_bing_fang_prefix(self):
        text = "丙方王五、赵六作为担保人承担责任。"
        names = filter_names_by_context(text, ["王五", "赵六"])
        self.assertEqual(names, ["王五", "赵六"])

    def test_ding_fang_prefix(self):
        """丁方前缀命中, 不受 whitelist 邻接过滤影响.

        注: whitelist 邻接过滤发生在 name_recognizer 层 (filter_names 阶段),
        本测试只验证 context 层能命中 — whitelist 与 prefix 同字 ('丁方') 的
        覆盖交互在 tests/unit/test_name_recognizer.py。
        """
        text = "丁方周强、吴九签署本协议。"
        names = filter_names_by_context(text, ["周强", "吴九"])
        self.assertEqual(names, ["周强", "吴九"])

    def test_jie_kuan_ren_prefix(self):
        text = "借款人孙十、钱十一未按期偿还本金。"
        names = filter_names_by_context(text, ["孙十", "钱十一"])
        self.assertEqual(names, ["孙十", "钱十一"])

    def test_zhai_wu_ren_prefix(self):
        text = "债务人周十二、徐十三合计欠款三百万元。"
        names = filter_names_by_context(text, ["周十二", "徐十三"])
        self.assertEqual(names, ["周十二", "徐十三"])

    def test_zhai_quan_ren_prefix(self):
        text = "债权人郑十四、刘十五依法向本院起诉。"
        names = filter_names_by_context(text, ["郑十四", "刘十五"])
        self.assertEqual(names, ["郑十四", "刘十五"])

    def test_dan_bao_ren_prefix(self):
        text = "保证人陈十六、杨十七对上述债务承担连带责任。"
        names = filter_names_by_context(text, ["陈十六", "杨十七"])
        self.assertEqual(names, ["陈十六", "杨十七"])


class TestExtraPrefixTokensInjection(unittest.TestCase):
    """v1.1.14: extra_prefix_tokens 参数注入 — 接通 config.json 的
    redaction.name_context.extra_tokens 配置项。

    动机: CHANGELOG v1.1.12 引入 extra_tokens 配置,但代码一直没读取;
    通过显式参数注入打通配置-实现链路。
    """

    def test_extra_tokens_recognize_names(self):
        """通过 extra_prefix_tokens 注入 '数据处理者', 应能识别."""
        text = "数据处理者周强在协议中签字确认。"
        names = filter_names_by_context(
            text, ["周强"], extra_prefix_tokens=frozenset({"数据处理者"}),
        )
        self.assertEqual(names, ["周强"])

    def test_extra_tokens_none_falls_back_to_default(self):
        """extra_prefix_tokens=None → 退回到 STRONG_PREFIX_TOKENS 默认集合."""
        text = "原告：周强，男，汉族。"
        names = filter_names_by_context(text, ["周强"], extra_prefix_tokens=None)
        self.assertEqual(names, ["周强"])

    def test_extra_tokens_empty_does_not_break(self):
        """extra_prefix_tokens=空 frozenset → 不报错, 仅依赖默认集合."""
        text = "原告：周强。"
        names = filter_names_by_context(
            text, ["周强"], extra_prefix_tokens=frozenset(),
        )
        self.assertEqual(names, ["周强"])

    def test_extra_tokens_iterable_accepted(self):
        """extra_prefix_tokens 也接受 list/iterable(便于从 config.json 直接传入 list)."""
        text = "数据控制者李四向本院提交证据。"
        names = filter_names_by_context(
            text, ["李四"], extra_prefix_tokens=["数据控制者"],
        )
        self.assertEqual(names, ["李四"])

    def test_extra_tokens_does_not_affect_label_pattern(self):
        """强标签模式 (原告:xxx) 走 _LABEL_PATTERN,与 prefix 无关; extra_tokens
        不应改变该路径行为."""
        text = "许可证：周强持有此证。"
        # 即使注入 '数据处理者' 等, '许可证：' 不是强标签角色词
        names = filter_names_by_context(
            text, ["周强"],
            extra_prefix_tokens=frozenset({"数据处理者", "数据控制者"}),
        )
        self.assertEqual(names, [],
            "强标签模式仅识别 role_token + 冒号, 不被 extra_tokens 干扰")


class TestWordSets(unittest.TestCase):
    """词表自身完整性保护 (regression)."""

    def test_strong_prefix_is_nonempty(self):
        self.assertGreater(len(STRONG_PREFIX_TOKENS), 10)

    def test_strong_suffix_is_nonempty(self):
        self.assertGreater(len(STRONG_SUFFIX_TOKENS), 5)

    def test_strong_prefix_and_suffix_overlap_allowed(self):
        """'经理'/'主任'/'教授' 等既能前缀也能后缀, 重叠是合理的.

        设计动机: 中文 '经理张磊' 与 '张磊经理' 都合法, 不应强行 disjoint.
        仅要求重叠不会破坏匹配 (双向上下文都会被识别).
        """
        # '经理' 在前后缀都存在时, 两个方向都能识别
        names = filter_names_by_context(
            "经理张磊", ["张磊"],  # 前缀方向
        )
        self.assertEqual(names, ["张磊"])
        names2 = filter_names_by_context(
            "张磊经理", ["张磊"],  # 后缀方向
        )
        self.assertEqual(names2, ["张磊"])


if __name__ == "__main__":
    unittest.main()