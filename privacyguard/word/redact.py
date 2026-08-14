"""Phase 3 Word 真脱敏写入 wrapper（D-23 — 沿用 main.py:replace_matches_in_paragraph run-level 替换）。

redact_paragraph / redact_word 均为 main.py:replace_matches_in_paragraph 的薄 wrapper，
不重写 run-level 替换逻辑（D-23 锁定）。lazy import inside function（避免 privacyguard.word
拉起 12.9k LOC main.py；cp30 教训扩展）。
"""


def redact_paragraph(para, matches, fallback_replacement_text: str = '[已脱敏]') -> None:
    """单段落 run-level 替换 wrapper（透传 main.py:replace_matches_in_paragraph）。"""
    from main import replace_matches_in_paragraph

    replace_matches_in_paragraph(
        para, matches, text_offset=0, fallback_replacement_text=fallback_replacement_text,
    )


def redact_word(doc, key: str, merged_matches: list, fallback_replacement_text: str = '[已脱敏]') -> None:
    """doc + key 形态的真脱敏写入。

    key 命名与 main.py:_open_word_docx:10797-10819 段落 / 表格初始化严格对齐：
    - 'paragraph_{para_idx}' → doc.paragraphs[para_idx]
    - 'table_{t}_cell_{r}_{c}' → doc.tables[t].rows[r].cells[c]（cell 多段累加 para_offset）

    表格 cell 多段累加 para_offset 形态与 main.py:12753-12766 既有实现完全一致
    （python-docx cell.text 用换行拼接段落）。
    """
    from main import replace_matches_in_paragraph

    if not merged_matches:
        return

    if key.startswith('paragraph_'):
        para_idx = int(key.split('_', 1)[1])
        if para_idx >= len(doc.paragraphs):
            return
        redact_paragraph(
            doc.paragraphs[para_idx], merged_matches,
            fallback_replacement_text=fallback_replacement_text,
        )
        return

    if key.startswith('table_'):
        parts = key.split('_')
        if len(parts) != 5:
            return
        t = int(parts[1])
        r = int(parts[3])
        c = int(parts[4])
        if t >= len(doc.tables):
            return
        table = doc.tables[t]
        if r >= len(table.rows):
            return
        cell = table.rows[r].cells[c]

        para_offset = 0
        paragraphs = list(cell.paragraphs)
        for idx, para in enumerate(paragraphs):
            original_para_len = len(''.join(run.text for run in para.runs))
            replace_matches_in_paragraph(
                para, merged_matches,
                text_offset=para_offset,
                fallback_replacement_text=fallback_replacement_text,
            )
            para_offset += original_para_len
            if idx < len(paragraphs) - 1:
                # python-docx cell.text 使用换行拼接段落
                para_offset += 1


__all__ = ['redact_word', 'redact_paragraph']
