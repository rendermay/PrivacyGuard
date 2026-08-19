# Project Research Summary

**Project:** PrivacyGuard v39.0.0 — Word 脱敏重做
**Domain:** 桌面端本地 Word 文档隐私信息脱敏（中文法律 / 政务 / 商务场景）；brownfield Python + PyQt6 桌面应用
**Researched:** 2026-08-19
**Confidence:** HIGH（基于源码实测 + Context7 官方文档 + 已落地的 162 项回归基线 + v37-v38 Validated 能力）

---

## Executive Summary

PrivacyGuard v39.0.0 的核心不是「加新 Feature」，而是把 v37-v38 散落在 `main.py` 13k 行单体内的 Word 脱敏能力**结构性重构**：抽出到 `privacyguard/word/*` 子包、补齐结构覆盖（页眉/页脚/批注/脚注/尾注/嵌入图 OCR）、重做姓名/地址词权重的精度与上下文判定、并严格保留 v37.8.0 的人工干预 + v38.0.1 的白名单片段级豁免语义基线。

v39 显式**不引入新 binary 依赖**——栈与 v38 完全一致（python-docx 1.2.0 + lxml 6.1.1 + mammoth 1.11.0 + jieba 0.42.1 + rapidocr-onnxruntime 1.4.4 + difflib stdlib）；LLM / 本地大模型 / 云端协同 / AI 自动替换**显式排除**，架构层仅留接口位（`LlmBackend` Protocol）。spaCy-zh / HanLP / PaddleNLP 因模型体积 + torch / paddlepaddle 依赖 + 与 onnxruntime 偶发冲突而拒绝。

**最大风险是「边重构边改语义」**：扫描接口（`paragraph.text` / `run.text` 双坐标系）、预览与保存的 offset 不一致、jieba `nr` 词性直接当结论、嵌入图 OCR 复用 PDF 通道但坐标系未对齐、162 项回归可能因 fixture 被一起改而「假阳性全绿」。**Mitigation** 是 Phase 1 冻结 v38 外部行为（ABI / signal payload / field schema / `HitOverrideStore.filtered_hits` 入口 / `whitelist_trim_only` 默认值），按 Strangler 模式逐步替换 main.py，最后再删除兼容层；并对每个新 Phase 维持 162 项基线 + 主样本（旧引擎 expected-hit manifest）做 differential regression。

---

## Key Findings

### Recommended Stack

v39 走「重构 + 工程调优」路线，依赖矩阵零变化。

**Core technologies（已就绪，无需新增）：**
- **python-docx 1.2.0**（2025-06-16）— Word 结构遍历；v1.2.0 新增 `document.comments` 原生 API；覆盖 ~95% 元素
- **lxml 6.1.1**（实装 / requirements.txt 6.0.2）— 补 python-docx 缺位的 footnotes/endnotes；走 `doc.part.rels`
- **mammoth 1.11.0**— DOCX→HTML 预览 + `extract_raw_text` 兜底；**仅 view 层，不作结构真值源**
- **jieba 0.42.1 + 自定义词典**（`privacyguard/pii/name_recognizer.py`）— v39 改为「降级为候选 → 多层打分」
- **rapidocr-onnxruntime 1.4.4**— Word 嵌入图 OCR 复用 PDF 端 `mixed_pdf.py` 路径
- **difflib（stdlib）**— 段落级脱敏前后 diff

**Explicitly excluded：** spaCy / HanLP / PaddleNLP / docx2python / docx2txt / docxtpl / pandoc / python-docx-ng / anytree；LLM / 云端 NER / 本地大模型 / 云端协同 / AI 自动替换。

### Expected Features

v39 共 **15 个 P1 必达项 + 6 个 P2 增量 + 3 个 P3 拒绝**：

**Must have（P1 — 不达不出 v39.0.0）：** ARCH-01/02/03/04 + FP-01/02/03/04 + FN-01/02/03/04 + TEST-01/02/03

**Should have（P2 — v39.0.x / v39.1 增量）：** 修订痕迹扫描、按 pattern 永久忽略规则、车牌号、per-file rule mapping for batch replace

**Defer / 显式拒绝：** LLM 云端 NER / 本地大模型 / 云端协同 / AI 自动替换 / 多语言 i18n / OCR 全自动预处理 / UI 视觉重做 / 打包链路 / DOC→DOCX / PDF 端改动

**v37-v38 已 Validated 必须保留语义基线：** 人工干预（HitOverrideStore 唯一消费入口）+ 黑/白名单 + `whitelist_trim_only=True` 默认值 + `source ∈ {rule, ocr, jieba, seal, blacklist, manual}` + 双预览合并顺序 `rule > manual > ocr`。

