# SecureRedact 开发进度与重构路线图分析报告

> 分析日期: 2026-11-12
> 分析对象: `G:\Project\SecureRedact\.agents\worktrees\dsh-3eb2fb3e-5817`(分支 `dsh-3eb2fb3e-5817`,与 `rename/secureredact` 同 tip `3a62724`)
> 版本基线: `version.txt` = **1.1.13**(注:CHANGELOG 最新条目为 1.1.14,详见第 3 节)
> 代码规模: `main.py` 253 行 / `secureredact/` 65 个 Python 模块 / `tests/unit/` 53 个测试文件、561 个用例
> 证据来源: `git log`(304 commits / 8 个分支)、`docs/refactor/` 17 份报告、`docs/planning/` 3 份计划、`docs/superpowers/` 4 份计划与 Spec、`CLAUDE.md` / `AGENTS.md` / `STATUS.md` / `CHANGELOG.md` / `PROJECT_INDEX.md` / `.project_info`、以及本机代码实测(grep / pytest 子集)

---

## 0. 关于 `frontend-refactor-plan.md` 的重要说明

任务要求阅读的**仓库根目录 `frontend-refactor-plan.md` 在本仓库中不存在**,证据如下:

| 检查项 | 命令 | 结果 |
|---|---|---|
| 工作区磁盘 | `Get-ChildItem -Recurse -Filter frontend-refactor-plan.md`(主仓 + worktree) | **0 命中** |
| Git 全历史 | `git log --all --oneline -- frontend-refactor-plan.md` | **0 命中**(该文件从未进入版本库) |
| 引用来源 | `docs/refactor/b0-report.md` 等 17 份报告的"关联文档"栏 | 一致指向 `frontend-refactor-plan.md` 阶段 B/B/C 章节 |
| `main.py` 注释 | 第 5–6 行 | "详见 `frontend-refactor-plan.md`(**OpenDesign 工作目录**)" |

**结论**:该计划是一份**只存在于开发者本地工作目录、从未入库**的路线图文档。仓库内可复现的等价物有三份,本报告以它们为准:

| 仓库内实际存在的计划 | 覆盖的阶段 |
|---|---|
| `docs/planning/gui-api-refactor-plan.md`(v1.2, 2026-08-29) | 阶段 P1–P5 ⇒ PR-C4 / C5.x / C6.x / C7 / C8 |
| `docs/superpowers/plans/2026-08-30-mainwindow-migration.md` | PR-C9(Task 1–6) |
| `docs/superpowers/plans/2026-08-30-visual-tokens-foundation.md` | PR-V1 + PR-V3 |
| `docs/superpowers/plans/2026-08-30-visual-component-baseline.md` | PR-C2.x → PR-V2 → PR-V4 → PR-C1.1(Plan 2b) |
| `docs/superpowers/specs/2026-08-30-visual-style-decision-design.md` | 视觉风格 Spec A(Dark + 微 Glass + 6 组件 + 降级) |
| **已从主线上被删除**: `.planning/ROADMAP.md`(v39.0.0, 7 Phase) | 仅存于 git 历史 `bfb88ea` 与废弃分支 `gsd/phase-2-local-attempt` |

此外,`docs/current/DEV_LOG.md`(任务要求阅读)**已不存在**:它在 `95f2ea7`(2026-08-31,"chore(cleanup): 移除 PrivacyGuard → SecureRedact rename 后的旧文件")中被一并删除,但 `PROJECT_INDEX.md` 至今仍把它列为"下次继续开发时先读"第 3 项。

---

## 1. 阶段总览表

### 1.1 阶段 / PR 编号总览

共识别出 **34 个有实质定义的阶段编号**(含 PR-B0/B1/B2.0–B2.8/B3/B4/B5/B5.1/B5.2、PR-C1/C1.1/C2.x/C3/C4/C4.0/C5.x/C6.x/C7/C8/C9、PR-V1/V2/V3/V4、计划 P1–P5)。另有 14 处 `PR-XXX` 占位符(PR-C9 前的临时命名,已在 `d9a725d` 统一替换)与 1 处 `PR-W`(Word 替换规则编辑器重做,独立轨道,见 `visual-component-baseline.md` §范围外)。

### 1.2 主表:阶段 / 目标 / 状态 / 日期 / 证据 commit

#### 阶段 B — 前端重构主体(MainWindow 拆分 / 入口迁移)

| 阶段 | 目标 | 状态 | 报告声称日期 | 证据 commit(实际日期) |
|---|---|---|---|---|
| **PR-B0** | 新建 `secureredact/main.py` 运行时入口; `main.py` 转 thin shim; 落 `tests/ui/` 视觉基线框架; `tests/scripts/test_ci.sh` CI 套件; 三处 deprecation 提醒 | ✅ 已完成 | 2026-08-25 | `e4426a7`(2026-08-27,综合集成,30 文件) |
| **PR-B1** | `secureredact/ui/styles/` 子包:Tokens dataclass + 6 个 `.qss` + `StylesheetLoader`; `_apply_light_theme` 615→58 行; DARK 内部 API 打通 | ✅ 已完成 | 2026-08-26 | `e4426a7`(2026-08-27) |
| **PR-B2.0** | `secureredact/ui/main_window/` 骨架; 迁出 `SinglePageCanvas` + `WebViewBridge`; `identifiers.py` 97 个 objectName 常量; 落实 1 张视觉基线 | ✅ 已完成 | 2026-08-26 | `e4426a7`(2026-08-27) |
| **PR-B2.1** | 工具栏 + 密度自适应 → `toolbar.py` mixin(13 方法,548 行) | ✅ 已完成 | 2026-08-27 | `e4426a7`(2026-08-27) |
| **PR-B2.2** | 工作台 + info_bar + 状态徽章 → `workbench.py` mixin(17 方法) | ✅ 已完成 | 2026-08-27 | `e4426a7`(2026-08-27) |
| **PR-B2.3** | Word 双栏预览 → `word_preview.py` mixin(19 方法,700 行) | ✅ 已完成 | 2026-08-27 | `99ab8ef`(2026-08-28,13 文件) |
| **PR-B2.4** | PDF 渲染编排 → `pdf_render.py` mixin(13 方法) | ✅ 已完成 | 2026-08-27 | `99ab8ef`(2026-08-28) |
| **PR-B2.5** | 批量替换编排 → `batch_replace.py` mixin(25 方法,805 行) | ✅ 已完成 | 2026-08-27 | `99ab8ef`(2026-08-28) |
| **PR-B2.6** | 918 行 `_refresh_windows_density_metrics` → `density.py` mixin | ✅ 已完成 | 2026-08-27 | `99ab8ef`(2026-08-28) |
| **PR-B2.7** | 925 行 `setup_ui` → `setup_ui.py` mixin | ✅ 已完成 | 2026-08-27 | `99ab8ef`(2026-08-28) |
| **PR-B2.8** | 10 个大型 UI 方法 → `handlers.py` mixin(864 行) | ✅ 已完成 | 2026-08-27 | `99ab8ef`(2026-08-28) |
| **PR-B3** | SettingsDialog(2,213 行)→ `secureredact/ui/settings/dialog.py`(2,259 行) | ✅ 已完成 | 2026-08-27 | `89a842b`(2026-08-28,11 文件) |
| **PR-B4** | 其他对话框迁移: `feedback.py` / `image_list.py` / `word_replace_rules.py` + `WordBatchReplaceWorker` → `secureredact/workers/` | ✅ 已完成 | 2026-08-27 | `89a842b`(2026-08-28) |
| **PR-B5** | 入口收口: main.py 6,653→3,772 行; 打包入口切 `secureredact/main.py`; 移除 main.py shim | ⚠️ **部分完成**(shim 未移除,见 §3.2-1) | 2026-08-27 | `89a842b`(2026-08-28) |
| **PR-B5.1** | 密度工具迁出 `secureredact/ui/utils/density.py` + main.py re-export | ✅ 已完成 | — | `a9f1701`(2026-08-30) |
| **PR-B5.2** | workbench/toolbar/word_preview/settings 辅助函数迁出(`_helpers.py` / `_batch_helpers.py` / `settings/_helpers.py`); 修补 12 文件漏迁符号 | ✅ 已完成 | — | `a9f1701` + `b27725e`(均 2026-08-30) |

