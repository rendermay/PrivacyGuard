# Roadmap: SecureRedact v39.0.0 — Word 脱敏重做

**Milestone:** v39.0.0
**Goal:** 系统性重做 Word 文档脱敏的架构 + 识别 + 扫描覆盖三类问题，根治误识 / 漏识 / 散落。
**Phase 数量:** 7（基线契约 → Story 遍历 → Strangler 抽取 → 数字规则 → 姓名地址 → 嵌入图 OCR → 批量性能回归）
**Created:** 2026-08-19

---

## Hard Constraints（贯穿全部 Phase）

> **CONST-01**: v39 期间**不修改** `secureredact/ocr/*`（PDF-only：`text_pdf.py` / `mixed_pdf.py`）+ `secureredact/workers/ocr_worker.py` + `OCRWorker.page_result_signal` payload。PDF 端任何代码改动都视为 v39 引入的回归需立即修复。ARCH-03 仅产出"只读"边界文档，**不重构** PDF 侧。
>
> **CONST-02**: v39 走纯架构重构 + 工程调优，**零新 binary 依赖**（依赖矩阵与 v38 一致：python-docx 1.2.0 + lxml 6.1.1 + mammoth 1.11.0 + jieba 0.42.1 + rapidocr-onnxruntime 1.4.4 + difflib stdlib）。
>
> **CONST-03**: 162 项全量回归不退化（按 ID 比对：160 PASS + 2 known fail 保持——`test_scan_default_level_matches` + `test_simple_config_reads_config_json_values`，自 v37.7.6 起存在）。

每个 Phase 的 guard / pre-condition 都必须显式声明「未触动 PDF 端」+ 162 项基线不退化。

---

## Phase Overview

| # | Phase | 类别 | 核心交付 | 主映射需求 |
|---|-------|------|----------|------------|
| 1 | 基线、Fixture 治理与接口契约冻结 | 基础设施 | ABI 冻结 / FIELD_MAPPING / 主样本 manifest / 162 项 compatibility lane | ARCH-02, ARCH-04, TEST-01, TEST-02 |
| 2 | Story 遍历与可逆坐标映射 | 架构 + FN | `doc_scanner` + `contracts` + `TextLinearizer` + source_map | FN-01, ARCH-02, ARCH-04 |
| 3 | Strangler 架构抽取 + 命中合并与写回 | 架构 | `rule_engine` / `hit_collector` / `save_writer` / main.py 兼容层 | ARCH-01, ARCH-02, ARCH-04 |
| 4 | 数字、Unicode、隔符号规则 | FP + FN | `normalize_with_source_map` + Luhn + GB 11643 + Unicode block | FP-01, FP-03, FP-04, FN-03 |
| 5 | 姓名、地名、地址上下文调优 | FP + FN | `NameRecognizer` 分层打分 + 多字段上下文窗口 | FP-02, FP-04, FN-04 |
| 6 | 嵌入图 OCR 与预览一致性 | FN + 预览 | `word/media/imageN.*` 抽字节 + OCR 命中回写 + `preview_bridge` + `web_bridge` | FN-02, ARCH-04 |
| 7 | 批量替换、性能、安全与发布回归 | 收尾 | `batch_replacer` + 三类性能 fixture + 四段端到端断言 + REUSE_BOUNDARY | TEST-01, TEST-03, ARCH-03 |

**Coverage check:** 17 项 v1 需求 + 1 项硬约束 CONST-01 全部映射，**0 unmapped**（详见底部 Coverage 矩阵）。

---

## Phase 1 — 基线、Fixture 治理与接口契约冻结

### Goal

在不触动 PDF 端与 main.py Word 行为的前提下，把 v38.0.1 外部可观察行为（ABI / signal payload / field schema / 消费入口）冻结成契约文档；并把主样本与最小 fixture 沉淀为「旧引擎 expected-hit manifest」，作为后续 6 个 Phase 的 differential regression ground truth。

### 为什么先做

Pitfall 13（一次性替换 main.py）+ Pitfall 16（162 项数量伪基线）+ Pitfall 18（SUT 输出当 fixture）三条预防都要求 Phase 1 先冻结。先有 baseline，才能在 Phase 2-7 真正放心动 Word 代码。

### Guard / Pre-condition

- **未触动 PDF 端**：`git diff main.py secureredact/ocr/* secureredact/workers/ocr_worker.py` 保持 v38.0.1 的 hotfix diff 不变（本 Phase 也不去删这些 diff）。
- **162 项基线不退化**：跑全量回归，160 PASS + 2 known fail 保持。
- 不修改 `main.py` 中任何 Word 相关代码；本 Phase 只新增文件。

### Maps to

- ARCH-02：规则 / 命中 / 预览三层接口契约的初稿（仅 doc + TypedDict，不改实现）
- ARCH-04：`docs/word/FIELD_MAPPING.md` 双签表初版（OCR / Word / Preview 三视角）
- TEST-01：compatibility lane 跑通（按 ID 比对）
- TEST-02：主样本 fixture 化 + 旧引擎 expected-hit manifest

### Success Criteria（observable user behaviors）

