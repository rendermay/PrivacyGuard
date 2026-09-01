# SecureRedact 视觉风格决策 — 设计 Spec

> **Brainstorming session:** 2026-08-30
> **Spec owner:** OpenDesign
> **Status:** Draft (待用户审阅)
> **后续:** 经用户批准后进入 writing-plans 阶段产出实施 plan

---

## 1. 背景与问题陈述

### 1.1 当前现状

SecureRedact v1.1.13+ 的视觉系统存在**方向漂移**：

| 资产 | 实际风格 | 应有风格（已有指南） |
|------|---------|---------------------|
| `theme.py` LIGHT 字典 | `#0F6CBD` Microsoft 浅蓝灰 | `#2563EB` 信任蓝（LOGO_DESIGN_GUIDE.md） |
| `tokens.py` dataclass | 同上 + 16 token 字段 | LOGO + ui_design_preview.html 的 30+ token |
| `theme.py` DARK 字典 | `#151C26` 自定深色 | `#0F172A` Slate-900（LOGO 推荐） |
| `MainWindow._apply_light_theme()` | 内嵌 622 行 QSS | 应收敛到 .qss + token |
| `MainWindowThemeMixin` (PR-C1) | light/dark/system 三模式 | ✅ 已就位 |
| `SettingsDialog` 主题切换 UI | ❌ 缺 | PR-C1.1 待做 |
| 视觉基线 | 5/8 skipTest | 应补齐 |
| 组件层抽象 | ❌ 无 | 应有 Button/Input/Tab/Card/Dock/Toolbar 6 类 |

### 1.2 已有的设计资产（无需重新设计）

- **`LOGO_DESIGN_GUIDE.md`**：色彩规范（信任蓝 #2563EB / 安全绿 #10B981 / 警示橙 #F59E0B / 深邃黑 #0F172A）+ 图标规格（macOS 22.5% 圆角）+ 关键词（安全 / 隐私 / 专业 / 亲和力 / 圆润）+ 参考（钉钉 / 企业微信 / 飞书 / 现代扁平化）
- **`ui_design_preview.html`**：完整的设计语言定义（CSS 变量 + 6 级阴影含 glow + 24px 大圆角 + cubic-bezier 过渡）
- **`assets/branding/v38/`**：已生成的 5 个功能图标 SVG（batch_word / feedback_support / image_merge_pdf / pdf_redaction / settings_advanced）

### 1.3 漂移的代价

- 当前 UI 是 "Windows-first 浅色办公风"，与品牌资产"现代扁平 + 亲和力 + 圆润"严重不符
- 视觉基线 5 张 skipTest，**没有任何视觉回归保护**
- 主题切换 UI 缺位（PR-C1 已就绪 backend，但用户无切换入口）
- 组件样式散落在 `MainWindow._apply_light_theme()` 622 行内嵌 QSS，无法复用、无法测试

---

## 2. 目标与非目标

### 2.1 目标（Spec A — 风格方向决策）

1. **收敛设计方向**：让 `tokens.py` / `theme.py` / `.qss` / `MainWindow._apply_*_theme()` 完全对齐 LOGO_DESIGN_GUIDE.md + ui_design_preview.html
2. **建立完整设计 token 体系**：从 16 颜色 token 扩展到 30+ token（含间距 / 圆角 / 阴影 / 动效 / 字体）
3. **抽象 6 类标准组件**：Button / Input / Tab / Card / Dock / Toolbar，每类 5 状态（normal / hover / pressed / disabled / focused）
4. **定义 Glass 降级路径**：在不支持 backdrop-filter 的平台（PyQt6 老版本、Linux 某些 WMs），自动回退到半透明纯色 + 加阴影
5. **建立视觉基线**：Playwright 截图覆盖 main window / settings dialog / 主题切换 / light & dark / 4 断点

### 2.2 非目标（明确不做）

1. **不重新设计 LOGO / 品牌色板**（已有 LOGO_DESIGN_GUIDE.md 是单一来源）
2. **不切换 GUI 技术栈**（保留 PyQt6）
3. **不做完整 design system 网站 / Storybook**（PyQt6 没有等价物）
4. **不做动效库**（仅在 QSS 中使用 cubic-bezier，无 JS 动效）
6. **不重做图标资产**（已有 v38 branding）
5. **不做交互模式重设计**（保留当前 Dock / Tab / 双栏预览的交互架构）

---

## 3. 核心决策（Brainstorming 输出）