**阶段 B 累计**(`b3-b4-b5-report.md` §5):`main.py` **13,011 → 3,772 行(−71.0%)**;最终经 PR-C9 再降至 253 行。

#### 阶段 C — 业务 API 化 / 主题 / CI / CLI / MainWindow 物理搬迁

| 阶段 | 目标 | 状态 | 报告声称日期 | 证据 commit(实际日期) |
|---|---|---|---|---|
| **PR-C1** | DARK/LIGHT/SYSTEM 三模式主题切换入口(`secureredact/ui/main_window/theme.py` mixin,MRO 第 10 层) | ✅ 已完成 | 2026-08-27 | `911014f`(2026-08-28) |
| **PR-C1.1** | SettingsDialog 增加主题切换 UI + `_on_theme_changed` callback + `app.theme` 持久化 | ❌ **未开始** | — | 无 |
| **PR-C2.x** | 视觉基线建立: `styles/baselines/compare.py`(compute_diff + 0.005 threshold)+ `_generate_baselines.py` + manifest + 4 张基线 PNG + CI 回归 step | ✅ 已完成 | 2026-08-31 | `39589ab` / `334dc65` / `5922a53` / `d3241e4`(均 2026-08-31) |
| **PR-C3(.x)** | main.py 模块级 Word 规则工具函数 → `secureredact/redaction/word_rules.py` | ✅ 已完成(**无完成报告**) | — | `299fcaa`(2026-08-28) |
| **PR-C4** | 业务 API 层骨架 `secureredact/api.py`:7 个函数 + 顶层转发 + `tests/unit/test_api.py` | ✅ 已完成(**无完成报告**) | — | `b3fc551`(2026-08-30) |
| **PR-C4.0** | REVIEWS-v2 C-1: worker 内联 `_shared_convert_doc_to_docx`,修 `.doc` 路径 100% NameError | ✅ 已完成 | — | `e08293d`(2026-08-30) |
| **PR-C5** | 4 个 stub 函数完整实现(`scan_pdf` / `scan_word` / `redact_pdf` / `redact_word`) | ✅ 已完成(**无完成报告**) | — | `32bab50`(2026-08-30) |
| **PR-C5.1** | `handlers.py` 切 API | ✅ 已完成(**无完成报告**) | — | `ae7b3ff`(2026-08-30) |
| **PR-C5.2** | `batch_replace.py` 切 API | ✅ 已完成(**无完成报告**) | — | `ab79a49`(2026-08-30) |
| **PR-C5.3** | `word_preview.py` 切 API | ✅ 已完成(**无完成报告**) | — | `a873968`(2026-08-30) |
| **PR-C5.4** | `pdf_render.py` 切 API | ✅ 已完成(**无完成报告**) | — | `9d562b0`(2026-08-30) |
| **PR-C6.1** | 迁出 `WORD_RULE_SCHEMA_VERSION` | ✅ 已完成(**无完成报告**) | — | `eb317a6`(2026-08-30) |
| **PR-C6.2** | 迁出 `ZOOM_MIN` / `ZOOM_MAX` | ✅ 已完成(**无完成报告**) | — | `237527b`(2026-08-30) |
| **PR-C6.3** | 迁出 `APP_NAME` / `VERSION` | ✅ 已完成(**无完成报告**) | — | `132f910`(2026-08-30) |
| **PR-C6.4** | 迁出 `SimpleConfig` + 全局 config singleton | ✅ 已完成(**无完成报告**) | — | `db8cc18`(2026-08-30) |
| **PR-C6.5** | 迁出 `DEFAULT_RULES` / `DEFAULT_RULES_META` → `secureredact/redaction/rules_loader.py` | ✅ 已完成(**无完成报告**) | — | `b0a7fcb`(2026-08-30) |
| **PR-C7** | 测试矩阵: `pytest.ini` markers + `test_api_smoke` + `test_main_window_import_smoke` + GitHub Actions `ci.yml` | ✅ 已完成(**无完成报告**) | — | `6703a3a` / `c0005ba` / `40ed73b`(均 2026-08-30) |
| **PR-C8** | CLI 薄壳 `secureredact/cli.py` + `tests/unit/test_cli.py` | ✅ 已完成(**无完成报告**) | — | `bfc916a`(2026-08-30) |
| **PR-C9** | MainWindow 主体(2,689→2,031 行)物理迁至 `secureredact/ui/main_window/window.py`; `_INTERACTIVE_JS_CODE` 抽至 `_js_constants.py`; 入口切新路径 | ✅ 已完成(代码层);⚠️ 功能层未复跑 | 2026-08-30 | `aa960eb` → `510608c` → `562affb` → `4d6631c` → `7c33890` → `7327cff` → `72208e7` → `49e9322`(2026-08-30);修复 `bc7c832`(08-30) |

#### 阶段 V — 视觉层(tokens 体系化 / 组件 .qss / 内嵌 QSS 迁移)

| 阶段 | 目标 | 状态 | 报告声称日期 | 证据 commit(实际日期) |
|---|---|---|---|---|
| **PR-V1** | tokens 体系化:16→17 颜色 token + 28 个非颜色 token(圆角/间距/阴影/动效/字体); `Theme.LIGHT/DARK` 从 tokens 派生(消除双源) | ❌ **仅在未合并分支** | — | `aeefe6c` / `d0fd25c` / `ac3956f` / `0944a4b` / `2a53c9a` / `d29b193` — **全部只在 `feature/visual-tokens-v1`**(`git merge-base --is-ancestor d29b193 HEAD` → exit=1) |
| **PR-V3** | `_platform.py` 平台检测 + `StylesheetLoader.glass_supported` 启动期检测 | ⚠️ **部分**:HEAD 上仅有 `glass.py`; `_platform.py` 未合并 | — | `053da21` / `9cbbce6` / `8719f50`(均在未合并分支) |
| **PR-V1 §6** | Glass 降级检测模块 `secureredact/ui/styles/glass.py` | ✅ 已完成(已 cherry-pick 进主线) | 2026-08-31 | `4c1ace4`(2026-08-31) |
| **PR-V2** | 6 类组件 `.qss`(`button` / `card` / `tab` / `input` / `dock` + `toolbar`/`workspace` 复用)+ `StylesheetLoader` scope 扩展 + glass 替换合并 | ✅ 已完成 | 2026-09-01 | `df3fc51` / `d57ae16` / `4913f7f` / `8b096d1` / `d1cc895` / `e7306f5` / `8353633` / `3a62724`(均 2026-09-01) |
| **PR-V4** | MainWindow / SettingsDialog 内嵌 QSS → `loader.apply`(41 处 `setStyleSheet` + `settings_dialog.qss` + `scroll.qss` + `settings_density.qss` 等) | ❌ **未开始** | — | 无(`settings_dialog.qss` / `scroll.qss` / `batch_replace.qss` 均不存在) |

