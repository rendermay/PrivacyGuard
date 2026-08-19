# 白名单片段级豁免 — 设计 spec

**作者**: Claude (brainstorming 流程产物)
**日期**: 2026-08-19
**项目**: SecureRedact 信息脱敏助手
**目标版本**: v38.0.0
**状态**: 设计中 (待用户审阅)
**前置 spec**: `docs/superpowers/specs/2026-08-18-blacklist-whitelist-design.md` (v37.9.0)

---

## 1. 背景与动机

v37.9.0 黑/白名单上线后，遇到一个语义颗粒度问题：

> 文本「法定代表人：周超，经理」当前默认会把「法定代表人：周超」作为一条命中。
> 用户把「法定代表人」加入白名单后，「周超」也连带不脱敏。
> 用户的期望是：「法定代表人」不脱敏，「周超」仍然脱敏。

根因：v37.9.0 决策 2 选择「子串匹配」+「命中即整条剥掉」语义：

```python
# secureredact/workers/ocr_worker.py:322
if any(wl and wl in text for wl in whitelist):
    continue  # 整条 hit 被剥掉
```

当一条 hit 的文本长度大于白名单子串时，这条语义过粗，无法表达「白名单只豁免自己，邻居仍要脱敏」。

本文档提出 v38 的「白名单片段级豁免」(Whitelist Span Trim)：把子串命中改成「段落级裁剪」，让白名单条目只豁免它所在的字符区间，剩余片段仍正常脱敏。

---

## 2. 目标与非目标

### 2.1 目标

- 白名单条目仅豁免自身所在片段；同 hit 区间内的其他敏感内容（如「周超」）仍然脱敏
- 覆盖三类命中源：
  - Word 段落 / 表格 matches（rule / jieba / blacklist）
  - PDF 文本通道 hits（rule / jieba / custom_keyword）
  - PDF 图片通道 OCR hits（image-block OCR）
- 通过 `redaction.whitelist_trim_only`（默认 `True`）开关控制行为，向后兼容 v37.9.0
- `source="manual"` 命中永远 passthrough（v37.8.0 既定原则）
- `source="seal"` 不走裁剪（seal hit 的 text 默认空字符串，无可裁剪语义）
- 不破坏 v37.8.0 `HitOverrideStore` 唯一消费入口语义

### 2.2 非目标（YAGNI）

- 不引入像素级 OCR 字符精确裁剪（沿用字符权重比例估算 + 保守回退）
- 不为白名单条目增加「上下文模式 / 术语模式」二选一下拉框
- 不改黑名单语义（blacklist 仍然整条注入）
- 不改白名单条目本身的存储结构（仍是 `List[str]`）
- 不为每个 hit 携带「原 hit 引用」去关联 override store

---

## 3. 决策记录（澄清结论）

| # | 决策 | 选项 | 选择 |
|---|---|---|---|
| 1 | trim 行为范围 | 全命中源 / 仅 Word / 仅 PDF 文本 | **全命中源** (Word + PDF-text + PDF-OCR) |
| 2 | 保留片段矩形来源 | 字符权重估算 / 重 search_for / 像素级 | **字符权重估算** (复用 `_calculate_from_line` 权重函数) |
| 3 | trim 默认开关 | 默认开 / 默认关 / 不加开关 | **新增 `whitelist_trim_only`，默认 True** |
| 4 | 子 hit 与 override 关联 | 继承原 hit_id / 新 hit_id | **新 hit_id** (start/end 变化即新决策) |
| 5 | 多行 hit 处理 | 尽量裁剪 / 保守回退 | **保守回退** (整条剥掉) |
| 6 | 命名空间 | `redaction.whitelist_trim_only` (bool) | 同上 |
| 7 | 算法归属文件 | 嵌入 worker / 独立模块 | **独立模块** `secureredact/redaction/whitelist_split.py` |

---

## 4. 架构

