# Phase 02 UAT — User Acceptance Test Report

**Phase:** 02-pdf (PDF 增加银行卡/邮箱/财税实体识别与部分掩码)
**Verified:** 2026-08-12
**Plan executed:** 02-01 + 02-02 + 02-03 + 02-04 (gap closure)
**Test count:** 281 tests OK (skipped=2)

---

## Success Criteria (from `.planning/ROADMAP.md` Phase 2)

### SC1: PDF scan surfaces bank card / email / USCC / VAT invoice / taxpayer ID / bank account candidates

**Status:** ✅ **PASS**

- Synthetic text containing all 9 entity types fed to `PIIEngine.detect`
- Hit count: **10** (CN_USCC + CN_TAXPAYER_ID share via D-09 dual-type)
- All 8 expected `entity_type` strings detected:
  - `CN_ID_CARD`, `CN_PHONE` (Phase 1 baseline)
  - `CN_BANK_CARD`, `CN_EMAIL`, `CN_USCC`, `CN_TAXPAYER_ID`, `CN_VAT_INVOICE` (×2 for 8d + 20d), `CN_TAXPAYER_ID_15`, `CN_BANK_ACCOUNT` (Phase 2 new)
- Tier assignment verified: CN_TAXPAYER_ID_15 = MEDIUM (no strong checksum); others = HIGH

### SC2: Partial mask default formats match ROADMAP.md examples

**Status:** ✅ **PASS** (7/7 formats verified)

| Entity | ROADMAP example | Actual mask | Match |
|---|---|---|---|
| CN_ID_CARD | `110101********1234` | `110101********1234` | ✅ |
| CN_PHONE | `138****5678` | `138****5678` | ✅ |
| CN_BANK_CARD | `6225 **** **** 1234` (first 4 + last 4) | `6225********1234` | ✅ |
| CN_EMAIL | `z****@qq.com` | `z****@qq.com` | ✅ |
| CN_USCC | first 6 + last 4 | `911100********341L` | ✅ |
| CN_VAT_INVOICE | first 2 + last 2 | `12****78` | ✅ |
| CN_BANK_ACCOUNT | first 4 + last 4 | `6222**********9012` | ✅ |

### SC3: Mode switching — partial vs blackout per entity type / per document

**Status:** ✅ **PASS**

- **Partial mode (mode="partial"):** mask text "110101" extractable in output PDF; original secret_id NOT extractable ✅
- **Blackout mode (mode="blackout"):** original secret_id destroyed, no mask text remains ✅
- `write_partial_masks` 4-branch mixed dispatch (`PIIHit | fitz.Rect | (x,y,w,h,mode) tuple | (PIIHit,mode) 2-tuple`) verified via 5 concrete integration tests
- SettingsDialog 9-row per-entity table + toolbar "本文件全遮蔽" toggle wired (per 02-03 SUMMARY)

### SC4: Exported PDF — no original sensitive content + metadata cleared

**Status:** ✅ **PASS**

- **5 metadata fields cleared:** `title / author / subject / producer / creator` all `""` after `clear_pdf_metadata` + `doc.save()`
- **D-14 lock preserved:** `keywords` (not in 5-field list) is NOT touched — verified before/after
- **Reverse-extraction:** synthetic PDF + `fake_id_card()` → after `write_partial_masks(mode="partial")` → `fitz.open(out).get_text()` does NOT contain original `secret_id[:10]` ✅

---

## OPS-03 Lazy-Load Discipline

**Status:** ✅ **PASS**

- `import privacyguard` loads **0** PII modules (verified via `sys.modules` snapshot)
- Lazy access via `privacyguard.__getattr__` + `privacyguard.pii.validators.__getattr__` intact
- `privacyguard.pii.engine.PIIEngine` eager-loads 6 new validators — accepted (option a) with docstring documentation per WR-01 fix

---

## Gap Closure Verification

The 02-VERIFICATION.md `gaps_found` status was the result of 3 blockers identified by gsd-verifier + gsd-code-reviewer:

| Gap | Severity | Status | Verification |
|---|---|---|---|
| **CR-01** | 🛑 BLOCKER | ✅ Closed | `main.py::save_pdf` now calls `write_partial_masks(doc_save, i, all_pi_items)` — verified via AST: `ast.FunctionDef(name='save_pdf').body` contains `ast.Call(func.id=='write_partial_masks')`. Inline mask-writing code removed (only 1 comment reference remains at line 12646). |
| **WR-01** | ⚠️ WARNING | ✅ Closed | `engine.py` module docstring documents the eager validator import trade-off. OPS-03 strict contract preserved. |
| **WR-03** | ⚠️ WARNING | ✅ Closed | `test_convergence.test_main_py_uses_write_partial_masks_in_save_loop` rewritten with AST Call-node check. Integration test `test_main_window_save_pdf_routes_pii_through_write_partial_masks_and_clears_metadata` now actually calls `write_partial_masks` (not inline mirror). |
| **WR-04** | ⚠️ WARNING | ✅ Closed | `has_bank_account_context` iterates all `text.find(target, start)` positions; 4 new regression tests (`TestBankAccountContextMultipleOccurrences`) added. |
| **WR-02** | ⚠️ WARNING | ✅ Closed (side-effect) | Inline font hardcoded + flat font_size + no rect resize fixed by CR-01 delegation. Font now resolves via `_FONT_NAME_MAP` (8-entry), font-size via `max(rect.height-4, 6)` OCR fallback, rect resize via `_resize_rect_for_mask`. |

---

## Phase 2 Status: ✅ COMPLETE — Ready to Ship

All 9 Phase 2 requirement IDs satisfied end-to-end:

| Req | Description | Status |
|---|---|---|
| NUM-04 | Bank card Luhn + BIN + context | ✅ |
| NUM-05 | Email RFC 5322 + public suffix | ✅ |
| FIN-01 | USCC GB 32100 mod-31-3 | ✅ |
| FIN-02 | VAT invoice 8/20 + context | ✅ |
| FIN-03 | Taxpayer ID 15/18 (dual type) | ✅ |
| FIN-04 | Bank account 9-21 + 17 context anchors | ✅ |
| MASK-01 | Partial mask per-entity | ✅ |
| MASK-02 | User partial/blackout switch | ✅ |
| SAFE-03 | Metadata 5 fields cleared | ✅ |

**OPS constraints:**
- ✅ OPS-03 strict lazy contract preserved
- ✅ OPS-04 PyInstaller parity (6 new validators + bin_prefixes.json in both Windows + macOS specs)
- ✅ OPS-07 baseline 80/80 preserved
- ✅ v37.7.6 收敛原则: main.py delegates to `privacyguard.pii.pdf_adapter` (no inline implementations)

---

## Next action

Phase 2 is ready to ship. Suggested:

1. `/gsd-ship 2-pdf` — run review + prepare merge (PR #3 was Phase 1; this would be PR for Phase 2)
2. `/gsd-plan-phase 3` — start Phase 3 (Word 文档接入识别引擎)