---
phase: 03-word
plan: 01
slug: tracer
type: execute
wave: 1
depends_on: []
files_modified:
  - privacyguard/word/__init__.py
  - privacyguard/word/adapter.py
  - privacyguard/word/worker.py
  - privacyguard/word/redact.py
  - privacyguard/word/clear_doc_props.py
  - privacyguard/pii/hits.py
  - privacyguard/__init__.py
  - tests/fixtures/__init__.py
  - tests/fixtures/fake_word.py
  - tests/unit/test_word_pii_pipeline.py
  - main.py
  - packaging/windows/config/PrivacyGuard_windows.spec
  - packaging/macos/config/PrivacyGuard.spec
autonomous: false
requirements:
  - FMT-02
  - OPS-03
  - OPS-04
  - OPS-07
user_setup: []

estimate:
  tokens: 85000
  raw_tokens: 42500
  tasks: 3
  confidence: medium

must_haves:
  truths:
    - "打开 docx 文件后无需点击扫描按钮，WordPIIWorker QThread 在 _open_word_docx 完成后自动启动并完成扫描（per D-09 auto-trigger）"
    - "PIIEngine.detect 命中 9 类实体中至少 6 类（CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT）输出 PIIHit 列表到 word_data[key][\"pii\"]（per D-15 / D-17 / D-18）"
    - "_save_word 调用 privacyguard/word/redact.py::redact_word 后导出的 docx 文档正文不含原文敏感字串，验证脚本断言 Document(out).paragraphs[*].text 不含 fake_id_card()（per D-23 + SAFE-02 reverse-extraction）"
    - "_save_word 在 new_doc.save(fname) 之前调 privacyguard/word/clear_doc_props.py::clear_word_doc_props；导出后 Document(out).core_properties.title / author / subject / keywords / last_modified_by 全部为 \"\"，revision 等于 1，app_properties.company / manager 为空字符串（per D-08 / D-24）"
    - "merge_word_matches_with_priority 新增 pii_matches=None 第六参数；priority 锁定 rule > pii > manual > ocr；区间重叠时 pii 命中覆盖 manual 命中（per D-19）"
    - "import privacyguard.word 不会拉起 python-docx 或 mammoth；privacyguard.word.__getattr__ + _LAZY_IMPORTS 严格 lazy-load（per D-06 / OPS-03）"
    - "现有基线测试保持通过（test_mixed_pdf_ocr / test_path_validation / test_ocr_api / test_package_imports / test_pdf_text_hit_dedup / test_app_config / test_word_replace_rules / test_batch_word_replace / test_config_alignment / test_fstring_safety / test_convergence）；新增 tests/unit/test_word_pii_pipeline.py 测试类全部 GREEN（per D-13 / D-14 / OPS-07）"
  artifacts:
    - privacyguard/word/__init__.py NEW — _LAZY_IMPORTS + __getattr__ 懒加载入口（5 项 lazy forward）
    - privacyguard/word/adapter.py NEW — WordAdapter.collect_units 完整实现
    - privacyguard/word/worker.py NEW — WordPIIWorker QThread 完整实现
    - privacyguard/word/redact.py NEW — redact_paragraph + redact_word wrapper 完整实现
    - privacyguard/word/clear_doc_props.py NEW — clear_word_doc_props 完整实现
    - privacyguard/pii/hits.py MODIFY — 新增 ENTITY_TYPE_SHORT_CODE 9 短码字典（D-21 单一来源 + ASCII uppercase；per BLOCKER 5 抽离 main.py）
    - privacyguard/__init__.py MODIFY — _LAZY_IMPORTS 追加 5 项 Word 符号 + ENTITY_TYPE_SHORT_CODE 转发（共 6 项）
    - tests/fixtures/__init__.py NEW — 允许 tests/fixtures/* 被顶层 import 链发现
    - tests/fixtures/fake_word.py NEW — build_fake_docx 合成含 PII 的 docx（D-26；Faker 合成数据）
    - tests/unit/test_word_pii_pipeline.py NEW — 5 个测试类共 7 个测试方法
    - main.py MODIFY — _open_word_docx 自动启动 WordPIIWorker / _on_word_pii_page_result 槽 / merge_word_matches_with_priority 第六参数 / _save_word 扩 pii_matches 入参
    - packaging/windows/config/PrivacyGuard_windows.spec MODIFY — hiddenimports 段追加 6 项 privacyguard.word.*（D-26 + cp30 教训扩展）
    - packaging/macos/config/PrivacyGuard.spec MODIFY — hiddenimports 段追加 6 项 privacyguard.word.*（D-26 + cp30 教训扩展 — 双 spec 字段级一致）
  key_links:
    - "WordPIIWorker.run() (privacyguard/word/worker.py) 到 PIIEngine.detect(TextUnit(page_index=0, text=word_data[key][\"text\"], source=\"text\"), page=None) (privacyguard/pii/engine.py:103-211) — format-agnostic 入口 (D-17)"
    - "WordPIIWorker.pii_signal 到 _on_word_pii_page_result(key, hits) 到 QMutexLocker(self._word_data_lock) 写 word_data[key][\"pii\"] (D-09 / D-18 + cp30 教训扩展)"
    - "WordAdapter.collect_units 到 main.py:_open_word_docx 段落 + 表格初始化路径 (main.py:10797-10819) 共享 key 命名 (paragraph_{idx} / table_{t}_cell_{r}_{c})"
    - "redact_word (privacyguard/word/redact.py) 懒加载 main.py:replace_matches_in_paragraph (main.py:965) — 不重写 run-level 替换 (D-23)"
    - "clear_word_doc_props (privacyguard/word/clear_doc_props.py) 到 python-docx core_properties / app_properties API — D-08 锁 5 core 字符串 + revision=1 + 2 app 字段 (D-24)"
    - "_save_word (main.py:12699) 调 redact_word + clear_word_doc_props → new_doc.save(fname) — 与 Phase 2 PDF SAFE-03 在 save 前调 clear_pdf_metadata 对称"
    - "merge_word_matches_with_priority 第六参数 pii_matches=None 默认值保持向后兼容（既有基线不破坏）（D-19）"
    - "ENTITY_TYPE_SHORT_CODE 字典从 main.py 抽离至 privacyguard/pii/hits.py（D-21 + BLOCKER 5 收敛）；main.py 与 privacyguard/word/candidate_dialog.py 均从此处 import（单一来源）"
    - "privacyguard/__init__.py::_LAZY_IMPORTS 包含 'ENTITY_TYPE_SHORT_CODE': ('privacyguard.pii.hits', 'ENTITY_TYPE_SHORT_CODE')（per D-06 懒加载纪律）"
    - "双 spec hiddenimports 字段级一致（cp30 教训扩展）：Windows spec 12 行（双段 × 6 项）+ macOS spec 6 行（单段 × 6 项）"
  prohibitions:
    - "不得在 main.py 内联 redact_word_docx 或 clear_word_doc_props_docx 实现；所有 Word 适配 / 真脱敏 / 文档属性清除逻辑一律进 privacyguard/word/*（per D-05 / v37.7.6 收敛原则）"
    - "不得在 privacyguard/word/__init__.py 或 privacyguard/word/worker.py 包级 eager import python-docx / mammoth / privacyguard.pii.engine；所有重模块必须经 _LAZY_IMPORTS / 函数内 import（per D-06 / OPS-03）"
    - "不得在 _on_word_pii_page_result 裸写 self.word_data[key][\"pii\"] = hits；必须 QMutexLocker(self._word_data_lock) 包裹（per D-09 / cp30 教训扩展）"
    - "不得让 clear_word_doc_props 写入 \"Anonymous\" / \"Redacted\" 等占位字符串；5 个 core 字符串字段必须全部 \"\"；revision 字段必须单独处理为整数 1（per D-08 / D-15）"
    - "不得触碰 doc.core_properties.creation_date / modified / Template / TotalTime 等保留字段（per D-08 锁定）"
    - "不得让 merge_word_matches_with_priority 新参数破坏 back-compat；新增 pii_matches 必须是带默认值的关键字参数（默认 None → 转 []），既有 test_word_replace_rules 与 test_batch_word_replace 必须保持 green（per D-19 / D-13）"
    - "不得让 build_fake_docx 引入真实个人信息（per OPS-05 合成数据；fake_pii.Faker 合成器复用）"
    - "不得让 PyInstaller spec 缺失 privacyguard.word.* hiddenimports；packaging/{windows,macos}/config/*.spec 字段级一致（per cp30 教训扩展）"
    - "不得在 main.py:_apply_word_pii_panel_updates 触发整页 web_view.setHtml(...)；必须走 web_view.page().runJavaScript(\"updateBlock(...)\") 局部 patch（per D-10 / cp27 锁定 — Wave 2 落地）"
    - "不得让 redact_word 直接重写 run-level 替换逻辑；仅作 main.py:replace_matches_in_paragraph 的 wrapper（per D-23）"
    - "不得让 _open_word_docx 等待手动点击 scan 按钮；WordPIIWorker 必须自动启动（per D-09 auto-trigger 锁定）"
    - "不得让 ENTITY_TYPE_SHORT_CODE 在 main.py 与 privacyguard/pii/hits.py 两处并存；唯一来源位于 privacyguard/pii/hits.py（per BLOCKER 5 + D-21）"
  backstop_statements: []

---

## Artifacts this phase produces

> 单一来源的 artifacts 清单 —— 与上方 `files_modified` 字段、`<tasks>` 内 `<files>` 列表以及 `<output>` 声明字段级一致。

**NEW 文件（8 项）：**
1. `privacyguard/word/__init__.py` — 懒加载 _LAZY_IMPORTS 入口（5 项 lazy forward）
2. `privacyguard/word/adapter.py` — WordAdapter.collect_units 完整实现
3. `privacyguard/word/worker.py` — WordPIIWorker QThread 完整实现
4. `privacyguard/word/redact.py` — redact_word wrapper 完整实现
5. `privacyguard/word/clear_doc_props.py` — clear_word_doc_props 完整实现
6. `tests/fixtures/__init__.py` — fixtures 包入口
7. `tests/fixtures/fake_word.py` — build_fake_docx 合成器
8. `tests/unit/test_word_pii_pipeline.py` — 5 个测试类（7 个测试方法）

**MODIFY 文件（5 项）：**
9. `privacyguard/pii/hits.py` — 新增 ENTITY_TYPE_SHORT_CODE 9 短码字典（D-21 单一来源；BLOCKER 5 抽离）
10. `privacyguard/__init__.py` — _LAZY_IMPORTS 追加 6 项（5 项 Word 符号 + ENTITY_TYPE_SHORT_CODE）
11. `main.py` — _open_word_docx / _on_word_pii_page_result / merge_word_matches_with_priority 第六参数 / _save_word 4 处接线
12. `packaging/windows/config/PrivacyGuard_windows.spec` — hiddenimports 段追加 6 项 privacyguard.word.*（双段 extend）
13. `packaging/macos/config/PrivacyGuard.spec` — hiddenimports 段追加 6 项 privacyguard.word.*（单段，与 Windows 字段级一致）

---

## Decision Coverage (D-01..D-26)

> 决策溯源矩阵：本 plan 实施 / 继承 / 不触达的 D-XX 决策。locked 决策在 `<task>` action 中以 `per D-NN` 引用。

| D-ID | Status | Task Reference | 备注 |
|------|--------|----------------|------|
| D-01 | inherited (range lock) | 全 plan 引用 ROADMAP Phase 3 范围 | 范围锁不重写；Phase 3 仅 Word 垂直切片 |
| D-02 | inherited (architecture) | 复用 privacyguard.pii.*；不在此 plan 扩展 | Phase 1/2 既有架构 |
| D-03 | inherited (dependency) | WordAdapter.collect_units 喂 privacyguard.pii.engine | Phase 1/2 已就位 |
| D-04 | **implement** | Task 1 + Task 2: word_data[key]["pii"] 新通道 | 与 ocr / manual 平级 |
| D-05 | **preserve + extend** | Task 1: privacyguard/word/5 模块新建（main.py 0 内联）；Task 2: 接线 main.py 调用方 | v37.7.6 收敛原则 |
| D-06 | **implement** | Task 1: privacyguard/word/__init__.py _LAZY_IMPORTS + __getattr__；privacyguard/__init__.py 转发 | OPS-03 懒加载纪律 |
| D-07 | **preserve** | cp27 增量 DOM patch 既有路径；Wave 2 落地 PII 局部 patch | D-10 锁定 |
| D-08 | **implement** | Task 1: clear_doc_props.py CORE_PROPS_TO_CLEAR 5 字段 + APP_PROPS_TO_CLEAR 2 字段 + revision int 1 | 8 字段范围锁 |
| D-09 | **implement** | Task 2: _open_word_docx 自动启动 WordPIIWorker；_on_word_pii_page_result 槽 | auto-trigger 锁定 |
| D-10 | **preserve** | 增量 patch 契约；Wave 2 实施 _apply_word_pii_panel_updates | cp27 锁；Wave 2 引用 |
| D-11 | **preserve** | 候选审阅 UI 极简版 = Wave 3 完整实施范围 | Phase 3 范围锁 |
| D-12 | **preserve** | 不引入新 PyPI 依赖；python-docx + mammoth 既有 | 依赖锁 |
| D-13 | **implement** | Task 1: tests/unit/test_word_pii_pipeline.py 5 测试类 7 测试方法 RED 骨架 → Task 2 GREEN | ≥ 1 新测试类 |
| D-14 | **preserve** | 既有 11 unittest 模块基线保持 GREEN；Wave 4 升级 baseline | OPS-07 基线门禁 |
| D-15 | **preserve** | 9 类 entity 沿用 Phase 2；不新增 entity_type | Phase 1/2 范围 |
| D-16 | **preserve** | PIIHit 9 字段锁；Word page_rect 置占位 (0,0,0,0) | D-05 / ENGINE-02 锁 |
| D-17 | **implement** | WordAdapter.collect_units 喂 TextUnit(page_index=key_index, text=..., source="text")；worker 内 page=None | engine.detect 入口 |
| D-18 | **implement** | Task 1 + Task 2: word_data[key]["pii"] = hits；_on_word_pii_page_result 槽 QMutexLocker 写 | 三通道平级 |
| D-19 | **implement** | Task 2: merge_word_matches_with_priority 第六参数 pii_matches=None；priority 顺序 rule > pii > manual > ocr；pii_matches 分派 PIIHit → dict | back-compat 默认值 |
| D-20 | **preserve** | PII 红框 #D64545 / #FF6B6B；Wave 2 落地 | 颜色锁；Wave 2 引用 |
| D-21 | **implement (refactored)** | Task 1: privacyguard/pii/hits.py 新增 ENTITY_TYPE_SHORT_CODE 9 短码字典；main.py 与 candidate_dialog.py 均从此 import（per BLOCKER 5）；9 短码 ASCII uppercase | 单一来源抽离 |
| D-22 | **preserve** | data-key 注入复用 _add_data_key_attributes / _add_data_key_regex_fallback 既有 helper；Wave 4 验证 | 不重写 |
| D-23 | **implement** | Task 1 + Task 2: redact_word wrapper 复用 main.py:replace_matches_in_paragraph run-level 替换；lazy import inside function | 不重写 run-level 逻辑 |
| D-24 | **implement** | Task 2: _save_word 内 new_doc.save(fname) 前调 clear_word_doc_props | 与 Phase 2 SAFE-03 对称 |
| D-25 | **preserve** | WordCandidateDialog 极简版 = Wave 3 完整实施范围 | D-11 范围锁 |
| D-26 | **implement** | Task 1: tests/fixtures/fake_word.py::build_fake_docx 用 python-docx 合成含 PII 的 docx；Task 1 + Task 2: packaging/{windows,macos}/*.spec hiddenimports 追加 6 项 privacyguard.word.*（双 spec 字段级一致） | OPS-05 + cp30 |

**Legend:**
- **implement** — 本 plan 实施该决策（task 内 per D-NN 引用）
- **preserve** — 继承上游锁；不在本 plan 重新实施，但 Wave 后续 plan 引用
- **inherited** — 跨阶段锁；本 plan 仅引用不重写

---

<objective>
落地 Phase 3 端到端 spine：docx 打开 → 9 类 PII 自动识别（CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_EMAIL / CN_USCC / CN_TAXPAYER_ID / CN_TAXPAYER_ID_15 / CN_VAT_INVOICE / CN_BANK_ACCOUNT）→ 写入 word_data[key]["pii"] 通道 → _save_word 调 redact_word 真脱敏 + clear_word_doc_props 清 8 字段 → reverse-extraction 断言新增测试类全部 GREEN。Wave 1 必须在最小可行切片上证明整条链路通；Wave 2 / 3 / 4 在此基础上扩展。
</objective>

<purpose>
Phase 3 不能在 FMT-02 没就位的情况下交付。Tracer 在最小输入上证明三件事：
(1) WordPIIWorker 在 _open_word_docx 后自动启动（D-09），不依赖手动 scan 按钮；
(2) redact_word 调用 main.py:replace_matches_in_paragraph 既有 run-level 替换 API（D-23），导出的 docx 不含原文敏感字串（SAFE-02 reverse-extraction）；
(3) clear_word_doc_props 紧邻 new_doc.save(fname) 前调（D-24），D-08 锁 8 字段全部清除。

Wave 1 RED 阶段只引入测试 + 模块骨架 + 占位符 + main.py 函数签名扩展，**不**让 _save_word 路由到抛 NotImplementedError 的 redact_word stub（per BLOCKER 6）—— runtime 必须保持完整可保存状态直到 Wave 2 GREEN 实施。
</purpose>

<output>
- privacyguard/word/ 子包 5 个文件：__init__.py / adapter.py / worker.py / redact.py / clear_doc_props.py（完整业务逻辑）
- privacyguard/pii/hits.py MODIFY：新增 ENTITY_TYPE_SHORT_CODE 9 短码字典（D-21 单一来源 + BLOCKER 5 抽离）
- privacyguard/__init__.py MODIFY：_LAZY_IMPORTS 追加 5 项 Word 符号 + ENTITY_TYPE_SHORT_CODE 转发
- tests/fixtures/fake_word.py + tests/fixtures/__init__.py
- tests/unit/test_word_pii_pipeline.py 5 个测试类（7 个测试方法）
- main.py 4 处修改：_open_word_docx 自动启动 / _on_word_pii_page_result 槽 / merge_word_matches_with_priority 第六参数 / _save_word 扩 pii_matches + redact_word + clear_word_doc_props
- packaging/{windows,macos}/config/*.spec MODIFY：hiddenimports 字段级一致追加 6 项 privacyguard.word.*
</output>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-word/03-RESEARCH.md
@.planning/phases/03-word/03-PATTERNS.md
@.planning/phases/03-word/03-UI-SPEC.md
@.planning/phases/03-word/03-VALIDATION.md
@.planning/phases/02-pdf/02-01-tracer-PLAN.md
@.planning/phases/02-pdf/02-PATTERNS.md
@CLAUDE.md
@privacyguard/pii/__init__.py
@privacyguard/pii/engine.py
@privacyguard/pii/hits.py
@privacyguard/pii/mask.py
@main.py:863-1018 (merge_word_matches_with_priority + apply_range_to_runs + replace_matches_in_paragraph)
@main.py:10777-10819 (_open_word_docx)
@main.py:11508 (_on_pii_page_result Phase 1 page_data 镜像)
@main.py:12699-12794 (_save_word)
@main.py:11602-11616 (QMutexLocker 既有 word_data 写形态)
@tests/fixtures/fake_pii.py (Phase 1 + Phase 2 合成器)
@tests/unit/test_package_imports.py (lazy-load 断言范本)
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Wave 0 — 落地 privacyguard/word/ 子包 + fake_word fixture + ENTITY_TYPE_SHORT_CODE 抽离 + 测试 RED 基线 + 双 spec hiddenimports</name>
  <files>
    - privacyguard/word/__init__.py
    - privacyguard/word/adapter.py
    - privacyguard/word/worker.py
    - privacyguard/word/redact.py
    - privacyguard/word/clear_doc_props.py
    - privacyguard/pii/hits.py
    - privacyguard/__init__.py
    - tests/fixtures/__init__.py
    - tests/fixtures/fake_word.py
    - tests/unit/test_word_pii_pipeline.py
    - packaging/windows/config/PrivacyGuard_windows.spec
    - packaging/macos/config/PrivacyGuard.spec
  </files>
  <read_first>
    - .planning/phases/03-word/03-PATTERNS.md (lines 16-37 — 7 个 NEW + 6 个 MODIFY 文件清单 + 关键 excerpts)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1015-1064 — WordAdapter.collect_units 完整代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1306-1365 — build_fake_docx 完整 fixture 代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1119-1172 — clear_word_doc_props 完整代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1066-1119 — redact_word 完整 wrapper 代码示例)
    - .planning/phases/03-word/03-VALIDATION.md (lines 41-65 — Per-Task Verification Map)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 381-444 — UI Considerations 24 covered · 3 backstop · 0 unresolved)
    - privacyguard/pii/__init__.py (Phase 1/2 _LAZY_IMPORTS + __getattr__ 范本)
    - privacyguard/pii/hits.py (PIIHit 9 字段锁 — D-16)
    - privacyguard/__init__.py (_LAZY_IMPORTS 已有 33 项符号 — 范本)
    - main.py:863-906 (merge_word_matches_with_priority 当前 5 参数签名)
    - main.py:10777-10819 (_open_word_docx 当前 word_data 初始化路径)
    - main.py:11508 (_on_pii_page_result Phase 1 page_data 镜像 — QMutexLocker 形态)
    - main.py:12699-12794 (_save_word 当前 paragraphs + tables 遍历形态)
    - tests/fixtures/fake_pii.py (Phase 1/2 9 类 PII 合成器)
    - tests/unit/test_package_imports.py (lazy-load 断言范本 — 需新增 5 项 word 子模块断言)
  </read_first>
  <action>
    Phase 3 Wave 1 = RED 基线任务。本任务**只写测试 + fixture + 模块骨架 + main.py 函数签名扩展 + 双 spec hiddenimports**（per BLOCKER 6 — RED 不破坏 runtime）。本任务结束时所有 NEW 测试必须 RED（NotImplementedError / ImportError / AttributeError），Wave 2 任务再写 GREEN 实现。

    **Step A — privacyguard/word/__init__.py 懒加载骨架**（NEW 文件，按 privacyguard/pii/__init__.py 形态镜像）。文件首部 docstring "PrivacyGuard Word 文档处理子系统（v38.x Phase 3 — FMT-02）。承载 Word → PII 引擎 TextUnit 适配、QThread worker、真脱敏 wrapper、Word 文档属性清除、候选审阅对话框。所有子模块经 _LAZY_IMPORTS + __getattr__ 懒加载（OPS-03）；禁止包级 eager import python-docx / mammoth / privacyguard.pii.engine。"。文件体严格定义：from importlib import import_module；__all__ 列表 5 项 = ['WordAdapter', 'redact_word', 'clear_word_doc_props', 'WordPIIWorker', 'WordCandidateDialog']；_LAZY_IMPORTS 字典 5 项 = {'WordAdapter': ('privacyguard.word.adapter', 'WordAdapter'), 'redact_word': ('privacyguard.word.redact', 'redact_word'), 'clear_word_doc_props': ('privacyguard.word.clear_doc_props', 'clear_word_doc_props'), 'WordPIIWorker': ('privacyguard.word.worker', 'WordPIIWorker'), 'WordCandidateDialog': ('privacyguard.word.candidate_dialog', 'WordCandidateDialog')}；def __getattr__(name) 严格按 privacyguard/pii/__init__.py:112-119 镜像（if name not in _LAZY_IMPORTS → AttributeError；否则 import_module + getattr + globals()[name] = value + return value）；def __dir__() 返回 sorted(set(globals()) | set(__all__))。**重要**：本文件**绝不**做 from privacyguard.pii.engine import PIIEngine 或 from docx import Document 这类 eager import。

    **Step B — privacyguard/word/adapter.py WordAdapter.collect_units 骨架**（NEW 文件）。模块 docstring "Phase 3 Word 文档 → PII 引擎 TextUnit 流适配器（D-04 / D-17）"。定义 class WordAdapter: 含静态方法 collect_units(docx_path) -> Tuple[List[TextUnit], Dict[int, str]]，函数体抛 NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现"). __all__ = ['WordAdapter']。**绝不**在模块顶部 from docx import Document 或 from privacyguard.pii.hits import TextUnit（这两行在函数体内延迟 import）。

    **Step C — privacyguard/word/worker.py WordPIIWorker QThread 骨架**（NEW 文件）。模块 docstring "Phase 3 Word PII 扫描 QThread worker（D-09 自动触发）"。定义 class WordPIIWorker(QThread)，含 pyqtSignal: pii_signal = pyqtSignal(str, list)（key, [hit_dict, ...]）+ finished_signal = pyqtSignal() + error_signal = pyqtSignal(str)（exception_class）。__init__(self, word_data: dict, parent=None) 保存 self._word_data = word_data；self._engine = None。run() 方法体抛 NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现 PIIEngine.detect 调用"). __all__ = ['WordPIIWorker']。**绝不**在模块顶部 from PyQt6.QtCore import QThread / pyqtSignal 或 from privacyguard.pii.engine import PIIEngine（这两组在模块顶部是允许的，因为 PyQt6 与 dataclasses 是常驻 import；privacyguard.pii.engine 在 run() 内延迟）。

    **Step D — privacyguard/word/redact.py wrapper 骨架**（NEW 文件）。模块 docstring "Phase 3 Word 真脱敏写入 wrapper（D-23 — 沿用 main.py:replace_matches_in_paragraph run-level 替换）"。定义 def redact_paragraph(para, matches, fallback_replacement_text='[已脱敏]') -> None：函数体内 lazy import main.py:replace_matches_in_paragraph；本任务实现为 NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现"). 定义 def redact_word(doc, key: str, merged_matches: list, fallback_replacement_text: str = '[已脱敏]') -> None：函数体 NotImplementedError. __all__ = ['redact_word', 'redact_paragraph']。**关键**：Wave 1 RED 阶段 main.py:_save_word **不**调用 redact_word stub（per BLOCKER 6）；仅保留占位 import 路径让模块可被发现。

    **Step E — privacyguard/word/clear_doc_props.py 骨架**（NEW 文件）。模块 docstring "Phase 3 Word 文档属性清除（D-08 / D-24 — 与 Phase 2 SAFE-03 clear_pdf_metadata 对称）"。模块顶层 Final 常量：CORE_PROPS_TO_CLEAR: Final = ('title', 'author', 'subject', 'keywords', 'last_modified_by')（5 字段字符串）+ APP_PROPS_TO_CLEAR: Final = ('company', 'manager')（2 字段字符串）。定义 def clear_word_doc_props(doc) -> None：函数体 NotImplementedError. __all__ = ['clear_word_doc_props', 'CORE_PROPS_TO_CLEAR', 'APP_PROPS_TO_CLEAR']。**关键**：Wave 1 RED 阶段 main.py:_save_word **不**调用 clear_word_doc_props stub（per BLOCKER 6）。

    **Step F — privacyguard/pii/hits.py 新增 ENTITY_TYPE_SHORT_CODE 字典**（MODIFY — per BLOCKER 5 + D-21 单一来源抽离）。在文件末尾（紧邻 __all__ = ['PIIHit', 'TextUnit', 'ConfidenceTier'] 之前）新增：
    ```python
    ENTITY_TYPE_SHORT_CODE: dict = {
        'CN_ID_CARD': 'ID',
        'CN_PHONE': 'PHONE',
        'CN_BANK_CARD': 'BANK',
        'CN_EMAIL': 'EMAIL',
        'CN_USCC': 'USCC',
        'CN_TAXPAYER_ID': 'TAX',
        'CN_TAXPAYER_ID_15': 'TAX15',
        'CN_VAT_INVOICE': 'VAT',
        'CN_BANK_ACCOUNT': 'ACCT',
    }
    ```
    9 短码字典；ASCII uppercase；D-21 锁。同步更新 __all__ = ['PIIHit', 'TextUnit', 'ConfidenceTier', 'ENTITY_TYPE_SHORT_CODE']。

    **Step G — privacyguard/__init__.py _LAZY_IMPORTS 扩展**（MODIFY）。在文件末尾 _LAZY_IMPORTS 字典追加 6 项：'WordAdapter': ('privacyguard.word', 'WordAdapter') / 'redact_word': ('privacyguard.word', 'redact_word') / 'clear_word_doc_props': ('privacyguard.word', 'clear_word_doc_props') / 'WordPIIWorker': ('privacyguard.word', 'WordPIIWorker') / 'WordCandidateDialog': ('privacyguard.word', 'WordCandidateDialog') / 'ENTITY_TYPE_SHORT_CODE': ('privacyguard.pii.hits', 'ENTITY_TYPE_SHORT_CODE')（per BLOCKER 5 单一来源）。同时在 __all__ 列表同步追加这 6 个字符串。**不**修改文件中其他任何代码（保持 Phase 2 既有 33 项符号与 _LAZY_IMPORTS 不动）。

    **Step H — tests/fixtures/__init__.py NEW**（允许 tests/fixtures/fake_word 通过 tests.fixtures.fake_word 路径被 unittest 发现）。文件为空 docstring "测试夹具包入口（Phase 3 — fake_word 合成器）"。

    **Step I — tests/fixtures/fake_word.py build_fake_docx 完整实现**（NEW 文件）。模块 docstring "Phase 3 合成含 PII 的 docx fixture（D-26 / OPS-05 — Faker 合成数据）"。实现 def build_fake_docx(paragraphs: Optional[List[str]] = None, tables: Optional[List[List[List[str]]]] = None, add_pii: bool = True) -> str。函数体严格按 03-RESEARCH.md:1316-1362 示例：from docx import Document + from typing import List, Optional；doc = Document()；遍历 paragraphs 调 doc.add_paragraph(p_text)；遍历 tables 三层循环（r_idx / c_idx）调 table.rows[r_idx].cells[c_idx].text = cell_text（与 _open_word_docx:10807-10819 表格初始化路径对齐）；add_pii=True 时 from tests.fixtures.fake_pii import fake_id_card / fake_phone / fake_email / fake_bank_card / fake_uscc 各追加一个 PII 段落（"甲方身份证 {fake_id_card()}" / "联系电话 {fake_phone()}" / "邮箱 {fake_email()}" / "卡号 {fake_bank_card()}" / "统一信用代码 {fake_uscc()}"）；最后 import tempfile + os；fd, path = tempfile.mkstemp(suffix='.docx')；os.close(fd)；doc.save(path)；return path。__all__ = ['build_fake_docx']。

    **Step J — tests/unit/test_word_pii_pipeline.py 5 个测试类 RED 骨架**（NEW 文件）。模块 docstring "Phase 3 Word 端到端 PII 流程测试（D-13 — 79/79 升级 88/88）"。import：unittest / os / tempfile / from docx import Document / from privacyguard.pii.engine import PIIEngine / from privacyguard.pii.hits import TextUnit, PIIHit / from privacyguard.pii.mask import mask_for_entity / from tests.fixtures.fake_pii import fake_id_card, fake_phone, fake_email, fake_bank_card, fake_uscc, fake_vat_invoice_20, fake_bank_account / from tests.fixtures.fake_word import build_fake_docx。本任务实现以下 5 个测试类的方法签名（函数体用 self.fail 或 assert False 标 RED）：

    TestWordAdapterCollectUnits.test_collect_units_returns_text_unit_per_block：调 build_fake_docx(paragraphs=["段落 0", "段落 1"]) → 调 WordAdapter.collect_units(path) → 断言 len(units) >= 2 + key_index 同步。本任务标 RED（NotImplementedError）。

    TestWordPIIAutoTrigger.test_engine_detects_pii_in_word_text：构造 text = f"身份证 {fake_id_card()} 手机 {fake_phone()} 邮箱 {fake_email()} 卡号 {fake_bank_card()} USCC {fake_uscc()} 发票 {fake_vat_invoice_20()} 账号 {fake_bank_account()}" → engine = PIIEngine() → hits = engine.detect(TextUnit(page_index=0, text=text, source='text')) → entity_types = {h.entity_type for h in hits} → 断言 len(entity_types) >= 6 + CN_ID_CARD / CN_PHONE / CN_EMAIL / CN_BANK_CARD / CN_USCC 全部命中。本任务标 RED（fake_vat_invoice_20 / fake_bank_account 已就位 — 直接 import）。

    TestWordRedactRoundTrip.test_redact_word_partial_mask_visible：从 main import merge_word_matches_with_priority / from privacyguard.word.redact import redact_word / from privacyguard.word.clear_doc_props import clear_word_doc_props。secret_id = fake_id_card() → path = build_fake_docx(paragraphs=[f"原文 {secret_id}"]) → word_data = {"paragraph_0": {"text": f"原文 {secret_id}", "ocr": [], "manual": [], "pii": []}} → engine = PIIEngine() → hits = engine.detect(TextUnit(page_index=0, text=word_data["paragraph_0"]["text"], source='text')) → word_data["paragraph_0"]["pii"] = hits → doc = Document(path) → merged = merge_word_matches_with_priority(word_data["paragraph_0"]["text"], rules=[], default_replacement_text="[已脱敏]", manual_matches=[], ocr_matches=[], pii_matches=hits) → redact_word(doc, "paragraph_0", merged) → clear_word_doc_props(doc) → tempfile.NamedTemporaryFile 写 out_path → doc.save(out_path) → out_doc = Document(out_path) → out_text = "".join(p.text for p in out_doc.paragraphs) → 断言 self.assertNotIn(secret_id, out_text) + self.assertIn(mask_for_entity("CN_ID_CARD", secret_id), out_text)。本任务标 RED（redact_word / clear_word_doc_props 抛 NotImplementedError）。

    TestWordDocumentPropertiesCleared 含 2 个方法：(a) test_clear_core_5_fields_always_succeeds：path = build_fake_docx(paragraphs=["test"]) → doc = Document(path) → 5 字段写敏感字符串 → clear_word_doc_props(doc) → 写 out_path → out_doc = Document(out_path) → 断言 5 字段全部 == ""。本任务标 RED。(b) test_clear_revision_set_to_1：path = build_fake_docx(paragraphs=["test"]) → doc = Document(path) → doc.core_properties.revision = 99 → clear_word_doc_props(doc) → 断言 doc.core_properties.revision == 1。本任务标 RED。

    TestWordMergePriorityRulePiManualOcr 含 2 个方法：(a) test_rule_beats_pii：构造 PIIHit + rules=[{"enabled": True, "mode": "exact", "find": "张三", "replace": "[姓名]"}] → merged = merge_word_matches_with_priority(text, rules, "[已脱敏]", manual_matches=[], ocr_matches=[], pii_matches=[hit]) → 断言 len(merged) == 2 + merged[0]["source"] == "rule" + merged[1]["source"] == "pii"。本任务标 RED。(b) test_pii_beats_manual_on_overlap：构造 PIIHit + manual = [{"start":0,"end":18,"text":secret_id,"replacement":"[手动]"}] → merged = merge_word_matches_with_priority(text, [], "[已脱敏]", manual_matches=manual, ocr_matches=[], pii_matches=[hit]) → 断言 len(merged) == 1 + merged[0]["source"] == "pii"。本任务标 RED。

    **Step K — main.py 函数签名扩展（Wave 1 仅扩展；Wave 2 启用）**（MODIFY）。本任务**仅做函数签名与占位扩展，不破坏现有 _save_word 路径**（per BLOCKER 6）：

    (a) main.py:10777 _open_word_docx 内 word_data 初始化完成后（紧接 self._reset_batch_session_state() 与 self.word_compare_mode = False 之间），插入：
    ```python
    # Phase 3 (03-word) — Wave 1 RED 占位 — Wave 2 实施 WordPIIWorker 启动
    self._word_pii_worker = None
    ```

    (b) main.py 在 _on_pii_page_result 后（约 main.py:11521 后）新增 _on_word_pii_page_result 占位方法（Wave 1 仅函数签名，函数体仅 print 占位；**不**抛 NotImplementedError —— 避免 worker signal 接不上导致主线程抛 RuntimeError；Wave 2 实施真实业务）：
    ```python
    def _on_word_pii_page_result(self, key: str, hits_data: list):
        """Phase 3: pii_signal 接收槽（D-09 / D-18 — Wave 1 占位，Wave 2 实施）"""
        # Wave 1 占位：仅记录，不写 word_data（避免破坏既有 _save_word 行为）；Wave 2 实施 QMutexLocker 写 + _apply_word_pii_panel_updates
        print(f'[Word PII STUB] key={key} hits_count={len(hits_data)}')
    ```

    (c) main.py:863 merge_word_matches_with_priority 函数签名扩展 — 第六参数 pii_matches=None（默认值保持 back-compat），函数体**保持现状**（不引入 pii 优先级处理 — Wave 2 实施）。扩展后签名：`def merge_word_matches_with_priority(text, rules, default_replacement_text, manual_matches=None, ocr_matches=None, pii_matches=None):`。**关键**：本步骤 Wave 1 不引入 _append_candidates(pii_matches, "pii") 调用，避免破坏既有 priority；Wave 2 GREEN 启用 pii 路径。**优先 _save_word 中 merge_word_matches_with_priority 调用暂不传 pii_matches**（per BLOCKER 6）。

    (d) main.py:12699 _save_word 内 paragraphs 循环 + tables 循环（main.py:12715-12766）merge_word_matches_with_priority 调用**保持现状**（不传 pii_matches — Wave 1 沿用既有路径）；`replace_matches_in_paragraph(para, merged_matches, text_offset=0, fallback_replacement_text=self.replacement_text)` 这一调用**保持现状**（不改为 redact_word 路径 —— Wave 1 RED 不破坏 runtime；Wave 2 GREEN 启用）。**不**在 `new_doc.save(fname)` 前插入 clear_word_doc_props 调用（Wave 1 不启用；Wave 2 启用）。

    **Step L — 双 spec PyInstaller hiddenimports parity**（MODIFY — per cp30 教训扩展）。

    - `packaging/windows/config/PrivacyGuard_windows.spec`（Phase 2 既有 13 项 PII hiddenimports 段 + 既有 hiddenimports 列表段 双段）追加 6 项：`'privacyguard.word', 'privacyguard.word.adapter', 'privacyguard.word.worker', 'privacyguard.word.redact', 'privacyguard.word.clear_doc_props', 'privacyguard.word.candidate_dialog'`。
    - `packaging/macos/config/PrivacyGuard.spec`（Phase 2 既有 13 项 PII hiddenimports 单段）追加同样 6 项。
    - 双 spec 字段级一致（cp30 教训扩展）。

    **Step M — 验证 RED 基线**（per BLOCKER 6 RED 不破坏 runtime 验证）。运行命令：
    ```bash
    set -o pipefail
    python3 -m compileall -q main.py privacyguard tests && \
    python3 -m unittest tests.unit.test_word_pii_pipeline -v 2>&1 | tail -25
    ```
    期望看到 5 个测试类全部以 ERROR 或 FAIL 形式报告（NotImplementedError 或 ImportError 或 AttributeError）—— RED 状态确认。运行 `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence -v` 期望既有基线保持 GREEN（merge_word_matches_with_priority 第六参数默认值 back-compat 验证 + _save_word 既有路径未破坏）。
  </action>
  <verify>
    <automated>set -o pipefail; python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline -v 2>&1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m compileall -q main.py privacyguard tests` 退出码 0（语法全部 GREEN，所有 NEW 文件 + MODIFY 文件无 SyntaxError）。
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v` 显示 5 个测试类（TestWordAdapterCollectUnits / TestWordPIIAutoTrigger / TestWordRedactRoundTrip / TestWordDocumentPropertiesCleared / TestWordMergePriorityRulePiManualOcr）共 7 个测试方法全部以 ERROR 或 FAIL 形式报告 —— RED 基线确认（NotImplementedError 或 KeyError 或 AttributeError）。
    - `python3 -c "from privacyguard.word import WordAdapter, redact_word, clear_word_doc_props, WordPIIWorker; print('OK')"` 成功 print OK（_LAZY_IMPORTS 路径打通，模块 import 不拉起 python-docx / mammoth）。
    - `python3 -c "import sys; import privacyguard.word; print('word.adapter' in sys.modules, 'word.worker' in sys.modules)"` 输出 False False（OPS-03 懒加载纪律 —— 子模块未在 import 时加载）。
    - `python3 -c "from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE; print(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'])"` 输出 ID（D-21 单一来源就位 + per BLOCKER 5 抽离）。
    - `grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec` 双 spec 各含 6 行命中（cp30 教训扩展字段级一致）。
    - `python3 -m unittest tests.unit.test_word_replace_rules.TestWordReplaceRules -v`（Phase 1 既有测试）保持 GREEN（merge_word_matches_with_priority 第六参数默认值 back-compat 验证）。
    - `python3 -m unittest tests.unit.test_batch_word_replace -v`（Phase 1 既有测试）保持 GREEN（merge_word_matches_with_priority back-compat 验证）。
    - `python3 -m unittest tests.unit.test_convergence -v`（Phase 1 既有测试）保持 GREEN（无新 main.py 内联实现）。
    - `python3 -m unittest tests.unit.test_package_imports -v`（Phase 1 既有测试）保持 GREEN（lazy-load 纪律不破坏）。
    - `python3 -c "from tests.fixtures.fake_word import build_fake_docx; p = build_fake_docx(); print('OK', p); import os; os.remove(p)"` 成功 print OK + 路径（fake_word fixture 落地）。
  </acceptance_criteria>
  <done>
    privacyguard/word/ 5 个文件就位（adapter / worker / redact / clear_doc_props 占位 NotImplementedError；__init__.py _LAZY_IMPORTS 完整）；privacyguard/pii/hits.py 9 短码字典 ENTITY_TYPE_SHORT_CODE 就位（per BLOCKER 5 抽离 main.py）；privacyguard/__init__.py 6 项 lazy forward 就位；tests/fixtures/fake_word.py build_fake_docx 完整实现；tests/unit/test_word_pii_pipeline.py 5 个测试类 7 个测试方法 RED 骨架就位；main.py 4 处扩展骨架就位（_open_word_docx 占位 / _on_word_pii_page_result 占位 / merge_word_matches_with_priority 第六参数 / _save_word 既有路径未破坏 per BLOCKER 6）；双 spec hiddenimports 字段级一致追加 6 项 privacyguard.word.*；所有 RED 测试失败原因可定位到具体 NotImplementedError 或 AttributeError。
  </done>
  <reversibility>rating="reversible" rationale="占位骨架 + fixture + 测试 + spec 扩展；Wave 2 在此基础实施真实业务，删除 RED 测试 + 占位即可恢复 v37.7.6 状态。"</reversibility>
</task>

<task type="auto" tdd="true">
  <name>GREEN Wave 1 — 实现 WordAdapter + WordPIIWorker + redact_word + clear_word_doc_props + main.py 接线</name>
  <files>
    - privacyguard/word/adapter.py
    - privacyguard/word/worker.py
    - privacyguard/word/redact.py
    - privacyguard/word/clear_doc_props.py
    - main.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-RESEARCH.md (lines 386-451 — WordAdapter.collect_units 完整代码示例 + key_index 双向映射语义)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1066-1119 — redact_word 完整 wrapper 代码示例 + cell 多段 para_offset 累加逻辑)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1119-1172 — clear_word_doc_props 完整代码示例 + hasattr + try/except 防御)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1242-1304 — _on_word_pii_page_result + _apply_word_pii_panel_updates 完整示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1576-1641 — _save_word 完整集成代码示例)
    - .planning/phases/03-word/03-RESEARCH.md (lines 1174-1240 — merge_word_matches_with_priority 完整扩展代码示例 + PIIHit asdict 分派)
    - .planning/phases/03-word/03-PATTERNS.md (lines 16-37 — 7 NEW + 6 MODIFY 文件关键 excerpts)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 312-327 — Word 文档属性清除 8 字段锁)
    - main.py:863-906 (merge_word_matches_with_priority 当前实现 — _append_candidates 已存在)
    - main.py:965-1018 (replace_matches_in_paragraph + apply_range_to_runs 既有 run-level 替换 — D-23 复用)
    - main.py:10777-10819 (_open_word_docx 当前 word_data 段落 + 表格初始化 — 与 WordAdapter.collect_units 共享 key 命名)
    - main.py:11508 (_on_pii_page_result Phase 1 page_data 镜像 — QMutexLocker 形态)
    - main.py:12699-12794 (_save_word 当前 paragraphs + tables 遍历形态)
    - privacyguard/pii/hits.py (PIIHit 9 字段锁 — D-16 + page_rect Word 路径置占位 (0,0,0,0))
    - privacyguard/pii/engine.py (PIIEngine.detect format-agnostic 入口)
  </read_first>
  <action>
    Wave 1 GREEN 任务。本任务实现 4 个 privacyguard/word/ 子模块的真实业务逻辑 + main.py 4 处接线；目标让 tests/unit/test_word_pii_pipeline.py 5 个测试类 7 个方法全部 GREEN。

    **privacyguard/word/adapter.py 完整实现**（替换 Wave 1 NotImplementedError 占位）。模块顶部 `from typing import Dict, List, Tuple`；函数体内 lazy import `from docx import Document` 与 `from privacyguard.pii.hits import TextUnit`（保持 OPS-03 懒加载纪律）。实现 WordAdapter.collect_units(docx_path) 严格按 03-RESEARCH.md:1018-1064 模板：doc = Document(docx_path)；idx = 0；遍历 doc.paragraphs（para_idx, para）：text = para.text or ''；if not text.strip(): continue；units.append(TextUnit(page_index=idx, text=text, source='text'))；key_index[idx] = f'paragraph_{para_idx}'；idx += 1。遍历 doc.tables 三层循环：for table_idx, table in enumerate(doc.tables): for r_idx, row in enumerate(table.rows): for c_idx, cell in enumerate(row.cells): text = cell.text or ''；if not text.strip(): continue；units.append(TextUnit(page_index=idx, text=text, source='text'))；key_index[idx] = f'table_{table_idx}_cell_{r_idx}_{c_idx}'；idx += 1。return units, key_index。__all__ = ['WordAdapter']。**关键**：与 main.py:_open_word_docx:10797-10819 段落 + 表格初始化路径的 key 命名严格对齐（paragraph_{idx} / table_{t}_cell_{r}_{c}）。

    **privacyguard/word/worker.py WordPIIWorker 完整实现**（替换 NotImplementedError 占位）。模块顶部 `from PyQt6.QtCore import QThread, pyqtSignal` + `from dataclasses import asdict`（这两个是常驻模块级 import，允许）。类定义保留 Wave 1 的 pyqtSignal 三项 + __init__ 不变。实现 run() 方法：try: from privacyguard.pii.engine import PIIEngine（lazy import）；self._engine = PIIEngine()；for key, data in self._word_data.items(): text = data.get('text', '') or ''；if not text.strip(): continue；unit = TextUnit(page_index=0, text=text, source='text')；hits = self._engine.detect(unit, page=None)；self.pii_signal.emit(key, [asdict(h) for h in hits])；self.finished_signal.emit()。except Exception as e: self.error_signal.emit(type(e).__name__)；self.finished_signal.emit()；return。模块顶部 lazy import `from privacyguard.pii.hits import TextUnit`（允许 —— TextUnit 是 dataclass 容器）。__all__ = ['WordPIIWorker']。**关键**：page=None（D-17 锁 + engine._resolve_page_rect 在 page=None 时返回占位 (0,0,0,0) —— 与 Phase 1 既有的 fallback 形态一致）；asdict(h) for h in hits（D-18 + 跨线程 pyqtSignal 必须传 dict 列表）。

    **privacyguard/word/redact.py 完整实现**（替换 NotImplementedError 占位）。实现 redact_paragraph(para, matches, fallback_replacement_text='[已脱敏]')：函数体内 lazy import `from main import replace_matches_in_paragraph`（避免 privacyguard.word 拉起 12.9k LOC main.py）；直接透传 replace_matches_in_paragraph(para, matches, text_offset=0, fallback_replacement_text=fallback_replacement_text)。实现 redact_word(doc, key, merged_matches, fallback_replacement_text='[已脱敏]') 严格按 03-RESEARCH.md:1082-1117 模板：if not merged_matches: return；if key.startswith('paragraph_')：para_idx = int(key.split('_', 1)[1])；if para_idx >= len(doc.paragraphs): return: replace_matches_in_paragraph(doc.paragraphs[para_idx], merged_matches, text_offset=0, fallback_replacement_text=fallback_replacement_text)。elif key.startswith('table_')：parts = key.split('_')；if len(parts) != 5: return；t, r, c = int(parts[1]), int(parts[3]), int(parts[4])；if t >= len(doc.tables): return；table = doc.tables[t]；if r >= len(table.rows): return；cell = table.rows[r].cells[c]；para_offset = 0；paragraphs = list(cell.paragraphs)；for idx, para in enumerate(paragraphs): original_para_len = len(''.join(run.text for run in para.runs))；replace_matches_in_paragraph(para, merged_matches, text_offset=para_offset, fallback_replacement_text=fallback_replacement_text)；para_offset += original_para_len；if idx < len(paragraphs) - 1: para_offset += 1（python-docx cell.text 用换行拼接 —— main.py:12764-12766 同步）。__all__ = ['redact_word', 'redact_paragraph']。**关键**：lazy import inside function（D-23 + cp30 教训扩展）；cell 多段 para_offset 累加与 main.py:12753-12766 既有形态完全一致（D-23 复用）。

    **privacyguard/word/clear_doc_props.py 完整实现**（替换 NotImplementedError 占位）。模块顶部 `from typing import Final`（常驻允许）。CORE_PROPS_TO_CLEAR 5 字段 + APP_PROPS_TO_CLEAR 2 字段保留 Wave 1 Final 常量。实现 clear_word_doc_props(doc) 严格按 03-RESEARCH.md:1136-1172 模板：core = doc.core_properties；for prop_name in CORE_PROPS_TO_CLEAR：if prop_name == 'title': core.title = ''；elif prop_name == 'author': core.author = ''；elif prop_name == 'subject': core.subject = ''；elif prop_name == 'keywords': core.keywords = ''；elif prop_name == 'last_modified_by': core.last_modified_by = ''。if hasattr(core, 'revision'): core.revision = 1（**整数**，D-08 / D-24 锁）。if hasattr(doc, 'app_properties') and doc.app_properties is not None：app = doc.app_properties；for prop_name in APP_PROPS_TO_CLEAR：if hasattr(app, prop_name)：try: setattr(app, prop_name, '')；except (AttributeError, ValueError): pass（python-docx v0.8.10 以下版本只读防御）。__all__ = ['clear_word_doc_props', 'CORE_PROPS_TO_CLEAR', 'APP_PROPS_TO_CLEAR']。**关键**：revision 必须 int(1)（D-08 / D-24 锁）；5 个 core 字符串字段全部 ""（不写 "Anonymous" / "Redacted" 占位 —— D-15 锁）。

    **main.py 4 处接线**（完成 Wave 1 RED 占位 → GREEN）：

    (a) main.py:10777 _open_word_docx 内 WordPIIWorker 启动接线（替换 Wave 1 self._word_pii_worker = None 占位）：在 word_data 初始化完成后、self.word_compare_mode = self._has_word_replacement_candidates() 之前，插入：
    ```python
    # Phase 3 (03-word) — WordPIIWorker 自动启动（D-09）
    from privacyguard.word.worker import WordPIIWorker
    self._word_pii_worker = WordPIIWorker(self.word_data, parent=self)
    self._word_pii_worker.pii_signal.connect(self._on_word_pii_page_result)
    self._word_pii_worker.error_signal.connect(self._on_word_pii_scan_error)
    self._word_pii_worker.finished_signal.connect(self._on_word_pii_scan_complete)
    self._word_pii_worker.start()
    ```

    (b) main.py 新增 _on_word_pii_page_result 槽（替换 Wave 1 print 占位）实现：lazy import `from privacyguard.pii.hits import PIIHit`；hits = [PIIHit(**h) for h in hits_data]；with QMutexLocker(self._word_data_lock)：if key in self.word_data: self.word_data[key]['pii'] = hits；else: print(f'[Word PII WARN] key {key} not in word_data')；self._apply_word_pii_panel_updates(key, hits)（**注**：_apply_word_pii_panel_updates 在 Wave 2 实施 —— 本波调用为占位方法 stub，return None；Wave 2 在 main.py 内实现真实 runJavaScript 局部 patch）。

    (c) main.py 新增 _on_word_pii_scan_error + _on_word_pii_scan_complete 槽（替换 Wave 1 未实现的连接）：_on_word_pii_scan_error(exception_class)：self._word_pii_status_chip_set(f'Word 隐私识别 引擎初始化失败：{exception_class}。已自动关闭本会话识别。')。_on_word_pii_scan_complete()：调 self._refresh_word_pii_status_chip()（Wave 2 实施）。

    (d) main.py:863 merge_word_matches_with_priority 函数体扩展（替换 Wave 1 的 _append_candidates(pii_matches, "pii") 占位）：在函数体顶部 `pii_matches = pii_matches or []`；在 _append_candidates 内部新增 PIIHit dataclass 实例分派（03-RESEARCH.md:1191-1207 模板）：`if isinstance(item, PIIHit): start = item.page_offset; end = item.page_offset + item.page_length; replacement = item.mask_strategy or fallback_text; item = {'start': start, 'end': end, 'text': item.normalized, 'replacement': replacement, 'source': source_name, 'mode': 'global', 'rule_name': ''}`。模块顶部新增 `from privacyguard.pii.hits import PIIHit`（PIIHit 是 dataclass，常驻模块级 import 允许）。priority 顺序保持：`rule` → `pii` → `manual` → `ocr`（D-19 锁）。

    (e) main.py:12699 _save_word 接线完成：paragraphs 循环 + tables 循环内 `replace_matches_in_paragraph(para, ...)` 调用改为 `redact_word(new_doc, key, merged_matches, self.replacement_text)`（含 cell 多段循环 —— 把 paragraphs 循环的 replace_matches_in_paragraph 与 tables 循环的 cell 多段循环都改为 redact_word）。在 `new_doc.save(fname)`（main.py:12769）之前插入：`from privacyguard.word.clear_doc_props import clear_word_doc_props`（lazy import —— 函数顶部不允许）+ `clear_word_doc_props(new_doc)`。

    **验证 GREEN**。运行命令 `python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline -v 2>&1 | tail -15` 期望 5 个测试类 7 个测试方法全部 OK。运行 `python3 -m unittest tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports -v` 验证既有基线保持 GREEN。运行 `python3 -c "import sys; import privacyguard; print('word' in sys.modules, 'word.adapter' in sys.modules, 'word.worker' in sys.modules)"` 输出 True False False（OPS-03 验证 —— privacyguard.word 子包已 import 但子模块未加载）。
  </action>
  <verify>
    <automated>set -o pipefail; python3 -m compileall -q main.py privacyguard tests && python3 -m unittest tests.unit.test_word_pii_pipeline tests.unit.test_word_replace_rules tests.unit.test_batch_word_replace tests.unit.test_convergence tests.unit.test_package_imports -v 2>&1 | tail -15</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m unittest tests.unit.test_word_pii_pipeline -v` 显示所有 7 个测试方法（test_collect_units_returns_text_unit_per_block / test_engine_detects_pii_in_word_text / test_redact_word_partial_mask_visible / test_clear_core_5_fields_always_succeeds / test_clear_revision_set_to_1 / test_rule_beats_pii / test_pii_beats_manual_on_overlap）全部 OK —— GREEN 状态确认。
    - TestWordRedactRoundTrip.test_redact_word_partial_mask_visible 断言 out_text 不含 secret_id + 含 mask_for_entity("CN_ID_CARD", secret_id) 字符串（reverse-extraction SAFE-02 + MASK-01 partial mask 落地）。
    - TestWordDocumentPropertiesCleared.test_clear_core_5_fields_always_succeeds 断言 out_doc.core_properties.title / author / subject / keywords / last_modified_by 全部等于 ""（D-08 SAFE-03 锁）。
    - TestWordDocumentPropertiesCleared.test_clear_revision_set_to_1 断言 doc.core_properties.revision == 1（D-08 revision int 字段锁）。
    - TestWordMergePriorityRulePiManualOcr.test_rule_beats_pii 断言 merged[0]["source"] == "rule" + merged[1]["source"] == "pii"（D-19 priority 锁 —— rule 比 pii 高优先级且不重叠）。
    - TestWordMergePriorityRulePiManualOcr.test_pii_beats_manual_on_overlap 断言区间重叠时 pii 命中保留，manual 命中被 skip（D-19 priority 锁 —— pii 比 manual 高优先级且重叠）。
    - 既有 11 unittest 模块基线全部 GREEN —— merge_word_matches_with_priority 第六参数 back-compat 验证。
    - `python3 -c "import sys; import privacyguard; print('word' in sys.modules, 'word.adapter' in sys.modules, 'word.worker' in sys.modules, 'word.redact' in sys.modules, 'word.clear_doc_props' in sys.modules)"` 输出 True False False False False（OPS-03 懒加载纪律 —— 子模块未在 import 时加载）。
    - `python3 -m compileall -q main.py privacyguard tests` 退出码 0（全部语法 GREEN）。
  </acceptance_criteria>
  <done>
    privacyguard/word/adapter.py WordAdapter.collect_units 完整实现并与 main.py:_open_word_docx key 命名一致；privacyguard/word/worker.py WordPIIWorker.run() 完整实现并通过 asdict(h) 跨线程送 PIIHit；privacyguard/word/redact.py redact_word wrapper 完整实现并 lazy import main.py:replace_matches_in_paragraph；privacyguard/word/clear_doc_props.py clear_word_doc_props 完整实现并写 5 core 字符串 + revision=1 + 2 app 字段；main.py 4 处接线完成（_open_word_docx 自动启动 / _on_word_pii_page_result QMutexLocker 写 / merge_word_matches_with_priority PIIHit 分派 / _save_word 扩 pii_matches + redact_word + clear_word_doc_props）；5 个测试类 7 个测试方法全部 GREEN；既有 11 unittest 模块基线保持 GREEN；OPS-03 懒加载纪律保持。
  </done>
  <reversibility>rating="costly" rationale="5 个模块文件落地 + main.py 4 处接线落地；删除需恢复既有基线 + RED 占位。"</reversibility>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Wave 1 人工验证 — 打开 docx 自动识别 + 双栏占位 + 文档属性清除在真实 UI 中无回归</name>
  <files>
    - main.py
  </files>
  <read_first>
    - .planning/phases/03-word/03-RESEARCH.md (lines 95-110 — Phase 3 最高风险清单)
    - .planning/phases/03-word/03-RESEARCH.md (lines 833-846 — Pitfall 1 Word run-boundary fragmentation)
    - .planning/phases/03-word/03-RESEARCH.md (lines 943-957 — Pitfall 7 _word_data_lock 并发安全)
    - .planning/phases/03-word/03-UI-SPEC.md (lines 290-308 — wordPiiStatusChip 状态机 7 阶段)
    - .planning/phases/03-word/03-VALIDATION.md (lines 80-91 — Manual-Only Verifications)
    - main.py:10777-10819 (_open_word_docx 当前接线)
    - main.py:11602-11616 (QMutexLocker 既有 word_data 写形态)
  </read_first>
  <what-built>
    Wave 1 GREEN 任务实施完成后：privacyguard/word/ 子包 5 模块（adapter / worker / redact / clear_doc_props）落地；main.py 4 处接线（_open_word_docx 自动启动 WordPIIWorker / _on_word_pii_page_result 槽 / merge_word_matches_with_priority 第六参数 pii_matches / _save_word 扩 redact_word + clear_word_doc_props）；privacyguard/pii/hits.py ENTITY_TYPE_SHORT_CODE 9 短码字典就位（per BLOCKER 5 单一来源）；packaging/{windows,macos}/*.spec 字段级一致追加 6 项 privacyguard.word.* hiddenimports（cp30 教训扩展）；tests/unit/test_word_pii_pipeline.py 5 个测试类 7 个测试方法 GREEN；既有 11 unittest 模块基线保持 GREEN。
  </what-built>
  <how-to-verify>
    **步骤 1 — 启动应用**：`cd /mnt/g/Project/PrivacyGuard && python3 main.py`

    **步骤 2 — 构造含 PII 的 docx**：`python3 -c "from tests.fixtures.fake_word import build_fake_docx; p = build_fake_docx(); print(p)"`（输出路径用作 Open 菜单输入）

    **步骤 3 — 主菜单 → Open → 选择上面合成的 docx**

    **步骤 4 — 观察状态栏 wordPiiStatusChip**：文本依次 `正在抽出 Word 段落文本…` → `扫描 Word 文本层…` → `扫描完成：未发现敏感内容` 或 `已识别 N 项敏感内容`（Wave 1 仅占位 emit；Wave 2 完整实施）。info_bar 中 wordPiiStatusChip 与 Phase 1 `piiStatusChip`（PDF）共存且无样式冲突。

    **步骤 5 — 切换到对比模式**：左栏仅显示原文（**不**含 PII `<mark>` 高亮 —— Wave 2 实施 cp27 局部 patch）；右栏仅显示原文（**不**含 partial mask —— Wave 2 实施）。**期望**：UI 流程不卡死、不抛异常、不破坏 Phase 1/2 既有双栏对比预览的滚动 / 缩放行为。

    **步骤 6 — 保存（Ctrl+S）→ 选择输出路径 → 等待保存完成 → 弹出"文件已保存至：{fname}"对话框**

    **步骤 7 — 验证文档属性清除**：`python3 -c "from docx import Document; d = Document('{fname}'); print('title=', repr(d.core_properties.title), 'author=', repr(d.core_properties.author))"` 验证 5 core 字段全部空字符串；`unzip -p {fname} docProps/core.xml | head -20` 应看不到原始敏感 title / author 字符串。

    **步骤 8 — 重新打开**：关闭 app；重新启动；再次打开同一 docx；确认 _on_word_pii_page_result 不抛 KeyError 或 RuntimeError。

    **通过条件**：步骤 4 chip 切换不抛异常；步骤 5 对比模式 UI 不卡死；步骤 6 保存流程完整跑通；步骤 7 输出 docx 的 core_properties.title / author / subject / keywords / last_modified_by 全部等于 ""，revision 等于 1；步骤 7 docProps/core.xml 中无原文敏感字串残留；步骤 8 重新打开不抛异常。

    **不通过条件**（任一即触发 Wave 2 修复）：状态栏 chip 抛 RuntimeError 或 AttributeError；对比模式切换后 UI 卡死（> 5 秒不响应）；保存过程抛 PermissionError 或 KeyError；导出的 docx 仍含原始 title / author 字符串；docProps/core.xml 中含原文敏感字符串；重新打开后 _on_word_pii_page_result 抛 KeyError 或 RuntimeError。
  </how-to-verify>
  <action>
    阻塞型 checkpoint：等待用户回复 "approved" 或失败步骤与异常信息。Wave 1 GREEN 任务已完成 5 个 privacyguard/word/ 子模块落地 + main.py 4 处接线 + 5 个测试类 GREEN + 既有 11 unittest 模块基线保持。本任务仅观察 UI 行为，不修改代码。
  </action>
  <resume-signal>Type "approved" to proceed to Wave 2 / Wave 3, or describe the failing step + exception details to trigger Wave 1 GREEN fix.</resume-signal>
  <verify>
    <automated>echo '人工验证 checkpoint — 阻塞型门禁，需用户输入 approved 后 Wave 2 / Wave 3 才可启动'</automated>
  </verify>
  <acceptance_criteria>
    - 用户在 UI 验证步骤 1-8 全部通过，回复 "approved"
    - 若失败：用户报告具体失败步骤与异常信息，Wave 1 GREEN 任务需进一步修复
  </acceptance_criteria>
  <done>
    真实 PyQt6 UI 中打开 docx 后状态栏 chip 切换正常 + 双栏对比模式无回归 + 保存后文档属性清除生效 + 重新打开不抛异常；用户回复 "approved"；Wave 2 / Wave 3 可启动。
  </done>
  <reversibility>rating="reversible" rationale="UI 验证仅观察，不修改代码；如未通过，回到 Wave 1 GREEN 任务修复。"</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| docx file path input | 用户拖拽 / Open 菜单传入 .docx 路径；main.py:_open_word_docx 解析 word/document.xml；WordAdapter.collect_units 遍历 paragraphs + tables；恶意 XML / 超大文档走既有 validate_safe_path + TempFileManager 防御 |
| WordPIIWorker QThread → MainWindow 主线程 | pyqtSignal 跨线程传 (key, hits_dict_list)；主线程 _on_word_pii_page_result 反序列化为 PIIHit；QMutexLocker 保护 word_data 写 |
| redact_word wrapper → main.py 模块级函数 | redact_word 内部 import main.py:replace_matches_in_paragraph；隐私导入风险；必须 lazy import inside function |
| clear_word_doc_props → python-docx core_properties / app_properties | app_properties 在 python-docx v0.8.10 以下版本只读 / 不可用；需 hasattr + try/except 防御 |
| PyInstaller frozen build → privacyguard.word.* | 缺 hiddenimports 时 cp30 教训复现 ModuleNotFoundError；packaging/{windows,macos}/config/*.spec 必须字段级一致 |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-03-WordRunBoundary | Information Disclosure | privacyguard/word/redact.py::redact_word | high | mitigate | 沿用 main.py:replace_matches_in_paragraph 既有 run-level 替换；tests/unit/test_word_pii_pipeline.py::TestWordRedactRoundTrip 构造 18 位身份证 + 调 redact_word + 反向断言 Document(out).paragraphs[*].text 不含原文（SAFE-02 reverse-extraction） |
| T-03-DocPropsLeak | Information Disclosure | privacyguard/word/clear_doc_props.py::clear_word_doc_props | high | mitigate | 5 core 字符串字段 + revision=1 + 2 app 字段；TestWordDocumentPropertiesCleared 写含 PII 元数据 → clear → 反向断言 5 字段全部 == "" |
| T-03-PIIAutoTrigger | Tampering / UX | main.py::_open_word_docx | medium | mitigate | WordPIIWorker.start() 紧接 word_data 初始化后调；TestWordPIIAutoTrigger 断言 worker run() 后 word_data[key]["pii"] 非空 |
| T-03-MergePriority | Tampering / false positive | main.py:merge_word_matches_with_priority | medium | mitigate | priority 锁定 rule > pii > manual > ocr；TestWordMergePriorityRulePiManualOcr 覆盖重叠区间 pii 覆盖 manual + rule 不被 pii 覆盖两种场景 |
| T-03-LazyImport | Denial of Service / OPS-03 | privacyguard/word/__init__.py | medium | mitigate | _LAZY_IMPORTS + __getattr__ 严格 lazy-load；test_package_imports 断言 sys.modules 中无 privacyguard.word 子模块 |
| T-03-RealPiiInFixture | Repudiation / OPS-05 | tests/fixtures/fake_word.py | high | mitigate | build_fake_docx 仅调 tests/fixtures/fake_pii.py 既有 Faker 合成器；test_word_pii_pipeline.py 末尾断言 fixture 不含真实身份字符串字面量 |
| T-03-PyInstallerHiddenimports | Denial of Service / cp30 | packaging/{windows,macos}/config/*.spec | high | mitigate | 双 spec 字段级一致追加 6 项 privacyguard.word.* hiddenimports；Wave 1 Step L 落地 |
| T-03-RevisionType | Information Disclosure / ValueError | privacyguard/word/clear_doc_props.py | medium | mitigate | revision 字段单独分支处理为 int(1)；core 字符串字段置空字符串；app_properties 走 hasattr + try/except |
| T-03-WordDataRace | Information Disclosure / race | WordPIIWorker + _save_word | medium | mitigate | _on_word_pii_page_result 必须 QMutexLocker(self._word_data_lock) 写 word_data[key]["pii"]；_save_word 读 word_data 时同样加锁 |
| T-03-ShortCodeSourceOfTruth | Tampering / D-21 single-source violation | privacyguard/pii/hits.py + main.py | medium | mitigate | per BLOCKER 5：ENTITY_TYPE_SHORT_CODE 9 短码字典唯一来源位于 privacyguard/pii/hits.py；main.py 与 privacyguard/word/candidate_dialog.py 均从此 import；test_convergence AST 断言 main.py 不内联 9 短码字面量 |

</threat_model>

<verification>
完整 Phase 3 验收命令（CLAUDE.md §基线）：
```bash
set -o pipefail
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
      tests.unit.test_word_pii_pipeline \
      -v
```
期望全部 OK；tests.unit.test_word_pii_pipeline 7 个测试方法全 GREEN，11 个基线模块保持 GREEN。

Wave 1 单独门禁：
```bash
set -o pipefail
python3 -m unittest tests.unit.test_word_pii_pipeline.TestWordPIIAutoTrigger tests.unit.test_word_pii_pipeline.TestWordRedactRoundTrip tests.unit.test_word_pii_pipeline.TestWordDocumentPropertiesCleared -v
```
期望 4 个测试方法 OK（test_engine_detects_pii_in_word_text / test_redact_word_partial_mask_visible / test_clear_core_5_fields_always_succeeds / test_clear_revision_set_to_1）。

辅助验证：
```bash
# ENTITY_TYPE_SHORT_CODE 单一来源（per BLOCKER 5）
python3 -c "from privacyguard.pii.hits import ENTITY_TYPE_SHORT_CODE; print(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'])"

# 双 spec PyInstaller hiddenimports parity（per cp30）
grep -E "privacyguard.word" packaging/windows/config/PrivacyGuard_windows.spec packaging/macos/config/PrivacyGuard.spec

# OPS-03 懒加载
python3 -c "import sys; import privacyguard; print('word.adapter:', 'privacyguard.word.adapter' in sys.modules)"
```
</verification>

<success_criteria>
- [ ] privacyguard/word/ 5 个模块文件落地（__init__.py / adapter.py / worker.py / redact.py / clear_doc_props.py），所有 lazy import 纪律保持
- [ ] privacyguard/pii/hits.py 新增 ENTITY_TYPE_SHORT_CODE 9 短码字典（per BLOCKER 5 单一来源抽离）
- [ ] privacyguard/__init__.py _LAZY_IMPORTS 追加 5 项 Word 符号 + ENTITY_TYPE_SHORT_CODE 转发（6 项总）
- [ ] tests/fixtures/fake_word.py build_fake_docx 合成含 PII 的 docx
- [ ] tests/unit/test_word_pii_pipeline.py 5 个测试类 7 个测试方法全部 GREEN
- [ ] 既有 11 unittest 模块基线（CLAUDE.md §基线）保持 GREEN
- [ ] OPS-03 懒加载纪律保持（import privacyguard 不拉起 privacyguard.word 子模块）
- [ ] D-05 v37.7.6 收敛原则保持（main.py 不含 redact_word / clear_word_doc_props 实现）
- [ ] D-08 文档属性清除 8 字段范围锁保持（5 core 字符串 + revision=1 + 2 app）
- [ ] D-19 priority 锁保持（rule > pii > manual > ocr；pii_matches 第六参数 back-compat）
- [ ] D-21 9 短码字典单一来源位于 privacyguard/pii/hits.py（per BLOCKER 5 抽离 main.py）
- [ ] D-23 redact_word 复用 main.py:replace_matches_in_paragraph（不重写 run-level 替换）
- [ ] D-24 clear_word_doc_props 紧邻 new_doc.save(fname) 前调
- [ ] D-26 双 spec hiddenimports 字段级一致 12 / 6 行（cp30 教训扩展）
- [ ] 真实 PyQt6 UI 验证通过（人工 checkpoint 8 步骤）
</success_criteria>

<output>
创建 `.planning/phases/03-word/03-01-tracer-SUMMARY.md` 当任务完成
</output>