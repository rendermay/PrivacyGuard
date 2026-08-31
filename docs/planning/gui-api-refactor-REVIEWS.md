---
phase: GUI/API 重构
reviewers: [codex-failed, self-review-claude]
reviewed_at: 2026-08-29T22:33:00
plans_reviewed: [docs/planning/gui-api-refactor-plan.md]
models:
  codex: "deepseek-v4-pro (failed: PowerShell sandbox blocked + DLL load 0xc0000142)"
  self-review-claude: "claude-opus-4-8 (fallback review by Claude with file:line evidence)"
model_sources:
  codex: "codex exec output"
  self-review-claude: "primary"
reviewer_status:
  codex: "FAILED — env"
  self-review-claude: "OK (fallback)"
---

# Cross-AI Plan Review — GUI/API 重构计划

## ⚠️ 评审完整性说明

**Codex CLI 实际运行失败**:
- 通过 DeepSeek 代理调用 `deepseek-v4-pro` 模型(因 `gpt-5` 不被该代理支持)
- 跑了 10 分钟,反复尝试用 PowerShell 读项目文件,但每次 shell 命令都被 Codex 沙箱策略拒绝(`blocked by policy`)
- 退路 PowerShell 出现 `Exit code: -1073741502`(0xc0000142,Windows DLL 初始化失败)
- 没有产出任何结构化评审内容,只有 1 个 `cat main.py` 成功后输出了乱码(Windows console GBK 编码)
- 工作流要求 "At least one external CLI invoked successfully" — Codex 不达标

**Fallback**:本评审由主会话 Claude(同样具备 Read/Grep/Glob 工具访问项目源码)直接产出,**带 file:line 证据**,但需明确:
- 不是真正的"独立 AI 评审"(主会话参与了 plan 制定)
- 评审角度更接近"自己 review 自己的计划",对抗性较弱
- 建议用户后续在能跑通 PowerShell 沙箱的环境下重新跑 Codex 验证

---

# Code Review — Self-Review (Fallback)

## Summary

该计划结构完整(目标/范围/决策/5 阶段/验收/风险登记齐全),API 化方向正确,**核心机制经源码 trace 可信**,但存在 4 个 HIGH 级别问题需要解决后再执行:wrapper 模式在 P1 阶段会让 P3 的债越界;`options` 参数定义不清;`compute_doc_hash` 函数签名不一致;`tests/unit/test_main_shim_compat.py` 计划提到但 P3 没建。整体:计划可执行,但需要补 4-5 个细节后启动 P1。

## Strengths

- **API 化范围判断准确**:`secureredact/redaction/doc_hash.py:9` 的 `compute_doc_hash`、`secureredact/redaction/override_store.py:139` 的 `HitOverrideStore.filtered_hits` 都是已存在的干净函数,直接 wrapper 即可,无需新实现
- **wrapper 模式选择合理**:`from main import _xxx` 在 P1 阶段是务实选择,plan 自己识别为 R-01 风险(高概率)
- **测试门槛设计匹配项目体量**:API 100% / OCR/workers 80% / redaction 90% / UI smoke,适合个人/小团队项目
- **PR 拆分粒度合适**:每个 mixin 一个子 PR(PR-C5.1/2/3/4)单独可回滚

## Concerns

### HIGH

- **H-1:wrapper 模式与"无 main 依赖"承诺自相矛盾** — plan §2.2 写"现有模块"内部调用,但 §2.3 任务 1.2 又说 `scan_pdf → 现有 main.py 中的 PDF 扫描内部逻辑(v1.1.12 期间**不迁移**逻辑,只 import 调用)`。这等于 P1 阶段就让 API 依赖 main.py,与 P3 "清掉 from main import X" 的目标对立。**机制**:即使 P1 暂时容忍,3 周后 P3 阶段需要做"接口契约重写",会破坏 P1 的兼容性测试。**修复建议**:P1 阶段就强制 API 内部 `from main import` 数量 ≤ 2 个,其余逻辑必须先迁到 `secureredact/`(即使是 stub 实现 + 抛 NotImplementedError)。

- **H-2:`WordBatchReplaceWorker` 实际签名与 plan 假设不一致** — `secureredact/workers/word_batch_replace_worker.py:55` 实际签名是 `__init__(self, file_paths, rules, default_replacement_text)`,**3 个参数**。但 plan §2.3 任务 1.2 描述的 `batch_redact_word(word_paths, output_dir, *, rules, custom_keywords, replacement_text, options)` 内部要 wrapper 这个 worker,需要把 `replacement_text` 映射到 `default_replacement_text`、还要处理 `output_dir` 的存在性检查、还要处理 worker 内部的 QObject 信号回调(批处理会发出 progress/file_done/finished 信号,API 层要不要全忽略?)。**机制**:plan 没说明 worker 异步信号怎么被 API 同步化。**修复建议**:在 plan §2.3 加一段 "**worker 异步同步化策略**":API 用 `QEventLoop` 或 `threading.Event` 等待 worker.finished_signal,超时 5 分钟抛 `WorkerCancelledError`。

