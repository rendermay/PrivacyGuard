# SecureRedact 打包发布与依赖健康度分析报告

> 分析对象：`G:\Project\SecureRedact\.agents\worktrees\dsh-3eb2fb3e-5817`
> 分析日期：2026-11-12
> 版本基准：`version.txt` = **1.1.13**（`1.1.13 - Name Context Injection`）
> 本报告为只读分析，未修改任何项目文件（仅新增本报告）。

---

## 0. 结论速览

| 维度 | 结论 |
|---|---|
| 打包链路可用性 | **可用但有断链**。Windows 主链（`build_complete.bat`）完整；macOS 的 `build_macos_app.sh` 因图标文件名错误 **100% 失败**；Windows v2 spec 是**无人引用的死代码** |
| 入口是否可切到 `secureredact.main` | **spec 层面已切（3/3 都指向 `secureredact/main.py`），但运行时仍强依赖根 `main.py`（3 处 import）→ PR-B5 尚不具备收口条件** |
| 依赖问题数 | **9 类**（缺失 3 / 多余 2 / 无上限 2 / 未固定 1 / 版本错位 1） |
| 配置健康度 | **严重**。运行时实际读 `secureredact/config.json`，而 spec 打包的是根 `config.json` → 打包后配置 100% 丢失；个人配置已进版本库 |
| 发布前必修项 | **11 项**（P0），建议项 **17 项**（P1） |
| LICENSE | **GPL-3.0 全文** 与商业闭源定位冲突，且安装器未附许可证 → 必须决策 |

---

## 1. 打包链路现状

### 1.1 目录与脚本清单

```
packaging/
├── README.md                                  # 索引（版本号 v1.1.11 陈旧）
├── DUAL_OCR_PACKAGING.md
├── windows/
│   ├── assets/icon.ico                        # 重命名前遗留副本
│   ├── config/
│   │   ├── SecureRedact_windows.spec          # ★ 实际生效的 spec（v1）
│   │   ├── SecureRedact_windows_v2.spec       # ✗ 死代码，无脚本引用
│   │   ├── SecureRedact_Setup.iss             # Inno Setup 安装器
│   │   ├── version_info.txt                   # 提交态 = 1.1.11（构建时自动重生成）
│   │   ├── hook-secureredact.py               # PyInstaller hook
│   │   └── runtime_hook_secureredact.py       # runtime hook
│   ├── docs/WINDOWS_BUILD_GUIDE.md
│   └── scripts/
│       ├── build_complete.bat                 # ★ 便携版主链
│       ├── 1_init_environment.bat
│       ├── 2_build_exe.bat
│       ├── 3_build_with_setup.bat             # 安装版主链
│       ├── 4_create_installer_only.bat
│       ├── generate_version_info.py           # version.txt → version_info.txt
│       ├── verify_dependencies.py             # 打包前依赖自检
│       ├── diagnose_onnxruntime.py
│       ├── launcher_wrapper.bat / emergency_launcher.bat
│       └── check_vcredist.bat
└── macos/
    ├── assets/PrivacyGuard.icns               # 重命名前遗留副本
    ├── config/SecureRedact.spec               # ★ 唯一 spec
    ├── config/entitlements.plist
    └── scripts/
        ├── build_complete.sh                  # ★ macOS 主链
        ├── build_macos_app.sh                 # ✗ 图标检查必失败
        ├── sign_macos_app.sh / notarize_macos_app.sh
```

> **CLAUDE.md 提到的 `SecureRedact_verify.spec` 在仓库中不存在**（全仓检索无此文件）。

### 1.2 Windows 链路（`build_complete.bat`，7 阶段）

```
Phase 1  环境检查  → venv_win/venv → version.txt → spec → assets\logo\windows\app_icon.ico → main.py ⚠
Phase 2  清理 dist/ + build/
Phase 3  verify_dependencies.py（缺依赖则中止）
Phase 3.5 generate_version_info.py（version.txt → version_info.txt）★
Phase 4  python -m PyInstaller --clean --noconfirm SecureRedact_windows.spec
Phase 5  拷贝 VC++ DLL / launcher_wrapper.bat / LICENSE→LICENSE.txt / README.md
Phase 6  清理 .gitignore/.project_info/tests/pip/__pycache__
Phase 7  验证 SecureRedact.exe + assets\donate_qrcode.png
Phase 8  Compress-Archive → releases\windows\SecureRedact-v<ver>-Windows-Portable.zip + SHA256
```

**优点**
- `generate_version_info.py` 在构建前自动生成版本资源 → EXE 属性里的版本号与 `version.txt` 天然同步（这是全项目唯一做对的版本同步机制）。
- 产物路径、校验和（SHA256）、LICENSE 随包分发均已实现。
- 打包前有 `verify_dependencies.py` 前置闸门。

**问题**

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| W1 | **硬检查根 `main.py` 存在** | `build_complete.bat:23, 109`；`1_init_environment.bat:79` | PR-B5 删除根 `main.py` 后打包脚本 **直接 exit 1**，构建链断裂 |
| W2 | `SecureRedact_windows_v2.spec` 无人引用 | — | 死代码；且 v2 spec **完全没有 secureredact hiddenimports**、`hookspath=[]`、`runtime_hooks=[]`，一旦被误启用即崩 |
| W3 | 两套图标源并存 | v1: `assets/logo/windows/app_icon.ico`；v2: `packaging/windows/assets/icon.ico` | 同一产品两个图标文件，易漂移 |
| W4 | `chcp 936`（GBK 代码页） | `build_complete.bat:5` | 中文构建日志在部分终端乱码 |
| W5 | 阶段编号错乱 | `Phase 2/8`→`[Phase 3/8]` | 可读性 |
| W6 | v1 spec 未收 `cv2` binaries | `SecureRedact_windows.spec:177` | 与 v2 spec 不一致（v2 有 `collect_dynamic_libs('cv2')`） |
| W7 | Inno Setup **未含 LICENSE** | `SecureRedact_Setup.iss` 无 `LicenseFile` 指令 | 见 `5.3 |

### 1.3 macOS 链路

**`build_complete.sh`**（推荐主链）— 结构与 Windows 对称，且 **spec 从 `version.txt` 动态读取版本号写入 Info.plist**（`CFBundleVersion` / `CFBundleShortVersionString`），是三份 spec 中唯一正确的版本处理。

**`build_macos_app.sh`** — 存在 **硬失败**：

```bash
# L92-95
if [ ! -f "${MACOS_DIR}/assets/SecureRedact.icns" ]; then
    print_error "未找到图标文件: SecureRedact.icns"
    exit 1
