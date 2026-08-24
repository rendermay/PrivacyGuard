# SecureRedact 信息脱敏助手 - 更新日志

本文档记录了 SecureRedact 信息脱敏助手的所有重要更新。

---

## [1.1.13] - 2026-08-24 — 姓名上下文注入 + 三层防护收口

### Added
- **姓名上下文注入 (方案 B)**: jieba 启发式识别的 `nr` 标注不再无脑注入 patterns。
  新增 `require_context` 参数(默认 `False`), `True` 时仅保留**在原文中具有强上下文**的候选。
  - 强前缀词: 原告/被告/经理/审判员/证人/鉴定人/法定代表人/...
  - 强后缀词: 先生/女士/同志/律师/教授/...
  - 强标签模式: `原告:周强` / `法定代表人：曹炳志`
- 新增模块 `secureredact/pii/name_context.py`:
  - `STRONG_PREFIX_TOKENS` / `STRONG_SUFFIX_TOKENS` 词表
  - `_LABEL_PATTERN` 正则
  - `filter_names_by_context(text, candidates)` 公共 API
- `ChineseNameRecognizer.extract()` / `extract_person_names()` 新增 `require_context: bool = False` 参数(向后兼容, 默认 False)。
- **WordWorker / OCRWorker 默认开启严格模式**(`require_context=True`), 实际生产路径仅注入有强上下文的人名。

### 配套回归 (v1.1.11 起的识别器防护收口)
- **白名单邻接过滤** (v1.1.11 fix): `whitelist` 参数, 防 `丁方经` / `戊方经` 等合同角色词粘连伪人名。
- **大写金额结构性免疫** (v1.1.11 fix): `AMOUNT_CHARS` 字表 + `_is_amount_word()`, 防 `陆佰柒` 等人民币大写金额片段被误识。
- **法律文书高频术语黑名单** (v1.1.11 fix): `EXCLUDE_WORDS` 新增 `许可证 / 登记证 / 所有权证 / 抵押证`, 防 `许`姓触发的术语误识别。
- 新增配置 `redaction.name_context.extra_tokens` (用户可扩展上下文词表, 例: `数据处理者 / 委托人 / 抵押人` 等)。

### 解决的具体误报案例
| 案例 | 根因 | 修复点 |
|---|---|---|
| `现甲、乙、丙、丁方经平等自愿…` → `丁方**` | jieba 切 "丁方经" 为 nr | 白名单邻接过滤 |
| `(大写：陆佰柒拾壹万…)` → `陆**拾壹万` | jieba 切 "陆佰柒" 为 nr | 大写金额字表 |
| 《建设用地规划许可证》→ `规划许**` | jieba 切 "许可证" 为 nr | 法律文书术语黑名单 |
| 后续任意 jieba nr 误报 | jieba nr 标注系统性不可靠 | 上下文注入 (本版本) |

### 兼容性
- `extract_person_names()` 默认 `require_context=False`, 旧调用零影响。
- WordWorker / OCRWorker 默认 `require_context=True` — 旧行为("本院认为张三"中识别张三)在该路径下不再命中, 但通过三层过滤仍能命中含 `EXCLUDE_WORDS` 之外的真名。
- `redaction.name_context` 缺失时回退内置默认词表, 无破坏性。
- 全量回归 **118/118 通过** (89 旧 + 29 新增上下文测试)。

### 已知覆盖率下降 (用户接受)
- 裸 nr 场景 (`本院认为张三的诉求成立` / `著作权人周强在…`) 在 `require_context=True` 下不再识别 — 设计预期, 用户已确认接受。
- 强上下文场景 (`原告：周强` / `经理张磊` / `法定代表人：曹炳志` / `起诉人：李四先生`) 全部保留识别。

---

## [1.1.12] - 2026-08-22 — 部分遮蔽 (Partial Masking) + USCC Word-Only 隔离

### Added
- **部分遮蔽 (Partial Masking)**: 内置脱敏规则从「整段打码 `*`」改为「保留前 N + 后 N 字符,中间 `*` 替换」:
  - 身份证号 (18位): 保留前 6 + 后 4 → `110101********1234`
  - 手机号码 (11位): 保留前 3 + 后 4 → `138****5678`
  - 银行卡号 (13-19位): 保留前 4 + 后 4 → `6222********1234`
  - 固定电话 (11-12位): 保留后 4 → `********5678`
  - 统一社会信用代码 (17-18位): 保留前 4 + 后 4 → `9151*********NK4W` / `9111**********YX29`
  - 法定代表人 / 姓名 (中文): 保留姓 → `张*` / `李**` / `欧***`
  - 电子邮箱 (特殊模式): `alice@example.com` → `a***@example.com`
  - 日期时间 / 地址: 整段打码(`********`)
