"""混合型 PDF 扫描辅助逻辑。"""

import re

import cv2
import fitz
import numpy as np


# v37.7.x 方案 X: 同一 OCR 行内,水平相邻的命中 rect 合并阈值 (扫描坐标像素).
# 解决 Page 0 "刘妹 034-62407159" 这类场景下,字符级 _calculate_from_line
# 行级线性插值在"汉字 pattern + 数字 pattern"同一行时产生的 rect 间隙.
#
# 阈值依据: _calculate_from_line 用 CJK 权重 1.0 vs 数字权重 0.55 做线性插值,
# 但汉字真实宽度约是数字的 1.4 倍. 一档汉字宽度 ≈ 字符宽 1.0 * 字号 ≈ 25 像素
# (scan_scale=2.0 下). 设 30 既能覆盖误差, 又不会跨过普通字符间空白 (~10 像素).
DEFAULT_HIT_MERGE_GAP_PX = 30.0

# 同一 OCR 行判定的 y 容忍 (扫描坐标像素). RapidOCR 偶发 1~2 像素的 y 抖动.
DEFAULT_LINE_Y_TOLERANCE_PX = 8.0


def compile_active_patterns(patterns):
    """编译启用的正则规则，跳过特殊标记和非法表达式。"""
    compiled = []
    for pattern in patterns or []:
        if not pattern or pattern == "__SEAL_DETECTION__":
            continue
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            continue
    return compiled


def collect_embedded_image_clip_rects(page_dict, min_width=24, min_height=24, min_area=400):
    """从 page.get_text('dict') 中提取有效图片块区域。"""
    if not isinstance(page_dict, dict):
        return []

    clip_rects = []
    seen = set()
    for block in page_dict.get("blocks", []):
        if block.get("type") != 1:
            continue

        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            continue

        x0, y0, x1, y1 = (float(v) for v in bbox)
        width = x1 - x0
        height = y1 - y0
        if width < min_width or height < min_height or width * height < min_area:
            continue

        key = (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
        if key in seen:
            continue
        seen.add(key)
        clip_rects.append((x0, y0, x1, y1))

    return clip_rects


def render_pdf_clip_to_bgr(page, clip_rect, scan_scale):
    """将 PDF 页面裁剪区域渲染为 OpenCV BGR 图像。"""
    clip = fitz.Rect(*clip_rect)
    pix = page.get_pixmap(
        matrix=fitz.Matrix(scan_scale, scan_scale),
        clip=clip,
        alpha=False,
    )
    img_data = np.frombuffer(pix.tobytes("png"), dtype=np.uint8)
    return cv2.imdecode(img_data, cv2.IMREAD_COLOR)


def iter_ocr_lines(ocr_results):
    """统一遍历 OCR 结果，兼容 OCRResult 和 RapidOCR 原始结构。"""
    for result in ocr_results or []:
        if hasattr(result, "box") and hasattr(result, "text"):
            yield result.box, result.text
            continue

        if isinstance(result, (list, tuple)) and len(result) >= 2:
            yield result[0], result[1]


def _line_y_center(line_box):
    """从 OCR 行 box (4 点) 计算 y 中心."""
    if not line_box or len(line_box) < 4:
        return None
    ys = [float(p[1]) for p in line_box]
    return (min(ys) + max(ys)) / 2.0


def _rect_to_tuple(rect):
    """归一化 rect 为 (x, y, w, h) tuple. 支持 QRectF, SimpleNamespace, dict, tuple."""
    if rect is None:
        return None
    # QRectF / QRect
    if hasattr(rect, "x") and hasattr(rect, "y") and hasattr(rect, "width") and hasattr(rect, "height"):
        try:
            return (float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()))
        except (TypeError, ValueError):
            return None
    # SimpleNamespace / 普通对象 with .x() .y() ...
    if hasattr(rect, "x0") and hasattr(rect, "y0") and hasattr(rect, "width") and hasattr(rect, "height"):
        # fitz.Rect 风格
        try:
            return (float(rect.x0), float(rect.y0), float(rect.width), float(rect.height))
        except (TypeError, ValueError):
            return None
    # dict
    if isinstance(rect, dict):
        try:
            return (
                float(rect.get("x", rect.get("x0", 0))),
                float(rect.get("y", rect.get("y0", 0))),
                float(rect.get("w", rect.get("width", 0))),
                float(rect.get("h", rect.get("height", 0))),
            )
        except (TypeError, ValueError):
            return None
    # tuple / list
    if isinstance(rect, (tuple, list)) and len(rect) >= 4:
        try:
            return (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))
        except (TypeError, ValueError):
            return None
    return None


