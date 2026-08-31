"""
PR-C2.x Task 1.1: 视觉基线对比工具

提供 `compute_diff(left, right)`,返回像素级差异统计,供后续 PR-C2.2 / PR-C2.3
做基线回归断言使用。

设计要点:
- 输入两张 PNG 路径(PIL.Image 支持的任何格式也可,但视觉基线统一存 PNG)。
- 输出 `(ratio, total, different)`:
    * ratio    — 差异像素 / 总像素,范围 [0, 1]
    * total    — 总像素数(width * height)
    * different— 任意 RGB 通道差值 > 4 的像素数(容许抗锯齿抖动;alpha 通道不参与)
- 完全相同图 → ratio == 0.0, different == 0。
- 尺寸不同 → 抛 ValueError,不静默裁剪。
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageChops


# 视觉基线差异容忍度阈值:diff ratio > THRESHOLD 即视为基线失守,
# 后续 PR-C2.2 截图对比测试会用此值做 assertLess 断言。
THRESHOLD: float = 0.005

# 单像素任意 RGB 通道差值 > 4 才计为"差异像素",用来吸收 JPEG/抗锯齿抖动。
_PIXEL_TOLERANCE: int = 4


def compute_diff(left: Path, right: Path) -> Tuple[float, int, int]:
    """计算两张同尺寸图片的像素差异。

    Args:
        left:  基线 PNG 路径(或其他 PIL 支持格式)。
        right: 当前截图 PNG 路径。

    Returns:
        (ratio, total, different):
            - ratio    = different / total
            - total    = width * height
            - different= 任意 RGB 通道差值超过 `_PIXEL_TOLERANCE` 的像素数

    Raises:
        ValueError: 两张图尺寸不一致。
    """
    img_left = Image.open(Path(left)).convert("RGBA")
    img_right = Image.open(Path(right)).convert("RGBA")

    if img_left.size != img_right.size:
        raise ValueError(
            f"图像尺寸不一致: left={img_left.size}, right={img_right.size}。"
            f"视觉基线必须严格同分辨率对比,禁止隐式缩放。"
        )

    width, height = img_left.size
    total = width * height

    # ImageChops.difference 返回两图逐像素差的 RGBA 图
    diff = ImageChops.difference(img_left, img_right)

    # 仅看 RGB 三通道(R,G,B 任一 > 容差即视为差异像素),
    # alpha 不参与 — 抗锯齿 / 透明度抖动太敏感。
    # 注意:必须先转 RGB 再 getbbox()。原 diff 图的 alpha 通道在两图
    # 同 alpha(=255)时会全为 0,会让 getbbox() 误判为"无差异"。
    rgb_diff = diff.convert("RGB")

    # bbox 是首个非零像素的包围盒;None 表示完全一致
    if rgb_diff.getbbox() is None:
        return (0.0, total, 0)

    pixels = rgb_diff.load()
    different = 0
    tol = _PIXEL_TOLERANCE
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r > tol or g > tol or b > tol:
                different += 1

    ratio = different / total if total else 0.0
    return (ratio, total, different)


__all__ = ["compute_diff", "THRESHOLD"]