fi
```

实际文件是 `packaging/macos/assets/PrivacyGuard.icns`（重命名遗留）→ **该脚本在任何机器上都在此行退出**，永远走不到打包步骤。

另一处待验证的路径假设：

```bash
# L148
"Contents/Resources/${APP_NAME}.icns"   # 期望 SecureRedact.icns
```

而 spec 传入的是 `assets/logo/macos/AppIcon.icns` → PyInstaller 写入 `Contents/Resources/` 的 icns 文件名是否被改写为 `<AppName>.icns` 需实测（不同 PyInstaller 版本行为不同），**建议在真机验证一次**。

其余：签名走 `PRIVACYGUARD_CODESIGN_IDENTITY` 环境变量 → **旧品牌前缀**；未设置时退化为 `codesign --sign -` 临时签名（macOS Gatekeeper 会拦），`notarize_macos_app.sh` 未被 `build_complete.sh` 自动调用。

### 1.4 spec 硬编码路径与版本号清单

| 位置 | 硬编码内容 | 评估 |
|---|---|---|
| Win v1 spec `:25` / macOS spec `:15` | 注释 `# PrivacyApp (项目根目录)` | ✗ 重命名前遗留注释 |
| Win v1 spec `:287` | `icon=assets/logo/windows/app_icon.ico` | ✓ 文件存在 |
| Win v2 spec `:281` | `icon=packaging/windows/assets/icon.ico` | ✓ 存在，但与 v1 不同源 |
| macOS spec `:145` | `icon=assets/logo/macos/AppIcon.icns` | ✓ 存在 |
| macOS spec `:146,155` | `bundle_identifier='com.secureredact.app'` | ✓ 与脚本一致 |
| 三个 spec 的 `project_root` 推导 | 相对 `SPEC` 上溯 3 层 | ✓ **无开发机绝对路径**，可移植 |
| `packaging/macos/assets/PrivacyGuard.icns` | 旧品牌名 | ✗ 冗余副本 |
| `packaging/windows/assets/icon.ico` | — | ✗ 冗余副本 |
| `assets/logo/linux/privacyguard_*.png` (8 个) | 旧品牌名 | ✗ 冗余 |

**结论：spec 内没有绝对路径污染**，全部相对推导 —— 这一点是健康的。

### 1.5 资源打包完整性

