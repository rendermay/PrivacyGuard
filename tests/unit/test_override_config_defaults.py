# -*- coding: utf-8 -*-
"""config.json 中 override 相关键的默认与持久化测试."""
import json
import os
import tempfile
import unittest


class OverrideConfigDefaultsTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "config.json")
        # 仅写入其他键,验证默认补齐
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"redaction": {"enable_name_recognition": False}}, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_defaults_present_when_missing(self):
        # import 触发 SimpleConfig 加载
        from main import SimpleConfig  # SimpleConfig 实际位于 main.py:98
        cfg = SimpleConfig(self.path)
        cfg.load()
        self.assertIn("overrides", cfg.get("redaction"))
        self.assertEqual(cfg.get("redaction.overrides.permanent"), [])
        self.assertTrue(cfg.get("redaction.enable_hit_override"))

    def test_round_trip_preserves_permanent(self):
        from main import SimpleConfig
        cfg = SimpleConfig(self.path)
        cfg.load()
        cfg.set("redaction.overrides.permanent", [
            {"hit_id": "abc|p_1|0|2|jieba", "action": "ignore", "scope": "permanent"}
        ])
        cfg.save()
        cfg2 = SimpleConfig(self.path)
        cfg2.load()
        self.assertEqual(len(cfg2.get("redaction.overrides.permanent")), 1)


if __name__ == "__main__":
    unittest.main()