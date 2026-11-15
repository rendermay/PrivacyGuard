# SecureRedact 项目全量分析报告

> **分析日期**：2026-11-12
> **分析对象**：工作目录 `<repo root>`
> **分支 / 提交**：`dsh-3eb2fb3e-5817` @ `3a62724`（`docs(refactor): PR-V2 完成报告`）
> **版本基线**：`version.txt` = **1.1.13**（CHANGELOG 顶部另有未发布的 1.1.14 条目）
> **分析方法**：4 路并行只读分析（架构 / 进度 / 测试CI / 打包发布）+ 主线独立复核（git 历史、依赖图、运行时实测）
> **本报告未修改任何项目源码**，仅新增 `docs/analysis/` 下的报告文件

---

## 0. 执行摘要（一页纸）

### 一句话结论

> **SecureRedact 的"物理重构"已经完成，"逻辑重构"停在半路，"质量门禁"处于失守状态，"交付"环节从未执行。**
> 代码规模与架构骨架是健康的，但存在 **3 个用户可感知的真实缺陷**、**CI 三个步骤必然全红**、**打包版配置与版本号双重失效**、**主线落后 66 个 commit 且已停摆 72 天**。

### 五个关键数字

| 指标 | 数值 | 含义 |
|---|---|---|
| 代码规模 | `secureredact/` 65 文件 / **19,914 行**；根 `main.py` **253 行** | 单体已从 13,011 行降到 253 行 shim ✅ |
| 测试规模 | **604 用例 / 60 模块**（`tests/` 10,057 行） | 相对 CLAUDE.md 声称的 162 项，实际 **3.7 倍** ✅ |
| 实跑结果 | **564 通过 / 20 失败 / 20 跳过**，15.1s | 93.4% 通过率，**CI 必红** ❌ |
| 覆盖率 | `secureredact` 全包 **40%**；`api.py` **91.77%**（CI 要求 100%） | 覆盖率门槛从未被真正拦住 ❌ |
| 开发节奏 | 最后提交 **2026-09-01**，距今 **72 天**；`main` 落后 **66 commits** | 重构成果**从未合并、从未发版** ❌ |

### 进度判定

| 维度 | 判定 | 依据 |
|---|---|---|
| 功能交付 | 🟢 **充分** | PDF（文本/OCR/混合/手动）+ Word（扫描/规则/批量）+ 人工干预 + 姓名识别 + CLI 全部落地 |
| 架构重构 | 🟡 **物理完成，逻辑未完成** | 目录切分 ✅ / 领域下沉 ✅ / 依赖倒转 ❌（UI 仍直连 Worker、2 处 import 根 `main`、10 处 import 根 `theme`） |
| 质量门禁 | 🔴 **失守** | CI 3 步必红；无 artifact；无 macOS；除 api 外无覆盖率门槛；`pip install || true` 静默变绿 |
| 打包发布 | 🔴 **有硬缺陷** | spec 缺 `version.txt`；打包的 `config.json` 与运行时读的不是同一个文件 |
| 文档一致性 | 🔴 **严重滞后** | CLAUDE.md / AGENTS.md / STATUS.md / .project_info 与代码三方不一致；30%+ 声明失实 |
| 流程健康 | 🔴 **停摆** | 10 周零提交；`main` 未合并；v39 路线图被误删且无人知晓 |

### 最高优先级的 5 件事

1. 🔴 **配置双源分裂** —— 用户在 `config.json` 里改的设置**运行时全部读不到**（`SimpleConfig` 读的是 `secureredact/config.json` 子集）
2. 🔴 **打包版双重失效** —— spec 未打包 `version.txt`（显示 1.1.12）+ 打包的配置文件位置错误（设置全丢、存不进去）
3. 🔴 **CI 必然全红** —— api 覆盖率 92% < 100%、`render_visual_baseline.py` 脚本 `sys.path` 缺失、20 个测试失败
4. 🟠 **主线未合并 + 72 天停摆** —— 66 个 commit 的重构成果只存在于工作分支，`main` 仍是 v1.1.13 旧代码
5. 🟠 **PR-B5 收口未真正完成** —— 2 处 UI `from main import` 使根 `main.py` 无法删除，"干净入口"仍反向依赖 shim

---

## 1. 项目画像

### 1.1 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| GUI | PyQt6 + PyQt6-WebEngine | 6.10.2 / 6.10.0（**错位**） |
| PDF | PyMuPDF (`fitz`) | 1.27.1 |
| OCR | rapidocr-onnxruntime + onnxruntime | 1.2.3 / `>=1.24.1`（**无上限**） |
| Word | python-docx + mammoth | 1.2.0 / 1.11.0 |
| 解析 | BeautifulSoup4 + lxml | 4.14.3 / 6.0.2 |
| 中文分词 | jieba | 0.42.1（**打包依赖 hooks-contrib，未固定**） |
| 图像 | opencv-python + Pillow | 4.13.0.92 / 12.1.1 |
| 打包 | PyInstaller + hooks-contrib | **未固定版本** |
| 测试 | pytest + pytest-cov + pytest-qt | **未固定版本** |
| Python | CPython | 3.11 / 3.13（CI 矩阵） |

### 1.2 代码规模分布