| 资源 | Win v1 | Win v2 | macOS | 评价 |
|---|---|---|---|---|
| `theme.py` | datas `.` + hiddenimport `theme` | datas `.` + hiddenimport `theme` | 同 | ⚠️ **双份**：模块进 PYZ，数据副本进 bundle 根，是死重量 |
| `config.json`（根） | datas `.` | datas `.` | datas `.` | ❌ **位置错**（见 `4） |
| `assets/`（含 donate/wx 二维码、logo 全套） | ✓ `assets` | ✓ | ✓ | ✓ 完整 |
| `version.txt` | ✗ **未打包** | ✗ | ✗ | ❌ **必修** |
| `secureredact/config.json` | ✗ | ✗ | ✗ | ❌ **必修** |
| `secureredact/ui/styles/**` 外部 QSS/字体 | — | — | — | ✓ **无遗漏**（样式全部由 `tokens.py`/`glass.py` 运行时生成，包内零非 py 文件） |
| `secureredact` 包数据 | `collect_data_files('secureredact')`（hook 内） | — | — | ✓ 空集，无遗漏 |

**`version.txt` 未打包是最高优先级缺陷**：3 处版本读取（`main.py:143`、`secureredact/__init__.py:14`、`secureredact/ui/main_window/window.py:117`）全部走 `Path(__file__).parent…/version.txt` 且 fallback 硬编码 `"1.1.12"`。冻结后 `version.txt` 不存在 → **打包版窗口标题与"关于"窗口显示 1.1.12**，而 EXE 属性是 1.1.13、`version.txt` 是 1.1.13 → **三处版本号互不相同**。

### 1.6 版本号全链路同步矩阵

| 位置 | 当前值 | 与 `version.txt`(1.1.13) |
|---|---|---|
| `version.txt` | 1.1.13 | ✅ 唯一基准 |
| `secureredact/__init__.py` | 读 version.txt / fallback `"1.1.12"` | ⚠️ fallback 陈旧 |
| `main.py` (根 shim) | 读 version.txt / fallback `"1.1.12"` | ⚠️ fallback 陈旧 |
| `secureredact/ui/main_window/window.py` | 读 version.txt / fallback `"1.1.12"` | ⚠️ fallback 陈旧 + **打包后必现 1.1.12** |
| `secureredact/utils/config.py` `DEFAULT_CONFIG["version"]` | `"1.0"` | ⚠️ 陈旧 |
| `packaging/windows/config/version_info.txt`（提交态） | **1.1.11** | ❌（构建时自动覆盖为 1.1.13） |
| `SecureRedact_Setup.iss` `#define MyAppVersion` | **"1.1.11"** | ❌（`3_build_with_setup.bat:138` 用 `/DMyAppVersion=$VERSION%` 覆盖，但 fallback 仍是陈旧值） |
| `packaging/README.md:13` | v1.1.11 | ❌ |
| `docs/packaging/README.md:9-10` | v1.1.11 / `37.7.4 - Release Audit and Final Polish` | ❌ 且"版本标识"与 `packaging/README.md` 的 `1.1.11 - Whitelist Span Trim` **互相矛盾** |
| `docs/packaging/windows-packaging-guide.md` / `macos-packaging-guide.md` | — | ❌ 含开发机路径（见 `5.4） |
| `README.md:15` | v1.1.11 / `37.7.6 - Full Convergence Remediation` | ❌ |
| `README_EN.md:5-7` | v1.1.11 / `37.7.6` | ❌ |
| `docs/current/STATUS.md:4` | 1.1.11 | ❌ |
| `docs/current/PROJECT_STRUCTURE.md:133` | 1.1.11 | ❌ |
| `docs/current/RECOVERY_GUIDE.md:36,99` | 1.1.11 | ❌ |
| `user-guides/用户使用手册.md`（多处，含 `:971`） | v1.1.11 | ❌ |
| `AGENTS.md` | 1.1.11 | ❌（与 CLAUDE.md 1.1.13 **不一致**） |
| `CLAUDE.md` | v1.1.13 | ✅ |
| `CHANGELOG.md` | 1.1.13 | ✅ |
| macOS Info.plist `CFBundleVersion` | 构建时读 version.txt | ✅ |

**统计：19 处版本引用中仅 4 处同步，11 处停留在 1.1.11，3 处 fallback 停在 1.1.12，1 处（config DEFAULT）停在 1.0。**

---

## 2. 入口一致性核查

### 2.1 入口对照表

| 位置 | 当前入口 | 判定 |
|---|---|---|
| `packaging/windows/config/SecureRedact_windows.spec:175` | `[os.path.join(project_root, 'secureredact/main.py')]` | ✅ **已切换** |
| `packaging/windows/config/SecureRedact_windows_v2.spec:167` | `secureredact/main.py` | ✅（死代码） |
| `packaging/macos/config/SecureRedact.spec:35` | `secureredact/main.py` | ✅ **已切换** |
| `start_app.sh` | `python -m secureredact.main` | ✅ **已切换** |
| `main.py`（根） | `if __name__=='__main__': from secureredact.main import main; sys.exit(main())` | ✅ shim 已转发 |
| `secureredact/main.py` | `def main(argv)` + `if __name__ == "__main__": sys.exit(main())` | ✅ 具备入口函数与 guard |
| `secureredact/cli.py:246` | `if __name__ == "__main__"` | ✅ 有 CLI 入口但无 console_scripts |
| `packaging/windows/scripts/build_complete.bat:23,109` | **硬检查根 `main.py` 存在** | ❌ 与 B5 冲突 |
| `packaging/windows/scripts/1_init_environment.bat:79` | **硬检查 `main.py` 存在** | ❌ 与 B5 冲突 |
| CLAUDE.md 所称 `secureredact.main:main` | 仓库**无** `pyproject.toml`/`setup.py`/`entry_points` | ⚠️ **语法上无载体**：PyInstaller `Analysis()` 只接受脚本路径，不接受 `module:function`；无 `pyproject.toml` 就没有 console_scripts |

**结论 1：spec / `start_app.sh` 层面入口已切换到 `secureredact` 包，但形式是"文件路径 `secureredact/main.py`"而非 CLAUDE.md 所述的 `secureredact.main:main`。**

### 2.2 PR-B5 收口阻塞项：根 `main.py` 仍是运行时硬依赖

全仓检索（排除 tests/）确认 **3 处生产代码 import 顶层 `main` 模块**：

| # | 位置 | 代码 | 影响 |
|---|---|---|---|
| B1 | `secureredact/main.py:107` | `from main import init_ocr_engine` | `PRIVACYGUARD_PRELOAD_OCR=true` 时启动即 ImportError（已被 try/except 捕获 → 仅警告，不致命） |
| B2 | `secureredact/ui/main_window/handlers.py:381` | `from main import OCRWorker, WordWorker` | ❌ **致命** — OCR/Word 扫描路径直接崩 |
| B3 | `secureredact/ui/main_window/setup_ui.py:40` | `from main import (...)` | ❌ **致命** — 主窗口构建期崩 |

> **判定：打包链路"已指向 secureredact"，但"入口可收口"尚不成立。** 删除根 `main.py` 会让 UI 在运行期 ImportError。
> 附带效应：PyInstaller 静态分析会因 B1/B2/B3 把根 `main.py` 打进包内成为顶层模块 `main`，与 `secureredact.main` 不冲突，但让"根 `main.py` 已死"的假设不成立。

### 2.3 spec 的 hiddenimports / datas 覆盖度（切到 `secureredact.main:main` 的前置条件逐项核对）

| 资源/模块 | v1 spec | v2 spec | macOS spec | 覆盖度 |
|---|---|---|---|---|
| `secureredact` 顶层 | ✅ 手工 + collect_submodules | ❌ **完全缺失** | ✅ | v1/macOS ✓ / v2 ✗ |
| `secureredact.utils.*` | ✅ | ❌ | ✅ | ✓ |
| `secureredact.ocr.*` | ✅ | ❌ | ✅ | ✓ |
| `secureredact.workers.*` | ✅（缺 `word_batch_replace_worker`） | ❌ | ✅（同上缺） | ⚠️ 靠 collect_submodules 兜底 |
| `secureredact.redaction.*` | ❌ 手工列表**未列**（hit_ref / doc_hash / override_store / rules_loader / whitelist_split / word_rules / black_white_list_store） | ❌ | ❌ | ⚠️ 仅靠 `collect_submodules` |
| `secureredact.pii.*`（name_context / name_recognizer） | ❌ 未列 | ❌ | ❌ | ⚠️ 仅靠 `collect_submodules` |
| `secureredact.ui.main_window.*`（12 个模块） | ❌ 未列 | ❌ | ❌ | ⚠️ 仅靠 `collect_submodules` |
| `secureredact.ui.dialogs.*` / `ui.settings.*` / `ui.utils.*` | ❌ 未列 | ❌ | ❌ | ⚠️ **命名空间包**（无 `__init__.py`）→ collect_submodules 递归行为需实测 |
| `secureredact.api` / `secureredact.cli` | ❌ 未列 | ❌ | ❌ | ⚠️ 仅靠 collect_submodules |
| `secureredact.utils.masking` | ❌ 未列 | ❌ | ❌ | ⚠️ |
| `theme.py` | ✅ datas + hiddenimport | ✅ | ✅ | ✓（双份冗余） |
| `assets/` | ✅ | ✅ | ✅ | ✓ |
| `version.txt` | ❌ | ❌ | ❌ | ❌ **必修** |
| `secureredact/config.json` | ❌ | ❌ | ❌ | ❌ **必修** |
| `hookspath` / `runtime_hooks` | ✅ 均指向 `packaging/windows/config` | ❌ `hookspath=[]` `runtime_hooks=[]` | ❌ `hookspath=[]` `runtime_hooks=[]` | ⚠️ macOS 不用 `hook-secureredact.py`（靠 collect_submodules 兜底） |
| `jieba` / `mammoth` | ❌ 未声明 | ❌ | ❌ | ⚠️ 依赖 hooks-contrib 与静态分析兜底（见 `3） |

**另一处隐式约束**：`theme.py` 位于**仓库根、不在 `secureredact` 包内**，而 `secureredact/ui/**` 下 **10 个模块** 依赖 `from theme import Theme`：

```
secureredact/ui/dialogs/image_list.py:113     secureredact/ui/main_window/window.py:58,970
secureredact/ui/dialogs/batch_replace.py:30    secureredact/ui/main_window/density.py:11
secureredact/ui/main_window/setup_ui.py:28     secureredact/ui/main_window/workbench.py:19
secureredact/ui/main_window/toolbar.py:18      secureredact/ui/main_window/dialog.py:26,1948
secureredact/ui/utils/density.py:27
```

→ PR-B5 移除根 `main.py` 时，**`theme.py` 必须继续留在仓库根**（spec 的 `pathex` 含 `project_root`，可解析），否则需一次性改这 10 处 import 把 `theme` 迁入 `secureredact/ui/styles/`。**该约束必须写进 B5 收口计划。**

### 2.4 入口切换就绪度结论

| 判定项 | 状态 |
|---|---|
| spec 入口指向 `secureredact/main.py` | ✅ 已完成（3/3） |
| `start_app.sh` 指向 `python -m secureredact.main` | ✅ 已完成 |
| `secureredact/main.py` 具备 `main()` + `__main__` guard | ✅ |
| spec hiddenimports 覆盖 secureredact 全部子包 | ⚠️ 部分靠 `collect_submodules` 兜底；v2 spec 完全缺失 |
| spec datas 覆盖 `theme.py` | ✅ |
| spec datas 覆盖 `assets` | ✅ |
| spec datas 覆盖 `version.txt` | ❌ **缺** |
| spec datas 覆盖运行时配置文件 | ❌ **缺且位置错** |
| 根 `main.py` 可安全删除 | ❌ **不可**（3 处运行时 import） |
| 打包脚本不再依赖根 `main.py` | ❌ **不满足**（2 个 .bat 硬检查） |
| `secureredact.main:main` 作为字符串入口可用 | ⚠️ 无 `pyproject.toml` 载体 |

> **综合判定：打包链路"可以指向 secureredact"（事实上已经指向），但"可以移除 main.py 并以 `secureredact.main:main` 收口"的条件尚不满足。** 缺口集中在 3 处残留 import + 2 个 .bat 的 `main.py` 硬检查 + spec 缺 `version.txt`/`config.json`。

---

## 3. 依赖对照表

### 3.1 全量对照

| 依赖 | `requirements.txt` | 代码实际 import | `verify_dependencies.py` | spec hiddenimports | 判定 |
|---|---|---|---|---|---|
| **PyMuPDF** (`fitz`) | `==1.27.1` | ✅ fitz（main / mixed_pdf / handlers / pdf_render / window / image_merge / ocr_worker / api） | ✅ | ✅ `fitz` / `fitz.fitz` | ✅ 一致 |
| **rapidocr-onnxruntime** | `==1.2.3` | ✅ rapidocr_onnxruntime（main / ocr.rapidocr） | ✅ | ✅ | ✅ 一致 |
| **onnxruntime** | `>=1.24.1` ⚠️**无上限** | ✅ | ✅ | ✅ + hooks-contrib `hook-onnxruntime.py` | ⚠️ 无上限 |
| **mammoth** | `==1.11.0` | ✅ mammoth（ui/main_window/word_preview.py:111） | ✅ | ❌ 未声明 | ⚠️ 靠静态分析兜底，建议显式声明 |
| **PyQt6** | `==6.10.2` | ✅ | ✅ | ✅ + 内置 hooks | ✅ |
| **PyQt6-WebEngine** | `==6.10.0` | ✅ `QtWebEngineWidgets` | ✅ | ✅ | ⚠️ 与 `PyQt6-Qt6==6.10.2` **版本错位**（6.10.0 vs 6.10.2） |
| **jieba** | `==0.42.1` | ✅ `jieba.posseg`（pii/name_recognizer.py:137） | ❌ **未纳入** | ❌ 未声明 | ⚠️ **高风险**：无 PyInstaller 内置 hook，靠 `pyinstaller-hooks-contrib>=2025.9` 的 `hook-jieba.py`；失败时 `_ensure_jieba` 捕获异常 → **静默降级为"无人名识别"，无任何用户可见报错** |
| **python-docx** | `==1.2.0` | ✅ docx | ✅ | ✅ `docx` | ✅ |
| **beautifulsoup4** | `==4.14.3` | ✅ bs4（10+ 文件） | ✅ | ✅ 完整导入链 | ✅ |
| **lxml** | `==6.0.2` | （bs4 / mammoth / docx 依赖） | ❌ 未纳入 | ✅ `lxml`/`lxml.etree` | ⚠️ |
| **opencv-python** | `==4.13.0.92` | ✅ cv2（main / mixed_pdf / ocr_worker / window） | ✅ | ✅ `cv2`（v1 spec 未收 binaries） | ⚠️ |
| **pillow** | `==12.1.1` | ✅ PIL | ✅ | ✅ | ✅ |
| **shapely** | `==2.1.2` | ❌ 无直接 import | ❌ | ❌ | ℹ️ rapidocr 传递依赖 |
| **pyclipper** | `==1.4.0` | ❌ 无直接 import | ❌ | ❌ | ℹ️ rapidocr 传递依赖 |
| **PyYAML** | `==6.0.3` | ❌ | ❌ | ❌ | ℹ️ rapidocr 传递依赖 |
| **six** | `==1.17.0` | ❌ | ❌ | ❌ | ℹ️ 传递依赖 |
| **protobuf** | `==6.33.5` | ❌ | ❌ | ❌ | ℹ️ onnxruntime 传递依赖 |
| **sympy / mpmath** | `==1.14.0` / `==1.3.0` | ❌ | ❌ | ❌ | ℹ️ 传递依赖 |
| **flatbuffers** | `==25.12.19` | ❌ | ❌ | ❌ | ℹ️ 传递依赖 |
| **cobble** | `==0.1.4` | ❌ | ❌ | ❌ | ℹ️ 传递依赖 |
| **packaging** | `==26.0` | ❌ | ❌ | ❌ | ℹ️ PyInstaller 自身依赖 |
| **psutil** | `>=5.9.0` ⚠️**无上限** | ❌ **无任何 import** | ❌ | ❌ | ❌ **多余 + 无上限** |
| **pyinstaller** | `==6.18.0` | — | — | — | ⚠️ 其硬依赖 `pyinstaller-hooks-contrib>=2025.9` **未在 requirements 固定** |
| **scikit-learn** | ❌ **缺失** | ❌ 无 import | ❌ | ⚌ v2 spec 有 `sklearn`/`sklearn.utils._typedefs` | ❌ **spec 有 / requirements 无** → 干净环境构建产生 warning |
| **pytest / pytest-cov / pytest-qt** | ❌ **缺失**（CI 手动装） | tests ✅ | — | — | ⚠️ 建议拆 `requirements-dev.txt` |
| **reportlab** | ❌ **缺失** | tests/create_test_pdf.py | — | — | ℹ️ 测试用 |

### 3.2 问题汇总（9 类）

| 类别 | 数量 | 明细 |
|---|---|---|
| **缺失** | 3 | ① `pyinstaller-hooks-contrib` 未在 requirements 出现/未固定（实际靠 pyinstaller 传递安装）② `pytest`/`pytest-cov`/`pytest-qt` 未入依赖清单 ③ `scikit-learn` 被 v2 spec 引用却不在 requirements |
| **多余** | 2 | ① `psutil`（代码零 import，且无上限）② v2 spec 的 `sklearn`/`sklearn.utils._typedefs` hiddenimports |
| **无上限** | 2 | `onnxruntime>=1.24.1`、`psutil>=5.9.0` |
| **未固定** | 1 | `pyinstaller-hooks-contrib`（实际解析到 2026.10，**构建不可复现**） |
| **版本错位** | 1 | `PyQt6-WebEngine==6.10.0` vs `PyQt6-Qt6==6.10.2` |
| **声明不完整** | — | `mammoth`/`jieba`/`lxml`/`shapely`/`pyclipper` 未进 `verify_dependencies.py` 的自检清单 |
| **传递依赖被显式列出** | — | cobble / flatbuffers / sympy / mpmath / protobuf / PyYAML / six / packaging 共 8 项，建议注释标注来源 |

### 3.3 PyInstaller 依赖图谱的实测结论（基于 `pyinstaller==6.18.0` 官方 wheel）

- `pyinstaller 6.18.0` 的 `Requires-Dist` 明确包含 **`pyinstaller-hooks-contrib>=2025.9`**（硬依赖，非可选）。
- `pyinstaller 6.18.0` **内置 353 个 hook**，其中**不含** `jieba`/`mammoth`/`cv2`/`lxml`/`bs4`/`rapidocr`。
- `pyinstaller-hooks-contrib`（当前 2026.10，691 个 hook）**含** `hook-jieba.py`、`hook-docx.py`、`hook-lxml.py`、`hook-onnxruntime.py`、`hook-pymupdf.py`、`hook-shapely.py`、`hook-sklearn.py`。
  → **jieba 的 `dict.txt`（5.0 MB）依赖 hooks-contrib 的 `hook-jieba.py` 才能进包**。该包版本未固定 → 一旦 hooks-contrib 变更收集策略，jieba 会在打包版**静默失效**（姓名识别整块失效，无报错）。**这是本次依赖审查的最高风险单点。**
- `mammoth` **无 hook**，但其包内**无数据文件、无 pkg_resources 调用** → 纯模块收集即可，风险低。

### 3.4 开发环境与 requirements 的实际偏差（实测 `pip list`）

| 包 | requirements | 本机实测 | 偏差 |
|---|---|---|---|
| numpy | 2.4.2 | 2.3.1 | ❌ |
| PyQt6 / PyQt6-Qt6 | 6.10.2 | 6.11.0 / 6.11.1 | ❌ |
| PyMuPDF | 1.27.1 | 1.26.4 | ❌ |
| lxml | 6.0.2 | 5.3.2 | ❌ |
| mammoth | 1.11.0 | 1.12.1 | ❌ |
| onnxruntime | >=1.24.1 | 1.28.0 | ⚠️ |
| opencv-python | 4.13.0.92 | **4.6.0.66 + opencv-contrib-python 4.10.0.84 并存** | ❌ **两个 cv2 提供者冲突** |
| pyinstaller | ==6.18.0 | **未安装** | ❌ |
| scikit-learn | （无） | 1.4.0 | ❌ 多余 |
| scikit-image | （无） | 0.25.2 | ❌ 多余 |

→ **开发环境完全不可由 `requirements.txt` 复现**，且存在 `opencv-python` 与 `opencv-contrib-python` 双提供者的 `cv2` 冲突（打包结果不可预测）。

---

## 4. 配置健康度

### 4.1 三个配置文件的真实关系（实测）

| 文件 | 叶子键数 | git 跟踪 | 运行时角色 |
|---|---|---|---|
| `config.json`（根） | 123 | ✅ 已跟踪 | ❌ **运行时根本不读**（但被 spec 打包） |
| `secureredact/config.json` | 76 | ✅ 已跟踪 | ✅ **运行时实际读取** |
| `config.json.template` | 90 | ✅ 已跟踪 | 模板（供用户复制） |

**根因**（`secureredact/utils/config.py:641`）：

```python
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.json')
#  <root>/secureredact/utils  + '..' + 'config.json'  →  <root>/secureredact/config.json
```

实测输出：

```
SimpleConfig path = ...\secureredact\utils\..\config.json
has blacklist   = None                      ← 根 config.json 里的 ["0432"] 读不到
has whitelist   = ['盖章','吉铁','丰满区','全能王','甲方',...]   ← 来自 secureredact/config.json
```

**三个后果**

1. **打包后配置 100% 丢失**：spec 把根 `config.json` 放进 `_internal/config.json`，而运行时找的是 `_internal/secureredact/config.json` → 不存在 → 只剩代码内 `DEFAULT_CONFIG` 兜底（用户白名单 / 黑名单 / 扫描档位 / box_adjust_ratio / 永久 override 全部消失）。
2. **打包后设置无法保存**：`config.save()` 写向 `_internal/secureredact/config.json`；装在 `C:\Program Files` 下无写权限 → `os.replace` 抛 `PermissionError` → 被 catch 后仅打印 → **用户设置静默丢失**。
3. **污染版本库**：运行时把用户配置写进 `secureredact/config.json` —— 一个 **git 跟踪的包内文件**；每次运行应用都会脏化 git 工作区。

### 4.2 `.gitignore` 判定

| 检查项 | 结果 |
|---|---|
| `config.json` 是否被忽略 | ❌ **否**（`.gitignore` 无相关规则），且 **已被 git 跟踪** |
| `secureredact/config.json` 是否被忽略 | ❌ **否**，且已被跟踪 |
| 已提交的个人数据 | ✅ 确认存在：根 `config.json` 的 `redaction.blacklist = ["0432"]`；根与包内 config 的 `redaction.whitelist = ["盖章","吉铁","丰满区","全能王","甲方","乙方","丙方","丁方","戊方"]`（"吉铁"/"丰满区"/"全能王" 明显是个人词条） |
| `*.spec` 规则 | ⚠️ `.gitignore:27` 的 `*.spec` **会忽略所有 spec 文件**。现有 3 个 spec 是历史 force-add 才入库的（`git check-ignore --no-index` 确认仍匹配）。**今后任何新增 / 改名 spec 会被静默忽略**——包括 CLAUDE.md 里提到的 `SecureRedact_verify.spec` |

> **建议规则**：在 `.gitignore` 中补 `!packaging/**/config/*.spec`（或 `!packaging/**/*.spec`）作为例外。

### 4.3 `ConfigManager` 与 `SimpleConfig` 并存且行为不一致

```
secureredact/utils/config.py
├── ConfigManager  (L195-610)   高级单例：DEFAULT_CONFIG 合并 / validate() / on_change() / reload() / export_template()
├── get_config() / get_config_value()  (L613-621)   ← 生产代码无调用方
├── SimpleConfig   (L628-772)   低阶：扁平 dict + dot-path / 原子写(tmp+replace) / 字段保护合并
└── config = SimpleConfig()      (L772)   ★ 运行时唯一使用的 singleton
```

| # | 不一致点 | `ConfigManager` | `SimpleConfig` | 运行时影响 |
|---|---|---|---|---|
| C1 | **配置路径** | 应用目录 `config.json`；不可写则回退 `~/.secureredact/config.json` | 固定 `secureredact/config.json`，**无回退** | ❌ 打包版必然写到只读位置 |
| C2 | **schema 校验** | `validate()`（窗口尺寸 / 扫描档位 / 偏移范围 / 规则完整性） | 无 | ❌ 非法配置无人拦截 |
| C3 | **变更监听** | `on_change()` + `reload()` | 无 | ❌ 设置中心改值无统一事件 |
| C4 | **DEFAULT_CONFIG 覆盖面** | 无 `enable_hit_override`/`overrides.permanent`/`name_context`/`whitelist_trim_only`/`blacklist`/`whitelist` | 在 `load()` 里用 `setdefault` 补 | ⚠️ 两套默认值逻辑重叠且不等价 |
| C5 | **默认扫描档位** | `DEFAULT_CONFIG` = 1.5 | 磁盘根 config.json = 1.5 | ✅ 一致 |
| C6 | **box_adjust_ratio** | `DEFAULT_CONFIG` = 0.0 | 磁盘 config.json = 0.5 | ⚠️ 不一致（磁盘覆盖代码默认） |
| C7 | **规则 pattern 覆盖语义** | 直接以磁盘为准 | `load()` 强制回写 `mask_*`，且当"代码 pattern 更长"时**覆盖磁盘 pattern**（`config.py:678-697`） | ⚠️ 用户在设置中心改 pattern 可能被静默还原 |
| C8 | **规则来源层级** | 1 层 | 磁盘 → SimpleConfig.load 强制覆盖 → `rules_loader._v113_apply_rule_overrides` 再强制代码默认 | ⚠️ **三层规则来源**，语义复杂、易漂移 |
| C9 | `version` 字段 | `DEFAULT_CONFIG["version"]="1.0"` | 同 | ⚠️ 与 `version.txt` 无关 |
| C10 | 生产使用 | ❌ 无调用方（仅单测） | ✅ 唯一生效 | ⚠️ 两套配置系统并存 = 双维护成本 |

### 4.4 `config.json.template` 键差异（实测：40 缺 / 7 多 / 6 值不一致）

**模板缺失（40 个叶子键）**

- 整条规则缺失：**地址（含门牌号）**、**固定电话**、**法定代表人**、**公司名**（各 7 个字段）
- `统一社会信用代码` 缺 `mask_mode`/`mask_keep_prefix`/`mask_keep_suffix`/`mask_char`
- `redaction.enable_name_recognition`、`redaction.enable_hit_override`、`redaction.overrides.permanent`、`redaction.whitelist_trim_only`
- `redaction.name_context._comment`、`redaction.name_context.extra_tokens`
- `redaction.blacklist`、`redaction.whitelist`
- `redaction.default_rules.印章` 的 mask 字段

**模板多出（7 个叶子键）— 全是死配置**

- `_comment`（顶层说明，正常）
- `redaction.precise_locator.description`（描述字段，无害）
- **`redaction.seal_detection.*` 整块**（`enabled`/`description`/`method`/`min_red_ratio`/`min_circularity`）→ **全仓检索确认：代码中无任何位置读取 `redaction.seal_detection.*`**；印章检测实际走 `pattern == "__SEAL_DETECTION__"` 哨兵 + `seal_detection_enabled` 运行时参数（`handlers.py:420`）。模板里的这块是**误导性死配置**。

**值不一致（6 处）**

| 键 | `config.json` | `config.json.template` |
|---|---|---|
| `redaction.replacement_text` | `"*"` | `"[已脱敏]"` |
| `redaction.scan.default_level` | `1.5` | `1.0` |
| `redaction.offset.x_range` | `[-20, 50]` | `[-20, 20]` |
| `redaction.precise_locator.enabled` | `true` | `false` |
| `ocr.box_adjust_ratio` | `0.5` | `0.0` |
| `redaction.default_rules.{日期时间, 统一社会信用代码}.description` | 文案 A | 文案 B（略） |

**模板整体缺失**：`app.window.*`、`security.*`、`ui.*`、`advanced.*`、`ocr.*` 大部分、`version`、`app.name`、`app.feedback_url` → 用模板初始化出的配置缺窗口尺寸、安全策略等默认值。模板也**未标注哪些键用户可改、哪些是代码强制**。

---

## 5. 发布准备度检查清单

### 5.1 版本号一致性

见 `1.6 矩阵。**结论：19 处引用中 15 处不同步**，核心缺陷是 spec 未打包 `version.txt`（导致打包版运行时显示 1.1.12）。

