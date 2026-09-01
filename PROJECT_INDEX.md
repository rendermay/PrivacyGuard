# SecureRedact 项目文档索引

**当前基线版本**: v1.1.11
**最后更新**: 2026-08-20
**当前状态**: ✅ 白名单片段级豁免（Whitelist Span Trim）发布

---

## 1. 下次继续开发时先读这些

按下面顺序读取即可快速接上当前进度：

1. `CLAUDE.md`
2. `docs/current/STATUS.md`
3. `docs/current/DEV_LOG.md`
4. `CHANGELOG.md`
5. `docs/guides/QUICK_START_FOR_CLAUDE_CODE.md`
6. `docs/current/PROJECT_STRUCTURE.md`

---

## 2. 当前主文档（Single Source of Truth）

### 项目状态与日志

- `docs/current/STATUS.md`
- `docs/current/DEV_LOG.md`
- `CHANGELOG.md`

### 开发协作文档

- `CLAUDE.md`
- `AGENTS.md`
- `docs/guides/QUICK_START_FOR_CLAUDE_CODE.md`
- `docs/guides/TESTING_GUIDE.md`
- `docs/guides/CLAUDE_CODE_TIPS.md`
- `docs/current/RECOVERY_GUIDE.md`
- `docs/current/PROJECT_STRUCTURE.md`

### 打包与发布

- `docs/packaging/README.md`
- `docs/packaging/windows-packaging-guide.md`
- `docs/packaging/macos-packaging-guide.md`
- `packaging/README.md`
- `packaging/windows/docs/WINDOWS_BUILD_GUIDE.md`
- `packaging/macos/docs/MACOS_BUILD_GUIDE.md`
- `packaging/DUAL_OCR_PACKAGING.md`

### 功能与设计

- `docs/features/DUAL_OCR_ENGINE.md`
- `docs/features/SECURITY_FEATURES.md`
- `docs/CROSS_PLATFORM_GUIDE.md`
- `docs/DEVELOPMENT_WORKFLOW.md`

### 用户文档

- `README.md`
- `README_EN.md`
- `user-guides/用户使用手册.md`
- `docs/marketing/`

---

## 3. 开发命令

```bash
# 启动应用
python main.py

# 编译检查
python -m compileall -q main.py secureredact tests

# 全量回归
python -m unittest discover -s tests/unit -v

# 版本检查
cat version.txt
```