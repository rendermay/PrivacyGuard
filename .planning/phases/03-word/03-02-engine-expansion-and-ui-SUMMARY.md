---
phase: 03-word
plan: 02
subsystem: pii
tags: [cp27-incremental-patch, pii-highlight, partial-mask, html-escape, qwebengineview, runjavascript, single-source-short-code, lazy-load]

# Dependency graph
requires:
  - phase: 03-word-01
    provides: privacyguard/word/ 5 模块完整实现 + ENTITY_TYPE_SHORT_CODE 9 短码字典（per BLOCKER 5 单一来源至 privacyguard/pii/hits.py）+ WordPIIWorker 自动启动 + _on_word_pii_page_result 占位 stub + _apply_word_pii_panel_updates 占位 stub + test_word_pii_pipeline.py 7 GREEN 测试方法
provides:
  - main.py MainWindow 类新增 4 项：_apply_word_pii_panel_updates 真实 body（cp27 局部 patch 契约）+ _build_pii_block_fragment 构造左栏原文 PII 高亮 HTML 片段 + _build_pii_mask_block_fragment 构造右栏 partial mask HTML 片段 + 改进 _on_word_pii_page_result 真实 body（防御性反序列化 dict → PIIHit + QMutexLocker 写 word_data[key]["pii"] + 锁释放后触发 _apply_word_pii_panel_updates）
  - main.py 模块顶部新增 2 个 import：from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE（per BLOCKER 5 + D-21 单一来源锁）+ from html import escape as html_escape
  - main.py _build_word_original_panel_updates + _build_word_replaced_panel_updates 把 pii_matches 通道纳入 merge_word_matches_with_priority 入参（per D-19 priority 与 _save_word 一致）
  - privacyguard/word/candidate_dialog.py NEW — WordCandidateDialog QDialog 占位骨架 + ENTITY_TYPE_LABEL 9 类实体中文标签字典（Wave 3 完整 UX-01 / UX-02 UI 行为待实施）
  - tests/unit/test_word_pii_pipeline.py 新增 TestWordPIIPanelHighlights 测试类（4 个测试方法：test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml / test_build_pii_block_fragment_contains_short_code_badge / test_build_pii_mask_block_fragment_contains_mask_string_not_original / test_entity_type_short_code_covers_all_9_locked_types）— 4/4 GREEN
  - cp27 增量 DOM patch 契约保持：web_view.page().runJavaScript("updateBlock(...)") 局部 patch；**禁止**触发整页 web_view.setHtml()（test 反向断言锁定）
affects:
  - 03-03（依赖 candidate_dialog skeleton 完整 UI 行为 + _apply_word_pii_panel_updates 增量 patch 形态）
  - 03-04（依赖 test_word_pii_pipeline.py 11/11 GREEN 状态作为 baseline 拆分依据）

# Actuals (#2632) — pairs with plan's estimate (70000 tokens / 3 tasks / medium confidence)
# Same scale: chars/4 over realized diff, not harness token count.
actuals:
  tokens: 8200    # chars/4 over files actually changed (RED: 137 → 0 deletions; GREEN: 200 insertions + 16 deletions + candidate_dialog.py 89; summary ~ 1000; total diff chars /4 ≈ 8200)
  tasks: 2        # 2 of 3 tasks completed (Task 1 RED + Task 2 GREEN committed; Task 3 UI checkpoint pending user verification)
  commits: 2      # 2 commits: test(03-02) RED + feat(03-02) GREEN

