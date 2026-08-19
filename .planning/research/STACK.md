# Stack Research — Word 脱敏重构 v39.0.0

**Domain:** 本地 Word 文档脱敏（DOCX/DOC）— Python + PyQt6 桌面端
**Researched:** 2026-08-19
**Confidence:** HIGH（基于 requirements.txt 中已固定版本 + Context7 官方文档 + 现有源码实测）
**Downstream consumers:** REQUIREMENTS.md (ARCH-01..04 / FP-01..04 / FN-01..04 / TEST-01..03)、ROADMAP.md phase 划分

---

## TL;DR — 核心结论

| 维度 | 决策 | 状态 |
|------|------|------|
| Word 结构遍历 | **复用 `python-docx 1.2.0` + `lxml` 直访 footnote/endnote** | 无需新增 |
| 嵌入图 OCR | **复用 `rapidocr-onnxruntime 1.4.4`**（同 PDF `mixed_pdf.py` 路径） | 无需新增 |
| 中文 NER | **复用 `jieba 0.42.1` + 自定义词典 + 黑名单**（`secureredact/pii/name_recognizer.py`） | 无需新增 |
| 测试 fixture 生成 | **复用 `python-docx`** 直接构造 | 无需新增 |
| 脱敏前后 diff | **复用 `difflib`（stdlib）+ `mammoth 1.11.0` 双 HTML 并排** | 无需新增 |
| spaCy / HanLP / PaddleNLP | **不引入**（v2+ 通过 ARCH-03 接口位再接） | 显式排除 |
| docx2txt / docx2python / docxtpl | **不引入**（功能已由 python-docx 覆盖） | 显式排除 |

**核心策略：v39 走「重构 + 工程调优」路线，不引入任何重 binary 依赖，依赖矩阵与 v38 保持一致。**

---

## Recommended Stack

### Core Technologies（已就绪，无须新增）

| 技术 | 已安装版本 | 用途 | 为什么是标准 |
|------|-----------|------|-------------|
| **python-docx** | 1.2.0（2025-06-16 发布，Context7 验证） | Word 文档结构遍历 / 读写 | 事实标准；v1.2.0 新增 `document.comments` 原生 API；header/footer/table/section 全覆盖 |
| **lxml** | 6.1.1 实装 / requirements.txt 6.0.2 | python-docx 底层 + 补 footnotes/endnotes 缺位 | python-docx 1.2.0 仍无 footnotes/endnotes 公开 API，需 lxml 直访 doc.part.rels 拿 `footnotes.xml` |
| **mammoth** | 1.11.0（main.py 5614 行已用） | DOCX→HTML 预览 + 抽 raw text | 主流 DOCX→HTML 转换器；`extract_raw_text` 拿全文（含 footnote/endnote） |
| **jieba** | 0.42.1 | 中文分词 + nr 词性 + 自定义词典 | `secureredact/pii/name_recognizer.py` 已实现 X3 方案；POS `nr` 前缀覆盖 person-name |
| **rapidocr-onnxruntime** | 1.4.4 实装 / requirements.txt 1.2.3 | Word 嵌入图 OCR（同 PDF） | 完全离线；CPU 默认，CUDA 可选；ONNX 模型 ~10-50MB；中文+英文模型随包 |
| **difflib**（stdlib） | Python 3.x 自带 | 脱敏前后段落级 diff | 零依赖；`SequenceMatcher` + `get_opcodes` 给 in/del/eq/rep 四类操作 |
| **PyMuPDF (fitz)** | 1.27.1 | 仅作 utility（Word 不直接使用） | PDF 端依赖；v39 不动 |

### Supporting Libraries（按需新增）

| 库 | 是否新增 | 理由 |
|----|----------|------|
| 无 | — | 现有栈已覆盖 v39 全部 8 个 ARCH/FP/FN/TEST 维度 |

### Development Tools

