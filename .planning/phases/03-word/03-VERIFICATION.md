---
phase: 03-word
verified: 2026-08-12T07:30:23Z
status: passed
score: 6/6 must-haves verified
behavior_unverified: 1
overrides_applied: 0
overrides: []

# Phase 3 verification — pre-existing finding, not Phase 3's responsibility
# version.txt in working tree is 1.0.0 but HEAD is 37.7.6.
# No Phase 3 commit modified version.txt (last commit touching it: 829a43d, before Phase 3).
# Phase 3 satisfies "should NOT bump version" constraint.
pre_existing_findings:
  - finding: version.txt working tree state mismatch
    detail: "Working tree version.txt = '1.0.0', HEAD version.txt = '37.7.6' (commit 829a43d). Local working-tree modification not from Phase 3 work; no Phase 3 commit (880853b..acb2a28) modified version.txt. The 'should NOT bump version' constraint is satisfied. Recommend the user reconcile working tree state (git checkout HEAD -- version.txt) before subsequent operations."
    severity: info
    phase_attributable: false

human_verification:
  - test: "Dual-pane UI verification (Wave 1)"
    test_action: "Launch `python3 main.py`, open a docx containing PII, observe status chip + compare preview + save flow"
    expected: "Status chip transitions through worker phases; PII auto-detected; left pane red highlight + right pane green partial mask; saved docx has cleared 5 core fields + revision=1"
    why_human: "PyQt6 main thread / QWebEngineView rendering / tooltip color / scroll-zoom sync — must be observed in real application"
    approved_by_user: true  # Wave 1 manual approval per request
  - test: "Dual-pane PII highlight + partial mask UI (Wave 2)"
    test_action: "Launch app, open PII docx, switch to compare mode, hover PII positions"
    expected: "Left pane: red semi-transparent box with short-code badge (ID/PHONE/BANK/...) + tooltip. Right pane: green box with only partial mask string (e.g., 530102********011X) + tooltip '已替换为：...'."
    why_human: "Visual rendering colors + tooltip text in PyQt6 QWebEngineView"
    approved_by_user: true  # Wave 2 manual approval per request
  - test: "WordCandidateDialog UI + UX-01 cancel + pagination/persistence (Wave 3)"
    test_action: "Open PII docx, click '查看全部候选', filter by type, paginate, cancel 5 hits, confirm N-5 hits, verify exported docx"
    expected: "Dialog UI matches Copywriting; pagination correct; cancellation preserves original text in saved docx for cancelled hits; confirmed hits redacted"
    why_human: "PyQt6 QListWidget + QCheckBox + QComboBox + QPushButton interaction in real UI"
    approved_by_user: true  # Wave 3 manual approval per request
  - test: "PyInstaller frozen build (Windows + macOS)"
    test_action: "Build via `packaging/windows/scripts/build_complete.bat` and `./packaging/macos/scripts/build_complete.sh`, launch frozen binary, open Word docx"
    expected: "No `ModuleNotFoundError: privacyguard.word.*` on either platform"
    why_human: "Requires Windows + macOS build environments with PyInstaller; spec parity is verified by grep but runtime binary load cannot be tested in this Linux environment"
    approved_by_user: null  # Requires Windows/macOS — deferred

gaps: []

behavior_unverified_items:
  - truth: "PyInstaller frozen build on Windows + macOS imports privacyguard.word.* without ModuleNotFoundError"
    test: "Run build_complete.bat / build_complete.sh, launch frozen binary, open Word docx, verify import succeeds"
    expected: "Frozen binary launches; Word docx opens; PII worker auto-triggers; no import errors in console"
    why_human: "Requires native Windows + macOS PyInstaller environments; spec parity (12/6 hiddenimports) verified by grep but runtime build cannot be executed on this Linux verification environment"

# Per-must-have verified counts
# Truths: 6/6 — all roadmap success criteria + plan frontmatter must-haves
# Truths list (with sources):
#   1. FMT-02: Word 文档接入识别引擎 — auto-trigger + redact + clear_doc_props + cp27 (verified)
#   2. FMT-02: _save_word calls redact_word + clear_word_doc_props + confirmed_hits guard (verified)
#   3. UX-01: WordCandidateDialog supports cancel (BLOCKER 3) + UX-02 pagination/persistence (BLOCKER 4) (verified)
#   4. OPS-03: privacyguard.word.* lazy-load (verified)
#   5. D-05: v37.7.6 convergence — no inline Word adapter in main.py (verified)
#   6. OPS-04: PyInstaller spec parity Windows 12 / macOS 6 (verified)
---

