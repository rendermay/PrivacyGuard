#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证 secureredact 模块语法"""

import ast
import sys

files_to_check = [
    'secureredact/__init__.py',
    'secureredact/utils/__init__.py',
    'secureredact/utils/security.py',
    'secureredact/utils/config.py',
    'secureredact/utils/exceptions.py',
    'secureredact/utils/temp_manager.py',
    'secureredact/ocr/__init__.py',
    'secureredact/ocr/base.py',
    'secureredact/ocr/manager.py',
    'secureredact/ocr/rapidocr.py',
    'secureredact/ocr/text_pdf.py',
    'secureredact/ocr/mixed_pdf.py',
    'secureredact/workers/__init__.py',
    'secureredact/workers/ocr_worker.py',
    'secureredact/workers/word_worker.py',
    'secureredact/workers/image_merge.py',
]

errors = []
for filepath in files_to_check:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        print(f"[OK] {filepath}")
    except SyntaxError as e:
        errors.append((filepath, str(e)))
        print(f"[ERROR] {filepath}: {e}")
    except FileNotFoundError:
        print(f"[SKIP] {filepath}: File not found")

if errors:
    print(f"\nTotal errors: {len(errors)}")
    sys.exit(1)
else:
    print("\nAll files passed syntax check!")
    sys.exit(0)
