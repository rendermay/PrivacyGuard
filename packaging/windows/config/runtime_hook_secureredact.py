# -*- coding: utf-8 -*-
"""
PyInstaller Runtime Hook for secureredact
在运行时确保 secureredact 模块路径正确
"""

import sys
import os

# 获取应用程序根目录（EXE 所在目录）
if getattr(sys, 'frozen', False):
    # 打包后的环境
    app_dir = os.path.dirname(sys.executable)
else:
    # 开发环境
    app_dir = os.path.dirname(os.path.abspath(__file__))

# 将 secureredact 目录添加到 sys.path
secureredact_paths = [
    app_dir,  # 根目录（包含 secureredact 包）
    os.path.join(app_dir, 'secureredact'),
    os.path.join(app_dir, 'secureredact', 'utils'),
    os.path.join(app_dir, 'secureredact', 'ocr'),
    os.path.join(app_dir, 'secureredact', 'workers'),
]

for path in secureredact_paths:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

print(f"[RUNTIME HOOK] Added secureredact paths to sys.path")
