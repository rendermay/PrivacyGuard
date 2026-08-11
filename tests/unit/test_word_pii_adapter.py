"""Phase 3 (03-word) — word_adapter 三函数 + 懒加载纪律测试（D-11 / D-13 / OPS-03）。

D-05 / D-08 / D-09 / D-11 锁定:
- `collect_pii_word_hits(paragraph_text, engine)` 复用 PIIEngine.detect (D-11 引擎层无 IO)
- `locate_pii_hits_in_paragraph(hits, paragraph_text)` 用 paragraph_text.find(needle, start)
  顺序扫描, 同文本重复逐个展开 (D-08 + D-09)
- `apply_pii_replacements_to_docx(doc, hit_locations, mode="partial"|"blackout")` 不
  import python-docx: 调用方持有 Document 句柄, partial 走 mask_for_entity, blackout 写 "[已脱敏]"。
  段级 paragraph.style.name 在 replace 前后保持不变 (D-07)
- 三函数经 _LAZY_IMPORTS 注册, from privacyguard.pii import X 触发 word_adapter 模块加载 (D-13 + OPS-03)
- word_adapter.py 源码不含 "from docx" / "import docx" 子串 (D-11 + T-03-02)
"""
import os
import sys
import tempfile
import unittest

from privacyguard.pii.engine import PIIEngine, TextUnit
from privacyguard.pii.word_adapter import (
    apply_pii_replacements_to_docx,
    collect_pii_word_hits,
    locate_pii_hits_in_paragraph,
)


# ----------------------------------------------------------------------
# Test 1: collect_pii_word_hits
# ----------------------------------------------------------------------
class TestCollectPiiWordHits(unittest.TestCase):
    """D-11: collect_pii_word_hits(paragraph_text, engine) -> List[PIIHit]
    复用 PIIEngine.detect 识别单段文本。
    """

    def test_empty_text_returns_empty_list(self):
        hits = collect_pii_word_hits("", PIIEngine())
        self.assertEqual(hits, [])

    def test_whitespace_only_text_returns_empty_list(self):
        hits = collect_pii_word_hits("   \n\t  ", PIIEngine())
        self.assertEqual(hits, [])

    def test_detects_id_card_in_paragraph(self):
        text = "测试 身份证 110101199001011234 后面"
        hits = collect_pii_word_hits(text, PIIEngine())
        self.assertGreater(len(hits), 0)
        # 第一条命中应为 18 位身份证 (CN_ID_CARD entity_type)
        entity_types = {h.entity_type for h in hits}
        self.assertIn("CN_ID_CARD", entity_types)

    def test_detects_multiple_entity_types(self):
        """多段混合身份证+手机号+邮箱返回多条按 entity 顺序命中。"""
        text = (
            "身份证 110101199001011234 "
            "电话 13812345678 "
            "邮箱 foo@qq.com"
        )
        hits = collect_pii_word_hits(text, PIIEngine())
        entity_types = {h.entity_type for h in hits}
        self.assertIn("CN_ID_CARD", entity_types)
        self.assertIn("CN_PHONE", entity_types)
        # 邮箱走公共域名后缀 path 应当命中 (REGEX 命中公共后缀 → 高置信度)
        self.assertTrue(
            any(h.entity_type == "CN_EMAIL" for h in hits),
            f"应在 hits 中包含至少一条 CN_EMAIL; actual entities: {entity_types}",
        )

    def test_returns_pii_hit_with_5_locked_fields(self):
        """D-05: PIIHit 字段锁; 返回的每个 hit 必须含 5 个必填字段。"""
        text = "测试 110101199001011234 文本"
        hits = collect_pii_word_hits(text, PIIEngine())
        if hits:
            hit = hits[0]
            for field in (
                "entity_type", "page_offset", "page_length",
                "page_rect", "confidence_tier",
            ):
                self.assertTrue(
                    hasattr(hit, field),
                    f"PIIHit 缺失字段 {field!r} (D-05 字段锁违反)",
                )


