# SecureRedact 项目恢复指南

## 概述
本指南用于下次打开项目时，快速进入当前开发基线。

---

## 快速恢复

### 1. 进入项目目录

```bash
cd <项目根目录>
```

### 2. 可选：激活虚拟环境

```bash
source venv/bin/activate
```

如果当前机器使用的是 `venvmac` 或 `venv_win`，按实际环境切换。

### 3. 启动应用

```bash
python main.py
```

### 4. 验证当前版本

```bash
cat version.txt
```

当前发布基线应为：`1.1.11`

---

## 下次接手优先阅读

1. `CLAUDE.md`
2. `docs/current/STATUS.md`
3. `docs/current/DEV_LOG.md`
4. `CHANGELOG.md`
5. `docs/guides/QUICK_START_FOR_CLAUDE_CODE.md`
6. `docs/current/PROJECT_STRUCTURE.md`

---

## 当前项目结构（最小必要）

```text
SecureRedact/
├── main.py
├── theme.py
├── version.txt
├── config.json
├── README.md
├── PROJECT_INDEX.md
├── CLAUDE.md
├── AGENTS.md
├── CHANGELOG.md
├── docs/
│   ├── current/        # 当前 active 文档（STATUS / DEV_LOG / RECOVERY / PROJECT_STRUCTURE）
│   ├── guides/         # 开发指南
│   ├── packaging/      # 跨平台打包文档
│   ├── features/       # 功能描述与设计
│   ├── marketing/      # 市场材料
│   └── ...
├── packaging/
│   ├── windows/        # Windows 打包脚本 + Inno Setup 配置
│   ├── macos/          # macOS 打包脚本 + 签名/公证配置
│   └── README.md       # 打包目录索引
├── secureredact/       # 模块化代码包
├── tests/              # 单元测试 + 集成测试
└── releases/           # 打包产物
```

---

## 当前标准验证命令

```bash
# 编译检查
python -m compileall -q main.py secureredact tests

# 全量回归
python -m unittest discover -s tests/unit -v

# 版本检查
cat version.txt
```

---

## 遇到问题时先确认

1. 当前版本是否是 `v1.1.11`
2. 问题发生在 PDF、Word，还是两者都有
3. 是否涉及首次操作、compare 切换、混合 PDF 图片区域，或 Word 高级设置保存后的预览刷新
4. 是否已经阅读 `docs/current/STATUS.md` 中最近一轮热修复说明

最后更新：2026-08-20