- 新增工具模块 `secureredact/utils/masking.py`, 提供 `apply_partial_mask` / `apply_email_mask` / `apply_name_mask` / `resolve_mask_config` / `apply_mask_for_rule` 五个函数, 全部为纯函数。
- 新增配置字段(每条 `default_rule`): `mask_mode` / `mask_keep_prefix` / `mask_keep_suffix` / `mask_char`。
  - `mask_mode` 支持 `default` / `email` / `name`
  - 字段缺失时默认 `default + 0+0` → 等价整段打码(向后兼容 v1.1.11)
- 新增全局表 `DEFAULT_RULES_META`(main.py 模块常量),与 `DEFAULT_RULES` 平行,提供无 config 场景下的 fallback。
- **USCC Word-Only 隔离**(v1.1.11 起未发布): 新增「统一社会信用代码」脱敏规则, 仅作用于 Word 文档。
  - 通过 `redaction.pdf_excluded_rules` 配置项按规则名过滤 `pdf_rules`, USCC pattern 根本不进入 `OCRWorker.rules` 参数, 实现 PDF 路径完全隔离
  - UI 规则面板为 USCC 加 `📝 仅 Word` 标识

### 影响范围
- Word 智能扫描 (`WordWorker._find_matches`): `source="rule"` 命中且 `rule_name` 在 `DEFAULT_RULES_META` 中 → 应用 mask。
- Word 批量替换 (`build_word_rule_matches`): 用户 batch 规则继续用 `rule["replace"]`, 不参与 mask(向后兼容)。
- Word 双栏预览: 右栏自动显示 mask 后文本; 左栏仍显示原文 + 高亮(零代码改动,自动跟随 Phase C)。
- Word 写盘导出: `_save_word` 自动写 mask 后文本(零代码改动)。
- PDF 路径完全不受影响 — USCC 隔离机制保持,既有命中行为零变化。

### 兼容性
- 现有 config.json / config.json.template / DEFAULT_CONFIG 缺失 mask 字段 → `get_redaction_rules()` 通过 `setdefault` 补齐, 无破坏性。
- 用户 batch 规则(`custom find/replace 对`)行为完全不变。
- `source="manual"` 命中永远 passthrough(人工框选是显式意图)。
- jieba 来源命中仍走 `replacement_text`(避免 jieba 误识别导致 mask 错乱), 留作 v1.1.13 扩展。
- 想恢复「整段打码」行为: 把对应 rule 的 `mask_keep_prefix` 和 `mask_keep_suffix` 都设为 0。
- 想让 USCC 同时作用于 PDF: 删除 `redaction.pdf_excluded_rules` 中的 `"统一社会信用代码"`。

### 项目里程碑
- 本版本完成「部分遮蔽」与「USCC Word-Only 隔离」两项核心能力, 法律文档脱敏语义可读性显著提升。
- USCC 隔离机制确保 PDF 路径既有行为零变化(已通过 286 项回归 + 7 项既有失败不扩大验证)。

---

## [1.1.11] - 2026-08-20 — 白名单片段级豁免 (Whitelist Span Trim)

### Added
- **白名单片段级豁免**：白名单条目仅豁免自身所在片段，同 hit 区间内的其他敏感内容仍然脱敏。
  - 例：「法定代表人：周超」+ 白名单「法定代表人」→ 「法定代表人」不脱敏，「周超」仍然脱敏。
- 新增开关 `redaction.whitelist_trim_only`（默认 `true`）。设为 `false` 回退到子串命中即整条剥掉行为。
- 新增模块 `secureredact/redaction/whitelist_split.py` 与静态工具 `OCRWorker._sub_rect_for_text_span`（CJK 字符权重比例估算）。

### 影响范围
- Word 段落 / 表格 matches（rule / jieba / blacklist）
- PDF 文本通道 hits（rule / jieba / custom_keyword）
- PDF 图片通道 OCR hits
- `source="manual"` 命中永远 passthrough（人工框选是显式意图）
- `source="seal"` 命中 passthrough（text 为空，无可裁剪语义）
- 多行 hit 走保守回退（整条剥掉）

### 兼容性
- 子 hit 的 `hit_id` 因 start/end 变化而独立，不与原 hit 的永久 override 关联。
- 想恢复旧行为：设 `"redaction.whitelist_trim_only": false`。

### 已知限制
- **PDF 图片通道 OCR hits** (`source="ocr"` 且 `hit.text=""`) 不走 trim，回退到整条剥掉。图片通道 trim 的完整实现留待后续版本。

### 项目里程碑
- 本版本作为项目重置后的第一个正式发布版本号。早期历史版本信息已从项目文档中清理。