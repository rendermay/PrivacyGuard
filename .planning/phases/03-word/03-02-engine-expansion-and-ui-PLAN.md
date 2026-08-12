---
phase: 03-word
plan: 02
slug: engine-expansion-and-ui
type: execute
wave: 2
depends_on:
  - 03-01
files_modified:
  - privacyguard/word/__init__.py
  - privacyguard/word/candidate_dialog.py
  - main.py
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
    - "_apply_word_pii_panel_updates 走 web_view.page().runJavaScript(\"updateBlock(...)\") 局部 patch，左栏注入 <mark class=\"pii-highlight\"> 包裹原文 + <span class=\"pii-tag\">CODE</span> 短码徽章，右栏注入 <mark class=\"pii-mask\"> 包裹 partial mask 字符串（per D-10 / cp27 增量 patch 锁定）"
    - "左右双栏 PII 高亮通过 cp27 局部 patch 注入，**禁止** 触发整页 web_view.setHtml(...)；TestWordPIIPanelHighlights 断言 web_view.page().runJavaScript 被调且 web_view.setHtml 未被调（per cp27 + D-10 反向断言）"
    - "_build_pii_block_fragment 按 hit.page_offset 排序 + cursor 累加构造 data-key block 内 HTML 片段；左栏 HTML 形态严格匹配 <mark class=\"pii-highlight\" data-entity-type=\"...\" title=\"...\"><span class=\"pii-tag\">CODE</span>{原文}</mark>（per D-21 + 03-UI-SPEC §Visuals）"
    - "_build_pii_mask_block_fragment 构造右栏 partial mask 片段，形态严格 <mark class=\"pii-mask\" data-entity-type=\"...\" title=\"已替换为：{mask_strategy literal}\">{mask_strategy}</mark>（per 03-UI-SPEC §Visuals §PII Partial-Mask）"
    - "main.py:_on_word_pii_page_result 写 word_data[key][\"pii\"] 后**同步**触发 _apply_word_pii_panel_updates；UI 双栏在 worker emit 后 < 200ms 内完成局部 patch（per D-09 / D-10）"
    - "PII 短码徽章 9 个固定值：ID / PHONE / BANK / EMAIL / USCC / TAX / TAX15 / VAT / ACCT；ENTITY_TYPE_SHORT_CODE 字典在 main.py 模块级常量定义，单一来源（per D-21 锁）"
    - "现有 86/86 测试基线（Wave 1 升级后）保持通过 + 新增 TestWordPIIPanelHighlights 全部 green（per OPS-07 baseline preservation）"
  artifacts:
    - privacyguard/word/candidate_dialog.py (WordCandidateDialog QDialog 占位骨架 — 完整 UI 行为 Wave 3 落地)
    - privacyguard/word/__init__.py MODIFY (__all__ + _LAZY_IMPORTS WordCandidateDialog 占位)
    - main.py MODIFY (_apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + ENTITY_TYPE_SHORT_CODE 字典 + _build_word_pii_panel_js_script)
  key_links:
    - "_on_word_pii_page_result (Wave 1 落地) 到 _apply_word_pii_panel_updates (Wave 2 落地) 到 web_view.page().runJavaScript(build_word_panel_update_script(block_updates)) (main.py:12000-12005 cp27 既有形态)"
    - "build_word_panel_update_script (main.py:471 既有 cp27 helper) — Wave 2 复用既有局部 patch JavaScript 模板，不重写"
    - "_build_pii_block_fragment 到 ENTITY_TYPE_SHORT_CODE 字典 (main.py 模块级) — 单一来源映射 entity_type → 9 短码（per D-21 锁）"
    - "_build_pii_mask_block_fragment 到 PIIHit.mask_strategy 字段（mask_for_entity 已生产 — Phase 2 MASK-01）"
    - "WordCandidateDialog 占位骨架到 Wave 3 完整 UI 行为（UX-01 / UX-02 落地）"
  prohibitions:
    - "不得在 PII 高亮路径调 web_view.setHtml(...)；必须走 web_view.page().runJavaScript(\"updateBlock(...)\") 局部 patch（per D-10 / cp27 硬约束）"
    - "不得重写 build_word_panel_update_script（cp27 既有 helper，main.py:471）；Wave 2 仅复用既有 script 模板"
    - "不得引入 PII 短码字典的第二个来源；ENTITY_TYPE_SHORT_CODE 必须 main.py 模块级单一字典（per D-21 锁）"
    - "不得让 _apply_word_pii_panel_updates 在 hits 为空 list 时仍触发 runJavaScript；空 list 走早返（per 03-RESEARCH.md:1269 early return）"
    - "不得让左栏 <mark class=\"pii-highlight\"> 与右栏 <mark class=\"pii-mask\"> 互相覆盖 / 串色 — 左红右绿（partial-mask 调色）严格视觉区分（per 03-UI-SPEC §Color）"
    - "不得让 _build_pii_block_fragment 使用 hit.mask_strategy 写到左栏；左栏包裹原文（hit.normalized 截取 page_offset:page_offset+page_length），**不**写 mask 字符串（per 03-UI-SPEC §Visuals §PII Highlight 锁定）"
    - "不得让 _build_pii_mask_block_fragment 把原文写到右栏；右栏**只**写 mask 字符串（hit.mask_strategy），**不**包裹原文（per 03-UI-SPEC §Visuals §PII Partial-Mask 锁定）"
    - "不得在 privacyguard/word/candidate_dialog.py 包级 eager import PyQt6.QtWidgets；保持 _LAZY_IMPORTS + 函数内 import（per D-06 / OPS-03）"
  backstop_statements:
    - statement: "在 720p / 100% DPI 下，8+ 个连续 PII 命中在左栏保持视觉可区分（mark + pii-tag badge 不重叠 / 不溢出）"
      verification: backstop
    - statement: "右栏 <mark class='pii-mask'> 的 tooltip（已替换为：{mask_strategy literal}）在 720p 视口下 light + dark 双主题均不溢出"
      verification: backstop

