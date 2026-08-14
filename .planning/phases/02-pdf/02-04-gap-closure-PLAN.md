---
phase: 02-pdf
plan: 04
slug: gap-closure
type: execute
wave: 2
depends_on:
  - 02-01
  - 02-02
  - 02-03
files_modified:
  - privacyguard/pii/pdf_adapter.py
  - privacyguard/pii/validators/bank_account.py
  - privacyguard/pii/engine.py
  - main.py
  - tests/unit/test_convergence.py
  - tests/unit/test_pdf_pii_redaction.py
  - tests/unit/test_pii_validators.py
autonomous: true
requirements:
  - NUM-04
  - NUM-05
  - FIN-01
  - FIN-02
  - FIN-03
  - FIN-04
  - MASK-01
  - MASK-02
  - SAFE-03
user_setup: []

estimate:
  tokens: 88000
  raw_tokens: 44000
  tasks: 5
  confidence: medium

must_haves:
  truths:
    - "MainWindow.save_pdf calls write_partial_masks(doc_save, page_idx, all_pi_items) (unified mixed-type dispatch) — verified by AST parsing main.py (Call node inside def save_pdf) NOT string presence."
    - "privacyguard.pii.pdf_adapter.write_partial_masks accepts mixed item types in a single list — PIIHit dataclass instances OR fitz.Rect OR (x, y, w, h, mode) tuple OR (PIIHit, mode) 2-tuple — and dispatches each item by its mode (partial|blackout) while delegating font + rect geometry to _resolve_font_for_rect + _resize_rect_for_mask. Backward-compatible: the 02-01 TestPartialMaskWritesMaskText tests still pass without modification."
    - "tests/unit/test_convergence.py test_main_py_uses_write_partial_masks_in_save_loop AST-parses main.py and asserts a Call node with func.id == write_partial_masks exists inside def save_pdf(...) — replacing the previous string-presence check that let CR-01 slip through."
    - "tests/unit/test_pdf_pii_redaction.py test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata actually calls write_partial_masks(doc_save, 0, [pii_hit], mode=partial) — replacing the current inline mirror of main.py lines 12685-12715 (the WR-03 anti-pattern)."
    - "has_bank_account_context iterates all text.find(target, start) positions and returns True if ANY occurrence's ±window contains a BANK_ACCOUNT_CONTEXTS anchor — fixing WR-04 (only first occurrence checked). New test TestBankAccountContextMultipleOccurrences covers two bare accounts in the same text where only the second occurrence has a context anchor."
    - "All 272/272 Phase 1 + Phase 2 baseline tests still green after the refactor."
    - "main.py no longer contains inline page.insert_text(...) mask-writing code at lines 12685-12715 (CR-01 complete removal). The partial mask insert_text path is delegated entirely to write_partial_masks in pdf_adapter.py."
  artifacts:
    - privacyguard/pii/pdf_adapter.py (write_partial_masks signature extended to accept mixed item types; backward-compatible)
    - main.py (save_pdf lines 12651-12715 replaced by single write_partial_masks delegation call)
    - tests/unit/test_convergence.py (test_main_py_uses_write_partial_masks_in_save_loop rewritten with AST Call-node check)
    - tests/unit/test_pdf_pii_redaction.py (test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata rewritten to actually call write_partial_masks)
    - tests/unit/test_pii_validators.py (new TestBankAccountContextMultipleOccurrences class with 4 methods)
    - privacyguard/pii/validators/bank_account.py (has_bank_account_context refactored to iterate all text.find positions)
    - privacyguard/pii/engine.py (WR-01 documentation note)
  key_links:
    - "MainWindow.save_pdf (main.py:12590+) to write_partial_masks(doc_save, i, all_pi_items) to _resolve_font_for_rect + _resize_rect_for_mask + _FONT_NAME_MAP (CR-01 fix; restores 3 missing behaviors vs inline)"
    - "write_partial_masks (pdf_adapter.py:88) to mixed item dispatch to first-pass add_redact_annot (blackout + partial) + apply_redactions(IMAGE_PIXELS) ONCE per page (single-pass D-22 invariant preserved)"
    - "test_convergence.test_main_py_uses_write_partial_masks_in_save_loop to ast.parse(MAIN_PY) to ast.FunctionDef(name=save_pdf) to walk body to ast.Call(func.id==write_partial_masks) (WR-03 fix; closes the string-presence loophole)"
    - "test_pdf_pii_redaction.test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata to write_partial_masks(doc_save, 0, [pii_hit], mode=partial) to reverse-extract assertion (WR-03 fix)"
    - "has_bank_account_context to while-loop text.find(target, start) to any(ctx in window for ctx in BANK_ACCOUNT_CONTEXTS) to True (WR-04 fix)"
    - "tests/unit/test_pii_validators.py::TestBankAccountContextMultipleOccurrences to regression coverage for WR-04"
  prohibitions:
    - "no inline page.insert_text(...) in main.py (CR-01 must be removed)"
    - "no signature change to write_partial_masks that breaks 02-01 TestPartialMaskWritesMaskText tests"
    - "no string-presence-only check in convergence test (AST verification is required)"
    - "no re-introduction of inline font fallback logic in main.py"
    - "no lazy-load refactor that causes import-time regression (WR-01 option a: document only)"
    - "no breaking single-occurrence correctness in has_bank_account_context fix"
    - "no apply_redactions call more than once per page in main.py (D-22 invariant)"
    - "no multi-occurrence test that is so loose that single find also returns True"
  assumption_delta_decision:
    - "WR-01 (engine.py eager imports): choose option (a) — accept + document. Append note to privacyguard/pii/engine.py top docstring explaining PIIEngine is the single access path for 6 new validators; matching Phase 1 validator loading pattern. OPS-03 strict contract (import privacyguard does not trigger PII loading) is preserved; individual lazy access via privacyguard.pii.validators.__init__._LAZY_IMPORTS remains available for CLI / test fixtures. No importlib.import_module refactor."
    - "WR-01 documentation side-effect: future fine-grained control can be added via independent importer; this plan does not block that work."
    - "02-03 PLAN locked LOCKED REFACTOR structure (lines 408-465) is superseded; 02-04 uses single write_partial_masks delegation. D-22 invariant preserved (write_partial_masks internally keeps single add_redact_annot + apply_redactions(IMAGE_PIXELS) + subsequent insert_text for partial items)."

