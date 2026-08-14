# Phase 04: PaddleOCR Fallback - Discussion Log

**Date:** 2026-08-13
**Mode:** discuss (default)

## Areas Discussed

### A-1: 触发策略（D-01, D-02）
- 用户原始选项：A（默认开启）/B（GUI 手动框选手写体）
- 用户选择：**B（手动框选）+ 代码默认关闭** — PaddleOCR fallback 代码完整就位但默认不启用
- 理由：PaddleOCR 在 Windows paddleocr 3.2 上对手写数字 0/4/6/o 互相混淆，规则层救不回。RapidOCR 处理印刷体稳定，手写体用手动框选补

### A-2: paddleocr 版本兼容（D-02）
- Windows 用户：paddleocr **3.2.0**（不是 3.0）
- 关键 API 差异：
  - `mode` / `show_log` / `use_gpu` 全部不存在（3.x 移除）
  - `use_doc_orientation_classify` / `use_doc_unwarping` / `use_textline_orientation` 新增
  - `predict()` 替代 `ocr()`（ocr() 是 deprecated wrapper）
  - 构造器白名单校验 (`parse_common_args`) — 任何不在白名单的 kwarg 触发 `Unknown argument`
- 解决方案：`inspect.signature` 内省构造器 + try/except 循环重试移除不兼容 kwarg
- 用户选择验证方案：**在用户 Windows 机器上跑实测**（Context7 文档 + 直接 `python -c "..."` 验证 API 表面）

### A-3: 触发条件（4 trigger D-03）
- T1 (低 conf): `avg_conf < 0.5` — 印刷体偶尔有低置信度行
- T2 (低密度): `chars/(h*w/1000) < 0.05` — 检测器失败
- **T3a (空结果 + 有图像) — 关键**：覆盖 RapidOCR 检测器在小裁剪区域失效场景
- T3b (caller 信号): 传 `high_value_entities` 显式兜底
- 用户选择：**全部保留**，T3a 是 fallback 真正价值所在

### A-4: 合并策略（D-04, D-05, D-06）
- D-04 box IoU > 0.5 dedup：标准做法
- D-05 value-substring dedup：长字符串覆盖短（如 `吉林市船营区人民法院七法庭` 覆盖 `吉林市船营区人民法院`）。**Layer E.1 修复了"首页 header 不该被涂"的 bug**
- D-06 cross-line longest-match box：避免 first-match box 选错位置（page 3 周强 y=315 vs 419）。**Layer E.2 部分修复**

### A-5: 性能预算（D-07）
- 选项：跑 1 次 / 跑 2 次投票 / 按需投票
- 用户选择：**跑 2 次投票**（当前代码）
- 代价：每页 +1-2s
- 收益：手写体识别稳定性略提升（虽然仍救不回 `0/4/6/o` 混淆）

### A-6: 模型选择（D-08, D-09）
- D-08: 关闭 3.x 5+ 个结构化模型（PP-LCNet_x1_0_doc_ori、UVDoc、textline_ori）
- D-09: 强制 `ocr_version="PP-OCRv4"`（避免默认 PP-OCRv5_server）
- 用户接受（这些是关键技术约束，没的商量）

### A-7: 静默降级（D-10）
- paddleocr 包未安装时，`OCREngineManager` 捕获异常并设 `fallback_enabled=False`
- 打印警告但不阻塞 RapidOCR 主路径
- 用户接受

### A-8: 实施到主体代码
- 选项：默认关闭 + 代码就位 / 默认开启 / 完全不落地
- 用户选择：**默认关闭，但代码就位**
- 理由：PaddleOCR fallback 对裁剪小区域检测回退有真实价值（这是我们测试发现的关键场景），保留代码作为可选路径

## Deferred Ideas

- 手写体识别增强（去 `0/4/6/o` 混淆） — 未来 phase
- GPU 加速 — 未来 phase
- 投票重数可配置 — 未来 phase
- PaddleOCR 调试面板 UI — 未来 phase

## Decisions Summary

| ID | Decision | Reversibility |
|---|---|---|
| D-01 | fallback 默认关闭 | reversible（config） |
| D-02 | 2.x/3.x 兼容 via inspect + try/except | reversible |
| D-03 | 4 trigger (T1/T2/T3a/T3b) | reversible |
| D-04 | IoU > 0.5 dedup | reversible |
| D-05 | value-substring 去重 | reversible |
| D-06 | cross-line longest-match | reversible |
| D-07 | 跑 2 次 PaddleOCR voting | reversible |
| D-08 | 关闭结构化模型 | costly（改回会卡） |
| D-09 | PP-OCRv4 轻量 | costly |
| D-10 | paddleocr 不可用静默降级 | reversible |

## Claude's Discretion

- `PRIVACYGUARD_PADDLEOCR_DEBUG=1` 调试开关默认关闭
- 投票重数固定 2 次

---

*Discussion completed: 2026-08-13*
*Phase: 04-paddleocr-fallback*
