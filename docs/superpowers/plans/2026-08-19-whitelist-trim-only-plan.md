# 白名单片段级豁免 (Whitelist Span Trim) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让白名单条目仅豁免自身所在的字符区间，同 hit 区间内的其他敏感内容（如「周超」）仍正常脱敏；同时保留 v37.9.0 的「整条剥掉」行为作为可回退开关。

**Architecture:** 在 `secureredact/redaction/whitelist_split.py` 实现纯函数 `_split_text_by_whitelist`，由 Word worker 与 OCR worker 在 filter 阶段调用；新增 `BlackWhiteListStore.is_trim_only()` 读 `redaction.whitelist_trim_only` 开关（默认 `True`）；PDF 通道通过新静态方法 `_sub_rect_for_text_span` 用字符权重比例估算子矩形；多行 / 退化场景走保守回退。

**Tech Stack:** Python 3、PyQt6（QRectF）、现有 PyMuPDF/RapidOCR 管线、unittest。

## File Structure

| File | Responsibility |
|---|---|
| `secureredact/redaction/whitelist_split.py` (Create) | 纯函数 `_split_text_by_whitelist`，无外部依赖 |
| `secureredact/redaction/black_white_list_store.py` (Modify) | 新增 `is_trim_only()` / `set_trim_only()`；扩展单例状态 |
| `secureredact/workers/word_worker.py` (Modify) | `_filter_whitelist` 改写支持 trim 模式 |
| `secureredact/workers/ocr_worker.py` (Modify) | `_apply_whitelist_filter` 改写 + 新增 `_sub_rect_for_text_span` 静态方法 |
| `tests/unit/test_whitelist_split.py` (Create) | `_split_text_by_whitelist` 全分支单测 |
| `tests/unit/test_whitelist_trim_only.py` (Create) | Word worker / OCR worker trim 集成单测 |
| `tests/unit/test_whitelist_trim_only_config.py` (Create) | store.is_trim_only + 配置兼容单测 |
| `tests/unit/test_ocr_worker_whitelist.py` (Modify) | 追加 end-to-end trim 用例 |
| `tests/unit/test_word_worker_black_white.py` (Modify) | 追加 end-to-end trim 用例 |
| `config.json` (Modify) | 新增 `redaction.whitelist_trim_only: true` |
| `CHANGELOG.md` (Modify) | v38.0.0 条目 |
| `CLAUDE.md` (Modify) | Common Commands 增加扩展回归命令 |

## Global Constraints

- v37.9.0 既定原则：`source="manual"` 永不被任何机制覆盖，本任务不动这条。
- v37.8.0 `HitOverrideStore` 唯一消费入口语义：子 hit 的 `hit_id` 因 start/end 变化而独立，符合预期，本任务不动 override store。
- v37.9.0 `redaction.blacklist` / `redaction.whitelist` 字段路径不变；新增 `redaction.whitelist_trim_only` 为同级 bool 字段。
- v37.9.0 `BlackWhiteListStore` 单例架构不变；新增方法不破坏既有签名。
- 字符权重需与 `secureredact/workers/ocr_worker.py:_calculate_from_line.get_char_weight` 完全一致（含 CJK 扩展 A / 兼容汉字）。
- 多行 / 退化场景必须保守回退（整条剥掉），不可错画矩形。
- 所有测试遵循项目既定 `unittest` 风格，禁止引入新框架。

---

## Task 1: 实现 `_split_text_by_whitelist` 纯函数

**Files:**
- Create: `secureredact/redaction/whitelist_split.py`
- Test: `tests/unit/test_whitelist_split.py`

**Interfaces:**
- Consumes: 无（无外部依赖）
- Produces: `_split_text_by_whitelist(text: str, whitelist: List[str]) -> List[Tuple[int, int, str]]`

- [ ] **Step 1: 写失败测试**

创建 `tests/unit/test_whitelist_split.py`：