1. **契约文档双签发布**：`docs/word/FIELD_MAPPING.md` 包含 `HitDict` TypedDict / `WordLocation` dataclass / `source ∈ {rule, ocr, jieba, seal, blacklist, manual}` Literal，OCR 视角列出现有 `OCRWorker.page_result_signal` payload 字段，Word 视角列出 v37-v38 WordWorker 输出字段，Preview 视角列出双预览 fragment 字段；OCR 视角列字段与 PDF 端实际 payload 完全一致（**未触动 PDF 端**作为验证手段）。
2. **消费入口冻结**：`HitOverrideStore.filtered_hits` 的 signature 字段 + `whitelist_trim_only` 默认值 True + `source` 集合 通过 `tests/unit/test_contract_freeze.py` 单元测试固化，跑全量回归确认不变。
3. **主样本 fixture 化**：`tests/fixtures/word/抵账协议0522.docx----刘骁毅原版.docx` 与 `tests/fixtures/word/manifest.json`（旧引擎 expected-hit 列表，含每个 hit 的 `start / end / text / source / rule_name`）入库；`tests/unit/test_main_sample_manifest.py` 跑通：旧引擎扫描主样本产出 hit 集合 ≡ manifest 集合（允许新增 hit 但旧 hit 不可丢失）。
4. **162 项 compatibility lane 跑通**：`tests/unit/test_convergence.py` + 全量回归脚本输出 `Ran 162 tests / FAILED (failures=2)`，2 个 known fail 的 ID 与 v38.0.1 完全相同。
5. **fixture builder 落地**：`tests/fixtures/builders/word_builder.py` 暴露 `build_simple_docx()`（姓名 + 身份证 + 手机号 + 地址 + 银行账号各 1 条），可生成最小合规 docx；`tests/fixtures/builders/PII_AUDIT.md` 记录 PII 字段是否真实值（应使用合成数据）。

### Files Touched（预计）

- 新增：`docs/word/FIELD_MAPPING.md`
- 新增：`tests/fixtures/word/manifest.json`
- 新增：`tests/fixtures/builders/word_builder.py`
- 新增：`tests/fixtures/builders/PII_AUDIT.md`
- 新增：`tests/unit/test_contract_freeze.py`
- 新增：`tests/unit/test_main_sample_manifest.py`
- 不动：`main.py` / `secureredact/ocr/*` / `secureredact/workers/ocr_worker.py` / `secureredact/workers/word_worker.py`

---

## Phase 2 — Story 遍历与可逆坐标映射

### Goal

实现 Word 全结构 Story 遍历（paragraph / table / header / footer / comment / footnote / endnote）+ 可逆的 offset 映射（原文 code-point ↔ normalized code-point），使下游 Phase 4 / 5 / 6 能在统一坐标系下做规则匹配与合并。

### 为什么这个顺序

FN-01 + ARCH-02 必须先于一切规则调优（否则规则命中坐标不可信）。Pitfall 1（嵌套表 / 修订 / 批注 / 页眉页脚漏扫）+ Pitfall 3（`para.text` vs `run.text` 双坐标系）+ Pitfall 6（OOXML namespace 错误）三条硬约束必须在此 Phase 解决。

### Guard / Pre-condition

- **未触动 PDF 端**：`secureredact/ocr/text_pdf.py` / `secureredact/ocr/mixed_pdf.py` / `secureredact/workers/ocr_worker.py` 与 v38.0.1 字节级一致。
- Phase 1 的契约文档已落地，本 Phase 在 `secureredact/word/contracts.py` 实现 TypedDict。
- 162 项基线不退化（Phase 2 仍不修改 main.py 的扫描代码，仅新增 `doc_scanner.py`；现有 main.py 的扫描路径与新增 `doc_scanner.py` 共存，main.py 暂不切换）。

### Maps to

- FN-01：Word 全结构纳入扫描（paragraph / table / header / footer / comment / footnote / endnote；`location` 字符串按 schema 编码）
- ARCH-02：`contracts.py` + `TextLinearizer` + source map 是契约的具体实现
- ARCH-04：`FIELD_MAPPING.md` 增加 Word 视角新增字段条目（`location` 格式 + `text_source` 标记）

### Success Criteria

1. **`doc_scanner.scan_document(path) -> DocSnapshot`** 端到端跑通主样本 + 6 个最小 fixture（paragraph / table / header / footer / comment / footnote / endnote 各 ≥1），每个 fixture 的 `snapshot.location_inventory` 含全部预期 location 字符串（`paragraph_{idx}` / `table_{T}_cell_{R}_{C}` / `header_{S}_{idx}` / `footer_{S}_{idx}` / `comment_{idx}` / `footnote_{idx}` / `endnote_{idx}`），且合并单元格去重后不重复扫描同一段文本。
2. **`TextLinearizer.linearize(paragraph) -> (text, source_map)`** 跑通 hyperlink / field / tab / 内容控件跨 run 场景：`source_map[normalized_idx]` 返回原文 code-point offset；`text` 等于 `paragraph.text`（Python `str.__eq__` 严格相等）。
3. **`contracts.py` TypedDict 严格性**：`HitDict` / `WordLocation` / `WordDocSnapshot` / `HitSource` Literal 由 mypy --strict 模式 pass（CI 中启用），字段缺失或类型错误 → 编译失败。
4. **多 section + linked-to-previous fixture**：`tests/fixtures/word/multi_section.docx` 含 2 个 section + header/footer 链接到上一个 section；`doc_scanner` 在不 materialize 新 part 的前提下正确读取「section 0 自己的 header/footer + section 1 自己的 header/footer」，不返回 None / 不抛异常。
5. **lxml 直访 footnotes/endnotes 适配**：`tests/unit/test_doc_scanner_footnotes.py` 跑通：含 `footnoteReference` 的 fixture 至少返回 1 个 `footnote_0` location；含 `endnoteReference` 的 fixture 至少返回 1 个 `endnote_0` location；fixture 通过 `python-docx + lxml` 双保存器写入 + 重打开 + 跑扫描的一致性测试。
6. **162 项基线不退化**：本 Phase 未切换 main.py 扫描路径，跑全量回归 160 PASS + 2 known fail 保持。

