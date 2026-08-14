---
phase: 03-word
plan: 02
slug: engine-expansion-and-ui
type: execute
wave: 2
depends_on:
  - 03-01
files_modified:
  - privacyguard/word/candidate_dialog.py
  - main.py
  - tests/unit/test_word_pii_pipeline.py
autonomous: false
requirements:
  - FMT-02
  - UX-01
user_setup: []

estimate:
  tokens: 70000
  raw_tokens: 35000
  tasks: 3
  confidence: medium

must_haves:
  truths:
    # E1 — 左栏 <mark class="pii-highlight"> (7 covered rows from 03-UI-SPEC.md lines 392-403)
    - "E1 covered·empty：hits == [] 时 _apply_word_pii_panel_updates return early；左栏显示原文无 mark；status chip → '扫描完成：未发现敏感内容'"
    - "E1 covered·loading：_open_word_docx 完成与 WordPIIWorker 首次 emit 间的窗口期内左栏显示纯文本；status chip 处理 loading copy"
    - "E1 covered·error：WordPIIWorker.run() 异常被 _on_word_pii_scan_error 捕获；status chip → error Copywriting 行；左栏无 mark 注入"
    - "E1 covered·populated：每个 PII hit 包裹 <mark class=\"pii-highlight\" data-entity-type=\"...\" title=\...><span class=\"pii-tag\">CODE</span>{original}</mark>；cursor help 显示浏览器原生 tooltip"
    - "E1 covered·partial：N 个相邻 hit 中部分 mask / 部分不 mask；相邻 hit 独立渲染；CSS 不强制最大密度"
    - "E1 covered·zero-one-many：1 个 PII hit = 1 mark + 1 span；N 个 = N × 2 inline 元素；WebEngineView scroll 自动处理"
    - "E1 covered·long-text：5,000+ 字符段落含 PII hit；cursor 累加 offset += hit.page_length 保证 HTML 良构；tooltip bounded ~30 chars"
    # E2 — 右栏 <mark class="pii-mask"> (7 covered rows from 03-UI-SPEC.md lines 406-417)
    - "E2 covered·empty：hits == [] 时右栏显示纯文本无 mark；既有 replaced-preview 渲染处理 no-hit 场景"
    - "E2 covered·loading：右栏渲染同步经 web_view.setHtml() 完成 preview load；mask patch 增量经 cp27；无额外占位 chrome"
    - "E2 covered·error：worker 错误时右栏保留最后应用的 mask 状态；无新错误表面；左栏 wordPiiStatusChip 错误 copy 覆盖"
    - "E2 covered·populated：每个 PII hit 被替换为 <mark class=\"pii-mask\" data-entity-type=\"...\" title=\...>{mask_strategy}</mark>；mark 仅包裹 mask 字符串（不包裹原文）"
    - "E2 covered·partial：pii + manual 重叠 hit 时 merge logic（D-19）解析 priority；每重叠区域仅 highest-priority mask 字符串注入"
    - "E2 covered·overflow：右栏 #0FA968@alpha 0.12 (light) / #34D399@alpha 0.18 (dark) 故意低对比 tint 与 #FFFFFF / #1E2836 背景；50 连续 mark 无 scrollbar-style overflow"
    - "E2 covered·zero-one-many：mask 字符串长度 bounded（最长 110101********1234 = 18 chars / mask_for_entity）；100 连续 mark = 1,800 chars 远低于 HTML 阈值"
    # General PII panel contract
    - "_apply_word_pii_panel_updates 走 web_view.page().runJavaScript(\"updateBlock(...)\") 局部 patch；左栏注入 <mark class=\"pii-highlight\"> 包裹原文 + <span class=\"pii-tag\">CODE</span> 短码徽章；右栏注入 <mark class=\"pii-mask\"> 包裹 partial mask 字符串（per D-10 / cp27 增量 patch 锁定）"
    - "左右双栏 PII 高亮通过 cp27 局部 patch 注入，**禁止** 触发整页 web_view.setHtml(...)；TestWordPIIPanelHighlights 断言 web_view.page().runJavaScript 被调 + web_view.setHtml 未被调（per cp27 + D-10 反向断言）"
    - "_build_pii_block_fragment 按 hit.page_offset 排序 + cursor 累加构造 data-key block 内 HTML 片段；左栏 HTML 形态严格匹配 <mark class=\"pii-highlight\" data-entity-type=\"...\" title=\"...\"><span class=\"pii-tag\">CODE</span>{原文}</mark>（per D-21 + 03-UI-SPEC §Visuals）"
    - "_build_pii_mask_block_fragment 构造右栏 partial mask 片段；形态严格 <mark class=\"pii-mask\" data-entity-type=\"...\" title=\"已替换为：{mask_strategy literal}\">{mask_strategy}</mark>（per 03-UI-SPEC §Visuals §PII Partial-Mask）"
    - "main.py:_on_word_pii_page_result 写 word_data[key][\"pii\"] 后**同步**触发 _apply_word_pii_panel_updates；UI 双栏在 worker emit 后 < 200ms 内完成局部 patch（per D-09 / D-10）"
    - "PII 短码徽章 9 个固定值：ID / PHONE / BANK / EMAIL / USCC / TAX / TAX15 / VAT / ACCT；ENTITY_TYPE_SHORT_CODE 字典唯一来源位于 privacyguard/pii/hits.py（per BLOCKER 5 + D-21 单一来源锁）；main.py 与 privacyguard/word/candidate_dialog.py 均从此 import"
    - "现有基线测试保持通过 + 新增 TestWordPIIPanelHighlights 全部 GREEN（per OPS-07 baseline preservation）"
  artifacts:
    - privacyguard/word/candidate_dialog.py NEW — WordCandidateDialog QDialog 占位骨架（Wave 3 完整 UI 行为）
    - main.py MODIFY — _apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + 改进 _on_word_pii_page_result 真实 body（QMutexLocker 写 + 触发 _apply_word_pii_panel_updates） + _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 把 pii 通道纳入合并路径
    - tests/unit/test_word_pii_pipeline.py MODIFY — 新增 TestWordPIIPanelHighlights 测试类（4 个测试方法）
  key_links:
    - "_on_word_pii_page_result (Wave 1 + Wave 2 接线) 到 _apply_word_pii_panel_updates (Wave 2 落地) 到 web_view.page().runJavaScript(build_word_panel_update_script(block_updates)) (main.py:471 cp27 既有形态)"
    - "build_word_panel_update_script (main.py:471 既有 cp27 helper) —— Wave 2 复用既有局部 patch JavaScript 模板，不重写"
    - "_build_pii_block_fragment 到 ENTITY_TYPE_SHORT_CODE 字典 (privacyguard/pii/hits.py 单一来源 — per BLOCKER 5 + D-21 锁)"
    - "_build_pii_mask_block_fragment 到 PIIHit.mask_strategy 字段（mask_for_entity 已生产 —— Phase 2 MASK-01）"
    - "WordCandidateDialog 占位骨架到 Wave 3 完整 UI 行为（UX-01 / UX-02 落地）"
  prohibitions:
    - "不得在 PII 高亮路径调 web_view.setHtml(...)；必须走 web_view.page().runJavaScript(\"updateBlock(...)\") 局部 patch（per D-10 / cp27 硬约束）"
    - "不得重写 build_word_panel_update_script（cp27 既有 helper，main.py:471）；Wave 2 仅复用既有 script 模板"
    - "不得引入 PII 短码字典的第二个来源；ENTITY_TYPE_SHORT_CODE 必须位于 privacyguard/pii/hits.py 单一字典（per BLOCKER 5 + D-21 锁）"
    - "不得让 _apply_word_pii_panel_updates 在 hits 为空 list 时仍触发 runJavaScript；空 list 走早返（per 03-RESEARCH.md:1269 early return）"
    - "不得让左栏 <mark class=\"pii-highlight\"> 与右栏 <mark class=\"pii-mask\"> 互相覆盖 / 串色 —— 左红右绿（partial-mask 调色）严格视觉区分（per 03-UI-SPEC §Color）"
    - "不得让 _build_pii_block_fragment 使用 hit.mask_strategy 写到左栏；左栏包裹原文（hit.normalized 截取 page_offset:page_offset+page_length），**不**写 mask 字符串（per 03-UI-SPEC §Visuals §PII Highlight 锁定）"
    - "不得让 _build_pii_mask_block_fragment 把原文写到右栏；右栏**只**写 mask 字符串（hit.mask_strategy），**不**包裹原文（per 03-UI-SPEC §Visuals §PII Partial-Mask 锁定）"
    - "不得在 privacyguard/word/candidate_dialog.py 包级 eager import PyQt6.QtWidgets；保持 _LAZY_IMPORTS + 函数内 import（per D-06 / OPS-03）"
  backstop_statements:
    - statement: "在 720p / 100% DPI 下，8+ 个连续 PII 命中在左栏保持视觉可区分（mark + pii-tag badge 不重叠 / 不溢出）"
      verification: backstop
    - statement: "右栏 <mark class='pii-mask'> 的 tooltip（已替换为：{mask_strategy literal}）在 720p 视口下 light + dark 双主题均不溢出"
      verification: backstop

