# SecureRedact 信息脱敏助手 - 更新日志

本文档记录了 SecureRedact 信息脱敏助手的所有重要更新。

---

## [1.1.15] - 2026-11-15 — 配置路径统一 + 发布就绪收口

> 本次发布把阶段 B/C/V 重构(66 个 commit)从工作分支合入 `main` 并首次打正式 tag。
> 核心目标是消除「代码写完但用户用不了 / 打包版残缺 / CI 长期全红」三类阻塞。

### Fixed

- **🔴 配置双源分裂(最高优先级)**: `SimpleConfig` 的默认路径此前指向
  `secureredact/config.json`(只含 `redaction` 子集), 而 `ConfigManager` 指向仓库根
  `config.json`。运行时实际用 `SimpleConfig` → **用户在根 `config.json` 里的所有设置
  运行期读不到**, 且打包版只打进根配置 → 配置 100% 丢失。
  - 新增 `secureredact/utils/config.py::resolve_config_paths()` 统一路径解析:
    开发树 = 仓库根 / 冻结 = `_MEIPASS` / 只读安装 = `~/.secureredact`
  - `SimpleConfig` 改为三段式读取: 出厂基线(只读) < 用户配置(覆盖) > 写回可写位置
  - `ConfigManager` 改用同一解析函数, 两套系统不再读不同文件
  - **删除 `secureredact/config.json`**(双源元凶; 内容是根配置的子集, 无信息丢失)
  - 连带修复: `redaction.name_context.extra_tokens` 等此前读不到的配置项重新生效
- **🔴 打包版版本号错乱**: 三个 PyInstaller spec 的 `datas` 都没包含 `version.txt` →
  冻结后落到 fallback `1.1.12`, 而 EXE 属性是真实版本 → 「窗口标题 / 关于窗口 /
  EXE 属性」三处版本号互相打架。现三份 spec 均补 `version.txt`;
  `SecureRedact_Setup.iss` 默认版本同步; `main.py` / `secureredact/__init__.py` /
  `ui/main_window/window.py` 三处版本 fallback 统一为 `1.1.15`。
- **🔴 主题切换永不落盘**: `MainWindowThemeMixin.set_theme()` 先 import 模块级 config
  singleton, 下一行又用 `config = getattr(self, "config", None)` 局部遮蔽它, 而
  `MainWindow` 从不设置 `self.config` → 持久化永远不执行(切主题后重启归位)。
- **🔴 主题配置键不一致**: 出厂 `config.json` / `DEFAULT_CONFIG` 用 `ui.theme`, 而代码
  读写的是 `app.theme` → 用户设的主题从来没被读过。现读写统一到 `ui.theme`,
  `"auto"` 归一为 `"system"`(跟随系统外观)。
- **🟠 配置项静默失效**: `ocr.zoom_min` / `ocr.zoom_max` / `ocr.progress_update_interval` /
  `app.name` 四项因硬编码副本而改配置不生效, 现全部改回 config 派生
  (`secureredact/__init__.py`、`workers/ocr_worker.py`、`workers/word_worker.py`)。
- **🟠 DEBUG_MODE 三处两义**: `canvas.py` 只读 env、`window.py` 的三元表达式在 config
  存在时**完全忽略 env**。现统一为「env 开启 OR config 开启」。
- **🟠 规则重叠导致重复遮蔽**: 18 位身份证号会同时命中「身份证号 / 统一社会信用代码 /
  银行卡号」三条字符集高度重叠的规则 → 命中数翻 3 倍、遮蔽边界不一致。
  新增 `secureredact/redaction/conflict_resolver.py`, 按优先级
  (身份证号 > USCC > 银行卡号) 消解重叠命中; 仅对这三条数字类规则生效,
  其他规则行为完全不变。
- **🟠 桌面端 QSS 占位符泄漏**: `glass.GLASS_AVAILABLE` 在导入期求值且无 QApplication
  实例时 `platformName()` 返回无意义默认值 → 判定玻璃可用 → `get_glass_substitution()`
  返回空 dict → `{card_background}` / `{dock_background}` 原样残留在最终 QSS,
  Qt 解析失败导致卡片/停靠面板背景色失效。现 `loader._build_mapping()` 对两个占位符
  做主题 token 兜底, 且 `_detect_glass()` 要求 QApplication 实例真实存在。
- **🟠 CI 视觉回归脚本无法运行**: `scripts/render_visual_baseline.py` 未把仓库根加入
  `sys.path` → CI 里报 `ModuleNotFoundError: No module named secureredact`。现已修复,
  任意 cwd 可运行。

### Changed

- **版本号**: `version.txt` 1.1.13 → **1.1.15**(代码早已包含 v1.1.14 的并列名单上下文
  与 `extra_tokens` 接通能力, 但版本号从未同步)。
- **CI 覆盖率门禁**: `secureredact/api.py` 覆盖率 91.14% → **100%**
  (新增 8 个 API 测试, 22 → 30 例), `--cov-fail-under=100` 退出码由 1 转 0。