def merge_adjacent_hit_rects(
    hits_with_box,
    gap_threshold_px=DEFAULT_HIT_MERGE_GAP_PX,
    y_tolerance_px=DEFAULT_LINE_Y_TOLERANCE_PX,
    output_factory=None,
):
    """v37.7.x 方案 X: 对同一 OCR 行内水平相邻的命中 rect 做合并.

    Args:
        hits_with_box: list[(line_box, rect)], rect 可以是 QRectF / tuple / SimpleNamespace.
        gap_threshold_px: 水平方向上两个 rect 的间距小于等于此值时,合并.
        y_tolerance_px: 判定"同一 OCR 行"的 y 中心差容忍 (扫描坐标像素).
        output_factory: 可选, 把 (x, y, w, h) tuple 转成输出对象.
                        默认使用 _make_output_rect, 优先尝试 QRectF,
                        失败则回退到 _TupleRect (满足 .x() .y() .width() .height() duck typing).

    Returns:
        合并后的 rect 列表. 默认每个 rect 都满足 duck typing .x()/.y()/.width()/.height(),
        与 PyQt6.QtCore.QRectF 接口一致, 兼容 main.py 的 _deduplicate_rects 调用.
    """
    if output_factory is None:
        output_factory = _make_output_rect

    if not hits_with_box:
        return []

    annotated = []
    for line_box, rect in hits_with_box:
        y_center = _line_y_center(line_box)
        if y_center is None:
            continue
        rect_t = _rect_to_tuple(rect)
        if rect_t is None:
            continue
        annotated.append((y_center, rect_t))

    if not annotated:
        return []

    # 按 y_center 分桶: 同桶 = 同一 OCR 行
    annotated.sort(key=lambda r: (r[0], r[1][0]))  # y 优先, x 次之
    buckets: list[list[tuple[float, tuple]]] = []
    for y_center, rect in annotated:
        placed = False
        for bucket in buckets:
            bucket_y = bucket[0][0]
            if abs(y_center - bucket_y) <= y_tolerance_px:
                bucket.append((y_center, rect))
                placed = True
                break
        if not placed:
            buckets.append([(y_center, rect)])

    merged: list = []
    for bucket in buckets:
        # 按 x0 排序
        bucket_rects = sorted(
            (rect for _, rect in bucket),
            key=lambda r: r[0],
        )
        current = bucket_rects[0]
        cx0, cy0, cw, ch = current
        cx1 = cx0 + cw
        for nxt in bucket_rects[1:]:
            nx0, ny0, nw, nh = nxt
            nx1 = nx0 + nw
            # 水平间距: nxt.x0 - current.x1
            gap = nx0 - cx1
            if gap <= gap_threshold_px:
                # 合并
                new_x0 = min(cx0, nx0)
                new_x1 = max(cx1, nx1)
                new_y0 = min(cy0, ny0)
                new_y1 = max(cy0 + ch, ny0 + nh)
                cx0, cy0 = new_x0, new_y0
                cw = new_x1 - new_x0
                ch = new_y1 - new_y0
                cx1 = new_x1
            else:
                merged.append(output_factory(cx0, cy0, cw, ch))
                cx0, cy0, cw, ch = nx0, ny0, nw, nh
                cx1 = nx0 + nw
        merged.append(output_factory(cx0, cy0, cw, ch))
    return merged


