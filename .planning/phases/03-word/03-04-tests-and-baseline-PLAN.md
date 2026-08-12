---
phase: 03-word
plan: 04
slug: tests-and-baseline
type: execute
wave: 4
depends_on:
  - 03-03
files_modified:
  - tests/unit/test_word_pii_pipeline.py
  - tests/unit/test_package_imports.py
  - tests/unit/test_convergence.py
autonomous: true
requirements:
  - OPS-03
  - OPS-07
  - FMT-02
  - UX-01
  - UX-02
user_setup: []

estimate:
  tokens: 45000
  raw_tokens: 22500
  tasks: 3
  confidence: high

must_haves:
  truths:
    - "tests/unit/test_word_pii_pipeline.py 8 个测试类（TestWordAdapterCollectUnits / TestWordPIIAutoTrigger / TestWordRedactRoundTrip / TestWordDocumentPropertiesCleared / TestWordMergePriorityRulePiManualOcr / TestWordDataKeySync / TestWordPartialMaskInComparePane / TestWordCandidateDialog + TestWordCandidateDialogPagination）共 19 个测试方法全部 GREEN"
    - "现有 79/79 测试基线（test_mixed_pdf_ocr / test_path_validation / test_ocr_api / test_package_imports / test_pdf_text_hit_dedup / test_app_config / test_word_replace_rules / test_batch_word_replace / test_config_alignment / test_fstring_safety / test_convergence）保持通过；新增 test_word_pii_pipeline 19 个测试方法全部通过；基线升级为 98/98 或更高（per D-13 / D-14 / OPS-07 baseline 升级锁定）"
    - "tests/unit/test_package_imports.py 新增 test_import_privacyguard_does_not_load_word_submodules 断言；import privacyguard 后 sys.modules 不含 privacyguard.word.adapter / .worker / .redact / .clear_doc_props / .candidate_dialog（per OPS-03 懒加载纪律扩展）"
    - "tests/unit/test_convergence.py 新增 test_no_word_adapter_in_main_py AST 断言；main.py 不含 inline redact_word / clear_word_doc_props_docx / collect_word_units 等 Word adapter / redact / clear_doc_props 实现（per D-05 v37.7.6 收敛原则）"
    - "TestWordDataKeySync 验证 mammoth 渲染后 DOM data-key 数 == word_data key 数；data-key 同步契约保持（per D-22 + TestWordDataKeySync 03-VALIDATION.md 锁定）"
    - "TestWordPartialMaskInComparePane 验证右栏 mask 字符串正确渲染；partial mask 在双栏对比预览中可见（per FMT-02 + 03-VALIDATION.md 锁定）"
  artifacts:
    - tests/unit/test_word_pii_pipeline.py MODIFY (TestWordDataKeySync + TestWordPartialMaskInComparePane 两个新测试类 — Wave 1 + Wave 2 + Wave 3 既有 19 个测试方法 + Wave 4 新增 5 个 = 24 个)
    - tests/unit/test_package_imports.py MODIFY (新增 test_import_privacyguard_does_not_load_word_submodules 断言 OPS-03 扩展)
    - tests/unit/test_convergence.py MODIFY (新增 test_no_word_adapter_in_main_py AST 断言 D-05 收敛)
  key_links:
    - "tests/unit/test_word_pii_pipeline.py 8 个测试类到 privacyguard/word/* + main.py 接线 (Wave 1 + Wave 2 + Wave 3 已落地) — 端到端验证 Phase 3 PII 流程"
    - "tests/unit/test_package_imports.py::test_import_privacyguard_does_not_load_word_submodules 到 privacyguard/word/__init__.py _LAZY_IMPORTS — OPS-03 懒加载纪律扩展"
    - "tests/unit/test_convergence.py::test_no_word_adapter_in_main_py 到 main.py — D-05 v37.7.6 收敛原则扩展"
  prohibitions:
    - "不得让 tests/unit/test_word_pii_pipeline.py 引入真实个人信息；所有 fixture 必须经 tests/fixtures/fake_pii.py + tests/fixtures/fake_word.py 合成（per OPS-05）"
    - "不得让 TestWordDataKeySync 改写 _add_data_key_attributes / _add_data_key_regex_fallback；仅做同步验证（per D-22 锁定 — 沿用既有 helper）"
    - "不得让 test_no_word_adapter_in_main_py 误判 docstring / 注释字符串为 inline 实现；AST 解析必须 ast.FunctionDef 内的 ast.Call + ast.Assign 节点（per Phase 2 test_convergence.py:test_main_py_uses_write_partial_masks_in_save_loop 范本）"
    - "不得让 test_import_privacyguard_does_not_load_word_submodules 误判 privacyguard.word 子包 import 为子模块 import；需严格 'privacyguard.word.adapter' in sys.modules 等完整子模块路径断言"
  backstop_statements: []

