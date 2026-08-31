"""
一次性基线截图生成脚本 — SecureRedact v1.1.13 PR-C2.x Task 1.2

**不入回归测试**,只在以下时机手动运行:

    QT_QPA_PLATFORM=offscreen python -m secureredact.ui.styles.baselines._generate_baselines

产出 4 张基线截图(PNG) + 1 份 manifest.json:

    main_window_light.png
    main_window_dark.png
    settings_dialog_light.png
    settings_dialog_dark.png
    manifest.json          # 每张图的 file / theme / size / sha256[:16]

注意:
- 强制设置 QT_QPA_PLATFORM=offscreen,允许在 CI / headless 环境跑。
- 使用 PyQt6 原生 `QWidget.grab()` 而非 Playwright(项目已有 Playwright,
  但 PyQt grab 与实际渲染管线一致,基线对比更可靠)。
- Manifest 的 sha256 用于在 PR-C2.x 后续 task 验证「基线是否被改过」。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


# 必须在所有 Qt / PyQt6 import 之前设置 offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


from PyQt6.QtCore import QSize  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from secureredact.ui.main_window.window import MainWindow  # noqa: E402
from secureredact.ui.settings.dialog import SettingsDialog  # noqa: E402
from secureredact.ui.styles.loader import StylesheetLoader  # noqa: E402
from secureredact.utils.config import SimpleConfig  # noqa: E402


HERE = Path(__file__).resolve().parent
SIZES = {"default": QSize(1280, 800)}


def _grab(widget, name: str, theme: str) -> dict:
    """对 widget 应用指定主题并 grab 成 PNG,返回 manifest 条目。"""
    loader = StylesheetLoader()
    loader.apply(widget, theme, scope="main")
    widget.resize(SIZES["default"])
    widget.show()
    QApplication.processEvents()
    pixmap = widget.grab()
    out = HERE / f"{name}.png"
    pixmap.save(str(out))
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    return {
        "file": out.name,
        "theme": theme,
        "size": [pixmap.width(), pixmap.height()],
        "sha256": sha[:16],
    }


def _build_app(argv: list[str]) -> QApplication:
    """构造 QApplication(已有则复用,避免 setStyleSheet 后重启样式)。"""
    app = QApplication.instance()
    if app is not None:
        return app
    return QApplication(argv)


def _make_minimal_config() -> SimpleConfig:
    """给 SettingsDialog 一个最小可用 SimpleConfig(config_manager=None 时会读默认 config.json)。"""
    import tempfile

    tmp = tempfile.mkdtemp(prefix="secureredact_baseline_")
    cfg_path = os.path.join(tmp, "config.json")
    # 最小可工作 JSON — 字段缺失时 SimpleConfig 会回退到默认值
    Path(cfg_path).write_text("{}", encoding="utf-8")
    return SimpleConfig(cfg_path)


def main() -> int:
    app = _build_app(sys.argv)

    config = _make_minimal_config()

    mw = MainWindow()
    dl = SettingsDialog(
        parent=mw,
        current_rules=[],
        use_enhance=False,
        custom_keywords="",
        scan_level=2.0,
        config_manager=config,
    )

    images = [
        _grab(mw, "main_window_light", "light"),
        _grab(mw, "main_window_dark", "dark"),
        _grab(dl, "settings_dialog_light", "light"),
        _grab(dl, "settings_dialog_dark", "dark"),
    ]

    manifest = {
        "version": "1.1.13",
        "viewport": [SIZES["default"].width(), SIZES["default"].height()],
        "images": images,
    }

    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"wrote {len(images)} baselines to {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())