### 5.2 README 与 user-guides 新旧程度

| 文件 | 状态 |
|---|---|
| `README.md` | v1.1.11 / `37.7.6 - Full Convergence Remediation` / 最后更新 2026-05-16 → **落后 2 个版本**；但正文已含 PR-B0 入口迁移提示（**局部更新、版本头未更新**的典型半更新状态）；release 链接指向 `github.com/lizilaywer/SecureRedact/releases/tag/v1.1.11` |
| `README_EN.md` | 同上；**另有批量替换事故**（见下） |
| `user-guides/用户使用手册.md`（28.9 KB） | 全文 v1.1.11（`:56`、`:105`、`:135`、`:173`、`:188`、`:971`）；**changelog 段把 10+ 个不同日期 / 内容的发布全部标成 "v1.1.11"**（`37.x → 1.1.x` 改名时只替换了前缀，编号体系塌陷）；下载文件名仍写 `SecureRedact-v1.1.11-macOS.dmg` / `-Setup.exe` |
| `docs/packaging/README.md` | v1.1.11 + `37.7.4`（与 `packaging/README.md` 的 `1.1.11 - Whitelist Span Trim` **互相矛盾**）；末行"最后更新：2026-03-18" |
| `packaging/README.md` | v1.1.11；含"2026-03-18 本轮同步内容"整节历史流水 |
| `docs/current/STATUS.md` | 基线 1.1.11；**`STATUS.md:30` 称 "config.json 为 2.0，测试期望 1.5" 已过时**（实测 `config.json` 现为 1.5）→ CLAUDE.md 里"已知既有失败 2 项"的描述同样过时 |
| `docs/current/PROJECT_STRUCTURE.md` | 1.1.11 |
| `docs/current/RECOVERY_GUIDE.md` | 1.1.11 |
| `AGENTS.md` vs `CLAUDE.md` | **同一份 agent 指南的两个版本**（1.1.11 vs 1.1.13），内容已明显分叉（AGENTS.md 完全没有人工干预 / hit override / PR-B0 章节） |
| `CHANGELOG.md` | ✅ 1.1.13，最新 |

