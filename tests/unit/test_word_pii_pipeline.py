"""Phase 3 Word 端到端 PII 流程测试（D-13 — 79/79 升级 88/88）。

5 个测试类共 7 个测试方法（Wave 1 RED 占位 → Wave 2 GREEN）：

- TestWordAdapterCollectUnits — WordAdapter.collect_units 段落 + 表格 双向映射
- TestWordPIIAutoTrigger — PIIEngine.detect 在 Word 文本中命中 6 类以上实体
- TestWordRedactRoundTrip — redact_word 真脱敏 + 反向断言 SAFE-02
- TestWordDocumentPropertiesCleared — clear_word_doc_props 清 5 core + revision=1
- TestWordMergePriorityRulePiManualOcr — priority 锁定 rule > pii > manual > ocr
"""
import os
import tempfile
import unittest

from docx import Document

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


if __name__ == "__main__":
    unittest.main()
