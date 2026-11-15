# P0-2 打包链路修正报告

> 任务：`task-1`（P0-2 打包链路修正：spec 补 version.txt + 配置打包路径）
> 工作目录：`G:\Project\SecureRedact\.agents\worktrees\dsh-3eb2fb3e-5817`
> 日期：2026-11-15
> **写入范围：仅 `packaging/**`**（已用 `git status --short -- packaging` 核验，见 §6）
> **未执行任何 PyInstaller 打包**

---

## 0. 结论速览

| 项 | 结果 |
|---|---|
| 改动文件 | 9 个修改 + 3 个新增，**全部在 `packaging/` 内** |
| 三个 spec 补 `version.txt` | ✅ 已补（datas → 应用目录 `.`） |
| 三个 spec 的 `config.json` | ✅ **核实：原本就已齐全**，无需补 |
| macOS 图标检查 100% 失败 | ✅ 已修（改为 `assets/logo/macos/AppIcon.icns`） |
| `Contents/Resources/*.icns` 路径假设 | ✅ **核实为错误**，已改为 `AppIcon.icns` |
| v2 spec 死代码警示 | ✅ 已加（未删除文件） |
| Inno Setup 版本默认值 | ✅ 1.1.11 → **1.1.13**（命令行传入仍优先） |
| Inno Setup LICENSE | ✅ 已加 `LicenseFile` + `[Files]` 复制指令 |
| `pyinstaller-hooks-contrib` 锁版本 | ✅ 新增 `packaging/requirements-build.txt`（根 `requirements.txt` 超出写入范围，需 lead 同步） |
| `verify_dependencies.py` 补 jieba | ✅ 已补，并新增 6 项依赖 + hooks 存在性校验 |
| 新增静态预检 | ✅ `packaging/verify_spec_datas.py`（AST 解析，不打包） |
| 验收 | compileall **0** / spec compile **0** / 预检 **0** / bash -n **0** |

---

## 1. T1 — 三个 spec 的 datas 补 version.txt

### 1.1 缺陷机理（已逐条核实）

运行时三处版本读取全部指向 `_MEIPASS/version.txt`：

| 读取点 | 代码 | 冻结后解析为 |
|---|---|---|
| `secureredact/__init__.py:14` | `Path(__file__).resolve().parent.parent / "version.txt"` | `_MEIPASS/version.txt` |
| `secureredact/ui/main_window/window.py:117` | `Path(__file__).resolve().parent.parent.parent.parent / "version.txt"` | `_MEIPASS/version.txt` |
| 根 `main.py`（shim） | `Path(__file__).resolve().parent / "version.txt"` | `_MEIPASS/version.txt` |

三个 spec 原本**都没有**把 `version.txt` 放进 `datas` → 冻结后文件不存在 → 全部落 fallback `"1.1.12"`，
而 EXE 版本资源（`version_info.txt`，构建时由 `generate_version_info.py` 从 `version.txt` 生成）是 **1.1.13**、
macOS `Info.plist` 的 `CFBundleVersion` 也是 **1.1.13** → 「窗口标题 / 关于窗口 / EXE 属性」三处版本号互相打架。

### 1.2 改动前后

**`packaging/windows/config/SecureRedact_windows.spec`**（`datas` 在 :178）

```diff
     datas=[
         # 包含主题文件
         (os.path.join(project_root, 'theme.py'), '.'),
-        # 包含配置文件
+        # 包含配置文件（应用目录 = sys._MEIPASS，与 EXE 同级）
         (os.path.join(project_root, 'config.json'), '.'),
+        # P0-1: 包含版本文件。
+        # 运行时版本读取全部走 Path(__file__).parent../version.txt:
+        #   secureredact/__init__.py             -> _MEIPASS/version.txt
+        #   secureredact/ui/main_window/window.py -> _MEIPASS/version.txt
+        #   main.py (根 shim)                     -> _MEIPASS/version.txt
+        # 冻结后缺失会落 fallback "1.1.12"，与 EXE 版本资源(version_info.txt)不一致，
+        # 导致「窗口标题 / 关于窗口 / EXE 属性」三处版本号互相打架。
+        (os.path.join(project_root, 'version.txt'), '.'),
         # 包含 assets 目录（二维码图片等）
         (os.path.join(project_root, 'assets'), 'assets'),
```