# ----------------------------------------------------------------------
# Test 2: locate_pii_hits_in_paragraph
# ----------------------------------------------------------------------
class TestLocatePiiHitsInParagraph(unittest.TestCase):
    """D-08 + D-09: locate_pii_hits_in_paragraph(hits, paragraph_text) -> [(PIIHit, offset)]
    paragraph_text.find(needle, start_offset) 顺序扫描; 同文本重复逐个展开。
    """

    def _make_hit(self, text):
        """构造一个 PIIHit (used for locate 测试, 不依赖收集路径)。"""
        from privacyguard.pii.hits import PIIHit
        return PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=0,
            page_length=len(text),
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="HIGH",
            source="text",
            mask_strategy=text[:6] + "*" * 8 + text[14:] if len(text) == 18 else "*" * len(text),
            normalized=text,
            validator_passed=True,
        )

    def test_locate_single_hit_returns_offset(self):
        """单一命中在 paragraph_text 中返回 (hit, offset) 偏移。"""
        text = "前面文本 110101199001011234 后面文本"
        needle = "110101199001011234"
        hit = self._make_hit(needle)
        locations = locate_pii_hits_in_paragraph([hit], text)
        self.assertEqual(len(locations), 1)
        # "前面文本" 是 4 个字符, 空格占 1 → offset = 5
        self.assertEqual(locations[0][1], text.find(needle))

    def test_locate_duplicate_text_expands_all_occurrences(self):
        """D-09: 同文本重复逐个展开为多个 (hit, offset) 元组。"""
        text = "110101199001011234 中间 110101199001011234 末尾"
        needle = "110101199001011234"
        hit = self._make_hit(needle)
        locations = locate_pii_hits_in_paragraph([hit], text)
        self.assertEqual(len(locations), 2)
        offsets = [off for _, off in locations]
        # 必须展开两次, 偏移分别为 0 和 (0 + 18 + 3) = 21
        self.assertEqual(offsets[0], 0)
        self.assertEqual(offsets[1], text.find(needle, 1))
        # 严格递增 (D-09 顺序展开)
        self.assertLess(offsets[0], offsets[1])

    def test_locate_three_duplicate_text_returns_three(self):
        """D-09: 同文本重复 3 次展开为 3 个独立 (hit, offset)。"""
        text = "X 110101Y 110101Z 110101W"
        needle = "110101"
        hit = self._make_hit(needle)
        locations = locate_pii_hits_in_paragraph([hit], text)
        self.assertEqual(len(locations), 3)
        offsets = [off for _, off in locations]
        self.assertEqual(offsets, [2, 9, 16])

    def test_locate_empty_hits_returns_empty(self):
        text = "some paragraph text"
        self.assertEqual(locate_pii_hits_in_paragraph([], text), [])

    def test_locate_empty_paragraph_text_returns_empty(self):
        hit = self._make_hit("110101")
        self.assertEqual(locate_pii_hits_in_paragraph([hit], ""), [])

    def test_locate_not_found_returns_empty_for_that_hit(self):
        """needle 不在 paragraph_text 中 → 不入 locations (但不抛错)。"""
        text = "some paragraph without needle"
        hit = self._make_hit("110101199001011234")
        self.assertEqual(locate_pii_hits_in_paragraph([hit], text), [])