- **打包链路**:
  - macOS `build_macos_app.sh` 原检查从不存在的 `SecureRedact.icns` → 100% 退出失败,
    现改为 spec 实际使用的 `assets/logo/macos/AppIcon.icns`
  - macOS spec 补 `LICENSE`(GPL-3.0 分发要求); Inno Setup 补 `LicenseFile` + LICENSE 复制
  - 新增 `packaging/requirements-build.txt` 锁定 `pyinstaller==6.18.0` +
    `pyinstaller-hooks-contrib==2026.10`(jieba 的 5MB 中文词典只靠 hooks-contrib 的
    `hook-jieba.py` 进包, 失效则打包版姓名识别静默失效); 根 `requirements.txt` 同步锁版
  - 新增 `packaging/verify_spec_datas.py` 静态预检并接入 3 个构建脚本:
    产物缺 `version.txt` / `config.json` / `LICENSE` 即构建失败(把静默退化变成构建失败)
  - `verify_dependencies.py` 依赖清单 11 → 17 项, 并校验 hook 存在性
  - `SecureRedact_windows_v2.spec`(死代码) 加醒目警示, 避免后人误启用
- **测试滞后修复(16 项)**: 断言锚点从已变形的 `main.py` 迁到真实实现所在模块
  (`redaction/rules_loader.py` / `ui/main_window/theme.py` / `secureredact/__init__.py`);
  路径校验用例去掉写死的 Windows 用户目录; 白名单断言改为结构断言;
  jieba 样本改为带强上下文的文本。

### Fixed (CI 真实执行后追加)

- **CI 首次真实执行暴露的三个阻断**(此前被 `pip install ... || true` 与本地环境掩盖):
  1. **onnxruntime DLL 崩溃** —— `numpy 2.4.2` + `onnxruntime 1.32.0` 与 PyQt6 + cv2 同时载入时
     onnxruntime DLL 触发 access violation(0xC0000005), **整个 pytest 进程崩溃**。
     `requirements.txt` 的 `onnxruntime>=1.24.1` 无上限 → CI 装到了无人验证过的 1.32.0。
     现锁回实测通过的 `numpy==2.3.1` + `onnxruntime==1.28.0`。
  2. **numpy 被重复加载** —— `secureredact/ocr/base.py` 与 `ocr/rapidocr.py` 的模块级
     `import numpy` 把 numpy 拖进 `secureredact.api` 的导入链, 在 coverage 预导入场景触发
     numpy 2.4 的 `cannot load module more than once per process` 硬错误 → api 覆盖率掉到 5%。
     两处 numpy **仅用于类型标注**, 改为 `if TYPE_CHECKING:` 导入(符合本项目「包导入惰性化」原则)。
  3. **依赖安装失败被静默吞掉** —— CI 的 `pip install -r requirements.txt || true` 会让依赖
     装不上时继续跑, 缺 PyQt6/PyMuPDF 时整批用例变 skip, **CI 照样变绿**。现已去掉 `|| true`。
### CI 首次全绿(2026-11-15 真实执行)

本次发布是 SecureRedact **历史上第一次在 GitHub Actions 上真正跑通 CI**。
在此之前 `main` 上的每一次 CI 运行结果都是 `failure`(可查 2026-08-31 / 09-01 / 11-15 的历史 run),
原因被 `pip install ... || true` 与从未同步的依赖版本共同掩盖。

| CI job | 结果 |
|---|---|
| test (Python 3.11, windows-latest) | ✅ success |
| test (Python 3.13, windows-latest) | ✅ success |
| test (Python 3.11, ubuntu-latest) | ✅ success |
| test (Python 3.13, ubuntu-latest) | ✅ success |

每个 job 的 10 个 step 中前 9 个在两个平台全绿; 第 10 步(视觉回归)按平台特性
限定为 `windows-latest`(像素基线只对生成平台成立)。

### 视觉基线的一个发现

重新生成基线时发现: 旧的 `settings_dialog_light.png` 与 `settings_dialog_dark.png`
**sha256 完全相同** —— 说明设置中心的 dark 主题**根本没有生效**(QSS 里的
`{card_background}` 占位符残留导致解析失败)。玻璃占位符修复后两者终于渲染出
不同结果, 这也解释了 CI 上 14.5%~20.8% 的异常差异。
### Verification

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 全量 pytest | 604 用例 / **20 失败** | **683 用例 / 0 失败 / 0 错误** |
| `secureredact/api.py` 覆盖率 | 91.14% (门禁退出码 1) | **100%** (退出码 0) |
| `compileall` | — | 退出码 0 |
| 打包 spec 静态预检 | 无 | 退出码 0 |

