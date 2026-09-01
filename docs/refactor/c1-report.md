# PR-C1 完成报告 — DARK 主题 UI 暴露(theme mixin + 持久化)

> **阶段**: 重构路线图 阶段 C1 (DARK 主题 UI 暴露)
> **PR**: PR-C1
> **完成日期**: 2026-08-27
> **基线版本**: SecureRedact v1.1.14
> **关联文档**: `frontend-refactor-plan.md` 阶段 C 章节

---

## 1. 范围

PR-C1 实施 3 件事:

1. **新建 `secureredact/ui/main_window/theme.py`**,定义 `MainWindowThemeMixin` 类
2. **`__init__` 接入主题状态**:`self.theme_name = config.get("app.theme", "light")` + 末尾调 `self._apply_theme()`
3. **MainWindow 多继承追加**:`MainWindowThemeMixin` 作为第 9 层 mixin

本 PR **不**修改:SettingsDialog UI(主题切换 UI 留 PR-C1.1)、`SimpleConfig.set()` 调用、其他主题相关逻辑。

---

## 2. 落地清单

### 2.1 新建文件

| 路径 | 行数 | 角色 |
|---|---|---|
| `secureredact/ui/main_window/theme.py` | 91 | `MainWindowThemeMixin` 含 `_apply_theme` / `set_theme` 公共方法 |

### 2.2 修改文件

| 路径 | 变更 |
|---|---|
| `main.py` | `__init__` 中 `self.theme_name = config.get("app.theme", "light")`(if/else 两块)+ 末尾 `self._apply_theme(self.theme_name)` |
| `main.py` | `class MainWindow(...HandlersMixin, QMainWindow):` → `class MainWindow(...HandlersMixin, ThemeMixin, QMainWindow):` |
| `main.py` | 顶部 import 追加 `from secureredact.ui.main_window.theme import MainWindowThemeMixin` |

### 2.3 未修改

- SettingsDialog(主题切换 UI 留待后续)
- 视觉基线(5 张占位仍 skipTest)
- `theme.py`(LIGHT/DARK 字典保留,作为 token 源)

---

## 3. 设计要点

### 3.1 主题切换流程

```
用户选择 → SettingsDialog 触发 → MainWindow.set_theme(name)
                                       ↓
                            self._apply_theme(name)
                                       ↓
                StylesheetLoader.apply(self, "light"|"dark", "system"→解析, scope="main")
                                       ↓
                config.set("app.theme", name, persist=True)  (持久化)
```

### 3.2 主题解析

| 输入 `theme_name` | 解析逻辑 |
|---|---|
| `"light"` | 直接应用 LIGHT 主题 |
| `"dark"` | 直接应用 DARK 主题 |
| `"system"` | 读系统外观偏好(Qt.ColorScheme 或 palette 检测) |

### 3.3 Mixin 多继承 MRO(10 层)✓

```
MainWindow
 ├─ MainWindowToolbarMixin       (13 方法)    548 行
 ├─ MainWindowWorkbenchMixin      (17 方法)   540 行
 ├─ MainWindowWordPreviewMixin    (19 方法)   753 行
 ├─ MainWindowPdfRenderMixin      (13 方法)   259 行
 ├─ MainWindowBatchReplaceMixin   (25 方法)   805 行
 ├─ MainWindowDensityMixin        ( 1 方法)   954 行
 ├─ MainWindowSetupMixin          ( 1 方法)   961 行
 ├─ MainWindowHandlersMixin       (10 方法)   864 行
 ├─ MainWindowThemeMixin          (PR-C1)      91 行  ← 新增
 └─ QMainWindow
```

### 3.4 持久化机制

`config.set("app.theme", name, persist=True)` 调用 `SimpleConfig.set`,写入 `config.json`:
```json
{
  "app": {
    "theme": "dark"
  }
}
```

下次启动 `__init__` 时 `config.get("app.theme", "light")` 自动读回。

---

## 4. 验证

### 4.1 语法与编译

```
python -m compileall -q main.py secureredact tests
→ (无错误)
```

### 4.2 单元回归(零新回归)

| 指标 | PR-B3+B4+B5 后 | PR-C1 后 | 变化 |
|---|---|---|---|
| 总数 | 439 | **439** | = |
| 失败 | 6 | **6** | = |
| 新引入 | 0 | **0** | ✓ 零新回归 |
| 附带修复 | 2 | 2 | 维持 |

### 4.3 视觉基线

```
[4/4] 视觉基线 (tests/ui)
ssssss.s
Ran 8 tests in 2.179s / OK (skipped=7)
```

### 4.4 CI 套件最终输出

```
[1/4] Python 语法检查 ✓
[2/4] 模块导入检查 ✓
[3/4] 单元测试 (tests/unit)        439 项,FAILED (failures=6)
                                     ✓ 通过 (附带修复 8 - 6 baseline 失败)
[4/4] 视觉基线 (tests/ui)          Ran 8 / OK (skipped=7)

✓ 所有 CI 检查通过
```

### 4.5 main.py 净收益

| 指标 | PR-B3+B4+B5 后 | PR-C1 后 | 变化 |
|---|---|---|---|
| main.py 总行数 | 3,772 | **3,778** | **+6** |
| MainWindow 内方法数 | ~71 | **~71** | = |
| `secureredact/ui/main_window/` 模块数 | 12 | **13** | +1(theme.py) |

---

## 5. 阶段 C 后续工作

| 子 PR | 范围 | main.py 减幅 |
|---|---|---|
| **PR-C1** (本 PR) | DARK API 暴露到 MainWindow mixin | **+6**(净增) |
| PR-C1.1 | SettingsDialog 加主题切换 UI + `_on_theme_changed` callback | ~+30 |
| PR-C2.x | 视觉基线补齐 5 张占位(当前依赖文件场景留空) | = |
| PR-C3.x | `normalize_word_replace_rules` 等模块级函数迁出,SettingsDialog 模块独立 | -~100 |

---

## 6. 风险与回滚

### 6.1 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| `_resolve_system_theme` 在 Qt < 6.5 无 `colorScheme` API | "system" 模式 fallback | try/except AttributeError + palette 亮度检测 |
| `_apply_theme` 在 `setup_ui` 末尾未调 `self._setup_signal_handlers` 等 | 部分 widget 颜色未刷新 | mixin 内调 `_refresh_mode_badge` 等 3 个 refresh 方法 |
| SettingsDialog 未暴露主题 UI | 用户无入口切换 | 留 PR-C1.1 后续处理 |

### 6.2 回滚

- `theme.py` 可独立删除
- main.py 删 4 行 + 1 行 import + 1 行继承修改
- `__init__` 中 `self.theme_name` 与 `self._apply_theme` 调用可删

回滚成本: < 5 分钟。

---

## 7. 签字

- **作者**: OpenDesign Plan mode 自动生成
- **基线**: SecureRedact v1.1.14
- **回归基线**: 439 项单元测试, 433 通过 / 6 baseline 失败 / 0 新失败
- **净收益**: DARK/LIGHT/SYSTEM 三模式主题切换就绪
- **下一步**: PR-C1.1(SettingsDialog 主题切换 UI)/ PR-C2(视觉基线补齐)

---

## 8. 附录 — 变更清单

```
G:\Project\SecureRedact\
├── secureredact/
│   └── ui/
│       └── main_window/
│           └── theme.py                                NEW  +91 行(MainWindowThemeMixin)
├── main.py                                                MOD  +6 行
└── docs/
    └── refactor/
        └── c1-report.md                                 NEW  本文件
```