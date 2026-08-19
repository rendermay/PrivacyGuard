# 黑名单 / 白名单 — 设计 spec

**作者**: Claude (brainstorming 流程产物)
**日期**: 2026-08-18
**项目**: SecureRedact 信息脱敏助手
**目标版本**: v37.9.0
**状态**: 设计中 (待用户审阅)

---

## 1. 背景与动机

v37.7.x 启用了中文姓名启发式识别（jieba），但带来两类**误伤**：

1. **jieba 误标 `nr`**：jieba 把"盖章"、"吉铁"等非人名词误标为人名 (`flag='nr'`)，配合 `SURNAME_SET` 命中后被脱敏。
2. **用户主动想保留的文本**被默认规则误伤（如某些公开电话号码、内部代号）。

仅靠 `EXCLUDE_WORDS` 黑名单修补 jieba 误伤是**治标**：jieba 词典会持续产生新的误标。需要给用户一个**主动控制**机制。

---

## 2. 目标与非目标

### 2.1 目标

- 提供"黑名单"：用户列出的文字**强制脱敏**，即使没有规则匹配。
- 提供"白名单"：用户列出的文字**永不脱敏**，即使被规则/jieba/OCR/seal 命中。
- 黑/白名单同时作用于 PDF（OCRWorker）和 Word（WordWorker）。
- 支持永久层（config.json 跨启动保留）+ 会话层（内存，本次启动有效）。
- 严格遵循 v37.8.0 既定原则：人工框选（`source="manual"`）永不被任何机制覆盖。

### 2.2 非目标（YAGNI）

- 黑/白名单条目的启用/禁用开关
- import/export、模板、跨文档共享
- 黑/白名单命中统计与日志
- 高级匹配模式（regex / word-boundary），本期仅 substring
- 改动 `HitOverrideStore` 的现有"唯一消费入口"语义（whiteList 在 worker 内过滤后仍走 `filtered_hits`）

---

## 3. 决策记录（澄清结论）

| # | 决策 | 选项 | 选择 |
|---|---|---|---|
| 1 | 白名单优先级 | 绝对优先 / 仅 jieba/OCR / 按条 force | **绝对优先** |
| 2 | 匹配模式 | 子串 / 完整词 / 三模式可选 | **子串** |
| 3 | 适用范围 | PDF / Word / 两者 | **两者** |
| 4 | 黑名单与 custom_keywords 关系 | 复用+重组 / 完全独立 / 只加白名单 | **完全独立**（force-add） |
| 5 | 生命周期 | 仅永久 / 仅会话 / 双层 | **永久 + 会话双层** |
| 6 | UI 位置 | 设置中心面板 / Tab / 独立 Dialog | **独立 Tab** |
| 7 | 架构约束 | 唯一消费入口 | **不强制**（方案 A 把过滤逻辑放在 worker 内）|

---

## 4. 架构

```
┌─────────────────────────────────────────────────────────────┐
│                       SettingsDialog                          │
│   [Tab: 自定义关键词]  [Tab: 黑名单★]  [Tab: 白名单★]          │
└────────────────────┬────────────────────────────────────────┘
                     │ 保存时回写到 config.json
                     ▼
       ┌─────────────────────────────┐
       │  redaction.blacklist /      │   永久层 (config.json)
       │  redaction.whitelist        │
       └─────────────────────────────┘
                     │ 启动时加载
                     ▼
       ┌─────────────────────────────┐
       │  BlackWhiteListStore 单例   │   会话层 (内存)
       │  add/remove/match           │
       └────────┬─────────────┬──────┘
                │ blacklist   │ whitelist
                ▼             ▼
  ┌─────────────────────────────────────┐
  │  OCRWorker._process_page            │   Worker 层
  │  ├─ 1. OCR + 规则匹配 (现有)         │
  │  ├─ 2. whitelist 过滤 (新)           │   ← 剥掉 hits 中包含白名单的
  │  ├─ 3. blacklist 注入 (新)          │   ← 扫描 image 通道 OCR tokens
  │  └─ 4. seal 检测 (现有)              │
  └─────────────────────────────────────┘
  ┌─────────────────────────────────────┐
  │  WordWorker._run                    │
  │  ├─ 1. 段落扫描 + 规则匹配 (现有)     │
  │  ├─ 2. whitelist 过滤 (新)           │
  │  └─ 3. blacklist 注入 (新)          │   ← 段落文本内 str.find
  └─────────────────────────────────────┘
                │ 过滤后 hits
                ▼
       ┌─────────────────────────────┐
       │  HitOverrideStore (现有)     │   唯一消费入口 (v37.8.0)
       └─────────────────────────────┘
```

