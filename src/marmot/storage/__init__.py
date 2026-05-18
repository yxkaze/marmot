"""
存储层。

提供三个独立的 Protocol 和多种实现。
"""
from .base import AlertEventStorage, RunRecordStorage, NotificationStorage
from .memory import MemoryStorage
from .sqlite import SQLiteStorage

__all__ = [
    "AlertEventStorage",
    "RunRecordStorage",
    "NotificationStorage",
    "MemoryStorage",
    "SQLiteStorage",
]