---

## Artifacts this phase produces

> 单一来源的 artifacts 清单 —— 与上方 `files_modified` 字段、`<tasks>` 内 `<files>` 列表以及 `<output>` 声明字段级一致。

**NEW 文件（1 项）：**
1. `privacyguard/word/candidate_dialog.py` — WordCandidateDialog QDialog 占位骨架（Wave 3 完整 UI 行为；本波仅骨架）

**MODIFY 文件（2 项）：**
2. `main.py` — 新增 _apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + 改进 _on_word_pii_page_result 真实 body（QMutexLocker 写 + 触发局部 patch）+ _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 把 pii 通道纳入合并路径
3. `tests/unit/test_word_pii_pipeline.py` — 追加 TestWordPIIPanelHighlights 测试类（4 个测试方法）

**不修改（per BLOCKER 7 修正 — Wave 1 已就位，本 plan 不重复）：**
- `privacyguard/word/__init__.py` — Wave 1 已就位 _LAZY_IMPORTS + 5 项 lazy forward；本波不修改
- `privacyguard/__init__.py` — Wave 1 已就位 _LAZY_IMPORTS 6 项；本波不修改
- `privacyguard/pii/hits.py` — Wave 1 已就位 ENTITY_TYPE_SHORT_CODE 字典；本波仅 import 引用

---

## Decision Coverage (D-01..D-26)

> 本 plan 实施 / 继承 / 不触达的 D-XX 决策。

| D-ID | Status | Task Reference | 备注 |
|------|--------|----------------|------|
| D-01 | inherited | 全 plan 引用 ROADMAP Phase 3 范围 | 范围锁 |
| D-02 | inherited | 复用 Phase 1/2 PII 引擎；不在此 plan 引入新引擎 | 架构锁 |
| D-03 | inherited | Wave 1 已落 D-17 入口 | Phase 1/2 就位 |
| D-04 | **preserve** | word_data[key]["pii"] 通道 Wave 1 已落 | Wave 1 实施 |
| D-05 | **preserve + extend** | 不在 main.py 内联 PII 高亮 / mask 生成逻辑；新代码 Wave 1 已就位 | v37.7.6 收敛原则 |
| D-06 | **preserve** | privacyguard/word/__init__.py _LAZY_IMPORTS Wave 1 已就位 | OPS-03 锁 |
| D-07 | **preserve** | cp27 增量 DOM patch 既有路径 | D-10 锁 |
| D-08 | **inherited** | clear_word_doc_props 8 字段锁 Wave 1 已落 | Wave 1 实施 |
| D-09 | **implement** | Task 2: _on_word_pii_page_result 真实 body（QMutexLocker 写 word_data + 触发 _apply_word_pii_panel_updates） | auto-trigger |
| D-10 | **implement** | Task 2: _apply_word_pii_panel_updates 严格走 cp27 局部 patch；TestWordPIIPanelHighlights 断言 runJavaScript 被调 + setHtml 未被调 | cp27 锁 |
| D-11 | **inherited** | 候选审阅 UI 极简版 = Wave 3 完整实施范围 | 范围锁 |
| D-12 | **inherited** | 不引入新 PyPI 依赖 | 依赖锁 |
| D-13 | **implement** | Task 1 + Task 2: TestWordPIIPanelHighlights 4 个测试方法 | ≥ 1 新测试类 |
| D-14 | **preserve** | 既有 11 unittest 模块基线保持 GREEN | OPS-07 门禁 |
| D-15 | **preserve** | 9 类 entity 沿用 Phase 2；不新增 entity_type | Phase 1/2 范围 |
| D-16 | **preserve** | PIIHit 9 字段锁；page_rect Word 占位 (0,0,0,0) | D-05 / ENGINE-02 锁 |
| D-17 | **preserve** | TextUnit 入口 Wave 1 已就位 | engine.detect 入口 |
| D-18 | **implement** | Task 2: _on_word_pii_page_result 槽 QMutexLocker 写 word_data[key]["pii"] | 三通道 |
| D-19 | **preserve** | merge_word_matches_with_priority 扩展 Wave 1 已落 | D-19 priority |
| D-20 | **preserve + extend** | PII 红框 #D64545 / #FF6B6B 既有；本 plan 实施 HTML mark + pii-tag | 颜色锁 |
| D-21 | **implement** | Task 2: ENTITY_TYPE_SHORT_CODE 字典从 privacyguard/pii/hits.py import（per BLOCKER 5 单一来源） | 单一来源 |
| D-22 | **preserve** | data-key 注入复用既有 helper；不重写 | cp27 既有 |
| D-23 | **inherited** | redact_word wrapper Wave 1 已落；本 plan 不涉及 | Wave 1 实施 |
| D-24 | **inherited** | clear_word_doc_props 位置 Wave 1 已落 | Wave 1 实施 |
| D-25 | **inherited** | WordCandidateDialog 极简版 = Wave 3 完整实施范围 | D-11 范围 |
| D-26 | **inherited** | build_fake_docx Wave 1 已落 | Wave 1 实施 |

