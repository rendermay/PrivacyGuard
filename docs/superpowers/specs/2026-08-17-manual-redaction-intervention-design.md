# 设计文档 — 自动脱敏结果的人工干预机制

**日期**: 2026-08-17
**作者**: Claude Code (brainstorming 阶段产出)
**目标版本**: v37.8.x(下一阶段)
**关联 Checkpoint**: 待实现 `cp33_<日期时间>`
**关联 Issue / 来源**: 用户脱敏验证 — jieba X3 集成后,出现「过度脱敏(常见词误判)」与「应脱未脱(漏检真实姓名)」两类问题,需要可逆的人工干预通道。

---

## 1. 目标与范围

为 SecureRedact 增加针对「自动脱敏命中结果」的人工干预能力,使最终用户在 jieba / OCR / 规则任一来源出现过脱或漏脱时,可以:

- **删除过度脱敏的遮挡**:对自动命中但不该脱的 hit 做「忽略」(本次会话或永久)
- **对未脱敏的位置进行人工遮挡**:复用现有手动画框(PDF) + 选词菜单(Word)

| 维度 | 选择 |
|------|------|
| 干预范围 | 所有自动脱敏来源(规则、OCR、jieba、印章) |
| 持久化 | 会话级 + 可选提升为永久 |
| 干预粒度 | 整条 hit |
| UI 入口 | 双入口 — 右键菜单(快) + 专用面板 dock(全) |
| 补脱入口 | 纯手动(已有画框 + 选词) |
| 数据标记 | 在 hit 上加 `source` 字段,平铺 |

---

## 2. 架构总览

**核心思想**:在 worker 产出 hit 与 UI 渲染之间插入一层「命中过滤与覆盖」,old 行为零变更(无 override 时等价)。

```
┌────────────────┐    hits(with source)    ┌──────────────────────┐
│ OCRWorker     │ ──────────────────────▶ │                      │
│  WordWorker    │                         │  HitOverrideStore    │
│  seal_detector │                         │   ├─ session: dict │
└────────────────┘                         │   └─ permanent: dict │
                                │
│ (config.json)  │
                                           └──────────┬───────────┘
                                                      │ filtered hits ▼
                              ┌──────────────────────────────────┐
                              │  渲染层 (canvas / webview)       │
                              │   ├─ 已忽略的 hit → 不画 / 不替换 │
                              │   ├─ 已确认的 hit → 加标记       │
                              │   └─ 正常 hit → 按现状渲染       │
                              └──────────────────────────────────┘ ▲
                                          │ 右键菜单 / 专用面板
                                          │ 用户操作 → store.ignore/confirm/promote
```

### 模块边界

- `secureredact/redaction/override_store.py`(新):`HitOverrideStore` 单例
- `secureredact/redaction/hit_ref.py`(新):`HitRef` 不可变标识 + `hit_id()` 工具
- `main.py`:
  - `MainWindow` 增加专用面板 dock
  - PDF `PDFCanvas` 增加右键菜单 + override 读取
  - Word `WebViewBridge` 新增 4 个槽函数
- 不修改 worker 代码(通过封装函数过滤 hits)

---

## 3. 数据模型

### 3.1 hit 增加 source 字段(平铺)

| 文件 | 现有结构 | 新结构 |
|------|---------|--------|
| `page_data[page]['ocr']` | `list[QRectF]` | `list[{"rect": QRectF, "source": "rule"\|"ocr"\|"jieba"\|"seal", "text": str, "rule_name": str}]` |
| `word_data[key]['ocr']` | `list[dict]` (已有 pattern/rule_name/start/end/text/replacement) | 在每个 dict 末尾加 `"source": "..."`,以及可选 `"confidence": float`(jieba 时为 0.7) |

`source` 取值:
- `rule`:用户自定义关键词或默认正则命中
- `ocr`:OCR 文本通道 + 图片通道命中
- `jieba`:姓名启发式识别
- `seal`:印章检测

### 3.2 override 不可变结构

```python
@dataclass(frozen=True)
class HitRef:
    doc_hash: str       # 当前文档 sha1 前 8 位
    location: str       # PDF: f"page_{i}";Word: f"paragraph_{idx}"
    start: int          # Word 字符位置;PDF 用 QRectF 转 (x,y,x2,y2)
    end: int
    text: str           # 用于人眼核对
    source: str         # 同上 @property
    def hit_id(self) -> str:
        return f"{self.doc_hash}|{self.location}|{self.start}|{self.end}|{self.source}"


@dataclass
class Override:
    ref: HitRef
    action: Literal["ignore", "confirm"]
    scope: Literal["session", "permanent"]
    promoted_at: str | None  # ISO 时间,仅 permanent 有
```

### 3.3 HitOverrideStore API

