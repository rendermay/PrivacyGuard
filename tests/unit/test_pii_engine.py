"""Phase 1 PII 引擎单元测试（ENGINE-01..07 覆盖率 + 根因修复测试）。

覆盖矩阵：
- ENGINE-01 自动扫描全文输出候选
- ENGINE-02 PIIHit 字段顺序与 dataclass 契约（D-05）
- ENGINE-03 HIGH / MEDIUM / LOW 三档置信度
- ENGINE-04 同一实体多次出现产生一致掩码
- ENGINE-05 全角 → 半角 + offset 回算
- ENGINE-06 跨行 / 跨空白边界识别
- ENGINE-07 200KB 输入不阻塞

B2 separator-bearing input: 引擎文字层路径需对 page 调用 search_for 取真实坐标。
W-A: 不可定位的命中记录在 unresolved_hits + error_log，不静默丢弃。
"""
import inspect
import time
import unittest
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

from privacyguard.pii.confidence import classify_hit
from privacyguard.pii.engine import PIIEngine
from privacyguard.pii.hits import PIIHit, TextUnit
from privacyguard.pii.mask import (
    mask_for_entity,
    partial_mask_id_card,
    partial_mask_phone,
)
from privacyguard.pii.normalize import (
    flatten_for_match,
    map_flat_to_original,
    normalize_digits,
)
from privacyguard.pii.overlap import resolve as resolve_overlap


# 标准样本
_GB_STD_18 = "53010219200508011X"


# ----------------------------------------------------------------------
# FakePage — 模拟 PyMuPDF Page.search_for
# ----------------------------------------------------------------------
class FakePage:
    """B2 测试用：记录 search_for 调用 + 返回预设 rects。"""

    def __init__(self, rects_by_text=None, default_rects=None):
        self.search_calls = []
        self._rects_by_text = rects_by_text or {}
        self._default_rects = default_rects or []

    def search_for(self, text):
        self.search_calls.append(text)
        if text in self._rects_by_text:
            rects = self._rects_by_text[text]
        else:
            rects = self._default_rects
        return list(rects)


def _rect(x0, y0, x1, y1):
    return SimpleNamespace(x0=x0, y0=y0, x1=x1, y1=y1,
                           width=x1 - x0, height=y1 - y0)


# ----------------------------------------------------------------------
# ENGINE-02: PIIHit schema
# ----------------------------------------------------------------------
class TestPIIHitSchema(unittest.TestCase):
    """D-05: PIIHit 字段顺序锁定 + frozen + 默认值。"""

    def test_field_order_locked(self):
        sig = inspect.signature(PIIHit)
        field_names = list(sig.parameters.keys())
        # D-05: 前 7 个字段名 + 顺序锁定；parameters.keys() 在 Python 3.12 上是
        # MappingView 但 list() 后可与 list 比较
        self.assertEqual(
            field_names[:7],
            [
                "entity_type",
                "page_offset",
                "page_length",
                "page_rect",
                "confidence_tier",
                "source",
                "mask_strategy",
            ],
        )

    def test_default_confidence_tier_is_high(self):
        hit = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=0,
            page_length=18,
            page_rect=(0.0, 0.0, 18.0, 1.0),
        )
        self.assertEqual(hit.confidence_tier, "HIGH")

    def test_dataclass_is_frozen(self):
        hit = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=0,
            page_length=18,
            page_rect=(0.0, 0.0, 18.0, 1.0),
        )
        with self.assertRaises(FrozenInstanceError):
            hit.entity_type = "OTHER"  # type: ignore[misc]

    def test_page_rect_is_4_tuple(self):
        hit = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=0,
            page_length=18,
            page_rect=(0.0, 0.0, 18.0, 1.0),
        )
        self.assertEqual(len(hit.page_rect), 4)
        for v in hit.page_rect:
            self.assertIsInstance(v, float)


