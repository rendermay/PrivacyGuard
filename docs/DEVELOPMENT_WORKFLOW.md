# SecureRedact 开发工作流

> 本文档描述当前项目的实际开发与发布流程。

---

## 当前基线

- 当前版本：`v1.1.11`
- 版本标识：`1.1.11 - Whitelist Span Trim`
- 版本唯一来源：项目根目录 `version.txt`
- 当前主运行时入口：`main.py`

---

## 日常开发流程

### 1. 阅读当前状态

按下面顺序阅读：

1. `CLAUDE.md`
2. `docs/current/STATUS.md`
3. `CHANGELOG.md`
4. `docs/guides/QUICK_START_FOR_CLAUDE_CODE.md`

### 2. 进入项目并运行

```bash
cd <项目根目录>
python main.py
```

### 3. 修改后做最少验证

```bash
python -m compileall -q main.py secureredact tests
python -m unittest discover -s tests/unit -v
```

### 4. 更新文档

每次影响运行路径、版本、打包方案的改动，都要同步更新：

- `README.md`
- `PROJECT_INDEX.md`
- `CLAUDE.md`
- `CHANGELOG.md`
- `docs/current/STATUS.md`

---

## 版本管理

### 当前规则

- `version.txt` 是唯一版本源
- `main.py` 和 `secureredact.__version__` 都从 `version.txt` 读取
- Windows 安装器默认版本与 EXE 版本资源要同步
- macOS spec 从 `version.txt` 动态读取版本
- 当前 packaging 文档以：
  - `docs/packaging/README.md`
  - `docs/packaging/windows-packaging-guide.md`
  - `docs/packaging/macos-packaging-guide.md`
  - `packaging/README.md`
  为准

### 更新版本的最少动作

1. 更新 `version.txt`
2. 如版本标识有变化，更新 `main.py` 中的展示字符串
3. 执行：

```bash
python packaging/windows/scripts/generate_version_info.py
```

4. 更新 active 文档和 `CHANGELOG.md`

---

## 跨平台开发原则

1. macOS 作为主要开发环境
2. Windows 主要负责打包与发布验证
3. 共享逻辑不要在 `main.py` 和 `secureredact/*` 两边各写一份
4. 打包方案当前以 `docs/packaging/*` 为主说明

---

## 打包流程

### macOS

```bash
bash packaging/macos/scripts/build_complete.sh
```

### Windows

```cmd
packaging\windows\scripts\build_complete.bat
```

如需安装包：

```cmd
packaging\windows\scripts\3_build_with_setup.bat
```

---

## 常见问题

### 如何确认当前版本？

```bash
cat version.txt
```

### 如果遇到回归 bug，先看什么？

1. `docs/current/STATUS.md`
2. `CHANGELOG.md`

最后更新：2026-08-20