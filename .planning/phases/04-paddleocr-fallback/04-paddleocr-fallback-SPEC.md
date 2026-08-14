# Phase 04: PaddleOCR Fallback - Specification

**Created:** 2026-08-13
**Status:** Awaiting user approval before modifying core code
**Ambiguity score:** 0.18 (gate: ≤ 0.20)
**Requirements:** 7 locked

## Goal

OCRWorker 在 image-block 粒度上为 RapidOCR 提供 PaddleOCR fallback：当 RapidOCR 对单个 image block 的识别结果置信度低、字符密度异常低、或未命中高价值敏感模式（CN_ID_CARD / CN_PHONE / CN_BANK_CARD / CN_BANK_ACCOUNT）时，自动调用 PaddleOCR 手写体模型补一次。两路结果按 box IoU 去重，取高置信度版本。预期效果是周强起诉状.pdf 端到端命中数从当前 28/30 提升到 ≥30/30（印刷体部分）。

## Background

当前 RapidOCR 是唯一 OCR 引擎，识别印刷体中文效果良好但手写体识别率低。周强起诉状回归中：
- page 1 的 `刘妹043-62407159`（手写体联系电话 + 姓名）完全漏识别
- page 3 的 `周强`（手写体起诉人签名）识别到但坐标偏差

两个手写体块均未触发任何敏感模式匹配。修复路径是引入 PaddleOCR 作为单 image block 级 fallback——同源（RapidOCR 就是 PaddleOCR 的 ONNX 导出）但支持手写体识别模型与可调后处理参数。

**实际验证结果**（2026-08-13 真实环境测试）：
- 在高分辨率（3x scale，216 DPI）下 RapidOCR 也能识别手写体——所以问题不是 scale
- PaddleOCR fallback 在小裁剪区域**比 RapidOCR 更鲁棒**（RapidOCR 检测器在小区域会失败，PaddleOCR 不会）
- PaddleOCR 对手写数字 `0/4/6/o` 互相混淆是**固有限制**，voting 救不回
- 最终方案：**默认关闭** PaddleOCR fallback，手写体用 GUI 手动框选

## Requirements

### R1 — PaddleOCR 引擎适配器
- **Current:** 仅 `privacyguard/ocr/rapidocr.py` 一个引擎。
- **Target:** 新增 `privacyguard/ocr/paddleocr.py` 实现 `OCREngineBase` 接口（`recognize(image) → List[OCRResult]`），使用 PP-OCRv4_mobile_det / PP-OCRv4_mobile_rec 模型（轻量级），可自动适配 paddleocr 2.x 和 3.x。
- **Acceptance:** `python3 -c "from privacyguard.ocr.paddleocr import PaddleOCREngine; e = PaddleOCREngine(); e._ensure_engine()"` 在 paddlepaddle 已安装环境下成功初始化。

### R2 — OCRManager 主备决策
- **Current:** `OCREngineManager` 只 wrap RapidOCR。
- **Target:** 扩展为 primary=RapidOCR + fallback=PaddleOCR，含 4 trigger：T1 (低conf) / T2 (低密度) / T3a (空结果) / T3b (caller 信号)。
- **Acceptance:** 单测 `test_T1_high_conf_no_fallback`：mock conf=0.9 → 不调用 fallback；`test_T1_low_conf_triggers_fallback`：mock conf=0.3 → 调用 fallback。

### R3 — Fallback 决策（image-block 粒度）
- **Current:** 无决策逻辑。
- **Target:** `_should_fallback(primary_results, image, high_value_entities)` 返回 True 当且仅当满足任一：
  - T1: `avg_conf < 0.5`（`config.paddleocr_fallback_conf_threshold`）
  - T2: `chars / (h*w/1000) < 0.05`（字符密度近乎为零）
  - **T3a** (关键): `primary_results 为空 + image 非空` — 覆盖 RapidOCR 检测器在小裁剪区失效
  - T3b: caller 传了 `high_value_entities`（caller 显式信号做敏感字段兜底）
- **Acceptance:** 四个 trigger 各有一个单测覆盖。

### R4 — 结果合并与去重
- **Current:** 无合并。
- **Target:** `_merge_results(primary, fallback) → List[OCRResult]`。对每个 fallback 结果，计算与 primary 中所有结果的 box IoU，IoU > 0.5 时取高置信度版本；IoU ≤ 0.5 时作为新结果加入。
- **Acceptance:** 单测 `test_merge_keeps_higher_conf`：同 box fallback conf=0.9 替换 primary conf=0.4；`test_merge_keeps_distinct`：IoU=0.2 的两个结果都保留。

### R5 — OCRWorker 接入
- **Current:** `OCRWorker.run()` 直接调用 `RapidOCREngine`。
- **Target:** 改为调用 `OCREngineManager.recognize_with_fallback`，传 `high_value_entities={CN_ID_CARD, CN_PHONE, CN_BANK_CARD, CN_BANK_ACCOUNT}`。
- **Acceptance:** 现有 baseline 138/138 测试不变。

### R6 — 静默降级（paddleocr 不可用时）
- **Current:** 无 fallback，谈不上降级。
- **Target:** 当 `paddleocr` 包未安装 / 模型加载失败 / `PaddleOCR(use_gpu=False)` 抛异常 → `OCREngineManager` 捕获并设 `fallback_enabled=False`，打印警告，继续只跑 RapidOCR。
- **Acceptance:** 单测 `test_fallback_silently_disables_on_import_error`：mock `paddleocr` import 抛 `ImportError` → `OCREngineManager.recognize_with_fallback()` 仍返回 primary 结果，不抛异常。