---

<objective>
落地 Phase 3 双栏 PII 高亮 + mask 显示的 cp27 增量 DOM patch 契约：左栏红框 `<mark class="pii-highlight">` + 短码徽章 `<span class="pii-tag">`；右栏绿调 `<mark class="pii-mask">` partial mask。WordCandidateDialog 占位骨架（完整 UX-01 / UX-02 行为 Wave 3 落地）。所有变更严格遵守 cp27（禁止整页 `setHtml`）+ D-10 + D-21 短码字典单一来源（per BLOCKER 5 抽离 main.py 到 privacyguard/pii/hits.py）。
</objective>

<purpose>
Phase 3 用户故事的核心是「打开 Word 文档，敏感候选在双栏对比预览的左右两侧同时高亮」。Wave 1 落地了 PII 引擎接入 + 真脱敏 + 文档属性清除，但 UI 层面双栏还没有 PII 高亮显示 —— Wave 2 把 cp27 增量 DOM patch 落地到 PII 路径。同时为 Wave 3 的候选审阅对话框提供占位骨架，避免 main.py 引用不存在的符号导致 import-time 错误。
</purpose>

<output>
- main.py MODIFY：新增 _apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + 改进 _on_word_pii_page_result 调用 _apply_word_pii_panel_updates；改进 _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 把 pii 通道纳入合并路径
- privacyguard/word/candidate_dialog.py NEW：WordCandidateDialog QDialog 占位骨架（Wave 3 完整实施）
- tests/unit/test_word_pii_pipeline.py MODIFY：新增 TestWordPIIPanelHighlights 测试类（4 个测试方法）
</output>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-word/03-RESEARCH.md
@.planning/phases/03-word/03-PATTERNS.md
@.planning/phases/03-word/03-UI-SPEC.md
@.planning/phases/03-word/03-VALIDATION.md
@.planning/phases/03-word/03-01-tracer-PLAN.md
@CLAUDE.md
@privacyguard/pii/hits.py (PIIHit 9 字段锁 — D-16 + ENTITY_TYPE_SHORT_CODE 9 短码字典 — D-21 单一来源 per BLOCKER 5)
@main.py:471 (build_word_panel_update_script — cp27 既有 helper)
@main.py:10777-10819 (_open_word_docx — Wave 1 接线)
@main.py:11508 (_on_pii_page_result Phase 1 page_data 镜像)
@main.py:11940-12005 (_build_word_original_panel_updates + _build_word_replaced_panel_updates + _apply_word_panel_updates — 既有 cp27 形态)
@main.py:12699-12794 (_save_word — Wave 1 接线)
</context>

<tasks>

