# GUI mixin 收尾 + 业务 API 化 — 分阶段实施计划

> 适用版本: v1.1.13 → v1.1.17(路线图,以写作时 `version.txt` 为准)
> 文档状态: Draft v1.2(REVIEWS-v2 修订)
> 计划长度目标: < 1000 行
> 适用范围: SecureRedact 桌面 GUI(Python + PyQt6 + RapidOCR + python-docx)

---

## 0. 目标 / 范围 / 不在范围 / 决策记录

### 0.1 目标

1. **业务稳定能力 API 化**:把跨调用边界、可独立测试、业务语义稳定的能力抽到 `secureredact.api` 顶层函数;GUI 改调 API;为未来 CLI / Web 复用打基础。
2. **清理 mixin 内的 `from main import X`**:把 v1.1.12 期间补加的 10+ 个跨包 lazy import 全部消解;让 mixin 只 import 干净符号。
3. **建立 API 100% 测试 + GUI smoke test 的双层测试矩阵**。
4. **每个 PR 单独可发布、可回滚**。

### 0.2 范围

| 在范围内 | 不在范围内 |
|---------|-----------|
| `secureredact/api.py` 新增 | view model 状态对象 |
| `secureredact/cli.py` 薄壳(可选) | UI 文案 / 样式拼接 |
| MainWindow mixin 调用面替换 | `main.py` shim 整体移除(属于 B5 收口,不在本次) |
| 漏迁符号回迁到 `secureredact/` 对应子包 | 重写 OCR / Word 算法逻辑 |
| API 层单测(100%) | GUI mixin 行为单测(仅 smoke) |
| | 跨包类型 dataclass 重构(仅在必要时引入) |

### 0.3 决策记录

| 编号 | 决策 | 理由 |
|------|------|------|
| D-01 | API 化走渐进式 + wrapper 模式,主链路调用 (`compute_doc_hash`、`HitOverrideStore.filtered_hits`、`WordBatchReplaceWorker` 类) 直接从 `secureredact/` 现有函数 wrapper;次链路调用 (`scan_pdf` 内的逐页扫描+OCR 编排、`scan_word` 内的段落匹配、`redact_pdf` 内的输出写入) 在 P1 阶段允许临时 `from main import _xxx`,但**每个 API 函数临时 import 数 ≤ 2**,且每个临时 import 必须在 P3 阶段被清账 | 兼顾向后兼容 + 控制技术债上限;不让 P3 的"清掉 from main import X" 工作量爆炸 |
| D-02 | `secureredact.api` 是顶层模块(不是包) | 简洁;不存在子模块冲突 |
| D-03 | API 函数全部 `from typing import` + type hints | 工具链可静态检查 |
| D-04 | API 异常统一抛 `secureredact.utils.exceptions` 已定义类型 | 不引入新异常体系 |
| D-05 | GUI mixin 阶段允许保留 `from main import X` 作为过渡标记 | 不强制一次性切换;每个 PR 单独清理一段 |
| D-06 | 测试门槛:API 层 100%;GUI mixin 仅 smoke | 避免无限 UI 测试;业务正确性靠 API 层保证 |
| D-07 | 每个 PR 单独可发布、可回滚 | 沿用现有 Git workflow |

---

## 1. 阶段总览

| 阶段 | 主题 | 周期估计 | PR 编号 |
|------|------|---------|---------|
| P1 | API 化骨架 | 0.5 周 | PR-C4 |
| P2 | GUI mixin 切换为 API | 1.0 周 | PR-C5.x(4 个子 PR) |
| P3 | 清掉 mixin 里的 `from main import X` | 0.5 周 | PR-C6.x(按 mixin 分批) |
| P4 | 测试矩阵与门槛设置 | 0.5 周 | PR-C7 |
| P5 | CLI 薄壳(可选) | 0.5 周 | PR-C8(可选) |
| 总计 | — | ~3 周 | — |

---

## 2. 阶段 1 — API 化骨架(PR-C4)

### 2.1 目标

- 新增 `secureredact/api.py` 作为对外门面。
- 暴露 7 个核心函数,覆盖「扫描 / 执行脱敏 / 命中过滤 / 文档哈希 / 批量替换」五大场景。
- 不引入 dataclass 类型(保持返回 dict / list[dict],与 GUI 现有消费方式一致)。
- 100% 单测覆盖。

