# Pitfalls Research

**Domain:** SecureRedact v39 Word 文档脱敏重构（python-docx + Mammoth + 中文规则/NER）  
**Researched:** 2026-08-19  
**Confidence:** MEDIUM（python-docx/Mammoth/Python 官方资料与项目源码为主；中文姓名/地址边界策略仍需真实样本验证）

## 建议的预防 Phase

为避免“先调规则、后发现坐标和遍历模型不成立”导致返工，ROADMAP 应按以下顺序安排：

1. **Phase 1 — 基线、fixture 治理与接口契约**：冻结 v38 外部行为、旧调用签名、signal payload、`WordHit`/`WordLocation` 字段及 offset 定义；建立旧引擎 characterization 与 differential harness。
2. **Phase 2 — Word story 遍历与可逆坐标映射**：先覆盖正文、递归表格、页眉页脚、批注、脚注、尾注；建立 logical text → OOXML node/source span 映射。
3. **Phase 3 — Strangler 式架构抽取**：把纯扫描/规则/命中合并/替换从 `main.py` 和 `QThread` 中抽出，保留薄兼容适配器。
4. **Phase 4 — 数字、Unicode、隔符号规则**：在统一规范化与 source map 上调手机号/身份证/银行卡等规则。
5. **Phase 5 — 姓名、地名、地址上下文调优**：把 jieba 降级为候选生成器，加入行政区划、职务、标签与层级地址上下文。
6. **Phase 6 — 嵌入图 OCR 与预览一致性**：接入 Word 图片 story，验证命中定位、Mammoth 预览降级与警告。
7. **Phase 7 — 性能、安全与发布回归**：10MB+/100 页结构化性能基线、峰值内存、取消响应、162 项兼容车道与新增 TEST-* 验收。

---

## Critical Pitfalls

### Pitfall 1：把 `Document.paragraphs` + `Document.tables` 当成完整且有序的 Word 文本

**现象：** 正文能扫到，但嵌套表格、修订标记中的段落、页眉页脚、批注、脚注、尾注漏掉；合并单元格又可能被重复扫描并生成重复命中。  
**原因：** `Document.paragraphs` 与 `Document.tables` 只是顶层集合；嵌套表格不在顶层 tables 中，表格是递归结构。python-docx 文档也明确指出部分修订内容不会出现在常规集合。`row.cells` 对横向/纵向合并单元格可能重复返回同一底层 cell。当前 `WordWorker.run()` 和 `_open_word_docx()` 正是按顶层 paragraph/table 双循环建立 key，结构覆盖天然不完整。  
**预防策略：** 建立唯一 `StoryWalker`：顶层使用 `iter_inner_content()` 保序；进入 table 后递归 `_Cell.iter_inner_content()`；按底层 XML 元素或稳定 locator 去重合并单元格；对每个 story 产生 `WordLocation(story_type, part_uri, section, block_path, ...)`，不要继续扩展 `paragraph_3` / `table_1_cell_2_4` 字符串约定。对 tracked changes 明确产品语义：扫描显示文本、原始文本，还是二者，并固化 fixture。  
**预警信号：** 统计到的段落数明显小于 Word UI 所见；嵌套表中相同命中出现两次；遍历代码在多个模块各自拼 key。  
**Phase to address：** **Phase 2**；这是 FN-01 与 ARCH-02 的前置，不应延后到规则调优阶段。

### Pitfall 2：把“页眉/页脚不存在”误判为属性是 `None`

**现象：** 对空 header 做无意义 try/except；多 section 文档重复扫描同一页眉；只扫默认页眉，漏掉首页/偶数页；仅仅读取后再保存却创建了新的空 header part 或改变继承表现。  
**原因：** `section.header`、`footer`、`first_page_header`、`even_page_header` 返回 proxy，**不是 `None`**。缺少显式 part 由 `is_linked_to_previous=True` 表示；多个 section 可继承同一个 part。首次访问底层 element 时，python-docx 的实现可沿继承链解析，第一节无定义时可 materialize 新定义。偶数页与首页还受文档/section 开关控制。  
**预防策略：** 只读扫描按现有 OPC relationship/part URI 枚举并去重，不通过“访问所有 proxy 再保存”探测存在性；覆盖 default/first/even × header/footer 六种 story；记录“定义所在 section”和“呈现于哪些 section”。不要用 `if section.header is None`。  
**预警信号：** 同一 header 命中按 section 数量重复；扫描后未替换内容但 DOCX 包 diff 出新 `headerN.xml`。  
**Phase to address：** **Phase 2**，并在 TEST-03 添加多 section + linked-to-previous fixture。

### Pitfall 3：以 `paragraph.text` 扫描，却用 `paragraph.runs` 重建 offset

