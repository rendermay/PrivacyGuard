"""Phase 3 Plan 4 Word PII 真脱敏 reverse-extraction 测试。

覆盖 SAFE-02 / D-04 / D-07，并用 AST 守护 main.py 保存路径确实调用
Word adapter，而不是只在预览层展示高亮。
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from docx import Document

from privacyguard.pii.engine import PIIEngine
from privacyguard.pii.mask import mask_for_entity
from privacyguard.pii.word_adapter import (
    apply_pii_replacements_to_docx,
    collect_pii_word_hits,
    locate_pii_hits_in_paragraph,
)
from tests.fixtures.fake_pii import fake_id_card, fake_phone


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_PY = PROJECT_ROOT / "main.py"


class TestWordPiiRedaction(unittest.TestCase):
    """验证保存后的 docx 通过独立 python-docx 通道重新提取。"""

    def _redact_document(self, text: str, mode: str = "partial") -> str:
        document = Document()
        document.add_paragraph(text)
        source_text = document.paragraphs[0].text
        hits = collect_pii_word_hits(source_text, PIIEngine())
        self.assertTrue(hits, "PIIEngine 未检测到测试敏感项，测试不能平凡通过")
        locations = locate_pii_hits_in_paragraph(hits, source_text)
        self.assertTrue(locations, "Word adapter 未能定位测试敏感项")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "redacted.docx"
            apply_pii_replacements_to_docx(
                document,
                {"paragraph_0": locations},
                mode=mode,
            )
            document.save(output_path)
            extracted = Document(output_path)
            return "\n".join(paragraph.text for paragraph in extracted.paragraphs)

    def test_redacted_docx_does_not_contain_original_secret(self):
        secret_id = fake_id_card()
        output_text = self._redact_document(f"测试身份证：{secret_id}")
        self.assertNotIn(secret_id, output_text)

    def test_partial_mask_id_card_visible_in_output(self):
        secret_id = fake_id_card()
        output_text = self._redact_document(f"测试身份证：{secret_id}")
        self.assertIn(mask_for_entity("CN_ID_CARD", secret_id), output_text)

    def test_partial_mask_phone_visible_in_output(self):
        secret_phone = fake_phone()
        output_text = self._redact_document(f"联系电话：{secret_phone}")
        self.assertIn(mask_for_entity("CN_PHONE", secret_phone), output_text)
        self.assertNotIn(secret_phone, output_text)

    def test_blackout_mode_replaces_with_brackets(self):
        secret_phone = fake_phone()
        output_text = self._redact_document(f"联系电话：{secret_phone}", mode="blackout")
        self.assertIn("[已脱敏]", output_text)
        self.assertNotIn(secret_phone, output_text)

    def test_paragraph_style_preserved_after_save(self):
        secret_id = fake_id_card()
        document = Document()
        paragraph = document.add_paragraph(f"标题中的身份证：{secret_id}", style="Heading 1")
        source_text = paragraph.text
        hits = collect_pii_word_hits(source_text, PIIEngine())
        locations = locate_pii_hits_in_paragraph(hits, source_text)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "styled-redacted.docx"
            apply_pii_replacements_to_docx(
                document,
                {"paragraph_0": locations},
                mode="partial",
            )
            document.save(output_path)
            saved_paragraph = Document(output_path).paragraphs[0]

        self.assertEqual(saved_paragraph.style.name, "Heading 1")
        self.assertNotIn(secret_id, saved_paragraph.text)


class TestSaveWordCallsPiiAdapter(unittest.TestCase):
    """AST 守护 _save_word 的生产接入点。"""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
        cls.save_word = next(
            (
                node
                for node in ast.walk(cls.tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "_save_word"
            ),
            None,
        )

    def test_save_word_function_exists(self):
        self.assertIsNotNone(self.save_word, "main.py 必须定义 _save_word")

    def test_save_word_calls_apply_pii_replacements(self):
        self.assertIsNotNone(self.save_word)
        calls = {
            node.func.id
            for node in ast.walk(self.save_word)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("apply_pii_replacements_to_docx", calls)

    def test_save_word_calls_locate_pii_hits(self):
        self.assertIsNotNone(self.save_word)
        calls = {
            node.func.id
            for node in ast.walk(self.save_word)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("locate_pii_hits_in_paragraph", calls)


if __name__ == "__main__":
    unittest.main()
