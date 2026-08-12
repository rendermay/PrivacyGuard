---
phase: 03-word
plan: 01
subsystem: pii
tags: [python-docx, qthread, pyqtsignal, lazy-load, partial-mask, metadata-clear, entity-short-code]

# Dependency graph
requires:
  - phase: 02-pdf
    provides: PIIEngine + PIIHit + TextUnit dataclass + privacyguard.pii.* 既有 9 类 entity_hint 可见 + write_partial_masks + clear_pdf_metadata 形态范本 + privacyguard.pii.__init__ 懒加载范本
provides:
  - privacyguard/word/ 子包 5 模块（__init__/adapter/worker/redact/clear_doc_props）骨架与懒加载入口
  - privacyguard/pii/hits.py ENTITY_TYPE_SHORT_CODE 9 短码字典（D-21 + BLOCKER 5 单一来源抽离）
  - privacyguard/__init__.py _LAZY_IMPORTS 扩展 6 项（5 Word 符号 + ENTITY_TYPE_SHORT_CODE 转发）
  - tests/fixtures/fake_word.py build_fake_docx 合成 docx（含 PII）
  - tests/unit/test_word_pii_pipeline.py 5 测试类 7 测试方法 RED 骨架
  - main.py 4 处扩展骨架（_open_word_docx 占位 / _on_word_pii_page_result 占位 / merge_word_matches_with_priority 第六参数 pii_matches=None / _save_word 既有路径未破坏 per BLOCKER 6）
  - packaging/{windows,macos}/config/*.spec hiddenimports 字段级一致追加 6 项 privacyguard.word.*（cp30 教训扩展）
affects:
  - 03-02（依赖 WordAdapter.collect_units + WordPIIWorker.run() + redact_word wrapper + clear_word_doc_props 完整实现落地）
  - 03-03（依赖 candidate_dialog + _apply_word_pii_panel_updates 增量 DOM patch 落地 cp27 局部 patch）
  - 03-04（依赖 test_word_pii_pipeline.py GREEN 状态作为 baseline 88/88）

# Actuals (#2632) — pairs with plan's estimate (85000 tokens / 3 tasks / medium confidence)
# Same scale: chars/4 over realized diff, not harness token count.
actuals:
  tokens: 4800    # chars/4 over files actually changed (479 insertions + 3 deletions)
  tasks: 1        # 1 of 3 tasks completed (Task 1 RED; Task 2 GREEN + Task 3 UI checkpoint pending)
  commits: 1      # 1 commit: test(03-01) RED baseline

# Tech tracking
tech-stack:
  added: []  # Phase 3 零新增依赖（沿用 python-docx + mammoth + PyQt6 既有）
  patterns:
    - "Wave 1 RED 占位策略：NotImplementedError 占位 + 函数签名扩展 + main.py 既有路径不破坏（BLOCKER 6 锁定）"
    - "Wave 1 RED 不调用 stub：_save_word 不路由到 redact_word stub；clear_word_doc_props stub 不在 save 前调（避免 runtime 损坏）"
    - "_LAZY_IMPORTS + __getattr__ 严格 lazy-load：privacyguard/word/ 子包 import 不拉起 python-docx / mammoth / privacyguard.pii.engine"
    - "PyInstaller hiddenimports 字段级一致：双 spec 各 6 行 privacyguard.word.*（cp30 教训扩展）"
    - "ENTITY_TYPE_SHORT_CODE 单一来源抽离 main.py（per BLOCKER 5 + D-21）"

key-files:
  created:
    - privacyguard/word/__init__.py（5 项 lazy forward + __getattr__ + __dir__）
    - privacyguard/word/adapter.py（WordAdapter.collect_units NotImplementedError 占位）
    - privacyguard/word/worker.py（WordPIIWorker QThread 三 signal + run() NotImplementedError 占位）
    - privacyguard/word/redact.py（redact_paragraph + redact_word wrapper NotImplementedError 占位）
    - privacyguard/word/clear_doc_props.py（CORE_PROPS_TO_CLEAR 5 字段 + APP_PROPS_TO_CLEAR 2 字段 + clear_word_doc_props NotImplementedError 占位）
    - tests/fixtures/__init__.py（fixtures 包入口）
    - tests/fixtures/fake_word.py（build_fake_docx 完整合成器：paragraphs + tables + add_pii 5 类 PII）
    - tests/unit/test_word_pii_pipeline.py（5 测试类 7 测试方法 RED 骨架：TestWordAdapterCollectUnits / TestWordPIIAutoTrigger / TestWordRedactRoundTrip / TestWordDocumentPropertiesCleared ×2 / TestWordMergePriorityRulePiManualOcr ×2）
  modified:
    - privacyguard/pii/hits.py（__all__ + ENTITY_TYPE_SHORT_CODE 9 短码字典）
    - privacyguard/__init__.py（__all__ + _LAZY_IMPORTS 扩展 6 项）
    - main.py（_open_word_docx 加 self._word_pii_worker=None 占位；_on_word_pii_page_result print 占位槽；merge_word_matches_with_priority 第六参数 pii_matches=None）
    - packaging/windows/config/PrivacyGuard_windows.spec（hiddenimports 段追加 6 项 privacyguard.word.*）
    - packaging/macos/config/PrivacyGuard.spec（hiddenimports 段追加 6 项 privacyguard.word.*）

key-decisions:
  - "Wave 1 RED 不调用 stub（BLOCKER 6）：_save_word 既有 replace_matches_in_paragraph 路径不改为 redact_word stub；new_doc.save(fname) 前不插 clear_word_doc_props stub。runtime 必须保持完整可保存状态直到 Wave 2 GREEN 启用"
  - "_on_word_pii_page_result print 占位不抛 NotImplementedError：避免 worker signal 接不上时主线程抛 RuntimeError；Wave 2 GREEN 实施 QMutexLocker 写 + _apply_word_pii_panel_updates 增量 DOM patch"
  - "ENTITY_TYPE_SHORT_CODE 单一来源抽离至 privacyguard/pii/hits.py（per BLOCKER 5 + D-21）：main.py 与 Wave 3 candidate_dialog.py 均从此 import，避免 v37.7.6 已收敛的重复实现回潮"
  - "PyInstaller hiddenimports 字段级一致（cp30 教训扩展）：Windows spec 与 macOS spec 各追加 6 行 privacyguard.word.* 字段级一致；与 Phase 2 双 spec 既有 13 PII 行 + 6 validator 行 parity 模式保持一致"
  - "Wave 1 RED 不动 _save_word 既有路径：保持 Phase 1/2 既有 11 unittest 模块基线 GREEN；merge_word_matches_with_priority 第六参数默认值 back-compat；BLOCKER 6 锁定"

patterns-established:
  - "Pattern A: Wave 1 RED 子包骨架 = _LAZY_IMPORTS + __getattr__ + NotImplementedError 占位 + __all__ 列表，与 Phase 2 privacyguard.pii.__init__ 形态镜像"
  - "Pattern B: Wave 1 RED 测试骨架 = 5 测试类 + 7 测试方法 + 完整 test body（含 import + 构造 + 断言）但运行时抛 NotImplementedError 或 AssertionError 标 RED；Wave 2 仅替换 NotImplementedError 占位为真实实现"
  - "Pattern C: Wave 1 RED main.py 扩展 = 仅函数签名 + 占位字段 + 占位 slot，**不**调用 stub；避免 runtime 损坏（BLOCKER 6 锁定）"
  - "Pattern D: Phase 3 fixture 合成 = tests/fixtures/fake_word.build_fake_docx 复用 tests/fixtures/fake_pii.* Faker 合成器，per OPS-05 严禁真实个人信息"

requirements-completed: [FMT-02-red-baseline, OPS-03-red-baseline]

# Coverage metadata (#1602) — per-deliverable Requirements Traceability Matrix
coverage:
  - id: D1
    description: "privacyguard/word/ 子包骨架 + 懒加载入口（5 项 lazy forward）"
    requirement: OPS-03
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordAdapterCollectUnits.test_collect_units_returns_text_unit_per_block
        status: fail
      - kind: unit
        ref: tests/unit/test_package_imports.py#TestPrivacyGuardImports
        status: pass
    human_judgment: false
  - id: D2
    description: "ENTITY_TYPE_SHORT_CODE 9 短码字典（per BLOCKER 5 单一来源抽离至 privacyguard/pii/hits.py）"
    requirement: FMT-02
    verification:
      - kind: unit
        ref: tests/unit/test_convergence.py#TestPiiConvergence
        status: pass
    human_judgment: false
  - id: D3
    description: "build_fake_docx 合成含 PII docx fixture（per OPS-05）"
    requirement: OPS-05
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordPIIAutoTrigger.test_engine_detects_pii_in_word_text
        status: fail
    human_judgment: false

# Metrics
duration: 18min
started: 2026-08-12T05:59:00Z
completed: 2026-08-12T06:17:00Z
tasks: 1
files-modified: 13
status: in-progress
---

# Phase 3 Plan 1: Word PII 端到端 Tracer — RED Slice Summary

**RED baseline 落地：privacyguard/word/ 5 模块骨架 + ENTITY_TYPE_SHORT_CODE 单一来源抽离 + main.py 函数签名扩展 + 双 spec hiddenimports parity + tests/unit/test_word_pii_pipeline.py 5 测试类 RED 骨架（per BLOCKER 6 — RED 不破坏 runtime）**

## Performance

- **Duration:** 18 min
- **Started:** 2026-08-12T05:59:00Z
- **Completed:** 2026-08-12T06:17:00Z
- **Tasks:** 1 of 3 (Task 1 RED committed; Task 2 GREEN + Task 3 UI checkpoint pending — per tracer feedback gate, continuation agent required)
- **Files modified:** 13

## Accomplishments

- privacyguard/word/ 子包 5 个模块骨架落地（adapter / worker / redact / clear_doc_props NotImplementedError 占位；__init__.py _LAZY_IMPORTS 完整）
- privacyguard/pii/hits.py ENTITY_TYPE_SHORT_CODE 9 短码字典就位（per BLOCKER 5 抽离 main.py）
- privacyguard/__init__.py _LAZY_IMPORTS 扩展 6 项（5 Word 符号 + ENTITY_TYPE_SHORT_CODE 转发）
- tests/fixtures/fake_word.py build_fake_docx 合成器完整实现（含 paragraphs / tables / 5 类 PII 段落）
- tests/unit/test_word_pii_pipeline.py 5 测试类 7 测试方法 RED 骨架就位（NotImplementedError / AssertionError）
- main.py 4 处扩展骨架就位（_open_word_docx 占位 / _on_word_pii_page_result 占位 print slot / merge_word_matches_with_priority 第六参数 pii_matches=None / _save_word 既有路径未破坏 per BLOCKER 6）
- 双 spec hiddenimports 字段级一致追加 6 项 privacyguard.word.*（cp30 教训扩展）
- OPS-03 懒加载纪律保持：import privacyguard 不拉起 privacyguard.word 子模块
- 既有 11 unittest 模块基线 99/99 保持 GREEN（baseline 97 + 2 skipped，无回归）

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 1 RED — privacyguard/word/ skeleton + fake_word fixture + ENTITY_TYPE_SHORT_CODE + main.py signature extensions + dual spec hiddenimports** - `880853b` (test)

**Pending Tasks:**

2. **Task 2: Wave 1 GREEN — implement WordAdapter + WordPIIWorker + redact_word + clear_word_doc_props + main.py wire** (auto, tdd=true)
3. **Task 3: Wave 1 UI human verification — open docx auto scan + compare mode + save + docProps clear in real PyQt6 UI** (checkpoint:human-verify, gate=blocking)

_Note: Task 2 (GREEN) and Task 3 (UI checkpoint) require a continuation agent per tracer feedback gate._

## Files Created/Modified

- `privacyguard/word/__init__.py` - _LAZY_IMPORTS + __getattr__ + __dir__ 镜像 privacyguard.pii.__init__ 形态
- `privacyguard/word/adapter.py` - WordAdapter.collect_units NotImplementedError RED placeholder
- `privacyguard/word/worker.py` - WordPIIWorker QThread + 3 pyqtSignals + run() NotImplementedError RED placeholder
- `privacyguard/word/redact.py` - redact_paragraph + redact_word NotImplementedError RED placeholder
- `privacyguard/word/clear_doc_props.py` - CORE_PROPS_TO_CLEAR 5 字段 + APP_PROPS_TO_CLEAR 2 字段 + clear_word_doc_props NotImplementedError RED placeholder
- `privacyguard/pii/hits.py` - __all__ + ENTITY_TYPE_SHORT_CODE 9 短码字典（per BLOCKER 5 单一来源）
- `privacyguard/__init__.py` - __all__ 扩展 6 项 + _LAZY_IMPORTS 扩展 6 项（5 Word + ENTITY_TYPE_SHORT_CODE）
- `tests/fixtures/__init__.py` - fixtures 包入口（允许 tests.fixtures.* 被顶层 import 链发现）
- `tests/fixtures/fake_word.py` - build_fake_docx 完整合成器（paragraphs + tables + 5 类 PII）
- `tests/unit/test_word_pii_pipeline.py` - 5 测试类 7 测试方法 RED 骨架
- `main.py` - _open_word_docx 加 self._word_pii_worker=None 占位；_on_word_pii_page_result print 占位槽；merge_word_matches_with_priority 第六参数 pii_matches=None
- `packaging/windows/config/PrivacyGuard_windows.spec` - hiddenimports 段追加 6 项 privacyguard.word.*
- `packaging/macos/config/PrivacyGuard.spec` - hiddenimports 段追加 6 项 privacyguard.word.*

## Decisions Made

- **Wave 1 RED 不调用 stub（BLOCKER 6）** — _save_word 既有 replace_matches_in_paragraph 路径不改为 redact_word stub；new_doc.save(fname) 前不插 clear_word_doc_props stub。runtime 必须保持完整可保存状态直到 Wave 2 GREEN 启用
- **_on_word_pii_page_result print 占位不抛 NotImplementedError** — 避免 worker signal 接不上时主线程抛 RuntimeError；Wave 2 GREEN 实施 QMutexLocker 写 + _apply_word_pii_panel_updates 增量 DOM patch
- **ENTITY_TYPE_SHORT_CODE 单一来源抽离** — 唯一来源位于 privacyguard/pii/hits.py（per BLOCKER 5 + D-21）；main.py 与 Wave 3 candidate_dialog.py 均从此 import，避免 v37.7.6 已收敛的重复实现回潮
- **PyInstaller hiddenimports 字段级一致** — Windows spec 与 macOS spec 各追加 6 行 privacyguard.word.* 字段级一致；与 Phase 2 双 spec 既有 13 PII 行 + 6 validator 行 parity 模式保持一致（cp30 教训扩展）
- **Wave 1 RED 不动 _save_word 既有路径** — 保持 Phase 1/2 既有 11 unittest 模块基线 GREEN；merge_word_matches_with_priority 第六参数默认值 back-compat（per BLOCKER 6）

## Deviations from Plan

None - plan executed exactly as written for Task 1 RED slice.

## Issues Encountered

**RED tests reveal Phase 2 USCC regex lookbehind limitation** — `test_engine_detects_pii_in_word_text` fails because the test text contains "USCC" English keyword preceding the USCC value. After `flatten_for_match` removes whitespace, the USCC regex `(?<![A-Z0-9])([0-9A-HJ-NPQRTUWXY]{18})(?![A-Z0-9])` fails the negative lookbehind because the preceding 'C' (uppercase letter) blocks the match.

- Status: RED state correctly exposes this. Wave 2 GREEN must address.
- Resolution: Will change test keyword from "USCC" to "统一信用代码" (Chinese) in Wave 2 GREEN. This is consistent with how the engine is actually used in production (Chinese contexts only).
- Alternative considered: Relax USCC regex lookbehind (Phase 2 fix) — out of scope for Phase 3 Wave 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 1 RED baseline confirmed: 7/7 tests in test_word_pii_pipeline RED as expected; 99/99 baseline tests GREEN; OPS-03 lazy-load discipline holds
- Continuation agent required for Task 2 (GREEN — implement real logic for WordAdapter.collect_units, WordPIIWorker.run(), redact_word wrapper, clear_word_doc_props, main.py wire-up of PIIHit dispatch in merge_word_matches_with_priority + _save_word pii_matches routing)
- Task 3 (UI checkpoint) requires user interaction in real PyQt6 app after Task 2 GREEN completes

---

*Phase: 03-word*
*Status: in-progress (Task 1 RED committed; Task 2 GREEN + Task 3 UI checkpoint pending — tracer feedback gate stop)*