### Files Touched（预计）

- 新增：`secureredact/word/__init__.py`
- 新增：`secureredact/word/contracts.py`
- 新增：`secureredact/word/doc_scanner.py`
- 新增：`secureredact/word/text_linearizer.py`
- 新增：`tests/fixtures/word/{nested_table,header_default,header_first,header_even,footer_default,comment,footnote,endnote,multi_section,hyperlink_cross_run}.docx`（或子目录）
- 新增：`tests/unit/test_doc_scanner.py`、`test_doc_scanner_footnotes.py`、`test_text_linearizer.py`、`test_word_contracts.py`
- 更新：`docs/word/FIELD_MAPPING.md`（Phase 2 增量）
- 不动：`main.py` 现有扫描路径 / `secureredact/ocr/*` / `secureredact/workers/ocr_worker.py`

---

## Phase 3 — Strangler 架构抽取 + 命中合并与写回

### Goal

把 Word 的规则 / 命中 / 保存三个层从 `main.py` 抽出到 `secureredact/word/{rule_engine,hit_collector,save_writer}.py`，main.py 改为调用新模块（保留兼容层），并实现「预览与保存共用 merge_priority 与 merged_hits_by_key」单一数据结构。

### 为什么这个顺序

ARCH-01/04 的落地必须配合 Strangler 抽取（Pitfall 13/14/15）。Phase 2 已稳定坐标，Phase 3 才能放心把规则与保存路径也抽出来。

### Guard / Pre-condition

- **未触动 PDF 端**：`secureredact/ocr/*` + `secureredact/workers/ocr_worker.py` + `OCRWorker.page_result_signal` payload 与 v38.0.1 字节级一致。
- Phase 2 的 `doc_scanner` + `contracts` 已落地。
- 162 项基线不退化（Strangler 模式：main.py 调用 `secureredact.word.*`，原实现保留为兼容层；新旧实现行为一致）。

### Maps to

- ARCH-01：`rule_engine.py` / `hit_collector.py` / `save_writer.py` 三个模块抽取；main.py 保留胶水
- ARCH-02：`merge_priority` + `merged_hits_by_key` 单一数据结构；预览与保存共用
- ARCH-04：`save_writer` 输出的 `text / start / end / source / replacement` 字段与 `FIELD_MAPPING.md` 完全一致；双签表新增 save 视角

### Success Criteria

1. **`rule_engine.scan(text, context) -> list[Hit]`** 跑通主样本：产出 hits 数量 ≥ v37.8.0 main.py 同路径（旧实现，保留兼容层）产出 hits；`source / rule_name / text / start / end` 字段值严格相等（`==`），允许 `replacement` 默认值差异但需记录在 `FIELD_MAPPING.md`。
2. **`hit_collector.merge(hits) -> MergedHits`**：输入三通道命中（rule / manual / ocr），输出 `merged_hits_by_key`（key = `(location, start, end)`），合并顺序 `rule > manual > ocr`；`merged_hits_by_key[key].final_source ∈ {rule, manual}`，ocr 通道命中若与 rule/manual 同坐标被覆盖；`merged_hits_by_key` 与 `merge_priority` 同一数据结构引用，无副本漂移。
3. **`save_writer.apply_hits(doc, merged_hits) -> SaveResult`**：实现 XML text-node patcher，**禁止** `run.text = ""` / `paragraph.text = ""`；patch 后重打开 docx 的 `paragraph.text` 与期望替换后文本严格相等，且不丢失批注 / 脚注引用 / drawing 子节点；`tests/unit/test_save_writer_patch.py` 跑通「patch 前 / patch 后 / 重打开」三阶段断言。
4. **main.py 兼容层落地**：`main.py` 的 Word 路径改为调用 `secureredact.word.*`，原 `WordWorker` 内联规则保留为 `_legacy_rule_engine` 私有函数；UI 行为不变（用户看不出差异）；`tests/unit/test_bridge_override_slots.py` + `test_word_source_field.py` + `test_pdf_source_field.py` 全部 PASS。
5. **核心 single-write test**：`tests/unit/test_word_core_single_write.py`：同一 paragraph 多次 patch 命中同一 run，最终 XML 仅 1 次写操作（避免循环 patcher）；通过 mock `lxml.etree._Element.text` setter 计数验证。
6. **162 项基线不退化**：全量回归 160 PASS + 2 known fail 保持。

### Files Touched（预计）

