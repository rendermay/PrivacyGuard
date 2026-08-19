# Feature Research — v39 Word 脱敏重做

**Domain:** 桌面端本地 Word 文档隐私信息脱敏（中文法律 / 政务 / 商务场景）
**Researched:** 2026-08-19
**Confidence:** HIGH（基于现有 PROJECT.md / 真实样本 / 已沉淀 162 项回归基线 / v37-v38 落地决策）
**Scope boundary:** 仅 v39.0.0 增量与重构，不复述 v37-v38 已 Validated 能力

---

## 1. Feature Landscape 总览

v39 的目标不是"加新功能"，而是把 Word 端的三类问题**结构性解决**：

| 维度 | 当前状态（v38.0.1） | v39 必达 |
|------|----------------------|----------|
| **结构覆盖** | 仅段落 + 表格主表 | 段落 / 表格 / 页眉 / 页脚 / 批注 / 脚注 / 尾注 / 嵌入图 / 修订痕迹 |
| **识别精度** | regex 命中即报，FP 高 | 字段词权重 + 行政区划 + 职务词 + 上下文拒识 |
| **架构** | main.py 散落 12k+ 行 | `secureredact/word/*` 边界，规则 / 命中 / 预览解耦 |
| **接口契约** | `source/start/end/rect/text` 命名不一致 | 统一字段映射表，与 PDF 端共用语义 |

下文按 Table Stakes / Differentiators / Anti-Features 三档展开，每档给出真实场景、复杂度、维护成本与对 v39 的明确建议（**做 / 不做 / 延后**）。

---

## 2. Table Stakes（Word 脱敏基本必须有 — 用户不奖励有，但缺失 = 产品残废）

### 2.1 结构覆盖：必须纳入扫描的 Word 结构

中文法律 / 政务文档的敏感信息**从不只出现在正文段落**。任何只扫段落的产品都会把 30%+ 的真实命中漏掉。

| Feature | Why Expected（真实场景） | 复杂度 | 维护成本 | v39 决策 |
|---------|--------------------------|--------|----------|----------|
| **正文段落扫描** | 主战场；判决书"经审理查明"段、合同"鉴于"段 | LOW | LOW | **保留**（v37 前已有，重构期保语义） |
| **表格 cell 扫描** | `抵账协议0522.docx` 甲方 / 乙方 / 身份证 / 银行账号 / 开户行全在表内；判决书原告被告信息表 | MEDIUM | MEDIUM | **必做**（FN-01 主战场） |
| **页眉扫描** | 文书抬头"XX 人民法院"、案号"（2025）京01民初1234号"含当事人/年份 | LOW | LOW | **必做**（FN-01） |
| **页脚扫描** | 页码、落款法院、送达日期、承办法官、书记员 | LOW | LOW | **必做**（FN-01） |
| **批注扫描** | 律师审阅批注常含当事人姓名、电话、身份证号 | MEDIUM | MEDIUM | **必做**（FN-01；中文法律审阅核心场景） |
| **脚注扫描** | 判决书脚注含法条引用 + 当事人缩写 + 案号 | MEDIUM | MEDIUM | **必做**（FN-01） |
| **尾注扫描** | 学术 / 法律论文尾注含参考文献作者、电话、邮箱 | MEDIUM | MEDIUM | **必做**（FN-01） |
| **嵌入图扫描** | 扫描件 Word / 身份证复印件 / 手写签名图 | HIGH | HIGH | **必做**（FN-02；走 OCR 通道，PDF 端已有 `RapidOCR` 可复用） |
| **修订痕迹扫描** | track-changes 中的原文 PII、批注框中的原文 | HIGH | HIGH | **v39.0 延后到 v39.1**（python-docx API 不直接支持，需依赖 OOXML lxml 解析；用户场景 60%+ 在已接受/已拒绝修订状态，可降级） |

**真实样本参考**：