**现象：** 普通中文段落正确，遇到 hyperlink、field、tab/换行、内容控件或跨 run 文本后替换错位；预览高亮与实际写回位置不同；命中合法但 `end > sum(len(run.text))` 被静默丢弃。  
**原因：** `Paragraph.iter_inner_content()` 才会按顺序给出 direct Run 与 Hyperlink；`paragraph.runs` 不能代表所有可见 inline 内容。`Run.text` 会把 tab/break 映射为 `\t`/`\n`，drawing 本身无文本；字段、修订、content control 又有额外包装。当前 `apply_range_to_runs()` 与 `replace_matches_in_paragraph()` 使用 `''.join(run.text for run in para.runs)`，与 `para.text`/Mammoth HTML 不保证同一坐标空间。  
**预防策略：** Phase 2 先实现 `TextLinearizer`，输出 `logical_text` 与 token 列表，每个 token 保留 `[logical_start, logical_end) → (part, element, local offsets)`；所有规则只消费 logical text，写回只消费 source map。定义 offset 为 **Python Unicode code-point、左闭右开**；JS/Qt WebEngine 的 UTF-16 offset 只能在 bridge 边界转换。  
**预警信号：** 代码中同时出现 `para.text` 与 `''.join(run.text...)`；针对 hyperlink/emoji/扩展汉字的测试不存在；靠 bounds check 跳过命中而无诊断。  
**Phase to address：** **Phase 1 定义契约，Phase 2 实现映射**；必须早于 Phase 4/5。

### Pitfall 4：直接赋值 `run.text` / `paragraph.text` 破坏非文本子节点

**现象：** 脱敏后批注消失、脚注引用丢失、图片/field/hyperlink 结构受损、整段格式被压成单一 run。  
**原因：** `paragraph.text=` 会替换段落 inline 内容；`run.text=` 会替换该 run 除字符格式外的子元素。python-docx issue #1519 已确认：若包含 `w:commentReference` 的 run 被重写，Word 下次打开时会删除相关批注。footnote issue #1 也记录了重写 run 会移除 `w:footnoteReference`。当前 `apply_range_to_runs()` 会改首 run 并把后续 run.text 清空，不能直接扩展到批注/脚注 story。  
**预防策略：** 将“文本扫描”和“OOXML patch”分层；patcher 只改目标 `w:t` 文本节点，遇到 comment/footnote reference、drawing、field boundary 时拆分安全文本 run，而不是清空整个 run；保存后重新打开并做 package-level invariant 检查（引用 ID 均可解析、relationship 不丢、Word repair log 为零）。  
**预警信号：** 替换实现给 `paragraph.text` 赋值；对空文本 run 一律写 `''`；测试只断言可见字符串，不检查 comments/relationships。  
**Phase to address：** **Phase 2**；TEST-03 必须验证“扫描 + 写回 + reopen”而非只验证扫描。

### Pitfall 5：假设 python-docx 对批注、脚注、尾注支持程度相同

**现象：** 批注 fixture 可以创建，脚注/尾注代码却报 `AttributeError`；或用 `.part_related_by()` 查不存在 part 时抛 `KeyError`；低层 XML 能读文本但保存后 relationship/content type 不完整，Word 提示修复文件。  
**原因：** 当前项目安装的 python-docx 为 1.2.0，已有 Comments API；但 footnote/endnote 仍是官方仓库开放 feature request（#1、#1087），没有对等公共 API。脚注/尾注是独立 package part，引用在 document/header/table 文本中，内容和关系在 `footnotes.xml`/`endnotes.xml` 及各自 `.rels`。还存在 separator/continuation separator 等特殊 note ID，不能作为用户内容扫描。  
**预防策略：** 批注使用 1.2.0 public API 读取内容，但写回仍保护 anchor/reference；脚注/尾注通过一个隔离的 `OpcNoteAdapter` 读取，先检查 relationship type 是否存在，再 namespace-safe 解析。v39 若只要求扫描，可明确“只读定位 + 安全写回”的验收边界；不要把任意低层 XPath 散进 scanner。缺 part 是正常分支，不应靠宽泛 `except Exception: pass`。  
**预警信号：** 对 comments/footnotes/endnotes 共用一个 getattr 循环；缺失 note 被记录为扫描错误；生成 fixture 时手工只加 XML 不加 `[Content_Types].xml` 与 relationship。  
**Phase to address：** **Phase 1 决定能力边界，Phase 2 实现 adapter，Phase 7 做包完整性回归**。

### Pitfall 6：错误使用 OOXML namespace 和 `.//w:t`