**`packaging/macos/config/SecureRedact.spec`**（`datas` 在 :38）— 同样补 `version.txt`，
并额外补 `LICENSE`（见 §4.3）：

```diff
         (os.path.join(project_root, 'config.json'), '.'),
+        # P0-1: 包含版本文件 —— 冻结后 Path(__file__).parent../version.txt 必须存在，
+        # 否则落 fallback "1.1.12"，与 Info.plist 的 CFBundleVersion 不一致。
+        (os.path.join(project_root, 'version.txt'), '.'),
+        # GPL-3.0 分发要求: 许可证全文必须随 .app 一起分发
+        # (Windows 侧由 build_complete.bat / SecureRedact_Setup.iss 负责拷贝)
+        (os.path.join(project_root, 'LICENSE'), '.'),
```

**`packaging/windows/config/SecureRedact_windows_v2.spec`**（`datas` 在 :181）— 同上补 `version.txt`。

### 1.3 config.json 核实结论（**原本就齐全，无需补**）

三个 spec 均已包含 `(os.path.join(project_root, 'config.json'), '.')`：

| spec | config.json | 结论 |
|---|---|---|
| `SecureRedact_windows.spec:182` | ✅ dest `.` | 已存在 |
| `SecureRedact_windows_v2.spec:183` | ✅ dest `.` | 已存在 |
| `SecureRedact.spec:42` | ✅ dest `.` | 已存在 |

**并且与 lead 并发落地的配置层改造完全对齐**（我核对了他新写的 `secureredact/utils/config.py`）：

```python
# secureredact/utils/config.py::resolve_config_paths()
if frozen and meipass:
    candidate = os.path.join(meipass, "config.json")   # 冻结 one-folder: _MEIPASS/config.json
```

| 打包形态 | `sys._MEIPASS` | 运行时查找 | spec dest `.` 落点 | 对齐 |
|---|---|---|---|---|
| Windows one-folder | `dist/SecureRedact/` | `_MEIPASS/config.json` | `dist/SecureRedact/config.json` | ✅ |
| macOS .app | `Contents/Frameworks` | `_MEIPASS/config.json` | `Contents/Resources/config.json` + 符号链接进 `Contents/Frameworks/config.json` | ✅ |

> macOS 的交叉链接机制已从 PyInstaller 6.18.0 源码 `PyInstaller/building/osx.py` 逐行核实：
> `DATA` 类型条目落到 `Contents/Resources`（L476-479），顶层文件额外在 `Contents/Frameworks` 建同名符号链接（L487-508）。

### 1.4 一处被并发改动推翻的中间方案（重要）

我最初额外加了 `(project_root/'secureredact'/'config.json', 'secureredact')` 作为兜底。
**执行期间 lead 删除了 `secureredact/config.json`**（`git status` 显示 `D  secureredact/config.json`），
该条目会指向不存在的文件、导致 PyInstaller 直接报 *"Unable to find ..."* 中断打包 → **已移除**。

移除前我已核实该目录**不会遮蔽 PYZ 内的包**：`PyInstaller/loader/pyimod02_importers.py:262-290`
的 `PyiFrozenFinder.find_spec()` **先查 PYZ（:276）**，只有 PYZ 中没有才回落到磁盘 FileFinder（:282-286），
所以 `_MEIPASS/secureredact/` 目录不存在遮蔽风险。结论保留记录，供后续参考。

### 1.5 「包内配置目录」可行性已实测（万一将来恢复该文件）

`PyiFrozenFinder` 优先 PYZ 的结论同样意味着：即使将来恢复 `secureredact/config.json`，
把 `datas` 写成 dest `'secureredact'` 也不会让磁盘目录盖掉 PYZ 里的模块 —— 该方案技术可行。

---

## 2. T2 — macOS 图标检查与 Resources 路径假设

### 2.1 图标检查（100% 失败的 bug）