**批量替换事故（必修）**

```
README_EN.md:169
- This project is licensed under the GNU General Public License v3 - see the [LICENSE](LICENSE) file for details.
+ This project is licensed under the GNU General Public License v1.1.11 - see the [LICENSE](LICENSE) file for details.
```

"37.x → 1.1.x" 的全局替换误伤了 `GPL v3`。同一事故在 `README.md:19` 侥幸未中（仍为 `GPL v3`）。

### 5.3 LICENSE 问题

- `LICENSE` = **完整 GNU GPL v3 文本**（35,825 B，SHA256 `633FD4DA62FF672331D65A8652E0AA13E7A93DE84BDF2E5D6197E2286278E036`），首行 "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007"，结尾为 GPL 附录说明。
- `README.md:19` 明确标注 `[License: GPL v3](LICENSE)`。
- **冲突**：产品是闭源商业桌面软件（Windows 安装包 + macOS DMG + `Copyright (C) 2026 SecureRedact Team`），却采用 GPL-3.0。GPL-3.0 要求分发时提供完整对应源码 —— 当前的 ZIP / Setup.exe / DMG **均不含源码**，构成许可证不合规。**发布前必须做出明确决策**：
  - (a) 确认项目本就应开源（GPL-3.0）→ 发行包必须附源码 tarball + 完整的 GPL 声明；
  - (b) 确认是模板残留 → 更换为商业 EULA / 闭源许可，并把 README 的 "GPL v3" 一并修正。
