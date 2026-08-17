# Phase: 自动脱敏命中的人工干预机制 (Hit Override)

**目标**：在不破坏现有脱敏链路的前提下，为自动命中结果提供「忽略 / 确认」的人工干预通道，并支持会话级与永久级两层作用域。

**创建日期**：2026-08-17
**作者**：Claude Code (Phase)
**关联 Checkpoint**：`v37_8_manual_intervention_cp33_<日期时间>`
**关联版本**：v37.7.6 → v37.8.0
**关联 Issue / 来源**：自动脱敏在法律文书等场景存在误命中与漏命中，用户需要在预览阶段直接修正结果，而不是反复调规则。

---

## 背景

v37.7.6 之前，自动命中（正则 / jieba 姓名 / 关键词 / 图片 OCR）的结果对用户是**只读**的：

- 误命中只能靠改规则或改配置回避，代价高且影响全局
- 漏命中只能改用手动框选，与自动结果无法统一管理
- 命中结果无稳定标识，跨会话不可复用

本阶段引入 `HitRef` + `HitOverrideStore`：

- 给每条自动命中一个**可复现的不可变标识** `hit_id`
- 用户对某条命中的判断（`ignore` / `confirm`）存为 `Override`
- 所有消费端统一经 `filtered_hits()` 应用 override，杜绝多点判定漂移

---

## Wave 划分

| Wave | 目标 | 文件清单 | 完成判据 |
|------|------|---------|---------|
| **1** | 核心层：HitRef + doc_hash + HitOverrideStore | 新增 `privacyguard/redaction/{hit_ref,doc_hash,override_store}.py` + 3 个测试模块 | 20/20 测试通过 ✅ |
| **2** | 配置默认键 | `config.json` + `main.py:SimpleConfig` + `test_override_config_defaults.py` | 2/2 通过；旧配置自动补齐 ✅ |
| **3** | PDF 通道接入 | `privacyguard/workers/ocr_worker.py` + `main.py:MainWindow` + 画布右键菜单 | 6/6 通过；payload 改 `list[dict]` ✅ |
| **4** | Word 通道接入 | `privacyguard/workers/word_worker.py` + `main.py:WebViewBridge` + 预览 JS | 7/7 通过 ✅ |
| **5** | dock + 持久化 + 文档 + 全量回归 | 干预 dock、`SettingsDialog`、`version.txt`、`CHANGELOG.md`、本文档、`CLAUDE.md` | 3/3 通过 + 全量回归对齐 ✅ |

---

## Wave 2 — 数据模型与配置详细

### 2.1 数据模型

```python
@dataclass(frozen=True)
class HitRef:
    doc_hash: str   # compute_doc_hash(file_path) → 8 位十六进制
    location: str   # PDF: 页码；Word: block key
    start: int
    end: int
    source: str     # regex / jieba / keyword / image_ocr / manual
    text: str

    @property
    def hit_id(self) -> str:
        return f"{self.doc_hash}|{self.location}|{self.start}|{self.end}|{self.source}"


@dataclass
class Override:
    hit_id: str
    action: str     # "ignore" | "confirm"
    scope: str      # "session" | "permanent"
    created_at: str # ISO8601
    ref: HitRef | None
```

### 2.2 doc_hash 语义

`compute_doc_hash(file_path)` 取 **绝对路径 + 文件字节数 + mtime** 做摘要，截断为 8 位。

含 mtime 的取舍：文档被编辑后 hash 自然变化，旧 override 失效，避免偏移后错位命中。代价是「同一文档另存后 override 不复用」，属可接受损失。

### 2.3 配置键

```json
"redaction": {
  "enable_hit_override": true,
  "overrides": { "permanent": [] }
}
```

- `enable_hit_override` 默认 `true`；关闭时 `filtered_hits()` 直通返回
- `overrides.permanent` 为 `dump_permanent()` 的序列化列表
- `SimpleConfig` 读取旧 `config.json` 时自动补齐两个新键

---

## Wave 3 — PDF 通道详细

### 3.1 目标

`OCRWorker.page_result_signal` 的 payload 由 `list[QRectF]` 升级为 `list[dict]`，携带 override 判定所需的全部字段。

### 3.2 payload 结构

```python
{
    "rect": QRectF(...),
    "source": "regex",   # regex / jieba / keyword / image_ocr
    "text": "周强",
    "start": 128,
    "end": 130,
}
```

### 3.3 消费端约定

- MainWindow 收到 payload 后统一调用
  `HitOverrideStore.instance().filtered_hits(hits, location=str(page_num), doc_hash=self._doc_hash)`
- 画布右键菜单动作：忽略 / 确认 / 撤销 / 提升为永久
- `manual` 来源命中**不参与过滤**（人工框选是显式意图）

### 3.4 不修改清单

- `privacyguard/__init__.py`
- `privacyguard/workers/__init__.py`
- `privacyguard/pii/validators/*`
- `theme.py`
- `packaging/**`（待真机 smoke 后再动）

---

## Wave 4 — Word 通道详细