#### 计划 P1–P5(`gui-api-refactor-plan.md` §1 阶段总览)

| 阶段 | 主题 | 计划 PR | 状态 | 证据 |
|---|---|---|---|---|
| **P1** | API 化骨架 | PR-C4 | ✅ 已完成 | `b3fc551` |
| **P2** | GUI mixin 切换为 API | PR-C5.x(4 子 PR) | ✅ 已完成 | `32bab50` + `ae7b3ff`/`ab79a49`/`a873968`/`9d562b0` |
| **P3** | 清掉 mixin 里的 `from main import X` | PR-C6.x | ⚠️ **未完成**(见 §3.2-2) | `eb317a6`…`b0a7fcb` 已做 5 个符号,残留 2 处 |
| **P4** | 测试矩阵与门槛设置 | PR-C7 | ✅ 已完成 | `6703a3a`/`c0005ba`/`40ed73b` |
| **P5**(可选) | CLI 薄壳 | PR-C8 | ✅ 已完成 | `bfc916a` |

#### 计划阶段 A / v39.0.0 七 Phase(已从主线删除)

| 阶段 | 目标 | 状态 | 证据 |
|---|---|---|---|
| **v39.0.0 Phase 1** | 基线、Fixture 治理与接口契约冻结 | ❌ 未开始(文档已删) | `.planning/ROADMAP.md` @ `bfb88ea`,2026-08-19 |
| **v39.0.0 Phase 2** | Story 遍历与可逆坐标映射 | ❌ 未开始 | 同上 |
| **v39.0.0 Phase 3** | Strangler 架构抽取 + 命中合并与写回 | ❌ 未开始 | 同上 |
| **v39.0.0 Phase 4** | 数字、Unicode、隔符号规则 | ❌ 未开始 | 同上 |
| **v39.0.0 Phase 5** | 姓名、地名、地址上下文调优 | ❌ 未开始 | 同上 |
| **v39.0.0 Phase 6** | 嵌入图 OCR 与预览一致性 | ❌ 未开始 | 同上 |
| **v39.0.0 Phase 7** | 批量替换、性能、安全与发布回归 | ❌ 未开始 | 同上 |
| **GSD 01-pdf / 02-pdf / 03-word** | 3 个 Phase 的完整 PLAN/SUMMARY/VERIFICATION 文档集(约 60 个 md) | ⚠️ 仅存于废弃分支 | `gsd/phase-1-pdf`(`e885cb0`, 2026-08-12)、`gsd/phase-2-local-attempt`(`bbb5f75`, 2026-08-12) |

> **"阶段 A"**:在仓库所有文档中 **grep "阶段 A" / "PR-A" 均 0 命中**。可推断 A 系列属于那份未入库的 `frontend-refactor-plan.md`(A → B0/B1 → B2 → B3/B4/B5 → C → V 的顶层骨架),无法从仓库内复原。

### 1.3 状态统计

| 状态 | 数量 | 明细 |
|---|---|---|
| ✅ 已完成 | **38** | B 系列 16 项(B0/B1/B2.0–B2.8/B3/B4/B5.1/B5.2 = 14)+ C 系列 19 项(C1/C2.x/C3/C4/C4.0/C5/C5.1–C5.4/C6.1–C6.5/C7/C8/C9 = 17)+ V 系列 2 项(V1 §6 / V2)+ 计划 P1/P2/P4/P5 = 4 + PR-C9 子任务 8 视为 1 个 PR → 合计 **38 个 PR 级阶段** |
| ⚠️ 部分完成 / 未达验收 | **4** | PR-B5(shim 未移除)、PR-C9(功能层未复跑)、PR-V1 / PR-V3(未合并分支)、计划 P3(残留 2 处 `from main import`) |
| ❌ 未开始 | **9** | PR-C1.1、PR-V4、v39.0.0 Phase 1–7、PR-W(Word 规则编辑器,独立轨道) |
| 📄 纯计划文档(无独立报告) | **12** | PR-C3 / C4 / C5.x / C6.x / C7 / C8 — 代码已落地但 `docs/refactor/` 无对应完成报告 |

---

## 2. 开发活动时间线

### 2.1 每周 commit 数(ISO 周,全部 8 个分支)

```text
2026-W08   8   (2 月中)
2026-W09   8   (2 月下旬)
2026-W18  14   (5 月初)
2026-W20   1   (5 月中)
2026-W33 134   (8/17–8/23)  ← 爆发期 ①
2026-W34  65   (8/24–8/30)  ← 爆发期 ②(阶段 B + 阶段 C)
2026-W35  41   (8/31–9/6)   ← 爆发期 ③(PR-C9 CI 修复 + PR-V2)
2026-W36  24   (9/7–9/13)
─────────────────────────────
W37–W45   0   ← 完全停滞(约 10 周)
总计      304  (8 个分支)
```

**近 3 个月(2026-08-12 至今)按日明细**:

```text
2026-08-16   2      2026-08-28   4
2026-08-17  23      2026-08-30  31   ← 单日峰值
2026-08-18  18      2026-08-31  15
2026-08-19  21      2026-09-01   9
2026-08-24   3      2026-09-02 之后  0
2026-08-25   2
2026-08-27   1
```

### 2.2 活跃期与停滞期

| 时期 | 活跃度 | 主要内容 |
|---|---|---|
| 2026-02 中 ~ 2026-02 下 | 低(8+8) | 早期功能迭代 |
| 2026-05 | 极低(14+1) | 几乎停滞,仅少量维护 |
| 2026-06 ~ 2026-08-15 | **0 commit** | 完全停滞(约 9 周) |
| **2026-08-16 ~ 2026-08-19** | **高(2+23+18+21 = 64)** | v37.8.0 人工干预机制 / 黑名单白名单 / v38 白名单片段级豁免 / v39 路线图 |
| **2026-08-27 ~ 2026-09-01** | **高(1+4+31+15+9 = 60)** | **阶段 B 全量落地 → 阶段 C (API 化 / CI / CLI / MainWindow 搬迁) → PR-C9 CI 修复 → PR-V1/V2 视觉层** |
| **2026-09-01 之后** | **0 commit** | **完全停滞 ≈ 10 周(2026-09-01 → 2026-11-12)** |

### 2.3 关键时间点

| 日期 | 事件 |
|---|---|
| 2026-08-19 | v1.1.13 发布(姓名上下文注入);改名为 SecureRedact;v39.0.0 路线图(7 Phase)写入 `.planning/`;**`main` 分支在此停住不再前进** |
| 2026-08-27 | 阶段 B 综合集成落地(`e4426a7`,30 文件) |
| 2026-08-28 | B2.3–B2.8(`99ab8ef`)+ B3/B4/B5(`89a842b`)+ C1(`911014f`)+ C3(`299fcaa`) |
| 2026-08-30 | 计划文档(`2671426`)+ C4/C5.x/C6.x/C7/C8 全量(`b3fc551`…`bfc916a`)+ PR-C9 Task 1–6(`aa960eb`…`49e9322`)+ B5.2(`a9f1701`/`b27725e`) |
| 2026-08-31 | PR-C2.x 视觉基线(`39589ab`…`d3241e4`)+ PR-V1 §6 glass(`4c1ace4`)+ **删除 `.planning/` 全套 v39 计划 + `docs/current/DEV_LOG.md`**(`95f2ea7`) |
| 2026-09-01 | PR-V2 7 个 commit + 完成报告(`3a62724`)—— **全仓库最后一次提交** |
| 2026-09-01 → 2026-11-12 | **零提交,零 PR,零发版(10 周)** |

