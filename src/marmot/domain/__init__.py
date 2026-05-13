"""
Domain layer - 纯逻辑，无 I/O，无线程。

本层包含告警系统的核心领域模型和业务逻辑。

子模块:
    - models: 数据类、枚举与工具函数
    - decisions: 状态机决策
    - state_machine: 状态机
    - evaluator: 规则评估器
"""

# 从 models 子模块导入所有类型，方便使用
from .models import *

# 状态机
from .decisions import Decision, SideEffect, NotifyFiring, NotifyResolved, NotifyEscalated, EnterSilence, EnterResolving, MarkEscalated
from .state_machine import AlertStateMachine

# 评估器
from .evaluator import ThresholdEvaluator, Observation

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
    "to_iso",
    "from_iso",
    "parse_duration",
    "build_dedup_key",
    "normalize_notify",
    # 状态机
    "Decision",
    "SideEffect",
    "NotifyFiring",
    "NotifyResolved",
    "NotifyEscalated",
    "EnterSilence",
    "EnterResolving",
    "MarkEscalated",
    "AlertStateMachine",
    # 评估器
    "ThresholdEvaluator",
    "Observation",
]
