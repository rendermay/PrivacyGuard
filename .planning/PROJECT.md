# PrivacyGuard 脱敏卫士

## What This Is

PrivacyGuard 是一款 Python + PyQt6 桌面应用，面向中文法律/政务/商务场景，对本地 Word 与 PDF 文档进行隐私信息（身份证、手机号、银行卡、姓名、地址等）的一键识别、可预览与可审计脱敏。所有计算在本地完成，不上传原文。

## Core Value

用户能在不联网的前提下，对一份 Word 或 PDF 文档**准确、可预览、可追溯**地完成敏感信息脱敏——任何一条命中都能定位回原文位置、说明来源（规则 / OCR / 人工），并且能在脱敏前后对比。

## Business Context

- **Customer**: 需要处理含敏感信息的本地文档的个体/律所/政务窗口用户
- **Revenue model**: 桌面应用销售 + Windows / macOS 安装包分发
- **Success metric**: 单文档端到端脱敏命中率 ≥ 95%、FP 误报可控、用户在 1 分钟内完成一次脱敏并能定位每条修改来源
- **Strategy notes**: 优先把 Word 这条线的识别质量/架构做扎实；LLM / 云端 NER 仅作 v2+ 备选，本地优先

## Requirements

### Validated

<!-- Shipped and confirmed valuable. 这些是已上线能力，禁止悄悄改语义 -->

- ✓ **PDF 文本通道脱敏** (v37 前) — PyMuPDF 搜索 + redact annotations
- ✓ **PDF 图片通道 OCR 脱敏** (v37.5+) — RapidOCR + 框选回写
- ✓ **PDF 混合通道脱敏** (v37.6 cp23) — 文本层 + 嵌入 image-block OCR 同时处理
- ✓ **Word 智能扫描** (v37 前) — regex 规则集（身份证 / 手机号 / 银行卡 / 日期 / 邮箱 / 印章 / 地址 / 固定电话 / 法定代表人）
- ✓ **Word 人工框选** (v37 前) — 精准 + 全局两种模式
- ✓ **Word 多字段替换规则** (v37.7+) — `exact` / `regex` 双模式 + 字段级独立规则
- ✓ **Word `.docx` / `.doc` 批量替换** (v37.7+) — 多文档批量处理 + 规则应用
- ✓ **Word 双预览** (v37.7+) — 左原文 + 右合并替换（`rule > manual > ocr`）
- ✓ **黑/白名单** (v37.9) — `BlackWhiteListStore` 单例 + 永久层 / 会话层
- ✓ **白名单片段级豁免** (v38 / v38.0.1) — `whitelist_trim_only` 开关
- ✓ **人工干预机制** (v37.8.0) — `HitOverrideStore` 单例 + `Ignore / Confirm / Revoke / Promote` 四种动作 + 干预 dock
- ✓ **Word 命中携带 source 字段** (v37.8.0) — 干预消费端可按 source 过滤
- ✓ **收敛回归 160/162** (v38.0.1) — 主回归不退化，已知 2 项失败自 v37.7.6 起存在

### Active

<!-- v39.0.0 当前 scope。任务见 REQUIREMENTS.md -->

#### 架构（ARCH）

- [ ] **ARCH-01**: 把 WordWorker / 规则 / 命中 / 预览从 main.py 抽出到 `privacyguard/word/*`，main.py 仅留胶水
- [ ] **ARCH-02**: 规则 / 命中 / 预览三层走明确接口契约，调一处不破另一处
- [ ] **ARCH-03**: 与 PDF 端共用部分（OCRWorker / HitOverrideStore / whitelist_split）划清复用边界并产出接口边界文档
- [ ] **ARCH-04**: 统一 `source / start / end / rect / text` 字段命名，产出字段映射表

#### 误识（FP）

- [ ] **FP-01**: 数字型规则拒识订单号 / 工单号 / 隔符号（空格 / 全角 / 破折号）号码
- [ ] **FP-02**: 姓名 / 地名 / 地址 词权重调优，行政区划 + 职务词不入姓名
- [ ] **FP-03**: 日期 / 邮箱 / 金额：年度 / 型号数字不进身份证；纯中文词不进邮箱
- [ ] **FP-04**: 词法 / 上下文：避免跨边界吞文本，中英 / 中数混合边界

#### 漏识（FN）

- [ ] **FN-01**: 表格 / 页眉 / 页脚 / 批注 / 脚注 / 尾注 全部纳入扫描
- [ ] **FN-02**: 嵌入图 / 扫描件 Word 走 OCR 通道
- [ ] **FN-03**: 跨格式 / 隔符号（空格 / 换行 / 全角 / 破折号）鲁棒匹配
- [ ] **FN-04**: 多字段组合上下文（人名 + 电话 + 地址联动）

#### 测试与回归

- [ ] **TEST-01**: 现有 162 项全量回归不退化（已知 2 项保持）
- [ ] **TEST-02**: 以「抵账协议0522.docx----刘骁毅原版.docx」等真实样本为基准的 fixture 集
- [ ] **TEST-03**: Word 结构全覆盖扫描端到端验证（表 / 页眉页脚 / 批注 / 脚注 / 尾注每类 ≥1 fixture）

### Out of Scope

<!-- 显式排除。带原因防止下次又被加回来 -->

