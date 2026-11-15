# SecureRedact 代码架构分析报告

> 分析对象：`SecureRedact` v1.1.13（`version.txt` = 1.1.13）
> 分析范围：`main.py` / `theme.py` / `test_fix.py` / `secureredact/**`（68 个 Python 文件 / 20,357 行）
> 排除：`tests/`、`docs/`、`packaging/`、`scripts/`
> 分析日期：2026-11-12　｜　工作副本：`.agents/worktrees/dsh-3eb2fb3e-5817`
> 方法：`glob`/`read`/`grep` 全量阅读 + AST 解析（模块树、行数、函数跨度、import 图、未使用 import）

---

## 0. 一句话结论

阶段 B 的**物理迁移已经完成**（`main.py` 从 13,011 行单体缩到 253 行 shim，`secureredact/` 已成体系），但**逻辑迁移没有完成**：13,326 行 UI 代码只是被"逐字搬运"进 9 个 mixin，层间依赖方向存在 5 类越界，**并且已经产生 6 处可复现的行为漂移**（其中 3 处是配置项静默失效、1 处是功能完全不落盘）。

---

## 1. 模块地图

### 1.1 顶层结构

```
SecureRedact/
├── main.py                    (253)   ← 兼容 shim（旧入口，已降级）
├── theme.py                   ( 89)   ← 根级配色字典（仍在被 9 个 UI 模块 import）
├── test_fix.py                (101)   ← 独立验证脚本（临时产物）
├── version.txt                        ← 版本单一来源
├── config.json                        ← 运行时配置
└── secureredact/             (65 文件 / 19,914 行)
    ├── __init__.py            (153)   包元数据 + 懒加载导出 + 纯常量
    ├── api.py                 (463)   业务 API 门面层
    ├── cli.py                 (247)   命令行薄壳
    ├── main.py                (161)   运行时入口（真入口）
    ├── core/__init__.py       (  0)   空占位包
    ├── ocr/                   (6 文件 / 617 行)
    ├── pii/                   (2 文件 / 671 行)
    ├── redaction/             (8 文件 / 1,050 行)
    ├── ui/                    (31 文件 / 13,326 行)   ← 66.9% 的代码量
    ├── utils/                 (9 文件 / 1,549 行)
    └── workers/               (6 文件 / 1,677 行)
```

### 1.2 `secureredact/` 各模块职责

#### 顶层模块（4 个）

| 模块 | 行数 | 职责（一句话） |
|---|---:|---|
| `secureredact/__init__.py` | 153 | 包元数据、`__version__` 读取、`__getattr__` 懒加载导出、以及 `APP_NAME/VERSION/ZOOM_MIN/ZOOM_MAX/WORD_RULE_SCHEMA_VERSION` 等纯常量 |
| `secureredact/main.py` | 161 | **真运行时入口**：装全局/线程异常钩子 → 可选预加载 OCR → 设图标 → 创建 `MainWindow` → `app.exec()` |
| `secureredact/api.py` | 463 | **业务 API 门面层**：`scan_pdf/scan_word/redact_pdf/redact_word/filter_hits_by_overrides/batch_redact_word/compute_doc_hash`，对外只吐 `dict`，不暴露 PyQt6 类型 |
| `secureredact/cli.py` | 247 | 命令行薄壳：`version / scan / redact / redact-word` 子命令，全部转发到 `secureredact.api` |

#### `secureredact/ocr/` —— OCR 引擎与 PDF 命中收集（6 文件 / 617 行）

| 模块 | 行数 | 职责 |
|---|---:|---|
| `ocr/__init__.py` | 18 | OCR 子包门面：导出 `BaseOCREngine/OCRResult/CharInfo/RapidOCREngine/OCREngineManager` |
| `ocr/base.py` | 66 | OCR 抽象基类与 `OCRResult`/`CharInfo` 数据结构 |
| `ocr/manager.py` | 43 | 单引擎管理器 `OCREngineManager`（v1.1.11 起只保留 RapidOCR） |
| `ocr/rapidocr.py` | 61 | `RapidOCREngine` 封装，**懒加载** `rapidocr_onnxruntime`（仅在 `recognize()` 内 import） |
| `ocr/mixed_pdf.py` | 373 | 混合型 PDF 命中收集：内嵌图片块 clip 矩形发现 + 图片块 OCR 命中 + 相邻命中矩形合并 |
| `ocr/text_pdf.py` | 56 | 文本型 PDF 命中框提取（唯一文本命中去重入口） |

#### `secureredact/pii/` —— 中文姓名识别（2 文件 / 671 行，**无 `__init__.py`**）

| 模块 | 行数 | 职责 |
|---|---:|---|
| `pii/name_recognizer.py` | 289 | 中文姓名启发式识别器（jieba X3）：金额词过滤、`extract_person_names()`、可选上下文过滤 |
| `pii/name_context.py` | 382 | 姓名上下文判别：区分"真名"与 jieba `nr` 误报（前缀/后缀/标签/枚举上下文） |

#### `secureredact/redaction/` —— 脱敏领域模型与规则（8 文件 / 1,050 行）

| 模块 | 行数 | 职责 |
|---|---:|---|
| `redaction/__init__.py` | 8 | 子包门面，导出 `HitRef` |
| `redaction/hit_ref.py` | 60 | `HitRef`（frozen 命中标识）+ `Override`（不可变状态覆盖）数据模型 |
| `redaction/doc_hash.py` | 22 | `compute_doc_hash()`：路径 + size + mtime 的 8 位 sha1 标识 |
| `redaction/override_store.py` | 291 | `HitOverrideStore` 单例：会话级 + 永久级双层 override 管理与 `filtered_hits()` 唯一消费入口 |
| `redaction/black_white_list_store.py` | 192 | `BlackWhiteListStore` 单例：黑/白名单的永久层 + 会话层管理 |
| `redaction/rules_loader.py` | 100 | `DEFAULT_RULES` / `DEFAULT_RULES_META` 加载器 + `_v113_apply_rule_overrides()` 强制代码层默认 |
| `redaction/whitelist_split.py` | 88 | 白名单片段级豁免的纯文本拆分（片段内只豁免白名单自身） |
| `redaction/word_rules.py` | 289 | Word 替换规则归一化 / 匹配构建 / 优先级合并 / 区间替换工具集（8 个函数） |

#### `secureredact/ui/` —— UI 层（31 文件 / 13,326 行）