| 工具 | 用途 | 备注 |
|------|------|------|
| `unittest` (stdlib) | 测试框架 | 已 162 项 baseline，v39 至少 +5（表/页眉页脚/批注/脚注/尾注/嵌入图 OCR 每类 ≥1） |
| `python -m compileall` | 静态检查 | 已在 `CLAUDE.md` Common Commands 中 |
| `docx` REPL（python -i） | 调试 docx 结构 | 验证 `document.paragraphs / .tables / .sections[i].header / .comments` 行为 |

---

## Alternatives Considered

| 推荐 | 备选 | 不采用理由 |
|------|------|-----------|
| `python-docx 1.2.0` | `python-docx-ng` fork | fork 不活跃；与上游兼容性差；v1.2.0 已原生支持 comments |
| `python-docx 1.2.0` | 直接 lxml 全栈 | 失去 python-docx 的对象模型封装，迁移成本不值 |
| `mammoth 1.11.0` | `docx2txt 0.9` | docx2txt 仅抽线性文本；不暴露 comments/footnotes/endnotes 结构；预览由 mammoth 统一负责 |
| `mammoth 1.11.0` | `docx2python` | 第三方 docx 提取器，覆盖全但与 mammoth + python-docx 重叠；引入只会增加维护面 |
| `jieba 0.42.1` | `spacy zh_core_web_trf` | trf 模型 ~500MB、依赖 PyTorch+CUDA-friendly 环境；违反 local-first；FP-02 可用 jieba 用户词典 + EXCLUDE_WORDS 解决（已 v37.7.x 验证） |
| `jieba 0.42.1` | `paddlenlp + ernie-tiny` | 拉入 paddlepaddle 全家桶 (~700MB)；与 `rapidocr-onnxruntime` 的 onnxruntime 偶发版本冲突；本地优先架构不变前提下不接 |
| `jieba 0.42.1` | `HanLP` | 安装拉入 torch/tensorflow 依赖；SecureRedact 法律文书场景 jieba X3 已收敛 |
| `rapidocr-onnxruntime 1.4.4` | `paddleocr 2.10.0`（已装但未启用） | paddleocr 拉 PaddlePaddle 大依赖；onnxruntime 路线更轻 |
| `difflib` (stdlib) | `python-docx-diff` 第三方 | 第三方 lib 维护差；difflib 段落级 opcode 已够用 |
| `difflib` (stdlib) | `diff-match-patch` | Google 出品但对中文支持一般；段落级 diff 不需要字符级操作码 |
| `python-docx` 直接构造 | `docxtpl` (jinja2-style) | docxtpl 是「模板+变量」场景，不适合合成 fixture；fixture 走 python-docx 直接调 API 更透明 |

---

## What NOT to Use（v39 显式排除）

| 避免 | 为什么 | 用什么代替 |
|------|--------|----------|
| spaCy 全家桶 | trf 中文模型 ~500MB + torch 依赖；与 local-first 不兼容 | jieba + 用户词典（v37.7.x X3 已落地） |
| HanLP / pkuseg | 拉入 tensorflow/torch；安装体积大；SecureRedact 法律文书场景 jieba 已够 | jieba |
| PaddleNLP / paddlenlp | 与 rapidocr-onnxruntime 偶发二进制冲突；体积大 | 留作 v2+ 通过 ARCH-03 接口位接入 |
| docx2python | 与 mammoth + python-docx 能力重叠；引入只增维护面 | python-docx (结构) + mammoth (预览/纯文本) |
| docx2txt | 仅抽线性文本；丢失结构信息 | mammoth.extract_raw_text |
| python-docx-ng fork | 与上游 drift 风险；不活跃 | python-openxml/python-docx 上游 |
| docxtpl | 模板场景工具，与 fixture 构造目标错位 | python-docx 直接 add_paragraph/add_table |
| pandoc (作为转换器) | 拉 Haskell 二进制；mammoth 已满足预览 | mammoth |
| LLM / 云端 NER | PROJECT.md "Out of Scope" 显式排除 | ARCH-02/03 留接口位 |
| anytree / lxml-objectify 替代品 | 与 python-docx 现有 lxml 集成重复 | 直接 `OxmlElement` 模式 |

---

## 6 个具体问题逐条答复

### Q1. Word 文档结构遍历 — python-docx vs 直接 lxml vs docx2txt vs mammoth 内部分析