### R7 — 默认关闭 PaddleOCR fallback（基于真实测试发现）
- **Current:** `config.json` `paddleocr_fallback_enabled=true`（v37.7.6 默认值）。
- **Target:** 修改默认值为 `false`——因为 PaddleOCR 在 Windows paddleocr 3.2 上对手写体识别非确定性（`0/4/6/o` 互相混淆），规则层救不回。印刷体由 RapidOCR 稳定处理，手写体用 GUI 手动框选。
- **Acceptance:** `config.json` 中 `ocr.paddleocr_fallback_enabled` 默认为 `false`；用户可通过 `paddleocr_fallback_enabled: true` 重新启用。

## Boundaries

**In scope:**
- 新增 `privacyguard/ocr/paddleocr.py`（PaddleOCREngine 适配器）
- 修改 `privacyguard/ocr/manager.py`（OCREngineManager 扩展加 fallback 决策 + voting）
- 修改 `privacyguard/workers/ocr_worker.py`（接入 OCREngineManager + 保留旧函数）
- 修改 `config.json`（加 paddleocr_fallback_* 配置，默认 disabled）
- 新增 `tests/scripts/test_paddleocr_fallback_mock.py`（15 个 mock 测试）
- 新增 `tests/unit/test_ocr_runtime_match.py`（17 个 group(1) 测试）

**Out of scope:**
- 改动 OCR 之外的 PII 识别管线
- 改动 mask mode / per_entity_default 默认值
- 替换 RapidOCR 为 PaddleOCR 全量路径
- 增加云端 OCR API
- 增加 GPU 加速
- 修改 Word 路径的 OCR
- 修改 main.py 的 UI（SettingsDialog 等）

## Constraints

- 零网络运行时（继承自 CLAUDE.md ENGINE-08）
- paddlepaddle-cpu 优先（节省 400MB CUDA 库）
- paddleocr 2.x 和 3.x 都要支持（自动版本检测 + 参数适配）
- 性能：单 image block PaddleOCR fallback 不超过 1s（按 RapidOCR 单块 ~50ms 的 20x 估）
- 单例：PaddleOCREngine 必须单例（模型加载 5s）
- Baseline 兼容：现有 138/138 测试在改动后必须仍然通过
- 真实 PDF 端到端：周强起诉状.pdf 触发 fallback 时能识别印刷体（手写体不在此 phase 的成功标准里）

## Acceptance Criteria

- [ ] `privacyguard/ocr/paddleocr.py` 存在并实现 `OCREngineBase` 接口
- [ ] `privacyguard/ocr/manager.py` 提供 `recognize_with_fallback(image, high_value_entities)` 入口
- [ ] `privacyguard/workers/ocr_worker.py` 调用 `OCREngineManager.recognize_with_fallback()`
- [ ] `config.json` 包含 `paddleocr_fallback_enabled: false` 默认值
- [ ] 单测 `test_manager_high_conf_no_fallback` 通过
- [ ] 单测 `test_manager_low_conf_triggers_fallback` 通过
- [ ] 单测 `test_manager_low_density_triggers_fallback` 通过
- [ ] 单测 `test_manager_empty_results_trigger_fallback` 通过
- [ ] 单测 `test_manager_high_value_triggers_fallback` 通过
- [ ] 单测 `test_merge_keeps_higher_conf` 通过
- [ ] 单测 `test_merge_keeps_distinct` 通过
- [ ] 单测 `test_fallback_silently_disables_on_import_error` 通过
- [ ] 现有 baseline 138/138 测试不回归
- [ ] 周强起诉状.pdf 端到端：印刷体 28/30 命中（手写体不在此 phase 范围）

## Real Experiment Findings (2026-08-13)

**Context7 文档（paddleocr 3.x 官方）查询**：
- `PaddleOCR.__init__` 接受的 kwargs（2.x/3.x 共 10+ 个，白名单由 `parse_common_args` 强制）
- `ocr.predict()` 返回 `[OCRResult, ...]`，每个有 `.json` 属性 = `{"res": {"rec_texts": [...], "rec_scores": [...], "dt_polys": [...], "rec_polys": [...], "rec_boxes": [...]}}`
- 3.x 默认加载 `use_doc_orientation_classify + use_doc_unwarping + use_textline_orientation` 5+ 个结构化模型（耗时 60+ 秒），必须显式 `False` 关闭
- 3.x 默认 `PP-OCRv5_server`（很重），设 `ocr_version="PP-OCRv4"` 切到轻量

**真实测试结果**（在用户 Windows 机器上）：
- PaddleOCR 对同一图像**两次调用结果不稳定**（如 `'刘之妹0433-62407159'` vs `'刘妹 o3-6207159'`）
- voting 跑 2 次取交集**仍救不回** `0/4/6/o` 互相混淆的根本问题
- RapidOCR 在裁剪小区域**检测器失效**（PaddleOCR 不失效——这是 fallback 真正价值）
- 在完整页 OCR 场景下，RapidOCR 和 PaddleOCR 几乎等价（差 2-4 行）

**结论**：PaddleOCR fallback 真正价值是**裁剪小区域检测器兜底**，不是手写体识别。手写体交给 GUI 手动框选。

---

*Phase: 04-paddleocr-fallback*
*Spec created: 2026-08-13*
*Context: 详见 04-CONTEXT.md*
