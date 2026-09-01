# Plan 2b — 视觉组件 / 基线 / 主题切换 UI 实施规划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan sub-PR-by-sub-PR. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Plan 2b 的 4 个 sub-PR（PR-C2.x → PR-V2 → PR-V4 → PR-C1.1）从「设计 Spec」落到可执行的 TDD task 列表，每 task 一个 commit。

**Architecture:** 严格沿用 PR-B 系列已验证的「顶部 re-export + 物理剪切」+ PR-V1 已验证的「dataclass token + .qss 占位符替换」组合。零业务逻辑变更；只动样式层与极少量新增 UI 入口。

**Tech Stack:** Python 3.x · PyQt6 · Playwright (Python sync_api, headless Chromium) · RapidOCR · dataclass (已用) · unittest

**Sub-PR 顺序（用户已选定，按依赖反向排列）：**

1. **PR-C2.x** 视觉基线（Playwright 截图回归）— 先暴露当前 UI 真相
2. **PR-V2** 6 类组件 .qss — 把现有 6 个 .qss 规范化、补齐 5 状态、用占位符
3. **PR-V4** MainWindow / SettingsDialog 内嵌 QSS 迁移 — 干掉 622 + 320 行内嵌样式
4. **PR-C1.1** SettingsDialog 主题切换 UI — 用户能切换 light/dark/system

---

## Global Constraints

- 不改 `version.txt`（v1.1.13 基线）
- 不改 `theme.py` 现有 alias 接口（向后兼容窗口 worker 路径）
- 不改 mixin 类结构（toolbar/workbench/word_preview/pdf_render/batch_replace/density/setup_ui/handlers/theme 全部不动）
- 不引入新依赖（Playwright 已在 `requirements.txt`；Glass 检测用 PyQt6 内置能力）
- 每个 Task 结束必须 `git commit` 一次，便于 bisect 回溯
- 单元测试基线：`tests/unit/` 全部通过 + 已知 6 项 baseline 失败（见 `docs/refactor/b3-b4-b5-report.md` §4.2），新 PR **不得引入任何新失败**
- Token 数值严格使用 `secureredact/ui/styles/tokens.py` 的 `LIGHT` / `DARK`，**禁止**在 .qss / Python 中写死 hex 值（`#E9F1FB`、`#FBFCFE`、`#F8FBFE` 等 hex 字面量必须迁移到 token 或专门新建 `info_*` token，本 PR 数据层先放 `secureredact/ui/styles/tokens.py` 的扩展位，应用层替换留 PR-V4 阶段）

---

## 当前已验证状态（snapshot 2026-08-31）

| 资产 | 行数 / 状态 | 备注 |
|---|---|---|
| `main.py` | 253 行 | Phase B5 compat shim |
| `secureredact/ui/main_window/window.py` | 2030 行 | MainWindow 已迁出 |
| `secureredact/ui/main_window/density.py` | 954 行 | 23 处 `setStyleSheet` |
| `secureredact/ui/main_window/batch_replace.py` | 827 行 | 6 处 `setStyleSheet` |
| `secureredact/ui/main_window/window.py` | — | 12 处 `setStyleSheet` |
| `secureredact/ui/main_window/theme.py` | 84 行 | 1 处 `setStyleSheet`（滚动区域） |
| `secureredact/ui/settings/dialog.py` | 2270 行 | 320 行 `_apply_dialog_theme()` f-string + ~30 处 `_apply_settings_density_styles()` 内嵌 |
| `secureredact/ui/styles/tokens.py` | 124 行 | 16 颜色 + 3 字体 token，dataclass |
| `secureredact/ui/styles/loader.py` | 89 行起 `StylesheetLoader` | 已可调用 `loader.apply(widget, "light", scope="main")` |
| `secureredact/ui/styles/base.qss` | 19 行 | QMainWindow/QWidget#appRoot/QLabel |
| `secureredact/ui/styles/menu.qss` | 35 行 | QMenu |
| `secureredact/ui/styles/progress.qss` | 18 行 | QProgressBar |
| `secureredact/ui/styles/toolbar.qss` | 46 行 | toolbar 元件 |
| `secureredact/ui/styles/workbench.qss` | 51 行 | workbench 元件 |
| `secureredact/ui/styles/workspace.qss` | 392 行 | workspace / batch / preview 全部 |
| Glass 检测模块 | **缺失** | 全代码 grep `backdrop-filter|glass` 仅命中 HTML 资源；属于 PR-V1 §6 遗留 |
| Playwright Python sync_api | 可 import | 但 `~/.cache/ms-playwright` 缺失，需 `playwright install chromium` |
| 测试基线 | 待确认 | `python -m unittest discover -s tests/unit` 应 ≥ 449 项 / 6 baseline 失败 |