threat_model:
  trust_boundaries:
    - name: PIIHit.normalized 输入
      description: Worker emit 的 PIIHit.normalized 是 dataclass 字段；可能为空字符串 / 非字符串 / 超长字符串；_build_pii_block_fragment 必须做防御性 length check
    - name: HTML injection through PII strings
      description: hit.normalized 可能含 HTML 特殊字符（< > & \"）；必须 html.escape 后再插入到 <mark> 内部，否则 XSS 风险（即便 QWebEngineView 本地预览仍走防御）
    - name: web_view.runJavaScript → JavaScript 引擎
      description: 拼接到 runJavaScript 字符串的内容必须严格转义；不直接拼接 hit.normalized 到 JavaScript 字符串中
    - name: data-key 同步
      description: mammoth 转 HTML 时可能插入 <strong> / <em> 等 inline 标签；_apply_word_pii_panel_updates 假设 _add_data_key_attributes 已就位（Wave 1 既有 — 不重写）
  stride:
    - id: T-03-SetHtmlRegression
      category: Tampering / cp27 契约破坏
      component: _apply_word_pii_panel_updates
      severity: critical
      disposition: mitigate
      mitigation: 严格走 web_view.page().runJavaScript(...)；tests/unit/test_word_pii_pipeline.py::TestWordPIIPanelHighlights mock web_view，断言 runJavaScript 被调 + setHtml 未被调
    - id: T-03-HTMLInjection
      category: Information Disclosure / XSS (local preview)
      component: _build_pii_block_fragment + _build_pii_mask_block_fragment
      severity: medium
      disposition: mitigate
      mitigation: html.escape hit.normalized + hit.mask_strategy + key 字符串；tests/unit/test_word_pii_pipeline.py::TestWordPIIPanelHighlights 断言 < > & " 在输出 HTML 中被 escape
    - id: T-03-ShortCodeMissing
      category: Tampering / UI 渲染异常
      component: main.py:ENTITY_TYPE_SHORT_CODE
      severity: low
      disposition: mitigate
      mitigation: 9 短码字典在 main.py 模块级 + try/except fallback；新 entity_type 出现时返回 entity_type 字符串本身（不抛 KeyError）
    - id: T-03-MaskInLeftPane
      category: Information Disclosure / UI 错位
      component: _build_pii_block_fragment
      severity: medium
      disposition: mitigate
      mitigation: 左栏**只**写 hit.normalized[page_offset:page_offset+page_length]；tests/unit/test_word_pii_pipeline.py::TestWordPIIPanelHighlights 断言左栏 HTML 不含 hit.mask_strategy

---

<objective>
落地 Phase 3 双栏 PII 高亮 + mask 显示的 cp27 增量 DOM patch 契约：左栏红框 `<mark class="pii-highlight">` + 短码徽章 `<span class="pii-tag">`；右栏绿调 `<mark class="pii-mask">` partial mask。WordCandidateDialog 占位骨架（完整 UX-01 / UX-02 行为 Wave 3 落地）。所有变更严格遵守 cp27（禁止整页 `setHtml`）+ D-10 + D-21 短码字典单一来源。
</objective>

<purpose>
Phase 3 用户故事的核心是「打开 Word 文档，敏感候选在双栏对比预览的左右两侧同时高亮」。Wave 1 落地了 PII 引擎接入 + 真脱敏 + 文档属性清除，但 UI 层面双栏还没有 PII 高亮显示 —— Wave 2 把 cp27 增量 DOM patch 落地到 PII 路径。同时为 Wave 3 的候选审阅对话框提供占位骨架，避免 main.py 引用不存在的符号导致 import-time 错误。
</purpose>

