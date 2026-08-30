"""
SecureRedact 配置管理模块

v1.1.11: 配置系统实现 - 支持 JSON 配置文件、热重载、向后兼容
"""

import json
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Union
from pathlib import Path


class ConfigError(Exception):
    """配置错误基类"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证错误"""
    pass


class ConfigNotFoundError(ConfigError):
    """配置文件未找到"""
    pass


# 默认配置常量
DEFAULT_CONFIG = {
    "version": "1.0",
    "app": {
        "name": "SecureRedact 信息脱敏助手",
        "window": {
            "default_width": 1300,
            "default_height": 900,
            "min_width": 900,
            "min_height": 600,
            "dialog_settings_width": 550,
            "dialog_settings_height": 700,
            "dialog_image_list_width": 600,
            "dialog_image_list_height": 500,
            "dialog_feedback_width": 480,
            "dialog_feedback_height": 600
        },
        "feedback_url": "https://fcnwakmkeuz7.feishu.cn/share/base/form/shrcnEM1JEbdIKzdB400egj9lHe"
    },
    "redaction": {
        "default_rules": {
            "身份证号": {
                "pattern": r"(?<!\d)([1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]|\d{15})(?!\d)",
                "enabled": True,
                "description": "匹配15位或18位身份证号码",
                "mask_mode": "default",
                "mask_keep_prefix": 6,
                "mask_keep_suffix": 4,
                "mask_char": "*",
            },
            "手机号码": {
                "pattern": r"(?<!\d)(1[3-9]\d{9})(?!\d)",
                "enabled": True,
                "description": "匹配中国大陆手机号码",
                "mask_mode": "default",
                "mask_keep_prefix": 3,
                "mask_keep_suffix": 4,
                "mask_char": "*",
            },
            "日期时间": {
                "pattern": r"\d{4}[年\-\.]\d{1,2}[月\-\.]\d{1,2}[日]?",
                "enabled": False,
                "description": "匹配日期格式。v1.1.13 起默认禁用 (用户决策: 选 B 不脱敏, 过度脱敏风险高于收益)",
                "mask_mode": "default",
                "mask_keep_prefix": 0,
                "mask_keep_suffix": 0,
                "mask_char": "*",
            },
            "电子邮箱": {
                "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "enabled": True,
                "description": "匹配电子邮箱地址",
                "mask_mode": "email",
                "mask_keep_prefix": 0,
                "mask_keep_suffix": 0,
                "mask_char": "*",
            },
            "银行卡号": {
                "pattern": r"(?<!\d)([1-9]\d{12,18})(?!\d)",
                "enabled": True,
                "description": "匹配13-19位银行卡号",
                "mask_mode": "default",
                "mask_keep_prefix": 4,
                "mask_keep_suffix": 4,
                "mask_char": "*",
            },
            "印章": {
                "pattern": "__SEAL_DETECTION__",
                "enabled": False,
                "description": "使用 OpenCV 自动检测并脱敏红色印章区域"
            },
            "地址（含门牌号）": {
                "pattern": r"(?:[一-龥]{0,15}?)(?:省|市|自治区|特别行政区)[一-龥\d\s,()（）\-\w]{4,60}?\d+\s*号",
                "enabled": True,
                "description": "匹配含省级行政区且末端为门牌号的地址(支持省/市开头,支持全角括号/英文字母/连字符,容忍数字与号之间空白)",
                "mask_mode": "default",
                "mask_keep_prefix": 8,
                "mask_keep_suffix": 2,
                "mask_char": "*",
            },
            "固定电话": {
                "pattern": r"(?<!\d)0\d{2,3}[-\s]?[\d\w]{7,8}(?!\d)",
                "enabled": True,
                "description": "匹配 0xx-xxxxxxxx 座机/固定电话(容忍 OCR 误识)",
                "mask_mode": "default",
                "mask_keep_prefix": 0,
                "mask_keep_suffix": 4,
                "mask_char": "*",
            },
            "法定代表人": {
                "pattern": r"法定代表人\s*[::：]?\s*[一-龥]{2,4}(?:·[一-龥]{2,4})?(?=[的之及与和按于在跟同向对为由被让等,，。；;）)\]】\s]|$)",
                "enabled": True,
                "description": "匹配'法定代表人'标签后的人名(支持半角/全角冒号)。v1.1.13: 加正向 lookahead 边界 — 防止贪婪匹配把 '继续主张' 等普通动词当人名 mask",
                "mask_mode": "name",
                "mask_keep_prefix": 1,
                "mask_keep_suffix": 0,
                "mask_char": "*",
            },
            "统一社会信用代码": {
                "pattern": r"(?<![A-Z0-9])([0-9][0-9A-HJ-NPQRTUWXY]{16,17})(?![A-Za-z0-9])",
                "enabled": True,
                "description": "匹配 GB 32100-2015 统一社会信用代码(17-18 位数字+大写字母,首字符为数字,排除 I/O/Z/S/V)。仅作用于 Word 路径,不影响 PDF。",
                "mask_mode": "default",
                "mask_keep_prefix": 4,
                "mask_keep_suffix": 4,
                "mask_char": "*",
            },
            "公司名": {
                "pattern": r"[一-龥]{2,40}(?:有限公司|股份有限公司|有限责任公司|集团公司|控股公司|合伙企业|公司|中心)",
                "enabled": True,
                "description": "匹配中文公司/企业名称(以有限公司/集团/公司/中心等尾缀)",
                "mask_mode": "default",
                "mask_keep_prefix": 0,
                "mask_keep_suffix": 0,
                "mask_char": "*",
            }
        },
        "replacement_text": "*",
        "custom_keywords": "",
        "blacklist": [],
        "whitelist": ["盖章", "吉铁", "丰满区", "全能王", "甲方", "乙方", "丙方", "丁方", "戊方"],
        "scan": {
            "default_level": 1.5,
            "available_levels": [1.0, 1.5, 2.0],
            "level_labels": {
                "1.0": "普通 (1.0x)",
                "1.5": "标准 (1.5x 推荐)",
                "2.0": "高精 (2.0x)"
            }
        },
        "offset": {
            "x_range": [-20, 50],
            "w_range": [-20, 20],
            "default_x": 0,
            "default_w": 0
        },
        "precise_locator": {
            "enabled": True
        }
    },
    "ocr": {
        "min_rect_width": 5,
        "progress_update_interval": 0.05,
        "zoom_min": 0.5,
        "zoom_max": 4.0,
        "box_adjust_ratio": 0.0,
        "box_adjust_range": [-0.3, 0.5]
    },
    "security": {
        "validate_paths": True,
        "allowed_extensions": [".pdf", ".doc", ".docx"]
    },
    "ui": {
        "theme": "auto",
        "animation_enabled": True,
        "show_tips": True
    },
    "advanced": {
        "debug_mode": False,
        "temp_cleanup_on_exit": True,
        "cv2_num_threads": 0,
        "omp_num_threads": 1
    }
}