> 上述行数与缺失项是 Plan 2b 的事实基线。任何后续 task 在开工前必须重新核对本表。

---

## File Structure（最终态）

```
secureredact/ui/styles/
├── tokens.py              # MOD：新增 4 个 info_* token（PR-C2.x 前置条件）
├── glass.py               # NEW：Glass 检测（PR-C2.x 前置条件，~40 行）
├── loader.py              # 不动
├── base.qss               # MOD：可选抽取通用样式（PR-V2 Task 1）
├── button.qss             # NEW：QPushButton 5 状态（PR-V2 Task 2）
├── input.qss              # NEW：QLineEdit/QTextEdit/QSpinBox/QComboBox 5 状态（PR-V2 Task 3）
├── tab.qss                # NEW：QTabWidget/QTabBar 5 状态（PR-V2 Task 4）
├── card.qss               # NEW：QFrame card variants（PR-V2 Task 5）
├── dock.qss               # NEW：QDockWidget 5 状态（PR-V2 Task 6）
├── toolbar.qss            # MOD：复用 button.qss 基类（PR-V2 Task 7）
├── workbench.qss          # 不动（已合规）
├── workspace.qss          # MOD：复用 card.qss（PR-V2 Task 7）
├── menu.qss               # 不动
└── progress.qss           # 不动

secureredact/ui/settings/
└── dialog.py              # MOD：新增「外观」分节（C1.1） + 替换内嵌 QSS（V4）

secureredact/ui/main_window/
├── theme.py               # 不动
├── density.py             # MOD：23 处 setStyleSheet → loader.apply（V4）
├── batch_replace.py       # MOD：6 处 setStyleSheet → loader.apply（V4）
└── window.py              # MOD：12 处 setStyleSheet → loader.apply（V4）

secureredact/ui/styles/baselines/    # NEW：视觉基线（PR-C2.x 产物）
├── main_window_light.png
├── main_window_dark.png
├── settings_dialog_light.png
├── settings_dialog_dark.png
├── baseline_manifest.json
└── compare.py                       # NEW：像素对比工具

tests/unit/
├── test_glass_detect.py             # NEW
├── test_visual_baseline.py          # NEW：基线生成 + 比对
├── test_component_qss.py            # NEW：6 类 .qss 占位符验证
├── test_main_window_qss_apply.py    # NEW：window.py 内嵌 → .qss 切换后等价
├── test_density_qss_apply.py        # NEW
├── test_batch_replace_qss_apply.py  # NEW
├── test_settings_dialog_theme_ui.py # NEW
└── test_settings_dialog_density_qss.py  # NEW
```

---

## 前置条件 Task 0：Glass 检测模块补齐（PR-V1 §6 遗留）

> 现状：PR-V1 spec §6 规划了 Glass 降级路径但代码层无落地。Plan 2b PR-V2 的 Card/Dock 组件将引入 `backdrop-filter`，必须先有检测。

### Task 0.1: 新建 `secureredact/ui/styles/glass.py`

**Files:**
- Create: `secureredact/ui/styles/glass.py`

**Interfaces:**
- Consumes: `QApplication.instance()`, `Qt.Window`（仅类型）
- Produces: 模块级常量 `GLASS_AVAILABLE: bool` + `get_glass_substitution() -> Mapping[str, str]`

- [ ] **Step 1: 写失败测试**

新建 `tests/unit/test_glass_detect.py`：

```python
from secureredact.ui.styles import glass


class GlassDetectTest(unittest.TestCase):
    def test_module_exposes_bool(self):
        self.assertIsInstance(glass.GLASS_AVAILABLE, bool)

    def test_substitution_returns_required_keys(self):
        mapping = glass.get_glass_substitution()
        for key in ("card_background", "dock_background"):
            self.assertIn(key, mapping)
            self.assertTrue(mapping[key].startswith("#") or "rgba" in mapping[key])
```

Run:
```bash
cd "G:/Project/SecureRedact" && python -m unittest tests.unit.test_glass_detect -v 2>&1 | tail -5
```
Expected: `ModuleNotFoundError: No module named 'secureredact.ui.styles.glass'`

- [ ] **Step 2: 最小实现（detect only）**