<output>
- main.py MODIFY：新增 _apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + ENTITY_TYPE_SHORT_CODE 字典 + 改进 _on_word_pii_page_result 调用 _apply_word_pii_panel_updates；改进 _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 把 pii 通道纳入合并路径
- privacyguard/word/candidate_dialog.py NEW：WordCandidateDialog QDialog 占位骨架（Wave 3 完整实施）
- privacyguard/word/__init__.py MODIFY：__all__ + _LAZY_IMPORTS WordCandidateDialog 占位（Wave 1 已就位，本任务仅添加类骨架 import 路径）
- tests/unit/test_word_pii_pipeline.py MODIFY：新增 TestWordPIIPanelHighlights 测试类
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
@privacyguard/pii/hits.py (PIIHit 9 字段锁 — D-16)
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
    - privacyguard/pii/hits.py (PIIHit dataclass — 字段顺序锁 + page_rect Word 路径置占位 (0,0,0,0))
    - tests/unit/test_word_pii_pipeline.py (Wave 1 RED 既有 5 个测试类 — 范本)
  </read_first>
  <action>
    在 tests/unit/test_word_pii_pipeline.py 追加 TestWordPIIPanelHighlights 测试类。本任务**只写测试**，主代码占位由 Wave 2 GREEN 任务实施。

    **TestWordPIIPanelHighlights 测试类**（含 4 个测试方法）：

    **test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml**：构造 minimal QApplication (pytest-qt 不可用 → QApplication([]) 或 unittest.mock.Mock)；构造 minimal MainWindow-like 桩：class _StubMainWindow 含 self.word_data = {"paragraph_5": {"text": "身份证 53010219200508011X 末位", "ocr": [], "manual": [], "pii": []}}；self.word_preview = Mock(spec=QWebEngineView)；self.word_preview_replaced = Mock(spec=QWebEngineView)。构造 hits = [PIIHit(entity_type='CN_ID_CARD', page_offset=4, page_length=18, page_rect=(0,0,0,0), confidence_tier='HIGH', source='text', mask_strategy=mask_for_entity('CN_ID_CARD', '53010219200508011X'), normalized='53010219200508011X')]。从 main import _apply_word_pii_panel_updates；调 stub._apply_word_pii_panel_updates(key='paragraph_5', hits=hits)。断言 stub.word_preview.page().runJavaScript.assert_called()（cp27 走局部 patch）；断言 stub.word_preview.setHtml.assert_not_called()（cp27 锁定禁止整页 setHtml）；断言 stub.word_preview_replaced.page().runJavaScript.assert_called()（左右双栏均走 runJavaScript）；断言 stub.word_preview_replaced.setHtml.assert_not_called()。

    **test_build_pii_block_fragment_contains_short_code_badge**：构造 key = "paragraph_5"；text = "身份证 53010219200508011X 末位"；hits 同上。从 main import _build_pii_block_fragment；构造 stub 含 self.word_data = {"paragraph_5": {"text": text, "ocr": [], "manual": [], "pii": []}}；fragment = stub._build_pii_block_fragment(key, hits)。断言 '<mark class="pii-highlight"' in fragment（HTML 元素名锁定）；断言 'data-entity-type="CN_ID_CARD"' in fragment（entity_type 属性锁定）；断言 '<span class="pii-tag">ID</span>' in fragment（短码徽章锁定 — D-21）；断言 '53010219200508011X' in fragment（原文包裹）；断言 mask_for_entity('CN_ID_CARD', '53010219200508011X') not in fragment（**左栏不含 mask 字符串** — Visuals §PII Highlight 锁定）。

    **test_build_pii_mask_block_fragment_contains_mask_string_not_original**：构造 key = "paragraph_5"；text = "身份证 53010219200508011X 末位"；hits 同上。从 main import _build_pii_mask_block_fragment；stub 同上；fragment = stub._build_pii_mask_block_fragment(key, hits)。断言 '<mark class="pii-mask"' in fragment（HTML 元素名锁定）；断言 'data-entity-type="CN_ID_CARD"' in fragment；断言 mask_for_entity('CN_ID_CARD', '53010219200508011X') in fragment（**右栏包裹 mask 字符串** — Visuals §PII Partial-Mask 锁定）；断言 '已替换为：' in fragment（title 属性前缀锁定）；断言 '53010219200508011X' not in fragment（**右栏不含原文** — Visuals §PII Partial-Mask 锁定）。

    **test_entity_type_short_code_covers_all_9_locked_types**：从 main import ENTITY_TYPE_SHORT_CODE。断言 set(ENTITY_TYPE_SHORT_CODE.keys()) == {'CN_ID_CARD', 'CN_PHONE', 'CN_BANK_CARD', 'CN_EMAIL', 'CN_USCC', 'CN_TAXPAYER_ID', 'CN_TAXPAYER_ID_15', 'CN_VAT_INVOICE', 'CN_BANK_ACCOUNT'}（9 短码字典全覆盖 — D-21 锁）。断言 ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'] == 'ID'；'CN_PHONE' == 'PHONE'；'CN_BANK_CARD' == 'BANK'；'CN_EMAIL' == 'EMAIL'；'CN_USCC' == 'USCC'；'CN_TAXPAYER_ID' == 'TAX'；'CN_TAXPAYER_ID_15' == 'TAX15'；'CN_VAT_INVOICE' == 'VAT'；'CN_BANK_ACCOUNT' == 'ACCT'。**关键**：9 个短码值锁定为 ASCII uppercase（D-21 锁）；不允许出现 '身份证' / 'phone' 等中文或小写。

    实现注意：MainWindow 桩类需要继承 MainWindow 但跳过 Qt 父类初始化（避免 QApplication 错误）。可使用 `class _StubMainWindow(MainWindow): def __init__(self): self.word_data = ...; self.word_preview = Mock(...); self.word_preview_replaced = Mock(...)；pass`；或更简单：直接在测试方法内定义 dict + Mock 对象，不继承 MainWindow，从 main module 取函数调（如 `_apply_word_pii_panel_updates(self, ...)` 是方法，需桩实例）。建议：在 setUp 内构造 stub 实例（不调 super().__init__()，避免 QApplication 父类构造），把 stub 实例传给函数调用。或：从 main module 用 `importlib` 取 unbound method，手动传 stub。**最简方案**：从 main import `_apply_word_pii_panel_updates` 作为 unbound 函数（main.py 函数是定义在 MainWindow class 内方法，需 stub 实例）。建议：直接 `class _StubMainWindow:` 含必需属性，**不继承** MainWindow；通过 `unittest.mock.patch('main.MainWindow')` 让 stub 替代 MainWindow；或更简单：在 main.py:11508 `_on_word_pii_page_result` 后 Wave 2 GREEN 任务把 `_apply_word_pii_panel_updates` 实现为可独立调用的模块级函数（接受 stub 实例参数），便于测试。**优先方案**：本 RED 测试在 setUp 内构造最小 MainWindow 子类 `class _StubMW(MainWindow): def __init__(self): self.word_data = ...；self.word_preview = Mock(spec=QWebEngineView)；self.word_preview_replaced = Mock(spec=QWebEngineView)；# 跳过 super().__init__()`；调用 `stub._apply_word_pii_panel_updates(...)`；Mock(spec=QWebEngineView) 自动提供 page() 返回 Mock。

    测试方法标 RED：每个方法末尾用 `self.fail("Wave 2 GREEN 实施后此测试应 pass")` 占位；Wave 2 GREEN 任务移除 self.fail。
  </action>
  <verify>
    <automated>python3 -m compileall -q tests/unit/test_word_pii_pipeline.py && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v 2>&1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q tests/unit/test_word_pii_pipeline.py` 退出码 0（语法 green）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v` 显示 4 个测试方法全部 FAIL（AttributeError: module 'main' has no attribute '_apply_word_pii_panel_updates' 或 _build_pii_block_fragment / _build_pii_mask_block_fragment / ENTITY_TYPE_SHORT_CODE）— RED 基线确认。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v`（含 Wave 1 既有 5 个测试类）显示既有 7 个测试方法保持 green，4 个新测试方法 FAIL（Wave 1 状态未破坏）。
    - `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports -v` 既有 79/79 基线保持 green（merge_word_matches_with_priority back-compat + lazy-load 纪律保持）。
  </acceptance_criteria>
  <done>
    TestWordPIIPanelHighlights 4 个测试方法 RED 骨架就位；测试方法明确断言 cp27 runJavaScript 契约（runJavaScript 被调 + setHtml 未被调）+ 短码徽章 HTML 形态 + 左栏原文 + 右栏 partial mask + 9 短码字典；RED 失败原因可定位到具体 AttributeError。
  </done>
  <reversibility>rating="reversible" rationale="仅测试文件追加；删除 TestWordPIIPanelHighlights 类即可恢复 Wave 1 状态。"</reversibility>
</task>

<task type="auto" tdd="true">
  <name>GREEN — 实现 _apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + ENTITY_TYPE_SHORT_CODE + 改进 _on_word_pii_page_result + WordCandidateDialog 占位骨架</name>
  <files>
    - main.py
    - privacyguard/word/candidate_dialog.py
    - privacyguard/word/__init__.py
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
    - privacyguard/pii/hits.py (PIIHit dataclass — 字段顺序锁)
    - privacyguard/pii/mask.py (mask_for_entity — Phase 2 MASK-01 锁)
  </read_first>
  <action>
    Wave 2 GREEN 任务。本任务实施 5 个新增方法 / 函数 + 1 个 QDialog 占位骨架；目标让 TestWordPIIPanelHighlights 4 个测试方法全部 green。

    **main.py 模块级新增 ENTITY_TYPE_SHORT_CODE 常量**（单一来源字典；D-21 锁）：在 main.py 模块顶部（紧邻 _range_overlaps / merge_word_matches_with_priority 等模块级函数附近）新增：
    ```python
    ENTITY_TYPE_SHORT_CODE = {
        'CN_ID_CARD': 'ID',
        'CN_PHONE': 'PHONE',
        'CN_BANK_CARD': 'BANK',
        'CN_EMAIL': 'EMAIL',
        'CN_USCC': 'USCC',
        'CN_TAXPAYER_ID': 'TAX',
        'CN_TAXPAYER_ID_15': 'TAX15',
        'CN_VAT_INVOICE': 'VAT',
        'CN_BANK_ACCOUNT': 'ACCT',
    }
    ```
    9 短码字典；ASCII uppercase；D-21 锁。模块顶部新增 `from privacyguard.pii.hits import PIIHit`（如未就位；PIIHit 是 dataclass 容器，常驻 import 允许）。模块顶部新增 `from html import escape as html_escape`（如未就位；常驻 import 允许）。

    **main.py MainWindow 类新增 4 个方法**（紧邻 _apply_word_panel_updates，约 main.py:12005 之后）：

    (a) `_apply_word_pii_panel_updates(self, key: str, hits: list)`：严格走 cp27 增量 patch（D-10 锁）；不触发整页 setHtml。实现：if not hits: return；block_updates = {key: self._build_pii_block_fragment(key, hits)}（左栏）；replaced_updates = {key: self._build_pii_mask_block_fragment(key, hits)}（右栏）；for view_attr, updates in (('word_preview', block_updates), ('word_preview_replaced', replaced_updates)): view = getattr(self, view_attr, None); if view and not view.isHidden(): script = build_word_panel_update_script(updates); view.page().runJavaScript(script)。**关键**：cp27 既有 build_word_panel_update_script（main.py:471）直接复用，**不**重写 JavaScript 模板。

    (b) `_build_pii_block_fragment(self, key: str, hits: list) -> str`：构造左栏原文高亮 HTML 片段（D-21 + Visuals §PII Highlight 锁）。实现：if key not in self.word_data: return ''；text = self.word_data[key].get('text', '')；sorted_hits = sorted(hits, key=lambda h: h.page_offset)；parts = []；cursor = 0；for hit in sorted_hits: if not isinstance(hit.page_offset, int) or not isinstance(hit.page_length, int) or hit.page_offset < 0 or hit.page_offset + hit.page_length > len(text): continue（防御性 length check）；if hit.page_offset > cursor: parts.append(html_escape(text[cursor:hit.page_offset]))；short_code = ENTITY_TYPE_SHORT_CODE.get(hit.entity_type, hit.entity_type)；mask_sample = hit.mask_strategy or ''；title_text = f'{hit.entity_type} · {mask_sample}'（D-21 tooltip 形态）；escaped_title = html_escape(title_text)；original_text = text[hit.page_offset:hit.page_offset + hit.page_length]；escaped_original = html_escape(original_text)；parts.append(f'<mark class="pii-highlight" data-entity-type="{html_escape(hit.entity_type)}" title="{escaped_title}"><span class="pii-tag">{short_code}</span>{escaped_original}</mark>')；cursor = hit.page_offset + hit.page_length。if cursor < len(text): parts.append(html_escape(text[cursor:]))。return ''.join(parts)。**关键**：左栏**只**写原文（text[page_offset:page_offset+page_length]），**不**写 hit.mask_strategy；短码徽章用 ENTITY_TYPE_SHORT_CODE 字典（D-21 锁）；html_escape 防 XSS。

    (c) `_build_pii_mask_block_fragment(self, key: str, hits: list) -> str`：构造右栏 partial mask HTML 片段（Visuals §PII Partial-Mask 锁）。实现：if key not in self.word_data: return ''；text = self.word_data[key].get('text', '')；sorted_hits = sorted(hits, key=lambda h: h.page_offset)；parts = []；cursor = 0；for hit in sorted_hits: if not isinstance(hit.page_offset, int) or not isinstance(hit.page_length, int) or hit.page_offset < 0 or hit.page_offset + hit.page_length > len(text): continue；if hit.page_offset > cursor: parts.append(html_escape(text[cursor:hit.page_offset]))；mask_text = hit.mask_strategy or ''；escaped_mask = html_escape(mask_text)；title_text = f'已替换为：{mask_text}'（Visuals 锁定）；escaped_title = html_escape(title_text)；parts.append(f'<mark class="pii-mask" data-entity-type="{html_escape(hit.entity_type)}" title="{escaped_title}">{escaped_mask}</mark>')；cursor = hit.page_offset + hit.page_length。if cursor < len(text): parts.append(html_escape(text[cursor:]))。return ''.join(parts)。**关键**：右栏**只**写 hit.mask_strategy（partial mask 字符串），**不**包裹原文。

    (d) 改进 `_on_word_pii_page_result`（Wave 1 占位已就位；本任务实现真实 body）：替换 Wave 1 的 NotImplementedError；实现：lazy import `from privacyguard.pii.hits import PIIHit`（如未就位）；hits = [PIIHit(**h) for h in hits_data]（防御性 try/except：except (TypeError, ValueError): print(f'[Word PII WARN] invalid hit dict: {h}'); continue）；with QMutexLocker(self._word_data_lock): if key in self.word_data: self.word_data[key]['pii'] = hits; else: print(f'[Word PII WARN] key {key} not in word_data'); self._apply_word_pii_panel_updates(key, hits)（**关键**：写完 word_data[key]['pii'] 后**同步**触发 cp27 局部 patch — D-10 / D-18 锁）。**关键**：QMutexLocker 包裹写 word_data；释放锁后再调 _apply_word_pii_panel_updates（避免锁内 UI 阻塞）。

    **main.py MainWindow 类 _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 改进**（main.py:11940-12000）：把 merge_word_matches_with_priority 调用追加 pii_matches 入参（与 _save_word 一致 — D-19 priority 锁）：
    ```python
    merged_matches = merge_word_matches_with_priority(
        source_text, rules, default_replacement_text,
        manual_matches=data.get('manual', []),
        ocr_matches=data.get('ocr', []),
        pii_matches=data.get('pii', []),  # Phase 3 NEW — Wave 2
    )
    ```
    `_build_word_original_panel_updates` 调用 rules=[]（保持既有行为）；`_build_word_replaced_panel_updates` 调用 rules=self.word_replace_rules。**注意**：这两个方法在渲染阶段（render_word_preview）使用，把 pii 通道纳入合并路径意味着右栏在重新渲染时会包含 PII partial mask；左栏原预览片段 `_build_word_original_preview_fragment` 保持不变（Phase 1 既有 _append_candidates 走 manual / ocr 高亮；PII 高亮走 _apply_word_pii_panel_updates 局部 patch 单独触发，避免重复渲染）。

    **privacyguard/word/candidate_dialog.py NEW 占位骨架**（Wave 3 完整 UI 行为）。模块 docstring "Phase 3 Word 候选审阅对话框（UX-01 / UX-02 极简版 — Wave 2 占位骨架，Wave 3 完整实施）"。定义：
    ```python
    from typing import List, Optional
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
    )

    class WordCandidateDialog(QDialog):
        """Phase 3 Word 候选审阅极简版（D-25 / UX-01 / UX-02 — Wave 2 占位，Wave 3 完整实施）"""
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
            layout.addWidget(QLabel('Word 候选审阅 — Wave 3 完整 UI 行为待实施'))
    ```
    __all__ = ['WordCandidateDialog', 'ENTITY_TYPE_LABEL']。模块顶部新增 `ENTITY_TYPE_LABEL` 字典（D-21 锁 + Visuals §Copywriting）：{'CN_ID_CARD': '身份证号', 'CN_PHONE': '手机号', 'CN_BANK_CARD': '银行卡号', 'CN_EMAIL': '电子邮箱', 'CN_USCC': '统一社会信用代码', 'CN_TAXPAYER_ID': '纳税人识别号（18 位）', 'CN_TAXPAYER_ID_15': '纳税人识别号（15 位）', 'CN_VAT_INVOICE': '增值税发票号', 'CN_BANK_ACCOUNT': '银行账号'}。**关键**：PyQt6.QtWidgets import 允许（PyQt6 是常驻依赖，与 Qt 框架生命周期绑定）。

    **privacyguard/word/__init__.py MODIFY**：Wave 1 已就位 WordCandidateDialog lazy forward；本任务**不修改**该文件（占位骨架已可被 lazy forward 加载）。如 Wave 1 占位骨架 import 失败，调整 _LAZY_IMPORTS['WordCandidateDialog'] target module 路径。

    **验证 GREEN**。运行命令 `python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v` 期望 4 个测试方法全 OK。运行 `python3 -c "from privacyguard.word.candidate_dialog import WordCandidateDialog; print('OK', WordCandidateDialog)"` 验证 import 不抛异常。运行 `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports tests.unit.test_app_config -v` 验证既有基线保持 green。
  </action>
  <verify>
    <automated>python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports -v 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v` 显示 4 个测试方法（test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml / test_build_pii_block_fragment_contains_short_code_badge / test_build_pii_mask_block_fragment_contains_mask_string_not_original / test_entity_type_short_code_covers_all_9_locked_types）全部 OK。
    - test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml 断言 stub.word_preview.page().runJavaScript 被调 + stub.word_preview.setHtml 未被调（cp27 契约锁定反向断言）。
    - test_build_pii_block_fragment_contains_short_code_badge 断言左栏 fragment 含 '<mark class="pii-highlight"' + 'data-entity-type="CN_ID_CARD"' + '<span class="pii-tag">ID</span>' + 原文 '53010219200508011X'，**且不**含 mask 字符串。
    - test_build_pii_mask_block_fragment_contains_mask_string_not_original 断言右栏 fragment 含 '<mark class="pii-mask"' + 'data-entity-type="CN_ID_CARD"' + mask 字符串，**且不**含原文 '53010219200508011X'。
    - test_entity_type_short_code_covers_all_9_locked_types 断言 ENTITY_TYPE_SHORT_CODE 字典覆盖 9 个 entity_type 且 ASCII uppercase 短码（ID / PHONE / BANK / EMAIL / USCC / TAX / TAX15 / VAT / ACCT）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v` 全部测试方法 green（Wave 1 7 个 + Wave 2 4 个 = 11 个）。
    - `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports tests.unit.test_app_config -v`（79/79 基线）全部 green — cp27 既有 build_word_panel_update_script 复用不破坏。
    - `python3 -c "from main import ENTITY_TYPE_SHORT_CODE; print(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'])"` 输出 ID（模块级常量可外部 import）。
    - `python3 -c "from privacyguard.word.candidate_dialog import WordCandidateDialog; print('OK')"` 输出 OK（占位骨架可被 lazy forward 加载）。
    - `python3 -m compileall -q main.py privacyguard tests` 退出码 0（语法 green）。
  </acceptance_criteria>
  <done>
    main.py 4 个方法 + 1 个模块级常量落地（_apply_word_pii_panel_updates / _build_pii_block_fragment / _build_pii_mask_block_fragment / _on_word_pii_page_result 真实实现 + ENTITY_TYPE_SHORT_CODE 字典）；左栏原文 + 短码徽章 + 右栏 partial mask 渲染契约落地；cp27 局部 patch 契约保持；privacyguard/word/candidate_dialog.py WordCandidateDialog 占位骨架就位；TestWordPIIPanelHighlights 4 个测试方法全部 GREEN；Wave 1 7 个测试方法保持 GREEN；79/79 既有基线保持 GREEN。
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
    Wave 2 GREEN 任务实施完成后：main.py 新增 4 个方法（_apply_word_pii_panel_updates / _build_pii_block_fragment / _build_pii_mask_block_fragment / 改进 _on_word_pii_page_result）+ 模块级常量 ENTITY_TYPE_SHORT_CODE 字典（9 短码 ASCII uppercase）；改进 _build_word_original_panel_updates 与 _build_word_replaced_panel_updates 把 pii 通道纳入合并路径；privacyguard/word/candidate_dialog.py WordCandidateDialog 占位骨架；TestWordPIIPanelHighlights 4 个测试方法 GREEN。
  </what-built>
  <how-to-verify>
    **步骤 1 — 启动应用**：`cd /mnt/g/Project/PrivacyGuard && python3 main.py`

    **步骤 2 — 构造含 PII 的 docx**：`python3 -c "from tests.fixtures.fake_word import build_fake_docx; p = build_fake_docx(); print(p)"`

    **步骤 3 — 主菜单 → Open → 选择合成的 docx**

    **步骤 4 — 等待 worker 完成**（status chip 显示 `已识别 N 项敏感内容`）

    **步骤 5 — 切换到对比模式**

    **步骤 6 — 观察左栏（原文预览）**：PII 命中位置出现红色半透明填充矩形（`<mark class="pii-highlight">` 背景 `#D64545@alpha 0.18` / `#FF6B6B@alpha 0.22`）；PII 命中位置左侧有红色短码徽章（`ID` / `PHONE` / `BANK` / `EMAIL` / `USCC` / `TAX` / `TAX15` / `VAT` / `ACCT`）；鼠标悬停 PII 命中位置 → 浏览器原生 tooltip 显示 `{entity_type全称} · {mask_sample}`。

    **步骤 7 — 观察右栏（替换预览）**：PII 命中位置出现绿色半透明填充矩形（`<mark class="pii-mask">` 背景 `#0FA968@alpha 0.12` / `#34D399@alpha 0.18`）；矩形内**只**显示 partial mask 字符串（如 `110101********1234`），**不**显示原文；鼠标悬停 → tooltip 显示 `已替换为：110101********1234`。

    **步骤 8 — 滚动 / 缩放 / 切换段落**：左右双栏**不**触发整页重渲染（cp27 契约锁定）；滚动位置 / 选中状态 / 缩放保持。

    **步骤 9 — 重新打开**：关闭 app；重新启动；再次打开同一 docx；PII 高亮与 mask 显示与首次一致。

    **通过条件**：步骤 6/7 双栏高亮 + tooltip 正确；步骤 8 cp27 增量 patch 不破坏滚动；步骤 9 重新打开一致。

    **不通过条件**（任一即触发 Wave 3 修复）：左栏未显示红色高亮或短码徽章缺失；右栏显示原文或未显示绿色 partial mask；滚动 / 缩放触发整页重渲染（cp27 契约破坏）；重新打开 docx 后高亮丢失。
  </how-to-verify>
  <action>
    阻塞型 checkpoint：等待用户回复 "approved" 或失败步骤与异常信息。Wave 2 GREEN 任务已完成 main.py 4 个方法 + ENTITY_TYPE_SHORT_CODE 字典 + privacyguard/word/candidate_dialog.py 占位骨架 + TestWordPIIPanelHighlights 4 测试方法 GREEN。本任务仅观察 UI 视觉，不修改代码。
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
| HTML injection through PII strings | hit.normalized 可能含 HTML 特殊字符（< > & \"）；必须 html.escape 后再插入到 <mark> 内部 |
| web_view.runJavaScript → JavaScript 引擎 | 拼接到 runJavaScript 字符串的内容必须严格转义；不直接拼接 hit.normalized 到 JavaScript 字符串中（cp27 既有 build_word_panel_update_script 已处理） |
| data-key 同步 | mammoth 转 HTML 时可能插入 <strong> / <em> 等 inline 标签；_apply_word_pii_panel_updates 假设 _add_data_key_attributes 已就位（Wave 1 既有 — 不重写） |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-03-SetHtmlRegression | Tampering / cp27 契约破坏 | _apply_word_pii_panel_updates | critical | mitigate | 严格走 web_view.page().runJavaScript(...)；TestWordPIIPanelHighlights 断言 runJavaScript 被调 + setHtml 未被调 |
| T-03-HTMLInjection | Information Disclosure / XSS (local preview) | _build_pii_block_fragment + _build_pii_mask_block_fragment | medium | mitigate | html.escape hit.normalized + hit.mask_strategy + key 字符串；TestWordPIIPanelHighlights 断言 < > & " 在输出 HTML 中被 escape |
| T-03-ShortCodeMissing | Tampering / UI 渲染异常 | main.py:ENTITY_TYPE_SHORT_CODE | low | mitigate | 9 短码字典在 main.py 模块级 + .get(entity_type, entity_type) fallback；新 entity_type 出现时返回 entity_type 字符串本身（不抛 KeyError） |
| T-03-MaskInLeftPane | Information Disclosure / UI 错位 | _build_pii_block_fragment | medium | mitigate | 左栏**只**写 hit.normalized[page_offset:page_offset+page_length]；TestWordPIIPanelHighlights 断言左栏 HTML 不含 hit.mask_strategy |
</threat_model>