**现象：** `.find('w:body')` 返回 `None`；在不同 lxml/python-docx 版本传 `namespaces=` 报参数错误；或 `.//w:t` 虽抓到很多文本，却漏掉 `w:delText`、误把 field instruction 当可见文本、丢失 hyperlink/SDT 的结构边界。  
**原因：** OOXML 元素名使用 namespace；底层 tag 是 Clark notation（`{namespace}body`），不是字面量 `w:body`。python-docx 的自定义 XML element `xpath()` 已注入 namespace 映射，接口与原生 lxml 并不完全相同。`w:t` 也可位于 hyperlink、SDT、tracked-change 等包装层内，单纯 descendant 搜索没有“可见文本语义”。  
**预防策略：** `find/findall` 使用 `qn('w:...')` 或 Clark name；python-docx element 的 XPath 使用其内建 prefix，不额外假设原生 lxml 签名；把“哪些 OOXML token 构成 logical text”写成显式 token policy，并为 `w:t/w:tab/w:br/w:cr/w:instrText/w:delText`、hyperlink、SDT、revision 分别测试。`w:body` 缺失、可选属性 `.get(...) is None`、`find(...) is None` 都应结构化报错。  
**预警信号：** XML 代码出现裸 `'w:t'` 的 `findall`；业务层到处调用私有 `_element.xpath()`；同一文档在 Windows/macOS 结果不同。  
**Phase to address：** **Phase 2**。

### Pitfall 7：把 Mammoth HTML 当作文档真值或位置模型

**现象：** 预览看起来少了图/表格边框/列表编号，团队误以为 scanner 漏扫；或反过来使用 HTML DOM offset 写回 DOCX，导致位置错位。chart/对象甚至可能被静默忽略。  
**原因：** Mammoth 的目标是“clean semantic HTML”，官方明确不追求复杂文档的版式保真；表格边框等格式被忽略，comments 默认不输出，text box 会被移动为包含段落后的独立段落。Issue #147 记录 chart 在 drawing 中被忽略且无 warning；#36/#79/#483 等记录 EMF、裁剪、表格宽度限制；列表编号恢复也有开放问题。  
**预防策略：** DOCX/OOXML story model 是唯一事实源，Mammoth 仅做 view projection；每次 conversion 保存并上报 `result.messages`，对不支持对象显示“预览降级”占位；DOM 节点只持 canonical location ID，不以 DOM 字符 offset 反推 OOXML。预览 fixture 验证“可定位与警告”，不要求像素级 Word fidelity。  
**预警信号：** scanner 读取 Mammoth HTML；测试把 HTML 文本等于 DOCX 全文作为前提；忽略 `result.messages`。  
**Phase to address：** **Phase 1 定义 projection 契约，Phase 6 接入预览/OCR 时验证**。

### Pitfall 8：隔符号规范化后丢失原文坐标

**现象：** `138 0013 8000`、全角数字或带破折号号码可以识别，但实际替换多删/少删；多个字段组合上下文指向错误位置。  
**原因：** 先执行 `replace(' ', '')`、NFKC 或去破折号，再在规范化字符串上返回 start/end，offset 已不再属于原文。跨 run/换行时问题更严重。  
**预防策略：** 规范化函数必须返回 `(normalized_text, index_map)`；每个规范化 code point 映射回原文 span，match 经 map 转回最小覆盖原文区间。规范化策略按规则声明：数字规则可折叠允许分隔符；姓名/地址不能无条件删空白。把 `normalized_span` 与 `source_span` 分开，不复用同一 start/end 字段。  
**预警信号：** 规则前有字符串 replace/NFKC，但函数只返回 str；测试只断言匹配文本，不断言原文切片等于预期。  
**Phase to address：** **Phase 2 建 source map，Phase 4 使用**。

### Pitfall 9：数字规则使用 `\b`、`\d` 或 `^...$` 而未定义语义

**现象：** 中文紧邻手机号时漏识；订单号中截出 11 位手机；全角/阿拉伯-印地数字意外进入身份证/银行卡；多行段落因为 anchor 行为发生漏识。  
**原因：** Python Unicode str pattern 中 `\d` 匹配 Unicode decimal digits，`\w` 包含 Unicode alphanumeric 与下划线；中文与数字都属于 word character，故 `\b` 不是“前后非数字”。`^/$` 是字符串/行 anchor，也不是号码边界。  
**预防策略：** 对中国证件/电话明确使用 ASCII `[0-9]`，若支持全角数字则先受控 NFKC 并保留 map；边界使用 `(?<![0-9])... (?![0-9])`，再加订单号/工单号上下文拒识与校验位/Luhn/号段校验。分隔符写成有限、可审计集合并限制次数，禁止泛用 `\D*`。  
**预警信号：** 数字规则以 `\b` 包围；使用 `\d+` 后再靠长度猜类型；没有“更长数字串内嵌号码”的反例。  
**Phase to address：** **Phase 4**，直接转化为 TEST-* 参数化正反例。

### Pitfall 10：用 `[一-鿿]` 代表“全部中文”