<task type="auto" tdd="true">
  <name>RED — 写 TestWordPIIPanelHighlights 测试，断言 cp27 增量 patch 契约 + 短码徽章 + partial mask 渲染</name>
  <files>
    - tests/unit/test_word_pii_pipeline.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-UI-SPEC.md (lines 174-247 — 左栏 <mark class="pii-highlight"> + 短码徽章 + 右栏 <mark class="pii-mask"> 完整 HTML 形态契约)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 312-327 — D-08 文档属性清除 8 字段锁 + 视觉契约)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1264-1304 — _apply_word_pii_panel_updates + _build_pii_block_fragment 完整代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 833-846 — Pitfall 9 整页 setHtml 触发重渲染破坏 cp27)
    - .planning/phases/03-word/03-VALIDATION.md (lines 41-65 — Per-Task Verification Map 03-02-01/02)
    - main.py:11940-12005 (_build_word_original_panel_updates + _apply_word_panel_updates 既有 cp27 形态 — Wave 2 镜像)
    - main.py:471 (build_word_panel_update_script — cp27 既有 JavaScript 模板)
    - privacyguard/pii/hits.py (PIIHit dataclass + ENTITY_TYPE_SHORT_CODE 9 短码字典 — 字段顺序锁 + page_rect Word 路径置占位 (0,0,0,0))
    - privacyguard/pii/mask.py (mask_for_entity — Phase 2 MASK-01 锁)
    - tests/unit/test_word_pii_pipeline.py (Wave 1 既有 5 个测试类 — 范本)
  </read_first>
  <action>
    在 tests/unit/test_word_pii_pipeline.py 追加 TestWordPIIPanelHighlights 测试类。本本任务**只写测试**，主代码占位由 Wave 2 GREEN 任务实施。

    **TestWordPIIPanelHighlights 测试类**（含 4 个测试方法）：

    **test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml**：构造 minimal QApplication (QApplication([]) 或 unittest.mock.Mock)；构造 minimal MainWindow-like 桩：class _StubMainWindow 含 self.word_data = {"paragraph_5": {"text": "身份证 53010219200508011X 末位", "ocr": [], "manual": [], "pii": []}}；self.word_preview = Mock(spec=QWebEngineView)；self.word_preview_replaced = Mock(spec=QWebEngineView)。构造 hits = [PIIHit(entity_type='CN_ID_CARD', page_offset=4, page_length=18, page_rect=(0,0,0,0), confidence_tier='HIGH', source='text', mask_strategy=mask_for_entity('CN_ID_CARD', '53010219200508011X'), normalized='53010219200508011X')]。从 main import _apply_word_pii_panel_updates；调 stub._apply_word_pii_panel_updates(key='paragraph_5', hits=hits)。断言 stub.word_preview.page().runJavaScript.assert_called()（cp27 走局部 patch）；断言 stub.word_preview.setHtml.assert_not_called()（cp27 锁定禁止整页 setHtml）；断言 stub.word_preview_replaced.page().runJavaScript.assert_called()（左右双栏均走 runJavaScript）；断言 stub.word_preview_replaced.setHtml.assert_not_called()。

    **test_build_pii_block_fragment_contains_short_code_badge**：构造 key = "paragraph_5"；text = "身份证 53010219200508011X 末位"；hits 同上。从 main import _build_pii_block_fragment；构造 stub 含 self.word_data = {"paragraph_5": {"text": text, "ocr": [], "manual": [], "pii": []}}；fragment = stub._build_pii_block_fragment(key, hits)。断言 '<mark class="pii-highlight"' in fragment（HTML 元素名锁定）；断言 'data-entity-type="CN_ID_CARD"' in fragment（entity_type 属性锁定）；断言 '<span class="pii-tag">ID</span>' in fragment（短码徽章锁定 —— D-21 + per BLOCKER 5 从 privacyguard/pii/hits.py 单一来源 import）；断言 '53010219200508011X' in fragment（原文包裹）；断言 mask_for_entity('CN_ID_CARD', '53010219200508011X') not in fragment（**左栏不含 mask 字符串** —— Visuals §PII Highlight 锁定）。

    **test_build_pii_mask_block_fragment_contains_mask_string_not_original**：构造 key = "paragraph_5"；text = "身份证 53010219200508011X 末位"；hits 同上。从 main import _build_pii_mask_block_fragment；stub 同上；fragment = stub._build_pii_mask_block_fragment(key, hits)。断言 '<mark class="pii-mask"' in fragment（HTML 元素名锁定）；断言 'data-entity-type="CN_ID_CARD"' in fragment；断言 mask_for_entity('CN_ID_CARD', '53010219200508011X') in fragment（**右栏包裹 mask 字符串** —— Visuals §PII Partial-Mask 锁定）；断言 '已替换为：' in fragment（title 属性前缀锁定）；断言 '53010219200508011X' not in fragment（**右栏不含原文** —— Visuals §PII Partial-Mask 锁定）。

    **test_entity_type_short_code_covers_all_9_locked_types**：从 main import ENTITY_TYPE_SHORT_CODE（或 from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE —— per BLOCKER 5 唯一来源）。断言 set(ENTITY_TYPE_SHORT_CODE.keys()) == {'CN_ID_CARD', 'CN_PHONE', 'CN_BANK_CARD', 'CN_EMAIL', 'CN_USCC', 'CN_TAXPAYER_ID', 'CN_TAXPAYER_ID_15', 'CN_VAT_INVOICE', 'CN_BANK_ACCOUNT'}（9 短码字典全覆盖 —— D-21 锁）。断言 ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'] == 'ID'；'CN_PHONE' == 'PHONE'；'CN_BANK_CARD'] == 'BANK'；'CN_EMAIL' == 'EMAIL'；'CN_USCC' == 'USCC'；'CN_TAXPAYER_ID' == 'TAX'；'CN_TAXPAYER_ID_15' == 'TAX15'；'CN_VAT_INVOICE' == 'VAT'；'CN_BANK_ACCOUNT' == 'ACCT'。**关键**：9 个短码值锁定为 ASCII uppercase（D-21 锁）；不允许出现 '身份证' / 'phone' 等中文或小写。

    实现注意：MainWindow 桩类需要含必需属性，**不继承** MainWindow；通过 stub 实例调用 bound method。建议：直接 `class _StubMainWindow:` 含必需属性；调用 `stub._apply_word_pii_panel_updates(...)`；Mock(spec=QWebEngineView) 自动提供 page() 返回 Mock。

    测试方法标 RED：每个方法末尾用 `self.fail("Wave 2 GREEN 实施后此测试应 pass")` 占位；Wave 2 GREEN 任务移除 self.fail。
  </action>
  <verify>
    <automated>set -o pipefail; python3 -m compileall -q tests/unit/test_word_pii_pipeline.py && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v 2>&1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q tests/unit/test_word_pii_pipeline.py` 退出码 0（语法 GREEN）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v` 显示 4 个测试方法全部 FAIL（AttributeError: module 'main' has no attribute '_apply_word_pii_panel_updates' 或 _build_pii_block_fragment / _build_pii_mask_block_fragment / ENTITY_TYPE_SHORT_CODE）—— RED 基线确认。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v`（含 Wave 1 既有 5 个测试类）显示既有 7 个测试方法保持 GREEN，4 个新测试方法 FAIL（Wave 1 状态未破坏）。
    - 既有 11 unittest 模块基线保持 GREEN（merge_word_matches_with_priority back-compat + lazy-load 纪律保持）。
  </acceptance_criteria>
  <done>
    TestWordPIIPanelHighlights 4 个测试方法 RED 骨架就位；测试方法明确断言 cp27 runJavaScript 契约（runJavaScript 被调 + setHtml 未被调）+ 短码徽章 HTML 形态 + 左栏原文 + 右栏 partial mask + 9 短码字典（per BLOCKER 5 抽离至 privacyguard/pii/hits.py 单一来源）；RED 失败原因可定位到具体 AttributeError。
  </done>
  <reversibility>rating="reversible" rationale="仅测试文件追加；删除 TestWordPIIPanelHighlights 类即可恢复 Wave 1 状态。"</reversibility>
</task>

<task type="auto" tdd="true">
  <name>GREEN — 实现 _apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + 改进 _on_word_pii_page_result + WordCandidateDialog 占位骨架</name>
  <files>
    - main.py
    - privacyguard/word/candidate_dialog.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-UI-SPEC.md (lines 174-247 — 左栏 <mark class="pii-highlight"> + 短码徽章 + 右栏 <mark class="pii-mask"> 完整 HTML 形态契约)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 290-308 — wordPiiStatusChip 状态机)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1264-1304 — _apply_word_pii_panel_updates + _build_pii_block_fragment 完整代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 833-846 — Pitfall 9 整页 setHtml 触发重渲染)
    - .planning/phases/03-word/03-PATTERNS.md (lines 22-23 — WordCandidateDialog 角色范本)
    - main.py:471 (build_word_panel_update_script — cp27 既有 JavaScript 模板)
    - main.py:10777-10819 (_open_word_docx — Wave 1 接线)
    - main.py:11508 (_on_pii_page_result Phase 1 page_data 镜像 — 形态参考)
    - main.py:11940-12005 (_build_word_original_panel_updates + _apply_word_panel_updates — cp27 既有形态)
    - privacyguard/pii/hits.py (PIIHit dataclass + ENTITY_TYPE_SHORT_CODE 9 短码字典 — D-21 单一来源 per BLOCKER 5)
    - privacyguard/pii/mask.py (mask_for_entity — Phase 2 MASK-01 锁)
  </read_first>
  <action>
    Wave 2 GREEN 任务。本任务实施 4 个新增方法 / 函数 + 1 个 QDialog 占位骨架；目标让 TestWordPIIPanelHighlights 4 个测试方法全部 GREEN。

    **main.py 模块顶部新增 ENTITY_TYPE_SHORT_CODE 单一来源 import**（per BLOCKER 5 + D-21 锁；不重新定义字典，仅 import）：模块顶部新增 `from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE`（常驻模块级 import 允许）。**关键**：不要在 main.py 内重新定义 ENTITY_TYPE_SHORT_CODE 字典（per BLOCKER 5 单一来源）；仅 import 引用即可；test_convergence AST 断言 main.py 不内联 9 短码字面量。模块顶部新增 `from html import escape as html_escape`（如未就位；常驻 import 允许）。

    **main.py MainWindow 类新增 4 个方法**（紧邻 _apply_word_panel_updates，约 main.py:12005 之后）：

    (a) `_apply_word_pii_panel_updates(self, key: str, hits: list)`：严格走 cp27 增量 patch（D-10 锁）；不触发整页 setHtml。实现：if not hits: return；block_updates = {key: self._build_pii_block_fragment(key, hits)}（左栏）；replaced_updates = {key: self._build_pii_mask_block_fragment(key, hits)}（右栏）；for view_attr, updates in (('word_preview', block_updates), ('word_preview_replaced', replaced_updates)): view = getattr(self, view_attr, None); if view and not view.isHidden(): script = build_word_panel_update_script(updates); view.page().runJavaScript(script)。**关键**：cp27 既有 build_word_panel_update_script（main.py:471）直接复用，**不**重写 JavaScript 模板。

    (b) `_build_pii_block_fragment(self, key: str, hits: list) -> str`：构造左栏原文高亮 HTML 片段（D-21 + Visuals §PII Highlight 锁）。实现：if key not in self.word_data: return ''；text = self.word_data[key].get('text', '')；sorted_hits = sorted(hits, key=lambda h: h.page_offset)；parts = []；cursor = 0；for hit in sorted_hits: if not isinstance(hit.page_offset, int) or not isinstance(hit.page_length, int) or hit.page_offset < 0 or hit.page_offset + hit.page_length > len(text): continue（防御性 length check）；if hit.page_offset > cursor: parts.append(html_escape(text[cursor:hit.page_offset]))；short_code = ENTITY_TYPE_SHORT_CODE.get(hit.entity_type, hit.entity_type)；mask_sample = hit.mask_strategy or ''；title_text = f'{hit.entity_type} · {mask_sample}'（D-21 tooltip 形态）；escaped_title = html_escape(title_text)；original_text = text[hit.page_offset:hit.page_offset + hit.page_length]；escaped_original = html_escape(original_text)；parts.append(f'<mark class="pii-highlight" data-entity-type="{html_escape(hit.entity_type)}" title="{escaped_title}"><span class="pii-tag">{short_code}</span>{escaped_original}</mark>')；cursor = hit.page_offset + hit.page_length。if cursor < len(text): parts.append(html_escape(text[cursor:]))。return ''.join(parts)。**关键**：左栏**只**写原文（text[page_offset:page_offset+page_length]），**不**写 hit.mask_strategy；短码徽章用 ENTITY_TYPE_SHORT_CODE 字典（D-21 + per BLOCKER 5 单一来源 import）；html_escape 防 XSS。

    (c) `_build_pii_mask_block_fragment(self, key: str, hits: list) -> str`：构造右栏 partial mask HTML 片段（Visuals §PII Partial-Mask 锁）。实现：if key not in self.word_data: return ''；text = self.word_data[key].get('text', '')；sorted_hits = sorted(hits, key=lambda h: h.page_offset)；parts = []；cursor = 0；for hit in sorted_hits: if not isinstance(hit.page_offset, int) or not isinstance(hit.page_length, int) or hit.page_offset < 0 or hit.page_offset + hit.page_length > len(text): continue；if hit.page_offset > cursor: parts.append(html_escape(text[cursor:hit.page_offset]))；mask_text = hit.mask_strategy or ''；escaped_mask = html_escape(mask_text)；title_text = f'已替换为：{mask_text}'（Visuals 锁定）；escaped_title = html_escape(title_text)；parts.append(f'<mark class="pii-mask" data-entity-type="{html_escape(hit.entity_type)}" title="{escaped_title}">{escaped_mask}</mark>')；cursor = hit.page_offset + hit.page_length。if cursor < len(text): parts.append(html_escape(text[cursor:]))。return ''.join(parts)。**关键**：右栏**只**写 hit.mask_strategy（partial mask 字符串），**不**包裹原文。

    (d) 改进 `_on_word_pii_page_result`（Wave 1 占位已就位；本任务实现真实 body）：替换 Wave 1 的 print 占位；实现：lazy import `from privacyguard.pii.hits import PIIHit`（如未就位）；hits = [PIIHit(**h) for h in hits_data]（防御性 try/except：except (TypeError, ValueError): print(f'[Word PII WARN] invalid hit dict: {h}'); continue）；with QMutexLocker(self._word_data_lock): if key in self.word_data: self.word_data[key]['pii'] = hits; else: print(f'[Word PII WARN] key {key} not in word_data')；self._apply_word_pii_panel_updates(key, hits)（**关键**：写完 word_data[key]['pii'] 后**同步**触发 cp27 局部 patch —— D-10 / D-18 锁）。**关键**：QMutexLocker 包裹写 word_data；释放锁后再调 _apply_word_pii_panel_updates（避免锁内 UI 阻塞）。

    **main.py MainWindow 类 _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 改进**（main.py:11940-12000）：把 merge_word_matches_with_priority 调用追加 pii_matches 入参（与 _save_word 一致 —— D-19 priority 锁）：
    ```python
    merged_matches = merge_word_matches_with_priority(
        source_text, rules, default_replacement_text,
        manual_matches=data.get('manual', []),
        ocr_matches=data.get('ocr', []),
        pii_matches=data.get('pii', []),  # Phase 3 NEW — Wave 2
    )
    ```
    `_build_word_original_panel_updates` 调用 rules=[]（保持既有行为）；`_build_word_replaced_panel_updates` 调用 rules=self.word_replace_rules。**注意**：这两个方法在渲染阶段（render_word_preview）使用，把 pii 通道纳入合并路径意味着右栏在重新渲染时会包含 PII partial mask；左栏原预览片段 `_build_word_original_preview_fragment` 保持不变（Phase 1 既有 _append_candidates 走 manual / ocr 高亮；PII 高亮走 _apply_word_pii_panel_updates 局部 patch 单独触发，避免重复渲染）。

    **privacyguard/word/candidate_dialog.py NEW 占位骨架**（Wave 3 完整 UI 行为）。模块 docstring "Phase 3 Word 候选审阅对话框（UX-01 / UX-02 极简版 —— Wave 2 占位骨架，Wave 3 完整实施）"。定义：
    ```python
    from typing import List, Optional
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
    )

    class WordCandidateDialog(QDialog):
        """Phase 3 Word 候选审阅极简版（D-25 / UX-01 / UX-02 —— Wave 2 占位，Wave 3 完整实施）"""
        PAGE_SIZE = 50

        def __init__(self, word_data: dict, parent=None):
            super().__init__(parent)
            self.word_data = word_data or {}
            self._all_hits: List[dict] = []
            self._page = 0
            self.setWindowTitle('Word 候选审阅')
            self.resize(700, 600)
            self._init_ui()

        def _init_ui(self):
            # Wave 2 占位：仅 setWindowTitle + resize；Wave 3 实施实体类型 / 来源筛选 + 50 条分页 + 4 CTAs
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel('Word 候选审阅 —— Wave 3 完整 UI 行为待实施'))
    ```
    __all__ = ['WordCandidateDialog', 'ENTITY_TYPE_LABEL']。模块顶部新增 `ENTITY_TYPE_LABEL` 字典（D-21 锁 + Visuals §Copywriting）：{'CN_ID_CARD': '身份证号', 'CN_PHONE': '手机号', 'CN_BANK_CARD': '银行卡号', 'CN_EMAIL': '电子邮箱', 'CN_USCC': '统一社会信用代码', 'CN_TAXPAYER_ID': '纳税人识别号（18 位）', 'CN_TAXPAYER_ID_15': '纳税人识别号（15 位）', 'CN_VAT_INVOICE': '增值税发票号', 'CN_BANK_ACCOUNT': '银行账号'}。**关键**：PyQt6.QtWidgets import 允许（PyQt6 是常驻依赖，与 Qt 框架生命周期绑定）。

    **不修改 privacyguard/word/__init__.py 与 privacyguard/__init__.py**（per BLOCKER 7 修正 —— Wave 1 已就位 _LAZY_IMPORTS，本 plan 不重复修改）。如 Wave 1 占位骨架 import 失败，调整 _LAZY_IMPORTS['WordCandidateDialog'] target module 路径在 Wave 3 统一处理。

    **验证 GREEN**。运行命令：
    ```bash
    set -o pipefail
    python3 -m compileall -q main.py privacyguard tests && \
    python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights \
                          tests.unit.test_word_replace_rules \
                          tests.unit.test_batch_word_replace \
                          tests.unit.test_convergence \
                          tests.unit.test_package_imports \
                          tests.unit.test_app_config \
                          tests.unit.test_fstring_safety \
                          -v
    ```
    期望 TestWordPIIPanelHighlights 4 个测试方法全 OK + 既有基线 11 unittest 模块保持 GREEN。运行 `python3 -c "from privacyguard.word.candidate_dialog import WordCandidateDialog; print('OK', WordCandidateDialog)"` 验证 import 不抛异常。运行 `python3 -c "from main import ENTITY_TYPE_SHORT_CODE; print(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'])"` 输出 ID（per BLOCKER 5 单一来源从 privacyguard/pii/hits.py import 成功）。
  </action>
  <verify>
    <automated>set -o pipefail; python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports tests.unit.test_app_config tests.unit.test_fstring_safety -v 2>&1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v` 显示 4 个测试方法（test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml / test_build_pii_block_fragment_contains_short_code_badge / test_build_pii_mask_block_fragment_contains_mask_string_not_original / test_entity_type_short_code_covers_all_9_locked_types）全部 OK。
    - test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml 断言 stub.word_preview.page().runJavaScript 被调 + stub.word_preview.setHtml 未被调（cp27 契约锁定反向断言）。
    - test_build_pii_block_fragment_contains_short_code_badge 断言左栏 fragment 含 '<mark class="pii-highlight"' + 'data-entity-type="CN_ID_CARD"' + '<span class="pii-tag">ID</span>' + 原文 '53010219200508011X'，**且不**含 mask 字符串。
    - test_build_pii_mask_block_fragment_contains_mask_string_not_original 断言右栏 fragment 含 '<mark class="pii-mask"' + 'data-entity-type="CN_ID_CARD"' + mask 字符串，**且不**含原文 '53010219200508011X'。
    - test_entity_type_short_code_covers_all_9_locked_types 断言 ENTITY_TYPE_SHORT_CODE 字典覆盖 9 个 entity_type 且 ASCII uppercase 短码（ID / PHONE / BANK / EMAIL / USCC / TAX / TAX15 / VAT / ACCT）；来源唯一来自 privacyguard/pii/hits.py（per BLOCKER 5）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v` 全部测试方法 GREEN（Wave 1 7 个 + Wave 2 4 个 = 11 个）。
    - 既有 11 unittest 模块基线全部 GREEN —— cp27 既有 build_word_panel_update_script 复用不破坏（per WARNING 3 包含 test_fstring_safety）。
    - `python3 -c "from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE; print(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'])"` 输出 ID（per BLOCKER 5 单一来源就位）。
    - `python3 -c "from privacyguard.word.candidate_dialog import WordCandidateDialog; print('OK')"` 输出 OK（占位骨架可被 lazy forward 加载）。
    - `python3 -m compileall -q main.py privacyguard tests` 退出码 0（语法 GREEN）。
  </acceptance_criteria>
  <done>
    main.py 4 个方法 + 1 个 import 落地（新增 _apply_word_pii_panel_updates / _build_pii_block_fragment / _build_pii_mask_block_fragment / 改进 _on_word_pii_page_result 真实 body + from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE 单一来源）；左栏原文 + 短码徽章 + 右栏 partial mask 渲染契约落地；cp27 局部 patch 契约保持；privacyguard/word/candidate_dialog.py WordCandidateDialog 占位骨架就位；TestWordPIIPanelHighlights 4 个测试方法全部 GREEN；Wave 1 7 个测试方法保持 GREEN；既有 11 unittest 模块基线保持 GREEN；per BLOCKER 5 短码字典单一来源 import 至 privacyguard/pii/hits.py。
  </done>
  <reversibility>rating="costly" rationale="main.py 4 处新增方法 + WordCandidateDialog 骨架；删除需恢复 Wave 1 状态并删除候选骨架。"</reversibility>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Wave 2 人工验证 — 双栏 PII 高亮 + partial mask 在真实 UI 中视觉正确</name>
  <files>
    - main.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-UI-SPEC.md (lines 174-247 — 左栏 <mark class="pii-highlight"> + 短码徽章 + 右栏 <mark class="pii-mask"> 完整 HTML 形态契约)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 290-308 — wordPiiStatusChip 状态机)
    - .planning/phases/03-word/03-VALIDATION.md (lines 80-91 — Manual-Only Verifications)
    - .planning/phases/03-word/03-RESEARCH.md (lines 833-846 — Pitfall 9 cp27 契约)
    - main.py:471 (build_word_panel_update_script — cp27 既有 helper)
    - main.py:11508 (Wave 1 + Wave 2 接线后 _on_word_pii_page_result)
  </read_first>
  <what-built>
    Wave 2 GREEN 任务实施完成后：main.py 新增 4 个方法（_apply_word_pii_panel_updates / _build_pii_block_fragment / _build_pii_mask_block_fragment / 改进 _on_word_pii_page_result）+ from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE 9 短码字典单一来源（per BLOCKER 5）；改进 _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 把 pii 通道纳入合并路径；privacyguard/word/candidate_dialog.py WordCandidateDialog 占位骨架；TestWordPIIPanelHighlights 4 个测试方法 GREEN。
  </what-built>
  <how-to-verify>
    **步骤 1 — 启动应用**：`cd /mnt/g/Project/PrivacyGuard && python3 main.py`

    **步骤 2 — 构造含 PII 的 docx**：`python3 -c "from tests.fixtures.fake_word import build_fake_docx; p = build_fake_docx(); print(p)"`

    **步骤 3 — 主菜单 → Open → 选择合成的 docx**

    **步骤 4 — 等待 worker 完成**（status chip 显示 `已识别 N 项敏感内容`）

    **步骤 5 — 切换到对比模式**

    **步骤 6 — 观察左栏（原文预览）**：PII 命中位置出现红色半透明填充矩形（`<mark class="pii-highlight">` 背景 `#D64545@alpha 0.18` / `#FF6B6B@alpha 0.22`）；PII 命中位置左侧有红色短码徽章（`ID` / `PHONE` / `BANK` / `EMAIL` / `USCC` / `TAX` / `TAX15` / `VAT` / `ACCT`，per BLOCKER 5 单一来源 from privacyguard/pii/hits.py）；鼠标悬停 PII 命中位置 → 浏览器原生 tooltip 显示 `{entity_type全称} · {mask_sample}`。

    **步骤 7 — 观察右栏（替换预览）**：PII 命中位置出现绿色半透明填充矩形（`<mark class="pii-mask">` 背景 `#0FA968@alpha 0.12` / `#34D399@alpha 0.18`）；矩形内**只**显示 partial mask 字符串（如 `110101********1234`），**不**显示原文；鼠标悬停 → tooltip 显示 `已替换为：110101********1234`。

    **步骤 8 — 滚动 / 缩放 / 切换段落**：左右双栏**不**触发整页重渲染（cp27 契约锁定）；滚动位置 / 选中状态 / 缩放保持。

    **步骤 9 — 重新打开**：关闭 app；重新启动；再次打开同一 docx；PII 高亮与 mask 显示与首次一致。

    **通过条件**：步骤 6/7 双栏高亮 + tooltip 正确；步骤 8 cp27 增量 patch 不破坏滚动；步骤 9 重新打开一致。

    **不通过条件**（任一即触发 Wave 3 修复）：左栏未显示红色高亮或短码徽章缺失；右栏显示原文或未显示绿色 partial mask；滚动 / 缩放触发整页重渲染（cp27 契约破坏）；重新打开 docx 后高亮丢失。
  </how-to-verify>
  <action>
    阻塞型 checkpoint：等待用户回复 "approved" 或失败步骤与异常信息。Wave 2 GREEN 任务已完成 main.py 4 个方法 + ENTITY_TYPE_SHORT_CODE 单一来源 import + privacyguard/word/candidate_dialog.py 占位骨架 + TestWordPIIPanelHighlights 4 测试方法 GREEN。本任务仅观察 UI 视觉，不修改代码。
  </action>
  <resume-signal>Type "approved" to proceed to Wave 3, or describe the failing step + visual evidence to trigger Wave 2 GREEN fix.</resume-signal>
  <verify>
    <automated>echo '人工验证 checkpoint — 阻塞型门禁，需用户输入 approved 后 Wave 3 才可启动'</automated>
  </verify>
  <acceptance_criteria>
    - 用户在 UI 验证步骤 1-9 全部通过，回复 "approved"
    - 若失败：用户报告具体失败步骤与异常信息，Wave 2 GREEN 任务需进一步修复
  </acceptance_criteria>
  <done>
    真实 PyQt6 UI 中打开 docx 后左栏红色 PII 高亮 + 短码徽章 + tooltip 正确；右栏绿色 partial mask + 仅 mask 字符串 + tooltip 正确；滚动 / 缩放 / 切换段落 cp27 契约保持；重新打开 docx 后 PII 高亮与 mask 显示一致；用户回复 "approved"；Wave 3 可启动。
  </done>
  <reversibility>rating="reversible" rationale="UI 验证仅观察，不修改代码；如未通过，回到 Wave 2 GREEN 任务修复。"</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| PIIHit.normalized 输入 | Worker emit 的 PIIHit.normalized 是 dataclass 字段；可能为空字符串 / 非字符串 / 超长字符串；_build_pii_block_fragment 必须做防御性 length check |