- **第三方许可清单缺失**：PyQt6（GPLv3 / 商业双授权）、PyQt6-WebEngine（LGPLv3 / 商业）、PyMuPDF（AGPL-3.0 / 商业）、onnxruntime（MIT）、rapidocr-onnxruntime（Apache-2.0）、jieba（MIT）、mammoth（BSD-2-Clause）、opencv-python（Apache-2.0）、beautifulsoup4（MIT）、numpy（BSD-3）、python-docx（MIT）、shapely（BSD-3）、pyclipper（MIT）。**无 NOTICE / 第三方许可汇总文件**，也无 `THIRD_PARTY_LICENSES`。
- **Inno Setup 安装器未附 LICENSE**：`SecureRedact_Setup.iss` 无 `LicenseFile` 指令 → 即便维持 GPL 也未满足"随附许可证"要求。而便携版 `build_complete.bat:208-214` 会把 `LICENSE` 拷成 `LICENSE.txt` ✅（仅根目录一份）。

### 5.4 硬编码绝对路径 / 开发机路径

| 位置 | 路径 | 类型 |
|---|---|---|
| `README.md:49` | `cd /Users/a49144/Desktop/codexhub/SecureRedactApp` | ❌ macOS 开发机 |
| `docs/guides/QUICK_START_FOR_CLAUDE_CODE.md:52` | 同上 | ❌ |
| `docs/guides/TESTING_GUIDE.md:43, 50, 318` | 同上 | ❌ |
| `docs/packaging/macos-packaging-guide.md:20` | 同上 | ❌ |
| `docs/packaging/windows-packaging-guide.md:20, 34` | `C:\Users\YourName\Desktop\SecureRedactApp` | ⚠️ 占位符 |
| `CLAUDE.md` / `AGENTS.md` "Run app" 段 | `/Users/a49144/Desktop/codexhub/SecureRedactApp` | ❌ |
| `secureredact/utils/security.py:113` | `sys._MEIPASS` | ✅ 正确的 frozen 路径处理 |
| `packaging/windows/scripts/launcher_wrapper.bat` 等 | `C:\Windows\System32\*.dll` | ✅ 合理 |
| `3_build_with_setup.bat:118-123` | `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` | ✅ 合理（含多路径回退） |
| **三个 spec 文件** | 全部相对 `SPEC` 推导 | ✅ **无绝对路径** |