### Architecture Approach

**Strangler 抽取模式** — 不一次性替换 main.py，按依赖图逐步抽到 `privacyguard/word/*` 子包（10 个模块），main.py 始终可运行；目标：13275 行 → < 10000 行。

**目标模块边界（`privacyguard/word/*`）：**
1. `contracts.py` — `HitDict` TypedDict / `WordLocation` dataclass / `WordDocSnapshot` dataclass / `HitSource` Literal
2. `doc_scanner.py` — DOCX 结构读取（paragraph / table / header / footer / comment / footnote / endnote / image_block）
3. `rule_engine.py` — 规则 + jieba + blacklist 注入 + whitelist trim
4. `hit_collector.py` — 多通道命中聚合 + `merge_priority` + `HitOverrideStore.filtered_hits` 唯一入口
5. `preview_bridge.py` — mammoth DOCX→HTML + data-key 注入 + 双 panel fragment
6. `batch_replacer.py` — `WordBatchReplaceWorker` 重构（QThread，signal ABI 兼容）
7. `save_writer.py` — `apply_range_to_runs` + `replace_matches_in_paragraph` 重构（run 级 XML text-node patcher）
8. `web_bridge.py` — `WebViewBridge`（4 槽 + contextmenu；后置注入 main_window）

**保留公共层：** `redaction/*`（HitRef / HitOverrideStore / BlackWhiteListStore / whitelist_split / doc_hash）+ `pii/name_recognizer.py` + `utils/{doc_converter, temp_manager, security, exceptions}` + `ocr/*`（PDF-only）。

**字段契约表（ARCH-04）：** `start / end / text / source / rule_name / replacement / pattern / mode / rect(only OCR) / doc_hash / location`；`source ∈ Literal["rule","ocr","jieba","seal","blacklist","manual"]`；`location` 字符串格式：`paragraph_{idx}` / `table_{T}_cell_{R}_{C}` / `header_{S}_{idx}` / `footer_{S}_{idx}` / `comment_{idx}` / `footnote_{idx}` / `endnote_{idx}` / `image_block_{idx}`。

### Critical Pitfalls（前 6 条最致命）

1. **`Document.paragraphs + Document.tables` 当作完整 Word 文本**（Pitfall 1）— 嵌套表 / 修订 / 页眉页脚 / 批注 / 脚注 / 尾注漏掉；合并单元格重复扫描。预防：唯一 `StoryWalker` 用 `iter_inner_content()` 保序；递归 table；按底层 XML 去重 merged cell。
2. **直接赋值 `run.text` / `paragraph.text` 破坏非文本子节点**（Pitfall 4，python-docx issue #1519）— 批注消失 / 脚注引用丢失 / drawing 受损。预防：patcher 只改 `w:t` 文本节点，**不直接赋空串**；保存后做 package-level invariant。
3. **`para.text` 扫描 + `run.text` 重建 offset 不一致**（Pitfall 3）— hyperlink / field / tab / 内容控件 / 跨 run 后替换错位。预防：`TextLinearizer`（Python Unicode code-point、左闭右开）+ token list + source map；JS/Qt UTF-16 offset 在 bridge 边界转换。
4. **jieba `nr` 直接当姓名结论**（Pitfall 11，jieba issue #470）— 生僻姓名切碎 / 产品名误标 /职务词误标。预防：jieba 只生成 candidate；多层打分（词性 + 黑名单 + 上下文 + 姓氏库）；负词作上下文 feature。
5. **OOXML namespace 处理错误**（Pitfall 6）— `.find('w:body')` 返回 `None`；漏 `w:delText`。预防：`qn('w:...')` 或 Clark name；显式 token policy；缺失结构化报错。
6. **Mammoth HTML 当文档真值或位置模型**（Pitfall 7，Mammoth issue #147）— chart / 对象静默忽略。预防：DOCX/OOXML 是唯一事实源；Mammoth 仅 view projection；保留 `result.messages`；DOM 节点只持 canonical location ID。

