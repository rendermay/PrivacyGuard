---
phase: 02-pdf
plan: 04
slug: gap-closure
subsystem: pdf-redaction
tags: [cr-01, wr-01, wr-03, wr-04, convergence, tdd]
dependency_graph:
  requires: [02-01-tracer, 02-02-engine-expansion, 02-03-main-py-settings-packaging]
  provides: [convergence-clean-pdf-save-loop, multi-occurrence-context-detection, ast-verified-call-gate]
  affects: [privacyguard.pii.pdf_adapter, privacyguard.pii.engine, privacyguard.pii.validators.bank_account, main.py]
tech-stack:
  added: []
  patterns: [ast-call-site-verification, multi-occurrence-loop, mixed-type-dispatch]
key-files:
  created: []
  modified:
    - privacyguard/pii/pdf_adapter.py
    - privacyguard/pii/validators/bank_account.py
    - privacyguard/pii/engine.py
    - main.py
    - tests/unit/test_convergence.py
    - tests/unit/test_pdf_pii_redaction.py
    - tests/unit/test_pii_validators.py
decisions:
  - "write_partial_masks signature extended (backward-compatible) to accept 4 item types: PIIHit dataclass | fitz.Rect | (x, y, w, h, mode) 5-tuple | (PIIHit, mode) 2-tuple — preserves 02-01 TestPartialMaskWritesMaskText callers"
  - "Single delegation call replaces 60+ lines of inline mask writing in main.py::save_pdf (CR-01 fix; v37.7.6 收敛 restored)"
  - "AST-based convergence gate replaces string-presence check; closes loophole that let CR-01 slip through (WR-03 fix)"
  - "has_bank_account_context iterates all text.find(target, start) positions; returns True if ANY occurrence has context anchor (WR-04 fix)"
  - "WR-01 (engine.py eager imports): chose option (a) accept + document — OPS-03 strict contract preserved; individual lazy access via privacyguard.pii.validators.__getattr__ remains intact"
metrics:
  duration: ~10 min
  completed_date: 2026-08-12
  tasks_completed: 5
  commits: 5
  test_count_before: 272
  test_count_after: 281
  test_delta: +9 (4 TestBankAccountContextMultipleOccurrences + 5 TestWritePartialMasksMixedItemDispatch)
status: complete
actuals:
  tokens: 24000    # chars/4 over the files actually changed
  tasks: 5
  commits: 5
---

# Phase 02 Plan 04: Gap Closure Summary

**One-liner:** Closed CR-01 (inline mask writer), WR-01 (eager imports doc), WR-03 (weak convergence test), WR-04 (single-occurrence bank context) — 281/281 tests green.

## What Was Built

This plan closes the 3 remaining Phase 2 verification failures (plus WR-03 as a side-effect gate upgrade):

1. **CR-01 fix** — `write_partial_masks` signature extended with 4-branch mixed item dispatch (PIIHit | fitz.Rect | 5-tuple | 2-tuple). `main.py::save_pdf` replaced 60+ lines of inline `add_redact_annot + apply_redactions + delete_annot + insert_text` with a single `write_partial_masks(doc_save, i, all_pi_items)` delegation call. D-22 single-pass invariant preserved (apply_redactions fires exactly once per page).

2. **WR-04 fix** — `has_bank_account_context` now iterates all `text.find(target, start)` positions and returns True on the FIRST occurrence whose ±window contains a `BANK_ACCOUNT_CONTEXTS` anchor. Previously only checked `text.find(target)` (first occurrence only), which silently leaked bare accounts in multi-occurrence texts.

3. **WR-01 fix (option a)** — `privacyguard/pii/engine.py` module docstring now documents that PIIEngine eagerly loads all 6 new validators (uscc / bank_card / email / vat_invoice / bank_account / taxpayer_id) and rationale for accepting this. OPS-03 strict contract preserved (verified: `import privacyguard` still loads no PII modules).

4. **WR-03 fix (gate upgrade)** — `test_convergence.test_main_py_uses_write_partial_masks_in_save_loop` rewritten with AST-based verification that walks `ast.FunctionDef(name='save_pdf')` body for `ast.Call(func.id=='write_partial_masks')`. Closes the loophole that let CR-01 (imported-but-never-called) slip through. The integration test `test_pdf_pii_redaction.test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata` is rewritten to actually call `write_partial_masks(doc_save, 0, [pii_hit], mode='partial')` rather than mirror main.py's inline code.

## Task Completion

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | RED tests + write_partial_masks refactor + has_bank_account_context fix | `2cc8c18` (RED), `5da17f2` (GREEN) | pdf_adapter.py, bank_account.py, test_pii_validators.py, test_pdf_pii_redaction.py |
| 2 | main.py save_pdf single delegation | `d45fb95` | main.py |
| 3 | AST convergence gate + real write_partial_masks call in integration test | `1588ad2` | test_convergence.py, test_pdf_pii_redaction.py |
| 4 | WR-01 documentation in engine.py docstring | `45d0460` | engine.py |
| 5 | Full suite + SUMMARY (this file) | _see below_ | SUMMARY.md |

## Test Results

```
Ran 281 tests in 3.025s
OK (skipped=2)
```

