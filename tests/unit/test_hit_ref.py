# -*- coding: utf-8 -*-
"""HitRef 不可变标识与 hit_id 稳定性测试."""
import unittest
from secureredact.redaction.hit_ref import HitRef


class HitRefTest(unittest.TestCase):

    def test_hit_id_stable_for_same_input(self):
        ref = HitRef(
            doc_hash="a1b2c3d4",
            location="paragraph_3",
            start=10, end=12,
            text="周强",
            source="jieba",
        )
        self.assertEqual(
            ref.hit_id,
            "a1b2c3d4|paragraph_3|10|12|jieba",
        )
        # 第二次调用仍稳定
        self.assertEqual(ref.hit_id, "a1b2c3d4|paragraph_3|10|12|jieba")

    def test_hitref_differs_on_text_change(self):
        # text 字段不参与 hit_id 计算(用于人眼核对),但参与 dataclass 整体相等性
        a = HitRef("a1b2c3d4", "p_3", 10, 12, "周强", "jieba")
        b = HitRef("a1b2c3d4", "p_3", 10, 12, "周强2", "jieba")
        # hit_id 必须相同(text 不计入)
        self.assertEqual(a.hit_id, b.hit_id)
        # 但 dataclass 整体不相等(text 字段不同)
        self.assertNotEqual(a, b)

    def test_hit_id_differs_on_source_change(self):
        a = HitRef("a1b2c3d4", "p_3", 10, 12, "周强", "jieba")
        b = HitRef("a1b2c3d4", "p_3", 10, 12, "周强", "ocr")
        self.assertNotEqual(a.hit_id, b.hit_id)

    def test_hitref_is_immutable(self):
        ref = HitRef("a", "b", 0, 1, "t", "ocr")
        with self.assertRaises(Exception):
            ref.text = "modified"

    def test_hitref_validates_source(self):
        with self.assertRaises(ValueError):
            HitRef("a", "b", 0, 1, "t", "INVALID_SOURCE")

    def test_hitref_accepts_v37_9_sources(self):
        """v1.1.11: 黑名单 (blacklist) 与人工 (manual) 必须是合法 source.

        历史 bug: VALID_SOURCES 只包含 (rule, ocr, jieba, seal),
        导致 _hit_to_ref 在处理 source='blacklist' 时抛 ValueError,
        try/except 静默吞掉 → 用户右键 ignore 永久提升失败, 永久 override 丢失.
        """
        for src in ("blacklist", "manual"):
            ref = HitRef("a", "b", 0, 1, "t", src)
            self.assertEqual(ref.source, src)


if __name__ == "__main__":
    unittest.main()