**现象：** 生僻姓名（扩展 A/B 等）漏识；含 supplementary-plane Han 字的 offset 在 JS 端偏一；兼容汉字或日文汉字被意外纳入/排除。  
**原因：** `[一-鿿]` 只覆盖 U+4E00–U+9FFF 基本 CJK Unified Ideographs，不含 Extension A（U+3400–U+4DBF）及 supplementary-plane 扩展。Python `str` 按 Unicode code point 索引，而 JS DOM offset 按 UTF-16 code unit，非 BMP 字符会产生坐标差。  
**预防策略：** 中央化 `is_han`/Unicode block policy，明确是否包含 Extension、Compatibility Ideographs；不要让每条 regex 自带不同范围。fixture 至少包含基本区、Extension A、一个非 BMP Han、emoji + 中文混排，并验证 Python↔JS offset 转换。若继续只用 `re`，使用集中生成的显式范围/谓词，而非散落字符类。  
**预警信号：** 多处复制 `[一-鿿]`；前端直接使用 Python start/end 做 Range；生僻姓名只能靠加入词典修复。  
**Phase to address：** **Phase 1 定义 offset/字符集契约，Phase 4 实现，Phase 6 验证预览 bridge**。

### Pitfall 11：把 jieba `nr` 当作最终姓名结论

**现象：** 生僻姓名被切碎漏识；产品名、日期短语、职务/机构片段被标成人名；加自定义词典修复一个样本后破坏其他分词。jieba issue #470 就有“今天下午”被标成人名的真实案例，#210/#222 反映词频/自定义词典会改变分词结果。  
**原因：** jieba posseg 是分词 + 词性标注，不是面向法律文书校准的姓名 NER；HMM 与词频对未登录词、复姓和领域词敏感。全局 hard blacklist 又会误伤真实同名词。  
**预防策略：** jieba 只生成 candidate；最终 scorer 使用姓氏形态、长度、姓名标签（姓名/当事人/法定代表人）、职务前后文、行政区划/机构后缀、产品词典和跨字段一致性。负词作为上下文 feature，而非“出现即永久禁止”。自定义词典版本化，fixture 同时含正例与近邻 hard negative，记录每次词典变更的 precision/recall delta。  
**预警信号：** `flag == 'nr'` 直接生成 hit；为每个误报向全局 blacklist 加词；规则评估只有命中率没有 FP 集。  
**Phase to address：** **Phase 5**；不得在 Phase 2/3 架构尚未稳定时混入调参。

### Pitfall 12：用一个贪婪 regex 同时解析行政区划、街道、门牌号

**现象：** 地址只命中“吉林市船营区”而漏掉门牌；或从“住址”一直吞到下一法律条款；“某某街道办事处主任”被当完整地址/姓名。  
**原因：** 中文地址没有空格边界，省/市/区/县/镇/乡/街道/路/号/栋/单元/室是嵌套层级且有同形词；行政区划本身未必应按完整住址处理。单一 `.*?` 或宽泛汉字区间无法同时控制召回与边界。  
**预防策略：** 分层产生 component（行政区、道路、门牌、楼栋房间）并执行 longest-valid chain；设置每层最大长度和终止词；用“住址/住所/送达地址”等标签提高置信度；行政区 + 职务/机构后缀进入拒识/降权；将“仅行政区”和“精确门牌地址”作为不同敏感级别。  
**预警信号：** 地址规则含跨标点 `.*`；没有 component-level debug 输出；地址正例只有一种省市区格式。  
**Phase to address：** **Phase 5**，并以真实法律文书 hard-negative 评估。

### Pitfall 13：一次性替换 `main.py`，而不是建立可删除的兼容层

**现象：** 单元测试通过但 UI 构造参数、PyQt signal、取消语义、深拷贝 payload 或默认规则注入变化；旧调用方在运行时才报错。  
**原因：** 当前 `main.py` 仍定义 `class WordWorker(_ModularWordWorker)` 薄层，负责注入 `DEFAULT_RULES`；模块 worker 的 constructor、`finished_signal(dict)`、`progress_signal(int)` 与 `__scan_meta__` 已成为隐式 ABI。直接“整理签名”会重演过去的漂移，但本次风险点是**删除兼容 ABI 太早**，不是重复实现本身。  
**预防策略：** 先把纯 `WordScanService`（无 PyQt、无 UI state）抽出；保留原 `main.WordWorker` constructor 和 signal payload 作为 adapter；characterization test 记录取消时 partial result、异常时 diagnostics、deep-copy 隔离。迁移所有调用方并有 AST/import guard 后，最后删除 adapter。  
**预警信号：** Phase PR 同时改 scanner、QThread、UI slot 与字段名；测试直接实例化新类而未覆盖旧 import path。  
**Phase to address：** **Phase 1 冻结 ABI，Phase 3 执行 strangler 迁移**。

### Pitfall 14：字段重命名期间“全系统永久双轨”

