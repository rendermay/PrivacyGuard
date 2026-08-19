# Phase: 中文姓名启发式识别 (jieba X3) 集成

**目标**：在不破坏现有架构的前提下，为 SecureRedact 增加可选的中文人名启发式识别能力。

**创建日期**：2026-08-15
**作者**：Claude Code (Phase)
**关联 Checkpoint**：`v37.7.x_name_recognition_x3_cp32_<日期时间>`
**关联 Issue / 来源**：用户脱敏验证 — 起诉状《周强起诉状_GUI模式脱敏.pdf》分析指出原告"周强"在原告段/著作权人段/签名段三处应脱敏却未脱敏。

---

## 背景

`main.py` 中现有 `DEFAULT_RULES` 正则规则集无法识别正文中的"姓名+汉字"组合（如"著作权人周强在贵州省版权局…"），只能命中"标签+姓名+标点"模板。

子 agent 已完成 B 方案 (jieba) 可行性研究，推荐 X3 路线：
- jieba 0.42.1 (已安装) + 姓氏表准入 + 黑名单过滤 + 上下文加权
- 默认 OFF (新增 `enable_name_recognition: bool = False`)
- PyInstaller 影响：+42MB (仅启用时)

---

## Wave 划分

| Wave | 目标 | 文件清单 | 完成判据 |
|------|------|---------|---------|
| **0** | GSD 规划 | (本文档) | 文档落盘 |
| **1** | 核心识别器 + 单测 | 新增 `secureredact/pii/name_recognizer.py` + `tests/unit/test_name_recognizer.py` | 17/17 测试通过 + 全量回归 102/102 ✅ |
| **2** | Worker 接入 (本阶段) | 修改 `secureredact/workers/ocr_worker.py` + `word_worker.py` + `main.py` 兼容层 | 默认 OFF 时 102/102 全过；新增 worker mock 测试 PASS |
| **3** | UI + 持久化 + spec + requirements | 修改 `main.py` SettingsDialog + `config.json` + `SecureRedact_verify.spec` + `requirements.txt` | UI smoke 通过 + 配置 round-trip 通过 + spec 语法编译通过 |
| **4** | 全量回归 + 性能 + 文档 | 修改 `CHANGELOG.md` / `docs/current/DEV_LOG.md` / `CLAUDE.md` | ≥102/102 PASS + 性能预算达成 + 三处文档同步 |

---

## Wave 2 — Worker 接入详细计划

### 2.1 目标
在 `OCRWorker.__init__` 与 `WordWorker.__init__` 增加 `enable_name_recognition: bool = False` 参数。
当且仅当 `True` 时调用 `extract_person_names()`，把识别的姓名经 `re.escape()` 后追加到 `all_patterns`。

### 2.2 文件清单

#### 修改
- `secureredact/workers/ocr_worker.py`
  - 行 47–49 `OCRWorker.__init__` 增加 `enable_name_recognition: bool = False` 参数
  - 行 387 之前：仅当 `self.enable_name_recognition` 为真时追加识别人名
- `secureredact/workers/word_worker.py`
  - 行 24 `WordWorker.__init__` 增加 `enable_name_recognition: bool = False` 参数
  - 行 111 之前：同上

#### 不修改
- `secureredact/__init__.py`
- `secureredact/workers/__init__.py`
- `config.json`

### 2.3 关键约束

- **默认 OFF 等价现状**：当 `enable_name_recognition=False` 时，`all_patterns` 与现状完全一致；调用点必须用 `if not self.enable_name_recognition: return` 短路
- **去重**：识别结果对 `self.rules + self.custom_keywords` 已存在的 pattern 去重
- **PyMuPDF 坐标语义**：命中仍走现有 `calculate_sub_rect` 行级计算
- **OCRWorker 文本通道**：`collect_text_pdf_hit_boxes` 接受任意 pattern 列表
- **OCRWorker 图片通道**：`collect_image_block_ocr_hits` 通过 `re.finditer` 命中
- **WordWorker**：`re.finditer(pattern, text, ...)` 注入即生效

### 2.4 风险与回退

