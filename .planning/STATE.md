---
gsd_state_version: 1.0
milestone: v37.7.6
milestone_name: milestone
status: shipped
stopped_at: Phase 3 UI-SPEC approved
last_updated: "2026-08-12T04:08:45.842Z"
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 11
  completed_plans: 7
current_phase_name: PDF 增加银行卡/邮箱/财税实体识别与部分掩码
---

# PrivacyGuard v38.x — Project State

**Project:** PrivacyGuard 脱敏卫士
**Milestone:** v38.x — Pure-local Chinese PII Recognition + Excel/Image Support
**Updated:** 2026-08-10

---

## Project Reference

**Core value**: 打开文档就自动列出所有敏感项，用户不用再手输关键词。如果自动识别不可靠，这一轮就等于没做。

**Active milestone**: v38.x — embed pure-local Chinese PII auto-recognition engine and extend format support to Excel + standalone images.

**Constraints (must not violate)**:

- 零网络依赖；识别全程在本地完成
- 新增共享逻辑一律放进 `privacyguard/`，不得在 `main.py` 再写一份实现（v37.7.6 收敛原则）
- OCR 与识别引擎保持懒加载，不得在包导入期初始化
- 任何新增模块必须同步验证 Windows / macOS PyInstaller 打包
- 79/79 测试基线保持通过

---

## Current Position

**Phase**: 1 (UI-SPEC approved; awaiting /gsd-plan-phase)
**Plan**: TBD
**Status**: Phase 1 CONTEXT gathered + UI-SPEC approved → ready for `/gsd-plan-phase 1`
**Next action**: `/gsd-plan-phase 1` produces detailed PLAN.md files for Phase 1

**Progress**: 0% — 0 phases complete out of 8 planned. UI-SPEC 1/1 approved.

---

## Performance Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Phases planned | 8 | 8 |
| Phases complete | 0 | 8 |
| Requirements mapped | 50 | 50 |
| Requirements coverage | 100% | 100% |
| Test baseline (v37.7.6) | 79/79 pass | 79/79+ pass |
| Build artifacts | Windows + macOS | Windows + macOS (must include PII modules + dictionaries) |
| Active config path | `SimpleConfig` (`main.py`) | unchanged |
| Lazy-loading compliance | enforced (cp30) | unchanged |

---
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01-pdf P01-02 | 45 | 3 tasks | 6 files |

## Accumulated Context

### Decisions

- **识别引擎走纯本地规则路线**（regex + 校验位 + 词典 + 上下文锚点）— 不接云端 LLM（破坏"零网络"底线）；不引入 Presidio / spaCy（bundle weight 过大）；自研 `<50 KB Python` 引擎。
- **每个格式走"垂直 MVP 切片"**（PDF → Word → Excel → Image）— 而非横向"先做全部引擎再做全部格式"。这样能在第一个 phase 就端到端验证 PIIHit → 真脱敏的完整链路。
- **SAFE-01 / SAFE-02 在首个产生脱敏产物的切片（Phase 1）就必须就位** — 任何"假脱敏"都是灾难性失败。
- **Detection is format-independent**：一份 `PIIHit` 数据结构贯穿四格式；引擎无 Qt、无线程、无格式 I/O；apply 阶段才在 `DocumentAdapter` 边界做格式分支。
- **新数据存进现有 dict 的新 key**（`page_data[page]["pii"]` / `word_data[key]["pii"]`），不另起数据结构 — 守住 v37.7.6 收敛原则。
- **Excel 走 openpyxl**（唯一能 round-trip 保留公式/样式的库）；图片复用 RapidOCR + Pillow；不引入 xlrd（除非承诺 `.xls` 支持）。
- [Phase ?]: B2: detect(unit, page=None) — page 提供时走真实 page.search_for(original_substring)；fallback 按分隔符拆 chunk union
- [Phase ?]: W-A: 不可定位 hit 记录到 unresolved_hits + error_log（不静默丢弃）
- [Phase ?]: I1: bare 15-digit 无 context anchor → MEDIUM（避免订单号误识别）
- [Phase ?]: page_rect 根因修复：engine 内部通过 page 参数取真实坐标，调用方不再需要各自 page.search_for workaround（test_pdf_pii_redaction.py 保留 safety net）

### Architectural Facts