# Tech tracking
tech-stack:
  added: []  # Phase 3 零新增依赖（沿用 PyQt6 + python-docx + mammoth 既有）
  patterns:
    - "TDD 双 commit 节奏：test(03-02) RED → feat(03-02) GREEN（per BLOCKER 6 RED 不破坏 runtime，GREEN 落地真实业务）"
    - "cp27 增量 DOM patch 真实 body：web_view.page().runJavaScript(build_word_panel_update_script(updates))（**禁止**SetHtml）—— TestWordPIIPanelHighlights 反向断言守住契约"
    - "_build_pii_block_fragment 防御性 length check：hit.page_offset / page_length 必须 int 且 offset+length <= len(text)；失败 continue 跳过"
    - "_build_pii_mask_block_fragment 同样 length check + html_escape 防 XSS（T-03-HTMLInjection 缓解）"
    - "_on_word_pii_page_result 防御性反序列化：lazy import PIIHit + try/except (TypeError, ValueError) 跳过 invalid hit dict；QMutexLocker 写 word_data[key]['pii']；锁释放后再触发 _apply_word_pii_panel_updates（避免锁内 UI 阻塞）"
    - "view.isHidden() try/except 防御：Mock(spec=QWebEngineView) 测试场景 + 真实 isHidden() 异常都容错；hidden=True 时跳过 runJavaScript"
    - "merge_word_matches_with_priority pii_matches 第六参数 = data.get('pii', [])（per D-19 priority 顺序与 _save_word 一致）"
    - "candidate_dialog.py ENTITY_TYPE_LABEL 字典：9 类实体中文标签（per 03-UI-SPEC §Copywriting 一致）"
    - "ENTITY_TYPE_SHORT_CODE 单点引入 main.py：从 privacyguard.pii.hits 直 import（per BLOCKER 5 锁），test_convergence AST 断言 main.py 不内联 9 短码字面量"

key-files:
  created:
    - privacyguard/word/candidate_dialog.py（WordCandidateDialog QDialog 占位骨架 + ENTITY_TYPE_LABEL 9 类实体中文标签字典）
  modified:
    - main.py（模块顶部新增 2 个 import + MainWindow 类新增 4 个方法 + 2 处 _build_word_*_panel_updates pii_matches 纳入）
    - tests/unit/test_word_pii_pipeline.py（新增 TestWordPIIPanelHighlights 测试类 4 个方法 + types.MethodType / unittest.mock.Mock / PyQt6.QtWebEngineWidgets 顶部 import + _build_pii_panel_stub + _build_id_card_hit 辅助函数）

key-decisions:
  - "Wave 2 RED 不调用 stub（per BLOCKER 6 节奏）—— _save_word 与 _on_word_pii_page_result 既有接线 Wave 1 已就位；Wave 2 GREEN 仅激活 _apply_word_pii_panel_updates + 两个 fragment helper"
  - "_apply_word_pii_panel_updates 真实 body 走 cp27：view.page().runJavaScript(build_word_panel_update_script(updates))；try/except 容错（与现有 _apply_word_panel_updates 一致）"
  - "_build_pii_block_fragment title 使用 entity_type + 中文标签（per Visuals §PII Highlight 锁定：fragment 不含 mask 字符串）—— 不写入 mask_sample 到 title 属性（test 严格契约）"
  - "_build_pii_mask_block_fragment title = '已替换为：{mask_strategy}'，mark 内部仅 mask 字符串（per Visuals §PII Partial-Mask 锁定）"
  - "_on_word_pii_page_result 防御性反序列化：既兼容 dict 也兼容 PIIHit 实例；test_/真实 worker 两条路径都不抛异常"
  - "_build_word_*_panel_updates 把 pii_matches 通道纳入 merge_word_matches_with_priority 入参（第 6 参数）—— 与 _save_word 与 Wave 1 测试一致（D-19 priority 顺序）"
  - "candidate_dialog.py 占位骨架：只 setWindowTitle + resize + 占位 label；PAGE_SIZE = 50；ENTINITY_TYPE_LABEL 9 类中文标签就位（Wave 3 实施实体类型 / 来源筛选 + 4 CTAs）"
  - "PyQt6.QtWidgets 在 candidate_dialog.py 模块级 import 允许（PyQt6 是常驻依赖，与 Qt 框架生命周期绑定）—— 不违反 OPS-03 懒加载约束"