```python
# -*- coding: utf-8 -*-
"""_split_text_by_whitelist 单元测试."""
import unittest

from secureredact.redaction.whitelist_split import _split_text_by_whitelist


class SplitTextByWhitelistTest(unittest.TestCase):

    def test_empty_text_returns_single_empty_span(self):
        self.assertEqual(_split_text_by_whitelist("", []), [(0, 0, "")])

    def test_empty_whitelist_returns_full_span(self):
        self.assertEqual(_split_text_by_whitelist("abc", []), [(0, 3, "abc")])

    def test_empty_text_with_whitelist_returns_empty(self):
        # text 为空, 白名单非空 → 无保留片段
        self.assertEqual(_split_text_by_whitelist("", ["abc"]), [])

    def test_no_match_returns_full_span(self):
        self.assertEqual(
            _split_text_by_whitelist("abc", ["xyz"]),
            [(0, 3, "abc")],
        )

    def test_wl_in_middle_keeps_both_sides(self):
        # "aaaXbbb" + ["X"] → [("aaa", 0, 3), ("bbb", 4, 7)]
        self.assertEqual(
            _split_text_by_whitelist("aaaXbbb", ["X"]),
            [(0, 3, "aaa"), (4, 7, "bbb")],
        )

    def test_wl_at_start(self):
        # "Xbbb" + ["X"] → [("bbb", 1, 4)]
        self.assertEqual(_split_text_by_whitelist("Xbbb", ["X"]), [(1, 4, "bbb")])

    def test_wl_at_end(self):
        # "aaaX" + ["X"] → [("aaa", 0, 3)]
        self.assertEqual(_split_text_by_whitelist("aaaX", ["X"]), [(0, 3, "aaa")])

    def test_wl_covers_full_text(self):
        # "aaa" + ["aaa"] → []
        self.assertEqual(_split_text_by_whitelist("aaa", ["aaa"]), [])

    def test_multiple_non_overlapping_wl(self):
        # "abc" + ["a", "c"] → [("b", 1, 2)]
        self.assertEqual(_split_text_by_whitelist("abc", ["a", "c"]), [(1, 2, "b")])

    def test_overlapping_wl_merged(self):
        # "aaaa" + ["aa", "aaa"] → wl 位置 [(0,2),(0,3)] 合并 [(0,3)] → 反转 [("a", 3, 4)]
        self.assertEqual(
            _split_text_by_whitelist("aaaa", ["aa", "aaa"]),
            [(3, 4, "a")],
        )

    def test_wl_appearing_multiple_times(self):
        # "XaXaX" + ["X"] → [("a", 1, 2), ("a", 3, 4)]
        self.assertEqual(
            _split_text_by_whitelist("XaXaX", ["X"]),
            [(1, 2, "a"), (3, 4, "a")],
        )

    def test_chinese_text_with_cjk_substring(self):
        # "法定代表人：周超" + ["法定代表人"] → [("：周超", 5, 8)]
        self.assertEqual(
            _split_text_by_whitelist("法定代表人：周超", ["法定代表人"]),
            [(5, 8, "：周超")],
        )

    def test_empty_string_in_whitelist_ignored(self):
        # 空串白名单条目视为无匹配
        self.assertEqual(
            _split_text_by_whitelist("abc", ["", "b"]),
            [(0, 1, "a"), (2, 3, "c")],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.unit.test_whitelist_split -v`
Expected: `ModuleNotFoundError: No module named 'secureredact.redaction.whitelist_split'`

- [ ] **Step 3: 实现 `_split_text_by_whitelist`**

创建 `secureredact/redaction/whitelist_split.py`：

```python
# -*- coding: utf-8 -*-
"""白名单片段级豁免的纯文本拆分逻辑.

v38: 用于 worker filter 阶段, 把 hit 文本按白名单子串位置切成保留片段.
"""
from __future__ import annotations

from typing import List, Tuple


def _split_text_by_whitelist(
    text: str,
    whitelist: List[str],
) -> List[Tuple[int, int, str]]:
    """按白名单子串位置把 text 切成若干保留片段.

    Args:
        text: hit 原文
        whitelist: 当前生效的白名单条目 (substring 匹配)

    Returns:
        [(start_offset, end_offset, text_span), ...]
        - offset 是 Python str 索引 (左闭右开)
        - 全段被白名单覆盖 → []
        - text 不含任何 wl → [(0, len(text), text)]
        - 空 text + 空 whitelist → [(0, 0, "")]

    Notes:
        - 空字符串 / 纯空格 wl 条目跳过 (store 层已 sanitize, 此处再次防御)
        - 多条目命中同一区间 → 合并后取反
        - 单条目多次出现 → 每处都豁免
    """
    if not isinstance(text, str):
        return []
    if not isinstance(whitelist, list):
        return [(0, len(text), text)]

    if not whitelist:
        return [(0, len(text), text)]

    # 1) 收集所有 wl 命中区间
    spans: List[Tuple[int, int]] = []
    for wl in whitelist:
        if not isinstance(wl, str):
            continue
        wl = wl.strip()
        if not wl:
            continue
        idx = 0
        while True:
            pos = text.find(wl, idx)
            if pos < 0:
                break
            spans.append((pos, pos + len(wl)))
            idx = pos + 1  # 允许重叠检测

    if not spans:
        return [(0, len(text), text)]

    # 2) 合并重叠区间
    spans.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # 3) 取反集
    kept: List[Tuple[int, int, str]] = []
    cursor = 0
    n = len(text)
    for s, e in merged:
        if s > cursor:
            kept.append((cursor, s, text[cursor:s]))
        cursor = max(cursor, e)
    if cursor < n:
        kept.append((cursor, n, text[cursor:n]))

    return kept
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.unit.test_whitelist_split -v`
Expected: `Ran 13 tests ... OK`

- [ ] **Step 5: 提交**

```bash
git add secureredact/redaction/whitelist_split.py tests/unit/test_whitelist_split.py
git commit -m "feat(redaction): _split_text_by_whitelist — 白名单片段级拆分纯函数"
```

---

## Task 2: 给 BlackWhiteListStore 加 `is_trim_only()` / `set_trim_only()` + 配置读取

**Files:**
- Modify: `secureredact/redaction/black_white_list_store.py:31-156`
- Test: `tests/unit/test_whitelist_trim_only_config.py`

**Interfaces:**
- Consumes: `_config.get("redaction.whitelist_trim_only", True)` 返回任意类型
- Produces: `BlackWhiteListStore.is_trim_only() -> bool`、`BlackWhiteListStore.set_trim_only(value: bool) -> None`、`BlackWhiteListStore._trim_only_override: Optional[bool]`