```
┌─────────────────────────────────────────────────────────────┐
│                  config.json (新增 whitelist_trim_only)      │
│                            │                                 │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  BlackWhiteListStore.effective_whitelist()           │    │
│  │  _is_trim_only() → bool   (新)                       │    │
│  └─────────┬─────────────────────────┬─────────────────┘    │
│            │ whitelist items          │ trim_only flag       │
│            ▼                         ▼                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  secureredact/redaction/whitelist_split.py (新)      │   │
│  │  _split_text_by_whitelist(text, whitelist)           │   │
│  │    → List[(start_offset, end_offset, text_span)]    │   │
│  └─────────┬─────────────────────────┬─────────────────┘   │
│            │ spans                    │                     │
│            ▼                         │                     │
│  ┌─────────────────────────────────────────────┐           │
│  │  OCRWorker._apply_whitelist_filter  (改)    │           │
│  │  ├─ trim_only=False → 旧行为 (整条剥掉)     │           │
│  │  └─ trim_only=True  → 按 spans 生成子 hit   │           │
│  │       ├─ PDF-text / jieba / blacklist:        │           │
│  │       │  _sub_rect_for_text_span 估算矩形    │           │
│  │       └─ PDF-OCR:                              │           │
│  │          _resolve_text_from_rect + 同上算法   │           │
│  └─────────────────────────────────────────────┘           │
│  ┌─────────────────────────────────────────────┐           │
│  │  WordWorker._filter_whitelist (改)           │           │
│  │  ├─ trim_only=False → 旧行为 (整条剥掉)     │           │
│  │  └─ trim_only=True  → 按 spans 重生 start/end │           │
│  └─────────────────────────────────────────────┘           │
│                            │                                 │
│                            ▼                                 │
│              过滤后 hits (子 hit 已就位)                      │
│                            │                                 │
│                            ▼                                 │
│           HitOverrideStore.filtered_hits (v37.8.0 不动)      │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 数据模型

### 5.1 config.json schema 新增字段

```json
{
  "redaction": {
    "blacklist": ["盖章", "签字"],
    "whitelist": ["法定代表人", "12345"],
    "whitelist_trim_only": true,
    "overrides": { "permanent": [] }
  }
}
```

- **缺省**：`True` (v38 起默认开启)
- **类型校验**：非 bool → 回退 `True` + WARN 一次
- **向后兼容**：v37.9.0 config 升级时缺失字段 → 默认 `True`

### 5.2 BlackWhiteListStore 扩展

```python
class BlackWhiteListStore:
    # ... 既有方法不变

    def is_trim_only(self) -> bool:
        """v38: 读取 whitelist_trim_only 开关. 缺省 True, 非 bool 回退 True."""
        # 实现走 self._trim_only 缓存 + self._config.get("redaction.whitelist_trim_only", True)
        ...
```

不破坏既有方法签名。

### 5.3 核心算法：`_split_text_by_whitelist`

新文件 `secureredact/redaction/whitelist_split.py`：

```python
def _split_text_by_whitelist(
    text: str,
    whitelist: List[str],
) -> List[Tuple[int, int, str]]:
    """按白名单子串位置把 text 切成若干保留片段.

    Returns:
        [(start_offset, end_offset, text_span), ...]
        - offset 是 Python str 索引 (左闭右开)
        - 全段被覆盖 → []
        - 无白名单命中 → [(0, len(text), text)]

    Edge cases:
        - whitelist / text 为空 → [(0, len(text), text)] 或 []
        - 多条目命中同一区间 → 合并后取反
        - 单条目多次出现 → 多处都豁免
    """
```

算法步骤：

1. 遍历每条 wl，用 `text.find(wl, start)` 找到所有出现位置
2. 区间合并：sort + sweep，合并相交或相邻区间
3. 取反：从 `0` 扫到 `len(text)`，跳过合并区间，输出保留段
4. 空段过滤：`(start, end, "")` 不输出

---

## 6. 各通道集成

### 6.1 Word 通道（`secureredact/workers/word_worker.py`）

`_filter_whitelist` 改写：

```python
def _filter_whitelist(self, hits: list) -> list:
    """剥掉包含白名单子串的 hit; trim_only=True 时只剥子串本身."""
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
        # 旧行为: 整条剥掉
        if not trim_only:
            continue
        # 新行为: 每段保留片段生成新 hit
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