```diff
-# 检查图标文件
-if [ ! -f "${MACOS_DIR}/assets/SecureRedact.icns" ]; then
-    print_error "未找到图标文件: SecureRedact.icns"
+# 检查图标文件
+# 注意: 必须与 spec 中 BUNDLE(icon=...) 传入的路径保持一致。
+# packaging/macos/config/SecureRedact.spec 用的是项目根 assets/logo/macos/AppIcon.icns
+# （旧的 packaging/macos/assets/PrivacyGuard.icns 是重命名前的遗留副本，spec 未引用）。
+# 之前这里检查的是 assets/SecureRedact.icns —— 该文件从不存在，脚本会在此行 100% exit 1。
+APP_ICON="${PROJECT_ROOT}/assets/logo/macos/AppIcon.icns"
+APP_ICON_NAME="$(basename "${APP_ICON}")"
+if [ ! -f "${APP_ICON}" ]; then
+    print_error "未找到图标文件: ${APP_ICON}"
     exit 1
 fi
+print_info "应用图标: ${APP_ICON}"
```

事实核对：

| 路径 | 是否存在 | 谁在用 |
|---|---|---|
| `packaging/macos/assets/PrivacyGuard.icns` | ✅ 存在 | **无人引用**（重命名前遗留） |
| `assets/logo/macos/AppIcon.icns` | ✅ 存在 | **spec 的 `BUNDLE(icon=...)`** |
| `packaging/macos/assets/SecureRedact.icns` | ❌ **不存在** | 原脚本检查的就是它 |

### 2.2 `Contents/Resources/*.icns` 路径假设（原为错误）

原脚本把 `Contents/Resources/${APP_NAME}.icns`（= `SecureRedact.icns`）列为必需文件。
PyInstaller 6.18.0 `PyInstaller/building/osx.py:574` 明确：

```python
# Copy icns icon to Resources directory.
shutil.copyfile(self.icon, os.path.join(self.name, 'Contents', 'Resources', os.path.basename(self.icon)))
```

→ 落地文件名是 **icon 参数的 basename**，即 `AppIcon.icns`，**不是** `SecureRedact.icns`。
原检查即使脚本跑到这一步也会误判失败。

```diff
 REQUIRED_FILES=(
     "Contents/MacOS/${APP_NAME}"
     "Contents/Info.plist"
-    "Contents/Resources/${APP_NAME}.icns"
+    # PyInstaller 的 BUNDLE 会把 icns 原样拷贝到 Contents/Resources/<icns 文件名>
+    # (osx.py: shutil.copyfile(self.icon, .../Contents/Resources/basename(self.icon)))
+    # 因此这里必须是 AppIcon.icns，而不是 ${APP_NAME}.icns。
+    "Contents/Resources/${APP_ICON_NAME}"
 )
```

> `build_complete.sh` 里原有的 `Contents/Resources/assets/donate_qrcode.png` 检查**是正确的** ——
> `assets` 是 data-only 目录，按 osx.py 的目录级交叉链接规则落在 `Contents/Resources/assets/`，无需修改。

---

## 3. T3 — v2 spec 死代码警示（未删除文件）

在 `packaging/windows/config/SecureRedact_windows_v2.spec` 顶部加入 30 行警示块，说明：

1. **当前生效的是 `SecureRedact_windows.spec`**；
2. 三个构建入口（`build_complete.bat` / `2_build_exe.bat` / `3_build_with_setup.bat`）全部指向 v1 spec；
3. 本文件缺失 v1 已有的关键配置 —— 无 `secureredact.*` hiddenimports、`hookspath=[]`、`runtime_hooks=[]`、
   无 `secureredact/config.json` → 误启用即构建失败或运行期崩；
4. 图标来源与 v1 不同（此处 `packaging/windows/assets/icon.ico`，v1 为 `assets/logo/windows/app_icon.ico`），
   依赖收集也不等价（v2 收了 `cv2` binaries，v1 没有）→ **两边产物不等价**；
5. 维护约定：保留仅作历史参考；若要真正启用，需先与 v1 逐项对齐，再同步三个 .bat 的 spec 路径。

---

## 4. T4 — Inno Setup 版本默认值 + LICENSE

### 4.1 版本默认值对齐

