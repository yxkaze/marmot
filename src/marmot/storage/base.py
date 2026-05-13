"""
存储层 Protocol 定义。

按实体拆分为三个独立的 Protocol：
- AlertEventStorage: 告警事件存储
- RunRecordStorage: 运行记录存储
- NotificationStorage: 通知记录存储
"""
from typing import Protocol

from ..domain.models.events import AlertEvent, RunRecord, Notification


class AlertEventStorage(Protocol):
    """告警事件存储 Protocol。"""
    
    def create_alert_event(self, event: AlertEvent) -> AlertEvent:
        """创建告警事件。"""
        ...
    
    def update_alert_event(self, event: AlertEvent) -> None:
        """更新告警事件。"""
        ...
    
    def get_alert(self, alert_id: int) -> AlertEvent | None:
        """通过 ID 获取告警事件。"""
        ...
    
    def get_active_alert(self, dedup_key: str) -> AlertEvent | None:
        """通过 dedup_key 获取当前活跃的告警事件。"""
        ...
    
    def list_active_alerts(self) -> list[AlertEvent]:
        """列出所有活跃告警。"""
        ...
    
    def list_alert_history(self, limit: int = 100) -> list[AlertEvent]:
        """列出已恢复的告警历史。"""
        ...


class RunRecordStorage(Protocol):
    """运行记录存储 Protocol。"""
    
    def create_run(self, run: RunRecord) -> RunRecord:
        """创建运行记录。"""
        ...
    
    def update_run(self, run: RunRecord) -> None:
        """更新运行记录。"""
        ...
    
    def get_run(self, run_id: int) -> RunRecord | None:
        """通过 ID 获取运行记录。"""
        ...
    
    def get_latest_run(self, dedup_key: str) -> RunRecord | None:
        """通过 dedup_key 获取最近一条运行记录。"""
        ...
    
    def list_runs(self, limit: int = 100) -> list[RunRecord]:
        """列出运行记录。"""
        ...


class NotificationStorage(Protocol):
    """通知记录存储 Protocol。"""
    
    def record_notification(self, n: Notification) -> int:
        """记录通知。"""
        ...
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 200,
    ) -> list[Notification]:
        """列出通知记录。"""
        ...