**`ui/main_window/`（19 文件 / 9,604 行）—— 主窗口 9 mixin 架构**

| 模块 | 行数 | 职责 |
|---|---:|---|
| `ui/main_window/__init__.py` | 22 | 门面：导出 `MainWindow` / `SinglePageCanvas` / `WebViewBridge` / `identifiers` / `DEBUG_MODE` |
| `ui/main_window/window.py` | **2030** | `MainWindow` 主类容器（9 mixin + `QMainWindow` 多继承，79 个方法）+ 从 main.py 整块搬来的 import/常量区 |
| `ui/main_window/setup_ui.py` | **979** | UI 整体编排 mixin：工具栏 + 工作台 + 工作区 + 状态徽 + 信号连接（**单方法 943 行**） |
| `ui/main_window/density.py` | **954** | Windows 密度适配 mixin（**单方法 918 行**，逐控件硬编码尺寸/样式） |
| `ui/main_window/handlers.py` | 874 | 事件处理 mixin：键盘、扫描启动、高亮注入、Word 保存（10 个方法） |
| `ui/main_window/batch_replace.py` | 827 | 批量替换编排 mixin（25 个方法） |
| `ui/main_window/word_preview.py` | 773 | Word 双栏预览 mixin：DOCX→HTML→双栏增量 DOM patch（19 个方法） |
| `ui/main_window/_js_constants.py` | 562 | WebView 交互 JS 字符串常量（纯资产模块） |
| `ui/main_window/toolbar.py` | 557 | 工具栏 mixin + 按钮样式（13 个方法，含 199 行 QSS 字符串方法） |
| `ui/main_window/workbench.py` | 545 | 工作台 + info_bar + 状态徽章 mixin（17 个方法） |
| `ui/main_window/_helpers.py` | 277 | MainWindow 共享辅助：预览分段构造、面板更新脚本、模式标签 |
| `ui/main_window/canvas.py` | 277 | `SinglePageCanvas`：PDF 单页画布（QLabel + 鼠标/滚轮事件 + 手动框选） |
| `ui/main_window/pdf_render.py` | 263 | PDF 渲染编排 mixin：缩放/适配/翻页渲染 |
| `ui/main_window/webview_bridge.py` | 245 | `WebViewBridge`：Python ↔ JavaScript 通信桥（Word 双栏预览 + 人工干预槽位） |
| `ui/main_window/identifiers.py` | 177 | 集中所有 `setObjectName` 字面量常量 |
| `ui/main_window/theme.py` | 84 | 主题切换 mixin：`_apply_theme()` / `set_theme()`（light/dark/system） |
| `ui/main_window/_batch_helpers.py` | 158 | 批量替换结果表 / 摘要 / 筛选辅助函数 |

**`ui/settings/`（2 文件 / 2,318 行，无 `__init__.py`）**

| 模块 | 行数 | 职责 |
|---|---:|---|
| `ui/settings/dialog.py` | **2270** | `SettingsDialog`：设置中心（42 个方法，`__init__` 800 行）—— 全仓最大单体 |
| `ui/settings/_helpers.py` | 48 | 设置中心共享辅助：导航标签、hero 标签、百分比格式化 |

**`ui/dialogs/`（3 文件 / 614 行，无 `__init__.py`）**

| 模块 | 行数 | 职责 |
|---|---:|---|
| `ui/dialogs/word_replace_rules.py` | 280 | `WordReplaceRulesDialog`：多字段替换规则编辑（exact/regex） |
| `ui/dialogs/feedback.py` | 169 | `FeedbackDialog`：反馈表单 |
| `ui/dialogs/image_list.py` | 165 | `ImageListDialog`：图片列表与缩略图 |

**`ui/styles/`（7 文件 / 692 行）**

| 模块 | 行数 | 职责 |
|---|---:|---|
| `ui/styles/__init__.py` | 40 | 导出 `StylesheetLoader` / `get_tokens` / `get_substitution_map` |
| `ui/styles/loader.py` | 147 | QSS 加载器：合并 `.qss` 文件 + `{token}` 占位符替换 |
| `ui/styles/tokens.py` | 125 | 设计 token 冻结 dataclass（16 个语义 token，LIGHT/DARK） |
| `ui/styles/glass.py` | 82 | 玻璃特效可用性检测与降级替换 |
| `ui/styles/baselines/_render.py` | 124 | 视觉基线渲染工具（共享层） |
| `ui/styles/baselines/compare.py` | 87 | 视觉基线像素 diff |
| `ui/styles/baselines/_generate_baselines.py` | 87 | 一次性基线截图生成脚本 |

**`ui/utils/`（1 文件 / 98 行，无 `__init__.py`）**

| 模块 | 行数 | 职责 |
|---|---:|---|
| `ui/utils/density.py` | 98 | 密度模式 helper：`resolve_workspace_density_mode` / `resolve_settings_density_mode` / `_shift_density_mode` |

#### `secureredact/utils/` —— 基础设施层（9 文件 / 1,549 行）

| 模块 | 行数 | 职责 |
|---|---:|---|
| `utils/config.py` | **772** | **两套配置体系并存**：`ConfigManager`（415 行，高级 API：schema 校验 / 热重载 / 字段监听）+ `SimpleConfig`（141 行，扁平 dot-path 读写）+ 全局 `config` 单例（:772）+ 内嵌 `DEFAULT_CONFIG`（:30） |
| `utils/masking.py` | 244 | 部分遮蔽（Partial Masking）工具：`apply_partial_mask` / `apply_email_mask` / `apply_name_mask` / `apply_mask_for_rule` |
| `utils/doc_converter.py` | 183 | DOC → DOCX 转换（LibreOffice 主路径 + antiword 兜底）—— 全仓唯一"全部 raise"的模块 |
| `utils/temp_manager.py` | 135 | `TempFileManager`：临时目录生命周期管理（atexit 兜底清理） |
| `utils/security.py` | 116 | `validate_safe_path()` 路径穿越校验 + `resource_path()` 打包资源定位 |
| `utils/__init__.py` | 54 | 工具包门面（导出异常类 / TempFileManager / 路径工具 / ConfigManager） |
| `utils/exceptions.py` | 45 | 自定义异常：`PrivacyAppError` 基类 + 5 个子类 |

#### `secureredact/workers/` —— 线程层（6 文件 / 1,677 行）