```python
"""
Glass 降级检测 — v1.1.13 PR-V1 §6 补齐

PyQt6 在 Windows 10+ / macOS 11+ 支持 backdrop-filter CSS 属性；
Linux Wayland / 老 Windows / 部分 VM 不可用。检测逻辑：
1. 优先读 qApp.styleHints().colorScheme() 暗示的 platform
2. 探测 Qt version（< 6.5 直接 False）
3. 探测环境变量 QT_QUICK_BACKEND=software 时降级
"""
from __future__ import annotations

import os
from typing import Dict, Mapping

from PyQt6.QtCore import qVersion
from PyQt6.QtWidgets import QApplication


def _detect_glass() -> bool:
    major, minor, *_ = (int(p) for p in qVersion().split("."))
    if (major, minor) < (6, 5):
        return False
    if os.environ.get("QT_QUICK_BACKEND") == "software":
        return False
    qapp = QApplication.instance()
    if qapp is None:
        return False
    try:
        platform_name = qapp.platformName().lower()
        if platform_name.startswith("offscreen"):
            return False
        if platform_name == "minimal":
            return False
    except AttributeError:
        return False
    return True


GLASS_AVAILABLE: bool = _detect_glass()


def get_glass_substitution() -> Mapping[str, str]:
    """返回 Glass 降级时各组件应当使用的背景 token 覆盖值。

    当 GLASS_AVAILABLE=False 时调用方应把 backdrop-filter 改为半透明纯色 + 加阴影。
    """
    if GLASS_AVAILABLE:
        return {}
    return {
        "card_background": "rgba(255, 255, 255, 0.92)",
        "dock_background": "rgba(247, 248, 250, 0.94)",
    }


__all__ = ["GLASS_AVAILABLE", "get_glass_substitution"]
```

- [ ] **Step 3: 跑测试**

```bash
cd "G:/Project/SecureRedact" && python -m unittest tests.unit.test_glass_detect -v 2>&1 | tail -3
```
Expected: `Ran 2 tests / OK`

- [ ] **Step 4: Commit**

```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/styles/glass.py tests/unit/test_glass_detect.py && git commit -m "feat(ui): PR-V1 §6 补齐 — Glass 降级检测模块"
```

---

## 前置条件 Task 0.2：安装 Playwright Chromium

- [ ] **Step 1: 验证 Python 包已装**

```bash
cd "G:/Project/SecureRedact" && python -c "from playwright.sync_api import sync_playwright; print('OK')"
```
Expected: `OK`

- [ ] **Step 2: 安装浏览器二进制（CI 也要跑所以走官方 install）**

```bash
cd "G:/Project/SecureRedact" && python -m playwright install chromium 2>&1 | tail -5
```
Expected: `chromium installed at ...`

- [ ] **Step 3: 验证 headless 启动**

```bash
cd "G:/Project/SecureRedact" && python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    page.set_content('<h1>test</h1>')
    print('headless OK', page.title())
    b.close()
"
```
Expected: `headless OK `（标题空字符串 OK）

> **不 commit**：浏览器二进制不入 git；写入 `requirements.txt` 已含 `playwright` 即可。

---

## Sub-PR 1：PR-C2.x 视觉基线（先暴露现状）

**Goal:** 在 PR-V2/V4/C1.1 改样式前，先把「当前 UI 长什么样」用截图固化下来，作为后续视觉回归的 ground truth。

**Architecture:** PyQt6 的 `QWidget.grab()` 返回 `QPixmap`，用 `pixmap.save("baselines/xxx.png")` 落盘。比对阶段用 Pillow `ImageChops.difference` 计算像素差。

### Task 1.1: 新建基线截图工具

**Files:**
- Create: `secureredact/ui/styles/baselines/compare.py`
- Create: `tests/unit/test_visual_baseline.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_visual_baseline.py
import os
import unittest
from pathlib import Path

from secureredact.ui.styles.baselines import compare


BASELINE_DIR = Path(__file__).resolve().parent.parent.parent / "secureredact" / "ui" / "styles" / "baselines"


class CompareToolTest(unittest.TestCase):
    def test_compute_diff_returns_tuple(self):
        # 用任意两张 16x16 png 验证
        a_path = BASELINE_DIR / "main_window_light.png"
        self.assertTrue(a_path.exists(), f"missing baseline: {a_path}")
        diff_ratio, total_pixels, different_pixels = compare.compute_diff(
            a_path, a_path
        )
        self.assertEqual(diff_ratio, 0.0)
        self.assertEqual(different_pixels, 0)
        self.assertGreater(total_pixels, 0)
```