### 2.2 产出文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `secureredact/api.py` | 新增 | 顶层门面模块 |
| `secureredact/__init__.py` | 修改 | 增加 `from .api import ...` 转发 7 个函数 |
| `tests/unit/test_api.py` | 新增 | API 层 100% 覆盖 |
| `docs/current/API_REFERENCE.md` | 新增 | API 函数签名/示例(用户面向) |

### 2.3 任务列表

#### 任务 1.1 — 设计 7 个函数签名

```python
# secureredact/api.py
from pathlib import Path
from typing import Any, Dict, List, Optional

# === 1. 文档哈希 ===
def compute_doc_hash(file_path: str | Path) -> str:
    """8 位文档标识,基于路径+size+mtime,与 redaction/doc_hash.py 对齐。

    Args:
        file_path: 文档路径,接受 `str` 或 `pathlib.Path`。内部用 `os.fspath()` 归一化。
    """

# === 2. PDF 命中扫描(不执行脱敏,只产 hit 列表)===
def scan_pdf(
    pdf_path: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    options: Optional[Dict[str, Any]] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    """逐页扫描 PDF,合并 text layer + image block OCR。

    Args:
        pdf_path: PDF 路径,接受 `str` 或 `pathlib.Path`。
        rules: 规则字典(键为规则名,值为正则 pattern)。
        custom_keywords: 用户自定义关键词(空格分隔)。
        options: 可选行为控制(详见 §2.7 Options 契约)。

    Returns:
        {page_num(int, 0-based): [{"rect": (x, y, w, h) tuple,
          "source": str, "text": str, ...}, ...]}

    Note:
        返回的 `rect` 用 4 元 tuple 而非 dict(API 层不引入 dict 包装开销,
        也不暴露 QRectF 类型)。
    """

# === 3. Word 命中扫描 ===
def scan_word(
    word_path: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    replacement_text: str = "[已脱敏]",
    options: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """扫描 Word 段落,产出 matches 列表(每个 match 含 start/end/text/source/rule_name)。"""

# === 4. PDF 一站式脱敏 ===
def redact_pdf(
    pdf_path: str | Path,
    output_path: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    doc_hash: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """完整 PDF 脱敏链路:扫描 → override 过滤 → 合并 → 输出。

    Returns:
        {"output": str, "pages": int, "hits": int, "elapsed_sec": float}
    """

# === 5. Word 一站式脱敏 ===
def redact_word(
    word_path: str | Path,
    output_path: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    replacement_text: str = "[已脱敏]",
    doc_hash: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """完整 Word 替换链路。"""

# === 6. 命中 override 过滤 ===
def filter_hits_by_overrides(
    hits: List[Dict[str, Any]],
    *,
    location: str,
    doc_hash: Optional[str] = None,
    doc_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """包装 HitOverrideStore.instance().filtered_hits(),GUI 是唯一调用方。

    任何新消费端必须走此函数,禁止直接调用 HitOverrideStore。

    Args:
        hits: 待过滤的命中列表。
        location: 命中位置(`f"page_{i}"` / `f"paragraph_{idx}"` 等)。
        doc_hash: 文档 8 位哈希。若提供,优先使用;否则从 `doc_path` 计算。
        doc_path: 文档路径。仅当 `doc_hash` 未提供时生效,内部调用
            `compute_doc_hash()` 计算。

    Note:
        至少需要 `doc_hash` 或 `doc_path` 之一,否则抛 `ValueError`。
    """

# === 7. 批量 Word 替换 ===
def batch_redact_word(
    word_paths: List[str | Path],
    output_dir: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    replacement_text: str = "[已脱敏]",
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """批量替换多份 Word,返回 {success: [...], failed: [{path, error}, ...]}。

    Args:
        word_paths: 输入 Word 文档路径列表。
        output_dir: 输出目录(必须存在,否则抛 `FileNotFoundError`)。
        rules: 规则字典。
        custom_keywords: 用户自定义关键词(空格分隔)。
        replacement_text: 统一替换文本。
        options: 可选行为控制(详见 §2.7 Options 契约)。

    Returns:
        {
            "success": [{"input": str, "output": str, "rule_counts": [...]}],
            "failed": [{"input": str, "error": str}],
            "stopped": bool,
            "total": int
        }

    Raises:
        FileNotFoundError: `output_dir` 不存在。
        WorkerCancelledError: 批处理超时(默认 5 分钟,可经 `options.timeout_sec` 调整)。
    """
```

#### 任务 1.2 — 实现 7 个函数(wrapper 模式)

