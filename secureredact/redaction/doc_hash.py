# -*- coding: utf-8 -*-
"""文档 doc_hash 工具: 路径 + size + mtime_ns 的 sha1 前 8 位."""
from __future__ import annotations

import hashlib
import os


def compute_doc_hash(file_path: str) -> str:
    """计算文档 doc_hash.

    算法: sha1(file_path + "\n" + str(size) + "\n" + str(mtime_ns)).
    返回 8 位 hex(短到足够区分文档,长到不易碰撞).

    Raises:
        OSError: 文件不存在或无权限读取 stat.
    """
    if not file_path:
        raise OSError("file_path 为空")
    stat = os.stat(file_path)
    payload = f"{file_path}\n{stat.st_size}\n{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:8]