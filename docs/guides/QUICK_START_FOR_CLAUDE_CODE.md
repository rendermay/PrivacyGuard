# SecureRedact Claude Code 快速上手指南

> 用于下次继续开发时，最快速接上当前进度。

---

## 先读这些文件

按下面顺序读取：

1. `CLAUDE.md`
2. `docs/current/STATUS.md`
3. `CHANGELOG.md`
4. `docs/current/PROJECT_STRUCTURE.md`
5. `docs/current/RECOVERY_GUIDE.md`

---

## 当前基线

- **版本号**: v1.1.11
- **版本标识**: `1.1.11 - Whitelist Span Trim`
- **最后更新**: 2026-08-20
- **当前状态**: 白名单片段级豁免（Whitelist Span Trim）发布基线
  - 首页、PDF、Word、批量、图片、高级设置已统一到桌面级壳层语言
  - 当前默认阶段已切换到真机截图驱动的细节抛光

---

## 当前最重要的事实

1. `main.py` 仍然是活动运行时主入口。
2. `secureredact/` 有共享模块，但不要假设所有逻辑都已完全模块化。
3. 版本唯一来源是 `version.txt`。
4. `secureredact` 包导入必须保持 OCR 懒加载，不要恢复 eager import。
5. PDF 混合页当前依赖：
   - 文本层命中
   - `page.get_text("dict")` 图片块提取
   - 图片块 OCR
   - 页面坐标偏移修正
6. Word 预览当前依赖：
   - `data-key` 标记
   - 分块 HTML 片段生成
   - 局部 DOM 更新
   - compare 面板 loaded-source 状态判断

---

## 快速命令

```bash
cd /Users/a49144/Desktop/codexhub/SecureRedactApp

# 运行应用
python3 main.py

# 语法检查
python3 -m compileall -q main.py secureredact tests

# 主回归测试
python3 -m unittest \
  tests.unit.test_mixed_pdf_ocr \
  tests.test_path_validation \
  tests.unit.test_ocr_api \
  tests.unit.test_package_imports \
  tests.unit.test_pdf_text_hit_dedup \
  tests.unit.test_app_config \
  tests.unit.test_word_replace_rules \
  tests.unit.test_batch_word_replace \
  -v
```

---

## 如果继续开发

### 默认下一步

如果没有新的回归 bug，当前优先继续：

1. 真机截图驱动的 UI 细节抛光
2. 每文件单独规则映射（Phase 2）
3. 批量规则集模板管理
4. 替换后预览按来源筛选高亮

### 如果是回归 bug

先确认：

1. 是否影响 PDF、Word，还是两者都有
2. 是否发生在 compare 模式切换时
3. 是否发生在首次打开文档后第一次执行操作时
4. PDF 是否涉及混合页中的图片 / 扫描区域
5. 是否和 `data-key` 定位、局部 DOM 更新有关

---

## 当前验证基线

- `python3 -m compileall -q main.py secureredact tests`：通过
- 主回归测试：`52/52` 通过

---

## 当前回滚点

- `20260309_runtime_remediation_cp18_verified`
- `20260309_word_compare_bugfix_cp20_verified`
- `20260309_mixed_pdf_ocr_cp23_verified`
（无 — 历史 checkpoint 与 rollback 工具链已清理；项目以 `version.txt` 为单一版本源。）
