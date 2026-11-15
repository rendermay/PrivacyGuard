# -*- mode: python ; coding: utf-8 -*-
"""
SecureRedact Windows Build Spec File v2
PyInstaller Configuration - Enhanced for onnxruntime 1.24.1 compatibility
"""

# ============================================================================
# ⚠️⚠️ 死代码警告 —— 请勿直接启用本文件 ⚠️⚠️
# ============================================================================
# 【当前生效的 spec 是】packaging/windows/config/SecureRedact_windows.spec
#
# 【为什么本文件是死代码】
#   1. 没有任何打包脚本引用它。仓库内全部构建入口都指向 v1 spec：
#        - packaging/windows/scripts/build_complete.bat      (便携版主链)
#        - packaging/windows/scripts/2_build_exe.bat
#        - packaging/windows/scripts/3_build_with_setup.bat  (安装版主链)
#      仅凭文件名无法触发本文件，必须显式改脚本路径才可能启用。
#
#   2. 本文件缺少 v1 spec 已有的关键配置，直接启用会构建失败或运行期崩：
#        - 无 secureredact.* 的 hiddenimports  -> 模块名解析失败(ModuleNotFoundError)
#        - hookspath=[]                        -> 不加载 hook-secureredact.py
#        - runtime_hooks=[]                    -> 不加载 runtime_hook_secureredact.py
#        - 不含 secureredact/config.json      -> 打包版配置丢失
#
#   3. 本文件与 v1 spec 的图标来源不同(此处为 packaging/windows/assets/icon.ico，
#      v1 为 assets/logo/windows/app_icon.ico)，且只收集了部分依赖(cv2 binaries
#      在此有、在 v1 没有)，两边的产物并不等价。
#
# 【维护约定】
#   本文件保留仅作历史参考，不参与任何发布链路。
#   如需真正启用 v2，请先把它与 v1 spec 逐项对齐(hiddenimports / hookspath /
#   runtime_hooks / datas)，再同步更新上述三个 .bat 脚本的 spec 路径。
# ============================================================================

import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

import os
import glob
from PyInstaller.utils.hooks import copy_metadata, collect_all, collect_dynamic_libs

# 获取路径
current_dir = os.path.dirname(os.path.abspath(SPEC))
windows_dir = os.path.dirname(current_dir)
packaging_dir = os.path.dirname(windows_dir)
project_root = os.path.dirname(packaging_dir)

block_cipher = None

# ========== 关键修复: 精确收集 onnxruntime 文件 ==========
import site
import onnxruntime

# 获取 onnxruntime 实际安装路径
onnxruntime_path = os.path.dirname(onnxruntime.__file__)
print(f"[INFO] onnxruntime path: {onnxruntime_path}")

# 收集所有 onnxruntime 文件（包括 capi 子目录）
onnx_binaries = []
onnx_datas = []

# 递归收集所有 DLL 和 PYD 文件
for root, dirs, files in os.walk(onnxruntime_path):
    for file in files:
        file_path = os.path.join(root, file)
        # 计算相对路径作为目标目录
        rel_path = os.path.relpath(root, os.path.dirname(onnxruntime_path))

        if file.endswith(('.dll', '.pyd', '.so')):
            # DLL 文件放入 binaries
            dest_dir = rel_path if rel_path != '.' else 'onnxruntime'
            onnx_binaries.append((file_path, dest_dir))
            print(f"[BIN] {file} -> {dest_dir}")
        elif file.endswith(('.py', '.json', '.txt')):
            # Python 文件和配置放入 datas
            dest_dir = rel_path if rel_path != '.' else 'onnxruntime'
            onnx_datas.append((file_path, dest_dir))