| 模块 | 行数 | 职责 |
|---|---:|---|
| `workers/ocr_worker.py` | **1030** | `OCRWorker`：单页 OCR 全流程（文本层命中 + 图片块 OCR + 黑名单注入 + 白名单过滤 + 印章检测），19 个方法 |
| `workers/word_worker.py` | 312 | `WordWorker`：Word 文档智能脱敏扫描（8 个方法） |
| `workers/word_batch_replace_worker.py` | 241 | `WordBatchReplaceWorker`：批量 `.docx/.doc` 替换（带错误决策队列） |
| `workers/image_merge.py` | 60 | `ImageMergeWorker`：多图合并 |
| `workers/__init__.py` | 34 | 懒加载导出（避免 eager OCR import） |

---

## 2. 规模统计

### 2.1 总量

| 范围 | 文件数 | 行数 | 占比 |
|---|---:|---:|---:|
| `secureredact/` 全部 | 65 | 19,914 | 97.9% |
| 根级 `main.py` + `theme.py` + `test_fix.py` | 3 | 443 | 2.1% |
| **合计** | **68** | **20,357** | 100% |

按子包：

| 子包 | 行数 | 占 `secureredact/` |
|---|---:|---:|
| `ui/` | 13,326 | 66.9% |
| ├ `ui/main_window/` | 9,604 | 48.2% |
| ├ `ui/settings/` | 2,318 | 11.6% |
| ├ `ui/styles/` | 692 | 3.5% |
| ├ `ui/dialogs/` | 614 | 3.1% |
| └ `ui/utils/` | 98 | 0.5% |
| `workers/` | 1,677 | 8.4% |
| `utils/` | 1,549 | 7.8% |
| `redaction/` | 1,050 | 5.3% |
| `pii/` | 671 | 3.4% |
| `ocr/` | 617 | 3.1% |
| `api.py` + `cli.py` + `main.py` + `__init__.py` | 1,024 | 5.1% |

### 2.2 最大的文件（单体风险）

| 排名 | 文件 | 行数 | 主体规模 | 单体风险 |
|---:|---|---:|---|---|
| 1 | `secureredact/ui/settings/dialog.py` | **2,270** | `SettingsDialog` 类 2,216 行 / 42 方法 | 🔴 **极高**。一个对话框吃掉全仓 11.4%，`__init__` 单方法 800 行，密度计算在 4 个巨型方法间重复 |
| 2 | `secureredact/ui/main_window/window.py` | **2,030** | `MainWindow` 类 1,897 行 / 79 方法 | 🔴 **极高**。9 mixin 拼接后的"上帝类"；含 75 个未使用 import |
| 3 | `secureredact/workers/ocr_worker.py` | **1,030** | `OCRWorker` 类 990 行 / 19 方法 | 🟠 高。唯一承载全部 OCR 业务编排的单体 |
| 4 | `secureredact/ui/main_window/setup_ui.py` | **979** | **1 个类 / 1 个方法** | 🔴 **极高**。整个文件 = 一个 943 行函数（96%） |
| 5 | `secureredact/ui/main_window/density.py` | **954** | **1 个类 / 1 个方法** | 🔴 **极高**。整个文件 = 一个 918 行函数（96%） |
| 6 | `secureredact/ui/main_window/handlers.py` | 874 | 10 方法 | 🟠 高 |
| 7 | `secureredact/ui/main_window/batch_replace.py` | 827 | 25 方法 | 🟠 高 |
| 8 | `secureredact/ui/main_window/word_preview.py` | 773 | 19 方法 | 🟠 高 |
| 9 | `secureredact/utils/config.py` | 772 | `ConfigManager` 415 + `SimpleConfig` 141 | 🟠 高（两套配置体系同文件） |
| 10 | `secureredact/ui/main_window/_js_constants.py` | 562 | 纯字符串常量 | 🟢 低（合理资产模块） |

**集中度**：Top 3 文件（dialog.py + window.py + ocr_worker.py）= 5,330 行 = 全仓 **26.2%**；
Top 5（+ setup_ui.py + density.py）= 7,263 行 = **35.7%**；
`ui/` 一个目录占 **66.9%**。

### 2.3 超大函数（>100 行，全量 18 个）

| 文件:起始行 | 函数 | 长度 |
|---|---|---:|
| `ui/main_window/setup_ui.py:37` | `MainWindowSetupMixin.setup_ui` | **943** |
| `ui/main_window/density.py:37` | `_refresh_windows_density_metrics` | **918** |
| `ui/settings/dialog.py:58` | `SettingsDialog.__init__` | **800** |
| `ui/settings/dialog.py:965` | `_refresh_settings_layout_density` | 340 |
| `ui/settings/dialog.py:1946` | `_apply_dialog_theme` | 325 |
| `ui/settings/dialog.py:1345` | `_apply_settings_density_styles` | 249 |
| `workers/ocr_worker.py:752` | `OCRWorker._process_page` | 210 |
| `ui/main_window/toolbar.py:359` | `_get_button_style` | 199 |
| `ui/main_window/word_preview.py:395` | `_get_word_preview_scroll_restore_script` | 172 |
| `ui/main_window/toolbar.py:174` | `_refresh_toolbar_responsiveness` | 160 |
| `ui/main_window/window.py:181` | `MainWindow.__init__` | 151 |
| `ui/main_window/handlers.py:551` | `_highlight_sensitive_info` | 126 |
| `ui/main_window/batch_replace.py:466` | `_refresh_batch_workspace` | 119 |
| `ui/main_window/handlers.py:760` | `_save_word` | 115 |
| `ui/dialogs/feedback.py:48` | `FeedbackDialog.__init__` | 114 |
| `pii/name_recognizer.py:145` | `ChineseNameRecognizer.extract` | 112 |
| `api.py:356` | `batch_redact_word` | 108 |
| `workers/ocr_worker.py:143` | `OCRWorker._detect_seals` | 101 |

另有 30 个函数落在 60–100 行临界带。

---

## 3. 入口迁移核实（CLAUDE.md 说法是否成立）

### 3.1 结论：说法**基本成立，但行数已过时，且文档自相矛盾**

