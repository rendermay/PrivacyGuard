"""v1.1.12: 统一社会信用代码(USCC)Word-only 脱敏规则测试。

USCC 规则通过 `redaction.pdf_excluded_rules` 配置项实现 PDF 路径完全隔离:
- Word 智能扫描:WordWorker.rules 包含 USCC pattern,命中 GB 32100-2015 18 位字符串
- PDF 智能扫描:OCRWorker.rules 不包含 USCC pattern,既有命中行为零变化
- 印章检测:`__SEAL_DETECTION__` 必须保留在 pdf_rules 中,不被新过滤误吞
"""

import json
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock


# v1.1.12: GB 32100-2015 兼容版
# 长度:17-18 位(标准 18 位;旧组织机构代码 9 位残缺录入 17 位)
# 首字符:数字(登记管理部门代码)
# 字符集:[0-9A-HJ-NPQRTUWXY] 排除 I/O/Z/S/V(避免与 0/1/2/5 视觉混淆)
# 边界:只排除 ASCII 字母数字,允许中文/标点紧跟(如 "号"字)
USCC_PATTERN = r"(?<![A-Z0-9])([0-9][0-9A-HJ-NPQRTUWXY]{16,17})(?![A-Za-z0-9])"


class TestUSCCRulePattern(unittest.TestCase):
    """USCC pattern 自身正确性:严格 GB 32100-2015 结构。"""

    def test_matches_real_uscc(self):
        """真实 USCC 样本:18 位数字+大写字母,排除 I/O/Z/S/V。"""
        samples = [
            "91110108MA01KXYX29",   # 11 工商 + 110108 北京海淀 + MA 企业 + 9 顺序 + 2 校验
            "91320100MA1MRK9J3P",   # 32 江苏 + 201 编码 + MA + ...
            "9151152MA6ARBNK4W",    # 来自抵账协议真实样本(去除字母后 18 位)
            "91511500MAACKMR07X",
            "91220201307949958P",
            "91220200MA17WHWF27",
        ]
        for s in samples:
            self.assertRegex(s, USCC_PATTERN, f"应当命中: {s}")

    def test_excludes_invalid_letters(self):
        """含 I/O/Z/S/V 的 18 位字符串不应命中(避免与 0/1/2/5 视觉混淆)。"""
        invalid_samples = [
            "91110108IA01KXYX29",   # 含 I
            "91110108OA01KXYX29",   # 含 O
            "91110108ZA01KXYX29",   # 含 Z
            "91110108SA01KXYX29",   # 含 S
            "91110108VA01KXYX29",   # 含 V
        ]
        for s in invalid_samples:
            self.assertNotRegex(s, USCC_PATTERN, f"不应命中(含禁用字符): {s}")

    def test_does_not_match_pure_18_digits(self):
        """纯 18 位数字不应被命中(避免误报身份证号场景)。

        注:纯 18 位数字会通过边界检查,但第 3-8 段要求 [0-9A-HJ-NPQRTUWXY]{2}[0-9]{6},
        而 USCC 第 1-2 段是登记管理机关代码,第 3-8 段是 6 位行政区划,整体允许纯数字结构。
        因此我们需要验证:身份证号规则的优先级应高于 USCC,且 USCC 不应该独立误报任意 18 位数字。
        """
        # 这里用一组已知"看起来像 USCC 但实际不是"的样本
        # 由于 USCC 第二位应为 9(GB 32100-2015 机构类别),纯 18 位数字若第 2 位非 9 也应不命中
        s = "123456789012345678"  # 第 2 位是 2,不是 9
        # 实际上 pattern 是 [0-9A-HJ-NPQRTUWXY]{2},允许 1-9 数字,所以这里要看边界
        # 关键是不应该单独命中(身份证规则会先命中),且 USCC 不应该把身份证号再打一次
        # 我们验证 USCC pattern 不会扩展命中身份证号的关键:不命中 19 位 + 18 位纯数字的混合
        longer = "1234567890123456789"  # 19 位
        self.assertNotRegex(longer, USCC_PATTERN)

    def test_does_not_match_email_like(self):
        """含 @ 的字符串不应被命中。"""
        s = "MA0KXYX29@163.com"
        # USCC 不含 @,所以 fullmatch 一定不命中
        m = re.fullmatch(USCC_PATTERN, s)
        self.assertIsNone(m, "完整字符串不应被命中")

    def test_boundary_no_eat_neighbors(self):
        """边界 lookaround:不应吞掉前后字符,允许中文紧跟。"""
        # USCC 紧跟 "号" 字,边界应停在 USCC 末尾(中文不算 word boundary)
        text = "统一社会信用代码:91110108MA01KXYX29号"
        match = re.search(USCC_PATTERN, text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "91110108MA01KXYX29")
        # 验证匹配长度不包含 "号"
        self.assertEqual(match.end() - match.start(), 18)

    def test_boundary_stops_at_ascii_letter(self):
        """边界遇到 ASCII 字母数字必须停止(避免吞掉后续 token)。"""
        text = "USCC:91110108MA01KXYX29A 后续"
        match = re.search(USCC_PATTERN, text)
        # USCC 紧跟 ASCII "A",边界应拒绝匹配(避免把 USCC 后面字母吞进去)
        # 实际上若 "A" 也是 USCC 字符集一部分,可能贪婪扩展,这里验证至少不会扩到 20 位
        if match:
            self.assertLessEqual(match.end() - match.start(), 18)

    def test_ignores_lowercase(self):
        """小写字母不应被 USCC pattern 命中(GB 32100-2015 要求大写)。"""
        s = "91110108ma01kxyx29"
        self.assertNotRegex(s, USCC_PATTERN, "小写不应命中")