- [ ] **Step 1: 写失败测试**

创建 `tests/unit/test_whitelist_trim_only_config.py`：

```python
# -*- coding: utf-8 -*-
"""BlackWhiteListStore.is_trim_only 配置读取测试."""
import unittest
from unittest.mock import MagicMock

from secureredact.redaction.black_white_list_store import BlackWhiteListStore


class IsTrimOnlyTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def test_default_true_without_config(self):
        """未 bind_config 时, 默认 True (v38 起 trim_only 默认开)."""
        store = BlackWhiteListStore.instance()
        self.assertTrue(store.is_trim_only())

    def test_explicit_true_from_config(self):
        config = MagicMock()
        config.get.return_value = True
        BlackWhiteListStore.instance().bind_config(config)
        self.assertTrue(BlackWhiteListStore.instance().is_trim_only())
        config.get.assert_called_with("redaction.whitelist_trim_only", True)

    def test_explicit_false_from_config(self):
        config = MagicMock()
        config.get.return_value = False
        BlackWhiteListStore.instance().bind_config(config)
        self.assertFalse(BlackWhiteListStore.instance().is_trim_only())

    def test_non_bool_falls_back_to_true_with_warn(self):
        config = MagicMock()
        config.get.return_value = "true"  # 字符串, 应回退
        BlackWhiteListStore.instance().bind_config(config)
        with self.assertLogs("secureredact.redaction.black_white_list_store",
                             level="WARNING") as cm:
            self.assertTrue(BlackWhiteListStore.instance().is_trim_only())
        self.assertTrue(any("whitelist_trim_only" in m for m in cm.output))

    def test_set_trim_only_overrides_config(self):
        config = MagicMock()
        config.get.return_value = True
        BlackWhiteListStore.instance().bind_config(config)
        store = BlackWhiteListStore.instance()
        store.set_trim_only(False)
        self.assertFalse(store.is_trim_only())

    def test_reset_singleton_clears_override(self):
        store = BlackWhiteListStore.instance()
        store.set_trim_only(False)
        BlackWhiteListStore.reset_singleton()
        self.assertTrue(BlackWhiteListStore.instance().is_trim_only())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.unit.test_whitelist_trim_only_config -v`
Expected: `AttributeError: 'BlackWhiteListStore' object has no attribute 'is_trim_only'`

- [ ] **Step 3: 在 store 上实现 `is_trim_only` / `set_trim_only`**

修改 `secureredact/redaction/black_white_list_store.py`：

1. 顶部 import 增加 `from typing import Any`（已有可忽略）
2. `__init__` 末尾追加：
   ```python
           self._trim_only_override: Optional[bool] = None  # v38: 测试用, 优先级最高
   ```
3. 在文件末尾（`save_permanent` 之后）追加两个方法：

```python
    # ---- v38: trim_only 开关 ----

    def is_trim_only(self) -> bool:
        """v38: 是否启用「白名单只豁免片段」语义.

        优先级: set_trim_only 覆盖 > bind_config 配置 > 默认 True.
        非 bool 配置值回退 True 并 WARN 一次.
        """
        if self._trim_only_override is not None:
            return self._trim_only_override
        if self._config is None:
            return True
        try:
            val = self._config.get(
                "redaction.whitelist_trim_only", True
            )
        except Exception as exc:
            logger.warning("is_trim_only 读配置失败,回退 True: %s", exc)
            return True
        if not isinstance(val, bool):
            logger.warning(
                "whitelist_trim_only 类型错误,回退 True: %s",
                type(val).__name__,
            )
            return True
        return val

    def set_trim_only(self, value: bool) -> None:
        """v38: 测试用直接覆盖 trim_only. 优先级高于 bind_config 配置.

        生产代码不要调用本方法; 走 config.json 自然切换.
        """
        with self._lock:
            self._trim_only_override = bool(value)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.unit.test_whitelist_trim_only_config -v`
Expected: `Ran 6 tests ... OK`

- [ ] **Step 5: 跑既有 store 测试确保无回归**

Run: `python3 -m unittest tests.unit.test_black_white_list_store tests.unit.test_black_white_list_config tests.unit.test_override_store -v`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add secureredact/redaction/black_white_list_store.py tests/unit/test_whitelist_trim_only_config.py
git commit -m "feat(redaction): BlackWhiteListStore.is_trim_only / set_trim_only — v38 开关"
```

---

## Task 3: 改写 WordWorker `_filter_whitelist` 支持 trim 模式

**Files:**
- Modify: `secureredact/workers/word_worker.py:193-207` (替换 `_filter_whitelist` 方法体)
- Test: `tests/unit/test_whitelist_trim_only.py` (本任务写 Word 部分)

**Interfaces:**
- Consumes: `_split_text_by_whitelist` (Task 1)、`BlackWhiteListStore.is_trim_only()` (Task 2)
- Produces: `_filter_whitelist(hits: list) -> list` 行为不变 (trim_only=False) 或切分子 hit (trim_only=True)

- [ ] **Step 1: 写失败测试**

创建 `tests/unit/test_whitelist_trim_only.py`：

```python
# -*- coding: utf-8 -*-
"""白名单 trim_only 集成测试 — Word + PDF."""
import unittest

