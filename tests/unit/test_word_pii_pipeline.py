"""Phase 3 Word 端到端 PII 流程测试（D-13 — 79/79 升级 88/88）。

5 + 1 个测试类共 7 + 4 个测试方法（Wave 1 → Wave 2 GREEN）：

- TestWordAdapterCollectUnits — WordAdapter.collect_units 段落 + 表格 双向映射
- TestWordPIIAutoTrigger — PIIEngine.detect 在 Word 文本中命中 6 类以上实体
- TestWordRedactRoundTrip — redact_word 真脱敏 + 反向断言 SAFE-02
- TestWordDocumentPropertiesCleared — clear_word_doc_props 清 5 core + revision=1
- TestWordMergePriorityRulePiManualOcr — priority 锁定 rule > pii > manual > ocr
- TestWordPIIPanelHighlights — cp27 增量 patch 契约 + 短码徽章 + partial mask 渲染
"""
import os
import tempfile
import unittest
from types import MethodType
from unittest.mock import Mock

from docx import Document
from PyQt6.QtWebEngineWidgets import QWebEngineView

from privacyguard.pii.engine import PIIEngine
from privacyguard.pii.hits import TextUnit
from privacyguard.pii.mask import mask_for_entity

from tests.fixtures.fake_pii import (
    fake_bank_account,
    fake_bank_card,
    fake_email,
    fake_id_card,
    fake_phone,
    fake_uscc,
    fake_vat_invoice_20,
)
from tests.fixtures.fake_word import build_fake_docx


class TestWordAdapterCollectUnits(unittest.TestCase):
    """WordAdapter.collect_units 段落 + 表格双向映射。"""

    def test_collect_units_returns_text_unit_per_block(self):
        """collect_units 至少返回与段落数 + 单元格数一致的 TextUnit 列表 + key_index 映射。"""
        path = build_fake_docx(paragraphs=["段落 0", "段落 1"])
        try:
            from privacyguard.word import WordAdapter
            units, key_index = WordAdapter.collect_units(path)
            self.assertGreaterEqual(len(units), 2)
            # key_index 的所有 value 字符串必须能在 word_data 中被引用
            for key in key_index.values():
                self.assertIsInstance(key, str)
        finally:
            os.remove(path)


class TestWordPIIAutoTrigger(unittest.TestCase):
    """PIIEngine.detect 在 Word 文本中命中 6 类以上实体（9 类可见）。"""

    def test_engine_detects_pii_in_word_text(self):
        """构造含 7 类 PII 的 Word 文本，断言 entity_types >= 6。"""
        text = (
            f"身份证 {fake_id_card()} "
            f"手机 {fake_phone()} "
            f"邮箱 {fake_email()} "
            f"卡号 {fake_bank_card()} "
            f"统一信用代码 {fake_uscc()} "
            f"发票 {fake_vat_invoice_20()} "
            f"账号 {fake_bank_account()}"
        )
        engine = PIIEngine()
        hits = engine.detect(TextUnit(page_index=0, text=text, source='text'))
        entity_types = {h.entity_type for h in hits}
        self.assertGreaterEqual(
            len(entity_types), 6,
            f"期望 ≥6 类 PII 命中，实际 {len(entity_types)}: {entity_types}",
        )
        # 关键类别必须命中
        for required in ('CN_ID_CARD', 'CN_PHONE', 'CN_EMAIL', 'CN_BANK_CARD', 'CN_USCC'):
            self.assertIn(required, entity_types, f"必须命中 {required}")