### 6.2 PDF 文本通道（`secureredact/workers/ocr_worker.py`）

新增静态工具 `_sub_rect_for_text_span`：

```python
@staticmethod
def _sub_rect_for_text_span(
    rect: Optional[QRectF],
    text: str,
    kept_start: int,
    kept_end: int,
) -> Optional[QRectF]:
    """字符权重比例估算 (CJK 1.0 / 其它 0.55).

    Returns:
        QRectF 或 None (退化 / 多行 → 走保守回退, 调用方丢弃该片段).
    """
    if rect is None or not text or kept_end <= kept_start:
        return None
    kept_span = text[kept_start:kept_end]
    if "\n" in kept_span:
        return None
    # 与 secureredact/workers/ocr_worker.py:_calculate_from_line 的 get_char_weight 对齐
    weights = [
        1.0 if (
            "一" <= c <= "鿿"   # CJK 统一汉字
            or "㐀" <= c <= "䶿"  # CJK 扩展 A
            or "豈" <= c <= "﫿"  # CJK 兼容汉字
        ) else 0.55  # 数字 / 英文 / 标点 / 其他
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

`_apply_whitelist_filter` 改写：

```python
def _apply_whitelist_filter(self, rects: list, page_idx: int) -> list:
    """剥掉包含白名单子串的 hit; trim_only=True 时只剥子串本身."""
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
            kept.append(hit)  # 解析失败 → 沿用旧行为保留
            continue
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
        # 旧行为: 整条剥掉
        if not trim_only:
            continue
        # 新行为: 每个保留片段生成子 hit
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

### 6.3 PDF 图片通道 OCR

走同一 `_apply_whitelist_filter` 路径。区别仅在 `hit.text` 来源：

- text-channel hit：`text` 由 `collect_text_pdf_hit_boxes` 填入
- image-channel OCR hit：`text=""`，本函数内通过 `_resolve_text_from_rect` 查回

trim 算法与 sub-rect 估算逻辑相同，无需额外分支。

---

## 7. 错误处理

| 场景 | 行为 |
|---|---|
| `redaction.whitelist_trim_only` 字段缺失 | 默认 `True` |
| 字段类型非 bool | 回退 `True` + WARN 一次（`logger.warning`） |
| 白名单为空 | filter 短路，行为与 v37.9.0 一致 |
| 白名单条目为空字符串 | 跳过该条目（store 已 sanitize） |
| 子 hit sub-rect 退化（宽 ≤ 0） | 该子 hit 丢弃，其余保留 |
| 保留片段含换行 `\n` | 该片段丢弃（保守回退） |
| OCR 通道解析文本失败（cache 未命中） | 该 hit 沿用旧行为保留（不剥不裁剪） |
| 跨多行 hit 命中白名单 | 保守回退：trim_only=True 也按整条剥掉 |
| `source="manual"` 命中 | 永远 passthrough |
| `source="seal"` 命中 | 永远 passthrough（text 为空，无可裁剪语义） |
| 多源混合 hit（blacklist 注入 + rule 同位置） | 按生成顺序处理；同位置的 whitelist 子串对两类都生效 |
| blacklist hit 含 whitelist 子串（如 bl_item="法定代表人张三" + wl=["法定代表人"]） | trim 语义生效：bl_item 被切成「张三」片段并保留为子 hit；用户黑名单语义被 trim 精细化。如不希望此行为，将 blacklist 条目收紧到精确 token |

---

## 8. 测试计划

### 8.1 `tests/unit/test_whitelist_split.py`（新文件）