```diff
-; 版本来源: 命令行 /DMyAppVersion 或默认值
+; 版本来源: 命令行 /DMyAppVersion 优先（由 3_build_with_setup.bat / 4_create_installer_only.bat
+; 从项目根 version.txt 读出后传入），缺失时回落到下面的默认值。
+; ⚠️ 默认值必须与项目根 version.txt 保持一致，否则安装包文件名 / AppVersion 会与
+;    EXE 版本资源(version_info.txt)、应用内显示的版本号对不上。
+;    当前 version.txt = 1.1.13

 #define MyAppName "SecureRedact"
 #define MyAppNameFull "SecureRedact 信息脱敏助手"
 #ifndef MyAppVersion
-  #define MyAppVersion "1.1.11"
+  #define MyAppVersion "1.1.13"
 #endif
```

**「命令行传入优先」本来就成立**：`#ifndef MyAppVersion` 语义即「未定义时才用默认值」，
而 `3_build_with_setup.bat:138` 与 `4_create_installer_only.bat:89` 都执行
`ISCC ... /DMyAppVersion=%VERSION%`，其中 `VERSION` 从根 `version.txt` 读出。
所以 `#define` 只是**兜底**，现在兜底值也正确了。

### 4.2 LICENSE —— 原先**完全没有**，已补齐两处

```diff
 [Setup]
 SetupIconFile=..\..\..\assets\logo\windows\app_icon.ico
 UninstallDisplayIcon={app}\{#MyAppExeName}
+; GPL-3.0 要求分发时附带许可证副本：安装向导直接展示许可证全文。
+; 该文件是项目根 LICENSE 的逐字节副本（GPL 原文不可改动），
+; 随包分发的副本见下方 [Files] 段（源为项目根 LICENSE）。
+LicenseFile=LICENSE.txt
@@
 [Files]
 Source: "..\scripts\launcher_wrapper.bat"; DestDir: "{app}"; Flags: ignoreversion
+; GPL-3.0 分发要求：安装目录必须包含许可证全文。
+; 源取项目根 LICENSE（唯一权威副本），落地名统一为 LICENSE.txt。
+Source: "..\..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
 ; 注意: 不要在任何共享系统文件上使用 "Flags: ignoreversion"
```

新增 `packaging/windows/config/LICENSE.txt`（GPL 原文要求逐字分发，**不能加任何头部注释**）：

```
根 LICENSE        sha256 = 633FD4DA62FF672331D65A8652E0AA13E7A93DE84BDF2E5D6197E2286278E036
config LICENSE.txt sha256 = 633FD4DA62FF672331D65A8652E0AA13E7A93DE84BDF2E5D6197E2286278E036
identical = True   (35825 bytes, 纯 ASCII, 无 BOM)
```

> Inno Setup 的 `LicenseFile` 要求文件带 `.txt/.rtf/.html` 后缀（根 `LICENSE` 无扩展名会被 ISCC 拒绝），
> 故采用「config 目录内放逐字节副本 + `[Files]` 从根 LICENSE 复制进安装目录」的组合：
> 向导展示的是副本，随包分发的是根 LICENSE（唯一权威源）。

### 4.3 macOS 侧的 LICENSE 缺口（顺带补齐）

macOS 此前**没有任何环节**把 LICENSE 放进 `.app` / DMG → GPL 分发要求在 macOS 平台同样不满足。
已通过 spec 的 datas 补齐（落 `Contents/Resources/LICENSE`），并在 `build_complete.sh` 增加产物校验。

---

## 5. T5 — 依赖锁定与校验

### 5.1 新增 `packaging/requirements-build.txt`

> **注意：根 `requirements.txt` 超出本任务的写入范围（根目录文件），我无法修改。**
> 该文件同时被 lead 占用（正在改配置层）。故在 `packaging/` 内建立构建期专用锁定清单，
> 并让三个构建脚本实际引用它（不是死文件）。**请 lead 把这两行同步回根 `requirements.txt`。**

```
pyinstaller==6.18.0
pyinstaller-hooks-contrib==2026.10
```

为什么必须锁 `pyinstaller-hooks-contrib`（实测证据链）：