class TestWordRedactRoundTrip(unittest.TestCase):
    """redact_word 真脱敏 + 反向断言 SAFE-02（导出 docx 不含原文敏感字串）。"""

    def test_redact_word_partial_mask_visible(self):
        """构造含身份证的段落，redact_word + clear_word_doc_props 后导出 docx 不含原文 + 含 partial mask。"""
        from privacyguard.word.redact import redact_word
        from privacyguard.word.clear_doc_props import clear_word_doc_props
        from main import merge_word_matches_with_priority

        secret_id = fake_id_card()
        path = build_fake_docx(paragraphs=[f"原文 {secret_id}"])
        try:
            word_data = {
                "paragraph_0": {
                    "text": f"原文 {secret_id}",
                    "ocr": [],
                    "manual": [],
                    "pii": [],
                }
            }
            engine = PIIEngine()
            hits = engine.detect(TextUnit(page_index=0, text=word_data["paragraph_0"]["text"], source='text'))
            word_data["paragraph_0"]["pii"] = hits

            doc = Document(path)
            merged = merge_word_matches_with_priority(
                word_data["paragraph_0"]["text"],
                rules=[],
                default_replacement_text="[已脱敏]",
                manual_matches=[],
                ocr_matches=[],
                pii_matches=hits,
            )
            redact_word(doc, "paragraph_0", merged)
            clear_word_doc_props(doc)

            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as fh:
                out_path = fh.name
            try:
                doc.save(out_path)
                out_doc = Document(out_path)
                out_text = "".join(p.text for p in out_doc.paragraphs)
                self.assertNotIn(
                    secret_id, out_text,
                    f"导出 docx 仍含原文敏感字串：{secret_id}",
                )
                self.assertIn(
                    mask_for_entity("CN_ID_CARD", secret_id), out_text,
                    f"导出 docx 应含 partial mask：{mask_for_entity('CN_ID_CARD', secret_id)}",
                )
            finally:
                os.remove(out_path)
        finally:
            os.remove(path)


class TestWordDocumentPropertiesCleared(unittest.TestCase):
    """clear_word_doc_props 清 5 core + revision=1（D-08 / D-24）。"""

    def test_clear_core_5_fields_always_succeeds(self):
        """写入敏感 5 字段 → clear → 导出 docx → 断言 5 字段全部 == ""。"""
        from privacyguard.word.clear_doc_props import clear_word_doc_props

        path = build_fake_docx(paragraphs=["test"])
        try:
            doc = Document(path)
            # 写敏感字符串
            doc.core_properties.title = "SENSITIVE TITLE"
            doc.core_properties.author = "SENSITIVE AUTHOR"
            doc.core_properties.subject = "SENSITIVE SUBJECT"
            doc.core_properties.keywords = "SENSITIVE KEYWORDS"
            doc.core_properties.last_modified_by = "SENSITIVE LAST_MODIFIED_BY"

            clear_word_doc_props(doc)

            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as fh:
                out_path = fh.name
            try:
                doc.save(out_path)
                out_doc = Document(out_path)
                for prop_name in ('title', 'author', 'subject', 'keywords', 'last_modified_by'):
                    value = getattr(out_doc.core_properties, prop_name)
                    self.assertEqual(
                        value, "",
                        f"{prop_name} 应为 ''，实际 {value!r}",
                    )
            finally:
                os.remove(out_path)
        finally:
            os.remove(path)

    def test_clear_revision_set_to_1(self):
        """clear_word_doc_props 必须把 revision 字段重置为整数 1（D-08 / D-24 锁）。"""
        from privacyguard.word.clear_doc_props import clear_word_doc_props

        path = build_fake_docx(paragraphs=["test"])
        try:
            doc = Document(path)
            doc.core_properties.revision = 99

            clear_word_doc_props(doc)

            self.assertEqual(doc.core_properties.revision, 1)
        finally:
            os.remove(path)


