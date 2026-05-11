"""
Domain layer - 纯逻辑，无 I/O，无线程。

本层包含告警系统的核心领域模型和业务逻辑。

子模块:
    - models: 数据类、枚举与工具函数
    - decisions: 状态机决策（待实现）
    - state_machine: 状态机（待实现）
    - evaluator: 规则评估器（待实现）
"""

# 从 models 子模块导入所有类型，方便使用
from .models import *

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