1. `pyinstaller 6.18.0` 的 `Requires-Dist` 明确含 `pyinstaller-hooks-contrib>=2025.9`（硬依赖）；
2. `pyinstaller 6.18.0` **内置 353 个 hook，其中不含 jieba**；
3. `pyinstaller-hooks-contrib` 提供 `hook-jieba.py`，其全部内容就是 `collect_data_files('jieba')`
   → jieba 的 5 MB `dict.txt` **只能靠它进包**（已核对 `collect_data_files` 的排除规则：
   仅排除 `.py/.pyc` 与二进制扩展名，`.txt` 会被收集）；
4. hooks-contrib **未锁版本时**实际解析到 2026.10（随时间漂移）→ 构建不可复现；
5. 钩子缺失的后果是**静默降级**：`secureredact/pii/name_recognizer.py::_ensure_jieba()` 捕获所有异常后
   置空 → 中文姓名识别整块失效，**界面上无任何报错**。

版本选择依据：`pyinstaller==6.18.0` 发布于 2026-01-13，要求 `>=2025.9`；
实测 2025.9 与 2026.10 **均含** `hook-jieba.py` / `hook-docx.py` / `hook-onnxruntime.py` / `hook-pymupdf.py`。
锁 **2026.10** 可让「显式锁定」与「当前 pip 实际解析结果」一致，不改变现有构建行为。

### 5.2 三个构建脚本改为引用锁定清单

原先三处都是**不带版本约束**的 `pip install pyinstaller` —— 会把 `requirements.txt` 里
已固定的 `pyinstaller==6.18.0` 覆盖成当天最新版。

```diff
 # 1_init_environment.bat
-echo [4/5] Installing PyInstaller...
-pip install pyinstaller -q
-echo [OK] PyInstaller installed
+echo [4/5] Installing PyInstaller (pinned)...
+:: P0-5: 锁定构建期依赖版本。
+:: 之前的 "pip install pyinstaller" 不带版本约束，会把 requirements.txt 里
+:: 已固定的 pyinstaller==6.18.0 覆盖成当天最新版 -> 构建不可复现。
+:: 同时补上此前完全没被固定的 pyinstaller-hooks-contrib：jieba 的 5MB 词典
+:: (jieba/dict.txt) 只能靠它的 hook-jieba.py 进包，缺失会导致打包版
+:: 中文姓名识别静默失效（界面上无任何报错）。
+pip install -r "%PROJECT_DIR%\packaging\requirements-build.txt" -q
+if errorlevel 1 (
+    echo [ERROR] Failed to install pinned build dependencies
+    echo [HINT] Check packaging\requirements-build.txt
+    pause
+    exit /b 1
+)
+echo [OK] PyInstaller (pinned) installed
```

```diff
 # macOS build_complete.sh
-if ! python3 -c "import PyInstaller" 2>/dev/null; then
-    echo "[INFO] 当前环境未安装 PyInstaller，正在安装..."
-    python3 -m pip install pyinstaller
-fi
+# P0-5: 锁定构建期依赖版本(pyinstaller + pyinstaller-hooks-contrib)。
+# ...（注释同上）
+echo "[INFO] 校验/安装锁定版构建依赖..."
+python3 -m pip install -r "$PROJECT_DIR/packaging/requirements-build.txt"
```

`build_macos_app.sh` 同理改为无条件执行 `pip install -r .../requirements-build.txt`
（原逻辑「只在 PyInstaller 缺失时安装」会导致版本已存在但版本号不对时漏装）。

### 5.3 `verify_dependencies.py` 补 jieba + 6 项依赖 + hooks 存在性校验

**依赖清单从 11 项扩到 17 项**，新增的都是**实际运行时硬依赖**（原清单遗漏）：

| 新增项 | 谁在用 | 漏掉的后果 |
|---|---|---|
| `jieba` | `secureredact/pii/name_recognizer.py:137` (`jieba.posseg`) | **中文姓名识别整块失效**（静默） |
| `lxml` | bs4 / mammoth / python-docx 的解析后端 | 解析器降级或报错 |
| `shapely` | `rapidocr_onnxruntime/utils.py:25` (`from shapely.geometry import Polygon`) | **OCR 顶层 ImportError** |
| `pyclipper` | `rapidocr_onnxruntime/utils.py:23` | **OCR 顶层 ImportError** |
| `yaml` | `rapidocr_onnxruntime/utils.py:12` | **OCR 顶层 ImportError** |
| `six` | `rapidocr_onnxruntime/utils.py:24` | **OCR 顶层 ImportError** |