- 新增：`secureredact/word/rule_engine.py`
- 新增：`secureredact/word/hit_collector.py`
- 新增：`secureredact/word/save_writer.py`
- 新增：`tests/unit/test_rule_engine.py`、`test_hit_collector.py`、`test_save_writer_patch.py`、`test_word_core_single_write.py`
- 修改：`main.py`（仅 Word 路径，调用 `secureredact.word.*`；原实现保留为 `_legacy_*`）
- 更新：`docs/word/FIELD_MAPPING.md`（Phase 3 双签 save / preview 视角）
- 不动：`secureredact/ocr/*` / `secureredact/workers/ocr_worker.py` / PDF 路径

---

## Phase 4 — 数字、Unicode、隔符号规则

### Goal

把数字型规则（身份证 / 手机号 / 银行卡 / 邮箱 / 金额）+ Unicode block policy + 隔符号规范化统一封装到 `secureredact/word/normalizer.py` + `secureredact/word/numeric_rules.py`，使 FP-01 / FP-03 / FP-04 / FN-03 全部落地。

### Guard / Pre-condition

- **未触动 PDF 端**：本 Phase 不修改 `secureredact/ocr/text_pdf.py`（数字规则 Word 端独立维护；如 PDF 端未来需要复用走 ARCH-03 接口位）
- Phase 2 / 3 的 `TextLinearizer` + `contracts` + `hit_collector` 已稳定
- 162 项基线不退化（新增 normalizer，rule_engine 调用，行为变更需 manifest 对齐）

### Maps to

- FP-01：数字型规则拒识订单号 / 工单号 / 110/119/120/800 业务号；mobile 锚定 `(?<![0-9])1[3-9]\d{9}(?![0-9])`
- FP-03：年度 / 型号 / 工单号不进身份证；纯中文 / 中英混合不进邮箱；身份证 18/15 位 + GB 11643-1999 校验码；银行卡 Luhn
- FP-04：避免跨边界吞文本；中央化 `is_han`；Unicode block 覆盖 Extension A/B/supplementary-plane
- FN-03：`normalize_with_source_map` 返回 `(normalized_text, index_map)`；start/end 严格用原文 code-point

### Success Criteria

1. **`normalize_with_source_map(text) -> (normalized, source_map)` 严格逆映射**：`source_map` 是 `list[int]`，长度 = `len(normalized)`；`[''.join(text[i] for i in source_map_part)] == normalized_part`；且 `''.join(text[i] for i in source_map) == normalized` 严格相等（Python `str.__eq__`）。`tests/unit/test_normalizer_source_map.py` 跑通空格 / 全角 / 破折号 / 换行 4 种分隔符共 ≥8 个 fixture。
2. **GB 11643-1999 校验码**：`tests/unit/test_id_card_checkcode.py` 跑通 30 个真实身份证（合成 PII 审计通过）+ 20 个非法校验码全部拒识；18 位与 15 位均支持；年份 1900-当前 + 月日合法。
3. **银行卡 Luhn**：`tests/unit/test_bank_card_luhn.py` 跑通 20 个真实卡号（合成 PII 审计通过）+ 20 个 Luhn 失败号全部拒识；19 位与 16 位均支持。
4. **手机号拒识**：`tests/unit/test_mobile_reject.py` 跑通 `110 / 119 / 120 / 122 / 400 / 800 / 12315 / 12345 / 955xx / 订单号 / 工单号` 共 ≥10 类业务号全部不进 mobile；正常 11 位手机号（`1[3-9]\d{9}`）全识别。`(?<![0-9])...(?![0-9])` 锚定验证：嵌入在数字串（如 `1113800000000`）中的 `13800000000` 片段不被识别。
5. **`is_han` Unicode block policy**：`tests/unit/test_is_han.py` 跑通 `一-鿕`（Basic）+ `㐀-䶿`（Ext A）+ `𠀀-𪛖`（Ext B，等价 surrogate 对）+ supplementary-plane `𫝀-𫠟` + 中英混合 `Hi 你好` 边界，全部返回预期布尔值（无 `chr(0x10000)` 跨界误判）。
6. **跨边界吞文本验证**：`tests/unit/test_no_boundary_swallow.py`：输入 `"手机号：138xxxxxxxx"` + `"Email:foo@bar.com 中英"` + `"金额¥1,234.56元"` 三类 fixture，命中 start/end 严格落在原文 code-point（`：` 与 `@` 与 `¥` 不被吞），source_map 严格逆映射。
7. **162 项基线不退化**：全量回归 160 PASS + 2 known fail 保持。

### Files Touched（预计）

- 新增：`secureredact/word/normalizer.py`
- 新增：`secureredact/word/numeric_rules.py`
- 新增：`secureredact/word/unicode_blocks.py`
- 新增：`tests/unit/test_normalizer_source_map.py`、`test_id_card_checkcode.py`、`test_bank_card_luhn.py`、`test_mobile_reject.py`、`test_is_han.py`、`test_no_boundary_swallow.py`
- 修改：`secureredact/word/rule_engine.py`（调用 normalizer + numeric_rules；旧 main.py 路径保留兼容层）
- 更新：`tests/fixtures/word/manifest.json`（增 normalizer manifest）
- 不动：`secureredact/ocr/*` / `secureredact/workers/ocr_worker.py` / PDF 路径

---

## Phase 5 — 姓名、地名、地址上下文调优

