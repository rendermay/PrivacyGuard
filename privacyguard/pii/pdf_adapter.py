"""PII 真脱敏 apply 阶段（SAFE-01 / MASK-01 / SAFE-03）。

- apply_pii_redactions: 沿用 main.py:12354-12385 已生产验证的 PyMuPDF 真删除 API。
- write_partial_masks: Phase 2 MASK-01 — partial mask 写入（D-01 + D-02 + D-03 + D-21）。
- clear_pdf_metadata: Phase 2 SAFE-03 — PDF 元数据 5 字段清除（D-14 + D-15 + D-16）。

禁止使用 `page.draw_rect`（假脱敏，黑框覆盖但底层文本仍可还原）。

主要常量：
- fitz.PDF_REDACT_IMAGE_PIXELS = 2（**不是**默认 0；否则图像像素不被销毁）
- garbage=4 + deflate=True + clean=True 三个 save flag 联合清扫元数据 / 未引用对象。
"""
from typing import Callable, Dict, Iterable, List, Literal, Optional, Tuple, Union

import fitz

from privacyguard.pii.hits import PIIHit


Rect = Tuple[float, float, float, float]


# 02-04: write_partial_masks mixed item type alias (CR-01 fix).
# Each item in the items list can be:
#   - PIIHit dataclass (routed via global mode)
#   - fitz.Rect (routed via global mode)
#   - (x, y, w, h, mode) tuple (per-item mode)
#   - (PIIHit, mode) 2-tuple (per-item mode + PIIHit mask_strategy routing)
PartialMaskItem = Union[
    "PIIHit",
    "fitz.Rect",
    Tuple[float, float, float, float, str],
    Tuple["PIIHit", str],
]


# PyMuPDF font name 映射表（page.get_text("dict") 返回的 font 名 → insert_text 支持的 fontname）
# D-02 锁定：文本层路径从 page.get_text("dict") 取最近 span 的 font + size 同步插入。
_FONT_NAME_MAP: Dict[str, str] = {
    "Helvetica": "helv",
    "Helvetica-Oblique": "heit",
    "Helvetica-Bold": "hebo",
    "Helvetica-BoldOblique": "hebi",
    "Times-Roman": "tiro",
    "Times-Bold": "tibo",
    "Courier": "cour",
    "Courier-Bold": "cobo",
}


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


# ----------------------------------------------------------------------
# Phase 2 (02-01-tracer) — write_partial_masks + clear_pdf_metadata
# ----------------------------------------------------------------------

def write_partial_masks(
    doc: "fitz.Document",
    page_idx: int,
    items: List[PartialMaskItem],
    mode: Literal["partial", "blackout"] = "partial",
) -> None:
    """PII 命中 partial mask 写入（D-01 + D-02 + D-03 + D-21 + D-22 single-pass）。

    02-04 (CR-01 fix): accepts mixed item types in a single call:
        - PIIHit dataclass → routed via global ``mode``
        - fitz.Rect → routed via global ``mode``
        - (x, y, w, h, mode) 5-tuple → per-item mode (no mask text)
        - (PIIHit, mode) 2-tuple → per-item mode + PIIHit mask_strategy routing

    mode="partial":
        1. add_redact_annot（黑底色块）
        2. apply_redactions(IMAGE_PIXELS) — **仅一次**（D-22 单页不变式）
        3. insert_text 在色块上写 mask_strategy
            - 字体：优先 page.get_text("dict") 取最近 span 的 font + size
            - 字号：OCR / 占位 rect 路径用 rect.height - 4 估算（floor 6）
            - 颜色：白字 (1.0, 1.0, 1.0)

    mode="blackout":
        仅 add_redact_annot + apply_redactions(IMAGE_PIXELS)（沿用 Phase 1 行为）

    Backward-compat: 02-01 callers passing List[PIIHit] + global mode 仍可工作。
    """
    if not items:
        return
    page = doc[page_idx]
    fill_color = (0.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # 02-04: 4-branch mixed item dispatcher (CR-01 fix).
    # Normalize each item into (rect, mask_text_or_None, item_mode).
    # ------------------------------------------------------------------
    normalized: List[Tuple[fitz.Rect, Optional[str], str]] = []
    for item in items:
        # 2-tuple form: (PIIHit, mode) — per-item mode + PIIHit mask_strategy
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and hasattr(item[0], "page_rect")
            and hasattr(item[0], "mask_strategy")
            and isinstance(item[1], str)
        ):
            hit, item_mode = item
            r = hit.page_rect
            rect = fitz.Rect(r[0], r[1], r[0] + r[2], r[1] + r[3])
            normalized.append((rect, hit.mask_strategy or "", item_mode))
        # 5-tuple form: (x, y, w, h, mode) — per-item mode + no mask text
        elif (
            isinstance(item, tuple)
            and len(item) == 5
            and isinstance(item[4], str)
        ):
            x, y, w, h, item_mode = item
            rect = fitz.Rect(x, y, x + w, y + h)
            normalized.append((rect, None, item_mode))
        # fitz.Rect → global mode, no mask text
        elif isinstance(item, fitz.Rect):
            normalized.append((item, None, mode))
        # PIIHit dataclass → global mode, mask_strategy from hit
        elif hasattr(item, "page_rect") and hasattr(item, "mask_strategy"):
            r = item.page_rect
            rect = fitz.Rect(r[0], r[1], r[0] + r[2], r[1] + r[3])
            normalized.append((rect, item.mask_strategy or "", mode))
        else:
            # 防御性：未知 item 跳过（不应发生）
            continue

    if not normalized:
        return

    # 1. 先画黑底色块（所有 item 一次性 add_redact_annot）
    for rect, _mask_text, _item_mode in normalized:
        annot = page.add_redact_annot(rect)
        annot.set_colors(stroke=fill_color, fill=fill_color)
        annot.update()

    # 2. 真删除（销毁底层文本+像素）— D-22 单页不变式：仅一次
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)

    # 3. 清理 annot 防止编辑器修改
    for annot in page.annots() or []:
        page.delete_annot(annot)

    # 4. partial-mode item 写 mask_strategy 文字
    for rect, mask_text, item_mode in normalized:
        if item_mode != "partial":
            continue
        if not mask_text:
            # 无 mask 文字 → 跳过（如 5-tuple blackout item）
            continue
        # 字号 / 字体：try PIIHit 路径的 font lookup（基于 normalized text）；
        # 否则用 OCR / 占位 rect 的 fallback 估算
        font_size = max(float(rect.height) - 4.0, 6.0)
        font_name = "helv"
        try:
            d = page.get_text("dict")
            for block in d.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = span.get("text", "")
                        if txt and mask_text and (
                            mask_text[:6] in txt or any(c in txt for c in mask_text[:3])
                        ):
                            raw_font = span.get("font", "helv")
                            font_name = _FONT_NAME_MAP.get(raw_font, "helv")
                            raw_size = span.get("size", font_size)
                            try:
                                font_size = float(raw_size)
                            except (TypeError, ValueError):
                                pass
                            font_size = max(font_size, 6.0)
                            break
        except Exception:
            pass

        # D-03: rect 宽度按 mask_text 字符数重算 + 居中
        resized_rect = _resize_rect_for_mask(rect, mask_text, font_size)
        text_width = font_size * len(mask_text) * 0.6
        x_center = resized_rect.x0 + (resized_rect.width - text_width) / 2
        y_center = resized_rect.y0 + (resized_rect.height + font_size) / 2 - 2
        page.insert_text(
            (x_center, y_center),
            mask_text,
            fontsize=font_size,
            fontname=font_name,
            color=(1.0, 1.0, 1.0),
        )