- 空 text、空 whitelist → `[(0, 0, "")]`
- 空 text + 非空 whitelist → `[]`
- 单条 wl 命中中间（"aaaXbbb" + ["X"]）→ `[("aaa", 0, 3), ("bbb", 4, 7)]`
- 单条 wl 命中开头（"Xbbb" + ["X"]）→ `[("bbb", 1, 4)]`
- 单条 wl 命中结尾（"aaaX" + ["X"]）→ `[("aaa", 0, 3)]`
- 单条 wl 覆盖整段（"aaa" + ["aaa"]）→ `[]`
- 多条 wl 不重叠（"abc" + ["a", "c"]）→ `[("b", 1, 2)]`
- 多条 wl 重叠（"aaaa" + ["aa", "aaa"]）→ `[("a", 3, 4)]`
- 单条 wl 多处出现（"XaXaX" + ["X"]）→ `[("a", 1, 2), ("a", 3, 4)]`
- 单条 wl 部分重叠（"aaaa" + ["aa"]）→ `[("aa", 2, 4)]`（保留非覆盖段）

### 8.2 `tests/unit/test_whitelist_trim_only.py`（新文件）

- Word: `_filter_whitelist` 在 `trim_only=True` 下产出子 hits，start/end/text 正确
- Word: `trim_only=False` 时退化为整条剥掉
- Word: 旧「无 trim 必要」hit（text 不含 wl）原样保留
- Word: `manual` 源 passthrough 不变
- Word: 保留片段空字符串被过滤
- PDF文本通道: `_apply_whitelist_filter` 在 `trim_only=True` 下产出 sub-rect（验证 rect 是原 rect 的子集）
- PDF文本通道: sub-rect 退化（宽 ≤ 0）→ 该子 hit 丢弃
- PDF OCR 通道: 配 `_resolve_text_from_rect` mock 验证 sub-rect 计算
- PDF OCR 通道: 解析失败（cache 未命中）→ hit 原样保留
- 跨多行 hit: 保守回退为整条剥掉（`trim_only=True` 也走这条）
- `seal` 源: passthrough 不变

### 8.3 `tests/unit/test_whitelist_trim_only_config.py`（新文件）

- `whitelist_trim_only` 字段缺失 → 默认 `True`
- 字段为 `true` / `false` → 正确读取
- 字段非 bool（字符串 / int / null） → 回退 `True` + 触发 WARN
- v37.9.0 老 config 升级不报错

### 8.4 集成测试

`tests/unit/test_ocr_worker_whitelist.py` 追加用例：

- 「法定代表人：周超」文本 + wl=["法定代表人"] + `trim_only=True` → 产出 1 条 hit，rect 是 "：周超" 的子矩形，text="：周超"

`tests/unit/test_word_worker_black_white.py` 追加用例：

- 段落 "法定代表人：周超" + wl=["法定代表人"] + `trim_only=True` → 产出 1 条 match，start/end 对应「周超」子串

---

## 9. 兼容性 / 迁移

- v38 默认 `whitelist_trim_only=True`，开箱即用新行为
- v37.9.0 用户升级后想恢复旧行为：在 `config.json` 设 `"redaction.whitelist_trim_only": false`
- 永久 override / 人工干预机制不变：override store 按 hit_id 匹配；子 hit 的 hit_id 因 start/end 变化而不同，等价于「新决策独立关联 override」，符合 v37.8.0 唯一消费入口语义
- 全量回归命令（CLAUDE.md §Common Commands）增加：
  ```
  python3 -m unittest \
    tests.unit.test_whitelist_split \
    tests.unit.test_whitelist_trim_only \
    tests.unit.test_whitelist_trim_only_config \
    tests.unit.test_ocr_worker_whitelist \
    tests.unit.test_word_worker_black_white \
    -v
  ```

---

## 10. 实施清单（概要，供 writing-plans 拆解）