| 维度 | 决策 | 理由 |
|------|------|------|
| **范围** | Spec A — 风格方向决策 | Spec B/C/D 后续单独 brainstorm |
| **基线对齐** | 对齐 LOGO_DESIGN_GUIDE.md + ui_design_preview.html | 团队已投入 2 份设计稿，最小风险路径 |
| **Approach** | Approach 1（Dark + 微 Glass） | 与 LOGO/UI 设计指南 100% 对齐 |
| **组件** | 6 类（Button / Input / Tab / Card / Dock / Toolbar） | 覆盖全部高频 widget |
| **Glass 降级** | 半透明纯色 + 加阴影 | 视觉差异极小，PyQt6 兼容 100% |
| **验证** | Playwright 截图回归 | 主路径，符合 testing.md 优先级 |

---

## 4. 设计 Token 完整数值

### 4.1 颜色 Token（16 个 + 1 个新增）

#### 4.1.1 Light（暖白办公版）

| Token | 旧值 | 新值 | 来源 |
|-------|------|------|------|
| `background` | `#F7F8FA` | `#FAFAFA` | Tailwind Slate-50 |
| `surface` | `#FFFFFF` | `#FFFFFF` | 不变 |
| `primary` | `#0F6CBD` | `#2563EB` | LOGO 信任蓝 Blue-600 |
| `primary_hover` | — | `#1D4ED8` | LOGO Blue-700（新增） |
| `secondary` | `#5F6B7A` | `#475569` | Tailwind Slate-600 |
| `accent` | `#0FA968` | `#10B981` | LOGO 安全绿 Emerald-500 |
| `text` | `#18212F` | `#0F172A` | LOGO Slate-900 |
| `text_secondary` | `#5F6B7A` | `#64748B` | Tailwind Slate-500 |
| `border` | `#E2E8F0` | `#E2E8F0` | 不变 |
| `shadow` | `rgba(18,31,53,0.10)` | `rgba(15,23,42,0.08)` | 微调 |
| `info_bar` | `#F9FBFD` | `#F8FAFC` | 微调 |
| `scroll_area` | `#F6F8FB` | `#F1F5F9` | Tailwind Slate-100 |
| `hover` | `#EEF4FB` | `#F1F5F9` | 微调 |
| `pressed` | `#E3ECF8` | `#E2E8F0` | 微调 |
| `success` | `#0FA968` | `#10B981` | LOGO |
| `danger` | `#D64545` | `#EF4444` | LOGO Red-500 |
| `warning` | `#D9831F` | `#F59E0B` | LOGO Amber-500 |

#### 4.1.2 Dark（默认 / LOGO 主推）

| Token | 旧值 | 新值 | 来源 |
|-------|------|------|------|
| `background` | `#151C26` | `#0F172A` | LOGO Slate-900 |
| `surface` | `#1E2836` | `#1E293B` | Tailwind Slate-800 |
| `primary` | `#56A8FF` | `#3B82F6` | LOGO Blue-500 |
| `primary_hover` | — | `#2563EB` | Blue-600（新增） |
| `secondary` | `#9AA8BA` | `#94A3B8` | Tailwind Slate-400 |
| `accent` | `#34D399` | `#34D399` | 不变 |
| `text` | `#F6F8FC` | `#F8FAFC` | 微调 |
| `text_secondary` | `#AAB5C5` | `#94A3B8` | 微调 |
| `border` | `#324255` | `rgba(148,163,184,0.18)` | 半透明 Slate |
| `shadow` | `rgba(0,0,0,0.30)` | `rgba(0,0,0,0.40)` | 加深 |
| `info_bar` | `#1E2A3B` | `#1E293B` | 微调 |
| `scroll_area` | `#1A2330` | `#0F172A` | 纯 Slate-900 |
| `hover` | `#263241` | `rgba(59,130,246,0.12)` | 蓝调 hover |
| `pressed` | `#314155` | `rgba(59,130,246,0.20)` | 蓝调 pressed |
| `success` | `#34D399` | `#34D399` | 不变 |
| `danger` | `#FF6B6B` | `#F87171` | Tailwind Red-400 |
| `warning` | `#FFB454` | `#FBBF24` | Tailwind Amber-400 |

### 4.2 圆角 Token（5 级）

```python
RADIUS_SM = 6          # 标签 / chip
RADIUS_MD = 10         # 按钮 / 输入框
RADIUS_LG = 16         # 卡片 / dock 容器
RADIUS_XL = 24         # 主面板容器
RADIUS_PILL = 999      # 头像 / 徽章
```

来源：`ui_design_preview.html` `--radius-sm: 6px; --radius-md: 10px; --radius-lg: 16px; --radius-xl: 24px;`

### 4.3 间距 Token（8 进制 / 6 级）

