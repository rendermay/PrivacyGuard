"""
PR-C2.x Task 1.3: 视觉基线渲染工具(共享层)

把 `_generate_baselines.py`(Task 1.2,写基线)和 `scripts/render_visual_baseline.py`
(Task 1.3,CI 渲染当前快照)共用的 grab/manifest 逻辑提到此处,
让两处脚本代码一致、避免漂移。

不放入回归测试 — 渲染层依赖 PyQt6 + offscreen 平台,
真正的回归由 `tests/unit/test_visual_baseline.py::test_main_window_light_unchanged`
对生成的 `_current_*.png` 与基线 `main_window_*.png` 做像素级断言。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, TypedDict

# 必须在所有 Qt / PyQt6 import 之前设置 offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from secureredact.ui.styles.loader import StylesheetLoader  # noqa: E402


# 基线视口尺寸(与 Task 1.2 manifest 保持一致)
DEFAULT_SIZE = QSize(1280, 800)


class BaselineEntry(TypedDict):
    """单张基线/当前快照的 manifest 条目。"""

    file: str
    theme: str
    size: list[int]
    sha256: str


class Manifest(TypedDict):
    """基线 manifest。"""

    version: str
    viewport: list[int]
    images: list[BaselineEntry]


def build_app(argv: list[str]) -> QApplication:
    """构造 QApplication(已有则复用,避免 setStyleSheet 后重启样式)。"""
    app = QApplication.instance()
    if app is not None:
        return app  # type: ignore[return-value]
    return QApplication(argv)


def grab(widget: QWidget, name: str, theme: str, out_dir: Path) -> BaselineEntry:
    """对 widget 应用指定主题并 grab 成 PNG,返回 manifest 条目。

    Args:
        widget: 已经实例化好的 MainWindow / SettingsDialog。
        name:   输出文件名前缀(不含后缀),如 ``main_window_light``。
        theme:  ``light`` / ``dark``。
        out_dir: PNG 落盘目录。

    Returns:
        BaselineEntry — file / theme / size / sha256[:16]。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    loader = StylesheetLoader()
    loader.apply(widget, theme, scope="main")
    widget.resize(DEFAULT_SIZE)
    widget.show()
    QApplication.processEvents()
    pixmap = widget.grab()
    out = out_dir / f"{name}.png"
    pixmap.save(str(out))
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    return {
        "file": out.name,
        "theme": theme,
        "size": [pixmap.width(), pixmap.height()],
        "sha256": sha[:16],
    }


def write_manifest(
    out_dir: Path,
    entries: Iterable[BaselineEntry],
    version: str = "1.1.13",
) -> Path:
    """写一份 manifest.json,记录每张图的 file/theme/size/sha256[:16]。

    Args:
        out_dir: manifest 落盘目录(通常与 PNG 同目录)。
        entries: 全部抓取的图片条目。
        version: 版本号,默认 ``1.1.13``(与 plan §Task 1.2 一致)。

    Returns:
        manifest 文件的 Path。
    """
    manifest: Manifest = {
        "version": version,
        "viewport": [DEFAULT_SIZE.width(), DEFAULT_SIZE.height()],
        "images": list(entries),
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest_path


__all__ = [
    "DEFAULT_SIZE",
    "BaselineEntry",
    "Manifest",
    "build_app",
    "grab",
    "write_manifest",
]
