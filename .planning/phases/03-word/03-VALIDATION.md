---
phase: 3
slug: word
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-12
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Word 文档接入识别引擎 — FMT-02 / UX-01 / UX-02.
> Source of truth: `.planning/phases/03-word/03-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `unittest` (Python stdlib) — 沿用 Phase 1/2 基线 |
| **Config file** | 无独立配置（`unittest` 自动发现） |
| **Quick run command** | `python3 -m unittest tests.unit.test_word_pii_pipeline -v` |
| **Full suite command** | `python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_package_imports tests.unit.test_pdf_text_hit_dedup tests.unit.test_app_config tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety tests.unit.test_convergence tests.unit.test_word_pii_pipeline -v` |
| **Estimated runtime** | ~30 seconds (unittest 全套基线 + 新增 Word PII 集成) |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m unittest tests.unit.test_word_pii_pipeline -v`
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green (既有 11 unittest 模块基线 + 新增 test_word_pii_pipeline 全部 GREEN)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | FMT-02 | T-03-WordRunBoundary | redact 后 para.text 不含原文 | integration | `tests.unit.test_word_pii_pipeline.TestWordRedactRoundTrip` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | FMT-02 | T-03-DocPropsLeak | clear_word_doc_props 后 5 core + 2 app 字段 == "" | integration | `tests.unit.test_word_pii_pipeline.TestWordDocumentPropertiesCleared` | ✅ | ⬜ pending |
| 03-01-03 | 01 | 1 | FMT-02 | T-03-PIIAutoTrigger | _open_word_docx 自动启动 WordPIIWorker；不点扫描按钮 | integration | `tests.unit.test_word_pii_pipeline.TestWordPIIAutoTrigger` | ✅ | ⬜ pending |
| 03-01-04 | 01 | 1 | OPS-03 | T-03-LazyImport | privacyguard.word 子包 import 不拉起 5 个子模块 | unit | `tests.unit.test_package_imports.test_import_privacyguard_does_not_load_word_submodules` (Wave 4) | ✅ | ⬜ pending |
| 03-01-05 | 01 | 1 | OPS-04 | T-03-PyInstallerHiddenimports | privacyguard.word.* 在 Windows + macOS hiddenimports | smoke | `grep privacyguard.word packaging/{windows,macos}/config/*.spec` | ✅ | ⬜ pending |
| 03-01-06 | 01 | 1 | D-21 | T-03-ShortCodeSourceOfTruth | ENTITY_TYPE_SHORT_CODE 9 短码字典 from privacyguard/pii/hits.py | unit | `python3 -c "from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE"` | ✅ | ⬜ pending |
| 03-01-07 | 01 | 1 | D-19 | T-03-MergePriority | priority 锁定 rule > pii > manual > ocr | unit | `tests.unit.test_word_pii_pipeline.TestWordMergePriorityRulePiManualOcr` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 2 | FMT-02 | T-03-DataKeySync | mammoth 渲染后 DOM data-key 数 == word_data key 数 | integration | `tests.unit.test_word_pii_pipeline.TestWordDataKeySync` (Wave 4) | ✅ | ⬜ pending |
| 03-02-02 | 02 | 2 | FMT-02 | T-03-PartialMask | 右栏 PII 高亮写 partial mask 字符串（110101\*\*\*\*\*\*\*\*1234） | integration | `tests.unit.test_word_pii_pipeline.TestWordPartialMaskInComparePane` (Wave 4) | ✅ | ⬜ pending |
| 03-02-03 | 02 | 2 | FMT-02 | T-03-SetHtmlRegression | _apply_word_pii_panel_updates 走 runJavaScript 不走 setHtml | unit | `tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights` | ✅ | ⬜ pending |
| 03-02-04 | 02 | 2 | D-10 | T-03-SetHtmlRegression | cp27 增量 DOM patch 契约保持 | unit | `tests.unit.test_word_pii_pipeline.TestWordPIIPanelHighlights` | ✅ | ⬜ pending |
| 03-03-01 | 03 | 3 | UX-01 | T-03-CandidateDialog | WordCandidateDialog 显示 PII 命中 + 逐条 checkbox | unit | `tests.unit.test_word_pii_pipeline.TestWordCandidateDialog` | ✅ | ⬜ pending |
| 03-03-02 | 03 | 3 | UX-02 | T-03-CandidateFilter | > 50 条分页 + entity_type 筛选 + 来源筛选 | unit | `tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination` | ✅ | ⬜ pending |
| 03-03-03 | 03 | 3 | UX-01 | T-03-UX01CancellationBroken | confirmed_hits 持久化 + candidate_only_pii 永不写入 save 路径 | integration | `tests.unit.test_word_pii_pipeline.TestWordCandidateDialogSelectionAcrossPages` + _save_word guard | ✅ | ⬜ pending |
| 03-03-04 | 03 | 3 | UX-01 | T-03-SelectionLostAcrossPages | _selection dict + hit identity 四元组跨翻页持久化 | unit | `tests.unit.test_word_pii_pipeline.TestWordCandidateDialogSelectionAcrossPages` | ✅ | ⬜ pending |
| 03-03-05 | 03 | 3 | OPS-04 | T-03-PyInstallerParity | 6 项 privacyguard.word.* hiddenimports 双 spec 字段级一致 | smoke | `grep privacyguard.word packaging/{windows,macos}/config/*.spec` | ✅ | ⬜ pending |
| 03-04-01 | 04 | 4 | OPS-07 | — | 既有 11 unittest 模块基线保持 GREEN | integration | 完整 full suite command | ✅ | ⬜ pending |
| 03-04-02 | 04 | 4 | OPS-03 | T-03-LazyImport | test_import_privacyguard_does_not_load_word_submodules | unit | `tests.unit.test_package_imports.test_import_privacyguard_does_not_load_word_submodules` | ✅ | ⬜ pending |
| 03-04-03 | 04 | 4 | D-05 | T-03-ShortCodeSourceOfTruth | test_no_word_adapter_in_main_py AST 断言 main.py 不内联 Word adapter | unit | `tests.unit.test_convergence.test_no_word_adapter_in_main_py` | ✅ | ⬜ pending |
| 03-04-04 | 04 | 4 | D-22 | T-03-DataKeySync | TestWordDataKeySync 验证 mammoth data-key 同步契约 | integration | `tests.unit.test_word_pii_pipeline.TestWordDataKeySync` | ✅ | ⬜ pending |
| 03-04-05 | 04 | 4 | FMT-02 | T-03-PartialMask | TestWordPartialMaskInComparePane 验证右栏 partial mask 渲染 | integration | `tests.unit.test_word_pii_pipeline.TestWordPartialMaskInComparePane` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Phase 3 全部 13 项 Wave 0 任务已在各 plan tasks 中直接实施（不再作为独立 Wave 0 阶段）。
> Wave 0 = false 因为 fixtures + skeleton 模块均出现在 plan tasks 中；validate-phase §6 应根据 plan tasks 完成情况确认 nyquist_compliant: true。