### 2.4 分支拓扑与"主线落后"

| 分支 | tip | 日期 | 状态 |
|---|---|---|---|
| `main` | `65b7006` | 2026-08-19 | **落后 HEAD 66 个 commit**,停留在 v1.1.13 |
| `rename/secureredact` = `dsh-3eb2fb3e-5817` | `3a62724` | 2026-09-01 | **实际工作主线**(阶段 B/C/V 全部在此) |
| `feature/visual-tokens-v1` | `d29b193` | 2026-08-31 | **PR-V1/V3 完整实现停留在此,从未合并** |
| `origin/rename/secureredact` | `2730a54` | 2026-09-01 | 落后本地产线 8 个 commit(PR-V2 未推) |
| `fix/pii-e2e` / `gsd/phase-1-pdf` / `gsd/phase-2-local-attempt` | — | 2026-08-12 ~ 08-17 | 已废弃(承载 v39 的 3-Phase 完整计划文档) |
| `backup/main-local-20260817` | `f496ec5` | 2026-08-11 | 备份分支 |

> ⚠️ **所有阶段 B / C / V 的重构成果都没有落到 `main` 分支上**。任何按 `main` 检出的开发者拿到的是 v1.1.13 时代的旧代码。

---

## 3. 文档与代码一致性核查

按"文档声称 → 代码实测 → 结论"三段式列出全部偏差。

### 3.1 文档说完成,代码也完成(✅ 一致,已抽样验证)

| 文档声称 | 实测证据 |
|---|---|
| PR-B3/B4:5 个顶层类迁出 | `secureredact/ui/settings/dialog.py` + `ui/dialogs/{feedback,image_list,word_replace_rules}.py` + `workers/word_batch_replace_worker.py` 全部存在 |
| PR-B5:打包入口切 `secureredact.main:main` | 3 个 spec 全部指向 `secureredact/main.py`:`packaging/macos/config/SecureRedact.spec`:35、`packaging/windows/config/SecureRedact_windows.spec`:175、`..._v2.spec`:167;`start_app.sh` → `python -m secureredact.main` |
| PR-C4:7 个 API 函数 | `secureredact/api.py` 实测 `compute_doc_hash` / `scan_pdf` / `scan_word` / `redact_pdf` / `redact_word` / `filter_hits_by_overrides` / `batch_redact_word` —— 全部存在 |
| PR-C4:API 层 `from main import` = 0 | `secureredact/api.py` 中 `from main import` **0 处实际代码引用**(唯一命中是 docstring 里的文字 "实现走 wrapper 模式,`from main import` = 0") |
| PR-C6.1–C6.5:符号迁出 | `WORD_RULE_SCHEMA_VERSION` / `ZOOM_MIN`/`ZOOM_MAX` / `APP_NAME`/`VERSION` / `SimpleConfig`+config / `DEFAULT_RULES`+`DEFAULT_RULES_META` —— main.py 中均为 `from secureredact...` 导入 |
| PR-C7:CI workflow | `.github/workflows/ci.yml` 存在,含 compileall / smoke / API 100% coverage gate / 全量 / 视觉回归 5 个 step,矩阵 windows+ubuntu × py3.11+3.13 |
| PR-C8:CLI 薄壳 | `secureredact/cli.py` + `tests/unit/test_cli.py`(9 例)存在 |
| PR-C9:main.py 253 行 | 实测 `(Get-Content main.py).Count` = **253** ✓; `window.py` 87KB / `_js_constants.py` 24.7KB 存在 |
| PR-V2:6 类组件 `.qss` | `button.qss` / `card.qss` / `tab.qss` / `input.qss` / `dock.qss` / `toolbar.qss` / `workspace.qss` 全部存在,配套 `test_{button,card,tab,input,dock,workspace}_qss.py` |
| PR-C2.x:视觉基线 | `secureredact/ui/styles/baselines/{compare.py,_generate_baselines.py,_render.py}` + `tests/unit/test_visual_baseline.py`(10 例)+ CI step 存在 |

### 3.2 ❗ 文档说完成,但代码没有 / 不完全

#### 偏差 1(高):PR-B5 声称"移除 main.py shim",实际 shim 完整保留

- **文档原文**: `docs/refactor/b3-b4-b5-report.md` §1 表格 —— "PR-B5 | **移除 main.py shim** + 切换打包脚本入口 | ✓"
- **代码实测**: `main.py` **仍然存在,253 行**,顶部仍保留 20 行 PR-B0 deprecation 注释("PR-B5 收口时本文件将被彻底移除"),并保留 **40+ 条 re-export**(含 9 个 mixin、4 个对话框、`SimpleConfig`、`DEFAULT_RULES`、`MainWindow`、以及 `OCRWorker`/`WordWorker` 两个兼容 subclass)。
- **同一份报告 §4.6** 又写 "`main.py` < 5000 行 ✓ **3,772 行**(达成)"——**文档内部自相矛盾**:既说"移除 shim",又用"shim 还在但变小了"当验收依据。
- **判定**:PR-B5 的真实状态应为 **"入口切换完成、shim 移除未完成"**。

#### 偏差 2(高):计划里程碑 M3 要求 `from main import` 0 命中,实际残留 2 处

- **计划原文**: `docs/planning/gui-api-refactor-plan.md` §7.2 —— "M3(P3 完成) | `grep -rn "from main import" secureredact/ui/ secureredact/api.py` | **0 命中**"
- **代码实测**:
  - `secureredact/ui/main_window/handlers.py:381` → `from main import OCRWorker, WordWorker  # PR-B5.2: 延迟导入(plan §3.7 保留到 B5 收口)`
  - `secureredact/ui/main_window/setup_ui.py:40` → `from main import (  # type: ignore[attr-defined]` (多符号导入块)
- **判定**:计划 P3 / PR-C6.x **未完成**;计划 §3.7 本身写明"main.py shim 完全移除目标是 v1.1.17 / B5 收口",而 B5 未真正收口 → 形成了**闭环依赖**。

#### 偏差 3(高):PR-V1 / PR-V3 完整实现从未合并到主线

- **文档原文**: `docs/superpowers/plans/2026-08-30-visual-tokens-foundation.md` 全篇以 PR-V1 / PR-V3 为目标;`feature/visual-tokens-v1` 分支上有 `docs/refactor/v1-task-report.md`("PR-V1 完成报告(tokens 体系化 + Glass 检测)")。
- **代码实测**:
  - `git merge-base --is-ancestor d29b193 HEAD` → **exit=1**(未合并)
  - `git log --oneline HEAD..feature/visual-tokens-v1` → **10 个 commit 未进主线**,含 `ac3956f`(Theme 从 tokens 派生)、`aeefe6c`(28 个非颜色 token)、`d0fd25c`(primary_hover token)、`053da21`(`_platform.py`)、`9cbbce6`(`glass_supported`)、`2a53c9a`(V1 完成报告)
  - HEAD 上 `secureredact/ui/styles/tokens.py` 实测**只有 16 个颜色 token**,无圆角/间距/阴影/动效/字体 token
  - HEAD 上 `secureredact/ui/styles/_platform.py` **不存在**(只有 cherry-pick 进来的 `glass.py`)
  - HEAD 上根 `theme.py` 仍是**硬编码 hex 字典**(`"#F7F8FA"` 等),**双源未消除**
- **判定**:PR-V1/PR-V3 属"**代码已做但未进入交付分支**",且 HEAD 上只落了 §6 一小块。

