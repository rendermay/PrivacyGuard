# -*- coding: utf-8 -*-
"""HitRef 不可变标识与 hit_id 稳定性测试."""
import unittest
from privacyguard.redaction.hit_ref import HitRef


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

    def test_hit_id_differs_on_text_change(self):
        a = HitRef("a1b2c3d4", "p_3", 10, 12, "周强", "jieba")
        b = HitRef("a1b2c3d4", "p_3", 10, 12, "周强2", "jieba")
        self.assertNotEqual(a.hit_id, b.hit_id)

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


if __name__ == "__main__":
    unittest.main()