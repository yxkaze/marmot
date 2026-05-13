"""
分发器。

消费 Decision，执行副作用（写存储、发通知）。
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
from ..domain.models.enums import NotificationStatus
from .registry import NotifierRegistry
from .clock import Clock


class Dispatcher:
    """分发器。
    
    应用决策：更新事件状态、发送通知。
    """
    
    def __init__(
        self,
        storage: Any,
        notifier_registry: NotifierRegistry,
        clock: Clock,
    ):
        self.storage = storage
        self.notifier_registry = notifier_registry
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
                state="firing",
                severity=action.severity,
                notify_targets=action.notify_targets,
                message=f"Alert firing: {event.rule_name}",
            )
        elif isinstance(action, NotifyResolved):
            self._send_notification(
                event=event,
                state="resolved",
                severity=None,
                notify_targets=action.notify_targets,
                message=f"Alert resolved: {event.rule_name}",
            )
        elif isinstance(action, (EnterSilence, EnterResolving)):
            pass
    
    def _send_notification(
        self,
        event: AlertEvent,
        state: str,
        severity: str | None,
        notify_targets: list[str],
        message: str,
    ) -> None:
        """发送通知。"""
        now = self.clock.now()
        
        for target in notify_targets:
            notifier = self.notifier_registry.get(target)
            if not notifier:
                continue
            
            notification = Notification(
                alert_event_id=event.id,
                rule_name=event.rule_name,
                dedup_key=event.dedup_key,
                status=NotificationStatus.PENDING.value,
                state=state,
                severity=severity,
                labels=event.labels,
                message=message,
                notifier_name=target,
                sent_at=now,
            )
            
            try:
                success = notifier.send(notification)
                notification.status = NotificationStatus.SENT.value if success else NotificationStatus.FAILED.value
            except Exception:
                notification.status = NotificationStatus.FAILED.value
            
            self.storage.record_notification(notification)