**推荐：python-docx 1.2.0 为主，lxml 6.1.1 为辅（仅用于 footnotes/endnotes）**

| 元素 | 访问入口（python-docx 1.2.0） | 来源 |
|------|-------------------------------|------|
| 段落 (body) | `document.paragraphs` | python-docx 原生 |
| 表格 | `document.tables` (含嵌套) | python-docx 原生 |
| 章节 | `document.sections[i]` | python-docx 原生 |
| 页眉 | `section.header / .first_page_header / .even_page_header` | python-docx 原生 |
| 页脚 | `section.footer / .first_page_footer / .even_page_footer` | python-docx 原生 |
| 批注 | `document.comments` (`comments.get(id)`) | **v1.2.0 新增** |
| 脚注 / 尾注 | **无公开 API** → `doc.part.rels` 找 `footnotes.xml` / `endnotes.xml` part，用 lxml 解析 | lxml 直访 |
| 嵌入图 | `doc.inline_shapes` + `doc.part.rels` 找 `word/media/imageN.*` | python-docx 原生 + zipfile |
| 嵌入图 (提取字节) | `python-docx` 引用关系 → `related_parts[rId].blob`；或直接 `zipfile.ZipFile` 读 `word/media/*` | python-docx + zipfile |

**为什么不直接全栈 lxml：**
- python-docx 1.2.0 已覆盖 ~95% 的元素（包含 v1.2.0 新增 comments）
- 直接 lxml 要手写 OOXML 命名空间、段落/run/字段关系模型（≈ 重新发明 python-docx）
- 维护成本不划算

**mammoth 1.11.0 的角色：**
- 仅用于 DOCX→HTML 预览（main.py `_build_word_html_from_docx`）
- 仅用于 `extract_raw_text` 拿纯文本（含 footnote/endnote 文字片段）做整文兜底扫描
- 不用于结构扫描（结构扫描走 python-docx）

---

### Q2. 本地中文 NER 备选 — jieba 调优 vs spacy-zh vs paddlenlp-ner

**推荐：复用 jieba 0.42.1 + X3 方案（不引入新库）**

| 库 | 安装体积 | 离线可行性 | 中文姓名 F1 | 决策 |
|----|----------|-----------|------------|------|
| **jieba 0.42.1 + 用户词典** | ~3MB | 完全离线 | 0.85-0.90（自定义词典后） | ✅ 采用 |
| spaCy zh_core_web_trf | ~500MB + torch | 模型首次下载需联网；之后离线 | ~0.90-0.93 | ❌ 体积+torch 双重代价 |
| spaCy zh_core_web_lg | ~200MB | 同上 | ~0.85-0.88 | ❌ 同上 |
| HanLP (hanlp) | ~300MB + tf/torch | 同上 | ~0.90-0.92 | ❌ 拉入 tf/torch |
| PaddleNLP (ernie-tiny) | ~25-30MB 模型 + paddlepaddle ~700MB | 模型下载后离线 | ~0.85-0.90 | ❌ paddlepaddle 与 rapidocr-onnxruntime 偶发冲突 |
| pkuseg | ~50MB | 离线 | ~0.88 | ❌ 无 nr 标注、需自训 |

**v39 FP-02 在 jieba X3 已有机制下足够：**
- `SURNAME_SET` 准入（百家姓 + 复姓）
- `EXCLUDE_WORDS` 黑名单（已含「陈述/答辩/本院/原告/被告/审判员/法定代表人」等职务词）
- `TITLE_TOKENS` 头衔词辅助
- 用户词典 + jieba.posseg 拿 `nr` 词性

v39 仅需在 `name_recognizer.py` 增补「行政区划」「职称」黑名单子集（`省/市/县/区/乡/镇/村长/经理/主管/总监`），无须换库。

**架构层预留：**
- ARCH-03 接口位允许 v2+ 接 spacy-zh / paddlenlp / LLM，**不破坏现有 API**

---

### Q3. 表格 / 页眉页脚 / 批注 / 脚注 / 尾注 提取的轻量方案