#### 偏差 4(中高):PR-C9 功能层验收从未复跑

- **文档原文**: `docs/refactor/c9-task-report.md` §4.7 "⚠️ **必跑验收项(必须在 PyQt6 可用机器上复跑)**" —— 列了 5 项阻断合并的验收(单测 / path_validation / `pytest tests/ui` / `python main.py` / `python -m secureredact.main`),§6 签字写明"受限于本机 PyQt6 DLL 环境,完整 439 单元测试 + 8 视觉基线**必须在 PyQt6 可用机器复跑**"。
- **代码实测**: 后续 PR-C9 CI 修复共 5 个 commit(`21e0b35` / `18a8a21` / `c5051c7` / `891c5d5` / `4ae7300` / `f281154` / `f252853`),修的是 CI 自身的 collection ERROR 与 coverage path,**没有** PR-C9 功能验收复跑记录。
- **判定**:PR-C9 的**功能层验收签字缺失**,只有代码层(compileall + AST + wc -l)签字。

#### 偏差 5(中):计划 §2.2 要求的 `docs/current/API_REFERENCE.md` 不存在

- **计划原文**: §2.2 产出文件表 —— "`docs/current/API_REFERENCE.md` | **新增** | API 函数签名/示例(用户面向)"
- **实测**: `Test-Path docs/current/API_REFERENCE.md` → **False**
- **判定**:PR-C4 交付缺 1 项产出物。

#### 偏差 6(中):CLAUDE.md 声称的"仅 2 项已知失败"与实测不符

- **文档原文**: `CLAUDE.md` "已知既有失败(非回归,自 v1.1.11 起存在): `test_config_alignment.test_scan_default_level_matches` 与 `test_simple_config_reads_config_json_values`"
- **实测**(定向跑 `test_config_alignment` + `test_app_config` + `test_convergence` + `test_package_imports`):
  - ❌ `test_config_alignment::TestConfigAlignment::test_simple_config_reads_config_json_values`(文档已记)
  - ❌ `test_config_alignment::TestVersionSource::test_version_txt_is_single_source`
  - ❌ `test_app_config::TestAppConfig::test_config_manager_reads_same_config_json_as_simple_config` → `AssertionError: None != '*'`(replacement_text 在两套配置系统不一致)
  - ❌ `test_convergence::TestVersionFallbackAlignment::test_main_py_version_fallback_matches_current` → `AssertionError: '1.1.12' != '1.1.13'`
  - **共 4 项失败,而非文档声称的 2 项**。其中后 2 项与 `main.py:read_app_version()` 的 fallback 硬编码 `"1.1.12"` 落后 `version.txt` 的 `1.1.13` 直接相关。
- **注**:B0 报告 §4.3 当时列了 **8 项** baseline 失败(含上面两项 version fallback),说明 version fallback 类失败**长期存在但被 `CLAUDE.md` 收窄为"2 项"**。

#### 偏差 7(中):`.project_info` / `PROJECT_INDEX.md` / `PROJECT_STRUCTURE.md` / `STATUS.md` 严重过期

