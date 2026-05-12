"""
内存存储实现。

用于测试和早期开发，不持久化。
"""
from datetime import datetime
from threading import RLock
from typing import Any
from dataclasses import asdict

from ..domain.models.events import AlertEvent, RunRecord, Notification


class MemoryStorage:
    """内存存储实现（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._alert_events: dict[int, AlertEvent] = {}
        self._alert_events_by_key: dict[str, int] = {}  # dedup_key -> id
        self._run_records: list[RunRecord] = []
        self._notifications: list[Notification] = []
        self._next_id = 1
    
    def _get_next_id(self) -> int:
        """获取下一个 ID。"""
        with self._lock:
            id = self._next_id
            self._next_id += 1
            return id
    
    def get_or_create_alert_event(
        self,
        rule_name: str,
        dedup_key: str,
        **defaults
    ) -> tuple[AlertEvent, bool]:
        """获取或创建告警事件。"""
        with self._lock:
            # 查找已存在的事件
            if dedup_key in self._alert_events_by_key:
                event_id = self._alert_events_by_key[dedup_key]
                return self._alert_events[event_id], False
            
            # 创建新事件
            event_id = self._get_next_id()
            now = datetime.utcnow()
            
            event = AlertEvent(
                id=event_id,
                rule_name=rule_name,
                dedup_key=dedup_key,
                state=defaults.get('state', 'pending'),
                severity=defaults.get('severity'),
                stage=defaults.get('stage'),
                message=defaults.get('message', ''),
                labels=defaults.get('labels', {}),
                current_value=defaults.get('current_value'),
                consecutive_hits=defaults.get('consecutive_hits', 0),
                consecutive_misses=defaults.get('consecutive_misses', 0),
                fired_at=defaults.get('fired_at', now),
                resolved_at=defaults.get('resolved_at'),
                silenced_until=defaults.get('silenced_until'),
                escalated_at=defaults.get('escalated_at'),
                escalation_level=defaults.get('escalation_level', 0),
            )
            
            self._alert_events[event_id] = event
            self._alert_events_by_key[dedup_key] = event_id
            
            return event, True
    
    def update_alert_event(self, event_id: int, **updates) -> None:
        """更新告警事件。"""
        with self._lock:
            if event_id not in self._alert_events:
                raise ValueError(f"Alert event {event_id} not found")
            
            event = self._alert_events[event_id]
            
            # 创建更新后的事件
            updated_data = asdict(event)
            updated_data.update(updates)
            
            self._alert_events[event_id] = AlertEvent(**updated_data)
    
    def get_alert_event(self, event_id: int) -> AlertEvent | None:
        """获取单个告警事件。"""
        with self._lock:
            return self._alert_events.get(event_id)
    
    def list_active_alerts(self, rule_name: str | None = None) -> list[AlertEvent]:
        """列出活跃告警。"""
        with self._lock:
            events = list(self._alert_events.values())
            
            # 过滤活跃状态
            from ..domain.models.enums import AlertState
            active_states = {
                AlertState.PENDING.value,
                AlertState.FIRING.value,
                AlertState.SILENCED.value,
                AlertState.ESCALATED.value,
                AlertState.RESOLVING.value,
            }
            events = [e for e in events if e.state in active_states]
            
            # 过滤规则名称
            if rule_name:
                events = [e for e in events if e.rule_name == rule_name]
            
            # 按时间倒序
            events.sort(key=lambda e: e.fired_at, reverse=True)
            return events
    
    def list_alert_history(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[AlertEvent]:
        """列出告警历史。"""
        with self._lock:
            events = list(self._alert_events.values())
            
            # 过滤规则名称
            if rule_name:
                events = [e for e in events if e.rule_name == rule_name]
            
            # 按时间倒序
            events.sort(key=lambda e: e.fired_at, reverse=True)
            
            return events[:limit]
    
    def create_run_record(
        self,
        rule_name: str,
        status: str,
        message: str = "",
        error: str | None = None,
        labels: dict | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> int:
        """创建运行记录。"""
        with self._lock:
            record_id = self._get_next_id()
            
            record = RunRecord(
                id=record_id,
                rule_name=rule_name,
                status=status,
                message=message,
                error=error,
                labels=labels or {},
                started_at=started_at or datetime.utcnow(),
                finished_at=finished_at,
            )
            
            self._run_records.append(record)
            return record_id
    
    def list_recent_runs(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[RunRecord]:
        """列出最近运行记录。"""
        with self._lock:
            records = self._run_records.copy()
            
            # 过滤规则名称
            if rule_name:
                records = [r for r in records if r.rule_name == rule_name]
            
            # 按时间倒序
            records.sort(key=lambda r: r.started_at, reverse=True)
            
            return records[:limit]
    
    def create_notification(
        self,
        alert_event_id: int,
        rule_name: str,
        dedup_key: str,
        status: str,
        state: str | None = None,
        message: str = "",
        severity: str | None = None,
        labels: dict | None = None,
        stage: str | None = None,
        notifier_name: str = "",
        sent_at: datetime | None = None,
    ) -> int:
        """创建通知记录。"""
        with self._lock:
            notification_id = self._get_next_id()
            
            notification = Notification(
                id=notification_id,
                alert_event_id=alert_event_id,
                rule_name=rule_name,
                dedup_key=dedup_key,
                status=status,
                state=state,
                message=message,
                severity=severity,
                labels=labels or {},
                stage=stage,
                notifier_name=notifier_name,
                sent_at=sent_at or datetime.utcnow(),
            )
            
            self._notifications.append(notification)
            return notification_id
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 100
    ) -> list[Notification]:
        """列出通知记录。"""
        with self._lock:
            notifications = self._notifications.copy()
            
            # 过滤告警事件 ID
            if alert_event_id:
                notifications = [n for n in notifications if n.alert_event_id == alert_event_id]
            
            # 按时间倒序
            notifications.sort(key=lambda n: n.sent_at, reverse=True)
            
            return notifications[:limit]