class _TupleRect:
    """duck-typing QRectF: 提供 .x() .y() .width() .height() 接口.

    当 PyQt6 不可用或测试环境下, 替代 QRectF 输出, 满足 main.py 的
    _deduplicate_rects 用 r.x() / r.y() / r.width() / r.height() 调用.
    """
    __slots__ = ("_x", "_y", "_w", "_h")

    def __init__(self, x: float, y: float, w: float, h: float) -> None:
        self._x, self._y, self._w, self._h = float(x), float(y), float(w), float(h)

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y

    def width(self) -> float:
        return self._w

    def height(self) -> float:
        return self._h


def _make_output_rect(x: float, y: float, w: float, h: float):
    """构造一个与 QRectF 接口兼容的 rect 对象."""
    try:
        from PyQt6.QtCore import QRectF  # type: ignore
        return QRectF(float(x), float(y), float(w), float(h))
    except Exception:
        return _TupleRect(float(x), float(y), float(w), float(h))


def collect_image_block_ocr_hits(
    page,
    patterns,
    scan_scale,
    recognize_fn,
    calculate_rect_fn,
    clip_to_page_rect_fn,
    preprocess_fn=None,
    page_dict=None,
    render_clip_fn=None,
    image_clip_rects=None,
):
    """对嵌入图片区域执行 OCR，并返回页面坐标系下的命中矩形。"""
    compiled_patterns = compile_active_patterns(patterns)
    if not compiled_patterns:
        return []

    if image_clip_rects is None:
        if page_dict is None:
            page_dict = page.get_text("dict")
        image_clip_rects = collect_embedded_image_clip_rects(page_dict)

    render_clip = render_clip_fn or render_pdf_clip_to_bgr
    # v37.7.x 方案 X: 收集 (line_box, page_rect) 而非纯 page_rect, 末尾做相邻合并.
    hits_with_box: list = []

    for clip_rect in image_clip_rects or []:
        try:
            clip_img = render_clip(page, clip_rect, scan_scale)
        except Exception as exc:
            print(f"[OCR WARN] 裁剪图片区域失败: {type(exc).__name__}: {exc}")
            continue

        if clip_img is None or getattr(clip_img, "size", 0) == 0:
            continue

        # v37.7.x 双路 OCR: 同时跑原始图 (用于手写体) 和预处理图 (用于印刷体增强).
        # 原 OCRWorker 仅跑预处理图, 导致 preprocess_image 把手写体行擦掉.
        # 现在合并两路输出作为识别行来源, 后续 calculate_rect_fn 用对应 scan_img.
        scan_outputs: list = []  # list of (scan_img, ocr_results)

        # 路 1: 原始图 (手写体友好)
        try:
            res_raw = recognize_fn(clip_img)
            scan_outputs.append((clip_img, res_raw or []))
        except Exception as exc:
            print(f"[OCR WARN] 原始图 OCR 失败: {type(exc).__name__}: {exc}")

        # 路 2: 预处理图 (印刷体增强) -- 仅在 preprocess_fn 存在时
        if preprocess_fn is not None:
            try:
                pre_img = preprocess_fn(clip_img)
                res_pre = recognize_fn(pre_img)
                scan_outputs.append((pre_img, res_pre or []))
            except Exception as exc:
                print(f"[OCR WARN] 预处理图 OCR 失败: {type(exc).__name__}: {exc}")

        for scan_img, ocr_results in scan_outputs:
            for box, text in iter_ocr_lines(ocr_results):
                if not text:
                    continue
                for pattern in compiled_patterns:
                    for match in pattern.finditer(text):
                        local_rect = calculate_rect_fn(box, text, match.span(), scan_img)
                        if local_rect is None:
                            continue
                        page_rect = clip_to_page_rect_fn(local_rect, clip_rect)
                        if page_rect is not None:
                            hits_with_box.append((box, page_rect))

    # 方案 X: 同一 OCR 行内水平相邻命中合并, 消除字符级权重误差留下的 rect 间隙.
    return merge_adjacent_hit_rects(hits_with_box)