```
secureredact/  65 文件 / 19,914 行  (97.9%)
├── ui/                    13,326 行 (66.9%)  ← 重心全在 UI
│   ├── main_window/        9,604 行  (9 mixin + 主类)
│   ├── settings/           2,318 行
│   ├── styles/               692 行  (.qss + token + loader)
│   ├── dialogs/              614 行
│   └── utils/                 98 行
├── workers/                1,677 行  (OCR/Word/批量/图片合并 线程)
├── utils/                  1,549 行  (config 772 / masking 244 / doc_converter 183 ...)
├── redaction/              1,050 行  (override / 规则 / 白名单切分 / word_rules)
├── pii/                      671 行  (姓名识别 + 上下文)
├── ocr/                      617 行  (文本 PDF / 混合 PDF / RapidOCR 封装)
└── api.py+cli.py+main.py+__init__.py   1,024 行
根级 main.py + theme.py + test_fix.py    443 行  (2.1%)
```

**集中度**：Top 3 文件（`settings/dialog.py` 2,270 + `main_window/window.py` 2,030 + `workers/ocr_worker.py` 1,030）= **5,330 行 = 26.2%**；Top 5 = **35.7%**。

### 1.3 已交付能力清单（✅ 可用）

| 能力 | 状态 | 说明 |
|---|---|---|
| PDF 文本层脱敏 | ✅ | PyMuPDF 文本命中 + 去重 |
| PDF 扫描件 OCR 脱敏 | ✅ | RapidOCR 单页全流程 |
| PDF 混合型（文本+图片块） | ✅ | `ocr/mixed_pdf.py`：图片块发现 → clip → OCR → 坐标回写 |
| PDF 手动框选脱敏 | ✅ | `SinglePageCanvas` |
| Word 智能扫描 | ✅ | `WordWorker`，含 source 字段 |
| Word 手动精确/全局脱敏 | ✅ | |
| Word 多字段替换规则 | ✅ | exact / regex 双模式，run 级合并 |
| Word 批量替换 | ✅ | `.docx` / `.doc`（LibreOffice + antiword 兜底） |
| Word 双栏预览 | ✅ | mammoth → HTML → keyed DOM 增量 patch |
| 人工干预（忽略/确认/撤销/提升永久） | ✅ | `HitOverrideStore` 会话+永久双层 |
| 黑/白名单 | ✅ | 含 v38 片段级豁免（`whitelist_trim_only`） |
| 中文姓名识别 | ✅ | jieba 启发式 + 三层过滤 + 强上下文注入（v1.1.13/1.1.14） |
| 部分遮蔽（partial masking） | ✅ | `utils/masking.py`，按规则 meta 保留前后缀 |
| 业务 API 门面 | ✅ | `api.py` 7 个函数，100% 覆盖门槛（当前 92%） |
| CLI | ✅ | `cli.py`: version / scan / redact / redact-word |
| 拖拽打开 | ✅ | |
| Windows / macOS 打包脚本 | ⚠️ | 存在，但有硬缺陷（见 §5.4） |

---

## 2. 开发进度

### 2.1 阶段 / PR 进度总表

共识别 **34 个有实质定义的阶段编号**（B0/B1/B2.0–B2.8/B3/B4/B5/B5.1/B5.2、C1/C1.1/C2.x/C3–C9、V1–V4、计划 P1–P5、v39 七 Phase）。

| 状态 | 数量 | 明细 |
|---|---:|---|
| ✅ 已完成 | **38** | B 系列 14 项、C 系列 17 项、V 系列 2 项、计划 P1/P2/P4/P5 |
| ⚠️ 部分完成 | **4** | PR-B5（入口已切，shim 未移除）、PR-C9（代码层完成，功能层验收缺失）、PR-V1/PR-V3（代码在未合并分支）、计划 P3（残留 2 处 `from main import`） |
| ❌ 未开始 | **9** | PR-C1.1（主题切换 UI）、PR-V4（内嵌 QSS 迁移）、v39 Phase 1–7、PR-W |
| 📄 代码已落地但无完成报告 | **12** | PR-C3/C4/C5.x/C6.x/C7/C8 等 |

### 2.2 各阶段明细（只列有决策价值的）