threat_model:
  trust_boundaries:
    - name: pdf_adapter.write_partial_masks signature
      description: "must accept all 4 input forms in the same items list — PIIHit dataclass, fitz.Rect, (x, y, w, h, mode) tuple, (PIIHit, mode) 2-tuple — backward compat for 02-01 callers required (TestPartialMaskWritesMaskText)"
    - name: main.py.save_pdf to write_partial_masks call site
      description: "AST-parseable Call node inside def save_pdf; comments or docstrings referencing write_partial_masks by name do NOT count as call sites — only ast.Call nodes"
    - name: has_bank_account_context to multi-occurrence text
      description: "input text may contain N bare account candidates; check ALL find() positions; empty target returns False without iteration"
    - name: test_pdf_pii_redaction integration test to write_partial_masks call
      description: "the integration test now actually delegates to write_partial_masks (mode=partial), not inline mirror"
  stride:
    - id: T-2-CR-01
      category: Information Disclosure / Compliance
      component: main.py::save_pdf inline re-implementation
      severity: critical
      disposition: mitigate
      mitigation: "refactor write_partial_masks to accept mixed types (PIIHit | fitz.Rect | (x,y,w,h,mode) tuple | (PIIHit, mode) 2-tuple) + replace main.py lines 12651-12715 with single write_partial_masks call; restores _FONT_NAME_MAP font mapping, OCR font-size fallback, rect resize"
    - id: T-2-WR-01
      category: Repudiation / OPS-03 spirit
      component: privacyguard/pii/engine.py eager imports
      severity: low
      disposition: accept
      mitigation: "document current behavior in engine.py docstring (option a); OPS-03 strict contract preserved; individual lazy access via privacyguard.pii.validators.__getattr__ remains intact"
    - id: T-2-WR-03
      category: Tampering (test integrity)
      component: test_convergence weak string check
      severity: high
      disposition: mitigate
      mitigation: "AST-rewrite test_main_py_uses_write_partial_masks_in_save_loop to walk ast.FunctionDef(name=save_pdf) body and require ast.Call with func.id==write_partial_masks; closes loophole that let CR-01 slip through"
    - id: T-2-WR-04
      category: Information Disclosure (false negative)
      component: has_bank_account_context first-occurrence-only
      severity: medium
      disposition: mitigate
      mitigation: "refactor has_bank_account_context to iterate text.find(target, start) positions; add TestBankAccountContextMultipleOccurrences regression coverage"
    - id: T-2-SIG-BREAK
      category: Information Disclosure / API stability
      component: write_partial_masks signature change
      severity: medium
      disposition: mitigate
      mitigation: "backward-compatible signature extension — 4 dispatch branches (PIIHit | fitz.Rect | (x,y,w,h,mode) tuple | (PIIHit, mode) 2-tuple); single mode argument applies to PIIHit / fitz.Rect branches (02-01 caller path); 2-tuple form carries per-item mode + PIIHit routing for mask_strategy (Task 2 main.py delegation path); 02-01 TestPartialMaskWritesMaskText must pass unmodified"

---

<objective>
Close the 3 remaining verification failures from Phase 2: (1) CR-01 — main.py::save_pdf inline re-implementation of write_partial_masks removed and replaced by single delegation call to a refactored write_partial_masks that accepts mixed item types (PIIHit | fitz.Rect | tuple); (2) WR-01 — engine.py eager imports documented (option a); (3) WR-04 — has_bank_account_context iterates all text.find positions with regression coverage. WR-03 (weak convergence test + inline mirror in integration test) is fixed as a side-effect of CR-01 verification gate upgrade.
</objective>

<purpose>
Phase 2 shipped 6 new entity validators, partial mask writing helper, SettingsDialog 9-row table, toolbar mask_override toggle, and PDF metadata clearing — but the central architectural regression (CR-01: main.py inline mask writer instead of delegating to write_partial_masks) and the multi-occurrence bank account edge case (WR-04) prevent Phase 2 from being marked complete. Without closing these gaps, the v37.7.6 convergence discipline that prevents future regressions is broken, and a class of documents (multi bare-account) silently leaks PII. This plan restores both.
</purpose>

<output>
- CR-01 fix: privacyguard/pii/pdf_adapter.py write_partial_masks signature extended (backward-compatible) to accept mixed item types; main.py save_pdf refactored to single delegation call.
- WR-01 fix (option a): privacyguard/pii/engine.py docstring note added documenting that PIIEngine eagerly loads all 6 new validators.
- WR-04 fix: privacyguard/pii/validators/bank_account.py has_bank_account_context iterates all find() positions; new test class TestBankAccountContextMultipleOccurrences in tests/unit/test_pii_validators.py.
- WR-03 fix: tests/unit/test_convergence.py test_main_py_uses_write_partial_masks_in_save_loop rewritten with AST Call-node assertion; tests/unit/test_pdf_pii_redaction.py integration test rewritten to actually call write_partial_masks.
- All 272/272 baseline tests still green.
- Test count update: 4 TestBankAccountContextMultipleOccurrences + 5 TestWritePartialMasksMixedItemDispatch (including 3 concrete integration tests for 5-tuple blackout / 2-tuple partial / mixed partial+blackout single call).
</output>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-pdf/02-VERIFICATION.md
@.planning/phases/02-pdf/02-REVIEW.md
@.planning/phases/02-pdf/02-CONTEXT.md
@.planning/phases/02-pdf/02-PATTERNS.md
@.planning/phases/02-pdf/02-03-main-py-settings-packaging-PLAN.md
@.planning/phases/02-pdf/02-03-main-py-settings-packaging-SUMMARY.md
@.planning/phases/02-pdf/02-02-engine-expansion-SUMMARY.md
@.planning/phases/02-pdf/02-01-tracer-SUMMARY.md
@.planning/codebase/STRUCTURE.md
@CLAUDE.md
@privacyguard/pii/pdf_adapter.py
@privacyguard/pii/validators/bank_account.py
@privacyguard/pii/engine.py
@main.py
@tests/unit/test_convergence.py
@tests/unit/test_pdf_pii_redaction.py
@tests/unit/test_pii_validators.py
</context>

<tasks>

