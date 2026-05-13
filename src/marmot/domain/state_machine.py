"""
告警状态机。

纯函数实现，无副作用。接收当前事件和观测结果，返回决策。
"""

from datetime import datetime
from typing import Any

from .decisions import (
    Decision,
    EnterResolving,
    EnterSilence,
    NotifyFiring,
    NotifyResolved,
)
from .models.enums import AlertState
from .models.events import AlertEvent


class AlertStateMachine:
    """告警状态机（纯函数）。"""
    
    @staticmethod
    def transition(
        event: AlertEvent,
        hit: bool,
        consecutive_count: int,
        now: datetime,
        silence_seconds: float = 0,
    ) -> Decision:
        """状态转换。"""
        state = event.state
        
        # PENDING 状态：等待确认
        if state == AlertState.PENDING:
            if hit:
                new_hits = event.consecutive_hits + 1
                if new_hits >= consecutive_count:
                    return Decision(
                        new_state=AlertState.FIRING,
                        event_patch={"consecutive_hits": new_hits},
                        actions=[NotifyFiring(
                            severity=event.severity,
                            notify_targets=[],
                        )]
                    )
                else:
                    return Decision(
                        new_state=AlertState.PENDING,
                        event_patch={"consecutive_hits": new_hits}
                    )
            else:
                return Decision(
                    new_state=AlertState.PENDING,
                    event_patch={"consecutive_hits": 0, "consecutive_misses": 1}
                )
        
        # FIRING 状态：已触发
        elif state == AlertState.FIRING:
            if hit:
                if silence_seconds > 0:
                    silence_until = now.timestamp() + silence_seconds
                    return Decision(
                        new_state=AlertState.SILENCED,
                        event_patch={"silenced_until": silence_until},
                        actions=[EnterSilence(until=silence_until)]
                    )
                else:
                    return Decision(
                        new_state=AlertState.FIRING,
                        event_patch={"consecutive_hits": event.consecutive_hits + 1}
                    )
            else:
                return Decision(
                    new_state=AlertState.RESOLVING,
                    event_patch={"consecutive_misses": 1},
                    actions=[EnterResolving()]
                )
        
        # SILENCED 状态：静默中
        elif state == AlertState.SILENCED:
            if event.silenced_until and now.timestamp() >= event.silenced_until:
                if hit:
                    if silence_seconds > 0:
                        silence_until = now.timestamp() + silence_seconds
                        return Decision(
                            new_state=AlertState.SILENCED,
                            event_patch={"silenced_until": silence_until},
                            actions=[
                                NotifyFiring(
                                    severity=event.severity,
                                    notify_targets=[],
                                ),
                                EnterSilence(until=silence_until)
                            ]
                        )
                    else:
                        return Decision(
                            new_state=AlertState.FIRING,
                            event_patch={"silenced_until": None}
                        )
                else:
                    return Decision(
                        new_state=AlertState.RESOLVING,
                        event_patch={"silenced_until": None, "consecutive_misses": 1},
                        actions=[EnterResolving()]
                    )
            else:
                return Decision(new_state=AlertState.SILENCED)
        
        # RESOLVING 状态：恢复确认中
        elif state == AlertState.RESOLVING:
            if hit:
                return Decision(
                    new_state=AlertState.FIRING,
                    event_patch={"consecutive_hits": 1, "consecutive_misses": 0},
                    actions=[NotifyFiring(
                        severity=event.severity,
                        notify_targets=[],
                    )]
                )
            else:
                new_misses = event.consecutive_misses + 1
                if new_misses >= consecutive_count:
                    return Decision(
                        new_state=AlertState.RESOLVED,
                        event_patch={"consecutive_misses": new_misses, "resolved_at": now},
                        actions=[NotifyResolved(notify_targets=[])]
                    )
                else:
                    return Decision(
                        new_state=AlertState.RESOLVING,
                        event_patch={"consecutive_misses": new_misses}
                    )
        
        # ESCALATED 状态：已升级
        elif state == AlertState.ESCALATED:
            if hit:
                return Decision(new_state=AlertState.ESCALATED)
            else:
                return Decision(
                    new_state=AlertState.RESOLVING,
                    event_patch={"consecutive_misses": 1},
                    actions=[EnterResolving()]
                )
        
        # RESOLVED 状态：已恢复
        elif state == AlertState.RESOLVED:
            if hit:
                return Decision(
                    new_state=AlertState.PENDING,
                    event_patch={"consecutive_hits": 1, "consecutive_misses": 0, "resolved_at": None}
                )
            else:
                return Decision(new_state=AlertState.RESOLVED)
        
        else:
            return Decision(new_state=state)