| CLAUDE.md 声明 | 核实结果 | 证据 |
|---|---|---|
| "真正的运行时入口已迁至 `secureredact/main.py`（v1.1.13 PR-B0 引入）" | ✅ **成立** | `secureredact/main.py:132` 定义 `main()`；`:148-157` 完整执行 QApplication → 图标 → MainWindow → `app.exec()` |
| "`main.py` 已转为过渡期兼容 shim" | ✅ **成立** | `main.py:1-13` 自述 shim；`:250-252` `from secureredact.main import main as _entry_main; sys.exit(_entry_main())` |
| "`main.py`（**13,026 行**）" | ⚠️ **数字过时** | 当前 `main.py` = **253 行**。git `e4426a7^`（PR-B2 之前）实测 **13,011 行**，说明该数字描述的是**重构前**的旧单体，迁移后未更新 |
| "`main.py` is still the active runtime entry and remains monolithic"（同一份 CLAUDE.md 的 "Current Technical Reality" 段） | ❌ **与自身 v1.1.13 banner 矛盾** | 该段是 v1.1.11 遗留文本未更新 |
| "Runtime currently uses `SimpleConfig` in `main.py`" | ❌ **过时** | `SimpleConfig` 实际定义在 `secureredact/utils/config.py:628`，`main.py:37` 只是 re-export |
| "`secureredact/main.py` 是否真实存在且可导入" | ✅ **真实存在且可导入** | 系统 Python 实测：`import secureredact.main` → OK；`import main` → OK，`main.MainWindow.__module__ == 'secureredact.ui.main_window.window'` |

### 3.2 两者关系（真实拓扑）

```
python main.py                          python -m secureredact.main
     │                                          │
     ▼                                          ▼
main.py (253 行 shim)                        secureredact/main.py (161 行)
     │  imports ~30 symbols for compat              │
     │  (main.py:31-81)                              │  ⚠️ 反向依赖！
     │                                               ├──:107  from main import init_ocr_engine
     ▼                                               │       (仅 PRIVACYGUARD_PRELOAD_OCR=true 时触发)
secureredact/*  ←──────────────────────────────┘
     │
     ▼
secureredact.ui.main_window.window.MainWindow  (唯一实体)
```

**`main.py` 的真实内容**（253 行）：
- `:15-81`：67 行 import + re-export（**其中约 90 个符号是纯死代码**）
- `:87-112`：`init_ocr_engine()` —— OCR 引擎延迟初始化（**shim 里唯一的真实逻辑**）
- `:141-147`：`read_app_version()` —— 与 `window.py:115`、`secureredact/__init__.py:13` 重复的第 3 份
- `:151-165`：`cv2.setNumThreads(0)` / `OMP_NUM_THREADS` / `APP_NAME` / `ZOOM_MIN/MAX` 等常量（**与 `window.py:124-130` 逐字重复**）
- `:186-199`：`OCRWorker` 兼容子类（自动注入 `box_adjust_ratio`）
- `:206-221`：`WordWorker` 兼容子类（自动注入 `DEFAULT_RULES`）
- `:235-252`：`__main__` 入口，委托 `secureredact.main:main()`

### 3.3 关键缺口

| 问题 | 位置 | 影响 |
|---|---|---|
| **新入口反向依赖旧 shim** | `secureredact/main.py:107` `from main import init_ocr_engine` | PR-B5 删除 `main.py` 时，`python -m secureredact.main` 的 OCR 预加载路径直接断链；且"干净入口"实际会加载整个根 shim |
| **shim 兼容安全网测试已经红了** | `tests/unit/test_main_shim_compat.py:77` | 实测 `Ran 10 tests / FAILED (errors=1)`：`KeyError: 'WORD_RULE_SCHEMA_VERSION'` —— `main.py` 已不再导出该符号（迁到 `secureredact/__init__.py:105`），但兼容清单没同步 |
| **文档自相矛盾** | CLAUDE.md banner vs "Current Technical Reality" 段 | 接手者会误判 `main.py` 仍是单体入口 |
| `docs/current/STATUS.md` 仍停在 v1.1.11 | `docs/current/STATUS.md:4` | 与 CLAUDE.md 的 v1.1.13 脱节 |

---

## 4. 分层评估

### 4.1 期望的分层 vs 实际依赖方向

```
   ┌───────────────────────────────┐
   │ UI 层  secureredact/ui/**     │  33 文件 / 13,326 行
   │  main_window / settings /      │
   │  dialogs / styles / utils      │
   └───────────┬───────────────────┘
               │ ✗ 期望：只向下依赖 API 层
   ┌───────────▼───────────────────┐
   │ API 层  secureredact/api.py   │  门面（7 个函数）
   │  CLI 层  secureredact/cli.py   │
   └───────────┬───────────────────┘
               │ ✓ 方向正确
   ┌───────────▼───────────────────┐
   │ 领域层  redaction/  pii/       │
   │ 线程层  workers/               │
   └───────────┬───────────────────┘
               │ ✓ 方向正确
   ┌───────────▼───────────────────┐
   │ 基础设施  utils/  ocr/          │
   └───────────────────────────────┘
```

### 4.2 实际跨层边（AST 全量扫描，179 条包内 import 边）

| 违规类型 | 数量 | 具体位置（file:line） |
|---|---:|---|
| **UI → 根级 `main`（跨层 import 私货）** | **2** | `ui/main_window/handlers.py:381` `from main import OCRWorker, WordWorker`；`ui/main_window/setup_ui.py:40` `from main import (SinglePageCanvas, WebViewBridge, resolve_workspace_density_mode, ...)` |
| **UI → 根级 `theme`（包外私货）** | **10** | `ui/main_window/window.py:58`、`window.py:970`、`ui/main_window/setup_ui.py:28`、`ui/main_window/density.py:27`、`ui/main_window/toolbar.py:18`、`ui/main_window/workbench.py:19`、`ui/main_window/batch_replace.py:30`、`ui/settings/dialog.py:26`、`ui/utils/density.py:11`、`ui/dialogs/image_list.py:113` |
| **UI → OCR 层（且是未使用 import）** | **2** | `ui/main_window/window.py:60-63`（`collect_embedded_image_clip_rects` / `collect_image_block_ocr_hits`）、`window.py:64`（`collect_text_pdf_hit_boxes`）—— AST 分析确认三者**在 window.py 内零引用**，是从 main.py 整块搬运时留下的死 import |
| **UI → Worker 层** | 5 | `ui/main_window/window.py:79/80/81/96`、`ui/main_window/batch_replace.py:29` |
| **入口 → 根 shim（反向依赖）** | 1 | `secureredact/main.py:107` |
| **API → Worker 层** | 1 | `secureredact/api.py:390`（lazy import，可接受） |
| **包内自引用（循环 import 隐患）** | 1 | `ui/main_window/window.py:97` `from secureredact.ui.main_window import SinglePageCanvas, WebViewBridge` ↔ `ui/main_window/__init__.py:14` `from .window import MainWindow` |
| **UI → API（✅ 方向正确）** | 3 | `ui/main_window/batch_replace.py:694`、`ui/main_window/word_preview.py:596`、`ui/main_window/handlers.py:386` |