### 5.5 其他发布阻塞项

| 项 | 现状 |
|---|---|
| **CI 安装被吞** | `.github/workflows/ci.yml:43, 50`：`pip install -r requirements.txt **|| true**` → 依赖安装失败 CI 仍继续（后续靠 skip 蒙混过关） |
| **CI 无 macOS** | 矩阵仅 `windows-latest` + `ubuntu-latest`，但产品发布 macOS DMG → **macOS 打包链路零 CI 覆盖** |
| **CI 无打包冒烟** | 没有任何 PyInstaller 构建验证 |
| **无打包元数据** | 无 `pyproject.toml`/`setup.py`/`MANIFEST.in` → 无 console_scripts、无 wheel/sdist、`secureredact.main:main` 无载体 |
| **CI 与 requirements 重复安装** | `requirements.txt` 已含 `pyinstaller==6.18.0`，CI 也装 pytest 系但未入清单 |
| **旧品牌环境变量** | `PRIVACYGUARD_DEBUG`（main.py:165）、`PRIVACYGUARD_PRELOAD_OCR`（secureredact/main.py:21）、`PRIVACYGUARD_CODESIGN_IDENTITY`（build_complete.sh:26）→ 与 SecureRedact 品牌不一致（改名遗留；改名需向前兼容评估） |
| **releases/ 为空** | 无任何历史发布产物留存 |
| **测试资产入包** | `collect_submodules('secureredact')` 会把 `secureredact/ui/styles/baselines/_generate_baselines.py`/`_render.py`（开发用渲染 harness）打进正式包 |

---

## 6. 发布前必修项 / 建议项分级清单

### 6.1 P0 — 发布前必修（11 项）

| # | 必修项 | 位置 | 验收标准 |
|---|---|---|---|
| **P0-1** | **spec 的 `datas` 补 `version.txt`**（三个 spec 同改） | `SecureRedact_windows.spec:178-185`、`SecureRedact_windows_v2.spec:181-185`、`SecureRedact.spec:38-45` | 打包版窗口标题与"关于"窗口显示 **1.1.13**，与 `version_info.txt` / Info.plist 一致 |
| **P0-2** | **统一运行时配置路径**（当前打包版配置 100% 丢失、设置无法保存） | `secureredact/utils/config.py:641` + 三个 spec 的 datas | 打包版能读到初始配置，且 `config.save()` 落到用户可写位置（建议 `~/.secureredact/config.json`，frozen 下用 `sys.executable` 所在目录或 `%APPDATA%`） |
| **P0-3** | **个人配置移出版本库** | `.gitignore`、`config.json`、`secureredact/config.json` | `git rm --cached` 两处 + .gitignore 覆盖两路径；仓库内不再出现 "0432"、"吉铁"、"丰满区"、"全能王" 等个人词条 |
| **P0-4** | **`.gitignore` 增加 spec 例外规则** | `.gitignore:27` | 追加 `!packaging/**/config/*.spec`；新建 spec 能正常 `git add` |
| **P0-5** | **固定 `pyinstaller-hooks-contrib` 版本** | `requirements.txt` | 显式 `pyinstaller-hooks-contrib==<版本>`；jieba 词典与 onnxruntime / docx / lxml 的收集行为锁定（当前靠传递依赖漂移到 2026.10） |
| **P0-6** | **修 `build_macos_app.sh` 图标检查** | `build_macos_app.sh:92-95` | 文件名改为实际存在的 `PrivacyGuard.icns`（或统一重命名资源）；同时验证 `:148` 的 `Contents/Resources/SecureRedact.icns` 命名假设 |
| **P0-7** | **版本号全量统一到 1.1.13** | `version_info.txt`、`SecureRedact_Setup.iss:8`、`README.md`、`README_EN.md`、`docs/packaging/README.md`、`packaging/README.md`、`docs/current/{STATUS,PROJECT_STRUCTURE,RECOVERY_GUIDE}.md`、`user-guides/用户使用手册.md`、`AGENTS.md` | 全仓 `grep -rn '1\.1\.11'` 只剩历史 changelog 条目；"版本标识"在各文档间一致 |
| **P0-8** | **LICENSE 决策与落地** | `LICENSE`、`README*.md`、`SecureRedact_Setup.iss`、新增 `THIRD_PARTY_LICENSES.md` | 明确 GPL-3.0 还是商业许可；安装器加 `LicenseFile`；发行包附第三方许可清单；GPL 路线还需附源码 |
| **P0-9** | **修 `README_EN.md:169` 的 "GPL v1.1.11"** | `README_EN.md` | 恢复为 "GNU General Public License v3"；并排查同类批量替换事故 |
| **P0-10** | **解除根 `main.py` 的运行时依赖** | `secureredact/main.py:107`、`secureredact/ui/main_window/handlers.py:381`、`secureredact/ui/main_window/setup_ui.py:40` | 3 处改为从 `secureredact` 内部导入（OCRWorker / WordWorker 已在 `secureredact.workers` 内，只需改导入路径）；**在此之前禁止删除根 `main.py`** |
| **P0-11** | **CI 去掉 `\|\| true`** | `.github/workflows/ci.yml:43, 50` | `pip install -r requirements.txt` 失败即 job 失败；同时把 pytest 系依赖写入 `requirements-dev.txt` 并在 CI 引用 |

### 6.2 P1 — 发布前建议（17 项）