| HTML injection through PII strings | hit.normalized 可能含 HTML 特殊字符（< > & "）；必须 html.escape 后再插入到 <mark> 内部 |
| web_view.runJavaScript → JavaScript 引擎 | 拼接到 runJavaScript 字符串的内容必须严格转义；不直接拼接 hit.normalized 到 JavaScript 字符串中 |
| data-key 同步 | mammoth 转 HTML 时可能插入 <strong> / <em> 等 inline 标签；_apply_word_pii_panel_updates 假设 _add_data_key_attributes 已就位（Wave 1 既有 —— 不重写） |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-03-SetHtmlRegression | Tampering / cp27 契约破坏 | _apply_word_pii_panel_updates | critical | mitigate | 严格走 web_view.page().runJavaScript(...)；tests/unit/test_word_pii_pipeline.py::TestWordPIIPanelHighlights mock web_view，断言 runJavaScript 被调 + setHtml 未被调 |
| T-03-HTMLInjection | Information Disclosure / XSS (local preview) | _build_pii_block_fragment + _build_pii_mask_block_fragment | medium | mitigate | html.escape hit.normalized + hit.mask_strategy + key 字符串；TestWordPIIPanelHighlights 断言 < > & " 在输出 HTML 中被 escape |
| T-03-ShortCodeMissing | Tampering / UI 渲染异常 | privacyguard/pii/hits.py:ENTITY_TYPE_SHORT_CODE | low | mitigate | 9 短码字典在 privacyguard/pii/hits.py 模块级（per BLOCKER 5 单一来源）+ .get(entity_type, entity_type) fallback；新 entity_type 出现时返回 entity_type 字符串本身（不抛 KeyError） |
| T-03-MaskInLeftPane | Information Disclosure / UI 错位 | _build_pii_block_fragment | medium | mitigate | 左栏**只**写 hit.normalized[page_offset:page_offset+page_length]；TestWordPIIPanelHighlights 断言左栏 HTML 不含 hit.mask_strategy |
| T-03-ShortCodeSourceOfTruth | Tampering / D-21 single-source violation | main.py + privacyguard/pii/hits.py | medium | mitigate | per BLOCKER 5：main.py 仅 from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE，不内联 9 短码字典；test_convergence AST 断言 main.py 不内联 9 短码字面量 |