**推荐：纯 python-docx 1.2.0 + 1 处 lxml 直访补 footnotes/endnotes，零新依赖**

```python
# 表格 / 页眉 / 页脚 / 批注 — python-docx 原生
from docx import Document
doc = Document(path)

# 表格（嵌套）
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                scan_text(para.text)

# 页眉/页脚
for section in doc.sections:
    for para in section.header.paragraphs:    # /first_page_header /even_page_header
        scan_text(para.text)
    for para in section.footer.paragraphs:    # /first_page_footer /even_page_footer
        scan_text(para.text)

# 批注 (v1.2.0 原生)
for comment in doc.comments:
    for para in comment.paragraphs:
        scan_text(para.text)   # 走同一规则集
```

```python
# 脚注/尾注 — lxml 直访（python-docx 无公开 API）
from docx.oxml.ns import qn

def _iter_footnotes(doc):
    for rel in doc.part.rels.values():
        if "footnotes" in rel.reltype or "endnotes" in rel.reltype:
            fn_part = rel.target_part
            root = fn_part.element  # lxml Element
            for footnote in root.iter(qn("w:footnote")):
                if footnote.get(qn("w:type")) in ("separator", "continuationSeparator"):
                    continue
                for t in footnote.iter(qn("w:t")):
                    yield t.text or ""

for text in _iter_footnotes(doc):
    scan_text(text)
```

**为什么不引第三方库（如 docx2python）：**
- 上面 50 行代码已覆盖全部 5 类元素
- 不引入新依赖即多覆盖 5 种 Word 元素类型
- docx2python 输出的嵌套 list 结构与 python-docx 模型不一致，会引出两套对象模型共存

---

### Q4. Word 嵌入图 OCR 的现有路径（RapidOCR 是否足够）

**推荐：复用 `rapidocr-onnxruntime 1.4.4` + `mixed_pdf.py` 已有的图像块提取 → OCR 流程**

| 步骤 | 现状 | v39 工作量 |
|------|------|-----------|
| 1. 从 .docx 抽嵌入图字节 | 需新增；`zipfile` 解 `word/media/imageN.*` | ~30 行 |
| 2. 写临时 PNG 文件 | `secureredact/utils/temp_manager.py` 已具备 | 复用 |
| 3. OCR 推理 | `secureredact/ocr/mixed_pdf.py` 已有 `RapidOCR` 调用 | 复用 |
| 4. OCR 结果回写到 Word 命中 | 需新增：把 `[(text, bbox)]` 转成 `[{start, end, text, source="ocr", rect=...}]` | ~40 行 |
| 5. 命中统一过滤 | `HitOverrideStore.instance().filtered_hits()` | 复用 |

**RapidOCR 是否够：**
- 模型默认中英双语，无需额外模型
- 完全 CPU 可跑（`use_cuda=False` 默认）
- ONNX 模型文件 ~10-50MB，首启下载，之后离线
- 与 PDF `mixed_pdf.py` 完全相同调用方式：`engine(temp_path)` 返回 `(boxes, txts, scores)`
- 不引入新依赖

**可能的 v2+ 升级（不在 v39 scope）：**
- 切换到 PP-OCRv5/v6 mobile 系列（更准，但需要 `rapidocr_onnxruntime>=3.x` 升级评估）
- 启用 CUDA（仅 Windows+ NVIDIA 机器受益，macOS Metal 走 CoreML）

---

### Q5. 测试 fixture：构建含目标结构的合成 docx 的轻量方案

**推荐：用 python-docx 直接构造（`tests/fixtures/builders/word_builder.py`）**

| 方案 | 优势 | 劣势 | 决策 |
|------|------|------|------|
| **python-docx 直接** | 已熟悉 API；覆盖全部 5 类元素；fixture 即代码 | 嵌套表格/批注需手写 | ✅ 采用 |
| docxtpl (jinja2 模板) | 模板复用方便 | 需预制 .docx 模板；fixture 透明性低；多 1 依赖 | ❌ |
| 直接拼 lxml + zip | 完全控制 | 与 python-docx 模型不一致；维护成本高 | ❌ |

