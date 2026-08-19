# 跨设备 Clone 与环境搭建指南

本指南说明在新设备上从 GitHub clone SecureRedact 仓库（含本次 fix/pii-e2e 分支修复）并搭建可运行环境的标准流程。

适用版本：**v37.7.7** 之后（含中文姓名启发式识别 + 图片通道修复链）

---

## 1. 选择 Clone 源

| 仓库 | URL | 用途 |
|---|---|---|
| **个人 fork (推荐)** | `https://github.com/rendermay/SecureRedact.git` | 个人工作分支，含本次修复 |
| 项目上游 | `https://github.com/lizilaywer/SecureRedact.git` | 主分支，正式发布版 |

**本次修复已发布到 fork**：`fix/pii-e2e` 分支，commit `eae7656`。

---

## 2. 标准 Clone 流程

### 2.1 仅个人 fork（推荐场景）

```bash
git clone https://github.com/rendermay/SecureRedact.git
cd SecureRedact
git checkout fix/pii-e2e
```

### 2.2 同时跟踪上游（需要从上游同步）

```bash
# 1. clone 个人 fork
git clone https://github.com/rendermay/SecureRedact.git
cd SecureRedact

# 2. 加 upstream 远程
git remote add upstream https://github.com/lizilaywer/SecureRedact.git

# 3. 验证 remote 配置
git remote -v
# 期望输出:
# fork    https://github.com/rendermay/SecureRedact.git (fetch)
# fork    https://github.com/rendermay/SecureRedact.git (push)
# upstream https://github.com/lizilaywer/SecureRedact.git (fetch)
# upstream https://github.com/lizilaywer/SecureRedact.git (push)

# 4. 切换到本次修复分支
git checkout fix/pii-e2e
```

### 2.3 验证 clone 成功

```bash
git log --oneline -3
# 期望第一行:
# eae7656 feat(ocr): 中文姓名启发式识别 + 图片通道修复链
```

---

## 3. Python 环境准备

### 3.1 系统要求

| 维度 | 最低要求 | 推荐 |
|---|---|---|
| Python | 3.10+ | **3.13**（本机验证版本） |
| 操作系统 | Windows 10/11 / macOS 12+ / Ubuntu 20.04+ | 同左 |
| 内存 | 4 GB | 8 GB+（OCR 模型加载需要） |
| 磁盘 | 2 GB | 5 GB（含 jieba 词典） |

### 3.2 创建虚拟环境

#### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
```

#### Windows (Git Bash)

```bash
python -m venv venv
source venv/Scripts/activate
python -m pip install --upgrade pip
```

#### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

⚠️ **避免在 conda base 环境跑 GUI**：PyQt6 DLL 在 PowerShell conda base 下会加载失败（CLAUDE.md 已记录）。

### 3.3 安装依赖

```bash
pip install -r requirements.txt
```

关键依赖：

| 包 | 版本 | 用途 |
|---|---|---|
| PyQt6 | ≥6.0 | GUI 框架 |
| PyMuPDF (fitz) | ≥1.20 | PDF 文档处理 |
| rapidocr_onnxruntime | ≥1.3 | OCR 引擎 |
| jieba | **==0.42.1** (锁定) | 中文分词 |
| numpy / opencv-python | 最新 | 图像处理 |

---

## 4. 编译与回归测试

### 4.1 编译检查

```bash
python -m compileall -q main.py secureredact tests
```

期望：**无输出**（静默成功）。

### 4.2 全量单元测试

```bash
python -m unittest discover tests/unit
```

期望输出：

```
................................................................
................................................................
..................
Ran 126 tests in 5.5s