### Goal

把 `secureredact/pii/name_recognizer.py` 的 jieba `nr` 直接结论改为「候选 → 多层打分」，加入行政区划黑名单（GB/T 2260 子集）+ 职务词黑名单（经理 / 主任 / 法官 / 律师 / 法定代表人）+ 多字段组合上下文窗口（同一段 + 前后 50 字）。

### Guard / Pre-condition

- **未触动 PDF 端**：OCR 通道独立于本 Phase；如 PDF 端未来复用 NameRecognizer 走 ARCH-03 接口位
- Phase 4 的 normalizer + Unicode block policy 已稳定
- 162 项基线不退化（jieba 打分变更，旧期望 manifest 需 re-baseline）

### Maps to

- FP-02：姓名 / 地名 / 地址词权重；jieba 只生成候选；行政区划黑名单；职务词黑名单；姓名多层打分
- FP-04：词法上下文
- FN-04：多字段组合上下文

### Success Criteria

1. **NameRecognizer 分层打分落地**：`tests/unit/test_name_recognizer_scoring.py` 跑通：4 层（L1 词法 0.3 / L2 黑名单 -0.5 一票否决 / L3 上下文 +0.4 / L4 姓氏库必满足）按 README 文档的权重计算；总得分 < 阈值不输出姓名 hit；L2 一票否决时即使 L1/L3/L4 全满分也输出 `None`。
2. **行政区划 + 职务词黑名单**：`tests/unit/test_name_blacklists.py` 跑通：含「北京市」「朝阳区」「海淀区」「上海市」「广东省」等 ≥20 个行政区划的 fixture，jieba 候选 `北京市`/`朝阳区` 等不输出为姓名；含「经理」「主任」「法官」「律师」「法定代表人」「董事长」「总经理」「行长」等 ≥10 个职务词的 fixture，jieba 候选 `王经理`/`李主任` 等只输出姓（`王`/`李`）或拒绝（依职务词边界规则）。
3. **姓名 hard-negative corpus**：`tests/fixtures/word/hard_negative_names.docx` 含 ≥30 条法律文书真实姓名片段（合成 PII 审计通过，非真实身份证 / 手机号）；`tests/unit/test_name_recognizer_hard_negative.py` 跑通：precision ≥ 0.85，recall ≥ 0.80（v37-v38 旧 baseline 数据需在 commit message 记录对比）。
4. **多字段组合上下文窗口**：`tests/unit/test_combined_context.py`：输入 paragraph 含 `姓名：王某某 电话：138xxxxxxxx 地址：北京市朝阳区xxx路1号` 三字段，`王某某` 姓名 hit 在电话/地址 hit 同时存在时打 +0.4 加权（vs 单独姓名段落 +0.2）；窗口为同一段 + 前后 50 字（超出窗口的电话/地址不触发加权）。
5. **姓名识别同段合并**：`tests/unit/test_name_segment_merge.py`：输入同一段含 `王某某` 与 `王某某的配偶李某某`，两处姓名 hit 不合并（location 不同 run），但同段内 `王某某` 与 `王某某先生` 重叠时后者合并入前者（保留前者 start/end）。
6. **162 项基线不退化**：全量回归 160 PASS + 2 known fail 保持；`test_name_recognizer.py` + `test_worker_name_recognition.py` + `test_enable_name_recognition_persistence.py` 全部 PASS。

### Files Touched（预计）

- 修改：`secureredact/pii/name_recognizer.py`（jieba 候选 → 多层打分；行政区划 + 职务词黑名单）
- 新增：`secureredact/pii/name_blacklists.py`（GB/T 2260 子集 + 职务词子集）
- 新增：`secureredact/word/context_window.py`（多字段组合上下文窗口）
- 新增：`tests/fixtures/word/hard_negative_names.docx`（合成 PII）
- 新增：`tests/unit/test_name_recognizer_scoring.py`、`test_name_blacklists.py`、`test_name_recognizer_hard_negative.py`、`test_combined_context.py`、`test_name_segment_merge.py`
- 更新：`docs/word/FIELD_MAPPING.md`（增 `field_type` 字段 + 打分权重表）
- 不动：`secureredact/ocr/*` / `secureredact/workers/ocr_worker.py` / PDF 路径

---

## Phase 6 — 嵌入图 OCR 与预览一致性

### Goal

为 Word `word/media/imageN.*` 嵌入图按需触发 OCR，复用 PDF 端 `mixed_pdf.py` 的 OCR 推理路径（**只调用，不修改**）；同时实现 mammoth DOCX→HTML + data-key 注入 + 双 panel fragment 的 `preview_bridge`，使 OCR 命中与预览坐标一致。

### 为什么放在 Phase 5 之后

FN-02 需要复用 Phase 5 的 normalizer 处理 OCR 文本 + Phase 4 的 `start/end` 原文 offset；预览一致性依赖 Phase 3 的 `hit_collector.merge` 单一数据结构。

### Guard / Pre-condition

- **未触动 PDF 端**：本 Phase **仅 import 调用** `secureredact.ocr.mixed_pdf.run_ocr` / `secureredact.workers.ocr_worker.OCRWorker`（v37-v38 公开 API），**不修改** `secureredact/ocr/mixed_pdf.py` / `secureredact/workers/ocr_worker.py` / `OCRWorker.page_result_signal` payload。ARCH-03 接口位（v2+）不在本 Phase 落地。
- Phase 5 的 NameRecognizer + 黑名单已稳定
- 162 项基线不退化（OCR 通道对 Word 是新增能力，旧 fixture 无 OCR 命中）

