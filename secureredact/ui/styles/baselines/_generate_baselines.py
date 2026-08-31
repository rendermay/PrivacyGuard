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
- 共享的 grab/manifest 逻辑已迁到 `_render.py`(Task 1.3),保持本脚本
  与 `scripts/render_visual_baseline.py` 的行为一致。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


# 必须在所有 Qt / PyQt6 import 之前设置 offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


from PyQt6.QtWidgets import QApplication  # noqa: E402

from secureredact.ui.main_window.window import MainWindow  # noqa: E402
from secureredact.ui.settings.dialog import SettingsDialog  # noqa: E402
from secureredact.ui.styles.baselines._render import build_app, grab, write_manifest  # noqa: E402
from secureredact.utils.config import SimpleConfig  # noqa: E402


HERE = Path(__file__).resolve().parent


def _make_minimal_config() -> SimpleConfig:
    """给 SettingsDialog 一个最小可用 SimpleConfig(config_manager=None 时会读默认 config.json)。"""
    tmp = tempfile.mkdtemp(prefix="secureredact_baseline_")
    cfg_path = os.path.join(tmp, "config.json")
    # 最小可工作 JSON — 字段缺失时 SimpleConfig 会回退到默认值
    Path(cfg_path).write_text("{}", encoding="utf-8")
    return SimpleConfig(cfg_path)


def main() -> int:
    app: QApplication = build_app(sys.argv)

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
        grab(mw, "main_window_light", "light", HERE),
        grab(mw, "main_window_dark", "dark", HERE),
        grab(dl, "settings_dialog_light", "light", HERE),
        grab(dl, "settings_dialog_dark", "dark", HERE),
    ]

    manifest_path = write_manifest(HERE, images, version="1.1.13")

    print(f"wrote {len(images)} baselines to {HERE}")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
