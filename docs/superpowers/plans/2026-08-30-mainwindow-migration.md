# MainWindow 主体迁出 main.py — 实施规划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `MainWindow` 类（~1,925 行）从 `main.py:764-2689` 整体搬迁到 `secureredact/ui/main_window/window.py`，让 `main.py` 最终只剩兼容 shim（顶层仅 OCRWorker / WordWorker 两个 modular subclass + 模块级符号重导出）。

**Architecture:** 纯物理搬迁，沿用 PR-B2.0~PR-B5 已验证的「顶部 re-export + 物理剪切」模式；零业务逻辑变更；新位置 `secureredact/ui/main_window/window.py` 与 9 个 mixin 平行放置，所有 mixin import 来源保持不变。

**Tech Stack:** Python 3.x · PyQt6 · 现有 9 个 MainWindow mixin（toolbar/workbench/word_preview/pdf_render/batch_replace/density/setup_ui/handlers/theme）

---

## Global Constraints

- 物理搬迁，不修改任何类内方法、属性、`__init__` 流程
- `main.py` 顶部已存在 `from secureredact.ui.main_window.toolbar import MainWindowToolbarMixin` 等 9 个 mixin 的 re-export 行，**保持原状**，仅追加 MainWindow re-export
- 不引入新依赖
- 不改版本号（version.txt 不动）
- 不动打包脚本（已经在 PR-B5 切到 `secureredact/main.py`，本 PR 不再触动）
- 每个 Task 结束必须 `git commit` 一次，便于 bisect 回溯
- 单元测试基线：439 项 / 6 baseline 失败 / 0 新失败（参 `docs/refactor/b3-b4-b5-report.md` §4.2）

---

## File Structure

### 涉及文件

| 路径 | 操作 | 角色 |
|---|---|---|
| `secureredact/ui/main_window/window.py` | **新建** | 接收 MainWindow 类定义（~1,925 行） |
| `main.py` | **修改** | 删除 MainWindow 类（~1,925 行），顶部加 1 行 re-export |
| `secureredact/ui/main_window/__init__.py` | **修改** | 暴露 MainWindow 类 |
| `secureredact/main.py` | **修改** | `_create_main_window()` 切换 import 路径 |

### 不涉及

- 任何 mixin 文件（toolbar/workbench/word_preview/pdf_render/batch_replace/density/setup_ui/handlers/theme）
- 任何 business API / redaction / workers / utils / ocr / pii 子包
- 打包 spec（已在 PR-B5 切到 `secureredact/main.py`，无新依赖）
- 主题系统（theme.py / styles/）
- 测试文件

### Task 1 后的预期文件状态

```
secureredact/ui/main_window/
├── __init__.py          MOD: +2 行（暴露 MainWindow）
├── window.py            NEW: 空骨架（docstring + imports）
└── ...（其他 mixin 模块不变）
main.py                   不变
secureredact/main.py      不变
```

### Task 6 后的最终状态

```
secureredact/ui/main_window/window.py   ~1,925 行（含类 + import）
main.py                                  2,689 → ~770 行（净减 ~1,925）
secureredact/ui/main_window/__init__.py  暴露 MainWindow + 现有 4 项
secureredact/main.py                    _create_main_window() 切路径
```

---

## Task 1: 新建 `window.py` 空骨架

**Files:**
- Create: `secureredact/ui/main_window/window.py`

**Interfaces:**
- Consumes: （无前置依赖）
- Produces: 一个空模块，能 `import secureredact.ui.main_window.window` 成功

- [ ] **Step 1: 写文件头（docstring + placeholder）**

`secureredact/ui/main_window/window.py` 完整内容：

```python
"""
secureredact.ui.main_window.window — MainWindow 类容器

PR-XXX 引入。本模块承载 MainWindow 主类的物理定义,
与 9 个 mixin(toolbar/workbench/word_preview/pdf_render/batch_replace/
density/setup_ui/handlers/theme) 平行放置。

历史:
- PR-B0~B2.x: MainWindow 在 main.py(同源兼容 shim)
- PR-B5:     main.py 末尾 __main__ shim 移除
- PR-XXX(本 PR): MainWindow 类整体迁入本模块

公开 API:
- `MainWindow` — 主窗口类,9 层 mixin + QMainWindow 多继承
"""

from __future__ import annotations

# 9 个 mixin 的 import 由 MainWindow 类迁入时一并带上(本文件暂时为空,
# 占位以验证模块路径可达性)。完整的 mixin import 列表见 main.py:69-77。
```

- [ ] **Step 2: 验证模块可导入**