**现象：** 有的 hit 写 `text`，有的写 `value`；`source` 新旧值并存；消费者用 `.get(new, old)` 后永远无法知道哪个是 canonical；序列化、override hit_id 和预览筛选逐渐分叉。  
**原因：** dict 无 schema/version，兼容逻辑散到每个消费者。新增 story 后，仅 `source/start/end/rect/text` 已不足以唯一定位 Word 命中；PDF 的 rect 与 Word 的 source span 又不同。  
**预防策略：** 定义版本化 `WordHit`/TypedDict/dataclass 与 `WordLocation`；核心层**只写 canonical v39 schema**，旧 dict 仅在 adapter 入口读、adapter 出口写；字段映射表包含类型、必填性、坐标空间、允许 source enum、缺省策略。加入 contract test，未知字段/source fail-fast 或进入 diagnostics，不静默降级。设定删除双轨的明确 phase exit criterion。  
**预警信号：** 核心业务出现多处 `hit.get('new', hit.get('old'))`；同一 hit 同时带 `rect` 和 Word offset 却无 channel/location；source enum 由字符串比较隐式扩展。  
**Phase to address：** **Phase 1 定义，Phase 3 完成迁移并移除核心双读**。

### Pitfall 15：为了“复用”把 PDF 与 Word 命中/白名单流程强行统一

**现象：** Word 片段 trim 可以精确调整 start/end，PDF OCR 图片命中却没有可靠字符到 rectangle 子区域映射；共享函数改动后 PDF v38.0.1 行为回归。  
**原因：** `_split_text_by_whitelist()` 是纯字符串 interval algebra，可共享；但 Word 命中有线性 source map，PDF text 有 page coordinates，PDF OCR/image 可能只有整框与 OCR 文本。共享整个 hit processor 会把不同坐标语义伪装成同一 dict。  
**预防策略：** 只共享纯函数（区间并集/反集、名单规范化、source enum 基础类型）；Word/PDF 各自拥有 adapter 与 policy。为共享函数建立 channel contract matrix：能否 trim、如何回写、无字符级 geometry 时是整条 drop 还是保留。v39 明确不改 PDF；通过现有 PDF 回归作为 boundary test。  
**预警信号：** 共享函数开始判断 `if rect` / `if page_idx`；Word 重构 PR 修改 `ocr_worker.py`；一个 hit 类型含大量 Optional channel 字段。  
**Phase to address：** **Phase 1 产出边界文档，Phase 3 enforce imports；Phase 7 跑 PDF 回归**。

### Pitfall 16：只盯“162 项测试数量”，没有冻结行为基线

**现象：** 仍显示 Ran 162，但断言被改宽、fixture 被更新成新输出、已知失败被跳过；或新增测试使数量变化后 gate 失去意义。  
**原因：** 数量不是语义。重构期间最容易发生 snapshot/expected 与实现一起改，或只跑新模块测试而绕过旧 `main.py` 调用路径。  
**预防策略：** 保留原 162 项命令为不可修改的 compatibility lane，并按测试 ID 记录 160 PASS + 2 个精确已知失败；新增 v39 suite 独立统计。Phase 1 对主样本生成旧引擎 expected-hit manifest（location/start/end/text/source/rule），Phase 3–5 对同一输入 old-vs-new differential；任何差异必须标为“意图变化”并由对应 FP/FN requirement 接受。测试代码/fixture 变更与实现变更分开审阅。  
**预警信号：** PR 同时大量更新 golden；只报告通过率而不报告失败 ID；旧 import path 没有测试。  
**Phase to address：** **Phase 1 建 gate；每个 Phase 持续运行；Phase 7 最终验收**。

---

## 属性、缺失值与异常处理速查

| 对象/操作 | 正确预期 | 不要这样做 | 建议处理 | Phase |
|---|---|---|---|---|
| `section.header/footer/...` | proxy，通常不为 `None`；缺定义看 `is_linked_to_previous` | `if header is None` | 按现有 part/relationship 枚举并去重 | 2 |
| `paragraph.text` / `run.text` | 通常是 `str`，可为空串；setter 会重建子节点 | 用 setter 做结构无损替换 | linearizer + XML text-node patcher | 2 |
| `cell.width`、table/style 继承值 | 某些格式属性允许 `None` | 为扫描文本强行读取/计算布局 | 文本扫描不依赖版式 Optional 属性 | 2 |
| `element.find(...)`、XML `.get(...)` | 可返回 `None` | 紧接 `.text`/索引 | 显式 branch + story diagnostics | 2 |
| comments/footnotes/endnotes part | part 可完全不存在 | 无条件 `part_related_by()` | 先检查 rel type；缺失是正常分支，坏关系才报错 | 2 |
| image relationship/blob | 外链、损坏或不支持格式可失败 | 每图 `except Exception: pass` | 捕获 `KeyError`/I/O/解码类异常，保留 location + warning | 6 |
| DOCX package open | 可遇到 `PackageNotFoundError`、`BadZipFile`、XML parse error、坏 relationship | 把所有错误吞成“0 命中” | 文档级失败与 story 级降级分开；UI 明示 incomplete scan | 2/7 |
| Mammoth conversion | `result.messages` 可含 warning；也存在已知静默遗漏 | 只取 `result.value` | 收集 warning；另做 OOXML object inventory 对账 | 6 |