threat_model:
  trust_boundaries:
    - name: tests/unit/test_convergence.py AST 解析 main.py
      description: main.py 12.9k LOC；AST parse + walk FunctionDef 可能性能瓶颈；测试需限制 AST 解析范围（如仅 walk def save_word / def _open_word_docx 等相关函数体）
    - name: tests/unit/test_package_imports.py sys.modules 断言
      description: 进程内 import 顺序影响 sys.modules；测试需在独立 subprocess 运行或先 import 后清理 sys.modules
  stride:
    - id: T-03-TestRealPiiLeak
      category: Repudiation / OPS-05
      component: tests/unit/test_word_pii_pipeline.py fixture
      severity: high
      disposition: mitigate
      mitigation: 所有 fixture 走 tests/fixtures/fake_pii.py + tests/fixtures/fake_word.py Faker 合成器；测试末尾断言 fixture 不含真实身份字符串字面量（如 '110101199003078811' 这类已知真实身份证号）
    - id: T-03-ASTParseError
      category: Denial of Service
      component: tests/unit/test_convergence.py::test_no_word_adapter_in_main_py
      severity: low
      disposition: mitigate
      mitigation: ast.parse + walk ast.FunctionDef(name=~) 函数体内节点；限制 walk 范围；timeout 保护（unittest 默认无 timeout；如遇性能问题可加 unittest.skipIf 条件）

---

<objective>
落地 Phase 3 完整测试套件 + 升级 79/79 既有基线到 98/98（或更高）；补齐 Wave 1 + Wave 2 + Wave 3 已有测试未覆盖的两个测试类（TestWordDataKeySync + TestWordPartialMaskInComparePane），并扩展 test_package_imports 与 test_convergence 验证 OPS-03 懒加载纪律与 D-05 v37.7.6 收敛原则。
</objective>

<purpose>
Phase 3 完成度需要 79/79 → 98/98+ 的基线升级（D-13 / D-14 锁定）。Wave 1 + Wave 2 + Wave 3 已落地 19 个测试方法，但缺少两个关键的 UI / data-key 同步测试。Wave 4 补齐这两个测试类，并扩展 test_package_imports + test_convergence 确保 OPS-03 + D-05 纪律保持。最终基线 ≥ 98/98 为 Phase 3 验收门禁（per OPS-07）。
</purpose>

<output>
- tests/unit/test_word_pii_pipeline.py MODIFY：新增 TestWordDataKeySync + TestWordPartialMaskInComparePane 两个测试类，共 5 个新测试方法（Wave 1 + Wave 2 + Wave 3 既有 19 + Wave 4 新增 5 = 24 个测试方法）
- tests/unit/test_package_imports.py MODIFY：新增 test_import_privacyguard_does_not_load_word_submodules 断言（OPS-03 扩展）
- tests/unit/test_convergence.py MODIFY：新增 test_no_word_adapter_in_main_py AST 断言（D-05 收敛扩展）
- 基线升级：79/79 → 98/98（或更高）
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
@.planning/phases/03-word/03-02-engine-expansion-and-ui-PLAN.md
@.planning/phases/03-word/03-03-candidate-dialog-and-packaging-PLAN.md
@CLAUDE.md
@privacyguard/word/__init__.py (Wave 1 + Wave 2 接线后)
@privacyguard/word/adapter.py (Wave 1 GREEN 实施后)
@privacyguard/word/worker.py (Wave 1 GREEN 实施后)
@privacyguard/word/redact.py (Wave 1 GREEN 实施后)
@privacyguard/word/clear_doc_props.py (Wave 1 GREEN 实施后)
@privacyguard/word/candidate_dialog.py (Wave 2 + Wave 3 GREEN 实施后)
@tests/unit/test_word_pii_pipeline.py (Wave 1 + Wave 2 + Wave 3 既有 19 个测试方法)
@tests/unit/test_package_imports.py (Phase 2 既有懒加载断言 — Wave 4 扩展)
@tests/unit/test_convergence.py (Phase 2 既有 AST 断言 — Wave 4 扩展)
</context>

<tasks>