# ----------------------------------------------------------------------
# ENGINE-01: PIIEngine.detect 基础 + B2 separator + W-A unresolvable
# ----------------------------------------------------------------------
class TestEngineDetect(unittest.TestCase):
    """ENGINE-01: PIIEngine.detect 文字层路径全部命中分支。"""

    def setUp(self):
        self.engine = PIIEngine()

    def test_detects_valid_id_card(self):
        unit = TextUnit(page_index=0, text=f"张三 {_GB_STD_18} 已婚", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].entity_type, "CN_ID_CARD")
        self.assertTrue(hits[0].validator_passed)
        self.assertEqual(hits[0].confidence_tier, "HIGH")

    def test_detects_valid_phone(self):
        unit = TextUnit(page_index=0, text="联系 13812345678", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].entity_type, "CN_PHONE")

    def test_rejects_iot_phone(self):
        unit = TextUnit(page_index=0, text="设备 14012345678", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 0)

    def test_rejects_invalid_id_check_digit(self):
        unit = TextUnit(page_index=0, text="bad 530102192005080119 here", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 0)

    def test_detects_15_digit_via_upgrade(self):
        """15 位升级通过 B1 双门 + I1 demotion（无 context anchor → MEDIUM）。"""
        unit = TextUnit(page_index=0, text="old 420106690901234 here", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].entity_type, "CN_ID_CARD")
        # I1: bare 15-digit without context anchor → MEDIUM
        self.assertEqual(hits[0].confidence_tier, "MEDIUM")

    def test_detects_15_digit_with_context_anchor(self):
        """15 位升级通过 B1 双门 + context anchor 保留 HIGH。"""
        unit = TextUnit(
            page_index=0,
            text="身份证号 420106690901234 已确认",
            source="text",
        )
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 1)
        # 包含"身份证号"锚点 → 不降级
        self.assertEqual(hits[0].confidence_tier, "HIGH")

    def test_empty_text_returns_no_hits(self):
        unit = TextUnit(page_index=0, text="", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 0)

    def test_whitespace_only_returns_no_hits(self):
        unit = TextUnit(page_index=0, text="   \n\t  ", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 0)

    # ---------- B2: separator-bearing input tests ----------

    def test_separated_id_card_recognized(self):
        """B2: 文字层含分隔符的 ID 卡需以原始 substring 调 page.search_for。

        真实 rect 必须非占位（width × height > 0），且 search_for 收到原始 substring。
        使用手工计算的正确校验位 ID "110101199003078814"。
        """
        page = FakePage(rects_by_text={
            "110101-19900307-8814": [_rect(50.0, 100.0, 200.0, 115.0)],
        })
        engine = PIIEngine()
        unit = TextUnit(
            page_index=0,
            text="订单 110101-19900307-8814 备注",
            source="text",
        )
        hits = engine.detect(unit, page=page)
        self.assertEqual(len(hits), 1)
        self.assertEqual(page.search_calls, ["110101-19900307-8814"])
        x, y, w, h = hits[0].page_rect
        self.assertGreater(w * h, 0.0, "page_rect 必须非零面积")

    def test_fullwidth_digits_id_card_recognized(self):
        """B2: 全角数字 ID 卡 — search_for 收到原始全角 literal。"""
        page = FakePage(rects_by_text={
            "１１０１０１１９６７０３０７８８１１": [_rect(50.0, 100.0, 250.0, 115.0)],
        })
        engine = PIIEngine()
        unit = TextUnit(
            page_index=0,
            text="测试 １１０１０１１９６７０３０７８８１１ 备注",
            source="text",
        )
        hits = engine.detect(unit, page=page)
        self.assertEqual(len(hits), 1)
        # 引擎以原始 fullwidth literal 调用 page.search_for
        self.assertEqual(page.search_calls, ["１１０１０１１９６７０３０７８８１１"])

    def test_separator_split_fallback(self):
        """B2 fallback: 原始 substring 搜不到时按分隔符拆 chunk 并 union。

        chunks < 6 字符视为噪声跳过（避免误匹配序列号 "8814"）；
        本测试中 "110101" 与 "19900307" 都 >= 6 字符 → union bounding rect。
        """
        page = FakePage(rects_by_text={
            # 原始连字符形式搜索返回空（PyMuPDF 无法匹配跨连字符）
            "110101-19900307-8814": [],
            # chunked 形式可定位（仅 >= 6 字符会被实际搜索）
            "110101": [_rect(50.0, 100.0, 110.0, 115.0)],
            "19900307": [_rect(115.0, 100.0, 200.0, 115.0)],
            # "8814" < 6 字符（噪声阈值），不会被搜索
            "8814": [_rect(205.0, 100.0, 240.0, 115.0)],
        })
        engine = PIIEngine()
        unit = TextUnit(
            page_index=0,
            text="订单 110101-19900307-8814 备注",
            source="text",
        )
        hits = engine.detect(unit, page=page)
        self.assertEqual(len(hits), 1)
        # union rect (仅 110101 + 19900307): x0=50, y0=100, x1=200, y1=115
        x, y, w, h = hits[0].page_rect
        self.assertAlmostEqual(x, 50.0)
        self.assertAlmostEqual(y, 100.0)
        self.assertGreater(w * h, 0.0)
        self.assertAlmostEqual(w, 150.0)  # 200 - 50
        self.assertAlmostEqual(h, 15.0)   # 115 - 100

    def test_zero_area_rect_records_unresolved_not_emits(self):
        """W-A: 引擎 DETECTED 但 page 不可定位时记录 unresolved + log，不静默丢弃。"""
        page = FakePage(rects_by_text={})  # 所有 search_for 返回空
        engine = PIIEngine()
        unit = TextUnit(page_index=0, text=f"bad {_GB_STD_18} here", source="text")
        # 故意把 page_rect 设为占位 (0,0,0,0) 模拟退化 rect
        # 即使 GB 标准样本通过校验位，但 page.search_for 返回空 → 不可定位
        hits = engine.detect(unit, page=page)
        # 命中不在返回列表（避免发出零面积 rect）
        self.assertEqual(len(hits), 0)
        # 但 engine 必须记录它已检测到但未能定位
        self.assertEqual(len(engine.unresolved_hits), 1)
        self.assertIn(_GB_STD_18, engine.unresolved_hits[0].normalized)
        # error_log 至少包含一行 ("PII NO-RECT", page_idx, candidate)
        self.assertGreaterEqual(len(engine.error_log), 1)
        first_row = engine.error_log[0]
        self.assertEqual(first_row[0], "PII NO-RECT")
        self.assertEqual(first_row[1], 0)  # page_idx