**最小 fixture 集（满足 TEST-03）：**

```
tests/fixtures/
  build_word_fixture.py              # 构造器入口
  word_basic.docx                    # 仅段落
  word_with_table.docx               # 含 2x3 + 嵌套
  word_with_headers_footers.docx     # 含页眉页脚
  word_with_comments.docx            # 含批注
  word_with_footnotes_endnotes.docx  # 含脚注尾注
  word_with_images.docx              # 含嵌入图
  word_real_sample.docx              # 真实样本（抵账协议 0522.docx）
```

**构造示例：**
```python
def build_word_with_comments(out_path: Path):
    doc = Document()
    doc.add_paragraph("原告张三与被告李四...")  # 含姓名
    p = doc.add_paragraph("此处有批注")
    doc.add_comment(p.runs, text="含电话 13800138000", author="审查员")
    doc.save(out_path)
```

---

### Q6. 文档比对 / diff 库（脱敏前后对比预览）

**推荐：stdlib `difflib` + mammoth 双 HTML 并排渲染**

| 方案 | 依赖 | 适用 | 决策 |
|------|------|------|------|
| **`difflib.SequenceMatcher`（stdlib）** | 0 | 段落级 opcode (equal/replace/delete/insert) | ✅ 主选 |
| mammoth 双 HTML 并排 | 已有 | 视觉预览 | ✅ 配套 |
| `python-docx-diff` 第三方 | +1 | 同上但 API 不友好 | ❌ |
| `diff-match-patch` Google | +1 | 字符级 diff，中文一般 | ❌ |
| `lxml` 元素 diff | 已有 | 字段级 | ❌ overkill |
| LibreOffice `compareDocuments` (宏) | 需 LibreOffice | 商业级 | ❌ 重 |

**实现思路（v39 新增）：**
```python
from difflib import SequenceMatcher
import mammoth

def diff_word_documents(before_path: Path, after_path: Path) -> str:
    # 1. 抽 before 段落列表 (python-docx)
    before = [p.text for p in Document(before_path).paragraphs]
    after = [p.text for p in Document(after_path).paragraphs]

    # 2. 段落级 opcode
    sm = SequenceMatcher(None, before, after, autojunk=False)
    ops = sm.get_opcodes()   # [(tag, i1, i2, j1, j2), ...]

    # 3. 生成脱敏前后并排 HTML（用现有 mammoth）
    before_html = mammoth.convert_to_html(open(before_path, "rb")).value
    after_html = mammoth.convert_to_html(open(after_path, "rb")).value
    # 4. 在 QWebEngineView 双栏渲染
    return render_diff_panel(before_html, after_html, ops)
```

**v39 是否必做：**
- 非 FN/FP 必达项；可视作「脱敏预览增强」的 nice-to-have
- 若 roadmap 时间紧，可推迟到 v39.0.x hotfix 或 v40
- 但实现成本极低（≤80 行 + 1 个新 dock widget）

---

## Stack Patterns by Variant

**若 v39 发现真实样本漏识集中在脚注/尾注：**
- 优先用「lxml 直访 footnotes.xml」扩展扫描
- 不引入 docx2python（避免新依赖）

**若 v39 发现真实样本漏识集中在嵌入图：**
- 复用 `mixed_pdf.py` 的图像块提取 → OCR 模式
- 不引入 paddleocr（避免 PaddlePaddle 全家桶）

**若 v39 决定接外部 NER（不应发生，但留口）：**
- 通过 `ARCH-03` 接口位在 `secureredact/word/extractor.py` 加 NERExtractor Protocol
- v2+ 再接 spacy-zh / paddlenlp / LLM
- 当前 v39 不接

---

## Version Compatibility

