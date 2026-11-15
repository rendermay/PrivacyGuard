"""P0-5 回归: 配置文件路径解析统一(修复「配置双源分裂」)。

背景:
    v1.1.13 之前 SimpleConfig 的默认路径是 secureredact/config.json,
    ConfigManager 的默认路径是仓库根 config.json —— 两套系统读的不是同一个文件。
    后果:
      1. 用户在根 config.json 里改的设置, 运行期读不到
      2. 打包版只把根 config.json 打进包, 运行时配置 100% 丢失
      3. 设置中心保存到 secureredact/config.json, 与用户看到的文件不是同一个

本文件锁定修复后的行为, 防止回归。
"""
import json
import os
import sys
import unittest
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestConfigPathResolution(unittest.TestCase):
    """路径解析必须指向仓库根 config.json, 且只有一份。"""

    def test_no_duplicate_config_file_in_package(self):
        """secureredact/config.json 必须不存在 —— 它就是双源分裂的元凶。"""
        stray = REPO_ROOT / "secureredact" / "config.json"
        self.assertFalse(
            stray.exists(),
            f"secureredact/config.json 重新出现了 —— 会再次造成配置双源分裂: {stray}",
        )

    def test_resolve_config_paths_points_to_repo_root(self):
        """开发树里解析出的写入路径必须是仓库根 config.json。"""
        from secureredact.utils.config import resolve_config_paths

        write_path, base_path = resolve_config_paths()
        self.assertEqual(
            os.path.normcase(os.path.abspath(write_path)),
            os.path.normcase(str(REPO_ROOT / "config.json")),
            f"配置写入路径应指向仓库根 config.json, 实际: {write_path}",
        )
        # 开发树里读写同路径, 无独立只读基线
        self.assertIsNone(base_path)

    def test_simple_config_reads_repo_root_config(self):
        """SimpleConfig() 必须读到仓库根 config.json 的真实值。"""
        from secureredact.utils.config import SimpleConfig

        config = SimpleConfig()
        self.assertEqual(config.get("redaction.replacement_text"), "*")
        self.assertEqual(config.get("redaction.scan.default_level"), 1.5)
        # 根 config.json 的顶层键必须全部可见
        for key in ("app", "ocr", "redaction", "security", "ui", "advanced"):
            self.assertIsNotNone(config.get(key), f"配置缺少顶层键: {key}")

    def test_config_manager_and_simple_config_agree(self):
        """两套配置系统必须读同一个文件(原缺陷: 读的是两个不同文件)。"""
        from secureredact.utils.config import ConfigManager, SimpleConfig

        simple = SimpleConfig()
        ConfigManager._instance = None
        manager = ConfigManager()

        for key in ("redaction.replacement_text", "redaction.scan.default_level"):
            self.assertEqual(
                simple.get(key),
                manager.get(key),
                f"{key} 在 SimpleConfig 与 ConfigManager 之间不一致",
            )

    def test_simple_config_explicit_path_still_supported(self):
        """显式传入 config_path 时行为不变(测试与用户配置均依赖)。"""
        from secureredact.utils.config import SimpleConfig

        fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump({"redaction": {"replacement_text": "[X]"}}, handle)
            config = SimpleConfig(temp_path)
            self.assertEqual(config.get("redaction.replacement_text"), "[X]")
        finally:
            os.remove(temp_path)