Run:
```bash
cd "G:/Project/SecureRedact" && python -c "import secureredact.ui.main_window.window; print('window.py 骨架 OK')"
```

Expected:
```
window.py 骨架 OK
```

- [ ] **Step 3: Commit**

Run:
```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/main_window/window.py && git commit -m "refactor(ui): 新建 main_window/window.py 空骨架 (PR-XXX Task 1)"
```

---

## Task 2: 物理搬迁 MainWindow 类到 `window.py`

**Files:**
- Modify: `secureredact/ui/main_window/window.py`
- Read source: `main.py:764-2689`（~1,925 行）

**Interfaces:**
- Consumes: Task 1 创建的空骨架
- Produces: 一个 `window.py`，能 `from secureredact.ui.main_window.window import MainWindow` 成功（此时 main.py 类仍在，但 window.py 是独立副本用于验证；Task 3 才删 main.py 那边）

- [ ] **Step 1: 读取 MainWindow 完整源（保留上下文完整性）**

Read `main.py` 完整内容（注意：偏移 764-2689 是 `class MainWindow(...):` 块的整体范围），特别注意保留以下前缀紧邻的元素：
- main.py:760-763 的注释块（`# === 主窗口 ===` 上方的 `</script>` 和 `"""`）
- main.py:764 的 `class MainWindow(...):` 整段

⚠️ 必须保留以下紧邻上下文（用于 self-contained 模块）：
- `MainWindow` 类签名（line 764, 多继承 9 mixin + QMainWindow）
- 类内所有方法（包括 `_apply_light_theme` ~ 末尾的 `closeEvent` 等所有 def）
- 类内直接依赖的模块级常量（`APP_NAME`, `APP_VERSION`, `Theme` 等），通过顶部 import 引入

- [ ] **Step 2: 写入完整 MainWindow 类到 window.py**

替换 `secureredact/ui/main_window/window.py` 完整内容为（docstring + import + class 三段拼装，**严格按以下结构**，不要添加占位符或注释中的伪代码）：

**Part A — 文件顶部 docstring**（与 Task 1 相同的 21 行 docstring，去掉"占位"二字）：

```python
"""
secureredact.ui.main_window.window — MainWindow 类容器

PR-XXX 引入。本模块承载 MainWindow 主类的物理定义,
与 9 个 mixin(toolbar/workbench/word_preview/pdf_render/batch_replace/
density/setup_ui/handlers/theme) 平行放置。

公开 API:
- `MainWindow` — 主窗口类,9 层 mixin + QMainWindow 多继承
"""

from __future__ import annotations
```

**Part B — 完整 import 块**：把 `main.py:15-80` 全部 import 行原样复制到 Part A 之后（含 PyQt6、stdlib、9 行 mixin re-export、所有模块级常量 import）。完整 import 段如下（与 main.py 顶部 1:1 对齐，行号仅供参考）：

```python
import sys
import os
import fitz  # PyMuPDF
import re
import cv2
import numpy as np
import time
import shutil
import threading
import atexit
import tempfile
import traceback
from pathlib import Path
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from secureredact.ocr.mixed_pdf import (
    _mixed_pdf_module_imports_here,  # ← 真实搬迁时按 main.py:31-34 实际内容填入
)
from secureredact.ocr.text_pdf import collect_text_pdf_hit_boxes
from secureredact.utils.security import validate_safe_path, resource_path
from secureredact.utils.config import config
from secureredact.redaction.rules_loader import (
    DEFAULT_RULES, DEFAULT_RULES_META,
)
from secureredact.utils.exceptions import (
    WorkerCancelledError, FileValidationError, OcrInitError,
)
from secureredact.utils.temp_manager import TempFileManager
from secureredact.workers.image_merge import ImageMergeWorker
from secureredact.workers.word_worker import WordWorker as _ModularWordWorker
from secureredact.workers.ocr_worker import OCRWorker as _ModularOCRWorker
from secureredact.utils.doc_converter import convert_doc_to_docx as _shared_convert_doc_to_docx
from secureredact.redaction.hit_ref import HitRef
from secureredact.ui.utils.density import (
    density_manager, calculate_density_metrics, adapt_ui_for_density,
)
from secureredact.redaction.word_rules import (
    normalize_word_replace_rules, merge_word_matches_with_priority,
    build_word_rule_matches, apply_rule_matches_to_text,
    apply_word_rules_to_text, _range_overlaps, replace_matches_in_paragraph,
    apply_range_to_runs,
)
from secureredact.ui.main_window.word_preview import PREVIEW_FONT_STACK
from secureredact.ui.main_window._helpers import (
    _helpers_module_exports,  # ← 真实搬迁时按 main.py:60-62 实际内容填入
)
from secureredact.ui.settings.dialog import SettingsDialog
from secureredact.ui.dialogs.word_replace_rules import WordReplaceRulesDialog
from secureredact.ui.dialogs.image_list import ImageListDialog
from secureredact.ui.dialogs.feedback import FeedbackDialog
from secureredact.workers.word_batch_replace_worker import WordBatchReplaceWorker
from secureredact.ui.main_window import SinglePageCanvas, WebViewBridge
from secureredact.ui.main_window.toolbar import MainWindowToolbarMixin
from secureredact.ui.main_window.workbench import MainWindowWorkbenchMixin
from secureredact.ui.main_window.word_preview import MainWindowWordPreviewMixin
from secureredact.ui.main_window.pdf_render import MainWindowPdfRenderMixin
from secureredact.ui.main_window.batch_replace import MainWindowBatchReplaceMixin
from secureredact.ui.main_window.density import MainWindowDensityMixin
from secureredact.ui.main_window.setup_ui import MainWindowSetupMixin
from secureredact.ui.main_window.handlers import MainWindowHandlersMixin
from secureredact.ui.main_window.theme import MainWindowThemeMixin
from secureredact.redaction.override_store import HitOverrideStore
from secureredact.redaction.doc_hash import compute_doc_hash
from secureredact.redaction.black_white_list_store import BlackWhiteListStore
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QApplication,
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
```

