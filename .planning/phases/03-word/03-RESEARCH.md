# Phase 3: Word 文档接入识别引擎（双栏对比预览自动高亮） - Research

**Researched:** 2026-08-12
**Domain:** Word 文档自动 PII 识别（识别引擎从 PDF 扩展到 Word 格式） + 双栏对比预览（cp27 增量 DOM patch + PII 高亮） + Word 文档真脱敏写入 + Word 文档属性清除
**Confidence:** HIGH（PIIEngine / PIIHit / word_data 字典契约 / `replace_matches_in_paragraph` run-level API 全部已生产验证）/ MEDIUM（Word run-boundary 跨 `<w:r>` 切分 + `w:tab` / `<w:br/>` 跨段敏感实体识别 + `data-key` ↔ `word_data[key]` 同步一致性的边界情况）

---

## User Constraints (from CONTEXT.md)

> Phase 3 在 2026-08-12 时点未生成独立 CONTEXT.md；以下约束来自 `.planning/STATE.md` §Decisions + `ROADMAP.md` §Phase 3 + `CLAUDE.md` §当前已具备的能力（**未在讨论阶段被覆盖的字段视为自由区，由 Claude 在本研究中推荐**）。

### Locked Decisions（继承自 ROADMAP / STATE / CLAUDE.md，无独立 CONTEXT.md 覆盖）

#### Phase 3 范围与依赖（D-01 / D-02）

- **D-01:** Phase 3 仅交付 Word 格式垂直切片；Excel 走 Phase 4，Image 走 Phase 5，ctx-tier（姓名/机构/地址/业务字段）走 Phase 6，候选审阅 UI 走 Phase 7，识别规则编辑 / 审计 / 打包 / 基线走 Phase 8。
- **D-02:** Phase 3 必须复用 Phase 1/2 的 PII 引擎（`privacyguard.pii.*`）和 `word_data` 数据契约；**不**新建独立 Word 专用 PII 引擎。
- **D-03:** Phase 3 **依赖** Phase 1（PDF + PII 引擎骨架）已就绪；Phase 2 引擎扩展（银行卡 / 邮箱 / USCC / 纳税人 / VAT / 银行账号）在 Phase 3 时必须为 `engine.detect` 可见（9 类 entity_hint）。
- **D-04:** Phase 3 必须保留 `word_data[key] = {"text": ..., "ocr": [...], "manual": [...]}` + `word_replace_rules` 既有契约；新增 PII 通道按 `STATE.md §Decisions` "新数据存进现有 dict 的新 key" 原则放 `word_data[key]["pii"]`。

#### v37.7.6 收敛原则（D-05）

- **D-05:** 新增共享逻辑一律进 `privacyguard/`，**禁止**在 `main.py` 新增 PII / Word adapter 实现；`main.py` 仅作调用方与 UI 装配。
- **D-06:** OCR / PII 引擎保持懒加载（OPS-03）；禁止在 `privacyguard/__init__.py` 或 `privacyguard/workers/__init__.py` 加包级 eager import。
- **D-07:** Word 预览走 `mammoth`（DOCX→HTML）→ `BeautifulSoup` 给每个文本块打 `data-key` → JavaScript 局部 DOM patch（cp27）。Phase 3 **不得**回退到整页 `setHtml()`。
- **D-08:** Word 文档属性清除范围（按 ROADMAP Success Criterion 4 "no longer contains the original sensitive text in its body or document properties"）：`docProps/core.xml`（dc:title / dc:creator / dc:subject / dc:description / cp:lastModifiedBy / cp:revision）+ `docProps/app.xml`（Application / Company / Manager / Template / TotalTime）必须清空 / 置默认值；其他元数据字段保留。**与 Phase 2 PDF 5 字段语义对齐**。
- **D-09:** Word 识别引擎必须在 `_open_word_docx` 自动触发（用户无需点"扫描"按钮）；触发后 `pii` 通道填入 `word_data[key]["pii"]`，左右两栏高亮。
- **D-10:** 双栏对比预览保留 cp27 增量 DOM patch：左栏按 `data-key` 局部高亮 PII（红框 / 半透明填充 + entity_type 标签），右栏按 `data-key` 局部写入 partial mask 字符串；**不得**触发整页 `setHtml()`。
- **D-11:** 候选审阅列表（UX-01）= 现有 `_has_word_replacement_candidates` + 候选面板的 **Phase 7 极简版**；Phase 3 仅做"打开后自动列出 + 逐条确认"基础能力（与当前 word_replace_rules 形态一致），**不**做 Phase 7 的实体类型开关 / 文档级白名单 / 撤销栈。Phase 3 候选列表最低功能：按 entity_type 筛选 + 超过 50 条分页。
- **D-12:** Phase 3 增量不引入新 PyPI 依赖；`python-docx` 与 `mammoth` 现有依赖。**禁止**引入 `docx2txt` / `python-docx-redactor` / `aspose-words` 等新库。
- **D-13:** Phase 3 必须保持 79/79 现有测试基线（CLAUDE.md 列出的 10 个 unittest 模块）全部通过 + 增加至少 1 个新测试类（推荐 `test_word_pii_pipeline.py` 覆盖 Word 端到端 PII 流程）。Phase 3 完成后基线升级为 88/88 或更高。
- **D-14:** 79/79 基线门禁（OPS-07）通过完整命令 `python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_package_imports tests.unit.test_pdf_text_hit_dedup tests.unit.test_app_config tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety tests.unit.test_convergence -v` 验证。

#### 识别覆盖范围（D-15）

- **D-15:** Phase 3 复用 Phase 2 已落地的 9 类 PII（CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT）；**不**新增 entity_type。Phase 6 上下文型识别（CTX-01..05）不在 Phase 3 范围。

#### PIIHit 字段契约（D-16）

- **D-16:** 沿用 Phase 1 D-05 锁定的 7 字段 + Phase 2 D-09 复用的 2 字段：`entity_type` / `page_offset` / `page_length` / `page_rect` / `confidence_tier` / `source` / `mask_strategy` / `normalized` / `validator_passed`。
  - Word 适配时：`page_offset` / `page_length` 映射到 word_data[key]["text"] 字符串偏移；`page_rect` 在 Word 不可用（无 PDF 坐标），置占位 `(0, 0, 0, 0)`（Phase 3 显式约定）。
  - `source` = `"text"`（文字层）；Word 暂不做图片 OCR 路径（cp36+ 规划）。
  - `mask_strategy` = `mask_for_entity(entity_type, normalized)`（Phase 2 mask.py 已有）。

#### PIIEngine 输入契约（D-17）

- **D-17:** `PIIEngine.detect(unit: TextUnit, page=None)` 已是 format-agnostic。Word 适配时传 `TextUnit(page_index=key_index, text=word_data[key]["text"], source="text")`；`page` 参数为 `None`（Word 无 fitz.Page）。命中 `page_rect` 在引擎 `_resolve_page_rect` 路径需扩展 Word fallback（见 §Open Questions）。

#### 数据契约扩展（D-18 / D-19）

- **D-18:** `word_data[key]` 新增 `"pii": [PIIHit, ...]` 通道（与 `"ocr"` / `"manual"` 平级）。Phase 3 写读路径：
  - 写：`MainWindow._on_word_pii_page_result(key, hits)` 槽（新增）→ `self.word_data[key]["pii"] = hits`；
  - 读：`merge_word_matches_with_priority` 路径接收 `pii_matches` 第四参数（新增），与 `ocr_matches` / `manual_matches` 平级合并。
- **D-19:** `merge_word_matches_with_priority` 优先级扩展为：**`rule > pii > manual > ocr`**（D-18）。理由：PII 引擎是「自动识别」高置信度，rule 是「用户规则」更高；manual 框选覆盖 OCR 但不及自动识别；OCR 是「用户手动 OCR」最低。

### Claude's Discretion（Phase 3 自由区，研究推荐）

- **PII 高亮颜色（D-20）：** 与 PDF 沿用 `#D64545`（Phase 1 UI-SPEC 锁定深红色）；不引入新色。
- **PII 标签徽章（D-21）：** 左栏 PII rect 上方显示 entity_type 短码（`ID` / `PHONE` / `BANK` / `EMAIL` / `USCC` / `TAX` / `TAX15` / `VAT` / `ACCT`）；HTML 渲染走 `<span class="pii-tag">[ID]</span>` 嵌入 PII 命中位置。
- **`data-key` 与 `word_data` 同步策略（D-22）：** `_open_word_docx` 时一次性扫描 paragraphs + tables（`main.py:10796-10819`），按相同 key 命名（`paragraph_{idx}` / `table_{t}_cell_{r}_{c}`）建立对应；HTML 渲染时 `_add_data_key_attributes` 同步打 `data-key` 标记（`main.py:12236-12277`）。Phase 3 建议新增 `_scan_word_data_keys()` 工具函数，验证书面 key 集合 == 渲染后 DOM `data-key` 集合，失败时打 warn 并 reload 整页（cp27 退路）。
- **PII 写入 Word 真脱敏路径（D-23）：** 复用 `replace_matches_in_paragraph`（`main.py:965-1018`）+ 新增 `pii_matches` 入参；按 PIIHit 顺序合并 → `apply_range_to_runs` 段落 run-level 替换 → `mask_for_entity` 写 partial mask 字符串（沿用 Phase 2 MASK-01 partial mask 策略）。
- **Word 文档属性清除 helper（D-24）：** 新增 `privacyguard/word/clear_doc_props.py::clear_word_doc_props(doc, props={"core": [...], "app": [...]})`；调用位置紧邻 `new_doc.save(fname)`（与 Phase 2 `clear_pdf_metadata` 在 `doc.save` 前调对称）。
- **候选列表（UX-01 / UX-02 最低功能）（D-25）：** 沿用现有 `_has_word_replacement_candidates` + Phase 7 候选审阅 UI 的「极简版」= `QDialog` + `QListView` + 50 条分页 + entity_type 筛选下拉；不实现 Phase 7 的实体类型开关 / 文档级白名单 / 撤销栈。
- **Word 单元测试 fixture（D-26）：** `tests/fixtures/fake_word.py::build_fake_docx(...)` 用 `python-docx` 合成含 PII 的 docx（含 paragraphs + tables），避免依赖真实 Word 文件；遵循 OPS-05（合成数据）。

### Deferred Ideas (OUT OF SCOPE)

- Excel 文档支持（Phase 4 FMT-03 / FMT-04 / FMT-05）
- 独立图片文件支持（Phase 5 FMT-06 / SAFE-04 / SAFE-05）
- 上下文型 PII 识别（Phase 6 CTX-01..05）
- 候选审阅 UI 完整实现（Phase 7 UX-03 / UX-04 / UX-05 / UX-06）— Phase 3 仅做"打开后自动列出 + 逐条确认"基础能力
- 识别规则编辑 UI（Phase 8 UX-07）
- 审计报告（Phase 8 OPS-01）
- 跨平台打包验证（Phase 8 OPS-04）
- 真实文档准确率基线（Phase 8 OPS-06）
- main.py 单体拆分重构（STATE §Out of Scope 锁定）
- 切换到 `privacyguard.utils.config.py::ConfigManager`（STATE §Out of Scope 锁定）
- v38 UI 抛光（让位给本轮识别准确率痛点）
- Word 图片 OCR 路径（cp36+ 规划，独立项）

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FMT-02 | Word 处理路径接入识别引擎，识别候选在双栏对比预览中高亮 | §Standard Stack / §Architecture Patterns / §Code Examples — `word_data["pii"]` 通道 + `merge_word_matches_with_priority` 扩展 `pii_matches` + PII 双栏高亮 |
| UX-01 | 用户可在候选审阅列表中查看所有待确认识别项，并逐条决定是否脱敏 | §Standard Stack / §Architecture Patterns Pattern 4 — 候选列表 QDialog（Phase 7 极简版）+ 逐条 checkbox + entity_type 标签 |
| UX-02 | 候选列表支持按实体类型与来源筛选，且在候选数量较多时分页展示 | §Architecture Patterns Pattern 4 / §Common Pitfalls §1 — entity_type 筛选下拉 + 50 条分页 + 来源筛选（`ocr` / `manual` / `pii`） |

---

## Summary

Phase 3 把 Phase 1/2 已落地的 PII 引擎（9 类 entity：CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT）从 PDF 格式扩展到 Word 格式垂直切片。技术分五层：

(1) **Word Adapter 层** — `privacyguard/word/adapter.py::WordAdapter`（新）+ `privacyguard/word/redact.py::redact_word`（新）。`WordAdapter.collect_units(docx_path) -> Iterator[TextUnit]` 遍历 paragraphs + tables 转为 `TextUnit(page_index=key_index, text=block_text, source="text")`；`redact_word(docx_in, docx_out, mask_map)` 调 `replace_matches_in_paragraph` + 段落 + 表格 run-level 替换；Word 不可用 fitz.Page 坐标，page_rect 字段约定置占位 `(0, 0, 0, 0)`（D-16 / D-23）。

(2) **PII 通道** — `word_data[key]` 新增 `"pii": [PIIHit, ...]` 字段（D-04 / D-18）；`_open_word_docx` 完成 word_data 初始化后 **自动触发** `PIIEngine.detect`（无需用户点扫描按钮，D-09）；命中后通过 `pii_signal` 信号送回主线程；主线程 `_on_word_pii_page_result(key, hits)` 槽写入 `word_data[key]["pii"]` 并 emit 双栏高亮 patch 指令。

(3) **双栏高亮** — 左栏（原文预览）按 `data-key` 在 PII 命中位置局部插入 `<mark class="pii-highlight" data-entity-type="CN_ID_CARD">110101...</mark>`（D-21）；右栏（替换预览）按 `data-key` 局部写入 partial mask 字符串 `<mark class="pii-mask">110101********1234</mark>`。两栏 **不触发整页 setHtml**（D-10 / cp27）：通过 `web_view.page().runJavaScript("updateBlock('paragraph_5', innerHTML, '...')")` 局部 patch。

(4) **真脱敏写入** — `_save_word` 在 `replace_matches_in_paragraph` 路径增加 `pii_matches` 入参（D-23）；priority = `rule > pii > manual > ocr`（D-19）；按 PIIHit 顺序合并 → `apply_range_to_runs` 段落 run-level 替换 → `mask_for_entity` 写 partial mask 字符串。OCR / manual 路径**不动**（与 Phase 1/2 行为一致）。

(5) **Word 文档属性清除** — `privacyguard/word/clear_doc_props.py::clear_word_doc_props(doc)`（D-24）调 `python-docx` 的 `core_properties` / `app_properties` API 清除 D-08 锁定的字段（core: title / author / subject / keywords / last_modified_by / revision；app: company / manager）；调用位置紧邻 `new_doc.save(fname)`。验证：`doc.core_properties.title == ""` 等。