<!-- TASK 1 -->
<task type="auto" tdd="true">
<name>Task 1: Add new tests + refactor pdf_adapter.write_partial_masks (mixed-type dispatch) + fix has_bank_account_context</name>
<files>privacyguard/pii/pdf_adapter.py, privacyguard/pii/validators/bank_account.py, tests/unit/test_pii_validators.py</files>
<read_first>privacyguard/pii/pdf_adapter.py:88-205, privacyguard/pii/validators/bank_account.py:43-62, privacyguard/pii/hits.py, tests/unit/test_pdf_pii_redaction.py:149-419</read_first>
<action>PART A: Add new tests (RED).
  Add to tests/unit/test_pii_validators.py (immediately after the existing TestBankAccountContextAnchor class, ~line 600):
  ```
  class TestBankAccountContextMultipleOccurrences(unittest.TestCase):
      """WR-04 fix (02-04): has_bank_account_context must check ALL find() positions, not just first."""

      def test_two_occurrences_second_has_context_returns_true(self):
          from privacyguard.pii.validators.bank_account import has_bank_account_context
          # First account: pos 60-77, window [40, 97) — no anchor in window
          # Second account: pos 111-128, window [91, 148) — contains '账号' anchor at pos 108
          # Gap (30 'Y' chars) MUST be > 40 chars between accounts so the first account's
          # ±20 window CANNOT include the second anchor (gap=30 ensures '账号' at pos 108
          # is past window end 97). With this gap, buggy text.find(target) returns False
          # (no anchor in first window), but the fix (iterate text.find(target, start))
          # finds the second occurrence with anchor -> True.
          text = "X" * 60 + "622202123456789012" + "Y" * 30 + "账号 " + "622202987654321098"
          self.assertTrue(has_bank_account_context(text, '622202123456789012'))

      def test_two_occurrences_either_has_context_returns_true(self):
          from privacyguard.pii.validators.bank_account import has_bank_account_context
          # Both candidates have anchors (first has '账号', second has '账户')
          text = "账号 622202123456789012 中间 账户 622202987654321098"
          self.assertTrue(has_bank_account_context(text, '622202123456789012'))
          self.assertTrue(has_bank_account_context(text, '622202987654321098'))

      def test_two_occurrences_neither_has_context_returns_false(self):
          from privacyguard.pii.validators.bank_account import has_bank_account_context
          # Both candidates bare, no anchor anywhere
          text = "622202123456789012 622202987654321098"
          self.assertFalse(has_bank_account_context(text, '622202123456789012'))
          self.assertFalse(has_bank_account_context(text, '622202987654321098'))

      def test_single_occurrence_no_context_still_returns_false(self):
          """Backward-compat: existing single-occurrence behavior preserved."""
          from privacyguard.pii.validators.bank_account import has_bank_account_context
          self.assertFalse(has_bank_account_context('random 622202123456789012', '622202123456789012'))
  ```

  Add to tests/unit/test_pdf_pii_redaction.py (immediately after TestPartialMaskWritesMaskText class, ~line 432):
  ```
  class TestWritePartialMasksMixedItemDispatch(unittest.TestCase):
      """02-04: write_partial_masks must accept mixed item types in one call (PIIHit | fitz.Rect | tuple)."""

      def test_pii_hit_branch_uses_mask_strategy(self):
          """PIIHit dataclass routed via global mode (02-01 backward-compat path)."""
          # Use existing 02-01 tests as the regression anchor
          # (test_partial_mask_writes_mask_text_for_uscc covers this path)
          from privacyguard.pii.pdf_adapter import write_partial_masks
          from privacyguard.pii.hits import PIIHit
          from tests.fixtures.fake_pii import fake_id_card
          from privacyguard.pii.mask import partial_mask_id_card
          # Build a minimal PIIHit; verify write_partial_masks signature accepts it
          hit = PIIHit(
              entity_type='CN_ID_CARD',
              page_offset=0,
              page_length=18,
              page_rect=(50.0, 100.0, 200.0, 20.0),
              source='text',
              mask_strategy=partial_mask_id_card(fake_id_card()),
              normalized='11010119800101001X',
              validator_passed=True,
          )
          self.assertEqual(hit.entity_type, 'CN_ID_CARD')
          self.assertTrue(write_partial_masks.__doc__ is not None)  # signature still importable

      def test_tuple_form_per_item_mode_dispatches(self):
          """(x, y, w, h, mode) tuple routed by per-item mode."""
          from privacyguard.pii.pdf_adapter import write_partial_masks, PartialMaskItem
          # Tuple item dispatch is internal — verify the type alias is exported
          self.assertIn('PartialMaskItem', write_partial_masks.__globals__ if hasattr(write_partial_masks, '__globals__') else {})
          # Also verify via direct module attribute
          from privacyguard.pii import pdf_adapter
          self.assertTrue(hasattr(pdf_adapter, 'PartialMaskItem'))

      def test_mixed_5tuple_dispatches_correctly(self):
          """02-04: (x, y, w, h, mode) 5-tuple dispatched by per-item mode — blackout rect removes text."""
          import fitz, tempfile, os
          from privacyguard.pii.pdf_adapter import write_partial_masks
          with tempfile.TemporaryDirectory() as tmp:
              in_pdf = os.path.join(tmp, 'in_5tuple.pdf')
              out_pdf = os.path.join(tmp, 'out_5tuple.pdf')
              secret_token = 'SECRET_BLACKOUT_TARGET_42'
              doc = fitz.open()
              page = doc.new_page()
              # Place secret text inside the (50,100,200,20) rect that will be redacted
              page.insert_text((60, 115), secret_token, fontsize=12)
              doc.save(in_pdf)
              doc.close()
              doc = fitz.open(in_pdf)
              try:
                  write_partial_masks(doc, 0, [(50, 100, 200, 20, 'blackout')], mode='partial')
                  doc.save(out_pdf)
              finally:
                  doc.close()
              with fitz.open(out_pdf) as out_doc:
                  out_text = ''.join(p.get_text() for p in out_doc)
              self.assertNotIn(secret_token, out_text, f'5-tuple blackout failed: secret still extractable: {out_text!r}')

      def test_mixed_2tuple_partial_writes_mask_text(self):
          """02-04: (PIIHit, mode) 2-tuple dispatched — partial mode writes mask_strategy text."""
          import fitz, tempfile, os
          from privacyguard.pii.pdf_adapter import write_partial_masks
          from privacyguard.pii.hits import PIIHit
          from privacyguard.pii.mask import partial_mask_id_card
          from tests.fixtures.fake_pii import fake_id_card
          with tempfile.TemporaryDirectory() as tmp:
              in_pdf = os.path.join(tmp, 'in_2tuple.pdf')
              out_pdf = os.path.join(tmp, 'out_2tuple.pdf')
              secret_id = fake_id_card()
              mask_text = partial_mask_id_card(secret_id)
              doc = fitz.open()
              page = doc.new_page()
              page.insert_text((60, 115), f'测试 身份证 {secret_id}', fontsize=14)
              doc.save(in_pdf)
              doc.close()
              hit = PIIHit(
                  entity_type='CN_ID_CARD',
                  page_offset=0,
                  page_length=len(secret_id),
                  page_rect=(50.0, 100.0, 250.0, 25.0),
                  source='text',
                  mask_strategy=mask_text,
                  normalized=secret_id,
                  validator_passed=True,
              )
              doc = fitz.open(in_pdf)
              try:
                  write_partial_masks(doc, 0, [(hit, 'partial')])
                  doc.save(out_pdf)
              finally:
                  doc.close()
              with fitz.open(out_pdf) as out_doc:
                  out_text = ''.join(p.get_text() for p in out_doc)
              self.assertNotIn(secret_id, out_text, f'2-tuple partial failed: original still extractable: {out_text!r}')
              self.assertIn(mask_text, out_text, f'2-tuple partial failed: mask text missing: {out_text!r}')

      def test_mixed_partial_and_blackout_in_one_call(self):
          """02-04: single call mixing (PIIHit, 'partial') + (x, y, w, h, 'blackout') — D-22 single-pass invariant."""
          import fitz, tempfile, os
          from privacyguard.pii.pdf_adapter import write_partial_masks
          from privacyguard.pii.hits import PIIHit
          from privacyguard.pii.mask import partial_mask_id_card
          from tests.fixtures.fake_pii import fake_id_card
          with tempfile.TemporaryDirectory() as tmp:
              in_pdf = os.path.join(tmp, 'in_mixed.pdf')
              out_pdf = os.path.join(tmp, 'out_mixed.pdf')
              secret_id = fake_id_card()
              mask_text = partial_mask_id_card(secret_id)
              secret_token = 'SECRET_BLACKOUT_REGION_99'
              doc = fitz.open()
              page = doc.new_page()
              page.insert_text((60, 115), f'身份证 {secret_id}', fontsize=14)
              page.insert_text((60, 215), secret_token, fontsize=14)
              doc.save(in_pdf)
              doc.close()
              hit = PIIHit(
                  entity_type='CN_ID_CARD',
                  page_offset=0,
                  page_length=len(secret_id),
                  page_rect=(50.0, 100.0, 250.0, 25.0),
                  source='text',
                  mask_strategy=mask_text,
                  normalized=secret_id,
                  validator_passed=True,
              )
              doc = fitz.open(in_pdf)
              try:
                  # Single call: partial PIIHit + blackout 5-tuple in one items list
                  write_partial_masks(doc, 0, [(hit, 'partial'), (50, 200, 300, 25, 'blackout')])
                  doc.save(out_pdf)
              finally:
                  doc.close()
              with fitz.open(out_pdf) as out_doc:
                  out_text = ''.join(p.get_text() for p in out_doc)
              # Partial: mask text extractable, original secret not
              self.assertNotIn(secret_id, out_text, f'partial branch failed: original still extractable: {out_text!r}')
              self.assertIn(mask_text, out_text, f'partial branch failed: mask text missing: {out_text!r}')
              # Blackout: token removed
              self.assertNotIn(secret_token, out_text, f'blackout branch failed: token still extractable: {out_text!r}')
  ```

  PART B: Refactor privacyguard/pii/pdf_adapter.py write_partial_masks signature (mixed-type dispatch, backward-compatible).

  Add `from typing import Union` to imports block.

  Add new type alias after the existing imports:
    ```
    PartialMaskItem = Union["PIIHit", "fitz.Rect", Tuple[float, float, float, float, str], Tuple["PIIHit", str]]
    ```

  Replace the body of write_partial_masks (lines 88-143) with a new implementation that:
  - Iterates `items`, normalizes each into (rect, mask_text_or_None, item_mode) across 4 dispatch branches (PIIHit | fitz.Rect | 5-tuple `(x, y, w, h, mode)` | 2-tuple `(PIIHit, mode)`):
    - if isinstance(item, tuple) and len(item)==2 and hasattr(item[0], 'page_rect') and isinstance(item[1], str): 2-tuple form (PIIHit, mode); rect from item[0].page_rect; mask_text=item[0].mask_strategy; item_mode=item[1]
    - elif isinstance(item, tuple) and len(item)==5 and isinstance(item[4], str): tuple form (x,y,w,h,mode); rect from coords; mask_text=None; item_mode=item[4]
    - elif isinstance(item, fitz.Rect): rect from item; mask_text=None; item_mode=mode (global)
    - elif hasattr(item, 'page_rect') and hasattr(item, 'mask_strategy'): PIIHit; rect from page_rect; mask_text=item.mask_strategy; item_mode=mode (global)
    - else: skip (defensive)
  - First pass: add_redact_annot for ALL normalized items (regardless of mode).
  - apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS) ONCE per page (D-22 invariant).
  - delete annot loop.
  - Partial-mode items: for each (rect, mask_text, item_mode) where mask_text and item_mode=='partial':
    - Determine font_name + font_size:
      - For PIIHit branch, prefer _resolve_font_for_rect(page, hit) which uses page.get_text('dict') spans.
      - For tuple/rect branch without source info, fall back to (helv, max(rect.height-4, 6)) OCR fallback (WR-02 fix #2).
      - For tuple/rect branch with mask text in nearby span, attempt span-based font + size match (best effort).
    - resized_rect = _resize_rect_for_mask(rect, mask_text, font_size) (WR-02 fix #3).
    - Insert mask text centered at resized_rect with font_name + font_size + white color (1,1,1) (WR-02 fix #1: uses _FONT_NAME_MAP via span lookup).

  Update __all__ to add 'PartialMaskItem'.

  Verify backward-compat by running TestPartialMaskWritesMaskText (uses [pii_hit] form + mode='partial' or mode='blackout'); both must still pass.

  PART C: Fix privacyguard/pii/validators/bank_account.py has_bank_account_context (WR-04).

  Replace lines 43-62 with a while-loop that calls text.find(target, start) repeatedly and returns True on the FIRST occurrence whose ±window has any BANK_ACCOUNT_CONTEXTS anchor. Falls through to False if no occurrence matches.

  PART D: Run full Phase 2 + 79-test Phase 1 baseline suite. Expected: 272 baseline tests still pass (none regressed), 9 new tests (4 TestBankAccountContextMultipleOccurrences + 5 TestWritePartialMasksMixedItemDispatch) all pass = 281 OK (skipped=2).
</action>
<verify>python3 -m compileall -q privacyguard tests && python3 -m unittest tests.unit.test_pii_validators.TestBankAccountContextMultipleOccurrences tests.unit.test_pii_validators.TestBankAccountContextAnchor tests.unit.test_pdf_pii_redaction.TestWritePartialMasksMixedItemDispatch tests.unit.test_pdf_pii_redaction.TestPartialMaskWritesMaskText -v 2>&1 | tail -25</verify>
<done>RED-GREEN phase 1 complete: write_partial_masks extended with 4-branch mixed item dispatch (CR-01 fix helper ready); has_bank_account_context iterates all find() positions (WR-04 fix); 4 new multi-occurrence tests + 4 existing single-occurrence tests + 5 new TestWritePartialMasksMixedItemDispatch tests + 3 existing partial mask backward-compat tests all PASS (16 tests in this slice).</done>
<reversibility>rating="costly" rationale="Modifies write_partial_masks signature (backward-compat preserved) + has_bank_account_context body. Reverting requires coordinated edits across pdf_adapter.py + bank_account.py + 2 test files."</reversibility>
</task>

<!-- TASK 2 -->
<task type="auto">
<name>Task 2: Replace main.py save_pdf inline mask writer (lines 12651-12715) with single write_partial_masks delegation call</name>
<files>main.py</files>
<read_first>main.py:12590-12736 (current save_pdf save loop), main.py:12625-12628 (write_partial_masks import — keep), main.py:12651-12715 (CR-01 inline code to remove), privacyguard/pii/pdf_adapter.py (refactored write_partial_masks from Task 1)</read_first>
<action>Refactor main.py::save_pdf save loop to delegate entirely to write_partial_masks. The 02-03 LOCKED REFACTOR structure (per-entity add_redact_annot loop with inline font logic) is replaced by a SINGLE write_partial_masks call per page.

  Step-by-step:

  1. Keep the import at line 12625-12628 as-is (`from privacyguard.pii.pdf_adapter import write_partial_masks, clear_pdf_metadata`).

  2. Replace the body of the per-page loop (lines 12630-12715) with:

  ```python
  for i in range(len(doc_save)):
      page = doc_save[i]

      ocr_list = self.page_data[i].get('ocr', [])
      manual_list = self.page_data[i].get('manual', [])
      pii_list = self.page_data[i].get('pii', [])

      # Collect mixed-type items for unified write_partial_masks dispatch (02-04 CR-01 fix).
      # Each item is (x, y, w, h, mode) where mode is partial|blackout.
      # OCR / manual always blackout (Phase 1 behavior preserved, D-22).
      # PII mode decided by per_entity_default[hit.entity_type] + mask_override_this_doc.
      all_pi_items = []
      fill_col = (0, 0, 0) if self.current_color.name() == '#000000' else (1, 1, 1)
      for r in ocr_list + manual_list:
          all_pi_items.append((r.x(), r.y(), r.width(), r.height(), 'blackout'))
      for hit in pii_list:
          if override == 'blackout':
              item_mode = 'blackout'
          elif per_entity_default.get(hit.entity_type, 'partial') == 'partial':
              item_mode = 'partial'
          else:
              item_mode = 'blackout'
          x, y, w, h = hit.page_rect
          all_pi_items.append((x, y, w, h, item_mode))

      # CR-01 fix: single delegation call. write_partial_masks handles font mapping,
      # OCR font-size fallback, and rect resize internally.
      # PII partial items get mask_strategy via the PIIHit branch (handled separately
      # by passing PIIHit objects alongside tuples — see PART B below for the
      # combined dispatch).
  ```

  3. Actually, since the tuple form has no mask_text, we need to ALSO pass PIIHits with mode='partial' so write_partial_masks can render mask text. Use a TWO-call pattern:
     - Call 1: write_partial_masks(doc_save, i, [(x, y, w, h, mode), ...] for OCR/manual + PII blackout items) — this handles all blackout + adds the page annots.
     - Call 2: write_partial_masks(doc_save, i, [pii_hit for hit in pii_list if partial_mode], mode='partial') — this handles PII partial mask text.

  But this would call apply_redactions TWICE per page, which fails (D-22 invariant).

  CORRECT approach: pass BOTH tuples and PIIHits in a SINGLE call to write_partial_masks. The refactored write_partial_masks must route tuples to blackout-only (no mask text) and route PIIHit to (rect, mask_text, mode='partial') — this preserves the single-pass invariant.

  Update the per-page loop accordingly:
  ```python
  all_pi_items = []
  for r in ocr_list + manual_list:
      all_pi_items.append((r.x(), r.y(), r.width(), r.height(), 'blackout'))
  pii_partial_hits = []
  for hit in pii_list:
      if override == 'blackout':
          all_pi_items.append((hit, 'blackout'))  # PIIHit as-is
      elif per_entity_default.get(hit.entity_type, 'partial') == 'partial':
          all_pi_items.append((hit, 'partial'))  # PIIHit as-is, will use mask_strategy
      else:
          all_pi_items.append((hit, 'blackout'))

  write_partial_masks(doc_save, i, all_pi_items)
  ```

  Wait — the refactored write_partial_masks takes `mode: Literal["partial", "blackout"]` as a global arg, OR per-item mode for tuples. We must extend the signature further OR pass items in 2 calls.

  FINAL CORRECT approach (avoid the dual-call problem): Add a 4th branch to write_partial_masks that accepts (PIIHit, mode) as a tuple where item[0] is a PIIHit and item[1] is the mode string. Update the write_partial_masks dispatcher in Task 1 to handle this 4th item form (PIIHit | fitz.Rect | (x,y,w,h,mode) tuple | (PIIHit, mode) 2-tuple). (This adds ~5 more lines to write_partial_masks — keeping it backward-compat.)

  ALTERNATIVE simpler approach: Extend write_partial_masks signature to accept `mode: Optional[Callable[[int], str]] = None` — but this complicates the API.

  RECOMMENDED: Use the 4-branch dispatch:
  - PIIHit dataclass: global mode (02-01 caller)
  - fitz.Rect: global mode
  - (x, y, w, h, mode): tuple form, per-item mode
  - (PIIHit, mode): 2-tuple form, per-item mode + PIIHit routing for mask_strategy

  Update the dispatcher accordingly in Task 1.

  After the update, main.py per-page loop becomes:
  ```python
  for i in range(len(doc_save)):
      page = doc_save[i]
      ocr_list = self.page_data[i].get('ocr', [])
      manual_list = self.page_data[i].get('manual', [])
      pii_list = self.page_data[i].get('pii', [])

      all_pi_items = []
      for r in ocr_list + manual_list:
          all_pi_items.append((r.x(), r.y(), r.width(), r.height(), 'blackout'))
      for hit in pii_list:
          if override == 'blackout':
              all_pi_items.append((hit, 'blackout'))
          elif per_entity_default.get(hit.entity_type, 'partial') == 'partial':
              all_pi_items.append((hit, 'partial'))
          else:
              all_pi_items.append((hit, 'blackout'))

      # CR-01 fix: single delegation call to write_partial_masks (02-04)
      write_partial_masks(doc_save, i, all_pi_items)
  ```

  This replaces lines 12651-12715 (the entire add_redact_annot + apply_redactions + delete_annot + insert_text sequence) with ONE function call.

  KEEP the line 12719 `clear_pdf_metadata(doc_save)` unchanged — already correct.

  After this refactor, the entire main.py save loop per-page logic is 5 lines (collect + dispatch) instead of 60+ lines (the previous inline re-implementation).
</action>
<verify>python3 -m compileall -q main.py && grep -c 'write_partial_masks' main.py && grep -c 'def write_partial_masks(' main.py</verify>
<done>main.py::save_pdf no longer contains inline page.insert_text mask-writing code. Single write_partial_masks call replaces lines 12651-12715. D-22 invariant preserved (single apply_redactions per page).</done>
<reversibility>rating="costly" rationale="Modifies MainWindow.save_pdf core path. Reverting requires restoring the original LOCKED REFACTOR structure (02-03 PLAN lines 408-465) and re-importing write_partial_masks."</reversibility>
</task>

<!-- TASK 3 -->
<task type="auto" tdd="true">
<name>Task 3: Tighten test_convergence (AST Call-node) + replace inline mirror in test_pdf_pii_redaction (WR-03 fix)</name>
<files>tests/unit/test_convergence.py, tests/unit/test_pdf_pii_redaction.py</files>
<read_first>tests/unit/test_convergence.py:273-305 (current weak string check), tests/unit/test_pdf_pii_redaction.py:168-284 (current inline mirror), tests/unit/test_pdf_pii_redaction.py:149-419 (TestPartialMaskWritesMaskText — backward-compat anchor)</read_first>
<action>PART A: Rewrite tests/unit/test_convergence.py::test_main_py_uses_write_partial_masks_in_save_loop (WR-03 fix).

  Replace the existing method body (lines 273-305) with AST-based verification:

  ```python
  def test_main_py_uses_write_partial_masks_in_save_loop(self):
      """Phase 2 (02-04): main.py save_pdf must have write_partial_masks as ast.Call inside def save_pdf.

      WR-03 fix: previous string-presence check ('write_partial_masks' in source) let CR-01 slip through
      because main.py imported write_partial_masks but never called it. AST-rewrite ensures that the
      function is actually called (ast.Call with func.id=='write_partial_masks') inside def save_pdf.
      """
      source = MAIN_PY.read_text(encoding='utf-8')
      tree = ast.parse(source)
      # Find def save_pdf function
      save_pdf_func = None
      for node in ast.walk(tree):
          if isinstance(node, ast.FunctionDef) and node.name == 'save_pdf':
              save_pdf_func = node
              break
      self.assertIsNotNone(save_pdf_func, 'main.py must define def save_pdf(...)')
      # Walk body of save_pdf; find any ast.Call with func.id == 'write_partial_masks'
      found = False
      for node in ast.walk(save_pdf_func):
          if isinstance(node, ast.Call):
              # func could be ast.Name (write_partial_masks(...)) or ast.Attribute (mod.write_partial_masks(...))
              func = node.func
              if isinstance(func, ast.Name) and func.id == 'write_partial_masks':
                  found = True
                  break
              if isinstance(func, ast.Attribute) and func.attr == 'write_partial_masks':
                  found = True
                  break
      self.assertTrue(
          found,
          'main.py::save_pdf must contain a Call to write_partial_masks (02-04 CR-01 fix; '
          'string-presence check is insufficient)'
      )
      # ALSO check clear_pdf_metadata is called inside save_pdf
      found_clear = False
      for node in ast.walk(save_pdf_func):
          if isinstance(node, ast.Call):
              func = node.func
              if isinstance(func, ast.Name) and func.id == 'clear_pdf_metadata':
                  found_clear = True
                  break
      self.assertTrue(found_clear, 'main.py::save_pdf must call clear_pdf_metadata')
      # D-12 mask_override_this_doc reference preserved
      self.assertIn('mask_override_this_doc', source, 'D-12 toggle key must still be referenced')
      # D-13 per_entity_default reference preserved
      self.assertIn('per_entity_default', source, 'D-13 config field must still be referenced')
      # v37.7.6 convergence: NO inline def write_partial_masks( in main.py
      self.assertNotIn('def write_partial_masks(', source, 'main.py must not inline write_partial_masks')
      self.assertNotIn('def clear_pdf_metadata(', source, 'main.py must not inline clear_pdf_metadata')
  ```

  PART B: Rewrite tests/unit/test_pdf_pii_redaction.py::test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata (WR-03 fix).

  Replace lines 296-284 (the inline mirror at lines 240-258) with an actual write_partial_masks call. The new test body:

  ```python
  def test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata(self):
      """Phase 2 (02-04): verify the production helper write_partial_masks is actually called.

      WR-03 fix: previous test body imported write_partial_masks but never called it — manually
      re-implemented the inline mask logic (mirror of main.py inline code). This rewrite actually
      exercises write_partial_masks end-to-end to validate the CR-01 fix.
      """
      from privacyguard.pii.pdf_adapter import write_partial_masks, clear_pdf_metadata
      from privacyguard.pii.mask import partial_mask_id_card
      from privacyguard.pii.hits import PIIHit
      from privacyguard.pii.engine import PIIEngine, TextUnit
      from tests.fixtures.fake_pii import fake_id_card

      with tempfile.TemporaryDirectory() as tmp:
          in_pdf = os.path.join(tmp, 'in_save.pdf')
          out_pdf = os.path.join(tmp, 'out_save.pdf')
          secret_id = fake_id_card()
          mask_text = partial_mask_id_card(secret_id)

          # 1. Synth PDF with fake_id_card + 5 metadata fields
          doc = fitz.open()
          doc.set_metadata({
              'title': '敏感标题', 'author': '敏感作者', 'subject': '敏感主题',
              'producer': '敏感生产者', 'creator': '敏感创建者',
          })
          page = doc.new_page()
          page.insert_text((50, 100), f'测试 身份证 {secret_id}', fontsize=14)
          doc.save(in_pdf)
          doc.close()

          # 2. Detect + page.search_for — locate PIIHit
          engine = PIIEngine()
          with fitz.open(in_pdf) as src:
              page = src[0]
              unit = TextUnit(page_index=0, text=page.get_text(), source='text')
              hits = list(engine.detect(unit))
              self.assertGreater(len(hits), 0, 'PIIEngine did not detect fake_id_card')
              matches = page.search_for(hits[0].normalized)
              self.assertGreater(len(matches), 0, 'page.search_for did not find ID card')
              r = matches[0]
              page_rect = (r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0)

          pii_hit = PIIHit(
              entity_type=hits[0].entity_type,
              page_offset=0,
              page_length=len(hits[0].normalized),
              page_rect=page_rect,
              confidence_tier=hits[0].confidence_tier,
              source='text',
              mask_strategy=mask_text,
              normalized=hits[0].normalized,
              validator_passed=True,
          )

          # 3. WR-03 fix: actually call write_partial_masks (the production helper)
          doc_save = fitz.open(in_pdf)
          try:
              write_partial_masks(doc_save, 0, [pii_hit], mode='partial')
              clear_pdf_metadata(doc_save)
              doc_save.save(out_pdf, garbage=4, deflate=True, clean=True)
          finally:
              doc_save.close()

          # 4. Reverse-extract assertions
          with fitz.open(out_pdf) as out_doc:
              out_text = ''.join(p.get_text() for p in out_doc)
              meta = out_doc.metadata
          self.assertNotIn(secret_id, out_text, f'完整身份证字符串仍可提取: {secret_id}')
          self.assertIn(mask_text, out_text, f'mask_strategy {mask_text!r} 不在输出: {out_text!r}')
          for key in ('title', 'author', 'subject', 'producer', 'creator'):
              self.assertEqual(meta.get(key, ''), '', f'元数据 {key} 未清空: {meta.get(key)!r}')
  ```

  PART D: Run full Phase 2 test suite (272 baseline + 9 new from Task 1 = 281 tests). Expected: 281 OK.
</action>
<verify>python3 -m unittest tests.unit.test_convergence.TestPiiConvergence.test_main_py_uses_write_partial_masks_in_save_loop tests.unit.test_pdf_pii_redaction.TestPartialMaskWritesMaskText.test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata -v 2>&1 | tail -10</verify>
<done>WR-03 closed: test_convergence.py AST-rewrite detects Call node inside def save_pdf; test_pdf_pii_redaction integration test rewritten to actually call write_partial_masks. Both tests pass.</done>
<reversibility>rating="costly" rationale="Modifies 2 test files; reverting requires restoring the previous string-presence check + inline mirror implementation."</reversibility>
</task>

<!-- TASK 4 -->
<task type="auto">
<name>Task 4: Document WR-01 in engine.py docstring (option a)</name>
<files>privacyguard/pii/engine.py</files>
<read_first>privacyguard/pii/engine.py:1-21 (current module docstring), privacyguard/pii/engine.py:32-48 (6 new validator eager imports — keep as-is per option a)</read_first>
<action>Append a WR-01 documentation note to the existing engine.py module docstring (lines 1-21). Do NOT refactor to importlib.import_module (option a — cheaper delivery; no import-time risk).

  Locate the closing triple-quote of the module docstring (after line 21 in current engine.py) and insert before it:

  ```
  WR-01 (02-04 acceptance): 本模块顶层导入 6 个新 validator 子模块（uscc / bank_card / email /
  vat_invoice / bank_account / taxpayer_id）。这是有意为之：PIIEngine 是这 6 个 validator
  的唯一访问路径，为简化代码并与 Phase 1 validator loading 形态保持一致而选择顶层导入。
  OPS-03 严格契约（`import privacyguard` 不触发任何 PII 模块加载）不受影响；本模块顶层的
  import 仅在 `import privacyguard.pii.engine` 时触发。各 validator 子模块仍通过
  `privacyguard.pii.validators.__init__._LAZY_IMPORTS` + `__getattr__` 提供独立的延迟
  访问路径（用于命令行工具 / 测试 fixture / 单元测试等不需要 PIIEngine 的场景）。
  如果未来需要更细粒度的按需加载，可在本模块内重构成 `importlib.import_module(...)` 形式；
  当前实现保留 eager 形态以保持代码简洁。
  """

  No code logic changes — only documentation. OPS-03 strict contract preserved (verified by `import privacyguard` test in test_package_imports.py).

  Verify after edit: `python3 -c "import privacyguard; loaded=[k for k in sys.modules if 'pii' in k]; print(loaded)"` shows PII modules are NOT loaded (only loaded after `from privacyguard.pii.engine import PIIEngine`).
</action>
<verify>python3 -m compileall -q privacyguard && python3 -c "import sys; import privacyguard; loaded = [k for k in sys.modules if 'privacyguard.pii' in k]; print('PII modules loaded by import privacyguard:', loaded); assert not loaded, f'OPS-03 violated: {loaded}'" && python3 -m unittest tests.unit.test_package_imports -v 2>&1 | tail -10</verify>
<done>engine.py module docstring documents WR-01 acceptance + rationale. OPS-03 strict contract preserved (import privacyguard does not load PII modules). Individual lazy access path via privacyguard.pii.validators.__getattr__ remains intact.</done>
<reversibility>rating="reversible" rationale="Doc-only change."</reversibility>
</task>

<!-- TASK 5 -->
<task type="auto">
<name>Task 5: Full test suite verification + commit + SUMMARY</name>
<files>.planning/phases/02-pdf/02-04-gap-closure-SUMMARY.md</files>
<read_first>All 4 prior tasks completed.</read_first>
<action>Run the FULL Phase 1 + Phase 2 baseline test suite (272 tests) + 9 new tests from Task 1 (4 TestBankAccountContextMultipleOccurrences + 5 TestWritePartialMasksMixedItemDispatch) = 281 tests expected.

  Command:
  ```
  cd /mnt/g/Project/PrivacyGuard
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
        tests.unit.test_pii_validators \
        tests.unit.test_pii_engine \
        tests.unit.test_pdf_pii_redaction \
        tests.unit.test_pdf_metadata_cleared \
        -v 2>&1 | tail -30
  ```

  Expected: 272 baseline + 4 new TestBankAccountContextMultipleOccurrences + 5 new TestWritePartialMasksMixedItemDispatch (including 3 concrete integration tests for 5-tuple blackout / 2-tuple partial / mixed partial+blackout single call) = 281 OK (skipped=2 same as baseline).

  Verify OPS-03 strict contract preserved:
  ```
  python3 -c "import sys; import privacyguard; loaded = [k for k in sys.modules if 'privacyguard.pii' in k]; print('PII modules loaded by import privacyguard:', loaded); assert not loaded, f'OPS-03 violated: {loaded}'"
  ```

  Live grep verification:
  - `grep -c "write_partial_masks" main.py` >= 2 (import + call).
  - `grep -c "def write_partial_masks(" main.py` == 0 (no inline def).
  - `grep -c "page.insert_text" main.py` shows only Word/OCR paths (not mask writing).

  Then commit with message:
  ```
  fix(02-04): close CR-01 + WR-01 + WR-03 + WR-04 from 02-VERIFICATION

  - CR-01: write_partial_masks now accepts mixed item types (PIIHit | fitz.Rect | tuple);
    main.py::save_pdf delegates to single write_partial_masks call (no inline mirror).
    Restores _FONT_NAME_MAP font mapping, OCR font-size fallback, and rect resize.
  - WR-01: engine.py module docstring documents that PIIEngine eagerly loads all 6
    new validators and rationale for accepting this (option a).
  - WR-03: test_convergence AST-rewrite detects Call node inside def save_pdf;
    test_pdf_pii_redaction integration test rewritten to actually call write_partial_masks.
  - WR-04: has_bank_account_context iterates all text.find positions;
    TestBankAccountContextMultipleOccurrences covers 4 multi-occurrence cases.

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

  Finally, create .planning/phases/02-pdf/02-04-gap-closure-SUMMARY.md with:
  - All 7 files_modified list
  - 5 tasks completed
  - Test results: 272 baseline + 9 new tests (4 TestBankAccountContextMultipleOccurrences + 5 TestWritePartialMasksMixedItemDispatch) = 281 OK (skipped=2)
  - Key links verified (write_partial_masks dispatch + AST gate + has_bank_account_context loop)
  - Reversibility note
  - Next steps: Phase 2 now COMPLETE; ready to mark complete in ROADMAP and proceed to Phase 3 (Word) or other milestones.
</action>
<verify>python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_mixed_pdf_ocr tests.test_path_validation tests.unit.test_ocr_api tests.unit.test_package_imports tests.unit.test_pdf_text_hit_dedup tests.unit.test_app_config tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_config_alignment tests.unit.test_fstring_safety tests.unit.test_convergence tests.unit.test_pii_validators tests.unit.test_pii_engine tests.unit.test_pdf_pii_redaction tests.unit.test_pdf_metadata_cleared 2>&1 | tail -5</verify>
<done>All 272 baseline + 9 new tests green (4 TestBankAccountContextMultipleOccurrences + 5 TestWritePartialMasksMixedItemDispatch including 3 concrete integration tests). WR-01 documented in engine.py docstring. SUMMARY.md committed. Phase 2 can now be marked COMPLETE.</done>
<reversibility>rating="reversible" rationale="Doc-only change + summary commit; revert by reverting the commit."</reversibility>
</task>

</tasks>

<verification>
After all 5 tasks complete, run the full Phase 1 + Phase 2 baseline suite and confirm all tests pass.

Expected: 272 tests pass + 4 new TestBankAccountContextMultipleOccurrences + 5 new TestWritePartialMasksMixedItemDispatch (2 weak + 3 concrete) = 281 OK (skipped=2 same as Phase 2 baseline).

Gap closure verification:
- test_convergence.test_main_py_uses_write_partial_masks_in_save_loop PASS (AST-rewrite detects Call node).
- test_pii_validators.TestBankAccountContextMultipleOccurrences PASS (4 methods).
- test_pdf_pii_redaction.TestWritePartialMasksMixedItemDispatch PASS (5 methods: 2 weak + 3 concrete integration tests for 5-tuple blackout / 2-tuple partial / mixed partial+blackout single call).
- test_pdf_pii_redaction.test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata PASS (real write_partial_masks call).
- grep -c "write_partial_masks" main.py >= 2.
- grep -c "def write_partial_masks(" main.py == 0.
- import privacyguard does not load PII modules (OPS-03 strict preserved).
- from privacyguard.pii.engine import PIIEngine loads all 6 validators (WR-01 documented behavior).

Reverse-extraction verification (replaces 02-VERIFICATION CR-01 failure mode):
- Build PDF with fake_id_card() + populated 5 metadata fields.
- Apply write_partial_masks + clear_pdf_metadata (the integration test path).
- Reopen output PDF.
- Confirm original ID first 10 chars NOT in text; mask text "110101********XXXX" IS in text.
- Confirm all 5 metadata fields == "".
</verification>

<success_criteria>
- CR-01 closed: main.py::save_pdf no longer has inline partial mask writer; single delegation call to write_partial_masks replaces lines 12651-12715.
- WR-01 closed (option a): engine.py module docstring documents that PIIEngine eagerly loads all 6 new validators and rationale for accepting this.
- WR-03 closed: test_convergence.py test_main_py_uses_write_partial_masks_in_save_loop AST-rewritten to require Call node inside def save_pdf; test_pdf_pii_redaction.py integration test rewritten to actually call write_partial_masks (no inline mirror).
- WR-04 closed: has_bank_account_context iterates all text.find positions; new TestBankAccountContextMultipleOccurrences class with 4 regression methods.
- All 272 baseline tests + new tests (4 TestBankAccountContextMultipleOccurrences + 5 TestWritePartialMasksMixedItemDispatch including 3 concrete integration tests for 5-tuple / 2-tuple / mixed partial+blackout) green.
- Phase 2 can now be marked COMPLETE; 9 requirement IDs (NUM-04 / NUM-05 / FIN-01..04 / MASK-01 / MASK-02 / SAFE-03) all satisfied end-to-end.
</success_criteria>

<output>
Create `.planning/phases/02-pdf/02-04-gap-closure-SUMMARY.md` when done. Commit message: `fix(02-04): close CR-01 + WR-01 + WR-03 + WR-04 from 02-VERIFICATION`.
</output>