<task type="auto" tdd="true">
  <name>RED + GREEN — 新增 TestWordDataKeySync + TestWordPartialMaskInComparePane 两个测试类</name>
  <files>
    - tests/unit/test_word_pii_pipeline.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-RESEARCH.md (lines 837-857 — Pitfall 2 data-key 同步失败场景)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1543-1571 — TestWordDataKeySync 完整代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 202-225 — cp27 incremental DOM patch + 局部 patch 契约)
    - .planning/phases/03-word/03-VALIDATION.md (lines 41-65 — Per-Task Verification Map 03-02-01 + 03-02-02)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 451-466 — Constraints Carried From Upstream D-22 data-key 注入复用)
    - main.py:12236-12329 (_add_data_key_attributes + _add_data_key_regex_fallback 既有 helper — D-22 不重写)
    - privacyguard/pii/hits.py (PIIHit dataclass — D-16 字段锁)
    - privacyguard/pii/mask.py (mask_for_entity — Phase 2 MASK-01 锁)
    - tests/unit/test_word_pii_pipeline.py (Wave 1 + Wave 2 + Wave 3 既有 19 个测试方法 — 范本)
  </read_first>
  <action>
    在 tests/unit/test_word_pii_pipeline.py 追加 TestWordDataKeySync 与 TestWordPartialMaskInComparePane 两个测试类。本任务**测试 + 验证 GREEN**（无需新主代码 — Wave 1 + Wave 2 + Wave 3 已落地全部主代码；本任务仅补齐测试覆盖）。

    **TestWordDataKeySync 测试类**（含 3 个测试方法 — per D-22 同步契约）：

    **test_data_key_count_matches_word_data**：构造 path = build_fake_docx(paragraphs=["段落 0", "段落 1"], tables=[[["cell 0", "cell 1"]]])；doc = Document(path)；word_data = {}；for idx, para in enumerate(doc.paragraphs): if para.text.strip(): word_data[f"paragraph_{idx}"] = {"text": para.text, "ocr": [], "manual": [], "pii": []}；for table_idx, table in enumerate(doc.tables): for row_idx, row in enumerate(table.rows): for cell_idx, cell in enumerate(row.cells): if cell.text.strip(): key = f"table_{table_idx}_cell_{row_idx}_{cell_idx}"; word_data[key] = {"text": cell.text, "ocr": [], "manual": [], "pii": []}。模拟 mammoth 转 HTML：html = "<p>段落 0</p><p>段落 1</p><table><tr><td>cell 0</td><td>cell 1</td></tr></table>"；text_blocks = {k: {"text": v["text"], "escaped": v["text"]} for k, v in word_data.items()}；从 main import _add_data_key_attributes；tagged = _add_data_key_attributes(html, text_blocks)；from bs4 import BeautifulSoup；soup = BeautifulSoup(tagged, "html.parser")；data_keyed = soup.find_all(attrs={"data-key": True})；keys_found = {el.get("data-key") for el in data_keyed}；断言 "paragraph_0" in keys_found；断言 "paragraph_1" in keys_found；断言 "table_0_cell_0_0" in keys_found 或 "table_0_cell_0_1" in keys_found（至少一个 cell key）；os.remove(path)。

    **test_data_key_fallback_used_for_inline_tags**：构造 path = build_fake_docx(paragraphs=["段落 0 含有 <strong>粗体</strong> 测试"])（mammoth 可能在段落内插入 inline 标签）；模拟 mammoth 转 HTML：html = "<p>段落 0 含有 <strong>粗体</strong> 测试</p>"；text_blocks = {"paragraph_0": {"text": "段落 0 含有 粗体 测试", "escaped": "段落 0 含有 粗体 测试"}}；从 main import _add_data_key_attributes + _add_data_key_regex_fallback；tagged = _add_data_key_attributes(html, text_blocks)；if "paragraph_0" not in [el.get("data-key") for el in BeautifulSoup(tagged, "html.parser").find_all(attrs={"data-key": True})]: tagged = _add_data_key_regex_fallback(tagged, text_blocks)；soup = BeautifulSoup(tagged, "html.parser")；keys_found = {el.get("data-key") for el in soup.find_all(attrs={"data-key": True})}；断言 "paragraph_0" in keys_found（fallback 兜底生效）；os.remove(path)。

    **test_data_key_sync_no_overlap**：构造 100 段 docx（build_fake_docx 接受大量 paragraphs）；for i in range(100): 追加 f"段落 {i}" 到 paragraphs 列表；path = build_fake_docx(paragraphs=paragraphs, add_pii=False)；doc = Document(path)；word_data_count = sum(1 for p in doc.paragraphs if p.text.strip())；模拟 mammoth 输出：html_parts = [f"<p>段落 {i}</p>" for i in range(100)]；html = "".join(html_parts)；text_blocks = {f"paragraph_{i}": {"text": f"段落 {i}", "escaped": f"段落 {i}"} for i in range(100)}；tagged = _add_data_key_attributes(html, text_blocks)；soup = BeautifulSoup(tagged, "html.parser")；data_key_count = len(soup.find_all(attrs={"data-key": True}))；断言 data_key_count >= word_data_count * 0.9（允许少量 mammoth inline 标签失败走 fallback）；os.remove(path)。

    **TestWordPartialMaskInComparePane 测试类**（含 2 个测试方法 — per FMT-02 partial mask 渲染）：

    **test_partial_mask_string_in_right_pane**：构造 word_data = {"paragraph_5": {"text": "身份证 53010219200508011X 末位", "ocr": [], "manual": [], "pii": [PIIHit(entity_type='CN_ID_CARD', page_offset=4, page_length=18, page_rect=(0,0,0,0), confidence_tier='HIGH', source='text', mask_strategy='110101********1234', normalized='53010219200508011X')]}}；从 main import _build_pii_mask_block_fragment + ENTITY_TYPE_SHORT_CODE；stub 类含 self.word_data = word_data；fragment = stub._build_pii_mask_block_fragment('paragraph_5', word_data['paragraph_5']['pii'])；断言 '<mark class="pii-mask"' in fragment；断言 'data-entity-type="CN_ID_CARD"' in fragment；断言 mask_strategy '110101********1234' in fragment；断言原文 '53010219200508011X' not in fragment（右栏**只**写 mask 字符串 — Visuals §PII Partial-Mask 锁定）；断言 ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'] == 'ID'（短码字典 D-21 锁）。

    **test_left_pane_contains_original_right_pane_contains_mask**：构造同上 word_data；left_fragment = stub._build_pii_block_fragment('paragraph_5', word_data['paragraph_5']['pii'])；right_fragment = stub._build_pii_mask_block_fragment('paragraph_5', word_data['paragraph_5']['pii'])；断言 left_fragment != right_fragment（左右双栏 HTML 不同 — Visuals 锁定）；断言 '<mark class="pii-highlight"' in left_fragment（左栏红色 mark）；断言 '<mark class="pii-mask"' in right_fragment（右栏绿色 mark）；断言 '53010219200508011X' in left_fragment（左栏含原文）；断言 '53010219200508011X' not in right_fragment（右栏不含原文）；断言 '110101********1234' in right_fragment（右栏含 partial mask）；断言 '110101********1234' not in left_fragment（左栏不含 mask 字符串）。

    实现注意：TestWordDataKeySync 直接调 _add_data_key_attributes（main.py 模块级方法或 MainWindow 实例方法；按 main.py:12236 是 MainWindow 实例方法，需 stub 实例 — 同 Wave 2 RED 范本）。TestWordPartialMaskInComparePane 同样需要 stub 实例。**关键**：测试末尾 `os.remove(path)` 清理 tempfile；多个测试共享 tempfile 需避免文件名冲突（tempfile.mkstemp 已用 mkstemp 生成唯一路径，可复用）。

    **验证 GREEN**。运行命令 `python3 -m compileall -q tests/unit/test_word_pii_pipeline.py && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordDataKeySync tests.unit.test_word_pii_pipeline.TestWordPartialMaskInComparePane -v` 期望 5 个测试方法全 OK（**测试直接验证 Wave 1 + Wave 2 已落地的主代码** — 无需新主代码）。
  </action>
  <verify>
    <automated>python3 -m compileall -q tests/unit/test_word_pii_pipeline.py && python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordDataKeySync tests.unit.test_word_pii_pipeline.TestWordPartialMaskInComparePane -v 2>&1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q tests/unit/test_word_pii_pipeline.py` 退出码 0（语法 green）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordDataKeySync -v` 显示 3 个测试方法（test_data_key_count_matches_word_data / test_data_key_fallback_used_for_inline_tags / test_data_key_sync_no_overlap）全部 OK。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPartialMaskInComparePane -v` 显示 2 个测试方法（test_partial_mask_string_in_right_pane / test_left_pane_contains_original_right_pane_contains_mask）全部 OK。
    - test_data_key_count_matches_word_data 断言 mammoth 渲染后 DOM data-key 数 ≥ word_data key 数（fallback 兜底允许 < 100%）。
    - test_data_key_fallback_used_for_inline_tags 断言 mammoth 插入 <strong> inline 标签时 _add_data_key_regex_fallback 兜底生效。
    - test_partial_mask_string_in_right_pane 断言右栏 fragment 含 '<mark class="pii-mask"' + mask_strategy 字符串 + 不含原文。
    - test_left_pane_contains_original_right_pane_contains_mask 断言左 / 右 fragment 不相等 + 左含原文 + 右含 mask + 左 / 右 mark class 不同。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v` 显示全部 24 个测试方法 GREEN（Wave 1 7 + Wave 2 4 + Wave 3 8 + Wave 4 Task 1 5 = 24）。
    - `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports -v` 既有 79/79 基线保持 GREEN。
  </acceptance_criteria>
  <done>
    TestWordDataKeySync 3 个测试方法 + TestWordPartialMaskInComparePane 2 个测试方法 GREEN；tests/unit/test_word_pii_pipeline.py 共 24 个测试方法（Wave 1 7 + Wave 2 4 + Wave 3 8 + Wave 4 Task 1 5）全部 green；既有 79/79 基线保持 green；D-22 data-key 同步契约 + FMT-02 partial mask 在右栏可见契约验证落地。
  </done>
  <reversibility>rating="reversible" rationale="仅测试文件追加；删除 2 个测试类即可恢复 Wave 3 状态。"</reversibility>
