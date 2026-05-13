"""
测试 Clock 抽象。
"""
import pytest
from marmot.runtime.clock import Clock, SystemClock


def test_clock_is_protocol():
    """Clock 应该是一个 Protocol。"""
    from typing import Protocol
    assert issubclass(Clock, Protocol)


def test_system_clock_now():
    """SystemClock.now() 应该返回当前 UTC 时间。"""
    clock = SystemClock()
    now = clock.now()
    
    from datetime import datetime
    assert isinstance(now, datetime)
    assert abs((datetime.utcnow() - now).total_seconds()) < 1.0


def test_system_clock_monotonic():
    """SystemClock.monotonic() 应该返回单调递增的时间。"""
    clock = SystemClock()
    t1 = clock.monotonic()
    t2 = clock.monotonic()
    
    assert isinstance(t1, float)
    assert t2 >= t1