- [ ] **Step 2: 实现 `compare.py`**

```python
"""
视觉基线对比工具 — v1.1.13 PR-C2.x 引入

不做像素完美比对（PyQt6 渲染有亚像素差异），允许 ≤ 0.5% 差异；
用于 PR-V2/V4 之后捕捉肉眼可见的回归（按钮错位、配色漂移）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageChops


THRESHOLD = 0.005  # 0.5%


def compute_diff(left: Path, right: Path) -> Tuple[float, int, int]:
    """计算两张同尺寸 png 的像素差。

    Returns:
        (diff_ratio, total_pixels, different_pixels)
    """
    a = Image.open(left).convert("RGBA")
    b = Image.open(right).convert("RGBA")
    if a.size != b.size:
        raise ValueError(f"size mismatch: {a.size} vs {b.size}")
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    total = a.size[0] * a.size[1]
    if bbox is None:
        return 0.0, total, 0
    pixels = sum(1 for p in diff.getdata() if any(c > 4 for c in p[:3]))
    return pixels / total, total, pixels


__all__ = ["compute_diff", "THRESHOLD"]
```

- [ ] **Step 3: 跑测试（预期 skip，等基线生成）**

```bash
cd "G:/Project/SecureRedact" && python -m unittest tests.unit.test_visual_baseline -v 2>&1 | tail -5
```
Expected: `AssertionError: missing baseline: .../main_window_light.png`（先失败，等 Task 1.2 生成后通过）

- [ ] **Step 4: Commit**

```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/styles/baselines/compare.py tests/unit/test_visual_baseline.py && git commit -m "feat(ui): PR-C2.x — 视觉基线对比工具（compute_diff + threshold）"
```

### Task 1.2: 生成 4 张基线截图

**Files:**
- Create: `secureredact/ui/styles/baselines/manifest.json`（脚本生成后写盘）
- Create: `secureredact/ui/styles/baselines/_generate_baselines.py`（一次性脚本，不入测试）

- [ ] **Step 1: 写生成脚本**

```python
"""
一次性基线生成脚本 — PR-C2.x Task 1.2

用法:
    python -m secureredact.ui.styles.baselines._generate_baselines

产出:
    main_window_light.png / main_window_dark.png
    settings_dialog_light.png / settings_dialog_dark.png
    manifest.json（每张图的尺寸 + sha256）

不写入回归测试（只跑一次）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# 强制 offscreen 平台，CI 无显示器也能跑
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from secureredact.main import build_app  # noqa: E402
from secureredact.ui.main_window.window import MainWindow  # noqa: E402
from secureredact.ui.settings.dialog import SettingsDialog  # noqa: E402


HERE = Path(__file__).resolve().parent
SIZES = {"default": QSize(1280, 800)}


def _grab(widget, name: str, theme: str):
    from secureredact.ui.styles import StylesheetLoader

    loader = StylesheetLoader()
    loader.apply(widget, theme, scope="main")
    widget.resize(SIZES["default"])
    widget.show()
    QApplication.processEvents()
    pixmap = widget.grab()
    out = HERE / f"{name}.png"
    pixmap.save(str(out))
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    return {"file": out.name, "theme": theme, "size": list(pixmap.size().toTuple()), "sha256": sha[:16]}


def main():
    QApplication.instance() or build_app(sys.argv)
    app = QApplication.instance()

    mw = MainWindow()
    dl = SettingsDialog(mw)

    manifest = {
        "version": "1.1.13",
        "viewport": [1280, 800],
        "images": [
            _grab(mw, "main_window_light", "light"),
            _grab(mw, "main_window_dark", "dark"),
            _grab(dl, "settings_dialog_light", "light"),
            _grab(dl, "settings_dialog_dark", "dark"),
        ],
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"wrote {len(manifest['images'])} baselines to {HERE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑生成**

```bash
cd "G:/Project/SecureRedact" && python -m secureredact.ui.styles.baselines._generate_baselines 2>&1 | tail -10
```
Expected: `wrote 4 baselines to .../baselines`

- [ ] **Step 3: 验证基线像素数合理**

```bash
cd "G:/Project/SecureRedact" && python -c "
from PIL import Image
import json, pathlib
here = pathlib.Path('secureredact/ui/styles/baselines')
for img_path in sorted(here.glob('*.png')):
    im = Image.open(img_path)
    print(img_path.name, im.size, im.getextrema())