**其他高频 Pitfall：** header/footer proxy `is_linked_to_previous`（Pitfall 2）/ comments vs footnotes/endnotes API 差异（#1/#1087）（Pitfall 5）/ 隔符号规范化丢原文坐标必须返回 `(normalized_text, index_map)`（Pitfall 8）/ 数字规则 `\b \d ^...$` 未定义语义（Pitfall 9）/ `[一-鿿]` 不覆盖 Extension A/B/supplementary-plane（Pitfall 10）/ 地址贪婪 regex（Pitfall 12）/ 一次性替换 main.py（Pitfall 13）/ 字段重命名永久双轨（Pitfall 14）/ 强行 PDF/Word 共用 hit processor（Pitfall 15）/ 162 项数量伪基线（按 ID 比对 160 PASS + 2 known fail）（Pitfall 16）/ 动态拼复杂 DOCX fixture（python-docx 简单 + golden checked-in + `fixture-manifest.json`）（Pitfall 17）/ SUT 输出生成 fixture（Pitfall 18）/ 10MB/100页伪性能指标（text-heavy / table-heavy / media-heavy 三类）（Pitfall 19）/ 只测「能扫到」不测「能写回 + 重打开」（四段断言）（Pitfall 20）。

---

## Implications for Roadmap

基于研究，建议 v39 采用**「架构先行 → 结构覆盖 → 规则调优 → 嵌入图 OCR → 性能回归」**7 阶段序列：

### Phase 1: 基线、Fixture 治理与接口契约冻结
**Rationale：** Pitfall 13/16/18 预防。**Delivers：** `HitOverrideStore.filtered_hits` + signal payload + `__scan_meta__` 冻结；162 项 compatibility lane不可修改（按 ID 比对 160 PASS + 2 known fail）；`docs/word/FIELD_MAPPING.md` + `WordHit` / `WordLocation` schema；`tests/fixtures/builders/word_builder.py` + 简单 fixture；主样本「旧引擎 expected-hit manifest」；fixture 派生（非真实 PII）+ package-level PII 审计 gate。

### Phase 2: Story 遍历与可逆坐标映射
**Rationale：** FN-01 + ARCH-02 必须先于一切规则调优；Pitfall 1/2/3/6 硬约束。**Delivers：** `doc_scanner.py`（唯一 `StoryWalker`：顶层 `iter_inner_content()` + 递归 table + default/first/even × header/footer 六种 story + comments v1.2.0 + footnotes/endnotes lxml 直访 adapter）；`contracts.py`；`TextLinearizer`（logical_text + token list + source map）；多 section + linked-to-previous fixture（不 materialize 新 part）。

### Phase 3: Strangler 架构抽取 + 命中合并与写回
**Rationale：** Pitfall 13/14/15。ARCH-01/04 全部落地。**Delivers：** `rule_engine.py`、`hit_collector.py`、`save_writer.py`（XML text-node patcher；**禁止 `run.text = ""` / `paragraph.text = ""`**）；main.py 兼容层；core single-write test；`FIELD_MAPPING.md` 双签。

### Phase 4: 数字、Unicode、隔符号规则
**Rationale：** FP-01 + FN-03 共用 normalizer。**Delivers：** `normalize_with_source_map`（返回 `(normalized_text, index_map)`）；身份证 18/15 位 + GB 11643-1999 校验码；手机号 1[3-9]xxxxxxx + 拒识规则（110/120/119/400/800/订单号/工单号）；银行卡 Luhn；中央化 `is_han` / Unicode block policy（覆盖 Extension A/B/supplementary-plane）；数字边界 `(?<![0-9])... (?![0-9])`；隔符号有限可审计集合。

### Phase 5: 姓名、地名、地址上下文调优
**Rationale：** FP-02 + FP-04 + FN-04；Pitfall 11/12 硬约束。**Delivers：** `NameRecognizer` 分层打分（L1 词法 0.3 / L2 黑名单 -0.5 一票否决 / L3 上下文 +0.4 / L4 姓氏库必满足）；行政区划黑名单子集（GB/T 2260）；职务词黑名单子集；地址分层 component + longest-valid chain；多字段组合上下文窗口（同一段 + 前后 50 字）；字段级 override 粒度（`filtered_hits` 增 `field_type`，向后兼容）。

### Phase 6: 嵌入图 OCR 与预览一致性
**Rationale：** FN-02 + 预览/OCR 一致性；Pitfall 7 硬约束。**Delivers：** Word 嵌入图抽字节（`zipfile` 解 `word/media/imageN.*` + `temp_manager`）；OCR 命中结构（`[(text, bbox)]` → `[{start, end, text, source="ocr", rect=...}]`）；按 blob hash + OCR config cache；`preview_bridge.build_base_html/left/right_panel_updates`（snapshot + mammoth + data-key + 警告收集）；`web_bridge.WebViewBridge`（4 槽 + contextmenu + 后置注入）；preview fixture 验证「可定位 + 警告」；image 损坏/外链/不支持格式 → `KeyError`/I/O/解码异常，保留 location + warning（**不** `except Exception: pass`）。