**已就位 Wave 0 任务清单（按 plan 引用）：**

- [x] `tests/fixtures/fake_word.py` NEW — 03-01 Task 1 Step I：`build_fake_docx()` 合成含 PII 的 docx（D-26；Faker 合成数据）
- [x] `privacyguard/word/__init__.py` NEW — 03-01 Task 1 Step A：懒加载 `_LAZY_IMPORTS`（D-06；OPS-03）
- [x] `privacyguard/word/adapter.py` NEW — 03-01 Task 1 Step B + Task 2：`WordAdapter.collect_units`（D-04 / D-17）
- [x] `privacyguard/word/worker.py` NEW — 03-01 Task 1 Step C + Task 2：`WordPIIWorker` QThread（D-09）
- [x] `privacyguard/word/redact.py` NEW — 03-01 Task 1 Step D + Task 2：`redact_word` wrapper（D-23）
- [x] `privacyguard/word/clear_doc_props.py` NEW — 03-01 Task 1 Step E + Task 2：`clear_word_doc_props`（D-24）
- [x] `privacyguard/word/candidate_dialog.py` NEW — 03-02 Task 2 + 03-03 Task 2：`WordCandidateDialog` 完整 UI（UX-01 / UX-02）
- [x] `main.py` MODIFY — 03-01 Task 1 Step K + Task 2 (e)：`_open_word_docx` 自动启动 `WordPIIWorker` + `_on_word_pii_page_result` 槽 + `merge_word_matches_with_priority` 第六参数 + `_save_word` 扩 pii_matches（D-09 / D-18 / D-19 / D-23 / D-24）
- [x] `main.py` MODIFY — 03-02 Task 2 + 03-03 Task 2：`_apply_word_pii_panel_updates` + `_build_pii_block_fragment` + `_build_pii_mask_block_fragment` + `_on_word_candidate_dialog_accept` + `_save_word` guard（D-10 / UX-01 / BLOCKER 3 / BLOCKER 4）
- [x] `privacyguard/pii/hits.py` MODIFY — 03-01 Task 1 Step F：`_LAZY_IMPORTS` 追加 Word 符号 + `ENTITY_TYPE_SHORT_CODE` 9 短码字典（D-06 + D-21 + BLOCKER 5）
- [x] `privacyguard/__init__.py` MODIFY — 03-01 Task 1 Step G：`_LAZY_IMPORTS` 追加 6 项 word 符号 + `ENTITY_TYPE_SHORT_CODE` 转发（D-06 + BLOCKER 5）
- [x] `tests/unit/test_word_pii_pipeline.py` NEW + MODIFY — 03-01 Task 1 Step J + 03-02 Task 1 + 03-03 Task 1 + 03-04 Task 1：12 个测试类（D-13）
- [x] `packaging/windows/config/PrivacyGuard_windows.spec` MODIFY — 03-01 Task 1 Step L + 03-03 Task 2：`hiddenimports` 段追加 6 项 `privacyguard.word.*`（cp30 教训）
- [x] `packaging/macos/config/PrivacyGuard.spec` MODIFY — 03-01 Task 1 Step L + 03-03 Task 2：`hiddenimports` 段追加 6 项 `privacyguard.word.*`（cp30 教训 parity）
- [x] `tests/fixtures/__init__.py` NEW — 03-01 Task 1 Step H：让 `fake_word` 被 `tests/` 顶层 import 链发现
- [x] `tests/unit/test_package_imports.py` MODIFY — 03-04 Task 2：`test_import_privacyguard_does_not_load_word_submodules`（OPS-03 扩展）
- [x] `tests/unit/test_convergence.py` MODIFY — 03-04 Task 2：`test_no_word_adapter_in_main_py` AST 断言（D-05 收敛扩展）

*Wave 0 complete 已根据 plan tasks 完成情况标记 true；validate-phase §6 应确认 nyquist_compliant: true*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Word 对比模式启动后右栏实时高亮 PII | FMT-02 | UI 渲染 + 增量 DOM patch 需真实 QWebEngineView | 启动 app → 打开含身份证号 docx → 双栏对比模式 → 观察右栏 partial mask 字符串即时出现，不等待整页重渲染 |
| `docProps/core.xml` / `docProps/app.xml` 在导出后真清空 | FMT-02 | 文件 IO + XML schema validation | `unzip -p out.docx docProps/core.xml \| grep dc:title` 应返回空值 |
| `packaging/windows/build_complete.bat` 启动 PyInstaller 打包，Windows 二进制可成功 import `privacyguard.word` | OPS-04 | 跨平台二进制构建需真机 | Windows: `packaging\\windows\\scripts\\build_complete.bat` → 启动 dist/PrivacyGuard.exe → 打开 docx → 无 `ModuleNotFoundError: privacyguard.word` |

*If none: "All phase behaviors have automated verification." — 不适用；UI 与打包必须人工验证*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (18 tasks listed above — 与 plan tasks 一致)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (set by `validate-phase` §6 after Wave 0 complete)