" 2>&1 | tail -10
```
Expected: 4 张图尺寸一致（1280x800），`extrema` 在每个通道都有合理 spread（不是全 0）

- [ ] **Step 4: 跑先前失败的 compare 测试**

```bash
cd "G:/Project/SecureRedact" && python -m unittest tests.unit.test_visual_baseline -v 2>&1 | tail -3
```
Expected: `Ran 1 test / OK`

- [ ] **Step 5: Commit（不入二进制图，git-lfs 或 docs-only manifest）**

由于 PNG 体积可能较大，先只 commit manifest + 测试，再单独跑 `.gitattributes` 处理：

```bash
cd "G:/Project/SecureRedact" && git add secureredact/ui/styles/baselines/_generate_baselines.py secureredact/ui/styles/baselines/manifest.json && git commit -m "test(ui): PR-C2.x — 基线 manifest + 生成脚本"
```

### Task 1.3: 视觉回归 assertion 进 CI

- [ ] **Step 1: 在 `test_visual_baseline.py` 追加场景**

```python
def test_main_window_light_unchanged(self):
    from secureredact.ui.styles.baselines import compare
    baseline = BASELINE_DIR / "main_window_light.png"
    current = BASELINE_DIR / "_current_main_window_light.png"
    # 由 harness 提前渲染 _current_*.png；CI 比对
    if not current.exists():
        self.skipTest("no current render (run CI harness first)")
    diff_ratio, total, diff = compare.compute_diff(baseline, current)
    self.assertLess(diff_ratio, compare.THRESHOLD, f"regression: {diff}/{total} pixels differ")
```

- [ ] **Step 2: 写 CI harness（独立脚本）**

新建 `scripts/render_visual_baseline.py`：

```python
"""
CI 用：渲染当前 main_window / settings_dialog 到 baselines/_current_*.png，
然后跑 tests/unit/test_visual_baseline.py。
"""
# 与 _generate_baselines.py 同样逻辑，只是输出 _current_*.png
```

- [ ] **Step 3: 接 CI**

在 `.github/workflows/ci.yml`（或当前 CI 配置）新增 step：

```yaml
- name: Visual regression
  run: |
    python scripts/render_visual_baseline.py
    python -m unittest tests.unit.test_visual_baseline -v
```

- [ ] **Step 4: Commit**

```bash
cd "G:/Project/SecureRedact" && git add tests/unit/test_visual_baseline.py scripts/render_visual_baseline.py .github/workflows/ci.yml && git commit -m "ci(ui): PR-C2.x — 视觉基线回归进 CI"
```

> **本 PR 收口**：写 `docs/refactor/c2x-task-report.md`（仿 c1-report.md 模板，含 4 张基线图引用、THRESHOLD 取值理由、CI 集成方式）。

---

## Sub-PR 2：PR-V2 6 类组件 .qss

**Goal:** 6 类高频 Qt widget（Button / Input / Tab / Card / Dock / Toolbar）抽取为独立 .qss 文件，5 状态齐全（normal / hover / pressed / disabled / focused），全部用 token 占位符。

**Architecture:** 每个组件 .qss 通过 `StylesheetLoader.apply(widget, theme, scope="<scope>")` 按需加载，与已有 `base.qss` / `menu.qss` / `progress.qss` / `workbench.qss` / `workspace.qss` 并列。

### Task 2.1: `button.qss` — QPushButton 5 状态

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_component_qss.py
import re
import unittest
from pathlib import Path

from secureredact.ui.styles.tokens import get_substitution_map


class ComponentQssTest(unittest.TestCase):
    def _check(self, name: str, required_states: list[str], required_tokens: list[str]):
        path = Path(__file__).resolve().parent.parent.parent / "secureredact" / "ui" / "styles" / f"{name}.qss"
        content = path.read_text(encoding="utf-8")
        for state in required_states:
            self.assertIn(state, content, f"{name}.qss missing state {state}")
        mapping = get_substitution_map("light")
        rendered = content.format(**mapping)
        for token in required_tokens:
            self.assertIn(token, content or rendered, f"{name}.qss missing token {token}")

    def test_button_qss_5_states(self):
        self._check(
            "button",
            required_states=[":hover", ":pressed", ":disabled", ":focus", ":checked"],
            required_tokens=["{primary}", "{text}", "{surface}", "{border}"],
        )
```

- [ ] **Step 2: 实现 `button.qss`**

新建 `secureredact/ui/styles/button.qss`，包含 QPushButton / QToolButton 全部 5 状态；颜色全部用 `{primary}` / `{surface}` / `{text}` / `{border}` / `{hover}` / `{pressed}`。

- [ ] **Step 3: 跑测试 + commit**