| 阶段 | 目标 | 状态 | 证据 commit |
|---|---|---|---|
| PR-B0 | `secureredact/main.py` 入口 + `main.py` 转 shim | ✅ | `e4426a7` |
| PR-B1 | `ui/styles/` 子包（tokens + qss + loader） | ✅ | `e4426a7` |
| PR-B2.0–B2.8 | MainWindow 拆 9 mixin（工具栏/工作台/Word预览/PDF/批量/密度/装配/处理/…） | ✅ | `e4426a7` + `99ab8ef` |
| PR-B3/B4 | SettingsDialog + 3 个对话框 + 批量 worker 迁出 | ✅ | `89a842b` |
| **PR-B5** | **入口收口 + 移除 main.py shim** | ⚠️ **入口已切，shim 未移除** | `89a842b` |
| PR-C1 | DARK/LIGHT/SYSTEM 主题切换入口（代码层） | ✅ | `911014f` |
| **PR-C1.1** | **SettingsDialog 主题切换 UI + 持久化** | ❌ **未开始** | — |
| PR-C2.x | 视觉基线（compare + generate + manifest + 4 PNG + CI） | ✅ | `39589ab`…`d3241e4` |
| PR-C3–C6.5 | 规则/配置/常量迁出（word_rules / api / SimpleConfig / DEFAULT_RULES …） | ✅ | `299fcaa`…`b0a7fcb` |
| PR-C5.1–C5.4 | GUI mixin 切 API（4 处调用点） | ✅ | `ae7b3ff`/`ab79a49`/`a873968`/`9d562b0` |
| PR-C7 | pytest markers + GitHub Actions CI | ✅ | `6703a3a`/`c0005ba`/`40ed73b` |
| PR-C8 | CLI 薄壳 | ✅ | `bfc916a` |
| PR-C9 | MainWindow 物理搬迁到 `ui/main_window/window.py` | ✅ 代码 / ⚠️ 验收缺失 | `aa960eb`…`72208e7` |
| PR-V1 §6 | Glass 降级检测模块 | ✅ | `4c1ace4` |
| **PR-V1 / PR-V3** | **tokens 体系化（16→44 token）+ 平台检测** | ⚠️ **10 个 commit 仅在未合并分支** | `feature/visual-tokens-v1` |
| PR-V2 | 6 类组件 `.qss` + loader scope 扩展 | ✅ | `df3fc51`…`3a62724` |
| **PR-V4** | **内嵌 QSS → `.qss`（83 处 `setStyleSheet`）** | ❌ **未开始** | — |

### 2.3 开发活动节奏

```
2026-02 中～下   16 commits   早期功能迭代
2026-05           15 commits   低速维护
2026-06～08-15    0 commits   完全停滞（9 周）
2026-08-16～19    64 commits   爆发期①：v1.1.13 姓名上下文 + 人工干预 + 白名单片段级豁免
2026-08-27～09-01 60 commits   爆发期②：阶段 B 全量 → 阶段 C（API/CI/CLI/搬迁）→ PR-V2
2026-09-01～11-12  0 commits   完全停滞（72 天）
```

**特征**：典型的 **"AI 辅助爆发 → 无验收 → 停摆"** 模式。两次爆发共 124 个 commit 完成了 80% 的工作量，但：
- 从未合并到 `main`（`main` 落后 66 commits）
- 从未打 tag、从未发版（最近 tag 是 `v38.0.1-pdf-baseline`，8 月前）
- 从未在真机做打包验证
- PR-V1/V3 的 10 个 commit 遗留在未合并分支

### 2.4 文档与代码一致性核查（10 项偏差）

| # | 文档声明 | 实测 | 严重度 |
|---|---|---|---|
| 1 | `frontend-refactor-plan.md` 是阶段 B 路线图 | **该文件从未进入版本库**（`git log --all` 0 命中），只存在于开发者本地目录 | 🔴 |
| 2 | `docs/current/DEV_LOG.md` 是"继续开发前必读"第 3 项 | 已被 `95f2ea7` 删除，`PROJECT_INDEX.md` 仍指向它 | 🔴 |
| 3 | PR-B5 "移除 main.py shim" | 253 行 shim + 40 余条 re-export 原样保留 | 🔴 |
| 4 | 计划里程碑 M3：`from main import` 0 命中 | 残留 `handlers.py:381`、`setup_ui.py:40` | 🔴 |
| 5 | CLAUDE.md "已知 2 项失败" | 实测 **4 项** | 🟠 |
| 6 | PR-V1/V3 已完成 | 10 个 commit 未合并；tokens 仍只有 16 个颜色 token；`theme.py` 仍硬编码 hex（**双源未消除**） | 🟠 |
| 7 | v39.0.0 七 Phase 路线图 | 被 `95f2ea7` **误删**（清理脚本按"PrivacyGuard 旧文件"归类），主线无任何记载；GSD 三 Phase 约 60 份文档仅存于废弃分支 | 🟠 |
| 8 | `docs/current/STATUS.md` | 停在 v1.1.11，**完全未记录阶段 B/C/V 任何一项**，1488 行是 2026-03～08 的 UI 微调流水账 | 🔴 |
| 9 | `.project_info` | 版本 v23.3 / 2026-02-11，导航到的 5 个文件全部不存在 | 🟠 |
| 10 | `docs/planning/gui-api-refactor-plan.md` §2.2 产出 `API_REFERENCE.md` | 文件不存在 | 🟡 |

**版本口径 19 处引用中仅 4 处同步**（`version.txt` 1.1.13 / `secureredact/__init__.py` fallback 1.1.12 / `main.py` fallback 1.1.12 / `window.py` fallback 1.1.12 / Inno Setup 默认 1.1.11 / `config.DEFAULT_CONFIG` 1.0 / README 1.1.11 / AGENTS.md 1.1.11 / STATUS.md 1.1.11 …）。

---

## 3. 质量现状

### 3.1 测试与 CI

**实跑结果**（Windows · Python 3.13.5 · `QT_QPA_PLATFORM=offscreen`）：

| 指标 | 数值 |
|---|---|
| 收集用例 | **604**（60 模块） |
| 通过 | **564**（93.4%） |
| 失败 | **20** |
| 跳过 | **20**（全部因缺样本文件或占位场景，**无一是缺依赖**） |
| 错误 | 0 |
| 耗时 | **15.1s** |
| `secureredact` 全包覆盖率 | **40%**（10,438 stmt / 6,287 miss） |

