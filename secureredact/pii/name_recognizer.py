# -*- coding: utf-8 -*-
"""
中文姓名启发式识别器 (X3 方案).

jieba.posseg.cut 标注人名 + 姓氏表准入 + 黑名单过滤 + 上下文加权.

设计原则:
- 默认懒加载,jieba 词典缺失/导入失败时静默回退到空 list
- 单例模式,但每个调用都创建新实例的成本可控
- 严格仅识别法律文书高频姓名,避免误伤普通词
"""
from __future__ import annotations

import logging
import re
import threading
from typing import FrozenSet, List, Optional

logger = logging.getLogger(__name__)


# 姓氏集合: 百家姓常用单姓 + 复姓
SURNAME_SET: FrozenSet[str] = frozenset(
    # 常见单姓 (百家姓高频前 100)
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆"
    "萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵"
    "席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢"
    "莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁"
    "荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗"
    "班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀"
    "蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰"
    "郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容"
    "向古易慎戈廖庚终暨居衡步都耿满弘匡国文寇广禄阙东殴殳沃利蔚越夔隆师"
    "巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查後荆红游竺权"
    "逯盖益桓公"
    # 百家姓高频补充 (v1.1.11 regression fix): 漏"付"姓导致"付明义"等姓名被漏识别
    "付"
    # 复姓 (常见 30+)
    "欧阳司马上官诸葛东方皇甫尉迟公孙令狐宇文慕容长孙慕容司徒司空"
)

# 黑名单: 法律文书高频非人名词
EXCLUDE_WORDS: FrozenSet[str] = frozenset({
    # 法律程序词
    "陈述", "答辩", "代理", "审查", "审判", "裁定", "判决", "起诉",
    "脱敏", "通知", "公告", "送达", "不予", "认为", "应当", "本院",
    "原告", "被告", "上诉人", "被上诉人", "申请人", "被申请人",
    "管辖", "应诉", "反诉", "撤诉", "驳回", "调解", "执行", "保全",
    "开庭", "举证", "质证", "辩论", "宣判",
    # 角色/机构
    "代理人", "审判员", "陪审员", "书记员", "律师", "公证人", "检察官",
    "审判长", "审判员", "人民陪审员", "委托代理人", "法定代理人",
    "法定代表人", "指定代理人", "诉讼代理人", "辩护人",
    # 国家/机构/方向
    "中国", "中华", "本公司", "本行", "本院", "本所", "本机关",
    "东北", "西南", "东南", "西北", "南北", "东西",
    "中央", "省市", "县区",
    # 法律文书高频术语 (v1.1.11 fix: 防 '许'姓触发的 '许可证' 类误识别)
    # jieba 倾向把内含 SURNAME 字的 3 字术语切成 nr;这些术语显然非人名
    "许可证", "登记证", "所有权证", "抵押证",
})

# 头衔/称谓词 (前后相邻出现时辅助识别)
TITLE_TOKENS: FrozenSet[str] = frozenset({
    "先生", "女士", "同志", "经理", "董事", "总裁", "局长", "主任",
    "书记", "院长", "校长", "老师", "教授", "博士", "律师", "法官",
    "检察官", "审判长", "审判员", "书记员",
})

# 长度边界
_MIN_NAME_LEN = 2
_MAX_NAME_LEN = 4


# 人民币大写金额字表 (GB/T 16173 / 央行支付办法).
# 凡是 token 文本剔标点后所有汉字都属于该字表, 即视为大写金额片段,
# 结构性免疫 — 不当作人名, 避免 '陆佰柒' (内含 SURNAME 字 '陆') 被误判.
AMOUNT_CHARS: FrozenSet[str] = frozenset(
    "零壹贰叁肆伍陆柒捌玖"   # 大写数字 0-9
    "拾佰仟万亿"             # 整数单位: 十/百/千/万/亿
    "圆元角分整正负"         # '圆'(简) '元'(繁) + '角'/'分' + '整'/'正'/'负' 标记
)
_AMOUNT_PUNCT_RE = re.compile(
    r"[\s　()（）:：。，,。.\-_/\\|、；;]"
)


def _is_amount_word(text: str) -> bool:
    """判断 token 文本是否像人民币大写金额片段.

    判定: 剔除常见中英文标点 / 空白后, 所有汉字都属于 AMOUNT_CHARS.
    - 空串 / 无汉字 / 任一汉字不在字表 → 否.
    - 含非汉字字符 (字母 / 数字) → 否 (避免 '陆佰A' 这类怪异组合被误豁免).

    动机: 防 jieba 把 '陆佰柒' (内含 SURNAME 字 '陆') 切成 nr 人名. 详见
    tests.unit.test_name_recognizer.TestRecognizerAmountWordImmunity.
    """
    if not text:
        return False
    stripped = _AMOUNT_PUNCT_RE.sub("", text)
    if not stripped:
        return False
    has_chinese = False
    for ch in stripped:
        if "一" <= ch <= "鿿":
            has_chinese = True
            if ch not in AMOUNT_CHARS:
                return False
        else:
            # 含非汉字 (字母 / 数字 / 其他) → 判定为非纯金额
            return False
    return has_chinese