**原则：** try/except 应包围“可选 story/外部解码边界”，不应包围整个遍历并静默返回部分结果。当前 worker 的宽异常列表会把中途失败包装为 partial payload；v39 应在兼容 payload 中新增结构化 diagnostics，同时保持旧 signal ABI。

---

## 测试 / Fixture Pitfalls

### Pitfall 17：在每次测试运行时动态拼复杂 DOCX

**现象：** header/footer/table fixture 容易生成，footnote/endnote 却依赖私有 API；不同 Office/LibreOffice 保存后 XML 不同，测试不稳定；手工 OOXML 漏 content type 或 relationship。  
**原因：** python-docx 1.2.0 可生成 body/table/header/footer/comment，但没有原生 foot/endnote API。复杂 Word 功能跨多个 OPC parts，动态 builder 本身会变成另一套待测试产品。  
**预防策略：** 两层 fixture：
1. 用 python-docx builder 生成简单可组合 fixture（body/table/header/footer/comments、nested/merged cells）；
2. 用 Word/LibreOffice 一次性创建并人工验证的 checked-in golden（footnote/endnote、复杂对象），同时保存 `fixture-manifest.json`（stories、expected text、relationships、生成软件版本、SHA-256）。
测试中复制 golden 到 temp 后操作，不原地保存。  
**Phase to address：** **Phase 1 建治理，Phase 2 补 TEST-03**。

### Pitfall 18：用待测脱敏器生成“已脱敏 fixture”

**现象：** 真实 PII 仍藏在 comments.xml、footnotes.xml、customXml、document properties 或 embedded object；fixture 又天然迎合当前算法，无法发现漏识。  
**原因：** 只检查正文可见文本；把 system-under-test 的输出当安全清洗工具形成循环验证；DOCX 是 ZIP package，不是单一 document.xml。  
**预防策略：** 首选“保持结构、替换为确定性合成 PII”的派生 fixture，而非提交真实样本；替换过程独立于待测 scanner，并由人工双审。对整个解压包扫描真实姓名/号码/email 与元数据，清理 `docProps`、comments/notes、customXml、media/OLE；保存 provenance，但仓库不保存原始 PII。主样本可作为本地受限 acceptance corpus，不作为公开 fixture。  
**Phase to address：** **Phase 1**，对应 TEST-02；这是 fixture 入库前 gate。

### Pitfall 19：性能 fixture 只写“10MB / 100 页 / 小于 N 秒”

**现象：** 同为 10MB，一个只是大图片、一个有 9 万 cells，耗时差几十倍；CI 抖动导致 flaky；优化扫描后 Mammoth 或 UI patch 仍卡住。  
**原因：** DOCX 是压缩包，“页数”是 Word 布局结果，python-docx 不负责分页；成本更相关的是 uncompressed XML bytes、paragraph/run/cell 数、merged/nested table 数、图片数量与像素、notes/comments 数。官方 issue #1516 指出 huge table proxy 因支持 mutation 而重复解析，9000×10 cell 级别会严重变慢；Mammoth 也明确警告 pathological CPU/memory 输入。  
**预防策略：** 至少准备三种 fixture：text-heavy、table-heavy、media-heavy；记录结构指标、cold/warm elapsed、峰值 RSS、命中数、取消延迟、UI event-loop heartbeat。CI 用宽预算 + 相对基线（例如不得退化超过既定比例），nightly/发布机再用硬预算；先 warm-up，固定版本与机器档案。不要用 `gc.collect()` 掩盖对象持有问题。  
**Phase to address：** **Phase 1 采 v38 baseline，Phase 7 设 v39 gate**。

### Pitfall 20：测试“能扫到”，不测试“能安全写回并重新打开”

