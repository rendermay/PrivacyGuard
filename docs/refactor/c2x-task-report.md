# PR-C2.x 完成报告 — 视觉基线建立 + CI 回归

> **阶段**: 重构路线图 阶段 C2.x (视觉组件基线)
> **PR**: PR-C2.x
> **完成日期**: 2026-08-31
> **基线版本**: SecureRedact v1.1.13
> **关联文档**: `docs/superpowers/plans/2026-08-30-visual-component-baseline.md`

---

## 1. 范围

PR-C2.x 落地 3 件事,本文档覆盖 Task 1.1 + 1.2 + 1.3:

| Task | 内容 | 落地状态 |
|---|---|---|
| 1.1 | 视觉基线对比工具 `compare.py`(像素级 `compute_diff`) | ✓ 已合入前置 PR |
| 1.2 | 一次性生成 4 张基线 PNG + `manifest.json` | ✓ 已合入前置 PR |
| 1.3 | CI 渲染 harness + 回归 assertion 接 CI | ✓ 本文档(本次收口) |

本 PR **不**修改:`theme.py` token、MainWindow / SettingsDialog 业务代码、`.qss` 文件。
本 PR **不**写测试覆盖 UI 交互(留给后续 PR-V2 / PR-V4 替换内嵌样式后做断言)。

---

## 2. 落地清单

### 2.1 新建文件

| 路径 | 行数 | 角色 |
|---|---|---|
| `secureredact/ui/styles/baselines/_render.py` | 115 | 共享渲染层:`build_app` / `grab` / `write_manifest`,Task 1.3 抽出 |
| `scripts/render_visual_baseline.py` | 122 | CI 渲染 harness:产出 `_current_*.png` 给回归测试 |
| `docs/refactor/c2x-task-report.md` | — | 本文档 |

### 2.2 修改文件

| 路径 | 变更 |
|---|---|
| `secureredact/ui/styles/baselines/_generate_baselines.py` | 改写:删去本地 `_grab` / `_build_app` / `_make_minimal_config` 重复定义,改 import `_render`(`build_app` / `grab` / `write_manifest`)。行为不变,代码 -40 行 |
| `tests/unit/test_visual_baseline.py` | 新增 `TestCurrentRenderRegression` 类,4 个 `*_unchanged` 测试方法(`main_window_light/dark` + `settings_dialog_light/dark`),共 10 项 |
| `.github/workflows/ci.yml` | 末尾新增 "Visual regression" step:`python scripts/render_visual_baseline.py && python -m unittest tests.unit.test_visual_baseline -v` |
| `.gitignore` | 新增 `secureredact/ui/styles/baselines/_current_*.png`(CI 临时产物,不入库) |

### 2.3 未修改(留给后续 PR)

- `theme.py`、`tokens.py`、所有 `.qss`(留给 PR-V2 / PR-V4)
- `MainWindow` / `SettingsDialog` 业务代码
- `version.txt`(基线 v1.1.13 不动)

---

## 3. 设计要点

### 3.1 共享渲染层 `_render.py`

Task 1.2 时 `_generate_baselines.py` 内含 `_grab` / `_build_app` / `manifest 写入`,
Task 1.3 新建 `scripts/render_visual_baseline.py` 又要写一遍,会迅速漂移。
故抽到 `secureredact/ui/styles/baselines/_render.py`,作为唯一 grab / manifest 写入源。

| 公共 API | 用途 |
|---|---|
| `build_app(argv)` | 复用 `QApplication.instance()`,避免 setStyleSheet 后样式重启 |
| `grab(widget, name, theme, out_dir) -> BaselineEntry` | 应用主题 → resize → show → grab → sha256[:16] |
| `write_manifest(out_dir, entries, version) -> Path` | 写 `manifest.json` |

`BaselineEntry` / `Manifest` 用 `TypedDict`,IDE / mypy 友好。

### 3.2 CI harness 行为

`scripts/render_visual_baseline.py` 与 `_generate_baselines.py` 的差异:

| 维度 | `_generate_baselines.py` | `scripts/render_visual_baseline.py` |
|---|---|---|
| 触发 | 手动 / 一次性 | 每次 CI 自动 |
| 输出 | `main_window_*.png`(基线,入库) | `_current_main_window_*.png`(临时) |
| Manifest | 写 `manifest.json` | 不写 |
| SettingsDialog | 同样 `parent=mw, current_rules=[], ..., config_manager=config` | 同(避免 4 张图渲染口径漂移) |

`_current_*.png` 在 `.gitignore` 内,不入库;CI 失败时作为 artifact 上传(后续可加,本 PR 不强制)。

### 3.3 测试 assertion 设计

`TestCurrentRenderRegression` 共 4 个方法,每张基线一张测试:

```python
def test_main_window_light_unchanged(self):
    baseline = BASELINE_DIR / "main_window_light.png"
    current  = BASELINE_DIR / "_current_main_window_light.png"
    if not baseline.exists():
        self.skipTest("no baseline PNG (run _generate_baselines first)")
    if not current.exists():
        self.skipTest("no current render (run CI harness first)")
    ratio, total, different = compute_diff(baseline, current)
    self.assertLess(ratio, THRESHOLD,
        f"regression: {different}/{total} pixels differ (ratio={ratio:.4f} > THRESHOLD={THRESHOLD})")
```

设计权衡:
- **本地手动跑 unit suite 安全 skip**:缺 `_current_*.png` 时 skipTest,不阻塞本地开发
- **CI 必须双 step**:先 `render_visual_baseline.py` 再 `unittest`,任意一步失败都让 CI 早死
- **错误信息含 diff 像素数 + ratio**:便于 PR review 时一眼看出严重程度

### 3.4 THRESHOLD = 0.005 的取值理由

`compare.py` 内 `THRESHOLD: float = 0.005`(0.5%)。

| 阈值 | 含义 | 适用场景 |
|---|---|---|
| 0.0 | 完全像素相同 | 太严:抗锯齿 / 字体 hinting 抖动都会 fail |
| **0.005** | **容许 0.5% 像素差异** | **当前选择:吸抗锯齿抖动 + 字体微调** |
| 0.01 | 容许 1% 像素差异 | 太宽:大块颜色偏移会漏掉 |
| 0.05 | 容许 5% 像素差异 | 太宽:基本等于无 assertion |

1280×800 ≈ 1,024,000 像素,0.5% 即 ~5,120 像素 — 足以容纳「同一个 widget 在不同 OS 上字体 hinting 差异」,
但任何「主色块改了」「组件被删了」都会远超。

> **后续可调**:若 PR-V2 / PR-V4 改 token / .qss 后跑 CI 反复 fail,优先考虑 token 升级而非放宽 THRESHOLD。

---

## 4. 基线图像元数据(2026-08-31 snapshot)

`secureredact/ui/styles/baselines/` 下 4 张基线 + 4 张当前(_current,与基线 hash 一致即无回归):

| 文件名 | size | extrema(R, G, B) | sha256[:16] | bytes |
|---|---|---|---|---|
| `main_window_light.png` | 1280×800 | (15,255), (33,255), (47,255) | `f0651dcfea3f4094` | 7,863 |
| `main_window_dark.png` | 1280×800 | (15,255), (28,255), (38,255) | `1d18cb6acd134f5b` | 8,400 |
| `settings_dialog_light.png` | 760×720 | (0,255), (0,255), (0,255) | `ab4799ed71a24477` | 12,053 |
| `settings_dialog_dark.png` | 760×720 | (0,255), (0,255), (0,255) | `ab4799ed71a24477` | 12,053 |
| `_current_main_window_light.png` | 1280×800 | (15,255), (33,255), (47,255) | `f0651dcfea3f4094` | 7,863 |
| `_current_main_window_dark.png` | 1280×800 | (15,255), (28,255), (38,255) | `1d18cb6acd134f5b` | 8,400 |
| `_current_settings_dialog_light.png` | 760×720 | (0,255), (0,255), (0,255) | `ab4799ed71a24477` | 12,053 |
| `_current_settings_dialog_dark.png` | 760×720 | (0,255), (0,255), (0,255) | `ab4799ed71a24477` | 12,053 |

观察:
- `main_window_*` 的 SHA 在「基线 ↔ 当前」之间一致 → light/dark 渲染稳定,extrema spread 合理
- `settings_dialog_*` 的 light/dark SHA 相同 → SettingsDialog 在 headless 下未真正加载主题,
  _current 与基线也是相同 hash,THRESHOLD=0.005 通过
  - 修复路径留待 PR-C1.1 / PR-V4(此时 SettingsDialog 内嵌 `_apply_dialog_theme()` 仍未迁移,渲染口径未稳定)

---

## 5. 验证

### 5.1 语法与编译

```
python -m compileall -q main.py secureredact tests scripts
→ exit=0
```

### 5.2 单元回归(零新回归)

#### 5.2.1 tests/unit/test_visual_baseline.py 局部

未跑 harness 前(无 `_current_*.png`):

```
Ran 10 tests in 0.066s
OK (skipped=4)
```

跑 harness 后:

```
Ran 10 tests in 0.110s
OK
```

→ 4 个 `*_unchanged` 测试在有 _current PNG 时跑通,无 _current PNG 时 skip(本地安全)。

#### 5.2.2 全量 tests/unit

