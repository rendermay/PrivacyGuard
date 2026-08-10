"""Phase 1 反向提取真脱敏验证（SAFE-01 / SAFE-02）。

D-14 规定：反向提取优先 `fitz.open(out).get_text()` 路径，避免依赖
poppler-utils；pdftotext 仅作人工验证备用。

B3 scope decision：01-01 tracer 仅覆盖**文字层**路径的 reverse-extraction。
image-pixels-only 场景由 Plan 01-03 Task 3（collect_full_page_ocr_hits）
扩展后另行验证，因为 image-only PDF 的 page.get_text() 为空字符串，
会让零命中 reverse-extraction 平凡通过——这是 01-01 必须规避的真空绿色。
"""
import os
import tempfile
import unittest

import fitz

from privacyguard.pii.engine import PIIEngine, TextUnit
from privacyguard.pii.pdf_adapter import apply_pii_redactions
from tests.fixtures.fake_pii import fake_id_card, fake_phone
from tests.e2e.create_pii_test_pdf import (
    create_pii_test_pdf,
    create_pii_id_only_pdf,
    create_pii_phone_only_pdf,
)


class TestPdfPiiRedaction(unittest.TestCase):
    """SAFE-01 / SAFE-02：fitz.open(out).get_text() 反向断言敏感字符串不存在。"""

    def _build_pii_pdf(self, in_pdf: str) -> tuple:
        """构建一个含 18 位身份证 + 11 位手机号的文字层测试 PDF。

        返回 (secret_id, secret_phone)。
        """
        secret_id = fake_id_card()
        secret_phone = fake_phone()
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (50, 100),
            f"测试样本 身份证 {secret_id} 手机 {secret_phone}",
            fontsize=14,
        )
        doc.save(in_pdf)
        doc.close()
        return secret_id, secret_phone

    def test_redacted_text_not_extractable(self):
        """完整 spine：synth PDF -> PIIEngine.detect -> apply_pii_redactions ->
        fitz.open(out).get_text() -> 断言敏感前 10/7 位消失。
        """
        with tempfile.TemporaryDirectory() as tmp:
            in_pdf = os.path.join(tmp, "in.pdf")
            out_pdf = os.path.join(tmp, "out.pdf")
            secret_id, secret_phone = self._build_pii_pdf(in_pdf)

            # 1. detect
            engine = PIIEngine()
            rects_per_page = {}
            with fitz.open(in_pdf) as src:
                for i, page in enumerate(src):
                    unit = TextUnit(page_index=i, text=page.get_text(), source="text")
                    page_hits = []
                    for hit in engine.detect(unit):
                        r = hit.page_rect
                        page_hits.append(
                            fitz.Rect(r[0], r[1], r[0] + r[2], r[1] + r[3])
                        )
                    if page_hits:
                        rects_per_page[i] = page_hits

            # Pre-condition: 引擎必须检测到至少一个 hit（否则测试无意义）。
            self.assertGreater(
                len(rects_per_page.get(0, [])),
                0,
                "PIIEngine 未检测到任何命中；测试失败（不应平凡通过）",
            )

            # 2. apply 真脱敏
            apply_pii_redactions(in_pdf, out_pdf, rects_per_page)

            # 3. 反向提取并断言
            with fitz.open(out_pdf) as out_doc:
                out_text = "".join(p.get_text() for p in out_doc)
            self.assertNotIn(
                secret_id[:10],
                out_text,
                f"身份证前 10 位仍可提取: {secret_id[:10]} in {out_text!r}",
            )
            self.assertNotIn(
                secret_phone[:7],
                out_text,
                f"手机号前 7 位仍可提取: {secret_phone[:7]} in {out_text!r}",
            )

    def test_redacted_id_alone(self):
        """隔离测试：仅含 18 位身份证的 PDF 反向不应保留前 10 位。"""
        with tempfile.TemporaryDirectory() as tmp:
            in_pdf = os.path.join(tmp, "in_id.pdf")
            out_pdf = os.path.join(tmp, "out_id.pdf")
            secret_id = "53010219200508011X"  # GB 11643 标准样本

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 100), f"测试样本 身份证 {secret_id}", fontsize=14)
            doc.save(in_pdf)
            doc.close()

            engine = PIIEngine()
            rects_per_page = {}
            with fitz.open(in_pdf) as src:
                for i, p in enumerate(src):
                    unit = TextUnit(page_index=i, text=p.get_text(), source="text")
                    page_hits = []
                    for hit in engine.detect(unit):
                        r = hit.page_rect
                        page_hits.append(
                            fitz.Rect(r[0], r[1], r[0] + r[2], r[1] + r[3])
                        )
                    if page_hits:
                        rects_per_page[i] = page_hits

            self.assertGreater(
                len(rects_per_page.get(0, [])),
                0,
                "PIIEngine 未检测到 GB 11643 标准样本 53010219200508011X",
            )

            apply_pii_redactions(in_pdf, out_pdf, rects_per_page)

            with fitz.open(out_pdf) as out_doc:
                out_text = "".join(p.get_text() for p in out_doc)
            self.assertNotIn(
                secret_id[:10],
                out_text,
                f"GB 11643 标准样本前 10 位仍可提取: {secret_id[:10]}",
            )


if __name__ == "__main__":
    unittest.main()