**最高风险** 是 Word run-boundary fragmentation（单条身份证号 `110101199003078811` 被 Word 切到 2-3 个 `<w:r>` run 内），导致 `para.text` 拼接后字符串匹配但 run-level 替换不完整。规避路径：`replace_matches_in_paragraph` 已通过 `apply_range_to_runs` 正确处理跨 run 区间替换（D-16 Phase 1 已生产验证），Phase 3 仅需传入 `pii_matches` 字典与 `ocr` / `manual` 同位置。**次高风险** 是 `data-key` 块 ID ↔ `word_data[key]` 字符串同步（D-22）：HTML 渲染时 `_add_data_key_attributes` 通过文本归一化比较，可能因 mammoth 转 HTML 时插入 `<strong>` / `<em>` 等标签导致 `element.get_text() != original_text` 失败 → 整个 block 没有 data-key → 局部 patch 失效。规避：`_add_data_key_regex_fallback`（`main.py:12283-12329`）作为后备；Phase 3 验证脚本应断言渲染后 DOM `data-key` 数 == word_data key 数。第三高风险是 Word 文档属性清除范围（D-08 锁定的 core / app 字段定义）；规避：本机 `python-docx` 验证 `doc.core_properties.title` / `doc.core_properties.author` / `doc.core_properties.subject` / `doc.core_properties.keywords` / `doc.core_properties.last_modified_by` / `doc.core_properties.revision` + `doc.app_properties.company` / `doc.app_properties.manager` 字段可置空字符串。第四高风险是 Phase 2 已有 9 类 entity hint 在 Phase 3 必须全部可见（`engine.detect` 暴露 CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_VAT_INVOICE / CN_TAXPAYER_ID_15 / CN_BANK_ACCOUNT）—— 本机验证 `engine.detect(text="13812345678 53010219200508011X")` 命中 ≥ 2 个 PIIHit 即可。第五高风险是 `_on_word_pii_page_result` 必须在主线程执行（Qt 信号槽约定），且与 `_word_data_lock = QMutex()`（`main.py:1153`）并发安全（cp30 教训扩展到 word_data）。

**Primary recommendation:** 严格沿用 Phase 1/2 的 PIIEngine + PIIHit 契约（D-16 / D-17），新增 `privacyguard/word/adapter.py::WordAdapter` + `privacyguard/word/redact.py::redact_word` + `privacyguard/word/clear_doc_props.py::clear_word_doc_props` 三个文件（全部放 `privacyguard/word/`，**不**进 main.py）。`word_data[key]["pii"]` 通道按 D-04 / D-18 扩展；`merge_word_matches_with_priority` 按 D-19 扩展 pii 优先级。`_open_word_docx` 自动触发 PII 检测（D-09）；双栏预览按 cp27 增量 DOM patch（D-10），不重渲染整页。`_save_word` 沿用 `replace_matches_in_paragraph` 路径扩 pii_matches 入参（D-23）。Word 文档属性清除走 `python-docx` core_properties / app_properties API（D-08 / D-24）。`data-key` 同步在 `_add_data_key_attributes` 既有路径上加兜底验证脚本（D-22），失败回退到 `_add_data_key_regex_fallback`。

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Word 文档 paragraphs + tables 单元化 | `privacyguard/word/adapter.py::WordAdapter.collect_units`（pure Python） | `python-docx` Document API | format-I/O 归 adapter；adapter 暴露 format-agnostic `TextUnit` 流给 PII 引擎 |
| PII 引擎 detect | `privacyguard/pii/engine.py::PIIEngine.detect`（既有 Phase 1/2） | — | format-agnostic；adapter 喂 `TextUnit(page_index=key, text=block_text, source="text")` |
| PII 通道在 word_data 写入 | `MainWindow._on_word_pii_page_result`（`main.py` 新增槽） | `word_data[key]["pii"] = hits`（D-04 / D-18） | 与 Phase 1 `_on_pii_page_result`（`main.py:11393-11406`）对称；走 QMutex 加锁 |
| 双栏 PII 高亮（左栏红框 / 右栏 partial mask） | `MainWindow._apply_word_pii_panel_updates`（新增） | `_word_*_panel_updates` 局部 DOM patch（cp27） | cp27 增量 patch 契约；不触发整页 setHtml（D-10） |
| PII 真脱敏写入 | `privacyguard/word/redact.py::redact_word`（新） | `main.py:replace_matches_in_paragraph` 既有 run-level 替换 | 真脱敏逻辑归 privacyguard/；main.py 只装配 |
| Word 文档属性清除 | `privacyguard/word/clear_doc_props.py::clear_word_doc_props`（新） | `python-docx` core_properties / app_properties | SAFE-03 类比 PDF 元数据清除（D-08 / D-24） |
| `merge_word_matches_with_priority` 优先级扩展 | `main.py:863-906`（既有模块级函数） | — | 与现有 rule / manual / ocr 三层平级加 pii 第四层（D-19） |
| 候选列表 UI（Phase 7 极简版） | `privacyguard/word/candidate_dialog.py::WordCandidateDialog`（新） | — | UX-01 / UX-02 最低功能（QDialog + QListView + 分页 + 筛选） |
| 候选 fixture | `tests/fixtures/fake_pii.py`（既有 Phase 1/2） + `tests/fixtures/fake_word.py::build_fake_docx`（新） | — | OPS-05 合成数据；fake_word 用 `python-docx` 构造 |
| `data-key` 同步验证 | `tests/unit/test_word_pii_pipeline.py::test_data_key_sync`（新） | — | 验证渲染后 DOM `data-key` 数 == word_data key 数（D-22） |
| PIIHit 字段契约 | `privacyguard/pii/hits.py::PIIHit`（既有 Phase 1 D-05） | — | D-16 字段锁；Word page_rect 置占位 (0, 0, 0, 0) |
| 懒加载纪律 | `privacyguard/word/__init__.py`（新） | `__getattr__` + `_LAZY_IMPORTS`（与 `privacyguard.pii.__init__.py:69-119` 对称） | OPS-03 强制；`import privacyguard.word` 不拉起 python-docx / mammoth |
| PyInstaller 跨平台打包 | `packaging/{windows,macos}/...` PyInstaller spec | cp30 教训 + Phase 1/2 沿用 | `datas` 段追加 `privacyguard/word/data/`（如需）+ `hiddenimports` 追加 `privacyguard.word.adapter` 等新模块 |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python-docx` | 现有（项目已固定） | Word 文档读 / 写（paragraphs + tables + core_properties / app_properties） | 唯一能 round-trip 保留 docx 格式的开源库；Phase 3 沿用 |
| `mammoth` | 现有（项目已固定） | DOCX → HTML 转换（双栏预览） | mammoth 输出干净 HTML，与 BeautifulSoup + JavaScript 局部 patch 配合最稳定 |
| `BeautifulSoup` (bs4) | 现有 | HTML 解析（data-key 注入 / 局部 patch） | 既有 `_add_data_key_attributes`（`main.py:12236-12277`）沿用 |
| `privacyguard.pii.engine.PIIEngine` | Phase 1 | 9 类 PII 识别（CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT） | Phase 1/2 已生产验证；Phase 3 复用不扩展 |
| `privacyguard.pii.hits.PIIHit` | Phase 1 D-05 | PII 命中数据契约（7 + 2 字段） | D-16 字段锁；page_rect 在 Word 置占位 (0, 0, 0, 0) |
| `privacyguard.pii.mask.mask_for_entity` | Phase 2 | 9 类 partial mask 字符串 | 既有 mask.py 沿用 |
| `re` (Python stdlib) | 3.12 | `data-key` regex fallback（`main.py:12283-12329`） | 既有；Phase 3 沿用 |
| `dataclasses` (stdlib) | 3.12 | `PIIHit` 跨线程 `asdict()` 序列化 | Phase 1 沿用 |
| `QMutex` / `QMutexLocker` (PyQt6) | 现有 | `word_data` 线程安全（`main.py:1153` + `main.py:11602-11616`） | cp30 教训；Phase 3 worker 写 word_data 必须加锁 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `privacyguard.pii.validators.{id_card,phone_segment,uscc,bank_card,email,vat_invoice,taxpayer_id,bank_account}` | Phase 1/2 | 9 类 PII 校验 | `engine.detect` 内部调用；Phase 3 不直接调 |
| `tests.fixtures.fake_pii.{fake_id_card,fake_phone,fake_bank_card,fake_email,fake_uscc,...}` | Phase 1/2 | 合成 PII 字符串 | `tests/fixtures/fake_word.py` 内构造含 PII 的 docx |
| `privacyguard.utils.security.resource_path` | 现有 | 词典 / 资源路径 | Phase 3 无新数据文件，沿用 |
| `main.py:replace_matches_in_paragraph` (line 965) | 现有 | run-level 替换 | D-23 复用；新增 `pii_matches` 入参 |
| `main.py:merge_word_matches_with_priority` (line 863) | 现有 | 优先级合并 | D-19 扩展 `pii_matches` 第四参数；优先级 `rule > pii > manual > ocr` |
| `main.py:apply_range_to_runs` (line 909) | 现有 | 跨 run 区间替换 | D-16 跨 run 边界处理 |
| `main.py:_add_data_key_attributes` (line 12236) | 现有 | HTML 渲染时打 data-key | D-22 同步验证 |
| `main.py:_add_data_key_regex_fallback` (line 12283) | 现有 | data-key 同步后备 | D-22 失败回退 |
| `main.py:_word_data_lock` (line 1153) | 现有 | word_data 线程安全 | D-09 worker 写 pii 通道加锁 |
| `main.py:_save_word` (line 12699) | 现有 | Word 保存 | D-23 调 `redact_word` + `clear_word_doc_props` |
| `main.py:_open_word_docx` (line 10777) | 现有 | Word 打开 | D-09 打开后自动触发 PII 检测 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `python-docx` 段落 + 表格遍历 | `docx2txt`（仅文本） | docx2txt 不保留段落结构 / run 边界 / core_properties；不可写回 |
| `python-docx` core_properties API | 直接 `xml.etree` 改 `docProps/core.xml` | python-docx API 官方 + 自动处理 XML namespace；xml.etree 易遗漏字段 |
| `mammoth` DOCX→HTML | `aspose-words`（商业） | aspose-words 需要 license + 增加 ~30MB 打包体积 |
| 局部 DOM patch（cp27） | 整页 `setHtml()` | 整页重渲染会丢失滚动位置 / 选中状态 / 缩放；cp27 局部 patch 保留交互 |
| Phase 7 极简候选列表 | 完整 Phase 7 候选审阅 UI | Phase 7 实体类型开关 / 文档级白名单 / 撤销栈不在 Phase 3 范围 |
| `mask_for_entity` 复用 Phase 2 | 重写 Word 专用 mask 逻辑 | v37.7.6 收敛 + mask 策略跨格式一致；Phase 3 复用 |
| `replace_matches_in_paragraph` 复用 main.py | 新写 `privacyguard/word/redact.py` 全套替换 | D-23 复用 `replace_matches_in_paragraph`；redact_word 仅作 wrapper 入口（接受 mask_map + 调用既有 run-level 替换） |
| QMutex (`_word_data_lock`) 加锁 | threading.Lock | `_word_data_lock` 是 Qt 线程安全惯例；沿用避免 race |
| `python-docx` `app_properties.company` 直接置空 | 单独写 `docProps/app.xml` | python-docx `app_properties` API 在 v0.8.10+ 稳定；本机验证 |

**Installation:**
无新增 PyPI 依赖。`python-docx` 与 `mammoth` 现有项目已固定版本。

**Version verification (本机 2026-08-12 验证):**
```bash
python3 -c "import docx; print(docx.__version__)"               # 实测 python-docx 版本
python3 -c "import mammoth; print(mammoth.__version__)"         # 实测 mammoth 版本
python3 -c "from docx import Document; d = Document(); d.core_properties.title = ''; d.core_properties.author = ''; print('OK')"
python3 -c "from privacyguard.pii.engine import PIIEngine; e = PIIEngine(); from privacyguard.pii.hits import TextUnit; hits = e.detect(TextUnit(page_index=0, text='13812345678 53010219200508011X zhangsan@qq.com', source='text')); print(len(hits), [h.entity_type for h in hits])"
```

### Phase 3 候选 `entity_type` 字符串锁（D-15 锁定）

| entity_type | 中文标签 | HTML 短码 | partial_mask 输出（D-23 复用 Phase 2 mask.py） |
|-------------|---------|-----------|------------------------------------------------|
| `CN_ID_CARD` | 身份证 | `ID` | `110101********1234` |
| `CN_PHONE` | 手机 | `PHONE` | `138****5678` |
| `CN_BANK_CARD` | 银行卡 | `BANK` | `6222 **** **** 1234` |
| `CN_EMAIL` | 邮箱 | `EMAIL` | `z****@qq.com` |
| `CN_USCC` | 统一社会信用代码 | `USCC` | `911100********L` |
| `CN_TAXPAYER_ID` | 纳税人识别号（18 位） | `TAX` | `911100********L`（与 USCC 同） |
| `CN_TAXPAYER_ID_15` | 纳税人识别号（15 位） | `TAX15` | `110101*****001` |
| `CN_VAT_INVOICE` | 增值税发票号 | `VAT` | `12******78`（8 位）/ `23**********78`（20 位） |
| `CN_BANK_ACCOUNT` | 银行账号 | `ACCT` | `6222********0000` |

### Word 文档属性清除范围（D-08 / D-24 锁定）

| 范围 | 字段 | python-docx API | 清除值 |
|------|------|-----------------|--------|
| core.xml | `dc:title` | `doc.core_properties.title` | `""` |
| core.xml | `dc:creator` | `doc.core_properties.author` | `""` |
| core.xml | `dc:subject` | `doc.core_properties.subject` | `""` |
| core.xml | `cp:keywords` | `doc.core_properties.keywords` | `""` |
| core.xml | `cp:lastModifiedBy` | `doc.core_properties.last_modified_by` | `""` |
| core.xml | `cp:revision` | `doc.core_properties.revision` | `1`（数字） |
| app.xml | Application | 不可写（python-docx 不暴露） | 保留 |
| app.xml | Company | `doc.core_properties.comments`（部分版本） 或 `doc.app_properties` | `""` |
| app.xml | Manager | `doc.app_properties` | `""` |
| app.xml | Template | `doc.app_properties` | 保留 |
| app.xml | TotalTime | `doc.app_properties` | `0` |

**本机验证（2026-08-12 待补）**：
- `python3 -c "from docx import Document; d = Document(); print(d.core_properties.title, d.core_properties.author, d.core_properties.subject, d.core_properties.keywords, d.core_properties.last_modified_by, d.core_properties.revision)"`
- 设置后：`d.core_properties.title = ''`; `d.save('/tmp/x.docx')`; `d2 = Document('/tmp/x.docx')`; `print(d2.core_properties.title == "")`

### `data-key` 块 ID ↔ `word_data` 同步契约（D-22 锁定）

| word_data key | HTML 元素 | mammoth 输出后预期 |
|---------------|-----------|------------------|
| `paragraph_{idx}` | `<p data-key="paragraph_{idx}">` 或 fallback `<span data-key>` | mammoth 对每个段落输出 `<p>`，inline 元素 `<strong>` / `<em>` 嵌入 |
| `table_{t}_cell_{r}_{c}` | `<td data-key="table_{t}_cell_{r}_{c}">` | mammoth 对每个 cell 输出 `<td>` |

**关键约束**：
- `_add_data_key_attributes`（`main.py:12236-12277`）通过 `element.get_text()` 归一化匹配；可能因 `<strong>` 拆字失败 → 触发 `_add_data_key_regex_fallback`（`main.py:12283-12329`）
- Phase 3 验证脚本（`tests/unit/test_word_pii_pipeline.py::test_data_key_sync`）断言渲染后 `soup.find_all(attrs={"data-key": True})` 数 == `len(word_data)`，失败打 warn + 整页 reload

---

## Package Legitimacy Audit

> Phase 3 不新增 PyPI 依赖（沿用 `python-docx` + `mammoth` + PyQt6 + bs4）。所有逻辑在 `privacyguard/word/` 子包内实现（adapter + redact + clear_doc_props + candidate_dialog）。

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| 现有 `python-docx` | PyPI | 稳定 | n/a | github.com/python-openxml/python-docx | OK | Approved（项目已固定） |
| 现有 `mammoth` | PyPI | 稳定 | n/a | github.com/mwilliamson/python-mammoth | OK | Approved（项目已固定） |
| 现有 `beautifulsoup4` | PyPI | 稳定 | n/a | github.com/wention/BeautifulSoup | OK | Approved（项目已固定） |
| 现有 `PyQt6` | PyPI | 稳定 | n/a | riverbankcomputing.com | OK | Approved（项目已固定） |

**新增 0 个 PyPI 依赖**（D-12 锁定）。

**Packages removed due to [SLOP] verdict:** 无
**Packages flagged as suspicious [SUS]:** 无

---

## Architecture Patterns

### System Architecture Diagram

```
                              ┌────────────────────────────────────────────┐
                              │  PyQt6 Main Thread (`main.py` ~12.9k LOC)  │
                              │                                            │
  drag/drop / Open menu       │   ▼                                        │
  ────────────────── ──      │  ┌─────────────────────────────────────┐  │
       │                     │  │  MainWindow (`main.py:5149`)         │  │
       ▼                     │  │  ├ self.word_data[key] = {            │  │
  ┌──────────┐               │  │  │     'text':   <block text>,        │  │
  │  File    │               │  │  │     'ocr':    [...],               │  │
  │  open    │────open_word─▶│  │  │     'manual': [...],               │  │
  └──────────┘               │  │  │     'pii':    [PIIHit, ...]    ◀────┼── D-04/D-18 (new channel)
       │                     │  │  │   }                                 │  │
       │                     │  │  ├ self.word_replace_rules             │  │
       │                     │  │  ├ self._word_data_lock = QMutex()      │  │
       │                     │  │  └ self.active_rules / replacement     │  │
       │                     │  └──────────┬──────────────────────────┘  │
       │                     │             │ auto-trigger (D-09)           │
       │                     │             ▼                                │
       │                     │  ┌─────────────────────────────────────┐  │
       │                     │  │  WordPIIWorker (QThread) (NEW)      │  │
       │                     │  │  privacyguard/word/worker.py (NEW)   │  │
       │                     │  │  ──────────────────────────────────  │  │
       │                     │  │  for key, text in word_data.items(): │  │
       │                     │  │    unit = TextUnit(                 │  │
       │                     │  │      page_index=key_index,          │  │
       │                     │  │      text=word_data[key]['text'],   │  │
       │                     │  │      source='text')                 │  │
       │                     │  │    pii_hits = engine.detect(         │  │
       │                     │  │      unit, page=None)               │  │
       │                     │  │    self.pii_signal.emit(             │  │
       │                     │  │      key, [dataclasses.asdict(h)     │  │
       │                     │  │        for h in pii_hits])           │  │
       │                     │  └──────────────┬───────────────────────┘  │
       │                     └─────────────────┼───────────────────────────┘
       │                                       │
       │                                       ▼ pii_signal
       │                     ┌─────────────────────────────────────────┐
       │                     │  _on_word_pii_page_result(key, hits)    │  ◀── MainWindow slot (NEW, D-18)
       │                     │  with QMutexLocker(self._word_data_lock):│
       │                     │    self.word_data[key]['pii'] = hits    │  ◀── write channel
       │                     │    self._apply_word_pii_panel_updates(  │  ◀── trigger cp27 patch (D-10)
       │                     │      key, hits)                         │
       │                     └─────────────────┬───────────────────────┘
       │                                       │ runJavaScript
       │                                       ▼
       │                     ┌─────────────────────────────────────────┐
       │                     │  QWebEngineView (left + right panel)     │
       │                     │  window.__updateBlock(                   │  ◀── cp27 incremental DOM patch
       │                     │    'paragraph_5',                        │
       │                     │    '<mark class="pii-highlight">[ID]</mark>     │
       │                     │     110101199003078811                   │
       │                     │     </mark>'                             │
       │                     │  )                                       │
       │                     │  — 不触发整页 setHtml (cp27 锁)          │
       │                     └─────────────────────────────────────────┘
       │
       │     ── save path ─────────────────────────────────────────────────
       ▼
  _save_word(fname) (D-23)
       │
       │   for each key in word_data:
       │     merged = merge_word_matches_with_priority(
       │       text, word_replace_rules, replacement,
       │       manual_matches=data['manual'],
       │       ocr_matches=data['ocr'],
       │       pii_matches=data['pii'])    ◀── D-19 pii 第四参数
       │
       │   redact_word(doc, key, merged)     ◀── privacyguard/word/redact.py
       │     replace_matches_in_paragraph(   ◀── main.py:965 (既有)
       │       para, merged, text_offset=0,
       │       fallback_replacement_text=mask)
       │     apply_range_to_runs(para, start, end, mask)  ◀── main.py:909 (既有)
       │
       │   clear_word_doc_props(doc)         ◀── privacyguard/word/clear_doc_props.py (D-24)
       │     doc.core_properties.title = ""
       │     doc.core_properties.author = ""
       │     doc.core_properties.subject = ""
       │     doc.core_properties.keywords = ""
       │     doc.core_properties.last_modified_by = ""
       │     doc.core_properties.revision = 1
       │
       ▼
  new_doc.save(fname, ...)
  ◀── FMT-02 真脱敏 + D-08 文档属性清除