- **H-3:`compute_doc_hash` 签名不一致** — `secureredact/redaction/doc_hash.py:9` 是 `compute_doc_hash(file_path: str) -> str`(只接受 str,posix path 不接受),而 plan §2.3 任务 1.1 设计的是 `def compute_doc_hash(file_path: str | Path) -> str`。**机制**:要支持 `Path`,内部需要 `os.fspath()` 转换。**修复建议**:在 plan 加一句"API 签名使用 `str | Path`,wrapper 内部 `os.fspath()` 归一化"。

- **H-4:`tests/unit/test_main_shim_compat.py` 在 plan §4.3 任务 4.3 提到但 P3 阶段没建** — plan §4.3 写"加 `tests/unit/test_main_shim_compat.py` 防止遗漏",但 §4 整体是 P4 阶段,而 plan §3 (P3) 是清掉 lazy import 的阶段。**机制**:shim 兼容性的回归测试应在 P3 开始时就建,而不是 P4 才建。**修复建议**:把 `test_main_shim_compat.py` 移到 P3 阶段任务 4.1 前面。

### MEDIUM

- **M-1:`options: Optional[Dict[str, Any]]` 是"黑洞参数"** — plan §2.3 任务 1.1 五个 API 函数都接受 `options: Optional[Dict[str, Any]]`,但 plan 完全没列出 `options` 接受哪些 key、各 key 的类型、默认值、影响的行为。**机制**:`options` 一旦被代码消费,就是新 API 表面的一部分,得写进文档。**修复建议**:在 plan 加 §2.4 附录 "Options 字典契约",列出所有合法 key 和值域。

- **M-2:`HitOverrideStore.filtered_hits` 已经有 `doc_hash: str` 必填,plan 设计成 `Optional`** — `secureredact/redaction/override_store.py:139` 是 `def filtered_hits(self, hits: List[dict], *, location: str, doc_hash: str) -> List[dict]`(`doc_hash` 是必填 keyword-only)。plan §2.3 任务 1.1 设计成 `filter_hits_by_overrides(..., doc_hash: Optional[str] = None)`,与底层签名不一致。**机制**:`doc_hash=None` 时会发生什么?是等同于"无 doc 特定 override"还是抛错?plan 没说明。**修复建议**:plan 明确写 "doc_hash=None 时等价于 `compute_doc_hash(path)` 计算后传入"。

- **M-3:`name_context_extra_tokens` 参数从 config.json 注入,plan 完全没提** — `secureredact/workers/ocr_worker.py:58` 第 9 个参数 `name_context_extra_tokens`,来源是 `main.py:443-444` 的 `config.get("redaction.name_context.extra_tokens", [])`。plan §3.3 任务 2.1 写 "启动前注入 rules / keywords" 但**漏掉 `name_context_extra_tokens`**。**机制**:API 内部 wrapper OCRWorker 时,这条新逻辑丢了,中文名识别会回退到默认 STRONG_PREFIX_TOKENS。**修复建议**:plan §2.3 任务 1.2 加一行"OCRWorker 启动前从 `config.get('redaction.name_context.extra_tokens', [])` 读出,作为 `name_context_extra_tokens` 参数传入"。

- **M-4:`redact_pdf` / `redact_word` 写文件路径在沙箱/只读目录无错误处理** — plan §2.3 任务 1.1 返回 `{"output": str, ...}`,但 `output_path` 在父目录不存在或权限不足时,会抛 `PermissionError` 或 `FileNotFoundError`(裸 Python 异常),而不是规整的 `secureredact.utils.exceptions.SecurityError`。**机制**:plan §0.3 D-04 说"API 异常统一抛 `secureredact.utils.exceptions` 已定义类型",但没在 7 个函数签名上声明 `raises`。**修复建议**:每个 API 函数在 docstring 加 `Raises:` 段,列出每种异常触发条件。

- **M-5:QRectF 实际只有 2 处使用,plan 担忧的"PyQt6 类型泄漏"可能过度** — `main.py` 里 `QRectF` 只有 2 处。`scan_pdf` 返回的 `rect` 可以是 `(x, y, w, h)` tuple 或 `{x, y, w, h}` dict,这种转换在 wrapper 内部一次完成,简单可控。plan 列为"严格返回 dict;wrapper 转换"过度了。**修复建议**:plan 加一句"API 返回的 rect 是 `(x, y, w, h)` 4 元 tuple,无 dict 包装",简化消费者使用。

### LOW

- **L-1:plan §6.2 CLI 例子用 `--rules '{"phone": "..."}'` 这种 JSON 字符串解析** — Windows CMD 不会自动处理 JSON 内的双引号,需要 escape,实际用户体验差。**修复建议**:P5 实现时用 `python -m secureredact.cli redact --rules-file rules.json` 从文件读,而不是命令行 JSON。