- **LLM / 云端 NER 接入** — 本地优先架构不变；仅在架构层预留接口位（ARCH-02 / ARCH-03）供 v2+ 接入
- **UI 视觉重做 / 新交互** — 当前 UI 已稳定；v39 不动 UI 视觉（结构性 UI 调整允许）
- **打包 / Windows / macOS 构建链路改动** — v37-v38 打包链路已稳定，不在本里程碑范围
- **PDF 端** — v37.9 黑/白名单 + v38 trim 已收敛完成；本里程碑不动 PDF 通道（修复 v39 引入的回归除外）
- **DOC 格式 → DOCX 转换逻辑** — 已收敛到 `privacyguard/utils/doc_converter.py`，不在 v39 范围

## Context

- **当前版本**: v38.0.1（2026-08-19，`whitelist_trim_only` hotfix 后）
- **架构现状**:
  - `main.py` 仍是 active runtime entry，~583 KB / 12k+ 行
  - `privacyguard/` 已抽出 `ocr / workers / utils / redaction / core / pii / ui` 七个包
  - 但 Word 相关逻辑仍大量内联在 `main.py`，规则 / 命中 / 预览耦合度高
- **真实样本**:
  - 主样本：`pdf/抵账协议0522.docx----刘骁毅原版.docx`（32 KB，含姓名+法律条款）
  - 参照：`pdf/丰满法院民事判决书捷信小额贷(1).pdf`、`pdf/付明义判决书2026-07-29 14.29.pdf`、`pdf/周强起诉状.pdf`
- **测试基线**: 162 项 / 160 PASS（已知 2 项失败：`test_scan_default_level_matches` + `test_simple_config_reads_config_json_values`，自 v37.7.6 起存在）
- **历史交付**:
  - v37.7.x 收敛（去重 / 配置对齐 / f-string 安全）
  - v37.8.0 人工干预（HitOverride）
  - v37.9.0 黑/白名单
  - v38.0.0 + v38.0.1 白名单片段级豁免
- **CLAUDE.md 索引**: 详见项目根 `CLAUDE.md`（含 Read First、Current Technical Reality、Common Commands、Packaging、Current Checkpoints）

## Constraints

- **Tech stack**: Python 3.x + PyQt6；`python-docx` 处理 Word；`mammoth` DOCX→HTML 预览；`RapidOCR` 图像通道
- **Local-first**: 不引入任何强制联网依赖；OCR / 规则 / 字典全部本地
- **Compatibility**: 与 v37.x / v38.x 现有 `HitOverrideStore` / `whitelist_trim_only` / `BlackWhiteListStore` 行为兼容，外部观察者（用户、测试、UI）看不出语义差异
- **Versioning**: 单一版本源 `version.txt`；`main.py` 与 `privacyguard.__version__` 同源；release 必须同步 Windows / macOS 资源版本
- **Regression**: 162 项测试基线不退化（含已知 2 项失败）
- **Hotfix policy**: 涉及对外语义变化（如 trim 行为变化、override scope 变化）走 v38.0.x hotfix；架构级重构走 v39.0.0 主版本

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| v37-v38 走「增量 feature + hotfix」节奏 | 已有 38 项人工干预测试 + 大量回归基线，避免大重构炸面 | ✓ Good |
| `whitelist_trim_only` 默认 True、显式开关关闭 | 默认安全，向后兼容旧行为 | ✓ Good（v38.0.0 / v38.0.1 验证通过） |
| `HitOverrideStore` 单例 + `filtered_hits()` 唯一消费入口 | 强制所有命中消费走统一过滤，防止旁路 | ✓ Good（v37.8.0 落地） |
| LLM / 云端 NER 暂不接入 | 用户场景需要 local-first + 隐私保证 | — Pending（架构层预留接口位） |
| v39 走主版本号大重构 | 8 维度 + 真实样本驱动，FP/FN 双指标需要架构级重做 | — Pending（本次里程碑） |
| 保留 `main.py` 单体 runtime entry | 重构期不影响打包 / 启动 / 调试路径 | — Pending（v39 验证） |

---

*Last updated: 2026-08-19 after starting milestone v39.0.0*

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

## Current Milestone: v39.0.0 — Word 脱敏重做

**Goal**: 系统性重做 Word 文档脱敏的架构 + 识别 + 扫描覆盖三类问题，根治误识 / 漏识 / 散落。

**Target features:**
- 架构层：main.py Word 散落抽取、规则/命中/预览解耦、PDF/Word 复用边界文档化、字段命名统一
- 误识修复：数字型拒识订单号/工单号、姓名/地名/地址词权重、行政区划 + 职务词入黑名单、词法上下文
- 漏识修复：表格/页眉页脚/批注/脚注/尾注扫描、嵌入图 OCR、隔符号鲁棒、多字段组合
- 验收：现有 160/162 全量回归不退化 + Word 独立可调用接口 + Word 结构全覆盖 fixture

**Acceptance criteria (v39.0.0 必达)**:
1. 现有 162 项全量回归不退化（已知 2 项失败保持）
2. Word 脱敏有独立可调用接口（`privacyguard/word/*` 边界清晰，main.py 仅留胶水）
3. Word 结构全覆盖（表格 / 页眉页脚 / 批注 / 脚注 / 尾注 每类 ≥1 fixture 端到端验证）