def _resolve_font_for_rect(
    page: "fitz.Page",
    hit: PIIHit,
) -> Tuple[str, float]:
    """D-02: 优先 page.get_text("dict") 现场取最近 span 的 font + size。

    文本层路径（unit.source="text"）：从 page.get_text("dict") 的 spans 中
    找包含 hit.normalized 的 span，返回其 font + size。

    OCR / 占位 rect 路径（unit.source != "text" 或 span 未找到）：
    回退到默认 sans-serif ("helv") + 估算字号 max(rect.height - 4, 6)。

    Args:
        page: PyMuPDF Page 对象
        hit: PIIHit（提供 normalized + page_rect + source）

    Returns:
        (font_name, font_size) — 可直接传 page.insert_text
    """
    fallback_size = max(float(hit.page_rect[3]) - 4.0, 6.0)
    try:
        if hit.source and hit.source != 'text':
            # OCR / image_block / full_page_ocr 路径：直接估算字号
            return ("helv", fallback_size)
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    if txt and hit.normalized and hit.normalized in txt:
                        raw_font = span.get("font", "helv")
                        font_name = _FONT_NAME_MAP.get(raw_font, "helv")
                        raw_size = span.get("size", fallback_size)
                        try:
                            size = float(raw_size)
                        except (TypeError, ValueError):
                            size = fallback_size
                        # floor 6 防退化
                        return (font_name, max(size, 6.0))
    except Exception:
        # get_text 失败 → 紧急 fallback
        return ("helv", 11.0)
    # span 未找到（文字层路径但 OCR 命中）→ 估算字号
    return ("helv", fallback_size)


def _resize_rect_for_mask(
    rect: fitz.Rect,
    mask_text: str,
    fontsize: float,
) -> fitz.Rect:
    """D-03: 按 mask_text 字符数重算 rect 宽度，居中保持。

    avg_w = fontsize * 0.6；new_w = max(len(mask_text) * avg_w + 4, rect.width)
    居中：cx = (rect.x0 + rect.x1) / 2 → 新 rect x0 = cx - new_w/2
    """
    avg_w = float(fontsize) * 0.6
    new_w = max(len(mask_text) * avg_w + 4.0, float(rect.width))
    cx = (float(rect.x0) + float(rect.x1)) / 2.0
    return fitz.Rect(cx - new_w / 2.0, float(rect.y0), cx + new_w / 2.0, float(rect.y1))


def clear_pdf_metadata(doc: "fitz.Document") -> None:
    """Phase 2: SAFE-03 PDF 元数据清除（D-14 + D-15 + D-16）。

    仅清 5 字段（title / author / subject / producer / creator），其他保留：
    - CreationDate / ModDate 不动（D-14 锁定）
    - Keywords / XMP metadata 不动（D-14 锁定）
    - 5 字段全部置空字符串（D-15 锁定），不写 "Anonymous" / "Redacted" /
      "PyMuPDF" 等占位字符串

    调用位置：MainWindow.save_pdf 中 doc.save() 前调用一次（D-16 锁定）。
    """
    doc.set_metadata({
        "title": "",
        "author": "",
        "subject": "",
        "producer": "",
        "creator": "",
    })


__all__ = [
    'collect_pii_rects',
    'apply_pii_redactions',
    # Phase 2 (02-01-tracer)
    'write_partial_masks',
    'clear_pdf_metadata',
    # Phase 2 (02-04-gap-closure) — CR-01 fix
    'PartialMaskItem',
]
