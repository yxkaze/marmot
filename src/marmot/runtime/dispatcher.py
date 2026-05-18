"""
分发器。

消费 Decision，执行副作用（写存储、调 sink 发通知）。
"""
from typing import Any

from ..domain.decisions import (
    Decision,
    NotifyFiring,
    NotifyResolved,
    EnterSilence,
    EnterResolving,
)
from ..domain.models.events import AlertEvent, Notification
from ..domain.models.enums import AlertState, NotificationStatus
from .registry import SinkRegistry
from .clock import Clock


class Dispatcher:
    """分发器。
    
    应用决策：更新事件状态、调用 sink 发通知、持久化通知记录。
    """
    
    def __init__(
        self,
        storage: Any,
        sink_registry: SinkRegistry,
        clock: Clock,
    ):
        self.storage = storage
        self.sink_registry = sink_registry
        self.clock = clock
    
    def apply(self, event: AlertEvent, decision: Decision) -> None:
        """应用决策。"""
        # 更新事件字段
        if decision.event_patch:
            for key, value in decision.event_patch.items():
                setattr(event, key, value)
        
        # 更新事件状态
        event.state = decision.new_state
        self.storage.update_alert_event(event)
        
        # 执行动作
        for action in decision.actions:
            self._execute_action(event, action)
    
    def _execute_action(self, event: AlertEvent, action: Any) -> None:
        """执行动作。"""
        if isinstance(action, NotifyFiring):
            self._send_notification(
                event=event,
                state=AlertState.FIRING,
                severity=action.severity,
                notify_targets=action.notify_targets,
                message="firing",
            )
        elif isinstance(action, NotifyResolved):
            self._send_notification(
                event=event,
                state=AlertState.RESOLVED,
                severity=None,
                notify_targets=action.notify_targets,
                message="resolved",
            )
        elif isinstance(action, (EnterSilence, EnterResolving)):
            pass
    
    def _send_notification(
        self,
        event: AlertEvent,
        state: AlertState,
        severity: Any,
        notify_targets: list[str],
        message: str,
    ) -> None:
        """对每个目标 sink 调用并持久化记录。

        顺序保证：先调 sink（允许其写回 ``notification.message`` /
        ``notification.labels``），再 record_notification。
        """
        now = self.clock.now()
        
        for target in notify_targets:
            sink = self.sink_registry.get(target)
            if not sink:
                continue
            
            notification = Notification(
                alert_event_id=event.id,
                rule_name=event.rule_name,
                dedup_key=event.dedup_key,
                status=NotificationStatus.PENDING,
                state=state,
                severity=severity,
                labels=dict(event.labels),
                stage=event.stage,
                message=message,
                sink_name=target,
                sent_at=now,
            )
            
            try:
                success = bool(sink(notification))
                notification.status = (
                    NotificationStatus.SENT if success else NotificationStatus.FAILED
                )
            except Exception:
                notification.status = NotificationStatus.FAILED
            
            # sink 可能已写回 notification.message / labels，
            # 此时再持久化能拿到真实内容
            self.storage.record_notification(notification)