</threat_model>

<verification>
```bash
set -o pipefail
python3 -m compileall -q main.py privacyguard tests \
  && python3 -m unittest \
      tests.unit.test_mixed_pdf_ocr \
      tests.test_path_validation \
      tests.unit.test_ocr_api \
      tests.unit.test_package_imports \
      tests.unit.test_pdf_text_hit_dedup \
      tests.unit.test_app_config \
      tests.unit.test_word_replace_rules \
      tests.unit.test_batch_word_replace \
      tests.unit.test_config_alignment \
      tests.unit.test_fstring_safety \
      tests.unit.test_convergence \
      tests.unit.test_word_pii_pipeline \
      -v
```
Wave 2 单独门禁：
```bash
set -o pipefail
python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v
```
期望 4 个测试方法 OK。

辅助验证：
```bash
# ENTITY_TYPE_SHORT_CODE 单一来源（per BLOCKER 5）
python3 -c "from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE; print(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'])"

# main.py 不内联 9 短码字典（per BLOCKER 5）
python3 -c "
import ast
from pathlib import Path
tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
found = False
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
        keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
        if 'CN_ID_CARD' in keys:
            found = True
            break
print('main.py inline 9-short-code dict:', 'FOUND (violation)' if found else 'NONE (correct)')
"
```
</verification>