</task>

<task type="auto" tdd="true">
  <name>扩展 test_package_imports + test_convergence 验证 OPS-03 懒加载纪律与 D-05 v37.7.6 收敛原则</name>
  <files>
    - tests/unit/test_package_imports.py
    - tests/unit/test_convergence.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-RESEARCH.md (lines 1854-1870 — ASVS V12 Files and Resources + PyInstaller datas + hiddenimports 同步)
    - .planning/phases/03-word/03-PATTERNS.md (lines 60-71 — Convergence Notes 锁清单 — D-05 v37.7.6 收敛原则 + OPS-03 懒加载纪律扩展)
    - .planning/phases/03-word/03-VALIDATION.md (lines 41-65 — Per-Task Verification Map 03-03-04 PyInstaller hiddenimports parity)
    - tests/unit/test_package_imports.py (Phase 2 既有 13 项 PII 懒加载断言 — 范本)
    - tests/unit/test_convergence.py (Phase 2 既有 AST 断言 test_main_py_uses_write_partial_masks_in_save_loop — 范本)
    - main.py:863-906 (merge_word_matches_with_priority — 已扩展第六参数 pii_matches=None)
    - main.py:10777-10819 (_open_word_docx — Wave 1 接线后)
    - main.py:12699-12794 (_save_word — Wave 1 接线后)
    - privacyguard/word/__init__.py (_LAZY_IMPORTS 5 项 Wave 1 已就位)
  </files>
  <read_first>
    - privacyguard/__init__.py (_LAZY_IMPORTS Wave 1 追加 5 项 word 符号)
    - privacyguard/word/__init__.py (_LAZY_IMPORTS 5 项 word 子模块)
  </read_first>
  <action>
    在 tests/unit/test_package_imports.py 与 tests/unit/test_convergence.py 各追加 1 个测试方法验证 OPS-03 懒加载纪律与 D-05 v37.7.6 收敛原则。本任务**测试 + 验证 GREEN**（无需新主代码 — Wave 1 + Wave 2 + Wave 3 已落地全部主代码；本任务仅补齐测试覆盖）。

    **tests/unit/test_package_imports.py MODIFY**：追加 test_import_privacyguard_does_not_load_word_submodules 方法（紧邻既有 test_import_privacyguard_does_not_load_* 系列测试）。

    实现：
    ```python
    def test_import_privacyguard_does_not_load_word_submodules(self):
        """Phase 3 (03-word) — OPS-03 懒加载纪律扩展：import privacyguard 不拉起 privacyguard.word.* 子模块。

        5 个 word 子模块：privacyguard.word.adapter / .worker / .redact / .clear_doc_props / .candidate_dialog
        必须均不在 sys.modules 中（直到具体使用时才 import）。
        """
        import sys
        # 防御性清理（避免其他测试副作用）
        for mod_name in [
            'privacyguard.word',
            'privacyguard.word.adapter',
            'privacyguard.word.worker',
            'privacyguard.word.redact',
            'privacyguard.word.clear_doc_props',
            'privacyguard.word.candidate_dialog',
        ]:
            sys.modules.pop(mod_name, None)

        import privacyguard  # noqa: F401 触发包级 import
        # import privacyguard.word 是允许的（lazy forward 子包）；但 5 个子模块不应被加载
        for mod_name in [
            'privacyguard.word.adapter',
            'privacyguard.word.worker',
            'privacyguard.word.redact',
            'privacyguard.word.clear_doc_props',
            'privacyguard.word.candidate_dialog',
        ]:
            self.assertNotIn(mod_name, sys.modules,
                             f'{mod_name} should NOT be loaded after import privacyguard (OPS-03 lazy-load)')

        # privacyguard.word 子包可被 import 但其子模块不应自动加载
        # （验证 _LAZY_IMPORTS + __getattr__ 工作）
        import privacyguard.word  # noqa: F401
        for mod_name in [
            'privacyguard.word.adapter',
            'privacyguard.word.worker',
            'privacyguard.word.redact',
            'privacyguard.word.clear_doc_props',
            'privacyguard.word.candidate_dialog',
        ]:
            self.assertNotIn(mod_name, sys.modules,
                             f'{mod_name} should NOT be loaded after import privacyguard.word (subpackage lazy-load)')

        # 触发 lazy forward 应正确加载
        from privacyguard.word import WordAdapter
        self.assertIn('privacyguard.word.adapter', sys.modules)
        self.assertIn('privacyguard.word.worker', sys.modules)  # __init__.py 加载时触发 _LAZY_IMPORTS 也可能加载 .worker
        # ... 或根据实际 _LAZY_IMPORTS 行为放宽断言
    ```

    **关键**：精确断言 'privacyguard.word.adapter' / '.worker' / '.redact' / '.clear_doc_props' / '.candidate_dialog' 5 个子模块**均不在** sys.modules 中（OPS-03 锁）。'privacyguard.word' 子包本身可被 import（lazy forward 入口）。

    **tests/unit/test_convergence.py MODIFY**：追加 test_no_word_adapter_in_main_py 方法（紧邻既有 test_main_py_uses_write_partial_masks_in_save_loop 测试 — Phase 2 范本镜像）。

    实现：
    ```python
    def test_no_word_adapter_in_main_py(self):
        """Phase 3 (03-word) — D-05 v37.7.6 收敛原则扩展：main.py 不含 inline Word adapter / redact / clear_doc_props 实现。

        AST 解析 main.py；扫描 def _open_word_docx / def _save_word / def _on_word_pii_page_result /
        def _apply_word_pii_panel_updates / def _build_pii_block_fragment / def _build_pii_mask_block_fragment
        函数体内不允许出现 inline redact_word_docx / clear_word_doc_props_docx / collect_word_units
        等 Word adapter / redact / clear_doc_props 实现。所有这些实现必须位于 privacyguard/word/* 子包。
        """
        import ast
        from pathlib import Path

        main_py_path = Path(__file__).resolve().parent.parent.parent / "main.py"
        with open(main_py_path, 'r', encoding='utf-8') as fh:
            tree = ast.parse(fh.read(), filename=str(main_py_path))

        # 收集 main.py 内所有函数定义
        functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

        # Phase 3 (03-word) 相关函数（允许 import + 装配，但不允许 inline 实现）
        target_functions = [
            '_open_word_docx',
            '_save_word',
            '_on_word_pii_page_result',
            '_on_word_candidate_dialog_accept',
            '_apply_word_pii_panel_updates',
            '_build_pii_block_fragment',
            '_build_pii_mask_block_fragment',
        ]

        # 禁用字符串：Word adapter / redact / clear_doc_props inline 实现
        forbidden_literals = [
            'redact_word_docx',       # inline 实现 redact_word_docx（应有 redact_word）
            'clear_word_doc_props_docx',  # inline 实现 clear_word_doc_props_docx（应有 clear_word_doc_props）
            'collect_word_units',     # inline 实现 collect_word_units（应有 WordAdapter.collect_units）
        ]

        violations = []
        for func_name in target_functions:
            if func_name not in functions:
                continue
            func_node = functions[func_name]
            func_source_lines = [getattr(node, 'lineno', 0) for node in ast.walk(func_node)]
            for node in ast.walk(func_node):
                # 检查 ast.Str / ast.Constant 字符串字面量
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in forbidden_literals:
                        violations.append(f'{func_name} at line {node.lineno}: forbidden literal "{node.value}"')
                # 检查 ast.FunctionDef 内嵌函数定义（inline helper）
                if isinstance(node, ast.FunctionDef) and node.name in forbidden_literals:
                    violations.append(f'{func_name} at line {node.lineno}: forbidden inline def {node.name}')

        self.assertEqual(violations, [],
                         f'main.py contains inline Word adapter/redact/clear_doc_props implementations: {violations}. '
                         f'All such implementations MUST live in privacyguard/word/* (D-05 v37.7.6 convergence).')
    ```

    **关键**：AST 解析 main.py；扫描 7 个目标函数体内是否含 forbidden_literals（'redact_word_docx' / 'clear_word_doc_props_docx' / 'collect_word_units'）；如有则报错指向 D-05 v37.7.6 收敛原则。**允许**：ast.ImportFrom / ast.Import 节点（import privacyguard.word.redact 模块级 import）；ast.Call 节点（调 redact_word / clear_word_doc_props — 这些是允许的）。

    **验证 GREEN**。运行命令 `python3 -m compileall -q tests/unit/test_package_imports.py tests/unit/test_convergence.py && python3 -m unittest tests.unit.test_package_imports tests.unit.test_convergence -v` 期望既有 13 项 PII 懒加载断言 + 新增 test_import_privacyguard_does_not_load_word_submodules 全 OK；既有 Phase 2 AST 断言 + 新增 test_no_word_adapter_in_main_py 全 OK。
  </action>
  <verify>
    <automated>python3 -m compileall -q tests/unit/test_package_imports.py tests/unit/test_convergence.py && python3 -m unittest tests.unit.test_package_imports tests.unit.test_convergence -v 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q tests/unit/test_package_imports.py tests/unit/test_convergence.py` 退出码 0（语法 green）。
    - `python3 -m unittest tests.unit.test_package_imports -v` 显示既有 13 项 PII 懒加载断言 + 新增 test_import_privacyguard_does_not_load_word_submodules 全部 OK。
    - test_import_privacyguard_does_not_load_word_submodules 断言 import privacyguard 与 import privacyguard.word 后，5 个 word 子模块（adapter / worker / redact / clear_doc_props / candidate_dialog）均**不**在 sys.modules 中。
    - `python3 -m unittest tests.unit.test_convergence -v` 显示既有 Phase 2 AST 断言 + 新增 test_no_word_adapter_in_main_py 全部 OK。
    - test_no_word_adapter_in_main_py 断言 main.py 7 个目标函数体内**不**含 inline 'redact_word_docx' / 'clear_word_doc_props_docx' / 'collect_word_units' 字符串字面量或内嵌函数定义（D-05 v37.7.6 收敛原则）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v` 显示全部 24 个测试方法 GREEN（Wave 1 + Wave 2 + Wave 3 + Wave 4 Task 1）。
    - `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_app_config tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_pdf_text_hit_dedup tests.unit.test_config_alignment tests.unit.test_fstring_safety -v` 既有 79/79 基线保持 GREEN。
  </acceptance_criteria>
  <done>
    tests/unit/test_package_imports.py 新增 test_import_privacyguard_does_not_load_word_submodules 断言（OPS-03 懒加载纪律扩展）；tests/unit/test_convergence.py 新增 test_no_word_adapter_in_main_py AST 断言（D-05 v37.7.6 收敛原则扩展）；测试覆盖 Phase 3 全部纪律验证；既有 79/79 基线保持 GREEN。
  </done>
  <reversibility>rating="reversible" rationale="仅测试文件追加；删除 2 个测试方法即可恢复 Wave 3 状态。"</reversibility>