- `pdf/抵账协议0522.docx----刘骁毅原版.docx`（32 KB） — 甲方乙方信息、身份证号、银行账号、地址全在**表格 cell 内**，段落中只有签字日期
- `pdf/丰满法院民事判决书捷信小额贷(1).pdf`（PDF 但同源 Word 模板） — 抬头"吉林省吉林市丰满区人民法院"在页眉，案号、当事人信息在表格
- `pdf/付明义判决书2026-07-29 14.29.pdf` — 承办法官、书记员在页脚，金额 / 身份证 / 地址在表格
- `pdf/周强起诉状.pdf` — 原告 / 被告 / 第三人信息表 + 事实与理由段

### 2.2 字段覆盖：必须能识别的字段

| Feature | Why Expected（中文场景） | 复杂度 | FP 风险 | v39 决策 |
|---------|--------------------------|--------|---------|----------|
| **身份证号**（18 位 / 15 位） | 中国唯一法定身份证号；GB 11643-1999 校验码 | LOW | MEDIUM（订单号冲突，见 §3.1） | **必做 + 校验码验证** |
| **手机号**（11 位 1[3-9]xxxxxxx） | 中国大陆手机号段 | LOW | MEDIUM（110/120/119/400 电话，见 §3.1） | **必做 + 拒识规则** |
| **银行卡号**（16-19 位 Luhn） | 银行卡 / 信用卡 | LOW | HIGH（订单号 / 工单号 长数字） | **必做 + Luhn 校验 + 上下文拒识**（FP-01） |
| **姓名**（2-4 字中文） | 中国姓名 + 涉外姓名 | MEDIUM | HIGH（地名 / 行政区划 / 职务词） | **必做 + jieba X3 权重**（v37.7.x 已部分实现，v39 重做） |
| **地址**（含省市区街道） | 中文地址无固定格式，靠关键字触发 | HIGH | HIGH（任意长文本命中） | **必做 + 行政区划黑名单 + 关键字窗口**（FP-02） |
| **邮箱** | RFC 5322 简化 | LOW | LOW | **必做**（v37 前已有） |
| **日期**（YYYY-MM-DD / YYYY年MM月DD日） | 合同 / 判决书日期 | LOW | MEDIUM（型号 / 版本号） | **必做 + 上下文拒识**（FP-03） |
| **金额**（含 ¥ / 元 / 万） | 合同金额、判决金额 | MEDIUM | MEDIUM（数字误吞） | **必做 + 关键字触发**（FP-03） |
| **固定电话**（区号-号码 / 400 / 800） | 公司电话、政务热线 | LOW | MEDIUM | **必做**（v37 前已有） |
| **法定代表人 / 统一社会信用代码** | 公司主体识别 | LOW | LOW | **必做**（v37 前已有） |
| **车牌号**（新能源 / 传统） | 判决书 / 合同常见 | LOW | LOW | **v39 增量**（用户新增诉求，建议加） |
| **IP 地址**（IPv4） | 网络相关文档 | LOW | LOW | **v39 增量**（低优先级） |

### 2.3 鲁棒性：必须抗住的场景

| Feature | Why Expected（真实场景） | 复杂度 | v39 决策 |
|---------|--------------------------|--------|----------|
| **半角空格分隔** | `138 0013 8000`（手机号三种标准格式之一） | LOW | **必做**（FN-03） |
| **全角空格 / 全角符号分隔** | `138　0013　8000`（Word 文档从 PDF 复制粘贴的常见污染） | LOW | **必做**（FN-03） |
| **破折号 / 短横线分隔** | `138-0013-8000`、`6222 0202 — 0013 8000 888`（银行回单格式） | LOW | **必做**（FN-03） |
| **换行 / 段落分隔** | 表格 cell 内手机号换行；脚注中跨行身份证 | MEDIUM | **必做**（FN-03） |
| **中英 / 中数混合边界** | `张三（ZhangSan）`、`13800138000张三`；不能把"张三"后面跟的英文名当身份证后缀 | MEDIUM | **必做**（FP-04） |
| **跨段落跨边界吞文本** | regex 贪婪匹配吞掉"至 13800138000 止"中的"至" / "止" | MEDIUM | **必做**（FP-04） |

---

## 3. Differentiators（本地+中文场景下值得做的差异化能力）

> ⚠️ **以下差异化能力中，"人工干预"、"黑白名单"、"白名单片段级豁免" 已在 v37.8.0 / v37.9.0 / v38.0.1 落地**——这些**不再是 v39 的增量**，但**是 v39 必须兼容**的语义基线。v39 的差异化增量是 §3.1 / §3.2 / §3.3。

