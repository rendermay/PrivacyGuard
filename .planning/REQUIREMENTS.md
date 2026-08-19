# Requirements: PrivacyGuard v39.0.0 — Word 脱敏重做

**Defined:** 2026-08-19
**Core Value:** 用户能在不联网的前提下，对一份 Word 或 PDF 文档**准确、可预览、可追溯**地完成敏感信息脱敏。

## v1 Requirements

v39.0.0 必达范围。共 5 类 / 17 项 + 1 项硬约束。每项映射到 ROADMAP 的某个 phase。

### 架构（ARCH）

- [ ] **ARCH-01**: 把 WordWorker / 规则 / 命中 / 预览从 `main.py` 抽出到 `privacyguard/word/*` 子包（contracts / doc_scanner / rule_engine / hit_collector / preview_bridge / batch_replacer / save_writer / web_bridge 共 8 个模块），`main.py` 仅留胶水 + 兼容层
- [ ] **ARCH-02**: 规则 / 命中 / 预览三层走明确接口契约；预览与保存共用 `merge_priority` 与 `merged_hits_by_key` 单一数据结构；调一处不破另一处
- [ ] **ARCH-03**: 与 PDF 端共用部分（HitRef / HitOverrideStore / BlackWhiteListStore / whitelist_split / doc_hash / name_recognizer）划清复用边界并产出 `docs/word/REUSE_BOUNDARY.md`（**只读不动**——见 CONST-01）
- [ ] **ARCH-04**: 统一 `source / start / end / rect / text / replacement / mode / rule_name / pattern / doc_hash / location` 字段命名，产出 `docs/word/FIELD_MAPPING.md` 双签表（OCR / Word / Preview 三视角）

### 误识修复（FP）

- [ ] **FP-01**: 数字型规则拒识订单号 / 工单号 / 110/119/120/800 等业务号；隔符号（空格 / 全角 / 破折号 / 换行）号码仍可匹配但 start/end 用原文 offset；mobile 锚定 `(?<![0-9])1[3-9]\d{9}(?![0-9])`
- [ ] **FP-02**: 姓名 / 地名 / 地址词权重调优；jieba 只生成候选不再作结论；行政区划黑名单（GB/T 2260 子集）+ 职务词黑名单（如"经理 / 主任 / 法官 / 律师 / 法定代表人"）拒识；姓名识别走多层打分
- [ ] **FP-03**: 年度 / 型号 / 工单号数字不进身份证；纯中文 / 中英混合不进邮箱；金额（¥/$/￥ + 数字）按需启停；身份证 18/15 位 + GB 11643-1999 校验码；银行卡走 Luhn
- [ ] **FP-04**: 词法 / 上下文：避免跨边界吞文本（如 "手机号：138xxxxxxxx" 不吞冒号）；中英 / 中数混合边界用 `is_han` 集中策略；中央化 Unicode block 覆盖 Extension A/B/supplementary-plane

### 漏识修复（FN）

- [ ] **FN-01**: Word 全结构纳入扫描：`paragraph / table (递归 + 合并单元格去重) / header (default/first/even) / footer (default/first/even) / comment (v1.2.0 API) / footnote / endnote`；`location` 字符串按 schema 编码
- [ ] **FN-02**: Word 嵌入图 OCR：抽 `word/media/imageN.*` 字节 → 复用 `mixed_pdf.py` 的 OCR 推理路径 → bbox 回写；按需触发（图片尺寸 / DPI 阈值）
- [ ] **FN-03**: 隔符号鲁棒匹配：`normalize_with_source_map` 返回 `(normalized_text, index_map)`，命中的 start/end 用原文 offset；空格 / 全角 / 破折号 / 换行可分隔但 start/end 严格用原文 code-point
- [ ] **FN-04**: 多字段组合上下文（人名 + 电话 + 地址联动）：同一段 + 前后 50 字窗口；姓名识出来后在该窗口内强相关字段加权；命中合并时同段内允许合并

### 测试与回归（TEST）

- [ ] **TEST-01**: 现有 162 项全量回归不退化（按 ID 比对：160 PASS + 2 known fail 保持）；每个 phase 单独跑基线
- [ ] **TEST-02**: 主样本 `pdf/抵账协议0522.docx----刘骁毅原版.docx` fixture 化 + 「旧引擎 expected-hit manifest」differential regression
- [ ] **TEST-03**: Word 结构全覆盖 fixture（表 / 页眉页脚 / 批注 / 脚注 / 尾注每类 ≥1）+ 主样本 + 真实嵌入图 docx；四段端到端断言（inventory → expected hits → apply redaction → reopen/package invariants）