### 4.3 具体坏味道（附证据）

#### ① 循环 import：`ui/main_window/__init__.py` ↔ `window.py`

```python
# secureredact/ui/main_window/__init__.py
12  from .canvas import DEBUG_MODE, SinglePageCanvas
13  from .webview_bridge import WebViewBridge
14  from .window import MainWindow          # ← 进 window.py

# secureredact/ui/main_window/window.py
97   from secureredact.ui.main_window import SinglePageCanvas, WebViewBridge   # ← 回到 __init__.py
```

当前能跑，**只因为 `__init__.py:12-13` 恰好先绑定了这两个名字**。任何人调整 `__init__.py` 的 import 顺序（哪怕只是插一行）就会立刻 `ImportError`。这是阶段 B 拆分留下的定时炸弹。

#### ② UI 层 `from main import ...` —— 阶段 B 明确禁止的方向

CLAUDE.md 顶部写着"**禁止继续往 `main.py` 添加新业务代码**"，但 UI 层仍在**主动从 `main.py` 取符号**：

- `handlers.py:381` —— `from main import OCRWorker, WordWorker`（注释自认"plan §3.7 保留到 B5 收口"）
- `setup_ui.py:40` —— `from main import (SinglePageCanvas, WebViewBridge, resolve_workspace_density_mode, ...)`，且注释 `setup_ui.py:38-39` 写着"不能用模块级语句（循环 import）"

**后果**：PR-B5 删除 `main.py` 时，这两处必然断链；而且它们把 UI 与"兼容层"绑死，导致兼容层无法退场。

#### ③ UI 层直接依赖包外根模块 `theme.py`（10 处）

根级 `theme.py` 不属于 `secureredact` 包，却有 10 个 UI 模块 import 它。打包（PyInstaller `SecureRedact_verify.spec`）时它是 hidden-import 风险点；更严重的是它与 `secureredact/ui/styles/tokens.py` 构成**两份手工同步的配色表**（详见 §6.2）。

#### ④ UI 层里残留业务逻辑吗？—— 基本已清理

全量扫描 `secureredact/ui/**` 的正则使用只有 **7 处**，全部是 HTML/字符串处理，不是脱敏规则：

```
ui/main_window/handlers.py:629    re.compile(re.escape(...) + r'(?![^<]*>)')   ← HTML 注入
ui/main_window/window.py:1913-1914  re.search / re.sub                          ← HTML 替换
ui/main_window/webview_bridge.py:80  re.finditer(pattern, text)                ← 文本扫描
ui/dialogs/word_replace_rules.py:199  re.compile(find_text)                    ← 搜索框
ui/main_window/_helpers.py:57     re.sub(r"[^a-z0-9]+", ...)                  ← slug 化
ui/styles/loader.py:53            _PLACEHOLDER_RE                             ← 占位符
```

✅ **结论：脱敏规则、遮蔽算法、白名单切分、姓名识别都已正确下沉到 `redaction/`、`utils/masking.py`、`pii/`；UI 层没有残留脱敏业务逻辑。这是阶段 B 做对的部分。**

#### ⑤ UI → Worker 直接耦合

`ui/main_window/window.py:79-81` 直接 import 三个 Worker 类。若严格分层，UI 应只依赖 `secureredact.api`（`api.py` 已提供 `scan_pdf/scan_word/redact_pdf/redact_word` 的同步门面）。目前 `api.py` 只被 3 处 UI 引用，**API 层的渗透率极低**，双通道并存导致"哪条路是权威"不清晰。

#### ⑥ 无 `__init__.py` 的命名空间包（4 个）

`secureredact/pii/`、`secureredact/ui/dialogs/`、`secureredact/ui/settings/`、`secureredact/ui/utils/` 均缺 `__init__.py`。Python 3.3+ 的 PEP 420 命名空间包可以工作，但：
- PyInstaller 静态分析对命名空间包支持较差，需要 `--hidden-import`
- `packaging/windows/config/hook-secureredact.py:31` 已经在手工补 hidden-import

#### ⑦ `secureredact/core/` 是空占位包

`secureredact/core/__init__.py` = 0 行，全仓唯一引用点是 `packaging/windows/config/hook-secureredact.py:31` 的 `'secureredact.core'`。属于重构遗留的空壳。

### 4.4 分层总评

| 维度 | 评价 |
|---|---|
| 物理分层（目录切分） | 🟢 **良好**。`ui / workers / redaction / pii / utils / ocr` 边界清晰，命名规范 |
| 领域逻辑下沉 | 🟢 **良好**。脱敏规则、遮蔽、白名单、姓名识别已正确下沉 |
| 依赖方向 | 🟡 **部分违规**。UI→Worker（5）、UI→根 `main`（2）、UI→根 `theme`（10）、入口→根 shim（1） |
| 循环依赖 | 🟡 **1 处隐患**（`ui/main_window/__init__.py:14` ↔ `window.py:97`） |
| API 层渗透率 | 🔴 **过低**。`api.py` 写好却只有 3 处 UI 调用；UI 仍直连 worker/ocr |
| 层内聚集度 | 🔴 **过高**。`ui/` 占 66.9%，两个 mixin 文件各含一个 900+ 行函数 |

**分层结论：骨架清晰，血肉未分。** 目录切分已完成，**依赖倒转尚未开始**——UI 仍在直连底层，且新增的 `api.py` 门面处于"建好但没人用"的状态。

---

## 5. 技术债清单（按严重度排序）

### 🔴 S1 —— 已产生可复现的功能缺陷