### Maps to

- FN-02：Word 嵌入图 OCR（按需触发 + blob hash cache + bbox 回写 + 损坏/外链/不支持格式降级）
- ARCH-04：`preview_bridge` 输出与 `FIELD_MAPPING.md` Preview 视角一致；OCR 命中新增 `source="ocr"` + `rect`

### Success Criteria

1. **`word_ocr.extract_media(docx_path) -> list[EmbeddedImage]`** 跑通：含 ≥1 个 `word/media/imageN.png` 的 fixture 返回 EmbeddedImage 列表（bytes + media_path + size）；`word/media/` 不存在 / zip 损坏 / 图片解码失败三种情况返回 `[]` + warning（非抛异常）。
2. **按需触发策略**：`tests/unit/test_word_ocr_threshold.py` 跑通：图片尺寸 < 50×50 或 DPI < 72 时不触发 OCR（返回空命中 + warning）；尺寸 ≥ 100×100 且 DPI ≥ 96 时触发 OCR；同一 blob 二次跑走 cache（通过 mock OCR provider 计数验证）。
3. **OCR 命中结构**：`tests/unit/test_word_ocr_hits.py`：OCR 输出 `[(text, bbox)]` → 转 `{start, end, text, source="ocr", rect=(x,y,w,h)}`；`start/end` 严格用图片内 normalized text 偏移（不跨段）；`source="ocr"` 与 rule/manual/jieba 同坐标时由 `hit_collector.merge` 按 `rule > manual > ocr` 顺序保留前两者。
4. **预览双 panel fragment 一致性**：`tests/unit/test_preview_bridge.py` 跑通：输入 DocSnapshot + MergedHits，输出左 panel HTML（原文 + 高亮）+ 右 panel HTML（合并替换 + 高亮）；两 panel 高亮节点的 `data-key` 与 `merged_hits_by_key` key 一一对应；mammoth `result.messages` 警告聚合到 `PreviewResult.warnings`（不静默吞掉）。
5. **image 损坏 / 外链 / 不支持格式降级**：`tests/unit/test_word_ocr_degradation.py`：构造 fixture 含 `word/media/image_corrupt.png`（PNG 头但坏数据）+ `word/media/image.tiff`（不支持格式）+ 外链图片（`r:id` 指向外部 URL）；OCR 调用 0 次或仅对合法 PNG 触发；损坏/不支持/外链 fixture 输出 `warning ∈ PreviewResult.warnings`，无 `except Exception: pass` 静默吞掉。
6. **`web_bridge.WebViewBridge` 4 槽 + contextmenu**：`tests/unit/test_web_bridge.py` 跑通 4 个槽（on_highlight_clicked / on_highlight_context_menu / on_compare_toggle / on_save_requested）+ contextmenu 触发 `ignore / confirm / revoke / promote` 四动作（与 v37.8.0 HitOverrideStore 对接）。
7. **162 项基线不退化**：全量回归 160 PASS + 2 known fail 保持；OCR provider 调用计数 = 0（不污染 PDF 端测试）。

### Files Touched（预计）

- 新增：`secureredact/word/word_ocr.py`（`extract_media` + 按需触发 + cache）
- 新增：`secureredact/word/preview_bridge.py`（`build_base_html` + `left_panel` + `right_panel_updates`）
- 新增：`secureredact/word/web_bridge.py`（`WebViewBridge` 4 槽 + contextmenu）
- 新增：`tests/fixtures/word/{with_media,media_corrupt,media_unsupported,media_external}.docx`
- 新增：`tests/unit/test_word_ocr.py`、`test_word_ocr_threshold.py`、`test_word_ocr_hits.py`、`test_word_ocr_degradation.py`、`test_preview_bridge.py`、`test_web_bridge.py`
- 更新：`docs/word/FIELD_MAPPING.md`（Preview 视角新增 data-key / warnings 字段）
- 不动：`secureredact/ocr/*`（仅 import）+ `secureredact/workers/ocr_worker.py`（仅 import）+ PDF 路径

---

## Phase 7 — 批量替换、性能、安全与发布回归

### Goal

把 `WordBatchReplaceWorker` 抽取到 `secureredact/word/batch_replacer.py`（signal ABI 兼容 + `doc_converter` 复用），落地三类性能 fixture（text-heavy / table-heavy / media-heavy）+ 四段端到端断言（inventory → expected hits → apply redaction → reopen/package invariants），并产出 `docs/word/REUSE_BOUNDARY.md`（ARCH-03 只读边界文档）。

### 为什么最后做

Phase 7 是 v39.0.0 release gate。批量 + 性能 + 安全需要 Phase 1-6 的能力全部就位；同时产出 ARCH-03 的只读边界文档，作为 v39 闭环。

### Guard / Pre-condition

