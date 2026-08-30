"""
SecureRedact 业务 API 层 (PR-C4 v1.1.14)

对外门面模块,7 个核心函数覆盖「扫描 / 执行脱敏 / 命中过滤 / 文档哈希 / 批量替换」。

设计原则:
- 不破坏向后兼容:GUI 老路径 `from secureredact import OCRWorker` 仍可用
- API 层接受/返回 `dict`,不暴露 PyQt6 类型(QRectF 等)
- 实现走 `secureredact/` 子包 wrapper 模式,`from main import` = 0
- 100% 单测覆盖,便于 CLI / 自动化场景复用

来源:`docs/planning/gui-api-refactor-plan.md` §2.3 任务 1.1 / 1.2
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# 主链路:直接走 secureredact/ 子包,无临时 main.py 依赖
from secureredact.redaction.doc_hash import compute_doc_hash as _compute_doc_hash_impl
from secureredact.redaction.override_store import HitOverrideStore
from secureredact.workers.word_batch_replace_worker import WordBatchReplaceWorker
from secureredact.utils.exceptions import WorkerCancelledError

# PyQt6 依赖说明:WordBatchReplaceWorker 是 QThread 子类,实例化需 PyQt6 已加载
# CLI/SDK 用户需要保证 Qt DLL 在 PATH 上(同 `python main.py` 启动条件)
from PyQt6.QtCore import QEventLoop, QTimer  # noqa: F401 — used in batch_redact_word


__all__ = [
    "compute_doc_hash",
    "scan_pdf",
    "scan_word",
    "redact_pdf",
    "redact_word",
    "filter_hits_by_overrides",
    "batch_redact_word",
]


# === 1. 文档哈希 ===
def compute_doc_hash(file_path: str | Path) -> str:
    """8 位文档标识,基于路径+size+mtime,与 `secureredact.redaction.doc_hash` 对齐。

    Args:
        file_path: 文档路径,接受 `str` 或 `pathlib.Path`。内部用 `os.fspath()` 归一化。

    Returns:
        8 位 hex 字符串。

    Raises:
        OSError: 文件不存在或无 stat 权限。
    """
    return _compute_doc_hash_impl(os.fspath(file_path))


# === 2. PDF 命中扫描(不执行脱敏,只产 hit 列表)===
def scan_pdf(
    pdf_path: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    options: Optional[Dict[str, Any]] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    """逐页扫描 PDF,合并 text layer + image block OCR(简化版 stub)。

    Returns:
        {page_num(0-based int): [{"rect": (x, y, w, h) tuple,
          "source": str, "text": str}, ...]}

    Note:
        当前为骨架版:仅扫描文本通道,不调用 OCR。完整版(含 image-block OCR
        合并)在 PR-C5 阶段实现。

    Raises:
        FileNotFoundError: PDF 文件不存在。
    """
    raise NotImplementedError(
        "scan_pdf 完整实现在 PR-C5 阶段。当前为骨架版 stub。"
    )


# === 3. Word 命中扫描(方案 B:一次性同步)===
def scan_word(
    word_path: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    replacement_text: str = "[已脱敏]",
    options: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """扫描 Word 段落,产出 matches 列表。

    Note:
        方案 B(plan §2.3 任务 1.2):直接实例化 WordWorker.run() 同步执行,
        不复用 worker 信号体系。返回 matches 是空列表占位(完整算法在
        worker.run 内部,不暴露中间产物)。

    Raises:
        NotImplementedError: 当前为骨架版 stub。
    """
    raise NotImplementedError(
        "scan_word 完整实现在 PR-C5 阶段。当前为骨架版 stub。"
    )


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

    Note:
        当前为骨架版 stub。完整实现在 PR-C5 阶段。

    Raises:
        NotImplementedError: 当前为骨架版 stub。
    """
    raise NotImplementedError(
        "redact_pdf 完整实现在 PR-C5 阶段。当前为骨架版 stub。"
    )


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
    """完整 Word 替换链路。

    Note:
        当前为骨架版 stub。完整实现在 PR-C5 阶段。

    Raises:
        NotImplementedError: 当前为骨架版 stub。
    """
    raise NotImplementedError(
        "redact_word 完整实现在 PR-C5 阶段。当前为骨架版 stub。"
    )