OK
```

**已知 baseline 失败**（与代码无关）：

- `test_config_alignment.TestConfigAlignment.test_scan_default_level_matches`
- `test_config_alignment.TestConfigAlignment.test_simple_config_reads_config_json_values`

这两个失败是 `config.json` (`scan.default_level=2.0`) 与 `DEFAULT_CONFIG` (`1.5`) 的预设不一致，与本次修复无关。

### 4.3 集成测试（可选）

```bash
python -m unittest tests.integration.test_end_to_end_redaction
python -m unittest tests.integration.test_gui_smoke
```

---

## 5. GUI 启动

```bash
python main.py
```

### 5.1 启动期望

```
[INFO] 应用图标已加载: ...
[清理] 打开新文档前的资源清理完成
```

### 5.2 实测验证修复效果

1. 打开 `PDF/周强起诉状.pdf`（**注意：该文件未被 git 跟踪，需手动复制**）
2. 在设置中**勾选"中文姓名启发式识别"**
3. 触发扫描
4. 期望日志：

```
[OCR] 页面 0: 文本命中 0, 图片块 1, 图片OCR命中 4
[OCR] 页面 1: 文本命中 0, 图片块 1, 图片OCR命中 9
[OCR] 页面 2: 文本命中 0, 图片块 1, 图片OCR命中 1
```

5. 期望脱敏覆盖：

| 页 | 关键命中 |
|---|---|
| Page 0 | 案号"0204民初5965号"、地址"吉林省吉林市永吉经济开发区…1号"、日期、"刘妹 034-62407159"（手写体电话） |
| Page 1 | 原告"周强"、身份证号、手机号、地址、固定电话、法定代表人"曹炳志"、著作权人"周强" |
| Page 2 | 签名段"周强"、日期 |

---

## 6. 故障排查

### 6.1 PyQt6 DLL 加载失败 (Windows)

```
ImportError: DLL load failed while importing QtCore
```

**原因**：在 PowerShell conda base 环境下运行。

**修复**：

- 用 Git Bash / WSL / cmd 启动
- 或切换到 venv：`source venv/Scripts/activate`

### 6.2 jieba 导入失败

```
ModuleNotFoundError: No module named 'jieba'
```

**修复**：

```bash
pip install jieba==0.42.1
```

### 6.3 OCR 引擎不可用

```
RapidOCR 引擎不可用，请检查依赖安装
```

**修复**：

```bash
pip install rapidocr_onnxruntime onnxruntime
```

### 6.4 中文显示为方块

Linux 缺少中文字体：

```bash
# Ubuntu/Debian
sudo apt-get install fonts-noto-cjk

# 重启应用
```

### 6.5 修复未生效（仍漏脱敏）

检查：

1. **分支正确**：`git branch --show-current` 应该是 `fix/pii-e2e`
2. **配置文件加载**：`config.json` 中 `redaction.enable_name_recognition: true`
3. **缓存**：删除 `__pycache__/` 目录重新跑

```bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
python main.py
```

---

## 7. 测试数据说明

下列文件**未被 git 跟踪**，需要手动准备：

| 文件 | 来源 | 用途 |
|---|---|---|
| `PDF/周强起诉状.pdf` | 原始测试 PDF | 验证图片通道修复效果 |
| `PDF/周强起诉状_GUI模式脱敏.pdf` | GUI 导出结果 | 对比预期脱敏覆盖 |
| `PDF/丰满法院民事判决书捷信小额贷(1).pdf` | 测试 PDF | 印刷体场景 |
| `PDF/付明义判决书2026-07-29 14.29.pdf` | 测试 PDF | 大文档性能基准 |

如需，可从原开发机复制或重新提供。

---

## 8. 关键 commit 摘要

| Commit | 内容 |
|---|---|
| `eae7656` | feat(ocr): 中文姓名启发式识别 + 图片通道修复链 |
| `829a43d` | v37.7.6: 全面重复实现收敛 + 工程保障修复 |

---

## 9. 一键复现脚本

```bash
git clone https://github.com/rendermay/SecureRedact.git
cd SecureRedact
git checkout fix/pii-e2e
python -m venv venv

# Windows (Git Bash):
source venv/Scripts/activate
# Linux/macOS:
# source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
python -m compileall -q main.py secureredact tests
python -m unittest discover tests/unit
```

期望最后输出：

```
Ran 126 tests in5.5s
OK
```

即可启动 GUI。

---

## 10. 联系与反馈

- **GitHub Issues**: https://github.com/rendermay/SecureRedact/issues
- **内部反馈表**: https://fcnwakmkeuz7.feishu.cn/share/base/form/shrcnEM1JEbdIKzdB400egj9lHe