1. 新增 `secureredact/redaction/whitelist_split.py` 及 `_split_text_by_whitelist`
2. `BlackWhiteListStore` 增加 `is_trim_only()` 方法 + 配置读取
3. `OCRWorker._apply_whitelist_filter` 改写 + `_sub_rect_for_text_span` 静态方法
4. `WordWorker._filter_whitelist` 改写
5. `config.json` 模板更新（README / 注释说明）
6. `tests/unit/test_whitelist_split.py` 新建
7. `tests/unit/test_whitelist_trim_only.py` 新建
8. `tests/unit/test_whitelist_trim_only_config.py` 新建
9. 既有 `test_ocr_worker_whitelist.py` / `test_word_worker_black_white.py` 追加 trim 用例
10. CHANGELOG.md 增 v38.0.0 条目
11. CLAUDE.md §Common Commands 增加扩展回归命令

---

## 11. 风险与开放问题

| 风险 | 缓解 |
|---|---|
| 字符权重估算对英文 / 数字过宽或过窄 | 与现有 `_calculate_from_line` 同精度（用户已接受） |
| 多行 hit 退化为整条剥掉，可能放过敏感内容 | 保守策略，宁可放过不可错画；用户可后续在 Settings 中调规则拆分 |
| 子 hit 的 hit_id 与原 hit 不关联 override | trim 本身即是新决策，关联会破坏 override 语义 |
| OCR 通道解析文本失败时保留原 hit | 不会引入新错误；保留旧行为即可 |
| config.json 缺字段时默认 True 破坏老用户预期 | 文档说明 + WARN；可一键回退 |

无未决问题。

---

## 12. v38.0.1 hotfix（2026-08-19）

### 触发场景
用户在 `pdf/周强起诉状.pdf` 加 custom_keyword「盖章」+ 白名单「盖章」，期望「盖章」不被脱敏。但 v38.0.0 输出仍把「盖章」涂黑。

### 根因
1. image-channel custom_keyword「盖章」命中 OCR 行「3.被传唤人收到传票后，应在送达回证上**签名或者盖章**。」的「盖章」子串
2. `calculate_sub_rect` 返回只覆盖「盖章」位置的小 `QRectF`
3. `_resolve_text_from_rect` 用「小 rect center 落在大 token bbox 内」反查，**返回整条 token 文本**「签名或者盖章」
4. `_split_text_by_whitelist("签名或者盖章", ["盖章"])` → `[("签名或者", 0, 4), ("。", 6, 7)]`
5. `_sub_rect_for_text_span` 用**原小 rect**做字符权重比例切分 → 把「签名或者」错误地画到「盖章」位置 →「盖章」rect 被涂黑

### 修复
`OCRWorker._apply_whitelist_filter` 增加 `original_text_was_empty` 分支：image-channel / seal hit（原原 hit.text 为空）走 **v37.9.0 整条剥掉**行为，不做 trim。text-channel hit（原原 hit.text 非空）继续走 v38 trim。

### 锁定测试
`tests/unit/test_whitelist_trim_only.py::OCRFilterImageChannelEmptyTextTest`（3 用例）—— 删除/修改本测试即删除 hotfix 行为，**严禁**。

### 代码注释
- `OCRWorker._apply_whitelist_filter` 顶部 docstring 含完整 bug 上下文 + 锁定测试引用
- `OCRWorker._apply_whitelist_filter` 内 `original_text_was_empty` 分支含显式 `⚠️` 警告
- `OCRWorker._resolve_text_from_rect` 顶部 docstring 标注返回值可能是完整 token
- `OCRWorker._process_page` 中 image-channel / seal hit 的 `text=""` 处含显式 `⚠️` 警告

### 完整修复路径（未来工作）
让 `collect_image_block_ocr_hits` 返回 matched 子串（而非仅 rect），让 `hit.text` 携带精确 keyword 文本，避免 resolve 反查带来的歧义。这样 image-channel 也能正确 trim。**任何尝试完整修复的 PR 必须先保留本节列出的所有注释与锁定测试**，确保不破坏当前正确行为。