patterns-established:
  - "Pattern G: Phase 3 Panel UI 局部 patch 测试 = Mock(spec=QWebEngineView) + MethodType(MainWindow.method, stub) —— Stub 不继承 MainWindow，但通过 MethodType 绑定 MainWindow 方法绕过 inherit 依赖"
  - "Pattern H: Phase 3 HTML fragment 防御性 length check = if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or offset + length > text_len or length <= 0: continue —— 避免越界 / 类型异常"
  - "Pattern I: Phase 3 反序列化兼容 = 输入既可能是 dict 也可能是 PIIHit 实例 —— 防御性 try/except (TypeError, ValueError) 跳过 invalid；保证 worker emit dict + 测试直接传 PIIHit 双路径都不抛"

requirements-completed: [FMT-02, UX-01]

# Coverage metadata (#1602) — per-deliverable Requirements Traceability Matrix
coverage:
  - id: D1
    description: "_apply_word_pii_panel_updates 走 cp27 局部 patch 契约（web_view.page().runJavaScript 被调 + web_view.setHtml 未被调）"
    requirement: FMT-02
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordPIIPanelHighlights.test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml
        status: pass
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordPIIPanelHighlights.test_build_pii_block_fragment_contains_short_code_badge
        status: pass
    human_judgment: false
  - id: D2
    description: "_build_pii_block_fragment 左栏原文 + 短码徽章 HTML 片段（D-21 + BLOCKER 5 单一来源）"
    requirement: FMT-02
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordPIIPanelHighlights.test_build_pii_block_fragment_contains_short_code_badge
        status: pass
    human_judgment: false
  - id: D3
    description: "_build_pii_mask_block_fragment 右栏 partial mask HTML 片段（Visuals §PII Partial-Mask 锁定）"
    requirement: FMT-02
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordPIIPanelHighlights.test_build_pii_mask_block_fragment_contains_mask_string_not_original
        status: pass
    human_judgment: false
  - id: D4
    description: "ENTITY_TYPE_SHORT_CODE 9 短码字典覆盖 9 类 entity + ASCII uppercase；来源唯一 privacyguard.pii.hits（per BLOCKER 5 + D-21）"
    requirement: FMT-02
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordPIIPanelHighlights.test_entity_type_short_code_covers_all_9_locked_types
        status: pass
      - kind: unit
        ref: tests/unit/test_convergence.py (AST 断言 main.py 不内联 9 短码字典)
        status: pass
    human_judgment: false
  - id: D5
    description: "Real PyQt6 UI 验证 — 打开 docx 后左栏红框 PII 高亮 + 短码徽章 + tooltip；右栏绿调 partial mask 视觉"
    requirement: UX-01
    verification: []
    human_judgment: true
    rationale: "UI 视觉验证涉及 PyQt6 主线程 / QWebEngineView 渲染 / tooltip 颜色 / 实际双栏滚动同步 —— 必须人工在真实 PyQt6 应用中验证 9 步骤 UI 流程"

# Metrics
duration: 8min
started: 2026-08-12T06:34:50Z
completed: 2026-08-12T06:43:00Z
tasks: 2
files-modified: 3
status: in-progress
---

# Phase 3 Plan 2: engine expansion + UI panel updates — Summary

**cp27 增量 DOM patch 契约落到 PII Panel：左栏 `<mark class="pii-highlight">` + 短码徽章 + 右栏 `<mark class="pii-mask">` partial mask；WordCandidateDialog 占位骨架就位；TestWordPIIPanelHighlights 4/4 GREEN（Task 3 UI 人工验证 pending）**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-12T06:34:50Z
- **Completed:** 2026-08-12T06:43:00Z
- **Tasks:** 2 of 3 (Task 1 RED + Task 2 GREEN committed; Task 3 UI checkpoint pending user verification)
- **Files modified:** 3 (main.py + tests/unit/test_word_pii_pipeline.py + privacyguard/word/candidate_dialog.py)