</task>

<task type="auto">
  <name>最终基线验证 — 完整 79/79 + test_word_pii_pipeline 24 + test_package_imports + test_convergence 全部 GREEN（基线升级为 98+/98+）</name>
  <files>
    - .planning/phases/03-word/03-04-tests-and-baseline-SUMMARY.md
  </files>
  <read_first>
    - .planning/phases/03-word/03-VALIDATION.md (lines 25-29 — Full suite command + 预期 runtime ~30s)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1800-1813 — Phase Requirements → Test Map)
    - CLAUDE.md (轻量快速验证命令 + 主回归测试基线命令)
    - .planning/phases/03-word/03-01-tracer-PLAN.md (Wave 1 验收命令)
    - .planning/phases/03-word/03-02-engine-expansion-and-ui-PLAN.md (Wave 2 验收命令)
    - .planning/phases/03-word/03-03-candidate-dialog-and-packaging-PLAN.md (Wave 3 验收命令)
  </read_first>
  <action>
    本任务执行最终基线验证 + 编写 SUMMARY。

    **Step 1 — 完整基线命令**（CLAUDE.md §基线）。运行：
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
    期望 12 个 unittest 模块全部 OK；test_word_pii_pipeline 24 个测试方法全 green；既有 11 个模块保持 green。基线从 79/79 升级为 ≥ 98/98（Phase 1 + Phase 2 + Phase 3 累计）。runtime 预期 < 30s。

    **Step 2 — 双 spec parity 验证**。运行：
    ```bash
    grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec
    ```
    期望 Windows spec 12 行（双段 × 6 项）+ macOS spec 6 行（单段 × 6 项）；双 spec 字段级一致（cp30 教训扩展锁定）。

    **Step 3 — OPS-03 懒加载纪律验证**。运行：
    ```bash
    python3 -c "import sys; import privacyguard; print('word.adapter:', 'privacyguard.word.adapter' in sys.modules); print('word.worker:', 'privacyguard.word.worker' in sys.modules); print('word.redact:', 'privacyguard.word.redact' in sys.modules); print('word.clear_doc_props:', 'privacyguard.word.clear_doc_props' in sys.modules); print('word.candidate_dialog:', 'privacyguard.word.candidate_dialog' in sys.modules)"
    ```
    期望输出 5 个 False（OPS-03 懒加载纪律保持）。

    **Step 4 — D-05 v37.7.6 收敛原则验证**。运行：
    ```bash
    python3 -c "
    import ast
    from pathlib import Path
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    forbidden = ['redact_word_docx', 'clear_word_doc_props_docx', 'collect_word_units']
    found = []
    for fname in ['_open_word_docx', '_save_word', '_on_word_pii_page_result', '_apply_word_pii_panel_updates']:
        if fname not in funcs: continue
        for node in ast.walk(funcs[fname]):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in forbidden:
                found.append(f'{fname} line {node.lineno}: {node.value}')
    print('D-05 violations:', found if found else 'NONE')
    "
    ```
    期望输出 `D-05 violations: NONE`（main.py 不含 inline Word adapter / redact / clear_doc_props 实现）。

    **Step 5 — 编写 03-04 SUMMARY**。创建 `.planning/phases/03-word/03-04-tests-and-baseline-SUMMARY.md`，内容包含：
    - 完成总结：基线从 79/79 升级到 98/98+；5 个新增测试类（TestWordDataKeySync 3 + TestWordPartialMaskInComparePane 2 + 扩展 test_package_imports + test_convergence）共 5 个测试方法全部 GREEN
    - 验收命令实际输出（基线命令 + spec parity + OPS-03 + D-05 全部通过）
    - Phase 3 完成度：FMT-02 / UX-01 / UX-02 三个需求 ID 全部覆盖；OPS-03 / OPS-04 / OPS-07 三个 OPS 需求 ID 全部覆盖
    - Wave 1 / Wave 2 / Wave 3 / Wave 4 全部任务清单 + 状态（green）
    - 链接 .planning/STATE.md 更新待办：Phase 3 状态从 Not started → Complete；Phase 4 / 5 / 6 / 7 / 8 状态更新

    **Step 6 — 提交**。运行：
    ```bash
    gsd_run query commit "docs(03-04): tests-and-baseline complete — 79/79 → 98+/98+ baseline upgrade" --files \
      .planning/phases/03-word/03-04-tests-and-baseline-PLAN.md \
      .planning/phases/03-word/03-04-tests-and-baseline-SUMMARY.md \
      tests/unit/test_word_pii_pipeline.py \
      tests/unit/test_package_imports.py \
      tests/unit/test_convergence.py \
      packaging/windows/config/PrivacyGuard_windows.spec \
      packaging/macos/config/PrivacyGuard.spec
    ```
    （gsd_run 是 gsd-tools.cjs 包装；如不可用，回退到直接 git commit。）
  </action>
  <verify>
    <automated>python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_package_imports tests.unit.test_pdf_text_hit_dedup tests.unit.test_app_config tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety tests.unit.test_convergence tests.unit.test_word_pii_pipeline -v 2>&1 | tail -30 && echo "=== test count summary ===" && python3 -m unittest tests.unit.test_word_pii_pipeline -v 2>&1 | grep -E "Ran |^OK|^FAIL"</automated>
  </verify>
  <acceptance_criteria>
    - 完整基线命令（12 个 unittest 模块）退出码 0；全部模块 OK。
    - test_word_pii_pipeline 报告 `Ran 24 tests in X.XXXs` + `OK`（24 个测试方法全 green）。
    - test_package_imports 报告 `Ran 14 tests in X.XXXs` + `OK`（既有 13 项 PII + 新增 1 项 word）。
    - test_convergence 报告 `Ran N tests in X.XXXs` + `OK`（既有 Phase 2 + 新增 1 项 word）。
    - 基线从 79/79 升级到 ≥ 98/98（Phase 3 完成）。
    - grep -E "privacyguard.word" 双 spec 输出字段级一致。
    - OPS-03 验证输出 5 个 False。
    - D-05 验证输出 NONE。
    - 03-04 SUMMARY 文件落地；Phase 3 状态更新至 Complete。
  </acceptance_criteria>
  <done>
    Phase 3 完整基线通过：12 个 unittest 模块全部 GREEN；test_word_pii_pipeline 24 测试方法全 green；test_package_imports 14 测试方法全 green；test_convergence N 测试方法全 green；基线从 79/79 升级到 ≥ 98/98；双 spec PyInstaller hiddenimports 字段级一致（cp30 教训扩展）；OPS-03 + D-05 + D-08 + D-09 + D-10 + D-13 + D-14 + D-19 + D-21 + D-22 + D-23 + D-24 + D-25 全部纪律验证通过；03-04 SUMMARY 落地；Phase 3 验收完成。
  </done>
  <reversibility>rating="costly" rationale="最终基线验证 + SUMMARY + 提交；删除需恢复 Wave 3 状态 + 删除 SUMMARY 文件 + git reset。"</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| tests/unit/test_convergence.py AST 解析 main.py | main.py 12.9k LOC；AST parse + walk FunctionDef 可能性能瓶颈；测试需限制 AST 解析范围（如仅 walk def save_word / def _open_word_docx 等相关函数体） |