| # | 位置(file:line) | 问题 | 证据 / 复现 |
|---:|---|---|---|
| 1 | `secureredact/ui/main_window/theme.py:79-81` | **主题切换永不落盘** | `set_theme()` 写 `config = getattr(self, "config", None)`，但 `MainWindow` **从未**设置 `self.config`（全仓 `self.config = ...` 只出现在 `ui/settings/dialog.py:68`）。因此 `config.set("app.theme", name, persist=True)` 永不执行 → 重启后主题回到 `config.json` 中的旧值（`window.py:204` 读取）。另外 `:74` 刚 `from secureredact.utils.config import config`，下一行就被局部同名变量遮蔽，是典型的重构手滑 |
| 2 | `secureredact/__init__.py:112-113` vs `main.py:163-164` | **`config.json` 的 `ocr.zoom_min/zoom_max` 静默失效** | UI 实际消费方是 `ui/main_window/pdf_render.py:68,88` `from secureredact import ZOOM_MIN, ZOOM_MAX` → 走**硬编码 0.5/4.0**；而 `config.json:187-188` 里的 `zoom_min/zoom_max` 只被 shim 的死变量读取。改配置无效。`secureredact/__init__.py:108-111` 的注释已自认"接受失去运行时可配置性" |
| 3 | `main.py:162` vs `workers/ocr_worker.py:38` / `workers/word_worker.py:20` | **`config.json` 的 `ocr.progress_update_interval` 静默失效** | 主配置项 `config.json:186` 存在，但两个 worker 都硬编码 `PROGRESS_UPDATE_INTERVAL = 0.05`，无人读 config |
| 4 | `secureredact/__init__.py:120` vs `main.py:156` / `ui/main_window/window.py:126` | **`config.json` 的 `app.name` 只影响一半** | 窗口标题走 config（`window.py:183`），反馈对话框走硬编码（`ui/dialogs/feedback.py:50` `from secureredact import APP_NAME`）→ 改名后两处不一致 |
| 5 | `secureredact/ui/main_window/canvas.py:31` vs `main.py:165` / `window.py:130` | **`DEBUG_MODE` 三处定义、两种语义** | `canvas.py:31` **只读 env**，另两处 **env + config**。源码注释 `canvas.py:28-30` 已自认："本模块读 env 拿到 false，造成 DEBUG 输出静默化。后续 PR-B2.x 阶段统一收口"——该收口未发生 |
| 6 | `tests/unit/test_main_shim_compat.py:77` | **shim 兼容安全网测试当前是红的** | 实测 `Ran 10 tests / FAILED (errors=1)`，`KeyError: 'WORD_RULE_SCHEMA_VERSION'`。`main.py` 不再导出该符号，但兼容清单未同步 |

### 🔴 S2 —— 结构性高风险

| # | 位置(file:line) | 问题 |
|---:|---|---|
| 7 | `ui/main_window/setup_ui.py:37` | `setup_ui` **单方法 943 行**（文件 979 行的 96%）。类 docstring 自承"原 main.py 内完整搬迁，逐字未改" |
| 8 | `ui/main_window/density.py:37` | `_refresh_windows_density_metrics` **单方法 918 行**（文件 954 行的 96%），逐控件硬编码 `setFixedHeight/setStyleSheet`，无表驱动 |
| 9 | `ui/settings/dialog.py:55,58,965,1345,1946` | `SettingsDialog` 2,216 行 / 42 方法；`__init__` 800 行；密度计算在 4 个巨型方法间重复 |
| 10 | `ui/main_window/window.py:18-110` | **75 个未使用 import**（import 块自述"合并自 main.py:15-80"），含 `fitz/cv2/np/bs4/PIL`、30+ 个 PyQt6 widget 类、3 个 OCR 函数 —— 全是搬运残留 |
| 11 | `ui/main_window/__init__.py:14` ↔ `window.py:97` | 循环 import，靠 import 顺序侥幸工作 |
| 12 | `ui/main_window/handlers.py:381`、`ui/main_window/setup_ui.py:40` | UI 层 `from main import ...`，与"禁止再动 main.py"的方向相悖，且阻塞 PR-B5 收口 |
| 13 | `secureredact/main.py:107` | 新入口反向依赖旧 shim（`from main import init_ocr_engine`） |
| 14 | `main.py:15-81` | **120 个未使用 import**（约 30 个是契约内 re-export，其余 ~90 个是 PyQt6 widget + stdlib 死代码） |

### 🟠 S3 —— 可观测性缺失 / 静默失败

| # | 位置 | 数量与代表 |
|---:|---|---|
| 15 | 全仓 `except` handler | **164 个**：裸 `except:` **0 个**（好）；`except Exception` **68 个**；纯静默（body 只有 pass/continue/return None）**23 个** |
| 16 | 8 处 `except Exception: pass`（零日志零返回） | `secureredact/main.py:59`、`ui/main_window/window.py:426`、`ui/main_window/word_preview.py:93`、`ui/main_window/theme.py:68`、`ui/settings/dialog.py:912`、`ui/settings/dialog.py:1881`、`utils/temp_manager.py:63`、`utils/temp_manager.py:134`。其中 `dialog.py:1881` 是**永久 override 回写失败静默**——用户点了"清理失效 overrides"，失败了但界面无任何提示 |
| 17 | 15 处类型化静默 | `ocr/mixed_pdf.py:39/124/131/142/148`（rect 归一化四连 `except (TypeError, ValueError): return None`，调用方无法区分"没有 rect"和"rect 坏了"——PDF 坐标错位类回归的温床）、`ocr/text_pdf.py:17`、`redaction/word_rules.py:118`、`ui/main_window/_batch_helpers.py:129`、`webview_bridge.py:240`、`window.py:1739`、`word_preview.py:701`、`utils/config.py:737`、`workers/word_batch_replace_worker.py:165/239`、`workers/word_worker.py:214` |
| 18 | 12 处"fallback 赋值型吞错" | `ui/main_window/handlers.py:404` `pdf_excluded_names = []`（规则过滤静默降级为空 → 静默漏脱敏）、`ui/settings/dialog.py:347/885/895/904`、`ui/main_window/toolbar.py:101/324`、`ui/main_window/window.py:418/704/714`、`ui/styles/glass.py:33/52` |
| 19 | `workers/ocr_worker.py:324-327` | `except Exception as e: print("[DEBUG] ..."); return int(min(x_coords)), int(max(x_coords))` —— 边界检测异常被吞后返回**兜底坐标**，脱敏框可能错位 |
| 20 | `utils/config.py:276/279/360/376/399/428/437/608/671/703/733` | 库层**用 print 代替 logger**，8 处 `except Exception` 全部"print + return False"，不抛异常 → 配置损坏时上层永远拿不到原因 |
| 21 | 全仓 `print(` 残留 | **138 处**，其中**库/UI/worker 层 87 处**（无 logging 模块、无级别、无开关，打包后 stdout 丢失即零可观测性）。重灾区：`workers/ocr_worker.py` 17、`ui/main_window/window.py` 14、`utils/config.py` 13、`ui/main_window/handlers.py` 12 |
| 22 | `ui/main_window/handlers.py:421-423` | **每次 OCR 无条件打印整个 `active_rules` + `pdf_rules` 列表**（每次都刷屏） |
| 23 | `ui/settings/dialog.py:1910-1911` | 源码自带注释 `# v1.1.11: 添加调试输出`，紧随两行 print 打印全部选中规则 —— 教科书级调试残留 |