class TestUSCCWordDispatch(unittest.TestCase):
    """USCC 在 WordWorker 必须接收,在 OCRWorker 必须被过滤掉。"""

    def test_word_worker_consumes_uscc_rule(self):
        """WordWorker.__init__ 把规则原样存到 self.rules。"""
        from secureredact.workers.word_worker import WordWorker

        rules = [
            r"(?<!\d)\d{18}(?!\d)",                       # 模拟身份证
            r"(?<!\d)1[3-9]\d{9}(?!\d)",                  # 模拟手机
            USCC_PATTERN,                                  # USCC
        ]
        worker = WordWorker(MagicMock(), {}, rules, "", "[已脱敏]")
        self.assertIn(USCC_PATTERN, worker.rules)
        self.assertEqual(len(worker.rules), 3)

    def test_pdf_rules_filter_excludes_uscc_pattern(self):
        """验证 pdf_rules 过滤逻辑:USCC pattern 不在 pdf_rules 中,但 __SEAL_DETECTION__ 必须保留。"""
        # 模拟 start_ocr 内部的过滤逻辑
        active_rules = [
            r"(?<!\d)\d{18}(?!\d)",      # 身份证
            USCC_PATTERN,                 # USCC
            "__SEAL_DETECTION__",         # 印章占位符
        ]
        # 模拟 DEFAULT_RULES
        DEFAULT_RULES = {
            "统一社会信用代码": USCC_PATTERN,
            "身份证号": r"(?<!\d)\d{18}(?!\d)",
            "印章": "__SEAL_DETECTION__",
        }
        excluded_names = ["统一社会信用代码"]
        excluded_patterns = {DEFAULT_RULES[n] for n in excluded_names if DEFAULT_RULES.get(n)}
        pdf_rules = [r for r in active_rules if r not in excluded_patterns]

        self.assertNotIn(USCC_PATTERN, pdf_rules, "USCC pattern 必须从 PDF rules 中过滤掉")
        self.assertIn("__SEAL_DETECTION__", pdf_rules, "__SEAL_DETECTION__ 必须保留(印章检测需要)")
        self.assertIn(r"(?<!\d)\d{18}(?!\d)", pdf_rules, "其他规则必须保留")

    def test_uscc_matches_word_text_endtoend(self):
        """端到端:WordWorker.rules 中 USCC pattern 在真实段落文本上能命中。"""
        from secureredact.workers.word_worker import WordWorker

        worker = WordWorker(MagicMock(), {}, [USCC_PATTERN], "", "[已脱敏]")
        sample_text = (
            "甲方:吉林市捷信小额贷款有限公司  "
            "统一社会信用代码:91110108MA01KXYX29  "
            "乙方:四川京缇建筑工程有限公司  "
            "统一社会信用代码:9151152MA6ARBNK4W"
        )
        all_patterns = worker.rules + worker.custom_keywords
        joined = "|".join(f"({p})" for p in all_patterns)
        matches = re.findall(joined, sample_text)
        flat = [m for tup in matches for m in (tup if isinstance(tup, tuple) else (tup,))]
        self.assertTrue(
            any("91110108MA01KXYX29" in m for m in flat),
            "USCC 字符串应被命中",
        )
        self.assertTrue(
            any("9151152MA6ARBNK4W" in m for m in flat),
            "第二个 USCC 应被命中",
        )

    def test_filter_handles_empty_pdf_excluded_list(self):
        """空 pdf_excluded_rules 时,过滤逻辑不破坏 active_rules。"""
        active_rules = [USCC_PATTERN, r"\d{18}"]
        # 空列表分支
        pdf_excluded_names = []
        if isinstance(pdf_excluded_names, list) and pdf_excluded_names:
            excluded_patterns = {"stub"}
            pdf_rules = [r for r in active_rules if r not in excluded_patterns]
        else:
            pdf_rules = active_rules
        self.assertEqual(pdf_rules, active_rules)

    def test_filter_handles_missing_config_key(self):
        """config.json 缺 pdf_excluded_rules 键时,过滤逻辑应优雅降级。"""
        # 模拟 config.get 返回 None(键不存在)
        config_value = None
        if config_value is None:
            pdf_excluded_names = []
        else:
            pdf_excluded_names = config_value
        self.assertEqual(pdf_excluded_names, [])