class TestConfigDerivedConstants(unittest.TestCase):
    """P0-5: 配置项不得静默失效 —— 常量必须从 config 派生。"""

    def test_zoom_bounds_come_from_config(self):
        """ZOOM_MIN / ZOOM_MAX 必须来自 config, 不是硬编码。"""
        import secureredact

        from secureredact.utils.config import config

        self.assertEqual(secureredact.ZOOM_MIN, config.get("ocr.zoom_min", 0.5))
        self.assertEqual(secureredact.ZOOM_MAX, config.get("ocr.zoom_max", 4.0))

    def test_app_name_comes_from_config(self):
        """APP_NAME / __app_name__ 必须来自 config(窗口标题与反馈框曾不一致)。"""
        import secureredact

        from secureredact.utils.config import config

        expected = config.get("app.name", "SecureRedact 信息脱敏助手")
        self.assertEqual(secureredact.APP_NAME, expected)
        self.assertEqual(secureredact.__app_name__, expected)

    def test_progress_interval_comes_from_config(self):
        """两个 worker 的 PROGRESS_UPDATE_INTERVAL 必须来自 config。"""
        from secureredact.utils.config import config
        from secureredact.workers.ocr_worker import (
            PROGRESS_UPDATE_INTERVAL as ocr_interval,
        )
        from secureredact.workers.word_worker import (
            PROGRESS_UPDATE_INTERVAL as word_interval,
        )

        expected = config.get("ocr.progress_update_interval", 0.05)
        self.assertEqual(ocr_interval, expected)
        self.assertEqual(word_interval, expected)

    def test_debug_mode_reads_env_and_config(self):
        """DEBUG_MODE 必须同时认 env 与 config(原实现只看其中之一)。"""
        import importlib

        from secureredact.ui.main_window import canvas

        # 默认两个开关都关 -> 关闭
        self.assertFalse(canvas.DEBUG_MODE)

        # env 打开 -> canvas 必须跟着打开
        old = os.environ.get("PRIVACYGUARD_DEBUG")
        os.environ["PRIVACYGUARD_DEBUG"] = "true"
        try:
            canvas2 = importlib.reload(canvas)
            self.assertTrue(
                canvas2.DEBUG_MODE,
                "PRIVACYGUARD_DEBUG=true 时 canvas.DEBUG_MODE 应为 True",
            )
        finally:
            if old is None:
                os.environ.pop("PRIVACYGUARD_DEBUG", None)
            else:
                os.environ["PRIVACYGUARD_DEBUG"] = old
            importlib.reload(canvas)


class TestThemePersistence(unittest.TestCase):
    """P0-5: 主题切换必须真的落盘, 且读写用同一个配置键。"""

    def test_set_theme_persists_to_ui_theme(self):
        """set_theme 后 ui.theme 必须变化(原实现被局部变量遮蔽, 永不持久化)。"""
        from secureredact.ui.main_window.theme import MainWindowThemeMixin
        from secureredact.utils.config import config

        class _Stub(MainWindowThemeMixin):
            def __init__(self):
                self.theme_name = "light"
                self.applied = None

            def _apply_theme(self, name=None):
                self.applied = name
                self.theme_name = name

        stub = _Stub()
        old_value = config.get("ui.theme")
        try:
            stub.set_theme("dark")
            self.assertEqual(stub.applied, "dark")
            self.assertEqual(
                config.get("ui.theme"),
                "dark",
                "set_theme 后 ui.theme 未落盘 —— 主题切换后重启会归位",
            )
        finally:
            # 还原, 避免污染仓库里的 config.json
            if old_value is not None:
                config.set("ui.theme", old_value, persist=True)
            else:
                config._config.get("ui", {}).pop("theme", None)
                config.save()

    def test_theme_config_key_is_ui_theme(self):
        """主题配置键必须是 ui.theme(与出厂 config.json / DEFAULT_CONFIG 一致)。"""
        from secureredact.utils.config import DEFAULT_CONFIG

        self.assertIn("theme", DEFAULT_CONFIG.get("ui", {}))

        repo_config = json.loads(
            (REPO_ROOT / "config.json").read_text(encoding="utf-8")
        )
        self.assertIn("theme", repo_config.get("ui", {}))
        # app 下不应再出现主题键(那是旧实现写出来的, 读侧从不认)
        self.assertNotIn("theme", repo_config.get("app", {}))

    def test_window_reads_ui_theme(self):
        """MainWindow 初始化读的是 ui.theme, 不是 app.theme。"""
        window_src = (
            REPO_ROOT / "secureredact" / "ui" / "main_window" / "window.py"
        ).read_text(encoding="utf-8")
        self.assertIn('config.get("ui.theme"', window_src)
        self.assertNotIn('config.get("app.theme"', window_src)


