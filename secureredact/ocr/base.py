"""
OCR 引擎基类和数据结构
提供统一的 OCR 结果格式，无论使用哪个引擎
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型标注
    # P0-6: numpy 只在类型标注里用到, 改为 TYPE_CHECKING 导入。
    # 之前模块级 import numpy 会把 numpy 拖进 secureredact.api 的导入链,
    # 在 CI 的 coverage 预导入场景下触发 numpy 2.4 的
    # "cannot load module more than once per process" 硬错误,
    # 导致 api 覆盖率门禁整条链路失败(实测 api.py 覆盖率掉到 5%)。
    import numpy as np


@dataclass
class CharInfo:
    """单字符信息（PaddleOCR有，RapidOCR为空列表）"""
    char: str
    box: List[List[float]]  # 四点坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    confidence: float


@dataclass
class OCRResult:
    """OCR 识别结果 - 统一格式"""
    text: str           # 完整文本
    box: List[List[float]]  # 整行框四点坐标
    chars: List[CharInfo]   # 字符列表（RapidOCR为空，PaddleOCR有字符级坐标）
    confidence: float
    engine: str         # 来源引擎标识 "rapidocr" 或 "paddleocr"


class BaseOCREngine(ABC):
    """OCR 引擎抽象基类"""

    name: str = "base"
    supports_char_level: bool = False

    @abstractmethod
    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        """
        识别图像中的文字

        Args:
            image: OpenCV 格式图像 (BGR)

        Returns:
            List[OCRResult]: 识别结果列表
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查引擎是否可用（依赖是否安装、模型是否存在）

        Returns:
            bool: 引擎是否可用
        """
        pass

    def warmup(self) -> bool:
        """
        预热引擎（可选，用于提前加载模型）

        Returns:
            bool: 预热是否成功
        """
        return True
