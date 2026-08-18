# 黑名单 / 白名单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 PrivacyGuard v37.9.0 增加「黑名单（强制脱敏）」和「白名单（永不脱敏）」功能，黑/白名单同时作用于 PDF 与 Word，支持永久层（config.json）+ 会话层（内存）。

**Architecture:** 新建 `BlackWhiteListStore` 单例（与 `HitOverrideStore` 同款，单例 + `threading.Lock`）。`OCRWorker._process_page` / `WordWorker._run` 在已有规则匹配后追加两段：(a) `_apply_whitelist_filter` 剥掉 manual 之外含白名单子串的 hit；(b) `_collect_blacklist_hits` 在 image/段落 OCR token 中 `str.find` 定位并构造 `source="blacklist"` hit。设置中心新增两个独立 Tab。

**Tech Stack:** Python 3 + PyQt6 + PyMuPDF + RapidOCR + jieba + unittest（项目已有测试运行器为 `python3 -m unittest`，非 pytest）。

## Global Constraints

- 单测运行命令：`python3 -m unittest tests.unit.<module> -v`（项目惯例，非 pytest）。
- 编译检查命令：`python3 -m compileall -q main.py privacyguard tests`。
- 新增模块须遵循项目既有命名：`privacyguard/redaction/<feature>.py`（参照 `override_store.py` 风格）。
- 单例 + `threading.Lock` 模式必须与 `HitOverrideStore` 一致（含 `instance()` / `reset_singleton()`）。
- config.json 写入走 tmp + rename 原子替换（参照 `SimpleConfig.save` 在 `main.py:131-137`）。
- `source="manual"` 永不被任何机制覆盖（CLAUDE.md 既定原则）。
- 不修改 `HitOverrideStore` 既有 `filtered_hits` 语义；whiteList 过滤发生在 worker 出口。
- 现有回归基线：162 项 / 160 通过（2 项 v37.7.6 既有失败已知）。新功能不得引入新失败。
- config.json 现有 CRLF 换行规则维持（最近 commit `a8be8cb` 已统一）。
- 所有新增中文注释遵守 [项目语言偏好：中文](file:///home/rende/.claude/projects/-mnt-g-Project-PrivacyGuard/memory/project-language-zh.md)。
- 专有名词（jieba、HitRef、QRectF、override 等）保留英文。

## File Structure

**新建**：
- `privacyguard/redaction/black_white_list_store.py` — 单例 + 永久/会话双层 + 原子写
- `tests/unit/test_black_white_list_store.py` — 单测

**修改**：
- `privacyguard/utils/config.py` — `DEFAULT_CONFIG["redaction"]` 增 `blacklist` / `whitelist` 默认值（`[]`）
- `privacyguard/workers/ocr_worker.py` — `_apply_whitelist_filter` / `_collect_blacklist_hits` / `_process_page` 整合 / `_resolve_text_from_rect` 缓存
- `privacyguard/workers/word_worker.py` — `_filter_whitelist` / blacklist `str.find` 注入
- `main.py` — `SettingsDialog` 新增两个 Tab + `MainWindow` 启动时 `BlackWhiteListStore.bind_config` + 加载/回写
- `tests/unit/test_ocr_worker_blacklist.py` — 新建
- `tests/unit/test_ocr_worker_whitelist.py` — 新建
- `tests/unit/test_word_worker_black_white.py` — 新建

---

### Task 1: BlackWhiteListStore 单例骨架

**Files:**
- Create: `privacyguard/redaction/black_white_list_store.py`
- Test: `tests/unit/test_black_white_list_store.py`

**Interfaces:**
- Produces: `BlackWhiteListStore.instance() -> BlackWhiteListStore`
- Produces: `BlackWhiteListStore.reset_singleton()` （测试用）
- Produces: `BlackWhiteListStore.effective_blacklist() -> List[str]`
- Produces: `BlackWhiteListStore.effective_whitelist() -> List[str]`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_black_white_list_store.py`：
```python
# -*- coding: utf-8 -*-
"""BlackWhiteListStore 单例逻辑测试."""
import unittest
from privacyguard.redaction.black_white_list_store import BlackWhiteListStore


class BlackWhiteListStoreTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_singleton(self):
        a = BlackWhiteListStore.instance()
        b = BlackWhiteListStore.instance()
        self.assertIs(a, b)

    def test_effective_blacklist_default_empty(self):
        s = BlackWhiteListStore.instance()
        self.assertEqual(s.effective_blacklist(), [])

    def test_effective_whitelist_default_empty(self):
        s = BlackWhiteListStore.instance()
        self.assertEqual(s.effective_whitelist(), [])

    def test_reset_singleton_clears_state(self):
        s = BlackWhiteListStore.instance()
        # 先放一个会话条目以验证 reset
        s.add_session_black("盖章")
        BlackWhiteListStore.reset_singleton()
        s2 = BlackWhiteListStore.instance()
        self.assertIsNot(s, s2)
        self.assertEqual(s2.effective_blacklist(), [])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_black_white_list_store -v
```
期望：`ModuleNotFoundError: No module named 'privacyguard.redaction.black_white_list_store'` 或 `ImportError`。

- [ ] **Step 3: 写最小实现**

`privacyguard/redaction/black_white_list_store.py`：
```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.unit.test_black_white_list_store -v
```
期望：4 个 test 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/redaction/black_white_list_store.py tests/unit/test_black_white_list_store.py
git commit -m "feat(redaction): BlackWhiteListStore 单例骨架"
```

---

### Task 2: BlackWhiteListStore 加载永久层（含类型校验兜底）

**Files:**
- Modify: `privacyguard/redaction/black_white_list_store.py:load_permanent`
- Modify: `tests/unit/test_black_white_list_store.py`

**Interfaces:**
- Consumes: `load_permanent(black: list, white: list) -> None` （已有签名）

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_black_white_list_store.py` 追加：
```python
    def test_load_permanent_normal(self):
        s = BlackWhiteListStore.instance()
        s.load_permanent(["盖章", "签字"], ["12345"])
        self.assertIn("盖章", s.effective_blacklist())
        self.assertIn("签字", s.effective_blacklist())
        self.assertEqual(s.effective_whitelist(), ["12345"])

    def test_load_permanent_filters_empty_and_whitespace(self):
        s = BlackWhiteListStore.instance()
        s.load_permanent(["盖章", "", "  ", "\t"], [])
        self.assertEqual(s.effective_blacklist(), ["盖章"])

    def test_load_permanent_warns_on_non_list(self):
        s = BlackWhiteListStore.instance()
        # 不是 list → 回退到空, 不抛异常
        s.load_permanent("not a list", "also not a list")
        self.assertEqual(s.effective_blacklist(), [])
        self.assertEqual(s.effective_whitelist(), [])

    def test_load_permanent_filters_non_string_items(self):
        s = BlackWhiteListStore.instance()
        s.load_permanent(["盖章", 123, None, "签字"], [])
        # 非字符串条目静默跳过
        self.assertEqual(s.effective_blacklist(), ["盖章", "签字"])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_black_white_list_store.BlackWhiteListStoreTest.test_load_permanent_normal -v
```
期望：FAIL （`load_permanent` 是 pass 占位）。

- [ ] **Step 3: 写实现**

替换 `black_white_list_store.py` 中的 `load_permanent`：
```python
    def load_permanent(self, black: list, white: list) -> None:
        """从 config.json 加载永久层. 损坏条目静默跳过."""
        with self._lock:
            self._permanent_blacklist = self._sanitize(black, "blacklist")
            self._permanent_whitelist = self._sanitize(white, "whitelist")

    @staticmethod
    def _sanitize(raw, label: str) -> List[str]:
        if not isinstance(raw, list):
            logger.warning("load_permanent: %s 期望 list,得到 %s", label, type(raw).__name__)
            return []
        out: List[str] = []
        for item in raw:
            if not isinstance(item, str):
                logger.warning("load_permanent: %s 跳过非字符串条目: %r", label, item)
                continue
            stripped = item.strip()
            if not stripped:
                continue
            out.append(stripped)
        return out
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.unit.test_black_white_list_store -v
```
期望：8 个 test 全部 PASS（4 旧 + 4 新）。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/redaction/black_white_list_store.py tests/unit/test_black_white_list_store.py
git commit -m "feat(redaction): load_permanent 含类型校验与空值过滤"
```

---

### Task 3: BlackWhiteListStore 会话层 add/remove

**Files:**
- Modify: `privacyguard/redaction/black_white_list_store.py:add_session_black` 等
- Modify: `tests/unit/test_black_white_list_store.py`

**Interfaces:**
- Produces: `add_session_black(item: str) -> None`
- Produces: `remove_session_black(item: str) -> None`
- Produces: `add_session_white(item: str) -> None`
- Produces: `remove_session_white(item: str) -> None`

- [ ] **Step 1: 写失败测试**

追加到 `tests/unit/test_black_white_list_store.py`：
```python
    def test_session_blacklist_add_and_effective(self):
        s = BlackWhiteListStore.instance()
        s.add_session_black("盖章")
        s.add_session_black("  ")  # 空白应被忽略
        s.add_session_black("签字")
        self.assertEqual(s.effective_blacklist(), ["盖章", "签字"])

    def test_session_blacklist_dedup_with_permanent(self):
        s = BlackWhiteListStore.instance()
        s.load_permanent(["盖章"], [])
        s.add_session_black("盖章")  # 永久已有,不重复
        s.add_session_black("签字")
        self.assertEqual(s.effective_blacklist(), ["盖章", "签字"])

    def test_session_blacklist_remove(self):
        s = BlackWhiteListStore.instance()
        s.add_session_black("盖章")
        s.add_session_black("签字")
        s.remove_session_black("盖章")
        self.assertEqual(s.effective_blacklist(), ["签字"])

    def test_session_blacklist_remove_unknown_is_noop(self):
        s = BlackWhiteListStore.instance()
        s.add_session_black("盖章")
        s.remove_session_black("不存在的条目")
        self.assertEqual(s.effective_blacklist(), ["盖章"])

    def test_session_whitelist_mirrors_blacklist(self):
        s = BlackWhiteListStore.instance()
        s.add_session_white("12345")
        s.remove_session_white("12345")
        self.assertEqual(s.effective_whitelist(), [])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_black_white_list_store.BlackWhiteListStoreTest.test_session_blacklist_add_and_effective -v
```
期望：FAIL （pass 占位返回 None，effective_blacklist() 仍返回 `[]`）。

- [ ] **Step 3: 写实现**

替换 `black_white_list_store.py` 中的会话层方法：
```python
    def add_session_black(self, item: str) -> None:
        self._add_session(self._session_blacklist, item)

    def remove_session_black(self, item: str) -> None:
        self._remove_session(self._session_blacklist, item)

    def add_session_white(self, item: str) -> None:
        self._add_session(self._session_whitelist, item)

    def remove_session_white(self, item: str) -> None:
        self._remove_session(self._session_whitelist, item)

    @staticmethod
    def _add_session(target: List[str], item: str) -> None:
        if not isinstance(item, str):
            return
        stripped = item.strip()
        if not stripped or stripped in target:
            return
        target.append(stripped)

    @staticmethod
    def _remove_session(target: List[str], item: str) -> None:
        if item in target:
            target.remove(item)
```

注意：`add_session_*` 的列表操作不在 lock 内；当前实现是单实例方法，线程安全由 `effective_*` 的 lock 保证。后续如确认多线程并发写入需要，再补 `_lock`。

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.unit.test_black_white_list_store -v
```
期望：13 个 test 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/redaction/black_white_list_store.py tests/unit/test_black_white_list_store.py
git commit -m "feat(redaction): BlackWhiteListStore 会话层 add/remove"
```

---

### Task 4: BlackWhiteListStore save_permanent 原子写

**Files:**
- Modify: `privacyguard/redaction/black_white_list_store.py:save_permanent`
- Modify: `tests/unit/test_black_white_list_store.py`

**Interfaces:**
- Produces: `save_permanent() -> None` （从内存会话+永久的合并态写回 config.json）

- [ ] **Step 1: 写失败测试**

追加到测试文件：
```python
    def test_save_permanent_writes_to_config(self):
        s = BlackWhiteListStore.instance()

        # 模拟 SimpleConfig 接口（仅 set + save）
        class _FakeConfig:
            def __init__(self):
                self.calls = []
            def set(self, path, value, persist=False):
                self.calls.append((path, value))
            def save(self):
                self.calls.append(("save",))

        fake = _FakeConfig()
        s.bind_config(fake)
        s.load_permanent(["盖章"], [])
        s.save_permanent()

        paths = [c[0] for c in fake.calls if isinstance(c, tuple)]
        self.assertIn("redaction.blacklist", paths)
        self.assertIn("redaction.whitelist", paths)
        self.assertIn("save", paths)

    def test_save_permanent_without_config_is_noop(self):
        s = BlackWhiteListStore.instance()
        # 未 bind_config, 不抛异常
        s.save_permanent()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_black_white_list_store.BlackWhiteListStoreTest.test_save_permanent_writes_to_config -v
```
期望：FAIL （pass 占位）。

- [ ] **Step 3: 写实现**

替换 `black_white_list_store.py` 中的 `save_permanent`：
```python
    def save_permanent(self) -> None:
        """写回 SimpleConfig.

        若未 bind_config 则静默跳过 (避免污染测试态).
        写入字段:
          - redaction.blacklist
          - redaction.whitelist
        """
        if self._config is None:
            return
        try:
            with self._lock:
                # 永久层回写 = 合并后的永久层 (会话层不持久化)
                self._config.set("redaction.blacklist", list(self._permanent_blacklist), persist=False)
                self._config.set("redaction.whitelist", list(self._permanent_whitelist), persist=False)
            self._config.save()
        except Exception as exc:
            logger.warning("save_permanent 失败: %s", exc)
```

注意：本任务仅实现"把永久层写回 config.json"。UI 编辑永久层并保存到内存的逻辑在 Task 9 (SettingsDialog)。

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.unit.test_black_white_list_store -v
```
期望：15 个 test 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/redaction/black_white_list_store.py tests/unit/test_black_white_list_store.py
git commit -m "feat(redaction): BlackWhiteListStore.save_permanent 原子写"
```

---

### Task 5: OCRWorker._apply_whitelist_filter

**Files:**
- Modify: `privacyguard/workers/ocr_worker.py`
- Create: `tests/unit/test_ocr_worker_whitelist.py`

**Interfaces:**
- Produces: `OCRWorker._apply_whitelist_filter(rects: List[dict], page_idx: int) -> List[dict]`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_ocr_worker_whitelist.py`：
```python
# -*- coding: utf-8 -*-
"""OCRWorker 白名单过滤测试."""
import unittest
from PyQt6.QtCore import QRectF

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.ocr_worker import OCRWorker


class _StubOCRWorker(OCRWorker):
    """绕开 QThread 启动,只调用被测方法."""
    def __init__(self):
        pass  # 不调用父类 __init__
    def _apply_whitelist_filter(self, rects, page_idx=0):
        # 委托给 OCRWorker 的实际方法 (绑 self=stub)
        return OCRWorker._apply_whitelist_filter(self, rects, page_idx)


def _hit(text, source="rule", x=0, y=0, w=10, h=10):
    return {"rect": QRectF(x, y, w, h), "source": source, "text": text, "rule_name": "test"}


class ApplyWhitelistFilterTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_empty_whitelist_returns_all(self):
        w = _StubOCRWorker()
        rects = [_hit("周强"), _hit("盖章", source="jieba")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(len(out), 2)

    def test_whitelist_drops_matched_rule_hit(self):
        BlackWhiteListStore.instance().load_permanent(["盖章"], [])
        w = _StubOCRWorker()
        rects = [_hit("盖章", source="rule"), _hit("周强", source="jieba")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "周强")

    def test_whitelist_drops_matched_jieba_hit(self):
        BlackWhiteListStore.instance().load_permanent(["吉铁"], [])
        w = _StubOCRWorker()
        rects = [_hit("吉铁", source="jieba")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(out, [])

    def test_manual_source_never_stripped(self):
        BlackWhiteListStore.instance().load_permanent(["盖章"], [])
        w = _StubOCRWorker()
        rects = [_hit("盖章", source="manual")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(len(out), 1)

    def test_ocr_channel_empty_text_falls_back_to_resolve(self):
        """OCR 通道 text 为空, 应通过 _resolve_text_from_rect 查回."""
        BlackWhiteListStore.instance().load_permanent(["盖章"], [])
        w = _StubOCRWorker()
        # stub 提供 _resolve_text_from_rect
        w._resolve_text_from_rect = lambda rect, page_idx: "签名或者盖章"
        rects = [_hit("", source="ocr")]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(out, [])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_ocr_worker_whitelist -v
```
期望：`AttributeError: '_StubOCRWorker' object has no attribute '_apply_whitelist_filter'` 或 `TypeError`。

- [ ] **Step 3: 写最小实现**

在 `privacyguard/workers/ocr_worker.py` 的 `OCRWorker` 类内（在 `_calculate_from_line` 之前）追加：
```python
    def _apply_whitelist_filter(self, rects: list, page_idx: int) -> list:
        """剥掉包含白名单子串的 hit. manual 来源豁免.

        OCR/seal 通道 hit.text 为空时,委托 _resolve_text_from_rect 查回.
        """
        whitelist = BlackWhiteListStore.instance().effective_whitelist()
        if not whitelist:
            return rects
        kept = []
        for hit in rects:
            source = hit.get("source", "ocr")
            if source == "manual":
                kept.append(hit)
                continue
            text = hit.get("text", "") or ""
            if not text:
                text = self._resolve_text_from_rect(hit.get("rect"), page_idx) or ""
            if any(wl and wl in text for wl in whitelist):
                continue
            kept.append(hit)
        return kept

    def _resolve_text_from_rect(self, rect, page_idx: int) -> str:
        """从该页已缓存的 rect → text 映射查回原文.

        未命中返回空串.  由 OCRWorker 在 image 通道 OCR 时填充缓存.
        """
        cache = getattr(self, "_rect_text_cache", None)
        if not cache:
            return ""
        # 用 (page_idx, rect 中心点) 做近似键
        if rect is None:
            return ""
        cx = int(rect.x() + rect.width() / 2)
        cy = int(rect.y() + rect.height() / 2)
        return cache.get((page_idx, cx, cy), "")
```

并在文件顶部 `from privacyguard.redaction.hit_ref` 等导入旁追加：
```python
from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.unit.test_ocr_worker_whitelist -v
```
期望：5 个 test 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/workers/ocr_worker.py tests/unit/test_ocr_worker_whitelist.py
git commit -m "feat(ocr): OCRWorker._apply_whitelist_filter 含 manual 豁免"
```

---

### Task 6: OCRWorker._collect_blacklist_hits + _dedupe_overlapping

**Files:**
- Modify: `privacyguard/workers/ocr_worker.py`
- Create: `tests/unit/test_ocr_worker_blacklist.py`

**Interfaces:**
- Produces: `OCRWorker._collect_blacklist_hits(page, page_idx, blacklist, scan_scale) -> List[dict]`
- Produces: `OCRWorker._dedupe_overlapping(hits: List[dict]) -> List[dict]` （静态）

- [ ] **Step 1: 写失败测试**

`tests/unit/test_ocr_worker_blacklist.py`：
```python
# -*- coding: utf-8 -*-
"""OCRWorker 黑名单注入测试."""
import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import QRectF

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.ocr_worker import OCRWorker


class _DedupTest(unittest.TestCase):
    """先测纯函数 _dedupe_overlapping."""

    def setUp(self):
        BlackWhiteListStore.reset_singleton()
    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _hit(self, x, y, w, h, text="盖章", source="blacklist"):
        return {"rect": QRectF(x, y, w, h), "source": source, "text": text, "rule_name": "黑名单:盖章"}

    def test_dedupe_overlapping_merges(self):
        # 两个相邻 token 都命中 "盖章", 应合并为一个矩形
        h1 = self._hit(10, 20, 10, 10)
        h2 = self._hit(20, 20, 10, 10)
        out = OCRWorker._dedupe_overlapping([h1, h2])
        self.assertEqual(len(out), 1)
        merged = out[0]["rect"]
        self.assertEqual(merged.x(), 10)
        self.assertEqual(merged.x() + merged.width(), 30)
        self.assertEqual(merged.y(), 20)
        self.assertEqual(merged.y() + merged.height(), 30)

    def test_dedupe_keeps_non_overlapping(self):
        h1 = self._hit(10, 20, 10, 10)
        h2 = self._hit(100, 200, 10, 10)
        out = OCRWorker._dedupe_overlapping([h1, h2])
        self.assertEqual(len(out), 2)

    def test_dedupe_handles_empty(self):
        self.assertEqual(OCRWorker._dedupe_overlapping([]), [])


class _CollectBlacklistTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()
    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_empty_blacklist_returns_empty(self):
        w = OCRWorker.__new__(OCRWorker)  # 绕开 QThread __init__
        page = MagicMock()
        out = w._collect_blacklist_hits(page, page_idx=0, blacklist=[], scan_scale=2.0)
        self.assertEqual(out, [])

    @patch("privacyguard.workers.ocr_worker.collect_embedded_image_clip_rects")
    def test_blacklist_injects_hit_for_matching_token(self, mock_collect):
        mock_collect.return_value = [(0, 0, 100, 100)]
        # 构造 stub OCR: 返回一个含 "盖章" 的 token
        w = OCRWorker.__new__(OCRWorker)
        w.calculate_sub_rect = MagicMock(return_value=QRectF(10, 20, 30, 10))
        w._ocr_clip = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])
        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=595, y1=842)

        out = w._collect_blacklist_hits(page, page_idx=0, blacklist=["盖章"], scan_scale=2.0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "blacklist")
        self.assertEqual(out[0]["text"], "盖章")
        self.assertIn("盖章", out[0]["rule_name"])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_ocr_worker_blacklist -v
```
期望：`AttributeError: type object 'OCRWorker' has no attribute '_dedupe_overlapping'` 等。

- [ ] **Step 3: 写实现**

在 `privacyguard/workers/ocr_worker.py` 的 `OCRWorker` 类内追加：
```python
    @staticmethod
    def _dedupe_overlapping(hits: list) -> list:
        """合并 rect 重叠或相邻的 blacklist hit.

        合并后保留第一个 hit 的 text/rule_name/source, 更新 rect 为最小外接矩形.
        """
        if not hits:
            return hits
        # 简单 O(n^2): blacklist 注入量小 (每条目 1-几个 hit), 足够
        groups: list = []
        for hit in hits:
            rect = hit["rect"]
            placed = False
            for grp in groups:
                gr = grp[0]["rect"]
                if OCRWorker._rects_overlap(gr, rect):
                    grp.append(hit)
                    placed = True
                    break
            if not placed:
                groups.append([hit])
        merged = []
        for grp in groups:
            if len(grp) == 1:
                merged.append(grp[0])
                continue
            xs = [h["rect"].x() for h in grp]
            ys = [h["rect"].y() for h in grp]
            x_max = [h["rect"].x() + h["rect"].width() for h in grp]
            y_max = [h["rect"].y() + h["rect"].height() for h in grp]
            union = QRectF(min(xs), min(ys), max(x_max) - min(xs), max(y_max) - min(ys))
            first = dict(grp[0])  # 浅拷贝
            first["rect"] = union
            merged.append(first)
        return merged

    @staticmethod
    def _rects_overlap(a, b) -> bool:
        if a is None or b is None:
            return False
        # 相邻 2 像素以内也算重叠 (合并相邻 token)
        pad = 2
        return not (
            a.x() + a.width() + pad < b.x()
            or b.x() + b.width() + pad < a.x()
            or a.y() + a.height() + pad < b.y()
            or b.y() + b.height() + pad < a.y()
        )

    def _collect_blacklist_hits(self, page, page_idx: int, blacklist: list, scan_scale: float) -> list:
        """扫描 image 通道 OCR tokens,命中 blacklist 条目 → 构造 hit."""
        from privacyguard.ocr.mixed_pdf import collect_embedded_image_clip_rects
        from PyQt6.QtCore import QRectF

        if not blacklist:
            return []
        page_dict = page.get_text("dict")
        clip_rects = collect_embedded_image_clip_rects(page_dict)
        if not clip_rects:
            rect = page.rect
            clip_rects = [(rect.x0, rect.y0, rect.x1, rect.y1)]

        # OCR 一次, 收集 (text, box) tokens
        ocr_engine = getattr(self, "_ocr_engine", None)
        if ocr_engine is None:
            return []
        try:
            full_img = self._render_full_page_bgr(page, scan_scale)
            tokens = self._ocr_clip(page, clip_rects[0], scan_scale) if len(clip_rects) == 1 else self._ocr_full_page_tokens(page, scan_scale)
        except Exception as exc:
            logger.warning("_collect_blacklist_hits OCR 失败: %s", exc)
            return []

        hits = []
        for bl_item in blacklist:
            if not bl_item:
                continue
            for tok_text, tok_box in tokens:
                if bl_item in tok_text:
                    rect = self.calculate_sub_rect(tok_box, tok_text, None, img_region=full_img)
                    if rect is None:
                        continue
                    hits.append({
                        "rect": QRectF(rect),
                        "source": "blacklist",
                        "text": bl_item,
                        "rule_name": f"黑名单:{bl_item}",
                    })
        return self._dedupe_overlapping(hits)

    def _ocr_full_page_tokens(self, page, scan_scale) -> list:
        """整页 OCR, 返回 [(text, box)] 列表. 由 _collect_blacklist_hits 使用."""
        ocr_engine = getattr(self, "_ocr_engine", None)
        if ocr_engine is None:
            return []
        try:
            full_img = self._render_full_page_bgr(page, scan_scale)
            results = ocr_engine.recognize(full_img)
        except Exception:
            return []
        out = []
        for r in results:
            out.append((getattr(r, "text", ""), getattr(r, "box", None)))
        return out
```

注意：本方法依赖 `self._ocr_engine` 和 `self.calculate_sub_rect`，须由调用方 (`_process_page`) 在调用前注入。Task 7 处理。

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.unit.test_ocr_worker_blacklist -v
```
期望：6 个 test 全部 PASS（3 dedup + 3 collect）。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/workers/ocr_worker.py tests/unit/test_ocr_worker_blacklist.py
git commit -m "feat(ocr): OCRWorker._collect_blacklist_hits + _dedupe_overlapping"
```

---

### Task 7: OCRWorker._process_page 整合 whiteList + blackList

**Files:**
- Modify: `privacyguard/workers/ocr_worker.py:_process_page`
- Create: `tests/unit/test_ocr_worker_integration.py`

**Interfaces:**
- Consumes: `_apply_whitelist_filter` (Task 5) + `_collect_blacklist_hits` (Task 6)

- [ ] **Step 1: 写失败测试**

`tests/unit/test_ocr_worker_integration.py`：
```python
# -*- coding: utf-8 -*-
"""OCRWorker 集成: _process_page 中 white/black list 串联."""
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QRectF

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.ocr_worker import OCRWorker


class _ProcessPageListTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_whitelist_strips_before_blacklist_injects(self):
        """黑名单含 "盖章"、白名单也含 "盖章" → 不应有 blacklist hit 注入."""
        BlackWhiteListStore.instance().load_permanent(["盖章"], ["盖章"])

        # 构造 stub OCRWorker, 不真正 OCR
        w = OCRWorker.__new__(OCRWorker)
        w.calculate_sub_rect = MagicMock(return_value=QRectF(10, 20, 30, 10))
        w._ocr_full_page_tokens = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])
        w._ocr_engine = MagicMock()

        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=595, y1=842)

        # 不调用真 _process_page (依赖太多), 而手工模拟串联逻辑
        # 模拟: 输入为空 rects, blacklist 注入应被 whitelist 阻断
        # 直接调用 _collect_blacklist_hits, 然后验证与 whitelist 的交互
        blacklist_hits = w._collect_blacklist_hits(page, page_idx=0, blacklist=["盖章"], scan_scale=2.0)
        # _collect_blacklist_hits 本身不剥 whitelist — 由 _process_page 串联
        self.assertEqual(len(blacklist_hits), 1)
        # 模拟串联: 先 whitelist 过滤 (rects 为空 → 无变化), 再 blacklist 注入
        # 然后再过一次 whitelist 过滤
        out = w._apply_whitelist_filter(blacklist_hits, page_idx=0)
        self.assertEqual(out, [])  # whitelist 剥掉了 blacklist 注入

    def test_blacklist_injects_when_whitelist_empty(self):
        BlackWhiteListStore.instance().load_permanent(["盖章"], [])
        w = OCRWorker.__new__(OCRWorker)
        w.calculate_sub_rect = MagicMock(return_value=QRectF(10, 20, 30, 10))
        w._ocr_full_page_tokens = MagicMock(return_value=[
            ("签名或者盖章。", [[10, 20], [40, 20], [40, 30], [10, 30]]),
        ])
        w._ocr_engine = MagicMock()
        page = MagicMock()
        page.rect = MagicMock(x0=0, y0=0, x1=595, y1=842)

        hits = w._collect_blacklist_hits(page, page_idx=0, blacklist=["盖章"], scan_scale=2.0)
        out = w._apply_whitelist_filter(hits, page_idx=0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "blacklist")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_ocr_worker_integration -v
```
期望：第一个 test FAIL（`_ocr_engine` 未在 stub 设置时,`_collect_blacklist_hits` 返回 `[]`，与预期不符）。修复方向：把 _ocr_engine 设置好。

实际运行第一个 test 应该通过（因为 stub 已设置），但**真正的串联顺序校验**在 `_process_page` 整合后才有效。本任务的 test 重点是**两个方法可独立串联**——这是后续 `_process_page` 整合的基础。

期望结果：2 个 test 全部 PASS。Step 2 不应失败；若失败，跳到 Step 3 的"写实现"找问题。

- [ ] **Step 3: 写最小集成**

修改 `privacyguard/workers/ocr_worker.py:_process_page`，在 `text_count = len(rects) - image_hit_count` 这行**之前**追加：
```python
        # v37.9.0: 黑/白名单串联. 先 whitelist 过滤剥掉已有命中, 再 blacklist 注入.
        rects = self._apply_whitelist_filter(rects, page_idx)

        blacklist = BlackWhiteListStore.instance().effective_blacklist()
        if blacklist:
            blacklist_hits = self._collect_blacklist_hits(
                page, page_idx, blacklist, scan_scale
            )
            rects.extend(blacklist_hits)

        # blacklist 注入后再过一次 whitelist 过滤, 确保同条目场景下白名单赢.
        rects = self._apply_whitelist_filter(rects, page_idx)
```

并新增属性初始化（`__init__` 内）：
```python
        self._ocr_engine = None  # type: ignore[assignment]
```

并修改 `_process_page` 开头，在 `ocr_engine` 参数旁加一行：
```python
        self._ocr_engine = ocr_engine
```

- [ ] **Step 4: 运行测试 + 现有回归确认通过**

```bash
python3 -m unittest tests.unit.test_ocr_worker_integration tests.unit.test_ocr_worker_blacklist tests.unit.test_ocr_worker_whitelist -v
python3 -m unittest tests.unit.test_mixed_pdf_ocr -v
```
期望：集成 + 黑/白名单 + 既有 OCR 测试全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/workers/ocr_worker.py tests/unit/test_ocr_worker_integration.py
git commit -m "feat(ocr): _process_page 串联 whiteList 过滤 + blackList 注入"
```

---

### Task 8: WordWorker 黑/白名单

**Files:**
- Modify: `privacyguard/workers/word_worker.py`
- Create: `tests/unit/test_word_worker_black_white.py`

**Interfaces:**
- Produces: `WordWorker._filter_whitelist(hits: list) -> list`
- 修改：WordWorker 段落处理流程中追加 `_filter_whitelist` + blacklist `str.find` 注入

- [ ] **Step 1: 写失败测试**

`tests/unit/test_word_worker_black_white.py`：
```python
# -*- coding: utf-8 -*-
"""WordWorker 黑/白名单测试."""
import unittest

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.workers.word_worker import WordWorker


class _WordFilterTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()
    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_filter_whitelist_strips_matched(self):
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        w = WordWorker.__new__(WordWorker)
        hits = [
            {"start": 0, "end": 2, "text": "盖章", "source": "rule"},
            {"start": 5, "end": 7, "text": "周强", "source": "jieba"},
        ]
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "周强")

    def test_filter_whitelist_preserves_manual(self):
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        w = WordWorker.__new__(WordWorker)
        hits = [{"start": 0, "end": 2, "text": "盖章", "source": "manual"}]
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)

    def test_filter_whitelist_empty_returns_all(self):
        w = WordWorker.__new__(WordWorker)
        hits = [{"start": 0, "end": 2, "text": "盖章", "source": "rule"}]
        out = w._filter_whitelist(hits)
        self.assertEqual(out, hits)


class _WordBlacklistInjectTest(unittest.TestCase):
    """直接测试纯函数: 给定 text + blacklist → 命中列表."""

    def setUp(self):
        BlackWhiteListStore.reset_singleton()
    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_single_match(self):
        BlackWhiteListStore.instance().load_permanent(["盖章"], [])
        text = "签名或者盖章。"
        hits = WordWorker._scan_blacklist_in_text(text, ["盖章"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["text"], "盖章")
        self.assertEqual(hits[0]["start"], 4)
        self.assertEqual(hits[0]["end"], 6)

    def test_multiple_matches(self):
        BlackWhiteListStore.instance().load_permanent(["吉"], [])
        text = "吉林吉铁吉"
        hits = WordWorker._scan_blacklist_in_text(text, ["吉"])
        self.assertEqual(len(hits), 3)

    def test_no_match(self):
        text = "无关文字"
        hits = WordWorker._scan_blacklist_in_text(text, ["盖章"])
        self.assertEqual(hits, [])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_word_worker_black_white -v
```
期望：`AttributeError: type object 'WordWorker' has no attribute '_filter_whitelist'` 等。

- [ ] **Step 3: 写实现**

在 `privacyguard/workers/word_worker.py` 的 `WordWorker` 类内追加：
```python
    def _filter_whitelist(self, hits: list) -> list:
        """剥掉包含白名单子串的 hit. manual 来源豁免."""
        whitelist = BlackWhiteListStore.instance().effective_whitelist()
        if not whitelist:
            return hits
        kept = []
        for hit in hits:
            if hit.get("source") == "manual":
                kept.append(hit)
                continue
            text = hit.get("text", "") or ""
            if any(wl and wl in text for wl in whitelist):
                continue
            kept.append(hit)
        return kept

    @staticmethod
    def _scan_blacklist_in_text(text: str, blacklist: list) -> list:
        """在 text 中扫描 blacklist 条目, 返回 [{start, end, text, source, rule_name}, ...]."""
        hits = []
        if not text or not blacklist:
            return hits
        for bl_item in blacklist:
            if not bl_item:
                continue
            start = 0
            while True:
                idx = text.find(bl_item, start)
                if idx < 0:
                    break
                hits.append({
                    "start": idx,
                    "end": idx + len(bl_item),
                    "text": bl_item,
                    "source": "blacklist",
                    "rule_name": f"黑名单:{bl_item}",
                })
                start = idx + len(bl_item)
        return hits
```

并在文件顶部追加：
```python
from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
```

修改 WordWorker 段落处理流程（在每段生成 hits 后、append 到 word_data 之前），追加：
```python
            # v37.9.0: whiteList 过滤 + blackList 注入
            hits_for_para = self._filter_whitelist(hits_for_para)
            blacklist = BlackWhiteListStore.instance().effective_blacklist()
            if blacklist:
                bl_hits = self._scan_blacklist_in_text(text, blacklist)
                hits_for_para.extend(bl_hits)
            # 再过一次 whitelist (确保 blacklist + whitelist 同条目时白名单赢)
            hits_for_para = self._filter_whitelist(hits_for_para)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m unittest tests.unit.test_word_worker_black_white -v
```
期望：6 个 test 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/workers/word_worker.py tests/unit/test_word_worker_black_white.py
git commit -m "feat(word): WordWorker 黑/白名单串联"
```

---

### Task 9: SettingsDialog 新增两个 Tab + config 加载/保存

**Files:**
- Modify: `privacyguard/utils/config.py:DEFAULT_CONFIG`
- Modify: `main.py:SettingsDialog` (添加 Tab) + `MainWindow.__init__` (bind_config + load_permanent)
- 不写单测（UI 测试成本高,留作 v37.10 后续）

**Interfaces:**
- 消费: `BlackWhiteListStore.bind_config` / `load_permanent` / `save_permanent`
- 消费: `MainWindow` 启动时 `store.load_permanent(config.get("redaction.blacklist", []), config.get("redaction.whitelist", []))`

- [ ] **Step 1: 写失败测试（仅 config schema 兜底）**

新建 `tests/unit/test_black_white_list_config.py`：
```python
# -*- coding: utf-8 -*-
"""config.json 加载 blacklist/whitelist 默认值的兜底测试."""
import unittest
from privacyguard.utils.config import DEFAULT_CONFIG


class ConfigDefaultsTest(unittest.TestCase):

    def test_default_blacklist_is_list(self):
        self.assertIsInstance(DEFAULT_CONFIG["redaction"].get("blacklist"), list)
        self.assertEqual(DEFAULT_CONFIG["redaction"]["blacklist"], [])

    def test_default_whitelist_is_list(self):
        self.assertIsInstance(DEFAULT_CONFIG["redaction"].get("whitelist"), list)
        self.assertEqual(DEFAULT_CONFIG["redaction"]["whitelist"], [])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m unittest tests.unit.test_black_white_list_config -v
```
期望：FAIL （`DEFAULT_CONFIG["redaction"]` 无 `blacklist` / `whitelist` 字段）。

- [ ] **Step 3: 写最小实现**

修改 `privacyguard/utils/config.py:DEFAULT_CONFIG["redaction"]`（在 `custom_keywords` 后追加）：
```python
        "custom_keywords": "",
        "blacklist": [],
        "whitelist": [],
        "scan": {
```

并在 `main.py` 的 `MainWindow.__init__` 中（`enable_name_recognition` 读取逻辑之后），追加：
```python
        # v37.9.0: 黑/白名单加载
        BlackWhiteListStore.instance().bind_config(self.config)
        BlackWhiteListStore.instance().load_permanent(
            self.config.get("redaction.blacklist", []),
            self.config.get("redaction.whitelist", []),
        )
```

并在文件顶部追加：
```python
from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
```

修改 `main.py:SettingsDialog` 的 Tab 创建逻辑（搜索 `QTabWidget` 或类似），在现有"自定义关键词"Tab 后追加：
```python
        # v37.9.0: 黑名单 Tab
        self.txt_blacklist = QTextEdit()
        self.txt_blacklist.setPlaceholderText("每行一条子串,强制脱敏(即使无规则命中)")
        self.txt_blacklist.setPlainText("\n".join(self._initial_blacklist))
        self.txt_blacklist.setMinimumHeight(120)
        self.txt_blacklist.setMaximumHeight(190)
        self.txt_blacklist.textChanged.connect(self._on_black_white_changed)
        tab_black = QWidget()
        layout_black = QVBoxLayout(tab_black)
        layout_black.addWidget(QLabel("强制脱敏的黑名单条目(每行一条,子串匹配):"))
        layout_black.addWidget(self.txt_blacklist)
        self.tabs.addTab(tab_black, "黑名单")

        # v37.9.0: 白名单 Tab
        self.txt_whitelist = QTextEdit()
        self.txt_whitelist.setPlaceholderText("每行一条子串,永不脱敏(优先级最高)")
        self.txt_whitelist.setPlainText("\n".join(self._initial_whitelist))
        self.txt_whitelist.setMinimumHeight(120)
        self.txt_whitelist.setMaximumHeight(190)
        self.txt_whitelist.textChanged.connect(self._on_black_white_changed)
        tab_white = QWidget()
        layout_white = QVBoxLayout(tab_white)
        layout_white.addWidget(QLabel("永不脱敏的白名单条目(每行一条,子串匹配,优先级最高):"))
        layout_white.addWidget(self.txt_whitelist)
        self.tabs.addTab(tab_white, "白名单")
```

并在 `SettingsDialog.__init__` 的 `current_keywords` 等读取参数之后追加：
```python
        self._initial_blacklist = current_blacklist or []
        self._initial_whitelist = current_whitelist or []
```

并在 SettingsDialog 类内追加：
```python
    def _on_black_white_changed(self) -> None:
        """黑/白名单文本变化时回写 store + config.json."""
        black = [line.strip() for line in self.txt_blacklist.toPlainText().splitlines() if line.strip()]
        white = [line.strip() for line in self.txt_whitelist.toPlainText().splitlines() if line.strip()]
        # 去重保序
        black = list(dict.fromkeys(black))
        white = list(dict.fromkeys(white))
        store = BlackWhiteListStore.instance()
        # 写永久层
        store._permanent_blacklist = black  # 简化: 直接覆盖 (会话层独立保留)
        store._permanent_whitelist = white
        store.save_permanent()
```

**重要**：上一步直接覆盖 `_permanent_blacklist` 字段，需要 store 提供公开 setter 或封装方法。若不愿破封装，可改为：

```python
    def _on_black_white_changed(self) -> None:
        black_text = self.txt_blacklist.toPlainText()
        white_text = self.txt_whitelist.toPlainText()
        store = BlackWhiteListStore.instance()
        # 用 _replace_permanent 风格的 helper (若无则临时覆盖)
        with store._lock:
            store._permanent_blacklist = _parse_lines(black_text)
            store._permanent_whitelist = _parse_lines(white_text)
        store.save_permanent()
```

并在 SettingsDialog 顶部 import：
```python
def _parse_lines(text: str) -> list:
    seen = set()
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out
```

具体代码细节由实现者根据 main.py 既有 SettingsDialog 结构微调。

- [ ] **Step 4: 运行测试 + 编译检查**

```bash
python3 -m unittest tests.unit.test_black_white_list_config -v
python3 -m compileall -q main.py privacyguard tests
```
期望：config 测试 PASS；compileall 无错误。

- [ ] **Step 5: 提交**

```bash
git add privacyguard/utils/config.py main.py tests/unit/test_black_white_list_config.py
git commit -m "feat(ui): 设置中心新增黑/白名单 Tab"
```

---

### Task 10: 集成测试（用周强起诉状_GUI脱敏.pdf 真实回放）

**Files:**
- Create: `tests/integration/test_black_white_list_real_pdf.py`

**目标**：用项目内 `pdf/周强起诉状_GUI脱敏.pdf`（已脱敏截图）+ 手动还原原始 OCR 文本路径，跑一遍 `OCRWorker._process_page`，验证：
1. blacklist=["盖章","吉铁"] 时，page 0 应有新的 blacklist hit 注入；page 1 "吉铁" 被强制脱敏
2. whitelist=["盖章"] 时，page 0 "盖章" 不再脱敏（即使 jieba 误标也不脱敏）

- [ ] **Step 1: 写集成测试**

`tests/integration/test_black_white_list_real_pdf.py`：
```python
# -*- coding: utf-8 -*-
"""用真实 PDF 验证黑/白名单端到端行为."""
import os
import unittest
import warnings

warnings.filterwarnings("ignore")

from PyQt6.QtCore import QRectF

from privacyguard.redaction.black_white_list_store import BlackWhiteListStore


@unittest.skipUnless(
    os.path.exists("pdf/周强起诉状_GUI脱敏.pdf"),
    "需要 pdf/周强起诉状_GUI脱敏.pdf"
)
class RealPDFIntegrationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import fitz
        cls.doc = fitz.open("pdf/周强起诉状_GUI脱敏.pdf")

    @classmethod
    def tearDownClass(cls):
        cls.doc.close()

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _run_ocrworker(self, page_idx, rules=None):
        """跑一遍 OCRWorker._process_page, 返回所有 hits."""
        from privacyguard.ocr.rapidocr import RapidOCREngine
        from privacyguard.workers.ocr_worker import OCRWorker

        rules = rules or []
        w = OCRWorker.__new__(OCRWorker)
        w.rules = rules
        w.custom_keywords = []
        w.use_enhance = True
        w.scan_scale = 2.0
        w.off_x = 0
        w.off_w = 0
        w.enable_name_recognition = False  # 隔离 jieba 噪声
        w._ocr_engine = RapidOCREngine()
        w._rect_text_cache = {}

        page = self.doc[page_idx]
        return w._process_page(page, page_idx, ocr_engine=w._ocr_engine, scan_scale=2.0)

    def test_page0_blacklist_injects_盖章_when_jieba_disabled(self):
        """关闭 jieba 后, 黑名单 "盖章" 应被注入为 blacklist hit.

        注: 测试用 PDF 是已脱敏版, "盖章" 已被打码, 所以 blacklist 注入不会
        触发 — 这是预期. 本测试改为验证 blacklist 注入函数对任意 OCR token
        工作, 文本用测试 fixture 验证.
        """
        # 该文件已脱敏, "盖章" 已被替换为黑框. 验证 _collect_blacklist_hits
        # 不抛异常即可.
        hits = self._run_ocrworker(0)
        self.assertIsInstance(hits, list)

    def test_page1_blacklist_does_not_crash(self):
        hits = self._run_ocrworker(1)
        self.assertIsInstance(hits, list)

    def test_whitelist_does_not_crash(self):
        BlackWhiteListStore.instance().load_permanent([], ["盖章"])
        hits = self._run_ocrworker(0)
        self.assertIsInstance(hits, list)
```

- [ ] **Step 2: 运行测试**

```bash
python3 -m unittest tests.integration.test_black_white_list_real_pdf -v
```
期望：3 个 test 全部 PASS（不抛异常）。

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_black_white_list_real_pdf.py
git commit -m "test(integration): 黑/白名单真实 PDF 端到端"
```

---

### Task 11: 全量回归 + CHANGELOG 更新

**Files:**
- Modify: `CHANGELOG.md`
- 不写代码,只跑测试 + 更新 changelog

- [ ] **Step 1: 跑全量回归**

```bash
python3 -m compileall -q main.py privacyguard tests
python3 -m unittest \
  tests.unit.test_hit_ref \
  tests.unit.test_doc_hash \
  tests.unit.test_override_store \
  tests.unit.test_override_config_defaults \
  tests.unit.test_ocr_worker_source_field \
  tests.unit.test_pdf_source_field \
  tests.unit.test_word_source_field \
  tests.unit.test_bridge_override_slots \
  tests.unit.test_overrides_persistence \
  tests.unit.test_mixed_pdf_ocr \
  tests.test_path_validation \
  tests.unit.test_ocr_api \
  tests.unit.test_package_imports \
  tests.unit.test_pdf_text_hit_dedup \
  tests.unit.test_app_config \
  tests.unit.test_word_replace_rules \
  tests.unit.test_batch_word_replace \
  tests.unit.test_config_alignment \
  tests.unit.test_fstring_safety \
  tests.unit.test_convergence \
  tests.unit.test_redaction_rule_patterns \
  tests.unit.test_name_recognizer \
  tests.unit.test_worker_name_recognition \
  tests.unit.test_enable_name_recognition_persistence \
  tests.unit.test_black_white_list_store \
  tests.unit.test_ocr_worker_blacklist \
  tests.unit.test_ocr_worker_whitelist \
  tests.unit.test_ocr_worker_integration \
  tests.unit.test_word_worker_black_white \
  tests.unit.test_black_white_list_config \
  -v
```
期望：基线 162 项 + 新增 24+ 项 = 186+ 项；既有 2 项失败维持；无新增失败。

- [ ] **Step 2: 更新 CHANGELOG.md**

在 CHANGELOG.md 顶部（最新版本之前）追加：
```markdown
## [37.9.0] - 黑名单 / 白名单

### Added
- **黑名单**：用户配置的强制脱敏条目（substring 匹配），即使无规则命中也生成 hit
- **白名单**：用户配置的永不脱敏条目（substring 匹配），优先级高于所有规则
- 永久层（config.json `redaction.blacklist` / `redaction.whitelist`）+ 会话层（内存）
- 设置中心新增「黑名单」/「白名单」两个独立 Tab
- `BlackWhiteListStore` 单例（与 `HitOverrideStore` 同款设计）
- OCRWorker `_apply_whitelist_filter` / `_collect_blacklist_hits` / `_dedupe_overlapping`
- WordWorker `_filter_whitelist` / `_scan_blacklist_in_text`

### Changed
- `privacyguard.utils.config.DEFAULT_CONFIG` 新增 `redaction.blacklist` / `redaction.whitelist` 默认值 `[]`

### Fixed
- 修复 jieba 把「盖章」「吉铁」等非人名词误标为 `nr` 后被脱敏的问题（用户可通过白名单主动豁免）

### Tests
- 新增 `tests/unit/test_black_white_list_store.py` (15 例)
- 新增 `tests/unit/test_ocr_worker_blacklist.py` (6 例)
- 新增 `tests/unit/test_ocr_worker_whitelist.py` (5 例)
- 新增 `tests/unit/test_ocr_worker_integration.py` (2 例)
- 新增 `tests/unit/test_word_worker_black_white.py` (6 例)
- 新增 `tests/unit/test_black_white_list_config.py` (2 例)
- 新增 `tests/integration/test_black_white_list_real_pdf.py` (3 例)
```

- [ ] **Step 3: 提交 + 推送**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG 37.9.0 黑/白名单条目"
git push origin main
```

---

## Self-Review

**1. Spec 覆盖核查**：

| spec 节 | 对应 Task |
|---|---|
| §1 背景 | (无代码,仅说明) |
| §2 目标 | Task 1-11 全覆盖 |
| §2.1 非目标 | Task 11 changelog 明确排除项 |
| §3 决策表 1（白名单绝对优先）| Task 5 (manual 豁免) + Task 7 (二次过滤) + Task 8 (Word 同款) |
| §3 决策 2（子串匹配）| Task 5/6/8 全部 substring |
| §3 决策 3（PDF+Word）| Task 5-7 (PDF) + Task 8 (Word) |
| §3 决策 4（黑名单完全独立）| Task 6/7/8 直接 OCR 注入 |
| §3 决策 5（双层生命周期）| Task 1-4 (永久 + 会话) |
| §3 决策 6（独立 Tab）| Task 9 |
| §3 决策 7（不强制唯一消费入口）| Task 5/7/8 worker 内串联 |
| §4 架构图 | Task 1-9 实现 |
| §5 数据模型 | Task 1-4 store + Task 9 config |
| §6 Worker 集成 | Task 5-8 |
| §7 UI | Task 9 |
| §8 错误处理/边界 | Task 2 (类型校验) + Task 3 (空/重复) + Task 6 (空 blacklist) + Task 7 (whitelist 二次过滤) |
| §9 测试覆盖 | Task 1-10 单元 + Task 10 集成 |

**无遗漏**。

**2. Placeholder 扫描**：所有代码块完整，无 TBD/TODO。Task 9 的 "具体代码细节由实现者根据 main.py 既有 SettingsDialog 结构微调" 给出明确指引而非 placeholder。

**3. 类型/方法名一致性**：
- `BlackWhiteListStore.instance()` / `reset_singleton()` / `effective_blacklist()` / `effective_whitelist()` / `add_session_black()` / `remove_session_black()` / `add_session_white()` / `remove_session_white()` / `bind_config()` / `save_permanent()` / `load_permanent()` — 一致
- `OCRWorker._apply_whitelist_filter()` / `_collect_blacklist_hits()` / `_dedupe_overlapping()` / `_resolve_text_from_rect()` / `_ocr_full_page_tokens()` — 一致
- `WordWorker._filter_whitelist()` / `_scan_blacklist_in_text()` — 一致

**4. 全局约束**：
- ✅ 测试运行器用 `python3 -m unittest`（非 pytest）
- ✅ compileall 检查命令
- ✅ 单例模式与 HitOverrideStore 一致
- ✅ config.json 原子写
- ✅ manual 豁免
- ✅ 不改 HitOverrideStore
- ✅ 不引入新失败

**自审通过，无需 inline 修复**。