**20 个失败的分类**（关键判断：只有 4 例是真缺陷）：

| 类别 | 数量 | 性质 | 处理 |
|---|---:|---|---|
| A 测试断言锚定旧代码位置 | 8 | 测试滞后 | 锚点从 `main.py` 改到 `secureredact/redaction/rules_loader.py` / `ui/main_window/theme.py` / `secureredact/__init__.py` |
| B 版本回退值漂移 | 2 | **产品缺陷** | 统一 fallback 为 1.1.13 |
| C **配置双源分裂** | 2 | **产品缺陷（最高）** | 合并两个 `config.json` |
| D 路径校验跨平台 | 4 | 测试问题 | 用 `tempfile.mkdtemp()`/`Path.home()` 替代写死的 `C:\Users\Admin` |
| E 默认白名单断言过期 | 1 | 测试问题 | 同步新默认值 |
| F 规则重叠 / 契约变更 | 2 | 混合 | 规则去重 + jieba 严格模式用例更新 |

**CI 逐条复现 —— 三个步骤必然让 job 失败**：

| CI 步骤 | 实测 | 退出码 |
|---|---|---|
| `compileall` | 通过 | 0 |
| `pytest -m smoke` | 10 passed | 0 |
| `pytest -m api --cov=secureredact.api --cov-fail-under=100` | 22 passed 但覆盖 **91.77%** | **1** |
| `pytest -m "not slow"` | **20 failed** | **1** |
| `python scripts/render_visual_baseline.py` | **`ModuleNotFoundError: No module named 'secureredact'`**（脚本未把仓库根加入 `sys.path`） | **1** |
| `unittest tests.unit.test_visual_baseline` | 渲染成功后仍 2 例失败：`settings_dialog_dark` 差异 **14.37%**、`settings_dialog_light` **14.24%**（阈值 0.5%） | 0 |

> **判定：这条流水线长期是红的，或者从未被真正执行过。** 覆盖率门槛从未拦住过任何东西。

**CI 结构性隐患**（17 项，Top 8）：

| # | 隐患 | 严重度 |
|---|---|---|
| 1 | 覆盖率门槛当前必失败（92% < 100%） | 🔴 |
| 2 | 视觉渲染脚本 `sys.path` 缺失 → 必失败 | 🔴 |
| 3 | 视觉基线本身已失效（14% 差异） | 🔴 |
| 4 | `pip install -r requirements.txt || true` 吞掉安装失败 → 缺依赖时全变 skip，**CI 照样绿** | 🔴 |
| 5 | 全量测试步骤 20 失败 | 🔴 |
| 6 | `slow` marker 全仓零使用 → `-m "not slow"` == 全量 604 例 | 🟠 |
| 7 | **无 macOS 矩阵**（项目却提供 macOS 打包链） | 🟠 |
| 8 | **无任何 artifact 产出**（失败时无 coverage.xml / junit.xml / 渲染 PNG 落盘） | 🟠 |

其余：除 api 外无覆盖率门槛、`integration` marker 零使用、无 `timeout-minutes`、无 `concurrency`、Actions 未按 SHA 固定、测试依赖未固定版本、`requirements.txt` 混装打包重量件、真实入口 `secureredact/main.py` **零覆盖**。

### 3.2 架构与分层

| 维度 | 评价 |
|---|---|
| 物理模块化 | 🟢 良好 —— 65 文件目录边界清晰 |
| 领域逻辑下沉 | 🟢 良好 —— 脱敏/遮蔽/白名单/姓名识别已正确下沉，**UI 层零残留业务正则**（全量扫描仅 7 处 HTML/字符串处理） |
| 入口迁移 | 🟢 基本完成 —— `main.py` 253 行 shim，`secureredact/main.py` 实测可导入、**MainWindow 可 offscreen 构造成功** |
| 依赖方向 | 🟡 部分违规 —— UI→Worker 5 处、UI→根 `main` 2 处、UI→根 `theme` 10 处、入口→shim 1 处 |
| 循环依赖 | 🟡 1 处定时炸弹（`ui/main_window/__init__.py:14` ↔ `window.py:97`，靠 import 顺序侥幸工作） |
| **API 层渗透率** | 🔴 **过低** —— `api.py` 463 行写好，UI 只用 3 处；双通道并存导致"哪条路是权威"不清晰 |
| 层内聚集度 | 🔴 过高 —— `ui/` 占 66.9%；两个文件各含一个 900+ 行单函数 |
| 可观测性 | 🔴 无 `logging` 模块；87 处库/UI/worker 层 `print()`；23 处纯静默吞错 |

**超大函数（>100 行）共 18 个**，最极端的 5 个：

| 位置 | 长度 |
|---|---:|
| `ui/main_window/setup_ui.py:37` `setup_ui` | **943 行**（占文件 96%） |
| `ui/main_window/density.py:37` `_refresh_windows_density_metrics` | **918 行**（占文件 96%） |
| `ui/settings/dialog.py:58` `SettingsDialog.__init__` | **800 行** |
| `ui/settings/dialog.py:1946` `_apply_dialog_theme` | 325 行 |
| `ui/settings/dialog.py:1345` `_apply_settings_density_styles` | 249 行 |