### 3.1 多字段组合上下文识别（v39 真正差异化 — FP-04 + FN-04 合并解）

**问题：** 单字段正则无法判断"13800138000"是手机号还是订单号；"张三"是姓名还是行政区划/职务词。

**方案：** 在 regex 命中后增加**轻量上下文窗口**（同一段落 + 前后 50 字），结合以下信号综合判定：

| 信号 | 用法 | 示例 |
|------|------|------|
| **同段出现"身份证"/"手机号"/"电话"关键字** | 强增强 | "张三 身份证 110101199001011234" → 姓名+身份证 |
| **同段出现"地址"/"住址"/"户籍"** | 强增强 | "现住北京市朝阳区..." → 地址 |
| **同段出现"甲方"/"乙方"/"原告"/"被告"** | 强增强 | "甲方：张三" → 姓名 |
| **数字旁边出现"订单"/"工单"/"编号"/"案号"** | 拒识 | "工单号 13800138000" → 不命中手机号 |
| **数字旁边出现"¥"/"元"/"万元"** | 拒识（针对手机/身份证） | "赔偿 1380013.80 元" → 不命中手机号 |
| **姓名候选紧跟"职务"/"区长"/"局长"/"主任"/"书记"** | 拒识 | "朝阳区 张局长" → 不命中姓名（"张" 是姓氏但"局长"是职务） |

**复杂度：** MEDIUM-HIGH
**用户价值：** HIGH（直接命中 FP / FN 双痛点）
**维护成本：** MEDIUM（窗口大小、关键字集合需要持续打磨）
**v39 决策：** **必做**（FP-04 + FN-04 主战场）

### 3.2 中文姓名启发式重做（v39 重构 — 不是新增）

**问题：** v37.7.x 的 jieba X3 权重对行政区划 / 职务词的拒识不够稳，"北京市朝阳区" 中的"朝阳"可能被误判为姓名。

**方案：** v39 重新设计 `NameRecognizer`，分层打分：

| 层 | 信号 | 权重 |
|----|------|------|
| L1 词法 | jieba 词性标注（nr = 人名） | 0.3 |
| L2 黑名单 | 行政区划（省 / 市 / 区 / 县 / 街道 / 镇 / 村）+ 职务词（长 / 主任 / 局长 / 书记 / 委员 / 代表 / 教授 / 律师 / 法官） | -0.5（一票否决） |
| L3 上下文 | 紧邻"先生 / 女士 / 同志 / 同学" / "甲方 / 乙方" | +0.4 |
| L4 姓氏库 | 国家级《现代汉语姓氏表》+ GB/T 17751 常见姓氏 | 必满足 |

**复杂度：** MEDIUM
**用户价值：** HIGH（FP-02 主战场）
**维护成本：** MEDIUM（姓氏库、行政区划库需随政策更新）
**v39 决策：** **必做**（FP-02，重做而非修补）

### 3.3 字段级 override 粒度（v39 增量 — 与 v37.8.0 兼容）

**问题：** v37.8.0 的 `HitOverrideStore` 是文档+位置级 override，用户希望"这条身份证命中永远忽略，但其他身份证保留"。

**方案：** 在 `HitOverrideStore.filtered_hits()` 上扩展 `field_type` 参数；override 配置 schema 增加 `field_type` 字段（向后兼容：缺失时按 location 匹配）。

| 场景 | 当前行为 | v39 行为 |
|------|----------|----------|
| 用户在某文档某位置忽略身份证 | 同文档同位置身份证忽略 | **同文档同位置同字段类型身份证忽略**（语义更精确） |
| 用户永久忽略某规则模式 | N/A（不支持） | **支持按 pattern 永久忽略**（v39.1 增量） |

**复杂度：** MEDIUM
**用户价值：** MEDIUM-HIGH
**维护成本：** LOW（schema 兼容性 + 单测即可）
**v39 决策：** **必做**（FP 系列兜底机制）

### 3.4 已 Validated 差异化能力（v39 必须保语义兼容，不重做）