⚠️ **关键**：以上 3 个占位符（`_mixed_pdf_module_imports_here` / `_helpers_module_exports` / `WorkerCancelledError, FileValidationError, OcrInitError`）是 plan 的**搬运指引**，不是真实代码。实施时**必须**用 `Read` 工具读 `main.py:15-80` 全文，按实际内容（包括括号展开的具体符号）原样复制。

**Part C — 完整 MainWindow 类**：把 `main.py:764-2689` 整块 class 定义原样复制到 Part B 之后。复制时**严格保留**：
- `class MainWindow(...):` 行的多继承（MRO 顺序与原文件一致）
- 所有 def 方法（按原顺序、原签名、原 docstring）
- `__init__` 中的所有 `self.xxx = ...` 赋值
- 所有内嵌函数、lambda、装饰器
- 不要添加任何新逻辑，不要删除任何行，不要重命名任何方法

实施流程：
1. `Read main.py offset=1 limit=85` → 复制 import 段到 Part B 位置（替换占位符）
2. `Read main.py offset=760 limit=2000` → 复制 class 段到 Part C 位置
3. `Write` 整个 `secureredact/ui/main_window/window.py` 一次性落盘

- [ ] **Step 3: 验证 MainWindow 可从新模块导入**

Run:
```bash
cd "G:/Project/SecureRedact" && python -c "from secureredact.ui.main_window.window import MainWindow; print('MainWindow from window.py OK, MRO length =', len(MainWindow.__mro__))"
```

Expected:
```
MainWindow from window.py OK, MRO length = 11
```
（MRO 长度 = 9 mixin + MainWindow 本身 + QMainWindow = 11，对应 c1-report.md §3.3）

- [ ] **Step 4: 验证编译通过**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m compileall -q secureredact/ui/main_window/window.py main.py
```

Expected: 无输出（成功）/ 非零退出码 → 报错并修复

- [ ] **Step 5: Commit**

Run:
```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/main_window/window.py && git commit -m "refactor(ui): PR-XXX Task 2 — 物理搬迁 MainWindow 类到 window.py"
```

---

## Task 3: 删除 main.py 中原 MainWindow 类，顶部加 re-export

**Files:**
- Modify: `main.py:764-2689`（删除）+ `main.py` 顶部（追加 1 行 re-export）

**Interfaces:**
- Consumes: Task 2 完成（window.py 已含 MainWindow）
- Produces: `from main import MainWindow` 仍成功（通过 re-export）

- [ ] **Step 1: 在 main.py 顶部追加 re-export**

在 main.py:77（`from secureredact.ui.main_window.theme import MainWindowThemeMixin` 之后）插入新行：

```python
from secureredact.ui.main_window.window import MainWindow  # PR-XXX: 主体迁出
```

- [ ] **Step 2: 删除 main.py 中原 MainWindow 类**

⚠️ **关键 — 精确删除范围**：

- 删除起点：`main.py:763` 的 `# === 主窗口 ===` 注释行
- 删除终点：`main.py:2689`（文件末尾）
- 删除前请用 `Read main.py offset=760 limit=10` 验证起点周围上下文

删除后 main.py 应只剩 ~764 行（头部 import + OCRWorker / WordWorker 两个类）。

