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
    MarkEscalated,
    NotifyEscalated,
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
        hit: bool,  # 是否触发（超过阈值）
        consecutive_count: int,  # 规则要求的连续次数
        now: datetime,
        silence_seconds: float = 0,  # 静默时间
    ) -> Decision:
        """状态转换。
        
        参数:
            event: 当前告警事件
            hit: 本次是否触发（超过阈值）
            consecutive_count: 规则要求的连续次数
            now: 当前时间
            silence_seconds: 静默时间（秒）
            
        返回:
            Decision: 决策（新状态 + 动作）
        """
        state = event.state if isinstance(event.state, AlertState) else AlertState(event.state)
        
        # PENDING 状态：等待确认
        if state == AlertState.PENDING:
            if hit:
                # 触发中，增加计数
                new_hits = event.consecutive_hits + 1
                if new_hits >= consecutive_count:
                    # 达到触发条件
                    return Decision(
                        new_state=AlertState.FIRING.value,
                        event_patch={"consecutive_hits": new_hits},
                        actions=[NotifyFiring(
                            severity=event.severity.value if hasattr(event.severity, 'value') else event.severity,
                            notify_targets=[],  # TODO: 从规则获取
                        )]
                    )
                else:
                    # 继续计数
                    return Decision(
                        new_state=AlertState.PENDING.value,
                        event_patch={"consecutive_hits": new_hits}
                    )
            else:
                # 恢复正常，重置
                return Decision(
                    new_state=AlertState.PENDING.value,
                    event_patch={"consecutive_hits": 0, "consecutive_misses": 1}
                )
        
        # FIRING 状态：已触发
        elif state == AlertState.FIRING:
            if hit:
                # 还在触发
                if silence_seconds > 0:
                    # 进入静默
                    silence_until = now.timestamp() + silence_seconds
                    return Decision(
                        new_state=AlertState.SILENCED.value,
                        event_patch={"silenced_until": silence_until},
                        actions=[EnterSilence(until=silence_until)]
                    )
                else:
                    # 无静默，继续 FIRING
                    return Decision(
                        new_state=AlertState.FIRING.value,
                        event_patch={"consecutive_hits": event.consecutive_hits + 1}
                    )
            else:
                # 开始恢复
                return Decision(
                    new_state=AlertState.RESOLVING.value,
                    event_patch={"consecutive_misses": 1},
                    actions=[EnterResolving()]
                )
        
        # SILENCED 状态：静默中
        elif state == AlertState.SILENCED:
            # 检查静默是否结束
            if event.silenced_until and now.timestamp() >= event.silenced_until:
                # 静默结束
                if hit:
                    # 还在触发，继续告警
                    if silence_seconds > 0:
                        # 再次静默
                        silence_until = now.timestamp() + silence_seconds
                        return Decision(
                            new_state=AlertState.SILENCED.value,
                            event_patch={"silenced_until": silence_until},
                            actions=[
                                NotifyFiring(
                                    severity=event.severity.value if hasattr(event.severity, 'value') else event.severity,
                                    notify_targets=[],
                                ),
                                EnterSilence(until=silence_until)
                            ]
                        )
                    else:
                        # 回到 FIRING
                        return Decision(
                            new_state=AlertState.FIRING.value,
                            event_patch={"silenced_until": None}
                        )
                else:
                    # 开始恢复
                    return Decision(
                        new_state=AlertState.RESOLVING.value,
                        event_patch={"silenced_until": None, "consecutive_misses": 1},
                        actions=[EnterResolving()]
                    )
            else:
                # 还在静默中，不改变状态
                return Decision(new_state=AlertState.SILENCED.value)
        
        # RESOLVING 状态：恢复确认中
        elif state == AlertState.RESOLVING:
            if hit:
                # 又触发了，回到 FIRING
                return Decision(
                    new_state=AlertState.FIRING.value,
                    event_patch={"consecutive_hits": 1, "consecutive_misses": 0},
                    actions=[NotifyFiring(
                        severity=event.severity.value if hasattr(event.severity, 'value') else event.severity,
                        notify_targets=[],
                    )]
                )
            else:
                # 继续恢复
                new_misses = event.consecutive_misses + 1
                if new_misses >= consecutive_count:
                    # 达到恢复条件
                    return Decision(
                        new_state=AlertState.RESOLVED.value,
                        event_patch={"consecutive_misses": new_misses, "resolved_at": now},
                        actions=[NotifyResolved(notify_targets=[])]
                    )
                else:
                    # 继续确认
                    return Decision(
                        new_state=AlertState.RESOLVING.value,
                        event_patch={"consecutive_misses": new_misses}
                    )
        
        # ESCALATED 状态：已升级
        elif state == AlertState.ESCALATED:
            if hit:
                # 还在触发，保持状态
                return Decision(new_state=AlertState.ESCALATED.value)
            else:
                # 开始恢复
                return Decision(
                    new_state=AlertState.RESOLVING.value,
                    event_patch={"consecutive_misses": 1},
                    actions=[EnterResolving()]
                )
        
        # RESOLVED 状态：已恢复
        elif state == AlertState.RESOLVED:
            if hit:
                # 又触发了，重新开始
                return Decision(
                    new_state=AlertState.PENDING.value,
                    event_patch={"consecutive_hits": 1, "consecutive_misses": 0, "resolved_at": None}
                )
            else:
                # 保持已恢复
                return Decision(new_state=AlertState.RESOLVED.value)
        
        # 未知状态
        else:
            return Decision(new_state=state.value)