### 🟡 S4 —— 一致性 / 工程卫生

| # | 位置 | 问题 |
|---:|---|---|
| 24 | `secureredact/pii/`、`ui/dialogs/`、`ui/settings/`、`ui/utils/` | 4 个包缺 `__init__.py`（PEP 420 命名空间包，打包需 hidden-import） |
| 25 | `secureredact/core/__init__.py` | 0 行空占位包，唯一引用在 `packaging/windows/config/hook-secureredact.py:31` |
| 26 | `workers/word_worker.py:16-17` | 同一模块连续两行 import 同一模块（`apply_mask_for_rule` 重复） |
| 27 | `ui/settings/dialog.py:65` | `from secureredact.utils.config import config` 被 `:68` `self.config = config_manager` 完全遮蔽 → 死 import |
| 28 | `main.py:246-248` | `__main__` 块无条件打印全部 `DEFAULT_RULES_META` 的 mask 参数（启动噪音） |
| 29 | `secureredact/__init__.py:53-59` | `except ImportError` 把 7 个 API 符号全设为 `None` → 调用方 `None is not callable`，而非明确的 ImportError |
| 30 | `theme.py` vs `ui/styles/tokens.py:44+` vs `ui/main_window/window.py:148-162` | 三处配色定义；`tokens.py:42` 注释声称"与 theme.py LIGHT/DARK 完全一致"，但无测试守护 |

### ⚪ S5 —— TODO 标记：**零命中**

| 位置 | 数量 | 说明 |
|---|---:|---|
| 全仓 `TODO / FIXME / XXX / HACK` | **0**（唯一 2 处 `XXX` 是 `PR-XXX` 编号占位符，见 `ui/main_window/__init__.py:5,14`） | 项目几乎不用标记式待办，**技术债是"隐形"的** —— 靠巨型函数 / 死代码 / 静默吞错承载，而不是靠 TODO 文本。这一点本身就是一个信号：**债没有可见性，所以不会被偿还** |

---

## 6. 重复 / 并存实现清单

### 6.1 已产生行为漂移（6 项，⚠️ 需修）

| # | 主题 | 实现 A | 实现 B | 实际生效 | 漂移说明 |
|---:|---|---|---|---|---|
| 1 | **缩放上下限** | `secureredact/__init__.py:112-113` 硬编码 `0.5/4.0` | `main.py:163-164` config 派生 | **A**（`pdf_render.py:68,88` 用 A） | `config.json:187-188` 的 `ocr.zoom_min/zoom_max` 改了不起作用 |
| 2 | **应用名** | `secureredact/__init__.py:120` 硬编码 | `main.py:156` / `window.py:126` config 派生 | **两者并用** | 窗口标题跟随 config，反馈对话框不跟随 → 同屏不一致 |
| 3 | **进度节流** | `main.py:162` config 派生 | `ocr_worker.py:38` / `word_worker.py:20` 硬编码 | **B** | `config.json:186` 的 `ocr.progress_update_interval` 是死配置 |
| 4 | **DEBUG 开关** | `main.py:165` / `window.py:130`（env **+ config**） | `canvas.py:31`（仅 env） | **两者语义不同** | 源码注释已自认漂移，未收口 |
| 5 | **主题持久化** | `window.py:204` 读 `config.get("app.theme")` | `theme.py:79-81` 写 `getattr(self,"config",None)` → 永远 None | **写侧失效** | 切换主题后重启归位（见 §5 S1-1） |
| 6 | **shim re-export 契约** | `tests/unit/test_main_shim_compat.py:13-21` 列 11 个符号 | `main.py` 实际导出 | **缺 1 个** | `WORD_RULE_SCHEMA_VERSION` 已迁至 `secureredact/__init__.py:105`，测试未同步 → **测试当前 ERROR** |

### 6.2 并存但尚未漂移（潜在风险，7 项）

| # | 主题 | 实现 A | 实现 B | 风险 |
|---:|---|---|---|---|
| 7 | **两套配置体系** | `utils/config.py:195` `ConfigManager`（415 行，schema 校验 + 热重载 + 字段监听） | `utils/config.py:628` `SimpleConfig`（141 行，扁平 dot-path）+ `:772` 全局单例 | `ConfigManager` **在生产代码中零调用**，只有 `tests/unit/test_app_config.py` 与 `tests/integration/test_gui_smoke.py` 在用。两套默认值来源不同（`ConfigManager` 自带 `DEFAULT_CONFIG` 全量，`SimpleConfig` 只借用其中 `default_rules`/`whitelist` 子集做字段保护，`config.py:681,698`） |
| 8 | **默认脱敏规则三处存放** | `utils/config.py:50+` `DEFAULT_CONFIG["redaction"]["default_rules"]` | `redaction/rules_loader.py:66-95` 硬编码 12 条（else 分支） | `rules_loader.py:15` 自称"从 main.py 整块复制，行为零改动"，两处内容需**手工同步**，无一致性测试 |
| 9 | **版本号读取 3 份** | `main.py:141` `read_app_version()` | `ui/main_window/window.py:115` `read_app_version()`；`secureredact/__init__.py:13` `_read_version()` | 相对路径写法各不相同（`parent` / `parent×4` / `parent×2`），当前结果一致，但打包路径变更时易碎 |
| 10 | **Word 规则工具 3 处 re-export** | `redaction/word_rules.py` 原实现 | `main.py:58` + `ui/main_window/window.py:87` 各一份 re-export | 三份 `from ... import` 长列表手工维护 |
| 11 | **主题体系 3 套** | 根 `theme.py:10-47` 配色字典 | `ui/styles/tokens.py:44+` dataclass；`ui/main_window/window.py:148-162` 内联 QSS | `tokens.py:42` 声称"与 theme.py 完全一致"但无测试；`window.py` 是第三份内联副本 |
| 12 | **同名模块易混** | `ui/utils/density.py`（98 行，helper） | `ui/main_window/density.py`（954 行，mixin） | 两个 `density.py` 同名不同包，import 时极易拿错 |
| 13 | **兼容 Worker 子类 2 处** | `main.py:186` `OCRWorker` / `:206` `WordWorker` | `workers/ocr_worker.py:41` / `workers/word_worker.py:23` 基类 | 兼容层仅做参数注入，目前无漂移；但 PR-B5 收口时必须同步清理 `handlers.py:381` |