- `main.py` (~12.6k LOC) 仍是活跃运行时入口；`privacyguard/` 子包已承载部分抽离的共享模块。
- 版本号唯一来源：`version.txt`（当前 `37.7.6`）。任何版本号改动必须同步：`version.txt` → `main.py` → `privacyguard/__version__` → `packaging/` → `CHANGELOG.md`。
- `SimpleConfig`（`main.py`）是当前生效配置；`privacyguard/utils/config.py::ConfigManager` **不是运行时路径**。
- 已有基线能力：PDF（文字/图片/混合 + 手动矩形）、Word（智能扫描 + 手动 + 双栏对比预览 + 批量替换）、高级设置面板、Windows/macOS PyInstaller 打包。
- 已知回归历史：`cp30` 修复过 `privacyguard.utils.security` 模块导入失败（PyInstaller）；新增模块时需同步验证 `datas` 与 `hiddenimports`。

### Open Questions / Research Flags

- **手机号段号白名单** — 需要 MIIT 最新公告交叉验证（166/198/199、190/192/196/197、虚拟运营商段、14X 物联网排除）→ Phase 1 实施前再确认
- **行政区划词典打包策略** — 全集 ~70 万条 vs 省市区分集 ~3500 条；Phase 6 才需要全集
- **全电发票 20 位号码格式** — 新版格式正则确认（Phase 2 末）
- **词典文件 LICENSE 审查** — `Chinese-Names-Corpus` / `sysloser/adcode` / `HALOSTAR/chinese_surnames` 兼容性确认（Phase 1 前）
- **`confidence.py` 是否暴露原始 0.0-1.0 score** — UX 决策，Phase 7 定
- **`RedactionReport` 是否捆绑原文件 SHA-256** — 合规价值 vs IO 成本，Phase 8 定
- **Excel 列头→实体类型映射 schema** — Phase 4 实施前定型

### Active Blockers

None — awaiting user approval of drafted roadmap to begin Phase 1 planning.

---

## Phase Tracking

### Phase 1: PDF 自动识别身份证号与手机号并真脱敏

- **Status**: UI-SPEC approved (2026-08-10); planning not started
- **Plans**: 0 / TBD
- **UI-SPEC**: approved by gsd-ui-checker (5/6 PASS, 1 non-blocking FLAG on Spacing); ui-consideration probe: 20 covered / 2 backstop / 0 unresolved. Path: `.planning/phases/01-pdf/01-UI-SPEC.md`
- **Key deliverables**: `privacyguard/pii/` types + Engine + 校验位 + PdfAdapter；PyMuPDF `add_redact_annot + apply_redactions` 真删除；reverse-test 断言
- **First vertical slice** — proves the whole chain works end-to-end

### Phase 2: PDF 增加银行卡/邮箱/财税实体识别与部分掩码

- **Status**: Not started
- **Plans**: 0 / TBD
- **Depends on**: Phase 1

### Phase 3: Word 文档接入识别引擎

- **Status**: Not started
- **Plans**: 0 / TBD
- **Depends on**: Phase 1

### Phase 4: Excel 工作簿支持

- **Status**: Not started
- **Plans**: 0 / TBD
- **Depends on**: Phase 1

### Phase 5: 独立图片文件支持

- **Status**: Not started
- **Plans**: 0 / TBD
- **Depends on**: Phase 1

### Phase 6: 上下文型实体识别

- **Status**: Not started
- **Plans**: 0 / TBD
- **Depends on**: Phase 1

### Phase 7: 候选审阅 UI

- **Status**: Not started
- **Plans**: 0 / TBD
- **Depends on**: Phase 1, Phase 3

### Phase 8: 识别规则编辑 + 审计 + 打包 + 基线

- **Status**: Not started
- **Plans**: 0 / TBD
- **Depends on**: Phase 1

---

## Ship Status

**PR:** https://github.com/lizilaywer/PrivacyGuard/pull/3
**Branch:** `gsd/phase-1-pdf` (fork: rendermay/PrivacyGuard) → `main`
**Commits on main since Plan 01-01 dispatch:** 17 commits (Plans 01-01/01-02/01-03 + ship-note)
**Verification:** passed (16/16 must-haves)
**Date:** 2026-08-11

## Session Continuity

**Last session:** 2026-08-12T03:15:49.401Z
**Stopped at:** Phase 3 UI-SPEC approved
**Resume file:** .planning/phases/03-word/03-UI-SPEC.md

**Last session**: 2026-08-10 — Phase 1 CONTEXT gathered, UI-SPEC approved.
**Last action**: Wrote `.planning/phases/01-pdf/01-UI-SPEC.md` (5/6 PASS via gsd-ui-checker; ui-consideration probe resolved 20/20 state categories with 0 unresolved).
**Resume instructions**: `/gsd-plan-phase 1` to produce detailed PLAN.md files for Phase 1.

---

*State file — refresh after every phase transition.*
