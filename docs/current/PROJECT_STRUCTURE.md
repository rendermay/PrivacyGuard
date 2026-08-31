# SecureRedact 当前项目结构说明

> 仅保留当前生效结构与路径。

---

## 根目录关键文件

```text
SecureRedact/
├── main.py
├── theme.py
├── version.txt
├── config.json
├── config.json.template
├── README.md
├── README_EN.md
├── PROJECT_INDEX.md
├── AGENTS.md
├── CLAUDE.md
├── CHANGELOG.md
├── requirements.txt
├── start_app.sh
├── clean_project.sh
```

---

## 当前代码目录

```text
secureredact/
├── __init__.py
├── ocr/
│   ├── __init__.py
│   ├── base.py
│   ├── manager.py
│   ├── mixed_pdf.py
│   ├── rapidocr.py
│   └── text_pdf.py
├── redaction/
│   ├── black_white_list_store.py
│   ├── doc_hash.py
│   ├── hit_ref.py
│   ├── override_store.py
│   └── whitelist_split.py
├── pii/
│   └── name_recognizer.py
├── utils/
│   ├── config.py
│   ├── doc_converter.py
│   ├── exceptions.py
│   ├── security.py
│   └── temp_manager.py
└── workers/
    ├── ocr_worker.py
    ├── word_worker.py
    └── image_merge.py
```

说明：
- `main.py` 仍是活动运行时主入口。
- `secureredact/` 提供共享模块，但并未完全替代 `main.py`。
- OCR 当前固定为 RapidOCR 单引擎。

---

## 文档目录

```text
docs/
├── current/
│   ├── STATUS.md
│   ├── DEV_LOG.md
│   ├── PROJECT_STRUCTURE.md
│   └── RECOVERY_GUIDE.md
├── guides/
│   ├── QUICK_START_FOR_CLAUDE_CODE.md
│   ├── CLAUDE_CODE_TIPS.md
│   └── TESTING_GUIDE.md
├── packaging/
│   ├── README.md
│   ├── windows-packaging-guide.md
│   └── macos-packaging-guide.md
├── features/
├── marketing/
├── CODE_REVIEW_ANALYSIS_OPUS.md
├── CODE_REVIEW_REPORT202602172000_glm.md
├── CROSS_PLATFORM_GUIDE.md
└── DEVELOPMENT_WORKFLOW.md
```

---

## 打包目录

```text
packaging/
├── README.md
├── DUAL_OCR_PACKAGING.md
├── macos/
│   ├── assets/
│   ├── config/
│   ├── docs/
│   └── scripts/
└── windows/
    ├── assets/
    ├── config/
    ├── docs/
    └── scripts/
```

说明：
- 当前 active 打包说明以 `docs/packaging/*.md` 为主。
- `packaging/*/docs/*.md` 保留为目录内索引。
- Windows 默认版本资源由 `packaging/windows/scripts/generate_version_info.py` 自动生成。

---

## 构建与发布目录

```text
build/
dist/
releases/macos/
releases/windows/
```

---

## 当前版本信息

- **当前版本**: v1.1.11
- **版本标识**: `1.1.11 - Whitelist Span Trim`
- **最后更新**: 2026-08-20