```bash
cd "G:/Project/SecureRedact" && python -m unittest tests.unit.test_component_qss -v 2>&1 | tail -3
git add secureredact/ui/styles/button.qss tests/unit/test_component_qss.py
git commit -m "feat(ui): PR-V2 — button.qss (QPushButton 5 状态)"
```

### Task 2.2: `input.qss` — QLineEdit/QTextEdit/QSpinBox/QComboBox 5 状态

（结构同 Task 2.1，required_states 增加 `:read-only`）

### Task 2.3: `tab.qss` — QTabWidget/QTabBar 5 状态

（required_states 含 `:tab:hover` / `:tab:selected` / `:tab:disabled`）

### Task 2.4: `card.qss` — QFrame#xxxCard variants

（required_tokens 增加 `{card_background}`，定义时用 token 占位符；Glass 检测关闭时由 StylesheetLoader 自动替换为半透明色）

### Task 2.5: `dock.qss` — QDockWidget 5 状态

（注意 Dock 的 title bar 是 QDockWidget::title 子组件，必须单独写）

### Task 2.6: `toolbar.qss` 复用 button.qss 基类

- [ ] **Step 1: 把 toolbar.qss 中 QToolButton 相关样式整段删掉，替换为 `/* @import button.qss */` 注释**

（Qt 不支持 @import；改用 StylesheetLoader 加载顺序保证 toolbar.qss 之后 load button.qss）

- [ ] **Step 2: 在 `StylesheetLoader` 增 `scope="toolbar"` 行为**

```python
def apply(self, widget, theme: str, scope: str = "main"):
    files = self._scope_files(scope)  # {"toolbar": ["base.qss", "button.qss", "toolbar.qss"]}
    ...
```

- [ ] **Step 3: Commit**

### Task 2.7: `workspace.qss` 复用 card.qss

- 同 Task 2.6 思路，把 `QFrame#workspaceCard` / `#batchDetailSection` 等 12 个 card 类抽出到 `card.qss`

### Task 2.8: PR-V2 收口报告

新建 `docs/refactor/v2-task-report.md`：
- 6 个新 .qss 文件清单
- toolbar/workspace 复用后净减行数
- 全量回归（V1 基线 449 + 6 baseline 失败保持，新增 test_component_qss.py 6 项）

---

## Sub-PR 3：PR-V4 MainWindow / SettingsDialog 内嵌 QSS 迁移

**Goal:** 把 42 处 `setStyleSheet(...)` 内嵌调用 + SettingsDialog 320 行 `_apply_dialog_theme()` f-string + ~30 处 `_apply_settings_density_styles()` 调用，全部替换为 `StylesheetLoader.apply(widget, theme, scope=...)`。

**Architecture:** 每次替换都遵循「先复制原样式进 .qss 文件 → 替换 setStyleSheet 调用为 loader.apply → 视觉对比」三步。

### Task 3.1: 提取 `theme.py` 滚动区域样式到 `scroll.qss`

- [ ] **Step 1: 把 `self.scroll.setStyleSheet(self.scroll_style.format(...))` 改为 loader.apply**

- [ ] **Step 2: 新建 `scroll.qss`**

- [ ] **Step 3: 跑全量测试 + 视觉基线（Task 1.3 harness）确认无变化**

- [ ] **Step 4: Commit**

### Task 3.2 ~ 3.7: window.py 12 处 → batch 分组

每批 2 处，连续 commit：
- Task 3.2: window.py 第 1-2 处（toolbar 区域）
- Task 3.3: window.py 第 3-5 处（mode badge / status bar）
- Task 3.4: window.py 第 6-8 处（info bar / hint bar）
- Task 3.5: window.py 第 9-10 处（workspace 状态）
- Task 3.6: window.py 第 11-12 处（zoom indicator + page indicator）
- Task 3.7: 收口验证（density.py 23 处 + batch_replace.py 6 处 + window.py 12 处 = 41 处统计 = 0）

### Task 3.8: `density.py` 23 处 → 6 个 scope

按 widget 树分组：
- scope=`density.idle` → 12 处（idle hero / idle section）
- scope=`density.workbench` → 5 处
- scope=`density.batch` → 4 处
- scope=`density.preview` → 2 处

每 scope 一个 .qss 文件：`secureredact/ui/styles/density_idle.qss` 等。

### Task 3.9: `batch_replace.py` 6 处 → `batch_replace.qss`

### Task 3.10: `SettingsDialog._apply_dialog_theme()` 320 行 f-string → `settings_dialog.qss`