class TestWordMergePriorityRulePiManualOcr(unittest.TestCase):
    """merge_word_matches_with_priority 第六参数 pii_matches 优先级锁定 rule > pii > manual > ocr。"""

    def test_rule_beats_pii(self):
        """规则命中与 PII 命中不重叠时，merged 应包含两条：rule 在前 + pii 在后。"""
        from main import merge_word_matches_with_priority
        from privacyguard.pii.hits import PIIHit

        text = "张三 13812345678"
        rules = [{"enabled": True, "mode": "exact", "find": "张三", "replace": "[姓名]"}]
        phone_hit = PIIHit(
            entity_type='CN_PHONE',
            page_offset=3,
            page_length=11,
            page_rect=(0.0, 0.0, 66.0, 12.0),
            mask_strategy="138****5678",
            normalized="13812345678",
        )
        merged = merge_word_matches_with_priority(
            text, rules, "[已脱敏]",
            manual_matches=[], ocr_matches=[],
            pii_matches=[phone_hit],
        )
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["source"], "rule")
        self.assertEqual(merged[1]["source"], "pii")

    def test_pii_beats_manual_on_overlap(self):
        """区间重叠时 pii 命中覆盖 manual 命中（D-19 priority 锁）。"""
        from main import merge_word_matches_with_priority
        from privacyguard.pii.hits import PIIHit

        secret_id = fake_id_card()
        text = f"原文 {secret_id}"
        manual = [{"start": 0, "end": 18, "text": secret_id, "replacement": "[手动]"}]
        id_hit = PIIHit(
            entity_type='CN_ID_CARD',
            page_offset=3,
            page_length=18,
            page_rect=(0.0, 0.0, 108.0, 12.0),
            mask_strategy=mask_for_entity("CN_ID_CARD", secret_id),
            normalized=secret_id,
        )
        merged = merge_word_matches_with_priority(
            text, [], "[已脱敏]",
            manual_matches=manual, ocr_matches=[],
            pii_matches=[id_hit],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "pii")


def _build_pii_panel_stub():
    """构造 PII 面板测试 stub（不继承 MainWindow；通过 MethodType 绑定 MainWindow 方法）。"""
    from main import MainWindow

    stub = type("_StubMainWindow", (), {})()
    stub.word_data = {
        "paragraph_5": {
            "text": "身份证 53010219200508011X 末位",
            "ocr": [],
            "manual": [],
            "pii": [],
        }
    }
    # 左右双栏 WebEngineView（Mock spec 保证 page() / runJavaScript 被自动模拟）
    stub.word_preview = Mock(spec=QWebEngineView)
    stub.word_preview.isHidden.return_value = False
    stub.word_preview_replaced = Mock(spec=QWebEngineView)
    stub.word_preview_replaced.isHidden.return_value = False
    # 绑定 MainWindow 三个新方法到 stub（via MethodType 替代继承）
    stub._apply_word_pii_panel_updates = MethodType(
        MainWindow._apply_word_pii_panel_updates, stub
    )
    stub._build_pii_block_fragment = MethodType(
        MainWindow._build_pii_block_fragment, stub
    )
    stub._build_pii_mask_block_fragment = MethodType(
        MainWindow._build_pii_mask_block_fragment, stub
    )
    return stub


def _build_id_card_hit():
    """构造单条 CN_ID_CARD PIIHit 命中（page_offset=4 page_length=18）。"""
    from privacyguard.pii.hits import PIIHit

    secret = "53010219200508011X"
    return [
        PIIHit(
            entity_type='CN_ID_CARD',
            page_offset=4,
            page_length=18,
            page_rect=(0, 0, 0, 0),
            confidence_tier='HIGH',
            source='text',
            mask_strategy=mask_for_entity('CN_ID_CARD', secret),
            normalized=secret,
        )
    ]