新增回归测试: `tests/unit/test_config_path_resolution.py`、`
`tests/unit/test_version_fallback_sync.py`、
`tests/unit/test_rule_conflict_resolution.py`, 以及 `test_api.py` 新增 8 例。

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

## [1.1.14] - 2026-08-25 — 并列名单上下文 + extra_tokens 接通

### Fixed
- **`甲方与李秋实、孙毅、李洪赢…之间借款合同纠纷` 类并列名单漏识**:
  v1.1.13 默认严格模式 (`require_context=True`) 在「前缀词到第一个人名中间隔着公司名/汉字」时失效 (前缀紧邻路径与列表传递路径都不覆盖)。本版本补两层修复:
  - **枚举式前缀上下文**: `prefix + 与/和/跟/同/及 + list + 之间/于/…` 整体正则匹配, 列表内所有姓名视同有上下文。
    适用场景: `甲方与 A、B、C 之间…` / `原告张三、李四、王五另案…` / `借款人孙十、钱十一未按期偿还…`。
  - **列举式传递 (迭代到不动点)**: 已识别的 candidate 后续用 `顿号/逗号/分号` 直接相邻的名字也视同有上下文。
    适用场景: 多元素列表 (`甲方与 A、B、C、D 之间…`)。
- **`_INSIDE_CHARS` 加顿号 `、` 等**: 原集合不含顿号, 导致 `_name_has_prefix_context` 在「prefix + 顿号 + name」结构中断。本版本补 `、·/／—–-&＆`。

### Changed
- **`STRONG_PREFIX_TOKENS` 扩词 (v1.1.14)**:
  - 合同/债权角色: `甲方 / 乙方 / 丙方 / 丁方 / 戊方 / 己方 / 庚方 / 辛方 / 壬方 / 癸方` / `借款人 / 出借人 / 贷款人 / 债务人 / 债权人` / `保证人 / 连带保证人 / 一般保证人 / 担保人 / 反担保人` / `抵押人 / 抵押权人 / 出质人 / 质权人`。
  - 动机: 抵账协议/债权转让/借款合同等场景中, 当事人常以「甲方与 xxx、xxx 之间」格式并列出现。
- **`redaction.name_context.extra_tokens` 接通运行时**:
  CHANGELOG v1.1.12 引入但代码一直未读取的配置项, 本版本打通:
  - `name_context.py`: `filter_names_by_context()` / `_name_has_prefix_context()` 接收 `extra_prefix_tokens` 参数, 与默认词集合并。
  - `name_recognizer.py`: `ChineseNameRecognizer.extract()` / `extract_person_names()` 新增 `extra_prefix_tokens: Optional[List[str]]` 参数 (向后兼容, 默认 None)。
  - `WordWorker.__init__` / `OCRWorker.__init__` 新增 `name_context_extra_tokens` 参数, 默认 `[]` (向后兼容)。
  - `main.py`: WordWorker (11434) / OCRWorker (11416) 实例化点从 `self.config.get("redaction.name_context.extra_tokens", [])` 读取并注入。
  - 作用: 用户可在 `config.json` 自定义行业专属前缀词 (例: 信托合同加 `受托人 / 委托人`, 数据合同加 `数据处理者 / 数据控制者`), 无需改代码。

### Added (测试)
- `tests/unit/test_name_context.py` 新增 `TestPartyRolePrefix` (8 例): 甲方/乙方/丙方/丁方/借款人/债务人/债权人/保证人 前缀识别 + 并列名单识别。
- `tests/unit/test_name_context.py` 新增 `TestExtraPrefixTokensInjection` (5 例): extra_prefix_tokens 注入 / None fallback / 空 frozenset / list iterable / 不影响强标签模式。
- `tests/unit/test_worker_name_recognition.py` 新增 `TestWorkerNameContextExtraTokens` (4 例): WordWorker / OCRWorker 接收 `name_context_extra_tokens` 参数并存到 `self.name_context_extra_tokens`。

### 兼容性
- `extract_person_names()` 新参数 `extra_prefix_tokens` 默认 None — 旧调用零影响。
- WordWorker / OCRWorker 新参数 `name_context_extra_tokens` 默认 `[]` — 旧调用零影响。
- `STRONG_PREFIX_TOKENS` 扩词不破坏现有 42 例上下文测试 (全部 PASS)。
- `name_context` 配置项 (`extra_tokens`) 即使为空 list / 缺失, 行为与 v1.1.13 完全一致。

### 解决的具体漏识案例
| 案例 | 修复点 |
|---|---|
| `甲方与李秋实、孙毅…之间` → 全部 `**` | 枚举式前缀上下文 + 列举式传递 |
| `乙方张磊、李四共同出资` → `乙方张**`/`李**` | `乙方` 加进 STRONG_PREFIX_TOKENS |
| `借款人孙十、钱十一未按期偿还` → `**十`/`**十一` | `借款人` 加进 STRONG_PREFIX_TOKENS |
| `数据处理者周强在协议中签字` → `**强` (用户配置 extra_token) | extra_prefix_tokens 注入 |

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