- 每个函数 ≤ 30 行。
- **PR-C4.0 fix-up 必做(REVIEWS-v2 C-1)**:P1 启动前,先在 `secureredact/workers/word_batch_replace_worker.py` 顶部加 `from secureredact.utils.doc_converter import convert_doc_to_docx as _shared_convert_doc_to_docx`,把 `main.py:49` 同款 import 内联到 worker 模块。这是当前 `.doc` 文件转换路径 100% 触发的隐藏 NameError(worker:229 引用该符号,但 1–19 行 import 全部找不到)。
- 主链路直接 wrapper `secureredact/` 现有实现,无 `from main` 依赖:
  - `compute_doc_hash` → `secureredact.redaction.doc_hash.compute_doc_hash`(接受 str;若入参为 `Path`,wrapper 内部 `os.fspath()` 归一化)
  - `filter_hits_by_overrides` → `secureredact.redaction.override_store.HitOverrideStore.instance().filtered_hits`
  - `batch_redact_word` → wrapper `secureredact.workers.word_batch_replace_worker.WordBatchReplaceWorker`(详见下方"**worker 异步同步化策略**")
- 次链路在 P1 阶段允许临时 `from main import _xxx`,但**每个 API 函数临时 import 数 ≤ 2**(D-01 修正):
  - `scan_pdf` → main.py 中的 PDF 扫描内部编排逻辑(暂未迁移到 `secureredact/`)
  - `scan_word` → `secureredact.workers.word_worker.WordWorker.run` 内核心算法
  - `redact_pdf` / `redact_word` → 现有 GUI 启动 worker 后执行的导出逻辑
- **worker 异步同步化策略**:`batch_redact_word` 调用 `WordBatchReplaceWorker` 是异步(QThread 信号回调),API 层必须同步返回:
  ```python
  from PyQt6.QtCore import QEventLoop, QTimer
  loop = QEventLoop()
  worker.finished_signal.connect(loop.quit)
  worker.start()
  QTimer.singleShot(timeout_sec * 1000, loop.quit)
  loop.exec()
  if worker.isRunning():
      worker.requestInterruption()
      raise WorkerCancelledError(f"timeout {timeout_sec}s")
  ```
  关键点:用 `QEventLoop`(非 `threading.Event`,因为 worker 是 QThread,信号槽必须在 Qt 主事件循环里),超时通过 `QTimer.singleShot` 兜底。注意:此实现**只在 Qt 主线程内可用**;若调用方不是 Qt 主线程,需要先在主线程跑(通过 `QMetaObject.invokeMethod` 切线程),后续在 plan 修订中补 `is_main_thread()` 断言 + 友好错误信息。
- **`batch_redact_word` 错误处理(REVIEWS-v2 C-2 修复)**:`WordBatchReplaceWorker._wait_for_error_decision` 用 `threading.Event.wait(0.1)` 阻塞在 worker 线程里等 `provide_error_decision`,但 `QEventLoop` 阻塞 main 线程等 `finished_signal` —— 批处理中某文件出错时,双方都阻塞导致死锁。**wrapper 必须在 worker.start() 前 monkey-patch `provide_error_decision`**,或用 `QTimer.singleShot(5000, lambda: worker._decision_event.set())` 兜底 —— 5 秒后自动放行 `"skip"` 决策。文档明示:"批处理中遇到错误默认 5 秒后自动 skip"。
- **超时硬上限(REVIEWS-v2 C-3 修复)**:`WordBatchReplaceWorker.requestInterruption()` 只在 `for file_path in enumerate(self.file_paths)` 循环顶部检查(行 95);`_process_single_file` 内部(`doc.save()` 等)不响应中断,单文件处理可能耗时数十秒。**`timeout_sec` 仅在文件粒度生效**;§2.4 acceptance 改为"`batch_redact_word` 在 N 个测试 .docx 文件 + `timeout_sec ≥ N × 30s` 时返回"(确保最坏情况仍能完成)。
- **`OCRWorker` 启动前**:从 `config.get('redaction.name_context.extra_tokens', [])` 读出 v1.1.14 新增的 `name_context_extra_tokens` 参数,从 `config.get('ocr.box_adjust_ratio', 0.0)` 读出 `box_adjust_ratio`,传入 worker。**这条 v1.1.14 逻辑 plan 之前漏掉了,本版本补回**(对应 REVIEWS.md M-3)。
- **`scan_word` 同步性(REVIEWS-v2 I-6 修复)**:选 **方案 B** —— `scan_word` / `redact_word` 直接实例化 `WordWorker.run()` 作为**一次性同步执行**(不复用 worker 信号体系),输出 matches 同步返回。**不复用** `QEventLoop` 模式(避免与 WordWorker 现有的信号设计耦合);后续若需要异步,留作 v1.1.16+ 工作。