class TestFrozenConfigPaths(unittest.TestCase):
    """模拟 PyInstaller 冻结形态, 验证配置路径解析。

    这条分支在开发机上永远不会执行(只有打包后的 exe 才会走),
    而打包版配置 100% 丢失正是本版本修复的缺陷 —— 必须有测试守护。
    """

    def _simulate_frozen(self, meipass):
        old_frozen = getattr(sys, "frozen", None)
        old_meipass = getattr(sys, "_MEIPASS", None)
        try:
            sys.frozen = True
            sys._MEIPASS = meipass
            yield
        finally:
            if old_frozen is None:
                try:
                    delattr(sys, "frozen")
                except AttributeError:
                    pass
            else:
                sys.frozen = old_frozen
            if old_meipass is None:
                try:
                    delattr(sys, "_MEIPASS")
                except AttributeError:
                    pass
            else:
                sys._MEIPASS = old_meipass

    def test_frozen_reads_bundled_config_and_writes_user_dir(self):
        """冻结态: 基线读 _MEIPASS/config.json, 写入用户目录 ~/.secureredact。"""
        from contextlib import contextmanager
        from secureredact.utils import config as cfg_mod

        @contextmanager
        def _frozen(meipass):
            old_frozen = getattr(sys, "frozen", None)
            old_meipass = getattr(sys, "_MEIPASS", None)
            try:
                sys.frozen = True
                sys._MEIPASS = meipass
                yield
            finally:
                if old_frozen is None:
                    try:
                        delattr(sys, "frozen")
                    except AttributeError:
                        pass
                else:
                    sys.frozen = old_frozen
                if old_meipass is None:
                    try:
                        delattr(sys, "_MEIPASS")
                    except AttributeError:
                        pass
                else:
                    sys._MEIPASS = old_meipass

        with tempfile.TemporaryDirectory() as tmp:
            meipass = os.path.join(tmp, "_internal")
            os.makedirs(meipass)
            bundled = os.path.join(meipass, "config.json")
            with open(bundled, "w", encoding="utf-8") as handle:
                json.dump({"redaction": {"replacement_text": "[FROZEN]"}}, handle)

            with _frozen(meipass):
                write_path, base_path = cfg_mod.resolve_config_paths()

            self.assertIsNotNone(base_path, "冻结态必须找到随包出厂配置")
            self.assertEqual(
                os.path.normcase(os.path.abspath(base_path)),
                os.path.normcase(os.path.abspath(bundled)),
                "冻结态基线必须是 _MEIPASS/config.json",
            )
            self.assertEqual(
                os.path.normcase(os.path.abspath(write_path)),
                os.path.normcase(os.path.abspath(os.path.expanduser("~/.secureredact/config.json"))),
                "冻结态写入必须是用户目录(安装到 Program Files 时只读)",
            )

    def test_frozen_simple_config_reads_bundled_config(self):
        """冻结态下 SimpleConfig 必须真的读到随包出厂配置(打包版配置丢失的回归守护)。"""
        from contextlib import contextmanager
        from secureredact.utils.config import SimpleConfig

        @contextmanager
        def _frozen(meipass):
            old_frozen = getattr(sys, "frozen", None)
            old_meipass = getattr(sys, "_MEIPASS", None)
            try:
                sys.frozen = True
                sys._MEIPASS = meipass
                yield
            finally:
                if old_frozen is None:
                    try:
                        delattr(sys, "frozen")
                    except AttributeError:
                        pass
                else:
                    sys.frozen = old_frozen
                if old_meipass is None:
                    try:
                        delattr(sys, "_MEIPASS")
                    except AttributeError:
                        pass
                else:
                    sys._MEIPASS = old_meipass

        with tempfile.TemporaryDirectory() as tmp:
            meipass = os.path.join(tmp, "_internal")
            os.makedirs(meipass)
            with open(os.path.join(meipass, "config.json"), "w", encoding="utf-8") as handle:
                json.dump({"redaction": {"replacement_text": "[FROZEN]"}}, handle)

            with _frozen(meipass):
                config = SimpleConfig()

            self.assertEqual(
                config.get("redaction.replacement_text"),
                "[FROZEN]",
                "冻结态必须读到随包出厂配置 —— 打包版配置 100% 丢失的回归守护",
            )


if __name__ == "__main__":
    unittest.main()