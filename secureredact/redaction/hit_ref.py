# -*- coding: utf-8 -*-
"""HitRef: 不可变的 hit 标识 + Override: 不可变的状态覆盖."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


VALID_SOURCES = ("rule", "ocr", "jieba", "seal", "blacklist", "manual")
VALID_ACTIONS = ("ignore", "confirm")
VALID_SCOPES = ("session", "permanent")


@dataclass(frozen=True)
class HitRef:
    """标识一个具体的命中条目.

    - doc_hash: 当前文档 sha1 前 8 位
    - location: PDF 用 f"page_{i}";Word 用 f"paragraph_{idx}" 等
    - start/end: PDF 用 QRectF 离散化后的整型;Word 用字符位置
    - text: 命中原文(用于人眼核对,不参与 hit_id 计算)
    - source: 来源标记
    """

    doc_hash: str
    location: str
    start: int
    end: int
    text: str
    source: str

    def __post_init__(self) -> None:
        if self.source not in VALID_SOURCES:
            raise ValueError(
                f"source 必须是 {VALID_SOURCES} 之一,得到 {self.source!r}"
            )
        if self.end < self.start:
            raise ValueError("end 必须 >= start")

    @property
    def hit_id(self) -> str:
        return f"{self.doc_hash}|{self.location}|{self.start}|{self.end}|{self.source}"


@dataclass(frozen=True)
class Override:
    """覆盖态:对某条 HitRef 的会话级或永久级反馈."""

    ref: HitRef
    action: Literal["ignore", "confirm"]
    scope: Literal["session", "permanent"]
    promoted_at: Optional[str] = None  # ISO 字符串,仅 permanent 有

    def __post_init__(self) -> None:
        if self.action not in VALID_ACTIONS:
            raise ValueError(f"action 必须是 {VALID_ACTIONS},得到 {self.action!r}")
        if self.scope not in VALID_SCOPES:
            raise ValueError(f"scope 必须是 {VALID_SCOPES},得到 {self.scope!r}")
        if self.scope == "permanent" and not self.promoted_at:
            raise ValueError("permanent override 必须有 promoted_at")