```python
class HitOverrideStore:
    """单例,通过 MainWindow._override_store 访问"""

    def ignore(self, ref: HitRef, *, scope: Literal["session","permanent"]="session") -> None
    def confirm(self, ref: HitRef, *, scope: Literal["session","permanent"]="session") -> None
    def promote(self, hit_id: str) -> None  # session → permanent
    def revert(self, hit_id: str) -> None    # 撤销任何 override
    def is_ignored(self, ref: HitRef) -> bool  # session OR permanent 命中
    def is_confirmed(self, ref: HitRef) -> bool
    def filtered_hits(self, hits: list, location: str) -> list  # 应用 override 过滤
    def iter_overrides(self, scope: str | None = None) -> Iterator[Override]
    def save_permanent(self) -> None  # 写 config.json
    def load_permanent(self, items: list) -> None  # 启动时从 config.json 读
```

### 3.4 兼容性保证

- 现有 `page_data[page]['manual']` 和 `word_data[key]['manual']` 维持原结构,无需变
- 仅 OCR 自动 hit 列表加 source 字段

---

## 4. PDF 端集成

### 4.1 OCRWorker 端 — 数据结构调整

- 当前 `page_result_signal.emit(i, rects)` 直接传 `list[QRectF]`
- 改为传 `list[dict]`(含 `rect` / `source` / `text` / `rule_name`)
- jieba 来源时 `text` 取 `extract_person_names` 的原词;OCR 来源时取实际匹配文本

### 4.2 MainWindow 接收层

- `_on_page_result(page_idx, hit_dicts)`:
  - 计算当前文档 `doc_hash`(用文件路径 + 大小 + mtime,缓存避免每次算)
  - 调 `self._override_store.filtered_hits(hit_dicts, f"page_{page_idx}")`
  - 把过滤后的 `rect` 喂给 `self.canvas.update_content(...)`
  - 未被过滤的 hit 仍存到 `self.page_data[page_idx]['ocr']` 用于侧栏展示

### 4.3 PDFCanvas(mousePressEvent)改造

- 右键 hit 后,弹 `QMenu`,菜单项:
  - **「忽略此条」** → `ignore(HitRef, scope='session')`
  - **「确认是敏感信息」** → `confirm(...)`(主要用于漏检后再画框补,然后 confirm 防止 OCR 重复命中)
  - **「提升到永久名单」** → 仅在已有 ignore/confirm 时可点
  - **「撤销」** → 仅在该 hit 已被覆盖时可点
- 状态刷新:菜单操作后 `self.update()` 重画 + 通过 `MainWindow` 通知侧栏 dock 刷新

### 4.4 不画框删除的兼容

- 现有右键删除手动框 / OCR 框逻辑保留 — 但语义变成「本次忽略」:
  - **手动框**(`rects_manual`):保留 `del` 行为(手动画的本就是用户表达,不进 override store)
  - **OCR 框**(`rects_ocr` 中 item):改为 `store.ignore()` + 不再直接 `del`,由下次 `_safe_canvas_update` 走 `filtered_hits` 自然不画
- 该差异保证「手动画框永远生效」+ 「OCR 框可恢复」两个语义并存

### 4.5 双入口之专用面板 dock

- 位置:主窗口底部,可隐藏(键盘 `Ctrl+Shift+H` 切换)
- 内容:三栏 table — `text / source / location / action / scope`
- 操作列:每行一个「撤销」按钮 + 一个「提升到永久」按钮(仅 session 行)
- 顶部摘要:`已忽略 N 条(永久 M) / 已确认 K 条(永久 L)`
- 选中文本源(过滤器):`all / rule / ocr / jieba / seal`
- 双击一行 → 跳转对应页 + 高亮闪烁该 hit

---

## 5. Word 端集成

### 5.1 WebViewBridge 新增 4 个槽函数

```python
@pyqtSlot(str, str, str, str)  # key, source, text, hit_id
def ignore_ocr_hit(self, key, source, text, hit_id): ...

@pyqtSlot(str, str, str, str)
def confirm_ocr_hit(self, key, source, text, hit_id): ...

@pyqtSlot(str)  # hit_id
def promote_override(self, hit_id): ...

@pyqtSlot(str)
def revert_override(self, hit_id): ...
```

均委托给 `self.main_window._override_store` + 触发 `self.main_window.render_word_preview()` 重渲染。

### 5.2 HTML 渲染层

- `render_word_preview()` 当前已对每个 word block 生成 `<mark class="ocr-hit" data-key="...">`
- 增加:
  - `data-source="rule|ocr|jieba"` 属性
  - `data-hit-id="..."` 属性
  - 对已 `ignore` 的 hit:**完全不渲染该 `<mark>`**(从 DOM 移除,文本恢复原字)
  - 对已 `confirm` 的 hit:加 `.ocr-hit--confirmed` CSS 类(加深背景色)