#### 任务 1.3 — 在 `secureredact/__init__.py` 暴露

- 新增 `from .api import (compute_doc_hash, scan_pdf, scan_word, redact_pdf, redact_word, filter_hits_by_overrides, batch_redact_word)`
- 加入 `__all__`

#### 任务 1.4 — 测试 `tests/unit/test_api.py`

- 用例结构:每个函数 3-5 条,覆盖正常路径 + 异常路径 + 边界
- 不实际启动 PyQt6(API 层不依赖 QApplication,只接受/返回 dict)
- 用例示例:
  - `test_compute_doc_hash_deterministic`
  - `test_scan_pdf_returns_page_keyed_dict`
  - `test_scan_word_returns_match_list`
  - `test_redact_pdf_writes_output_file`
  - `test_filter_hits_by_overrides_drops_ignored`
  - `test_batch_redact_word_separates_success_failure`

### 2.4 验收标准(acceptance criteria)

- [ ] `from secureredact import compute_doc_hash, scan_pdf, scan_word, redact_pdf, redact_word, filter_hits_by_overrides, batch_redact_word` 全部成功
- [ ] `tests/unit/test_api.py` 全部通过
- [ ] API 层覆盖率 ≥ 100%(用 `pytest --cov=secureredact/api --cov-fail-under=100`)
- [ ] `python3 -m compileall -q secureredact/api.py` 通过
- [ ] GUI 老路径(直接 `from secureredact import OCRWorker`)不受影响
- [ ] **每个 API 函数内部 `from main import` 数 ≤ 2**(D-01 修订),`grep -c "from main import" secureredact/api.py` ≤ 14
- [ ] **`compute_doc_hash(Path("/tmp/a.pdf")) == compute_doc_hash("/tmp/a.pdf")`**(签名一致性回归测试,H-3 修订)
- [ ] **`compute_doc_hash(Path("a.pdf").resolve()) == compute_doc_hash("a.pdf")`**(REVIEWS-v2 I-5 真实歧义测试,前提:`a.pdf` 在工作目录存在)
- [ ] **`batch_redact_word` 用 2 个 `.docx` 测试文件 + `timeout_sec ≥ 2 × 30s`(60 秒)跑通**,返回 success/failed 字典结构正确,且 `len(success) + len(failed) == len(word_paths)`;超时硬上限按文件粒度生效(REVIEWS-v2 C-3 修订)
- [ ] **`batch_redact_word` 批处理中遇到文件错误,5 秒后自动 `"skip"` 决策**(REVIEWS-v2 C-2 死锁修复)
- [ ] **性能基准**:`compute_doc_hash(< 5MB 测试文件) < 100ms`(测 wrapper 开销;**scan_pdf 含 OCR 不参与性能基准**——REVIEWS-v2 m-4 修订)
- [ ] **`filter_hits_by_overrides(doc_hash=None, doc_path=None)` 抛 `ValueError("doc_hash or doc_path required")`**(M-2 + m-5 修订)

### 2.7 Options 契约

`options: Optional[Dict[str, Any]]` 接受的合法 key(M-1 修订)。**适用 API 函数**列标记每 key 被哪些函数实际消费(REVIEWS-v2 I-7 矩阵,7 个 API × 6 个 key 共 42 格;空白格 = ignored,无效值会抛 `KeyError`):

| key | 类型 | 默认 | 适用 API 函数 | 影响行为 |
|-----|------|------|--------------|---------|
| `timeout_sec` | int | 300 | `batch_redact_word` | worker 超时秒数(用于 §2.3 任务 1.2 的同步化) |
| `enable_name_recognition` | bool | False | `scan_pdf`, `redact_pdf` | 透传给 `OCRWorker.enable_name_recognition` |
| `name_context_extra_tokens` | list[str] | None | `scan_pdf`, `redact_pdf` | 透传给 `OCRWorker.name_context_extra_tokens`(默认走 STRONG_PREFIX_TOKENS) |
| `box_adjust_ratio` | float | 0.0 | `scan_pdf`, `redact_pdf` | 透传给 `OCRWorker.box_adjust_ratio` |
| `use_enhance` | bool | False | `scan_pdf`, `redact_pdf` | PDF 扫描增强(WordWorker 无此参数,传 `redact_word`/`batch_redact_word` 被 ignored) |
| `progress_callback` | Callable[[str, int, int], None] | None | `redact_pdf`, `batch_redact_word` | 进度回调,签名 `(stage, current, total)` |