### 硬约束（CONST）

- [ ] **CONST-01**: v39 期间**不修改** `privacyguard/ocr/*`（PDF-only 模块：text_pdf / mixed_pdf）+ `privacyguard/workers/ocr_worker.py`（PDF OCR worker）+ `OCRWorker.page_result_signal` payload；PDF 端任何代码改动都视为 v39 引入的回归需立即修复。ARCH-03 仅产出"只读"边界文档，**不重构** PDF 侧

## v2 Requirements

Deferred to future release (v39.0.x / v39.1+)。Tracked but not in current v39.0.0 roadmap。

### 增量（P2 — v39.0.x / v39.1）

- **INC-01**: 修订痕迹扫描（tracked changes / w:ins / w:del）— python-docx 无 API，需 lxml 直访；v39.1+
- **INC-02**: 按 pattern 永久忽略规则 — schema 扩展（与 v37.8.0 永久 override schema 兼容性待评估）；v39.0.x
- **INC-03**: 车牌号规则（含新能源）— 优先级低；v39.1+
- **INC-04**: per-file rule mapping for batch replace — 项目当前路线图；v39.1+
- **INC-05**: 批量规则集模板（template import/export） — v39.1+
- **INC-06**: 预览按 source 过滤高亮 — UI 增量；v39.0.x

### 架构位（P2 — 接口留位，v39 不接）

- **INT-01**: `LlmBackend` Protocol / abstract — 留接口位供 v2+ 接 LLM 云端或本地小模型；v39 不实现
- **INT-02**: `field_type` 字段扩展 `HitOverrideStore.filtered_hits` — 为 v39.1+ 的字段级 override 留位

## Out of Scope

显式排除。带原因防止下次又被加回来。

| Feature / 改动 | 原因 |
|---------|------|
| LLM / 云端 NER API 接入 | 违反 local-first + 律师保密 + 延迟；架构层仅留 `LlmBackend` Protocol 接口位 |
| 本地大模型推理（spaCy / HanLP / PaddleNLP / LLaMA / Qwen） | 体积 ≥4GB + 1-3 分钟 + GPU 依赖 + license 风险 |
| AI 自动替换内容 | 法律严肃性 + 回滚成本；当前 v37.8.0「预览 + 人工干预」已覆盖 |
| OCR 全自动预处理 | 5-30s 延迟 + 命中冲突；v39 走 FN-02「嵌入图按需 OCR」 |
| 多语言 i18n | 100% 中文法律场景；界面全部中文化 |
| 云端协同 / 同步 | local-first + 同步冲突；config.json 走 git / 共享盘 |
| docx2python / docx2txt / docxtpl / pandoc | 维护面 + 结构丢失；python-docx + mammoth 够用 |
| python-docx-ng fork | 上游 drift 风险；走官方 python-openxml |
| UI 视觉重做 / 新交互 | 当前 UI 已稳定；v39 不动视觉（结构性 UI 调整允许） |
| 打包 / Windows / macOS 构建链路改动 | v37-v38 打包链路已稳定；不在 v39 范围 |
| **PDF 端脱敏代码改动** | **用户硬约束（CONST-01）+ 风险敞口过大**；v39 仅读 PDF 源不修改 |
| DOC → DOCX 转换逻辑改动 | 已收敛到 `privacyguard/utils/doc_converter.py`，v39 不动 |
| Word 嵌入图 OCR 之外的图像 OCR（如 floating image / OLE / chart） | 降级策略复杂；Phase 6 spike 后再评估 |

## Traceability

由 roadmapper 在 ROADMAP.md 创建时填充。当前为空。

| Requirement | Phase | Status |
|-------------|-------|--------|
| (待 roadmapper 填充) | | Pending |

**Coverage:**
- v1 requirements: 17 total
- 硬约束: 1（CONST-01，全 v39 适用）
- 待 roadmapper 映射到 7 个 phase

---

*Requirements defined: 2026-08-19*
*Last updated: 2026-08-19 after research synthesis + user constraint CONST-01 (PDF 端不改)*