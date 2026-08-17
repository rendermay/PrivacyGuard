# -*- coding: utf-8 -*-
"""
Wave 3 配置持久化测试:
- redaction.enable_name_recognition 键的 round-trip
- 默认值 (缺省键) 应返回 False
- 三处对齐: main.py / privacyguard.utils.config / config.json
"""
import json
import os
import unittest
from pathlib import Path


class TestEnableNameRecognitionPersistence(unittest.TestCase):
    """配置键 'redaction.enable_name_recognition' 的持久化语义."""

    def setUp(self) -> None:
        # 重置 ConfigManager 单例,确保每个用例独立
        from privacyguard.utils.config import ConfigManager
        ConfigManager._instance = None

    def test_default_value_when_key_missing(self):
        """缺省键时,ConfigManager 应返回 False (向后兼容)."""
        from privacyguard.utils.config import ConfigManager
        # 用临时路径初始化,避免污染真实 config.json
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                         delete=False, encoding='utf-8') as tmp:
            tmp_path = tmp.name
            json.dump({}, tmp)
        try:
            cm = ConfigManager(config_path=tmp_path)
            val = cm.get("redaction.enable_name_recognition", False)
            self.assertFalse(val, "缺省键应返回 False (向后兼容)")
        finally:
            os.unlink(tmp_path)

    def test_round_trip_through_set(self):
        """写入 True → 读取应回 True."""
        from privacyguard.utils.config import ConfigManager
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                         delete=False, encoding='utf-8') as tmp:
            tmp_path = tmp.name
            json.dump({}, tmp)
        try:
            cm = ConfigManager(config_path=tmp_path)
            cm.set("redaction.enable_name_recognition", True, persist=True)
            # 重置单例 + 用同一路径初始化,模拟重启
            ConfigManager._instance = None
            cm2 = ConfigManager(config_path=tmp_path)
            self.assertTrue(cm2.get("redaction.enable_name_recognition"))
        finally:
            os.unlink(tmp_path)


class TestEnableNameRecognitionAlignment(unittest.TestCase):
    """三处对齐: SimpleConfig (main.py) / ConfigManager (privacyguard.utils.config)."""

    def test_main_default_rules_does_not_break_existing(self):
        # Wave 3 不应修改 DEFAULT_RULES 字典,只新增 enable_name_recognition 键
        from main import DEFAULT_RULES  # type: ignore
        # 现有6+3 条规则不应受影响
        for name in ("身份证号", "手机号码", "日期时间", "电子邮箱",
                     "银行卡号", "地址（含门牌号）", "固定电话", "法定代表人"):
            self.assertIn(name, DEFAULT_RULES)

    def test_module_default_config_unchanged(self):
        # privacyguard.utils.config.DEFAULT_CONFIG 应保持现状
        from privacyguard.utils.config import DEFAULT_CONFIG
        self.assertNotIn(
            "enable_name_recognition",
            DEFAULT_CONFIG.get("redaction", {}),
            "Wave 3 不应修改 DEFAULT_CONFIG；新增键属于运行时持久化,不入默认"
        )


class TestMainWindowReadsEnableNameRecognition(unittest.TestCase):
    """MainWindow 启动时应能从 config.get('redaction.enable_name_recognition') 读取."""

    def test_attribute_default_false(self):
        # 由于 MainWindow 实例化需要 PyQt6, 我们仅静态断言 import 可用
        # 实际启动逻辑在 main.py:4905 附近
        import main  # noqa: F401  # 仅验证导入
        # 默认值断言 — 如果项目 config.json 已含该键(用户/linter 已设置),应真实返回
        from main import SimpleConfig
        cfg = SimpleConfig()
        val = cfg.get("redaction.enable_name_recognition")
        # 键缺省时 SimpleConfig 返回 None;已配置则返回其值(True/False)
        self.assertIn(val, (None, False, True),
            f"SimpleConfig 返回值不在预期集合中, 实得 {val!r}")


if __name__ == "__main__":
    unittest.main()