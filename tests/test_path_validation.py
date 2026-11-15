#!/usr/bin/env python3
"""路径安全校验单元测试（测试生产实现）。"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from secureredact.utils.security import validate_safe_path


class TestPathValidation(unittest.TestCase):
    def test_windows_backslash_path_allowed_on_windows(self):
        """Windows 平台下反斜杠路径分隔符不应被判为危险字符。

        路径必须落在允许目录内(家目录),否则会先命中"路径不在允许范围内",
        根本走不到分隔符判定 —— 故用真实家目录而非写死的 Windows 用户目录
        (后者在任何机器上都不在允许目录内)。
        """
        with patch("secureredact.utils.security.platform.system", return_value="Windows"):
            docx_path = str(Path.home() / "test.docx")
            ok, msg = validate_safe_path(docx_path, [".doc", ".docx"])
            self.assertTrue(ok, msg)

    def test_windows_backslash_path_rejected_on_non_windows(self):
        with patch("secureredact.utils.security.platform.system", return_value="Darwin"):
            ok, msg = validate_safe_path(r"C:\Users\Admin\test.docx", [".doc", ".docx"])
            self.assertFalse(ok)
            self.assertIn("危险字符", msg)

    def test_shell_metacharacters_rejected(self):
        with patch("secureredact.utils.security.platform.system", return_value="Windows"):
            for bad in [";", "|", "&", "$", "`", ">", "<"]:
                with self.subTest(bad=bad):
                    ok, _ = validate_safe_path(f"C:\\test{bad}x.doc", [".doc"])
                    self.assertFalse(ok)

    def test_url_encoded_sequence_rejected(self):
        with patch("secureredact.utils.security.platform.system", return_value="Windows"):
            ok, msg = validate_safe_path(r"C:\test%0a.doc", [".doc"])
            self.assertFalse(ok)
            self.assertIn("危险序列", msg)

    def test_extension_whitelist_case_insensitive(self):
        """扩展名白名单应大小写不敏感(.DOCX == .docx)。

        路径必须落在允许目录内(家目录),否则会先命中"路径不在允许范围内",
        根本没走到扩展名判断 —— 故用真实家目录而非写死的 Windows 用户目录。
        """
        with patch("secureredact.utils.security.platform.system", return_value="Windows"):
            docx_path = str(Path.home() / "test.DOCX")
            ok, msg = validate_safe_path(docx_path, [".doc", ".docx"])
            self.assertTrue(ok, msg)

    def test_outside_allowed_directory_rejected(self):
        with patch("secureredact.utils.security.platform.system", return_value="Darwin"):
            ok, msg = validate_safe_path("/etc/passwd")
            self.assertFalse(ok)
            self.assertIn("不在允许范围", msg)

    def test_temp_path_allowed(self):
        """临时目录下的路径应被允许(非 Windows 分支)。

        validate_safe_path 用原生 os.path 语义做归一化,因此在 Windows 上
        模拟 Darwin 时必须同时把 gettempdir() 换成 POSIX 形态的 /tmp ——
        否则 os.path.join 会拼出带反斜杠的 Windows 路径,先命中"危险字符",
        走不到临时目录放行逻辑。路径本身也用 POSIX 形态 /tmp/xxx。
        """
        with patch("secureredact.utils.security.platform.system", return_value="Darwin"), \
             patch("secureredact.utils.security.tempfile.gettempdir", return_value="/tmp"):
            temp_path = "/tmp/secureredact_test.docx"
            ok, msg = validate_safe_path(temp_path, [".docx"])
            self.assertTrue(ok, msg)

    def test_prefix_bypass_path_rejected(self):
        """家目录同前缀的兄弟目录(/home/testuser_evil)不得被前缀绕过。

        非 Windows 分支必须用 POSIX 形态路径:Windows 上 os.path.expanduser("~")
        返回带反斜杠的 Windows 用户目录,会先命中"危险字符"而走不到范围判定。
        故同时把 expanduser() 换成 POSIX 家目录,保持前后一致。
        """
        with patch("secureredact.utils.security.platform.system", return_value="Darwin"), \
             patch("secureredact.utils.security.os.path.expanduser",
                   return_value="/home/testuser"):
            fake_sibling = "/home/testuser_evil/test.docx"
            ok, msg = validate_safe_path(fake_sibling, [".docx"])
            self.assertFalse(ok)
            self.assertIn("不在允许范围", msg)

    def test_main_py_uses_shared_validate_safe_path(self):
        """main.py 应直接使用共享实现，不保留本地副本。"""
        with open(os.path.join(ROOT, "main.py"), "r", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("from secureredact.utils.security import validate_safe_path", source,
            "main.py 应从共享模块导入 validate_safe_path")
        self.assertNotRegex(source, r'def validate_safe_path\s*\(',
            "main.py 不应包含 validate_safe_path 的本地定义")

    def test_main_py_uses_shared_resource_path(self):
        """main.py 应使用共享 resource_path，不保留本地副本。"""
        with open(os.path.join(ROOT, "main.py"), "r", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("resource_path", source,
            "main.py 应引用 resource_path")
        lines = source.split('\n')
        local_defs = [l for l in lines if l.strip().startswith('def resource_path')]
        self.assertEqual(len(local_defs), 0,
            f"main.py 不应包含 resource_path 的本地定义，发现: {local_defs}")


if __name__ == "__main__":
    unittest.main()