```

### Recommended Project Structure

```
privacyguard/word/                            # ◀── NEW (Phase 3)
├── __init__.py                              # 懒加载 _LAZY_IMPORTS + re-export (D-06)
├── adapter.py                               # ◀── NEW: WordAdapter.collect_units / collect_key_index
├── redact.py                                # ◀── NEW: redact_word() 段落 + 表格 run-level 替换 wrapper
├── clear_doc_props.py                       # ◀── NEW: clear_word_doc_props(doc) (D-24)
├── candidate_dialog.py                      # ◀── NEW: WordCandidateDialog QDialog (UX-01/02 极简版)
├── data/                                    # (预留：Phase 8 用户词典可能用，Phase 3 暂空)
│   └── (空)
└── worker.py                                # ◀── NEW: WordPIIWorker QThread (D-09 自动触发)

main.py (modify, ~5 sites)
├── Site 1: _open_word_docx (line 10777)      # ◀── MODIFY: 打开后启动 WordPIIWorker
├── Site 2: _on_word_pii_page_result (NEW)   # ◀── ADD: pii_signal 接收槽 (D-18)
├── Site 3: merge_word_matches_with_priority (line 863)
│                                             # ◀── MODIFY: 新增 pii_matches 第四参数 (D-19)
├── Site 4: _save_word (line 12699)           # ◀── MODIFY: 调 redact_word + clear_word_doc_props
├── Site 5: _build_word_*_panel_updates       # ◀── MODIFY: 把 data['pii'] 纳入合并路径
└── Site 6: _add_data_key_attributes (line 12236)
                                              # ◀── MODIFY: 同步验证 (D-22)

tests/
├── fixtures/fake_word.py                    # ◀── NEW: build_fake_docx() 合成含 PII 的 docx (D-26)
├── unit/test_word_pii_pipeline.py           # ◀── NEW: Word 端到端 PII 流程测试
│   ├── TestWordAdapterCollectUnits
│   ├── TestWordPIIAutoTrigger
│   ├── TestWordPIIPanelHighlights
│   ├── TestWordRedactRoundTrip              ◀── D-23 + 13 类 PII partial mask 写入
│   ├── TestWordDocumentPropertiesCleared    ◀── D-08 / D-24
│   ├── TestWordDataKeySync                  ◀── D-22
│   ├── TestWordMergePriorityRulePiManualOcr ◀── D-19
│   └── TestWordCandidateDialog              ◀── UX-01/02
└── ... (其他基线 79/79 测试不动)

privacyguard/__init__.py                      # ◀── MODIFY: _LAZY_IMPORTS 追加 WordAdapter / redact_word / clear_word_doc_props
```

### Pattern 1: WordAdapter.collect_units（D-04 / D-17 / D-22）

**What:** `WordAdapter.collect_units(docx_path) -> List[TextUnit]` 遍历 paragraphs + tables 转为 `TextUnit(page_index=key_index, text=block_text, source="text")`。`collect_key_index() -> Dict[int, str]` 维护 key_index ↔ word_data key 的双向映射（D-22）。

**When to use:** `_open_word_docx` 后自动启动 `WordPIIWorker`，worker 内部调 `WordAdapter.collect_units` 喂给 `engine.detect`。

**Example:**
```python
# privacyguard/word/adapter.py
from typing import Dict, Iterator, List, Tuple
from docx import Document
from privacyguard.pii.hits import TextUnit


class WordAdapter:
    """Phase 3: Word 文档 → PII 引擎可消费 TextUnit 流的格式适配器（D-04 / D-17）。

    沿用 Phase 1/2 PII 引擎的 format-agnostic 接口；
    Word 不可用 fitz.Page 坐标，page_rect 字段在 PIIHit 中置占位 (0, 0, 0, 0)。
    """

    @staticmethod
    def collect_units(docx_path: str) -> Tuple[List[TextUnit], Dict[int, str]]:
        """遍历 docx 的 paragraphs + tables，产出 TextUnit + key 索引。

        Args:
            docx_path: .docx 文件路径

        Returns:
            (units, key_index):
                units: List[TextUnit] 顺序与 word_data 字典迭代顺序一致
                key_index: Dict[TextUnit.page_index → word_data key 字符串]
                    用于 PII 命中后回写 word_data[key]['pii']
        """
        doc = Document(docx_path)
        units: List[TextUnit] = []
        key_index: Dict[int, str] = {}
        idx = 0

        # 段落（与 main.py:10796-10804 同步）
        for para_idx, para in enumerate(doc.paragraphs):
            key = f"paragraph_{para_idx}"
            text = para.text or ""
            if not text.strip():
                continue
            units.append(TextUnit(page_index=idx, text=text, source="text"))
            key_index[idx] = key
            idx += 1

        # 表格（与 main.py:10807-10819 同步）
        for table_idx, table in enumerate(doc.tables):
            for row_idx, row in enumerate(table.rows):
                for cell_idx, cell in enumerate(row.cells):
                    key = f"table_{table_idx}_cell_{row_idx}_{cell_idx}"
                    text = cell.text or ""
                    if not text.strip():
                        continue
                    units.append(TextUnit(page_index=idx, text=text, source="text"))
                    key_index[idx] = key
                    idx += 1

        return units, key_index


__all__ = ['WordAdapter']
```

### Pattern 2: redact_word（D-23 真脱敏 wrapper）

**What:** `redact_word(doc, key, merged_matches)` 沿用 main.py:965 `replace_matches_in_paragraph` run-level 替换路径，不重写替换逻辑（D-23 + D-05 收敛原则）。

**When to use:** `_save_word` 中 PII / ocr / manual 合并后调。

**Example:**
```python
# privacyguard/word/redact.py
from typing import List
from docx import Document
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from privacyguard.pii.hits import PIIHit


# === D-23 复用 main.py 既有 run-level 替换 ===
# 实际替换在 main.py 模块级函数中实现（replace_matches_in_paragraph / apply_range_to_runs）。
# Phase 3 redact_word 仅作 wrapper：遍历 paragraphs + tables，按 key 找到对应 block，
# 调既有 replace_matches_in_paragraph。

# 为避免 main.py 内部函数直接被 privacyguard 引用，Phase 3 在 redact_word 内
# 用 importlib 在 lazy 路径上引 main.py 的符号（cp30 教训：避免隐私 import 触发
# 整个 main.py 12.9k LOC 加载）。


def _resolve_run_level_replacer():
    """懒加载 main.py:replace_matches_in_paragraph；避免 privacyguard.word 导入触发 main.py 加载。"""
    from main import replace_matches_in_paragraph
    return replace_matches_in_paragraph


def redact_paragraph(para, matches, fallback_replacement_text="[已脱敏]"):
    """单段落 run-level 替换（沿用 main.py:replace_matches_in_paragraph）。"""
    replacer = _resolve_run_level_replacer()
    replacer(para, matches, text_offset=0,
             fallback_replacement_text=fallback_replacement_text)


def redact_word(doc: "_Document", key: str, merged_matches: List[dict],
                fallback_replacement_text: str = "[已脱敏]"):
    """Phase 3: 按 key 找到 doc 内对应段落 / 表格 cell，调 run-level 替换（D-23）。

    Args:
        doc: python-docx Document
        key: word_data 的 key（"paragraph_{idx}" 或 "table_{t}_cell_{r}_{c}"）
        merged_matches: merge_word_matches_with_priority 输出的合并匹配列表
        fallback_replacement_text: mask 字符串 fallback
    """
    if not merged_matches:
        return
    if key.startswith("paragraph_"):
        para_idx = int(key.split("_", 1)[1])
        if para_idx >= len(doc.paragraphs):
            return
        redact_paragraph(doc.paragraphs[para_idx], merged_matches, fallback_replacement_text)
    elif key.startswith("table_"):
        # table_t_cell_r_c
        parts = key.split("_")
        if len(parts) != 5:
            return
        t, r, c = int(parts[1]), int(parts[3]), int(parts[4])
        if t >= len(doc.tables):
            return
        table = doc.tables[t]
        if r >= len(table.rows):
            return
        row = table.rows[r]
        if c >= len(row.cells):
            return
        cell = row.cells[c]
        # cell.paragraphs 多段（与 main.py:12753-12766 同步：para_offset 累加）
        para_offset = 0
        for idx, para in enumerate(cell.paragraphs):
            original_para_len = len("".join(run.text for run in para.runs))
            from main import replace_matches_in_paragraph
            replace_matches_in_paragraph(para, merged_matches,
                                         text_offset=para_offset,
                                         fallback_replacement_text=fallback_replacement_text)
            para_offset += original_para_len
            if idx < len(cell.paragraphs) - 1:
                para_offset += 1  # python-docx cell.text 用换行拼接


__all__ = ['redact_word', 'redact_paragraph']
```

### Pattern 3: clear_word_doc_props（D-08 / D-24）

**What:** 调 `python-docx` 的 `core_properties` / `app_properties` API 清除 D-08 锁定的字段（core: title / author / subject / keywords / last_modified_by / revision；app: company / manager）。调用位置紧邻 `new_doc.save(fname)`（与 Phase 2 `clear_pdf_metadata` 在 `doc.save` 前调对称）。

**Example:**
```python
# privacyguard/word/clear_doc_props.py
"""Phase 3: Word 文档属性清除（D-08 / D-24）。

与 Phase 2 SAFE-03 PDF 元数据清除语义对齐：
- Phase 2: 5 字段（title / author / subject / producer / creator）置空字符串
- Phase 3: 6 字段 core + 1 字段 app，置空字符串 / 默认值

调用位置：MainWindow._save_word 中 new_doc.save(fname) 前调一次。
"""
from typing import Final

from docx import Document


# D-08 锁定的 Word 文档属性清除范围
CORE_PROPS_TO_CLEAR: Final = (
    "title", "author", "subject", "keywords",
    "last_modified_by",
)
APP_PROPS_TO_CLEAR: Final = (
    "company", "manager",
)


