# Phase 04: PaddleOCR Fallback - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning

<domain>
## Phase Boundary

为 OCRWorker 提供 PaddleOCR fallback 路径，覆盖 RapidOCR 检测器在小裁剪区域失效的场景。PaddleOCR 真正价值是**裁剪小区域检测回退**，不是手写体识别——手写体由 GUI 手动框选 (`rects_manual`) 处理。

域：单 image block 级别的 OCR 双引擎协作。PaddleOCR 跑 2 次取交集 (voting) 减少单次随机性。
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**7 requirements are locked.** See `04-paddleocr-fallback-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `04-paddleocr-fallback-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md Boundaries):**
- 新增 `privacyguard/ocr/paddleocr.py`（PaddleOCREngine 适配器）
- 修改 `privacyguard/ocr/manager.py`（OCREngineManager 扩展加 fallback 决策 + voting）
- 修改 `privacyguard/workers/ocr_worker.py`（接入 OCREngineManager + 保留旧函数）
- 修改 `config.json`（加 paddleocr_fallback_* 配置，默认 disabled）
- 新增 `tests/scripts/test_paddleocr_fallback_mock.py`（15 个 mock 测试）
- 新增 `tests/unit/test_ocr_runtime_match.py`（17 个 group(1) 测试）

**Out of scope (from SPEC.md Boundaries):**
- 改动 OCR 之外的 PII 识别管线
- 改动 mask mode / per_entity_default 默认值
- 替换 RapidOCR 为 PaddleOCR 全量路径
- 增加云端 OCR API
- 增加 GPU 加速
- 修改 Word 路径的 OCR
- 修改 main.py 的 UI（SettingsDialog 等）
</spec_lock>

<decisions>
## Implementation Decisions

### 触发策略
- **D-01:** PaddleOCR fallback **默认关闭**（`config.json` `paddleocr_fallback_enabled=false`）。原因：PaddleOCR 在 Windows paddleocr 3.2 上对手写数字 `0/4/6/o` 互相混淆，规则层无法救回。RapidOCR 已能稳定处理印刷体。手写体由 GUI 手动框选。 — **Reversibility:** reversible — 改 config 即可
- **D-02:** PaddleOCR fallback **启用时**：自动适配 paddleocr 2.x 和 3.x，通过 `inspect.signature` 内省构造器 + try/except 循环重试。处理 show_log / use_gpu / mode / rec_model_dir 等逐版本参数差异。 — **Reversibility:** reversible — 简化逻辑只需保留 3.x 路径

### 触发条件（4 个 trigger）
- **D-03:** `_should_fallback` 返回 True 当满足任一：
  - T1: `avg_conf < 0.5`
  - T2: `chars / (h*w/1000) < 0.05`（字符密度近乎为零）
  - T3a: `primary_results 为空 + image 非空` — 关键，覆盖 RapidOCR 检测器在小裁剪区失效
  - T3b: caller 传了 `high_value_entities` — 显式兜底信号 — **Reversibility:** reversible — 改 trigger 即可

### 合并策略
- **D-04:** `_merge_results` 用 box IoU > 0.5 去重，取高置信度版本。 — **Reversibility:** reversible
- **D-05:** value-substring 去重：长字符串覆盖短字符串（如 `吉林市船营区人民法院` 覆盖 `吉林市船营区`）。Layer E.1 已实施。 — **Reversibility:** reversible
- **D-06:** cross-line aggregation 用**最长连续匹配**的 OCR 行 box 选最优位置。Layer E.2 已实施。 — **Reversibility:** reversible

### 性能预算（已确定）
- **D-07:** PaddleOCR fallback 跑 2 次取交集（voting），每页 +1-2s。稳定性优先于速度。 — **Reversibility:** reversible — 改回 1 次即可

### 模型选择
- **D-08:** paddleocr 3.x 必须显式设 `use_doc_orientation_classify=False`、`use_doc_unwarping=False`、`use_textline_orientation=False` 跳过 5+ 个结构化模型加载（耗时 60+ 秒）。 — **Reversibility:** costly — 改回默认值会卡死
- **D-09:** 强制 `ocr_version="PP-OCRv4"` 切到轻量模型族（避免默认 PP-OCRv5_server）。 — **Reversibility:** costly — 改回 v5 会重很多

### 静默降级
- **D-10:** paddleocr 包未安装 / 模型加载失败时，`OCREngineManager` 捕获异常并设 `fallback_enabled=False`，打印警告，继续只跑 RapidOCR。 — **Reversibility:** reversible

### Claude's Discretion

- 调试日志开关（`PRIVACYGUARD_PADDLEOCR_DEBUG=1`）由 Claude 控制，避免污染默认日志
- 合并代码时手写体识别能力的进一步优化（投票后正则匹配），可留作 P2 backlog

### 折叠的待办
无（cross_reference_todos 显示 0 项匹配）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-specific
- `04-paddleocr-fallback-SPEC.md` — Locked requirements and acceptance criteria
- `/tmp/paddleocr_fallback_spec/FINDINGS.md`（已清理）— 真实环境测试发现（PaddleOCR 0/4/6/o 互相混淆、RapidOCR 检测器在小区域失效等）

### Context7 官方文档（paddleocr 3.x）
- `https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.md` — 官方推荐配置：`use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, ocr_version="PP-OCRv4"`
- `https://github.com/PaddlePaddle/PaddleOCR/blob/main/_pipelines/ocr.py` — OCRResult 类定义、predict() 签名
- `https://github.com/PaddlePaddle/PaddleOCR/blob/main/paddleocr/_common_args.py` — parse_common_args 白名单校验
- `https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/paddlex/quick_start.md` — predict() 返回 JSON 结构（rec_texts / rec_scores / dt_polys / rec_polys / rec_boxes 平行数组）