**矩阵含义**:
- `timeout_sec` / `progress_callback` 只在耗时操作里生效(`batch_redact_word`、`redact_pdf`)
- `enable_name_recognition` / `name_context_extra_tokens` / `box_adjust_ratio` / `use_enhance` 是 PDF-OCR 专属,Word 端 ignored
- 任何 P1 阶段新引入的 `options` key 必须在此表登记 + 标记适用函数,否则算 API 违约

### 2.5 依赖

- 无(纯新增)

### 2.6 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| API 内部需要 `main.py` 的私有函数 | 中 | 通过 `from main import _scan_pdf_impl` 等临时 import,后续 P3 阶段回迁 |
| PyQt6 类型泄漏到 API 返回值 | 中 | 返回 dict 而不是 QRectF,转译在 wrapper 内完成 |
| 测试 PyQt6 启动慢 | 低 | API 测试不实例化 QApplication |

---

## 3. 阶段 2 — GUI mixin 切换为 API(PR-C5.x)

### 3.1 目标

- 6 个 MainWindow mixin 中,**直接调用 worker / pii / redaction 模块**的代码全部改为调 API。
- 保留 mixin 内部对 PyQt6 / QThread 的直接使用(API 层不接管 UI 线程模型)。
- 每个 mixin 一个子 PR,方便回滚。

### 3.2 涉及文件

| 文件 | 当前直接 import 的模块 | 切换为 API |
|------|----------------------|-----------|
| `secureredact/ui/main_window/handlers.py` | `OCRWorker`, `WordWorker` | `redact_pdf`, `redact_word` |
| `secureredact/ui/main_window/batch_replace.py` | `WordBatchReplaceWorker` | `batch_redact_word` |
| `secureredact/ui/main_window/word_preview.py` | `secureredact.redaction.*` | `filter_hits_by_overrides`, `scan_word` |
| `secureredact/ui/main_window/pdf_render.py` | `secureredact.redaction.black_white_list_store` | 暂留(P3 再迁) |
| `secureredact/ui/main_window/_helpers.py` | 无业务 import | 不需要切换 |
| `secureredact/ui/main_window/setup_ui.py` | 无业务 import | 不需要切换 |

### 3.3 任务列表

#### 任务 2.1 — PR-C5.1 `handlers.py` 切换

- 把 `OCRWorker` / `WordWorker` 实例化 + 启动保留在 mixin(GUI 线程模型不能动)
- 把「启动前注入 rules / keywords」的代码改为读 API 函数签名里的 `options` 字段
- Acceptance:
  - [ ] mixin 内不再 `from secureredact.workers import OCRWorker`(改为 `from secureredact.workers import OCRWorker as _OCRWorker` 或保留 import,但**新增** API 调用点)
  - [ ] 点击「智能脱敏」按钮行为不变
  - [ ] 单测:`tests/unit/test_bridge_override_slots` 仍通过

#### 任务 2.2 — PR-C5.2 `batch_replace.py` 切换

- 批量替换 worker 启动前,调用 `batch_redact_word` 拿到 `success` / `failed` 列表预览
- Acceptance:
  - [ ] 「预估成功 / 失败数」UI 标签逻辑正常
  - [ ] `tests/unit/test_batch_word_replace` 通过

#### 任务 2.3 — PR-C5.3 `word_preview.py` 切换

- 在 hits 显示前调用 `filter_hits_by_overrides`
- Acceptance:
  - [ ] 右键「忽略 / 确认 / 撤销 / 提升为永久」交互不变
  - [ ] `tests/unit/test_override_store` / `test_overrides_persistence` 通过

#### 任务 2.4 — PR-C5.4 `pdf_render.py` 切换(保守版)

- 仅切换「黑/白名单读写」:从直接 `BlackWhiteListStore` 调用改为通过 API(仅在 P5 添加对应函数后)
- Acceptance:
  - [ ] 黑/白名单 UI 编辑不变

### 3.4 依赖

- 依赖 P1 完成(API 函数必须先存在)

### 3.5 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| GUI 性能因额外 wrapper 调用下降 | 低 | API 函数是 thin wrapper,开销 < 1ms |
| 部分 mixin 内部耦合过紧,无法拆出 API 调用点 | 中 | 允许保留 `from secureredact.workers import ...`;只新增 API 调用点即可 |
| QThread 信号绑定不能经过 API | 中 | API 函数返回 dict,mixin 自行启动 worker + 绑定信号 |