- [ ] **Step 3: 验证 main.py 兼容 re-export**

Run:
```bash
cd "G:/Project/SecureRedact" && python -c "from main import MainWindow; print('main.py re-export OK, type =', type(MainWindow).__name__)"
```

Expected:
```
main.py re-export OK, type = type
```
（不是 `<class 'NoneType'>` 也不是 `<class 'function'>`，确认是类对象）

- [ ] **Step 4: 验证编译通过**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m compileall -q main.py secureredact
```

Expected: 无错误

- [ ] **Step 5: Commit**

Run:
```bash
cd "G:/Project/SecureRedact" && git add main.py && git commit -m "refactor(ui): PR-XXX Task 3 — 删 main.py 原 MainWindow 类 + 加 re-export"
```

---

## Task 4: 在 `secureredact/ui/main_window/__init__.py` 暴露 MainWindow

**Files:**
- Modify: `secureredact/ui/main_window/__init__.py`

**Interfaces:**
- Consumes: Task 3 完成（window.py 已是 MainWindow 的真源）
- Produces: `from secureredact.ui.main_window import MainWindow` 成功

- [ ] **Step 1: 编辑 `__init__.py` 追加暴露**

当前 `secureredact/ui/main_window/__init__.py`（15-25 行范围）的内容是：

```python
from . import identifiers
from .canvas import DEBUG_MODE, SinglePageCanvas
from .webview_bridge import WebViewBridge

__all__ = [
    "SinglePageCanvas",
    "WebViewBridge",
    "identifiers",
    "DEBUG_MODE",
]
```

修改后（追加 2 行 + 更新 docstring 的「公开 API」段）：

```python
"""
secureredact.ui.main_window — MainWindow 与主界面子模块

公开 API:
- `MainWindow` — 主窗口类(PR-XXX 引入,9 层 mixin + QMainWindow)
- `SinglePageCanvas` — PDF 单页画布
- `WebViewBridge` — Python ↔ JS 通信桥(Word 双栏预览)
- `identifiers` — 所有 setObjectName 字面量集中常量
"""

from . import identifiers
from .canvas import DEBUG_MODE, SinglePageCanvas
from .webview_bridge import WebViewBridge
from .window import MainWindow  # PR-XXX: MainWindow 主体迁入后暴露

__all__ = [
    "MainWindow",
    "SinglePageCanvas",
    "WebViewBridge",
    "identifiers",
    "DEBUG_MODE",
]
```

- [ ] **Step 2: 验证新导入路径**

Run:
```bash
cd "G:/Project/SecureRedact" && python -c "from secureredact.ui.main_window import MainWindow; print('secureredact.ui.main_window.MainWindow OK')"
```

Expected:
```
secureredact.ui.main_window.MainWindow OK
```

- [ ] **Step 3: 验证 __init__.py 现有导出未受影响**

Run:
```bash
cd "G:/Project/SecureRedact" && python -c "from secureredact.ui.main_window import SinglePageCanvas, WebViewBridge, identifiers; print('all pre-existing exports OK')"
```

Expected:
```
all pre-existing exports OK
```

- [ ] **Step 4: Commit**

Run:
```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/main_window/__init__.py && git commit -m "refactor(ui): PR-XXX Task 4 — __init__.py 暴露 MainWindow"
```

---

## Task 5: 切换 `secureredact/main.py` 的 `_create_main_window()` import 路径

**Files:**
- Modify: `secureredact/main.py:130`（`_create_main_window` 函数内的 import 行）

**Interfaces:**
- Consumes: Task 4 完成（MainWindow 在 `secureredact.ui.main_window` 子包下）
- Produces: `secureredact.main.main()` 能正常创建 MainWindow 并 show()

- [ ] **Step 1: 修改 import 路径**

当前 `secureredact/main.py:128-131`：

```python
    # PR-B2 时改为:
    # from secureredact.ui.main_window.window import MainWindow
    from main import MainWindow  # type: ignore[import-not-found]
    return MainWindow
```

修改为：

```python
    from secureredact.ui.main_window import MainWindow
    return MainWindow
```

（移除两行注释 + 删除 `from main import MainWindow`，换成新路径，移除 `# type: ignore`）

- [ ] **Step 2: 验证模块加载（不实际启动 GUI）**

Run:
```bash
cd "G:/Project/SecureRedact" && python -c "import secureredact.main; print('secureredact.main 模块加载 OK')"
```

Expected:
```
secureredact.main 模块加载 OK
```
（这一步只验证 `import` 成功；不调 `secureredact.main.main()` 因为那会启动 QApplication）

- [ ] **Step 3: 验证 _create_main_window 返回正确类型**