**技术债清单按严重度**：

| 级别 | 数量 | 代表 |
|---|---:|---|
| 🔴 S1 已产生可复现缺陷 | 6 | 主题永不落盘、zoom 上下限失效、progress 间隔失效、app.name 半生效、DEBUG_MODE 三处两义、shim 兼容测试 ERROR |
| 🔴 S2 结构性高风险 | 8 | 两个 900+ 行单函数、2,270 行设置中心、2,030 行上帝类（75 个死 import）、循环 import、2 处 `from main import`、入口反向依赖 shim、shim 120 个死 import |
| 🟠 S3 可观测性缺失 | 9 | 164 个 except（23 个纯静默）、8 处 `except: pass`、15 处类型化静默、12 处 fallback 赋值吞错、87 处 print、`handlers.py:421` 每次 OCR 打印全部规则 |
| 🟡 S4 工程卫生 | 7 | 4 个包缺 `__init__.py`、`secureredact/core/` 空占位包、2 处重复 import、死 import、启动时打印全部规则元数据、7 个 API 符号导入失败时置 None、三处配色定义 |
| ⚪ S5 TODO 标记 | **0 命中** | 技术债完全"隐形"——靠巨型函数/死代码/静默吞错承载，不靠 TODO 文本。**债没有可见性，就不会有人偿还** |

**已确认的 6 处行为漂移**：

| # | 主题 | 并存实现 | 实际生效 | 后果 |
|---|---|---|---|---|
| 1 | **配置源** | `ConfigManager`（读根 config.json） vs `SimpleConfig`（读 secureredact/config.json） | SimpleConfig | 🔴 **用户设置全部失效** |
| 2 | 缩放上下限 | `__init__.py` 硬编码 0.5/4.0 vs config 派生 | 硬编码 | `ocr.zoom_min/max` 死配置 |
| 3 | 进度节流 | `main.py` config 派生 vs worker 硬编码 0.05 | 硬编码 | `ocr.progress_update_interval` 死配置 |
| 4 | 应用名 | `__init__.py` 硬编码 vs config 派生 | 两者并用 | 窗口标题跟随配置、反馈框不跟随 |
| 5 | DEBUG 开关 | `canvas.py` 仅 env vs 另两处 env+config | 语义不同 | 调试输出静默化 |
| 6 | 主题持久化 | `window.py` 读 `app.theme` vs `theme.py` 写 `getattr(self,"config",None)` | 写侧失效 | 主题永不落盘 |

### 3.3 打包与发布

| 维度 | 状态 |
|---|---|
| 打包链路 | Windows 主链（`build_complete.bat`，7 阶段）完整；macOS `build_macos_app.sh` 因图标文件名错误 **100% 失败**（检查 `SecureRedact.icns`，实际是重命名遗留的 `PrivacyGuard.icns`）；Windows v2 spec 是无人引用的死代码 |
| 入口一致性 | ✅ 3 个 spec + `start_app.sh` 全部指向 `secureredact/main.py`；❌ 但运行时仍强依赖根 `main.py`（3 处 import，其中 2 处致命） |
| `version.txt` | ❌ **三个 spec 的 `datas` 均未包含** → 冻结后 fallback 到 `"1.1.12"`，而 EXE 属性是 1.1.13 → **窗口标题、关于窗口、EXE 属性三处版本号互不相同** |
| 配置文件 | ❌ 运行时读 `secureredact/config.json`，spec 却打包**根** `config.json` → **打包版配置 100% 丢失**，且 `save()` 写向 Program Files 只读位置 → 设置静默丢失 |
| `theme.py` | ⚠️ 位于仓库根、不在包内，被 10 个 UI 模块 import —— B5 收口的隐式约束，必须写进计划 |
| 依赖 | 9 类问题：缺失 3 / 多余 2 / 无上限 2 / 未固定 1 / 版本错位 1。**最高风险：`pyinstaller-hooks-contrib` 未固定** —— 实测 pyinstaller 6.18.0 内置 353 个 hook **不含 jieba**，其 5MB `dict.txt` 完全靠 hooks-contrib 的 `hook-jieba.py` 进包；失效则**打包版姓名识别静默降级、无任何报错** |
| LICENSE | ⚠️ 完整 GPL-3.0 全文，与闭源商业定位冲突；Inno Setup 未附许可证、无第三方许可清单 |
| 其他 | `config.json` 与 `secureredact/config.json` **均被 git 跟踪**，含个人词条（`"0432"`、`"吉铁"`、`"丰满区"`）；`.gitignore:27` 的 `*.spec` 会静默忽略任何新 spec；`README_EN.md:169` 的 "GPL **v1.1.11**" 是 37.x→1.1.x 批量替换误伤 |

---

## 4. 关键风险登记（Top 10，按"影响 × 可能性"排序）