<verification>
```bash
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
python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights -v
```
期望 4 个测试方法 OK。
</verification>

<success_criteria>
- [ ] main.py 4 个新增方法落地（_apply_word_pii_panel_updates / _build_pii_block_fragment / _build_pii_mask_block_fragment / 改进 _on_word_pii_page_result）
- [ ] main.py 模块级常量 ENTITY_TYPE_SHORT_CODE 字典落地（9 短码 ASCII uppercase）
- [ ] main.py _build_word_original_panel_updates + _build_word_replaced_panel_updates 把 pii 通道纳入合并路径
- [ ] privacyguard/word/candidate_dialog.py WordCandidateDialog 占位骨架就位
- [ ] TestWordPIIPanelHighlights 4 个测试方法全部 GREEN
- [ ] 86/86 既有基线（Wave 1 升级后）保持 GREEN
- [ ] cp27 增量 DOM patch 契约保持（runJavaScript 被调 + setHtml 未被调）
- [ ] 左栏原文 + 短码徽章 + 右栏 partial mask 视觉契约保持
- [ ] 真实 PyQt6 UI 双栏 PII 高亮 + partial mask 视觉验证通过
</success_criteria>

<output>
创建 `.planning/phases/03-word/03-02-engine-expansion-and-ui-SUMMARY.md` 当任务完成
</output>
