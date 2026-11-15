#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dependency Verification Script for SecureRedact
Run this before building to ensure all required modules are installed.

Usage:
    python packaging/windows/scripts/verify_dependencies.py

Exit codes:
    0 - All dependencies OK
    1 - Missing dependencies
"""

import sys
from pathlib import Path
from typing import Tuple

# Required modules with their import names and pip package names
REQUIRED_MODULES = [
    # (import_name, pip_package_name, description)
    ("bs4", "beautifulsoup4", "HTML parsing"),
    ("PyQt6", "PyQt6", "GUI framework"),
    ("PyQt6.QtWebEngineWidgets", "PyQt6-WebEngine", "Web engine for preview"),
    ("fitz", "PyMuPDF", "PDF processing"),
    ("docx", "python-docx", "Word document processing"),
    ("mammoth", "mammoth", "Word to HTML conversion"),
    ("cv2", "opencv-python", "Image processing for OCR"),
    ("numpy", "numpy", "Numerical computing"),
    ("rapidocr_onnxruntime", "rapidocr-onnxruntime", "OCR engine"),
    ("onnxruntime", "onnxruntime", "ONNX runtime for OCR"),
    ("PIL", "pillow", "Image processing"),
    # --- 以下为实际运行时硬依赖，原清单遗漏（P0-5） ---
    # v1.1.13 中文姓名识别直接依赖 jieba.posseg
    ("jieba", "jieba", "Chinese name recognition (jieba.posseg)"),
    # bs4 / mammoth / python-docx 的解析后端
    ("lxml", "lxml", "HTML/XML parser backend (bs4 / mammoth / python-docx)"),
    # rapidocr_onnxruntime 顶层 import，缺任一项 OCR 直接 ImportError
    ("shapely", "shapely", "OCR polygon post-processing (rapidocr)"),
    ("pyclipper", "pyclipper", "OCR text-box clipping (rapidocr)"),
    ("yaml", "PyYAML", "OCR config loading (rapidocr)"),
    ("six", "six", "OCR compatibility helpers (rapidocr)"),
]

# 与 packaging/requirements-build.txt 保持一致。
# pyinstaller 6.18.0 自身要求 pyinstaller-hooks-contrib>=2025.9；
# 不锁版本会导致「今天装到的 hooks-contrib」与「上次构建出的产物」行为不一致
# —— hook-jieba.py 一旦缺失/改名，打包版 jieba 词典不入包，姓名识别静默失效。
REQUIRED_HOOKS_CONTRIB_VERSION = "2026.10"

# 关键 hook 文件 / 数据文件 (包名, 相对文件名, 用途)
REQUIRED_HOOK_FILES = (
    ("_pyinstaller_hooks_contrib", "stdhooks/hook-jieba.py",
     "jieba dict.txt collection - missing means name recognition silently dies"),
    ("_pyinstaller_hooks_contrib", "stdhooks/hook-docx.py",
     "python-docx resource collection"),
    ("_pyinstaller_hooks_contrib", "stdhooks/hook-onnxruntime.py",
     "onnxruntime DLL collection"),
    ("_pyinstaller_hooks_contrib", "stdhooks/hook-pymupdf.py",
     "PyMuPDF resource collection"),
    ("jieba", "dict.txt",
     "jieba Chinese dictionary (~5MB)"),
)

def check_module(import_name: str) -> Tuple[bool, str]:
    """Check if a module can be imported."""
    try:
        __import__(import_name)
        return True, "OK"
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error: {e}"

def verify_dependencies() -> bool:
    """Verify all required dependencies are installed."""
    print("=" * 60)
    print("  SecureRedact Dependency Verification")
    print("=" * 60)
    print()

    missing = []
    errors = []

    print(f"{'Module':<35} {'Status':<10}")
    print("-" * 60)

    for import_name, pip_name, description in REQUIRED_MODULES:
        success, message = check_module(import_name)

        if success:
            print(f"{import_name:<35} {'OK':<10}")
        else:
            print(f"{import_name:<35} {'MISSING':<10}")
            missing.append((import_name, pip_name, description, message))

    print()
    print("=" * 60)

    if missing:
        print("  [ERROR] Missing dependencies detected!")
        print("=" * 60)
        print()
        print("Missing modules:")
        for import_name, pip_name, description, error in missing:
            print(f"  - {import_name} ({description})")
            print(f"    Install: pip install {pip_name}")
            print(f"    Error: {error}")
            print()

        print("To fix, run:")
        print("  pip install -r requirements.txt")
        print()
        return False
    else:
        print("  [OK] All dependencies verified!")
        print("=" * 60)
        print()
        return True

def check_bs4_collectable() -> bool:
    """
    Check if bs4 can be collected by PyInstaller.
    This verifies that bs4 is properly installed in the current environment.
    """
    print("Checking PyInstaller collectability...")

    try:
        from PyInstaller.utils.hooks import collect_all

        # Try to collect bs4 module
        datas, binaries, hiddenimports = collect_all('bs4')

        if not datas and not hiddenimports:
            print("  [WARN] collect_all('bs4') returned empty results")
            print("  [HINT] bs4 may not be properly installed")
            return False

        print(f"  [OK] bs4 collectable: {len(datas)} datas, {len(hiddenimports)} hidden imports")
        return True
    except ImportError:
        print("  [SKIP] PyInstaller not installed, skipping collectability check")
        return True
    except Exception as e:
        print(f"  [WARN] Error checking bs4 collectability: {e}")
        return False

def _package_version(distribution: str):
    """Return the installed version of a distribution, or None if not installed."""
    try:
        from importlib import metadata as importlib_metadata
    except ImportError:  # pragma: no cover - Python < 3.8 fallback
        try:
            import importlib_metadata  # type: ignore
        except ImportError:
            return None
    try:
        return importlib_metadata.version(distribution)
    except Exception:
        return None


def _parse_version(value: str) -> tuple:
    """Parse '2026.10' / '6.18.0' into a comparable tuple of ints."""
    parts = []
    for chunk in str(value).split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _find_package_file(package_name: str, file_name: str):
    """Locate a data file inside an installed package; return None if missing."""
    try:
        module = __import__(package_name)
    except Exception:
        return None
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return None
    candidate = Path(module_file).parent / file_name
    return candidate if candidate.exists() else None


def check_packaging_hooks() -> bool:
    """Verify the PyInstaller hooks and data files the build depends on.

    Why this check exists:
        jieba's Chinese dictionary (jieba/dict.txt, ~5MB) can only reach the
        bundle through hooks-contrib's hook-jieba.py, whose whole content is
        collect_data_files('jieba'). When that hook is missing, importing
        jieba inside the frozen app fails, and
        secureredact/pii/name_recognizer.py::_ensure_jieba() swallows the
        exception -- so Chinese name recognition silently stops working with
        no error shown to the user. Such a silent downgrade has to be blocked
        before the build, not discovered after release.
    """
    print()
    print("=" * 60)
    print("  Packaging Hooks / Data Files Check")
    print("=" * 60)
    print()

    ok = True

    # 1) hooks-contrib installed, and at the locked version
    installed = _package_version("pyinstaller-hooks-contrib")
    if installed is None:
        print("  [FAIL] pyinstaller-hooks-contrib is not installed")
        print("         jieba's dict.txt only enters the bundle via hooks-contrib's")
        print("         hook-jieba.py; without it Chinese name recognition silently")
        print("         stops working in the packaged app.")
        print("         Install: pip install pyinstaller-hooks-contrib==%s"
              % REQUIRED_HOOKS_CONTRIB_VERSION)
        ok = False
    else:
        print("  [OK] pyinstaller-hooks-contrib %s" % installed)
        if _parse_version(installed) < _parse_version(REQUIRED_HOOKS_CONTRIB_VERSION):
            print("  [FAIL] version is older than the locked %s (build is not reproducible)"
                  % REQUIRED_HOOKS_CONTRIB_VERSION)
            print("         Install: pip install pyinstaller-hooks-contrib==%s"
                  % REQUIRED_HOOKS_CONTRIB_VERSION)
            ok = False

    # 2) the hook files / data files themselves must be present on disk
    for package_name, file_name, purpose in REQUIRED_HOOK_FILES:
        path = _find_package_file(package_name, file_name)
        if path is None:
            print("  [FAIL] %s/%s not found  (%s)" % (package_name, file_name, purpose))
            ok = False
        else:
            print("  [OK] %s/%s  (%s)" % (package_name, file_name, purpose))

    return ok


def main():
    """Main entry point."""
    # Check basic dependencies
    deps_ok = verify_dependencies()

    # Check PyInstaller collectability and packaging hooks if deps are OK
    hooks_ok = True
    if deps_ok:
        check_bs4_collectable()
        hooks_ok = check_packaging_hooks()

    # Exit with appropriate code
    if deps_ok and hooks_ok:
        print("Verification passed. Ready to build.")
        sys.exit(0)
    else:
        print("Verification failed. Please install missing dependencies.")
        sys.exit(1)

if __name__ == "__main__":
    main()
