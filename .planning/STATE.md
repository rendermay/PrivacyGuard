---
gsd_state_version: 1.0
milestone: v39.0.0
milestone_name: Word 脱敏重做
status: planning
last_updated: "2026-08-19T07:05:00.000Z"
last_activity: 2026-08-19
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Current Position

Phase: Roadmap created (7 phases planned, 0 started)
Plan: —
Status: Roadmap defined — ready for Phase 1 discussion
Last activity: 2026-08-19 — Milestone v39.0.0 roadmap created

## Roadmap Overview

7 phases:
1. 基线、Fixture 治理与接口契约冻结
2. Story 遍历与可逆坐标映射
3. Strangler 架构抽取 + 命中合并与写回
4. 数字、Unicode、隔符号规则
5. 姓名、地名、地址上下文调优
6. 嵌入图 OCR 与预览一致性
7. 批量替换、性能、安全与发布回归

## Next Action

`/gsd-discuss-phase 1` — 基线契约冻结讨论

## Hard Constraints (All Phases)

- CONST-01: PDF 端不动（`secureredact/ocr/*` + `ocr_worker.py` + signal payload）
- CONST-02: 零新 binary 依赖
- CONST-03: 162 项基线不退化（160 PASS + 2 known fail 保持）

Coverage: 17/17 v1 + 1/1 CONST-01 = 100%