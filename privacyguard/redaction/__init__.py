# -*- coding: utf-8 -*-
"""人工干预数据模型与存储包.

默认懒加载,任何调用方只 import 用到的子模块即可。
"""
from privacyguard.redaction.hit_ref import HitRef, Override, VALID_SOURCES

__all__ = ["HitRef", "Override", "VALID_SOURCES"]