## Accomplishments

- main.py 新增 4 个方法 + 2 个 import 落地：`_apply_word_pii_panel_updates` 真实 body（cp27 局部 patch 契约）+ `_build_pii_block_fragment` 左栏原文 + 短码徽章 + `_build_pii_mask_block_fragment` 右栏 partial mask + 改进 `_on_word_pii_page_result` 真实 body（防御性反序列化 + QMutexLocker 写 + 锁释放触发 patch）
- main.py 模块顶部新增 `from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE` 单一来源 import（per BLOCKER 5 + D-21 锁；test_convergence AST 断言 main.py 不内联 9 短码字典 NONE correct）
- main.py `_build_word_original_panel_updates` + `_build_word_replaced_panel_updates` 把 `pii_matches` 通道纳入 `merge_word_matches_with_priority` 入参（per D-19 priority 顺序与 `_save_word` 一致）
- privacyguard/word/candidate_dialog.py NEW：WordCandidateDialog QDialog 占位骨架 + `ENTITY_TYPE_LABEL` 9 类实体中文标签字典（Wave 3 完整 UX-01 / UX-02 UI 行为待实施）
- TestWordPIIPanelHighlights 4 个测试方法全部 GREEN：cp27 runJavaScript 契约 + 短码徽章 HTML 形态 + 左栏原文 + 右栏 partial mask + 9 短码字典
- OPS-03 懒加载纪律保持：import privacyguard 不拉起 candidate_dialog 子模块（PyQt6.QtWidgets 在 candidate_dialog 模块级 import 允许，因为 PyQt6 是常驻依赖与 Qt 框架生命周期绑定）
- 既有 11 unittest 模块基线 99/99 保持 GREEN（2 skipped 沿用 Wave 1，无回归）

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — TestWordPIIPanelHighlights 4 测试方法 cp27 增量 patch + 短码徽章 + partial mask 契约** - `ba94cbb` (test)
2. **Task 2: GREEN — _apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + candidate_dialog 骨架 + main.py 改进** - `41ad3e8` (feat)

**Pending Tasks:**

3. **Task 3: Wave 2 UI human verification — 打开 docx 真实 PyQt6 应用中左栏红框 PII 高亮 + 短码徽章 + tooltip；右栏绿调 partial mask + 仅 mask 字符串 + tooltip；cp27 局部 patch 不破坏滚动 / 缩放** (checkpoint:human-verify, gate=blocking)

_Note: Task 3 requires user verification in real PyQt6 app — see Checkpoint Details below._

## Files Created/Modified

- `main.py` - 模块顶部新增 2 个 import（ENTITY_TYPE_SHORT_CODE + html_escape）；MainWindow 类新增 4 个方法（_apply_word_pii_panel_updates + _build_pii_block_fragment + _build_pii_mask_block_fragment + 改进 _on_word_pii_page_result）；_build_word_original_panel_updates + _build_word_replaced_panel_updates 把 pii_matches 通道纳入 merge_word_matches_with_priority
- `privacyguard/word/candidate_dialog.py` - NEW：WordCandidateDialog QDialog 占位骨架 + ENTITY_TYPE_LABEL 9 类实体中文标签字典（Wave 3 完整 UI 行为待实施）
- `tests/unit/test_word_pii_pipeline.py` - 新增 TestWordPIIPanelHighlights 测试类（4 个测试方法 + _build_pii_panel_stub + _build_id_card_hit 辅助函数 + types.MethodType / unittest.mock.Mock / PyQt6.QtWebEngineWidgets 顶部 import）

## Decisions Made

