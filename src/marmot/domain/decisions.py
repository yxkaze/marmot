"""
状态机决策。

状态机输出的是"决策"，而不是直接执行动作。
决策包含：新状态 + 要执行的动作列表。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NotifyFiring:
    """发送告警通知。"""
    severity: str
    notify_targets: list[str]
    message: str = ""


@dataclass(slots=True)
class NotifyResolved:
    """发送恢复通知。"""
    notify_targets: list[str]
    message: str = ""


@dataclass(slots=True)
class NotifyEscalated:
    """发送升级通知。"""
    severity: str
    notify_targets: list[str]
    escalation_level: int
    message: str = ""


@dataclass(slots=True)
class EnterSilence:
    """进入静默期。"""
    until: float  # 静默结束时间戳


@dataclass(slots=True)
class EnterResolving:
    """进入恢复确认。"""


@dataclass(slots=True)
class MarkEscalated:
    """标记已升级。"""
    escalation_level: int
    severity: str


# SideEffect 是动作的并集类型
SideEffect = NotifyFiring | NotifyResolved | NotifyEscalated | EnterSilence | EnterResolving | MarkEscalated


@dataclass(slots=True)
class Decision:
    """状态机决策。
    
    包含状态转换所需的所有信息：
    - new_state: 新状态
    - event_patch: 要更新的事件字段
    - actions: 要执行的动作列表
    
    示例:
        Decision(
            new_state=AlertState.FIRING,
            actions=[NotifyFiring(severity="error", notify_targets=["dingtalk"])]
        )
    """
    new_state: str
    event_patch: dict[str, Any] = field(default_factory=dict)
    actions: list[SideEffect] = field(default_factory=list)