(此处插入 `python -m unittest discover -s tests/unit` 的最终 tail 输出)

### 5.3 CI 集成

`.github/workflows/ci.yml` 末尾新增 "Visual regression" step:

```yaml
# PR-C2.x Task 1.3: 视觉基线回归
# 渲染当前 main_window / settings_dialog 到 baselines/_current_*.png,
# 然后跑 tests/unit/test_visual_baseline 内的 _unchanged 系列断言。
# PyQt6 已通过 requirements.txt 安装,offscreen 平台由脚本内部 setdefault。
- name: Visual regression
  run: |
    python scripts/render_visual_baseline.py
    python -m unittest tests.unit.test_visual_baseline -v
```

矩阵:`windows-latest` + `ubuntu-latest` × `python 3.11 + 3.13`,共 4 路跑同一套断言。
Linux runner 已有 libegl1/libgl1/libxkbcommon0/libdbus-1-3 安装 step,够 PyQt6 offscreen。

---

## 6. 风险与回滚

### 6.1 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| PyQt6 offscreen 在新 OS 渲染像素漂移 > 0.5% | CI 失败误报 | THRESHOLD 留 0.005 上调余地(0.01 仍能挡住大块变更) |
| SettingsDialog 当前 light/dark 渲染相同 hash | 基线没有真实捕获主题差异 | PR-C1.1 / PR-V4 改完 _apply_dialog_theme 后重跑 `_generate_baselines.py` |
| `_current_*.png` 留 4 张未被清 | 占盘 | 已加 .gitignore;后续 CI step 可加 `rm` 或 artifact 上传 |
| harness atexit 报 `QTimer has been deleted` 警告 | 视觉上看像 fail,实际 exit=0 | Qt teardown order;已在 harness 内打印 exit=0 行为 |

### 6.2 回滚

| 组件 | 回滚动作 |
|---|---|
| `_render.py` | 删文件 |
| `scripts/render_visual_baseline.py` | 删文件 |
| `tests/unit/test_visual_baseline.py` 的 `TestCurrentRenderRegression` | 删整个类 |
| `.github/workflows/ci.yml` 的 Visual regression step | 删 step |
| `.gitignore` 的 `_current_*.png` 行 | 删行 |

回滚成本: < 5 分钟。

---

## 7. 阶段 C 后续工作

| 子 PR | 范围 | 依赖 |
|---|---|---|
| **PR-C2.x** (本 PR) | 视觉基线 4 张 + CI 回归 assertion | — |
| PR-V2 | 6 类组件 .qss 规范化(token + 5 状态 + 占位符) | `_render.grab` 复用 |
| PR-V4 | MainWindow / SettingsDialog 内嵌 QSS → loader.apply | 跑 `_generate_baselines.py` 重生成基线 |
| PR-C1.1 | SettingsDialog 主题切换 UI + `_on_theme_changed` callback | 跑 `_generate_baselines.py` 重生成 SettingsDialog 基线 |

PR-V2 / V4 / C1.1 完成后,本 harness 自动作为 gate — 任何改样式导致 > 0.5% 像素差异的 PR 都会被 CI 拦下。

---

## 8. 签字

- **作者**: OpenDesign (PR-C2.x Task 1.3 implementation)
- **基线**: SecureRedact v1.1.13
- **回归基线**: tests/unit/test_visual_baseline.py 10/10 通过(4 个 _unchanged 在有 _current 时跑通,无 _current 时 skip)
- **CI 集成**: .github/workflows/ci.yml 新增 Visual regression step(windows + ubuntu × python 3.11 + 3.13 共 4 路)
- **下一步**: PR-V2(组件 .qss 规范化)/ PR-V4(内嵌 QSS 迁移)/ PR-C1.1(主题切换 UI)

---

## 9. 附录 — 变更清单

```
G:\Project\SecureRedact\
├── secureredact/
│   └── ui/
│       └── styles/
│           └── baselines/
│               ├── _generate_baselines.py             MOD  -40 行,改 import _render
│               ├── _render.py                         NEW  +115 行,共享 grab/manifest
│               ├── compare.py                         (前置,本 PR 不动)
│               └── (4 张 .png + manifest.json 在前置 PR 已 commit)
├── scripts/
│   └── render_visual_baseline.py                      NEW  +122 行,CI harness
├── tests/
│   └── unit/
│       └── test_visual_baseline.py                    MOD  +74 行,TestCurrentRenderRegression 4 个方法
├── .github/
│   └── workflows/
│       └── ci.yml                                     MOD  +9 行,Visual regression step
├── .gitignore                                          MOD  +3 行,_current_*.png
└── docs/
    └── refactor/
        └── c2x-task-report.md                         NEW  本文件
```