| 能力 | 落地版本 | v39 处理 |
|------|----------|----------|
| **人工干预（Ignore/Confirm/Revoke/Promote）** | v37.8.0 | **保留**，ARCH-01 抽取后必须保留 `HitOverrideStore.instance().filtered_hits()` 唯一入口 |
| **黑/白名单（BlackWhiteListStore）** | v37.9.0 | **保留**，ARCH-01 抽取后入口不变 |
| **白名单片段级豁免（whitelist_trim_only）** | v38.0.0 + v38.0.1 | **保留**，配置键 `redaction.whitelist_trim_only` 默认 True 不变 |
| **source 字段（rule / manual / ocr / blacklist）** | v37.8.0 | **保留**，ARCH-04 字段命名统一时优先复用 |
| **双预览合并顺序 `rule > manual > ocr`** | v37.7+ | **保留**，预览层是 v39 最容易碰坏的层，回归必跑 |

---

## 4. Anti-Features（看似该做但 v39 坚决不做）

| Anti-Feature | 表面吸引力 | 为什么不做 | 替代方案 |
|--------------|------------|------------|----------|
| **LLM 云端 NER 调用**（GPT / 文心 / 通义） | 准确率高、零维护 | (1) 违反 **local-first** 架构约束（PROJECT.md Constraint）；(2) 用户文档含未公开案件信息，云端调用违反律师 / 当事人保密义务；(3) 每次调用 3-8s 延迟，破坏"1 分钟完成一次脱敏"指标；(4) 厂商限流 / 服务下线 / 涨价都是风险 | 架构层在 `secureredact/word/rules/` 预留 `LlmBackend` 抽象接口位（v39 不实现，v2+ 评估） |
| **本地大模型推理**（Qwen / ChatGLM / Llama 量化） | 离线 + 高精度 | (1) 4-bit 量化 7B 模型 ≥ 4 GB binary，PyInstaller 打包后安装包膨胀 10x+；(2) CPU 推理 50+ token/s 对单文档可能 1-3 分钟，破坏 1 分钟指标；(3) GPU 推理要 CUDA，Mac 用户不支持；(4) 模型 license 复杂（Qwen 商用授权、Llama 社区协议） | 词典 + regex + 启发式组合（v39 方案），覆盖率 90%+；剩余 10% 留给人工干预 |
| **AI 自动决定替换内容**（"智能替换"） | UX 上"全自动很爽" | (1) 替换内容是法律 / 政务严肃操作，"张某某" vs "张三" vs "当事人 A" 对法律效力影响不同，必须由人定；(2) 自动替换一旦错，用户回滚成本极高（要重打开原文档）；(3) v37.8.0 已经提供"提升为永久规则"机制，AI 自动反而削弱这条人工控制路径 | 保留"预览 + 人工干预"链路；v39 不引入任何自动替换决策 |
| **OCR 全自动预处理**（打开文档先 OCR 一遍） | "文档里有图也能扫"很诱人 | (1) OCR 一次 5-30 秒，绝大多数纯文本 Word 不需要；(2) OCR 命中与文本层命中会产生冲突，需要去重；(3) 嵌入图 OCR 走"按需 OCR"才合理 | v39 只在"嵌入图检测到时按需 OCR"，且 OCR 结果必须与文本层命中做去重（PDF 端已有此逻辑可复用） |
| **多语言界面 / i18n** | "面向海外华人市场" | (1) 当前用户 100% 中文法律 / 政务场景；(2) PyQt6 + gettext 引入工程量大；(3) 多语言会模糊焦点 | 不做；v39 界面文案全部中文化（与 v37-v38 一致） |
| **云端协同（多人共用 override / whitelist）** | "团队共享脱敏规则" | (1) local-first 架构约束；(2) 同步冲突解决复杂（CRDT / OT）；(3) 用户场景以单兵 / 小所为主，协同需求未验证 | `config.json` 走用户手动 git / 共享盘；不做云端 |
| **自动 OCR 训练 / 微调** | "用用户文档微调模型" | (1) 训练数据收集涉及用户文档隐私；(2) 微调 pipeline 复杂；(3) RapidOCR 已 SOTA，无明显收益 | 用 RapidOCR 默认模型；不训练 |
| **实时光标悬浮预览命中** | "鼠标移上去显示为什么命中" | (1) Qt 模型层实时 hover 事件成本高；(2) 与现有"双预览"交互重复；(3) 易引入回归 | 保留"右侧 dock 显示命中详情"（v37.8.0 已落地） |