### Phase 7: 批量替换、性能、安全与发布回归
**Rationale：** batch_replacer + v39 release gate；Pitfall 19/20。**Delivers：** `batch_replacer.py`（signal ABI 兼容 + `doc_converter` 复用）；三类性能 fixture（text-heavy / table-heavy / media-heavy）+ 结构指标 + cold/warm elapsed + peak RSS + cancel latency + UI event-loop heartbeat；四段端到端断言（inventory → expected hits → apply redaction → reopen/package invariants）；162 项 compatibility lane 不退化（按 ID 比对）；v39 增量测试独立统计；`wc -l main.py` 从 13275 → < 10000；main.py 集成后删除冗余实现；Mammoth HTML sanitize `javascript:` + `external_file_access=False`；失败 story diagnostics 聚合 + incomplete 阻止无提示保存。

### Phase Ordering Rationale

依赖图强制约束（FEATURES.md §5）：ARCH-01/04 先做 → FN-01 先于 FN-02/FN-04 → FP-01 与 FN-03 同层 → FN-04 最后。

Pitfall 强制约束：Phase 1 冻结 ABI + baseline；Phase 2 先建 source map；Phase 3 patcher 不破坏 reference；Phase 5 在架构稳定后调参。

### Research Flags

**Needs research-phase：** Phase 2（footnote/endnote 写回边界 + tracked changes + Word/LibreOffice package 差异）/ Phase 5（hard-negative ≥30 法律文书 corpus + precision/recall delta）/ Phase 6（嵌入图类型分布 spike +不可读对象降级）/ Phase 7（v38 在本机 baseline：cold/warm elapsed + peak RSS + cancel latency）。

**Standard patterns (skip research)：** Phase 1（ABI 冻结 + characterization test）/ Phase 3（Strangler 抽取）/ Phase 4（Luhn + GB 11643 + jieba 词典）/ Phase 6 部分（WebViewBridge 4 槽 + mammoth + data-key）。

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | **HIGH** | requirements.txt 已固定版本 + Context7 官方 + 本地 pip list 实测；零新依赖有完整备选对比 |
| **Features** | **HIGH** | PROJECT.md + 真实样本（`pdf/抵账协议0522.docx----刘骁毅原版.docx` 32 KB 含表格甲方/乙方/身份证/银行账号/地址）+ 162 项回归基线 + v37-v38 决策 |
| **Architecture** | **HIGH** | main.py 13275 行 + `privacyguard/workers/word_worker.py` 254 行 + 162 项基线 + 已落地 `redaction/`；依赖图清晰 |
| **Pitfalls** | **MEDIUM** | python-docx / Mammoth / jieba 官方 issue tracker + 项目源码为主；**中文姓名 / 地址边界策略仍需真实样本验证** |

**Overall confidence：** **HIGH**。Phase 5/6/7 的研究 flag 已标。

### Gaps to Address

- Phase 5 前构造 ≥30 份法律文书 hard-negative fixture（合成替换 + 跨字段 scorer）+ jieba 词典版本化 precision/recall delta 评估
- Phase 2 前在 Word + LibreOffice 双保存器跑 footnote/endnote fixture，验证 relationship + content_type
- Phase 6 前扫描真实样本 docx 的 `word/media/*` 类型分布（png/jpg/emf/wmf/tiff/bmp）+ OCR 成功率
- Phase 7 前采集 v38 baseline（text/table/media 三类 fixture 的 cold/warm elapsed + peak RSS + cancel latency）
- ARCH-03 接口位 v2+ 实际协议形状（v39 不接，留位即可）

---

## Sources

### Primary（HIGH）
- Context7 /python-openxml/python-docx（1.2.0 release notes + comments API + issue #1/#1087/#1516/#1519）
- Context7 /mwilliamson/python-mammoth（1.11.0 + issue #147/#36/#79/#483/#413）
- Context7 /rapidai/rapidocr（ONNX models + CUDA/CPU/DML/CANN/CoreML）
- Context7 /fxsjy/jieba（0.42.1 + issue #470/#210/#222/#1017）
- Context7 /ankushshah89/python-docx2txt（0.9 范围）
- Context7 /websites/docxtpl_readthedocs_io_en（确认不适用于 fixture 合成）
- Python `re` 官方文档（Unicode `\d \w \b` + `re.ASCII`）
- Unicode Blocks 数据（CJK + Extension A/B/supplementary-plane）