# ----------------------------------------------------------------------
# ENGINE-03: confidence tier
# ----------------------------------------------------------------------
class TestConfidenceTiers(unittest.TestCase):
    """ENGINE-03: classify_hit 三档 + 边界。"""

    def test_high_when_validator_passes_and_regex_matches(self):
        self.assertEqual(classify_hit(True, True, "text"), "HIGH")

    def test_medium_when_regex_matches_but_validator_fails(self):
        self.assertEqual(classify_hit(False, True, "text"), "MEDIUM")

    def test_low_otherwise(self):
        self.assertEqual(classify_hit(False, False, "text"), "LOW")

    def test_classify_hit_branches(self):
        """覆盖所有 4 种 validator/regex 组合。"""
        cases = [
            (True, True, "HIGH"),
            (True, False, "LOW"),
            (False, True, "MEDIUM"),
            (False, False, "LOW"),
        ]
        for vp, rm, expected in cases:
            with self.subTest(validator_passed=vp, regex_matched=rm):
                self.assertEqual(classify_hit(vp, rm, "text"), expected)


# ----------------------------------------------------------------------
# ENGINE-04: 一致掩码缓存
# ----------------------------------------------------------------------
class TestMaskConsistency(unittest.TestCase):
    """ENGINE-04: 同一 normalized 实体在引擎内产出一致 mask。"""

    def test_same_normalized_yields_same_mask(self):
        engine = PIIEngine()
        unit = TextUnit(
            page_index=0,
            text="张三 13812345678 联系人 13812345678 备选 13812345678",
            source="text",
        )
        hits = engine.detect(unit)
        self.assertEqual(len(hits), 3)
        masks = {h.mask_strategy for h in hits}
        self.assertEqual(
            len(masks),
            1,
            f"3 个相同 normalized 应共享 1 个 mask，实际 {masks}",
        )

    def test_different_normalized_yields_different_mask(self):
        engine = PIIEngine()
        unit = TextUnit(
            page_index=0,
            text="A: 13812345678  B: 13912345678",
            source="text",
        )
        hits = engine.detect(unit)
        self.assertEqual(len(hits), 2)
        self.assertNotEqual(
            hits[0].mask_strategy,
            hits[1].mask_strategy,
        )


