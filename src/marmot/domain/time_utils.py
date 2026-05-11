"""
时间工具函数。

提供时间相关的纯函数，无 I/O，无状态。
"""

import re
from datetime import UTC, datetime
from typing import Any


_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)?$")


def utcnow() -> datetime:
    """返回当前 UTC 时间。
    
    返回:
        当前 UTC 时间的 datetime 对象
        
    示例:
        now = utcnow()  # datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    """
    return datetime.now(tz=UTC)


def to_iso(dt: datetime | None) -> str | None:
    """将 datetime 转换为 ISO 8601 格式字符串。
    
    参数:
        dt: datetime 对象，可以为 None
        
    返回:
        ISO 格式字符串，如果输入为 None 则返回 None
        
    示例:
        to_iso(datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC))
        # 返回 "2024-01-01T12:00:00+00:00"
    """
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat()


def from_iso(v: str | None) -> datetime | None:
    """将 ISO 8601 格式字符串转换为 datetime。
    
    参数:
        v: ISO 格式字符串，可以为 None 或空字符串
        
    返回:
        datetime 对象，如果输入为空则返回 None
        
    示例:
        from_iso("2024-01-01T12:00:00+00:00")
        # 返回 datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    """
    if not v:
        return None
    return datetime.fromisoformat(v)


def parse_duration(v: Any) -> float | None:
    """解析时长字符串为秒数。
    
    支持多种格式:
        - 数字: 300, 300.5
        - 带单位: "5m", "2h", "1d", "500ms", "30s"
        - 单位不区分大小写
        
    单位说明:
        - ms: 毫秒
        - s: 秒 (默认单位)
        - m: 分钟
        - h: 小时
        - d: 天
        
    参数:
        v: 时长值，可以是数字或字符串
        
    返回:
        秒数，如果无法解析则返回 None
        
    示例:
        parse_duration(300)      # 返回 300.0
        parse_duration("5m")     # 返回 300.0
        parse_duration("2h")     # 返回 7200.0
        parse_duration("1d")     # 返回 86400.0
        parse_duration("500ms")  # 返回 0.5
        parse_duration("invalid") # 返回 None
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    
    s = str(v).strip()
    m = _DURATION_RE.match(s)
    if not m:
        return None
    
    num = float(m.group(1))
    unit = m.group(2) or "s"
    
    unit_multipliers = {
        "ms": 0.001,
        "s": 1.0,
        "m": 60.0,
        "h": 3600.0,
        "d": 86400.0,
    }
    
    return num * unit_multipliers.get(unit, 1.0)
