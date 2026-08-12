"""Phase 3 Word PII 扫描 QThread worker（D-09 自动触发）。"""
from PyQt6.QtCore import QThread, pyqtSignal


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
        """Wave 1 RED 占位 — Wave 2 Task 实现 PIIEngine.detect 调用。"""
        raise NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现")


__all__ = ['WordPIIWorker']