- **未触动 PDF 端**：本 Phase 不修改 `secureredact/ocr/*` / `secureredact/workers/ocr_worker.py`；`docs/word/REUSE_BOUNDARY.md` 仅描述 PDF 端公开 API 边界，**不重构 PDF 侧**
- Phase 6 的 preview_bridge + web_bridge + OCR 已稳定
- 162 项基线不退化（性能基线比对：v38 旧版 baseline 需在 Phase 7 前采集）

### Maps to

- TEST-01：162 项全量回归不退化（按 ID 比对）
- TEST-03：Word 结构全覆盖 fixture + 四段端到端断言
- ARCH-03：`docs/word/REUSE_BOUNDARY.md`（只读边界文档，划清 HitRef / HitOverrideStore / BlackWhiteListStore / whitelist_split / doc_hash / name_recognizer / OCR worker 在 PDF/Word 双端的复用边界）

### Success Criteria

1. **`batch_replacer.WordBatchReplaceWorker` 重构**：`tests/unit/test_batch_word_replace.py`（v37.7+ 既有）继续 PASS；新增 `tests/unit/test_batch_replacer_signal_abi.py` 验证 `progress_signal / done_signal / error_signal` 的 payload schema 与 v37.8.0 旧实现字节级一致（Python `dataclasses.asdict` + JSON dump + diff）。
2. **三类性能 fixture**：
   - `tests/fixtures/perf/text_heavy.docx`：≥10 MB，≥500 段落，≥5000 命中候选
   - `tests/fixtures/perf/table_heavy.docx`：≥1 个 ≥100×100 单元格表，合并单元格 ≥50%
   - `tests/fixtures/perf/media_heavy.docx`：≥20 个 `word/media/imageN.*`（≥100 KB 各）
   
   `tests/perf/test_perf_regression.py` 跑通：cold elapsed（首次扫描）≤ v38 baseline ×1.5；warm elapsed（二次扫描）≤ v38 baseline ×1.2；peak RSS ≤ v38 baseline ×1.3；cancel latency ≤ 500 ms。
3. **四段端到端断言**：`tests/integration/test_end_to_end_redaction.py`：每个真实样本 fixture 跑 4 段：
   - **inventory 段**：`doc_scanner.scan_document(path).location_inventory` 含预期 location 集
   - **expected hits 段**：`rule_engine + hit_collector` 产出 MergedHits ≡ manifest（按 key 比对）
   - **apply redaction 段**：`save_writer.apply_hits` 产出 docx 字节；reopen 后 `paragraph.text` 与期望替换后文本严格相等
   - **reopen / package invariants 段**：reopen docx 验证 comments / footnotes / endnotes / drawings / media 全部保留（package-level invariant，无丢失）
4. **`docs/word/REUSE_BOUNDARY.md` 产出**：列出 7 个共享模块（HitRef / HitOverrideStore / BlackWhiteListStore / whitelist_split / doc_hash / name_recognizer / OCR worker）在 PDF / Word 双端的 import 关系图 + public API 列表 + 不变量；文档明确标注「v39 不修改 PDF 端，仅读取并固化复用边界」；`tests/unit/test_reuse_boundary_doc.py` 验证文档存在 + 7 个模块全部出现 + PDF 端文件路径无修改（与 v38.0.1 git diff 一致）。
5. **main.py 集成**：`wc -l main.py` 从 13275 → < 10000；删除兼容层 `_legacy_*` 函数；UI 行为不变（双预览 / 干预 dock / 批量替换全部正常）；`tests/unit/test_bridge_override_slots.py` + `test_word_source_field.py` + `test_pdf_source_field.py` 全部 PASS。
6. **安全检查**：`tests/unit/test_mammoth_sanitize.py` 跑通 mammoth HTML `javascript:` protocol 全部 sanitize + `external_file_access=False`；`tests/unit/test_failure_diagnostics.py` 跑通 story 解析失败聚合 diagnostics + 不完整状态阻止无提示保存。
7. **162 项基线不退化**：全量回归 160 PASS + 2 known fail 保持；v39 增量测试（`tests/unit/test_word_*` + `tests/unit/test_doc_scanner_*` + `tests/perf/*` + `tests/integration/*`）独立统计，全部 PASS。

### Files Touched（预计）

- 新增：`secureredact/word/batch_replacer.py`
- 新增：`docs/word/REUSE_BOUNDARY.md`
- 新增：`tests/fixtures/perf/{text_heavy,table_heavy,media_heavy}.docx`
- 新增：`tests/perf/test_perf_regression.py`
- 新增：`tests/integration/test_end_to_end_redaction.py`
- 新增：`tests/unit/test_batch_replacer_signal_abi.py`、`test_reuse_boundary_doc.py`、`test_mammoth_sanitize.py`、`test_failure_diagnostics.py`
- 修改：`main.py`（删除 `_legacy_*` 兼容层；集成 `secureredact.word.*`）
- 更新：`docs/word/FIELD_MAPPING.md`（v39 闭环）
- 更新：`CHANGELOG.md` + `version.txt`（v39.0.0 release）
- 不动：`secureredact/ocr/*` / `secureredact/workers/ocr_worker.py` / PDF 路径

---