from secureredact.redaction.black_white_list_store import BlackWhiteListStore
from secureredact.workers.word_worker import WordWorker


def _match(text, source="rule", start=0, end=None, pattern="x"):
    if end is None:
        end = start + len(text)
    return {
        "pattern": pattern,
        "rule_name": "test",
        "start": start,
        "end": end,
        "text": text,
        "replacement": "***",
        "source": source,
    }


class WordFilterWhitelistTrimTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _filter(self, hits, trim_only):
        store = BlackWhiteListStore.instance()
        store.load_permanent([], ["法定代表人"])
        store.set_trim_only(trim_only)
        w = WordWorker.__new__(WordWorker)  # 绕开 QThread
        return w._filter_whitelist(hits)

    def test_trim_only_true_splits_hit_into_kept_span(self):
        hits = [_match("法定代表人：周超", start=0, end=8)]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")
        self.assertEqual(out[0]["start"], 5)
        self.assertEqual(out[0]["end"], 8)

    def test_trim_only_false_drops_whole_hit(self):
        hits = [_match("法定代表人：周超", start=0, end=8)]
        out = self._filter(hits, trim_only=False)
        self.assertEqual(out, [])

    def test_no_match_passes_through(self):
        hits = [_match("周强", start=0, end=2)]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(out, hits)

    def test_manual_source_passes_through(self):
        hits = [_match("法定代表人：周超", start=0, end=8, source="manual")]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(out, hits)

    def test_empty_kept_span_filtered(self):
        # 白名单覆盖整段 → kept span 列表为空 → 整条剥掉
        hits = [_match("法定代表人", start=0, end=5)]
        out = self._filter(hits, trim_only=True)
        self.assertEqual(out, [])

    def test_multi_span_emit_each(self):
        # "盖章并签名" + wl=["盖章", "签名"] → 两段都被剥, 仅保留 "并"
        hits = [_match("盖章并签名", start=0, end=5)]
        store = BlackWhiteListStore.instance()
        store.load_permanent([], ["盖章", "签名"])
        store.set_trim_only(True)
        w = WordWorker.__new__(WordWorker)
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "并")
        self.assertEqual(out[0]["start"], 2)
        self.assertEqual(out[0]["end"], 3)

    def test_relative_start_offset_preserved(self):
        # hit 在段落中的 start=10, 保留片段是 [12, 14]
        hits = [_match("周超", start=12, end=14)]
        store = BlackWhiteListStore.instance()
        store.load_permanent([], [])  # 无白名单
        store.set_trim_only(True)
        w = WordWorker.__new__(WordWorker)
        out = w._filter_whitelist(hits)
        self.assertEqual(out[0]["start"], 12)
        self.assertEqual(out[0]["end"], 14)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.unit.test_whitelist_trim_only -v`
Expected: `AssertionError` 在 `test_trim_only_true_splits_hit_into_kept_span`（旧代码整条剥掉，期望保留子片段）

- [ ] **Step 3: 改写 `_filter_whitelist`**

修改 `secureredact/workers/word_worker.py`：

1. 在 `from secureredact.redaction.black_white_list_store import BlackWhiteListStore` 之后增加：
   ```python
   from secureredact.redaction.whitelist_split import _split_text_by_whitelist
   ```

2. 替换 `_filter_whitelist`（约 193-207 行）：

```python
    def _filter_whitelist(self, hits: list) -> list:
        """v38: 剥掉包含白名单子串的 hit; trim_only=True 时只剥白名单片段."""
        store = BlackWhiteListStore.instance()
        whitelist = store.effective_whitelist()
        if not whitelist or not hits:
            return hits
        trim_only = store.is_trim_only()
        kept: list = []
        for hit in hits:
            if hit.get("source") == "manual":
                kept.append(hit)
                continue
            text = hit.get("text", "") or ""
            spans = _split_text_by_whitelist(text, whitelist)
            # 无 trim 必要 → no_split 成立 ⟺ text 不含 wl, 旧行为与新行为都是原样保留
            no_split = (
                len(spans) == 1
                and spans[0][0] == 0
                and spans[0][1] == len(text)
            )
            if no_split:
                kept.append(hit)
                continue
            # 旧行为 (v37.9.0): 整条剥掉
            if not trim_only:
                continue
            # 新行为 (v38): 每段保留片段生成新 hit
            hit_start = hit.get("start", 0)
            for s, e, t in spans:
                if not t:
                    continue
                new_hit = dict(hit)
                new_hit["start"] = hit_start + s
                new_hit["end"] = hit_start + e
                new_hit["text"] = t
                kept.append(new_hit)
        return kept
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.unit.test_whitelist_trim_only -v`
Expected: `Ran 7 tests ... OK`

- [ ] **Step 5: 跑既有 Word worker 测试确保无回归**

Run: `python3 -m unittest tests.unit.test_word_worker_black_white -v`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add secureredact/workers/word_worker.py tests/unit/test_whitelist_trim_only.py
git commit -m "feat(word): WordWorker._filter_whitelist 支持 trim_only — 只豁免白名单片段"
```

---

## Task 4: 改写 OCRWorker `_apply_whitelist_filter` + 新增 `_sub_rect_for_text_span`