# Phase 3: Word 文档接入识别引擎 — Verification Report

**Phase Goal:** Word 文档接入识别引擎 — FMT-02 / UX-01 / UX-02
**Requirements:** FMT-02, UX-01, UX-02
**Branch:** `gsd/phase-2-local-attempt`
**Verified:** 2026-08-12T07:30:23Z
**Status:** **passed**
**Score:** 6/6 must-haves verified

## Goal Achievement

### Phase Goal vs. Codebase Evidence

The phase goal is to integrate the existing PII engine into the Word document path with:
- Auto-triggered PII scanning on docx open (no manual scan button)
- Dual-pane compare preview with PII highlighting (left = red box + short-code badge; right = partial mask)
- Candidate review dialog (filter, paginate, cancel)
- Document property clearing on save

All four 计划 (03-01 through 03-04) have committed atomic changes and the codebase demonstrates the goal is achieved:

| Plan | Commits | Files Modified | Test Additions | Verified |
|------|---------|----------------|----------------|----------|
| 03-01 tracer (Wave 1) | `880853b` + `d25f6cc` | 13 | 7 | YES |
| 03-02 engine + UI (Wave 2) | `ba94cbb` + `41ad3e8` | 3 | 4 | YES |
| 03-03 candidate dialog (Wave 3) | `c3df015` + `d88a804` | 4 | 9 | YES |
| 03-04 tests + baseline (Wave 4) | `9ec0161` + `a94101a` + `acb2a28` | 4 | 7 | YES |

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | FMT-02: WordPIIWorker auto-triggers on `_open_word_docx`; `_save_word` calls `redact_word` + `clear_word_doc_props` | VERIFIED | main.py:10880-10885 (auto-start); main.py:13000-13001 (imports); main.py:13000+ (calls). Test `test_redact_word_partial_mask_visible` GREEN. Behavioral test confirmed: original secret_id NOT in result, partial mask IS in result. |
| 2 | FMT-02: merge_word_matches_with_priority extended with `pii_matches=None` 6th param; priority rule > pii > manual > ocr | VERIFIED | main.py:863-906 (extended). Tests `test_rule_beats_pii` + `test_pii_beats_manual_on_overlap` GREEN. |
| 3 | FMT-02: cp27 incremental DOM patch preserved (`runJavaScript("updateBlock(...)")` not `setHtml`) | VERIFIED | main.py:474-492 (`build_word_panel_update_script` reused from cp27); main.py:11622-11651 (`_apply_word_pii_panel_updates` uses `runJavaScript`). Test `test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml` GREEN. |
| 4 | UX-01: WordCandidateDialog with PAGE_SIZE=50 + 4 CTAs + entity/source filter + confirmed signal + UX-01 cancel semantics (confirmed_hits + candidate_only_pii + _save_word guard) | VERIFIED | privacyguard/word/candidate_dialog.py:48-394 (full implementation); main.py:11773-11817 (`_on_word_candidate_dialog_accept`); main.py:13019-13030 (save guard). 9 test methods GREEN (`TestWordCandidateDialog` 5 + `TestWordCandidateDialogPagination` 3 + `TestWordCandidateDialogSelectionAcrossPages` 1). Behavioral verification: dialog opens with correct title, all_hits, btn_confirm text '确认选中的 N 项'. |
| 5 | UX-02: Pagination (PAGE_SIZE=50) + entity-type filter + source filter | VERIFIED | candidate_dialog.py:45 (`PAGE_SIZE = 50`); candidate_dialog.py:164-181 (filter combo boxes); candidate_dialog.py:257-263 (`(total + PAGE_SIZE - 1) // PAGE_SIZE` calc). Tests `test_pagination_over_50_entries` + `test_pagination_filter_combination` + `test_row_label_truncates_normalized_at_30_chars` GREEN. |
| 6 | OPS-03 + D-05 + OPS-04: lazy-load + no inline Word adapter + PyInstaller spec parity | VERIFIED | OPS-03: `import privacyguard` → 5 False (word.adapter/worker/redact/clear_doc_props/candidate_dialog all not in sys.modules). D-05: AST scan of 7 target functions → NONE. OPS-04: Windows spec 12 lines (dual-segment × 6) + macOS spec 6 lines (single-segment × 6) — module name sets identical. Tests `test_import_privacyguard_does_not_load_word_submodules` + `test_no_word_adapter_in_main_py` GREEN. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `privacyguard/word/__init__.py` | `_LAZY_IMPORTS` + `__getattr__` | VERIFIED | 5 lazy forwards + 5 __all__ + __dir__ |
| `privacyguard/word/adapter.py` | `WordAdapter.collect_units` | VERIFIED | 50 LOC, lazy imports inside function |
| `privacyguard/word/worker.py` | `WordPIIWorker` QThread | VERIFIED | 54 LOC, 3 pyqtSignals, lazy PIIEngine import |
| `privacyguard/word/redact.py` | `redact_word` + `redact_paragraph` | VERIFIED | 72 LOC, lazy main.py import, cell para_offset accumulation |
| `privacyguard/word/clear_doc_props.py` | `clear_word_doc_props` | VERIFIED | 52 LOC, 5 core + revision=1 + 2 app fields |
| `privacyguard/word/candidate_dialog.py` | Full WordCandidateDialog UI | VERIFIED | 394 LOC, PAGE_SIZE=50, 9 entity labels, hit identity quad, confirmed signal |
| `privacyguard/__init__.py` | Lazy top-level forwards | VERIFIED | 6 new entries (5 Word + ENTITY_TYPE_SHORT_CODE) |
| `privacyguard/pii/hits.py` | `ENTITY_TYPE_SHORT_CODE` 9-code dict | VERIFIED | Single source; ASCII uppercase codes (ID/PHONE/BANK/EMAIL/USCC/TAX/TAX15/VAT/ACCT) |
| `tests/fixtures/fake_word.py` | `build_fake_docx` synthesizer | VERIFIED | Faker-based docx synthesis with paragraphs + tables |
| `tests/unit/test_word_pii_pipeline.py` | 25 test methods | VERIFIED | All 25 GREEN |
| `tests/unit/test_package_imports.py` | `test_import_privacyguard_does_not_load_word_submodules` | VERIFIED | GREEN |
| `tests/unit/test_convergence.py` | `test_no_word_adapter_in_main_py` | VERIFIED | GREEN |
| `main.py` | 4 wire-up locations | VERIFIED | `_open_word_docx` (10880) + `_on_word_pii_page_result` (11578) + `_apply_word_pii_panel_updates` (11622) + `_save_word` (12995) |
| `packaging/windows/config/PrivacyGuard_windows.spec` | 6 Word hiddenimports in dual-segment | VERIFIED | 12 lines (extend + inline) |
| `packaging/macos/config/PrivacyGuard.spec` | 6 Word hiddenimports in single-segment | VERIFIED | 6 lines |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `_open_word_docx` (main.py) | `WordPIIWorker.start()` | `from privacyguard.word.worker import WordPIIWorker` | WIRED | main.py:10880-10885 |
| `_on_word_pii_page_result` (main.py) | `word_data[key]['pii']` write | `QMutexLocker(self._word_data_lock)` | WIRED | main.py:11598-11602 |
| `_on_word_pii_page_result` (main.py) | `_apply_word_pii_panel_updates` | direct call | WIRED | main.py:11604 |
| `_apply_word_pii_panel_updates` (main.py) | cp27 incremental patch | `build_word_panel_update_script` + `runJavaScript` | WIRED | main.py:11646-11648 (NO setHtml — verified by test) |
| `_build_pii_block_fragment` (main.py) | `ENTITY_TYPE_SHORT_CODE` | import from privacyguard.pii.hits | WIRED | main.py:36 (top-level import); main.py uses `.get(entity_type, entity_type)` |
| `redact_word` (privacyguard.word.redact) | `replace_matches_in_paragraph` (main.py) | lazy import inside function | WIRED | privacyguard/word/redact.py:11, 28 |
| `clear_word_doc_props` (privacyguard.word.clear_doc_props) | python-docx core/app properties | direct property assignment | WIRED | privacyguard/word/clear_doc_props.py:25-49 |
| `_save_word` (main.py) | `redact_word` + `clear_word_doc_props` | function call (before `new_doc.save(fname)`) | WIRED | main.py:13000-13001 |
| `_save_word` (main.py) | `confirmed_hits` guard | filter `pii_for_save` | WIRED | main.py:13019-13027 (per BLOCKER 3 UX-01 cancel) |
| `_on_word_candidate_dialog_accept` (main.py) | `word_data[key]['confirmed']` | `QMutexLocker(self._word_data_lock)` | WIRED | main.py:11809-11815 |
| `WordCandidateDialog.confirmed` (privacyguard.word.candidate_dialog) | `_on_word_candidate_dialog_accept` (main.py) | pyqtSignal.connect | WIRED | main.py:11770 |
| PyInstaller spec | `privacyguard.word.*` modules | `hiddenimports` field | WIRED | Windows 12 lines, macOS 6 lines |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `word_data[key]['pii']` | worker-emitted hits | `WordPIIWorker.run()` → `PIIEngine.detect(TextUnit, page=None)` | YES | FLOWING |
| `_build_pii_block_fragment` output | HTML fragment | `word_data[key]['text']` + `hits` | YES | FLOWING |
| `_build_pii_mask_block_fragment` output | HTML fragment | `word_data[key]['text']` + `hits[].mask_strategy` | YES | FLOWING |
| `redact_word` output | python-docx paragraph/cell mutations | `replace_matches_in_paragraph` | YES | FLOWING |
| `clear_word_doc_props` output | docx core/app properties | direct mutation | YES | FLOWING |
| `WordCandidateDialog._all_hits` | list of all PII/OCR/manual hits | `word_data[*][pii/ocr/manual]` | YES | FLOWING |
| `_save_word` guard | `pii_for_save` | filter `data['pii']` by `confirmed_hits` set | YES | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `redact_word` actually redacts | `python3 -c "...build_fake_docx...redact_word..."` | Original `53010219200508011X` NOT in result; partial mask `530102********011X` IS in result | PASS |
| `clear_word_doc_props` clears 5 core fields | `python3 -c "...set sensitive values, clear, save/reload..."` | title='', author='', subject='', keywords='', last_modified_by='', revision=1 | PASS |
| `WordAdapter.collect_units` returns correct key_index | `python3 -c "...build_fake_docx + collect_units..."` | 10 units, 10 keys (paragraph_0..7 + table_0_cell_0_0/1) | PASS |
| `WordCandidateDialog` initializes | `python3 -c "...QApplication + WordCandidateDialog..."` | window title='Word 候选审阅', list_widget.count=2, btn_confirm='确认选中的 2 项', PAGE_SIZE=50 | PASS |
| Full test suite passes | `python3 -m unittest tests.test_path_validation tests.unit.test_mixed_pdf_ocr tests.unit.test_ocr_api tests.unit.test_package_imports tests.unit.test_pdf_text_hit_dedup tests.unit.test_app_config tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety tests.unit.test_convergence tests.unit.test_word_pii_pipeline` | `Ran 126 tests in 2.935s — OK (skipped=2)` | PASS |
| OPS-03 lazy-load discipline | `python3 -c "import sys; import privacyguard; print('word.adapter:', 'privacyguard.word.adapter' in sys.modules)"` | All 5 word submodules → False | PASS |
| D-05 v37.7.6 convergence | AST scan of 7 target functions for forbidden literals | `D-05 violations: NONE` | PASS |
| OPS-04 spec parity | `grep -cE "privacyguard\.word" packaging/{windows,macos}/config/*.spec` | Windows: 12 / macOS: 6 | PASS |
| D-21 single source (BLOCKER 5) | `python3 -c "from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE; print(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'])"` | `CN_ID_CARD: ID` (with all 9 keys present) | PASS |

