# -*- coding: utf-8 -*-
"""WordWorker match dict 加 source 字段测试.

Wave 3 Task 5:
- jieba 启发式识别后的匹配,match dict 应携带 source='jieba'
- rule 路径应携带 source='rule'
- custom_keywords 路径应携带 source='rule' (与 PDF ocr 不同;
  WordWorker 把 custom_keywords 也视为规则类,不区分 ocr/source)
"""
import unittest


class WordWorkerSourceTest(unittest.TestCase):

    def test_match_dict_has_source_field(self):
        """jieba 启发式识别 (enable_name_recognition=True) 命中后,
        word_data[key]['ocr'] 中的 dict 应携带 source='jieba'."""
        from secureredact.workers.word_worker import WordWorker

        # 构造 fake word_doc
        class FakePara:
            text = "周强是作者"
            def __init__(self, t): self.text = t
        class FakeDoc:
            paragraphs = [FakePara("周强是作者")]
            tables = []

        doc = FakeDoc()
        word_data = {"paragraph_0": {"text": "周强是作者", "ocr": [], "manual": []}}
        worker = WordWorker(
            word_doc=doc, word_data=word_data,
            rules=[], custom_keywords="",
            replacement_text="*", default_rules={},
            enable_name_recognition=True,
        )
        worker.run()
        matches = word_data["paragraph_0"]["ocr"]
        self.assertGreater(len(matches), 0,
            "jieba 路径至少应产出 1 条匹配")
        self.assertIn("source", matches[0],
            "match dict 必须有 source 字段")
        self.assertEqual(matches[0]["source"], "jieba")
        self.assertEqual(matches[0]["text"], "周强")


if __name__ == "__main__":
    unittest.main()