# ----------------------------------------------------------------------
# ENGINE-05 / ENGINE-06: normalize + flatten + map_flat_to_original
# ----------------------------------------------------------------------
class TestNormalization(unittest.TestCase):
    """ENGINE-05: 全角 → 半角 + 分隔符剥离。"""

    def test_fullwidth_digits_normalized_to_ascii(self):
        self.assertEqual(normalize_digits("１２３"), "123")

    def test_separators_stripped(self):
        self.assertEqual(normalize_digits("1-3 8 1 2 3 4 5 6 7 8"), "13812345678")

    def test_fullwidth_space_stripped(self):
        self.assertEqual(normalize_digits("138　12345678"), "13812345678")

    def test_flatten_strips_newlines(self):
        """ENGINE-06: 跨行拼接。"""
        self.assertEqual(flatten_for_match("110101\n19900307\n8811"), "110101199003078811")

    def test_flatten_strips_tabs(self):
        self.assertEqual(flatten_for_match("138\t12345678"), "13812345678")

    def test_map_flat_to_original_basic(self):
        """ENGINE-05: offset 回算 — flat = "13812345678"，span(3,7) 应回 "1234" 段。"""
        flat = "13812345678"
        original = "138 1234 5678"
        orig_span = map_flat_to_original(flat, (3, 7), original)
        self.assertIsNotNone(orig_span)
        orig_start, orig_end = orig_span  # type: ignore[misc]
        self.assertEqual(original[orig_start:orig_end], "1234")

    def test_map_flat_to_original_returns_none_when_unmappable(self):
        """防御: flat span 超出范围时返回 (None, None)。"""
        flat = "abc"
        original = "abc"
        # span 超出 flat 长度
        result = map_flat_to_original(flat, (10, 20), original)
        self.assertEqual(result, (None, None))


# ----------------------------------------------------------------------
# ENGINE-06: cross-boundary
# ----------------------------------------------------------------------
class TestCrossBoundary(unittest.TestCase):
    """ENGINE-06: 跨行 / 跨空白 ID 卡 / 手机号识别。"""

    def setUp(self):
        self.engine = PIIEngine()

    def test_id_card_across_newlines_recognized(self):
        # 使用 110101199003078814（手工计算的正确校验位 ID）跨换行
        unit = TextUnit(page_index=0, text="110101\n19900307\n8814", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].entity_type, "CN_ID_CARD")

    def test_phone_across_space_recognized(self):
        unit = TextUnit(page_index=0, text="联系 138 1234 5678", source="text")
        hits = self.engine.detect(unit)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].entity_type, "CN_PHONE")


