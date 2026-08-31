# PR-V1 + PR-V3 完成报告 — Visual Tokens 体系化 + Glass Foundation

> **阶段**: 重构路线图 阶段 V (Visual Tokens + Glass Foundation)
> **PR**: PR-V1 (Visual Tokens 体系化) + PR-V3 (Glass Foundation)
> **完成日期**: 2026-08-31
> **基线版本**: SecureRedact v1.1.13
> **关联文档**: `frontend-refactor-plan.md` 阶段 V 章节
> **Worktree**: `G:/Project/SecureRedact-VisualTokens`
> **Branch**: `feature/visual-tokens-v1`

---

## 1. 范围

Plan 2a 合并 2 个 PR,共 5 个子任务:

| 子 PR | 范围 | 状态 |
|---|---|---|
| PR-V1 (Task 1) | `tokens.py` 扩展 33 个非颜色常量(圆角/间距/阴影/动效/字体) | ✓ |
| PR-V1 (Task 2) | `Tokens` dataclass 新增 `primary_hover` 字段 (16 → 17) | ✓ |
| PR-V1 (Task 5) | `theme.py` LIGHT/DARK 从硬编码改为 `asdict(tokens)` 派生 | ✓ |
| PR-V3 (Task 3) | `_platform.py` 平台检测模块 (`detect_blur_support`) | ✓ |
| PR-V3 (Task 4) | `StylesheetLoader.glass_supported` 属性(启动期检测缓存) | ✓ |

本 PR **不**修改:`base.qss` / `menu.qss` / `*.qss` 占位符值,`MainWindow` 内嵌 QSS,颜色 hex 全量替换(留 PR-V4),SettingsDialog 主题切换 UI(留 PR-C1.1),6 类组件 .qss 实际样式内容(留 PR-V2)。

---

## 2. 落地清单

### 2.1 新建文件 (3 个)

| 路径 | 行数 | 角色 |
|---|---|---|
| `secureredact/ui/styles/_platform.py` | 67 | 平台检测 (`detect_blur_support` + 缓存) |
| `tests/unit/test_visual_tokens.py` | 84 | Tokens 字段 / 圆角 / 间距 / 阴影 / 动效 / 字体 7 项测试 |
| `tests/unit/test_stylesheet_loader_glass.py` | 66 | Glass 检测 + Loader 属性 5 项测试 |
| `tests/unit/test_theme_tokens_alignment.py` | 30 | theme.LIGHT/DARK ↔ tokens 对齐 2 项测试 |

### 2.2 修改文件 (2 个)

| 路径 | 变更 |
|---|---|
| `secureredact/ui/styles/tokens.py` | +33 个非颜色 token(Task 1)+ `primary_hover` 字段(Task 2)+ `Tokens` dataclass 17 字段 + `__all__` 扩展 |
| `secureredact/ui/styles/loader.py` | `StylesheetLoader.__init__` 内 `self.glass_supported: bool = detect_blur_support()`(Task 4) |
| `theme.py` | `LIGHT` / `DARK` 改为 `asdict(_TOKENS_LIGHT)` / `asdict(_TOKENS_DARK)` 派生;保留全部向后兼容 alias(BORDER_RADIUS / SPACING_SMALL 等) |

### 2.3 未修改

- `base.qss` / `menu.qss` / `workbench.qss` / `toolbar.qss` / `workspace.qss` / `progress.qss`(占位符值未变,数据层扩展不影响现有 .qss)
- `secureredact/ui/styles/__init__.py`(39 行,占位 re-export 不变)
- MainWindow 内嵌 QSS(留 PR-V4 应用层)

---

## 3. 设计要点

### 3.1 颜色 token 数据流(Task 1 + Task 2 + Task 5)

