"""PII 真脱敏 apply 阶段（SAFE-01）—— 沿用 main.py:12354-12385 已生产验证的
PyMuPDF 真删除 API。

禁止使用 `page.draw_rect`（假脱敏，黑框覆盖但底层文本仍可还原）。

主要常量：
- fitz.PDF_REDACT_IMAGE_PIXELS = 2（**不是**默认 0；否则图像像素不被销毁）
- garbage=4 + deflate=True + clean=True 三个 save flag 联合清扫元数据 / 未引用对象。
"""
from typing import Dict, Iterable, Optional, Tuple

import fitz

from privacyguard.pii.hits import PIIHit


Rect = Tuple[float, float, float, float]


def collect_pii_rects(page_data: Dict[int, dict]) -> Dict[int, list]:
    """从 MainWindow.page_data 提取每页 PII 命中 → fitz.Rect 列表。

    输入: page_data = {page_idx: {"ocr": [...], "manual": [...], "pii": [PIIHit, ...]}}
    输出: {page_idx: [fitz.Rect, ...]}
    """
    out: Dict[int, list] = {}
    for page_idx, data in page_data.items():
        rects = []
        for hit in data.get('pii', []):
            r = hit.page_rect  # (x, y, w, h)
            rects.append(fitz.Rect(r[0], r[1], r[0] + r[2], r[1] + r[3]))
        if rects:
            out[page_idx] = rects
    return out


def apply_pii_redactions(
    pdf_in: str,
    pdf_out: str,
    rects_per_page: Dict[int, Iterable[fitz.Rect]],
    fill_color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """PyMuPDF 真删除：add_redact_annot + apply_redactions(IMAGE_PIXELS) + garbage=4。

    Pitfall 9：必须显式传 `images=fitz.PDF_REDACT_IMAGE_PIXELS`（=2），
    默认值 0（PDF_REDACT_IMAGE_NONE）不会销毁图像像素层。

    Pitfall 10：保存时同时 `garbage=4 + deflate=True + clean=True` 三件套，
    否则残留对象 / 元数据可能导致敏感信息泄漏。
    """
    doc = fitz.open(pdf_in)
    try:
        for i in range(len(doc)):
            page = doc[i]
            for r in rects_per_page.get(i, []):
                annot = page.add_redact_annot(r)
                annot.set_colors(stroke=fill_color, fill=fill_color)
                annot.update()
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
            for annot in page.annots() or []:
                page.delete_annot(annot)
        doc.save(pdf_out, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()


__all__ = ['collect_pii_rects', 'apply_pii_redactions']