- **cp27 增量 patch 真实 body** = `web_view.page().runJavaScript(build_word_panel_update_script(updates))`；try/except 容错（与现有 `_apply_word_panel_updates` 一致）；view.isHidden() 防御（Mock + 真实 isHidden 异常都容错）
- **_build_pii_block_fragment title 不含 mask_sample** = 使用 entity_type + 中文标签（per test 严格契约：fragment 不含 mask 字符串）；遵守 BLOCKER 5 + D-21 单一来源
- **_build_pii_mask_block_fragment title = '已替换为：{mask_strategy}'** + mark 内部仅 mask 字符串（per Visuals §PII Partial-Mask 锁定）
- **_on_word_pii_page_result 防御性反序列化** = 输入既可能是 dict（worker emit）也可能是 PIIHit 实例（test 直接传）；try/except (TypeError, ValueError) 跳过 invalid
- **QMutexLocker 写 word_data[key]['pii'] + 锁释放后再触发 _apply_word_pii_panel_updates** = 避免锁内 UI 阻塞（per D-09 / D-18 + cp30 教训扩展）
- **_build_word_*_panel_updates 把 pii_matches 通道纳入 merge_word_matches_with_priority 入参** = 第 6 参数 `data.get('pii', [])`；与 _save_word 与 Wave 1 测试一致（D-19 priority 顺序）
- **candidate_dialog.py 占位骨架** = 只 setWindowTitle + resize + 占位 label；PAGE_SIZE = 50；ENTITY_TYPE_LABEL 9 类中文标签就位（Wave 3 实体类型 / 来源筛选 + 4 CTAs）
- **PyQt6.QtWidgets 在 candidate_dialog.py 模块级 import 允许** = PyQt6 是常驻依赖，与 Qt 框架生命周期绑定；不违反 OPS-03 懒加载约束

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _build_pii_block_fragment title 改为 entity_type + 中文标签（不包含 mask_sample）**
- **Found during:** Task 2 GREEN verification
- **Issue:** Plan 中 `_build_pii_block_fragment` title_text = `f'{hit.entity_type} · {mask_sample}'` —— 但 test_build_pii_block_fragment_contains_short_code_badge 严格断言 `mask_for_entity('CN_ID_CARD', '53010219200508011X') not in fragment`（"**左栏不含 mask 字符串** —— Visuals §PII Highlight 锁定"）。mask_sample 写入 title 会让 mask 字符串在 fragment 中出现，触发 assertNotIn 失败
- **Fix:** title_text = `f'{entity_type} · {ENTITY_TYPE_LABEL[entity_type]}'`，使用候选审阅对话框的 9 类中文标签字典（per 03-UI-SPEC §Copywriting 一致 + per test 严格契约）
- **Files modified:** main.py
- **Verification:** test_build_pii_block_fragment_contains_short_code_badge GREEN（fragment 不含 mask 字符串）
- **Committed in:** 41ad3e8 (Task 2 GREEN commit)

### Auto-fixed Plan Refinements

**2. [Rule 2 - Missing Critical] _build_pii_mask_block_fragment 同样 length check 防御**
- **Found during:** Task 2 GREEN verification
- **Issue:** Plan 中 `_build_pii_mask_block_fragment` 已包含 length check 描述，但 `_build_pii_block_fragment` 描述里同样需要 length check（保持两个 helper 行为一致）
- **Fix:** `_build_pii_block_fragment` 与 `_build_pii_mask_block_fragment` 共享 length check 防御：`if not isinstance(offset, int) or not isinstance(length, int) or offset < 0 or offset + length > text_len or length <= 0: continue`
- **Files modified:** main.py
- **Verification:** 4/4 TestWordPIIPanelHighlights GREEN
- **Committed in:** 41ad3e8 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both auto-fixes essential for GREEN correctness. No scope creep — title 调整是 test 契约驱动；length check 共享是 helper 行为一致性。

## Issues Encountered

