"""
secureredact.cli 单元测试 (PR-C8, plan §6.3)

设计原则:
- 不依赖 QApplication / PyQt6
- 子命令 + --version / --help smoke test
- 命令行参数解析覆盖
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr

import pytest  # noqa: F401 — for markers


@pytest.mark.cli
@pytest.mark.smoke
class TestCliVersion(unittest.TestCase):
    """--version / --help smoke (plan §6.5 验收)。"""

    def test_version_prints_version(self):
        import secureredact
        out = io.StringIO()
        with redirect_stdout(out):
            from secureredact.cli import main
            rc = main(["--version"])
        self.assertEqual(rc, 0)
        self.assertIn(secureredact.__version__, out.getvalue())

    def test_help_prints_subcommands(self):
        out = io.StringIO()
        with redirect_stdout(out):
            from secureredact.cli import main
            rc = main(["--help"])
        self.assertEqual(rc, 0)
        text = out.getvalue()
        # plan §6.2 命令面 3 个子命令
        for sub in ("scan", "redact", "redact-word"):
            self.assertIn(sub, text)

    def test_no_args_shows_help(self):
        """argv 空时打印 help(plan §6.5 '不实例化 QApplication' 由 --help 路径验证)。"""
        out = io.StringIO()
        with redirect_stdout(out):
            from secureredact.cli import main
            rc = main([])
        self.assertEqual(rc, 0)
        self.assertIn("scan", out.getvalue())


@pytest.mark.cli
class TestCliBuildParser(unittest.TestCase):
    """argparse 解析。"""

    def test_parser_has_all_subcommands(self):
        from secureredact.cli import build_parser
        parser = build_parser()
        # scan / redact / redact-word
        for sub in ("scan", "redact", "redact-word"):
            self.assertIn(sub, parser._subparsers._group_actions[0].choices)

    def test_scan_input_required(self):
        from secureredact.cli import build_parser
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["scan"])

    def test_redact_word_replacement_default(self):
        from secureredact.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["redact-word", "in_dir", "--output", "out_dir"])
        self.assertEqual(args.replacement, "[已脱敏]")


@pytest.mark.cli
class TestCliLoadRules(unittest.TestCase):
    """_load_rules 规则读取(JSON 字符串 / JSON 文件 / 空)。"""

    def setUp(self):
        from secureredact.cli import _load_rules

        # 构造带 --rules 的 namespace
        class _NS:
            pass

        self._load = _load_rules
        self._ns_json = _NS()
        # JSON 字符串中合法 escape 只有 \" \\/ \\b \\f \\n \\r \\t \\uXXXX
        # 用 \\\\d 表达字面 \d(JSON 解析后是 \\d → Python 字符串 \d)
        self._ns_json.rules = '{"phone": "1[3-9]\\\\d{9}"}'
        self._ns_json.rules_file = None
        self._ns_empty = _NS()
        self._ns_empty.rules = None
        self._ns_empty.rules_file = None

    def test_load_from_json_string(self):
        rules = self._load(self._ns_json)
        # 解析后是 Python 字符串 "1[3-9]\\d{9}"(反斜杠 + d)
        self.assertEqual(rules, {"phone": "1[3-9]\\d{9}"})

    def test_load_empty_returns_empty_dict(self):
        self.assertEqual(self._load(self._ns_empty), {})

    def test_load_from_file(self):
        import tempfile
        from secureredact.cli import _load_rules
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".json", mode="w", encoding="utf-8"
        ) as f:
            json.dump({"phone": "1[3-9]\\d{9}"}, f)
            path = f.name
        try:
            class _NS:
                pass
            ns = _NS()
            ns.rules = None
            ns.rules_file = path
            rules = _load_rules(ns)
            self.assertEqual(rules, {"phone": "1[3-9]\\d{9}"})
        finally:
            os_unlink_safe(path)


def os_unlink_safe(path: str) -> None:
    import os
    try:
        os.unlink(path)
    except OSError:
        pass


if __name__ == "__main__":
    unittest.main()