def clear_word_doc_props(doc) -> None:
    """Phase 3: Word 文档属性清除（D-08 / D-24）。

    仅清 6 个 core 字段 + 2 个 app 字段（D-08 锁定）；
    CreationDate / ModDate / Template / TotalTime 等保留；
    所有清空字段置空字符串，不写 "Anonymous" / "Redacted" 等占位字符串。

    Args:
        doc: python-docx Document 对象（已加载或新建）
    """
    core = doc.core_properties
    for prop_name in CORE_PROPS_TO_CLEAR:
        if prop_name == "title":
            core.title = ""
        elif prop_name == "author":
            core.author = ""
        elif prop_name == "subject":
            core.subject = ""
        elif prop_name == "keywords":
            core.keywords = ""
        elif prop_name == "last_modified_by":
            core.last_modified_by = ""
    # revision 是整数，置 1（默认值）；不能置空字符串
    if hasattr(core, "revision"):
        core.revision = 1

    # app_properties 视 python-docx 版本而定（v0.8.10+ 稳定）
    if hasattr(doc, "app_properties") and doc.app_properties is not None:
        app = doc.app_properties
        for prop_name in APP_PROPS_TO_CLEAR:
            if hasattr(app, prop_name):
                try:
                    setattr(app, prop_name, "")
                except (AttributeError, ValueError):
                    # 部分版本 app_properties 只读
                    pass


__all__ = ['clear_word_doc_props', 'CORE_PROPS_TO_CLEAR', 'APP_PROPS_TO_CLEAR']
```

### Pattern 4: WordCandidateDialog（UX-01 / UX-02 极简版）

**What:** `QDialog` + `QListView` 列出 word_data 内全部 PII 命中（来自 `word_data[key]["pii"]`），entity_type 筛选下拉 + 50 条分页 + 来源（ocr / manual / pii）筛选 + 逐条确认 checkbox。

**When to use:** 工具栏 / 主菜单触发「候选审阅」入口时打开。

**Example:**
```python
# privacyguard/word/candidate_dialog.py
"""Phase 3: Word 候选审阅对话框（UX-01 / UX-02 极简版）。

Phase 3 仅做：
- 列出 word_data 内全部 PII 命中（来自 pii 通道）
- entity_type 筛选下拉
- 50 条分页
- 来源筛选（ocr / manual / pii 三选一 + 全部）
- 逐条确认 checkbox（与 Phase 7 撤销栈 / 文档级白名单无关）

完整 Phase 7 候选审阅 UI（UX-03 / UX-04 / UX-05 / UX-06）走独立 phase。
"""
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from privacyguard.pii.hits import PIIHit


ENTITY_TYPE_LABEL = {
    "CN_ID_CARD": "身份证",
    "CN_PHONE": "手机",
    "CN_BANK_CARD": "银行卡",
    "CN_EMAIL": "邮箱",
    "CN_USCC": "统一社会信用代码",
    "CN_TAXPAYER_ID": "纳税人识别号（18 位）",
    "CN_TAXPAYER_ID_15": "纳税人识别号（15 位）",
    "CN_VAT_INVOICE": "增值税发票号",
    "CN_BANK_ACCOUNT": "银行账号",
}


