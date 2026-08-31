"""
PR-C2.x Task 1.1: 视觉基线对比工具单元测试

覆盖 `secureredact/ui/styles/baselines/compare.py::compute_diff` 的两条主路径：
1. 完全相同的两张图 → ratio == 0.0
2. 像素差异显著的图 → ratio > 0
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from secureredact.ui.styles.baselines import compare
from secureredact.ui.styles.baselines.compare import THRESHOLD, compute_diff


BASELINE_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "secureredact"
    / "ui"
    / "styles"
    / "baselines"
)


def _make_solid_png(path: Path, color: tuple[int, int, int, int], size: int = 16) -> Path:
    """生成一张填充纯色的 PNG(用于测试,不依赖任何基线文件)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (size, size), color)
    img.save(path)
    return path


def _make_baseline_if_missing(path: Path, size: int = 16) -> Path:
    """如果基线 PNG 不存在则生成一张临时占位 PNG(仅用于本测试)。"""
    if path.exists():
        return path
    return _make_solid_png(path, (200, 200, 200, 255), size=size)


class TestComputeDiff(unittest.TestCase):

    def setUp(self) -> None:
        # 确保基线目录存在(可被 compare.py 的 __init__.py 找到)
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    def test_compute_diff_returns_tuple(self):
        """完全相同的两张图 → ratio==0.0, different==0, total>0。"""
        # Task 1.2 之前,基线 PNG 可能不存在;缺失则临时生成一张
        baseline = _make_baseline_if_missing(
            BASELINE_DIR / "main_window_light.png", size=16
        )
        ratio, total, different = compute_diff(baseline, baseline)
        self.assertEqual(ratio, 0.0)
        self.assertEqual(different, 0)
        self.assertGreater(total, 0)

    def test_compute_diff_detects_change(self):
        """两张差异显著的图 → ratio > 0。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            red_path = _make_solid_png(tmp_dir / "red.png", (255, 0, 0, 255))
            blue_path = _make_solid_png(tmp_dir / "blue.png", (0, 0, 255, 255))
            ratio, total, different = compute_diff(red_path, blue_path)
            self.assertGreater(ratio, 0.0)
            self.assertGreater(different, 0)
            self.assertEqual(total, 16 * 16)

    def test_compute_diff_size_mismatch_raises(self):
        """尺寸不同的两张图必须显式抛 ValueError,不静默。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            small = _make_solid_png(tmp_dir / "small.png", (255, 0, 0, 255), size=8)
            big = _make_solid_png(tmp_dir / "big.png", (0, 0, 255, 255), size=32)
            with self.assertRaises(ValueError):
                compute_diff(small, big)

    def test_threshold_default(self):
        """THRESHOLD 默认值必须为 0.005,作为后续 diff 上限判定。"""
        self.assertEqual(THRESHOLD, 0.005)


class TestCompareModuleExports(unittest.TestCase):

    def test_module_has_compute_diff(self):
        """compute_diff 必须可从 baselines.compare 直接导入。"""
        self.assertTrue(callable(compare.compute_diff))

    def test_module_all_contains_compute_diff(self):
        """__all__ 必须导出 compute_diff 与 THRESHOLD。"""
        self.assertIn("compute_diff", compare.__all__)
        self.assertIn("THRESHOLD", compare.__all__)


if __name__ == "__main__":
    unittest.main()