```python
SPACING_XS = 4         # 内边距微调
SPACING_SM = 8         # 紧凑布局
SPACING_MD = 14        # 标准间距（按钮内边距、表单字段间距）
SPACING_LG = 22        # 区块间距
SPACING_XL = 32        # section 大间距
SPACING_2XL = 48       # 页面顶部 / 大留白
```

迁移映射：
- `SPACING_SMALL = 8` → `SPACING_SM`
- `SPACING_MEDIUM = 14` → `SPACING_MD`
- `SPACING_LARGE = 22` → `SPACING_LG`

### 4.4 阴影 Token（4 级 + glow）

```python
SHADOW_SM = "0 1px 2px rgba(0,0,0,0.06)"
SHADOW_MD = "0 4px 6px -1px rgba(0,0,0,0.10), 0 2px 4px -2px rgba(0,0,0,0.10)"
SHADOW_LG = "0 10px 15px -3px rgba(0,0,0,0.10), 0 4px 6px -4px rgba(0,0,0,0.10)"
SHADOW_XL = "0 20px 25px -5px rgba(0,0,0,0.10), 0 8px 10px -6px rgba(0,0,0,0.10)"
SHADOW_GLOW = "0 0 40px rgba(37,99,235,0.30)"     # 仅 Dark 主题
```

来源：`ui_design_preview.html` 完整定义；`SHADOW_GLOW` 仅 Dark 主题生效（避免在浅色背景发光突兀）。

### 4.5 动效 Token（3 duration + 2 ease）

```python
DURATION_FAST = 150    # hover / press 反馈
DURATION_NORMAL = 200  # 默认过渡
DURATION_SLOW = 300    # 页面切换 / 抽屉动画

EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)"        # 弹性出口（适合入场）
EASE_IN_OUT = "cubic-bezier(0.4, 0, 0.2, 1)"     # 平滑（适合状态切换）
```

迁移映射：
- `ANIMATION_DURATION = 200` → `DURATION_NORMAL`

### 4.6 字体 Token（2 family + 4 weight + 6 size）

```python
FONT_FAMILY_DISPLAY = "'Inter', 'Segoe UI Variable', 'PingFang SC', sans-serif"
FONT_FAMILY_BODY = "'Inter', 'Segoe UI Variable', 'Microsoft YaHei UI', sans-serif"

FONT_WEIGHT_REGULAR = 400
FONT_WEIGHT_MEDIUM = 500
FONT_WEIGHT_SEMIBOLD = 600
FONT_WEIGHT_BOLD = 700

FONT_SIZE_XS = 11      # 极小（仅时间戳 / 标记）
FONT_SIZE_SM = 12      # 副文本
FONT_SIZE_BASE = 14    # 正文
FONT_SIZE_LG = 18      # 小标题
FONT_SIZE_XL = 24      # 标题
FONT_SIZE_2XL = 32     # 大标题
```

迁移映射：
- `FONT_SIZE_SMALL = 12` → `FONT_SIZE_SM`
- `FONT_SIZE_NORMAL = 14` → `FONT_SIZE_BASE`
- `FONT_SIZE_LARGE = 18` → `FONT_SIZE_LG`

---

## 5. 6 类标准组件样式规格

### 5.1 通用 5 状态

| 状态 | 触发条件 | 视觉变化 |
|------|---------|----------|
| `normal` | 默认 | 主背景 + 主文字 |
| `hover` | 鼠标悬停 | 背景切到 `hover`，文字不变 |
| `pressed` | 鼠标按下 | 背景切到 `pressed`，文字不变 |
| `focused` | 键盘 / 点击聚焦 | 加 2px `primary` 边框 |
| `disabled` | `widget.setEnabled(False)` | 透明度 0.4，所有交互禁用 |

### 5.2 组件清单与核心差异

| 组件 | 容器圆角 | 主样式 | 备注 |
|------|---------|--------|------|
| **Button** | `RADIUS_MD` | 填充主色（primary），hover 切 `primary_hover` | 区分 primary / secondary / ghost 三种 variant |
| **Input** | `RADIUS_MD` | 透明背景 + 1px `border`，focused 切 `primary` 边框 + 加 `SHADOW_SM` glow | 含 TextInput / NumberInput / FilePathInput |
| **Tab** | `RADIUS_PILL` | selected 态填充 `primary` alpha=0.15 + 主色文字；unselected 透明 | 横向 + 竖向两种 |
| **Card** | `RADIUS_LG` | `surface` 背景 + `SHADOW_MD` | hover 升 `SHADOW_LG` |
| **Dock** | `RADIUS_XL` | 半透明 `surface` alpha=0.85 + `SHADOW_LG` + backdrop-filter blur(8px) | 主面板 dock 容器 |
| **Toolbar** | `RADIUS_MD` | 半透明 `info_bar` alpha=0.85 + backdrop-filter blur(8px) | 顶部工具条 |

