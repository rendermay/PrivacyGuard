---
phase: GUI/API 重构
reviewers: [codex-failed, self-review-claude-v1, independent-subagent-v2-superpowers]
reviewed_at: 2026-08-29T22:55
plans_reviewed: [docs/planning/gui-api-refactor-plan.md]
models:
  codex: "deepseek-v4-pro (failed: PowerShell sandbox blocked + DLL load 0xc0000142)"
  self-review-claude-v1: "claude-opus-4-8 (fallback review)"
  independent-subagent-v2-superpowers: "general-purpose subagent (superpowers:requesting-code-review workflow)"
reviewer_status:
  codex: "FAILED — env"
  self-review-claude-v1: "OK"
  independent-subagent-v2-superpowers: "OK"
---

# Cross-AI Plan Review v2 — GUI/API 重构计划(superpowers:requesting-code-review)

## ⚠️ 评审完整性说明

**Codex CLI 实际跑失败**(PowerShell 沙箱 + DLL 加载失败)。

**REVIEWS-v1**:主会话 Claude 自评(fallback,对自己 plan 评审,对抗性较弱)。

**REVIEWS-v2(本文件)**:superpowers `requesting-code-review` 流程派独立 subagent 评审,使用 Read/Glob/Grep 工具访问项目源码,产出与 v1 对照的新发现。

---

# Independent Subagent Report

## Strengths

- **§2.3 任务 1.2 正确识别 3 个主链路可直接 wrapper**:`compute_doc_hash` (`secureredact/redaction/doc_hash.py:9`), `HitOverrideStore.filtered_hits` (line 139), `WordBatchReplaceWorker.__init__` (line 55) 三个函数确实签名简单且可作 wrapper 锚点
- **§2.7 Options 契约 (M-1 修复)**:明确列出 6 个合法 key + 类型 + 默认值,相比 v1 是显著改进
- **§2.3 任务 1.2 worker 同步化 (H-2 修复)**:给出 `QEventLoop + QTimer.singleShot` 具体代码示例,并清楚标识"Qt 主线程内可用"约束
- **§2.3 任务 1.2 `name_context_extra_tokens` 注入 (M-3 修复)**:符合 `ocr_worker.py:74` 注释提示
- **§2.4 acceptance `compute_doc_hash(Path("/tmp/a.pdf")) == compute_doc_hash("/tmp/a.pdf")` (H-3 修复)**:强制 Path 支持落到测试
- **§4.3 任务 0 新增 `test_main_shim_compat.py` 阶段前置 (H-4 修复)**:明确放在 P3 启动时新建
- **§0.3 D-01 revised 限制 `from main import` ≤ 2 (H-1 修复)**:给出具体上限
- **§3.7 准确区分 P3 与 B5/v1.1.17 (Q-3 缓解)**:与 CLAUDE.md:23 一致

---

## Issues

### Critical (would cause P1 to fail or break user code)

#### C-1. `WordBatchReplaceWorker` 存在隐藏命名错误未被发现,`batch_redact_word` 直接引爆

- **Section:** §2.3 任务 1.2
- **Claim being verified:** "batch_redact_word → wrapper secureredact.workers.word_batch_replace_worker.WordBatchReplaceWorker"
- **What's actually wrong:** `secureredact/workers/word_batch_replace_worker.py:229` 函数体内引用 `_shared_convert_doc_to_docx(doc_path)`,但第 1–19 行所有 import 中**找不到 `_shared_convert_doc_to_docx` 的来源**。该符号实际定义在 `main.py:49`(`from secureredact.utils.doc_converter import convert_doc_to_docx as _shared_convert_doc_to_docx`)。也就是说,**当前 worker 模块在没有 `main.py` shim 时直接导入会 NameError** —— `.doc` 文件转换路径 100% 触发
- **Evidence:** `G:/Project/SecureRedact/secureredact/workers/word_batch_replace_worker.py:229` vs 文件顶部 1–19 行 import;`G:/Project/SecureRedact/main.py:49`
- **Fix:** P1 任务 1.2 必须先在 `word_batch_replace_worker.py` 顶部加 `from secureredact.utils.doc_converter import convert_doc_to_docx as _shared_convert_doc_to_docx`,把 main.py:49 同款 import 内联到 worker 模块

#### C-2. `QEventLoop` + `_wait_for_error_decision` 死锁风险未被分析