| 文档 | 声称 | 实测 |
|---|---|---|
| `.project_info` | 版本 **v23.3**,更新 2026-02-11,状态"生产就绪",导航到 `INDEX.md`/`QUICK_REFERENCE.md`/`PROJECT_STATUS.md`/`TEST_LOG.md` | **这 5 个文件全部不存在**;仍是 PrivacyGuard 时代内容,连"移除深色主题"都还写着(而 v1.1.14 已加回 DARK 切换) |
| `PROJECT_INDEX.md` | 基线 v1.1.11(2026-08-20);"下次继续开发先读 `docs/current/DEV_LOG.md`" | `DEV_LOG.md` **已被删除**;索引第 1 条是 `CLAUDE.md` 却未提 `docs/refactor/` 与 `docs/planning/` |
| `docs/current/PROJECT_STRUCTURE.md` | v1.1.11;目录树里 `secureredact/` 只有 ocr/redaction/pii/utils/workers,**无 ui/ 无 api.py 无 cli.py 无 core/**;"`main.py` 仍是活动运行时主入口" | 实际 `secureredact/` 有 **65 个 .py**,含 `ui/(main_window 17 + styles 8 + dialogs 3 + settings 2 + utils 1 + __init__ 1,合计 32)`、`api.py`、`cli.py`、`core/`;`main.py` 已非主入口 |
| `docs/current/STATUS.md` | 头部写 "日期 2026-08-17 / 基线 v1.1.11 / 标识 37.8.0" | **完全未记录阶段 B / C / V 任何一项重构**;全文 1488 行是 2026-03 ~ 2026-08 的 UI 微调流水账(cp20/cp22/cp26/cp27/cp28…cp31 系列) |
| `AGENTS.md` | v1.1.11,"main.py 仍是活动运行时入口且保持单体" | 与 `CLAUDE.md`(v1.1.13)及实际代码(253 行 shim)三方不一致 |

#### 偏差 8(中):`.planning/` v39 路线图 + GSD 三 Phase 完整文档集被误删

- **删除 commit**: `95f2ea7`(2026-08-31)"chore(cleanup): 移除 PrivacyGuard → SecureRedact rename 后的旧文件"
- **被删内容**: `.planning/PROJECT.md` / `STATE.md` / `REQUIREMENTS.md` / `ROADMAP.md`(v39.0.0 7 Phase)+ `.planning/research/` 缓存 + `docs/current/DEV_LOG.md`
- **同时被删**: `docs/current/DEV_LOG.md`(`git log --all -- docs/current/DEV_LOG.md` 显示其最后存在于 `6c87771`)
- **幸存的残余**: 完整的 3-Phase 计划文档集(01-pdf / 02-pdf / 03-word,约 60 个 PLAN/SUMMARY/VERIFICATION md)仍留在**已废弃分支** `gsd/phase-2-local-attempt`(tip `bbb5f75`, 2026-08-12)
- **判定**:清理脚本按"PrivacyGuard 旧文件"归类,把 **v39 正在进行的计划** 一并清掉,导致 v39 路线图在主线上**彻底不可见**。

#### 偏差 9(低):PR-V1 计划文件名与实现不符

- **计划**: `visual-tokens-foundation.md` File Structure 要求新建 `secureredact/ui/styles/_platform.py`
- **实现**: HEAD 上是 `secureredact/ui/styles/glass.py`(无 `_platform.py`);且 `_platform.py` 只存在于未合并分支
- **判定**:命名/落地路径偏离计划,无功能影响,但增加检索成本。

#### 偏差 10(低):阶段 B 各报告的"完成日期"早于实际提交日期

| 报告 | 声称完成日期 | 实际 commit 日期 |
|---|---|---|
| `b0-report.md` | 2026-08-25 | 2026-08-27(`e4426a7`) |
| `b1-report.md` | 2026-08-26 | 2026-08-27(`e4426a7`) |
| `b2-report.md` | 2026-08-26 | 2026-08-27(`e4426a7`) |
| `b2-1..b2-8-report.md` | 2026-08-27 | 2026-08-27 / 08-28(`e4426a7` / `99ab8ef`) |
| `b3-b4-b5-report.md` | 2026-08-27 | 2026-08-28(`89a842b`) |
| `c1-report.md` | 2026-08-27 | 2026-08-28(`911014f`) |

- **根因**: `b2-integrated-report.md` §1 明确写"**综合 PR(将原计划 B0/B1/B2.0/B2.1 合并为一次落地)**"——即 10+ 份分阶段报告描述的是**同一次合并提交**里的工作,报告的日期是"计划日期"而非"落地日期"。
- **判定**:非代码缺陷,但**日期维度不可直接用于排期推断**。

### 3.3 ✅ 代码已做但文档没记(共 12 个 PR + 2 条重大遗漏)

| 项 | commit | 缺口 |
|---|---|---|
| PR-C3(`word_rules.py` 迁出) | `299fcaa`(08-28) | `docs/refactor/` **无 c3 报告** |
| PR-C4(`api.py` 骨架) | `b3fc551`(08-30) | 无 c4 报告;§2.2 要求的 `API_REFERENCE.md` 也缺 |
| PR-C5 + C5.1–C5.4 | `32bab50` `ae7b3ff` `ab79a49` `a873968` `9d562b0` | 无 c5 报告 |
| PR-C6.1–C6.5 | `eb317a6` `237527b` `132f910` `db8cc18` `b0a7fcb` | 无 c6 报告 |
| PR-C7 | `6703a3a` `c0005ba` `40ed73b` | 无 c7 报告 |
| PR-C8 | `bfc916a` | 无 c8 报告 |
| PR-B5.1 / PR-B5.2 | `a9f1701` `b27725e` | 只在 `b3-b4-b5-report.md` 里被顺带提及,**无独立验收签字** |
| PR-C9 CI 修复 ×7 | `21e0b35`…`891c5d5` `f281154` `f252853` `4ae7300` | 只在 `c9-task-report.md` §"2.3 提交记录"里列 SHA,**无独立修复报告/验收** |
| **PR-C9 Task 6 后的完整行数账** | — | `c9-task-report.md` §4.4 的行数账在 HEAD 上已**过期**(仍按 2026-08-30 的 2,031 行记;而 `window.py` 现为 87KB/约 2,700 行) |
| **v39.0.0 七 Phase 计划** | `127622f` `8acf925` `2026097` `bfb88ea` | 被 `95f2ea7` 误删,主线上**无任何记载** |
| **GSD 3-Phase 计划文档集(~60 md)** | 分支 `gsd/phase-1-pdf` / `gsd/phase-2-local-attempt` | 同上,主线上无记载 |

### 3.4 版本号一致性核查

| 位置 | 版本 |
|---|---|
| `version.txt`(唯一版本源) | **1.1.13** |
| `CLAUDE.md` 头部 | v1.1.13("Last Updated 2026-08-24") ✓ |
| `CHANGELOG.md` 最新条目 | **[1.1.14] - 2026-08-25**(但排在 1.1.13 **之后**、1.1.12 之前,顺序错乱) |
| `main.py:read_app_version()` fallback | **"1.1.12"** ← 落后 2 个版本(实测触发测试失败) |
| `secureredact/__init__.py` fallback | 需与 version.txt 对齐(`test_convergence` 有对应用例) |
| `AGENTS.md` / `PROJECT_INDEX.md` / `PROJECT_STRUCTURE.md` / `STATUS.md` | v1.1.11 |
| `.project_info` | v23.3 |
| `docs/refactor/c2x-task-report.md` 基线 | v1.1.13;而 `c9-task-report.md` 基线写 **v1.1.14** —— 与 `version.txt` 的 1.1.13 矛盾 |

> **结论**:CHANGELOG 已写到 1.1.14,但 `version.txt` 仍停在 1.1.13,导致 **CHANGELOG / version.txt / main.py fallback / AGENTS.md / PROJECT_INDEX.md / STATUS.md / .project_info 共 7 处版本口径不一**。这是"文档漂移"最集中的体现。

---

## 4. 已交付能力清单

### 4.1 产品能力(源自 `CHANGELOG.md` + `STATUS.md` + 代码实测)

| 能力域 | 已交付项 |
|---|---|
| **PDF 脱敏** | 文本层检索(PyMuPDF)· 扫描件 OCR(RapidOCR 单引擎)· 混合型 PDF(文本层 + 内嵌图片块 OCR 双向通道)· 手动矩形框选 · 图片通道白名单裁剪 · 印章检测(CV) |
| **Word 脱敏** | 智能扫描 · 手动精确/全局脱敏 · 多字段替换规则(`exact`/`regex`)· `.docx`/`.doc` 批量替换 · **部分遮蔽**(保留前 N + 后 N)· 统一社会信用代码(**Word-Only 隔离**)· 姓名上下文注入(方案 B,三层防护)· 并列名单上下文 + `extra_tokens` 接通 |
| **名单能力** | jieba 启发式人名识别 + 强前缀/后缀/标签上下文 · 白名单邻接过滤 · 大写金额字表免疫 · 法律文书术语黑名单 |
| **黑白名单** | `BlackWhiteListStore` 单例(session + permanent 双层)· 设置中心黑/白名单 Tab · **白名单片段级豁免**(v38 `whitelist_trim_only`)· 白名单仅豁免自身片段,同区间其他敏感内容仍脱敏 |
| **人工干预** | `HitRef`/`Override`/`HitOverrideStore` 三层核心 · 右键「忽略 / 确认 / 撤销 / 提升为永久」· 会话级 + 永久级 override · `filtered_hits()` 唯一消费入口 |
| **Word 双栏预览** | 左原文 + 高亮 / 右合并替换(`rule > manual > ocr`)· DOM keyed patch 增量更新 · 同步滚动 |
| **UI 能力** | 拖放打开 · 深色/浅色/跟随系统三主题(`MainWindowThemeMixin`)· 11 个 `.qss` 作用域 + 5 状态组件样式 · 密度自适应 · 工具栏/工作台/批量工作区 |
| **工程化** | 561 个单元用例 · pytest markers(api/integration/smoke/slow)· GitHub Actions CI(4 路矩阵 + API 100% coverage gate + 视觉回归)· 视觉基线 harness(0.005 像素阈值)· 视觉基线 CI gate · CLI 薄壳(`python -m secureredact.cli`) |
| **架构** | `main.py` 13,026 → **253 行(−98.1%)**;65 个模块分层(`ocr/` `redaction/` `pii/` `workers/` `utils/` `ui/` `core/`);9 个 MainWindow mixin + 10 层 MRO;7 函数业务 API 层 |
| **打包** | Windows(macOS)打包脚本 + 3 个 spec 全部指向 `secureredact/main.py` |

### 4.2 阶段 B/C/V 交付的架构成果(单列)

```text
main.py                     13,026 行  →  253 行   (−98.1%)
secureredact/ui/main_window/  17 模块(9 mixin + canvas/webview_bridge/identifiers/
                                window/_js_constants/_helpers/_batch_helpers/theme)
secureredact/ui/styles/      11 .qss + tokens.py + loader.py + glass.py + baselines/
secureredact/ui/settings/    dialog.py(2,259 行)+ _helpers.py
secureredact/ui/dialogs/     feedback / image_list / word_replace_rules
secureredact/api.py          7 个业务 API 函数
secureredact/cli.py          CLI 薄壳
secureredact/redaction/      rules_loader.py + word_rules.py 新增
tests/unit/                  53 个文件 / 561 用例
.github/workflows/ci.yml    5 step × 4 路矩阵
```

---

## 5. 未完成与遗留风险 / 技术债清单

> 每条均标注**原文出处**,便于复核。

### 5.1 明确未开始的阶段(4 项)

| # | 项 | 出处原文 |
|---|---|---|
| U-1 | **PR-C1.1 — SettingsDialog 主题切换 UI**:新「外观」分节 + theme combo 联动 `MainWindow.set_theme` + `app.theme` 持久化 + `tests/unit/test_settings_dialog_theme_ui.py` | `docs/superpowers/plans/2026-08-30-visual-component-baseline.md` §"Sub-PR 4"(Task 4.1–4.4);`docs/refactor/v2-task-report.md` §7;`docs/refactor/c2x-task-report.md` §7 |
| U-2 | **PR-V4 — 内嵌 QSS 迁移**:41 处 `setStyleSheet` → `loader.apply`;新建 `scroll.qss` / `settings_dialog.qss` / `settings_density.qss` / `density_idle.qss` / `batch_replace.qss` 等 | `visual-component-baseline.md` §"Sub-PR 3"(Task 3.1–3.12);`v2-task-report.md` §7 |
| U-3 | **v39.0.0 七 Phase(Word 脱敏重做)**:基线契约冻结 / Story 遍历 + 可逆坐标映射 / Strangler 抽取 / 数字 Unicode 规则 / 姓名地名地址调优 / 嵌入图 OCR / 批量性能回归 | `.planning/ROADMAP.md`(git `bfb88ea`, **已被 `95f2ea7` 删除**) |
| U-4 | **PR-W — Word 替换规则编辑器重做(独立轨道)** | `visual-component-baseline.md` §范围外第 3 条 |

### 5.2 计划中已定义但未收口的里程碑 / 验收项

| # | 项 | 出处原文 |
|---|---|---|
| T-1 | **M3 未达成**:"`grep -rn "from main import" secureredact/ui/ secureredact/api.py` → **0 命中**" | `gui-api-refactor-plan.md` §7.2 里程碑检查表 |
| T-2 | **PR-B5 收口未达成**:"PR-B5 收口时 `main.py` 将被彻底移除,所有打包入口同步切换到 `secureredact.main:main`" | `CLAUDE.md` 入口迁移提示;main.py 第 7 行注释 |
| T-3 | **R-01 高概率未清账**:"API 内部仍需 `from main import _xxx`,跨包依赖残留 | 概率 **高** | P3 阶段每个 API 函数内部的 main 依赖都要清账" | `gui-api-refactor-plan.md` §8 风险登记 |
| T-4 | **R-06 / R-08 未消**:"用户旧脚本 `from main import X` 失效 | 缓解:`main.py` shim **暂保留到 B5 收口**" | `gui-api-refactor-plan.md` §8 R-06 / R-08 |
| T-5 | **P1 验收项缺 1**:"`docs/current/API_REFERENCE.md` | 新增 | API 函数签名/示例(用户面向)" | `gui-api-refactor-plan.md` §2.2 |
| T-6 | **P3 阶段前置动作未完全按序**:"新增 `tests/unit/test_main_shim_compat.py`,持续验证 `main.py` 中待迁移符号还可用…**每个符号迁移后,移除 shim compat 测试中对应条目**" —— 实测该文件存在(10 例),但迁移已做完、清单未缩减 | `gui-api-refactor-plan.md` §4.3 任务 0 |
| T-7 | **`.planning/` 恢复** | `95f2ea7` 删除动作本身 |

### 5.3 报告里自认的技术债 / 已知限制(原文摘录)

| # | 原文出处与内容 |
|---|---|
| D-1 | `b3-b4-b5-report.md` §4.6: "`main.py` < 5000 行 ✓ **3,772 行**(达成)" —— 但 §1 表格又写"移除 main.py shim"。**验收口径自相矛盾**。 |
| D-2 | `b2-8-report.md` §6.1/6.2:"剩余 6,653 行内容:…**实际可压缩到 ~6,300-6,500 行区间(非 5000)**,与规划的激进目标有差距";并列出候选 PR-B2.9(`__init__` 工厂化 + 文件 IO 迁出,`-~250`)与 PR-B2.10(`_wrap_html_document` 迁出,`-~29`)—— **两者均未执行**。 |
| D-3 | `b2-6-report.md` §6.1:"未迁出到 mixin 的剩余内容:文件 IO(`open_pdf`/`_open_pdf_file`/`_open_word_docx`/`_open_word_doc`/`_save_word`/`_convert_doc_to_docx` ≈ 329 行)、数据查询 `_has_*` 系列 ~50 行…" |
| D-4 | `b2-3-report.md` §6.1:"**18 个 Word 相关方法未迁出**(`_save_word`、`_open_word_docx`、`_count_enabled_word_rules` 等)…" |
| D-5 | `b2-4-report.md` §6.1:"PDF 文件 IO(`open_pdf` 等)未迁出…**13 个方法跨类拆分不够彻底**,PDF 渲染相关仍有 ~30 个方法留 MainWindow → 后续 PR-B2.4.1 / B2.6 渐进" |
| D-6 | `b1-report.md` §5.1:"`_apply_light_theme` 内 5 个局部 widget setStyleSheet(Word 双栏 / word_header_divider / toolbar_meta_style 共享)**未迁**";"`theme.py` 字典**未删除** — backward compat 保留" |
| D-7 | `b0-report.md` §5.1:"❌ 未提交基线 PNG(框架就绪,实际 6 帧测试类留到 PR-B2/B3)";b2 系列直到 b2-8 仍为"**1 张已落实(02),5 张占位**" |
| D-8 | `c2x-task-report.md` §6.1:"SettingsDialog 当前 light/dark 渲染**相同 hash** | 基线没有真实捕获主题差异 | PR-C1.1 / PR-V4 改完 `_apply_dialog_theme` 后重跑 `_generate_baselines.py`" |
| D-9 | `c2x-task-report.md` §6.1:"`_current_*.png` 留 4 张未被清 | 占盘 | 已加 .gitignore" |
| D-10 | `c9-task-report.md` §5 范围外:"1. 视觉层重做…→ 待 brainstorming 风格方向后另起 plan;2. MainWindow 内方法的进一步拆分(如把 `_apply_light_theme` 迁入 `theme.py`);3. `main.py` 剩余 OCRWorker/WordWorker 兼容 subclass 的进一步处理;4. `main.py` 剩余模块级符号的最终清理" |
| D-11 | `v2-task-report.md` §6.1:"`workspace.qss` 残留 **17 处 hex 字面量** | 未来 token 翻新时需逐个替换 | 由 PR-V4 task 3.2 / 3.5 替换为 loader.apply 时一并迁" |
| D-12 | `v2-task-report.md` §6.1:"`_build_mapping` 主题 token 与 glass key 同名冲突 | `{card_background}` 被 token 默认值压住 glass 替换 | 当前 token dict 无 card/dock_background 字段;**若未来冲突需加优先级策略**" |
| D-13 | `v2-task-report.md` §6.1:"`StylesheetLoader.SCOPES` 主 scope 累加到 **11 个 .qss** | 启动 stylesheet 字符串变大(数十 KB) | 实测启动耗时 < 5ms" |
| D-14 | `c1-report.md` §6.1:"`_resolve_system_theme` 在 **Qt < 6.5 无 `colorScheme` API** | 'system' 模式 fallback | try/except AttributeError + palette 亮度检测" |
| D-15 | `c1-report.md` §6.1:"SettingsDialog 未暴露主题 UI | **用户无入口切换** | 留 PR-C1.1 后续处理" |
| D-16 | `gui-api-refactor-plan.md` §2.3 任务 1.2:"每个 API 函数临时 import 数 ≤ 2 … 每个临时 import **必须在 P3 阶段被清账**" |
| D-17 | `gui-api-refactor-plan.md` §2.3:"**`batch_redact_word` 只在 Qt 主线程内可用**;若调用方不是 Qt 主线程,需要先在主线程跑…**后续在 plan 修订中补 `is_main_thread()` 断言 + 友好错误信息**" |
| D-18 | `gui-api-refactor-plan.md` §2.3:"**`timeout_sec` 仅在文件粒度生效**;单文件处理可能耗时数十秒" |
| D-19 | `gui-api-refactor-plan.md` §2.3 REVIEWS-v2 C-2:"批处理中某文件出错时,双方都阻塞导致**死锁**。wrapper 必须在 worker.start() 前 monkey-patch `provide_error_decision`…5 秒后自动放行 'skip' 决策" |
| D-20 | `gui-api-refactor-plan.md` §0.2 范围表:"`main.py` shim 整体移除(属于 B5 收口,**不在本次**)" |
| D-21 | `CHANGELOG.md` v1.1.11 §已知限制:"**PDF 图片通道 OCR hits**(`source="ocr"` 且 `hit.text=""`)不走 trim,回退到整条剥掉。图片通道 trim 的完整实现**留待后续版本**" |
| D-22 | `CHANGELOG.md` v1.1.13 §已知覆盖率下降:"裸 nr 场景(`本院认为张三的诉求成立` / `著作权人周强在…`)在 `require_context=True` 下**不再识别** — 设计预期,用户已确认接受" |
| D-23 | `CHANGELOG.md` v1.1.12:"jieba 来源命中仍走 `replacement_text`(避免 jieba 误识别导致 mask 错乱),**留作 v1.1.13 扩展**" |
| D-24 | `CHANGELOG.md` v1.1.12:"USCC 隔离机制确保 PDF 路径既有行为零变化(已通过 **286 项回归 + 7 项既有失败**不扩大验证)" —— 与 CLAUDE.md 的"162 项 / 2 失败"口径不同 |
| D-25 | `gui-api-refactor-plan.md` §3.5:"P2 完成不等于 P3 完成。P2 完成后 `main.py` 仍保留 `OCRWorker` / `WordWorker` 等兼容层" |

### 5.4 工程/流程层面风险(本次分析新增,非文档原文)

| # | 风险 | 证据 |
|---|---|---|
| R-1 | **`main` 分支落后 66 个 commit**,阶段 B/C/V 全部成果不在默认分支上 | `git log --oneline main..HEAD` = 66 |
| R-2 | **10 周零提交**,项目处于事实停滞期;无人推进 PR-V4 / PR-C1.1 / v39 | 2026-09-01 → 2026-11-12 |
| R-3 | **`origin/rename/secureredact` 落后本地 8 个 commit**(PR-V2 未推送) | `2730a54` vs `3a62724` |
| R-4 | **PR-V1/V3 的 10 个 commit 成为"孤儿"**,若分支被删则 tokens 体系化成果永久丢失 | `git branch --contains` 仅 `feature/visual-tokens-v1` |
| R-5 | **单点文档入口断裂**:`PROJECT_INDEX.md` 让新人先读 `DEV_LOG.md`(已删);`main.py` 顶部注释让新人去找 `frontend-refactor-plan.md`(从未入库) | 见 §0 |
| R-6 | **`version.txt` / CHANGELOG / main.py fallback 三方不一致**,且已实际导致 2 个测试失败 | 见 §3.2-偏差 6 |
| R-7 | **本地存在未跟踪文件**:根 `SecureRedact_verify.spec`(B0 报告点名要改的文件)未入 git,无法审计 | `git ls-files | Select-String spec` 只有 packaging 下 3 个 |
| R-8 | **全量 `tests/unit` 本机跑不完**(>12 分钟未结束,OCR/Qt 环境受限),文档中的"439 项(B 系列基线)/561 项(当前实收)全绿"结论本机无法复现 | 本次后台任务被手动终止 |

---

## 6. 小结

1. **重构本体进展显著且质量可用**。阶段 B 把 `main.py` 从 13,026 行砍到 253 行(−98.1%),MainWindow 拆成 9 个 mixin + 10 层 MRO,QSS 集中化到 11 个 `.qss`,并建立了 API 层、CLI、CI、视觉基线四套基础设施。**38 个 PR 级阶段判定为已完成**。

2. **"阶段 B 前端重构"已实质完成,但**收口**没完成**。PR-B5 的"移除 main.py shim"未兑现(253 行 shim + 40+ re-export 原样保留),计划里程碑 M3 的"`from main import` 0 命中"未兑现(残留 `handlers.py:381` 与 `setup_ui.py:40` 两处)。这形成了一个 **B5 ↔ P3 互为前置的闭环**,是当前最应优先打破的依赖。

3. **开发节奏是"两次冲刺 + 一次长期停滞"**。2026-08-16~08-19(64 commits)、2026-08-27~09-01(60 commits)是两个爆发窗口,其间有 9 周(06~08 中)、31 周(09-01 后至今)两段完全空白。**最后一次实质提交是 2026-09-01 的 `3a62724`(PR-V2 完成报告)**,距今 72 天。

4. **文档漂移是当前最大的系统性问题**,且可量化:
   - 7 处版本口径不一(version.txt 1.1.13 / CHANGELOG 1.1.14 / main.py fallback 1.1.12 / CLAUDE.md 1.1.13 / AGENTS.md 1.1.11 / PROJECT_INDEX·STRUCTURE·STATUS 1.1.11 / .project_info v23.3)
   - `.project_info`(v23.3, 2026-02)整份过期,导航指向 5 个不存在的文件
   - `STATUS.md`(72KB / 1488 行)**完全未记录阶段 B/C/V**,全是 2026-03~08 的 UI 微调流水账
   - `PROJECT_STRUCTURE.md` 的目录树与实际 `secureredact/` 差了一个 `ui/` 子树 + 3 个顶层模块
   - **12 个 PR(C3/C4/C5.x/C6.x/C7/C8 等)代码已落地但 `docs/refactor/` 无完成报告**
   - **v39.0.0 七 Phase 路线图 + GSD 三 Phase 完整计划文档集被 `95f2ea7` 误删**,仅残存于废弃分支
   - **PR-V1/V3 的 10 个 commit 未合并**,tokens 体系化成果悬空

5. **下一步建议(按优先级)**:
   1. 把 `main` 快进到 `3a62724`,并合并/抢救 `feature/visual-tokens-v1` 的 10 个 commit(否则 tokens 体系化成果有丢失风险)。
   2. 打破 B5 ↔ P3 闭环:一次性完成 `main.py` shim 彻底删除 + `handlers.py` / `setup_ui.py` 两处 `from main import` 清账 + 同步缩减 `test_main_shim_compat.py` 清单。
   3. 同步版本口径:统一 `version.txt` / CHANGELOG / `main.py` fallback,并修掉实测的 4 个失败(其中 2 个是 version fallback 与 config 漂移)。
   4. 恢复 `.planning/` 与 `docs/current/DEV_LOG.md`,或至少把 v39 路线图迁到 `docs/planning/`。
   5. 更新 `STATUS.md` / `PROJECT_STRUCTURE.md` / `PROJECT_INDEX.md` / `.project_info` / `AGENTS.md` 到 v1.1.13+ 实际结构,并补写 C3–C8 共 12 个 PR 的完成报告。
   6. 推进 PR-V4 + PR-C1.1(视觉层收口,Plan 2b 的最后两个 sub-PR),并重跑 `_generate_baselines.py` 使 SettingsDialog 的 light/dark 基线真正区分开(消除 D-8)。

---

*本报告全部结论均基于对 `dsh-3eb2fb3e-5817` worktree 的实际代码检视与 `git log` 验证;凡标注"实测"处均为本机命令输出,凡标注"原文出处"处均可回溯到具体文件与行号。*