- Plan 中 `_build_pii_block_fragment` title 包含 mask_sample 与 test 严格契约（左栏 fragment 不含 mask 字符串）冲突 —— 已在 Deviation #1 处理（title 改为 entity_type + 中文标签）
- PrivacyGuard 是 PyQt6 桌面应用 —— Task 3 UI checkpoint 必须人工在真实 PyQt6 应用中验证（非自动化）

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Tasks 1 + 2 完成（RED baseline + GREEN 实施）
- Task 3 等待用户在真实 PyQt6 应用中人工验证（9 步骤 UI 测试 — 见 Checkpoint Details）
- Task 3 通过后，Wave 2 计划完成；可进入 Phase 3 Plan 03（candidate_dialog 完整 UI 行为 + 打包）

---

## Checkpoint Details — Task 3 UI Human Verification

**Type:** human-verify
**Gate:** blocking
**Status:** awaiting user verification

**What built:**
- main.py 4 个新增方法 + 2 个 import 落地（_apply_word_pii_panel_updates / _build_pii_block_fragment / _build_pii_mask_block_fragment / 改进 _on_word_pii_page_result + ENTITY_TYPE_SHORT_CODE + html_escape）
- _build_word_original_panel_updates + _build_word_replaced_panel_updates 把 pii_matches 通道纳入合并路径
- privacyguard/word/candidate_dialog.py WordCandidateDialog 占位骨架 + ENTITY_TYPE_LABEL 9 类中文标签字典
- TestWordPIIPanelHighlights 4 个测试方法 GREEN

**How to verify:**
1. **启动应用**: `cd /mnt/g/Project/PrivacyGuard && python3 main.py`
2. **构造含 PII 的 docx**: `python3 -c "from tests.fixtures.fake_word import build_fake_docx; p = build_fake_docx(); print(p)"`
3. **主菜单 → Open → 选择合成的 docx**
4. **等待 worker 完成**（status chip 显示 `已识别 N 项敏感内容`）
5. **切换到对比模式**
6. **观察左栏（原文预览）**：PII 命中位置出现红色半透明填充矩形（`<mark class="pii-highlight">` 背景 `#D64545@alpha 0.18` / `#FF6B6B@alpha 0.22`）；PII 命中位置左侧有红色短码徽章（`ID` / `PHONE` / `BANK` / `EMAIL` / `USCC` / `TAX` / `TAX15` / `VAT` / `ACCT`，per BLOCKER 5 单一来源 from privacyguard.pii.hits.py）；鼠标悬停 PII 命中位置 → 浏览器原生 tooltip 显示 `CN_ID_CARD · 身份证号`
7. **观察右栏（替换预览）**：PII 命中位置出现绿色半透明填充矩形（`<mark class="pii-mask">` 背景 `#0FA968@alpha 0.12` / `#34D399@alpha 0.18`）；矩形内**只**显示 partial mask 字符串（如 `530102********011X`），**不**显示原文；鼠标悬停 → tooltip 显示 `已替换为：530102********011X`
8. **滚动 / 缩放 / 切换段落**：左右双栏**不**触发整页重渲染（cp27 契约锁定）；滚动位置 / 选中状态 / 缩放保持
9. **重新打开**：关闭 app；重新启动；再次打开同一 docx；PII 高亮与 mask 显示与首次一致

**通过条件**：步骤 6/7 双栏高亮 + tooltip 正确；步骤 8 cp27 增量 patch 不破坏滚动；步骤 9 重新打开一致。

**不通过条件**（任一即触发 Wave 3 修复）：左栏未显示红色高亮或短码徽章缺失；右栏显示原文或未显示绿色 partial mask；滚动 / 缩放触发整页重渲染（cp27 契约破坏）；重新打开 docx 后高亮丢失。

**Resume signal:** Type "approved" to mark Task 3 complete, or describe the failing step + visual evidence.

---

*Phase: 03-word*
*Status: in-progress (Task 1 RED + Task 2 GREEN committed; Task 3 UI checkpoint pending user verification)*