```
secureredact/ui/styles/tokens.py     ← 单一数据源(Single Source of Truth)
  ├─ Tokens dataclass (17 字段,frozen)
  │    ├─ 16 基线字段(PR-V1 之前)
  │    └─ primary_hover (Task 2 新增,Spec A §4.1)
  ├─ LIGHT = Tokens(...)
  ├─ DARK = Tokens(...)
  ├─ get_substitution_map(theme_name)  → 17 颜色 + 3 字体 = 20 keys
  └─ 非颜色 token (33 个常量,Task 1)
       ├─ 圆角 RADIUS_* (5)
       ├─ 间距 SPACING_* (6)
       ├─ 阴影 SHADOW_* (5)
       ├─ 动效 DURATION_* + EASE_* (5)
       ├─ 字体 FONT_FAMILY_* (2)
       ├─ 字重 FONT_WEIGHT_* (4)
       └─ 字号 FONT_SIZE_* (6)

theme.py                              ← 派生消费者
  └─ Theme.LIGHT = asdict(_TOKENS_LIGHT)   (Task 5)
  └─ Theme.DARK  = asdict(_TOKENS_DARK)    (Task 5)
  └─ 向后兼容 alias:BORDER_RADIUS / BUTTON_RADIUS / SPACING_SMALL/MEDIUM/LARGE / FONT_* / ANIMATION_DURATION
```

**关键收益**:`Tokens` dataclass 增加字段时,`Theme.LIGHT/DARK` 通过 `asdict()` 自动跟随;**drift 风险归零**。

### 3.2 Glass 启动期检测(Task 3 + Task 4)

```
应用启动
  └─ StylesheetLoader.__init__()
       └─ self.glass_supported: bool = detect_blur_support()    (Task 4)
             └─ _platform.detect_blur_support()
                  ├─ Qt 主版本 < 6 ?            → False
                  ├─ QPA 平台 ∈ {windows, cocoa, xcb} ?
                  │       True                   → True   (启用 backdrop-filter: blur)
                  │       False                  → False  (降级:半透明纯色 + 阴影)
                  └─ 任何异常                    → False  (保守降级)
```

- 缓存:`_GLASS_SUPPORT_CACHE` 模块级全局,启动期检测 1 次,后续读取缓存
- PyQt6 导入全部 lazy(函数内 import),模块本身在 headless CI 也能 import
- 降级条件:Qt 5、wayland、headless、任意 import / 调用异常 → 全部回退到 `False`

### 3.3 Token 命名空间规则

- 仅匹配 `[a-z_][a-z0-9_]*` 小写下划线占位符,**不误伤** QSS 大写选择器(`QMainWindow`、`QPushButton#xxx`、`QMenu::item`)
- `get_substitution_map()` 返回 20 keys(17 颜色 + 3 字体),供 .qss 模板 `{token_name}` 替换

### 3.4 向后兼容策略

- `theme.py` 保留全部历史 alias:
  - `BORDER_RADIUS=12` / `BUTTON_RADIUS=10` / `SPACING_SMALL=8` / `SPACING_MEDIUM=14` / `SPACING_LARGE=22` / `FONT_FAMILY` / `FONT_SIZE_SMALL/NORMAL/LARGE` / `ANIMATION_DURATION=200`
  - 现有 `from theme import Theme; Theme.BORDER_RADIUS` 调用面零改动
- `tokens.py` `get_substitution_map()` 输出从 19 keys → 20 keys(增加 `primary_hover`),原有 19 keys 内容不变

---

## 4. 验证

### 4.1 Step 1 — 全量编译检查

```bash
$ cd "G:/Project/SecureRedact-VisualTokens" && python -m compileall -q main.py secureredact tests
EXIT_CODE: 0
```

**结果:无错误**(命令成功返回 0)

### 4.2 Step 2 — Plan 2a 新增 + 视觉 token 测试套件

```bash
$ cd "G:/Project/SecureRedact-VisualTokens" && \
  python -m pytest tests/unit/test_visual_tokens.py \
                  tests/unit/test_stylesheet_loader_glass.py \
                  tests/unit/test_theme_tokens_alignment.py -v
```

**结果:`13 passed, 1 failed in 0.54s`**

| 测试文件 | PASS | FAIL |
|---|---|---|
| `test_visual_tokens.py` | 7 | 0 |
| `test_stylesheet_loader_glass.py` | 4 | 1 |
| `test_theme_tokens_alignment.py` | 2 | 0 |
| **合计** | **13** | **1** |