---

## 5. 数据模型

### 5.1 config.json schema

```json
{
  "redaction": {
    "blacklist": ["盖章", "签字"],
    "whitelist": ["12345", "hotline"],
    "overrides": { "permanent": [] }
  }
}
```

- **缺省**：`[]`，行为与 v37.8.0 完全一致
- **类型校验**：若字段存在但不是 `list[str]`，回退到 `[]` 并打 WARN 一次
- **空值过滤**：加载时过滤掉空字符串 / 纯空格

### 5.2 BlackWhiteListStore 单例

```
路径: secureredact/redaction/black_white_list_store.py
模式: 与 override_store.py 同款 (单例 + threading.Lock)
```

字段：
- `_permanent_blacklist: List[str]`
- `_permanent_whitelist: List[str]`
- `_session_blacklist: List[str]`
- `_session_whitelist: List[str]`

方法：
- `instance() -> BlackWhiteListStore`
- `effective_blacklist() -> List[str]` （永久+会话合并去重）
- `effective_whitelist() -> List[str]`
- `add_session_black(item: str)` / `remove_session_black(item: str)`
- `add_session_white(item: str)` / `remove_session_white(item: str)`
- `save_permanent(black: List[str], white: List[str])` （原子写 config.json）

### 5.3 hit dict 扩展

新增合法 `source` 值：`"blacklist"`。`HitOverrideStore.filtered_hits` 无需改动（已支持任意 source）。

---

## 6. Worker 集成

### 6.1 OCRWorker

插入点：`ocr_worker.py:_process_page`

```python
def _process_page(self, page, page_idx, *, ocr_engine, scan_scale):
    rects = []
    # ... 现有步骤（OCR + 规则 + jieba 注入）...

    # 新增：白名单过滤（先剥，避免后续注入被立刻剥）
    rects = self._apply_whitelist_filter(rects, page_idx)

    # 新增：黑名单注入
    blacklist = BlackWhiteListStore.instance().effective_blacklist()
    if blacklist:
        rects.extend(self._collect_blacklist_hits(page, page_idx, blacklist, scan_scale))

    # ... 现有印章检测 ...
    return rects
```

**`_apply_whitelist_filter`**：
- 对每个 hit，若 `source == "manual"` 保留。
- 否则取 `hit["text"]`；若为空则用 `_resolve_text_from_rect(hit["rect"], page_idx)` 查回。
- 若任一白名单条目是 text 的子串 → 剥掉。

**`_resolve_text_from_rect`**：从该页已缓存的"rect → text"映射（image 通道 OCR 阶段构造）查回原文。

**`_collect_blacklist_hits`**：
- 遍历 `image_clip_rects`，每个 clip 内 OCR 一遍得 `(text, box)` token 列表。
- 对每条 blacklist 条目，对每 token，若条目在 token 文本中 → 用 `calculate_sub_rect` 构造 QRectF。
- 命中 dict：`{"rect": ..., "source": "blacklist", "text": <条目原文>, "rule_name": "黑名单:<条目>"}`。
- 调用 `_dedupe_overlapping(hits)` 合并同一条目跨多个 token 的重叠矩形（合并为最大外接矩形）。

### 6.2 WordWorker

插入点：`word_worker.py:_run`，每个段落处理后追加两段：

```python
hits_for_para = self._filter_whitelist(hits_for_para)
blacklist = BlackWhiteListStore.instance().effective_blacklist()
for bl_item in blacklist:
    start = 0
    while True:
        idx = text.find(bl_item, start)
        if idx < 0: break
        hits_for_para.append({
            "start": idx, "end": idx + len(bl_item),
            "source": "blacklist", "text": bl_item,
            "rule_name": f"黑名单:{bl_item}",
        })
        start = idx + len(bl_item)
```