### Probe Execution — N/A (not a probe-based phase)

Phase 3 is an integration/feature phase, not a probe-based migration. The behavioral spot-checks above substitute for probe execution.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| **FMT-02** | 03-01, 03-02, 03-04 | Word 处理路径接入识别引擎，识别候选在双栏对比预览中高亮 | SATISFIED | WordPIIWorker auto-trigger (10880) + dual-pane rendering (11622/11653/11700) + cp27 preserved (474) + 23 test methods GREEN |
| **UX-01** | 03-02, 03-03 | 用户可在候选审阅列表中查看所有待确认识别项，并逐条决定是否脱敏 | SATISFIED | WordCandidateDialog complete UI + UX-01 cancel semantics (confirmed_hits + candidate_only_pii + _save_word guard) + 14 test methods GREEN |
| **UX-02** | 03-03 | 候选列表支持按实体类型与来源筛选，且在候选数量较多时分页展示 | SATISFIED | PAGE_SIZE=50 + entity_filter + source_filter + row_label[:30] truncation + 3 test methods GREEN |

Plus OPS-03 / OPS-04 / OPS-07 also covered by Wave 1 + Wave 3 + Wave 4 enforcement.

### Anti-Patterns Found

None. The following negative checks passed:
- No TBD / FIXME / XXX markers in Phase 3 code
- No `return null` / `return {}` / `return []` stubs in production paths
- No `console.log`-only implementations
- No hardcoded empty data in production paths (only `pii_for_save = []` default in `_save_word` guard — defensive, not a stub)
- No real PII in fixtures (all Faker-synthesized via `tests/fixtures/fake_pii.py` + `tests/fixtures/fake_word.py`)
- D-05 AST scan: NONE violations across 7 target functions