### Project-local（HIGH — 直接源码）
- `main.py`（13275 行）+ `privacyguard/workers/word_worker.py`（254 行）+ `ocr_worker.py`（1006 行）
- `privacyguard/redaction/{hit_ref, override_store, black_white_list_store, whitelist_split, doc_hash}.py`
- `privacyguard/ocr/{text_pdf, mixed_pdf}.py`（PDF-only）+ `pii/name_recognizer.py`
- `requirements.txt` + 本地 `pip list`（实测：python-docx 1.2.0 / jieba 0.42.1 / lxml 6.1.1 / onnxruntime 1.28.0 / rapidocr-onnxruntime 1.4.4）
- `tests/unit/{test_word_source_field, test_bridge_override_slots, test_override_store, test_convergence, test_batch_word_replace, test_whitelist_split, test_whitelist_trim_only, test_whitelist_trim_only_config, test_name_recognizer, test_worker_name_recognition}.py`

### Project docs（HIGH）
- `.planning/PROJECT.md`（v39 范围 + ARCH/FP/FN/TEST 编号 + Out of Scope）
- `CLAUDE.md`（v38.0.0 + v38.0.1 基线）
- `CHANGELOG.md`（v37-v38 已落地能力）
- `docs/superpowers/specs/2026-08-19-whitelist-trim-only-design.md`
- `docs/current/STATUS.md`（已知 2 项回归：`test_scan_default_level_matches` + `test_simple_config_reads_config_json_values`，`redaction.scan.default_level` 期望 1.5 实测 2.0）

### Secondary（MEDIUM）
- WebSearch spaCy zh_core_web_trf（~500MB + torch + F1 ~0.90）
- WebSearch PaddleNLP ernie-tiny（~25-30MB 但 paddlepaddle ~700MB）
- WebSearch python-docx iterate all elements（Stack Overflow / issue #951）
-行业标准：GB 11643-1999 / GB/T 17751 / GB/T 2260 / GB 32100-2015 / JR/T 0025
- 法规：《最高人民法院关于人民法院在互联网公布裁判文书的规定》/ PIPL（2021）/ 《数据安全法》（2021）

### Tertiary（LOW — 需 v39 实施期验证）
- 中文姓名 / 地址 hard-negative 真实 corpus 指标- Word / LibreOffice package 差异
- 嵌入图类型分布
- v38 在本机的性能 baseline

---

## Quick Reference — v39 不做（防回潮）

| 显式不做 | 原因 | 替代方案 |
|---------|------|---------|
| LLM 云端 NER | 违反 local-first + 律师保密 + 延迟 + 厂商风险 | `LlmBackend` 接口位（v2+） |
| 本地大模型推理 | 4-bit ≥4GB + 1-3 分钟 + GPU + license | 词典 + regex + 启发式 |
| AI 自动替换 | 法律严肃性 + 回滚成本 | 「预览 + 人工干预」（v37.8.0） |
| OCR 全自动预处理 | 5-30s 延迟 + 命中冲突 | 「嵌入图按需 OCR」（FN-02） |
| 多语言 i18n | 100% 中文法律场景 | 界面全部中文化 |
| 云端协同 | local-first + 同步冲突 | config.json git / 共享盘 |
| spaCy / HanLP / PaddleNLP | 体积 + 依赖冲突 | jieba X3（v39 重做打分） |
| docx2python / docx2txt | 维护面 + 结构丢失 | python-docx + mammoth |
| docxtpl | 模板场景错位 | python-docx 直接 add_paragraph |
| pandoc | Haskell 二进制 | mammoth |
| python-docx-ng fork | 上游 drift | python-openxml 上游 |
| 修订痕迹扫描（v39.0） | python-docx 无 API | 延后到 v39.1 |
| 按 pattern 永久忽略 | schema 扩展 | 延后到 v39.1 |
| 车牌号 | 低优先级 | 延后到 v39.1 |
| per-file rule mapping |后续轨道 | v39.1+ |
| UI 视觉重做 | Out of Scope | 不做 |
| 打包链路改动 | Out of Scope | 不做 |
| PDF 端改动 | **用户硬约束** + Out of Scope | 不做（v39 引入的回归除外） |
| DOC→DOCX 转换逻辑 | Out of Scope | 不做 |

---

*Research completed: 2026-08-19*
*Ready for roadmap: yes*
*Suggested phases: 7（基线契约 → Story 遍历 → Strangler 抽取 → 数字规则 → 姓名地址 → 嵌入图 OCR → 批量性能回归）*
*Phases needing research-phase: 2 / 5 / 6 / 7*
*Phases with standard patterns: 1 / 3 / 4 / 6-partial*