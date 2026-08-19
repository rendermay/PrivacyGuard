"""
OCR 处理 Worker

v36.5: 模块化拆分，从 main.py 提取
v37.7.6: 全面上行 main.py 的高级特性：
  - 印章检测 (_detect_seals)
  - 像素级文本边界 (_detect_text_boundaries)
  - CJK 智能字符权重 (_calculate_from_line)
  - 检测框收缩 (_shrink_box)
  - box_adjust_ratio 参数
  - error_signal
  - RapidOCREngine 统一引擎接口
  - 坐标转换统一（在 calculate_sub_rect 内除以 scan_scale）
"""

import time
import traceback
import gc
import logging
import numpy as np
import cv2
import fitz
from PyQt6.QtCore import QThread, pyqtSignal, QRectF
import re

logger = logging.getLogger(__name__)

from privacyguard.ocr.mixed_pdf import (
    collect_embedded_image_clip_rects,
    collect_image_block_ocr_hits,
)
from privacyguard.ocr.text_pdf import collect_text_pdf_hit_boxes
from privacyguard.redaction.black_white_list_store import BlackWhiteListStore
from privacyguard.redaction.whitelist_split import _split_text_by_whitelist

# 常量定义
PROGRESS_UPDATE_INTERVAL = 0.05


class OCRWorker(QThread):
    """OCR 处理线程

    v36.4: 使用信号槽机制替代共享字典，解决线程安全问题
    v36.5: 模块化拆分
    v37.7.6: 全面上行高级特性
    """
    finished_signal = pyqtSignal(dict)
    progress_signal = pyqtSignal(int)
    page_result_signal = pyqtSignal(int, list)  # v36.4: 逐页发送结果 (页码, 矩形列表)
    # Wave 2.1 (Task 3): 矩形列表元素升级为 dict {rect: QRectF, source: str, text: str, rule_name: str}
    # Task 4 (MainWindow) 消费者依赖 source 字段区分 manual/ocr/jieba/seal.
    error_signal = pyqtSignal(str)  # v37.0.5: 错误信号

    def __init__(self, pdf_path, rules, use_enhance, custom_keywords, scan_scale, off_x, off_w,
                 use_char_level_ocr: bool = False, seal_detection_enabled: bool = False,
                 box_adjust_ratio: float = 0.0, enable_name_recognition: bool = False):
        super().__init__()
        self.pdf_path = pdf_path
        self.rules = rules
        self.use_enhance = use_enhance
        raw_keywords = custom_keywords.replace('\n', ' ').split()
        self.custom_keywords = [re.escape(k.strip()) for k in raw_keywords if k.strip()]
        self.scan_scale = scan_scale
        self.off_x = off_x
        self.off_w = off_w

        # v37.7.x: 中文姓名启发式识别开关 (默认 False,向后兼容)
        # 启用后从整页文本提取候选姓名,经 re.escape 后追加到 custom_keywords 列表
        self.enable_name_recognition = enable_name_recognition

        # v37.4.0: 只使用 RapidOCR，不再使用字符级 OCR
        self.use_char_level_ocr = False

        # v37.3.5: 检测框调节比例（支持负值扩大、正值收缩）
        self.box_adjust_ratio = box_adjust_ratio

        # v37.5.0: 印章检测功能
        self.seal_detection_enabled = seal_detection_enabled
        self._seal_detector = None  # 延迟加载
        # v37.9.0: 黑/白名单注入/过滤用. _process_page 开头会覆盖, 此处先建空槽.
        self._ocr_engine = None  # type: ignore[assignment]
        print(f"[OCRWorker] 初始化, seal_detection_enabled={seal_detection_enabled}")

    def preprocess_image(self, img_np):
        """图像预处理

        ┌────────────────────────────────────────────────────────────────────┐
        │ ⚠️  BGR→GRAY→OTSU→erode 这条 pipeline 是 collect_image_block_ocr_hits│
        │ 路 2 (印刷体增强) 的唯一来源. 任何一步调整 (核大小 / iterations /    │
        │ 阈值方法) 都会改变印刷体识别率, 并间接影响                            │
        │ merge_adjacent_hit_rects 的合并阈值是否仍然合适.                  │
        │                                                                    │
        │ 历史教训: 早期版本 erode iterations=2 会把手写体行擦掉, 导致        │
        │ collect_image_block_ocr_hits 仅剩路 1 输出, 印刷体命中率下降.     │
        │ 现在 iterations=1 是反复调参后的折中.                              │
        └────────────────────────────────────────────────────────────────────┘
        """
        try:
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            kernel = np.ones((2, 2), np.uint8)
            enhanced = cv2.erode(binary, kernel, iterations=1)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        except cv2.error as e:
            print(f"图像处理错误: {e}")
            return img_np

    def _render_full_page_bgr(self, page, scan_scale):
        """v37.7.x: 把整页 PDF 渲染为 BGR 图像 (供全页 OCR 用).

        与 render_pdf_clip_to_bgr 的区别: 不带 clip, 整页 0..width 0..height.

        ┌────────────────────────────────────────────────────────────────────┐
        │ ⚠️  alpha=False 必须保留 — 否则 cv2.imdecode 拿到 4 通道 BGRA,     │
        │ 后面的 cv2.cvtColor(img, BGR2GRAY) 会因通道数不匹配抛异常, 全页    │
        │ OCR / 姓名识别 / 黑名单注入 整条链路静默失效.                       │
        └────────────────────────────────────────────────────────────────────┘
        """
        pix = page.get_pixmap(
            matrix=fitz.Matrix(scan_scale, scan_scale),
            alpha=False,
        )
        img_data = np.frombuffer(pix.tobytes("png"), dtype=np.uint8)
        return cv2.imdecode(img_data, cv2.IMREAD_COLOR)

    def _get_seal_detector(self):
        """v37.5.0: 印章检测器（使用 OpenCV，无需额外依赖）"""
        if self._seal_detector is not None:
            return self._seal_detector
        self._seal_detector = True
        return self._seal_detector

    def _detect_seals(self, img_np, scan_scale):
        """v37.5.0: 使用 OpenCV 检测印章区域

        检测策略：
        1. 颜色过滤：检测红色区域
        2. 形状分析：筛选圆形/椭圆形区域
        3. 尺寸过滤：排除过大或过小的区域

        Args:
            img_np: 扫描图像（BGR 格式）
            scan_scale: 扫描缩放比例

        Returns:
            list[QRectF]: 印章区域列表（PDF 坐标系）

        ┌────────────────────────────────────────────────────────────────────┐
        │ ⚠️  HSV 阈值 (H 0-20 + 160-180, S/V 30-255), 面积上下限            │
        │ (100×100 < area < 50%×image), red_ratio/solidity/aspect/          │
        │ circularity 阈值 都是 v37.5.0 反复调参后的实测值, 不能凭直觉       │
        │ "优化". 放宽任一阈值 → 红色印刷字被误判为印章 (覆盖过大);           │
        │ 收紧任一阈值 → 真印章漏检.                                         │
        │                                                                    │
        │ 坐标换算 (x / scan_scale) 必须保留 — seal_rects 走 source="seal", │
        │ 与 OCR hit 在同一坐标系混用, 改换算单位会导致 hit rect 跨页错位.   │
        │                                                                    │
        │ 锁定测试: tests/unit/test_ocr_worker_source_field.py (seal      │
        │ source 字段断言).                                                  │
        └────────────────────────────────────────────────────────────────────┘
        """
        seal_rects = []

        if not self._get_seal_detector():
            return seal_rects

        try:
            h, w = img_np.shape[:2]
            print(f"[Seal Detection] 开始检测，图像尺寸: {w}x{h}")

            hsv = cv2.cvtColor(img_np, cv2.COLOR_BGR2HSV)

            red_lower1 = np.array([0, 30, 30])
            red_upper1 = np.array([20, 255, 255])
            red_lower2 = np.array([160, 30, 30])
            red_upper2 = np.array([180, 255, 255])

            mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
            mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
            red_mask = cv2.bitwise_or(mask1, mask2)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            print(f"[Seal Detection] 红色轮廓数: {len(contours)}")

            for contour in contours:
                area = cv2.contourArea(contour)
                min_area = 100 * 100
                max_area = (h * w) * 0.5
                if area < min_area or area > max_area:
                    continue

                x, y, w_rect, h_rect = cv2.boundingRect(contour)

                roi = red_mask[y:y+h_rect, x:x+w_rect]
                if roi.size == 0:
                    continue
                red_ratio = np.sum(roi > 0) / roi.size
                if red_ratio < 0.3:
                    continue

                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                solidity = float(area) / hull_area if hull_area > 0 else 0
                if solidity < 0.7:
                    continue

                aspect_ratio = float(w_rect) / h_rect if h_rect > 0 else 1
                if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                    continue

                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity < 0.5:
                        continue

                pdf_x = x / scan_scale
                pdf_y = y / scan_scale
                pdf_w = w_rect / scan_scale
                pdf_h = h_rect / scan_scale

                seal_rects.append(QRectF(pdf_x, pdf_y, pdf_w, pdf_h))
                print(f"[Seal Detection] 检测到印章: red_ratio={red_ratio:.2f}, "
                       f"aspect={aspect_ratio:.2f}, circularity={circularity:.2f}")

        except Exception as e:
            print(f"[Seal Detection] 检测失败: {type(e).__name__}: {e}")

        return seal_rects

    def _shrink_box(self, box, x_ratio=0.15, y_ratio=0.1):
        """v37.3.3: 收缩检测框边距

        Args:
            box: OCR 检测框 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            x_ratio: 水平方向收缩比例
            y_ratio: 垂直方向收缩比例

        Returns:
            收缩后的检测框
        """
        x_coords = [p[0] for p in box]
        y_coords = [p[1] for p in box]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        width = x_max - x_min
        height = y_max - y_min

        x_shrink = width * x_ratio / 2
        y_shrink = height * y_ratio / 2

        new_x_min = x_min + x_shrink
        new_x_max = x_max - x_shrink
        new_y_min = y_min + y_shrink
        new_y_max = y_max - y_shrink

        if new_x_min >= new_x_max:
            new_x_min = x_min
            new_x_max = x_max
        if new_y_min >= new_y_max:
            new_y_min = y_min
            new_y_max = y_max

        return [[new_x_min, new_y_min], [new_x_max, new_y_min],
                [new_x_max, new_y_max], [new_x_min, new_y_max]]

    def _detect_text_boundaries(self, img_region, box):
        """v37.3.7: 像素级文本边界检测

        通过水平投影分析找到检测框内实际文字的左右边界。

        Args:
            img_region: 扫描图像（BGR格式）
            box: OCR 检测框

        Returns:
            (actual_left, actual_right): 实际文字左右边界
        """
        try:
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            x_min = int(max(0, min(x_coords)))
            x_max = int(min(img_region.shape[1], max(x_coords)))
            y_min = int(max(0, min(y_coords)))
            y_max = int(min(img_region.shape[0], max(y_coords)))

            if x_max <= x_min or y_max <= y_min:
                return int(min(x_coords)), int(max(x_coords))

            roi = img_region[y_min:y_max, x_min:x_max]
            if roi.size == 0:
                return int(min(x_coords)), int(max(x_coords))

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            h_projection = np.sum(binary, axis=0)
            threshold = max(1, binary.shape[0] * 0.05)
            text_cols = np.where(h_projection > threshold)[0]

            if len(text_cols) == 0:
                return int(min(x_coords)), int(max(x_coords))

            actual_left = x_min + text_cols[0]
            actual_right = x_min + text_cols[-1]

            return actual_left, actual_right

        except Exception as e:
            print(f"[DEBUG] _detect_text_boundaries 错误: {e}")
            x_coords = [p[0] for p in box]
            return int(min(x_coords)), int(max(x_coords))

    def calculate_sub_rect(self, box, text, match_span, img_region=None):
        """v37.4.0: 计算子字符串的矩形区域（行级计算 + 像素边界检测）

        Args:
            box: 整行文本的检测框
            text: 整行文本
            match_span: 匹配位置 (start_idx, end_idx)
            img_region: 扫描图像区域，用于像素边界检测

        Returns:
            QRectF: 子字符串矩形区域（PDF坐标系）
        """
        try:
            start_idx, end_idx = match_span
            return self._calculate_from_line(box, text, start_idx, end_idx, img_region=img_region)
        except (ValueError, ZeroDivisionError, TypeError) as e:
            print(f"[WARN] calculate_sub_rect 错误: {e}")
            return None

    def _apply_whitelist_filter(self, rects: list, page_idx: int) -> list:
        """v38: 剥掉包含白名单子串的 hit; trim_only=True 时只剥白名单片段.

        OCR/seal 通道 hit.text 为空时,委托 _resolve_text_from_rect 查回.
        manual 来源豁免 (人工框选是显式意图).

        ┌────────────────────────────────────────────────────────────────────┐
        │ ⚠️  v38.0.1 hotfix — DO NOT REMOVE the original_text_was_empty    │
        │ branch below without first implementing proper matched-text      │
        │ propagation for image-channel hits.                               │
        │                                                                    │
        │ 历史 bug: image-channel custom_keyword 命中「签名或者盖章」中的     │
        │ 「盖章」子串时, _resolve_text_from_rect 反查得到整条 OCR token      │
        │ 文本「签名或者盖章」(因为小 hit rect 中心落在大 token bbox 内),   │
        │ trim + _sub_rect_for_text_span 用原小 rect 做权重切分会把          │
        │ 「签名或者」画到「盖章」位置, 导致错误脱敏.                       │
        │                                                                    │
        │ 当前修复: image-channel / seal hit (原 text 为空) 走 v37.9.0 行为  │
        │ (整条剥掉), 不做 trim. text-channel hit (原 text 非空) 继续走 trim. │
        │                                                                    │
        │ 锁定测试: tests/unit/test_whitelist_trim_only.py::                 │
        │           OCRFilterImageChannelEmptyTextTest                      │
        │                                                                    │
        │ 完整修复路径 (让 image-channel 也能 trim) 需要让                    │
        │ collect_image_block_ocr_hits 返回 matched 子串, 让 hit.text         │
        │ 携带精确 keyword, 避免 resolve 反查歧义. 见                        │
        │ CHANGELOG.md v38.0.0 「已知限制」段.                               │
        └────────────────────────────────────────────────────────────────────┘
        """
        store = BlackWhiteListStore.instance()
        whitelist = store.effective_whitelist()
        if not whitelist:
            return rects
        trim_only = store.is_trim_only()
        kept: list = []
        for hit in rects:
            source = hit.get("source", "ocr")
            if source == "manual":
                kept.append(hit)
                continue
            text = hit.get("text", "") or ""
            original_text_was_empty = (text == "")
            if not text:
                text = self._resolve_text_from_rect(hit.get("rect"), page_idx) or ""
            if not text:
                # 解析失败 → 沿用旧行为保留
                kept.append(hit)
                continue
            # ┌────────────────────────────────────────────────────────────┐
            # │ ⚠️  v38.0.1 hotfix — DO NOT REMOVE / SKIP THIS BRANCH.       │
            # │ image-channel / seal hit (原 text 为空): 必须走 v37.9.0       │
            # │ 整条剥掉, 不做 trim. 原因见上方 docstring 与 CHANGELOG.       │
            # │ 任何放宽此约束的修改都必须先实现 matched 子串传递到 hit.text.   │
            # └────────────────────────────────────────────────────────────┘
            if original_text_was_empty:
                if any(wl and wl in text for wl in whitelist):
                    continue  # 整条剥掉 — 勿改为 drop-while-preserve
                kept.append(hit)
                continue
            spans = _split_text_by_whitelist(text, whitelist)
            # 无 trim 必要 → 原样保留 (旧/新行为一致)
            no_split = (
                len(spans) == 1
                and spans[0][0] == 0
                and spans[0][1] == len(text)
            )
            if no_split:
                kept.append(hit)
                continue
            # 旧行为 (v37.9.0): 整条剥掉
            if not trim_only:
                continue
            # 新行为 (v38): 每个保留片段生成子 hit
            original_rect = hit.get("rect")
            for s, e, t in spans:
                if not t:
                    continue
                sub_rect = self._sub_rect_for_text_span(original_rect, text, s, e)
                if sub_rect is None:
                    continue  # 保守回退 (含换行 / 退化宽度)
                new_hit = dict(hit)
                new_hit["rect"] = sub_rect
                new_hit["text"] = t
                kept.append(new_hit)
        return kept

    @staticmethod
    def _sub_rect_for_text_span(
        rect,
        text: str,
        kept_start: int,
        kept_end: int,
    ):
        """v38: 字符权重比例估算子矩形. 多行 / 退化 → 返回 None (保守回退).

        字符权重与 _calculate_from_line.get_char_weight 对齐:
          - CJK 统一汉字 (一-鿿): 1.0
          - CJK 扩展 A (㐀-䶿): 1.0
          - CJK 兼容汉字 (豈-﫿): 1.0
          - 其它: 0.55
        """
        if rect is None or not text or kept_end <= kept_start:
            return None
        kept_span = text[kept_start:kept_end]
        if "\n" in kept_span:
            return None
        weights = [
            1.0 if (
                "一" <= c <= "鿿"
                or "㐀" <= c <= "䶿"
                or "豈" <= c <= "﫿"
            ) else 0.55
            for c in text
        ]
        total = sum(weights) or len(text)
        prefix = sum(weights[:kept_start])
        match = sum(weights[kept_start:kept_end])
        if total <= 0 or match <= 0:
            return None
        sub_x = rect.x() + (prefix / total) * rect.width()
        sub_w = (match / total) * rect.width()
        if sub_w <= 0:
            return None
        return QRectF(sub_x, rect.y(), sub_w, rect.height())

    def _resolve_text_from_rect(self, rect, page_idx: int) -> str:
        """从该页已缓存的 OCR token 列表中, 找包含 rect 中心的 token, 返回其原文.

        未命中返回空串.  由 _warm_rect_text_cache 填充缓存.

        ┌────────────────────────────────────────────────────────────────────┐
        │ ⚠️  注意 — 返回的 text 可能是完整的 OCR token (而非 rect 实际       │
        │ 覆盖范围的子串). 调用方必须理解此特性, 不能直接拿返回值做精确     │
        │ 字符级 sub-rect 切分. 具体案例与处理见 _apply_whitelist_filter     │
        │ 中 `original_text_was_empty` 分支 (v38.0.1 hotfix).               │
        └────────────────────────────────────────────────────────────────────┘
        """
        if rect is None:
            return ""
        tokens_per_page = getattr(self, "_rect_tokens_per_page", None)
        if not tokens_per_page:
            return ""
        cx = rect.x() + rect.width() / 2
        cy = rect.y() + rect.height() / 2
        for token_rect, text in tokens_per_page.get(page_idx, []):
            if token_rect.contains(cx, cy):
                return text
        return ""

    def _warm_rect_text_cache(self, page, page_idx: int, scan_scale: float) -> None:
        """v37.9.0-hotfix2: 把整页 OCR token 的 (bbox → text) 填进缓存.

        上下文: OCR 通道 hit.text 默认空字符串, _apply_whitelist_filter 无法做子串匹配.
        本方法做一次整页 OCR, 把每个 token 的 QRectF + 原文 存到 _rect_tokens_per_page,
        让 _resolve_text_from_rect 能用 bbox-containment 反查.
        只在 whitelist 非空时调用, 避免无意义 OCR 开销.

        注意: token bbox 在 image 坐标 (0..image_h, 0..image_w), 而 hit rect 是 page 坐标 (PDF 点),
        需要除以 scan_scale 对齐. 这里存的是 image 坐标 (因为 hit rect 是 image 坐标除以 scan_scale).
        """
        tokens_per_page = getattr(self, "_rect_tokens_per_page", None)
        if tokens_per_page is None:
            tokens_per_page = {}
            self._rect_tokens_per_page = tokens_per_page
        tokens = self._ocr_full_page_tokens(page, scan_scale)
        cache_list = []
        for text, box in tokens:
            if not text or not box or len(box) < 4:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x0, y0 = min(xs), min(ys)
            x1, y1 = max(xs), max(ys)
            # image 坐标 → page 坐标: 除以 scan_scale
            token_rect = QRectF(
                x0 / scan_scale,
                y0 / scan_scale,
                (x1 - x0) / scan_scale,
                (y1 - y0) / scan_scale,
            )
            cache_list.append((token_rect, text))
        tokens_per_page[page_idx] = cache_list

    @staticmethod
    def _rects_overlap(a, b) -> bool:
        """两个 rect 是否重叠 / 相邻 (相邻 2 像素以内也算)."""
        if a is None or b is None:
            return False
        pad = 2
        return not (
            a.x() + a.width() + pad < b.x()
            or b.x() + b.width() + pad < a.x()
            or a.y() + a.height() + pad < b.y()
            or b.y() + b.height() + pad < a.y()
        )

    @staticmethod
    def _dedupe_overlapping(hits: list) -> list:
        """合并 rect 重叠或相邻的 blacklist hit.

        合并后保留第一个 hit 的 text/rule_name/source, 更新 rect 为最小外接矩形.
        """
        if not hits:
            return hits
        # 简单 O(n^2): blacklist 注入量小 (每条目 1-几个 hit), 足够
        groups: list = []
        for hit in hits:
            rect = hit["rect"]
            placed = False
            for grp in groups:
                gr = grp[0]["rect"]
                if OCRWorker._rects_overlap(gr, rect):
                    grp.append(hit)
                    placed = True
                    break
            if not placed:
                groups.append([hit])
        merged = []
        for grp in groups:
            if len(grp) == 1:
                merged.append(grp[0])
                continue
            xs = [h["rect"].x() for h in grp]
            ys = [h["rect"].y() for h in grp]
            x_max = [h["rect"].x() + h["rect"].width() for h in grp]
            y_max = [h["rect"].y() + h["rect"].height() for h in grp]
            union = QRectF(min(xs), min(ys), max(x_max) - min(xs), max(y_max) - min(ys))
            first = dict(grp[0])  # 浅拷贝
            first["rect"] = union
            merged.append(first)
        return merged

    def _ocr_full_page_tokens(self, page, scan_scale) -> list:
        """整页 OCR, 返回 [(text, box)] 列表. 由 _collect_blacklist_hits 使用."""
        ocr_engine = getattr(self, "_ocr_engine", None)
        if ocr_engine is None:
            return []
        try:
            full_img = self._render_full_page_bgr(page, scan_scale)
            results = ocr_engine.recognize(full_img)
        except Exception:
            return []
        out = []
        for r in results:
            out.append((getattr(r, "text", ""), getattr(r, "box", None)))
        return out

    def _collect_blacklist_hits(self, page, page_idx: int, blacklist: list, scan_scale: float) -> list:
        """扫描 image 通道 OCR tokens,命中 blacklist 条目 → 构造 hit.

        ┌────────────────────────────────────────────────────────────────────┐
        │ ⚠️  历史上曾分支调用 self._ocr_clip(...) 但该方法从未实现,          │
        │ AttributeError 被 try/except 吞掉 → 黑名单注入静默失效 (扫描型    │
        │ PDF 上 blacklist 完全不工作). 当前统一走 _ocr_full_page_tokens    │
        │ full-page OCR fast path. 任何"按 clip 范围 OCR"的优化必须先        │
        │ 实现 _ocr_clip 并保留 full-page 回退, 不能直接换掉 fast path.      │
        │                                                                    │
        │ hit 走 source="blacklist", 必须在 _apply_whitelist_filter 二次过滤  │
        │ 之后追加 (见 _process_page 末尾的二次 whitelist 调用), 否则同条目  │
        │ blacklist 命中会被白名单先剥掉.                                     │
        └────────────────────────────────────────────────────────────────────┘
        """
        from privacyguard.ocr.mixed_pdf import collect_embedded_image_clip_rects
        from PyQt6.QtCore import QRectF

        if not blacklist:
            return []
        page_dict = page.get_text("dict")
        clip_rects = collect_embedded_image_clip_rects(page_dict)
        if not clip_rects:
            rect = page.rect
            clip_rects = [(rect.x0, rect.y0, rect.x1, rect.y1)]

        # OCR 一次, 收集 (text, box) tokens
        # v37.9.0-hotfix: 统一走 _ocr_full_page_tokens (worker 实际只有 full-page OCR fast path).
        # 早期版本这里分支调用 self._ocr_clip(...), 但 _ocr_clip 从未实现, 实际生产中
        # AttributeError 被 try/except 吞掉 → 黑名单注入静默失效. 现统一, 简单且与 _ocr_full_page_tokens 一致.
        ocr_engine = getattr(self, "_ocr_engine", None)
        if ocr_engine is None:
            return []
        try:
            full_img = self._render_full_page_bgr(page, scan_scale)
            tokens = self._ocr_full_page_tokens(page, scan_scale)
        except Exception as exc:
            logger.warning("_collect_blacklist_hits OCR 失败: %s", exc)
            return []

        # tok_box 是 OCR 坐标 (image / scan_scale 比例) 下的多边形 [[x,y], ...],
        # 而页面 hit 是 PDF 坐标系. 我们没有 _process_page 的 per-clip clip_rect
        # 上下文, 但 _ocr_full_page_tokens 用的就是整页 full_img, 所以 image → page
        # 的偏移就是 (0,0), 仅需除以 scan_scale.
        def _box_to_page_rect(tok_box):
            if not tok_box or len(tok_box) < 4:
                return None
            xs = [p[0] for p in tok_box]
            ys = [p[1] for p in tok_box]
            x0, y0 = min(xs), min(ys)
            x1, y1 = max(xs), max(ys)
            return QRectF(
                x0 / scan_scale,
                y0 / scan_scale,
                (x1 - x0) / scan_scale,
                (y1 - y0) / scan_scale,
            )

        hits = []
        for bl_item in blacklist:
            if not bl_item:
                continue
            for tok_text, tok_box in tokens:
                if bl_item in tok_text:
                    rect = _box_to_page_rect(tok_box)
                    if rect is None:
                        continue
                    hits.append({
                        "rect": rect,
                        "source": "blacklist",
                        "text": bl_item,
                        "rule_name": f"黑名单:{bl_item}",
                    })
        return self._dedupe_overlapping(hits)

    def _calculate_from_line(self, box, text, start_idx, end_idx, img_region=None):
        """v37.3.7: 行级坐标估算 + 像素边界检测 + CJK 智能字符权重

        Returns:
            QRectF: 子字符串矩形区域（PDF坐标系）

        ┌────────────────────────────────────────────────────────────────────┐
        │ ⚠️  get_char_weight() 内嵌的 CJK 权重 1.0 vs 数字/英文 0.55 是    │
        │ v37.7.x 反复调参的结果, 与 mixed_pdf.DEFAULT_HIT_MERGE_GAP_PX     │
        │ (30px) 联合调过 — 任一侧变动都会让"汉字 + 数字"同行场景出现         │
        │ rect 间隙 (例 "刘妹 034-62407159"). 调整前必须跑                  │
        │ tests/unit/test_mixed_pdf_ocr.py 全量回归.                         │
        │                                                                    │
        │ 坐标换算 (/ self.scan_scale, - self.off_x, - self.off_w) 也不能动: │
        │ mixed_pdf.collect_image_block_ocr_hits 的调用方依赖此函数返回      │
        │ PDF 坐标系 rect, 若改成 scan 坐标, 后续 save_pdf 的                │
        │ page.add_redact_annot 会把脱敏区画到完全错的位置.                  │
        │                                                                    │
        │ img_region 优先于 shrunk_box 的分支顺序不能换 — 像素边界精度       │
        │ 高于经验收缩, 换顺序会让手写体场景下边界检测被跳过.                 │
        └────────────────────────────────────────────────────────────────────┘
        """
        try:
            # 优先使用像素边界检测
            if img_region is not None:
                line_x_min, line_x_max = self._detect_text_boundaries(img_region, box)
            else:
                shrunk_box = self._shrink_box(box, x_ratio=self.box_adjust_ratio,
                                               y_ratio=self.box_adjust_ratio * 0.6)
                line_x_min = min([p[0] for p in shrunk_box])
                line_x_max = max([p[0] for p in shrunk_box])

            line_y_min = min([p[1] for p in box])
            line_y_max = max([p[1] for p in box])

            if len(text) == 0 or line_x_max <= line_x_min:
                return None

            # 智能字符宽度估算（区分中文/数字/英文）
            def get_char_weight(char):
                if '\u4e00' <= char <= '\u9fff':  # CJK统一汉字
                    return 1.0
                elif '\u3400' <= char <= '\u4dbf':  # CJK扩展A
                    return 1.0
                elif '\uF900' <= char <= '\uFAFF':  # CJK兼容汉字
                    return 1.0
                else:
                    return 0.55  # 数字、英文、符号等

            total_weight = sum(get_char_weight(c) for c in text)
            prefix_weight = sum(get_char_weight(c) for c in text[:start_idx])
            match_weight = sum(get_char_weight(c) for c in text[start_idx:end_idx])

            if total_weight <= 0:
                total_weight = len(text)
                prefix_weight = start_idx
                match_weight = end_idx - start_idx

            line_width = line_x_max - line_x_min
            sub_x = line_x_min + (prefix_weight / total_weight) * line_width
            sub_w = (match_weight / total_weight) * line_width

            # 小边距
            margin = 1.0
            sub_x += margin
            sub_w = max(5, sub_w - margin * 2)

            # 坐标转换：扫描坐标 -> PDF坐标
            pdf_x = sub_x / self.scan_scale
            pdf_y = line_y_min / self.scan_scale
            pdf_w = sub_w / self.scan_scale
            pdf_h = (line_y_max - line_y_min) / self.scan_scale

            # PDF坐标系下应用偏移
            final_x = pdf_x - self.off_x
            final_w = max(5, pdf_w - self.off_w)

            return QRectF(final_x, pdf_y, final_w, pdf_h)
        except (ValueError, ZeroDivisionError, TypeError) as e:
            print(f"[WARN] _calculate_from_line 错误: {e}")
            return None

    def _process_page(self, page, page_idx, *, ocr_engine, scan_scale):
        """Wave 2.1 (Task 3): 处理单页 OCR,返回 list[dict] hits.

        每项含:
          - rect: QRectF (PDF 坐标)
          - source: str ∈ {"rule", "ocr", "jieba", "seal"}
          - text: str (命中原文,OCR 通道与 seal 通道为空)
          - rule_name: str (触发命中的 pattern 描述)

        同时通过 page_result_signal.emit(page_idx, rects) 通知消费者.
        """
        # v37.9.0: 把 ocr_engine 挂到 self, 供 _collect_blacklist_hits 等用
        self._ocr_engine = ocr_engine
        rects = []
        page_text = page.get_text()
        page_dict = page.get_text("dict")
        image_clip_rects = collect_embedded_image_clip_rects(page_dict)

        # v37.7.x 修订: 中文姓名启发式识别同时覆盖 文本通道 和 图片通道.
        # 原实现 (page_text 非空才注入) 在扫描型 PDF (page_text="") 上完全失效.
        # 修复: 即使 page_text 为空, 也先用 RapidOCR 全页扫一次,把行级文本拼起来
        # 喂给 jieba 抽取人名,然后 re.escape 追加到 all_patterns (image 通道后续会用到).
        #
        # v37.x 修订: 阈值化触发条件. CamScanner/intsig 等扫描型 PDF 的 page_text
        # 几乎为空但非空 — 通常仅含页码水印 (如 "1\n", 长度 < 10). 原 `not jieba_source_text`
        # 在此场景下判 False, 兜底 OCR 永远不触发, jieba 拿到 "1" → 0 个人名 →
        # 整页姓名脱敏静默失效. 阈值 JIEBA_MIN_TEXT_LEN 用于判定"文本太短, 走 OCR 兜底".
        JIEBA_MIN_TEXT_LEN = 50
        all_patterns = self.rules + self.custom_keywords
        jieba_extra = []
        if self.enable_name_recognition:
            jieba_source_text = page_text or ""
            if len(jieba_source_text.strip()) < JIEBA_MIN_TEXT_LEN and image_clip_rects:
                try:
                    _ocr_for_names = ocr_engine.recognize(
                        self._render_full_page_bgr(page, scan_scale)
                    )
                    _line_texts = [
                        getattr(r, "text", "")
                        for r in (_ocr_for_names or [])
                    ]
                    jieba_source_text = "\n".join(
                        t for t in _line_texts if t
                    )
                except Exception as _exc:
                    # 永不向调用方抛异常; 静默回退到空字符串即可
                    print(f"[OCRWorker] 全页 OCR (姓名抽取用) 失败: {_exc}")
                    jieba_source_text = ""

            if jieba_source_text:
                try:
                    from privacyguard.pii.name_recognizer import (
                        extract_person_names,
                    )
                    _names = extract_person_names(jieba_source_text)
                    if _names:
                        _existing = set(self.rules) | set(self.custom_keywords)
                        jieba_extra = [
                            re.escape(n) for n in _names
                            if n not in _existing
                        ]
                        if jieba_extra:
                            all_patterns = all_patterns + jieba_extra
                except Exception as _exc:
                    print(f"[OCRWorker] 姓名识别失败: {_exc}")

        # 文本通道: 分三路,各自打 source 标签
        if page_text.strip():
            # self.rules -> source='rule'
            if self.rules:
                rule_hits = collect_text_pdf_hit_boxes(
                    page, self.rules, page_text=page_text
                )
                rects.extend({
                    "rect": QRectF(x, y, w, h),
                    "source": "rule",
                    "text": text,
                    "rule_name": rule_name,
                } for x, y, w, h, text, rule_name in rule_hits)

            # self.custom_keywords -> source='ocr'
            if self.custom_keywords:
                custom_hits = collect_text_pdf_hit_boxes(
                    page, self.custom_keywords, page_text=page_text
                )
                rects.extend({
                    "rect": QRectF(x, y, w, h),
                    "source": "ocr",
                    "text": text,
                    "rule_name": rule_name,
                } for x, y, w, h, text, rule_name in custom_hits)

            # jieba 注入 -> source='jieba'
            if jieba_extra:
                jieba_hits = collect_text_pdf_hit_boxes(
                    page, jieba_extra, page_text=page_text
                )
                rects.extend({
                    "rect": QRectF(x, y, w, h),
                    "source": "jieba",
                    "text": text,
                    "rule_name": "姓名启发式",
                } for x, y, w, h, text, _rule_name in jieba_hits)

        if not image_clip_rects and not page_text.strip():
            image_clip_rects = [(page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)]

        image_hit_count = 0
        if image_clip_rects:
            # image 通道: collect_image_block_ocr_hits 仍返回 QRectF 列表,
            # 在调用点 wrap 为 dict (与 brief 一致, 不动 mixed_pdf.py 契约)
            image_hit_rects = collect_image_block_ocr_hits(
                page,
                all_patterns,
                scan_scale,
                recognize_fn=lambda scan_img: ocr_engine.recognize(scan_img),
                calculate_rect_fn=lambda box, text, span, scan_img: self.calculate_sub_rect(
                    box,
                    text,
                    span,
                    img_region=scan_img,
                ),
                clip_to_page_rect_fn=lambda local_rect, clip_rect: QRectF(
                    local_rect.x() + clip_rect[0],
                    local_rect.y() + clip_rect[1],
                    local_rect.width(),
                    local_rect.height(),
                ),
                preprocess_fn=self.preprocess_image if self.use_enhance else None,
                page_dict=page_dict,
                image_clip_rects=image_clip_rects,
            )
            rects.extend({
                "rect": qr,
                "source": "ocr",
                # ⚠️  v38.0.1: 故意保持 text="" 不要改. 改为非空需先实现
                # collect_image_block_ocr_hits 返回 matched 子串 (而非仅 rect),
                # 否则 _apply_whitelist_filter 的 image-channel 分支会错位涂黑.
                # 详见 _apply_whitelist_filter 顶部 docstring + CHANGELOG v38.0.0.
                "text": "",
                "rule_name": "OCR图像通道",
            } for qr in image_hit_rects)
            image_hit_count = len(image_hit_rects)

        # v37.9.0-hotfix2: OCR 通道 hit.text 默认为空,
        # whitelist 过滤需要从 (page_idx, rect_center) 反查原文.
        # warm cache 让 _resolve_text_from_rect 能查回 OCR token 文本.
        if BlackWhiteListStore.instance().effective_whitelist():
            self._warm_rect_text_cache(page, page_idx, scan_scale)

        # v37.9.0: 黑/白名单串联. 先 whitelist 过滤剥掉已有命中, 再 blacklist 注入.
        rects = self._apply_whitelist_filter(rects, page_idx)

        blacklist = BlackWhiteListStore.instance().effective_blacklist()
        if blacklist:
            blacklist_hits = self._collect_blacklist_hits(
                page, page_idx, blacklist, scan_scale
            )
            rects.extend(blacklist_hits)

        # blacklist 注入后再过一次 whitelist 过滤, 确保同条目场景下白名单赢.
        rects = self._apply_whitelist_filter(rects, page_idx)

        if image_clip_rects or (page_text.strip() and rects):
            text_count = len(rects) - image_hit_count
            print(
                f"[OCR] 页面 {page_idx}: 文本命中 {text_count}, "
                f"图片块 {len(image_clip_rects)}, 图片OCR命中 {image_hit_count}"
            )

        # v37.5.0: 印章检测 -> source='seal'
        if self.seal_detection_enabled and "__SEAL_DETECTION__" in self.rules:
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(scan_scale, scan_scale))
                img_data = np.frombuffer(pix.tobytes("png"), dtype=np.uint8)
                img_np = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
                scan_img = self.preprocess_image(img_np) if self.use_enhance else img_np
                seal_rects = self._detect_seals(scan_img, scan_scale)
                rects.extend({
                    "rect": sr,
                    "source": "seal",
                    # ⚠️  v38.0.1: seal hit text 故意保持 "" 不要改.
                    # _apply_whitelist_filter 中 `original_text_was_empty` 分支
                    # 会让 seal hit 走 v37.9.0 整条剥掉行为 (不 trim), 避免 sub-rect
                    # 错位. 详见 _apply_whitelist_filter 顶部 docstring.
                    "text": "",
                    "rule_name": "印章检测",
                } for sr in seal_rects)
                if seal_rects:
                    print(f"[Seal Detection] 页面 {page_idx} 检测到 {len(seal_rects)} 个印章")
            except Exception as e:
                print(f"[Seal Detection] 页面 {page_idx} 检测失败: {type(e).__name__}: {e}")

        # 逐页发送结果 (Wave 2.1: payload 改为 list[dict])
        self.page_result_signal.emit(page_idx, rects)
        return rects

    def run(self):
        """执行 OCR 扫描

        v37.0.6: 重构信号发送顺序，确保资源清理后再发送信号
        v37.0.5: 增强异常处理
        v36.4: 使用信号槽机制替代共享字典
        Wave 2.1 (Task 3): 单页处理提取到 _process_page, payload 升级 list[dict]
        """
        error_msg = None
        doc = None
        try:
            # v37.4.0: 直接使用 RapidOCR
            from privacyguard.ocr.rapidocr import RapidOCREngine
            ocr_engine = RapidOCREngine()

            if not ocr_engine.is_available():
                error_msg = "RapidOCR 引擎不可用，请检查依赖安装"
                print(f"[OCR ERROR] {error_msg}")
                return

            print(f"[OCR] 使用引擎: {ocr_engine.name}")

            doc = fitz.open(self.pdf_path)
            total = len(doc)
            SCAN_SCALE = self.scan_scale
            last_emit_time = 0

            batch_size = 10

            for batch_start in range(0, total, batch_size):
                if self.isInterruptionRequested():
                    break

                batch_end = min(batch_start + batch_size, total)

                for i in range(batch_start, batch_end):
                    if self.isInterruptionRequested():
                        break

                    page = doc[i]
                    self._process_page(page, i, ocr_engine=ocr_engine, scan_scale=SCAN_SCALE)

                    # 背压控制
                    current_progress = int((i+1)/total * 100)
                    current_time = time.time()
                    if current_time - last_emit_time > PROGRESS_UPDATE_INTERVAL or i == total - 1:
                        self.progress_signal.emit(current_progress)
                        last_emit_time = current_time

                if self.isInterruptionRequested():
                    break

                # 批次间垃圾回收
                if batch_end < total:
                    gc.collect()

        except Exception as e:
            error_msg = f"OCR 处理错误: {type(e).__name__}: {e}"
            print(f"[OCR ERROR] {error_msg}")
            traceback.print_exc()
        finally:
            if doc:
                doc.close()

        # 资源清理后发送信号
        if error_msg:
            self.error_signal.emit(error_msg)
        self.finished_signal.emit({})