- **Section:** §2.3 任务 1.2
- **Claim being verified:** plan 用 `QEventLoop` + `QTimer.singleShot` 等 `WordBatchReplaceWorker.finished_signal` 实现同步化
- **What's actually wrong:** `word_batch_replace_worker.py:71-80` 显示 worker 的 `_wait_for_error_decision` 用 `threading.Event.wait(0.1)` 阻塞在 worker 线程里,等待 main thread 调用 `provide_error_decision`。API 调用方在 main thread 阻塞在 `loop.exec()`。当批处理中某文件出错:**worker 线程阻塞等决策;main thread 阻塞等 `finished_signal`;没有任何一方会主动调用 `provide_error_decision`,死锁**
- **Evidence:** `G:/Project/SecureRedact/secureredact/workers/word_batch_replace_worker.py:71-80`
- **Fix:** wrapper 中为 `_decision_event` 注册自动 fallback —— 超时 5 秒后默认决策 `"skip"`,或 wrapper 启动前 monkey-patch `provide_error_decision` 设为自动 skip

#### C-3. `QTimer.singleShot(timeout, loop.quit)` + worker 中断只在文件粒度生效

- **Section:** §2.3 任务 1.2 / §2.4 acceptance
- **Claim being verified:** "若 worker 仍在 isRunning() → requestInterruption() → 抛 WorkerCancelledError"
- **What's actually wrong:** `word_batch_replace_worker.py:95` 显示 `isInterruptionRequested()` 检查只在 `for idx, file_path in enumerate(self.file_paths)` 循环顶部;`_process_single_file` 内部(包含 `doc.save()`、可能的 OCR/转换调用)不会响应中断。单个大文件 `python-docx` save 可能耗时数十秒,**实际超时远超 `timeout_sec`**
- **Evidence:** `G:/Project/SecureRedact/secureredact/workers/word_batch_replace_worker.py:95`、`:131-150`
- **Fix:** §2.4 acceptance 应增加"超时硬上限 = `timeout_sec + max(单文件处理时长)`",或文档明示"超时按文件粒度生效"

### Important (should fix before P1 starts)

#### I-1. plan 头部版本号与 version.txt 不一致

- **Section:** 文件头 `适用版本: v1.1.12 → v1.1.16`
- **Claim being verified:** 计划跨 v1.1.12 → v1.1.16 共 4 个 minor
- **What's actually wrong:** `version.txt` 当前是 `1.1.13`,且 git log 显示最新 commit 已提交 v1.1.14 (PR-C1/C2/C3)。plan 在 2026-08-29 写作时若按 v1.1.12 起算已经过时;按 v1.1.13 起算则 §3.7"v1.1.17 / B5"距离更远
- **Evidence:** `G:/Project/SecureRedact/version.txt` 内容 = `1.1.13`
- **Fix:** 把头部改成 `v1.1.13 → v1.1.17 (路线图)`;或者在 §0.1 注明"以写作时 version.txt 为准"

#### I-2. M3 acceptance grep 命令漏掉了 `secureredact/api.py`

- **Section:** §7.2 (M3) + §9.2
- **Claim being verified:** "P3 完成 = `grep -rn "from main import" secureredact/ui/` → 0 命中"
- **What's actually wrong:** §0.3 D-01 明确允许 `secureredact/api.py` 在 P1 阶段使用临时 `from main import X`,D-01 修订要求 ≤ 2 per function。但 §7.2 M3 仅 grep `secureredact/ui/`,**api.py 自身的 `from main import` 没有清理验收**
- **Evidence:** plan §7.2 M3 行;plan §0.3 D-01 表
- **Fix:** §7.2 M3 acceptance 改成 `grep -rn "from main import" secureredact/ui/ secureredact/api.py` → 0 命中

#### I-3. §5.2 测试矩阵内部矛盾

- **Section:** §5.2 表 + §5.3 任务 4.2
- **Claim being verified:** §5.2 表格写"GUI mixin 层" smoke 包含"仅 import + 实例化";§5.3 任务 4.2 明确写"不实例化(避免依赖 QApplication)"
- **What's actually wrong:** 两者直接矛盾
- **Evidence:** plan §5.2 表 vs §5.3 任务 4.2
- **Fix:** §5.2 表中 GUI 行改成 "smoke | 仅 import";或 §5.3 任务 4.2 改成"使用 `QApplication([]) offscreen mode` 实例化"

#### I-4. §5.4 acceptance 与 §5.3 任务 4.3 marker 顺序倒置

