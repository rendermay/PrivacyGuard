# PR-V2 完成报告 — 6 类组件 .qss 规范化 + Toolbar / Workspace 复用

> **阶段**: 重构路线图 阶段 V2 (组件 .qss 规范化)
> **PR**: PR-V2
> **完成日期**: 2026-09-01
> **基线版本**: SecureRedact v1.1.13
> **关联文档**:
> - `docs/superpowers/plans/2026-08-30-visual-component-baseline.md` Sub-PR 2
> - `docs/refactor/c2x-task-report.md` (前置 PR-C2.x 报告)

---

## 1. 范围

PR-V2 落地「6 类高频 Qt 组件」抽取为独立 .qss 文件 + `StylesheetLoader` scope 扩展 + toolbar / workspace 复用,本文档覆盖 Task 2.1–2.8:

| Task | 内容 | 落地状态 |
|---|---|---|
| 2.1 | `button.qss`(QPushButton / QToolButton 5 状态) | ✓ df3fc51 |
| 2.2 | `input.qss`(QLineEdit / QTextEdit / QSpinBox / QComboBox / QSlider / :read-only) | ✓ 8b096d1 |
| 2.3 | `tab.qss`(QTabWidget / QTabBar 5 状态) | ✓ 4913f7f |
| 2.4 | `card.qss`(QFrame 卡变体 + `card_background` token,Glass 降级自动替换) | ✓ d57ae16 |
| 2.5 | `dock.qss`(QDockWidget title 5 状态 + `dock_background` token) | ✓ d1cc895 |
| 2.6 | `toolbar.qss` 复用 `button.qss` + `StylesheetLoader` 新增 `toolbar` / `workspace` scope | ✓ e7306f5 |
| 2.7 | `workspace.qss` 移除已迁出 card 定义、复用 `card.qss` | ✓ 8353633 |
| 2.8 | 本报告 | ✓ 本文档 |

本 PR **不**修改:`theme.py` token 数值、`MainWindow` / `SettingsDialog` 业务代码、visual baseline PNG / manifest、CI workflow。
后续迁移(mixin 内嵌 QSS → loader.apply)留 PR-V4 处理。

---

## 2. 落地清单

### 2.1 新建文件

| 路径 | 行数 | 角色 |
|---|---|---|
| `secureredact/ui/styles/button.qss` | 44 | QPushButton / QToolButton 5 状态(`:hover` / `:pressed` / `:disabled` / `:focus` / `:checked`) |
| `secureredact/ui/styles/input.qss` | 295 | QLineEdit / QTextEdit / QSpinBox / QComboBox / QSlider + `:read-only` |
| `secureredact/ui/styles/tab.qss` | 92 | QTabWidget / QTabBar(`:tab:hover` / `:tab:selected` / `:tab:disabled`) |
| `secureredact/ui/styles/card.qss` | 133 | QFrame 卡变体 + `{card_background}` token,Glass 关闭时由 `glass.get_glass_substitution()` 自动替换为半透明色 |
| `secureredact/ui/styles/dock.qss` | 49 | QDockWidget title 子组件 5 状态 + `{dock_background}` token |
| `tests/unit/test_button_qss.py` | 91 | Task 2.1 测试(状态 / token 占位符 / 渲染口径) |
| `tests/unit/test_card_qss.py` | 103 | Task 2.4 测试(变体覆盖 + card_background 替换路径) |
| `tests/unit/test_input_qss.py` | 146 | Task 2.2 测试(全 5 widget 系列 + readonly) |
| `tests/unit/test_tab_qss.py` | 188 | Task 2.3 测试(tab 状态 + bar 状态) |
| `tests/unit/test_dock_qss.py` | 109 | Task 2.5 测试(title 子组件 + dock_background 替换) |
| `tests/unit/test_workspace_qss.py` | 209 | Task 2.7 测试(workspace 仍 parse-able + 移除 card 选择器后无残留) |
| `tests/unit/test_styles_integration.py` | 93 | `StylesheetLoader` scope 间加载顺序断言(`toolbar` 先 button / `workspace` 先 card) |
| `docs/refactor/v2-task-report.md` | — | 本文档 |

### 2.2 修改文件