**Files:**
- Modify: `secureredact/workers/ocr_worker.py:305-325` (替换 `_apply_whitelist_filter`) + 新增静态方法
- Test: `tests/unit/test_whitelist_trim_only.py` (追加 OCR 部分)

**Interfaces:**
- Consumes: `_split_text_by_whitelist` (Task 1)、`BlackWhiteListStore.is_trim_only()` (Task 2)、`_resolve_text_from_rect` (既有)
- Produces: 
  - `_apply_whitelist_filter(rects: list, page_idx: int) -> list`
  - `_sub_rect_for_text_span(rect: Optional[QRectF], text: str, kept_start: int, kept_end: int) -> Optional[QRectF]` (静态)

- [ ] **Step 1: 追加 OCR worker 的失败测试**

修改 `tests/unit/test_whitelist_trim_only.py`，在文件末尾追加：

```python
from PyQt6.QtCore import QRectF
from secureredact.workers.ocr_worker import OCRWorker


class _StubOCRWorker(OCRWorker):
    """绕开 QThread, 只调用被测方法."""
    def __init__(self):
        pass

    def _apply_whitelist_filter(self, rects, page_idx=0):
        return OCRWorker._apply_whitelist_filter(self, rects, page_idx)


def _hit(text, source="rule", x=0, y=0, w=100, h=12):
    return {"rect": QRectF(x, y, w, h), "source": source, "text": text, "rule_name": "test"}


class OCRFilterWhitelistTrimTest(unittest.TestCase):

    def setUp(self):
        BlackWhiteListStore.reset_singleton()

    def tearDown(self):
        BlackWhiteListStore.reset_singleton()

    def _filter(self, rects, trim_only, wl=("法定代表人",), resolve_map=None):
        store = BlackWhiteListStore.instance()
        store.load_permanent([], list(wl))
        store.set_trim_only(trim_only)
        w = _StubOCRWorker()
        if resolve_map is not None:
            w._resolve_text_from_rect = lambda rect, page_idx: resolve_map.get(id(rect), "")
        return w._apply_whitelist_filter(rects, page_idx=0)

    def test_text_channel_trim_only_true_emits_sub_rect(self):
        rects = [_hit("法定代表人：周超", x=0, y=0, w=100, h=12)]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")
        # 子矩形 x 应在原矩形内, 宽度约为原 (3/8)
        sub = out[0]["rect"]
        self.assertGreaterEqual(sub.x(), 0)
        self.assertLess(sub.x() + sub.width(), 100.1)
        self.assertAlmostEqual(sub.width(), 100 * 3 / 8, delta=5)

    def test_text_channel_trim_only_false_drops_whole_hit(self):
        rects = [_hit("法定代表人：周超")]
        out = self._filter(rects, trim_only=False)
        self.assertEqual(out, [])

    def test_text_channel_no_match_passes_through(self):
        rects = [_hit("周强")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, rects)

    def test_text_channel_manual_passes_through(self):
        rects = [_hit("法定代表人：周超", source="manual")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, rects)

    def test_text_channel_empty_kept_span_drops_hit(self):
        # 白名单覆盖整段 → spans=[] → 整条剥掉
        rects = [_hit("法定代表人")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, [])

    def test_ocr_channel_resolves_text_then_trims(self):
        # OCR 通道 hit.text="", 通过 _resolve_text_from_rect 查回
        hit = _hit("", source="ocr", x=0, y=0, w=100, h=12)
        out = self._filter(
            [hit],
            trim_only=True,
            resolve_map={id(hit["rect"]): "法定代表人：周超"},
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")

    def test_multi_line_text_in_kept_span_falls_back(self):
        # 保留片段含换行 → 保守回退 → 该片段丢弃
        # 构造一个 hit, 其 text 含换行且 wl 在第一行
        rects = [_hit("法定代表人\n周超")]
        out = self._filter(rects, trim_only=True)
        self.assertEqual(out, [])

    def test_sub_rect_for_text_span_basic(self):
        # 直接验证 _sub_rect_for_text_span 静态方法
        rect = QRectF(0, 0, 100, 12)
        sub = OCRWorker._sub_rect_for_text_span(rect, "abcdef", 2, 4)
        self.assertIsNotNone(sub)
        # CJK 全算 1.0 权重, 比例 2/6 和 2/6
        self.assertAlmostEqual(sub.x(), 100 * 2 / 6, delta=0.01)
        self.assertAlmostEqual(sub.width(), 100 * 2 / 6, delta=0.01)

    def test_sub_rect_for_text_span_cjk_weight(self):
        # CJK 字符权重 1.0, 其它 0.55
        rect = QRectF(0, 0, 100, 12)
        # "法定代表人周超" 全 CJK, 8 字符, kept [5, 7] = "周超"
        # prefix_weight = 5 (全 1.0), match_weight = 2, total = 8
        sub = OCRWorker._sub_rect_for_text_span(rect, "法定代表人周超", 5, 7)
        self.assertIsNotNone(sub)
        self.assertAlmostEqual(sub.x(), 100 * 5 / 8, delta=0.01)
        self.assertAlmostEqual(sub.width(), 100 * 2 / 8, delta=0.01)

    def test_sub_rect_for_text_span_mixed_width(self):
        # 中英文混排, ASCII 字符权重 0.55
        rect = QRectF(0, 0, 100, 12)
        # "a法定代表人" → weights [0.55, 1.0, 1.0, 1.0, 1.0, 1.0] total=5.55
        # kept [1, 4] = "法定代", weights [1,1,1] sum=3
        # prefix_weight = 0.55
        sub = OCRWorker._sub_rect_for_text_span(rect, "a法定代表人", 1, 4)
        self.assertIsNotNone(sub)
        self.assertAlmostEqual(sub.x(), 100 * 0.55 / 5.55, delta=0.1)
        self.assertAlmostEqual(sub.width(), 100 * 3 / 5.55, delta=0.1)

    def test_sub_rect_returns_none_on_multiline_kept(self):
        rect = QRectF(0, 0, 100, 12)
        self.assertIsNone(
            OCRWorker._sub_rect_for_text_span(rect, "ab\ncd", 0, 4)
        )

    def test_sub_rect_returns_none_on_invalid_args(self):
        rect = QRectF(0, 0, 100, 12)
        self.assertIsNone(OCRWorker._sub_rect_for_text_span(None, "abc", 0, 1))
        self.assertIsNone(OCRWorker._sub_rect_for_text_span(rect, "", 0, 0))
        self.assertIsNone(OCRWorker._sub_rect_for_text_span(rect, "abc", 2, 2))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.unit.test_whitelist_trim_only.OCRFilterWhitelistTrimTest -v`