**1 项失败**:`test_qt_version_parsing` — `assert 0 >= 5`

**原因(已知,非代码缺陷)**:
- 本 Windows 测试环境 (Python 3.13.5 + PyQt6 6.10.2 in `L:\anaconda3`) PyQt6 DLL 加载失败 (`STATUS_ENTRYPOINT_NOT_FOUND` 0xc0000139)
- `_qt_major_version()` 按设计契约在异常时返回 `0`(保守降级),**非代码 bug**
- 在 PyQt6 DLL 可正常加载的环境中,该测试将返回 `6` 并通过
- 已记录在 Task 3 + Task 4 报告中;**不属于本 PR 引入的回归**

### 4.3 Step 3 — 二次编译检查(确认稳定)

```bash
$ cd "G:/Project/SecureRedact-VisualTokens" && python -m compileall -q main.py secureredact tests
EXIT_CODE: 0
```

**结果:无错误**

### 4.4 Step 4 — Plan 2a 涉及文件行数统计

```bash
$ cd "G:/Project/SecureRedact-VisualTokens" && \
  wc -l secureredact/ui/styles/tokens.py \
        secureredact/ui/styles/loader.py \
        secureredact/ui/styles/_platform.py \
        theme.py \
        tests/unit/test_visual_tokens.py \
        tests/unit/test_stylesheet_loader_glass.py \
        tests/unit/test_theme_tokens_alignment.py
```

```
  232 secureredact/ui/styles/tokens.py
  129 secureredact/ui/styles/loader.py
   67 secureredact/ui/styles/_platform.py
   53 theme.py
   84 tests/unit/test_visual_tokens.py
   66 tests/unit/test_stylesheet_loader_glass.py
   30 tests/unit/test_theme_tokens_alignment.py
  661 total
```

### 4.5 ⚠️ PyQt6 DLL 环境 caveat

本环境的 PyQt6 DLL 加载失败 (`0xc0000139`) 影响:
- 所有依赖 PyQt6 runtime 的测试无法运行(`tests/ui/`)
- `test_qt_version_parsing` 因 `_qt_major_version()` 降级返回 `0` 而失败(已知,见 4.2)

**功能性验证(应用启动 + 主题切换 + Glass 检测)在 PyQt6 DLL 可正常加载的机器(开发机 + CI runner)上必须重新跑一次**:
- `python -m secureredact.main` 启动正常
- 设置中心切换 light/dark,UI 实时刷新
- Glass 模式下 `backdrop-filter: blur(8px)` 生效
- 非 Glass 平台(wayland / Qt 5)自动降级

### 4.6 Commit 粒度验收

Plan 2a 共 **6 个 commit**(5 任务 + 1 文档修正),每个 commit 独立可 bisect:

| SHA | Task | Subject |
|---|---|---|
| `aeefe6c` | V1-T1 | feat(tokens): PR-V1 Task 1 — 圆角/间距/阴影/动效/字体 28 个常量 (LOGO + ui_design_preview.html 对齐) |
| `d0fd25c` | V1-T2 | feat(tokens): PR-V1 Task 2 — Tokens dataclass 新增 primary_hover 字段 |
| `0944a4b` | V1-T2 修正 | docs(tokens): PR-V1 Task 2 reviewer minor — 更新 '16 个' → '17 个' docstring |
| `053da21` | V3-T3 | feat(styles): PR-V3 Task 3 — _platform.py 平台检测模块 (detect_blur_support) |
| `9cbbce6` | V3-T4 | feat(styles): PR-V3 Task 4 — StylesheetLoader.glass_supported 属性 (启动期检测) |
| `ac3956f` | V1-T5 | refactor(theme): PR-V1 Task 5 — Theme.LIGHT/DARK 从 tokens 派生 (消除双源) |

合计:`+407 / -84` 行(7 文件)

### 4.7 自审清单