### 5.3 Glass 降级

仅 **Dock / Toolbar** 使用 Glass 效果。

```css
/* 标准 Glass */
background-color: rgba(surface_rgb, 0.85);
backdrop-filter: blur(8px);
-webkit-backdrop-filter: blur(8px);    /* macOS Safari/WebKit */

/* 降级后（detect_blur_support() 返回 False） */
background-color: rgba(surface_rgb, 0.92);    /* alpha 稍高补偿 */
box-shadow: SHADOW_LG;                        /* 加重阴影补深度 */
```

降级触发条件（启动时检测一次）：
- Qt < 6.5
- 平台为 Wayland（部分合成器不支持 backdrop-filter）
- 老 X11（无合成器）
- Win 7（无 DWM）

降级日志：单次启动期打印 `[INFO] Glass 降级到半透明纯色 (Qt X.Y / platform)`

---

## 6. Glass 降级路径

### 6.1 降级逻辑

```python
# secureredact/ui/styles/_platform.py（新建）
from PyQt6.QtCore import QT_VERSION_STR

def _resolve_qpa_platform() -> str:
    """检测当前 QPA 平台 (windows / cocoa / xcb / wayland)。"""
    from PyQt6.QtGui import QGuiApplication
    return QGuiApplication.platformName().lower()

def detect_blur_support() -> bool:
    """启动期检测 backdrop-filter 支持。
    
    Returns:
        True: 启用 Glass (backdrop-filter: blur(8px))
        False: 降级到半透明纯色 + 加阴影
    """
    major = int(QT_VERSION_STR.split('.')[0])
    if major < 6:
        return False
    platform = _resolve_qpa_platform()
    # 仅这些平台稳定支持 backdrop-filter
    return platform in ("windows", "cocoa", "xcb")
```

### 6.2 QSS 模板占位符

在 `tokens.py` 增加 `glass_supported` 布尔字段；`StylesheetLoader.render()` 根据该值决定输出的 Dock/Toolbar QSS 块。

### 6.3 降级日志

启动期检测结果记入 `[INFO]` 日志，用户在 `logs/` 目录可见。

---

## 7. 视觉验证策略（Playwright 截图回归）

### 7.1 测试覆盖矩阵

| 场景 | Light | Dark | 断点 |
|------|-------|------|------|
| **Main window（默认空文档）** | ✅ | ✅ | 1024 / 1440 |
| **Main window（PDF 加载 + 高亮）** | ✅ | ✅ | 1024 / 1440 |
| **Main window（Word 双栏预览）** | ✅ | ✅ | 1024 / 1440 |
| **Settings dialog（未打开主题 UI）** | ✅ | ✅ | — |
| **Settings dialog（展开主题 radio）** | ✅ | ✅ | — |
| **Feedback dialog** | ✅ | ✅ | — |
| **ImageList dialog** | ✅ | ✅ | — |
| **Word replace rules dialog** | ✅ | ✅ | — |

合计：8 场景 × 2 主题 × 2 断点（部分）= ~20 张截图

### 7.2 测试实施

工具：`pytest-qt`（已有） + `pytest-playwright`（新增）
基线存储：`tests/ui/baseline/*.png`
差异容忍：`pixelmatch` < 0.5%

```python
# tests/ui/test_visual_baseline.py（新建 / 替换现有 5 张 skipTest）
import pytest
from playwright.sync_api import sync_playwright

@pytest.mark.visual
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_main_window_default(theme):
    """主窗口默认状态截图回归。"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"app://main?theme={theme}")
        page.screenshot(path=f"tests/ui/baseline/main_window_{theme}.png")
        # 后续: 与 baseline 对比, pixelmatch < 0.5%
```

### 7.3 CI 集成

GitHub Actions（PR-C7 task 4.3 已配置）新增 visual-baseline job：
```yaml
- name: Visual baseline regression
  run: pytest tests/ui -v -m visual
```

---

## 8. 范围与依赖（Spec A 在整个视觉层重做的位置）