# ----------------------------------------------------------------------
# Test 3: apply_pii_replacements_to_docx
# ----------------------------------------------------------------------
class TestApplyPiiReplacementsToDocx(unittest.TestCase):
    """D-06 + D-07: apply_pii_replacements_to_docx(doc, hit_locations, mode)
    partial 走 mask_for_entity, blackout 写 "[已脱敏]"; 段级 style.name 在 replace 前后不变。
    """

    def _make_doc_with_paragraph(self, text: str, style_name: str = "Normal"):
        """构造一个含单段 (指定 style) 的 docx Document。"""
        from docx import Document
        from docx.shared import Pt
        doc = Document()
        p = doc.add_paragraph(text)
        # 设置非默认 style 验证 D-07 段级样式保留
        if style_name != "Normal":
            try:
                p.style = doc.styles[style_name]
            except KeyError:
                pass
        return doc

    def test_redacted_paragraph_loses_original_secret(self):
        """partial mode 真脱敏: 段内不再含原始敏感字符串。"""
        secret = "110101199001011234"
        doc = self._make_doc_with_paragraph(f"测试样本 身份证 {secret} 后面文本")
        text = doc.paragraphs[0].text
        hit = self._make_hit(secret)
        from privacyguard.pii.hits import PIIHit
        hit_obj = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=text.find(secret),
            page_length=len(secret),
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="HIGH",
            source="text",
            mask_strategy="110101********1234",
            normalized=secret,
            validator_passed=True,
        )
        apply_pii_replacements_to_docx(doc, {"paragraph_0": [(hit_obj, text.find(secret))]}, mode="partial")
        new_text = doc.paragraphs[0].text
        self.assertNotIn(secret, new_text)

    def test_partial_mode_writes_mask_text(self):
        """partial mode 产物含 mask 字符串 ('********')。"""
        secret = "110101199001011234"
        doc = self._make_doc_with_paragraph(f"身份证 {secret}")
        text = doc.paragraphs[0].text
        from privacyguard.pii.hits import PIIHit
        hit = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=text.find(secret),
            page_length=len(secret),
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="HIGH",
            source="text",
            mask_strategy="110101********1234",
            normalized=secret,
            validator_passed=True,
        )
        apply_pii_replacements_to_docx(doc, {"paragraph_0": [(hit, text.find(secret))]}, mode="partial")
        new_text = doc.paragraphs[0].text
        self.assertIn("110101********1234", new_text)

    def test_blackout_mode_writes_brackets(self):
        """blackout mode 产物含 '[已脱敏]'。"""
        secret = "13812345678"
        doc = self._make_doc_with_paragraph(f"电话 {secret}")
        text = doc.paragraphs[0].text
        from privacyguard.pii.hits import PIIHit
        hit = PIIHit(
            entity_type="CN_PHONE",
            page_offset=text.find(secret),
            page_length=len(secret),
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="HIGH",
            source="text",
            mask_strategy="138****5678",
            normalized=secret,
            validator_passed=True,
        )
        apply_pii_replacements_to_docx(doc, {"paragraph_0": [(hit, text.find(secret))]}, mode="blackout")
        new_text = doc.paragraphs[0].text
        self.assertIn("[已脱敏]", new_text)
        self.assertNotIn(secret, new_text)

    def test_paragraph_style_preserved_after_replace(self):
        """D-07: 段级 paragraph.style.name 在 replace 前后不变。"""
        from docx import Document
        doc = Document()
        p = doc.add_paragraph("测试 110101199001011234 文本")
        original_style = p.style.name
        text = p.text
        from privacyguard.pii.hits import PIIHit
        hit = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=text.find("110101199001011234"),
            page_length=18,
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="HIGH",
            source="text",
            mask_strategy="110101********1234",
            normalized="110101199001011234",
            validator_passed=True,
        )
        apply_pii_replacements_to_docx(
            doc,
            {"paragraph_0": [(hit, text.find("110101199001011234"))]},
            mode="partial",
        )
        self.assertEqual(doc.paragraphs[0].style.name, original_style)

    def test_replace_across_runs_replaces_full_substring(self):
        """跨 run 命中 (run0='110101' + run1='199001011234') replace 后段内不再含子串。

        注意: D-07 允许段级样式保留 + run 级格式丢失; 这里仅断言子串消失。
        """
        from docx import Document
        doc = Document()
        p = doc.add_paragraph()
        # 故意拆成两个 run, 模拟 Word 文档的复杂结构
        run0 = p.add_run("前缀 110101")
        run1 = p.add_run("199001011234 末尾")
        text = p.text
        full_needle = "110101199001011234"
        from privacyguard.pii.hits import PIIHit
        hit = PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=text.find(full_needle),
            page_length=len(full_needle),
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="HIGH",
            source="text",
            mask_strategy="110101********1234",
            normalized=full_needle,
            validator_passed=True,
        )
        apply_pii_replacements_to_docx(
            doc,
            {"paragraph_0": [(hit, text.find(full_needle))]},
            mode="partial",
        )
        new_text = doc.paragraphs[0].text
        self.assertNotIn(full_needle, new_text)

    def test_no_hits_for_key_skips_paragraph(self):
        """hit_locations 中无对应 key 时, paragraph 原样保留。"""
        from docx import Document
        doc = Document()
        doc.add_paragraph("原文 110101199001011234 文本")
        original_text = doc.paragraphs[0].text
        apply_pii_replacements_to_docx(doc, {"paragraph_NONE": []}, mode="partial")
        self.assertEqual(doc.paragraphs[0].text, original_text)

    def test_round_trip_through_disk_does_not_leak_secret(self):
        """完整 reverse-extraction: 写入磁盘 → 重新读取 → 断言敏感字符串不存在。"""
        from docx import Document
        secret = "110101199001011234"
        doc = Document()
        doc.add_paragraph(f"前缀 {secret} 后缀")
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "in.docx")
            doc.save(in_path)
            doc2 = Document(in_path)
            text = doc2.paragraphs[0].text
            from privacyguard.pii.hits import PIIHit
            hit = PIIHit(
                entity_type="CN_ID_CARD",
                page_offset=text.find(secret),
                page_length=len(secret),
                page_rect=(0.0, 0.0, 0.0, 0.0),
                confidence_tier="HIGH",
                source="text",
                mask_strategy="110101********1234",
                normalized=secret,
                validator_passed=True,
            )
            apply_pii_replacements_to_docx(
                doc2,
                {"paragraph_0": [(hit, text.find(secret))]},
                mode="partial",
            )
            out_path = os.path.join(tmp, "out.docx")
            doc2.save(out_path)
            doc3 = Document(out_path)
            out_text = doc3.paragraphs[0].text
            self.assertNotIn(secret, out_text)

    def _make_hit(self, text):
        from privacyguard.pii.hits import PIIHit
        return PIIHit(
            entity_type="CN_ID_CARD",
            page_offset=0,
            page_length=len(text),
            page_rect=(0.0, 0.0, 0.0, 0.0),
            confidence_tier="HIGH",
            source="text",
            mask_strategy=text[:6] + "*" * 8 + text[14:] if len(text) == 18 else "*" * len(text),
            normalized=text,
            validator_passed=True,
        )