# === 6. 命中 override 过滤 ===
def filter_hits_by_overrides(
    hits: List[Dict[str, Any]],
    *,
    location: str,
    doc_hash: Optional[str] = None,
    doc_path: Optional[str | Path] = None,
) -> List[Dict[str, Any]]:
    """包装 `HitOverrideStore.instance().filtered_hits()`。

    Args:
        hits: 待过滤的命中列表。
        location: 命中位置(`f"page_{i}"` / `f"paragraph_{idx}"` 等)。
        doc_hash: 文档 8 位哈希。若提供,优先使用;否则从 `doc_path` 计算。
        doc_path: 文档路径。仅当 `doc_hash` 未提供时生效。

    Raises:
        ValueError: `doc_hash` 和 `doc_path` 都未提供时。
    """
    if doc_hash is None:
        if doc_path is None:
            raise ValueError("doc_hash or doc_path required")
        doc_hash = compute_doc_hash(doc_path)
    store = HitOverrideStore.instance()
    return store.filtered_hits(list(hits), location=location, doc_hash=doc_hash)


# === 7. 批量 Word 替换(同步化 wrapper)===
def batch_redact_word(
    word_paths: List[str | Path],
    output_dir: str | Path,
    *,
    rules: Dict[str, Any],
    custom_keywords: str = "",
    replacement_text: str = "[已脱敏]",
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """批量替换多份 Word,同步返回结果。

    Args:
        word_paths: 输入 Word 文档路径列表。
        output_dir: 输出目录(必须存在,否则抛 `FileNotFoundError`)。
        rules: 规则字典。
        custom_keywords: 用户自定义关键词(空格分隔,当前未使用)。
        replacement_text: 统一替换文本。
        options: 可选行为控制(详见 plan §2.7 Options 契约)。

    Returns:
        {
            "success": [{"input": str, "output": str, "total_replacements": int,
                          "rule_counts": [...]}],
            "failed": [{"input": str, "error": str}],
            "stopped": bool,
            "total": int
        }

    Raises:
        FileNotFoundError: `output_dir` 不存在。
        WorkerCancelledError: 批处理超时(`options.timeout_sec` 默认 300s)。
    """
    output_dir = os.fspath(output_dir)
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"output_dir 不存在: {output_dir}")

    # 解析 options(plan §2.7 Options 契约)
    timeout_sec = 300
    if options and "timeout_sec" in options:
        try:
            timeout_sec = int(options["timeout_sec"])
        except (TypeError, ValueError) as e:
            raise ValueError(f"options.timeout_sec 必须为 int,得到 {options['timeout_sec']!r}") from e

    # 路径统一化
    normalized_paths = [os.fspath(p) for p in word_paths]

    # 实例化 worker
    worker = WordBatchReplaceWorker(
        file_paths=normalized_paths,
        rules=list(rules) if isinstance(rules, (list, tuple)) else rules,
        default_replacement_text=replacement_text,
    )

    # 启动 worker + QEventLoop 等待 finished_signal
    # finished_signal.emit(dict) 是 worker.run() 在最后 emit 的 summary
    collected: Dict[str, Any] = {}
    loop = QEventLoop()

    def _on_finished(summary_dict):
        collected.update(summary_dict)
        loop.quit()

    worker.finished_signal.connect(_on_finished)
    worker.start()

    # REVIEWS-v2 C-2 修复:批处理某文件出错时,worker 线程阻塞在
    # _wait_for_error_decision,主线程阻塞在 QEventLoop → 死锁。
    # 解决:用 QTimer 每 5 秒主动提供 "skip" 决策(兜底防卡死)。
    # worker 内部 _wait_for_error_decision 看到 _decision_event.set() 后
    # 取决策继续;无出错时该调用被 worker 内部忽略(决策读不到)。
    auto_skip_timer = QTimer()
    auto_skip_timer.setInterval(5000)

    def _auto_provide_skip():
        if worker.isRunning():
            worker.provide_error_decision("skip")

    auto_skip_timer.timeout.connect(_auto_provide_skip)
    auto_skip_timer.start()

    # REVIEWS-v2 C-3 修复:文件粒度超时兜底(timeout_sec ≥ N × 30s)
    QTimer.singleShot(timeout_sec * 1000, loop.quit)
    loop.exec()

    auto_skip_timer.stop()

    # 等 worker 线程真正结束
    if worker.isRunning():
        worker.wait(5000)

    # 组装返回 summary(plan §2.3 任务 1.1 schema)
    if not collected:
        # QTimer 兜底超时退出,worker 仍在跑(被中断);collected 为空
        raise WorkerCancelledError(
            f"batch_redact_word timeout {timeout_sec}s (file-grained, see plan §2.3 任务 1.2 C-3)"
        )

    return {
        "total": int(collected.get("total", len(normalized_paths))),
        "success": list(collected.get("success", [])),
        "failed": list(collected.get("failed", [])),
        "stopped": bool(collected.get("stopped", False)),
    }