class ChineseNameRecognizer:
    """中文姓名启发式识别器 (X3 方案).

    线程安全: 实例方法无状态,可被多线程共享.
    """

    def __init__(self) -> None:
        # jieba 导入懒处理: 第一次调用时才真正引入
        self._posseg_module = None
        self._init_lock = threading.Lock()
        self._initialized = False

    def _ensure_jieba(self) -> None:
        """确保 jieba.posseg 可用; 失败时静默置空."""
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            try:
                import jieba.posseg as pseg  # type: ignore
                self._posseg_module = pseg
            except Exception as exc:  # ImportError / pkg_resources / etc.
                logger.warning(
                    "jieba.posseg 初始化失败,姓名识别回退到空结果: %s", exc)
                self._posseg_module = None
            self._initialized = True

    def extract(
        self,
        text: Optional[str],
        whitelist: Optional[List[str]] = None,
        require_context: bool = False,
    ) -> List[str]:
        """从文本中抽取候选姓名,返回去重后保序的列表.

        - 输入空 / None / 非字符串: 返回 []
        - jieba 不可用: 返回 []
        - 多个同名: 仅返回一次
        - whitelist (v1.1.11 fix): 若提供且非空,凡是 token 文本 **包含** 任一非空白名单
          子串的候选,均不返回 (substring 匹配, 与 BlackWhiteListStore 语义一致).
          动机: 防 jieba 把 '丁方经' 切成 nr 人名,造成白名单邻接误报. 详见
          tests.unit.test_name_recognizer.TestRecognizerWhitelistFiltering.
        - require_context (v1.1.12): 若为 True, 进一步收紧 — 仅保留在原文中
          至少有一处强上下文 (强前缀 / 强后缀 / 强标签) 的候选. 大幅降低 jieba
          启发式的 nr 误报 (e.g. '规划许可证'/'陆佰柒'), 但代价是无显式上下文的
          真实姓名会漏识. 默认 False (向后兼容, 三层过滤保留全部). 详见
          tests.unit.test_name_recognizer.TestRecognizerContextFiltering 与
          tests.unit.test_name_context.filter_names_by_context.
        """
        if not isinstance(text, str) or not text:
            return []

        self._ensure_jieba()
        if self._posseg_module is None:
            return []

        try:
            tokens = list(self._posseg_module.cut(text))
        except Exception as exc:
            logger.warning("jieba.posseg.cut 失败: %s", exc)
            return []

        # whitelist 预处理: strip 后去空, 保留用户语义. None / [] / 全空白 → 不过滤
        wl_eff: List[str] = []
        if isinstance(whitelist, list):
            for w in whitelist:
                if isinstance(w, str):
                    s = w.strip()
                    if s:
                        wl_eff.append(s)

        candidates: List[str] = []
        for token in tokens:
            word = token.word
            flag = token.flag

            # 词性必须以 nr 开头 (覆盖 nr / nrfg / nrf 等 jieba 细分)
            if not flag.startswith("nr"):
                continue

            # 长度必须在 2-4
            if not (_MIN_NAME_LEN <= len(word) <= _MAX_NAME_LEN):
                continue

            # 黑名单过滤
            if word in EXCLUDE_WORDS:
                continue

            # 大写金额结构性免疫: '陆佰柒' / '壹拾陆' 等内含 SURNAME 字
            # 的金额片段, 一律不当作人名. 早于白名单邻接过滤执行 —
            # 金额免疫是结构性硬规则, 不依赖用户配置.
            if _is_amount_word(word):
                continue

            # 姓氏首字校验: 必须以 SURNAME_SET 中的字开头
            # 兼容 · 分隔的复姓名(如 "买买提·阿凡提")
            first_char = word[0]
            if first_char not in SURNAME_SET:
                # 复姓情形: 前两字应在复姓集合
                if len(word) >= 3 and word[:2] in SURNAME_SET:
                    pass  # 通过
                else:
                    continue

            # 白名单邻接过滤: token 文本包含任一非空白名单子串 → 不当作人名
            # 防 '丁方经' / '戊方经' / '丁方代理人' 这类粘连伪人名
            if wl_eff and any(wl in word for wl in wl_eff):
                continue

            candidates.append(word)

        # 去重保序
        seen: set = set()
        unique: List[str] = []
        for name in candidates:
            if name not in seen:
                seen.add(name)
                unique.append(name)

        # v1.1.12: 上下文过滤 (方案 B 双轨制的实际语义)
        # 仅当 require_context=True 时, 进一步收紧为 '在原文中有上下文' 的候选.
        # 注意: 此步骤不感知 whitelist; whitelist 邻接过滤已在更早阶段执行.
        if require_context and unique:
            # 局部 import 避免循环依赖 + 启动开销
            from secureredact.pii.name_context import filter_names_by_context
            unique = filter_names_by_context(text, unique)

        return unique


# 单例 + 便捷函数
_default_recognizer: Optional[ChineseNameRecognizer] = None
_recognizer_lock = threading.Lock()


def _get_default_recognizer() -> ChineseNameRecognizer:
    global _default_recognizer
    if _default_recognizer is None:
        with _recognizer_lock:
            if _default_recognizer is None:
                _default_recognizer = ChineseNameRecognizer()
    return _default_recognizer


def extract_person_names(
    text: Optional[str],
    whitelist: Optional[List[str]] = None,
    require_context: bool = False,
) -> List[str]:
    """便捷函数: 调用默认单例识别.

    whitelist / require_context 语义与 ChineseNameRecognizer.extract 完全一致 — 向后兼容, 默认 None / False.
    """
    return _get_default_recognizer().extract(
        text, whitelist=whitelist, require_context=require_context,
    )