# ----------------------------------------------------------------------
# Test 4: Importability — 懒加载纪律 (OPS-03 / D-13)
# ----------------------------------------------------------------------
class TestWordAdapterImportability(unittest.TestCase):
    """OPS-03 懒加载纪律: from privacyguard.pii import X 触发 word_adapter 模块加载;

    word_adapter.py 源码不含 'from docx' / 'import docx' 子串 (D-11 + T-03-02)。
    """

    def _snapshot_privacyguard_modules(self):
        return {
            name: module
            for name, module in list(sys.modules.items())
            if name == "privacyguard" or name.startswith("privacyguard.")
        }

    def _restore_privacyguard_modules(self, cached):
        for name in list(sys.modules):
            if name == "privacyguard" or name.startswith("privacyguard."):
                sys.modules.pop(name, None)
        sys.modules.update(cached)

    def test_collect_pii_word_hits_triggers_word_adapter_loaded(self):
        """D-13: from privacyguard.pii import collect_pii_word_hits 触发 word_adapter 模块加载。"""
        import importlib
        cached = self._snapshot_privacyguard_modules()
        for name in list(cached):
            sys.modules.pop(name, None)
        try:
            module = importlib.import_module("privacyguard")
            self.assertNotIn(
                "privacyguard.pii.word_adapter", sys.modules,
                "import privacyguard 不应触发 privacyguard.pii.word_adapter (OPS-03)",
            )
            _ = module.collect_pii_word_hits
            self.assertIn(
                "privacyguard.pii.word_adapter", sys.modules,
                "访问 collect_pii_word_hits 后 word_adapter 应被加载 (D-13 _LAZY_IMPORTS)",
            )
        finally:
            self._restore_privacyguard_modules(cached)

    def test_locate_pii_hits_in_paragraph_triggers_word_adapter_loaded(self):
        """D-13: locate_pii_hits_in_paragraph 触发 word_adapter 懒加载。"""
        import importlib
        cached = self._snapshot_privacyguard_modules()
        for name in list(cached):
            sys.modules.pop(name, None)
        try:
            module = importlib.import_module("privacyguard")
            self.assertNotIn("privacyguard.pii.word_adapter", sys.modules)
            _ = module.locate_pii_hits_in_paragraph
            self.assertIn(
                "privacyguard.pii.word_adapter", sys.modules,
                "访问 locate_pii_hits_in_paragraph 后 word_adapter 应被加载",
            )
        finally:
            self._restore_privacyguard_modules(cached)

    def test_apply_pii_replacements_to_docx_triggers_word_adapter_loaded(self):
        """D-13: apply_pii_replacements_to_docx 触发 word_adapter 懒加载。"""
        import importlib
        cached = self._snapshot_privacyguard_modules()
        for name in list(cached):
            sys.modules.pop(name, None)
        try:
            module = importlib.import_module("privacyguard")
            self.assertNotIn("privacyguard.pii.word_adapter", sys.modules)
            _ = module.apply_pii_replacements_to_docx
            self.assertIn(
                "privacyguard.pii.word_adapter", sys.modules,
                "访问 apply_pii_replacements_to_docx 后 word_adapter 应被加载",
            )
        finally:
            self._restore_privacyguard_modules(cached)

    def test_word_adapter_source_does_not_import_docx(self):
        """D-11 + T-03-02: word_adapter.py 源码不含 'from docx' / 'import docx'。"""
        from pathlib import Path
        word_adapter_path = (
            Path(__file__).resolve().parents[2]
            / "privacyguard" / "pii" / "word_adapter.py"
        )
        # 文件可能尚未存在 (RED 阶段), 此时先跳过; 但若存在, 必须无 docx import
        if not word_adapter_path.exists():
            self.skipTest(
                "privacyguard/pii/word_adapter.py 不存在; Task 2 GREEN 后此检查生效"
            )
        source = word_adapter_path.read_text(encoding="utf-8")
        for forbidden in ("from docx import", "import docx"):
            self.assertNotIn(
                forbidden, source,
                f"word_adapter.py 不应含 '{forbidden}' (D-11: PII 引擎无 IO)",
            )


if __name__ == "__main__":
    unittest.main()