---

## 5. Feature Dependencies（依赖关系 — 直接驱动 Phase 顺序）

```
ARCH-04 统一字段命名
    └──requires──> 字段映射表（source/start/end/rect/text）
                       └──requires──> 所有 Word 消费端切换到新字段名
                                          └──conflicts──> v37.8.0 现有 source 字段语义

FN-01 结构全覆盖（页眉/页脚/批注/脚注/尾注）
    └──requires──> python-docx section/header/footer/comment API
    └──enhances──> FP-04 上下文窗口（可扩到表头表尾）

FN-02 嵌入图 OCR
    └──requires──> FN-01（同结构扫描框架）
    └──requires──> secureredact/ocr/RapidOCR（PDF 端已有，可复用）

FN-03 隔符号鲁棒
    └──requires──> FP-01 拒识规则（同一 normalizer 层）

FN-04 多字段组合上下文
    └──requires──> ARCH-04 统一字段
    └──requires──> FN-01 结构全覆盖（上下文窗口跨结构）
    └──enhances──> FP-01/FP-02/FP-03 所有拒识信号

FP-01 数字型拒识（订单号/工单号/隔符号）
    └──requires──> FN-03 隔符号鲁棒（同 normalizer 层）

FP-02 姓名/地名/地址 词权重
    └──enhances──> v37.7.x NameRecognizer（重做而非新建）

FP-04 词法/上下文（跨边界吞文本）
    └──requires──> FN-04 多字段组合上下文（同上下文窗口）

TEST-02 真实样本 fixture
    └──requires──> 抵账协议0522.docx + 4 份判决书
    └──requires──> 每类结构 ≥1 fixture（表/页眉/页脚/批注/脚注/尾注/嵌入图）
```

**Phase 顺序的强制约束：**

1. **ARCH-01 / ARCH-04 必须先做** — 后续所有 FP / FN 改造都依赖统一字段名 + 模块边界
2. **FN-01 必须先于 FN-02 / FN-04** — 上下文窗口要跨结构
3. **FP-01 必须与 FN-03 同层** — 同一 normalizer
4. **FN-04 最后做** — 它依赖 FN-01 + FP-01 + FP-04 + ARCH-04

---

## 6. MVP Definition（v39.0.0 必达范围）

### 6.1 Launch With（v39.0.0 必达 — 不达不出）

- [ ] **ARCH-01** main.py Word 散落抽取到 `secureredact/word/*` — 用户价值: HIGH, 成本: HIGH, **P1**
- [ ] **ARCH-02** 规则 / 命中 / 预览三层接口契约 — 用户价值: HIGH（开发期价值），成本: MEDIUM, **P1**
- [ ] **ARCH-03** PDF/Word 复用边界文档（OCRWorker / HitOverrideStore / whitelist_split） — 用户价值: MEDIUM, 成本: LOW, **P1**
- [ ] **ARCH-04** 统一字段命名（source/start/end/rect/text）+ 字段映射表 — 用户价值: HIGH, 成本: LOW, **P1**
- [ ] **FP-01** 数字型拒识（订单号/工单号/隔符号号码） — 用户价值: HIGH, 成本: MEDIUM, **P1**
- [ ] **FP-02** 姓名 / 地名 / 地址 词权重重做 — 用户价值: HIGH, 成本: MEDIUM, **P1**
- [ ] **FP-03** 日期 / 邮箱 / 金额 上下文拒识 — 用户价值: MEDIUM, 成本: LOW, **P1**
- [ ] **FP-04** 词法 / 上下文（跨边界吞文本） — 用户价值: HIGH, 成本: MEDIUM, **P1**
- [ ] **FN-01** 表格 / 页眉 / 页脚 / 批注 / 脚注 / 尾注 扫描 — 用户价值: HIGH, 成本: MEDIUM, **P1**
- [ ] **FN-02** 嵌入图 / 扫描件 Word 走 OCR 通道 — 用户价值: MEDIUM, 成本: HIGH, **P1**
- [ ] **FN-03** 跨格式 / 隔符号鲁棒匹配 — 用户价值: HIGH, 成本: MEDIUM, **P1**
- [ ] **FN-04** 多字段组合上下文（人名 + 电话 + 地址联动） — 用户价值: HIGH, 成本: MEDIUM-HIGH, **P1**
- [ ] **TEST-01** 162 项全量回归不退化（已知 2 项失败保持） — 用户价值: HIGH（基线），成本: LOW, **P1**
- [ ] **TEST-02** 真实样本 fixture 集 — 用户价值: HIGH, 成本: LOW, **P1**
- [ ] **TEST-03** Word 结构全覆盖端到端 fixture（每类 ≥1） — 用户价值: HIGH, 成本: LOW, **P1**