- 整段 `self.setStyleSheet(f"""...""")` 替换为 `loader.apply(self, theme, scope="settings_dialog")`
- 新建 `secureredact/ui/styles/settings_dialog.qss`（约 250 行，对应原 f-string）

### Task 3.11: `_apply_settings_density_styles()` 30 处 → `settings_density.qss`

- 类似 3.10，30 处小 setStyleSheet 合并到一个 .qss

### Task 3.12: PR-V4 收口报告

新建 `docs/refactor/v4-task-report.md`：
- 迁移前/后 setStyleSheet 调用数对比
- 新增 .qss 文件清单
- 视觉基线对比图（来自 PR-C2.x harness）
- 全量回归通过

---

## Sub-PR 4：PR-C1.1 SettingsDialog 主题切换 UI

**Goal:** 用户能在「设置 → 外观」直接切换 light / dark / system，持久化到 config.json。

**Architecture:** 在 SettingsDialog 顶部「导航」加一项「7 外观」；右侧内容区加一个 `QComboBox`（3 选项），change 事件 → 调 MainWindow.set_theme(name) → MainWindow 自己持久化。

### Task 4.1: 新增「外观」分节到 SettingsDialog

**Files:**
- Modify: `secureredact/ui/settings/dialog.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_settings_dialog_theme_ui.py
class SettingsDialogThemeUiTest(unittest.TestCase):
    def test_appearance_section_exists(self):
        from secureredact.ui.settings.dialog import SettingsDialog
        # 用 mock parent + 必要参数构造
        dlg = SettingsDialog(parent=None, current_rules=[], use_enhance=False,
                              custom_keywords="", scan_level=2.0)
        titles = dlg._settings_nav_base_titles
        self.assertTrue(any("外观" in t or "Appearance" in t for t in titles),
                        f"no appearance nav item in {titles}")

    def test_theme_combo_has_three_options(self):
        dlg = SettingsDialog(parent=None, current_rules=[], use_enhance=False,
                              custom_keywords="", scan_level=2.0)
        # 找到 appearance 对应的 QComboBox
        combos = [cb for cb in dlg.findChildren(QComboBox)
                  if cb.objectName() == "themeModeCombo"]
        self.assertEqual(len(combos), 1)
        self.assertEqual(combos[0].count(), 3)
```

- [ ] **Step 2: 修改 dialog.py**

在 `_settings_nav_base_titles` 末尾追加 `"7 外观"`；新增 `box_appearance` 卡片（含 `QComboBox#themeModeCombo`，3 选项：浅色 / 深色 / 跟随系统）。

- [ ] **Step 3: 跑测试**

```bash
cd "G:/Project/SecureRedact" && python -m unittest tests.unit.test_settings_dialog_theme_ui -v 2>&1 | tail -3
```
Expected: `Ran 2 tests / OK`

- [ ] **Step 4: Commit**

```bash
git add secureredact/ui/settings/dialog.py tests/unit/test_settings_dialog_theme_ui.py
git commit -m "feat(ui): PR-C1.1 — SettingsDialog 新增外观分节（theme combo）"
```

### Task 4.2: theme combo 联动 MainWindow.set_theme

- [ ] **Step 1: 写失败测试**

```python
def test_theme_change_calls_main_window(self):
    parent = MockMainWindow()
    dlg = SettingsDialog(parent=parent, current_rules=[], use_enhance=False,
                          custom_keywords="", scan_level=2.0)
    combo = dlg.findChild(QComboBox, "themeModeCombo")
    combo.setCurrentIndex(2)  # system
    dlg._on_theme_mode_changed(2)
    self.assertEqual(parent.last_set_theme, "system")
```

- [ ] **Step 2: 实现 `_on_theme_mode_changed`**

```python
def _on_theme_mode_changed(self, index: int):
    name = {0: "light", 1: "dark", 2: "system"}.get(index, "light")
    mw = self.parent()
    if mw is not None and hasattr(mw, "set_theme"):
        mw.set_theme(name)
```

- [ ] **Step 3: commit**

### Task 4.3: 切换后持久化验证

- [ ] **Step 1: 写失败测试**

```python
def test_theme_persists_to_config(self, tmp_path):
    config_path = tmp_path / "config.json"
    config = SimpleConfig(str(config_path))
    mw = MainWindow.__new__(MainWindow)
    mw.config = config
    mw.theme_name = "light"
    mw.set_theme("dark")
    assert config.get("app.theme") == "dark"
```