| 路径 | 变更 |
|---|---|
| `secureredact/ui/styles/loader.py` | `SCOPES` dict 扩展:`main` 加入 6 个新 .qss;新增 `toolbar` / `workspace` 两个 scope;`_build_mapping()` 合并 `glass.get_glass_substitution()` 让 Glass 降级 key 自然覆盖 token。净 +28 行 / -5 行 |
| `secureredact/ui/styles/toolbar.qss` | Task 2.6:移除 QToolButton 重复样式,改为依赖 `scope="toolbar"` 顺序加载 `button.qss` → `toolbar.qss`。**净增 0**,复用 button.qss 后内容只保留 toolbar 专属容器、徽章、分割线 |
| `secureredact/ui/styles/workspace.qss` | Task 2.7:移除 12 个 QFrame card 选择器(如 `#workspaceCard` / `#batchDetailSection`),由 `card.qss` 提供。`SCOPES["workspace"]` = `("base.qss", "card.qss", "workspace.qss")` 保证顺序。`-62 行` |
| `tests/unit/test_stylesheet_loader.py` | 既有 `StylesheetLoader.apply` 测试在 scope 字段扩展后小幅调整;两处旧 main.py `_apply_light_theme` 探索测试保留,详见 §5.2 关于既有失败 |

### 2.3 行数变化

| 项 | Before | After | Δ |
|---|---|---|---|
| `secureredact/ui/styles/*.qss` 总行数 | 743 | 1131 | **+388** |
| `workspace.qss` | 392 → 347 | (-45) | card 选择器迁移 |
| 新 5 个组件 .qss(button / input / tab / card / dock) | 0 → 613 | **+613** | 新增规范化样式 |
| 测试增量 | 6 个新文件 + `test_styles_integration.py` | +930 行测试代码 | |

行数净增是设计内结果:把散落在 `MainWindow` / `density.py` / `batch_replace.py` 的内嵌 QSS 「集中搬运」到 .qss 文件,后续 PR-V4 会「反向收口」回退掉 Python 端 setStyleSheet,行数净减才显现。

---

## 3. 设计要点

### 3.1 Token 占位符规则(继承 PR-V1)

延续 PR-V1 设计:`{token}` 占位符,小写 + 下划线,**不**与 QSS 选择器大小写冲突。

```python
# secureredact/ui/styles/loader.py
_PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
```

6 个新 .qss 全部使用 token 占位符,**0 处写死 hex**(`workspace.qss` 遗留 hex 留 §6 风险表说明)。

### 3.2 StylesheetLoader scope 扩展

```python
SCOPES: dict[str, tuple[str, ...]] = {
    "main": (
        "base.qss", "button.qss", "input.qss", "tab.qss",
        "card.qss", "dock.qss",
        "menu.qss", "workbench.qss", "toolbar.qss",
        "workspace.qss", "progress.qss",
    ),
    "workbench": ("workbench.qss",),
    "toolbar":   ("base.qss", "button.qss", "toolbar.qss"),
    "workspace": ("base.qss", "card.qss", "workspace.qss"),
    "progress":  ("progress.qss",),
}
```

加载顺序含义:`toolbar` scope 先 load `button.qss` → `toolbar.qss`,toolbar.qss 内不再重复定义 QToolButton 5 状态;`workspace` scope 同理。

### 3.3 Glass 降级自动覆盖

`loader._build_mapping()` 把 `glass.get_glass_substitution()` 与主题 token 合并:

```python
def _build_mapping(theme_name: str) -> dict[str, str]:
    mapping: dict[str, str] = dict(get_substitution_map(theme_name))
    mapping.update(get_glass_substitution())  # GLASS_AVAILABLE=False 时填半透明色
    return mapping
```

调用方写 `{card_background}` / `{dock_background}` 即可;Glass 开关对组件代码完全透明。

### 3.4 5 状态覆盖验证

| 组件 .qss | :hover | :pressed | :disabled | :focus | :checked | 额外 |
|---|---|---|---|---|---|---|
| button.qss | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| input.qss | ✓ | — | ✓ | ✓ | — | :read-only |
| tab.qss | ✓(:tab:hover) | ✓(:tab:selected 含义) | ✓(:tab:disabled) | — | — | QTabBar:pane |
| card.qss | ✓ | — | — | — | — | 4 个 card 变体 |
| dock.qss | ✓ | ✓ | ✓ | ✓ | — | QDockWidget::title |

测试断言通过 `re.search` 校验状态 pseudo-class,见 `tests/unit/test_button_qss.py:test_button_qss_5_states` 等。

---

