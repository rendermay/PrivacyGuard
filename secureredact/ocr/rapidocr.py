"""
RapidOCR 引擎实现
- 速度快
- 行级检测框
- 默认引擎
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型标注
    # P0-6: numpy 只在类型标注里用到, 改为 TYPE_CHECKING 导入,
    # 避免把 numpy 拖进 secureredact.api 的导入链(见 ocr/base.py 同项说明)。
    import numpy as np

from .base import BaseOCREngine, OCRResult, CharInfo


class RapidOCREngine(BaseOCREngine):
    """RapidOCR 引擎封装"""

    name = "rapidocr"
    supports_char_level = False

    def __init__(self):
        self._engine = None

    def is_available(self) -> bool:
        """检查 RapidOCR 是否可用"""
        try:
            from rapidocr_onnxruntime import RapidOCR
            return True
        except ImportError:
            return False

    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        """
        使用 RapidOCR 识别图像

        Args:
            image: OpenCV 格式图像 (BGR)

        Returns:
            List[OCRResult]: 识别结果列表
        """
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()

        result, _ = self._engine(image)
        results = []

        if result:
            for line in result:
                box, text = line[0], line[1]
                # RapidOCR 返回的 box 格式: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                results.append(OCRResult(
                    text=text,
                    box=box,
                    chars=[],  # RapidOCR 不支持字符级
                    confidence=0.9,
                    engine="rapidocr"
                ))

        return results