### Human Verification Required

| # | Item | Why Human | Status |
|---|------|-----------|--------|
| 1 | Dual-pane UI (Wave 1) | PyQt6 main thread + QWebEngineView rendering | APPROVED by user per task description |
| 2 | Dual-pane PII highlight + partial mask (Wave 2) | Visual colors + tooltip text in QWebEngineView | APPROVED by user per task description |
| 3 | WordCandidateDialog UI + UX-01 cancel + pagination (Wave 3) | PyQt6 widget interaction | APPROVED by user per task description |
| 4 | PyInstaller frozen build (Windows + macOS) | Requires native PyInstaller environments | DEFERRED — cannot be tested on this Linux verification environment |

### Per-Plan Status Summary

| Plan | Title | Status | Commits | Tests |
|------|-------|--------|---------|-------|
| 03-01 | tracer (end-to-end spine) | COMPLETE | `880853b`, `d25f6cc` | 7 GREEN |
| 03-02 | engine expansion + UI panel updates | COMPLETE | `ba94cbb`, `41ad3e8` | 4 GREEN |
| 03-03 | candidate dialog + packaging | COMPLETE | `c3df015`, `d88a804` | 9 GREEN |
| 03-04 | tests + baseline closure | COMPLETE | `9ec0161`, `a94101a`, `acb2a28` | 7 GREEN |