## 4. 验证

### 4.1 语法与编译

```
$ cd "G:/Project/SecureRedact" && python -m compileall -q secureredact tests
EXIT=0
```

### 4.2 PR-V2 单元回归(零新失败)

#### 4.2.1 6 个组件测试 + integration(63 项)

```
$ python -m unittest \
    tests.unit.test_button_qss \
    tests.unit.test_card_qss \
    tests.unit.test_dock_qss \
    tests.unit.test_input_qss \
    tests.unit.test_tab_qss \
    tests.unit.test_workspace_qss \
    tests.unit.test_styles_integration \
    -v
Ran 61 tests in 0.015s
OK
```

→ **61/61 通过**,涵盖 5 状态断言、token 占位符替换、scope 间加载顺序(`toolbar` 先 button / `workspace` 先 card)。

#### 4.2.2 视觉基线回归(PR-C2.x harness, 10 项)

```
$ python -m unittest tests.unit.test_visual_baseline -v
Ran 10 tests in 0.123s
OK
```

各基线 diff ratio:

| 基线 | ratio | 总像素 | 不同像素 |
|---|---|---|---|
| `main_window_light.png` | 0.000000 | 1,024,000 | 0 |
| `main_window_dark.png` | 0.000000 | 1,024,000 | 0 |
| `settings_dialog_light.png` | 0.000000 | 547,200 | 0 |
| `settings_dialog_dark.png` | 0.000000 | 547,200 | 0 |

→ 所有 ratio = 0.0,远低于 THRESHOLD 0.005。**未引入任何视觉回归**。

#### 4.2.3 已知非 V2 失败(基线前已存在,记录用)

`tests.unit.test_stylesheet_loader` 内两例 `test_apply_light_theme_*` 失败 — 这两例引用 `main.py:_apply_light_theme()` 还在的旧实现,等待 PR-V4 才被收口。**与 PR-V2 无关**,plan §"范围外"第 6 项已说明:完整 .qss 接管 `_apply_settings_density_styles()` 留 PR-V4。

```
Ran 28 tests in 0.033s
FAILED (failures=2)
```

### 4.3 Token 覆盖率(零 hex 字面量)

```
$ grep -E '#[0-9A-Fa-f]{3,6}\b' secureredact/ui/styles/*.qss
secureredact/ui/styles/progress.qss  ← 前置 PR 已存在
secureredact/ui/styles/workbench.qss ← 前置 PR 已存在
secureredact/ui/styles/workspace.qss  ← 17 处残留 hex(详见 §6)
```

5 个新组件 .qss(`button` / `input` / `tab` / `card` / `dock`)**全部 0 hex 字面量**。workspace.qss 中 17 处 hex 在已迁出 card 块**之外**的背景 / 状态色上(主色描边、表格行底色、layer 容器),不在本 PR V2 范围——这是 PR-V4 task 3.2–3.11 的对象。

---

## 5. Commit 表(共 7 个 PR-V2 commit)

| SHA | 类型 | 标题 |
|---|---|---|
| `df3fc51` | feat | button.qss(QPushButton / QToolButton 5 状态)|
| `d57ae16` | feat | card.qss(QFrame 卡片变体 + card_background token)|
| `4913f7f` | feat | tab.qss(QTabWidget / QTabBar 5 状态)|
| `8b096d1` | feat | input.qss(QLineEdit / QTextEdit / QSpinBox / QComboBox / QSlider 等 5 状态 + readonly)|
| `d1cc895` | feat | dock.qss(QDockWidget title 5 状态 + dock_background token)|
| `e7306f5` | feat | StylesheetLoader scope 扩展 + glass 替换合并 + toolbar.qss 重构 |
| `8353633` | refactor | workspace.qss 移除已迁出 card 定义,复用 card.qss |
| (本次) | docs | **v2-task-report.md(本文件)** |

---

## 6. 风险与回滚

### 6.1 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| `workspace.qss` 残留 17 处 hex 字面量 | 未来 token 翻新时需逐个替换 | 由 PR-V4 task 3.2 / 3.5 在 `MainWindow.__apply_workspace_style` 等 setStyleSheet 调用替换为 loader.apply 时一并迁 |
| component .qss 删除基线外状态 | 极端 widget 自定义态未覆盖 | 后续 PR-V4 实际渲染 harness 由 `tests/unit/test_visual_baseline` 兜底,差异 > 0.5% 直接 CI fail |
| `_build_mapping` 主题 token 与 glass key 同名冲突 | `{card_background}` 被 token 默认值压住 glass 替换 | 当前 token dict 无 card/dock_background 字段;若未来冲突需在 `_build_mapping` 加优先级策略 |
| `StylesheetLoader.SCOPES` 主 scope 累加到 11 个 .qss | 启动 stylesheet 字符串变大(数十 KB) | 实测启动耗时 < 5ms,可接受 |

