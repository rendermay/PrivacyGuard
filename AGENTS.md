# AGENTS.md

This file is the primary development guide for Codex and other coding agents working in this repository.

---

## Project Overview

**Project**: SecureRedact 信息脱敏助手  
**Current Version**: v1.1.11 (`1.1.11 - Whitelist Span Trim`)  
**Last Updated**: 2026-08-20  
**Status**: v1.1.11 白名单片段级豁免完成；全量回归 162 项 / 160 通过（2 项为 v1.1.11 起既有失败）

SecureRedact is a Python + PyQt6 desktop application for intelligent redaction of PDF and Word documents.

### Current active capabilities

- PDF redaction:
  - text PDF search via PyMuPDF
  - image PDF OCR via RapidOCR
  - mixed PDF redaction via text-layer search + embedded image-block OCR
  - manual rectangle redaction
- Word redaction:
  - intelligent scan
  - manual precise/global redaction
  - multi-field replacement rules (`exact` / `regex`)
  - batch replace for `.docx` / `.doc`
- Word dual preview:
  - left: original preview with OCR/manual highlights
  - right: merged replaced preview (`rule > manual > ocr`)
- Drag & drop open
- Windows and macOS packaging scripts

---

## Read First

When resuming work, read these files in order:

1. `docs/current/STATUS.md`
2. `docs/current/DEV_LOG.md`
3. `CHANGELOG.md`
4. `docs/guides/QUICK_START_FOR_CLAUDE_CODE.md`

---

## Current Technical Reality

### Main architecture

- `main.py` is still the active runtime entry and remains monolithic.
- `secureredact/` contains shared modules and partial extractions, but not all runtime logic has moved there.
- Avoid reintroducing drift between `main.py` and `secureredact/*`.

### Version source

- Single source of truth: `version.txt`
- `main.py` and `secureredact.__version__` both read from it
- Packaging defaults and version resources must stay aligned with `version.txt`

### Active config path

- Runtime currently uses `SimpleConfig` in `main.py`
- Shared config utilities also exist in `secureredact/utils/config.py`
- Do not assume `ConfigManager` is the active runtime path unless you have explicitly switched the app over

### OCR dependency behavior

- `secureredact` package import is now lazy
- `RapidOCR` must only initialize at actual OCR execution time
- Do not add package-level eager OCR imports back into `secureredact/__init__.py` or `secureredact/workers/__init__.py`

### Mixed PDF handling

- Mixed PDF pages must not be treated as text-only or scan-only.
- The active path is:
  1. text-layer hit collection
  2. embedded image block discovery via `page.get_text("dict")`
  3. image-block OCR
  4. local OCR box offset back into page coordinates
- Shared logic lives in `secureredact/ocr/mixed_pdf.py`

---

## Key Runtime Data Structures

### PDF state

- `self.page_data[page_num] = {"ocr": [...], "manual": [...]}`

### Word state

- `self.word_data[key] = {"text": ..., "ocr": [...], "manual": [...], ...}`
- `self.word_replace_rules` stores session-level multi-field replacement rules

### Word preview model

The active path is:

1. DOCX -> HTML via `mammoth`
2. HTML tagged with `data-key`
3. Left panel updates by block with original-text highlight fragments
4. Right panel updates by block with merged replacement fragments
5. DOM is updated via keyed JavaScript patching instead of always doing full `setHtml()`

Important:

- compare mode may start with the right panel hidden or blank
- `cp20` added per-panel loaded-source tracking
- `cp27` restricted incremental DOM patching to actual word blocks and prevents highlight-node corruption
- when compare mode becomes active after an empty state, the right panel must reload the full document before applying partial updates

---

## Main Files

- `main.py` - active application runtime
- `theme.py` - UI theme definitions
- `version.txt` - single version source
- `config.json` - local runtime config
- `secureredact/__init__.py` - package metadata + lazy exports
- `secureredact/ocr/text_pdf.py` - shared text-PDF hit collection
- `secureredact/ocr/mixed_pdf.py` - shared mixed-PDF image-block OCR helper
- `secureredact/workers/ocr_worker.py` - modular OCR worker
- `secureredact/workers/word_worker.py` - modular Word worker
- `secureredact/workers/image_merge.py` - modular image merge worker
- `secureredact/utils/doc_converter.py` - shared DOC→DOCX converter
- `secureredact/utils/config.py` - modular config manager
- `secureredact/utils/exceptions.py` - shared exception classes
- `secureredact/utils/temp_manager.py` - shared temp file manager
- `secureredact/utils/security.py` - shared path validation & resource_path

---

## Common Commands

### Run app

```bash
cd /Users/a49144/Desktop/codexhub/SecureRedactApp
python3 main.py
```

### Compile check

```bash
python3 -m compileall -q main.py secureredact tests
```

### Main regression suite

```bash
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
  -v
```

Current verified baseline: `79/79`.

### Version check

```bash
cat version.txt
```

---

## Packaging

Use the current packaging docs instead of old ad-hoc notes:

- `docs/packaging/README.md`
- `docs/packaging/windows-packaging-guide.md`
- `docs/packaging/macos-packaging-guide.md`
- `packaging/README.md`

Main commands:

```bash
# macOS
./packaging/macos/scripts/build_complete.sh

# Windows
packaging/windows/scripts/build_complete.bat
```

---

## Current Checkpoints

（无 — 历史 checkpoint 已随 rollback 工具链一同清理；项目以 `version.txt` 为单一版本源。）

---

## Current Development Direction

Current default track:

1. screenshot-driven UI polish on top of the completed v38 code layer
2. Phase 2: per-file rule mapping for batch replace
3. batch rule-set templates
4. preview highlight filtering by source (`rule / manual / ocr`)

If the UI polish track is paused and no regressions are being fixed, default next feature work should be:

1. Phase 2: per-file rule mapping for batch replace
2. batch rule-set templates
3. preview highlight filtering by source (`rule / manual / ocr`)

If a regression appears in PDF OCR, prioritize checking:

1. text-layer vs image-block split
2. image clip extraction validity
3. OCR box offset back to page coordinates
4. deduplication after merged hits