| # | 风险 | 影响 | 可能性 | 证据 |
|---|---|---|---|---|
| 1 | **配置双源分裂** | 用户所有设置失效；打包版配置全丢 | **已发生** | `utils/config.py:641` 路径解析 |
| 2 | **CI 长期全红** | 质量门禁形同虚设，重构可无感退化 | **已发生** | 逐条复现三步退出码 1 |
| 3 | **spec 缺 `version.txt`** | 打包版显示 1.1.12 | **已发生** | 三份 spec 的 datas 段 |
| 4 | **主线未合并（落后 66 commits）** | 按 `main` 检出的开发者拿到 v1.1.13 旧代码；成果有丢失风险 | **已发生** | `git rev-list --count main..HEAD` = 66 |
| 5 | **根 `main.py` 无法删除** | "入口收口"名不副实；删除即运行期 ImportError | **已发生** | `setup_ui.py:40`、`handlers.py:381` |
| 6 | **PR-V1/V3 成果遗失** | tokens 双源未消除、`theme.py` 硬编码 hex 长期共存 | **已发生** | `git merge-base --is-ancestor` = exit 1 |
| 7 | **规则重叠** | 18 位身份证同时命中 3 条规则 → 重复遮蔽/误遮蔽 | **已发生** | `tests/scripts/test_word_processor.py` |
| 8 | **打包版姓名识别静默失效** | 核心功能在发布物中消失且无提示 | 中（hooks-contrib 失效时） | 实测 pyinstaller 无 jieba hook |
| 9 | **GPL-3.0 与闭源商业冲突** | 法律风险 | 中 | `LICENSE` 全文 |
| 10 | **覆盖率保护仅 1 个模块** | UI 层 1%–7% 覆盖，重构无保护 | **已发生** | `--cov=secureredact` = 40% |

---

## 5. 下一步开发建议

### 5.1 P0 — 立即修（约 2–3 天，解除阻塞）

> 目标：**把"能跑"变成"能交付"**。这一组不修，后面所有工作都在给一个用户设置失效、CI 全红、打包版残缺的基线上加码。

| # | 动作 | 位置 | 验收 |
|---|---|---|---|
| **P0-1** | **统一配置源**：`SimpleConfig` 默认路径改为「应用/项目根目录 `config.json`」，删除 `secureredact/config.json`；`ConfigManager` 若无生产调用则一并删除（省 415 行） | `secureredact/utils/config.py:628-641,195` | `config.get("redaction.replacement_text") == "*"`；`test_app_config` / `test_config_alignment` 变绿；**用户改配置立即生效** |
| **P0-2** | **spec 补 `version.txt`**，并把 `config.json` 打包路径改为运行时真实读取路径；`save()` 写用户目录（`%APPDATA%/$HOME`）而非只读安装目录 | 3 份 spec 的 `datas`；`utils/config.py` | 打包版标题显示 1.1.13；设置可保存并重启保留 |
| **P0-3** | **让 CI 变绿**：① `api.py` 补 13 行测试至 100%；② `scripts/render_visual_baseline.py` 加 `sys.path` 注入；③ 重新生成 `settings_dialog` 视觉基线（当前差 14%） | `tests/unit/test_api.py`、`scripts/render_visual_baseline.py`、`secureredact/ui/styles/baselines/` | 三步退出码全为 0 |
| **P0-4** | **修 16 个滞后测试**（A/D/E 类）：锚点改到新模块位置；路径测试改用 `tempfile.mkdtemp()`/`Path.home()` | `tests/unit/test_redaction_rule_patterns.py` 等 6 个文件 | 全量 604 用例 **0 失败** |
| **P0-5** | **修 4 个真缺陷**：版本 fallback 三处统一 1.1.13；`theme.py:79` 改用模块级 `config` 单例（或给 MainWindow 注入 `self.config`）恢复主题落盘；`ZOOM_MIN/MAX`、`PROGRESS_UPDATE_INTERVAL`、`APP_NAME`、`DEBUG_MODE` 统一到 config 单一源 | `secureredact/__init__.py:112-120`、`main.py:162-165`、`ui/main_window/theme.py:79`、`workers/ocr_worker.py:38`、`workers/word_worker.py:20`、`ui/main_window/canvas.py:31` | 改 config 后行为确实改变 |
| **P0-6** | **规则去重**：身份证/银行卡/统一社会信用代码三规则重叠命中时只保留优先级最高的一条（建议加统一命中后按规则优先级 + 位置合并） | `redaction/rules_loader.py` 或新增 `redaction/dedup.py` | 18 位身份证只命中 1 条规则 |
| **P0-7** | **清理版本库中的个人配置**：`config.json`、`secureredact/config.json` 移出版本库（保留 `config.json.template`）；`.gitignore` 修 `*.spec` 例外（`!packaging/**/*.spec`） | `.gitignore`、`config.json` | `git ls-files config.json` 为空 |
| **P0-8** | **合并到主线 + 打 tag**：`main` ← 当前分支，打 `v1.1.13` tag，推 `origin`；顺手把 `feature/visual-tokens-v1` 的 10 个 commit 评估后合入（PR-V1/V3 成果不能丢） | git | `git rev-list --count main..HEAD` = 0；CI 在 `main` 上绿 |

### 5.2 P1 — 收口（约 1 周，把"重构做完"）