### 6.2 v39.0.x Hotfix 范围（v39.0 完成后）

- [ ] **修订痕迹扫描**（python-docx 不直接支持，需 lxml） — **P2**
- [ ] **按 pattern 永久忽略规则**（schema 扩展） — **P2**
- [ ] **车牌号字段**（用户新增诉求） — **P2**

### 6.3 v39.1+ 增量

- [ ] **per-file rule mapping for batch replace**（PROJECT.md 后续轨道） — **P2**
- [ ] **batch rule-set templates** — **P2**
- [ ] **preview highlight filtering by source** — **P2**

### 6.4 v2+ 远期（不在 v39 范围，ARCH 已预留接口位）

- [ ] **LLM / 云端 NER 接入**（`LlmBackend` 抽象） — **P3**，需先验证 PMF
- [ ] **本地大模型推理** — **P3**，需先评估硬件门槛
- [ ] **云端协同**（override / whitelist 共享） — **P3**

---

## 7. Feature Prioritization Matrix

| Feature | 用户价值 | 实现成本 | 维护成本 | 优先级 |
|---------|----------|----------|----------|--------|
| ARCH-01 Word 散落抽取 | HIGH | HIGH | LOW | **P1** |
| ARCH-02 接口契约 | HIGH（开发） | MEDIUM | LOW | **P1** |
| ARCH-03 复用边界文档 | MEDIUM | LOW | LOW | **P1** |
| ARCH-04 字段统一 | HIGH | LOW | LOW | **P1** |
| FP-01 数字型拒识 | HIGH | MEDIUM | MEDIUM | **P1** |
| FP-02 姓名词权重 | HIGH | MEDIUM | MEDIUM | **P1** |
| FP-03 日期/邮箱/金额拒识 | MEDIUM | LOW | LOW | **P1** |
| FP-04 跨边界 | HIGH | MEDIUM | LOW | **P1** |
| FN-01 结构全覆盖 | HIGH | MEDIUM | LOW | **P1** |
| FN-02 嵌入图 OCR | MEDIUM | HIGH | HIGH | **P1** |
| FN-03 隔符号 | HIGH | MEDIUM | LOW | **P1** |
| FN-04 多字段组合 | HIGH | MEDIUM-HIGH | MEDIUM | **P1** |
| TEST-01 162 项基线 | HIGH（基线） | LOW | LOW | **P1** |
| TEST-02 fixture | HIGH | LOW | LOW | **P1** |
| TEST-03 结构 fixture | HIGH | LOW | LOW | **P1** |
| 修订痕迹 | MEDIUM | HIGH | HIGH | **P2** |
| pattern 永久忽略 | MEDIUM | LOW | LOW | **P2** |
| 车牌号 | LOW | LOW | LOW | **P2** |
| per-file rule mapping | MEDIUM | MEDIUM | LOW | **P2** |
| batch 规则模板 | MEDIUM | MEDIUM | LOW | **P2** |
| preview source 过滤 | MEDIUM | LOW | LOW | **P2** |
| LLM 云端 | HIGH（理论上） | HIGH（架构） | HIGH（合规） | **P3 / 拒绝** |
| 本地 LLM | HIGH（理论上） | HIGH | HIGH | **P3 / 拒绝** |
| 云端协同 | MEDIUM | HIGH | HIGH | **P3 / 拒绝** |