### 5.3 右键菜单(JS 端)

- 监听 `contextmenu` 在 `<mark class="ocr-hit">` 上时,弹出 `QMenu` 或 JS 自绘 menu(统一用 `QMenu` 经 WebChannel 回传)
- 菜单项同 PDF:**「忽略 / 确认 / 提升到永久 / 撤销」**
- 右键空白处仍走默认行为(浏览器菜单)

### 5.4 补脱入口(已有,无需变)

- 选中文字右键 → 已有的 `add_manual_redaction`(精确) / `add_manual_redaction_global`(全局) 保留
- 选中文字时若该文字已被某条 override 忽略,菜单项追加「取消忽略并加入确认」

### 5.5 双入口专用面板

- 共用 MainWindow 同一个 dock(`QDockWidget` 在 PDF/Word 模式都可见,内容根据当前模式切换)
- Word 模式时,行内容:`text / source / key / action / scope`
- 双击行 → 滚动 WebView 到对应 `data-key`,并临时加闪烁动画

---

## 6. 持久化与配置

### 6.1 config.json 新增键

```json
{
  "redaction": {
    "enable_name_recognition": false,
    "overrides": {
      "permanent": [
        {
          "hit_id": "<doc_hash>|paragraph_3|10|12|jieba",
          "doc_hash": "a1b2c3d4",
          "location": "paragraph_3",
          "start": 10,
          "end": 12,
          "text": "周强",
          "source": "jieba",
          "action": "ignore",
          "promoted_at": "2026-08-17T12:34:56"
        }
      ]
    }
  }
}
```

### 6.2 加载与保存时机

- 应用启动:从 `config.json` 读 `redaction.overrides.permanent`,调 `store.load_permanent(items)`
- 提升操作:`store.promote(hit_id)` → `save_permanent()` → 立即写 config.json(用 `SimpleConfig.save()`,现有机制)
- 应用退出:不主动 save(session 数据不落盘)

### 6.3 doc_hash 计算与命中策略

- 计算:`sha1(file_path + str(size) + str(mtime_ns)).hexdigest()[:8]`
- 同一文档(路径 + 大小 + mtime 完全一致) → doc_hash 相同 → permanent override 命中
- 文档被修改(mtime 变化) → doc_hash 不同 → permanent 失效但**不删除条目,仅不再命中**(避免误删用户反馈)
- 提供「清理失效 permanent overrides」按钮(设置中心 + dock 顶部菜单),按"创建于 90 天前 + 上次打开 30 天前"判定

### 6.4 默认行为

- 永久名单只接受 `ignore` / `confirm` 两种 action;**不持久化 `manual` 框**(manual 是空间位置,跨文档无意义)
- 同名同 source 的词跨文档共享 ignore(如"周强"在 3 个文档都被忽略 → permanent 1 条即可,**复用**)

### 6.5 写入幂等性

- 同 `hit_id` 已存在 permanent → 覆盖 `promoted_at` 但不重复写

---

## 7. 错误处理、边界与回退

### 7.1 异常路径

| 场景 | 处理 |
|------|------|
| config.json 损坏 /字段缺失 | `load_permanent` 捕获 `JSONDecodeError` + `KeyError`,静默回退到空名单,日志 warn |
| doc_hash 计算抛 `OSError`(文件被删) | `override_store.filtered_hits` 内 try/except → 不命中任何 permanent |
| WebViewBridge 槽函数收到未知 hit_id | 日志 warn + noop,不抛到 UI |
| 右键菜单弹出时 WebView 已销毁 | `try/except RuntimeError`,菜单不弹,不闪退 |
| 提升时 doc_hash 与启动时不一致(文件被替换) | 不写盘 + 弹 toast "文档已变更,无法提升" |

### 7.2 边界

- 同 `(text, source, location, start, end)` 完全相等时:session 优先级高于 permanent,但 UI 仍只显示一次
- `ignore` 与 `confirm` 互斥:对同一 hit 先 confirm 再 ignore → ignore 生效;反向同理(后写覆盖)
- 命中过滤顺序:`manual → (ocr ∩ confirm) − (ocr ∩ ignore)`,manual 永远不被 ignore(用户画框的优先级最高)

### 7.3 性能预算

- `filtered_hits` 单页 O(n),n 通常 < 200,实测 < 1ms
- `iter_overrides` 全量遍历 < 1000 条,UI 不卡顿
- doc_hash 启动时算一次,缓存到 `MainWindow._current_doc_hash`

### 7.4 回退开关

- 新增 `redaction.enable_hit_override` (默认 `True`) 配置键;关掉后 store 完全不读取,UI dock 也隐藏
- 与 `enable_name_recognition` 解耦 — jieba 关闭后,override 仍能对其他来源生效