# ----------------------------------------------------------------------
# ENGINE-07: 200KB 不阻塞
# ----------------------------------------------------------------------
class TestLargeDocumentNoBlock(unittest.TestCase):
    """ENGINE-07: 200KB 单页文本必须在 <1s 内完成 detect。"""

    def test_200kb_text_completes_quickly(self):
        engine = PIIEngine()
        # 构造 200KB 文本，含 3 个 ID 卡
        id1 = _GB_STD_18
        id2 = "110101199003078811"
        id3 = "44030719880101003X"
        filler = "测试噪声文本" * 18000  # ~200KB
        text = filler + f" {id1} 噪声 {id2} 噪声 {id3} " + filler
        self.assertGreater(len(text), 200_000)
        unit = TextUnit(page_index=0, text=text, source="text")
        start = time.perf_counter()
        hits = engine.detect(unit)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0, f"200KB detect 耗时 {elapsed:.3f}s 超过 1s")
        # 至少检测到 1 个 ID 卡
        id_hits = [h for h in hits if h.entity_type == "CN_ID_CARD"]
        self.assertGreaterEqual(len(id_hits), 1)

    def test_long_text_with_no_hits_returns_empty_quickly(self):
        engine = PIIEngine()
        filler = "测试噪声文本没有任何敏感信息" * 15000  # ~200KB
        self.assertGreater(len(filler), 200_000)
        unit = TextUnit(page_index=0, text=filler, source="text")
        start = time.perf_counter()
        hits = engine.detect(unit)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0, f"200KB 无命中 detect 耗时 {elapsed:.3f}s 超过 1s")
        self.assertEqual(len(hits), 0)


# ----------------------------------------------------------------------
# Mask 单元测试（partial_mask_* + mask_for_entity）
# ----------------------------------------------------------------------
class TestMaskStrategies(unittest.TestCase):
    """MASK-01 部分掩码：身份证前 6 后 4 / 手机前 3 后 4。"""

    def test_partial_mask_id_card_normal(self):
        self.assertEqual(
            partial_mask_id_card("110101199003078811"),
            "110101********8811",
        )

    def test_partial_mask_id_card_wrong_length_returns_all_asterisk(self):
        # 长度异常 → 全掩码
        self.assertEqual(partial_mask_id_card("123"), "***")

    def test_partial_mask_phone_normal(self):
        self.assertEqual(partial_mask_phone("13812345678"), "138****5678")

    def test_partial_mask_phone_wrong_length_returns_all_asterisk(self):
        self.assertEqual(partial_mask_phone("123"), "***")

    def test_mask_for_entity_dispatch(self):
        self.assertEqual(
            mask_for_entity("CN_ID_CARD", "110101199003078811"),
            "110101********8811",
        )
        self.assertEqual(
            mask_for_entity("CN_PHONE", "13812345678"),
            "138****5678",
        )
        self.assertEqual(
            mask_for_entity("UNKNOWN", "abcdef"),
            "******",
        )


# ----------------------------------------------------------------------
# Overlap dedup
# ----------------------------------------------------------------------
class TestOverlapDedup(unittest.TestCase):
    """overlap.resolve: 同位置保留 validator_passed=True 优先。"""

    def test_resolve_dedup_validator_passed_priority(self):
        h_passed = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=0,
            page_length=18,
            page_rect=(0.0, 0.0, 18.0, 1.0),
            normalized="53010219200508011X",
            validator_passed=True,
        )
        h_failed = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=0,
            page_length=18,
            page_rect=(0.0, 0.0, 18.0, 1.0),
            confidence_tier="MEDIUM",
            normalized="530102192005080119",
            validator_passed=False,
        )
        result = resolve_overlap([h_failed, h_passed])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].validator_passed)

    def test_resolve_sorts_by_offset(self):
        h1 = PIIHit(
            entity_type="CN_PHONE",
            page_offset=20,
            page_length=11,
            page_rect=(0.0, 0.0, 11.0, 1.0),
            normalized="13912345678",
        )
        h2 = PIIHit(
            entity_type="CN_PHONE",
            page_offset=5,
            page_length=11,
            page_rect=(0.0, 0.0, 11.0, 1.0),
            normalized="13812345678",
        )
        result = resolve_overlap([h1, h2])
        self.assertEqual(result[0].normalized, "13812345678")
        self.assertEqual(result[1].normalized, "13912345678")

    def test_resolve_empty(self):
        self.assertEqual(resolve_overlap([]), [])