（后 4 项是我直接 grep 已安装的 `rapidocr_onnxruntime` 源码确认的顶层 import，非推测。）

新增 `check_packaging_hooks()`，校验：

1. `pyinstaller-hooks-contrib` 是否安装、版本是否 ≥ 锁定版本（低于则 FAIL，构建不可复现）；
2. 四个关键 hook 文件是否**真的存在于磁盘**：
   `_pyinstaller_hooks_contrib/stdhooks/hook-{jieba,docx,onnxruntime,pymupdf}.py`
   （包名是 `_pyinstaller_hooks_contrib`、hook 在 `stdhooks/` 子目录 —— 已从 wheel 布局核实）；
3. `jieba/dict.txt` 是否存在。

**双向实测**（本机未装 hooks-contrib → FAIL/exit 1；临时解包官方 wheel 注入 `sys.path` → 全 OK/exit 0）：

```
[FAIL] pyinstaller-hooks-contrib is not installed
[FAIL] _pyinstaller_hooks_contrib/stdhooks/hook-jieba.py not found
...
[OK] jieba/dict.txt
Verification failed. → exit=1

# 注入官方 wheel 后：
[OK] pyinstaller-hooks-contrib 2026.10
[OK] _pyinstaller_hooks_contrib/stdhooks/hook-jieba.py  (jieba dict.txt collection - ...)
[OK] _pyinstaller_hooks_contrib/stdhooks/hook-docx.py  ...
[OK] _pyinstaller_hooks_contrib/stdhooks/hook-onnxruntime.py ...
[OK] _pyinstaller_hooks_contrib/stdhooks/hook-pymupdf.py ...
[OK] jieba/dict.txt  (jieba Chinese dictionary (~5MB))
RESULT ok = True → exit=0
```

> 新增的打印文本**全部为 ASCII**：Windows 控制台默认 GBK（且 `build_complete.bat` 用 `chcp 936`），
> 中文会变乱码（实测首次实现时确实乱码，已改）。中文说明保留在注释里。

---

## 6. 额外新增：静态预检 + 产物校验（防回归）

### 6.1 `packaging/verify_spec_datas.py`（新增，AST 解析，不打包）

对三个 spec 逐个校验：

1. spec 是合法 Python（`ast.parse`）；
2. `datas` / `icon` 引用的**每个源路径都真实存在**（源缺失会让 PyInstaller 报 *"Unable to find ..."* 中断构建，
   在十几分钟的构建日志里极易漏看）；
3. `version.txt` 必须被打进应用目录（dest `.`）—— 否则运行时退化到陈旧 fallback；
4. `config.json` 必须被打进应用目录（dest `.`）—— 否则配置退化到 `DEFAULT_CONFIG`。

用 `ast` 解析而非正则，因此能正确处理 `datas=[...] + onnx_datas + ...` 的列表拼接形式。

**当前输出（exit=0）**：

```
  [OK] valid Python (ast.parse)
  [OK] datas theme.py                           -> .
  [OK] datas config.json                        -> .
  [OK] datas version.txt                        -> .
  [OK] datas assets                             -> assets
  [OK] icon  assets\logo\windows\app_icon.ico   -> -
  [OK] version.txt is packaged into the application directory
  [OK] config.json is packaged into the application directory
  ... (三个 spec 全过)
  [OK] All spec checks passed.
```

已接入三个构建脚本（构建前执行，失败即中止）：
`build_complete.bat`（Phase 3.2）、`build_complete.sh`（阶段 1）、`build_macos_app.sh`（步骤 1）。

### 6.2 构建后产物校验（把「静默退化」变成「构建失败」）

| 脚本 | 新增校验 |
|---|---|
| `build_complete.bat`（Phase 7） | `dist\SecureRedact\version.txt`、`dist\SecureRedact\config.json` 存在，否则 `VERIFY_FAIL=1` |
| `build_complete.sh`（阶段 4） | `.app` 内 `version.txt` / `config.json` / `LICENSE` 存在（同时查 `Contents/Resources` 与 `Contents/Frameworks`），否则 exit 1 |
| `build_macos_app.sh`（步骤 4） | 同上（`version.txt` / `config.json`） |