<success_criteria>
- [ ] main.py 4 个新增方法落地（_apply_word_pii_panel_updates / _build_pii_block_fragment / _build_pii_mask_block_fragment / 改进 _on_word_pii_page_result）
- [ ] main.py 通过 `from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE` 单一来源 import（per BLOCKER 5 抽离 + D-21 锁）；不内联 9 短码字典
- [ ] main.py _build_word_original_panel_updates + _build_word_replaced_panel_updates 把 pii 通道纳入合并路径
- [ ] privacyguard/word/candidate_dialog.py WordCandidateDialog 占位骨架就位
- [ ] TestWordPIIPanelHighlights 4 个测试方法全部 GREEN
- [ ] 既有 11 unittest 模块基线（CLAUDE.md §基线）保持 GREEN（含 test_fstring_safety — per WARNING 3）
- [ ] cp27 增量 DOM patch 契约保持（runJavaScript 被调 + setHtml 未被调）
- [ ] 左栏原文 + 短码徽章 + 右栏 partial mask 视觉契约保持
- [ ] 真实 PyQt6 UI 双栏 PII 高亮 + partial mask 视觉验证通过
</success_criteria>

<output>
创建 `.planning/phases/03-word/03-02-engine-expansion-and-ui-SUMMARY.md` 当任务完成
</output>