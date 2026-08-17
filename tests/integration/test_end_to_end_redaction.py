# -*- coding: utf-8 -*-
"""
端到端模拟: 起诉状 PDF 文本 → OCRWorker 命中规则 → 验证脱敏覆盖.

复现《周强起诉状_GUI模式脱敏.pdf》3 页文本,使用与 OCRWorker 完全相同的
all_patterns 逻辑,验证默认规则 + 姓名识别启用后的覆盖情况.
"""
import re
import unittest
from unittest.mock import patch

# 起诉状 3 页文本(模拟 OCR 输出)
PDF_PAGE_TEXTS = [
    # Page 1 — 传票
    """吉林市船营区人民法院
传票
案号：（2025）吉0204民初5965号
案由：侵害作品信息网络传播权纠纷
被传唤人：吉林铁道职业技术大学
住所：吉林省吉林市永吉经济开发区吉桦东路1号
传唤事由：开庭
应到时间：2025年10月15日 10:00
应到处所：吉林市船营区人民法院七法庭-讯飞融合
""",
    # Page 2 — 起诉状
    """民事起诉状
原告：周强，男，1985年3月5日生，汉族，身份证号：110101198503078899，
住址：河北省保定市唐县迷城乡西迷城村二区144号，联系电话：13912345678。

被告：吉林铁道职业技术大学；住所地：吉林省吉林市永吉经济开发区吉桦东路1号；
法定代表人：曹炳志；联系方式：0432-6613680/0432-6420599/0432-6420799；
统一社会信用代码：12220000X05293527B 案由：侵害作品信息网络传播权纠纷

原告于2025年1月15日，著作权人周强在贵州省版权局完成作品登记。
登记号为【黔作登字-2025-F-01652484】的美术（禁止游泳）作品
""",
    # Page 3 — 起诉状尾部
    """发布的：(https://mp.weixin.qq.com/s/fK9utrlJuCKYxMV83eLlVQ)
中未经授权擅自使用案涉作品。
2025年9月10日，经委托重庆易保全网络科技有限公司对被告
的侵权行为进行证据保全公证。

起诉人：周强
"""
]


def build_default_rules_patterns():
    """复刻 main.py DEFAULT_RULES 字典(同步步骤 1/3 + 步骤 4 默认规则)."""
    return [
        r"(?<!\d)([1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]|\d{15})(?!\d)",  # 身份证号
        r"(?<!\d)(1[3-9]\d{9})(?!\d)",  # 手机号
        r"\d{4}[年\-\.]\d{1,2}[月\-\.]\d{1,2}[日]?",  # 日期
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # 邮箱
        r"(?<!\d)([1-9]\d{12,18})(?!\d)",  # 银行卡
        r"[一-龥]{2,15}(?:省|市|自治区|特别行政区)[一-龥\d\s,]{4,40}\d+号",  # 地址
        r"(?<!\d)0\d{2,3}[-\s]?[\d\w]{7,8}(?!\d)",  # 固定电话
        r"法定代表人\s*[::：]?\s*[一-龥]{2,4}(?:·[一-龥]{2,4})?",  # 法定代表人
    ]


def hit_patterns(text, patterns, extra_patterns=None):
    """模拟 OCRWorker 的命中逻辑,返回 (pattern_idx, match_text) 列表."""
    hits = []
    all_pats = list(patterns)
    if extra_patterns:
        all_pats.extend(extra_patterns)
    for idx, pat in enumerate(all_pats):
        for m in re.finditer(pat, text):
            hits.append((idx, m.group(0), m.start(), m.end()))
    return hits


class TestEndToEndRedaction(unittest.TestCase):
    """复现起诉状 3 页的脱敏覆盖情况."""

    def setUp(self) -> None:
        self.patterns = build_default_rules_patterns()

    def test_page1_default_rules_only(self):
        """Page 1 仅靠默认规则应命中案号、日期."""
        hits = hit_patterns(PDF_PAGE_TEXTS[0], self.patterns)
        hit_texts = [h[1] for h in hits]
        # 应命中
        self.assertTrue(any("（2025）" in t or "5965" in t for t in hit_texts),
            f"应命中案号, 实得 {hit_texts}")
        self.assertTrue(any("10:00" in t or "2025" in t for t in hit_texts),
            f"应命中日期, 实得 {hit_texts}")

    def test_page2_default_rules_only(self):
        """Page 2 默认规则应命中身份证号、手机号、地址、固定电话、法定代表人."""
        hits = hit_patterns(PDF_PAGE_TEXTS[1], self.patterns)
        hit_texts = [h[1] for h in hits]
        # 身份证号
        self.assertTrue(any("110101198503078899" in t for t in hit_texts),
            f"应命中身份证号, 实得 {hit_texts}")
        # 手机号
        self.assertTrue(any("13912345678" in t for t in hit_texts),
            f"应命中手机号, 实得 {hit_texts}")
        # 地址
        self.assertTrue(any("河北省" in t and "144号" in t for t in hit_texts),
            f"应命中地址, 实得 {hit_texts}")
        # 固定电话
        self.assertTrue(any("0432-6613680" in t for t in hit_texts),
            f"应命中固定电话, 实得 {hit_texts}")
        # 法定代表人: 整段"法定代表人：曹炳志"
        self.assertTrue(any("曹炳志" in t for t in hit_texts),
            f"应命中法定代表人姓名, 实得 {hit_texts}")

    def test_page3_default_rules_only(self):
        """Page 3 默认规则应命中日期."""
        hits = hit_patterns(PDF_PAGE_TEXTS[2], self.patterns)
        hit_texts = [h[1] for h in hits]
        # 日期 2025年9月10日
        self.assertTrue(any("2025" in t and "9" in t for t in hit_texts),
            f"应命中日期, 实得 {hit_texts}")

    def test_page2_plaintiff_name_with_heuristic(self):
        """Page 2 启用姓名识别后,应额外命中'周强'(原告段+著作权人段)."""
        hits = hit_patterns(PDF_PAGE_TEXTS[1], self.patterns)
        hit_texts_before = [h[1] for h in hits]

        # 模拟开启姓名识别后追加到 all_patterns
        with patch("privacyguard.workers.ocr_worker.QThread.__init__",
                   new=lambda self: None):
            # 调用识别器 (跳过 jieba 冷启动)
            from privacyguard.pii.name_recognizer import extract_person_names
            names = extract_person_names(PDF_PAGE_TEXTS[1])

        self.assertIn("周强", names,
            f"姓名识别应命中'周强', 实得 {names}")

    def test_page3_plaintiff_signature_with_heuristic(self):
        """Page 3 启用姓名识别后,应命中签名'周强'."""
        from privacyguard.pii.name_recognizer import extract_person_names
        names = extract_person_names(PDF_PAGE_TEXTS[2])
        self.assertIn("周强", names,
            f"姓名识别应命中签名'周强', 实得 {names}")

    def test_url_redaction_not_covered(self):
        """微信公众号 URL 仍不会被默认规则覆盖(已知遗留项)."""
        hits = hit_patterns(PDF_PAGE_TEXTS[2], self.patterns)
        hit_texts = [h[1] for h in hits]
        # 文档明确告知该 URL 是已知遗留
        self.assertFalse(any("mp.weixin.qq.com" in t for t in hit_texts),
            "URL 规则未实现(预期行为,本 Phase 不覆盖)")


if __name__ == "__main__":
    unittest.main()