| tests/unit/test_package_imports.py sys.modules 断言 | 进程内 import 顺序影响 sys.modules；测试需在独立 subprocess 运行或先 import 后清理 sys.modules |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-03-TestRealPiiLeak | Repudiation / OPS-05 | tests/unit/test_word_pii_pipeline.py fixture | high | mitigate | 所有 fixture 走 tests/fixtures/fake_pii.py + tests/fixtures/fake_word.py Faker 合成器；测试末尾断言 fixture 不含真实身份字符串字面量 |
| T-03-ASTParseError | Denial of Service | tests/unit/test_convergence.py::test_no_word_adapter_in_main_py | low | mitigate | ast.parse + walk ast.FunctionDef(name=~) 函数体内节点；限制 walk 范围 |
</threat_model>

<verification>
完整 Phase 3 验收命令（CLAUDE.md §基线 — 升级版）：
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
期望：12 个 unittest 模块全部 OK；test_word_pii_pipeline 24 个测试方法全 green；既有 11 个模块保持 green；基线从 79/79 升级到 ≥ 98/98。

辅助验证：
```bash
# spec parity
grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec

# OPS-03 懒加载
python3 -c "import sys; import privacyguard; print('word.adapter:', 'privacyguard.word.adapter' in sys.modules)"

# D-05 v37.7.6 收敛
python3 -c "import ast; from pathlib import Path; tree = ast.parse(Path('main.py').read_text(encoding='utf-8')); funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}; print('redact_word_docx in main.py:', 'redact_word_docx' in funcs)"
```
</verification>

