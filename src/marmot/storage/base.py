"""
存储层 Protocol 定义。
"""
from datetime import datetime
from typing import Protocol

from ..domain.models.events import AlertEvent, RunRecord, Notification


class Storage(Protocol):
    """存储抽象 Protocol。
    
    定义了告警事件、运行记录、通知记录的 CRUD 操作。
    对齐 main 分支的 SQLiteStorage 接口设计。
    """
    
    # ── AlertEvent ──────────────────────────────────────
    
    def create_alert_event(self, event: AlertEvent) -> AlertEvent:
        """创建告警事件。
        
        参数:
            event: 告警事件对象（id 可为 None，由存储层分配）
            
        返回:
            带有 id 的事件对象
        """
        ...
    
    def update_alert_event(self, event: AlertEvent) -> None:
        """更新告警事件。
        
        参数:
            event: 带有 id 的事件对象，按 id 匹配更新
        """
        ...
    
    def get_alert(self, alert_id: int) -> AlertEvent | None:
        """通过 ID 获取告警事件。"""
        ...
    
    def get_active_alert(self, dedup_key: str) -> AlertEvent | None:
        """通过 dedup_key 获取当前活跃的（未恢复的）告警事件。"""
        ...
    
    def list_active_alerts(self) -> list[AlertEvent]:
        """列出所有活跃告警（未恢复的）。"""
        ...
    
    def list_alert_history(self, limit: int = 100) -> list[AlertEvent]:
        """列出已恢复的告警历史。"""
        ...
    
    # ── RunRecord ───────────────────────────────────────
    
    def create_run(self, run: RunRecord) -> RunRecord:
        """创建运行记录。
        
        参数:
            run: 运行记录对象（id 可为 None，由存储层分配）
            
        返回:
            带有 id 的记录对象
        """
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
    
    # ── Notification ────────────────────────────────────
    
    def record_notification(self, n: Notification) -> int:
        """记录通知。
        
        返回:
            记录 ID
        """
        ...
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 200,
    ) -> list[Notification]:
        """列出通知记录。"""
        ...