**现象：** TEST-03 每类 fixture 都有 hit，于是宣告完成；保存后 Word 修复文件、批注消失、链接损坏或预览定位错误。  
**原因：** scan coverage、replacement integrity、preview projection 是三个不同层次。复杂 story 的风险主要出现在 patch/save/reopen。  
**预防策略：** 每类 fixture 做四段断言：inventory → expected hits → apply redaction → reopen/package invariants；再做 Mammoth preview location 对账。foot/endnote 至少验证 reference ID 与 note part ID 对应，comments 验证 `commentReference` 仍存在，图片/OLE 验证 relationship 数量与 blob hash 未意外变化。  
**Phase to address：** **Phase 2（结构 E2E）与 Phase 6（预览/OCR）**。

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| 继续扩展 `word_data` 松散 dict | 改动少 | 字段/坐标空间不可验证，消费者漂移 | 仅限 Phase 1 adapter 边界 |
| scanner 继承 `QThread` 并直接改 UI state | 少写一层 | 无法纯单测、取消/并发语义耦合 | v38 兼容 adapter 可保留，核心层不可 |
| 用 Mammoth HTML 做全文抽取 | 快速覆盖部分结构 | 结构丢失、offset 不可逆、静默遗漏 | 仅预览，不可作为扫描真值 |
| 对每个误报加全局 blacklist | 立刻降 FP | 真实同名漏识、词典不可解释 | 仅经过 corpus delta 评估的领域词 |
| foot/endnote XML 逻辑散落在业务层 | 快速读到文本 | 保存损坏、版本难升级 | 不可接受；必须隔离 adapter |
| `except Exception: pass` 跳过坏 story | UI 看似完成 | 隐性 FN，用户误信“已扫描完成” | 不可接受；必须 diagnostics |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| 对 `table.rows/cells` 多轮扫描 | table-heavy 文档超线性变慢 | 单次 story snapshot；必要时隔离只读 XML adapter；处理 merged cell | 数万 cell，官方 #1516 已有 9000×10 例 |
| 每条规则遍历全文并重复规范化 | 规则数增加后线性叠加 | 每 story 规范化一次；预编译规则；分规则族扫描 | 大文档 × 多规则/词典 |
| 每个命中触发 Mammoth 全量转换/`setHtml()` | UI 卡顿、内存尖峰 | canonical model 增量更新；conversion 与 scan 解耦 | 数百命中或 media-heavy 文档 |
| deep-copy 整个 `word_data` 多次 | 扫描结束峰值内存翻倍 | 核心 immutable result + adapter 一次性转换 | 10MB+、大量 run/cell |
| OCR 对重复 image relationship 重跑 | 相同 logo/页眉图片多次 OCR | 按 blob hash + OCR config cache，location 单独映射 | 多 section/页眉复用图片 |

## Security / Privacy Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| 不检查 Mammoth HTML | DOCX 链接可带 `javascript:`；官方说明 Mammoth 不做 sanitisation | WebEngine 注入前 sanitize/禁用危险 scheme；保持 `external_file_access=False` |
| 将真实法律文书提交为 fixture | PII 泄漏到 Git 历史，后删文件也无法撤回 | 合成替换、独立 package 全扫描、人工双审 |
| 对超大/畸形 DOCX 无资源限制 | 高 CPU/内存导致桌面应用失去响应 | worker 隔离、取消、软/硬资源预算、zip expansion 限制 |
| 失败 story 仍显示“扫描完成” | 用户误以为文档完整脱敏 | diagnostics 聚合，incomplete 状态阻止无提示保存 |

## “Looks Done But Isn't” Checklist

- [ ] **表格覆盖：** 是否递归 nested table，并对 merged cell 去重，而非只扫 `Document.tables`？
- [ ] **页眉页脚：** 是否覆盖 default/first/even，且 linked section 不重复、不 materialize 新 part？
- [ ] **批注：** 是否不仅扫描 comment text，还在写回后保留 anchor/reference？
- [ ] **脚注尾注：** 是否检查 optional part、跳过特殊 separator note、保存后引用完整？
- [ ] **Offset：** 是否有 hyperlink、tab/break、非 BMP Han、跨 run、规范化分隔符的 round-trip 测试？
- [ ] **Mammoth：** 是否处理 `result.messages`，并明确 HTML 不是 canonical model？
- [ ] **NER：** 是否同时跑 positive 与 hard-negative corpus，而非只展示召回提升？
- [ ] **兼容层：** 旧 constructor、signals、`__scan_meta__`、取消与 partial result 是否仍可用？
- [ ] **回归：** 旧 162 项 compatibility lane 是否原样执行，2 个已知失败是否按精确 ID 跟踪？
- [ ] **Fixture 隐私：** 是否对整个解压 package 而非只对 document.xml 做 PII 扫描？
- [ ] **性能：** 是否分别覆盖 text/table/media heavy，并记录 peak RSS 与取消延迟？

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification / 对应需求 |
|---|---|---|
| 不完整 story 遍历、merged cell 重复 | Phase 2 | TEST-03；每类 story ≥1，nested/merged 额外 fixture |
| header/footer 继承与副作用 | Phase 2 | 多 section package diff + hit 去重 |
| logical/source/DOM offset 混用 | Phase 1–2 | ARCH-02/04；round-trip property tests |
| run setter 破坏引用 | Phase 2 | 保存/reopen invariant |
| comments vs notes API 能力差异 | Phase 1–2 | FN-01；adapter contract |
| Mammoth 结构/对象丢失 | Phase 1、6 | preview warning + location ID 对账 |
| 隔符号 source map | Phase 2、4 | FN-03 / FP-01 参数化测试 |
| 数字边界错误 | Phase 4 | FP-01/03/04 hard negatives |
| CJK 范围与非 BMP offset | Phase 1、4、6 | Unicode fixture + bridge test |
| jieba `nr` 直接定案 | Phase 5 | FP-02；precision/recall delta |
| 地址贪婪边界 | Phase 5 | FP-02/04、FN-04 |
| main.py 一次性切换 | Phase 1、3 | ARCH-01；旧 import/signals characterization |
| schema 永久双轨 | Phase 1、3 | ARCH-04 mapping + core single-write test |
| PDF/Word 过度共享 | Phase 1、3、7 | ARCH-03 + 现有 PDF suites 不退化 |
| 162 数量伪基线 | Phase 1–7 | TEST-01；按 ID/outcome 比对 |
| fixture 循环脱敏/隐私泄漏 | Phase 1 | TEST-02；package PII audit |
| 10MB/100页伪性能指标 | Phase 1、7 | 结构指标 + elapsed/RSS/cancel/UI baseline |