### 6.3 死代码残留（4 项）

| # | 位置 | 说明 |
|---:|---|---|
| 14 | `main.py:15-81` 中约 90 个未使用符号 | PyQt6 widget 类、`fitz/cv2/np/bs4/PIL/sip`、stdlib —— 搬运残渣 |
| 15 | `ui/main_window/window.py:18-110` 中 75 个未使用符号 | 同上，含 3 个 OCR 函数（证明 UI 曾直接调 OCR，现已不再需要） |
| 16 | `secureredact/core/` | 0 行空包 |
| 17 | `ui/settings/dialog.py:65` | 被 `:68` 遮蔽的死 import |

---

## 7. 小结与建议

### 7.1 一张表看全貌

| 维度 | 现状 | 评分 |
|---|---|---|
| 物理模块化 | 65 个文件 / 19,914 行，目录边界清晰 | 🟢 良好 |
| 入口迁移 | `main.py` 已是 253 行 shim，真入口 `secureredact/main.py` 可导入可运行 | 🟢 基本完成 |
| 领域逻辑下沉 | 脱敏/遮蔽/白名单/姓名识别已正确下沉，UI 无残留业务正则 | 🟢 良好 |
| 依赖方向 | UI→Worker 5 处、UI→根 `main` 2 处、UI→根 `theme` 10 处、入口→shim 1 处 | 🟡 部分违规 |
| 循环依赖 | 1 处（`ui/main_window/__init__.py:14` ↔ `window.py:97`） | 🟡 隐患 |
| 行为一致性 | **6 处已确认漂移**，其中 4 处是"配置项静默失效" | 🔴 待修 |
| 单体风险 | 2 个 900+ 行单函数文件 + 2,270 行设置中心 + 2,030 行上帝类 | 🔴 高 |
| 可观测性 | 138 处 print（87 处在库/UI/worker）、23 处静默吞错、无 logging 模块 | 🔴 高 |
| 工程卫生 | 4 个包缺 `__init__.py`、1 个空包、TODO 标记全仓为零 | 🟡 中 |

### 7.2 建议的收口顺序（不新增功能，只还债）

**第一优先 —— 修已确认的功能缺陷（约 1 天）**
1. `ui/main_window/theme.py:79` → 改用模块级 `config` 单例（或给 `MainWindow` 加 `self.config = config`），恢复主题落盘
2. `secureredact/__init__.py:112-113,120` → `ZOOM_MIN/MAX`、`APP_NAME` 改回 config 派生；或反过来删掉 `config.json` 中已失效的键
3. `workers/ocr_worker.py:38` / `word_worker.py:20` → `PROGRESS_UPDATE_INTERVAL` 接 config
4. `ui/main_window/canvas.py:31` → `DEBUG_MODE` 与 `window.py:130` 对齐
5. `main.py` 补回 `WORD_RULE_SCHEMA_VERSION` re-export（或更新 `tests/unit/test_main_shim_compat.py` 清单）→ 让兼容安全网重新变绿

**第二优先 —— 切依赖方向（约 1 周）**
6. `handlers.py:381`、`setup_ui.py:40` → 改为直连 `secureredact.workers` / `secureredact.ui.main_window`，**不经过 `main`**
7. `secureredact/main.py:107` → 把 `init_ocr_engine()` 迁进 `secureredact/ocr/`，彻底断开"新入口依赖旧 shim"
8. 根 `theme.py` → 迁入 `secureredact/ui/styles/`，把 10 处 `from theme import Theme` 全部改指；`tokens.py` 与 `theme.py` 二选一
9. `ui/main_window/__init__.py` ↔ `window.py:97` → 打破循环（建议 `window.py` 改为 `from .canvas import SinglePageCanvas`）
10. 补 `secureredact/pii/__init__.py`、`ui/dialogs/__init__.py`、`ui/settings/__init__.py`、`ui/utils/__init__.py`；删除空包 `secureredact/core/`
11. 清理 `main.py` 与 `window.py` 的死 import（~165 个），让"文件职责"与"实际内容"一致

**第三优先 —— 拆单体（约 2–4 周）**
12. `setup_ui.py` 943 行 → 按"工具栏 / 工作台 / 工作区 / 状态徽 / 信号连接"拆 5 个方法
13. `density.py` 918 行 → 改表驱动（控件名 → 尺寸/样式规格表）
14. `ui/settings/dialog.py` 2,270 行 → 按设置分组拆页（OCR / 脱敏 / 扫描 / 人工干预 / 关于）
15. `window.py` 79 方法的 `MainWindow` → 把事件处理、拖放、Word 滚动同步下沉到独立 controller

**第四优先 —— 可观测性（约 2 天）**
16. 引入 `logging`（模块级 logger，`INFO/WARNING/ERROR` + 文件 handler），把 87 处库/UI/worker 的 print 迁过去
17. 8 处 `except Exception: pass` 补日志；其中 `dialog.py:1881`（永久 override 回写）必须让用户看到失败
18. `ocr/mixed_pdf.py:124-148` 的 4 连静默 `return None` → 改为抛/带哨兵值，让调用方能区分

### 7.3 一句话总结

**阶段 B 做完了"搬家"，没做完"分家"。** 目录切分让代码"看起来"分层了，但 66.9% 的代码仍压在 UI 层，两个文件各含一个 900+ 行的方法，UI 仍在直连 Worker/OCR/根 `main`，而搬家过程中已经悄悄弄坏了 6 处行为（主题不落盘、3 个 config 项失效、DEBUG 语义分裂、兼容测试变红）。**继续按当前路线推进（先做 B5 删 `main.py`）之前，必须先把 §5 S1 的 6 条功能缺陷修掉**——否则删掉 `main.py` 的那一刻，UI 层的两处 `from main import ...` 和入口的 OCR 预加载路径会同时断链。

---

*报告生成：DSH arch-analyst ｜ 所有 file:line 均经 AST / grep / 实测导入交叉验证*