Total Phase 3 test additions: 27 new test methods, all GREEN.
Baseline preservation: 99 → 126 test methods (+27 with 2 skipped, baseline unchanged).

### Decision Discipline Verification

| Decision | Status | Verification |
|----------|--------|--------------|
| D-08 (8 fields cleared, no "Anonymous" placeholders) | ENFORCED | `clear_word_doc_props.py:13-15` (5 core + 2 app Final constants); tests GREEN |
| D-09 (WordPIIWorker auto-trigger) | ENFORCED | main.py:10880-10885 (no manual scan button); test_engine_detects_pii_in_word_text GREEN |
| D-10 (cp27 incremental patch, no setHtml) | ENFORCED | main.py:11648 (runJavaScript); test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml GREEN |
| D-19 (priority rule > pii > manual > ocr) | ENFORCED | main.py:863-906 (priority order); test_rule_beats_pii + test_pii_beats_manual_on_overlap GREEN |
| D-21 (ENTITY_TYPE_SHORT_CODE single source) | ENFORCED | privacyguard/pii/hits.py (only source); main.py imports from there; test_convergence AST checks no inline dict |
| D-22 (data-key injection reuse) | ENFORCED | tests use MethodType-bound stub; test_data_key_* GREEN |
| D-23 (redact_word wraps replace_matches_in_paragraph) | ENFORCED | privacyguard/word/redact.py:11, 28 (lazy import) |
| D-24 (clear_word_doc_props before save) | ENFORCED | main.py:13001 (before new_doc.save(fname)) |
| D-25 (WordCandidateDialog minimal scope) | ENFORCED | No Phase 7 features (UX-03/04/05/06); dialog supports only filter + paginate + confirm/cancel |
| OPS-03 (lazy-load discipline) | ENFORCED | 5 word submodules not in sys.modules after `import privacyguard` |
| OPS-04 (PyInstaller parity) | ENFORCED | Windows 12 / macOS 6 spec lines; module name sets identical |
| OPS-07 (baseline preservation) | ENFORCED | 126 tests GREEN (was 99 + 27 new) |

### Verdict

**Phase 3 goal is achieved.** All roadmap success criteria + all plan must-haves are verified through:
- Codebase artifacts (privacyguard/word/ 5 modules, candidate_dialog, main.py wire-up)
- Test execution (126/126 tests GREEN, 2 skipped as baseline)
- Behavioral spot-checks (redact_word, clear_word_doc_props, WordCandidateDialog, WordAdapter all working)
- Discipline checks (OPS-03 lazy-load, D-05 AST convergence, OPS-04 spec parity, D-21 single source)

The 3 manual UI verifications (Wave 1/2/3) were approved by the user per task description. The PyInstaller frozen build verification is deferred — requires native Windows + macOS PyInstaller environments not available in this Linux verification environment.

The version.txt working tree discrepancy (1.0.0 vs HEAD 37.7.6) is a pre-existing condition not caused by Phase 3 work (no Phase 3 commit modified version.txt). Phase 3 satisfies the "should NOT bump version" constraint.

---

_Verified: 2026-08-12T07:30:23Z_
_Verifier: Claude (gsd-verifier)_