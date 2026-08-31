# -*- coding: utf-8 -*-
"""WebViewBridge HitOverrideStore 槽函数测试.

Wave 3 Task 5:
- ignore_ocr_hit / confirm_ocr_hit / promote_override / revert_override
  桥接于 HitOverrideStore。
- handle_ocr_hit_contextmenu 把 QMenu 选中的动作转给上述槽。
- 解析 hit_id 失败时不应抛异常。

策略:
- fake bridge 直接构造(继承 WebViewBridge),绕过 main_window 初始化
- store 走 reset_singleton 隔离
"""
import unittest
from unittest.mock import MagicMock, patch

from secureredact.redaction.hit_ref import HitRef
from secureredact.redaction.override_store import HitOverrideStore


def _hit_id(doc_hash="a1b2c3d4", location="paragraph_0",
            start=2, end=4, source="jieba"):
    ref = HitRef(doc_hash, location, start, end, "周强", source)
    return ref.hit_id, ref


class _FakeBridge:
    """只用最近 4 个 bridge 槽;main_window 用 MagicMock 注入。"""

    def __init__(self, mock_mw):
        self.main_window = mock_mw
        # 把要测的 4 个槽函数注入 fake 实例
        from main import WebViewBridge
        # 复用真实方法的实现逻辑;绑定到 fake self
        self.ignore_ocr_hit = WebViewBridge.ignore_ocr_hit.__get__(self, type(self))
        self.confirm_ocr_hit = WebViewBridge.confirm_ocr_hit.__get__(self, type(self))
        self.promote_override = WebViewBridge.promote_override.__get__(self, type(self))
        self.revert_override = WebViewBridge.revert_override.__get__(self, type(self))
        # handle_ocr_hit_contextmenu 需要 QMenu,单独测


class BridgeOverrideSlotsTest(unittest.TestCase):

    def setUp(self):
        HitOverrideStore.reset_singleton()
        # fake main_window 持有真实 store 单例 + 必要的 callable
        self.mock_mw = MagicMock()
        self.mock_mw._override_store = HitOverrideStore.instance()
        # render_word_preview 必须真实可调用 — 设为 noop
        self.mock_mw.render_word_preview = MagicMock()
        self.bridge = _FakeBridge(self.mock_mw)

    def tearDown(self):
        HitOverrideStore.reset_singleton()

    def test_ignore_ocr_hit_marks_ignored(self):
        hit_id, _ref = _hit_id()
        self.bridge.ignore_ocr_hit(
            "paragraph_0", "jieba", "周强", hit_id,
        )
        # store 中应该有这条 ignore
        self.assertTrue(
            self.mock_mw._override_store.is_ignored(_ref),
            "ignore_ocr_hit 应在 store 写入 ignore",
        )
        # render_word_preview 应被触发一次
        self.mock_mw.render_word_preview.assert_called_once()

    def test_confirm_ocr_hit_marks_confirmed(self):
        hit_id, _ref = _hit_id(source="ocr")
        self.bridge.confirm_ocr_hit(
            "paragraph_0", "ocr", "周强", hit_id,
        )
        self.assertTrue(
            self.mock_mw._override_store.is_confirmed(_ref),
            "confirm_ocr_hit 应在 store 写入 confirm",
        )
        self.mock_mw.render_word_preview.assert_called_once()

    def test_promote_override_only_after_ignore_or_confirm(self):
        """promote 不存在 hit_id 时应是 noop,不应抛异常."""
        hit_id, _ref = _hit_id()
        # 未 ignore / confirm
        self.bridge.promote_override(hit_id)
        # store 中不应出现该 hit_id
        self.assertFalse(self.mock_mw._override_store.is_ignored(_ref))
        self.assertFalse(self.mock_mw._override_store.is_confirmed(_ref))

    def test_promote_override_after_ignore(self):
        hit_id, ref = _hit_id()
        self.mock_mw._override_store.ignore(ref, scope="session")
        self.bridge.promote_override(hit_id)
        permanent = [o for o in self.mock_mw._override_store.iter_overrides(scope="permanent")
                     if o.ref.hit_id == hit_id]
        self.assertEqual(len(permanent), 1,
            "promote_override 应把 session override 提到 permanent")
        self.assertEqual(permanent[0].action, "ignore")

    def test_revert_override_clears_state(self):
        hit_id, ref = _hit_id()
        store = self.mock_mw._override_store
        store.ignore(ref, scope="session")
        self.assertTrue(store.is_ignored(ref))
        self.bridge.revert_override(hit_id)
        self.assertFalse(store.is_ignored(ref),
            "revert_override 应从 store 删除该 override")
        self.mock_mw.render_word_preview.assert_called_once()

    def test_ignore_ocr_hit_corrupt_hit_id_does_not_raise(self):
        """未知 hit_id 容错:传入畸形 hit_id 不应抛异常;store 应保持空。"""
        # 正常 hit_id 形如 'a1b2c3d4|paragraph_0|2|4|jieba',5 段以 | 分隔
        # 这里只给 2 段 — 解析 HitRef 必然失败
        corrupt_hit_id = "broken|hit_id"
        try:
            self.bridge.ignore_ocr_hit(
                "paragraph_0", "jieba", "周强", corrupt_hit_id,
            )
        except Exception as exc:  # pragma: no cover - 失败信号
            self.fail(f"corrupt hit_id 不应抛异常: {exc}")
        # store 仍空,未记录 ignore
        self.assertEqual(
            len(list(self.mock_mw._override_store.iter_overrides())),
            0,
            "corrupt hit_id 不应在 store 写入任何 override",
        )
        # render_word_preview 不应被触发(因为解析失败早 return)
        self.mock_mw.render_word_preview.assert_not_called()


if __name__ == "__main__":
    unittest.main()