### 3.6 验收

- 完整回归套件通过(见 §7.1)
- 每个子 PR 单独合并,单独回滚

### 3.7 阶段 B5 兼容性约束(REVIEWS H-1 衍生)

P2 完成不等于 P3 完成。P2 完成后 `main.py` 仍保留 `OCRWorker` / `WordWorker` 等兼容层(`class OCRWorker(_ModularOCRWorker): ...`),老的 `from main import OCRWorker` 仍可用;P3 阶段才逐步把这些兼容层迁走。**`main.py` shim 完全移除目标是 v1.1.17 / B5 收口**(对应 REVIEWS Open Question Q-3),不在本规划范围。

---

## 4. 阶段 3 — 清掉 mixin 里的 `from main import X`(PR-C6.x)

### 4.1 目标

- 阶段 2 之前的 v1.1.12 期间补的 10+ 个 `from main import X` 跨包 lazy import,逐步迁移到 `secureredact/` 对应子包。
- 完成后 mixin 只 `import` 干净符号。
- **本阶段首个动作**(REVIEWS H-4 修订):在任务开始**之前**新增 `tests/unit/test_main_shim_compat.py`,持续验证 `main.py` 中待迁移符号还可用,作为迁移过程的安全网。每个符号迁移后,移除 shim compat 测试中对应条目。

### 4.2 摸底方法

```bash
grep -rn "^from main import" secureredact/ui/main_window/ secureredact/ui/dialogs/
```

按 grep 结果建任务列表,每个符号一个子 PR。

### 4.3 任务模板(每个符号适用)

#### 任务 0 — 阶段启动前置(REVIEWS H-4 修订,必须先做)

1. 新建 `tests/unit/test_main_shim_compat.py`
2. 用例结构:对每个当前仍在 `main.py` 模块级、被 mixin/测试以 `from main import X` 引用的符号,写 1 条"导入可用 + 值类型正确"的 smoke 测试
3. 例:`test_main_shim_compat.py` 顶部放上清单(每个符号一行),后续每迁移一个符号,从清单删除一行并跑测试
4. Acceptance:测试当前 100% 通过;每个迁移 PR 都跑这条测试

#### 任务 N — 迁移符号 `X`

1. **定位**:在 `main.py` 找到 `X` 的定义(类/函数/常量)
2. **判断归属**:
   - 业务逻辑 → `secureredact/<对应子包>/`
   - UI 专属 → `secureredact/ui/<对应子模块>/`
   - 主窗口 mixin 工具 → `secureredact/ui/main_window/_helpers.py`(已经存在的扩展点)
3. **搬迁**:
   - 移动代码到目标模块
   - 在目标模块内改用绝对 import (`from secureredact.xxx import YYY`)
4. **过渡兼容**:
   - 在 `main.py` 保留 `X = ...` 的别名(v1.1.x 仍兼容)
   - mixin 内 `from main import X` 改为 `from secureredact.<新位置> import X`
5. **下一版本移除**:v1.1.17 / B5 收口时移除 `main.py` 中的兼容别名

#### Acceptance(每个子 PR)

- [ ] grep `from main import` 在该文件内 0 命中
- [ ] `python3 -m compileall -q main.py secureredact` 通过
- [ ] 现有回归套件通过
- [ ] GUI smoke 启动(人工或启动脚本)通过

### 4.4 优先级排序

1. 业务规则相关(如 `DEFAULT_RULES_META`)→ 优先
2. 异常 / 工具函数 → 中
3. UI 内部常量 / 工具 → 末批

### 4.5 依赖

- 依赖 P1 完成(部分符号可能要迁到 API 层)

### 4.6 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 符号搬动后 PyInstaller 打包失败 | 中 | 在每次 PR 后跑 `packaging/windows/scripts/build_complete.bat` smoke 编译 |
| 兼容别名遗漏 | 低 | 加 `tests/unit/test_main_shim_compat.py` 防止遗漏 |
| 搬动后引入循环 import | 中 | 目标模块使用 `TYPE_CHECKING` 或延迟 import |

---

## 5. 阶段 4 — 测试矩阵与门槛设置(PR-C7)

### 5.1 目标

- 明确每个层级的测试类型 / 覆盖率门槛。
- 把现有分散的测试文件按层级归类。
- 把 P1/P2 的新测试接入。

### 5.2 测试矩阵

