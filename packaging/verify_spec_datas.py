#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static pre-flight check for the PyInstaller specs (no build is performed).

For every spec this verifies:

  1. the spec is valid Python (ast.parse);
  2. every source path referenced by the datas / icon entries actually exists
     on disk -- a missing source makes PyInstaller abort the build with an
     "Unable to find ..." error that is easy to miss in a long build log;
  3. version.txt is packaged into the application directory -- the runtime
     reads it via Path(__file__).parent../version.txt and silently falls back
     to a stale hard-coded string when it is missing;
  4. config.json is packaged into the application directory -- the runtime
     reads <app dir>/config.json as the factory-default baseline.

Usage:
    python packaging/verify_spec_datas.py

Exit codes:
    0 - all checks passed
    1 - at least one check failed
"""

from __future__ import annotations

import ast
import os
import sys


# spec path -> label
SPECS = (
    ("packaging/windows/config/SecureRedact_windows.spec", "Windows (active)"),
    ("packaging/windows/config/SecureRedact_windows_v2.spec", "Windows v2 (dead code)"),
    ("packaging/macos/config/SecureRedact.spec", "macOS"),
)

# Files that MUST end up in the application directory (dest ".")
REQUIRED_AT_APP_ROOT = ("version.txt", "config.json")


def _project_root(spec_path: str) -> str:
    """Specs live in <root>/packaging/<platform>/config/ -> 3 levels up."""
    config_dir = os.path.dirname(os.path.abspath(spec_path))
    return os.path.dirname(os.path.dirname(os.path.dirname(config_dir)))


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _resolve_join(node, root: str):
    """Resolve os.path.join(project_root, 'a', 'b') -> absolute path or None."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "join"):
        return None
    # func.value must be the os.path attribute chain
    path_attr = func.value
    if not (isinstance(path_attr, ast.Attribute) and path_attr.attr == "path"):
        return None
    if not isinstance(path_attr.value, ast.Name) or path_attr.value.id != "os":
        return None
    parts = []
    for arg in node.args:
        if isinstance(arg, ast.Name) and arg.id == "project_root":
            parts.append(root)
        else:
            const = _const_str(arg)
            if const is None:
                return None
            parts.append(const)
    if not parts:
        return None
    return os.path.join(*parts)


def _collect_spec_entries(tree, root: str):
    """Return (datas_entries, icon_entries) as (src, dest) tuples."""
    datas = []
    icons = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = getattr(node.func, "id", None)
        if func_name == "Analysis":
            for kw in node.keywords:
                if kw.arg != "datas":
                    continue
                for elt in ast.walk(kw.value):
                    if not (isinstance(elt, ast.Tuple) and len(elt.elts) == 2):
                        continue
                    src = _resolve_join(elt.elts[0], root)
                    dest = _const_str(elt.elts[1])
                    if src is not None:
                        datas.append((src, dest))
        elif func_name == "EXE":
            for kw in node.keywords:
                if kw.arg != "icon":
                    continue
                src = _resolve_join(kw.value, root)
                if src is not None:
                    icons.append((src, None))

    return datas, icons


def check_spec(spec_path: str, label: str, repo_root: str) -> bool:
    print("-" * 68)
    print("  %s" % spec_path)
    print("  [%s]" % label)
    print("-" * 68)

    ok = True
    abs_spec = os.path.join(repo_root, spec_path)
    if not os.path.isfile(abs_spec):
        print("  [FAIL] spec file not found")
        return False

    with open(abs_spec, "r", encoding="utf-8") as fh:
        source = fh.read()

    try:
        tree = ast.parse(source, filename=abs_spec)
    except SyntaxError as exc:
        print("  [FAIL] not valid Python: %s" % exc)
        return False
    print("  [OK] valid Python (ast.parse)")

    root = _project_root(abs_spec)
    datas, icons = _collect_spec_entries(tree, root)

    if not datas:
        print("  [FAIL] no resolvable datas entries found")
        ok = False

    for src, dest in datas + icons:
        exists = os.path.exists(src)
        if not exists:
            ok = False
        rel = os.path.relpath(src, root) if src.startswith(root) else src
        tag = "datas" if dest is not None else "icon "
        print("  [%s] %s %-34s -> %s"
              % ("OK" if exists else "FAIL", tag, rel, dest if dest is not None else "-"))

    basenames = {}
    for src, dest in datas:
        basenames.setdefault(os.path.basename(src), set()).add(dest)
    for required in REQUIRED_AT_APP_ROOT:
        dests = basenames.get(required)
        if not dests:
            print("  [FAIL] %s is NOT packaged - runtime would fall back to a stale value" % required)
            ok = False
        elif "." not in dests:
            print("  [FAIL] %s is packaged to %s, expected the application directory '.'" % (required, dests))
            ok = False
        else:
            print("  [OK] %s is packaged into the application directory" % required)

    print()
    return ok


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 68)
    print("  SecureRedact - PyInstaller spec static pre-flight check")
    print("  (no build is performed)")
    print("=" * 68)
    print()

    all_ok = True
    for spec_path, label in SPECS:
        if not check_spec(spec_path, label, repo_root):
            all_ok = False

    print("=" * 68)
    if all_ok:
        print("  [OK] All spec checks passed.")
    else:
        print("  [FAIL] Spec checks failed - fix the items marked FAIL above.")
    print("=" * 68)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