```
Spec A (本文件) ─── 设计 token + 6 组件样式 + Glass 降级 + 验证策略
        ↓ 输出
        ├─ Spec B: Design system 实施 (PR-V1/V2/V3)
        │   ├─ PR-V1: tokens.py 体系化 (本 spec §4 全量落地)
        │   ├─ PR-V2: 6 个标准组件 .qss (本 spec §5 全量落地)
        │   ├─ PR-V3: StylesheetLoader 加 glass_supported 分支
        │   └─ PR-V4: 6 类组件接入现有 MainWindow (替换 _apply_light_theme 622 行)
        ├─ Spec C: 主题切换 UI (PR-C1.1)
        │   └─ SettingsDialog 加主题 radio + _on_theme_changed callback
        └─ Spec D: 视觉基线 (PR-C2.x)
            └─ Playwright 截图回归 8 场景 × 2 主题 × 2 断点
```

依赖关系：
- Spec B 依赖 Spec A（本 spec）
- Spec C 依赖 Spec A + Spec B（需要 tokens + 组件层就绪）
- Spec D 依赖 Spec A + Spec B（需要新设计生效才能截图）

---

## 9. 风险与回滚

### 9.1 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| **Glass 在某些平台失效** | 中 | 视觉降级 | detect_blur_support() + 降级路径已设计 |
| **DARK 主题让 OCR 标识对比度下降** | 中 | 功能性 | OCR 标识沿用 `danger` 红（#EF4444 / #F87171），亮度对比 ≥4.5:1 |
| **字体加载在老 Win 缺 Inter** | 中 | 视觉降级到 Segoe UI Variable | font-family fallback 链已设计 |
| **Playwright 在 Windows headless 不可用** | 低 | 测试阻塞 | 视觉测试 CI job 标注为非阻塞，允许本地手测 |
| **main_window 内嵌 622 行 QSS 替换引入回归** | 中 | UI 异常 | 视觉基线 + 439 单元回归双保险 |

### 9.2 回滚路径

| 回滚点 | 操作 |
|--------|------|
| **tokens.py 回滚** | `git revert <commit-hash>` 一键回滚到 v1.1.13 baseline |
| **组件 QSS 回滚** | 同上 |
| **Glass 降级** | 启动时打印的 `[INFO]` 日志 + `detect_blur_support()` 返回值，便于事后回溯 |
| **视觉基线回滚** | 删除 `tests/ui/baseline/*.png` 后回滚 spec D 的 PR |

---

## 10. 验收标准（Definition of Done）

### 10.1 必须满足

- [ ] `tokens.py` 包含 §4 全部 token（颜色 + 圆角 + 间距 + 阴影 + 动效 + 字体）
- [ ] `theme.py` 移除重复常量（保留 `get_tokens` / `get_substitution_map` 的转接层）
- [ ] 6 个标准组件 .qss 文件（Button / Input / Tab / Card / Dock / Toolbar）落地到 `secureredact/ui/styles/components/`
- [ ] `StylesheetLoader` 支持 `glass_supported` 分支（True / False 两套输出）
- [ ] `detect_blur_support()` 启动期检测 + 降级日志
- [ ] `MainWindow._apply_light_theme()` 622 行内嵌 QSS 全部迁移到 6 个组件 .qss
- [ ] 视觉基线 8 场景 × 2 主题共 16 张截图全部 pass
- [ ] 439 单元测试 0 新失败

### 10.2 不在 Done 范围内

- SettingsDialog 主题切换 UI（Spec C / PR-C1.1）
- 单元测试补充覆盖组件（Spec D 之后单独 plan）
- 用户使用手册 / 产品介绍页面同步更新（独立 PR）

---

## 11. 签字

- **Brainstorming 完成日期**：2026-08-30
- **Spec 范围**：Spec A（风格方向决策）
- **Spec 基线**：SecureRedact v1.1.14
- **后续阶段**：经用户批准 → writing-plans 阶段产出实施 plan
- **下游 Spec**：B (Design system 实施) / C (主题切换 UI) / D (视觉基线) 各自独立 brainstorm

---

## 附录 A — 决策追溯

| 决策点 | 选项 | 选定 | 理由 |
|--------|------|------|------|
| 范围 | A / A+B / A+场景 / 1-2 页面 | A | 设计一切的起点，避免在 tokens 上反复返工 |
| 基线 | 对齐 LOGO / 重起 / LOGO+运动 | 对齐 LOGO | 最小风险路径，已有 2 份设计稿 |
| Approach | 1 / 2 / 3 | Approach 1 | 与 ui_design_preview.html 100% 对齐 |
| 组件 | 4 / 5 / 6 | 6 类 | Button/Input/Tab/Card/Dock/Toolbar |
| Glass 降级 | 半透明纯色+阴影 / 完全实心 / 设置中心开关 | 半透明纯色+阴影 | 视觉差异极小，老平台 100% 兼容 |
| 验证 | Playwright / 截图+单元 / 手工对比 | Playwright | testing.md 优先级最高 |