- **Section:** §5.4 acceptance
- **Claim being verified:** "`pytest -m api` 覆盖率 ≥ 100%"
- **What's actually wrong:** `pytest -m api` 依赖 `pytest.ini` 中 `markers = api:...` 配置,而该配置由 §5.3 任务 4.3 在 P4 末尾才建立。验收测试在配置之前使用 marker,CI 会失败 "unknown marker"
- **Evidence:** plan §5.4 vs §5.3 任务 4.3
- **Fix:** 把 §5.3 任务 4.3 (pytest.ini) 提到任务 4.1 之前;或者验收命令改成具体文件路径 `pytest tests/unit/test_api.py`

#### I-5. `compute_doc_hash` Path wrapper 内部必须 `os.fspath()` 但 plan 没写测试断点

- **Section:** §2.3 任务 1.2 + §2.4 acceptance
- **Claim being verified:** wrapper 内部 `os.fspath()` 归一化
- **What's actually wrong:** 当前实现 (`secureredact/redaction/doc_hash.py:20-21`) 用 `os.stat(file_path)` 和 `f"{file_path}\n{...}"`。如果调用方传 `Path("a").resolve()`,两次调用可能产生不同 path 字符串,hash 也会不同。§2.4 acceptance 只测 `Path("/tmp/a.pdf") == "/tmp/a.pdf")` —— 两种写法在 `os.fspath()` 后都是 `/tmp/a.pdf`,恰好通过。**但没测 `Path("./a.pdf") == Path("a.pdf").resolve()` 这种真实歧义**
- **Evidence:** `G:/Project/SecureRedact/secureredact/redaction/doc_hash.py:20-21`
- **Fix:** §2.4 acceptance 补充测试 `compute_doc_hash(Path("a.pdf").resolve()) == compute_doc_hash("a.pdf")`(前提:先确保 a.pdf 存在否则 OSError)

#### I-6. plan §2.3 任务 1.2 没回答 "scan_word 是同步还是异步"

- **Section:** §2.3 任务 1.2
- **Claim being verified:** "scan_word → secureredact.workers.word_worker.WordWorker.run 内核心算法"
- **What's actually wrong:** `WordWorker` 也是 `QThread`,`WordWorker.run()` 在 worker 线程跑。scan_word 是 API 函数,需同步返回。如果 scan_word 调用 `WordWorker.run()` 直接 wrapper 等于阻塞主线程 —— 而 `WordWorker` 启动需要 Qt 主线程信号绑定模式。plan 没说明是新建一次性 worker.run 后 `.wait()` 阻塞,还是用同样 QEventLoop 模式
- **Evidence:** `G:/Project/SecureRedact/secureredact/workers/word_worker.py`(QThread 子类)
- **Fix:** §2.3 任务 1.2 补充 "scan_word/redact_word 内部同样用 QEventLoop 模式" 或 "scan_word 直接实例化 `WordWorker.run()` 后丢弃 worker 对象(仅复用算法),输出同步返回"

#### I-7. `use_enhance` 在 WordWorker 缺位时仍属 Options key,但 plan 不区分 PDF/Word 入参

- **Section:** §2.7
- **Claim being verified:** Options key 通用 6 个
- **What's actually wrong:** 5 个 API 函数签名都接受 `options: Optional[Dict[str, Any]]`,但 `use_enhance` 实际上与 Word 端 `redact_word`/`batch_redact_word` 无关 —— Word worker 没有 use_enhance 参数。如果 `use_enhance=True` 传到 redact_word,应该忽略还是抛错?plan 没规定
- **Evidence:** `G:/Project/SecureRedact/secureredact/workers/word_worker.py:35`(WordWorker 无 `use_enhance`);OCR worker:55 有 `use_enhance`
- **Fix:** §2.7 增加备注列"适用 API 函数":`use_enhance` 仅 `scan_pdf`/`redact_pdf` 消费;其它函数传 `use_enhance=True` 视为 ignored。其它 key 同样按需标注

### Minor (nice to have)

- **m-1:** §3.2 表中 `pdf_render.py` 当前直接 import 写的是 `secureredact.redaction.black_white_list_store`,但实际 grep 显示 `pdf_render.py:68` import 的是 `ZOOM_MIN`/`ZOOM_MAX`
- **m-2:** §3.6 验收"完整回归套件通过"无具体命令(REVIEWS L-2 未修)
- **m-3:** §6.2 CLI `--rules '{"phone": "..."}'` 在 Windows CMD 下 escape 不友好(REVIEWS L-1 未修)
- **m-4:** §2.4 acceptance `scan_pdf(<5MB) < 1.5s` 没有 5MB 测试 PDF
- **m-5:** `filter_hits_by_overrides` ValueError message 未指定
- **m-6:** §2.4 acceptance 批处理"2 个测试文件"未指定为 `.docx`

