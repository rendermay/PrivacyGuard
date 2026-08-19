# -*- coding: utf-8 -*-
"""
中文姓名启发式识别器单元测试 (X3 方案).

覆盖法律文书高频姓名样例;与 worker/UI 解耦,直接调用识别器 API.
"""
import time
import unittest

from privacyguard.pii.name_recognizer import ChineseNameRecognizer, extract_person_names


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

    # ---- 姓氏集合完整性 (regression: v37.x 漏"付") ----

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


if __name__ == "__main__":
    unittest.main()
