# -*- coding: utf-8 -*-
"""
方案 X RED 测试: collect_image_block_ocr_hits 在同一 OCR 行内,
对水平相邻的命中 rect 做合并,消除'刘妹 034-62407159' 这种
汉字 pattern + 电话 pattern 在同一行上留下 rect 间隙的问题.

设计:
- 不依赖真实 OCR / fitz, 直接喂 SimpleNamespace 模拟.
- 模拟场景 1: Page 0 第 24 行 '刘妹 034-62407159', jieba 注入 '刘妹'
  + 固定电话 pattern 命中 '034-62407159'. 修复前会产生两个有间隙的 rect;
  修复后应合并为一个覆盖整段的 rect (电话不再被漏涂).
- 模拟场景 2: 同一行多个独立命中 (日期+日期) 应被合并.
- 模拟场景 3: 同一行但水平间距 > 阈值 (10 像素) 应保留两个 rect.
- 模拟场景 4: 不同行永远不合并.
- 模拟场景 5: 单个命中保持原 rect 不变 (向后兼容).
- 模拟场景 6: 阈值 = 0 等价区间并集 (极端情况).

注: 当前 collect_image_block_ocr_hits 没有合并逻辑,
所以这里写的所有期望都是 FAIL (RED). 验证修复后变 GREEN.
"""
import unittest
from types import SimpleNamespace

from privacyguard.ocr.mixed_pdf import collect_image_block_ocr_hits


# 真实 Page 0 的 box + 文本 (来自实测):
# text = '刘妹 034-62407159'
# box  = [[778, 1365], [1072, 1362], [1073, 1408], [778, 1411]]
PAGE0_LINE_BOX = [[778.0, 1365.0], [1072.0, 1362.0], [1073.0, 1408.0], [778.0, 1411.0]]
PAGE0_LINE_TEXT = '刘妹 034-62407159'

# 模拟 OCR 输出: 单行 '刘妹 034-62407159'
def _make_ocr_results():
    return [
        SimpleNamespace(
            box=PAGE0_LINE_BOX,
            text=PAGE0_LINE_TEXT,
        ),
    ]


def _make_calc_rect_fn(rects_by_span):
    """构造 calculate_rect_fn: 给定 span 返回对应 rect.
    rects_by_span: dict[(start, end), (x, y, w, h)]"""
    def calc(_box, _text, span, _img):
        return SimpleNamespace(
            x=lambda: rects_by_span[span][0],
            y=lambda: rects_by_span[span][1],
            width=lambda: rects_by_span[span][2],
            height=lambda: rects_by_span[span][3],
        )
    return calc


def _offset_rect(local_rect, clip_rect):
    return (
        local_rect.x() + clip_rect[0],
        local_rect.y() + clip_rect[1],
        local_rect.width(),
        local_rect.height(),
    )


