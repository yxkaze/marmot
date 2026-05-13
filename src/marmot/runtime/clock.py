"""
时间抽象。

Clock Protocol 让测试可以注入假时钟，
SystemClock 是生产环境的默认实现。
"""
import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """时间抽象 Protocol。"""
    
    def now(self) -> datetime:
        """获取当前 UTC 时间。"""
        ...
    
    def monotonic(self) -> float:
        """获取单调时间（秒），保证不倒退。"""
        ...


class SystemClock:
    """系统时钟实现。"""
    
    def now(self) -> datetime:
        """获取当前 UTC 时间。"""
        return datetime.now(UTC)
    
    def monotonic(self) -> float:
        """获取单调时间（秒）。"""
        return time.monotonic()