Expected: 大部分失败，旧代码无 trim 逻辑

- [ ] **Step 3: 在 OCR worker 实现 `_sub_rect_for_text_span` + 改写 `_apply_whitelist_filter`**

修改 `secureredact/workers/ocr_worker.py`：

1. 在 import 区域增加：
   ```python
   from secureredact.redaction.whitelist_split import _split_text_by_whitelist
   ```

2. 在 `_apply_whitelist_filter` 方法（305-325 行）之后新增静态方法：

```python
    @staticmethod
    def _sub_rect_for_text_span(
        rect,
        text: str,
        kept_start: int,
        kept_end: int,
    ):
        """v38: 字符权重比例估算子矩形. 多行 / 退化 → 返回 None (保守回退).

        字符权重与 _calculate_from_line.get_char_weight 对齐:
          - CJK 统一汉字 (一-鿿): 1.0
          - CJK 扩展 A (㐀-䶿): 1.0
          - CJK 兼容汉字 (豈-﫿): 1.0
          - 其它: 0.55
        """
        if rect is None or not text or kept_end <= kept_start:
            return None
        kept_span = text[kept_start:kept_end]
        if "\n" in kept_span:
            return None
        weights = [
            1.0 if (
                "一" <= c <= "鿿"
                or "㐀" <= c <= "䶿"
                or "豈" <= c <= "﫿"
            ) else 0.55
            for c in text
        ]
        total = sum(weights) or len(text)
        prefix = sum(weights[:kept_start])
        match = sum(weights[kept_start:kept_end])
        if total <= 0 or match <= 0:
            return None
        sub_x = rect.x() + (prefix / total) * rect.width()
        sub_w = (match / total) * rect.width()
        if sub_w <= 0:
            return None
        return QRectF(sub_x, rect.y(), sub_w, rect.height())
```

3. 替换 `_apply_whitelist_filter`（305-325 行）：

```python
    def _apply_whitelist_filter(self, rects: list, page_idx: int) -> list:
        """v38: 剥掉包含白名单子串的 hit; trim_only=True 时只剥白名单片段."""
        store = BlackWhiteListStore.instance()
        whitelist = store.effective_whitelist()
        if not whitelist:
            return rects
        trim_only = store.is_trim_only()
        kept: list = []
        for hit in rects:
            source = hit.get("source", "ocr")
            if source == "manual":
                kept.append(hit)
                continue
            text = hit.get("text", "") or ""
            if not text:
                text = self._resolve_text_from_rect(hit.get("rect"), page_idx) or ""
            if not text:
                # 解析失败 → 沿用旧行为保留
                kept.append(hit)
                continue
            spans = _split_text_by_whitelist(text, whitelist)
            # 无 trim 必要 → 原样保留 (旧/新行为一致)
            no_split = (
                len(spans) == 1
                and spans[0][0] == 0
                and spans[0][1] == len(text)
            )
            if no_split:
                kept.append(hit)
                continue
            # 旧行为 (v37.9.0): 整条剥掉
            if not trim_only:
                continue
            # 新行为 (v38): 每个保留片段生成子 hit
            original_rect = hit.get("rect")
            for s, e, t in spans:
                if not t:
                    continue
                sub_rect = self._sub_rect_for_text_span(original_rect, text, s, e)
                if sub_rect is None:
                    continue  # 保守回退 (含换行 / 退化宽度)
                new_hit = dict(hit)
                new_hit["rect"] = sub_rect
                new_hit["text"] = t
                kept.append(new_hit)
        return kept
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.unit.test_whitelist_trim_only -v`
Expected: `Ran 18 tests ... OK` (7 Word + 11 OCR)

- [ ] **Step 5: 跑既有 OCR worker 测试确保无回归**

