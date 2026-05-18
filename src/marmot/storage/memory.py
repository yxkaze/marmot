"""
内存存储实现。

用于测试和早期开发，不持久化。
接口对齐 main 分支的 SQLiteStorage。
"""
from datetime import datetime
from threading import RLock

from ..domain.models.events import AlertEvent, RunRecord, Notification
from ..domain.models.enums import AlertState


class MemoryStorage:
    """内存存储实现（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._alert_events: dict[int, AlertEvent] = {}
        self._run_records: dict[int, RunRecord] = {}
        self._notifications: dict[int, Notification] = {}
        self._next_id = 1
    
    def _alloc_id(self) -> int:
        """分配一个唯一 ID。"""
        with self._lock:
            id = self._next_id
            self._next_id += 1
            return id
    
    # ── AlertEvent ──────────────────────────────────────
    
    def create_alert_event(self, event: AlertEvent) -> AlertEvent:
        """创建告警事件。"""
        with self._lock:
            event.id = self._alloc_id()
            self._alert_events[event.id] = event
            return event
    
    def update_alert_event(self, event: AlertEvent) -> None:
        """更新告警事件。"""
        with self._lock:
            if event.id not in self._alert_events:
                raise ValueError(f"Alert event {event.id} not found")
            self._alert_events[event.id] = event
    
    def get_alert(self, alert_id: int) -> AlertEvent | None:
        """通过 ID 获取告警事件。"""
        with self._lock:
            return self._alert_events.get(alert_id)
    
    def get_active_alert(self, dedup_key: str) -> AlertEvent | None:
        """通过 dedup_key 获取当前活跃的（未恢复的）告警事件。

        若同一 dedup_key 存在多条活跃记录，返回 id 最大的一条（最新创建），
        与 SQLiteStorage 行为保持一致。
        """
        with self._lock:
            matched = [
                e for e in self._alert_events.values()
                if e.dedup_key == dedup_key and e.state != AlertState.RESOLVED
            ]
            if not matched:
                return None
            return max(matched, key=lambda e: e.id or 0)
    
    def list_active_alerts(self) -> list[AlertEvent]:
        """列出所有活跃告警。"""
        active_states = {
            AlertState.PENDING,
            AlertState.FIRING,
            AlertState.SILENCED,
            AlertState.ESCALATED,
            AlertState.RESOLVING,
        }
        with self._lock:
            events = [e for e in self._alert_events.values() if e.state in active_states]
            events.sort(key=lambda e: e.fired_at, reverse=True)
            return events
    
    def list_alert_history(self, limit: int = 100) -> list[AlertEvent]:
        """列出已恢复的告警历史。"""
        with self._lock:
            resolved = [
                e for e in self._alert_events.values()
                if e.state == AlertState.RESOLVED
            ]
            resolved.sort(key=lambda e: e.fired_at, reverse=True)
            return resolved[:limit]
    
    # ── RunRecord ───────────────────────────────────────
    
    def create_run(self, run: RunRecord) -> RunRecord:
        """创建运行记录。"""
        with self._lock:
            run.id = self._alloc_id()
            self._run_records[run.id] = run
            return run
    
    def update_run(self, run: RunRecord) -> None:
        """更新运行记录。"""
        with self._lock:
            if run.id not in self._run_records:
                raise ValueError(f"Run record {run.id} not found")
            self._run_records[run.id] = run
    
    def get_run(self, run_id: int) -> RunRecord | None:
        """通过 ID 获取运行记录。"""
        with self._lock:
            return self._run_records.get(run_id)
    
    def get_latest_run(self, dedup_key: str) -> RunRecord | None:
        """通过 dedup_key 获取最近一条运行记录。"""
        with self._lock:
            runs = [r for r in self._run_records.values() if r.dedup_key == dedup_key]
            if not runs:
                return None
            runs.sort(key=lambda r: r.started_at, reverse=True)
            return runs[0]
    
    def list_runs(self, limit: int = 100) -> list[RunRecord]:
        """列出运行记录。"""
        with self._lock:
            records = list(self._run_records.values())
            records.sort(key=lambda r: r.started_at, reverse=True)
            return records[:limit]
    
    # ── Notification ────────────────────────────────────
    
    def record_notification(self, n: Notification) -> int:
        """记录通知。"""
        with self._lock:
            n.id = self._alloc_id()
            self._notifications[n.id] = n
            return n.id
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 200,
    ) -> list[Notification]:
        """列出通知记录。"""
        with self._lock:
            notifications = list(self._notifications.values())
            if alert_event_id is not None:
                notifications = [n for n in notifications if n.alert_event_id == alert_event_id]
            notifications.sort(key=lambda n: n.sent_at, reverse=True)
            return notifications[:limit]
