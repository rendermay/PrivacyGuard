"""Phase 3 Word PII 扫描 QThread worker（D-09 自动触发）。"""
from dataclasses import asdict

from PyQt6.QtCore import QThread, pyqtSignal

from privacyguard.pii.hits import TextUnit


class WordPIIWorker(QThread):
    """Phase 3 Word PII 扫描 worker（D-09 自动触发）。

    Signals:
        pii_signal(str, list): emit (key, hits_dict_list) 每个 word_data key 完成扫描时
        finished_signal(): scan 完全完成时
        error_signal(str): 异常时 emit exception class name
    """

    pii_signal = pyqtSignal(str, list)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, word_data: dict, parent=None):
        super().__init__(parent)
        self._word_data = word_data
        self._engine = None

    def run(self) -> None:
        """扫描 word_data 每个 key，调 PIIEngine.detect，emit pii_signal(key, hits_dict_list)。

        PIIEngine.detect 的 page=None → engine._resolve_page_rect 返回占位 rect
        （D-17 锁；与 Phase 1 既有 fallback 形态一致）。

        跨线程 pyqtSignal 必须传 dict 列表（picklable），PIIHit 通过 dataclasses.asdict 序列化。
        主线程 _on_word_pii_page_result 反序列化为 PIIHit 写回 word_data[key]['pii']。
        """
        try:
            from privacyguard.pii.engine import PIIEngine

            self._engine = PIIEngine()
            for key, data in self._word_data.items():
                text = (data.get('text', '') or '') if isinstance(data, dict) else ''
                if not text.strip():
                    continue
                unit = TextUnit(page_index=0, text=text, source='text')
                hits = self._engine.detect(unit, page=None)
                self.pii_signal.emit(key, [asdict(h) for h in hits])
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(type(e).__name__)
            self.finished_signal.emit()
            return


__all__ = ['WordPIIWorker']
