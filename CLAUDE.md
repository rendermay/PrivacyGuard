# CLAUDE.md

This file is the primary development guide for Claude Code and other coding agents working in this repository.

---

## Project Overview

**Project**: SecureRedact 信息脱敏助手  
**Current Version**: v1.1.13 (`1.1.13 - Name Context Injection`)  
**Last Updated**: 2026-08-24  
**Status**: v1.1.13 姓名上下文注入 + 三层防护收口完成；WordWorker/OCRWorker 默认严格模式 (require_context=True)

SecureRedact is a Python + PyQt6 desktop application for intelligent redaction of PDF and Word documents.

> **⚠️ v1.1.13+ 入口迁移提示 (PR-B0)**
>
> `main.py` (13,026 行) 已转为 **过渡期兼容 shim**。
> 真正的运行时入口已迁至 `secureredact/main.py`(v1.1.13 PR-B0 引入)。
>
> **禁止继续往 `main.py` 添加新业务代码。**所有新功能请写到 `secureredact/` 对应子包。
> 阶段 B 重构路线图:详见 `frontend-refactor-plan.md`(当前工作目录)+ `docs/refactor/` (项目内报告)。
> 阶段 B5 收口时 `main.py` 将被彻底移除,所有打包入口 (`SecureRedact_verify.spec`、`start_app.sh`、packaging 脚本) 同步切换到 `secureredact.main:main`。

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
- 白名单片段级豁免 (Whitelist Span Trim, v38):
  - 白名单条目仅豁免自身所在片段，同区间内其他敏感内容仍脱敏
  - 通过 `redaction.whitelist_trim_only`（默认 True）控制；设为 False 回退到 v1.1.11 行为
  - 覆盖 Word matches、PDF 文本通道、PDF 图片通道 OCR
- Drag & drop open
- 人工干预 (Manual Redaction Intervention):
  - 自动命中支持右键「忽略 / 确认 / 撤销 / 提升为永久」
  - 会话级 + 永久级双层 override，由 `HitOverrideStore` 单例统一管理
  - 专用干预 dock 面板（按 scope / action 筛选）
  - 设置中心「清理失效 overrides」
- Windows and macOS packaging scripts

---

## Read First

When resuming work, read these files in order:

1. `docs/current/STATUS.md`
2. `docs/current/DEV_LOG.md`
3. `CHANGELOG.md`
4. `docs/guides/QUICK_START_FOR_CLAUDE_CODE.md`
5. `docs/current/PROJECT_STRUCTURE.md`

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
- **v1.1.11 中文姓名启发式识别 (jieba X3)**：新增 `redaction.enable_name_recognition` 键，默认 False
- **v1.1.11 人工干预 (Hit Override)**：新增 `redaction.enable_hit_override`（默认 True）与 `redaction.overrides.permanent`

### Hit override store (人工干预)

- 核心包：`secureredact/redaction/`
  - `hit_ref.py` — `HitRef`(frozen) + `Override`；`hit_id = f"{doc_hash}|{location}|{start}|{end}|{source}"`
  - `doc_hash.py` — `compute_doc_hash(file_path)`，基于 路径 + size + mtime 的 8 位标识
  - `override_store.py` — `HitOverrideStore` 单例，session / permanent 双层作用域
- **唯一消费入口**：`HitOverrideStore.instance().filtered_hits(hits, location=..., doc_hash=...)`
  - 任何新的命中消费端都必须经此入口，禁止自行判定 override
- `manual` 来源命中永不被过滤（人工框选是显式意图）
- `OCRWorker.page_result_signal` payload 是 `list[dict]`（含 `rect` / `source` / `text` / `start` / `end`），**不再是** `list[QRectF]`
- 永久 override 存于 `config.json` 的 `redaction.overrides.permanent`，写入走 tmp + rename 原子替换
- 默认空 override 时行为与 v1.1.11 完全一致

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
- `secureredact/redaction/hit_ref.py` - `HitRef` / `Override` 数据模型
- `secureredact/redaction/doc_hash.py` - 文档 8 位标识
- `secureredact/redaction/override_store.py` - `HitOverrideStore` 单例 + `filtered_hits`

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

Current verified baseline: `162` 项 / `160` 通过（见下方 full regression）。

### Extended regression (hit override / 人工干预)

```bash
python3 -m unittest \
  tests.unit.test_hit_ref \
  tests.unit.test_doc_hash \
  tests.unit.test_override_store \
  tests.unit.test_override_config_defaults \
  tests.unit.test_ocr_worker_source_field \
  tests.unit.test_pdf_source_field \
  tests.unit.test_word_source_field \
  tests.unit.test_bridge_override_slots \
  tests.unit.test_overrides_persistence \
  -v
```

共 38 例，全部 PASS。

### Full regression (v1.1.11 基线)

```bash
python3 -m compileall -q main.py secureredact tests
python3 -m unittest \
  tests.unit.test_hit_ref \
  tests.unit.test_doc_hash \
  tests.unit.test_override_store \
  tests.unit.test_override_config_defaults \
  tests.unit.test_ocr_worker_source_field \
  tests.unit.test_pdf_source_field \
  tests.unit.test_word_source_field \
  tests.unit.test_bridge_override_slots \
  tests.unit.test_overrides_persistence \
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
  tests.unit.test_redaction_rule_patterns \
  tests.unit.test_name_recognizer \
  tests.unit.test_worker_name_recognition \
  tests.unit.test_enable_name_recognition_persistence \
  tests.unit.test_whitelist_split \
  tests.unit.test_whitelist_trim_only \
  tests.unit.test_whitelist_trim_only_config \
  -v
```

结果：`Ran 162 tests` / `FAILED (failures=2)`。

**已知既有失败（非回归，自 v1.1.11 起存在）**：
`tests.unit.test_config_alignment.test_scan_default_level_matches` 与
`test_simple_config_reads_config_json_values` —— `config.json` 中
`redaction.scan.default_level` 为 `2.0`，测试期望 `1.5`。修复前请勿把它当成新引入的回归。

### Extended regression (Chinese name recognition)

```bash
python3 -m unittest \
  tests.unit.test_redaction_rule_patterns \
  tests.unit.test_name_recognizer \
  tests.unit.test_worker_name_recognition \
  tests.unit.test_enable_name_recognition_persistence \
  -v
```

### Extended regression (whitelist trim_only / 白名单片段级豁免)

```bash
python3 -m unittest \
  tests.unit.test_whitelist_split \
  tests.unit.test_whitelist_trim_only \
  tests.unit.test_whitelist_trim_only_config \
  tests.unit.test_ocr_worker_whitelist \
  tests.unit.test_word_worker_black_white \
  -v
```

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
