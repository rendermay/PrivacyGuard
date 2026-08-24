"""
Word 文档处理 Worker

v1.1.11: 模块化拆分,从 main.py 提取
v1.1.12: 命中字段 `replacement` 支持 partial masking(按 rule_name 查 DEFAULT_RULES_META)
"""

import time
import copy
import re
from typing import Dict, Optional
from PyQt6.QtCore import QThread, pyqtSignal

from secureredact.redaction.black_white_list_store import BlackWhiteListStore
from secureredact.redaction.whitelist_split import _split_text_by_whitelist
from secureredact.utils.masking import apply_mask_for_rule, apply_name_mask
from secureredact.utils.masking import apply_mask_for_rule

# 常量定义
PROGRESS_UPDATE_INTERVAL = 0.05


class WordWorker(QThread):
    """Word 文档智能脱敏线程

    v1.1.11: 模块化拆分
    v1.1.12: partial masking 支持 — `default_rules_meta` 传入规则名 → mask 配置表
    """
    finished_signal = pyqtSignal(dict)
    progress_signal = pyqtSignal(int)

    def __init__(self, word_doc, word_data, rules, custom_keywords, replacement_text, default_rules=None,
                 enable_name_recognition: bool = False,
                 default_rules_meta: Optional[Dict[str, Dict]] = None):
        super().__init__()
        self.word_doc = word_doc
        self.word_data = word_data
        self.rules = rules
        raw_keywords = custom_keywords.replace('\n', ' ').split()
        self.custom_keywords = [re.escape(k.strip()) for k in raw_keywords if k.strip()]
        self.replacement_text = replacement_text
        self.default_rules = default_rules or {}
        # v1.1.12: mask 元数据(可空 → 全部走 replacement_text,向后兼容)
        self.default_rules_meta = default_rules_meta or {}

        # v1.1.11: 中文姓名启发式识别开关 (默认 False,向后兼容)
        self.enable_name_recognition = enable_name_recognition

    def run(self):
        """主处理流程 - 支持取消并保存进度（v1.1.11）"""
        processed = 0
        total = 0
        try:
            # 统计总数（段落 + 表格单元格）
            total_paragraphs = len(self.word_doc.paragraphs)
            total_tables = len(self.word_doc.tables)
            total_cells = sum(len(table.rows) * len(table.columns) for table in self.word_doc.tables)
            total = total_paragraphs + total_cells
            last_emit_time = 0

            # 处理段落
            for idx, para in enumerate(self.word_doc.paragraphs):
                if self.isInterruptionRequested():
                    break  # 保留已处理结果

                key = f'paragraph_{idx}'
                if key in self.word_data:
                    text = self.word_data[key]['text']
                    matches = self._find_matches(text)
                    # v1.1.11: whiteList 过滤 + blackList 注入
                    matches = self._filter_whitelist(matches)
                    blacklist = BlackWhiteListStore.instance().effective_blacklist()
                    if blacklist:
                        bl_hits = self._scan_blacklist_in_text(text, blacklist)
                        matches.extend(bl_hits)
                    # 再过一次 whitelist (确保 blacklist + whitelist 同条目时白名单赢)
                    matches = self._filter_whitelist(matches)
                    self.word_data[key]['ocr'] = matches

                processed += 1
                self._emit_progress(processed, total, last_emit_time)
                last_emit_time = time.time()

            # 处理表格（仅在未取消时继续）
            if not self.isInterruptionRequested():
                for table_idx, table in enumerate(self.word_doc.tables):
                    if self.isInterruptionRequested():
                        break  # 保留已处理结果

                    for row_idx, row in enumerate(table.rows):
                        for cell_idx, cell in enumerate(row.cells):
                            key = f'table_{table_idx}_cell_{row_idx}_{cell_idx}'
                            if key in self.word_data:
                                text = self.word_data[key]['text']
                                matches = self._find_matches(text)
                                # v1.1.11: whiteList 过滤 + blackList 注入
                                matches = self._filter_whitelist(matches)
                                blacklist = BlackWhiteListStore.instance().effective_blacklist()
                                if blacklist:
                                    bl_hits = self._scan_blacklist_in_text(text, blacklist)
                                    matches.extend(bl_hits)
                                # 再过一次 whitelist (确保 blacklist + whitelist 同条目时白名单赢)
                                matches = self._filter_whitelist(matches)
                                self.word_data[key]['ocr'] = matches

                            processed += 1
                            self._emit_progress(processed, total, last_emit_time)
                            last_emit_time = time.time()

            # 发射已扫描的结果（无论完成与否）
            # v1.1.11: 发送深拷贝避免数据竞争
            output = copy.deepcopy(self.word_data)
            output['__scan_meta__'] = {
                'processed_items': processed,
                'total_items': total,
                'cancelled': self.isInterruptionRequested()
            }
            self.finished_signal.emit(output)

        except (IOError, OSError, RuntimeError, ValueError,
                AttributeError, KeyError, IndexError) as e:
            print(f"Word扫描错误: {e}")
            # 出错时也返回已处理结果
            output = copy.deepcopy(self.word_data)
            output['__scan_meta__'] = {
                'processed_items': processed,
                'total_items': total,
                'cancelled': self.isInterruptionRequested()
            }
            self.finished_signal.emit(output)

    def _emit_progress(self, processed, total, last_emit_time):
        """背压控制的进度更新"""
        current_progress = int(processed / total * 100)
        current_time = time.time()
        if current_time - last_emit_time > PROGRESS_UPDATE_INTERVAL or processed == total:
            self.progress_signal.emit(current_progress)

    def _find_matches(self, text):
        """查找匹配的敏感信息"""
        matches = []
        all_patterns = self.rules + self.custom_keywords

        # v1.1.11: 中文姓名启发式识别 (默认 OFF)
        if self.enable_name_recognition and text:
            try:
                from secureredact.pii.name_recognizer import (
                    extract_person_names,
                )
                # v1.1.11 fix: 传入当前生效白名单,识别器据此豁免
                # '丁方经' / '戊方经' 等合同角色词粘连伪人名,避免白名单邻接误报.
                # v1.1.12: 启用 require_context=True, 仅注入在原文中具有强上下文
                # (原告: / 经理 / 审判员 / 先生...) 的人名, 大幅降低 jieba nr 误报.
                _whitelist = BlackWhiteListStore.instance().effective_whitelist()
                _names = extract_person_names(
                    text, whitelist=_whitelist, require_context=True,
                )
                if _names:
                    _existing = set(self.rules) | set(self.custom_keywords)
                    _extra = [
                        re.escape(n) for n in _names
                        if n not in _existing
                    ]
                    if _extra:
                        all_patterns = all_patterns + _extra
            except Exception as _exc:
                print(f"[WordWorker] 姓名识别失败: {_exc}")

        for pattern in all_patterns:
            try:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched_text = match.group()
                    rule_name = self._get_rule_name(pattern)
                    source = self._source_for_pattern(pattern)
                    # v1.1.12: rule 来源(命中 self.rules) + rule_name 在 META 中 → 应用 partial mask
                    # custom_keywords / jieba 来源 → 保留 replacement_text(向后兼容)
                    #   但 jieba 路径为了让 2 字姓名变 2 个 * 而不是 1 个 *,
                    #   修复为 replacement = '*' * len(matched_text)
                    replacement_value = self.replacement_text
                    if pattern in self.rules:
                        masked = apply_mask_for_rule(
                            matched_text, rule_name, self.default_rules_meta
                        )
                        if masked is not None:
                            replacement_value = masked
                    elif source == "jieba":
                        # v1.1.12: jieba 路径(自定义人名识别)
                        # 用 apply_name_mask 保留姓(只 mask 名), 例 "李秋实" → "李**", "张三" → "张*"
                        # 而非简单的 "*" * len 整段打码(丢失姓)
                        replacement_value = apply_name_mask(matched_text)
                    matches.append({
                        'pattern': pattern,
                        'rule_name': rule_name,
                        'start': match.start(),
                        'end': match.end(),
                        'text': matched_text,
                        'replacement': replacement_value,
                        'source': source,
                    })
            except re.error:
                # 忽略无效的正则表达式
                pass

        # v1.1.12: 去重 — 如果 jieba 路径的 hit 完全在 rule 路径 hit 范围内, 剥除 jieba hit
        # 避免"公司名"整段 mask + jieba 命中中间 2 字 重复打码造成输出错乱
        rule_ranges = [(m['start'], m['end']) for m in matches if m['source'] == 'rule']
        if rule_ranges:
            matches = [
                m for m in matches
                if m['source'] != 'jieba' or
                not any(rs <= m['start'] and m['end'] <= re_ for rs, re_ in rule_ranges)
            ]

        return matches

    def _source_for_pattern(self, pattern: str) -> str:
        """识别 pattern 属于哪个来源.

        jieba 来源的 pattern 是 ``re.escape(姓名)`` 形式,且**不在**
        self.rules / self.custom_keywords 内。

        rule 路径与 custom_keywords 都视为规则类 — Word 端不细分
        ocr(单独走 PDFChannel),所以二者统一打 ``source='rule'``。
        """
        if pattern in self.rules or pattern in self.custom_keywords:
            return "rule"
        return "jieba"

    def _get_rule_name(self, pattern):
        """根据模式获取规则名称"""
        for name, pat in self.default_rules.items():
            if pat == pattern:
                return name
        return "自定义"

    # ---- v1.1.11: 黑/白名单串联 ----

    def _filter_whitelist(self, hits: list) -> list:
        """v38: 剥掉包含白名单子串的 hit; trim_only=True 时只剥白名单片段."""
        store = BlackWhiteListStore.instance()
        whitelist = store.effective_whitelist()
        if not whitelist or not hits:
            return hits
        trim_only = store.is_trim_only()
        kept: list = []
        for hit in hits:
            if hit.get("source") == "manual":
                kept.append(hit)
                continue
            text = hit.get("text", "") or ""
            spans = _split_text_by_whitelist(text, whitelist)
            # 无 trim 必要 → no_split 成立 ⟺ text 不含 wl, 旧行为与新行为都是原样保留
            no_split = (
                len(spans) == 1
                and spans[0][0] == 0
                and spans[0][1] == len(text)
            )
            if no_split:
                kept.append(hit)
                continue
            # 旧行为 (v1.1.11): 整条剥掉
            if not trim_only:
                continue
            # 新行为 (v38): 每段保留片段生成新 hit
            hit_start = hit.get("start", 0)
            for s, e, t in spans:
                if not t:
                    continue
                new_hit = dict(hit)
                new_hit["start"] = hit_start + s
                new_hit["end"] = hit_start + e
                new_hit["text"] = t
                kept.append(new_hit)
        return kept

    @staticmethod
    def _scan_blacklist_in_text(text: str, blacklist: list) -> list:
        """在 text 中扫描 blacklist 条目, 返回 [{start, end, text, source, rule_name}, ...]."""
        hits = []
        if not text or not blacklist:
            return hits
        for bl_item in blacklist:
            if not bl_item:
                continue
            start = 0
            while True:
                idx = text.find(bl_item, start)
                if idx < 0:
                    break
                hits.append({
                    "start": idx,
                    "end": idx + len(bl_item),
                    "text": bl_item,
                    "source": "blacklist",
                    "rule_name": f"黑名单:{bl_item}",
                })
                start = idx + len(bl_item)
        return hits