**优先级口径：**
- **P1**: v39.0.0 必达，缺失则里程碑不通过
- **P2**: v39.0.x / v39.1 增量，不阻塞 v39.0.0
- **P3 / 拒绝**: 显式不做，架构层留接口位

---

## 8. 真实案例引用（v39 验收用）

| 样本 | 期望命中位置 | 期望拒识位置 |
|------|--------------|--------------|
| **抵账协议0522.docx** | 表格 cell 中甲方/乙方/身份证/银行账号/地址 | "2025年5月22日" 不应被当身份证 |
| **丰满法院民事判决书捷信小额贷.pdf**（同源 Word） | 页眉法院名、表格当事人、页脚承办法官/书记员 | "2025"年份不应进身份证 |
| **付明义判决书.pdf**（同源 Word） | 表格身份证、地址、页脚案号 | 案号"（2025）京01民初1234号"中的数字不应进手机号 |
| **周强起诉状.pdf**（同源 Word） | 表格原告/被告、事实与理由段身份证/地址 | 金额"¥50,000"不应进手机号 |
| **新增 fixture：批注 Word** | 审阅批注中的姓名/电话 | — |
| **新增 fixture：脚注 Word** | 脚注中当事人姓名 | — |
| **新增 fixture：尾注 Word** | 尾注中参考文献作者 | — |
| **新增 fixture：嵌入图 Word** | 图片 OCR 后身份证/姓名 | — |
| **新增 fixture：隔符号 Word** | "138 0013 8000" / "6222—0202—0013" | — |
| **新增 fixture：订单号 Word** | 工单号"PO-2025-13800138000" 不应进手机号 | 拒识主验证 |

---

## 9. 复杂度 / 价值 / 维护 三角评估（v39 决策辅助）

| 类别 | 实现成本 | 用户价值 | 维护成本 | v39 评分 |
|------|----------|----------|----------|----------|
| **架构抽取（ARCH-01/02/03/04）** | HIGH | HIGH（开发+长期） | LOW | **必做**（不做后续全崩） |
| **结构全覆盖（FN-01）** | MEDIUM | HIGH | LOW | **必做**（30%+ 漏识来源） |
| **嵌入图 OCR（FN-02）** | HIGH | MEDIUM | HIGH | **必做但取最小可行**（仅按需 OCR + 复用 PDF 通道） |
| **隔符号鲁棒（FN-03）** | MEDIUM | HIGH | LOW | **必做**（影响所有数字型命中） |
| **多字段组合（FN-04）** | MEDIUM-HIGH | HIGH | MEDIUM | **必做**（FP/FN 双收敛点） |
| **数字型拒识（FP-01）** | MEDIUM | HIGH | MEDIUM | **必做**（高频用户痛点） |
| **姓名重做（FP-02）** | MEDIUM | HIGH | MEDIUM | **必做**（v37.7.x 修补够，重做） |
| **日期/邮箱/金额拒识（FP-03）** | LOW | MEDIUM | LOW | **必做**（与 FP-01 同 normalizer，顺手做） |
| **词法上下文（FP-04）** | MEDIUM | HIGH | LOW | **必做**（跨边界吞文本是高优 UX 痛点） |
| **修订痕迹** | HIGH | MEDIUM | HIGH | **v39.1 延后** |
| **LLM / 云端** | HIGH（合规） | HIGH（理论上） | HIGH | **不做** |
| **本地 LLM** | HIGH | HIGH（理论上） | HIGH | **不做** |
| **AI 自动替换** | LOW | 反向（破坏信任） | LOW | **不做** |

---

## 10. Sources

### 项目内源