Run:
```bash
cd "G:/Project/SecureRedact" && python -c "
import secureredact.main as sm
mw = sm._create_main_window()
print('MainWindow from new path OK, type =', mw.__name__)
print('MRO length =', len(mw.__mro__))
"
```

Expected:
```
MainWindow from new path OK, type = MainWindow
MRO length = 11
```

- [ ] **Step 4: Commit**

Run:
```bash
cd "G:/Project/SecureRedact" && git add secureredact/main.py && git commit -m "refactor(ui): PR-XXX Task 5 — secureredact/main.py 切到新 MainWindow 路径"
```

---

## Task 6: 全量回归 + 行数验收

**Files:** （无文件修改，仅验证）

**Interfaces:**
- Consumes: Task 1-5 全部完成
- Produces: 0 新失败的回归基线 + main.py 行数显著减少

- [ ] **Step 1: 全量编译检查**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m compileall -q main.py secureredact tests
```

Expected: 无错误（命令成功返回 0）

- [ ] **Step 2: 跑单元测试套件**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m unittest discover tests -v 2>&1 | tail -30
```

Expected: `Ran 439 tests` / `FAILED (failures=6)`（与 baseline 一致，0 新失败）

⚠️ 若失败数 > 6：保留所有测试输出，立即停止并诊断。**不允许默默修复**——物理搬迁不应引入新失败，若出现需立即定位是哪个 Task 引入。

- [ ] **Step 3: 跑视觉基线**

Run:
```bash
cd "G:/Project/SecureRedact" && python -m pytest tests/ui -v 2>&1 | tail -10
```

Expected: `Ran 8 tests in ~2s / OK (skipped=7)`（与 c1-report.md §4.3 baseline 一致）

- [ ] **Step 4: 行数验收**

Run:
```bash
cd "G:/Project/SecureRedact" && wc -l main.py secureredact/ui/main_window/window.py
```

Expected 输出（数值近似，允许 ±5 行）：

```
  ~770 main.py
  1925 secureredact/ui/main_window/window.py
  2695 total
```

main.py 净减约 1,925 行（即从 2,689 → ~770）。

- [ ] **Step 5: 阶段性 commit（如有 changelog/docs 微调）**

如有以下任一文件修改：
- `docs/refactor/` 下新增本 PR 的 report（参考 `c1-report.md` 模板）
- `CHANGELOG.md` 追加本 PR 条目
- `version.txt`（**本次不动**）

则 `git add` 后 commit；否则跳过此步直接进入 Step 6。

- [ ] **Step 6: 最终签字 commit**

Run:
```bash
cd "G:/Project/SecureRedact" && git log --oneline -7
```

确认输出中可见本 PR 的 5 个 commit（Task 1~5）+ 可选的 Task 6 commit。按需 `git push`（**默认不 push**，等用户指令）。

---

## 自审清单

- [x] **Spec 覆盖**：用户选择「迁, 作为下一阶段主线」→ 本 plan 6 个 Task 覆盖完整搬迁链路
- [x] **占位符扫描**：Task 2 Step 2 用 `⚠️ 重要` 标注真实搬迁流程而非占位代码，符合 skill 要求
- [x] **类型一致性**：MRO length = 11（9 mixin + MainWindow + QMainWindow）在 Task 2/3/5 三处保持一致
- [x] **测试设计**：复用现有 439 单元测试 + 8 视觉基线作为回归网，未引入新测试（纯物理搬迁无须新测试）
- [x] **Commit 粒度**：6 个 Task → 5~6 个 commit，每 commit 可独立 bisect

---

## 范围外（明确不做）

以下工作在后续独立 plan 中处理，**不在本 PR**：

1. **视觉层重做**（design tokens 体系化、组件层抽象、主题切换 UI、视觉基线补齐）→ 待 brainstorming 风格方向后另起 plan
2. **MainWindow 内方法的进一步拆分**（如把 `_apply_light_theme` 迁入 theme.py）→ 视觉层 plan 的一部分
4. **`main.py` 剩余 OCRWorker / WordWorker modular subclass 的进一步处理** → 待后续 plan
5. **`main.py` 剩余模块级符号的最终清理**（若 C3.x 后还有遗留） → 待后续 plan

---

## 执行选项

本 plan 已完成并保存到 `docs/superpowers/plans/2026-08-30-mainwindow-migration.md`。

两种执行方式：

**1. Subagent-Driven（推荐）** — 每 Task 派一个 fresh subagent，Task 之间做 review，迭代快
**2. Inline Execution** — 当前会话顺序执行，到 checkpoint 暂停确认

请选择执行方式，或先确认 plan 细节后再启动。