- **L-2:plan §3.6 验收"完整回归套件通过"无具体命令** — §7.1 有命令,但 §3.6 复述时没引用。**修复建议**:§3.6 加"完整命令见 §7.1"。

- **L-3:plan §5.4 验收标准混用了 pytest markers (api / smoke) 但 §5.3 任务 4.3 才配置 markers** — 出现循环依赖。**修复建议**:把 pytest.ini 配置移到任务 4.1 之前,或者把验收标准的 pytest 改为 `pytest tests/unit/test_api.py`(具体路径,无 marker 依赖)。

## Suggestions

- 在 plan §0 加 "**术语表**" 解释 wrapper、shim、smoke test、PR-C5.x 等内部术语
- 在 plan §1 阶段总览加 "**已识别的债(技术债登记)**" 一节,把所有已发现但计划到 P3 才解决的债列出来(R-01 跨包依赖、命名不一致等),让团队知道债是承认的
- 在 plan §7.1 回归命令前加 "**前置条件**" 节(必须 `pip install -e .` 或 `python -m compileall` 通过)
- 在 plan §8 风险表加 R-08:"用户可能基于 1.1.x 老 API 写脚本,API 化后行为变化" — 风险等级:低,但需要 CHANGELOG 醒目
- 在 plan §2.4 验收标准加 "**性能基准**":`scan_pdf(< 5MB 测试文件>) < 1.5 秒`,防止 wrapper 加额外开销

## Risk Assessment

总体风险等级:**MEDIUM**(从 plan 自评的"MEDIUM"略下调到"MEDIUM 上限")

理由:
- 4 个 HIGH 问题都有明确修复路径,不是设计性错误
- 8 个核心 API 函数中 5 个可以直接 wrapper 现有实现,无新增技术风险
- 风险主要在 P3 阶段"清掉 from main import X" 的债是否能在 0.5 周内消化,plan 没量化这块工作量
- 13000 行 shim 拆完需要 ~3 周,plan 没量化人工 review 成本

## Open Questions

- **Q-1:API 层 `options: Dict[str, Any]` 的契约谁来定?** plan 没指明是 P1 阶段定还是代码写时边写边定。建议 P1 启动前先冻结一个最小 options schema。
- **Q-2:CLI 命令的 `--rules` 接受 dict 还是文件?** 影响 P5 用户体验,plan 给的是 dict 但建议改文件。
- **Q-3:shim 完全移除时机?** plan 说"v1.1.17 / B5 收口",但 version.txt 现在是 1.1.12 → 1.1.13 → 1.1.14 在路上,跳到 1.1.17 需要 4 个 minor 版本,是否过快?
- **Q-4:API 函数返回 dict vs dataclass?** plan §0.2 说"不引入 dataclass 类型",但 §0.2 表里写"view model 状态对象"不在范围,这两者是否冲突?dataclass 算 view model 吗?
- **Q-5:`compute_doc_hash` 在并发场景下行为?** 当前实现用 path+size+mtime,两个用户同时打开同一文件会得到相同 hash,这是否符合预期?

---

## Consensus Summary

### Agreed Strengths (self-review)
- API 化方向正确,目标明确
- 7 个 API 函数选取有依据(都是已有函数的 wrapper)
- 测试门槛分层合理
- PR 拆分粒度满足"可回滚"要求

### Agreed Concerns (self-review,按优先级)
- **HIGH**:wrapper 模式 vs 无 main 依赖 承诺矛盾
- **HIGH**:`WordBatchReplaceWorker` 异步信号 → API 同步化未设计
- **HIGH**:`compute_doc_hash` 签名不一致
- **HIGH**:`test_main_shim_compat.py` 阶段错位
- **MEDIUM**:`options` 黑洞参数 + `name_context_extra_tokens` 漏注入
- **MEDIUM**:QRectF 担忧过度 + 异常处理无 Raises 文档

### Divergent Views
- N/A(只有 self-review,无多 reviewer 对照)

---

## 行动项

在执行 P1 之前必须解决的 4 个 HIGH 问题:

1. **决策 API 是否允许临时 `from main import`**(H-1)
2. **设计 worker 异步 → API 同步的同步化机制**(H-2)
3. **补全 `compute_doc_hash` 对 `Path` 的支持**(H-3)
4. **把 `test_main_shim_compat.py` 移到 P3 阶段**(H-4)

解决后 plan 可升级到 v1.1,可启动 P1。

---

## 评审者元信息

| 字段 | 值 |
|------|---|
| 评审时间 | 2026-08-29T22:33 |
| 评审输入 | docs/planning/gui-api-refactor-plan.md(430 行) |
| Codex 状态 | **FAILED** — PowerShell 沙箱 + DLL 加载失败,无产出 |
| Fallback 评审者 | 主会话 Claude(Opus 4.8) |
| Fallback 证据深度 | 9 处 file:line 引用,直接 trace 源码 |
| 建议 | 后续在能跑通 Codex 沙箱的环境重跑,以验证 self-review 的客观性 |