- `/mnt/g/Project/SecureRedact/.planning/PROJECT.md` — v39 范围、ARCH/FP/FN/TEST 编号、Out of Scope 决策
- `/mnt/g/Project/SecureRedact/CLAUDE.md` — 当前技术现实、版本号、回归基线
- `/mnt/g/Project/SecureRedact/CHANGELOG.md` — v37-v38 已落地能力清单
- `/mnt/g/Project/SecureRedact/docs/superpowers/specs/2026-08-19-whitelist-trim-only-design.md` — 白名单片段级豁免设计基线
- `/mnt/g/Project/SecureRedact/docs/current/STATUS.md` — 当前状态 + 已知回归 2 项
- `/mnt/g/Project/SecureRedact/pdf/抵账协议0522.docx----刘骁毅原版.docx` — v39 主样本
- `/mnt/g/Project/SecureRedact/pdf/丰满法院民事判决书捷信小额贷(1).pdf` — 民事判决书样本
- `/mnt/g/Project/SecureRedact/pdf/付明义判决书2026-07-29 14.29.pdf` — 判决书样本
- `/mnt/g/Project/SecureRedact/pdf/周强起诉状.pdf` — 起诉状样本

### 已沉淀测试基线

- `tests/unit/test_whitelist_split.py` — 白名单 split 行为基线
- `tests/unit/test_whitelist_trim_only.py` + `test_whitelist_trim_only_config.py` — trim_only 行为基线
- `tests/unit/test_name_recognizer.py` + `test_worker_name_recognition.py` — v37.7.x 姓名识别基线
- `tests/unit/test_hit_ref.py` + `test_override_store.py` + `test_bridge_override_slots.py` — v37.8.0 人工干预基线
- `tests/unit/test_ocr_worker_source_field.py` + `test_word_source_field.py` + `test_pdf_source_field.py` — source 字段基线

### 行业标准 / 中文场景依据

- **GB 11643-1999** 公民身份号码（含校验码算法）
- **GB/T 17751** 中国人名汉语拼音字母拼写规则（姓氏库参考）
- **GB/T 2260** 中华人民共和国行政区划代码（行政区划黑名单来源）
- **GB 32100-2015** 法人和其他组织统一社会信用代码编码规则
- **JR/T 0025** 中国金融集成电路（IC）卡规范（银行卡号 Luhn 校验参考）
- **《最高人民法院关于人民法院在互联网公布裁判文书的规定》** — 司法公开场景的脱敏合规要求
- **《个人信息保护法》（PIPL, 2021）** — 个人信息处理的法律依据
- **《数据安全法》（2021）** — 数据本地化与脱敏的法律依据

### 已显式排除（防止回潮）

- LLM 云端 NER / 本地 LLM 推理 / AI 自动替换 — 见 PROJECT.md Out of Scope + 本文件 §4 Anti-Features
- UI 视觉重做 / 新交互 — 见 PROJECT.md Out of Scope
- 打包链路改动 — 见 PROJECT.md Out of Scope
- PDF 端改动（v39 引入的回归除外） — 见 PROJECT.md Out of Scope
- DOC → DOCX 转换逻辑 — 见 PROJECT.md Out of Scope

---

## 11. 摘要与建议

**v39 的核心不是加 Feature，而是把现有散落的 Word 能力"结构化"**：

1. **架构层（ARCH-01/02/03/04）** 是地基，没有它后续 FP / FN 改造会重复劳动。
2. **结构覆盖（FN-01）+ 隔符号鲁棒（FN-03）** 是漏识主战场，对应真实样本 30%+ 的命中缺口。
3. **多字段组合（FN-04）+ 上下文拒识（FP-01/02/03/04）** 是误识主战场，根治 v37-v38 反复 hotfix 的根源。
4. **嵌入图 OCR（FN-02）** 取最小可行即可，复用 PDF 端 `RapidOCR` 通道，避免重造轮子。
5. **人工干预 / 黑/白名单 / trim_only / source 字段** 是 v37-v38 已 Validated 的差异化能力，v39 必须**严格兼容语义**，不动 schema。
6. **LLM / 云端 / AI 自动替换** 显式排除，架构层仅留接口位。

**与 PROJECT.md v39 必达对齐：**
- ✓ 162 项全量回归不退化（已知 2 项失败保持）
- ✓ Word 脱敏独立可调用接口（`secureredact/word/*` 边界清晰）
- ✓ Word 结构全覆盖（每类 ≥1 fixture 端到端验证）

---

*Feature research for: SecureRedact v39.0.0 Word 脱敏重做*
*Researched: 2026-08-19*
*Confidence: HIGH*