class WordCandidateDialog(QDialog):
    """Phase 3: Word 候选审阅极简版（D-25 / UX-01 / UX-02）。"""

    PAGE_SIZE = 50  # 50 条分页

    def __init__(self, word_data: dict, parent=None):
        super().__init__(parent)
        self.word_data = word_data or {}
        self._all_hits: List[dict] = []  # [{key, hit, source}, ...]
        self._page = 0
        self._build_hit_list()
        self.setWindowTitle("Word 候选审阅")
        self.resize(700, 600)
        self._init_ui()

    def _build_hit_list(self):
        """从 word_data 三个通道收集全部 hit（pII + ocr + manual）。"""
        for key, data in self.word_data.items():
            for hit in data.get("pii", []) or []:
                self._all_hits.append({"key": key, "hit": hit, "source": "pii"})
            for hit in data.get("ocr", []) or []:
                self._all_hits.append({"key": key, "hit": hit, "source": "ocr"})
            for hit in data.get("manual", []) or []:
                self._all_hits.append({"key": key, "hit": hit, "source": "manual"})

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 顶部工具栏：entity_type 筛选 + 来源筛选
        top = QHBoxLayout()
        top.addWidget(QLabel("实体类型:"))
        self.entity_filter = QComboBox()
        self.entity_filter.addItem("全部", "")
        for et, label in ENTITY_TYPE_LABEL.items():
            self.entity_filter.addItem(label, et)
        self.entity_filter.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.entity_filter)

        top.addWidget(QLabel("来源:"))
        self.source_filter = QComboBox()
        self.source_filter.addItem("全部", "")
        for src in ("pii", "ocr", "manual"):
            self.source_filter.addItem(src, src)
        self.source_filter.currentIndexChanged.connect(self._refresh)
        top.addWidget(self.source_filter)
        top.addStretch(1)
        layout.addLayout(top)

        # 候选列表
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        # 分页
        bottom = QHBoxLayout()
        self.btn_prev = QPushButton("上一页")
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next = QPushButton("下一页")
        self.btn_next.clicked.connect(self._next_page)
        self.page_label = QLabel("0/0")
        bottom.addWidget(self.btn_prev)
        bottom.addWidget(self.btn_next)
        bottom.addWidget(self.page_label)
        bottom.addStretch(1)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

        self._refresh()

    def _filtered_hits(self) -> List[dict]:
        et = self.entity_filter.currentData()
        src = self.source_filter.currentData()
        out = []
        for entry in self._all_hits:
            if et and entry["hit"].entity_type != et:
                continue
            if src and entry["source"] != src:
                continue
            out.append(entry)
        return out

    def _refresh(self):
        self.list_widget.clear()
        filtered = self._filtered_hits()
        total = len(filtered)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self._page >= total_pages:
            self._page = total_pages - 1
        if self._page < 0:
            self._page = 0
        start = self._page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, total)
        for entry in filtered[start:end]:
            hit = entry["hit"]
            label = (
                f"[{entry['source']}] "
                f"{ENTITY_TYPE_LABEL.get(hit.entity_type, hit.entity_type)}: "
                f"{hit.normalized[:30]}{'...' if len(hit.normalized) > 30 else ''} "
                f"@ {entry['key']}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(item)
        self.page_label.setText(f"第 {self._page + 1} / {total_pages} 页（共 {total} 条）")
        self.btn_prev.setEnabled(self._page > 0)
        self.btn_next.setEnabled(self._page < total_pages - 1)

    def _prev_page(self):
        self._page -= 1
        self._refresh()

    def _next_page(self):
        self._page += 1
        self._refresh()


__all__ = ['WordCandidateDialog', 'ENTITY_TYPE_LABEL']
```

### Anti-Patterns to Avoid

- **`main.py` 写 `def redact_word_docx`:** 违反 v37.7.6 收敛原则（D-05）；必须在 `privacyguard/word/redact.py::redact_word`。
- **`page_rect` 在 Word 适配时强求 fitz.Rect 坐标:** Word 无 PDF 坐标；D-16 锁定置占位 `(0, 0, 0, 0)`；试图通过 mammoth 坐标转换是过度工程。
- **整页 `setHtml()` 触发重渲染:** 违反 cp27 增量 DOM patch 契约（D-10 / D-07）；必须走 `web_view.page().runJavaScript(...)` 局部 patch。
- **`_add_data_key_attributes` 改写为 mammoth 内嵌属性:** mammoth 输出 HTML 不带 data-key；必须在 BeautifulSoup 阶段注入；改 mammoth 配置会破坏 `_add_data_key_regex_fallback`（`main.py:12283-12329`）后备。
- **`PIIEngine.detect` 在 main.py 直接调:** 违反 v37.7.6 收敛原则 + 破坏 OPS-03 懒加载（cp30 教训）；必须由 `WordPIIWorker`（QThread）调。
- **`word_data[key]["pii"]` 用 list 套 dict 而非直接 PIIHit 列表:** 与 `ocr` / `manual` 既有契约不一致；保持 `[PIIHit, ...]` 列表形式。
- **`core_properties.title = None`:** python-docx 期望空字符串 `""`；置 `None` 会触发 `AttributeError`；D-24 锁定 `""`。
- **`page.search_for` 在 Word 适配时传 `page=None` 不防御:** engine 内 `_resolve_page_rect` 在 page=None 时应直接返回占位 `(0, 0, 0, 0)`（现有 fallback 形态，**不**触发搜索）。
- **候选列表（`WordCandidateDialog`）含 Phase 7 实体类型开关 / 撤销栈:** Phase 3 范围外（D-25）；扩展属于 Phase 7。
- **`tests/fixtures/fake_word.py` 用真实 Word 文件:** 违反 OPS-05 合成数据 + 增加仓库大小；用 `python-docx` 合成。

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Word 文档段落 + 表格遍历 | 自实现 `lxml` 解析 `word/document.xml` | `python-docx` Document API | python-docx 处理 OXML namespace + run 边界 + tables 自动；自实现易遗漏 OXML 细节 |
| Word run-level 跨 run 区间替换 | 自实现段落 cursor 跟踪 | `main.py:replace_matches_in_paragraph` + `apply_range_to_runs`（`main.py:909-1018`） | Phase 1 已生产验证，跨 run 边界处理正确；D-23 复用 |
| Word 文档属性清除 | 自实现 `lxml` 改 `docProps/core.xml` + `docProps/app.xml` | `privacyguard/word/clear_doc_props.py::clear_word_doc_props` | python-docx core_properties / app_properties API 自动处理 XML namespace 与关系文件；自实现易遗漏 `cp:lastModifiedBy` 字段 |
| PII 引擎 detect | 自写 Word 专用 PII 识别 | `privacyguard.pii.engine.PIIEngine.detect`（Phase 1/2） | D-02 锁定；Phase 3 复用 format-agnostic 入口 |
| `word_data[key]["pii"]` 通道 | 自定义新字典 `self.pii_hits` | `word_data[key]["pii"] = [PIIHit, ...]`（D-18） | 违反 v37.7.6 收敛原则（STATE §Decisions 锁定） |
| `data-key` 注入 | 自写 mammoth 后处理插件 | `_add_data_key_attributes`（`main.py:12236-12277`） + `_add_data_key_regex_fallback`（`main.py:12283-12329`） | cp27 已生产验证；Phase 3 沿用 |
| 双栏高亮（cp27 局部 patch） | 整页 `setHtml()` 重渲染 | `web_view.page().runJavaScript("updateBlock('paragraph_5', innerHTML)")` | cp27 锁定；整页重渲染丢失滚动 / 选中状态 / 缩放 |
| 候选列表（极简版） | 直接在 main.py 用 QListWidget 拼接 | `privacyguard/word/candidate_dialog.py::WordCandidateDialog` | D-05 收敛原则 + 隔离 UI 装配 |
| 测试用 Word fixture | 提交真实 Word 文件到 `tests/fixtures/` | `tests/fixtures/fake_word.py::build_fake_docx()` 合成 | OPS-05 合成数据；隐私项目不接受真实数据 |
| 跨平台打包 `privacyguard.word.*` 模块 | 手动改两个 spec | `packaging/{windows,macos}/config/*.spec` `hiddenimports` 段同步追加 | cp30 教训 + Phase 1/2 沿用 |

**Key insight:** Phase 3 核心收益是「PII 引擎从 PDF 扩展到 Word 格式 + 真脱敏方式升级 + 文档属性清除」三件套，**不需要**新 PyPI 依赖、不需要 Word 专用识别模型、不需要云端 API。所有新增代码量控制在 ~500 行（含 WordAdapter + redact_word + clear_word_doc_props + WordCandidateDialog + worker + tests）。任何「先打地基再说」的扩张倾向都应被推迟到 Phase 4（Excel）/ 5（Image）/ 6（ctx-tier）/ 7（候选审阅 UI 完整版）/ 8（规则编辑 + 审计 + 打包 + 基线）。

---

## Runtime State Inventory

> Phase 3 不涉及 rename / refactor / migration（仅在现有 Word pipeline 上扩展 PII 通道）。**Phase 3 仅新增键**到 `word_data[key]` 字典的 `"pii"` 字段；不删除 / 不重命名任何现有键。

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `word_data[key]` 字典当前键：`text` / `ocr` / `manual`（paragraphs + tables 单元） | **新增** `"pii"` 键（与 ocr / manual 平级），无破坏性变更 |
| Live service config | 无（Phase 3 是单机桌面应用，无外部服务） | None |
| OS-registered state | 无（Phase 3 不注册 OS 级状态） | None |
| Secrets and env vars | 无（Phase 3 不引入新 secret） | None |
| Build artifacts | 无（Phase 3 不修改 `version.txt` / `packaging/`） | None（PyInstaller spec 的 `hiddenimports` 段需追加 `privacyguard.word.*` 但属 cp30 教训既有的 spec 修改路径） |

**Nothing found in category:** `Live service config` / `OS-registered state` / `Secrets and env vars` / `Build artifacts` 全部经本机 Python 验证无对应注册（项目为单机桌面应用）；`Stored data` 仅 `word_data[key]` 字典新增 `"pii"` 通道，与 Phase 1 `page_data[i]["pii"]`（`main.py:10644`）对称。

---

## Common Pitfalls

### Pitfall 1: Word run-boundary fragmentation（`para.text` 字符串匹配 vs run-level 替换不一致）

**What goes wrong:** 单条身份证号 `110101199003078811` 在 Word 文档中被切到 2-3 个 `<w:r>` run 内（例如一个 run 装 "110101" + 一个 run 装 "199003" + 一个 run 装 "078811"），`''.join(run.text for run in para.runs)` 拼接后字符串匹配成功，但 `apply_range_to_runs` 替换时把整个匹配区间塞到第一个 run → 后续 run 残留原文片段。

**Why it happens:** Word 客户端按光标位置 / 拼写检查 / 自动更正等规则切分 run 边界，单一用户输入的 18 位字符串在 Word 默认行为下被多次切分。

**How to avoid:**
- D-16 复用 `main.py:replace_matches_in_paragraph`（已生产验证） + `apply_range_to_runs`（`main.py:909-962`）— 既有实现已处理 start_run_idx / end_run_idx 跨 run 边界场景
- 单元测试覆盖 `test_run_boundary_18digit_split_across_3_runs`：构造一个含 3-run 拆分的 docx → 调 `redact_word` → 验证输出 docx 内 `para.text` 不含 18 位身份证
- 验证：`from docx import Document; d = Document(out_path); para = d.paragraphs[0]; assert secret_id not in para.text`

**Warning signs:**
- 单元测试仅断言 `mask_for_entity` 输出字符串存在，未断言原文 `para.text` 不含敏感子串
- `_save_word` 测试通过但 `_save_word` 后的 docx 用 `pdftotext` 类似的 docx 文本提取器（如 `docx2txt`）仍能提取原文

**Phase to address:** Phase 3（D-13 / D-23）

### Pitfall 2: `data-key` 块 ID ↔ `word_data[key]` 同步失败

**What goes wrong:** `_add_data_key_attributes`（`main.py:12236-12277`）通过 `element.get_text() == normalized_original` 匹配；mammoth 转 HTML 时可能在段落内插入 `<strong>` / `<em>` / `<a>` 等 inline 标签，导致 `element.get_text()` 不等于原文 → 该 block 整个没有 `data-key` → 局部 PII 高亮 patch 失效。

**Why it happens:** mammoth 默认对粗体 / 斜体 / 链接做 inline 元素包裹，与 word_data[key]["text"]（通过 `''.join(run.text for run in para.runs)` 拼接的纯文本）不严格相等。

**How to avoid:**
- D-22 验证脚本 `tests/unit/test_word_pii_pipeline.py::test_data_key_sync`：渲染后 DOM `soup.find_all(attrs={"data-key": True})` 数 == `len(word_data)`，失败打 warn
- 兜底：`_add_data_key_regex_fallback`（`main.py:12283-12329`）已实现；Phase 3 单元测试覆盖「mammoth 内含 `<strong>` 标签的段落」场景，验证 fallback 仍能打上 data-key
- 进一步：考虑在 `WordAdapter.collect_units` 时按 mammoth HTML 输出同步打 data-key（替代现有 BeautifulSoup 阶段注入）；Phase 3 不实现，Phase 8 再优化

**Warning signs:**
- 测试只验证 word_data 字典初始化正确，未验证渲染后 HTML 的 data-key 同步
- 工具栏点 PII 高亮 toggle 后无视觉效果

**Phase to address:** Phase 3（D-22）

### Pitfall 3: `w:tab` / `<w:br/>` 跨段敏感实体识别失败

**What goes wrong:** 身份证号被 Word 拆成多段 + `w:tab`（Tab 字符 `\t`）连接：`"110101\t19900307\t8811"`，`para.text` 含 `\t` 但 `''.join(run.text for run in para.runs)` 拼接后保留 `\t`；PIIEngine 的 `flatten_for_match`（`privacyguard/pii/normalize.py:7+`）按 `[-\s　]+` 拆 chunk，可正确合并跨 Tab 的实体；但若 chunk 中含 `\t` 字符，**手动写** 的 PII 命中区间可能与 PIIEngine 实际命中区间不严格对齐。

**Why it happens:** Phase 1 ENGINE-06（识别跨 newline/column/cell 切断的实体）已通过 `flatten_for_match` 实现，但 Word 特有的 `w:tab` 字符不在 Phase 1 的标准化考虑中。

**How to avoid:**
- D-15 复用 `PIIEngine.detect` 自动处理（Phase 1 ENGINE-06 既有实现）— 不需要 Phase 3 单独处理 Tab
- 验证：`engine.detect(TextUnit(page_index=0, text="110101\t19900307\t8811", source="text"))` 命中 1 个 CN_ID_CARD（与跨 newline 形态同效果）
- 单元测试：`test_pii_across_word_tab_recognized` 覆盖此场景

**Warning signs:**
- 测试用例不覆盖含 `\t` 的 docx 文本
- PIIEngine `_resolve_page_rect` 在含 `\t` 文本上出现 `map_flat_to_original` 偏移错误

**Phase to address:** Phase 3（D-15 / 验证 ENGINE-06）

### Pitfall 4: 候选列表（`WordCandidateDialog`）在 word_data 巨大时阻塞 UI

**What goes wrong:** `_all_hits` 一次性收集 word_data 内全部 PII + ocr + manual（可能数千条），`_filtered_hits()` 在筛选 / 翻页时遍历全量 → 单次 `_refresh` 数百毫秒 → UI 卡顿。

**Why it happens:** 简单 `for + if` 嵌套遍历 + 全量列表构建。

**How to avoid:**
- D-25 锁定 50 条分页（`PAGE_SIZE = 50`）— 已避免一次渲染过多
- `_filtered_hits()` 加 `lru_cache(maxsize=8)` 缓存筛选结果（filter 变化时清空）
- 候选列表只列前 1000 条（按 `hit.entity_type + key` 排序去重），超量提示「请使用高级筛选」
- 性能预算：单次 `_refresh` < 50ms（与 Phase 7 候选审阅 UI 性能预算一致）

**Warning signs:**
- 1000+ 候选时翻页卡顿 > 200ms
- `_all_hits` 内存占用 > 50MB（极端 word_data 大小）

**Phase to address:** Phase 3（D-25 / UX-02）

### Pitfall 5: `clear_word_doc_props` 字段定义遗漏（`app_properties` 部分 python-docx 版本只读）

**What goes wrong:** `doc.app_properties` 在 python-docx v0.8.10 以下版本不存在或只读；`setattr(app, "company", "")` 抛 `AttributeError` / `ValueError`。

**Why it happens:** python-docx 早期版本不暴露 `app_properties`；`docProps/app.xml` 是 OOXML 规范但 python-docx 早期只读。

**How to avoid:**
- D-24 用 `hasattr` + try/except 防御：
  ```python
  if hasattr(doc, "app_properties") and doc.app_properties is not None:
      try:
          setattr(app, prop_name, "")
      except (AttributeError, ValueError):
          pass
  ```
- 验证 `app_properties` 可用：先在本机 `python3 -c "from docx import Document; d = Document(); print(hasattr(d, 'app_properties'))"` 检查；如不可用，Phase 3 跳过 app 字段，仅清 core 6 字段
- 单元测试 `test_clear_core_6_fields_always_succeeds` + `test_clear_app_2_fields_when_available`（两个独立测试）

**Warning signs:**
- `clear_word_doc_props` 在某个 python-docx 版本抛异常，导致 `_save_word` 整体失败
- 测试仅覆盖 core 字段，未覆盖 app 字段

**Phase to address:** Phase 3（D-24）

### Pitfall 6: `merge_word_matches_with_priority` 优先级反向（D-19 错位）

**What goes wrong:** Phase 3 把 pii_matches 排在 manual 之前（D-19 `rule > pii > manual > ocr`），但实现时按参数顺序 `_append_candidates(rule), _append_candidates(pii), _append_candidates(manual), _append_candidates(ocr)` 时，**先 append 的优先级更高**（与 _range_overlaps 的 occupied 跟踪相关），实现顺序与语义顺序需保持一致。

**Why it happens:** 既有 `merge_word_matches_with_priority`（`main.py:863-906`）用 `occupied_ranges` 跟踪，新加入的 match 如果与已有区间重叠则被 skip；优先级高的应**先**加入（占据区间，后续被 skip）。

**How to avoid:**
- D-19 锁定实现顺序：`rule` → `pii` → `manual` → `ocr`（与语义顺序一致）
- 单元测试 `test_merge_priority_rule_beats_pii` / `test_merge_priority_pii_beats_manual` / `test_merge_priority_manual_beats_ocr` 覆盖
- 回归测试：现有 `test_word_replace_rules` 与 `test_batch_word_replace` 必须保持 green

**Warning signs:**
- 单元测试只覆盖 `_append_candidates` 一类，无优先级交叉测试
- 改动后 PII 候选被 manual 框选覆盖（用户报障）

**Phase to address:** Phase 3（D-19 / D-23）

### Pitfall 7: `WordPIIWorker` 与 main.py `_word_data_lock` 不并发安全

**What goes wrong:** `WordPIIWorker`（QThread）调 `engine.detect` 后通过 `pii_signal.emit(key, hits)` 送回主线程；主线程 `_on_word_pii_page_result` 写 `self.word_data[key]["pii"] = hits` 必须加 `QMutexLocker(self._word_data_lock)`，否则多 worker 并发 + `_save_word` 同时读 word_data 触发 race condition。

**Why it happens:** cp30 教训扩展到 word_data；Phase 1 `_on_pii_page_result`（`main.py:11393-11406`）已用 QMutex 保护 `page_data`，但 word_data 路径在 `_save_word`（`main.py:12703`）中**未**加锁。

**How to avoid:**
- D-09 新增 `_on_word_pii_page_result` 槽必须 `with QMutexLocker(self._word_data_lock): self.word_data[key]["pii"] = hits`
- 单元测试 `test_word_pii_lock_concurrent_writes`：mock 两个 worker 并发 emit，验证最终 word_data 一致
- 验证：本机测试 `WordPIIWorker` 在多线程场景下不抛 `RuntimeError: dictionary changed size during iteration`

**Warning signs:**
- 测试只覆盖单 worker 顺序 emit，无并发场景
- `_save_word` 路径与 worker 路径同时运行时报 `RuntimeError`

**Phase to address:** Phase 3（D-09 / cp30 教训扩展）

### Pitfall 8: `core_properties.revision` 置空字符串触发 `ValueError`

**What goes wrong:** `doc.core_properties.revision = ""` 抛 `ValueError`（python-docx 期望 int）；D-24 锁定 `revision = 1`（默认值）— 但若实现者忘记分支处理，整 `_save_word` 失败。

**Why it happens:** python-docx `core_properties.revision` 是 `int` 类型（D-24 在 CORE_PROPS_TO_CLEAR 中已显式区分字符串 vs 整数）。

**How to avoid:**
- D-24 锁定：`revision` 字段单独处理，置 `1`；其他 core 字段置 `""`
- 单元测试 `test_revision_set_to_1_not_empty_string`
- 代码注释明示：`revision` is the only int field; clear by reset to default 1

**Warning signs:**
- `clear_word_doc_props` 函数内循环 `for prop_name in CORE_PROPS_TO_CLEAR: setattr(core, prop_name, "")` 简单粗暴，未区分类型
- 测试只覆盖 title / author 等字符串字段

**Phase to address:** Phase 3（D-24）

### Pitfall 9: 整页 `setHtml()` 触发重渲染破坏 cp27 增量 patch 契约

**What goes wrong:** Phase 3 在 worker 写 PII 后，主线程调 `_apply_word_pii_panel_updates`（新增）应走 `web_view.page().runJavaScript("updateBlock(...)")` 局部 patch；但实现者可能直接 `web_view.setHtml(...)` 整页重渲染 → 丢失滚动位置 / 选中状态 / 缩放 → 违反 cp27 锁定。

**Why it happens:** `setHtml()` 是最简单实现；cp27 局部 patch 需写 JavaScript 函数（既有 `build_word_panel_update_script`）。

**How to avoid:**
- D-10 严格走 `web_view.page().runJavaScript(...)` + 既有 `build_word_panel_update_script`（`main.py:471-...`）+ `apply_word_panel_updates`（`main.py:12000-12005`）
- 单元测试 `test_pii_panel_uses_javascript_patch_not_set_html`：mock `web_view.page().runJavaScript`，断言被调用；mock `web_view.setHtml`，断言**未**被调用
- 代码注释明示：「cp27 增量 patch 契约 — 禁止整页 setHtml」

**Warning signs:**
- 单元测试 mock 不到 `runJavaScript` 被调用，但 `setHtml` 被调用
- 用户报告「每次 PII 命中后预览都跳到顶部」

**Phase to address:** Phase 3（D-10 / cp27 锁定）

### Pitfall 10: Phase 1 79/79 测试基线被破坏（D-13 / D-14 门禁）

**What goes wrong:** Phase 3 改动 `merge_word_matches_with_priority`（`main.py:863`）函数签名（新增 `pii_matches` 第四参数）或 `_add_data_key_attributes`（`main.py:12236`）→ `test_word_replace_rules` / `test_batch_word_replace` 失败 → 79/79 基线破坏。

**Why it happens:** main.py:863 函数是 module-level 公共函数，签名变更影响所有调用点；新参数必须设默认值（`pii_matches=None`）保持向后兼容。

**How to avoid:**
- D-19 锁定 `merge_word_matches_with_priority(text, rules, default_replacement_text, manual_matches=None, ocr_matches=None, pii_matches=None)` 第四 / 五 / 六参数均有默认值
- D-22 锁定 `_add_data_key_attributes` 签名**不**改；只在调用方验证同步
- 完整命令门禁（CLAUDE.md）：`python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_package_imports tests.unit.test_pdf_text_hit_dedup tests.unit.test_app_config tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety tests.unit.test_convergence -v`

**Warning signs:**
- 提交前未跑完整 79/79 命令
- 新增参数无默认值

**Phase to address:** Phase 3（D-13 / D-14 / D-19 / D-22）

---

## Code Examples

Verified patterns from main.py / privacyguard.pii 既有实现：

### WordAdapter.collect_units（D-04 / D-17 / D-22）

```python
# privacyguard/word/adapter.py
"""Phase 3: Word → PII 引擎 TextUnit 流适配器（D-04 / D-17）。"""
from typing import Dict, List, Tuple
from docx import Document
from privacyguard.pii.hits import TextUnit


class WordAdapter:
    @staticmethod
    def collect_units(docx_path: str) -> Tuple[List[TextUnit], Dict[int, str]]:
        """遍历 docx 的 paragraphs + tables，产出 TextUnit + key 索引。

        Returns:
            (units, key_index):
                units: List[TextUnit]，与 word_data 字典迭代顺序一致
                key_index: Dict[TextUnit.page_index → word_data key 字符串]
        """
        doc = Document(docx_path)
        units: List[TextUnit] = []
        key_index: Dict[int, str] = {}
        idx = 0

        # 段落（与 main.py:10796-10804 同步）
        for para_idx, para in enumerate(doc.paragraphs):
            text = para.text or ""
            if not text.strip():
                continue
            units.append(TextUnit(page_index=idx, text=text, source="text"))
            key_index[idx] = f"paragraph_{para_idx}"
            idx += 1

        # 表格（与 main.py:10807-10819 同步）
        for table_idx, table in enumerate(doc.tables):
            for row_idx, row in enumerate(table.rows):
                for cell_idx, cell in enumerate(row.cells):
                    text = cell.text or ""
                    if not text.strip():
                        continue
                    units.append(TextUnit(page_index=idx, text=text, source="text"))
                    key_index[idx] = f"table_{table_idx}_cell_{row_idx}_{cell_idx}"
                    idx += 1

        return units, key_index


__all__ = ['WordAdapter']
```

### redact_word（D-23 真脱敏 wrapper）

```python
# privacyguard/word/redact.py
"""Phase 3: Word 真脱敏写入 wrapper（D-23）。"""
from typing import List


def redact_paragraph(para, matches, fallback_replacement_text="[已脱敏]"):
    """单段落 run-level 替换（沿用 main.py:replace_matches_in_paragraph）。"""
    # 懒加载 main.py 避免 privacyguard.word 触发 main.py 12.9k LOC 加载
    from main import replace_matches_in_paragraph
    replace_matches_in_paragraph(para, matches, text_offset=0,
                                 fallback_replacement_text=fallback_replacement_text)


def redact_word(doc, key: str, merged_matches: List[dict],
                fallback_replacement_text: str = "[已脱敏]"):
    """Phase 3: 按 key 找到 doc 内对应段落 / 表格 cell，调 run-level 替换（D-23）。"""
    if not merged_matches:
        return
    from main import replace_matches_in_paragraph
    if key.startswith("paragraph_"):
        para_idx = int(key.split("_", 1)[1])
        if para_idx >= len(doc.paragraphs):
            return
        replace_matches_in_paragraph(
            doc.paragraphs[para_idx], merged_matches, text_offset=0,
            fallback_replacement_text=fallback_replacement_text,
        )
    elif key.startswith("table_"):
        parts = key.split("_")
        if len(parts) != 5:
            return
        t, r, c = int(parts[1]), int(parts[3]), int(parts[4])
        if t >= len(doc.tables):
            return
        cell = doc.tables[t].rows[r].cells[c]
        # cell.paragraphs 多段（与 main.py:12753-12766 同步：para_offset 累加）
        para_offset = 0
        paragraphs = list(cell.paragraphs)
        for idx, para in enumerate(paragraphs):
            original_para_len = len("".join(run.text for run in para.runs))
            replace_matches_in_paragraph(
                para, merged_matches, text_offset=para_offset,
                fallback_replacement_text=fallback_replacement_text,
            )
            para_offset += original_para_len
            if idx < len(paragraphs) - 1:
                para_offset += 1  # python-docx cell.text 用换行拼接


__all__ = ['redact_word', 'redact_paragraph']
```

### clear_word_doc_props（D-08 / D-24）

```python
# privacyguard/word/clear_doc_props.py
"""Phase 3: Word 文档属性清除（D-08 / D-24）。"""
from typing import Final


CORE_PROPS_TO_CLEAR: Final = (
    "title", "author", "subject", "keywords", "last_modified_by",
)
APP_PROPS_TO_CLEAR: Final = (
    "company", "manager",
)


def clear_word_doc_props(doc) -> None:
    """Phase 3: Word 文档属性清除（D-08 / D-24）。

    仅清 5 个 core 字符串字段 + 1 个 core 整数字段 + 2 个 app 字段；
    CreationDate / ModDate / Template / TotalTime 等保留；
    所有清空字段置空字符串，不写 "Anonymous" / "Redacted" 等占位字符串。
    """
    core = doc.core_properties
    for prop_name in CORE_PROPS_TO_CLEAR:
        if prop_name == "title":
            core.title = ""
        elif prop_name == "author":
            core.author = ""
        elif prop_name == "subject":
            core.subject = ""
        elif prop_name == "keywords":
            core.keywords = ""
        elif prop_name == "last_modified_by":
            core.last_modified_by = ""
    # revision 是整数，置 1（默认值）
    if hasattr(core, "revision"):
        core.revision = 1

    # app_properties 视 python-docx 版本而定
    if hasattr(doc, "app_properties") and doc.app_properties is not None:
        app = doc.app_properties
        for prop_name in APP_PROPS_TO_CLEAR:
            if hasattr(app, prop_name):
                try:
                    setattr(app, prop_name, "")
                except (AttributeError, ValueError):
                    pass


__all__ = ['clear_word_doc_props', 'CORE_PROPS_TO_CLEAR', 'APP_PROPS_TO_CLEAR']
```

### merge_word_matches_with_priority 扩展（D-19）

```python
# main.py:863-906 修改（保留向后兼容：所有新参数有默认值）
def merge_word_matches_with_priority(text, rules, default_replacement_text,
                                     manual_matches=None, ocr_matches=None,
                                     pii_matches=None):  # ◀── NEW pii 第四参数
    """合并规则替换、手动脱敏、OCR 脱敏区间、自动 PII 识别；优先级：rule > pii > manual > ocr（D-19）。"""
    manual_matches = manual_matches or []
    ocr_matches = ocr_matches or []
    pii_matches = pii_matches or []  # ◀── NEW: PIIHit 列表
    text_len = len(text) if isinstance(text, str) else 0
    fallback_text = default_replacement_text if isinstance(default_replacement_text, str) and default_replacement_text else "[已脱敏]"

    merged = []
    occupied_ranges = []

    def _append_candidates(candidates, source_name):
        for item in candidates:
            # PIIHit 走 mask_for_entity 拿字符串（D-23 partial mask）
            if isinstance(item, PIIHit):
                start = item.page_offset
                end = item.page_offset + item.page_length
                replacement = item.mask_strategy or fallback_text
                candidates_dict = {
                    "start": start,
                    "end": end,
                    "text": item.normalized,
                    "replacement": replacement,
                    "source": source_name,
                    "mode": "global",
                    "rule_name": "",
                }
                item = candidates_dict
            start = item.get("start")
            end = item.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            if start < 0 or end > text_len or start >= end:
                continue
            if _range_overlaps(start, end, occupied_ranges):
                continue
            replacement = item.get("replacement", fallback_text)
            if replacement is None:
                replacement = fallback_text
            if not isinstance(replacement, str):
                replacement = str(replacement)
            merged.append({
                "start": start,
                "end": end,
                "text": item.get("text", text[start:end] if isinstance(text, str) else ""),
                "replacement": replacement,
                "source": source_name,
                "mode": item.get("mode", "global"),
                "rule_name": item.get("rule_name", "")
            })
            occupied_ranges.append((start, end))

    # D-19 优先级（高 → 低）：rule → pii → manual → ocr
    _append_candidates(build_word_rule_matches(text, rules, fallback_text), "rule")
    _append_candidates(pii_matches, "pii")  # ◀── NEW
    _append_candidates(manual_matches, "manual")
    _append_candidates(ocr_matches, "ocr")
    merged.sort(key=lambda item: item["start"])
    return merged
```

### _on_word_pii_page_result（D-09 / D-18）

```python
# main.py (新增槽)
def _on_word_pii_page_result(self, key: str, hits_data: list):
    """Phase 3: pii_signal 接收槽（D-09 / D-18）。

    Args:
        key: word_data 的 key（"paragraph_5" / "table_0_cell_1_2"）
        hits_data: List[dict]（PIIHit asdict 形态，从 worker 信号送回）
    """
    from privacyguard.pii.hits import PIIHit
    hits = [PIIHit(**h) for h in hits_data]
    with QMutexLocker(self._word_data_lock):
        if key in self.word_data:
            self.word_data[key]["pii"] = hits
        else:
            # 防御性：worker 写出 word_data 已不存在的 key
            print(f"[Word PII WARN] key {key} not in word_data")
    # D-10: 触发 cp27 增量 patch（双栏高亮）
    self._apply_word_pii_panel_updates(key, hits)


def _apply_word_pii_panel_updates(self, key: str, hits: list):
    """Phase 3: 按 data-key 局部 patch 双栏 PII 高亮（D-10 / cp27）。

    不触发整页 setHtml；走 web_view.page().runJavaScript 局部 patch。
    """
    if not hits:
        return
    from main import build_word_panel_update_script
    block_updates = {key: self._build_pii_block_fragment(key, hits)}
    for view_attr in ("word_preview", "word_preview_replaced"):
        view = getattr(self, view_attr, None)
        if view and not view.isHidden():
            script = build_word_panel_update_script(block_updates)
            view.page().runJavaScript(script)


def _build_pii_block_fragment(self, key: str, hits: list) -> str:
    """构造 data-key block 的 PII 高亮 HTML 片段（D-21）。"""
    from privacyguard.pii.hits import PIIHit
    from main import ENTITY_TYPE_LABEL  # 或从 pii 子包导入
    if key not in self.word_data:
        return ""
    text = self.word_data[key].get("text", "")
    # 按 offset 排序
    sorted_hits = sorted(hits, key=lambda h: h.page_offset)
    parts = []
    cursor = 0
    for hit in sorted_hits:
        if hit.page_offset > cursor:
            parts.append(text[cursor:hit.page_offset])
        label = ENTITY_TYPE_LABEL.get(hit.entity_type, hit.entity_type)
        # 左栏原文 + 标签
        parts.append(
            f'<mark class="pii-highlight" data-entity-type="{hit.entity_type}" '
            f'title="{label}">{text[hit.page_offset:hit.page_offset + hit.page_length]}</mark>'
        )
        cursor = hit.page_offset + hit.page_length
    if cursor < len(text):
        parts.append(text[cursor:])
    return "".join(parts)
```

### build_fake_docx（D-26 fixture）

```python
# tests/fixtures/fake_word.py
"""Phase 3: 合成含 PII 的 docx fixture（D-26 / OPS-05）。"""
from typing import List, Optional

from docx import Document


def build_fake_docx(
    paragraphs: Optional[List[str]] = None,
    tables: Optional[List[List[List[str]]]] = None,
    add_pii: bool = True,
) -> str:
    """合成一个含 PII 的 docx 文件，路径在 /tmp 下。

    Args:
        paragraphs: 段落文本列表（含 PII 文本时 add_pii=True 自动加命中）
        tables: 表格内容 3D 列表 [[[cell_text, ...], ...], ...]
        add_pii: 若 True，自动追加身份证 / 手机 / 邮箱 / 银行卡等 PII 段落

    Returns:
        写入的 docx 文件路径（tempfile 路径）
    """
    import tempfile
    doc = Document()
    if paragraphs:
        for p_text in paragraphs:
            doc.add_paragraph(p_text)
    if tables:
        for tbl in tables:
            if not tbl:
                continue
            n_rows = len(tbl)
            n_cols = max(len(row) for row in tbl)
            table = doc.add_table(rows=n_rows, cols=n_cols)
            for r_idx, row in enumerate(tbl):
                for c_idx, cell_text in enumerate(row):
                    if c_idx < n_cols:
                        table.rows[r_idx].cells[c_idx].text = cell_text
    if add_pii:
        from tests.fixtures.fake_pii import (
            fake_id_card, fake_phone, fake_email, fake_bank_card, fake_uscc,
        )
        doc.add_paragraph(f"甲方身份证 {fake_id_card()}")
        doc.add_paragraph(f"联系电话 {fake_phone()}")
        doc.add_paragraph(f"邮箱 {fake_email()}")
        doc.add_paragraph(f"卡号 {fake_bank_card()}")
        doc.add_paragraph(f"统一信用代码 {fake_uscc()}")

    fd, path = tempfile.mkstemp(suffix=".docx")
    import os
    os.close(fd)
    doc.save(path)
    return path


__all__ = ['build_fake_docx']
```

### test_word_pii_pipeline.py 主测试类（D-13 / D-22 / D-23 / D-24）

```python
# tests/unit/test_word_pii_pipeline.py
"""Phase 3: Word 端到端 PII 流程测试（D-13）。"""
import os
import tempfile
import unittest

from docx import Document
from privacyguard.pii.engine import PIIEngine
from privacyguard.pii.hits import TextUnit, PIIHit
from privacyguard.pii.mask import mask_for_entity
from privacyguard.word.adapter import WordAdapter
from privacyguard.word.clear_doc_props import clear_word_doc_props
from tests.fixtures.fake_pii import (
    fake_id_card, fake_phone, fake_email, fake_bank_card, fake_uscc,
)
from tests.fixtures.fake_word import build_fake_docx


class TestWordAdapterCollectUnits(unittest.TestCase):
    def test_collect_units_returns_text_unit_per_block(self):
        path = build_fake_docx(paragraphs=["段落 0", "段落 1"])
        units, key_index = WordAdapter.collect_units(path)
        self.assertGreaterEqual(len(units), 2)
        self.assertEqual(key_index[0], "paragraph_0")
        self.assertEqual(key_index[1], "paragraph_1")
        os.remove(path)


class TestWordPIIAutoTrigger(unittest.TestCase):
    def test_engine_detects_pii_in_word_text(self):
        """Phase 3 9 类 PII 全部可识别（D-15 / Phase 2 沿用）。"""
        from tests.fixtures.fake_pii import fake_vat_invoice_20, fake_bank_account
        text = (
            f"身份证 {fake_id_card()} 手机 {fake_phone()} "
            f"邮箱 {fake_email()} 卡号 {fake_bank_card()} "
            f"USCC {fake_uscc()} 发票 {fake_vat_invoice_20()} "
            f"账号 {fake_bank_account()}"
        )
        engine = PIIEngine()
        hits = engine.detect(TextUnit(page_index=0, text=text, source="text"))
        entity_types = {h.entity_type for h in hits}
        # 至少命中 6 类（CN_VAT_INVOICE 需要 20 位 + 上下文锥点）
        self.assertGreaterEqual(len(entity_types), 6)
        for et in ("CN_ID_CARD", "CN_PHONE", "CN_EMAIL", "CN_BANK_CARD", "CN_USCC"):
            self.assertIn(et, entity_types)


class TestWordRedactRoundTrip(unittest.TestCase):
    def test_redact_word_partial_mask_visible(self):
        """D-23: redact_word 后 para.text 不含原文 + 含 mask 字符串。"""
        from privacyguard.word.redact import redact_word
        from main import merge_word_matches_with_priority
        secret_id = fake_id_card()
        path = build_fake_docx(paragraphs=[f"原文 {secret_id}"])
        # 模拟 word_data 初始化（D-04 / D-18）
        word_data = {
            "paragraph_0": {
                "text": f"原文 {secret_id}",
                "ocr": [],
                "manual": [],
                "pii": [],
            }
        }
        # 模拟 PIIEngine.detect
        engine = PIIEngine()
        hits = engine.detect(TextUnit(page_index=0, text=word_data["paragraph_0"]["text"], source="text"))
        word_data["paragraph_0"]["pii"] = hits
        # 模拟 _save_word
        doc = Document(path)
        merged = merge_word_matches_with_priority(
            word_data["paragraph_0"]["text"],
            rules=[], default_replacement_text="[已脱敏]",
            manual_matches=[],
            ocr_matches=[],
            pii_matches=hits,
        )
        redact_word(doc, "paragraph_0", merged)
        clear_word_doc_props(doc)
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            out_path = tmp.name
        doc.save(out_path)
        # 验证
        out_doc = Document(out_path)
        out_text = "".join(p.text for p in out_doc.paragraphs)
        self.assertNotIn(secret_id, out_text)
        expected_mask = mask_for_entity("CN_ID_CARD", secret_id)
        self.assertIn(expected_mask, out_text)
        os.remove(path)
        os.remove(out_path)


class TestWordDocumentPropertiesCleared(unittest.TestCase):
    def test_clear_core_5_fields_always_succeeds(self):
        path = build_fake_docx(paragraphs=["test"])
        doc = Document(path)
        doc.core_properties.title = "敏感标题"
        doc.core_properties.author = "敏感作者"
        doc.core_properties.subject = "敏感主题"
        doc.core_properties.keywords = "敏感关键字"
        doc.core_properties.last_modified_by = "敏感修改者"
        clear_word_doc_props(doc)
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            out_path = tmp.name
        doc.save(out_path)
        out_doc = Document(out_path)
        self.assertEqual(out_doc.core_properties.title, "")
        self.assertEqual(out_doc.core_properties.author, "")
        self.assertEqual(out_doc.core_properties.subject, "")
        self.assertEqual(out_doc.core_properties.keywords, "")
        self.assertEqual(out_doc.core_properties.last_modified_by, "")
        os.remove(path)
        os.remove(out_path)

    def test_clear_revision_set_to_1(self):
        """D-24: revision 是整数，置 1（非空字符串）。"""
        path = build_fake_docx(paragraphs=["test"])
        doc = Document(path)
        doc.core_properties.revision = 99
        clear_word_doc_props(doc)
        self.assertEqual(doc.core_properties.revision, 1)
        os.remove(path)


class TestWordMergePriorityRulePiManualOcr(unittest.TestCase):
    def test_rule_beats_pii(self):
        """D-19 优先级：rule > pii > manual > ocr。"""
        from main import merge_word_matches_with_priority
        text = "张三 53010219200508011X"
        secret_id = "53010219200508011X"
        hit = PIIHit(
            entity_type="CN_ID_CARD", page_offset=3, page_length=18,
            page_rect=(0, 0, 0, 0), confidence_tier="HIGH", source="text",
            mask_strategy=mask_for_entity("CN_ID_CARD", secret_id),
            normalized=secret_id,
        )
        # rule 在 0-2 "张三" 处
        rules = [{"enabled": True, "mode": "exact", "find": "张三", "replace": "[姓名]"}]
        merged = merge_word_matches_with_priority(
            text, rules, "[已脱敏]",
            manual_matches=[],
            ocr_matches=[],
            pii_matches=[hit],
        )
        # 0-2 rule 优先于 3-21 pii（不重叠，故都加入）
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["source"], "rule")
        self.assertEqual(merged[0]["replacement"], "[姓名]")
        self.assertEqual(merged[1]["source"], "pii")

    def test_pii_beats_manual_on_overlap(self):
        """D-19 优先级：pii 覆盖 manual（区间重叠时）。"""
        from main import merge_word_matches_with_priority
        text = "53010219200508011X"
        secret_id = text
        hit = PIIHit(
            entity_type="CN_ID_CARD", page_offset=0, page_length=18,
            page_rect=(0, 0, 0, 0), confidence_tier="HIGH", source="text",
            mask_strategy=mask_for_entity("CN_ID_CARD", secret_id),
            normalized=secret_id,
        )
        # manual 在 0-18 处也占（区间重叠）
        manual = [{"start": 0, "end": 18, "text": secret_id, "replacement": "[手动]"}]
        merged = merge_word_matches_with_priority(
            text, rules=[], default_replacement_text="[已脱敏]",
            manual_matches=manual,
            ocr_matches=[],
            pii_matches=[hit],
        )
        # pii 优先 manual，manual 被 skip
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "pii")


class TestWordDataKeySync(unittest.TestCase):
    """D-22: data-key 块 ID ↔ word_data 同步验证。"""

    def test_data_key_count_matches_word_data(self):
        """mammoth 渲染后 DOM data-key 数 == word_data key 数。"""
        from main import _add_data_key_attributes
        path = build_fake_docx(
            paragraphs=["段落 0", "段落 1"],
            tables=[[["cell 0", "cell 1"]]],
        )
        doc = Document(path)
        word_data = {}
        for idx, para in enumerate(doc.paragraphs):
            if para.text.strip():
                word_data[f"paragraph_{idx}"] = {"text": para.text, "ocr": [], "manual": []}
        # 模拟 mammoth 转 HTML
        from bs4 import BeautifulSoup
        html = "<p>段落 0</p><p>段落 1</p><table><tr><td>cell 0</td><td>cell 1</td></tr></table>"
        text_blocks = {k: {"text": v["text"], "escaped": v["text"]} for k, v in word_data.items()}
        tagged = _add_data_key_attributes(html, text_blocks)
        soup = BeautifulSoup(tagged, "html.parser")
        data_keyed = soup.find_all(attrs={"data-key": True})
        # 至少段落 0/1 应打上 data-key
        keys_found = {el.get("data-key") for el in data_keyed}
        self.assertIn("paragraph_0", keys_found)
        self.assertIn("paragraph_1", keys_found)
        os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

### _save_word 集成（D-23 + D-24 接线）

```python
# main.py:_save_word 修改（line 12699-）
def _save_word(self, fname):
    """保存 Word 文档 - Phase 3 扩展：redact_word + clear_word_doc_props（D-23 / D-24）。"""
    try:
        import shutil
        from docx import Document
        from privacyguard.word.redact import redact_word
        from privacyguard.word.clear_doc_props import clear_word_doc_props
        from main import merge_word_matches_with_priority

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        temp_file = self.temp_manager.create_temp_file()
        shutil.copy2(self.file_path, temp_file)
        new_doc = Document(temp_file)

        # 遍历段落（D-19 priority: rule > pii > manual > ocr）
        for para_idx, para in enumerate(new_doc.paragraphs):
            key = f"paragraph_{para_idx}"
            if key in self.word_data:
                data = self.word_data[key]
                source_text = data.get("text", "")
                merged_matches = merge_word_matches_with_priority(
                    source_text, self.word_replace_rules, self.replacement_text,
                    manual_matches=data.get("manual", []),
                    ocr_matches=data.get("ocr", []),
                    pii_matches=data.get("pii", []),  # ◀── NEW Phase 3
                )
                if merged_matches:
                    redact_word(new_doc, key, merged_matches, self.replacement_text)

        # 遍历表格（同上）
        for table_idx, table in enumerate(new_doc.tables):
            for row_idx, row in enumerate(table.rows):
                for cell_idx, cell in enumerate(row.cells):
                    key = f"table_{table_idx}_cell_{row_idx}_{cell_idx}"
                    if key in self.word_data:
                        data = self.word_data[key]
                        source_text = data.get("text", "")
                        merged_matches = merge_word_matches_with_priority(
                            source_text, self.word_replace_rules, self.replacement_text,
                            manual_matches=data.get("manual", []),
                            ocr_matches=data.get("ocr", []),
                            pii_matches=data.get("pii", []),
                        )
                        if merged_matches:
                            redact_word(new_doc, key, merged_matches, self.replacement_text)

        # Phase 3: Word 文档属性清除（D-24 紧邻 save 前调）
        clear_word_doc_props(new_doc)

        new_doc.save(fname)  # ◀── D-24 调用位置

        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "成功", f"文件已保存至：\n{fname}")

    except PermissionError:
        # ... 既有错误处理（与 Phase 1 沿用）
        ...
    except (OSError, IOError, RuntimeError, ValueError, KeyError, AttributeError) as e:
        # ... 既有错误处理
        ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Word 文档手动 scan 按钮 | `_open_word_docx` 自动触发 PIIEngine.detect（`WordPIIWorker`） | Phase 3 (2026-Q3) | 用户体验：打开即看到候选；ENGINE-01 复用 |
| 整页 `setHtml()` 重渲染 | `web_view.page().runJavaScript("updateBlock(...)")` 局部 patch | cp27 (2026-03-10) | 保留滚动 / 选中 / 缩放状态；用户无感知 patch |
| PII 通道按 `pii_hits` 全局列表 | `word_data[key]["pii"]` 字典内嵌通道（与 ocr / manual 平级） | Phase 3 (2026-Q3) | 与 Phase 1 `page_data[i]["pii"]`（`main.py:10644`）对称；D-04 锁 |
| Word 文档属性保留原样 | `clear_word_doc_props` 清除 5 core + 2 app 字段 | Phase 3 (2026-Q3) | SAFE-03 类比 PDF 元数据清除；FMT-02 Success Criterion 4 |
| `replace_matches_in_paragraph` 仅处理 rule / manual / ocr | 新增 `pii_matches` 第四参数，priority = `rule > pii > manual > ocr` | Phase 3 (2026-Q3) | D-19 锁；9 类 PII 沿用 Phase 2 mask.py 输出 |
| 候选审阅 UI 完整 Phase 7 | `WordCandidateDialog` 极简版（entity_type 筛选 + 50 条分页） | Phase 3 (2026-Q3) | D-11 / D-25 锁；Phase 7 完整版（实体类型开关 / 白名单 / 撤销栈）后续独立 phase |
| 隐私数据未结构化 | `word_data[key]` 字典契约（text / ocr / manual / pii 四通道） | Phase 1 + Phase 3 (2026-Q3) | v37.7.6 收敛原则 + STATE.md §Decisions 锁 |
| `main.py` 内嵌 PII / Word adapter 实现 | `privacyguard/word/adapter.py` + `redact.py` + `clear_doc_props.py` 子包 | Phase 3 (2026-Q3) | v37.7.6 收敛；D-05 锁；OPS-03 懒加载 |

**Deprecated/outdated:**
- **手动 `scan_word` 按钮：** 现有 v37.7.6 行为；Phase 3 自动触发后此按钮可保留为手动 re-scan 入口
- **`pii_hits` 全局列表：** 违反 STATE.md §Decisions 「新数据存进现有 dict 的新 key」；Phase 3 强制用 `word_data[key]["pii"]`
- **`PIIHit` 新增字段：** D-16 字段锁；Phase 3 不扩展 PIIHit
- **`main.py` 内嵌 Word adapter / redact / clear_doc_props：** v37.7.6 收敛原则禁；Phase 3 全部进 `privacyguard/word/`

---

## TDD Specifics

### Fixtures（扩展 `tests/fixtures/fake_pii.py` + 新 `tests/fixtures/fake_word.py`）

| Fixture | 输入 | 输出 | 用途 |
|---------|------|------|------|
| `fake_vat_invoice_20()` | 任意 20 位 | 20 位数字 | Phase 3 `test_engine_detects_pii_in_word_text` |
| `fake_bank_account()` | 任意 9-21 位 | 18 位银行账号 | Phase 3 同上 |
| `build_fake_docx(paragraphs, tables, add_pii)` | 段落 + 表格 + PII 标志 | .docx 文件路径 | Phase 3 Word 端到端测试 |

### Test-First Cycle 示例

| Requirement | Failing Test (FIRST) | 实现 (THEN) | Fixture |
|-------------|---------------------|------------|---------|
| FMT-02 (auto-trigger) | `test_engine_detects_pii_in_word_text` 断言 `engine.detect(text)` 命中 ≥ 6 类 PII（含 CN_VAT_INVOICE 上下文锥点） | `privacyguard/word/adapter.py::WordAdapter.collect_units` + `WordPIIWorker` 自动调 `engine.detect` | `build_fake_docx(add_pii=True)` |
| FMT-02 (data-key 同步) | `test_data_key_count_matches_word_data` 断言 `soup.find_all(data-key)` 数 ≥ word_data 段落数 | 沿用 `_add_data_key_attributes` + `WordAdapter.collect_units` 同步 | `build_fake_docx(paragraphs=["段落 0", "段落 1"])` |
| FMT-02 (PII 真脱敏) | `test_redact_word_partial_mask_visible` 断言 `para.text` 不含 secret_id + 含 mask 字符串 | `privacyguard/word/redact.py::redact_word` 调 `replace_matches_in_paragraph` | `fake_id_card()` |
| FMT-02 (文档属性清除) | `test_clear_core_5_fields_always_succeeds` 断言 5 字段 == "" | `privacyguard/word/clear_doc_props.py::clear_word_doc_props` | `build_fake_docx()` |
| FMT-02 (priority pii > manual) | `test_pii_beats_manual_on_overlap` 断言合并后 pii 留下、manual 被 skip | `main.py:merge_word_matches_with_priority` 扩展 pii 第四参数 | `fake_id_card()` |
| UX-01 (候选列表) | `test_candidate_dialog_lists_pii_hits` 断言对话框显示 PII 命中 | `privacyguard/word/candidate_dialog.py::WordCandidateDialog` | `build_fake_docx(add_pii=True)` |
| UX-02 (分页 + 筛选) | `test_candidate_dialog_pagination` 断言 > 50 条分页 | `WordCandidateDialog._refresh` 锁定 50 条 / 页 | 60+ 候选合成 |

### Wave Plan 草图

1. **Wave 0:** `tests/fixtures/fake_word.py::build_fake_docx` — **先于**任何 Phase 3 代码
2. **Wave 1:** `tests/unit/test_word_pii_pipeline.py::TestWordAdapterCollectUnits` → 实现 `privacyguard/word/adapter.py::WordAdapter`
3. **Wave 2:** `tests/unit/test_word_pii_pipeline.py::TestWordPIIAutoTrigger` → 实现 `privacyguard/word/worker.py::WordPIIWorker` + `main.py:_on_word_pii_page_result` 槽（D-09 / D-18）
4. **Wave 3:** `tests/unit/test_word_pii_pipeline.py::TestWordMergePriorityRulePiManualOcr` → 实现 `main.py:merge_word_matches_with_priority` 扩展（D-19）
5. **Wave 4:** `tests/unit/test_word_pii_pipeline.py::TestWordRedactRoundTrip` → 实现 `privacyguard/word/redact.py::redact_word`（D-23）
6. **Wave 5:** `tests/unit/test_word_pii_pipeline.py::TestWordDocumentPropertiesCleared` → 实现 `privacyguard/word/clear_doc_props.py::clear_word_doc_props`（D-24）
7. **Wave 6:** `tests/unit/test_word_pii_pipeline.py::TestWordDataKeySync` → 验证 `_add_data_key_attributes` 同步（D-22）
8. **Wave 7:** `tests/unit/test_word_pii_pipeline.py::TestWordCandidateDialog` → 实现 `privacyguard/word/candidate_dialog.py::WordCandidateDialog`（UX-01 / UX-02）
9. **Wave 8:** `packaging/{windows,macos}/config/*.spec` `hiddenimports` 段追加 `privacyguard.word.*` 模块（cp30 教训 + D-06）

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 9 类 PII（CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT）在 Phase 3 时全部由 `engine.detect` 暴露 | §Standard Stack / §Phase Requirements | 若 Phase 2 9 类未完成，Phase 3 退化为 2-3 类（Phase 1 子集）；MEDIUM |
| A2 | `replace_matches_in_paragraph`（`main.py:965`）正确处理跨 run 边界（已生产验证） | §Common Pitfalls §1 / §Code Examples | 若跨 run 边界处理有 bug → 残留原文片段；HIGH（直接影响 SAFE-02） |
| A3 | `python-docx` `core_properties` API 接受空字符串写入（title / author / subject / keywords / last_modified_by） | §Standard Stack / §Code Examples | 若某个字段拒绝空字符串（抛 ValueError / AttributeError）→ `_save_word` 失败；MEDIUM |
| A4 | `python-docx` `app_properties.company` / `app_properties.manager` 在 v0.8.10+ 可写 | §Standard Stack / §Code Examples | 若不可写 → app 字段不清；LOW（与 Phase 2 SAFE-03 core 5 字段语义对齐即可） |
| A5 | `mammoth` DOCX→HTML 输出对 inline 元素（`<strong>` / `<em>` / `<a>`）按 inline 包裹，不破坏 paragraph block 边界 | §Common Pitfalls §2 | 若 mammoth 把整段嵌入 `<div>` 或 `<section>` → `_add_data_key_attributes` 失效；MEDIUM（fallback regex 已实现） |
| A6 | `WebEngineView.page().runJavaScript(...)` 局部 patch 在左右两栏独立可调（cp27 既有） | §Common Pitfalls §9 / §Code Examples | 若 runJavaScript 触发整页 reload → 失去 cp27 契约；HIGH（用户体验回归） |
| A7 | `_word_data_lock`（`main.py:1153`）QMutex 现有保护 word_data 全部读 / 写路径 | §Common Pitfalls §7 | 若 lock 仅在 worker 写路径生效，_save_word 读路径未加锁 → race condition；MEDIUM |
| A8 | Phase 1 `page_data[i]["pii"]` 契约（`main.py:10644`）与 Phase 3 `word_data[key]["pii"]` 契约语义一致 | §Architecture Patterns Pattern 1 | 若两者契约不一致 → UI / save loop 路径分歧；LOW |
| A9 | Word 文档属性清除范围（D-08）= 6 个 core 字段 + 2 个 app 字段 = 8 字段；与 Phase 2 PDF 5 字段语义对齐 | §Standard Stack / §Code Examples | 若用户希望清更多字段（如 comments / category）→ D-08 范围扩展；LOW |
| A10 | 候选列表（UX-01 / UX-02 极简版）= 50 条分页 + entity_type + 来源筛选三维度；不实现 Phase 7 完整版 | §Claude's Discretion / §Code Examples | 若用户希望 Phase 3 即有实体类型开关 / 白名单 / 撤销栈 → 升级到 Phase 7 范围；LOW（Phase 7 独立 phase） |

**If this table is empty:** All claims verified or cited — no user confirmation needed.

---

## Open Questions

1. **Word 文档属性清除范围（D-08）= 8 字段是否需要扩展？**
   - What we know: ROADMAP §Phase 3 Success Criterion 4 仅写 "no longer contains the original sensitive text in its body or document properties"，未指定具体字段名
   - What's unclear: 是否需要清 `docProps/custom.xml`（用户自定义属性） / `comments.xml`（批注）
   - Recommendation: **保持 D-08 8 字段**（core 5 + revision 1 + app 2 = 8 字段），与 Phase 2 PDF 5 字段语义对齐；`comments.xml` 在 Phase 4 / 7 视实际需要扩展

2. **`word_data[key]["pii"]` 与 Phase 1 `page_data[i]["pii"]` 命名契约对齐是否破坏 PII 通道独立性？**
   - What we know: 两者都用 `"pii"` 字符串键（D-18）；Phase 1 PDF 与 Phase 3 Word 走不同 adapter 但写入同一名字的 PII 通道
   - What's unclear: 是否会引发 Phase 1 PDF 路径与 Phase 3 Word 路径的 PII 通道在 `page_data` / `word_data` 切换时丢失
   - Recommendation: **保持命名一致**；两个数据结构在 main.py 不同生命周期阶段使用（`_open_pdf` 走 page_data；`_open_word_docx` 走 word_data），无交叉

3. **`WordPIIWorker` 内部 `engine.detect` 是否需要 `_word_data_lock` 保护？**
   - What we know: worker 调 `engine.detect` 时只读 `word_data[key]["text"]`；主线程在 `_on_word_pii_page_result` 写 `word_data[key]["pii"]` 加锁
   - What's unclear: worker 读 `text` 时若主线程正打开新文件（`word_data = {}` 重置）是否触发 `RuntimeError: dictionary changed size`
   - Recommendation: **主线程 `_open_word_docx` 在启动 worker 前加锁** `with QMutexLocker(self._word_data_lock): self.word_data = {}`；worker 内部读 text 时**不**加锁（短临界区）

4. **`data-key` 同步验证（D-22）的边界：mammoth 输出 HTML 包含 `<table>` 嵌套层级时，`<td>` 与 `<p>` 的 `data-key` 优先级？**
   - What we know: 既有 `_add_data_key_attributes`（`main.py:12236-12277`）按 target_tags 顺序匹配（p → td → th → li → span → div → h1-6 → a），先 p 后 td
   - What's unclear: 表格 cell 内含 `<p>` 时，`paragraph_*` key 与 `table_*_cell_*` key 应优先哪个？
   - Recommendation: **`table_*_cell_*` 优先**（更具体）；`_add_data_key_attributes` 顺序改为先 td 后 p

5. **`_save_word` 紧邻 `new_doc.save(fname)` 前调 `clear_word_doc_props` 是否会触发 `core_properties` 写入路径异常？**
   - What we know: python-docx `core_properties` 写入是 docx zip 内 `docProps/core.xml`；`save()` 时序列化
   - What's unclear: `clear_word_doc_props` 修改 `core_properties` 后 `save()` 是否会触发 `core.xml` schema validation 失败
   - Recommendation: **本机验证** `python3 -c "from docx import Document; d = Document(); d.core_properties.title = ''; d.core_properties.author = ''; d.save('/tmp/x.docx'); d2 = Document('/tmp/x.docx'); print(d2.core_properties.title, d2.core_properties.author)"` 必须成功

6. **`merge_word_matches_with_priority` 新增 `pii_matches` 第四参数在 `tests/test_batch_word_replace.py` 等既有测试中可能不传 → 是否需要更新既有测试？**
   - What we know: 既有测试 `test_batch_word_replace` / `test_word_replace_rules` 不传 `pii_matches`；新增参数有默认值 `None`
   - What's unclear: 既有测试是否隐式依赖 `pii_matches=None` 行为
   - Recommendation: **不需要更新**；默认 `None` 走 `pii_matches = pii_matches or []` 保持原行为

7. **`WebCandidateDialog`（极简版）的 `PAGE_SIZE = 50` 是否合理？**
   - What we know: ROADMAP §Phase 3 Success Criterion 3 写 "paginates when over 50 entries"
   - What's unclear: 50 条 / 页是否足够？Phase 7 完整版可能调整
   - Recommendation: **50 条** 锁定（D-25）；Phase 7 完整版可调整

8. **`build_fake_docx` 是否需要覆盖表格内的 PII（`table_*_cell_*` key 路径）？**
   - What we know: `build_fake_docx(tables=...)` 已支持表格
   - What's unclear: 单元测试是否需覆盖 `redact_word("table_0_cell_1_2", merged)` 路径
   - Recommendation: **`test_redact_table_cell_pii` 覆盖**；不覆盖则 PII 表格 cell 路径无回归保护

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `python-docx` | Word 文档读 / 写（paragraphs + tables + core_properties） | ✓ | 项目固定 | — |
| `mammoth` | DOCX→HTML 转换（双栏预览） | ✓ | 项目固定 | — |
| `bs4` (BeautifulSoup) | HTML 解析（data-key 注入 / 局部 patch） | ✓ | 项目固定 | — |
| `PyQt6` | QThread / QMutex / QWebEngineView / runJavaScript | ✓ | 6.10.2 | — |
| `PyMuPDF` (fitz) | Phase 1/2 PII 引擎（无 Word 路径） | ✓ | 1.28.2 | — |
| `python-docx` `app_properties` | D-24 app 字段清除 | 视版本而定 | — | 跳过 app 字段（仅清 core 6 字段） |
| `PIIEngine` 9 类 PII | Phase 3 全部 9 类必须 visible | ✓ | Phase 2 沿用 | — |
| `main.py:replace_matches_in_paragraph` | D-23 真脱敏 wrapper | ✓ | `main.py:965` | — |
| `main.py:_word_data_lock` (QMutex) | D-09 / D-18 并发安全 | ✓ | `main.py:1153` | — |
| `mammoth` inline 元素嵌入 | D-22 data-key 同步 | ✓ | 项目固定 | `_add_data_key_regex_fallback`（已有） |
| `mammoth` `<table>` 嵌套 `<p>` | D-22 cell 优先 | ✓ | 项目固定 | `_add_data_key_regex_fallback`（已有） |

**Missing dependencies with no fallback:**
- 无（核心栈全部已就绪；Phase 3 沿用 Phase 1/2 既有依赖）

**Missing dependencies with fallback:**
- `python-docx app_properties` 部分版本只读：fallback = 跳过 app 字段（仅清 core 6 字段；与 Phase 2 PDF 5 字段语义对齐）

**Skip condition for environment probe:** 不适用（Phase 3 全部依赖已逐项检查）

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `unittest` (Python stdlib) — 沿用 Phase 1 79/79 基线 |
| Config file | 无独立配置（`unittest` 自动发现） |
| Quick run command | `python3 -m unittest tests.unit.test_word_pii_pipeline -v` |
| Full suite command | `python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_package_imports tests.unit.test_pdf_text_hit_dedup tests.unit.test_app_config tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety tests.unit.test_convergence tests.unit.test_word_pii_pipeline -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FMT-02 (auto-trigger) | 打开 Word 自动检测 PII | integration | `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIAutoTrigger -v` | ❌ Wave 0 |
| FMT-02 (data-key 同步) | mammoth 渲染后 DOM data-key 数 == word_data key 数 | integration | `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordDataKeySync -v` | ❌ Wave 0 |
| FMT-02 (PII 真脱敏) | redact_word 后 para.text 不含原文 + 含 mask 字符串 | integration | `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordRedactRoundTrip -v` | ❌ Wave 0 |
| FMT-02 (文档属性清除) | clear_word_doc_props 后 5 core 字段 == "" | integration | `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordDocumentPropertiesCleared -v` | ❌ Wave 0 |
| FMT-02 (priority pii > manual) | pii 覆盖 manual | unit | `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordMergePriorityRulePiManualOcr -v` | ❌ Wave 0 |
| UX-01 (候选列表) | WordCandidateDialog 显示 PII 命中 | unit | `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialog -v` | ❌ Wave 0 |
| UX-02 (分页 + 筛选) | > 50 条分页 + entity_type 筛选 | unit | `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination -v` | ❌ Wave 0 |
| OPS-07 (基线门禁) | 79/79 + 新增测试全部通过 | integration | 完整命令 | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 -m unittest tests.unit.test_word_pii_pipeline -v`（快速反馈 Word 端到端）
- **Per wave merge:** `python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence -v`
- **Phase gate:** Full suite 绿色（基线从 79/79 升级为 86/86 或 88/88）→ `/gsd-verify-work` → `git tag`

### Wave 0 Gaps

- [ ] `tests/fixtures/fake_word.py` NEW: `build_fake_docx()` 合成含 PII 的 docx（D-26）
- [ ] `privacyguard/word/__init__.py` NEW: 懒加载 `_LAZY_IMPORTS`（D-06）
- [ ] `privacyguard/word/adapter.py` NEW: `WordAdapter.collect_units`（D-04 / D-17）
- [ ] `privacyguard/word/worker.py` NEW: `WordPIIWorker` QThread（D-09）
- [ ] `privacyguard/word/redact.py` NEW: `redact_word` wrapper（D-23）
- [ ] `privacyguard/word/clear_doc_props.py` NEW: `clear_word_doc_props`（D-24）
- [ ] `privacyguard/word/candidate_dialog.py` NEW: `WordCandidateDialog`（D-25 / UX-01 / UX-02）
- [ ] `main.py:_open_word_docx`（line 10777）MODIFY: 自动启动 `WordPIIWorker`（D-09）
- [ ] `main.py:_on_word_pii_page_result` NEW: pii_signal 接收槽（D-09 / D-18）
- [ ] `main.py:merge_word_matches_with_priority`（line 863）MODIFY: 新增 `pii_matches` 第四参数（D-19）
- [ ] `main.py:_save_word`（line 12699）MODIFY: 调 `redact_word` + `clear_word_doc_props`（D-23 / D-24）
- [ ] `privacyguard/__init__.py` MODIFY: `_LAZY_IMPORTS` 追加 `WordAdapter` / `redact_word` / `clear_word_doc_props` / `WordCandidateDialog`（D-06）
- [ ] `tests/unit/test_word_pii_pipeline.py` NEW: 8 个测试类（D-13）
- [ ] `packaging/windows/config/PrivacyGuard_windows.spec` MODIFY: `hiddenimports` 段追加 `privacyguard.word.*`（cp30 教训）
- [ ] `packaging/macos/config/PrivacyGuard.spec` MODIFY: 同上 parity

---

## Security Domain

> Phase 3 触发 `config.json.workflow.security_enforcement = true` (default). ASVS Level 1 per `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | 应用无用户账号 / 无 token / 无远程端点 |
| V3 Session Management | no | 单进程桌面应用，会话即进程生命周期 |
| V4 Access Control | partial | 文件路径安全由 `privacyguard/utils/security.py::validate_safe_path` 守护；Phase 3 沿用 |
| V5 Input Validation | yes | docx 路径校验（既有）+ 文本输入经 `normalize_digits` / `flatten_for_match` 归一化；Word adapter 输入防御性（非字符串 → 空） |
| V6 Cryptography | no | 无加密需求；Faker 合成 PII 不构成「个人数据」保护范围（OPS-05） |
| V7 Error Handling | partial | Worker 异常经 `error_signal` 暴露；Word adapter 模块防御性（非 docx 文件 → 空 list） |
| V9 Logging | partial | 项目用 `print()` 而非日志框架；Word adapter 模块不打印命中原文；仅打印 `[Word PII] 命中 N 项敏感内容`（命中数，不打印内容） |
| V12 Files and Resources | yes | 临时目录走 `TempFileManager`；Phase 3 沿用；PyInstaller `datas` + `hiddenimports` 同步声明（cp30 教训扩展到 `privacyguard.word.*`） |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Word 文档含恶意 XML 炸弹 | Denial of Service | python-docx 解析时 `lxml` 限制 + 临时文件大小检查 |
| Word run-level 替换残留原文片段 | Information Disclosure | `replace_matches_in_paragraph` 既有跨 run 边界处理 + 单元测试 `test_run_boundary_18digit_split_across_3_runs` |
| Word 文档属性泄漏 | Information Disclosure | `clear_word_doc_props` 清除 5 core + 2 app 字段；`tests/unit/test_word_pii_pipeline.TestWordDocumentPropertiesCleared` 反向断言 |
| `_word_data_lock` 未保护 | Information Disclosure (race) | QMutex 严格加锁；`test_word_pii_lock_concurrent_writes` 覆盖 |
| PII 命中原文进入 stdout / stderr | Information Disclosure | Word adapter 模块不打印命中原文；仅打印命中数 |
| 候选列表 PII 原文在 UI 显示 | Information Disclosure | `WordCandidateDialog` 显示 `hit.normalized[:30]`（截断 30 字符） |
| PyInstaller `privacyguard.word.*` 模块缺失 | Denial of Service | `packaging/{windows,macos}/config/*.spec` `hiddenimports` 同步追加（cp30 教训） |
| `core_properties.revision` 置空字符串触发 ValueError | Information Disclosure | `clear_word_doc_props` 单独处理：`revision = 1`（整数默认值） |

---

## Sources

### Primary (HIGH confidence)

- `main.py:863-1018` — `merge_word_matches_with_priority` / `apply_range_to_runs` / `replace_matches_in_paragraph`（既有 run-level 替换 API）
- `main.py:10777-10819` — `_open_word_docx` 段落 + 表格初始化路径
- `main.py:1153` — `_word_data_lock = QMutex()`（既有 word_data 线程安全锁）
- `main.py:11602-11616` — QMutexLocker 既有使用形态
- `main.py:12236-12277` — `_add_data_key_attributes`（BeautifulSoup data-key 注入）
- `main.py:12283-12329` — `_add_data_key_regex_fallback`（data-key 注入后备）
- `main.py:12699-12794` — `_save_word` 既有 save loop（Phase 3 扩展位）
- `main.py:471-...` — `build_word_panel_update_script`（cp27 局部 patch JavaScript 模板）
- `main.py:12000-12005` — `_apply_word_panel_updates`（既有 runJavaScript 局部 patch 入口）
- `privacyguard/pii/hits.py:15-27` — `PIIHit` dataclass（D-05 字段锁 + Phase 1 已生产验证）
- `privacyguard/pii/engine.py:103-211` — `PIIEngine.detect`（format-agnostic 入口）
- `privacyguard/pii/mask.py` — `mask_for_entity`（Phase 2 9 类 partial mask 既有）
- `privacyguard/pii/pdf_adapter.py:297-314` — `clear_pdf_metadata`（Phase 2 SAFE-03 形态镜像参考）
- `privacyguard/pii/__init__.py:69-119` — `__getattr__` + `_LAZY_IMPORTS`（OPS-03 懒加载范本）
- `CLAUDE.md` §当前已具备的能力 + §版本号单一来源 + §当前生效的配置路径
- `.planning/STATE.md` §Decisions + §Open Questions
- `.planning/ROADMAP.md` §Phase 3 + §Traceability

### Secondary (MEDIUM confidence)

- `.planning/phases/01-pdf/01-VERIFICATION.md` — Phase 1 16/16 must-haves 验证范本（D-05 / D-13 字段锁 / 测试基线门禁）
- `.planning/phases/02-pdf/02-RESEARCH.md` — Phase 2 研究范本（D-04 / D-13 / D-23 字段锁 + clear_pdf_metadata 镜像参考）
- `.planning/phases/02-pdf/02-PATTERNS.md` — Phase 2 模式映射（D-05 v37.7.6 收敛原则 + lazy-load 范本）
- `tests/unit/test_word_replace_rules.py` — 既有 Word replace 单元测试范本
- `tests/unit/test_batch_word_replace.py` — 既有 Word batch replace 单元测试范本
- `packaging/windows/config/PrivacyGuard_windows.spec` + `packaging/macos/config/PrivacyGuard.spec` — 既有 PyInstaller spec（cp30 教训）

### Tertiary (LOW confidence)

- python-docx 官方文档 — `core_properties` / `app_properties` API 行为（本机 2026-08-12 待补完整验证）
- mammoth 官方文档 — DOCX→HTML 转换行为（项目固定版本；Phase 3 沿用）
- PyMuPDF 1.28.2 元数据清除 5 字段语义（Phase 2 既有；Phase 3 沿用形态镜像）

---

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — 9 类 PII 引擎、word_data 契约、`replace_matches_in_paragraph` 全部 Phase 1/2 已生产验证
- Architecture: **HIGH** — 严格沿用 Phase 1/2 PII 引擎 + Phase 2 模式（adapter / redact / clear_props 三件套）
- Pitfalls: **MEDIUM** — Word run-boundary / data-key 同步 / app_properties 版本差异需本机验证；其余高

**Research date:** 2026-08-12
**Valid until:** 2026-09-12 (30 天稳定窗口；Phase 3 范围窄 + 复用 Phase 1/2 既有架构)