| # | 动作 | 位置 | 价值 |
|---|---|---|---|
| P1-1 | **清掉 2 处 `from main import`**：`handlers.py:381` → 直接 `from secureredact.workers.ocr_worker import OCRWorker` 等；`setup_ui.py:40` → 从 `secureredact.ui.main_window` / `secureredact.ui.utils.density` 直接 import | `ui/main_window/handlers.py:381`、`ui/main_window/setup_ui.py:40` | **解除 PR-B5 阻塞** |
| P1-2 | **入口不再反向依赖 shim**：`init_ocr_engine()` 从根 `main.py` 迁入 `secureredact/ocr/manager.py` | `secureredact/main.py:107`、`main.py:87-112` | 真入口干净 |
| P1-3 | **删掉根 `main.py` + 同步打包脚本**（`build_complete.bat:23,109`、`1_init_environment.bat:79` 的 `main.py` 硬检查） | `main.py`、2 个 `.bat` | 阶段 B 真正收口 |
| P1-4 | **`theme.py` 迁入 `secureredact/ui/styles/`**，10 处 import 改指，**`tokens.py` 与 `theme.py` 二选一**（推荐 tokens 为唯一源，theme.py 改为薄适配层） | 根 `theme.py`、10 个 UI 模块 | 消除三处配色定义 |
| P1-5 | **打破循环 import**：`window.py:97` 改 `from .canvas import SinglePageCanvas` | `ui/main_window/window.py:97` | 消除定时炸弹 |
| P1-6 | **补 4 个 `__init__.py`**（`pii/`、`ui/dialogs/`、`ui/settings/`、`ui/utils/`），**删空包 `secureredact/core/`** | 同上 | PyInstaller 静态分析友好 |
| P1-7 | **清理约 165 个死 import**（`main.py` 约 90 + `window.py` 75） | `main.py:15-81`、`window.py:18-110` | 文件职责与内容一致 |
| P1-8 | **修 `pip install || true` 吞错**，CI 依赖安装失败必须红 | `.github/workflows/ci.yml` | 消除静默变绿 |

### 5.3 P2 — 质量门禁（约 1–2 周，让 CI 真的可信）

| # | 动作 | 细节 |
|---|---|---|
| P2-1 | **CI 矩阵补 macOS**（`macos-13`/`macos-14` + py3.11/3.13） | 项目已提供 macOS 打包链，CI 不跑等于没有保障 |
| P2-2 | **产出 artifact**：`coverage.xml` + `junit.xml` + `_current_*.png` + diff 图 | 失败可在线诊断，不必本地复现 |
| P2-3 | **覆盖率门槛扩展**到关键模块：`redaction/` + `pii/` + `ocr/` + `utils/masking.py`（建议 ≥85%），UI 层单独设宽松阈值 | 当前全包 40%，UI 1%–7% 无保护 |
| P2-4 | **真正启用 `slow`/`integration` marker**，CI 拆"快测（PR 必跑）/ 全量（每日）" | 现在 `-m "not slow"` == 全量 |
| P2-5 | **补测试到薄弱面**：`ui/main_window`（setup_ui 1% / density 1% / handlers 4% / batch_replace 7%）、批量替换全链路（当前仅 2 例单测）、`ocr/mixed_pdf` 坐标回写与去重分支（72% 未覆盖） | 三张测试文件为最高杠杆 |
| P2-6 | **引入 `logging`**：模块级 logger（INFO/WARNING/ERROR + 文件 handler），把 87 处库/UI/worker 的 `print` 迁过去 | 打包后 stdout 丢失 = 零可观测性 |
| P2-7 | **8 处 `except Exception: pass` 补日志**；其中 `settings/dialog.py:1881`（永久 override 回写失败）必须让用户看到失败 | 静默吞错是脱敏产品的合规风险 |
| P2-8 | **加 `timeout-minutes` / `concurrency` / 按 SHA 固定 Actions / 拆 `requirements-dev.txt`** | 低成本卫生 |

### 5.4 P3 — 产品与体验（约 2–4 周）

**建议顺序（每项都能独立交付、独立验收）：**

| # | 功能 | 说明 | 为什么现在做 |
|---|---|---|---|
| **P3-1** | **PR-V4：内嵌 QSS 收口** | 83 处 `setStyleSheet` → `.qss` 文件（`settings_dialog.qss` / `scroll.qss` / `batch_replace.qss` / `settings_density.qss`），同步拆掉 `setup_ui.py`（943 行）与 `density.py`（918 行）两个巨型单函数 | loader/scope/token 基础设施已就绪；这是唯一还在消耗"视觉 token"红利的路径；顺带解决两个单体文件 |
| **P3-2** | **PR-C1.1：SettingsDialog 主题切换 UI** | 加「外观」分节 + theme combo 联动 `MainWindow.set_theme` + 持久化验证（**先修 P0-5 的落盘缺陷**再做，否则切换后重启归位） | 代码层已支持 light/dark/system，但 GUI 无入口 —— 功能写了却用户不可达 |
| **P3-3** | **批量替换 per-file 规则映射（Phase 2）** | 每文件独立规则集；当前无任何脚手架（`per-file/per_file/rule_mapping` 全仓 0 命中） | CLAUDE.md 列为第一优先功能项，但代码零基础，属全新功能 |
| **P3-4** | **批量规则集模板** | 规则集导入/导出（JSON），可复用"合同/判决书/授权书"等场景 | 依赖 P3-3 的规则集数据结构 |
| **P3-5** | **预览高亮按来源过滤** | 左栏高亮支持按 `rule / manual / ocr` 筛选（当前 43 处 `source` 字段已有数据，但过滤 UI 零命中） | 数据已具备，纯 UI 工作量小、用户感知强 |
| **P3-6** | **补 `docs/current/API_REFERENCE.md` + 重写 `STATUS.md` / `AGENTS.md` / `CLAUDE.md`** | 让下一位接手者不会被 10 项文档偏差误导 | 文档债已造成实际误判（"main.py 仍是单体"） |

