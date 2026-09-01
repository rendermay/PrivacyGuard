"""SecureRedact 视觉回归基线 (Visual Regression Baselines)

PR-B0 引入,跟随 UI 重构路线图(参见 `frontend-refactor-plan.md` 阶段 B0)。

## 作用

防止 QSS 调整、组件拆分、token 重命名等 UI 改动引入**视觉回归** —
肉眼不易察觉的偏移、间距错位、颜色错乱,在像素级比对下立即可见。

## 工作原理

```
                 ┌─────────────────────┐
                 │ BaselineScreenshot  │
                 │ Test.build_widget() │
                 └──────────┬──────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │ QWidget.grab() 截屏  │
                └──────────┬───────────┘
                           │
              ┌────────────┴─────────────┐
              ▼                          ▼
   tests/ui/actual/<name>.png   tests/ui/baselines/<name>.png
   (实拍,永远落盘)              (基线,人工审定)
              │                          │
              └──────────┬───────────────┘
                         ▼
              逐像素 RGB 比对 + 容差
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
           PASS                  FAIL
```

## 6 张基线截图

| 名称 | 场景 | 关键覆盖点 |
|---|---|---|
| `01_idle_main_window` | 主窗口空态 | workbench 上下文条 + 工具栏默认态 + 拖放引导 |
| `02_pdf_single_page` | 打开 PDF 单页 | canvas 渲染 + 命中红框 + 工具栏切换态 |
| `03_word_dual_preview` | Word 双栏预览 | 左原右替布局 + 高亮 + 滚动同步 |
| `04_settings_dialog_overview` | 设置首屏 | 规则面板 + 卡片布局 + 导航侧栏 |
| `05_batch_replace_results` | 批替换结果 | 表格行 + 过滤按钮 + 成功/失败分组 |
| `06_word_replace_rules` | Word 替换规则编辑器 | 表格 + 操作按钮 + JSON 导入/导出 |

## 运行命令

```bash
# 常规视觉回归(必须有基线)
python -m unittest tests.ui.baseline_screenshots

# 容差比对(跨平台 CI 推荐)
BASELINE_TOLERANCE=4 python -m unittest tests.ui.baseline_screenshots

# 写基线模式(人工审定后跑一次)
PRIVACYGUARD_WRITE_BASELINES=1 python -m unittest tests.ui.baseline_screenshots

# 仅跑某一帧
python -m unittest tests.ui.baseline_screenshots.IdleMainWindowTest
```

## CI 集成

`tests/scripts/test.sh` 已加入:

```bash
python -m unittest tests.ui.baseline_screenshots -v 2>&1
```

需要在有图形环境运行(CI 上用 Xvfb):

```bash
xvfb-run -a python -m unittest tests.ui.baseline_screenshots
```

## 约束

- 基线 PNG 一旦审定,任何视觉改动都必须**先过 PR 评审**才能 `WRITE_BASELINES`
- `actual/` 目录不进版本控制(.gitignore 已加)
- DPI 缩放、字体可用性、Qt 版本是跨机器最大变量,锁定 6.10.2
- macOS / Windows / Linux 三平台渲染可能不同,容差默认 0,跨平台建议 ≥ 4

## 已知限制

- **目前 6 帧的子类未实现** — PR-B0 仅交付框架,具体场景测试在 PR-B2/B3 落地
  (因为需要先拆出独立组件才能稳定构造场景)
- 帧的实现会引用 `secureredact/ui/` 拆分后的组件;PR-B0 阶段先占位,后续 PR 填充