| 层级 | 测试类型 | 覆盖率门槛 | 工具 |
|------|---------|-----------|------|
| `secureredact/api.py` | 单元 | 100% | pytest-cov |
| `secureredact/redaction/*.py` | 单元 | ≥ 90%(已达标) | pytest-cov |
| `secureredact/workers/*.py` | 单元 + 集成 | ≥ 80%(已达标) | pytest |
| `secureredact/ocr/*.py` | 单元 + 集成 | ≥ 80% | pytest |
| `secureredact/ui/main_window/*.py` | smoke | 仅 import(不实例化,避免 QApplication 依赖)(REVIEWS-v2 I-3 修订) | pytest-qt |
| `secureredact/ui/dialogs/*.py` | smoke | 仅 import + `QApplication.instance()` 非 None 检查(对话框构造需要 parent,不全实例化) | pytest-qt |

### 5.3 任务列表

#### 任务 4.0 — 配置 pytest(REVIEWS-v2 I-4 修订,**必须先做**)

- 创建 `pytest.ini`(`tests/` 目录顶部),配置 markers:
  ```ini
  [pytest]
  markers =
      api: API 层单元测试(100% 覆盖)
      integration: 集成测试
      smoke: 导入/实例化 smoke 测试
      slow: 超过 1 秒的测试
  testpaths = tests
  addopts = -ra -q
  ```
- Acceptance:后续 `pytest -m api` 不报 "unknown marker"

#### 任务 4.1 — 新增 `tests/unit/test_api_smoke.py`

- 每个 API 函数 1 条:「import 成功 + 函数存在」
- 运行时间 < 1 秒

#### 任务 4.2 — 新增 `tests/unit/test_main_window_import_smoke.py`

- 每个 mixin 模块:`import secureredact.ui.main_window.<name>` 不报错
- 不实例化(避免依赖 QApplication)

#### 任务 4.3 — CI 配置

- 在 `packaging/ci/` 增加 GitHub Actions workflow(如果还没有):
  - 运行 `pytest -m "not slow"`
  - 运行 `pytest --cov=secureredact/api --cov-fail-under=100 -m api`
  - 运行 `pytest -m smoke`

### 5.4 验收

- [ ] `pytest -m api` 覆盖率 ≥ 100%
- [ ] `pytest -m smoke` 通过
- [ ] 现有 162 项回归继续通过

### 5.5 依赖

- 依赖 P1 / P2 / P3 完成

---

## 6. 阶段 5(可选)— CLI 薄壳(PR-C8)

### 6.1 目标

- 提供一个轻量级命令行入口,验证 API 层确实支持 GUI 之外的消费方式。
- 不替换 GUI,仅做 demo + 自动化友好入口。

### 6.2 命令面

```bash
# 扫描并打印 JSON
python -m secureredact.cli scan input.pdf --rules '{"phone": "...", ...}' --json

# 执行脱敏
python -m secureredact.cli redact input.pdf --output out.pdf \
    --rules '{"phone": "...", ...}' \
    --keywords "张三 李四"

# 批量 Word 替换
python -m secureredact.cli redact-word word_dir/ --output out_dir/ \
    --rules '{"phone": "***"}'

# 查看版本
python -m secureredact.cli --version
```

### 6.3 产出文件

| 文件 | 说明 |
|------|------|
| `secureredact/cli.py` | argparse + 调用 `secureredact.api` |
| `tests/unit/test_cli.py` | CLI smoke(main 函数 / --help) |

### 6.4 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| API 设计不友好 CLI | 中 | P1 阶段同步把 `--json` 输出考虑进 API 返回结构 |
| PyQt6 间接被 CLI 触发 | 中 | `secureredact.api` 不依赖 PyQt6;CLI 也不依赖 |

### 6.5 验收

- [ ] `python -m secureredact.cli --help` 输出正常
- [ ] `python -m secureredact.cli redact <测试 PDF> --output <out>` 生成有效脱敏 PDF
- [ ] 不实例化 QApplication

---

## 7. 里程碑 + 验收方式

### 7.1 完整回归命令

```bash
# 1. 编译检查
python3 -m compileall -q main.py secureredact tests

# 2. 主回归(v1.1.11 基线 + 当前扩展)
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

# 3. 新增 API + smoke(PR-C4 / C7 后追加)
pytest -m "api or smoke" -v --cov=secureredact/api --cov-fail-under=100
```

### 7.2 里程碑检查表