### 6.3 入口检查改为「二者皆可」（超出 T1–T5，但同源）

`build_complete.bat`（2 处）与 `1_init_environment.bat`（1 处）原本**硬检查根 `main.py` 存在**，
一旦 lead 完成 PR-B5 删除根 `main.py`，打包链会直接 `exit 1`。改为两者皆可：

```diff
-if not exist "%PROJECT_DIR%\main.py" (
+:: 入口文件：阶段 B5 收口后根 main.py 会被移除，入口迁到 secureredact\main.py，
+:: 因此这里两个都接受。
+if not exist "%PROJECT_DIR%\main.py" if not exist "%PROJECT_DIR%\secureredact\main.py" (
     echo [ERROR] Entry point not found (main.py or secureredact\main.py)
```

> 这是**纯放宽**（原来能过的现在还能过），不改变任何现有行为，只为 PR-B5 扫清打包链障碍。
> 注意：真正删除根 `main.py` 还需要先解决 `secureredact/main.py:107`、
> `secureredact/ui/main_window/handlers.py:381`、`setup_ui.py:40` 三处运行时 import（lead 的写入范围）。

---

## 7. 验收记录

| # | 命令 | 退出码 |
|---|---|---|
| 1 | `python -m compileall -q packaging` | **0** |
| 2 | `python -c "compile(open(f).read(), f, 'exec')"` × 3 spec | **0**（三份全部 OK） |
| 3 | `python packaging/verify_spec_datas.py` | **0**（All spec checks passed） |
| 4 | `bash -n` × 4 个 macOS 脚本 | **0**（4/4） |
| 5 | `python packaging/windows/scripts/verify_dependencies.py` | **1**（本机确实未装 pyinstaller/hooks-contrib —— 预期行为，见 §5.3） |
| 6 | `git status --short -- packaging` | 9 改 + 3 增，**全在 packaging/ 内** |

`bash -n` 的坑：这台 Windows 上的 `bash` 是 WSL 代理，直接 `bash -n <Windows 路径>` 会静默返回 exit=2
（**未改动的脚本同样如此**，说明是路径翻译问题而非脚本错误）。改用 `Get-Content -Raw | bash -n` 并剥离 CRLF 后
四个脚本全部 exit=0。已确认 macOS 脚本在仓库内是 `i/lf`（LF），工作区的 CRLF 只是 `core.autocrlf=true` 的转换，
macOS 上不受影响。

**未执行任何实际 PyInstaller 打包**（按约束）。

---

## 8. 写入范围核验

```
$ git status --short -- packaging
 M packaging/macos/config/SecureRedact.spec
 M packaging/macos/scripts/build_complete.sh
 M packaging/macos/scripts/build_macos_app.sh
 M packaging/windows/config/SecureRedact_Setup.iss
 M packaging/windows/config/SecureRedact_windows.spec
 M packaging/windows/config/SecureRedact_windows_v2.spec
 M packaging/windows/scripts/1_init_environment.bat
 M packaging/windows/scripts/build_complete.bat
 M packaging/windows/scripts/verify_dependencies.py
?? packaging/requirements-build.txt
?? packaging/verify_spec_datas.py
?? packaging/windows/config/LICENSE.txt
```

工作区里 `secureredact/**`、`tests/**`、`main.py`、`config.json` 的改动**均来自 lead 与 task-2 执行者**，
不是本任务产生的（本任务的写入严格限定在 `packaging/`）。

---

## 9. 需要 lead 接手的两件事

1. **把 `pyinstaller-hooks-contrib==2026.10` 同步回根 `requirements.txt`**
   （根文件超出我的写入范围）。建议同时把 `pyinstaller==6.18.0` 保留在原处，
   使「显式锁定」与 `packaging/requirements-build.txt` 一致。
2. **确认 `secureredact/config.json` 的删除已定案** —— 我已按「已删除」处理，
   三个 spec 的 config 打包路径改为**只依赖根 `config.json` → dest `.`**，
   与 lead 新写的 `resolve_config_paths()` 完全对齐。若该文件将来恢复，
   本报告 §1.5 给出了可行的 datas 写法。