## Coverage Matrix（REQUIREMENTS.md traceability）

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARCH-01（WordWorker/规则/命中/预览抽取到 secureredact/word/*） | Phase 3, Phase 7（集成收尾） | Pending |
| ARCH-02（规则/命中/预览三层接口契约 + 单一数据结构） | Phase 1（契约初稿）, Phase 2（实现）, Phase 3（落地） | Pending |
| ARCH-03（PDF/Word 复用边界文档 — 只读不动） | Phase 7（`REUSE_BOUNDARY.md`） | Pending |
| ARCH-04（字段命名统一 + FIELD_MAPPING.md 双签） | Phase 1（初版）, Phase 2（增量）, Phase 6（Preview）, Phase 7（闭环） | Pending |
| FP-01（数字型规则拒识业务号 + mobile 锚定） | Phase 4 | Pending |
| FP-02（姓名/地名/地址词权重 + 黑名单 + 多层打分） | Phase 5 | Pending |
| FP-03（身份证 GB 11643 + 银行卡 Luhn + 边界） | Phase 4 | Pending |
| FP-04（词法/上下文/Unicode block 策略） | Phase 4（数字边界）, Phase 5（姓名上下文） | Pending |
| FN-01（Word 全结构 Story 遍历） | Phase 2 | Pending |
| FN-02（Word 嵌入图 OCR） | Phase 6 | Pending |
| FN-03（隔符号鲁棒匹配 + source map） | Phase 4 | Pending |
| FN-04（多字段组合上下文） | Phase 5 | Pending |
| TEST-01（162 项基线不退化） | Phase 1（compatibility lane）, Phase 2-6（每 Phase 单独跑）, Phase 7（release gate） | Pending |
| TEST-02（主样本 fixture 化 + 旧引擎 manifest） | Phase 1 | Pending |
| TEST-03（结构全覆盖 fixture + 四段端到端断言） | Phase 7 | Pending |
| **CONST-01（PDF 端不动）** | **全部 7 个 Phase 的 guard / pre-condition** | Pending |

**Coverage validation:**
- v1 requirements 总数: 17
- v1 mapped: 17（ARCH × 4 + FP × 4 + FN × 4 + TEST × 3 = 15 个具名需求 + 2 个 TEST-01 多 Phase）
- 硬约束: 1（CONST-01，全 v39 适用，作为每 Phase 的 guard）
- Unmapped: **0**
- 100% coverage ✓

---

## Dependencies Between Phases

```
Phase 1 (baseline / fixtures / contracts)
  ↓
Phase 2 (doc_scanner / TextLinearizer) ── depends on Phase 1 contracts
  ↓
Phase 3 (Strangler 抽取) ── depends on Phase 1 + Phase 2
  ↓
Phase 4 (normalizer / numeric rules) ── depends on Phase 2 TextLinearizer
  ↓
Phase 5 (name recognizer / context) ── depends on Phase 4 normalizer
  ↓
Phase 6 (Word OCR / preview bridge) ── depends on Phase 3 hit_collector + Phase 5 NameRecognizer
  ↓
Phase 7 (batch / perf / release) ── depends on Phase 1-6 全部
```

每个 Phase 完成后：
1. 162 项全量回归必须 160 PASS + 2 known fail 保持
2. `git diff main.py secureredact/ocr/* secureredact/workers/ocr_worker.py` 与 v38.0.1 hotfix diff 一致（CONST-01 验证）
3. STATE.md 进度更新

---

## Risks & Mitigations

| 风险 | 影响 | Mitigation |
|------|------|------------|
| 「边重构边改语义」导致 main.py Word 行为偏移 | UI 漂移 / 用户感知变化 | Phase 1 冻结 ABI；每 Phase 维持 compatibility lane；differential regression 必跑 |
| jieba 打分重做后 precision/recall 波动 | 姓名误识/漏识 | Phase 5 构造 ≥30 hard-negative fixture；commit 记录 v38 baseline 对比 |
| mammoth HTML sanitize 不全 | XSS / 文件外泄 | Phase 7 `test_mammoth_sanitize.py` 强制覆盖 `javascript:` protocol + `external_file_access=False` |
| 嵌入图 OCR 性能回归 | 主线程阻塞 5-30s | Phase 6 按需触发（尺寸 / DPI 阈值）+ blob hash cache；Phase 7 perf fixture 监控 |
| Strangler 抽取期间 main.py 与 secureredact.word.* 双轨漂移 | 行为分裂 | Phase 3-6 保留 `_legacy_*` 函数 + 断言新旧一致；Phase 7 一次性删除 |
| 162 项 fixture 一起改导致「假阳性全绿」 | 误判 PASS | 按 ID 比对（`test_convergence.py` + `test_config_alignment.py`）；differential regression 必跑 |

---

## Next Steps

1. 立即执行 `/gsd-discuss-phase 1`（基线契约冻结讨论）
2. 每个 Phase 完成后跑 `/gsd-verify-work`（UAT 验收）
3. Phase 7 完成后跑 `/gsd-complete-milestone`（v39.0.0 release gate）
4. v39.0.x hotfix（按需）：如 trim 行为变化 / override scope 变化 → v39.0.x；架构级重构 → v40.0.0

---

*Roadmap created: 2026-08-19*
*Phase 数量: 7（基线契约 → Story 遍历 → Strangler 抽取 → 数字规则 → 姓名地址 → 嵌入图 OCR → 批量性能回归）*
*CONST-01（PDF 端不动）: 全部 Phase guard*
*Coverage: 17/17 v1 + 1/1 CONST = 100%*