"""
Domain models - 数据类与枚举。

本模块聚合了所有领域数据结构，方便导入。

为了向后兼容，所有类型都可以从 marmot.domain.models 导入。
实际定义分散在以下模块中：
    - enums: 枚举类型
    - rules: 规则相关数据类
    - events: 事件相关数据类
    - time_utils: 时间工具函数
    - keys: 键生成工具函数
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
]