| 里程碑 | 验收命令 | 通过条件 |
|--------|---------|---------|
| M1(P1 完成) | 主回归 + API 单测 | 全部通过 |
| M2(P2 完成) | 主回归 + GUI 启动 smoke | 全部通过 |
| M3(P3 完成) | `grep -rn "from main import" secureredact/ui/ secureredact/api.py`(REVIEWS-v2 I-2 修订)| 0 命中 |
| M4(P4 完成) | `pytest -m "api or smoke"` + 覆盖率 | 100% API |
| M5(P5 可选) | `python -m secureredact.cli --help` | 正常输出 |

### 7.3 每次 PR 必须通过的 smoke

1. `python3 -m compileall -q main.py secureredact`
2. 主回归(§7.1 第 2 条)
3. 启动 GUI:`python3 main.py` (Linux/macOS) / `python main.py`(Windows)→ 至少看到主窗口不崩溃

---

## 8. 风险登记

| ID | 描述 | 概率 | 影响 | 缓解 |
|----|------|------|------|------|
| R-01 | API 内部仍需 `from main import _xxx`,跨包依赖残留 | 高 | 中 | P3 阶段每个 API 函数内部的 main 依赖都要清账 |
| R-02 | QRectF / QPointF 等 PyQt6 类型泄漏到 API 返回值 | 中 | 高 | 严格返回 dict;wrapper 转换 |
| R-03 | GUI mixin 切换为 API 后线程模型改变 | 中 | 高 | 保留 mixin 直接启动 worker 的权力,API 只接管数据准备 |
| R-04 | 测试覆盖率门槛 100% 难以长期维持 | 中 | 中 | CI fail-under=100 自动阻止合并 |
| R-05 | PyInstaller 打包因新 import 路径失败 | 中 | 高 | 每次 PR 后跑 build smoke |
| R-06 | 用户旧脚本 `from main import X` 失效 | 低 | 高 | `main.py` shim 暂保留到 B5 收口 |
| R-07 | API 函数过多导致维护成本上升 | 低 | 中 | 严格控制在 7 个,新增必须先 review |
| R-08 | API 化后老脚本 `from main import X` 行为变化 | 低 | 高 | `main.py` shim 暂保留到 B5 收口;CHANGELOG 醒目标注 deprecation 日程 |

---

## 9. 附录 — 函数清单快速参考

### 9.1 阶段 1 API 函数速查

| 函数 | 用途 | 替换的 mixin 路径 |
|------|------|------------------|
| `compute_doc_hash` | 8 位文档哈希 | 多处 |
| `scan_pdf` | PDF 命中扫描 | `handlers.py` / `pdf_render.py` |
| `scan_word` | Word 命中扫描 | `word_preview.py` |
| `redact_pdf` | PDF 一站式脱敏 | `handlers.py` |
| `redact_word` | Word 一站式脱敏 | `handlers.py` |
| `filter_hits_by_overrides` | 命中 override 过滤 | `word_preview.py` / `pdf_render.py` |
| `batch_redact_word` | 批量 Word 替换 | `batch_replace.py` |

### 9.2 阶段 3 待迁移符号 grep 命令

```bash
grep -rn "^from main import" secureredact/ui/main_window/ secureredact/ui/dialogs/ secureredact/ui/settings/
```

预期输出:每个符号一行,按文件分组,作为 P3 子 PR 的入口。

---

## 10. 变更日志

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| v1 | 2026-08-29 | planner | 初稿 |
| v1.1 | 2026-08-29 | claude (REVIEWS 修订) | 修复 4 个 HIGH 问题:H-1 wrapper 临时 import 上限 / H-2 worker 同步化策略 / H-3 compute_doc_hash Path 支持 / H-4 test_main_shim_compat 阶段前置;补 R-08 老脚本 deprecation 风险;补 Options 契约 §2.7;补 M-3 name_context_extra_tokens 注入说明 |
| v1.2 | 2026-08-29 | claude (REVIEWS-v2 superpowers:requesting-code-review 修订) | 修复 3 个 Critical + 7 个 Important:C-1 `_shared_convert_doc_to_docx` 内联到 worker / C-2 错误处理 monkey-patch 防死锁 / C-3 文件粒度超时口径;I-1 版本号对齐 v1.1.13→v1.1.17 / I-2 M3 grep 加 api.py / I-3 §5.2 GUI 行改"仅 import" / I-4 pytest.ini 配置提到任务 4.0 / I-5 Path.resolve() 真实歧义测试 / I-6 scan_word 同步选方案 B / I-7 Options 矩阵加"适用 API 函数"列 |
