# -*- coding: utf-8 -*-
"""override 持久化与清理测试."""
import json
import os
import tempfile
import shutil
import unittest

from secureredact.redaction.override_store import HitOverrideStore
from secureredact.redaction.hit_ref import HitRef


class OverridesPersistenceTest(unittest.TestCase):

    def setUp(self):
        HitOverrideStore.reset_singleton()
        self.tmpdir = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmpdir, "config.json")

    def tearDown(self):
        HitOverrideStore.reset_singleton()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_load_round_trip(self):
        """dump_permanent -> 写 config.json -> 重新 load_permanent -> is_ignored."""
        s = HitOverrideStore.instance()
        ref = HitRef("a1b2c3d4", "p_1", 0, 2, "周强", "jieba")
        s.ignore(ref, scope="permanent")
        items = s.dump_permanent()
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump({"redaction": {"overrides": {"permanent": items}}}, f)
        with open(self.cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        s2 = HitOverrideStore.instance()
        s2.load_permanent(data["redaction"]["overrides"]["permanent"])
        self.assertTrue(s2.is_ignored(ref))

    def test_clean_stale_removes_only_old(self):
        """clean_stale_permanent 仅保留 cutoff 之内的 promoted_at。"""
        from secureredact.redaction.override_store import clean_stale_permanent
        items = [
            {"hit_id": "a|p|0|2|jieba", "doc_hash": "a", "location": "p",
             "start": 0, "end": 2, "text": "x", "source": "jieba",
             "action": "ignore", "scope": "permanent",
             "promoted_at": "2020-01-01T00:00:00"},  # 老
            {"hit_id": "b|p|0|2|jieba", "doc_hash": "b", "location": "p",
             "start": 0, "end": 2, "text": "y", "source": "jieba",
             "action": "ignore", "scope": "permanent",
             "promoted_at": "2026-08-17T00:00:00"},  # 新
        ]
        cleaned = clean_stale_permanent(items, max_age_days=30, today="2026-08-17")
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["hit_id"], "b|p|0|2|jieba")

    def test_replace_permanent_removes_stale(self):
        """replace_permanent 应移除所有不存在的 permanent 条目."""
        s = HitOverrideStore.instance()
        # 加两个 permanent override
        ref_old = HitRef("a", "p", 0, 2, "old", "jieba")
        ref_new = HitRef("b", "p", 0, 2, "new", "ocr")
        s.ignore(ref_old, scope="permanent")
        s.ignore(ref_new, scope="permanent")
        # replace 只传 new
        new_items = s.dump_permanent()
        new_items = [it for it in new_items if it["doc_hash"] == "b"]
        s.replace_permanent(new_items)
        # ref_old 应不再被 ignored,ref_new 应仍被 ignored
        self.assertFalse(s.is_ignored(ref_old))
        self.assertTrue(s.is_ignored(ref_new))


if __name__ == "__main__":
    unittest.main()