| 风险 | 触发条件 | 回退方案 |
|------|---------|----------|
| 识别的人名与 `custom_keywords` 重复导致双倍 match | `extract_person_names` 返回值与已有关键词重叠 | 在追加前对 `(self.custom_keywords + self.rules)` 做 set 去重 |
| OCRWorker 字符级坐标精度不足 | 中文姓名常 2-3 字，行级 `_calculate_from_line` 字符权重可能偏移 | 暂保持现状，写入 DEV_LOG 作为已知精度边界 |
| 识别在大文档中过慢 | 性能基准 Wave 4 验证失败 | 引入「文本长度阈值」（< 50字符跳过）+「页面 hash 缓存」 |
| jieba 导入抛异常 | `import jieba.posseg` 失败 | 识别器内部 try/except 已捕获；worker 调用点不抛异常 |

### 2.5 验证命令

```bash
cd G:/Project/SecureRedact
python -m compileall -q secureredact/workers main.py
python -m unittest tests.unit.test_mixed_pdf_ocr tests.unit.test_ocr_api tests.unit.test_word_replace_rules tests.unit.test_redaction_rule_patterns tests.unit.test_name_recognizer -v
python -m unittest discover tests/unit -v   # 全量回归
```

### 2.6 完成判据

- `compileall` 无错误
- 全量回归 ≥102/102 通过 (默认 OFF 等价不变性)
- 新增 worker 测试 PASS (如果引入)

---

## 全局风险 (跨 Wave)

| # | 风险 | 触发条件 | 回退方案 |
|---|------|---------|----------|
| R1 | jieba 安装失败 / 词典缺失 | `import jieba` 抛 `ImportError` | `name_recognizer.py` 内 try/except 返回 `[]`；Worker 启动不抛 |
| R2 | 默认 OFF 与现状漂移 | Wave 2 后出现新失败 | `if not self.enable_name_recognition: return` 短路 |
| R3 | 姓名识别性能拖累 OCR | Wave 4 性能基准 > 1s/页 | 「文本长度阈值」+「页面 hash 缓存」 |
| R4 | PyInstaller 打包后 jieba 不可用 | Wave 3 spec 测试失败 | `runtime_hooks` 注入 `resource_path` |
| R5 | 人名误命中 | 真实 PDF 测试发现 | 扩充 `EXCLUDE_WORDS` |
| R6 | OCR 行级坐标精度不足 | 用户反馈识别到人名但高亮位置偏移 | 调整 `_calculate_from_line` CJK 字符权重 |
| R7 | jieba 升级破坏 API | jieba 0.43+ 改 `posseg` 接口 | `requirements.txt` 锁 `jieba==0.42.1` |

---

## 不修改清单 (边界守护)

- `secureredact/__init__.py` (保持现有懒加载)
- `secureredact/workers/__init__.py`
- `secureredact/pii/validators/*`
- `secureredact/ocr/*`
- `secureredact/utils/config.py` (新键归属 `redaction` 命名空间)
- `theme.py`, `version.txt`, `packaging/**`

---

## 进度跟踪

| Wave | 状态 | 完成日期 |
|------|------|---------|
| Wave 0: GSD 规划 | ✅ | 2026-08-15 |
| Wave 1: 核心识别器 + 单测 | ✅ | 2026-08-15 |
| Wave 2: Worker 接入 | ✅ | 2026-08-15 |
| Wave 3: UI + 持久化 + spec + requirements | ✅ | 2026-08-15 |
| Wave 4: 全量回归 + 性能 + 文档 | ✅ | 2026-08-16 |

## 最终验收

- **基线 79 → 114 测试 PASS**（+35：Wave 1 17 + Wave 2 7 + Wave 3 5 + 其他6）
- **文档同步**：CHANGELOG.md / DEV_LOG.md / CLAUDE.md / PHASE_NAME_RECOGNITION.md
- **Phase Checkpoint 命名**：`v37.7.x_name_recognition_x3_cp32_20260816`
- **未启用时与 v37.7.6 行为完全一致**（默认 OFF，向后兼容）