| # | 建议项 | 位置 |
|---|---|---|
| P1-1 | 删除或归档 `SecureRedact_windows_v2.spec`（死代码，且缺 secureredact hiddenimports / hookspath / runtime_hooks） | `packaging/windows/config/` |
| P1-2 | 补齐 spec hiddenimports 手工清单：`secureredact.redaction.*`、`secureredact.pii.*`、`secureredact.ui.main_window.*`、`secureredact.ui.dialogs.*`、`secureredact.ui.settings.*`、`secureredact.ui.utils.*`、`secureredact.api`、`secureredact.cli`、`secureredact.utils.masking`、`secureredact.workers.word_batch_replace_worker` | 三个 spec |
| P1-3 | 给命名空间包补 `__init__.py`：`secureredact/pii`、`secureredact/ui/dialogs`、`secureredact/ui/settings`、`secureredact/ui/utils`（消除 `collect_submodules` 行为不确定性） | `secureredact/` |
| P1-4 | `theme.py` 从 `datas` 移除（只保留 hiddenimports），消除模块 / 数据双份 | 三个 spec |
| P1-5 | 统一图标源到 `assets/logo/**`；清理 `packaging/macos/assets/PrivacyGuard.icns`、`packaging/windows/assets/icon.ico`、`assets/logo/linux/privacyguard_*.png` | `assets/`、`packaging/*/assets/` |
| P1-6 | 补齐 `verify_dependencies.py` 自检清单：`jieba`、`lxml`、`shapely`、`pyclipper`、`PyQt6.QtWebChannel`、`PyQt6.QtWebEngineCore` | `packaging/windows/scripts/verify_dependencies.py:19-32` |
| P1-7 | 依赖收敛：`psutil` 删除或加上限；`onnxruntime` 加上限（`<2.0`）；移除 v2 spec 多余的 `sklearn` hiddenimports | `requirements.txt`、v2 spec |
| P1-8 | `PyQt6-WebEngine` 与 `PyQt6-Qt6` 版本对齐（6.10.0 → 6.10.2） | `requirements.txt:16-17` |
| P1-9 | 拆分 `requirements-dev.txt`（pytest / pytest-cov / pytest-qt / reportlab） | `requirements.txt` |
| P1-10 | 重建 `config.json.template`：补 40 个缺失键、删死配置 `redaction.seal_detection.*`（或补上代码读取）、统一 6 处值差异、标注"用户可改 / 代码强制" | `config.json.template` |
| P1-11 | 统一 `ConfigManager` / `SimpleConfig`：或让 `ConfigManager` 成为唯一实现并补 frozen 路径回退，或明确标注 `ConfigManager` 为待废弃并从 `__all__` 移除 | `secureredact/utils/config.py` |
| P1-12 | `DEFAULT_CONFIG["version"]` 改为从 `version.txt` 派生；修 3 处 fallback `"1.1.12"` | `config.py:31`、`main.py:147`、`secureredact/__init__.py:18`、`window.py:121` |
| P1-13 | 清理文档中的开发机路径：`/Users/a49144/...`、`C:\Users\YourName\...` | README、docs/guides、docs/packaging、CLAUDE.md、AGENTS.md |
| P1-14 | CI 增加 `macos-latest` runner + 最小 PyInstaller 构建冒烟（至少产出 `SecureRedact.app` 与 EXE 并校验版本资源） | `.github/workflows/ci.yml` |
| P1-15 | 重写 `user-guides/用户使用手册.md` 的 changelog 段（"v1.1.11" 重复 10+ 次对应不同内容） | `user-guides/用户使用手册.md:789-880` |
| P1-16 | 修正过时描述：`docs/current/STATUS.md:30` 与 CLAUDE.md 中"config.json scan.default_level=2.0"的既有失败说明（实测已为 1.5） | `STATUS.md`、`CLAUDE.md` |
| P1-17 | 旧品牌环境变量前缀 `PRIVACYGUARD_*` 迁移到 `SECUREREDACT_*`（保留旧名兼容）；清理 spec 注释里的 `PrivacyApp`、`PrivacyGuard` 遗留 | `main.py:165`、`secureredact/main.py:21`、`build_complete.sh:26`、三个 spec 注释 |

### 6.3 建议的收口顺序

```
1. P0-3 / P0-4 / P0-2 / P0-1   ← 配置与版本（先做，否则打包产物必错）
2. P0-5 / P0-6 / P0-11 / P0-10 ← 依赖与脚本链路（让构建可复现）
3. P0-7 / P0-9                ← 文档版本号与替换事故
4. P0-8                       ← LICENSE 决策（需人工 / 法务确认，不阻塞其他项）
5. P1-1 ~ P1-17               ← 收尾清理
6. 在 P0-10 完成前：禁止删除根 main.py；把 build_complete.bat / 1_init_environment.bat 的
   "检查 main.py" 改为 "检查 secureredact/main.py"，并同步删除根 main.py 的硬依赖
```

---

## 7. 小结

1. **打包链路整体可用，但存在 3 处断链**：macOS `build_macos_app.sh` 图标检查必失败、Windows v2 spec 是死代码、三个 spec 都漏打包 `version.txt`。

2. **入口已"半切换"**：三个 spec 与 `start_app.sh` 均已指向 `secureredact/main.py`，但 `secureredact/main.py`、`handlers.py`、`setup_ui.py` 仍 import 根 `main` 模块，两个 `.bat` 仍硬检查根 `main.py` 存在。**结论：打包链路可以指向 `secureredact`，但 `secureredact.main:main` 收口条件尚不具备**，需先清除 3 处残留 import。另外 `theme.py` 位于仓库根并被 10 个 `secureredact/ui/**` 模块依赖，是 B5 收口的隐式约束，须写进路线图。

3. **依赖问题共 9 类**，最高风险单点是 **`pyinstaller-hooks-contrib` 未固定** —— jieba 词典（5 MB）完全依赖它的 `hook-jieba.py` 进包，一旦失效则**中文姓名识别在打包版中静默失效且无任何用户可见报错**。其次是 `onnxruntime`/`psutil` 两个无上限版本与 `psutil` 的多余声明。开发环境实测与 requirements 完全不一致（含 opencv 双提供者冲突、pyinstaller 未安装），构建不可复现。

4. **配置健康度是全项目最薄弱环节**：运行时实际读 `secureredact/config.json`，spec 却打包根 `config.json` → **打包版配置 100% 丢失、设置保存失败**；个人配置（"0432"、"吉铁"、"丰满区"）已进入版本库；`ConfigManager` 与 `SimpleConfig` 双实现且路径 / 校验 / 监听 / 默认值四重不一致；`config.json.template` 缺 40 个键、多 7 个死键、6 处值不一致。

5. **发布准备度**：19 处版本引用中 15 处不同步；README / user-guides 落后 2 个版本并含一起批量替换事故（`GPL v1.1.11`）；LICENSE 为完整 GPL-3.0 与闭源商业定位冲突且安装器未附许可证、无第三方许可清单；CI 用 `\|\| true` 吞掉依赖安装失败、无 macOS 覆盖、无打包冒烟。

6. **分级结果**：**P0 必修 11 项**（配置路径 / 版本打包 / 个人配置脱敏 / spec 例外 / hooks-contrib 固定 / macOS 图标 / 版本统一 / LICENSE / README 事故 / main.py 解耦 / CI 严格化），**P1 建议 17 项**。P0-2（配置路径）与 P0-1（version.txt 打包）建议优先处理 —— 它们是唯一会导致"打包版功能直接不可用"的两项。

---

*报告结束。本分析为只读，未修改项目任何文件。*