Run: `python3 -m unittest tests.unit.test_ocr_worker_whitelist tests.unit.test_ocr_worker_blacklist -v`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add secureredact/workers/ocr_worker.py tests/unit/test_whitelist_trim_only.py
git commit -m "feat(ocr): OCRWorker._apply_whitelist_filter 支持 trim_only — 只豁免白名单片段"
```

---

## Task 5: 端到端 trim 用例 + config.json + CHANGELOG

**Files:**
- Modify: `tests/unit/test_ocr_worker_whitelist.py`
- Modify: `tests/unit/test_word_worker_black_white.py`
- Modify: `config.json`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: 既有测试文件框架
- Produces: 端到端 trim 行为固定在既有测试文件中

- [ ] **Step 1: 在 `test_ocr_worker_whitelist.py` 追加 end-to-end trim 用例**

修改 `tests/unit/test_ocr_worker_whitelist.py`，在 `ApplyWhitelistFilterTest` 类内末尾追加：

```python
    def test_trim_only_keeps_only_non_whitelisted_substring(self):
        """v38: trim_only=True 时, 整段命中应被切成非白名单位置的子 hit."""
        BlackWhiteListStore.instance().load_permanent([], ["法定代表人"])
        BlackWhiteListStore.instance().set_trim_only(True)
        w = _StubOCRWorker()
        rects = [_hit("法定代表人：周超", x=0, y=0, w=100, h=12)]
        out = w._apply_whitelist_filter(rects, page_idx=0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")
        sub = out[0]["rect"]
        # 子矩形必须落在原矩形范围内
        self.assertGreaterEqual(sub.x(), 0)
        self.assertLessEqual(sub.x() + sub.width(), 100.01)
        self.assertLess(sub.width(), 100)
```

- [ ] **Step 2: 在 `test_word_worker_black_white.py` 追加 end-to-end trim 用例**

修改 `tests/unit/test_word_worker_black_white.py`，追加一个测试方法（具体类名按既有约定）：

```python
    def test_trim_only_keeps_only_non_whitelisted_substring(self):
        """v38: trim_only=True 时, 整段 Word 命中被切成非白名单位置的子 match."""
        from secureredact.redaction.black_white_list_store import BlackWhiteListStore
        BlackWhiteListStore.reset_singleton()
        store = BlackWhiteListStore.instance()
        store.load_permanent([], ["法定代表人"])
        store.set_trim_only(True)
        from secureredact.workers.word_worker import WordWorker
        w = WordWorker.__new__(WordWorker)
        hits = [{
            "pattern": "test", "rule_name": "test",
            "start": 0, "end": 8, "text": "法定代表人：周超",
            "replacement": "***", "source": "rule",
        }]
        out = w._filter_whitelist(hits)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "：周超")
        self.assertEqual(out[0]["start"], 5)
        self.assertEqual(out[0]["end"], 8)
```

- [ ] **Step 3: 更新 `config.json`**

修改 `/mnt/g/Project/SecureRedact/config.json`，在 `redaction` 节点下（与 `blacklist` / `whitelist` 同级）增加：

```json
    "whitelist_trim_only": true,
```

注意保持 JSON 逗号与换行风格（项目用 CRLF，先 `file config.json` 确认）。

- [ ] **Step 4: 更新 `CHANGELOG.md`**

在 `CHANGELOG.md` 顶部（最新版本之前）追加 v38.0.0 条目：

```markdown
## v38.0.0 - 白名单片段级豁免 (Whitelist Span Trim)

### 新增

- **白名单片段级豁免**：白名单条目仅豁免自身所在片段，同 hit 区间内的其他敏感内容仍然脱敏。
  - 例：「法定代表人：周超」+ 白名单「法定代表人」→ 「法定代表人」不脱敏，「周超」仍然脱敏。
- 新增开关 `redaction.whitelist_trim_only`（默认 `true`）。设为 `false` 回退到 v37.9.0 「子串命中即整条剥掉」行为。
- 新增模块 `secureredact/redaction/whitelist_split.py` 与静态工具 `OCRWorker._sub_rect_for_text_span`（CJK 字符权重比例估算）。

### 影响范围

- Word 段落 / 表格 matches（rule / jieba / blacklist）
- PDF 文本通道 hits（rule / jieba / custom_keyword）
- PDF 图片通道 OCR hits
- `source="manual"` 命中永远 passthrough（v37.8.0 不变）
- `source="seal"` 命中 passthrough（text 为空，无可裁剪语义）
- 多行 hit 走保守回退（整条剥掉）

### 兼容性

- 子 hit 的 `hit_id` 因 start/end 变化而独立，不与原 hit 的永久 override 关联（trim 本身是新决策，符合 v37.8.0 唯一消费入口语义）。
- v37.9.0 用户升级后想恢复旧行为：设 `"redaction.whitelist_trim_only": false`。
```

- [ ] **Step 5: 跑扩展回归确保所有测试通过**

Run: 
```bash
python3 -m compileall -q main.py secureredact tests
python3 -m unittest \
  tests.unit.test_whitelist_split \
  tests.unit.test_whitelist_trim_only \
  tests.unit.test_whitelist_trim_only_config \
  tests.unit.test_ocr_worker_whitelist \
  tests.unit.test_word_worker_black_white \
  -v
