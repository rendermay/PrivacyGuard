"""
SecureRedact 命令行薄壳 (PR-C8, plan §6)

职责:
- 提供 `python -m secureredact.cli <subcommand> ...` 入口
- 验证 PR-C4 业务 API 层确实支持 GUI 之外的消费方式
- 不替换 GUI,仅做 demo + 自动化友好入口

子命令:
  scan          扫描 PDF, 打印 JSON
  redact        执行 PDF 脱敏
  redact-word   批量 Word 替换
  --version     显示版本
  --help        显示帮助

设计:
- 避免 import 触发 secureredact.api 顶层依赖(PR-C5 已改 lazy)。
  redact-word 不调 batch_redact_word(PDF/Word 单文件路径),纯 stdlib 可用。
- 输出走 print + json.dumps,无 GUI 依赖。
- 规则支持两种来源:--rules '<JSON 字符串>'(Windows CMD 需 escape)或
  --rules-file path/to/rules.json(推荐,plan §0.3 风险 L-1)。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


def _load_rules(args) -> Dict[str, Any]:
    """从 --rules 或 --rules-file 读取规则。

    Returns:
        rules 字典。Word 端使用 list[dict],PDF 端使用 dict[name, pattern]。
        这里返回通用 dict,具体格式由调用方按需处理。
    """
    if args.rules_file:
        with open(args.rules_file, "r", encoding="utf-8") as f:
            return json.load(f)
    if args.rules:
        return json.loads(args.rules)
    return {}


def _cmd_version(_args) -> int:
    """显示版本号。"""
    try:
        import secureredact
        print(secureredact.__version__)
    except ImportError:
        print("unknown")
    return 0


def _cmd_scan(args) -> int:
    """扫描 PDF,打印 JSON 结果(plan §6.2)。"""
    import secureredact.api as api  # lazy import

    if not os.path.isfile(args.input):
        print(f"ERROR: file not found: {args.input}", file=sys.stderr)
        return 2

    custom_keywords = " ".join(args.keywords) if args.keywords else ""
    rules = _load_rules(args)

    try:
        hits_by_page = api.scan_pdf(
            args.input,
            rules=rules,
            custom_keywords=custom_keywords,
        )
    except Exception as e:
        print(f"ERROR: scan failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(hits_by_page, ensure_ascii=False, indent=2))
    else:
        total = sum(len(v) for v in hits_by_page.values())
        print(f"Scanned {args.input}: {total} hits across {len(hits_by_page)} pages")
        for page_num in sorted(hits_by_page):
            print(f"  page {page_num}: {len(hits_by_page[page_num])} hits")
    return 0


def _cmd_redact(args) -> int:
    """执行 PDF 脱敏(plan §6.2)。"""
    import secureredact.api as api  # lazy import

    if not os.path.isfile(args.input):
        print(f"ERROR: file not found: {args.input}", file=sys.stderr)
        return 2

    custom_keywords = " ".join(args.keywords) if args.keywords else ""
    rules = _load_rules(args)

    output_path = args.output
    if not output_path:
        # 默认: input + ".redacted"
        output_path = str(args.input) + ".redacted"

    try:
        result = api.redact_pdf(
            args.input,
            output_path,
            rules=rules,
            custom_keywords=custom_keywords,
        )
    except Exception as e:
        print(f"ERROR: redact failed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Redacted: {result['output']}")
        print(f"  pages: {result['pages']}")
        print(f"  hits:  {result['hits']}")
        print(f"  time:  {result['elapsed_sec']:.2f}s")
    return 0


def _cmd_redact_word(args) -> int:
    """批量 Word 替换(plan §6.2)。"""
    import secureredact.api as api  # lazy import

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f"ERROR: input is not a directory: {args.input}", file=sys.stderr)
        return 2

    output_dir = Path(args.output)
    if not output_dir.is_dir():
        print(f"ERROR: output dir not found: {args.output}", file=sys.stderr)
        return 2

    # 找所有 .docx (plan §6.2 默认 .docx,不调 batch_redact_word 处理 .doc)
    word_files = sorted(input_dir.glob("*.docx"))
    if not word_files:
        print(f"WARNING: no .docx files in {args.input}", file=sys.stderr)
        return 0

    custom_keywords = " ".join(args.keywords) if args.keywords else ""
    rules = _load_rules(args)

    # Word 端 rules 用 list 格式
    if isinstance(rules, dict):
        rules_list = [
            {"find": pattern, "mode": "regex", "enabled": True}
            for pattern in rules.values()
            if isinstance(pattern, str)
        ]
    else:
        rules_list = list(rules)

    results = []
    for word_path in word_files:
        out_path = output_dir / word_path.name
        try:
            result = api.redact_word(
                str(word_path),
                str(out_path),
                rules=rules_list,
                custom_keywords=custom_keywords,
                replacement_text=args.replacement,
            )
            results.append({"input": str(word_path), "result": result})
            if not args.json:
                print(f"  [OK]   {word_path.name}  →  {out_path.name}  ({result['hits']} hits, {result['elapsed_sec']:.2f}s)")
        except Exception as e:
            results.append({"input": str(word_path), "error": str(e)})
            if not args.json:
                print(f"  [FAIL] {word_path.name}: {e}", file=sys.stderr)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    failed = sum(1 for r in results if "error" in r)
    return 0 if failed == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    """构建 argparse(plan §6.2 命令面)。"""
    parser = argparse.ArgumentParser(
        prog="secureredact.cli",
        description="SecureRedact CLI - 脱敏 / 扫描的轻量级入口",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    # scan
    p_scan = sub.add_parser("scan", help="扫描 PDF 命中,不脱敏")
    p_scan.add_argument("input", help="输入 PDF 路径")
    p_scan.add_argument("--rules", help="规则 JSON 字符串(键为规则名,值为正则)")
    p_scan.add_argument("--rules-file", help="从 JSON 文件读规则")
    p_scan.add_argument("--keywords", nargs="*", help="自定义关键词(空格分隔)")
    p_scan.add_argument("--json", action="store_true", help="以 JSON 形式输出命中")
    p_scan.set_defaults(func=_cmd_scan)

    # redact
    p_redact = sub.add_parser("redact", help="执行 PDF 脱敏")
    p_redact.add_argument("input", help="输入 PDF 路径")
    p_redact.add_argument("--output", help="输出 PDF 路径(默认 <input>.redacted)")
    p_redact.add_argument("--rules", help="规则 JSON 字符串")
    p_redact.add_argument("--rules-file", help="从 JSON 文件读规则")
    p_redact.add_argument("--keywords", nargs="*", help="自定义关键词")
    p_redact.add_argument("--json", action="store_true")
    p_redact.set_defaults(func=_cmd_redact)

    # redact-word
    p_w = sub.add_parser("redact-word", help="批量 Word 替换")
    p_w.add_argument("input", help="输入 Word 目录(找 *.docx)")
    p_w.add_argument("--output", help="输出目录")
    p_w.add_argument("--rules", help="规则 JSON 字符串")
    p_w.add_argument("--rules-file", help="从 JSON 文件读规则")
    p_w.add_argument("--keywords", nargs="*", help="自定义关键词")
    p_w.add_argument("--replacement", default="[已脱敏]", help="统一替换文本")
    p_w.add_argument("--json", action="store_true")
    p_w.set_defaults(func=_cmd_redact_word)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口(plan §6.2 --version / --help 默认动作)。"""
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] in ("--version", "-V"):
        return _cmd_version(None)
    if not argv or argv[0] in ("--help", "-h"):
        parser = build_parser()
        parser.print_help()
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