---

## 7. UI

### 7.1 SettingsDialog 新增 Tab

- **Tab「黑名单」**：上方持久层 QTextEdit（多行，每行一条），下方会话层 QListWidget + [+] [-] 按钮。
- **Tab「白名单」**：同构。
- 顶部说明：「条目按子串匹配；白名单优先级高于所有规则；blacklist/whitelist 同条目时白名单赢」。
- 保存：QTextEdit 内容变化时调用 `BlackWhiteListStore.save_permanent(...)` 原子写。

### 7.2 行为契约

- Tab 切换时，`BlackWhiteListStore` 实时反映状态，不依赖磁盘往返。
- 空文本 / 纯空格 / 重复条目：保存前去重 + 过滤。

---

## 8. 错误处理与边界

| 场景 | 行为 |
|---|---|
| config.json blacklist/whitelist 字段缺失 | 回退 `[]`，无 WARN |
| 字段类型错误 | 回退 `[]`，WARN 一次 |
| 空字符串 / 纯空格条目 | 加载时过滤 |
| 极长条目（>100 字符） | 允许，UI 黄色提示 |
| blacklist 与 whitelist 同条目 | 白名单赢，该 blacklist 条目**无效**（不报错） |
| UI 重复输入 | 去重保序 |
| `instance()` 多线程并发 | `threading.Lock` 保护 |
| OCRWorker blacklist 注入时 OCR 失败 | 静默跳过 |
| WordWorker 段落 `text is None` | 视为空字符串，跳过 |
| 印章检测 + blacklist 冲突 | 两者独立生成 hit（不合并、不去重——印章是区域，黑名单是子串，语义不同） |

---

## 9. 测试覆盖

### 9.1 单元测试

- `tests/unit/test_black_white_list_store.py`
  1. 单例 + 线程安全
  2. 永久层加载（正常 / 字段缺失 / 字段类型错误）
  3. 会话层 add/remove 与 effective 列表去重保序
  4. 同条目 blacklist + whitelist → 永久白名单赢
  5. `save_permanent` 原子写（tmp + rename）
- `tests/unit/test_ocr_worker_blacklist.py`
  1. blacklist 注入：单/多 token 命中 / 跨 clip 命中
  2. `_dedupe_overlapping` 合并
  3. blacklist 空时不注入
  4. text 字段 = 条目原文
- `tests/unit/test_ocr_worker_whitelist.py`
  1. whitelist 命中 → 剥掉 rule/jieba/ocr/seal 通道
  2. manual 来源永不被剥
  3. text 为空（OCR 通道）→ `_resolve_text_from_rect` 兜底
  4. blacklist + whitelist 同条目 → 该 hit 不出现
- `tests/unit/test_word_worker_black_white.py`
  1. 段落内 blacklist 多次匹配（重叠窗口）
  2. 段落内 whitelist 过滤
  3. 段落 text 为 None

### 9.2 集成测试

1. `pdf/周强起诉状_GUI脱敏.pdf` + `blacklist=["盖章","吉铁"]` → 重跑 OCR：
   - page 0 "签名或者盖章。" 处新增 blacklist hit
   - page 1 "吉林铁道职业技术大学；住所地：…吉铁东路 1 号" 中"吉铁"被强制脱敏
2. 同 PDF + `whitelist=["盖章"]` → 重跑 OCR：page 0 "盖章" 不再脱敏（即使 jieba 误标 nr 也不脱敏）

---

## 10. 不在范围

- import/export、模板、跨文档共享
- regex / word-boundary 等高级匹配模式
- 黑/白名单命中统计与日志
- 改动 `HitOverrideStore` 的"唯一消费入口"语义
- 改动 `enable_name_recognition` / `EXCLUDE_WORDS`（X3 方案的独立改进）

---

## 11. 实施计划指针

完整 PLAN.md 在 writing-plans 阶段产出。本 spec 仅描述 WHAT，不描述 HOW 的步骤切分。