- [ ] **Step 2: 验证 `theme.py` 的 `set_theme` 已写 `app.theme`（已有则跳过）**

- [ ] **Step 3: commit（若 `set_theme` 未持久化，补一行；否则只补测试）**

### Task 4.4: PR-C1.1 收口报告

新建 `docs/refactor/c11-task-report.md`：
- 主题切换 UI 截图（来自 PR-C2.x harness，3 主题 × 1 视图 = 3 张）
- config.json schema 变化（仅 `app.theme` 字段）
- 全量回归通过

---

## 自审清单（执行前最后一遍）

- [x] **Spec 覆盖**：Spec A §2 目标（设计 token / 6 类组件 / Glass / 视觉基线 / 主题切换 UI）全部有 Sub-PR 覆盖
- [x] **占位符扫描**：本 plan 无 TBD/TODO/FIXME；Task 编号完整（0.1, 0.2, 1.1-1.3, 2.1-2.8, 3.1-3.12, 4.1-4.4）
- [x] **类型一致性**：所有 token 字段仍来自 `tokens.py` `Tokens` dataclass；Glass 降级仅替换 `card_background` / `dock_background` 两个 key，不破坏 dataclass 字段
- [x] **测试设计**：TDD 风格（每 task 写失败测试 → 实现 → 通过）；新增 ≥ 12 项单元测试
- [x] **Commit 粒度**：~22 task → ~22 commit（每个 sub-PR 收口报告单独 1 commit = 共 ~26 commit），每 commit 独立 bisect
- [x] **风险控制**：theme.py MainWindowThemeMixin 不动；mixin 类结构不动；token 数值不动；所有视觉变化经 PR-C2.x 基线 + 人工截图双重验证

---

## 范围外（明确不做）

1. **替换所有 hex 字面量为新 token**（Spec A §4.1 末尾的颜色翻新）→ 等 Plan 2b 全部 sub-PR 收口后做 Plan 2c
2. **视觉策略调整**（Spec B/C/D 决策）→ 单独 brainstorm
3. **Word 替换规则编辑器重做**（PR-W 系列，独立轨道）→ 不在视觉重构范围
4. **打包脚本中的图标 / 品牌资源更新**（v38 branding 已就位）→ 不再触碰
5. **Logo 重设 / 品牌重塑**（品牌资产已锁定）→ 不重做
6. **SettingsDialog 完全用 .qss 接管密度逻辑**（`_apply_settings_density_styles()` → 完整 .qss）→ PR-V4 Task 3.11 只做 80% 迁移，剩下 20% 字号动态计算留在 Python 层（无 .qss 等价物）
7. **PR-V1 §4.1 颜色 hex 全量更新** → 推迟到 Plan 2c；本 PR-V2/V4 仅做现有颜色搬家到 token，不改 token 数值

---

## 执行选项

本 plan 已完成并保存到 `docs/superpowers/plans/2026-08-30-visual-component-baseline.md`。

两种执行方式：

**1. Subagent-Driven（推荐）** — 每个 sub-PR 派 fresh subagent，sub-PR 之间做 review，迭代快；尤其适合 PR-V2（6 个组件文件并行起草 + 互审）

**2. Inline Execution** — 当前会话顺序执行，到 sub-PR 边界暂停确认；适合你想控制每个 commit 细节的情况

请选择执行方式，或先确认 plan 细节后再启动。

推荐默认：**Subagent-Driven**，按 sub-PR 切 4 批 agent，每批完成后做 1 次 review + 1 次 sub-PR 收口报告 + 1 次全量回归。

---

## 改动量预估

| Sub-PR | 新增文件 | 修改文件 | Commit 数 | 测试增项 | 行数变化 |
|---|---|---|---|---|---|
| 前置 0 | 2 | 0 | 2 | 2 | +80 |
| PR-C2.x | 5 | 1 | 3 | 2 | +200（含基线 PNG manifest） |
| PR-V2 | 7 | 3 | 9 | 7 | +500 / -50 |
| PR-V4 | 6 | 4 | 13 | 5 | +800 / -900（净减） |
| PR-C1.1 | 1 | 1 | 4 | 3 | +150 |
| **合计** | **21** | **9** | **31** | **19** | **+1730 / -950** |

预计每个 sub-PR 工作量：
- 前置 0：≤ 1 小时
- PR-C2.x：≤ 1 小时
- PR-V2：1-2 小时
- PR-V4：2-3 小时（最重）
- PR-C1.1：≤ 1 小时

**总计：约 1 个工作日内可全部完成（subagent-driven 模式）**。