- `WordWorker` 命中 dict 补 `source` / `start` / `end`
- `WebViewBridge` 新增 4 个 `pyqtSlot`，签名统一 `(key, source, text, hit_id)`：
  - `ignore_ocr_hit` / `confirm_ocr_hit` / `revert_ocr_hit` / `promote_ocr_hit`
- 预览 JS：高亮节点上挂 `data-hit-id`，右键菜单调用上述槽；`confirmed` / `ignored` 两套 CSS 视觉区分
- 右侧 replaced panel 同样经 `filtered_hits()`，与左侧判定一致

---

## 风险与回退

| # | 风险 | 触发条件 | 回退方案 |
|---|------|---------|----------|
| R1 | override 判定散落多个 Worker 导致漂移 | 新增消费端绕过 `filtered_hits()` | 保持 `filtered_hits()` 为唯一入口；review 时 grep 消费点 |
| R2 | `save_permanent` 半写坏 config | 保存过程中进程退出 | 已用 tmp + rename 原子写 |
| R3 | `load_permanent` 读到损坏条目抛异常 | 手改 config.json / 旧格式 | 逐条 try/except，坏条目跳过并告警，不阻断启动 |
| R4 | 文档改动后 override 错位命中 | 用户编辑源文档后重新脱敏 | `doc_hash` 已含 mtime，旧 override 自然失效 |
| R5 | permanent override 无限增长 | 长期使用累积 | `clean_stale_permanent(max_age_days=30)` + 设置中心清理按钮 |
| R6 | dock 条目过多难以定位 | 大文档批量干预 | dock 顶部按 `scope` / `action` 筛选 |
| R7 | 旧 payload 调用点漏迁移 | `list[QRectF]` → `list[dict]` 破坏性变更 | 全量回归 + `test_ocr_worker_source_field` / `test_pdf_source_field` 守护 |
| R8 | 关闭开关后行为不等价 | `enable_hit_override=false` | `filtered_hits()` 直通返回原列表 |

**全局回退**：删除 `config.json` 中 `redaction.overrides.permanent` 内容并设 `enable_hit_override=false`，即可恢复 v37.7.6 行为；代码级回退见 `rollback_journal.md` 的 cp33 条目。

---

## 进度跟踪

| Wave | 状态 | 完成日期 |
|------|------|---------|
| Wave 1: 核心层 (HitRef / doc_hash / HitOverrideStore) | ✅ | 2026-08-17 |
| Wave 2: 配置默认键 | ✅ | 2026-08-17 |
| Wave 3: PDF 通道接入 | ✅ | 2026-08-17 |
| Wave 4: Word 通道接入 | ✅ | 2026-08-17 |
| Wave 5: dock + 持久化 + 文档 + 全量回归 | ✅ | 2026-08-17 |

---

## 测试基线

| 测试模块 | 用例数 | 覆盖 |
|---------|-------|------|
| `tests/unit/test_hit_ref.py` | 5 | HitRef 不可变性 / hit_id 格式 / Override 校验 |
| `tests/unit/test_doc_hash.py` | 4 | 长度 8 / 稳定性 / mtime 敏感 / 缺失文件容错 |
| `tests/unit/test_override_store.py` | 11 | 单例 / ignore / confirm / revert / promote / filtered_hits / dump / load 损坏容错 |
| `tests/unit/test_override_config_defaults.py` | 2 | 新键默认值 / 旧配置补齐 |
| `tests/unit/test_ocr_worker_source_field.py` | 3 | payload dict 结构 + source 标签 |
| `tests/unit/test_pdf_source_field.py` | 3 | PDF 消费端接 filtered_hits |
| `tests/unit/test_word_source_field.py` | 1 | Word 命中 source 字段 |
| `tests/unit/test_bridge_override_slots.py` | 6 | 4 槽签名 + 坏 hit_id 容错 |
| `tests/unit/test_overrides_persistence.py` | 3 | 启动加载 / 退出保存 / 失效清理 |
| **合计新增** | **38** | |

**全量回归**：`162` 项，`160 PASS`。

**既有失败（非本阶段引入）**：`tests.unit.test_config_alignment` 的
`test_scan_default_level_matches` 与 `test_simple_config_reads_config_json_values`
—— `config.json` 中 `redaction.scan.default_level` 为 `2.0`，测试期望 `1.5`，自 v37.7.6 起存在。

---

## 最终验收

- **基线 124 → 162 测试**（+38：Wave 1 20 + Wave 2 2 + Wave 3 6 + Wave 4 7 + Wave 5 3）
- **文档同步**：`version.txt` / `CHANGELOG.md` / `STATUS.md` / `DEV_LOG.md` / `CLAUDE.md` / 本文档
- **Phase Checkpoint 命名**：`v37_8_manual_intervention_cp33_20260817`
- **无 override 时与 v37.7.6 行为完全一致**（向后兼容）
- **待办**：真机截图驱动的干预 dock 交互抛光；`packaging/**` 待真机 smoke 后同步