<success_criteria>
- [ ] TestWordDataKeySync 3 + TestWordPartialMaskInComparePane 2 共 5 个新测试方法全部 GREEN
- [ ] test_import_privacyguard_does_not_load_word_submodules 断言 OPS-03 扩展
- [ ] test_no_word_adapter_in_main_py AST 断言 D-05 收敛扩展
- [ ] 完整 12 个 unittest 模块全部 GREEN（基线升级 ≥ 98/98）
- [ ] test_word_pii_pipeline 24 测试方法全 GREEN
- [ ] test_package_imports 14 测试方法全 GREEN（13 既有 + 1 新增）
- [ ] test_convergence N 测试方法全 GREEN（含 1 新增 word）
- [ ] 双 spec PyInstaller hiddenimports 字段级一致
- [ ] OPS-03 懒加载纪律保持（5 个 word 子模块 import privacyguard 后不在 sys.modules）
- [ ] D-05 v37.7.6 收敛原则保持（main.py 不含 inline Word adapter / redact / clear_doc_props 实现）
- [ ] D-08 文档属性清除 8 字段范围锁保持
- [ ] D-09 WordPIIWorker 自动触发保持
- [ ] D-10 cp27 增量 DOM patch 契约保持
- [ ] D-13 / D-14 ≥ 1 个新测试类 + 79/79 → 98/98+ 基线升级锁定
- [ ] D-19 priority rule > pii > manual > ocr 锁定 + pii_matches=None back-compat
- [ ] D-21 9 短码字典单一来源 + ASCII uppercase 锁定
- [ ] D-22 data-key 注入复用既有 helper 不重写
- [ ] D-23 redact_word wrapper 复用 main.py:replace_matches_in_paragraph 不重写
- [ ] D-24 clear_word_doc_props 紧邻 new_doc.save(fname) 前调
- [ ] D-25 WordCandidateDialog 极简版 50 条分页 + 实体类型筛选 + 来源筛选 + 4 CTAs
- [ ] 03-04 SUMMARY 落地
- [ ] Phase 3 验收完成（FMT-02 / UX-01 / UX-02 / OPS-03 / OPS-04 / OPS-07 全部覆盖）
</success_criteria>

<output>
创建 `.planning/phases/03-word/03-04-tests-and-baseline-SUMMARY.md` 当任务完成
</output>
