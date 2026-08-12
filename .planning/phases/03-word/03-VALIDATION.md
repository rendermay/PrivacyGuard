---
phase: 3
slug: word
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
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
- **Before `/gsd-verify-work`:** Full suite must be green (基线 ≥ 79/79 + 新增测试全 pass)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | FMT-02 | T-03-WordRunBoundary | redact 后 para.text 不含原文 | integration | `tests.unit.test_word_pii_pipeline.TestWordRedactRoundTrip` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | FMT-02 | T-03-DocPropsLeak | clear_word_doc_props 后 5 core + 2 app 字段 == "" | integration | `tests.unit.test_word_pii_pipeline.TestWordDocumentPropertiesCleared` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | FMT-02 | T-03-PIIAutoTrigger | _open_word_docx 自动启动 WordPIIWorker；不点扫描按钮 | integration | `tests.unit.test_word_pii_pipeline.TestWordPIIAutoTrigger` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | FMT-02 | T-03-DataKeySync | mammoth 渲染后 DOM data-key 数 == word_data key 数 | integration | `tests.unit.test_word_pii_pipeline.TestWordDataKeySync` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | FMT-02 | T-03-PartialMask | 右栏 PII 高亮写 partial mask 字符串（110101\*\*\*\*\*\*\*\*1234） | integration | `tests.unit.test_word_pii_pipeline.TestWordPartialMaskInComparePane` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 2 | FMT-02 | T-03-MergePriority | merge_word_matches_with_priority: pii > manual > ocr | unit | `tests.unit.test_word_pii_pipeline.TestWordMergePriorityRulePiManualOcr` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 3 | UX-01 | T-03-CandidateDialog | WordCandidateDialog 显示 PII 命中 + 逐条 checkbox | unit | `tests.unit.test_word_pii_pipeline.TestWordCandidateDialog` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 3 | UX-02 | T-03-CandidateFilter | > 50 条分页 + entity_type 筛选 + 来源筛选 | unit | `tests.unit.test_word_pii_pipeline.TestWordCandidateDialogPagination` | ❌ W0 | ⬜ pending |
| 03-03-03 | 03 | 3 | OPS-07 | — | 79/79 基线 + 新增测试全 pass | integration | 完整 full suite command | ❌ W0 | ⬜ pending |
| 03-03-04 | 03 | 3 | OPS-04 | T-03-PyInstallerHiddenimports | `privacyguard.word.*` 在 Windows + macOS hiddenimports | smoke | `grep privacyguard.word packaging/{windows,macos}/config/*.spec` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Phase 3 全部 13 个 Wave 0 任务需在 Wave 1 前就位，否则规划阶段定义的「真实测试覆盖」无法运行。

- [ ] `tests/fixtures/fake_word.py` NEW — `build_fake_docx()` 合成含 PII 的 docx（D-26；Faker 合成数据）
- [ ] `privacyguard/word/__init__.py` NEW — 懒加载 `_LAZY_IMPORTS`（D-06；OPS-03）
- [ ] `privacyguard/word/adapter.py` NEW — `WordAdapter.collect_units`（D-04 / D-17）
- [ ] `privacyguard/word/worker.py` NEW — `WordPIIWorker` QThread（D-09）
- [ ] `privacyguard/word/redact.py` NEW — `redact_word` wrapper（D-23）
- [ ] `privacyguard/word/clear_doc_props.py` NEW — `clear_word_doc_props`（D-24）
- [ ] `privacyguard/word/candidate_dialog.py` NEW — `WordCandidateDialog`（D-25 / UX-01 / UX-02）
- [ ] `main.py` MODIFY — `_open_word_docx` 自动启动 `WordPIIWorker` + 新增 `_on_word_pii_page_result` 槽 + `merge_word_matches_with_priority` 第四参数 + `_save_word` 扩 pii_matches（D-09 / D-18 / D-19 / D-23）
- [ ] `privacyguard/__init__.py` MODIFY — `_LAZY_IMPORTS` 追加 Word 符号导出（D-06）
- [ ] `tests/unit/test_word_pii_pipeline.py` NEW — 8 个测试类（D-13）
- [ ] `packaging/windows/config/PrivacyGuard_windows.spec` MODIFY — `hiddenimports` 段追加 `privacyguard.word.*`（cp30 教训）
- [ ] `packaging/macos/config/PrivacyGuard.spec` MODIFY — 同上 parity
- [ ] `tests/fixtures/__init__.py` NEW — 让 `fake_word` 被 `tests/` 顶层 import 链发现

*If none: "Existing infrastructure covers all phase requirements." — 不适用；Wave 0 全部 ❌ 待补*

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
- [ ] Wave 0 covers all MISSING references (13 tasks listed above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (set by `validate-phase` §6 after Wave 0 complete)