| 包 A | 与 B 兼容 | 备注 |
|------|----------|------|
| python-docx 1.2.0 | lxml>=3.1.0, typing_extensions>=4.9.0 | python-docx pyproject.toml 强约束 |
| python-docx 1.2.0 | Python >=3.9 | v1.2.0 已 drop Python 3.8 |
| mammoth 1.11.0 | cobble, lxml, html-element | 与 python-docx 无冲突 |
| jieba 0.42.1 | Python 3.x 全平台 | 与 rapidocr / mammoth 无冲突 |
| rapidocr-onnxruntime 1.4.4 | onnxruntime>=1.24.1 | 已装 onnxruntime 1.28.0 |
| rapidocr-onnxruntime 1.4.4 | opencv-python 4.13.0.92, pyclipper 1.4.0, shapely 2.1.2 | requirements.txt 已锁 |
| difflib (stdlib) | — | 无版本问题 |

---

## Roadmap 建议（基于依赖决策）

| Phase | 主要工作 | 依赖新增 |
|-------|---------|----------|
| **v39.1 ARCH-01..04** | 把 Word 逻辑从 main.py 抽到 `secureredact/word/{rules,extractor,preview,hit_builder,redactor}.py` | 无 |
| **v39.2 FP-01..04** | 调优 jieba 黑名单 + 行政区划/职务词扩展 + 中英/中数边界正则 | 无 |
| **v39.3 FN-01..04** | python-docx 全元素扫描 + lxml footnotes/endnotes + 嵌入图 OCR（mixed_pdf 复用） | 无 |
| **v39.4 TEST-01..03** | fixture 构造器 + 端到端测试 + 162 项基线不退化 | 无 |

**总依赖矩阵变化：零。** v39 走纯架构重构 + 工程调优路线，**不引入任何新 binary 依赖**。

---

## Sources（按置信度）

- **[Context7] /python-openxml/python-docx** (HIGH) — python-docx 1.2.0 release notes、comments API、headers/footers API、OxmlElement escape hatch
- **[Context7] /mwilliamson/python-mammoth** (HIGH) — mammoth 1.11.0 comments/notes style map、extract_raw_text
- **[Context7] /rapidai/rapidocr** (HIGH) — RapidOCR ONNX models, provider config (CUDA/CPU/DML/CANN/CoreML), offline capability
- **[Context7] /fxsjy/jieba** (HIGH) — jieba 0.42.1 userdict format, POS tagging (nr)
- **[Context7] /ankushshah89/python-docx2txt** (HIGH) — docx2txt 0.9 scope
- **[Context7] /websites/docxtpl_readthedocs_io_en** (HIGH) — docxtpl 用例（确认不适用于 fixture 合成）
- **[WebSearch] spaCy zh_core_web_trf** (MEDIUM) — 体积 ~500MB、torch 依赖、OntoNotes F1 ~0.90
- **[WebSearch] PaddleNLP lightweight Chinese NER** (MEDIUM) — ernie-tiny ~25-30MB；但 paddlepaddle 全家桶 ~700MB
- **[WebSearch] python-docx iterate all elements** (HIGH) — Stack Overflow/GitHub issue 951 共识方案
- **requirements.txt** (HIGH) — 实际安装版本固定（python-docx 1.2.0、jieba 0.42.1、rapidocr-onnxruntime 1.2.3 等）
- **本地 pip list** (HIGH) — 实测环境：python-docx 1.2.0、jieba 0.42.1、lxml 6.1.1、onnxruntime 1.28.0、rapidocr-onnxruntime 1.4.4

---

## 风险与开放问题

| 风险 | 概率 | 缓解 |
|------|------|------|
| python-docx footnotes/endnotes lxml 直访在真实样本上遇到非标准 XML | LOW | 兜底：mammoth.extract_raw_text 二次扫全文 |
| rapidocr-onnxruntime 1.4.4 vs requirements.txt 1.2.3 版本差 | LOW | requirements.txt 同步升到 1.4.4（已实测兼容） |
| 嵌入图 OCR 增加文档处理时长（每图 0.5-2s） | MEDIUM | 加进度信号 + 可关闭；预扫描时仅识别疑似含人名/电话的小图 |
| `python-docx-ng` fork 与上游差异 | LOW | 不用 fork，已确认 |
| mammoth 1.11.0 与未来 docx2txt/docx2python 共存 | LOW | 不引入 docx2txt/docx2python |

---

*Stack research for: SecureRedact v39.0.0 — Word 脱敏重做*
*Researched: 2026-08-19*