class ConfigManager:
    """
    配置管理器单例类

    功能：
    - 加载和保存 JSON 配置文件
    - 默认配置 + 用户配置合并
    - 点分隔路径访问配置项
    - 配置验证
    - 变更监听回调
    - 线程安全

    用法：
        config = ConfigManager()  # 获取实例
        width = config.get("app.window.default_width", 1300)
        config.set("redaction.scan.default_level", 2.5, persist=True)
        rules = config.get_redaction_rules()
        config.reload()  # 热重载
    """

    _instance: Optional['ConfigManager'] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> 'ConfigManager':
        """单例模式实现"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径，默认使用应用目录下的 config.json
        """
        if self._initialized:
            return

        self._lock = threading.RLock()
        self._config: Dict[str, Any] = {}
        self._callbacks: List[Callable[[str, Any, Any], None]] = []
        self._config_path: str = config_path or self._get_default_config_path()

        # 加载配置
        self._load_config()
        self._initialized = True

    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        # 首先尝试应用目录
        app_dir = Path(__file__).parent.parent.parent
        config_path = app_dir / "config.json"

        # 如果应用目录不可写或不存在，使用用户目录
        try:
            if not os.access(app_dir, os.W_OK):
                raise PermissionError
        except (OSError, PermissionError):
            user_dir = Path.home() / ".secureredact"
            user_dir.mkdir(exist_ok=True)
            config_path = user_dir / "config.json"

        return str(config_path)

    def _load_config(self) -> None:
        """加载配置文件，合并默认配置和用户配置"""
        with self._lock:
            # 从默认配置开始
            self._config = self._deep_copy(DEFAULT_CONFIG)

            # 如果配置文件存在，加载并合并
            if os.path.exists(self._config_path):
                try:
                    with open(self._config_path, 'r', encoding='utf-8') as f:
                        user_config = json.load(f)
                    self._merge_config(self._config, user_config)
                except json.JSONDecodeError as e:
                    print(f"[ConfigManager] 配置文件格式错误: {e}")
                    print(f"[ConfigManager] 使用默认配置")
                except Exception as e:
                    print(f"[ConfigManager] 加载配置文件失败: {e}")
                    print(f"[ConfigManager] 使用默认配置")

    def _deep_copy(self, obj: Any) -> Any:
        """深拷贝对象"""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        return obj

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """递归合并配置"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = self._deep_copy(value)

    def _get_nested_value(self, config: Dict[str, Any], path: str) -> Any:
        """获取嵌套配置值"""
        keys = path.split('.')
        current = config
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                raise KeyError(f"配置路径不存在: {path}")
            current = current[key]
        return current

    def _set_nested_value(self, config: Dict[str, Any], path: str, value: Any) -> None:
        """设置嵌套配置值"""
        keys = path.split('.')
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def get(self, path: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            path: 点分隔的配置路径，如 "app.window.default_width"
                  如果为 None，返回整个配置字典
            default: 默认值，当配置不存在时返回

        Returns:
            配置值或默认值
        """
        with self._lock:
            if path is None:
                return self._deep_copy(self._config)

            try:
                return self._get_nested_value(self._config, path)
            except KeyError:
                return default

    def set(self, path: str, value: Any, persist: bool = True) -> bool:
        """
        设置配置值

        Args:
            path: 点分隔的配置路径
            value: 新值
            persist: 是否立即保存到文件

        Returns:
            是否设置成功
        """
        with self._lock:
            old_value = self.get(path)
            try:
                self._set_nested_value(self._config, path, value)
                if persist:
                    self._save_config()
                # 触发回调
                self._notify_change(path, old_value, value)
                return True
            except Exception as e:
                print(f"[ConfigManager] 设置配置失败: {e}")
                return False

    def _save_config(self) -> bool:
        """保存配置到文件"""
        try:
            # 确保目录存在
            config_dir = os.path.dirname(self._config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ConfigManager] 保存配置文件失败: {e}")
            return False

    def save(self) -> bool:
        """手动保存配置到文件"""
        with self._lock:
            return self._save_config()

    def reload(self) -> bool:
        """
        重新加载配置文件（热重载）

        Returns:
            是否重载成功
        """
        with self._lock:
            try:
                old_config = self._deep_copy(self._config)
                self._load_config()
                # 触发所有变更回调
                self._notify_reload(old_config, self._config)
                return True
            except Exception as e:
                print(f"[ConfigManager] 重载配置失败: {e}")
                return False

    def on_change(self, callback: Callable[[str, Any, Any], None]) -> Callable:
        """
        注册配置变更回调

        Args:
            callback: 回调函数，接收 (path, old_value, new_value) 参数

        Returns:
            取消注册的函数
        """
        with self._lock:
            self._callbacks.append(callback)

        def unregister():
            with self._lock:
                if callback in self._callbacks:
                    self._callbacks.remove(callback)

        return unregister

    def _notify_change(self, path: str, old_value: Any, new_value: Any) -> None:
        """触发配置变更回调"""
        for callback in self._callbacks:
            try:
                callback(path, old_value, new_value)
            except Exception as e:
                print(f"[ConfigManager] 回调执行错误: {e}")

    def _notify_reload(self, old_config: Dict, new_config: Dict) -> None:
        """通知所有配置重载"""
        # 简化为通知根路径变更
        for callback in self._callbacks:
            try:
                callback("", old_config, new_config)
            except Exception as e:
                print(f"[ConfigManager] 重载回调执行错误: {e}")

    def validate(self) -> List[str]:
        """
        验证配置有效性

        Returns:
            错误列表，空列表表示验证通过
        """
        errors = []

        with self._lock:
            # 验证窗口尺寸
            window = self._config.get("app", {}).get("window", {})
            if window.get("default_width", 0) < window.get("min_width", 0):
                errors.append("app.window.default_width 必须 >= min_width")
            if window.get("default_height", 0) < window.get("min_height", 0):
                errors.append("app.window.default_height 必须 >= min_height")

            # 验证扫描级别
            scan = self._config.get("redaction", {}).get("scan", {})
            default_level = scan.get("default_level")
            available_levels = scan.get("available_levels", [])
            if default_level and available_levels:
                if default_level not in available_levels:
                    errors.append(f"redaction.scan.default_level {default_level} 不在可用列表中")

            # 验证偏移范围
            offset = self._config.get("redaction", {}).get("offset", {})
            x_range = offset.get("x_range", [-20, 20])
            w_range = offset.get("w_range", [-20, 20])
            if len(x_range) != 2 or x_range[0] > x_range[1]:
                errors.append("redaction.offset.x_range 格式错误")
            if len(w_range) != 2 or w_range[0] > w_range[1]:
                errors.append("redaction.offset.w_range 格式错误")

            # 验证脱敏规则
            rules = self._config.get("redaction", {}).get("default_rules", {})
            for name, rule in rules.items():
                if isinstance(rule, dict):
                    pattern = rule.get("pattern")
                    if not pattern:
                        errors.append(f"redaction.default_rules.{name}.pattern 不能为空")
                elif isinstance(rule, str):
                    # 旧格式兼容：直接是 pattern 字符串
                    if not rule:
                        errors.append(f"redaction.default_rules.{name} 不能为空")

        return errors

    def get_redaction_rules(self, enabled_only: bool = False) -> Dict[str, Any]:
        """
        获取脱敏规则

        Args:
            enabled_only: 是否只返回启用的规则

        Returns:
            规则字典,兼容新旧两种格式

        v1.1.12: 末尾补齐缺失的 mask_* 字段(向后兼容 v1.1.11 配置)。
        """
        with self._lock:
            rules = self._config.get("redaction", {}).get("default_rules", {})
            result = {}

            for name, rule in rules.items():
                if isinstance(rule, dict):
                    if enabled_only and not rule.get("enabled", True):
                        continue
                    # v1.1.12: 补齐 mask 字段,缺失时使用默认值(整段打码,向后兼容)
                    rule.setdefault("mask_mode", "default")
                    rule.setdefault("mask_keep_prefix", 0)
                    rule.setdefault("mask_keep_suffix", 0)
                    rule.setdefault("mask_char", "*")
                    result[name] = rule
                elif isinstance(rule, str):
                    # 旧格式兼容
                    if not enabled_only:
                        result[name] = {
                            "pattern": rule,
                            "enabled": True,
                            "mask_mode": "default",
                            "mask_keep_prefix": 0,
                            "mask_keep_suffix": 0,
                            "mask_char": "*",
                        }
                else:
                    # 其他格式,尝试转换
                    if not enabled_only:
                        result[name] = {
                            "pattern": str(rule),
                            "enabled": True,
                            "mask_mode": "default",
                            "mask_keep_prefix": 0,
                            "mask_keep_suffix": 0,
                            "mask_char": "*",
                        }

            return result

    def get_rule_pattern(self, rule_name: str) -> Optional[str]:
        """
        获取指定规则的 pattern

        Args:
            rule_name: 规则名称

        Returns:
            pattern 字符串，不存在返回 None
        """
        rules = self.get_redaction_rules()
        rule = rules.get(rule_name)
        if isinstance(rule, dict):
            return rule.get("pattern")
        elif isinstance(rule, str):
            return rule
        return None

    def update_redaction_rules(self, rules: Dict[str, Any], persist: bool = True) -> bool:
        """
        更新脱敏规则

        Args:
            rules: 新规则字典
            persist: 是否保存到文件

        Returns:
            是否更新成功
        """
        return self.set("redaction.default_rules", rules, persist=persist)

    def get_config_path(self) -> str:
        """获取当前配置文件路径"""
        return self._config_path

    def reset_to_default(self, persist: bool = True) -> bool:
        """
        重置为默认配置

        Args:
            persist: 是否保存到文件

        Returns:
            是否重置成功
        """
        with self._lock:
            old_config = self._deep_copy(self._config)
            self._config = self._deep_copy(DEFAULT_CONFIG)

            if persist:
                self._save_config()

            self._notify_reload(old_config, self._config)
            return True

    def export_template(self, template_path: str) -> bool:
        """
        导出配置模板

        Args:
            template_path: 模板文件路径

        Returns:
            是否导出成功
        """
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ConfigManager] 导出模板失败: {e}")
            return False


