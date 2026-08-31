# 视觉基线 PNG(PR-B0 占位,实际基线在后续 PR 落地后由人工审定入库)

本目录存放 6 张经人工审定的"金标准"截图:

- `01_idle_main_window.png`     主窗口空态
- `02_pdf_single_page.png`       打开 PDF 单页
- `03_word_dual_preview.png`    Word 双栏预览
- `04_settings_dialog_overview.png` 设置首屏
- `05_batch_replace_results.png`  批替换结果
- `06_word_replace_rules.png`   Word 替换规则编辑器

抓取命令:

```bash
PRIVACYGUARD_WRITE_BASELINES=1 python -m unittest tests.ui.baseline_screenshots
```

实际生成的实拍图落在 `tests/ui/actual/`(不进 git)。