# ----------------------------------------------------------------------
# Engine 防御性：未传 page 时仍工作（向后兼容）
# ----------------------------------------------------------------------
class TestEngineWithoutPage(unittest.TestCase):
    """detect(unit) 不传 page 时仍能跑（向后兼容测试）。

    page_rect 在 text-layer 路径退化为占位 (0, 0, len*6, 12)。
    """

    def test_detect_without_page_uses_placeholder(self):
        engine = PIIEngine()
        unit = TextUnit(page_index=0, text=f"测试 {_GB_STD_18} 样本", source="text")
        hits = engine.detect(unit)
        self.assertEqual(len(hits), 1)
        x, y, w, h = hits[0].page_rect
        # 占位 rect: (0, 0, len*6, 12)
        self.assertEqual(x, 0.0)
        self.assertEqual(y, 0.0)
        self.assertEqual(h, 12.0)
        self.assertGreater(w, 0.0)


# ----------------------------------------------------------------------
# 顶层包 lazy 导入烟雾测试（防止 _LAZY_IMPORTS 表被误删）
# ----------------------------------------------------------------------
class TestLazyExportSurface(unittest.TestCase):
    """OPS-03: 顶层 privacyguard 包的 PII 导出表必须稳定可访问。"""

    def test_top_level_lazy_exports_resolve(self):
        # 显式访问每个 _LAZY_IMPORTS 条目，确认不抛 AttributeError
        from privacyguard import (
            PIIEngine,
            PIIHit,
            TextUnit,
            validate_18_id,
            is_mobile_segment,
            apply_pii_redactions,
            collect_pii_rects,
        )
        self.assertTrue(callable(PIIEngine))
        self.assertTrue(callable(PIIHit))
        self.assertTrue(callable(TextUnit))
        self.assertTrue(callable(validate_18_id))
        self.assertTrue(callable(is_mobile_segment))
        self.assertTrue(callable(apply_pii_redactions))
        self.assertTrue(callable(collect_pii_rects))


# ----------------------------------------------------------------------
# Engine hardening: rules_version classmethod + last_error / error_log
# ----------------------------------------------------------------------
class TestEngineHardening(unittest.TestCase):
    """PIIEngine 类级硬化：rules_version + last_error + error_log + unresolved_hits。"""

    def test_rules_version_returns_unknown_when_empty(self):
        self.assertEqual(PIIEngine.rules_version({}), "unknown")

    def test_rules_version_returns_unknown_when_none(self):
        self.assertEqual(PIIEngine.rules_version(None), "unknown")

    def test_rules_version_reads_next_review(self):
        rules = {"phone_segment": {"next_review": "2026-Q3"}}
        self.assertEqual(PIIEngine.rules_version(rules), "2026-Q3")

    def test_rules_version_fallback_when_no_phone_segment(self):
        self.assertEqual(PIIEngine.rules_version({"id_card": {}}), "unknown")

    def test_engine_init_initializes_error_log_and_unresolved(self):
        engine = PIIEngine()
        self.assertIsNone(engine.last_error)
        self.assertEqual(engine.error_log, [])
        self.assertEqual(engine.unresolved_hits, [])

    def test_rules_version_default_constant(self):
        from privacyguard.pii import RULES_VERSION_DEFAULT
        self.assertEqual(RULES_VERSION_DEFAULT, "2026-Q1")


if __name__ == "__main__":
    unittest.main()