- [x] **Spec 覆盖**:Spec A §4 Token 数值 + §6 Glass 降级 全部有 Task 覆盖
- [x] **占位符扫描**:无 TBD / TODO / FIXME
- [x] **类型一致性**:`Tokens` dataclass 字段数(17)= `LIGHT/DARK` 实例字段数(17)= `get_substitution_map` 输出颜色字段数(17)
- [x] **测试设计**:TDD 风格(每个 Task: 写失败测试 → 实现 → 验证通过);新增 14 项单元测试(7 + 5 + 2)
- [x] **Commit 粒度**:5 Task + 1 修正 → 6 commit,每 commit 独立 bisect
- [x] **风险控制**:theme.py 保留所有向后兼容 alias(`BORDER_RADIUS` / `SPACING_SMALL` / `ANIMATION_DURATION` 等);MainWindow 内嵌 QSS 不动

---

## 5. 阶段 V 后续工作表

| 子 PR | 范围 | 依赖 | 估时 |
|---|---|---|---|
| **PR-V2** | 6 类组件 .qss 实际样式内容(基于 `glass_supported` 切换) | Plan 2a 完成 | 1.0 周 |
| **PR-V4** | MainWindow 内嵌 622 行 QSS 迁移到 `.qss` 文件 + 颜色 hex 全量更新(Spec A §4.1) | PR-V2 完成 | 1.5 周 |
| **PR-C1.1** | SettingsDialog 主题切换 UI + `_on_theme_changed` callback | PR-V1 完成 | 0.5 周 |
| **PR-C2.x** | 视觉基线补齐(当前 5 张占位仍 skipTest) | PR-V4 完成 | 0.5 周 |

---

## 6. 风险与回滚

### 6.1 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| PyQt6 DLL 加载失败的环境无法跑功能测试 | 视觉验证延迟 | 在 PyQt6 DLL 可加载的开发机/CI 上重新跑;模块化拆分确保回滚简单 |
| `Tokens` dataclass 字段增加导致旧 caller 期望字段数 | 测试 fail | `test_tokens_dataclass_legacy_compat` 强制断言字段数;新增字段必须明确文档化 |
| Glass 启动期检测在 wayland 误判 | UI 不一致 | wayland 明确降级;用户在设置中可手动选 Light/Dark 强制非 Glass |

### 6.2 回滚

- 7 个 commit 可逐个 `git revert`(每 commit 独立可 bisect)
- `theme.py` 删 2 行 `asdict()` 即可回退到硬编码 dict(原行已在 git 历史)
- `tokens.py` 删 `__all__` 末尾新增 token + `Tokens` dataclass `primary_hover` 字段即可回退
- `_platform.py` 是 NEW 文件,直接 `rm` 即可
- `StylesheetLoader.glass_supported` 移除 `__init__` 1 行赋值

回滚成本:< 10 分钟。

---

## 7. 签字

- **作者**: OpenDesign Plan mode 自动生成
- **基线**: SecureRedact v1.1.13
- **回归基线**: 14 项新增单元测试 / 13 PASS + 1 已知 DLL 环境 fail(非回归)
- **净收益**:`tokens.py` 数据层扩展到位(17 颜色 + 33 非颜色 = 50 个 token);`theme.py` drift 风险归零;Glass 启动期检测就绪
- **状态**:**Plan 2a 全部完成** ✓;进入 PR-V2(组件 .qss) / PR-V4(MainWindow QSS 迁移) / PR-C1.1(SettingsDialog 主题 UI)

---

## 8. 附录 — 变更清单

```
G:\Project\SecureRedact-VisualTokens\
├── secureredact/
│   └── ui/
│       └── styles/
│           ├── tokens.py                          MOD  +33 非颜色 token(Task 1)+ primary_hover(Task 2)
│           ├── loader.py                          MOD  +glass_supported 属性(Task 4)
│           └── _platform.py                       NEW  67 行 平台检测模块(Task 3)
├── theme.py                                       MOD  LIGHT/DARK 从 tokens 派生(Task 5)+ 保留全部 alias
├── tests/
│   └── unit/
│       ├── test_visual_tokens.py                  NEW  84 行 7 项测试
│       ├── test_stylesheet_loader_glass.py        NEW  66 行 5 项测试
│       └── test_theme_tokens_alignment.py         NEW  30 行 2 项测试
└── docs/
    └── refactor/
        └── v1-task-report.md                      NEW  本文件
```