### 7.5 不破坏现有回归

- 默认配置下,store 内 session 与 permanent 都为空,所有命中流不变 → `compileall` 与现有 114/114 测试应仍全过
- 新增测试仅:
  - `tests/unit/test_override_store.py`(核心逻辑,12 项左右)
  - `tests/unit/test_hit_ref.py`(标识计算,5 项左右)
  - `tests/unit/test_pdf_source_field.py`(数据结构调整,5 项)
  - `tests/unit/test_word_source_field.py`(5 项)
  - `tests/unit/test_bridge_override_slots.py`(5 项)
  - `tests/unit/test_overrides_persistence.py`(6 项)

---

## 8. 测试策略

### 8.1 单元测试(覆盖核心逻辑)

| 文件 | 测试要点 | 预估条数 |
|------|---------|---------|
| `tests/unit/test_hit_ref.py` | hit_id 计算稳定性;同输入同输出;字段缺失抛错 | 5 |
| `tests/unit/test_override_store.py` | ignore/confirm/revert/promote 全路径;session 永久双层;filtered_hits 过滤正确性;is_ignored 优先级 | 12 |
| `tests/unit/test_pdf_source_field.py` | `page_data` 结构;`filtered_hits` 集成;空名单等价旧行为 | 5 |
| `tests/unit/test_word_source_field.py` | `word_data` 加 source;render 跳过 ignored;confirm 显示 confirm 类 | 5 |
| `tests/unit/test_bridge_override_slots.py` | 4 个槽函数;未知 hit_id 容错 | 5 |
| `tests/unit/test_overrides_persistence.py` | config.json 读写;损坏回退;同名复用 | 6 |

总计 ~38 条新测试,基线从 114 → 152。

### 8.2 回归测试(向后兼容保证)

- 现有 12 个 test_*.py 全保持绿色
- `compileall main.py secureredact tests` 无误

### 8.3 集成 / E2E(可选,后续 Wave)

- 不在本次实现范围 — 仅人工 smoke:打开真实 PDF,右键忽略 → 重新扫描不命中

### 8.4 测试桩

- `doc_hash` 测试时用 `mock.patch("builtins.open", ...)` 或临时 monkeypatch — 不引入新依赖

---

## 9. 实施 Wave 划分

| Wave | 范围 | 估行 |
|------|------|------|
| **W1** | `HitRef` + `HitOverrideStore` + 单元测试 | ~250 |
| **W2** | PDF 数据结构调整 + canvas 右键菜单 + filtered_hits 接入 + **PDF 导出路径同步 store** | ~350 |
| **W3** | Word 数据结构调整 + WebViewBridge 4 槽 + HTML 渲染层 + **Word 导出路径同步 store** | ~320 |
| **W4** | 专用面板 dock + 持久化 + 设置中心清理按钮 | ~250 |
| **W5** | 全量回归 + 文档同步 + 性能验证 | ~100 |

总估:约 1180 行新增/修改,跨 4-5 个 Wave。

---

## 10. 不修改清单(边界守护)

- `secureredact/__init__.py`(保持现有懒加载)
- `secureredact/workers/__init__.py`
- `secureredact/pii/validators/*`
- `secureredact/ocr/manager.py`、`rapidocr.py`
- `theme.py`、`version.txt`、`packaging/**`(直到本阶段通过真机 smoke)

---

## 11. 风险与回退

| # | 风险 | 触发条件 | 回退方案 |
|---|------|---------|----------|
| R1 | hit 数据结构调整破坏现有 worker 测试 | Wave 2/3 后 `test_pdf_text_hit_dedup` 等失败 | 保留 `QRectF` 直传路径,新增可选 `list[dict]` 路径,worker 默认仍发 QRectF 列表 |
| R2 | override 写盘损坏 config.json | `save_permanent` 抛 `OSError` | 写盘前 `tmp + rename`,失败时保留旧文件 |
| R3 | WebView 销毁导致右键菜单闪退 | 应用关闭途中点击 | `try/except RuntimeError` + 槽函数检查 `_webview` 有效性 |
| R4 | doc_hash 命中率低,用户反馈"为什么我的忽略不生效" | mtime 被压缩软件改写 | 文档头部信息(标题)进 doc_hash 二次校验 |
| R5 | permanent 累积过千条,UI 卡顿 | 长期使用 | dock 顶部"按 source 筛选" + 默认按 `text` 排序 |
| R6 | ignore 后导出仍残留 | filtered_hits 仅影响预览,导出路径未同步 | **Wave 2 在 `_export_pdf_with_hits` 等导出函数处对 hit 列表过一次 `filtered_hits`;Wave 3 在 `_export_word_with_replacements` 同理**,覆盖 PDF 与 Word 两端导出路径 |