## Sources

### 官方文档 / 官方仓库（MEDIUM，经 research seam 分类）

- [python-docx Document API：段落、表格、`iter_inner_content()` 与 comments](https://python-docx.readthedocs.io/en/latest/api/document.html)
- [python-docx Tables：表格递归、merged/omitted cells 的复杂性](https://python-docx.readthedocs.io/en/latest/user/tables.html)
- [python-docx Header analysis：linked-to-previous 与 proxy 非 None 行为](https://python-docx.readthedocs.io/en/latest/dev/analysis/features/header.html)
- [python-docx Text API：Run、Hyperlink、Paragraph inner content](https://python-docx.readthedocs.io/en/latest/api/text.html)
- [python-docx Run-level OOXML content](https://python-docx.readthedocs.io/en/latest/dev/analysis/features/text/run-content.html)
- [python-docx Comments API](https://python-docx.readthedocs.io/en/latest/api/comments.html)
- [python-docx issue #1：footnote support 与 run.text 删除引用的讨论](https://github.com/python-openxml/python-docx/issues/1)
- [python-docx issue #1087：endnote feature request](https://github.com/python-openxml/python-docx/issues/1087)
- [python-docx issue #1519：重写 run/paragraph text 导致 commentReference 丢失](https://github.com/python-openxml/python-docx/issues/1519)
- [python-docx issue #1516：huge table 读取性能与重复解析](https://github.com/python-openxml/python-docx/issues/1516)
- [Python Mammoth README：语义 HTML、支持项、表格格式限制、comments、security/performance](https://github.com/mwilliamson/python-mammoth/blob/master/README.md)
- [Mammoth issue #147：chart 被静默忽略](https://github.com/mwilliamson/mammoth.js/issues/147)
- [Mammoth issue #36：EMF 不支持](https://github.com/mwilliamson/mammoth.js/issues/36)
- [Mammoth issue #79：image cropping 未保留](https://github.com/mwilliamson/mammoth.js/issues/79)
- [Mammoth issue #483：table column widths 丢失](https://github.com/mwilliamson/mammoth.js/issues/483)
- [Mammoth issue #413：恢复编号列表错误](https://github.com/mwilliamson/mammoth.js/issues/413)
- [jieba README：HMM、自定义词典、词性标注能力](https://github.com/fxsjy/jieba/blob/master/README.md)
- [jieba issue #470：“今天下午”误标人名](https://github.com/fxsjy/jieba/issues/470)
- [jieba issue #210：自定义词典词频问题](https://github.com/fxsjy/jieba/issues/210)
- [jieba issue #222：新增词典后分词不准确](https://github.com/fxsjy/jieba/issues/222)
- [jieba issue #1017：posseg 与自定义词典加载](https://github.com/fxsjy/jieba/issues/1017)
- [Python `re` 官方文档：Unicode `\d`/`\w`/`\b` 与 `re.ASCII`](https://docs.python.org/3/library/re.html)
- [Unicode Blocks 数据：CJK Unified Ideographs 与扩展区](https://www.unicode.org/Public/UNIDATA/Blocks.txt)

### 项目内一手证据（HIGH，直接源码）

- `secureredact/workers/word_worker.py`：当前只遍历顶层 paragraphs/tables，dict hit schema，QThread signals，宽异常与 partial payload。
- `main.py`：`WordWorker` 兼容层、`_open_word_docx()` 的现有 key 结构、`apply_range_to_runs()` 的 run offset/writeback 路径。
- `secureredact/redaction/whitelist_split.py`：纯字符串 interval 语义，可共享但不含 channel geometry policy。
- `tests/unit/test_convergence.py`：已有薄兼容层收敛 guard，可扩展为 v39 strangler gate。

## 研究缺口 / Phase Research Flags

- **Phase 2 需要 deeper research：** footnote/endnote 的只读与安全写回边界、tracked changes 与 content controls 的产品语义、Word/LibreOffice package 差异。
- **Phase 5 需要样本研究：** 地址层级、职务/机构/产品词 hard negatives 的本项目 corpus 指标；公开资料不足以替代法律文书 fixture。
- **Phase 6 需要 spike：** floating image、shape/textbox、OLE/chart 的 inventory 与 OCR/fallback UI；Mammoth 对这些对象不能作为完整证据。
- **Phase 7 需要本机基线：** 不能从 issue tracker 推导 SecureRedact 的绝对秒数/内存阈值，必须在目标 Windows/macOS 打包环境实测。

---
*Pitfalls research for: SecureRedact v39 Word 文档脱敏重构*  
*Researched: 2026-08-19*
