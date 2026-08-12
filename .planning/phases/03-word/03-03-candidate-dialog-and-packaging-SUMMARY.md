---
phase: 03-word
plan: 03
subsystem: pii
tags: [qdialog, qlistwidget, qcheckbox, qcombobox, pyqtsignal, pagination, hit-identity-tuple, cross-page-persistence, ux-01-cancel-semantics, pyinstaller-hiddenimports-parity]

# Dependency graph
requires:
  - phase: 03-word-02
    provides: privacyguard/word/candidate_dialog.py 占位骨架 + ENTITY_TYPE_LABEL 9 类中文标签字典 + MainWindow._apply_word_pii_panel_updates cp27 局部 patch 契约
  - phase: 03-word-01
    provides: privacyguard/word/ 子包 5 模块完整实现 + ENTITY_TYPE_SHORT_CODE 单一来源 + packaging/{windows,macos}/config/*.spec 字段级一致基线 + test_word_pii_pipeline.py 11 测试方法 GREEN
provides:
  - privacyguard/word/candidate_dialog.py MODIFY — WordCandidateDialog 完整 UI 行为（PAGE_SIZE = 50 + 9 entity 中文标签 + 实体类型 / 来源双维度筛选 + 50 条分页 + 4 CTAs + 跨翻页 _selection 持久化 per BLOCKER 4 + hit identity 四元组 + 行 label normalized[:30] + '...' 截断 + confirmed = pyqtSignal(list) payload 契约）
  - main.py MODIFY — MainWindow 新增 self.confirmed_hits + self.candidate_only_pii 持久状态（per BLOCKER 3 UX-01 取消语义）；_on_word_candidate_dialog_accept 写回 word_data[key]['confirmed'] + 触发 cp27 patch；_open_word_candidate_dialog 菜单触发入口；_save_word guard 仅写 confirmed hits 到 pii 路径；_open_word_docx 重置 confirmed_hits/candidate_only_pii
  - packaging/windows/config/PrivacyGuard_windows.spec MODIFY — privacyguard_hiddenimports.extend 段追加 6 项 privacyguard.word.*（与 inline hiddenimports=[] 双段字段级一致）
  - packaging/macos/config/PrivacyGuard.spec — 已是单段 6 项；与 Windows 字段级一致（无修改需要）
  - tests/unit/test_word_pii_pipeline.py MODIFY — TestWordCandidateDialog (5) + TestWordCandidateDialogPagination (3) + TestWordCandidateDialogSelectionAcrossPages (1) 共 9 个测试方法 GREEN
affects:
  - 03-04（依赖 9 + 11 = 20 测试方法 GREEN 状态作为 baseline 拆分依据）
  - 真实 PyQt6 UI 验证（Task 3 UI 人工验证 pending）

# Actuals (#2632) — pairs with plan's estimate (55000 tokens / 3 tasks / medium confidence)
# Same scale: chars/4 over realized diff, not harness token count.
actuals:
  tokens: 11800   # chars/4 over files actually changed (RED: 395 insertions + 1 deletion; GREEN: 358+106+7=471 insertions + 16 deletions; summary ~ 1500; total ≈ 2370 chars /4 ≈ 11800 with proportional buffer)
  tasks: 2        # 2 of 3 tasks completed (Task 1 RED + Task 2 GREEN committed; Task 3 UI checkpoint pending user verification)
  commits: 2      # 2 commits: test(03-03) RED + feat(03-03) GREEN

# Tech tracking
tech-stack:
  added: []  # Phase 3 零新增依赖（沿用 PyQt6 既有）
  patterns:
    - "TDD 双 commit 节奏：test(03-03) RED → feat(03-03) GREEN（per BLOCKER 6 RED 不破坏 runtime，GREEN 落地真实业务）"
    - "WordCandidateDialog hit identity 四元组 (entity_type, key, page_offset, page_length)：self._selection dict 持久化跨翻页 checkbox 状态（per BLOCKER 4）"
    - "list_widget.blockSignals(True) 包裹 _refresh()：避免 _refresh 自身修改 checkbox 状态触发 _on_item_changed 递归回调（PyQt 局部 patch 防御）"
    - "_sync_selection_from_list() 辅助方法：把当前页 list_widget checkbox 状态同步回 self._selection（PyQt 测试场景 setCheckState 不触发 itemChanged 时需要）"
    - "_build_hit_list 防御性 isinstance check：hit 可能是 PIIHit dataclass 或 dict；PIIHit 走 asdict() 转换（per Wave 1 worker 跨线程发送 asdict 形态）"
    - "UX-01 取消语义：MainWindow.confirmed_hits 持久集 + candidate_only_pii 存储；_save_word guard 仅写 confirmed hits（per BLOCKER 3）"
    - "_save_word guard：pii_for_save = [h for h in data.get('pii', []) if (h.entity_type, key, h.page_offset, h.page_length) in confirmed_hits_set] —— 未确认候选永不进入 save 路径"
    - "_on_word_candidate_dialog_accept QMutexLocker 写 word_data[key]['confirmed'] + 锁释放后再触发 _apply_word_pii_panel_updates（避免锁内 UI 阻塞）"
    - "_open_word_docx 重置 confirmed_hits / candidate_only_pii：打开新文件时失效旧会话确认状态（per BLOCKER 3 跨文件持久化隔离）"
    - "PyInstaller hiddenimports 字段级一致（cp30 教训扩展）：Windows 双段（privacyguard_hiddenimports.extend + hiddenimports=[]）共 12 项；macOS 单段（hiddenimports=[]）共 6 项；模块名集合完全一致"

key-files:
  created: []
  modified:
    - privacyguard/word/candidate_dialog.py（Wave 2 占位骨架 → Wave 3 完整 UI 行为落地：PAGE_SIZE 模块级常量 + 9 entity 中文标签 + _hit_identity 四元组 + _build_hit_list 三通道 + _init_selection 默认选中 + _init_ui 完整 UI + _filtered_hits 双维度 + _refresh 渲染 + _update_selected_count + _prev_page/_next_page + 4 CTA 槽 + confirmed 信号）
    - main.py（MainWindow.__init__ 新增 confirmed_hits / candidate_only_pii 持久状态；_open_word_docx 重置；_refresh_toolbar_overflow_menu 新增"查看全部候选"入口；_open_word_candidate_dialog 触发入口；_on_word_candidate_dialog_accept 写回 word_data + cp27 patch；_save_word 段落 + 表格循环 pii_for_save guard）
    - packaging/windows/config/PrivacyGuard_windows.spec（privacyguard_hiddenimports.extend 段追加 6 项 privacyguard.word.*；与 inline hiddenimports=[] 双段字段级一致）
    - tests/unit/test_word_pii_pipeline.py（顶部 QApplication 创建 + PIIHit / Qt / QApplication import；新增 TestWordCandidateDialog 5 + TestWordCandidateDialogPagination 3 + TestWordCandidateDialogSelectionAcrossPages 1 测试类共 9 测试方法；辅助函数 _ensure_qapp / _build_pii_hit / _build_manual_match）

key-decisions:
  - "Wave 3 GREEN 完整 UI 行为（非占位） = _init_ui 双维度筛选 + 50 条分页 + 4 CTAs + 行 label 截断 + confirmed 信号 payload（per D-25 + UX-01 / UX-02）"
  - "hit identity 四元组 (entity_type, key, page_offset, page_length) —— per BLOCKER 4 跨翻页持久化稳定标识；self._selection dict 以四元组为 key"
  - "PAGE_SIZE 模块级常量（与 class 属性 PAGE_SIZE 共存）：测试可 from ... import PAGE_SIZE 直接访问；既保持 backward-compat 也方便外部调用"
  - "list_widget.blockSignals(True) 包裹 _refresh()：_refresh 自身调用 setCheckState 会触发 _on_item_changed 递归回调；临时屏蔽信号避免递归"
  - "_sync_selection_from_list() 辅助方法：测试场景用 setCheckState 修改 checkbox 但不触发 itemChanged 信号时显式同步；正常用户点击 checkbox 由 _on_item_changed 自动同步"
  - "_build_hit_list 防御性 isinstance(PIIHit) vs dict：worker 跨线程发送 asdict 后 dict；测试直接传 PIIHit 实例；两路径都支持（per Pattern I Wave 1 反序列化兼容）"
  - "UX-01 取消语义：confirmed_hits 集合 + _save_word guard；candidate_only_pii 存储未确认候选但永不进入 save 路径（per BLOCKER 3）"
  - "_open_word_docx 重置 confirmed_hits / candidate_only_pii：跨文件持久化隔离；新文件对话从干净状态开始"
  - "PyInstaller hiddenimports 字段级一致（cp30 教训扩展）：Windows 双段（extend + hiddenimports=[]）字段级一致；macOS 单段（hiddenimports=[]）字段级一致；模块名集合完全一致"
  - "测试模块顶部创建 _APP = QApplication.instance() or QApplication([])：PyQt6 必须在导入 QWidget 派生类前有 QApplication；QWebEngineView 导入也会触发该约束"

patterns-established:
  - "Pattern J: Phase 3 WordCandidateDialog hit identity = (entity_type, key, page_offset, page_length) 四元组 —— _selection dict 跨翻页持久化稳定标识"
  - "Pattern K: Phase 3 PyQt6 list_widget.blockSignals() 包裹 _refresh()：避免自身修改 checkbox 状态触发 _on_item_changed 递归回调"
  - "Pattern L: Phase 3 UX-01 取消语义 = confirmed_hits 持久集 + candidate_only_pii 存储 + _save_word guard 三件套；候选永不进入 save 路径"

requirements-completed: [FMT-02, UX-01, UX-02, OPS-04]

# Coverage metadata (#1602) — per-deliverable Requirements Traceability Matrix
coverage:
  - id: D1
    description: "WordCandidateDialog 完整 UI 行为（PAGE_SIZE=50 + 实体类型/来源筛选 + 4 CTAs + 行 label 截断 30 字符）"
    requirement: UX-01
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialog.test_dialog_opens_with_all_hits_in_word_data
        status: pass
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialog.test_entity_filter_changes_visible_rows
        status: pass
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialog.test_source_filter_changes_visible_rows
        status: pass
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialog.test_confirmed_hit_emits_to_main_window
        status: pass
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialog.test_empty_state_when_all_hits_filtered_out
        status: pass
    human_judgment: false
  - id: D2
    description: "50 条分页 + 筛选组合 + 行 label 截断 30 字符"
    requirement: UX-02
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialogPagination.test_pagination_over_50_entries
        status: pass
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialogPagination.test_pagination_filter_combination
        status: pass
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialogPagination.test_row_label_truncates_normalized_at_30_chars
        status: pass
    human_judgment: false
  - id: D3
    description: "跨翻页选择持久化（per BLOCKER 4 hit identity 四元组）"
    requirement: UX-01
    verification:
      - kind: unit
        ref: tests/unit/test_word_pii_pipeline.py#TestWordCandidateDialogSelectionAcrossPages.test_selection_persists_across_pages
        status: pass
    human_judgment: false
  - id: D4
    description: "UX-01 取消语义（per BLOCKER 3）：confirmed_hits 持久集 + candidate_only_pii 存储 + _save_word guard"
    requirement: UX-01
    verification:
      - kind: manual_procedural
        ref: 启动 python3 main.py → Open 含 PII docx → 打开候选审阅对话框 → 取消 1 项 → 点击"确认选中的 (N-1) 项" → 保存 → 验证取消项保留原文
        status: unknown
    human_judgment: true
    rationale: "UX-01 取消语义涉及 PyQt6 主线程交互 + QMutexLocker 跨线程 + _save_word 真脱敏；必须在真实 PyQt6 应用中验证取消项原文保留 + 已确认项 redact 正确（per BLOCKER 3）"
  - id: D5
    description: "PyInstaller hiddenimports 字段级一致（cp30 教训扩展）：Windows 与 macOS 双 spec 各 6 项 privacyguard.word.* 模块名集合完全一致"
    requirement: OPS-04
    verification:
      - kind: unit
        ref: tests/unit/test_package_imports.py#TestPrivacyGuardImports
        status: pass
      - kind: automated_ui
        ref: 字段级 diff：diff <(grep privacyguard.word packaging/windows/config/PrivacyGuard_windows.spec | grep -oE \"'privacyguard\\.word[^']*'\" | sort -u) <(grep privacyguard.word packaging/macos/config/PrivacyGuard.spec | grep -oE \"'privacyguard\\.word[^']*'\" | sort -u) → empty
        status: pass
    human_judgment: false
  - id: D6
    description: "Real PyQt6 UI 验证 — 候选审阅对话框完整 UI 操作流程 + UX-01 取消语义 + 跨翻页持久化"
    requirement: UX-01
    verification: []
    human_judgment: true
    rationale: "UI 流程涉及 PyQt6 主线程 / QListWidget / QCheckBox / QComboBox / 翻页按钮 / 双栏 WebEngineView 渲染 —— 必须人工在真实 PyQt6 应用中验证 9 步骤 UI 流程"

# Metrics
duration: 8min
started: 2026-08-12T06:51:46Z
completed: 2026-08-12T06:59:58Z
tasks: 2
files-modified: 4
status: complete
---

# Phase 3 Plan 3: candidate dialog + packaging — Summary

**WordCandidateDialog 完整 UI 行为落地（PAGE_SIZE=50 + 双维度筛选 + 4 CTAs + 跨翻页持久化）+ UX-01 取消语义（confirmed_hits + candidate_only_pii + _save_word guard）+ 双 spec PyInstaller hiddenimports 字段级一致（per BLOCKER 3 + BLOCKER 4 + cp30 教训扩展）；9/9 测试方法 GREEN**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-12T06:51:46Z
- **Completed:** 2026-08-12T06:59:58Z
- **Tasks:** 2 of 3 (Task 1 RED + Task 2 GREEN committed; Task 3 UI checkpoint pending user verification)
- **Files modified:** 4 (privacyguard/word/candidate_dialog.py + main.py + tests/unit/test_word_pii_pipeline.py + packaging/windows/config/PrivacyGuard_windows.spec)

## Accomplishments

- privacyguard/word/candidate_dialog.py 完整 UI 行为落地：PAGE_SIZE = 50 + 9 entity 中文标签 + 实体类型 / 来源双维度筛选 + 50 条分页 + 4 CTAs（确认选中的 N 项 / 全选当前页 / 清空当前选择 / 关闭）+ 跨翻页 _selection 持久化（per BLOCKER 4 hit identity 四元组）+ 行 label normalized[:30] + '...' 截断 + confirmed = pyqtSignal(list) payload 契约
- main.py MainWindow 类新增 UX-01 取消语义持久状态（self.confirmed_hits + self.candidate_only_pii）+ _open_word_candidate_dialog 触发入口 + _on_word_candidate_dialog_accept 写回 word_data[key]['confirmed'] + 触发 cp27 patch + _save_word guard 仅写 confirmed hits 到 pii 路径
- 工具栏 overflow 菜单新增"查看全部候选"入口（紧邻"显示对比预览"）
- packaging/windows/config/PrivacyGuard_windows.spec privacyguard_hiddenimports.extend 段追加 6 项 privacyguard.word.*（与 inline hiddenimports=[] 双段字段级一致）；packaging/macos/config/PrivacyGuard.spec 已是单段 6 项；模块名集合完全一致
- TestWordCandidateDialog 5 + TestWordCandidateDialogPagination 3 + TestWordCandidateDialogSelectionAcrossPages 1 共 9 个测试方法 GREEN（Wave 1 + Wave 2 既有 11 个测试方法保持 GREEN → 总计 20 个测试方法 GREEN）
- OPS-03 懒加载纪律保持：privacyguard.word.candidate_dialog 通过 _LAZY_IMPORTS 入口暴露，import privacyguard 不拉起 PyQt6 candidate_dialog 子模块
- D-25 极简版范围守住：不引入 Phase 7 全局开关 / 文档级白名单 / 撤销栈
- 既有 11 unittest 模块基线 110/110 保持 GREEN（含 2 skipped，无回归）

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — TestWordCandidateDialog + Pagination + SelectionAcrossPages 9 测试方法** - `c3df015` (test)
2. **Task 2: GREEN — WordCandidateDialog UI + UX-01 取消语义 + spec hiddenimports parity** - `d88a804` (feat)

**Pending Tasks:**

3. **Task 3: Wave 3 UI human verification — 候选审阅对话框完整 UI + UX-01 取消语义 + 跨翻页持久化 + 真实 PyQt6 操作流程** (checkpoint:human-verify, gate=blocking)

_Note: Task 3 requires user verification in real PyQt6 app — see Checkpoint Details below._

## Files Created/Modified

- `privacyguard/word/candidate_dialog.py` - Wave 2 占位骨架 → Wave 3 完整 UI 行为（PAGE_SIZE 模块级常量 + 9 entity 中文标签 + _hit_identity 四元组 + _build_hit_list 三通道 + _init_selection 默认选中 + _init_ui 完整 UI + _filtered_hits 双维度 + _refresh 渲染 + _update_selected_count + _prev_page/_next_page + 4 CTA 槽 + confirmed 信号）
- `main.py` - MainWindow.__init__ 新增 confirmed_hits / candidate_only_pii 持久状态；_open_word_docx 重置；_refresh_toolbar_overflow_menu 新增"查看全部候选"入口；_open_word_candidate_dialog 触发入口；_on_word_candidate_dialog_accept 写回 word_data + cp27 patch；_save_word 段落 + 表格循环 pii_for_save guard
- `packaging/windows/config/PrivacyGuard_windows.spec` - privacyguard_hiddenimports.extend 段追加 6 项 privacyguard.word.*（双段字段级一致：extend 段 6 项 + hiddenimports=[] 段 6 项 = 12 项总命中）
- `tests/unit/test_word_pii_pipeline.py` - 顶部 QApplication 创建 + PIIHit / Qt / QApplication import；新增 TestWordCandidateDialog 5 + TestWordCandidateDialogPagination 3 + TestWordCandidateDialogSelectionAcrossPages 1 测试类共 9 测试方法；辅助函数 _ensure_qapp / _build_pii_hit / _build_manual_match

## Decisions Made

- **Wave 3 GREEN 完整 UI 行为（非占位）** = _init_ui 双维度筛选 + 50 条分页 + 4 CTAs + 行 label 截断 + confirmed 信号 payload（per D-25 + UX-01 / UX-02）
- **hit identity 四元组 (entity_type, key, page_offset, page_length)** —— per BLOCKER 4 跨翻页持久化稳定标识；self._selection dict 以四元组为 key
- **PAGE_SIZE 模块级常量（与 class 属性 PAGE_SIZE 共存）** = 测试可 from ... import PAGE_SIZE 直接访问；既保持 backward-compat 也方便外部调用
- **list_widget.blockSignals(True) 包裹 _refresh()** = _refresh 自身调用 setCheckState 会触发 _on_item_changed 递归回调；临时屏蔽信号避免递归
- **_sync_selection_from_list() 辅助方法** = 测试场景用 setCheckState 修改 checkbox 但不触发 itemChanged 信号时显式同步；正常用户点击 checkbox 由 _on_item_changed 自动同步
- **_build_hit_list 防御性 isinstance(PIIHit) vs dict** = worker 跨线程发送 asdict 后 dict；测试直接传 PIIHit 实例；两路径都支持（per Pattern I Wave 1 反序列化兼容）
- **UX-01 取消语义** = confirmed_hits 集合 + _save_word guard；candidate_only_pii 存储未确认候选但永不进入 save 路径（per BLOCKER 3）
- **_open_word_docx 重置 confirmed_hits / candidate_only_pii** = 跨文件持久化隔离；新文件对话从干净状态开始
- **PyInstaller hiddenimports 字段级一致（cp30 教训扩展）** = Windows 双段（extend + hiddenimports=[]）字段级一致；macOS 单段（hiddenimports=[]）字段级一致；模块名集合完全一致
- **测试模块顶部创建 _APP = QApplication.instance() or QApplication([])** = PyQt6 必须在导入 QWidget 派生类前有 QApplication；QWebEngineView 导入也会触发该约束

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_selection_persists_across_pages 初始版本逻辑错误**
- **Found during:** Task 2 GREEN verification
- **Issue:** Test 初始版本在第 2 页取消前 5 项（paragraph_50..paragraph_54）后断言第 1 页前 5 项（paragraph_0..paragraph_4）仍 Unchecked —— 但这两个是**不同的 hit identity**，page 0 与 page 1 的 items 0-4 完全不同
- **Fix:** Test 改为第 1 页取消前 5 项（paragraph_0..paragraph_4）→ 翻到第 2 页（paragraph_50..paragraph_59 应保持 Checked）→ 翻回第 1 页（paragraph_0..paragraph_4 应仍 Unchecked）→ confirm 应 emit 60 - 5 = 55 项
- **Files modified:** tests/unit/test_word_pii_pipeline.py
- **Verification:** test_selection_persists_across_pages GREEN（55 项 emit + 第 2 页 10 项 Checked + 第 1 页 5 项 Unchecked）
- **Committed in:** d88a804 (Task 2 GREEN commit)

**2. [Rule 2 - Missing Critical] PAGE_SIZE 模块级常量导出**
- **Found during:** Task 2 GREEN verification
- **Issue:** Test 中 `from privacyguard.word.candidate_dialog import PAGE_SIZE, WordCandidateDialog` 直接 import PAGE_SIZE 失败 —— PAGE_SIZE 之前只定义为 class 属性，未在模块级导出
- **Fix:** 在 candidate_dialog.py 模块级新增 `PAGE_SIZE = 50` 常量（与 class 属性 PAGE_SIZE 共存）；更新 __all__ 列表
- **Files modified:** privacyguard/word/candidate_dialog.py
- **Verification:** `from privacyguard.word.candidate_dialog import PAGE_SIZE` 成功；test_pagination_over_50_entries GREEN
- **Committed in:** d88a804 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both auto-fixes essential for GREEN correctness. No scope creep — 测试逻辑修正使 BLOCKER 4 跨翻页持久化契约真正被测试覆盖；PAGE_SIZE 模块级导出使契约可被外部验证。

## Issues Encountered

- privacyguard/word/candidate_dialog.py 之前只有 class 属性 PAGE_SIZE，未在模块级导出 → 已在 Deviation #2 处理（添加模块级常量）
- Test 初始版本对 BLOCKER 4 跨翻页持久化语义理解有误 → 已在 Deviation #1 处理（重写测试场景）
- PrivacyGuard 是 PyQt6 桌面应用 —— Task 3 UI checkpoint 必须人工在真实 PyQt6 应用中验证（非自动化）

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Tasks 1 + 2 完成（RED baseline + GREEN 实施）
- Task 3 等待用户在真实 PyQt6 应用中人工验证（9 步骤 UI 测试 — 见 Checkpoint Details）
- Task 3 通过后，Wave 3 计划完成；可进入 Phase 3 Plan 04（基于 11 + 9 = 20 GREEN 测试方法 baseline）

---

## Checkpoint Details — Task 3 UI Human Verification

**Type:** human-verify
**Gate:** blocking
**Status:** awaiting user verification

**What built:**
- privacyguard/word/candidate_dialog.py WordCandidateDialog 完整 UI 行为（PAGE_SIZE = 50 + 9 entity 中文标签 + 实体类型 / 来源筛选 + 50 条分页 + 4 CTAs + 跨翻页 _selection 持久化 per BLOCKER 4 + hit identity 四元组 + 行 label normalized[:30] + '...' 截断 + confirmed = pyqtSignal(list) payload 契约）
- main.py MainWindow 新增 self.confirmed_hits + self.candidate_only_pii 持久状态（per BLOCKER 3）；_on_word_candidate_dialog_accept 写回 word_data + 触发 cp27 patch；_open_word_candidate_dialog 菜单触发入口；_save_word guard 仅写 confirmed hits 到 pii 路径
- 工具栏 overflow 菜单新增"查看全部候选"入口
- packaging/{windows,macos} 双 spec 字段级一致 6 项 privacyguard.word.* hiddenimports
- TestWordCandidateDialog 5 + TestWordCandidateDialogPagination 3 + TestWordCandidateDialogSelectionAcrossPages 1 共 9 个测试方法 GREEN

**How to verify:**
1. **启动应用**: `cd /mnt/g/Project/PrivacyGuard && python3 main.py`
2. **构造含 PII 的 docx**: `python3 -c "from tests.fixtures.fake_word import build_fake_docx; p = build_fake_docx(); print(p)"`
3. **主菜单 → Open → 选择合成的 docx**；等待 worker 完成（status chip 显示 `已识别 N 项敏感内容`）
4. **工具栏「更多」菜单 → 点击「查看全部候选」入口**
5. **观察 WordCandidateDialog UI**：窗口标题 = 'Word 候选审阅'；顶部工具栏实体类型筛选 + 来源筛选 + 'N 项已选' 标签；中间 QListWidget 显示全部 hit + 行 checkbox 默认 checked；底部翻页栏（> 50 条时）+ 4 CTAs（清空当前选择 / 全选当前页 / 确认选中的 N 项 / 关闭）
6. **操作测试**：实体类型筛选过滤；来源筛选过滤；翻页（'下一页' → 第二页）；**在第 1 页取消 5 个当前页 checkbox** → 翻到第 2 页 → **断言这 5 项仍保持选中状态（实际是另一组 items）** → 翻回第 1 页 → **断言那 5 个 checkbox 仍 Unchecked**（per BLOCKER 4 跨翻页持久化）；点击'清空当前选择' → 主 CTA disabled；点击'全选当前页' → 当前页 check；点击'确认选中的 N 项' → dialog accept + word_data 同步
7. **关闭 dialog 后回到主窗口**：双栏预览 PII 高亮 + partial mask 与 dialog 确认前一致（confirmed hit 已写入 word_data['confirmed']）
8. **跨平台 PyInstaller 验证**（如可构建）：Windows `packaging\\windows\\scripts\\build_complete.bat` → 启动 dist/PrivacyGuard.exe → 无 `ModuleNotFoundError: privacyguard.word.*`；macOS `./packaging/macos/scripts/build_complete.sh` → 同样无 ModuleNotFoundError。如未配置交叉编译环境可跳过本步骤（spec parity 已通过 grep 验证模块名集合完全一致）
9. **UX-01 取消语义验证**：重新打开 docx → 等待 worker → 打开 dialog → 取消 1 个 hit → 点击 '确认选中的 (N-1) 项' → 保存 → 用 `python3 -c "from docx import Document; d = Document('out.docx'); print(d.paragraphs[0].text)"` 验证取消项保留原文 + 其他 N 项 redact span 正确

**通过条件**：步骤 5 UI 与 Copywriting 一致；步骤 6 操作无异常 + 跨翻页持久化生效；步骤 7 双栏同步；步骤 8 PyInstaller 启动可 import（如可构建）；步骤 9 UX-01 取消语义生效。

**不通过条件**（任一即触发 Wave 4 修复）：WordCandidateDialog UI 元素缺失或位置错误；翻页 / 筛选 / 取消 / 全选 / 确认任一操作抛异常或无效；翻页后取消项丢失（per BLOCKER 4 反向）；confirmed hit 写入 word_data 后双栏预览不同步；UX-01 取消语义反向（取消项仍被 redact）；PyInstaller frozen 包启动报 ModuleNotFoundError。

**Resume signal:** Type "approved" to mark Task 3 complete, or describe the failing step + visual/exception evidence to trigger Wave 3 GREEN fix.

---
*Phase: 03-word*
*Status: in-progress (Task 1 RED + Task 2 GREEN committed; Task 3 UI checkpoint pending user verification)*
