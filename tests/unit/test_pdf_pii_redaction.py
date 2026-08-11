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

    def _detect_with_search_for(self, in_pdf):
        """detect + 用 page.search_for 取得精确坐标。

        引擎返回的 page_rect 在 text-layer path 是占位 (0, 0, w, h)，
        不能直接用于 redaction（会画到页面左上角）。这里基于 normalized
        文本二次查询 page.search_for 取真实坐标。
        """
        engine = PIIEngine()
        rects_per_page = {}
        all_hits = []
        with fitz.open(in_pdf) as src:
            for i, page in enumerate(src):
                unit = TextUnit(page_index=i, text=page.get_text(), source="text")
                page_hits = []
                for hit in engine.detect(unit):
                    all_hits.append(hit)
                    matches = page.search_for(hit.normalized)
                    if matches:
                        # 取第一个匹配；同一字符串多次匹配走 overlap.resolve
                        r = matches[0]
                        page_hits.append(fitz.Rect(r.x0, r.y0, r.x1, r.y1))
                    else:
                        # 兜底使用 hit 自带 rect（占位）
                        rp = hit.page_rect
                        page_hits.append(fitz.Rect(rp[0], rp[1], rp[0] + rp[2], rp[1] + rp[3]))
                if page_hits:
                    rects_per_page[i] = page_hits
        return rects_per_page, all_hits

    def test_redacted_text_not_extractable(self):
        """完整 spine：synth PDF -> PIIEngine.detect -> apply_pii_redactions ->
        fitz.open(out).get_text() -> 断言敏感前 10/7 位消失。
        """
        with tempfile.TemporaryDirectory() as tmp:
            in_pdf = os.path.join(tmp, "in.pdf")
            out_pdf = os.path.join(tmp, "out.pdf")
            secret_id, secret_phone = self._build_pii_pdf(in_pdf)

            # 1. detect + 二次定位
            rects_per_page, hits = self._detect_with_search_for(in_pdf)

            # Pre-condition: 引擎必须检测到至少一个 hit（否则测试无意义）。
            self.assertGreater(
                len(hits),
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

            rects_per_page, hits = self._detect_with_search_for(in_pdf)

            self.assertGreater(
                len(hits),
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


# ----------------------------------------------------------------------
# Phase 2 (02-01-tracer) — partial mask + blackout mode 反向测试
# ----------------------------------------------------------------------

class TestPartialMaskWritesMaskText(unittest.TestCase):
    """MASK-01: partial mask 写入后反向断言原文不存在 + mask_strategy 文字存在。"""

    def _build_pii_pdf(self, in_pdf: str, secret: str) -> None:
        """构建一个含一段 PII 字符串的合成 PDF（文字层路径）。"""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (50, 100),
            f"测试 {secret}",
            fontsize=14,
        )
        doc.save(in_pdf)
        doc.close()

    def _detect_and_get_rects(self, in_pdf: str, normalized: str):
        """detect + page.search_for 二次定位 → 返回 (rects_per_page_dict, hits_list)。

        用 page.search_for(normalized) 取精确坐标（text-layer 路径）。
        """
        from privacyguard.pii.engine import PIIEngine, TextUnit
        engine = PIIEngine()
        rects_per_page = {}
        all_hits = []
        with fitz.open(in_pdf) as src:
            for i, page in enumerate(src):
                unit = TextUnit(page_index=i, text=page.get_text(), source="text")
                page_hits = []
                for hit in engine.detect(unit):
                    all_hits.append(hit)
                    matches = page.search_for(hit.normalized)
                    if matches:
                        r = matches[0]
                        page_hits.append((r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0))
                    else:
                        rp = hit.page_rect
                        page_hits.append(rp)
                if page_hits:
                    rects_per_page[i] = page_hits
        return rects_per_page, all_hits

    def _build_hits(self, hits, rects_per_page, normalized, entity_type, mask_text):
        """把 detect 命中的 hit 转成 PIIHit 列表（page_rect 用 page.search_for 真实坐标）。"""
        from privacyguard.pii.hits import PIIHit
        out = []
        for page_idx, rect_list in rects_per_page.items():
            for rect in rect_list:
                if isinstance(rect, fitz.Rect):
                    x, y, w, h = rect.x0, rect.y0, rect.width, rect.height
                else:
                    x, y, w, h = rect
                out.append(PIIHit(
                    entity_type=entity_type,
                    page_offset=0,
                    page_length=len(normalized),
                    page_rect=(x, y, w, h),
                    confidence_tier="HIGH",
                    source="text",
                    mask_strategy=mask_text,
                    normalized=normalized,
                    validator_passed=True,
                ))
        return out

    def test_partial_mask_writes_mask_text_for_uscc(self):
        """MASK-01: partial mask 写入 USCC → 反向提取不含原文前 6 位 + 含 mask_strategy。"""
        from privacyguard.pii.mask import partial_mask_uscc
        from privacyguard.pii.pdf_adapter import write_partial_masks
        from tests.fixtures.fake_pii import fake_uscc
        uscc = fake_uscc()
        mask_text = partial_mask_uscc(uscc)
        self.assertEqual(len(mask_text), 18)
        self.assertTrue(mask_text.startswith(uscc[:6]))

        with tempfile.TemporaryDirectory() as tmp:
            in_pdf = os.path.join(tmp, "in_uscc.pdf")
            out_pdf = os.path.join(tmp, "out_uscc.pdf")
            self._build_pii_pdf(in_pdf, uscc)

            # detect + page.search_for 二次定位
            rects_per_page, hits = self._detect_and_get_rects(in_pdf, uscc)
            self.assertGreater(len(hits), 0, "PIIEngine 未检测到 fake_uscc")

            hits_with_rect = self._build_hits(
                hits, rects_per_page, uscc, "CN_USCC", mask_text,
            )

            # partial mask 写入
            doc = fitz.open(in_pdf)
            try:
                for page_idx in rects_per_page.keys():
                    page_hits = [h for h in hits_with_rect if True]
                    write_partial_masks(doc, page_idx, page_hits, mode="partial")
                doc.save(out_pdf, garbage=4, deflate=True, clean=True)
            finally:
                doc.close()

            # 反向提取
            with fitz.open(out_pdf) as out_doc:
                out_text = "".join(p.get_text() for p in out_doc)
            # 原文前 6 位应被销毁
            self.assertNotIn(
                uscc[:6],
                out_text,
                f"USCC 前 6 位仍可提取: {uscc[:6]} in {out_text!r}",
            )
            # mask_strategy 应保留（白字写在色块上 — PyMuPDF 可被 get_text 提取）
            self.assertIn(
                mask_text,
                out_text,
                f"mask_strategy {mask_text!r} 不在输出中: {out_text!r}",
            )

    def test_partial_mask_blackout_mode_destroys_only(self):
        """blackout mode: 仅销毁原文，不写 mask 文字。"""
        from privacyguard.pii.mask import partial_mask_uscc
        from privacyguard.pii.pdf_adapter import write_partial_masks
        from tests.fixtures.fake_pii import fake_uscc
        uscc = fake_uscc()
        mask_text = partial_mask_uscc(uscc)

        with tempfile.TemporaryDirectory() as tmp:
            in_pdf = os.path.join(tmp, "in_blackout.pdf")
            out_pdf = os.path.join(tmp, "out_blackout.pdf")
            self._build_pii_pdf(in_pdf, uscc)

            rects_per_page, hits = self._detect_and_get_rects(in_pdf, uscc)
            self.assertGreater(len(hits), 0)
            hits_with_rect = self._build_hits(
                hits, rects_per_page, uscc, "CN_USCC", mask_text,
            )

            doc = fitz.open(in_pdf)
            try:
                for page_idx in rects_per_page.keys():
                    page_hits = list(hits_with_rect)
                    write_partial_masks(doc, page_idx, page_hits, mode="blackout")
                doc.save(out_pdf, garbage=4, deflate=True, clean=True)
            finally:
                doc.close()

            with fitz.open(out_pdf) as out_doc:
                out_text = "".join(p.get_text() for p in out_doc)
            self.assertNotIn(uscc[:6], out_text, "blackout 模式未销毁原文")
            self.assertNotIn(mask_text, out_text, "blackout 模式不应写 mask 文字")

    def test_partial_mask_id_card_also_visible(self):
        """MASK-01: partial mask 写入 18 位身份证 → 反向提取不含原文前 6 位 + 含 mask。"""
        from privacyguard.pii.mask import partial_mask_id_card
        from privacyguard.pii.pdf_adapter import write_partial_masks
        from tests.fixtures.fake_pii import fake_id_card
        secret = fake_id_card()
        mask_text = partial_mask_id_card(secret)

        with tempfile.TemporaryDirectory() as tmp:
            in_pdf = os.path.join(tmp, "in_id.pdf")
            out_pdf = os.path.join(tmp, "out_id.pdf")
            self._build_pii_pdf(in_pdf, secret)

            rects_per_page, hits = self._detect_and_get_rects(in_pdf, secret)
            self.assertGreater(len(hits), 0)
            hits_with_rect = self._build_hits(
                hits, rects_per_page, secret, "CN_ID_CARD", mask_text,
            )

            doc = fitz.open(in_pdf)
            try:
                for page_idx in rects_per_page.keys():
                    page_hits = list(hits_with_rect)
                    write_partial_masks(doc, page_idx, page_hits, mode="partial")
                doc.save(out_pdf, garbage=4, deflate=True, clean=True)
            finally:
                doc.close()

            with fitz.open(out_pdf) as out_doc:
                out_text = "".join(p.get_text() for p in out_doc)
            self.assertNotIn(secret[:10], out_text, "身份证前 10 位仍可提取")
            self.assertIn(mask_text, out_text, "mask_strategy 不在输出")


if __name__ == "__main__":
    unittest.main()