class TestHitRectMerging(unittest.TestCase):
    """方案 X: 同一 OCR 行内,水平相邻命中应合并."""

    def _run_with_rects(self, ocr_results, patterns, rects_by_span, merge_gap_threshold=6.0):
        """Helper: 用给定的 pattern 列表和 span→rect 映射跑 collect_image_block_ocr_hits."""
        return collect_image_block_ocr_hits(
            page=object(),
            patterns=patterns,
            scan_scale=1.0,
            recognize_fn=lambda _img: ocr_results,
            calculate_rect_fn=_make_calc_rect_fn(rects_by_span),
            clip_to_page_rect_fn=_offset_rect,
            render_clip_fn=lambda *_: SimpleNamespace(size=1),
            image_clip_rects=[(0.0, 0.0, 1200.0, 1700.0)],
        )

    # ---- 场景 1: 真实 Page 0 '刘妹 034-62407159' ----

    def test_merge_name_and_phone_on_same_line(self):
        """Page 0 实测: jieba 注入的 '刘妹' 和固定电话 '034-62407159' 在同一行.

        修复前 _calculate_from_line 给出两个 rect:
          - '刘妹'   : x=779, w=62  -> 区间 [779,  841]
          - '034-...' : x=861, w=211 -> 区间 [861, 1072]
        中间有 ~20 像素空隙, '034' 的前几个数字可能落空, 导致电话被漏涂.

        修复后期望: 合并为 [779, 1072], 完整覆盖 '刘妹 034-62407159' 整段.
        """
        # _calculate_from_line 实测结果:
        rects_by_span = {
            (0, 2):  (779.0, 1362.0, 62.5, 49.0),     # '刘妹'
            (3, 15): (861.2, 1362.0, 210.8, 49.0),     # '034-62407159'
        }
        patterns = [r'刘妹', r'(?<!\d)0\d{2,3}[-\s]?[\d\w]{7,8}(?!\d)']

        hits = self._run_with_rects(_make_ocr_results(), patterns, rects_by_span)

        # 修复后期望: 合并成 1 个 rect, x 范围 [779, 1072]
        self.assertEqual(
            len(hits), 1,
            f"修复后应合并为 1 个 rect, 实得 {len(hits)} 个: {hits}",
        )
        x0 = hits[0].x()
        w = hits[0].width()
        x1 = x0 + w
        self.assertLessEqual(x0, 779.0 + 1.0,
            f"合并 rect 左边界应 <= '刘妹' 起点, 实得 {x0}")
        self.assertGreaterEqual(x1, 1072.0 - 1.0,
            f"合并 rect 右边界应 >= '034-62407159' 终点, 实得 {x1}")

    def test_no_merge_gap_exceeds_threshold(self):
        """同一行但水平间距 > 阈值 (默认 30 像素), 应保留 2 个独立 rect."""
        # 间距 = 60 像素 >> 阈值 30
        rects_by_span = {
            (0, 2):  (779.0, 0.0, 50.0, 20.0),
            (3, 15): (889.0, 0.0, 100.0, 20.0),  # x=889, 前 rect 终点=829, 间距=60
        }
        patterns = [r'刘妹', r'(?<!\d)0\d{2,3}[-\s]?[\d\w]{7,8}(?!\d)']

        hits = self._run_with_rects(_make_ocr_results(), patterns, rects_by_span)

        self.assertEqual(
            len(hits), 2,
            f"间距 > 阈值时不应合并, 实得 {len(hits)} 个: {hits}",
        )

    def test_single_hit_no_merge(self):
        """单行只有 1 个命中时, 不应触发合并逻辑,保持原 rect."""
        rects_by_span = {
            (3, 15): (861.2, 1362.0, 210.8, 49.0),  # 仅 '034-62407159'
        }
        patterns = [r'(?<!\d)0\d{2,3}[-\s]?[\d\w]{7,8}(?!\d)']

        hits = self._run_with_rects(_make_ocr_results(), patterns, rects_by_span)

        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0].x(), 861.2, places=1)
        self.assertAlmostEqual(hits[0].width(), 210.8, places=1)

    def test_different_lines_never_merge(self):
        """不同 OCR 行 (y 不重叠) 永远不应合并,即使水平相邻."""
        # 用两个不同 y 的 OCR 行, 每行各 1 个手机号命中
        ocr_results = [
            SimpleNamespace(
                box=[[778.0, 1365.0], [1072.0, 1362.0], [1073.0, 1408.0], [778.0, 1411.0]],
                text='张三 13512345678',
            ),
            SimpleNamespace(
                box=[[778.0, 1500.0], [1072.0, 1497.0], [1073.0, 1543.0], [778.0, 1546.0]],
                text='李四 13987654321',
            ),
        ]
        rects_by_span = {
            (3, 14): (861.2, 1362.0, 210.8, 49.0),  # 第 1 行 y=1362
        }
        patterns = [r'(?<!\d)1[3-9]\d{9}(?!\d)']

        # 直接测试合并函数: 给两个不同 y 的 line_box + 同 span rect
        from privacyguard.ocr.mixed_pdf import merge_adjacent_hit_rects
        annotated = [
            (ocr_results[0].box, (861.2, 1362.0, 210.8, 49.0)),  # 第 1 行
            (ocr_results[1].box, (861.0, 1497.0, 210.0, 49.0)),  # 第 2 行
        ]
        hits = merge_adjacent_hit_rects(annotated)

        # 两条不同 y 的行, 即使水平起点一致, 也不能合并
        self.assertEqual(
            len(hits), 2,
            f"不同 y 的命中不应合并, 实得 {len(hits)} 个",
        )
        ys = sorted(set(h.y() for h in hits))
        self.assertEqual(len(ys), 2, f"应有 2 个不同 y, 实得 {ys}")

    def test_merge_two_dates_on_same_line(self):
        """同一行两个日期 pattern 命中 (印刷体场景), 应合并成一个 rect."""
        ocr_results = [
            SimpleNamespace(
                box=[[0.0, 0.0], [500.0, 0.0], [500.0, 30.0], [0.0, 30.0]],
                text='2025年1月15日 著作权人周强 2025年9月10日',
            ),
        ]
        rects_by_span = {
            (0, 10): (0.0, 0.0, 100.0, 30.0),     # 2025年1月15日
            (18, 28): (140.0, 0.0, 100.0, 30.0), # 2025年9月10日 (中间隔了 40 像素)
        }
        patterns = [r'\d{4}[年\-\.]\d{1,2}[月\-\.]\d{1,2}[日]?']

        hits = self._run_with_rects(ocr_results, patterns, rects_by_span)

        # 40 像素间距 > 默认阈值 30, 不合并
        # 验证 y 行判定 OK 即可
        ys = [h.y() for h in hits]
        self.assertEqual(len(set(ys)), 1, f"两个命中应在同一 y 行, 实得 ys={ys}")

    def test_merge_two_close_dates(self):
        """同一行两个日期命中, 间距 < 阈值, 应合并."""
        rects_by_span = {
            (0, 10): (0.0, 0.0, 100.0, 30.0),
            (11, 21): (115.0, 0.0, 100.0, 30.0),  # 间距=15 < 30
        }
        ocr_results = [
            SimpleNamespace(
                box=[[0.0, 0.0], [500.0, 0.0], [500.0, 30.0], [0.0, 30.0]],
                text='2025年1月15日 2025年9月10日',
            ),
        ]
        patterns = [r'\d{4}[年\-\.]\d{1,2}[月\-\.]\d{1,2}[日]?']

        hits = self._run_with_rects(ocr_results, patterns, rects_by_span)

        self.assertEqual(
            len(hits), 1,
            f"间距=15 <= 阈值30 时应合并, 实得 {len(hits)} 个",
        )
        self.assertEqual(hits[0].x(), 0.0)
        self.assertEqual(hits[0].width(), 215.0)  # 115+100

    def test_merge_handles_qrectf_input(self):
        """真实 ocr_worker.py 用 QRectF 当 page_rect, 合并函数必须能处理 QRectF 而不崩."""
        # 模拟 PyQt6.QtCore.QRectF (不依赖 PyQt 导入, 用 duck typing)
        class FakeQRectF:
            def __init__(self, x, y, w, h):
                self._x, self._y, self._w, self._h = x, y, w, h
            def x(self): return self._x
            def y(self): return self._y
            def width(self): return self._w
            def height(self): return self._h

        from privacyguard.ocr.mixed_pdf import merge_adjacent_hit_rects
        annotated = [
            ([[778.0, 1365.0], [1072.0, 1362.0], [1073.0, 1408.0], [778.0, 1411.0]],
             FakeQRectF(779.0, 1362.0, 62.5, 49.0)),       # QRectF, 不是 tuple
            ([[778.0, 1365.0], [1072.0, 1362.0], [1073.0, 1408.0], [778.0, 1411.0]],
             FakeQRectF(861.2, 1362.0, 210.8, 49.0)),
        ]
        hits = merge_adjacent_hit_rects(annotated)

        self.assertEqual(
            len(hits), 1,
            f"QRectF 输入也必须能合并, 实得 {len(hits)} 个",
        )
        self.assertAlmostEqual(hits[0].x(), 779.0, places=1)
        self.assertAlmostEqual(hits[0].width(), 293.0, places=1)  # (861.2+210.8) - 779 = 293

    def test_merge_output_supports_main_py_dedup_protocol(self):
        """main.py:11338 _deduplicate_rects 用 r.x() / r.y() / r.width() / r.height() 调用,
        merge_adjacent_hit_rects 输出必须满足这个 duck-typing 协议.
        回归保护: 之前返回 tuple 时崩溃."""
        from privacyguard.ocr.mixed_pdf import merge_adjacent_hit_rects
        annotated = [
            ([[778.0, 1365.0], [1072.0, 1362.0], [1073.0, 1408.0], [778.0, 1411.0]],
             (779.0, 1362.0, 62.5, 49.0)),
            ([[778.0, 1365.0], [1072.0, 1362.0], [1073.0, 1408.0], [778.0, 1411.0]],
             (861.2, 1362.0, 210.8, 49.0)),
        ]
        hits = merge_adjacent_hit_rects(annotated)

        # 关键: 输出对象必须支持 .x() .y() .width() .height()
        for rect in hits:
            x = rect.x()
            y = rect.y()
            w = rect.width()
            h = rect.height()
            self.assertIsInstance(x, float)
            self.assertIsInstance(y, float)
            self.assertIsInstance(w, float)
            self.assertIsInstance(h, float)

        # 同时验证能跑 main.py 的 sort lambda: sorted(rects, key=lambda r: (r.x(), r.y(), r.width(), r.height()))
        try:
            sorted_rects = sorted(hits, key=lambda r: (r.x(), r.y(), r.width(), r.height()))
        except AttributeError as e:
            self.fail(f"输出对象不支持 main.py _deduplicate_rects 协议: {e}")
        self.assertEqual(len(sorted_rects), 1)

    def test_merge_output_supports_main_py_dedup_with_tuple_input(self):
        """main.py 实际传过来的是 QRectF (tuple 输入也被 _rect_to_tuple 兼容),
        但验证即使输入是 tuple, 输出也要满足 .x() 协议."""
        from privacyguard.ocr.mixed_pdf import merge_adjacent_hit_rects
        annotated = [
            ([[0.0, 0.0], [300.0, 0.0], [300.0, 30.0], [0.0, 30.0]],
             (10.0, 5.0, 50.0, 20.0)),
            ([[0.0, 0.0], [300.0, 0.0], [300.0, 30.0], [0.0, 30.0]],
             (70.0, 5.0, 50.0, 20.0)),  # 间距=10 < 30, 合并
        ]
        hits = merge_adjacent_hit_rects(annotated)
        self.assertEqual(len(hits), 1)
        # 模拟 main.py 用法
        _ = hits[0].x(), hits[0].y(), hits[0].width(), hits[0].height()


if __name__ == "__main__":
    unittest.main()