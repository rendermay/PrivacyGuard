"""Phase 3 Word 文档 → PII 引擎 TextUnit 流适配器（D-04 / D-17）。"""
from typing import Dict, List, Tuple


class WordAdapter:
    """Word 文档 → TextUnit 流适配器（D-04 / D-17）。"""

    @staticmethod
    def collect_units(docx_path: str) -> Tuple[List, Dict[int, str]]:
        """收集 docx 文件的段落 + 表格单元格文本，返回 (TextUnit 列表, key_index 映射)。

        Wave 1 RED 占位 — Wave 2 Task 实施。
        """
        raise NotImplementedError("Wave 1 RED placeholder — Wave 2 Task 实现")


__all__ = ['WordAdapter']