# 便捷函数
def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """获取配置管理器实例"""
    return ConfigManager(config_path)


def get_config_value(path: str, default: Any = None, config_path: Optional[str] = None) -> Any:
    """便捷函数：获取配置值"""
    config = ConfigManager(config_path)
    return config.get(path, default)


# =====================================================================
# PR-C6.4:从 main.py:144 迁出的 SimpleConfig + 全局 config singleton
# =====================================================================

class SimpleConfig:
    """简化配置管理器 - 直接从 config.json 读取(PR-C6.4 从 main.py:144 迁出)

    与 ConfigManager 区别:
    - ConfigManager:高级 API,支持多 schema 验证、热重载、字段监听
    - SimpleConfig:低阶 API,扁平 dict 读写 + dot-path 访问,无 schema 校验

    保留兼容 — main.py 仍 re-export,GUI / mixin 仍可 'from main import config'。
    """

    def __init__(self, config_path=None):
        self._config = {}
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.json')
        self._config_path = config_path
        self.load()

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """v1.1.12: 深度合并 — override 中有的字段覆盖 base, base 中独有字段保留。

        用于 SimpleConfig.save() 字段保护, 避免磁盘上其他版本/扩展字段被擦除。
        对 dict 类型递归合并, 非 dict 类型(标量/列表)直接覆盖。
        """
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = SimpleConfig._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def load(self):
        """加载配置文件并补齐默认键。

        v1.1.12: 额外从 DEFAULT_CONFIG(本模块内嵌)合并缺失的 default_rules 字段,
        避免 disk 配置被外部操作擦除 mask_* 等扩展字段时丢失功能。
        """
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
        except (OSError, IOError, json.JSONDecodeError) as e:
            print(f"[配置系统] 加载配置失败: {e}")

        red = self._config.setdefault("redaction", {})
        red.setdefault("enable_hit_override", True)
        overrides = red.setdefault("overrides", {})
        overrides.setdefault("permanent", [])

        # v1.1.12: 字段保护 — 强制覆盖内置规则的 mask_* 字段
        try:
            disk_rules = self._config.setdefault("redaction", {}).setdefault("default_rules", {})
            default_rules = DEFAULT_CONFIG.get("redaction", {}).get("default_rules", {})
            for rule_name, default_meta in default_rules.items():
                if rule_name not in disk_rules:
                    disk_rules[rule_name] = default_meta
                elif isinstance(default_meta, dict) and isinstance(disk_rules[rule_name], dict):
                    for k, v in default_meta.items():
                        if k.startswith("mask_") and k in default_meta:
                            disk_rules[rule_name][k] = v
                    if "pattern" in default_meta and "pattern" in disk_rules[rule_name]:
                        code_pat = default_meta["pattern"]
                        disk_pat = disk_rules[rule_name]["pattern"]
                        if code_pat != disk_pat:
                            code_normalized = code_pat.replace("\\", "").replace("\\\\", "")
                            disk_normalized = disk_pat.replace("\\", "").replace("\\\\", "")
                            if len(code_normalized) > len(disk_normalized):
                                disk_rules[rule_name]["pattern"] = code_pat

            default_whitelist = DEFAULT_CONFIG.get("redaction", {}).get("whitelist", [])
            disk_whitelist = self._config.setdefault("redaction", {}).setdefault("whitelist", [])
            for item in default_whitelist:
                if item not in disk_whitelist:
                    disk_whitelist.append(item)
        except Exception as _exc:
            print(f"[配置系统] 强制覆盖 mask 字段失败: {_exc}")

    def _load_config(self):
        """[兼容保留] 旧版加载入口,委托给 load()."""
        self.load()

    def save(self):
        """原子写回磁盘 — 先写 .tmp,再 os.replace 原子替换.

        v1.1.12: 字段保护 — 从磁盘读 + 合并,避免 SettingsDialog 保存时擦除
        disk 上 self._config 没有的字段(如 mask_* 等其他版本/扩展字段)。
        """
        tmp_path = self._config_path + ".tmp"
        try:
            try:
                if os.path.exists(self._config_path):
                    with open(self._config_path, 'r', encoding='utf-8') as f:
                        disk_config = json.load(f)
                else:
                    disk_config = {}
            except (OSError, IOError, json.JSONDecodeError):
                disk_config = {}

            merged = self._deep_merge(disk_config, self._config)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._config_path)
            return True
        except (OSError, IOError, TypeError) as e:
            print(f"[配置系统] 保存配置失败: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return False

    def get(self, key, default=None):
        """获取配置值(支持点分隔路径)"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key, value, persist=True):
        """设置配置值(支持点分隔路径)"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            elif not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        if persist:
            self.save()

    def get_redaction_rules(self):
        """获取脱敏规则"""
        return self.get('redaction.default_rules', {})


# 全局 config singleton(原 main.py:313 'config = SimpleConfig()' 迁出)
config = SimpleConfig()