### Project-level
- `.planning/PROJECT.md` — 项目核心价值与里程碑定义
- `.planning/ROADMAP.md` — Phase 04 范围定义
- `.planning/STATE.md` — 当前进度（v38.x 已 ship 前 3 phases）
- `.planning/phases/02-pdf/02-VERIFICATION.md` — Phase 2 失败的 VERIFICATION（含 4 个 gap，对 04 也有参考价值）

### PrivacyGuard 核心架构
- `privacyguard/ocr/base.py` — OCREngineBase 抽象接口 + OCRResult dataclass
- `privacyguard/ocr/rapidocr.py` — RapidOCREngine 实现
- `privacyguard/ocr/manager.py` — OCREngineManager（fallback 决策 + 合并）
- `privacyguard/ocr/text_pdf.py` — 文字型 PDF 处理（HEURISTIC 验证用）
- `privacyguard/ocr/mixed_pdf.py` — 混合型 PDF 处理（cross-line 聚合实现）
- `privacyguard/workers/ocr_worker.py` — OCRWorker 主类
- `main.py` — MainWindow + save_pdf 流程

### 测试参考
- `tests/unit/test_ocr_runtime_match.py` — 17 个 HEURISTIC group(1) 验证
- `tests/scripts/test_paddleocr_fallback_mock.py` — 15 个 fallback mock 测试（待建）
- `tests/unit/test_convergence.py` — main.py 收敛原则验证

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **OCREngineBase (`privacyguard/ocr/base.py:30-50`)**: 抽象接口 (`recognize` / `is_available` / `warmup`)，OCRResult dataclass 已定义。PaddleOCREngine 只需实现 `recognize(image) → List[OCRResult]`。
- **RapidOCREngine (`privacyguard/ocr/rapidocr.py:15-62`)**: 单引擎实现，可作为 PaddleOCREngine 的实现参考。
- **collect_image_block_ocr_hits (`privacyguard/ocr/mixed_pdf.py:84-144`)**: 已支持 `recognize_fn` 注入，OCRWorker 已改成调 fallback wrapper。
- **iter_ocr_lines (`privacyguard/ocr/mixed_pdf.py:73-81`)**: 已支持 `OCRResult` 对象（`hasattr(result, "box") and hasattr(result, "text")`）。
- **HEURISTIC_RULES (main.py:245-267)**: 21 条 label-anchored 通用规则 + 6 条 DEFAULT_RULES = 27 条 pattern，可直接喂给 OCRManager。

### Established Patterns
- **V37.7.6 收敛原则**: main.py 必须委托给共享模块，禁止内联复刻。OCRWorker 已收敛到 `privacyguard.workers.ocr_worker`。
- **PIIEngine 懒加载** (OPS-03): 启动时不 eager 加载 PII validators，运行时按需。PaddleOCREngine 同样要懒加载模型（5s 初始化）。
- **value-substring 去重** (Layer E.1): 长字符串覆盖短字符串。OCRWorker.collect_image_block_ocr_hits 内部已实施。
- **跨行聚合** (Layer E.2): 选**最长连续匹配**的 OCR 行 box 作 rect，最优位置。

### Integration Points
- **OCRManager (`privacyguard/ocr/manager.py`)**: 新增 `recognize_with_fallback` 入口，作为 OCRWorker 的统一调用接口。
- **OCRWorker.run() (`privacyguard/workers/ocr_worker.py:493`)**: 把 `_recognize_and_collect` 换成 `_recognize_and_collect_with_fallback`，传 `high_value_entities=_HIGH_VALUE_ENTITIES`。
- **config.json (`ocr` section)**: 新增 `paddleocr_fallback_*` 配置键。

</code_context>

<specifics>
## Specific Ideas

- **GUI 手动框选路径** (用户最终选择 B 方案): PrivacyGuard 已有完整 `rects_manual` 机制（`main.py:4282, 4297, 4302, 4443`）。手写体由用户拖框选补，OCR 引擎不负责。
- **PaddleOCR 投票稳定化**: paddleocr 每次调用结果不稳定。`_recognize_with_voting` 跑 2 次取 box IoU > 0.3 或 text 字符串完全匹配的交集。
- **优先级合并**: `rule > manual > ocr`（`main.py:928 _merge_matches`），手动框选第二优先级。
- **运行时调试开关**: `PRIVACYGUARD_PADDLEOCR_DEBUG=1` 打印 PaddleOCR 完整 30 行输出，便于诊断。

</specifics>

<deferred>
## Deferred Ideas

- **手写体识别增强**: 进一步优化 PaddleOCR 对手写数字 `0/4/6/o` 的识别（可能的方案：图像增强 + 多次 voting + 字符级后处理纠错）。当前选择 PaddleOCR fallback 默认关闭，由 GUI 手动框选替代。 — 未来 phase
- **GPU 加速**: paddlepaddle-gpu 加速。当前 paddlepaddle-cpu 已够用。 — 未来 phase
- **PaddleOCR 投票重数可配置**: 当前固定 2 次。可加 `paddleocr_fallback_voting_count` 配置。 — 未来 phase
- **PaddleOCR 完整调试面板 (UI)**: 在 SettingsDialog 加 PaddleOCR 详细状态。 — 未来 phase

### Reviewed Todos (not folded)
无（cross_reference_todos 显示 0 项匹配）

</deferred>

---

*Phase: 04-paddleocr-fallback*
*Context gathered: 2026-08-13*
*Next: /gsd-plan-phase 04-paddleocr-fallback*