class TestWordPIIPanelHighlights(unittest.TestCase):
    """Phase 3 (03-word) — TestWordPIIPanelHighlights 4 方法
    cp27 增量 patch 契约 + 短码徽章 + partial mask 渲染。
    """

    def test_apply_word_pii_panel_updates_uses_runJavaScript_not_setHtml(self):
        """_apply_word_pii_panel_updates 走 cp27 局部 patch:
        web_view.page().runJavaScript 被调 + web_view.setHtml 未被调（D-10 锁）。"""
        stub = _build_pii_panel_stub()
        hits = _build_id_card_hit()

        stub._apply_word_pii_panel_updates(key="paragraph_5", hits=hits)

        # cp27 契约: 局部 patch via runJavaScript（左右双栏）
        stub.word_preview.page().runJavaScript.assert_called()
        stub.word_preview_replaced.page().runJavaScript.assert_called()
        # cp27 反向断言: 禁止整页 setHtml
        stub.word_preview.setHtml.assert_not_called()
        stub.word_preview_replaced.setHtml.assert_not_called()

    def test_build_pii_block_fragment_contains_short_code_badge(self):
        """_build_pii_block_fragment 构造左栏原文高亮 + 短码徽章 HTML 片段。"""
        stub = _build_pii_panel_stub()
        hits = _build_id_card_hit()

        fragment = stub._build_pii_block_fragment(key="paragraph_5", hits=hits)

        # HTML 元素名 + entity_type 属性 + 短码徽章（per BLOCKER 5 + D-21 单一来源）
        self.assertIn('<mark class="pii-highlight"', fragment)
        self.assertIn('data-entity-type="CN_ID_CARD"', fragment)
        self.assertIn('<span class="pii-tag">ID</span>', fragment)
        # 原文包裹
        self.assertIn("53010219200508011X", fragment)
        # 左栏**不**含 mask 字符串（Visuals §PII Highlight 锁定）
        self.assertNotIn(
            mask_for_entity('CN_ID_CARD', '53010219200508011X'), fragment,
        )

    def test_build_pii_mask_block_fragment_contains_mask_string_not_original(self):
        """_build_pii_mask_block_fragment 构造右栏 partial mask 片段。"""
        stub = _build_pii_panel_stub()
        hits = _build_id_card_hit()

        fragment = stub._build_pii_mask_block_fragment(key="paragraph_5", hits=hits)

        # HTML 元素名 + entity_type 属性 + mask 字符串 + title 前缀
        self.assertIn('<mark class="pii-mask"', fragment)
        self.assertIn('data-entity-type="CN_ID_CARD"', fragment)
        self.assertIn(
            mask_for_entity('CN_ID_CARD', '53010219200508011X'), fragment,
        )
        self.assertIn("已替换为：", fragment)
        # 右栏**不**含原文（Visuals §PII Partial-Mask 锁定）
        self.assertNotIn("53010219200508011X", fragment)

    def test_entity_type_short_code_covers_all_9_locked_types(self):
        """ENTITY_TYPE_SHORT_CODE 9 短码字典覆盖 9 类 entity（D-21 单一来源锁）。
        9 个短码值锁定为 ASCII uppercase；不允许中文 / 小写。"""
        from main import ENTITY_TYPE_SHORT_CODE

        expected_keys = {
            'CN_ID_CARD', 'CN_PHONE', 'CN_BANK_CARD', 'CN_EMAIL',
            'CN_USCC', 'CN_TAXPAYER_ID', 'CN_TAXPAYER_ID_15',
            'CN_VAT_INVOICE', 'CN_BANK_ACCOUNT',
        }
        self.assertEqual(set(ENTITY_TYPE_SHORT_CODE.keys()), expected_keys)
        # ASCII uppercase 短码（D-21 锁）
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_ID_CARD'], 'ID')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_PHONE'], 'PHONE')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_BANK_CARD'], 'BANK')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_EMAIL'], 'EMAIL')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_USCC'], 'USCC')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_TAXPAYER_ID'], 'TAX')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_TAXPAYER_ID_15'], 'TAX15')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_VAT_INVOICE'], 'VAT')
        self.assertEqual(ENTITY_TYPE_SHORT_CODE['CN_BANK_ACCOUNT'], 'ACCT')


if __name__ == "__main__":
    unittest.main()