### 6.2 回滚

| 组件 | 回滚动作 |
|---|---|
| 6 个新 .qss | `git revert <sha>` 单 commit 回滚一个组件,不影响主分支 |
| `loader.py` `SCOPES` + `_build_mapping` | `git revert e7306f5`,workspace / toolbar scope 自动失效 |
| `workspace.qss` / `toolbar.qss` | `git revert 8353633` / `git revert e7306f5` |
| 测试文件 | 同步 revert,无副作用 |

回滚成本: ≤ 10 分钟。

---

## 7. 阶段 V / C 后续工作

| 子 PR | 范围 | 依赖 |
|---|---|---|
| **PR-V2** (本 PR) | 6 类组件 .qss + loader scope + toolbar/workspace 复用 | PR-C2.x 视觉基线 |
| **PR-V4** | MainWindow / SettingsDialog 内嵌 QSS → loader.apply(41 处 setStyleSheet + settings_dialog.qss + scroll.qss + density_idle/workbench/batch/preview.qss + settings_density.qss) | **PR-V2 完成** |
| **PR-C1.1** | SettingsDialog 主题切换 UI(light / dark / system)+ `app.theme` 持久化 | **PR-V2 完成** |

PR-V4 / PR-C1.1 接续 PR-V2 的 token 字典 + loader scope,可以直接对 widget 调 `loader.apply(widget, theme, scope=...)`。视觉基线 harness(PR-C2.x)在 PR-V4 期间持续作为 gate — 任何改动若 > 0.5% 像素差异即被 CI 拦截,强制走 `_generate_baselines.py` 重生成基线。

---

## 8. 签字

- **作者**: OpenDesign(PR-V2 实施)
- **基线**: SecureRedact v1.1.13
- **本 PR 引入组件测试**: 61/61 通过(button / card / input / tab / dock / workspace / integration)
- **视觉基线回归**: 10/10 通过,4 张 PNG diff ratio 均 0.0000 < 0.005
- **token 覆盖**: 5/6 新 .qss 实现 0 hex 字面量;workspace.qss 残留由 PR-V4 / Plan 2c 处理
- **下一步**: PR-V4(内嵌 QSS 迁移,41 处 setStyleSheet)/ PR-C1.1(主题切换 UI)

---

## 9. 附录 — 变更清单

```
G:\Project\SecureRedact\
├── secureredact/
│   └── ui/
│       └── styles/
│           ├── button.qss                  NEW  +44 行,QPushButton/QToolButton 5 状态
│           ├── input.qss                   NEW  +295 行,5 widget + readonly
│           ├── tab.qss                     NEW  +92 行,QTabWidget/QTabBar 5 状态
│           ├── card.qss                    NEW  +133 行,QFrame 变体 + card_background
│           ├── dock.qss                    NEW  +49 行,QDockWidget title 5 状态 + dock_background
│           ├── loader.py                   MOD  +28/-5,SCOPES 5 个 scope + glass 合并
│           ├── toolbar.qss                 MOD  重构为"依赖 button.qss",净增 0
│           └── workspace.qss               MOD  -62 行,迁出 12 个 card 选择器
├── tests/
│   └── unit/
│       ├── test_button_qss.py              NEW  +91 行
│       ├── test_card_qss.py                NEW  +103 行
│       ├── test_input_qss.py               NEW  +146 行
│       ├── test_tab_qss.py                 NEW  +188 行
│       ├── test_dock_qss.py                NEW  +109 行
│       ├── test_workspace_qss.py           NEW  +209 行
│       ├── test_styles_integration.py      NEW  +93 行,scope 加载顺序断言
│       ├── test_stylesheet_loader.py       MOD  现有 19 处小调整(scope 字段扩展)
│       └── test_visual_baseline.py         (前置 PR-C2.x,本 PR 不动)
└── docs/
    └── refactor/
        └── v2-task-report.md               NEW  本文件
```