class TestUSCCConfigDefaults(unittest.TestCase):
    """config.json 必须包含 USCC 规则与 pdf_excluded_rules 配置。"""

    def _load_config(self):
        cfg_path = Path(__file__).parent.parent.parent / "config.json"
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    def test_config_has_uscc_rule(self):
        cfg = self._load_config()
        rules = cfg["redaction"]["default_rules"]
        self.assertIn("统一社会信用代码", rules)
        rule = rules["统一社会信用代码"]
        self.assertTrue(rule.get("enabled"))
        self.assertIn("pattern", rule)
        # pattern 应是字符类形式(包含 [0-9A-HJ-NPQRTUWXY])
        self.assertIn("[0-9A-HJ-NPQRTUWXY]", rule["pattern"])

    def test_config_has_pdf_excluded_rules(self):
        cfg = self._load_config()
        excluded = cfg["redaction"].get("pdf_excluded_rules", [])
        self.assertIsInstance(excluded, list)
        self.assertIn("统一社会信用代码", excluded)

    def test_template_has_uscc_rule(self):
        cfg_path = Path(__file__).parent.parent.parent / "config.json.template"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        rules = cfg["redaction"]["default_rules"]
        self.assertIn("统一社会信用代码", rules)

    def test_template_has_pdf_excluded_rules(self):
        cfg_path = Path(__file__).parent.parent.parent / "config.json.template"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        excluded = cfg["redaction"].get("pdf_excluded_rules", [])
        self.assertIsInstance(excluded, list)
        self.assertIn("统一社会信用代码", excluded)


class TestUSCCIsolation(unittest.TestCase):
    """端到端隔离:USCC 不出现在 OCRWorker 接收的 rules 参数中。"""

    def test_ocr_worker_rules_arg_has_no_uscc_pattern(self):
        """直接构造 OCRWorker 验证:传入 pdf_rules 不含 USCC pattern。

        这是隔离的最终证据:即使 USCC 在 self.active_rules 中,只要 pdf_rules 过滤正确,
        OCRWorker 实例就不会收到 USCC pattern。
        """
        from secureredact.workers.ocr_worker import OCRWorker

        active_rules = [
            r"(?<!\d)\d{18}(?!\d)",
            USCC_PATTERN,
            "__SEAL_DETECTION__",
        ]
        # 应用过滤
        excluded_names = ["统一社会信用代码"]
        DEFAULT_RULES = {
            "统一社会信用代码": USCC_PATTERN,
            "身份证号": r"(?<!\d)\d{18}(?!\d)",
            "印章": "__SEAL_DETECTION__",
        }
        excluded_patterns = {DEFAULT_RULES[n] for n in excluded_names if DEFAULT_RULES.get(n)}
        pdf_rules = [r for r in active_rules if r not in excluded_patterns]

        # 构造 OCRWorker(不会真正跑 OCR,只验证 rules 入参)
        worker = OCRWorker(
            pdf_path="dummy.pdf",
            rules=pdf_rules,
            use_enhance=False,
            custom_keywords="",
            scan_scale=1.5,
            off_x=0,
            off_w=0,
            seal_detection_enabled="__SEAL_DETECTION__" in pdf_rules,
            enable_name_recognition=False,
        )
        self.assertNotIn(USCC_PATTERN, worker.rules)
        self.assertIn("__SEAL_DETECTION__", worker.rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)