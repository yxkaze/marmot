"""
Domain models - 数据类、枚举与工具函数。

本模块包含所有领域数据结构，包括：
    - 枚举类型（enums.py）
    - 规则相关数据类（rules.py）
    - 事件相关数据类（events.py）
    - 时间工具函数（time_utils.py）
    - 键生成工具函数（keys.py）
"""

# 枚举类型
from .enums import (
    AlertState,
    Severity,
    AlertStage,
    RunStatus,
    NotificationStatus,
    AggregateFn,
)

# 规则相关数据类
from .rules import (
    EscalationStep,
    ThresholdLevel,
    AggregateConfig,
    Rule,
    ThresholdRule,
)

# 事件相关数据类
from .events import (
    AlertEvent,
    RunRecord,
    Notification,
)

# 时间工具函数
from .time_utils import utcnow, to_iso, from_iso, parse_duration

# 键生成工具函数
from .keys import build_dedup_key, normalize_notify

__all__ = [
    # 枚举
    "AlertState",
    "Severity",
    "AlertStage",
    "RunStatus",
    "NotificationStatus",
    "AggregateFn",
    # 规则
    "EscalationStep",
    "ThresholdLevel",
    "AggregateConfig",
    "Rule",
    "ThresholdRule",
    # 事件
    "AlertEvent",
    "RunRecord",
    "Notification",
    # 工具函数
    "utcnow",
    "to_iso",
    "from_iso",
    "parse_duration",
    "build_dedup_key",
    "normalize_notify",
]
