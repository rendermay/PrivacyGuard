# -*- coding: utf-8 -*-
"""HitOverrideStore 单例逻辑测试."""
import unittest
from secureredact.redaction.override_store import HitOverrideStore
from secureredact.redaction.hit_ref import HitRef, Override


def _ref(text="周强", source="jieba", location="p_3", start=10, end=12, doc_hash="a1b2c3d4"):
    return HitRef(
        doc_hash=doc_hash,
        location=location,
        start=start,
        end=end,
        text=text,
        source=source,
    )


class HitOverrideStoreTest(unittest.TestCase):

    def setUp(self):
        HitOverrideStore.reset_singleton()

    def tearDown(self):
        HitOverrideStore.reset_singleton()

    def test_singleton(self):
        a = HitOverrideStore.instance()
        b = HitOverrideStore.instance()
        self.assertIs(a, b)

    def test_ignore_session_marks_ignored(self):
        s = HitOverrideStore.instance()
        ref = _ref()
        s.ignore(ref, scope="session")
        self.assertTrue(s.is_ignored(ref))
        self.assertFalse(s.is_confirmed(ref))

    def test_ignore_and_confirm_mutex_latter_wins(self):
        s = HitOverrideStore.instance()
        ref = _ref()
        s.ignore(ref, scope="session")
        s.confirm(ref, scope="session")
        self.assertFalse(s.is_ignored(ref))
        self.assertTrue(s.is_confirmed(ref))

    def test_revert_removes_override(self):
        s = HitOverrideStore.instance()
        ref = _ref()
        s.ignore(ref, scope="session")
        s.revert(ref.hit_id)
        self.assertFalse(s.is_ignored(ref))

    def test_promote_session_to_permanent(self):
        s = HitOverrideStore.instance()
        ref = _ref()
        s.ignore(ref, scope="session")
        s.promote(ref.hit_id)
        # 仍应被忽略
        self.assertTrue(s.is_ignored(ref))
        # 检查 permanent 存在
        perm = [o for o in s.iter_overrides(scope="permanent") if o.ref.hit_id == ref.hit_id]
        self.assertEqual(len(perm), 1)
        self.assertEqual(perm[0].scope, "permanent")
        self.assertIsNotNone(perm[0].promoted_at)

    def test_filtered_hits_removes_ignored(self):
        s = HitOverrideStore.instance()
        r1 = _ref(text="周强", start=10, end=12)
        r2 = _ref(text="李四", start=20, end=22)
        s.ignore(r1, scope="session")
        # hit dict 必须带 start/end 才能命中 ignored ref
        hits = [
            {"rect": None, "source": "jieba", "text": "周强", "rule_name": "姓名", "start": 10, "end": 12},
            {"rect": None, "source": "jieba", "text": "李四", "rule_name": "姓名", "start": 20, "end": 22},
        ]
        kept = s.filtered_hits(hits, location="p_3", doc_hash="a1b2c3d4")
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["text"], "李四")

    def test_filtered_hits_empty_store_keeps_all(self):
        s = HitOverrideStore.instance()
        hits = [
            {"rect": None, "source": "ocr", "text": "x", "rule_name": "r"},
            {"rect": None, "source": "ocr", "text": "y", "rule_name": "r"},
        ]
        kept = s.filtered_hits(hits, location="p_1", doc_hash="any")
        self.assertEqual(len(kept), 2)

    def test_filtered_hits_keeps_manual(self):
        s = HitOverrideStore.instance()
        r1 = _ref(text="周强", start=10, end=12)
        s.ignore(r1, scope="session")
        hits = [
            {"rect": None, "source": "manual", "text": "周强", "rule_name": "manual"},
        ]
        kept = s.filtered_hits(hits, location="p_3", doc_hash="a1b2c3d4")
        self.assertEqual(len(kept), 1)

    def test_permanent_persists_via_dict(self):
        s = HitOverrideStore.instance()
        ref = _ref()
        s.ignore(ref, scope="permanent")
        dump = s.dump_permanent()
        self.assertEqual(len(dump), 1)
        self.assertEqual(dump[0]["action"], "ignore")
        self.assertEqual(dump[0]["scope"], "permanent")
        self.assertEqual(dump[0]["hit_id"], ref.hit_id)
        self.assertEqual(dump[0]["text"], "周强")

    def test_load_permanent_restores_ignored(self):
        s = HitOverrideStore.instance()
        items = [{
            "hit_id": "a1b2c3d4|p_3|10|12|jieba",
            "doc_hash": "a1b2c3d4",
            "location": "p_3",
            "start": 10,
            "end": 12,
            "text": "周强",
            "source": "jieba",
            "action": "ignore",
            "scope": "permanent",
            "promoted_at": "2026-08-17T00:00:00",
        }]
        s.load_permanent(items)
        self.assertTrue(s.is_ignored(_ref()))
        self.assertEqual(len(list(s.iter_overrides(scope="permanent"))), 1)

    def test_load_permanent_handles_corrupt(self):
        s = HitOverrideStore.instance()
        # 不抛异常,仅 warn 日志
        s.load_permanent([{"bad": "data"}])
        self.assertEqual(len(list(s.iter_overrides(scope="permanent"))), 0)


if __name__ == "__main__":
    unittest.main()