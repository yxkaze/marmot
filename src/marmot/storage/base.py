"""
存储层 Protocol 定义。
"""
from typing import Protocol, Any
from datetime import datetime


class Storage(Protocol):
    """存储抽象 Protocol。
    
    定义了告警事件、运行记录、通知记录的 CRUD 操作。
    """
    
    # AlertEvent CRUD
    def get_or_create_alert_event(
        self,
        rule_name: str,
        dedup_key: str,
        **defaults
    ) -> tuple[Any, bool]:
        """获取或创建告警事件。
        
        参数:
            rule_name: 规则名称
            dedup_key: 去重键
            **defaults: 如果创建，使用的默认值
            
        返回:
            (event, created): 事件对象和是否新创建
        """
        ...
    
    def update_alert_event(self, event_id: int, **updates) -> None:
        """更新告警事件。
        
        参数:
            event_id: 事件 ID
            **updates: 要更新的字段
        """
        ...
    
    def list_active_alerts(self, rule_name: str | None = None) -> list[Any]:
        """列出活跃告警。
        
        参数:
            rule_name: 可选，过滤规则名称
            
        返回:
            活跃告警列表（非 RESOLVED 状态）
        """
        ...
    
    def list_alert_history(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出告警历史。
        
        参数:
            rule_name: 可选，过滤规则名称
            limit: 限制数量
            
        返回:
            告警历史列表（按时间倒序）
        """
        ...
    
    def get_alert_event(self, event_id: int) -> Any | None:
        """获取单个告警事件。
        
        参数:
            event_id: 事件 ID
            
        返回:
            事件对象或 None
        """
        ...
    
    # RunRecord CRUD
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
        """创建运行记录。
        
        返回:
            记录 ID
        """
        ...
    
    def list_recent_runs(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出最近运行记录。
        
        参数:
            rule_name: 可选，过滤规则名称
            limit: 限制数量
            
        返回:
            运行记录列表（按时间倒序）
        """
        ...
    
    # Notification CRUD
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
        """创建通知记录。
        
        返回:
            记录 ID
        """
        ...
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出通知记录。
        
        参数:
            alert_event_id: 可选，过滤告警事件 ID
            limit: 限制数量
            
        返回:
            通知记录列表（按时间倒序）
        """
        ...