# 收集 rapidocr_onnxruntime
rapidocr_binaries = []
rapidocr_datas = []
try:
    import rapidocr_onnxruntime
    rapidocr_path = os.path.dirname(rapidocr_onnxruntime.__file__)
    print(f"[INFO] rapidocr_onnxruntime path: {rapidocr_path}")

    for root, dirs, files in os.walk(rapidocr_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(root, os.path.dirname(rapidocr_path))

            if file.endswith(('.dll', '.pyd', '.so', '.onnx', '.json')):
                dest_dir = rel_path if rel_path != '.' else 'rapidocr_onnxruntime'
                rapidocr_binaries.append((file_path, dest_dir))
                print(f"[BIN-R] {file} -> {dest_dir}")
            elif file.endswith(('.py', '.yaml', '.yml')):
                dest_dir = rel_path if rel_path != '.' else 'rapidocr_onnxruntime'
                rapidocr_datas.append((file_path, dest_dir))
except Exception as e:
    print(f"[WARN] Failed to collect rapidocr: {e}")

# ========== 关键修复: VC++ 运行时 ==========
vcrt_binaries = []

# 必需的 VC++ DLL 列表（按优先级排序）
required_vc_dlls = [
    'vcruntime140_1.dll',  # 最关键: onnxruntime 1.24+ 必需
    'vcruntime140.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'concrt140.dll',
    'vccorlib140.dll',
]

# 从多个可能的位置收集
search_paths = []

# 1. System32
system_root = os.environ.get('SYSTEMROOT', 'C:\\Windows')
search_paths.append(os.path.join(system_root, 'System32'))
search_paths.append(os.path.join(system_root, 'SysWOW64'))

# 2. Python 安装目录
python_base = os.path.dirname(sys.executable)
search_paths.extend([
    os.path.join(python_base, 'DLLs'),
    os.path.join(python_base, 'Library', 'bin'),
    python_base,
])

# 3. Conda/Miniconda 环境
if 'CONDA_PREFIX' in os.environ:
    conda_prefix = os.environ['CONDA_PREFIX']
    search_paths.extend([
        os.path.join(conda_prefix, 'DLLs'),
        os.path.join(conda_prefix, 'Library', 'bin'),
        conda_prefix,
    ])

# 4. site-packages 中的 VC++ runtime
for site_path in site.getsitepackages():
    search_paths.append(site_path)

# 搜索并收集 DLL
collected_dlls = set()
for search_path in search_paths:
    if not os.path.exists(search_path):
        continue
    for dll_name in required_vc_dlls:
        if dll_name in collected_dlls:
            continue
        dll_path = os.path.join(search_path, dll_name)
        if os.path.exists(dll_path):
            vcrt_binaries.append((dll_path, '.'))
            collected_dlls.add(dll_name)
            print(f"[VCRT] Found {dll_name} at {search_path}")

# 检查关键 DLL 是否找到
critical_dlls = ['vcruntime140_1.dll', 'vcruntime140.dll', 'msvcp140.dll']
missing_critical = [dll for dll in critical_dlls if dll not in collected_dlls]
if missing_critical:
    print(f"[CRITICAL] Missing required VC++ DLLs: {missing_critical}")
    print("[CRITICAL] Please install VC++ Redistributable 2015-2022")

# ========== 收集其他依赖 ==========

# PyQt6 WebEngine
pyqt6_binaries = collect_dynamic_libs('PyQt6', destdir='PyQt6/Qt6/bin')

# OpenCV
cv2_binaries = collect_dynamic_libs('cv2')

# numpy - 收集核心模块和兼容层
numpy_binaries = collect_dynamic_libs('numpy')

# v37.0.6: 添加 numpy.core 兼容层（numpy 2.x 需要）
import numpy
numpy_path = os.path.dirname(numpy.__file__)
numpy_datas = []
numpy_core_path = os.path.join(numpy_path, 'core')
if os.path.exists(numpy_core_path):
    numpy_datas.append((numpy_core_path, 'numpy/core'))
    print(f"[NUMPY] Adding numpy.core compatibility layer from {numpy_core_path}")

print(f"\n[INFO] Summary:")
print(f"  - onnxruntime binaries: {len(onnx_binaries)}")
print(f"  - rapidocr binaries: {len(rapidocr_binaries)}")
print(f"  - VC++ runtime files: {len(vcrt_binaries)}")
print(f"  - PyQt6 binaries: {len(pyqt6_binaries)}")
print(f"  - numpy datas: {len(numpy_datas)}")

# ========== Analysis ==========
a = Analysis(
    [os.path.join(project_root, 'secureredact/main.py')],
    pathex=[
        project_root,
        current_dir,
        onnxruntime_path,  # 添加 onnxruntime 路径到 Python 路径
    ],
    binaries=(
        onnx_binaries +
        rapidocr_binaries +
        vcrt_binaries +
        pyqt6_binaries +
        cv2_binaries +
        numpy_binaries
    ),
    datas=[
        (os.path.join(project_root, 'theme.py'), '.'),
        # 包含配置文件（应用目录 = sys._MEIPASS，与 EXE 同级）
        (os.path.join(project_root, 'config.json'), '.'),
        # P0-1: 包含版本文件 —— 冻结后 Path(__file__).parent../version.txt 必须存在，
        # 否则落 fallback "1.1.12"，与 EXE 版本资源(version_info.txt)不一致。
        (os.path.join(project_root, 'version.txt'), '.'),
        (os.path.join(project_root, 'assets'), 'assets'),
    ] + onnx_datas + rapidocr_datas + numpy_datas,
    hiddenimports=[
        # PyQt6
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel',
        'PyQt6.QtWebEngineCore',
        # 核心依赖
        'cv2',
        'cv2.cv2',
        'fitz',
        'fitz.fitz',
        'numpy',
        'numpy.core._multiarray_umath',  # numpy 1.x 兼容
        'numpy._core._multiarray_umath',  # numpy 2.x
        'numpy._core',
        # OCR - 完整导入链
        'rapidocr_onnxruntime',
        'rapidocr_onnxruntime.rapid_ocr_api',
        'rapidocr_onnxruntime.utils',
        'rapidocr_onnxruntime.utils.load_image',
        # onnxruntime - 完整导入链
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi._pybind_state',
        'onnxruntime.capi.onnxruntime_pybind11_state',
        'onnxruntime.capi._ld_preload',
        'onnxruntime.capi.training',
        # 训练相关（可能被导入）
        'onnxruntime.training',
        'onnxruntime.quantization',
        'onnxruntime.transformers',
        # 主题和配置
        'theme',
        # 其他
        'PIL',
        'PIL._imaging',
        'PIL._imagingft',
        'PIL._imagingtk',
        'docx',
        'docx.api',
        'bs4',
        'lxml',
        'lxml.etree',
        'sklearn',
        'sklearn.utils._typedefs',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'PyQt6.QtMacExtras',
        'PyQt5',
        'PySide2',
        'PySide6',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 移除重复项
print(f"\n[INFO] Removing duplicates...")
a.binaries = list(set(a.binaries))
a.datas = list(set(a.datas))
print(f"  - Unique binaries: {len(a.binaries)}")
print(f"  - Unique datas: {len(a.datas)}")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SecureRedact',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # v37.0.6: 禁用控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(windows_dir, 'assets', 'icon.ico'),
    version=os.path.join(current_dir, 'version_info.txt'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SecureRedact',
)