---

## Cross-Check vs Prior REVIEWS

| Prior HIGH | v1.1 fix status | Evidence | New issue introduced by fix |
|------------|-----------------|----------|----------------------------|
| H-1 wrapper 矛盾 | **Yes** — §0.3 D-01 + §2.4 给出 ≤ 2/函数上限 | plan §34, §264 | I-2:grep acceptance 漏掉 `api.py` 自身 |
| H-2 worker 同步化 | **Partial** — §2.3 任务 1.2 给出 QEventLoop + QTimer 代码骨架,但未分析 `_wait_for_error_decision` 死锁(**C-2**)和中断粒度仅文件级(**C-3**) | plan §226-237 | 见 C-2/C-3 |
| H-3 compute_doc_hash Path | **Yes** — §2.3 任务 1.2 + §2.4 acceptance 用例齐备 | plan §85, §218, §265 | I-5:acceptance 测试未覆盖 `Path.resolve()` 真实歧义 |
| H-4 test_main_shim_compat 阶段 | **Yes** — §4.3 任务 0 改为 P3 启动前置 | plan §390-395 | 无 |

LOW (L-1, L-2, L-3) 三项 v1.1 均未修复(L-1: m-3;L-2: m-2;L-3: I-3 + I-4)

---

## NEW Issues vs Prior Review (highest-value)

v1 完全未发现)

1. **C-1**:`_shared_convert_doc_to_docx` 在 `word_batch_replace_worker.py` 内被引用但未 import
2. **C-2**:`QEventLoop` + `_wait_for_error_decision` 死锁,plan §2.3 任务 1.2 的 worker 同步化代码未覆盖的边界场景
3. **C-3**:`requestInterruption()` 在文件粒度生效,超时硬上限远大于 `timeout_sec`
4. **I-1**:plan 头部版本 `v1.1.12 → v1.1.16` 与 `version.txt` 当前 `1.1.13` 不符
5. **I-2**:M3 acceptance grep 命令漏掉 `secureredact/api.py` 自身
6. **I-6**:`scan_word` 同步/异步未明确
7. **I-7**:Options 6 个 key 的"适用 API 函数"矩阵缺失

---

## Recommendations (process improvements)

1. **P1 启动前强制 1 次 "wrapper smoke"**:先把 C-1 修掉,重跑 `tests/unit/test_batch_word_replace.py`
2. **P1 启动前在 `secureredact/api.py` 跑一次 grep "from main import" 阈值测试(≤ 14)作为 CI gate**
3. **把 plan §2.7 升级为"Options dict 矩阵表"**:6 key × 7 函数共 42 格
4. **把 `test_main_shim_compat.py` 的"待迁移符号清单"前置为 plan 附录 (§11)** 而不是 P3 阶段才建
5. **建议设立独立 PR-C4.0 "fix-up"**:把 C-1/C-2/C-3/I-1/I-2 一次性先 commit,再进 §2.3 任务 1.2 主体实现

---

## Assessment

**Ready to execute P1?** **No — With fixes**

**Reasoning:** 计划整体方向正确、结构清晰(v1.1 把 4 个 HIGH 都已落实或部分落实),但 **C-1/C-2/C-3 三条 Critical 必须在 P1 启动前解决** —— C-1 是必须先修的现存 bug,C-2/C-3 是 plan §2.3 任务 1.2 的实现骨架本身有缺陷。同时 I-1(版本号)、I-2(M3 acceptance 漏点)、I-6(scan_word 异步性)三项 Important 修正,否则 PR-C4 首次 review 就会被弹回。建议按 Recommendations #5 的"fix-up PR"模式,把 C-1~C-3 + I-1/I-2 一次性切到 v1.1.14-hotfix 后再进入 §2.3 任务 1.2 主体实现。

---

## 评审者元信息

| 字段 | 值 |
|------|---|
| 评审时间 | 2026-08-29T22:55 |
| 评审输入 | docs/planning/gui-api-refactor-plan.md (655 行 v1.1) |
| 评审方式 | superpowers:requesting-code-review(派 general-purpose subagent) |
| 工具访问 | Read/Glob/Grep(项目源码完整可读) |
| Evidence 数量 | 14 处 file:line 引用 |
| 与 v1 对照 | 4 HIGH 全验证 + 5 MEDIUM/LOW 未修 + 7 NEW |