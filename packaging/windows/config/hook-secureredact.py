# -*- coding: utf-8 -*-
"""
PyInstaller hook for secureredact package
强制包含所有子模块（修复 ModuleNotFoundError）
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# 收集所有子模块
hiddenimports = collect_submodules('secureredact')

# 如果 collect_submodules 返回空，手动添加所有子模块
if not hiddenimports:
    hiddenimports = [
        'secureredact',
        'secureredact.utils',
        'secureredact.utils.security',
        'secureredact.utils.config',
        'secureredact.utils.exceptions',
        'secureredact.utils.temp_manager',
        'secureredact.ocr',
        'secureredact.ocr.base',
        'secureredact.ocr.manager',
        'secureredact.ocr.rapidocr',
        'secureredact.ocr.text_pdf',
        'secureredact.ocr.mixed_pdf',
        'secureredact.workers',
        'secureredact.workers.ocr_worker',
        'secureredact.workers.word_worker',
        'secureredact.workers.image_merge',
        'secureredact.core',
        'secureredact.ui',
    ]

# 收集数据文件
datas = collect_data_files('secureredact')

print(f"[HOOK] Collected {len(hiddenimports)} secureredact hidden imports")
print(f"[HOOK] Collected {len(datas)} secureredact data files")
