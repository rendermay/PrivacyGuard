# -*- coding: utf-8 -*-
"""BlackWhiteListStore 单例: 黑名单 + 白名单的永久层/会话层管理."""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)


class BlackWhiteListStore:
    """单例 store.

    双层结构:
      - 永久层: 从 config.json 加载, save_permanent() 写回
      - 会话层: 仅本次启动有效, add_session_*/remove_session_*

    匹配语义: substring (用户决策, 见 spec 第 3 节).

    用法:
        store = BlackWhiteListStore.instance()
        store.add_session_black("盖章")
        store.bind_config(config)
        store.save_permanent()
    """

    _instance: Optional["BlackWhiteListStore"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._permanent_blacklist: List[str] = []
        self._permanent_whitelist: List[str] = []
        self._session_blacklist: List[str] = []
        self._session_whitelist: List[str] = []
        self._config = None  # type: ignore[assignment]

    @classmethod
    def instance(cls) -> "BlackWhiteListStore":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """仅供测试使用."""
        with cls._instance_lock:
            cls._instance = None

    # ---- 查询 ----

    def effective_blacklist(self) -> List[str]:
        with self._lock:
            seen: set = set()
            out: List[str] = []
            for item in self._permanent_blacklist + self._session_blacklist:
                if item and item not in seen:
                    seen.add(item)
                    out.append(item)
            return out

    def effective_whitelist(self) -> List[str]:
        with self._lock:
            seen: set = set()
            out: List[str] = []
            for item in self._permanent_whitelist + self._session_whitelist:
                if item and item not in seen:
                    seen.add(item)
                    out.append(item)
            return out

    # ---- 会话层写入（占位,Task 3 实现） ----

    def add_session_black(self, item: str) -> None:
        pass

    def remove_session_black(self, item: str) -> None:
        pass

    def add_session_white(self, item: str) -> None:
        pass

    def remove_session_white(self, item: str) -> None:
        pass

    # ---- 持久化（占位,Task 4 实现） ----

    def bind_config(self, config) -> None:
        self._config = config

    def save_permanent(self) -> None:
        pass

    def load_permanent(self, black: list, white: list) -> None:
        pass
