---
phase: 03-word
plan: 03
slug: candidate-dialog-and-packaging
type: execute
wave: 3
depends_on:
  - 03-02
files_modified:
  - privacyguard/word/candidate_dialog.py
  - main.py
  - privacyguard/__init__.py
  - packaging/windows/config/PrivacyGuard_windows.spec
  - packaging/macos/config/PrivacyGuard.spec
autonomous: false
requirements:
  - FMT-02
  - UX-01
  - UX-02
  - OPS-04
user_setup: []

estimate:
  tokens: 55000
  raw_tokens: 27500
  tasks: 3
  confidence: medium

must_haves:
  truths:
    - "WordCandidateDialog 完整 UI 行为落地：QDialog + QListWidget + 实体类型筛选下拉 + 来源筛选下拉 + 50 条分页 + 4 CTAs（确认选中的 N 项 / 全选当前页 / 清空当前选择 / 关闭），per 03-UI-SPEC §Visuals §WordCandidateDialog Layout + §Copywriting（UX-01 / UX-02 最低功能）"
    - "WordCandidateDialog PAGE_SIZE = 50（D-25 锁）；_refresh() 单次渲染 < 50ms（per 03-RESEARCH.md Pitfall 4 性能预算）"
    - "_build_hit_list 从 word_data 三个通道（pii / ocr / manual）收集全部 hit；_filtered_hits 按实体类型 + 来源双维度过滤；过滤结果为空时显示空态文案（per 03-UI-SPEC §Copywriting empty state）"
    - "确认选中的 N 项 CTA 把 checked 的 hit 列表回传给 main.py:_on_word_candidate_dialog_accept；main.py 调 _apply_word_pii_panel_updates 把 confirmed hit 注入 word_data[key][\"pii\"] 并触发 cp27 局部 patch（per D-25 + D-10）"
    - "packaging/windows/config/PrivacyGuard_windows.spec 与 packaging/macos/config/PrivacyGuard.spec hiddenimports 段字段级一致追加 5 项 privacyguard.word.* 隐藏导入：privacyguard.word.adapter / privacyguard.word.worker / privacyguard.word.redact / privacyguard.word.clear_doc_props / privacyguard.word.candidate_dialog（per cp30 教训扩展）"
    - "现有 86/86 测试基线（Wave 1 + Wave 2 升级后）保持通过 + 新增 TestWordCandidateDialog + TestWordCandidateDialogPagination 全部 green（per OPS-04 / OPS-07 baseline preservation）"
  artifacts:
    - privacyguard/word/candidate_dialog.py MODIFY (WordCandidateDialog 完整 UI 行为：_build_hit_list + _init_ui + _filtered_hits + _refresh + _prev_page + _next_page + accept + reject；ENTITY_TYPE_LABEL 字典；PAGE_SIZE = 50)
    - main.py MODIFY (_on_word_candidate_dialog_accept 把 confirmed hit 写回 word_data + 触发 cp27 patch；菜单 / 工具栏触发 WordCandidateDialog)
    - privacyguard/__init__.py MODIFY (无 — Wave 1 已就位 _LAZY_IMPORTS WordCandidateDialog forward)
    - packaging/windows/config/PrivacyGuard_windows.spec MODIFY (hiddenimports 段追加 5 项 privacyguard.word.*)
    - packaging/macos/config/PrivacyGuard.spec MODIFY (hiddenimports 段追加 5 项 privacyguard.word.*)
    - tests/unit/test_word_pii_pipeline.py MODIFY (TestWordCandidateDialog + TestWordCandidateDialogPagination)
  key_links:
    - "WordCandidateDialog (privacyguard/word/candidate_dialog.py) 到 word_data[*][\"pii\"|\"ocr\"|\"manual\"] 三通道数据源 (D-18 锁)"
    - "WordCandidateDialog.accept() 到 main.py:_on_word_candidate_dialog_accept 到 word_data[*][\"pii\"] 写回 + _apply_word_pii_panel_updates 触发 cp27 patch（D-10 + D-18 + D-25）"
    - "packaging/{windows,macos}/config/*.spec 到 PyInstaller Analysis.hiddenimports 字段（cp30 教训扩展 — frozen 启动必须能找到 privacyguard.word.* 模块）"
  prohibitions:
    - "不得让 WordCandidateDialog 引入 Phase 7 完整功能（实体类型全局开关 UX-03 / 文档级白名单 UX-05 / 撤销栈 UX-06）；Phase 3 仅做 50 条分页 + 实体类型筛选 + 来源筛选 + 4 CTAs 最低功能（per D-11 / D-25 锁）"
    - "不得让 WordCandidateDialog 单次 _refresh 渲染超过 100ms；5000 条候选必须分页 + PAGE_SIZE = 50（per 03-RESEARCH.md Pitfall 4 性能预算）"
    - "不得让 confirm 后的 hit 列表丢失 entity_type / source / key 信息；accepted.emit signal 必须传 (key, hit) 元组列表或 dict 列表（per D-18 契约）"
    - "不得让 packaging/{windows,macos}/config/*.spec 字段级不一致；双 spec 必须字段级一致追加 5 项 privacyguard.word.* hiddenimports（per cp30 教训扩展）"
    - "不得让 PyInstaller spec 在 privacyguard.pi 既有 13 项 hiddenimports 后插入 word 模块；必须独立 extend 段（避免破坏 Phase 2 既有隐藏导入）"
    - "不得让 WordCandidateDialog 暴露 PII 原文到 UI（除 normalized[:30] 截断显示外）；hit.normalized 截断 30 字符 + ellipsis（per 03-UI-SPEC §Visuals §PII Highlight §long-text 锁）"
  backstop_statements:
    - statement: "WordCandidateDialog 行标签（normalized[:30] + key）在 720p / 100% DPI 下截断干净、行高不溢出"
      verification: backstop