```
Expected: 全部通过；`test_ocr_worker_whitelist` 至少 8 个 case（含新增），`test_word_worker_black_white` 至少 1 个新增 case 通过

- [ ] **Step 6: 跑项目全量回归（CLAUDE.md §Common Commands 主回归 + 扩展）**

Run:
```bash
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
  tests.unit.test_whitelist_split \
  tests.unit.test_whitelist_trim_only \
  tests.unit.test_whitelist_trim_only_config \
  tests.unit.test_black_white_list_store \
  tests.unit.test_black_white_list_config \
  tests.unit.test_ocr_worker_whitelist \
  tests.unit.test_ocr_worker_blacklist \
  tests.unit.test_word_worker_black_white \
  -v
```
Expected: `Ran N tests` 全 PASS（已知既有失败 2 个：`test_scan_default_level_matches` 与 `test_simple_config_reads_config_json_values`）

- [ ] **Step 7: 提交**

```bash
git add tests/unit/test_ocr_worker_whitelist.py tests/unit/test_word_worker_black_white.py config.json CHANGELOG.md
git commit -m "feat(redaction): v38 端到端 trim 用例 + config + CHANGELOG"
```

---

## Task 6: 更新 CLAUDE.md Common Commands + 文档索引

**Files:**
- Modify: `CLAUDE.md` (§Common Commands 扩展回归段)
- Modify: `README.md`（如有 changelog 引用）

**Interfaces:**
- Consumes: 现有 §Common Commands 结构
- Produces: 用户运行扩展回归时可直接复制

- [ ] **Step 1: 在 CLAUDE.md §Common Commands 追加扩展回归命令**

修改 `/mnt/g/Project/SecureRedact/CLAUDE.md`，在 `### Extended regression (hit override / 人工干预)` 段之后追加：

```markdown
### Extended regression (whitelist trim_only / 白名单片段级豁免)

```bash
python3 -m unittest \
  tests.unit.test_whitelist_split \
  tests.unit.test_whitelist_trim_only \
  tests.unit.test_whitelist_trim_only_config \
  tests.unit.test_ocr_worker_whitelist \
  tests.unit.test_word_worker_black_white \
  -v
```
```

并在 `### Full regression (v37.8.0 基线)` 段内追加新测试模块名：

```markdown
  tests.unit.test_whitelist_split \
  tests.unit.test_whitelist_trim_only \
  tests.unit.test_whitelist_trim_only_config \
```

（确保插入位置与既有条目对齐，保持 alphabetical 或按 spec 分组的风格）

- [ ] **Step 2: 在 CLAUDE.md §Current active capabilities 追加 trim 描述**

在 `Word dual preview` 段后、`Drag & drop open` 段前（或「人工干预」段附近），追加：

```markdown
- 白名单片段级豁免 (Whitelist Span Trim, v38):
  - 白名单条目仅豁免自身所在片段，同区间内其他敏感内容仍脱敏
  - 通过 `redaction.whitelist_trim_only`（默认 True）控制；设为 False 回退到 v37.9.0 行为
  - 覆盖 Word matches、PDF 文本通道、PDF 图片通道 OCR
```

- [ ] **Step 3: 在 CLAUDE.md §Read First 列表中追加本 spec**

修改 `/mnt/g/Project/SecureRedact/CLAUDE.md`，在 `### Read First` 段中追加：

```markdown
7. `docs/superpowers/specs/2026-08-19-whitelist-trim-only-design.md`
```

（实际编号顺延，与既有条目对齐）

- [ ] **Step 4: 跑全量回归最终确认**

Run: 同 Task 5 Step 6 的全量回归命令

Expected: 全部通过（已知既有失败 2 个不变）

- [ ] **Step 5: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md 增 v38 whitelist trim_only 文档索引与回归命令"
```

---

## Self-Review Checklist (run before declaring plan complete)

- [x] **Spec coverage**:
  - §2.1 目标 → Task 3 (Word)、Task 4 (PDF text + image) ✓
  - §2.1 manual passthrough → Task 3 test + Task 4 test ✓
  - §2.1 seal passthrough → spec 文本说明 (Task 4 hit.text="" 路径自动 passthrough) ✓
  - §2.1 `whitelist_trim_only` 开关 → Task 2 ✓
  - §5.1 config.json schema → Task 5 ✓
  - §5.2 BlackWhiteListStore.is_trim_only → Task 2 ✓
  - §5.3 _split_text_by_whitelist → Task 1 ✓
  - §6.1 Word worker 改写 → Task 3 ✓
  - §6.2 _sub_rect_for_text_span → Task 4 ✓
  - §6.2 _apply_whitelist_filter 改写 → Task 4 ✓
  - §8 测试计划 (whitelist_split / trim_only / config) → Task 1 / 3-5 / 2 ✓
  - §10 实施清单 → Task 1-6 ✓
- [x] **Placeholder scan**: 无 TBD / TODO / 类似 X 占位
- [x] **Type consistency**:
  - `_split_text_by_whitelist(text: str, whitelist: List[str]) -> List[Tuple[int, int, str]]` 在 Task 1 定义，Task 3/4 调用一致
  - `is_trim_only() -> bool` 在 Task 2 定义，Task 3/4 调用一致
  - `set_trim_only(value: bool) -> None` 仅 Task 2 使用，签名一致
  - `_sub_rect_for_text_span(rect, text: str, kept_start: int, kept_end: int) -> Optional[QRectF]` Task 4 定义与调用一致

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-19-whitelist-trim-only-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?