- **Phase 1 baseline:** 80/80 tests pass (skipped=2)
- **Phase 2 baseline:** 201/201 tests pass (no skip)
- **New tests (Task 1):** 9 tests = 4 `TestBankAccountContextMultipleOccurrences` + 5 `TestWritePartialMasksMixedItemDispatch`
- **Total:** 272 baseline + 9 new = 281 OK (skipped=2)

### Reverse-Extraction Verification (CR-01 fix acceptance)

The integration test now exercises the production helper end-to-end:
- Build PDF with `fake_id_card()` + 5 metadata fields.
- Apply `write_partial_masks(doc_save, 0, [pii_hit], mode='partial')` + `clear_pdf_metadata(doc_save)`.
- Reopen output PDF.
- Original ID string NOT in text.
- mask_strategy "110101********XXXX" IS in text.
- All 5 metadata fields == "".

## Verification Commands Run

```bash
# Compile check
python3 -m compileall -q main.py privacyguard tests

# Full Phase 1 + Phase 2 suite (281 tests)
python3 -m unittest \
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
    tests.unit.test_pii_validators \
    tests.unit.test_pii_engine \
    tests.unit.test_pdf_pii_redaction \
    tests.unit.test_pdf_metadata_cleared \
    -v
```

Output: `Ran 281 tests in 3.025s — OK (skipped=2)`.

### OPS-03 Strict Contract Preserved

```bash
python3 -c "
import sys
import privacyguard
loaded = [k for k in sys.modules if 'privacyguard.pii' in k]
print('PII modules loaded by import privacyguard:', loaded)
assert not loaded, f'OPS-03 violated: {loaded}'
"
```
Output: `PII modules loaded by import privacyguard: []` — PASS.

### Live Grep Verification

```
write_partial_masks refs in main.py: 3          (1 import + 1 comment + 1 call) ≥ 2 PASS
inline def write_partial_masks in main.py: 0    PASS
page.insert_text in main.py: 1                  (only a docstring comment)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug] Fixed test_two_occurrences_second_has_context_returns_true design flaw**
- **Found during:** Task 1 GREEN phase
- **Issue:** The original test in the plan queried `has_bank_account_context(text, '622202123456789012')` on text where `622202123456789012` only appeared once (the second account was a different number `622202987654321098`). The documented intent was to test the SAME target appearing multiple times.
- **Fix:** Changed test to use the same target (`'622202123456789012'`) for both occurrences, so the multi-occurrence loop is actually exercised.
- **Files modified:** `tests/unit/test_pii_validators.py`
- **Commit:** `5da17f2`

### Pre-existing Issues (Out of Scope)

**1. Flaky test: `test_pii_engine.TestEngineTaxpayerId15.test_detects_15_digit_with_admin_prefix`**
- **Frequency:** ~1 in 10 runs (10/10 last check showed 1 failure)
- **Root cause:** `fake_taxpayer_id_15()` in `tests/fixtures/fake_pii.py` uses unconstrained `random.choice('0123456789')` for the 13 body digits. The engine's 15-digit taxpayer ID detection has specific validation rules that can occasionally reject random bodies.
- **Pre-existing in:** commit `a8ab75d` (Phase 2 docs commit before gap-closure work). Verified by checking out the original state — flake rate identical.
- **Not caused by gap-closure:** This plan did not touch `fake_taxpayer_id_15()` or the engine's taxpayer ID detection logic.
- **Recommendation for future plan:** Add validation loop to `fake_taxpayer_id_15()` (similar to `fake_id_card` / `fake_uscc` / `fake_bank_card` patterns) — generate + validate until accepted.

### Architectural Decisions

None — plan executed as designed. WR-01 chose option (a) as documented in plan frontmatter.

## Key Links Verified

- **MainWindow.save_pdf → write_partial_masks** — `main.py:12666` is a single delegation call inside `def save_pdf`. AST gate verifies this is a real `ast.Call` node (not just a string reference).
- **write_partial_masks dispatch** — 4 branches in `pdf_adapter.py`: PIIHit | fitz.Rect | 5-tuple | 2-tuple. Single-pass `apply_redactions(IMAGE_PIXELS)` per page (D-22 invariant).
- **has_bank_account_context loop** — `while True: idx = text.find(target, start); ...; start = idx + 1` — iterates all positions, returns True on first match.
- **AST gate** — `ast.walk(save_pdf_func)` finds `ast.Call` with `func.id == 'write_partial_masks'` inside `def save_pdf`.
- **OPS-03 strict contract** — `import privacyguard` still loads 0 PII modules.

## Next Steps

Phase 2 (PDF fiscal entity recognition + partial mask) is now COMPLETE. The 9 requirement IDs (NUM-04 / NUM-05 / FIN-01..04 / MASK-01 / MASK-02 / SAFE-03) are all satisfied end-to-end. Recommended next work:

1. Mark Phase 2 complete in ROADMAP.md and STATE.md.
2. Proceed to Phase 3 (Word) or another milestone per the project's main track (per CLAUDE.md "Current Development Direction").

## Reversibility

This plan modified 7 files with atomic commits. Reverting requires `git revert` of all 5 task commits (`2cc8c18`, `5da17f2`, `d45fb95`, `1588ad2`, `45d0460`) plus the SUMMARY commit.

Cost assessment: **medium** — the changes are localized to well-named functions and the v37.7.6 convergence test architecture makes regression detection immediate.
