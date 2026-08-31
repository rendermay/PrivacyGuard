"""
PR-C2.x Task 1.3: CI 视觉基线 harness

渲染当前 main_window / settings_dialog 到 ``_current_*.png``,
供 ``tests/unit/test_visual_baseline.py::test_main_window_light_unchanged``
等基线回归测试做像素级对比。

与 ``secureredact/ui/styles/baselines/_generate_baselines.py``(Task 1.2)的区别:

| 维度        | ``_generate_baselines.py``            | 本脚本(CI)                          |
|-------------|---------------------------------------|--------------------------------------|
| 触发        | 手动 / 一次性                          | 每次 CI 自动                          |
| 输出        | ``main_window_*.png``(基线,入库)     | ``_current_main_window_*.png``(临时) |
| Manifest    | 写 ``manifest.json``                  | 不写(测试不需要)                     |
| 是否入测试  | 否                                    | 否(产出物入测试)                     |

设计原则:

- 共享渲染逻辑走 ``secureredact/ui/styles/baselines/_render.py``,与基线生成脚本一致。
- 强制 ``QT_QPA_PLATFORM=offscreen``,允许 CI / headless 环境运行。
- ``_current_*.png`` 写入 baselines 目录(测试通过 BASELINE_DIR 直接定位),
  不入 git(``__pycache__`` 同级约定,后续若要加 ``.gitignore`` 即可)。
- 失败不抛 exit 0 — 调用方 ``tests/unit/test_visual_baseline`` 必须看到 PNG 才能跑;
  如果 harness 自身崩了,CI 早就在渲染 step 失败。

用法:

    python scripts/render_visual_baseline.py
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
from secureredact.ui.styles.baselines._render import build_app, grab  # noqa: E402
from secureredact.utils.config import SimpleConfig  # noqa: E402


# 与测试一致:tests/unit/test_visual_baseline.py 用同款相对路径定位
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
BASELINE_DIR = (
    PROJECT_ROOT / "secureredact" / "ui" / "styles" / "baselines"
)


def _make_minimal_config() -> SimpleConfig:
    """给 SettingsDialog 一个最小可用 SimpleConfig,与 _generate_baselines.py 一致。"""
    tmp = tempfile.mkdtemp(prefix="secureredact_baseline_ci_")
    cfg_path = os.path.join(tmp, "config.json")
    Path(cfg_path).write_text("{}", encoding="utf-8")
    return SimpleConfig(cfg_path)


def render_current(out_dir: Path = BASELINE_DIR) -> list[str]:
    """渲染 4 张 _current_*.png,返回写入的文件名列表。

    与基线生成一致(MainWindow LIGHT/DARK + SettingsDialog LIGHT/DARK),
    只是文件名加 ``_current_`` 前缀,manifest 不写。
    """
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

    rendered = [
        grab(mw, "_current_main_window_light", "light", out_dir),
        grab(mw, "_current_main_window_dark", "dark", out_dir),
        grab(dl, "_current_settings_dialog_light", "light", out_dir),
        grab(dl, "_current_settings_dialog_dark", "dark", out_dir),
    ]
    return [entry["file"] for entry in rendered]


def main() -> int:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    files = render_current(BASELINE_DIR)
    for name in files:
        print(f"rendered {BASELINE_DIR / name}")
    print(f"done: {len(files)} current renders -> {BASELINE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