### 5.5 明确**不建议**做的事

| # | 不建议 | 理由 |
|---|---|---|
| 1 | ❌ **重新写一份 v39 七 Phase 路线图** | v39 计划已在 `95f2ea7` 被误删且内容从未验证；当前最缺的不是规划，而是**修缺陷 + 合主线 + 发一个版** |
| 2 | ❌ **继续扩张 `api.py` 的 GUI 渗透率** | `api.py` 463 行、UI 只用 3 处、GUI 走的是 worker 线程路径（架构上是同步 API vs 线程模型两套）；应**先决策**：要么让它成为 CLI/嵌入式的唯一门面并写清边界，要么就承认它是 headless 路径，不强行改 GUI |
| 3 | ❌ **在 CI 变绿之前发版** | 当前 CI 三个步骤必红，发版等于把"配置失效 + 版本显示错误"打进安装包 |
| 4 | ❌ **先做 UI 美化再修配置** | 用户设置失效是"功能不可用"，视觉优化是"体验改善"，优先级差一个量级 |
| 5 | ❌ **继续用 `print` 做库层日志** | 打包后 stdout 丢失即零可观测性，而这是脱敏/合规产品 |

### 5.6 流程建议（针对 72 天停摆的根因）

1. **建立发布列车**：每周一次 `main` 合并 + 全量回归 + 打 tag，而不是"爆发 124 个 commit 后停摆"。
2. **每个 PR 必须过 CI 绿灯 + `main.py` 行数/契约断言**，禁止"报告声称完成但 CI 是红的"。
3. **重构 PR 必须附功能层验收**（PR-C9 的验收签字缺失就是这个漏洞的产物）。
4. **路线图文档必须入库**（`frontend-refactor-plan.md` 只在本地目录、`DEV_LOG.md` 被误删、v39 计划被误删 —— 三次同类事故）。
5. **清理脚本要白名单化**：`95f2ea7` 把"正在进行的 v39 计划"按"PrivacyGuard 旧文件"误删，说明清理没有区分。

---

## 6. 附录：证据索引

### 6.1 本次分析产出的分项报告

| 报告 | 内容 | 行数 |
|---|---|---:|
| [01-architecture.md](01-architecture.md) | 模块地图 / 规模统计 / 分层评估 / 30 项技术债 / 6 项行为漂移 | 约 500 |
| [02-progress.md](02-progress.md) | 34 阶段总表 / 开发活动时间线 / 10 项文档偏差 / 未完成清单 | 479 |
| [03-testing-ci.md](03-testing-ci.md) | 60 模块清单 / 实跑结果 / 20 失败逐项分析 / CI 17 项隐患 / 覆盖薄弱面 | 444 |
| [04-release-deps.md](04-release-deps.md) | 打包链路 / 入口一致性 / 依赖对照 / 配置健康度 / P0×11 + P1×17 | 577 |

### 6.2 关键复现命令

```bash
# 编译检查
python -m compileall -q main.py secureredact tests

# 全量测试（604 用例）
QT_QPA_PLATFORM=offscreen python -m pytest tests -q

# API 覆盖率门槛（CI 同款，当前 92% < 100%）
QT_QPA_PLATFORM=offscreen python -m pytest -m api --cov=secureredact.api --cov-fail-under=100

# 视觉回归（CI 同款，当前 ModuleNotFoundError）
python scripts/render_visual_baseline.py

# 配置双源复现（应返回 '*'，实际返回 None）
python -c "import secureredact.utils.config as c; print(c.config.get('redaction.replacement_text'))"

# 入口一致性
python -c "import secureredact.main; print('secureredact.main OK')"
python -c "from PyQt6.QtWidgets import QApplication; a=QApplication([]); from secureredact.ui.main_window import MainWindow; MainWindow(); print('MainWindow OK')"

# 主线落后
git rev-list --count main..HEAD   # 66
```

### 6.3 引用文件（分析时读取的仓库内文档）

`docs/current/STATUS.md`（1488 行）、`docs/current/PROJECT_STRUCTURE.md`、`docs/current/RECOVERY_GUIDE.md`、`docs/planning/gui-api-refactor-plan.md`、`docs/planning/gui-api-refactor-REVIEWS*.md`、`docs/superpowers/plans/2026-08-30-{mainwindow-migration,visual-component-baseline,visual-tokens-foundation}.md`、`docs/superpowers/specs/2026-08-30-visual-style-decision-design.md`、`docs/refactor/*.md`（17 份）、`CLAUDE.md`、`AGENTS.md`、`CHANGELOG.md`、`PROJECT_INDEX.md`、`.project_info`、`packaging/**`、`.github/workflows/ci.yml`。