threat_model:
  trust_boundaries:
    - name: word_data[*][\"pii\"|\"ocr\"|\"manual\"] 输入
      description: WordCandidateDialog 接受的 word_data 来源于 MainWindow；hit 可能是 dict 或 PIIHit dataclass；_build_hit_list 必须防御性 isinstance check
    - name: PyInstaller frozen build → privacyguard.word.candidate_dialog
      description: 缺 hiddenimports 时 cp30 教训复现 ModuleNotFoundError；packaging/{windows,macos}/config/*.spec 字段级一致
    - name: accepted signal → main.py:_on_word_candidate_dialog_accept
      description: 跨组件信号；confirmed hit 列表回传 MainWindow；MainWindow 必须防御性 isinstance check hit 是 PIIHit 还是 dict
  stride:
    - id: T-03-CandidateDialogPhase7
      category: Tampering / scope creep
      component: WordCandidateDialog
      severity: low
      disposition: mitigate
      mitigation: 锁 D-25 极简版范围；tests/unit/test_word_pii_pipeline.py::TestWordCandidateDialog 断言无 Phase 7 全局开关 / 白名单 / 撤销栈字段
    - id: T-03-PaginationPerformance
      category: Denial of Service / UI 卡顿
      component: WordCandidateDialog._refresh
      severity: medium
      disposition: mitigate
      mitigation: PAGE_SIZE = 50；_filtered_hits 单次遍历 + 切片；tests/unit/test_word_pii_pipeline.py::TestWordCandidateDialogPagination 断言 > 50 条分页且 total_pages = ceil(N / 50)
    - id: T-03-PyInstallerParity
      category: Denial of Service / cp30 教训扩展
      component: packaging/{windows,macos}/config/*.spec
      severity: high
      disposition: mitigate
      mitigation: 双 spec 字段级一致；tests/unit/test_package_imports.py 验证 sys.modules 中可导入 privacyguard.word.* 全部 5 项
    - id: T-03-PiiLeakInDialog
      category: Information Disclosure
      component: WordCandidateDialog 行文本
      severity: medium
      disposition: mitigate
      mitigation: hit.normalized[:30] 截断显示 + '...' 后缀；tests/unit/test_word_pii_pipeline.py::TestWordCandidateDialog 断言行文本不含 normalized[30:] 原文
    - id: T-03-AcceptedSignalContract
      category: Tampering
      component: accepted signal payload
      severity: medium
      disposition: mitigate
      mitigation: accepted 信号携带 [(key, hit_dict), ...] 列表；main.py:_on_word_candidate_dialog_accept 必须防御性 isinstance check hit 类型；tests/unit/test_word_pii_pipeline.py::TestWordCandidateDialog 断言 accepted 信号 payload 包含 key + entity_type + mask_strategy 三个字段

---

<objective>
落地 Phase 3 候选审阅对话框（UX-01 / UX-02 最低功能）+ 跨平台 PyInstaller spec parity（OPS-04 cp30 教训扩展）。Wave 3 在 Wave 2 占位骨架基础上实施完整 WordCandidateDialog UI 行为 + 双 spec 字段级一致追加 5 项 privacyguard.word.* hiddenimports。
</objective>

<purpose>
Phase 3 用户故事第 3 条「用户可以浏览按 block 候选列表并逐条确认；列表筛选按 entity type 并在 > 50 条时分页」需要 WordCandidateDialog 完整 UI 行为。同时 Phase 3 完成度必须保证 Windows + macOS 双平台 PyInstaller frozen 包启动可正常 import privacyguard.word.* 5 个新模块（cp30 教训扩展）。Wave 3 同时落地这两个能力。
</purpose>

<output>
- privacyguard/word/candidate_dialog.py MODIFY：WordCandidateDialog 完整 UI 行为（_build_hit_list / _init_ui / _filtered_hits / _refresh / _prev_page / _next_page / accept 槽）；PAGE_SIZE = 50；4 CTAs；实体类型筛选 + 来源筛选 + 50 条分页 + 行 checkbox
- main.py MODIFY：_on_word_candidate_dialog_accept 把 confirmed hit 写回 word_data + 触发 cp27 patch；菜单 / 工具栏触发入口
- packaging/windows/config/PrivacyGuard_windows.spec MODIFY：hiddenimports 段追加 5 项 privacyguard.word.*
- packaging/macos/config/PrivacyGuard.spec MODIFY：hiddenimports 段追加 5 项 privacyguard.word.*
- tests/unit/test_word_pii_pipeline.py MODIFY：TestWordCandidateDialog + TestWordCandidateDialogPagination 完整实现
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
@.planning/phases/03-word/03-02-engine-expansion-and-ui-PLAN.md
@CLAUDE.md
@privacyguard/pii/hits.py (PIIHit 9 字段锁 — D-16)
@privacyguard/word/candidate_dialog.py (Wave 2 占位骨架)
@main.py:10777-10819 (_open_word_docx — Wave 1 + Wave 2 接线)
@main.py:11508 (_on_word_pii_page_result — Wave 1 + Wave 2 真实实现)
@packaging/windows/config/PrivacyGuard_windows.spec (cp30 教训 — Phase 2 既有 13 项 PII hiddenimports)
@packaging/macos/config/PrivacyGuard.spec (cp30 教训 — Phase 2 既有 13 项 PII hiddenimports)
</context>

<tasks>

<task type="auto" tdd="true">
  <name>RED — 写 TestWordCandidateDialog + TestWordCandidateDialogPagination 测试，断言 50 条分页 + 筛选 + 4 CTAs</name>
  <files>
    - tests/unit/test_word_pii_pipeline.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-UI-SPEC.md (lines 248-289 — WordCandidateDialog Layout 完整结构 + 4 CTAs)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 121-150 — Copywriting 4 CTAs 文案 + 实体类型 / 来源筛选标签 + 分页标签)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 421-430 — E3 WordCandidateDialog UI Considerations state coverage)
    - .planning/phases/03-word/03-RESEARCH.md (lines 621-777 — Pattern 4 WordCandidateDialog 完整代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 875-891 — Pitfall 4 _refresh 性能预算 < 50ms + PAGE_SIZE = 50)
    - .planning/phases/03-word/03-VALIDATION.md (lines 41-65 — Per-Task Verification Map 03-03-01/02)
    - privacyguard/word/candidate_dialog.py (Wave 2 占位骨架 — 当前只有 setWindowTitle + 单 QLabel)
    - tests/unit/test_word_pii_pipeline.py (Wave 1 + Wave 2 既有 11 个测试类 — 范本)
  </read_first>
  <action>
    在 tests/unit/test_word_pii_pipeline.py 追加 TestWordCandidateDialog 与 TestWordCandidateDialogPagination 两个测试类。本任务**只写测试**，主代码占位由 Wave 3 GREEN 任务实施。

    **TestWordCandidateDialog 测试类**（含 5 个测试方法）：

    **test_dialog_opens_with_all_hits_in_word_data**：构造 word_data = {"paragraph_5": {"text": "...", "ocr": [], "manual": [], "pii": [PIIHit(... CN_ID_CARD ...), PIIHit(... CN_PHONE ...)]}, "table_0_cell_0_0": {"text": "...", "ocr": [], "manual": [dict(start=0,end=18,text='53010219200508011X',replacement='[手动]')], "pii": []}}。构造 QApplication([]) 或 unittest.mock.patch('PyQt6.QtWidgets.QApplication.instance', return_value=Mock)；从 privacyguard.word.candidate_dialog import WordCandidateDialog；dlg = WordCandidateDialog(word_data)。断言 dlg._all_hits 长度 == 3（paragraph_5 内 2 个 pii hit + table_0_cell_0_0 内 1 个 manual hit）；断言 dlg.windowTitle() == 'Word 候选审阅'；断言 dlg._page == 0（初始页）。

    **test_entity_filter_changes_visible_rows**：构造 word_data 含 3 个 CN_ID_CARD + 2 个 CN_PHONE 共 5 个 pii hit（同上构造法）；dlg = WordCandidateDialog(word_data)；dlg._refresh() 调一次（构造后自动调，但显式调一次确保列表刷新）；断言 dlg.list_widget.count() == 5（PAGE_SIZE 50 全部可见）；dlg.entity_filter.setCurrentIndex(dlg.entity_filter.findData('CN_PHONE'))；dlg._refresh()；断言 dlg.list_widget.count() == 2（仅 PHONE 命中）；dlg.entity_filter.setCurrentIndex(0)（"全部类型"）；dlg._refresh()；断言 dlg.list_widget.count() == 5。

    **test_source_filter_changes_visible_rows**：构造 word_data 含 3 个 pii hit + 2 个 ocr hit + 1 个 manual hit（混合来源）；dlg = WordCandidateDialog(word_data)；dlg._refresh()；断言 dlg.list_widget.count() == 6；dlg.source_filter.setCurrentIndex(dlg.source_filter.findData('ocr'))；dlg._refresh()；断言 dlg.list_widget.count() == 2（仅 ocr 命中）；dlg.source_filter.setCurrentIndex(dlg.source_filter.findData('pii'))；dlg._refresh()；断言 dlg.list_widget.count() == 3。

    **test_confirmed_hit_emits_to_main_window**：构造 word_data = {"paragraph_5": {"text": "...", "ocr": [], "manual": [], "pii": [PIIHit(... CN_ID_CARD ..., page_offset=0, page_length=18, mask_strategy='110101********1234', normalized='53010219200508011X')]}}；dlg = WordCandidateDialog(word_data)；dlg._refresh()；断言 dlg.list_widget.count() == 1；构造 captured = []；dlg.confirmed.connect(lambda payload: captured.append(payload))（**关键**：Wave 3 GREEN 任务需新增 confirmed = pyqtSignal(list) 信号 — 承载 [(key, hit_dict), ...] 列表）；dlg._on_confirm_clicked()（**关键**：Wave 3 GREEN 任务需新增此方法 — 收集所有 checkbox checked 的 hit，调 confirmed.emit(payload)）；断言 len(captured) == 1；断言 captured[0] 是 list 类型；断言 len(captured[0]) == 1（确认 1 项）；assertion captured[0][0] 是 tuple (key, hit_dict) 或 dict with 'key' field；断言 captured[0][0] 含 'key' = 'paragraph_5' + 'entity_type' = 'CN_ID_CARD' + 'mask_strategy' = '110101********1234' 三个字段。

    **test_empty_state_when_all_hits_filtered_out**：构造 word_data 含 1 个 CN_ID_CARD pii hit；dlg = WordCandidateDialog(word_data)；dlg.entity_filter.setCurrentIndex(dlg.entity_filter.findData('CN_PHONE'))；dlg._refresh()；断言 dlg.list_widget.count() == 0；断言 dlg.page_label.text() 含 '0'（空页）；断言 dlg.btn_confirm（主 CTA）disabled / not enabled（**关键**：Wave 3 GREEN 任务新增 btn_confirm 字段名锁定）。注意：若 dialog 含 page_label '第 1 / 1 页（共 0 条）' 文案，断言 '当前筛选下无候选' 文本可见。

    **TestWordCandidateDialogPagination 测试类**（含 3 个测试方法）：

    **test_pagination_over_50_entries**：构造 word_data 含 60 个 pii hit（每个 key 1 个 hit，60 个不同 key）；dlg = WordCandidateDialog(word_data)；dlg._refresh()；断言 dlg.list_widget.count() == 50（第一页 50 条）；断言 dlg.page_label.text() 含 '第 1 / 2 页（共 60 条）' 或等价文案（**关键**：PAGE_SIZE = 50 + ceil(60/50) = 2 页）；断言 dlg.btn_next.isEnabled() == True；断言 dlg.btn_prev.isEnabled() == False（首页不能上一页）；dlg._next_page()；dlg._refresh()；断言 dlg.list_widget.count() == 10（第二页 10 条剩余）；断言 dlg.btn_next.isEnabled() == False（末页不能下一页）。

    **test_pagination_filter_combination**：构造 word_data 含 30 个 CN_ID_CARD + 30 个 CN_PHONE = 60 个 pii hit；dlg = WordCandidateDialog(word_data)；dlg.entity_filter.setCurrentIndex(dlg.entity_filter.findData('CN_ID_CARD'))；dlg._refresh()；断言 dlg.list_widget.count() == 30（CN_ID_CARD 全部可见，无需分页）；断言 dlg.page_label.text() 含 '第 1 / 1 页（共 30 条）'；断言 dlg.btn_next.isEnabled() == False。

    **test_row_label_truncates_normalized_at_30_chars**：构造 hit = PIIHit(... normalized='1234567890123456789012345678901234567890ABCDEFGHIJ' (50 chars) ..., page_offset=0, page_length=50)；word_data = {"paragraph_5": {"text": "...", "ocr": [], "manual": [], "pii": [hit]}}；dlg = WordCandidateDialog(word_data)；dlg._refresh()；断言 dlg.list_widget.count() == 1；row_text = dlg.list_widget.item(0).text()；断言 normalized[30:] = '12345678901234567890ABCDEFGHIJ' (20 chars) not in row_text（**关键**：截断 30 字符不暴露剩余 20 字符）；断言 normalized[:30] = '123456789012345678901234567890' (30 chars) in row_text；断言 '...' 或 '…' in row_text（截断标识符锁定）。

    实现注意：QDialog 构造需要 QApplication；可在 setUp 内 `self.app = QApplication.instance() or QApplication([])`。Mock PyQt6 信号：使用 `unittest.mock.Mock` 或 `QSignalSpy`（PyQt6 提供）。建议：测试中用 Mock 对象收集信号 callback，避免 QSignalSpy 依赖。

    测试方法标 RED：每个方法末尾用 `self.fail("Wave 3 GREEN 实施后此测试应 pass")` 占位；Wave 3 GREEN 任务移除 self.fail。
  </action>
  <verify>
    <automated>python3 -m compileall -q tests/unit/test_word_pii_pipeline.py && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialog tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination -v 2>&1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q tests/unit/test_word_pii_pipeline.py` 退出码 0（语法 green）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialog tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination -v` 显示 8 个测试方法全部 FAIL（AttributeError: 'WordCandidateDialog' object has no attribute '_all_hits' / 'entity_filter' / 'list_widget' / 'btn_confirm' / 'confirmed' 等 — Wave 3 GREEN 实施后此测试应 pass）— RED 基线确认。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v`（含 Wave 1 + Wave 2 既有 11 个测试类）显示既有 11 个测试方法保持 green，8 个新测试方法 FAIL（Wave 1 + Wave 2 状态未破坏）。
    - `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports -v` 既有 79/79 基线保持 green。
  </acceptance_criteria>
  <done>
    TestWordCandidateDialog 5 个测试方法 + TestWordCandidateDialogPagination 3 个测试方法 RED 骨架就位；测试方法明确断言 50 条分页 + 实体类型 / 来源筛选 + 4 CTAs + confirmed 信号 payload 契约 + 行 label 截断 30 字符；RED 失败原因可定位到具体 AttributeError（_all_hits / entity_filter / list_widget / btn_confirm / confirmed 等）。
  </done>
  <reversibility>rating="reversible" rationale="仅测试文件追加；删除 2 个测试类即可恢复 Wave 2 状态。"</reversibility>
</task>

<task type="auto" tdd="true">
  <name>GREEN — 实施 WordCandidateDialog 完整 UI 行为 + main.py 菜单接入 + 双 spec PyInstaller hiddenimports parity</name>
  <files>
    - privacyguard/word/candidate_dialog.py
    - main.py
    - packaging/windows/config/PrivacyGuard_windows.spec
    - packaging/macos/config/PrivacyGuard.spec
  </files>
  <read_first>
    - .planning/phases/03-word/03-UI-SPEC.md (lines 248-289 — WordCandidateDialog Layout 完整结构)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 121-150 — Copywriting 4 CTAs 文案 + 实体类型 / 来源筛选标签)
    - .planning/phases/03-word/03-RESEARCH.md (lines 621-777 — Pattern 4 WordCandidateDialog 完整代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 875-891 — Pitfall 4 _refresh 性能预算)
    - .planning/phases/03-word/03-PATTERNS.md (lines 16-37 — privacyguard/word/candidate_dialog.py 角色范本)
    - .planning/phases/03-word/03-PATTERNS.md (lines 32-37 — packaging/{windows,macos} spec cp30 parity 范本)
    - privacyguard/word/candidate_dialog.py (Wave 2 占位骨架 — 当前只有 setWindowTitle + 单 QLabel)
    - main.py:10777-10819 (_open_word_docx — Wave 1 + Wave 2 接线)
    - main.py:11508 (_on_word_pii_page_result — Wave 1 + Wave 2 真实实现)
    - packaging/windows/config/PrivacyGuard_windows.spec:138-175 (既有 13 项 PII hiddenimports 段 — Wave 3 在其后 extend)
    - packaging/macos/config/PrivacyGuard.spec:31-48 + 94-109 (既有 13 项 PII hiddenimports 段 — Wave 3 在其后 extend)
  </read_first>
  <action>
    Wave 3 GREEN 任务。本任务实施 WordCandidateDialog 完整 UI 行为 + main.py 菜单接入 + 双 spec PyInstaller hiddenimports parity；目标让 TestWordCandidateDialog + TestWordCandidateDialogPagination 8 个测试方法全部 green。

    **privacyguard/word/candidate_dialog.py 完整实施**（替换 Wave 2 占位骨架）。模块顶部保留 03-RESEARCH.md:637-656 既有 import（QCheckBox / QComboBox / QDialog / QHBoxLayout / QLabel / QListWidget / QListWidgetItem / QPushButton / QVBoxLayout / Qt / List）+ 新增 `from PyQt6.QtCore import pyqtSignal`（confirmed 信号）+ `from privacyguard.pii.hits import PIIHit`（hit dataclass 容器）。

    模块级常量：
    ```python
    PAGE_SIZE = 50  # D-25 锁

    ENTITY_TYPE_LABEL = {
        'CN_ID_CARD': '身份证号',
        'CN_PHONE': '手机号',
        'CN_BANK_CARD': '银行卡号',
        'CN_EMAIL': '电子邮箱',
        'CN_USCC': '统一社会信用代码',
        'CN_TAXPAYER_ID': '纳税人识别号（18 位）',
        'CN_TAXPAYER_ID_15': '纳税人识别号（15 位）',
        'CN_VAT_INVOICE': '增值税发票号',
        'CN_BANK_ACCOUNT': '银行账号',
    }
    ```
    （D-21 + Visuals §Copywriting 锁定 — 9 个 entity type 全中文标签）

    class WordCandidateDialog(QDialog) 完整实施：
    - pyqtSignal: confirmed = pyqtSignal(list)（payload: [(key, hit_dict), ...] 列表 — main.py:_on_word_candidate_dialog_accept 接收）
    - __init__(self, word_data: dict, parent=None)：super().__init__(parent)；self.word_data = word_data or {}；self._all_hits: List[dict] = []；self._page = 0；self._build_hit_list()；self.setWindowTitle('Word 候选审阅')；self.resize(700, 600)；self._init_ui()。
    - _build_hit_list(self)：遍历 self.word_data.items()；for key, data in ...: for src in ('pii', 'ocr', 'manual'): for hit in data.get(src, []) or []: 防御性 isinstance check — 如果 hit 是 PIIHit dataclass 转 hit = asdict(hit)（asdict 来自 dataclasses；模块顶部 import）；如果 hit 是 dict 直接保留；normalized = hit.get('normalized', '') or ''；self._all_hits.append({'key': key, 'hit': hit, 'source': src, 'normalized': normalized})。**关键**：防御性 hit 类型分派（PIIHit vs dict）。
    - _init_ui(self)：QVBoxLayout(self)；
      - 顶部工具栏 QHBoxLayout：QLabel('实体类型：') + self.entity_filter (QComboBox + addItem('全部', '') + for et, label in ENTITY_TYPE_LABEL.items(): addItem(label, et) + currentIndexChanged.connect(self._refresh)) + QLabel('来源：') + self.source_filter (QComboBox + addItem('全部', '') + for src in ('pii', 'ocr', 'manual'): addItem(src, src) + currentIndexChanged.connect(self._refresh)) + addStretch(1) + QLabel('0 项已选')（self.selected_count_label）；
      - 候选列表 self.list_widget = QListWidget()（垂直、无滚动条样式覆盖）；
      - 分页底部 QHBoxLayout：self.btn_prev = QPushButton('上一页') + clicked.connect(self._prev_page) + self.btn_next = QPushButton('下一页') + clicked.connect(self._next_page) + self.page_label = QLabel('0/0') + addStretch(1) + QPushButton('关闭') + clicked.connect(self.reject)；
      - CTA 底部 QHBoxLayout：addStretch(1) + self.btn_clear_selection = QPushButton('清空当前选择') + clicked.connect(self._on_clear_selection) + QPushButton('全选当前页') + clicked.connect(self._on_select_all) + self.btn_confirm = QPushButton('确认选中的 0 项') + clicked.connect(self._on_confirm_clicked)（主 CTA — filled #0F6CBD / white text 由 _apply_dialog_theme 自动套用）；
      - addStretch(1) + QLabel('当前筛选下无候选，请放宽实体类型或来源筛选。')（self.empty_label，仅在 0 条时 visible）
    - _filtered_hits(self) -> List[dict]：et = self.entity_filter.currentData()；src = self.source_filter.currentData()；out = []；for entry in self._all_hits: if et and entry['hit'].get('entity_type') != et: continue；if src and entry['source'] != src: continue；out.append(entry)；return out。**关键**：防御性 .get() 链（hit 可能是 dict 或 dataclass asdict 后 dict；都用 dict 访问）。
    - _refresh(self)：self.list_widget.clear()；filtered = self._filtered_hits()；total = len(filtered)；total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)；if self._page >= total_pages: self._page = total_pages - 1；if self._page < 0: self._page = 0；start = self._page * PAGE_SIZE；end = min(start + PAGE_SIZE, total)；for entry in filtered[start:end]: hit = entry['hit']；et = hit.get('entity_type', 'UNKNOWN')；label_text = ENTITY_TYPE_LABEL.get(et, et)；normalized = entry['normalized']；display_text = normalized[:30] + ('...' if len(normalized) > 30 else '')；row_text = f"[{entry['source']}] {label_text} · {display_text} @ {entry['key']}"；item = QListWidgetItem(row_text)；item.setData(Qt.ItemDataRole.UserRole, entry)；item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)；item.setCheckState(Qt.CheckState.Checked)；self.list_widget.addItem(item)；self.page_label.setText(f'第 {self._page + 1} / {total_pages} 页（共 {total} 条）')；self.btn_prev.setEnabled(self._page > 0)；self.btn_next.setEnabled(self._page < total_pages - 1)；self.empty_label.setVisible(total == 0)；self.btn_confirm.setEnabled(total > 0)；self._update_selected_count()。**关键**：每行默认 checked（D-25 极简版 — 不做"逐条取消"功能，但默认全选 + 用户可手动 uncheck）。**性能**：单次 _refresh 遍历 filtered[start:end] 最多 50 条；性能预算 < 50ms（03-RESEARCH.md Pitfall 4）。
    - _update_selected_count(self)：checked = sum(1 for i in range(self.list_widget.count()) if self.list_widget.item(i).checkState() == Qt.CheckState.Checked)；self.selected_count_label.setText(f'{checked} 项已选')；self.btn_confirm.setText(f'确认选中的 {checked} 项')。
    - _prev_page(self)：self._page -= 1；self._refresh()。
    - _next_page(self)：self._page += 1；self._refresh()。
    - _on_select_all(self)：for i in range(self.list_widget.count()): self.list_widget.item(i).setCheckState(Qt.CheckState.Checked)；self._update_selected_count()。
    - _on_clear_selection(self)：for i in range(self.list_widget.count()): self.list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)；self._update_selected_count()。
    - _on_confirm_clicked(self)：payload = []；for i in range(self.list_widget.count()): item = self.list_widget.item(i)；if item.checkState() == Qt.CheckState.Checked: entry = item.data(Qt.ItemDataRole.UserRole)；hit = entry['hit']；key = entry['key']；hit_dict = hit if isinstance(hit, dict) else asdict(hit) if isinstance(hit, PIIHit) else {}；payload.append({'key': key, 'hit': hit_dict, 'source': entry['source']})；self.confirmed.emit(payload)；self.accept()。
    __all__ = ['WordCandidateDialog', 'ENTITY_TYPE_LABEL', 'PAGE_SIZE']。**关键**：confirmed 信号 payload 是 list[dict] 形式，每个 dict 含 'key' / 'hit' / 'source' 三个字段；hit 字段是 hit 的 dict 形态（asdict 后）。

    **main.py MODIFY**：新增 _on_word_candidate_dialog_accept(self, payload: list) 槽 + WordCandidateDialog 触发入口。

    _on_word_candidate_dialog_accept 实现：from privacyguard.pii.hits import PIIHit；from privacyguard.word.candidate_dialog import WordCandidateDialog（lazy import 函数内）；hits_by_key = {}；for entry in payload: key = entry.get('key')；hit_dict = entry.get('hit', {})；if not isinstance(hit_dict, dict): continue；try: hit = PIIHit(**hit_dict)；except (TypeError, ValueError) as e: print(f'[Word PII WARN] invalid hit dict: {e}'); continue；hits_by_key.setdefault(key, []).append(hit)；with QMutexLocker(self._word_data_lock): for key, hits in hits_by_key.items(): if key in self.word_data: existing_pii = self.word_data[key].get('pii', []) or []；existing_set = {(h.page_offset, h.page_length, h.entity_type) for h in existing_pii}；merged = list(existing_pii)；for hit in hits: if (hit.page_offset, hit.page_length, hit.entity_type) not in existing_set: merged.append(hit)；self.word_data[key]['pii'] = merged；for key, hits in hits_by_key.items(): self._apply_word_pii_panel_updates(key, self.word_data[key].get('pii', []))。

    WordCandidateDialog 触发入口：在 main.py 菜单栏（紧邻现有文件菜单 / 工具菜单）新增 `action_word_candidate_review = QAction('查看全部候选', self)` + triggered.connect(self._open_word_candidate_dialog)；_open_word_candidate_dialog 实现：if not self.word_data: QMessageBox.information(self, '提示', '请先打开 Word 文档'); return；from privacyguard.word.candidate_dialog import WordCandidateDialog（lazy import）；dlg = WordCandidateDialog(self.word_data, parent=self)；dlg.confirmed.connect(self._on_word_candidate_dialog_accept)；dlg.exec()。

    **packaging/windows/config/PrivacyGuard_windows.spec MODIFY**（cp30 教训扩展）：在文件 line 172（Phase 2 既有 13 项 PII hiddenimports 段末）`]` 后追加（独立 extend 段）：
    ```python
    # Phase 3 (03-word) — 5 new Word submodules (cp30 parity with macOS spec)
    privacyguard_hiddenimports.extend([
        'privacyguard.word',
        'privacyguard.word.adapter',
        'privacyguard.word.worker',
        'privacyguard.word.redact',
        'privacyguard.word.clear_doc_props',
        'privacyguard.word.candidate_dialog',
    ])
    ```
    同时在文件 line 281（hiddenimports 列表 line 280 末 `'privacyguard.pii.validators.taxpayer_id',` 后）的 `] + onnx_hiddenimports ...` 之前追加 5 项：
    ```python
    # Phase 3 (03-word) — 5 new Word submodules (cp30 parity with macOS spec)
    'privacyguard.word',
    'privacyguard.word.adapter',
    'privacyguard.word.worker',
    'privacyguard.word.redact',
    'privacyguard.word.clear_doc_props',
    'privacyguard.word.candidate_dialog',
    ```
    **关键**：双段 extend（既有 `privacyguard_hiddenimports.extend([...])` 段 + 既有 `hiddenimports=[...]` 列表段）都必须追加；保持与 Phase 2 既有 13 项 PII hiddenimports 平级。

    **packaging/macos/config/PrivacyGuard.spec MODIFY**（cp30 教训扩展）：在文件 line 109（Phase 2 既有 13 项 PII hiddenimports 段末）`]` 后追加（**macOS spec 与 Windows spec 字段级一致**）：
    ```python
    # Phase 3 (03-word) — 5 new Word submodules (cp30 parity with Windows spec)
    'privacyguard.word',
    'privacyguard.word.adapter',
    'privacyguard.word.worker',
    'privacyguard.word.redact',
    'privacyguard.word.clear_doc_props',
    'privacyguard.word.candidate_dialog',
    ```
    **关键**：macOS spec **不**分双段（Windows 是 `privacyguard_hiddenimports.extend([...])` + `hiddenimports=[...]` 双段；macOS 只有 `hiddenimports=[...]` 单段）；按 macOS 现有 spec 结构追加 5 项即可。

    **验证 GREEN**。运行命令 `python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialog tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination -v` 期望 8 个测试方法全 OK。运行 `grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec` 期望双 spec 各 5 行 `privacyguard.word.*` 命中。运行 `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports tests.unit.test_word_pii_pipeline -v` 验证既有 86/86 基线保持 green。
  </action>
  <verify>
    <automated>python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialog tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination tests.unit.test_package_imports -v 2>&1 | tail -20 && echo "=== spec parity check ===" && grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialog -v` 显示 5 个测试方法（test_dialog_opens_with_all_hits_in_word_data / test_entity_filter_changes_visible_rows / test_source_filter_changes_visible_rows / test_confirmed_hit_emits_to_main_window / test_empty_state_when_all_hits_filtered_out）全部 OK。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination -v` 显示 3 个测试方法（test_pagination_over_50_entries / test_pagination_filter_combination / test_row_label_truncates_normalized_at_30_chars）全部 OK。
    - test_pagination_over_50_entries 断言 60 个 hit 分为 2 页 + 每页 50 / 10 条 + 翻页按钮正确 enable/disable。
    - test_row_label_truncates_normalized_at_30_chars 断言行 label 含 normalized[:30] + '...' + 不含 normalized[30:]。
    - test_confirmed_hit_emits_to_main_window 断言 confirmed 信号 payload 含 [(key, hit_dict), ...] 列表，每个 hit_dict 含 'entity_type' + 'mask_strategy' 字段。
    - `grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec` 输出 12 行（双段 × 6 项 — 含 'privacyguard.word' 与 5 子模块）。
    - `grep -E "privacyguard.word" packaging/macos/config/PrivacyGuard.spec` 输出 6 行（单段 × 6 项）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v` 全部测试方法 green（Wave 1 7 + Wave 2 4 + Wave 3 8 = 19 个）。
    - `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports tests.unit.test_app_config tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_pdf_text_hit_dedup tests.unit.test_config_alignment tests.unit.test_fstring_safety -v`（79/79 基线）全部 green。
    - `python3 -c "from privacyguard.word.candidate_dialog import WordCandidateDialog; d = WordCandidateDialog({}); print('PAGE_SIZE =', d.PAGE_SIZE)"` 输出 PAGE_SIZE = 50（D-25 锁验证）。
    - `python3 -m compileall -q main.py privacyguard tests packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec` 退出码 0（语法 green；spec 文件 compileall 可选 — 退出 0 即 OK）。
  </acceptance_criteria>
  <done>
    privacyguard/word/candidate_dialog.py WordCandidateDialog 完整 UI 行为落地（PAGE_SIZE = 50 + 9 entity 标签 + 4 CTAs + 实体类型 / 来源筛选 + 50 条分页 + 行 label 截断 30 字符 + confirmed 信号 payload 契约）；main.py _on_word_candidate_dialog_accept 写回 word_data + 触发 cp27 patch；main.py 菜单 / 工具栏触发入口；packaging/{windows,macos} 双 spec 字段级一致追加 5 项 privacyguard.word.* hiddenimports；TestWordCandidateDialog 5 + TestWordCandidateDialogPagination 3 共 8 个测试方法全部 GREEN；Wave 1 + Wave 2 既有 11 个测试方法保持 GREEN；79/79 既有基线保持 GREEN。
  </done>
  <reversibility>rating="costly" rationale="WordCandidateDialog 完整 UI 行为落地 + 双 spec hiddenimports 扩展；删除需恢复 Wave 2 状态并删除 spec 字段。"</reversibility>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Wave 3 人工验证 — WordCandidateDialog UI 行为 + 双 spec PyInstaller 隐式导入在真实 UI 中正确</name>
  <files>
    - main.py
    - privacyguard/word/candidate_dialog.py
    - packaging/windows/config/PrivacyGuard_windows.spec
    - packaging/macos/config/PrivacyGuard.spec
  </files>
  <read_first>
    - .planning/phases/03-word/03-UI-SPEC.md (lines 248-289 — WordCandidateDialog Layout 完整结构)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 121-150 — Copywriting 4 CTAs 文案)
    - .planning/phases/03-word/03-VALIDATION.md (lines 80-91 — Manual-Only Verifications)
    - .planning/phases/03-word/03-PATTERNS.md (lines 32-37 — PyInstaller hiddenimports parity 范本)
    - main.py:_on_word_candidate_dialog_accept (Wave 3 GREEN 实施后)
    - privacyguard/word/candidate_dialog.py:WordCandidateDialog (Wave 3 GREEN 实施后)
  </read_first>
  <what-built>
    Wave 3 GREEN 任务实施完成后：privacyguard/word/candidate_dialog.py WordCandidateDialog 完整 UI 行为（PAGE_SIZE = 50 + 9 entity 标签 + 4 CTAs + 实体类型 / 来源筛选 + 50 条分页 + 行 label 截断 30 字符 + confirmed 信号 payload 契约）；main.py _on_word_candidate_dialog_accept 写回 word_data + 触发 cp27 patch；main.py 菜单 / 工具栏触发 WordCandidateDialog 入口；packaging/{windows,macos} 双 spec 字段级一致追加 5 项 privacyguard.word.* hiddenimports；TestWordCandidateDialog 5 + TestWordCandidateDialogPagination 3 共 8 个测试方法 GREEN。
  </what-built>
  <how-to-verify>
    **步骤 1 — 启动应用**：`cd /mnt/g/Project/PrivacyGuard && python3 main.py`

    **步骤 2 — 构造含 60+ PII 命中的 docx**：`python3 -c "from tests.fixtures.fake_word import build_fake_docx; p = build_fake_docx(); print(p)"`

    **步骤 3 — 主菜单 → Open → 选择合成的 docx**；等待 worker 完成（status chip 显示 `已识别 N 项敏感内容`，N ≥ 5）

    **步骤 4 — 工具菜单（或工具栏）→ 点击「查看全部候选」入口**

    **步骤 5 — 观察 WordCandidateDialog UI**：窗口标题 = 'Word 候选审阅'；顶部工具栏实体类型筛选 + 来源筛选 + 'N 项已选' 标签；中间 QListWidget 显示全部 hit + 行 checkbox 默认 checked；底部翻页栏（> 50 条时）+ 4 CTAs（清空当前选择 / 全选当前页 / 确认选中的 N 项 / 关闭）。

    **步骤 6 — 操作测试**：实体类型筛选过滤；来源筛选过滤；翻页（'下一页' → 第二页）；取消 checkbox → 'N 项已选' 标签递减；点击'清空当前选择' → 主 CTA disabled；点击'全选当前页' → 当前页 check；点击'确认选中的 N 项' → dialog accept + word_data 同步。

    **步骤 7 — 关闭 dialog 后回到主窗口**：双栏预览 PII 高亮 + partial mask 与 dialog 确认前一致（confirmed hit 已写入 word_data['pii']）。

    **步骤 8 — 跨平台 PyInstaller 验证**（如可构建）：Windows `packaging\\windows\\scripts\\build_complete.bat` → 启动 dist/PrivacyGuard.exe → 无 `ModuleNotFoundError: privacyguard.word.*`；macOS `./packaging/macos/scripts/build_complete.sh` → 同样无 ModuleNotFoundError。如未配置交叉编译环境可跳过本步骤（spec parity 已通过 grep 验证）。

    **通过条件**：步骤 5 UI 与 Copywriting 一致；步骤 6 操作无异常；步骤 7 双栏同步；步骤 8 PyInstaller 启动可 import（如可构建）。

    **不通过条件**（任一即触发 Wave 4 修复）：WordCandidateDialog UI 元素缺失或位置错误；翻页 / 筛选 / 取消 / 全选 / 确认任一操作抛异常或无效；confirmed hit 写入 word_data 后双栏预览不同步；PyInstaller frozen 包启动报 ModuleNotFoundError。
  </how-to-verify>
  <action>
    阻塞型 checkpoint：等待用户回复 "approved" 或失败步骤与异常信息。Wave 3 GREEN 任务已完成 WordCandidateDialog 完整 UI 行为 + main.py 接线 + 双 spec hiddenimports parity + 8 个测试方法 GREEN。本任务仅观察 UI 行为 + PyInstaller 启动（如可构建），不修改代码。
  </action>
  <resume-signal>Type "approved" to proceed to Wave 4, or describe the failing step + visual/exception evidence to trigger Wave 3 GREEN fix.</resume-signal>
  <verify>
    <automated>echo '人工验证 checkpoint — 阻塞型门禁，需用户输入 approved 后 Wave 4 才可启动'</automated>
  </verify>
  <acceptance_criteria>
    - 用户在 UI 验证步骤 1-7 全部通过 + 步骤 8（如可构建）通过；用户回复 "approved"
    - 若失败：用户报告具体失败步骤与异常信息，Wave 3 GREEN 任务需进一步修复
  </acceptance_criteria>
  <done>
    真实 PyQt6 UI 中 WordCandidateDialog UI 与 Copywriting 完全一致；翻页 / 筛选 / 取消 / 全选 / 确认操作生效；confirmed hit 写入 word_data 后双栏 PII 高亮 + partial mask 同步；PyInstaller frozen 包启动可正常 import privacyguard.word.*（如可构建）；用户回复 "approved"；Wave 4 可启动。
  </done>
  <reversibility>rating="reversible" rationale="UI 验证仅观察，不修改代码；如未通过，回到 Wave 3 GREEN 任务修复。"</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| word_data[*]["pii"\|"ocr"\|"manual"] 输入 | WordCandidateDialog 接受的 word_data 来源于 MainWindow；hit 可能是 dict 或 PIIHit dataclass；_build_hit_list 必须防御性 isinstance check |
| PyInstaller frozen build → privacyguard.word.candidate_dialog | 缺 hiddenimports 时 cp30 教训复现 ModuleNotFoundError；packaging/{windows,macos}/config/*.spec 字段级一致 |
| accepted signal → main.py:_on_word_candidate_dialog_accept | 跨组件信号；confirmed hit 列表回传 MainWindow；MainWindow 必须防御性 isinstance check hit 是 PIIHit 还是 dict |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-03-CandidateDialogPhase7 | Tampering / scope creep | WordCandidateDialog | low | mitigate | 锁 D-25 极简版范围；TestWordCandidateDialog 断言无 Phase 7 全局开关 / 白名单 / 撤销栈字段 |
| T-03-PaginationPerformance | Denial of Service / UI 卡顿 | WordCandidateDialog._refresh | medium | mitigate | PAGE_SIZE = 50；_filtered_hits 单次遍历 + 切片；TestWordCandidateDialogPagination 断言 > 50 条分页 |
| T-03-PyInstallerParity | Denial of Service / cp30 教训扩展 | packaging/{windows,macos}/config/*.spec | high | mitigate | 双 spec 字段级一致；tests/unit/test_package_imports.py 验证 sys.modules 中可导入 privacyguard.word.* 全部 5 项 |
| T-03-PiiLeakInDialog | Information Disclosure | WordCandidateDialog 行文本 | medium | mitigate | hit.normalized[:30] 截断显示 + '...' 后缀；TestWordCandidateDialog 断言行文本不含 normalized[30:] 原文 |
| T-03-AcceptedSignalContract | Tampering | accepted signal payload | medium | mitigate | accepted 信号携带 [{'key': key, 'hit': hit_dict, 'source': src}, ...] 列表；main.py 防御性 isinstance check；TestWordCandidateDialog 断言 payload 包含 key + entity_type + mask_strategy 三个字段 |
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

# spec parity 检查
grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec
```
Wave 3 单独门禁：
```bash
python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordCandidateDialog tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination -v
```
期望 8 个测试方法 OK。
</verification>

<success_criteria>
- [ ] privacyguard/word/candidate_dialog.py WordCandidateDialog 完整 UI 行为落地
- [ ] main.py _on_word_candidate_dialog_accept 写回 word_data + 触发 cp27 patch
- [ ] main.py 菜单 / 工具栏触发 WordCandidateDialog 入口
- [ ] packaging/{windows,macos} 双 spec 字段级一致追加 5 项 privacyguard.word.* hiddenimports
- [ ] TestWordCandidateDialog 5 + TestWordCandidateDialogPagination 3 共 8 个测试方法全部 GREEN
- [ ] 86/86 既有基线（Wave 1 + Wave 2 升级后）保持 GREEN
- [ ] WordCandidateDialog UI 与 Copywriting 锁定文案完全一致
- [ ] 真实 PyQt6 UI WordCandidateDialog 操作流程验证通过
</success_criteria>

<output>
创建 `.planning/phases/03-word/03-03-candidate-dialog-and-packaging-SUMMARY.md` 当任务完成
</output>
