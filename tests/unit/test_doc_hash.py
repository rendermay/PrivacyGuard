# -*- coding: utf-8 -*-
"""doc_hash 计算与缓存测试."""
import os
import tempfile
import unittest
from secureredact.redaction.doc_hash import compute_doc_hash


class DocHashTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "demo.txt")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("hello")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_returns_8_char_hex(self):
        h = compute_doc_hash(self.path)
        self.assertEqual(len(h), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_stable_for_same_file(self):
        a = compute_doc_hash(self.path)
        b = compute_doc_hash(self.path)
        self.assertEqual(a, b)

    def test_changes_when_content_changes(self):
        # 用不同 size 的内容触发 doc_hash 变化(避免依赖 mtime 精度,WSL ext2 mtime 不可靠)
        a = compute_doc_hash(self.path)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("world!!")  # 6 bytes 与初始 "hello" 5 bytes size 不同
        # 显式 sleep 保证 mtime 一定更新(跨平台兜底)
        import time
        time.sleep(0.05)
        b = compute_doc_hash(self.path)
        self.assertNotEqual(a, b)

    def test_missing_file_raises(self):
        with self.assertRaises(OSError):
            compute_doc_hash(os.path.join(self.tmpdir, "missing.txt"))


if __name__ == "__main__":
    unittest.main()