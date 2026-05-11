"""
事件相关数据类。

包含告警事件、任务执行记录、通知记录等核心实体。
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """返回当前 UTC 时间（避免 deprecation warning）。"""
    return datetime.now(UTC)


@dataclass(slots=True)
class AlertEvent:
    """告警事件实体。
    
    代表一个活跃或历史的告警。当规则首次触发时会创建 AlertEvent，
    随着状态机推进会不断更新。这是持久化的核心实体。
    
    属性:
        id: 数据库主键（自动生成）
        rule_name: 规则名称
        dedup_key: 去重键（rule_name + labels 的哈希）
        state: 当前状态 (pending/firing/silenced/escalated/resolving/resolved)
        severity: 严重程度 (info/warning/error/critical)
        stage: 触发机制 (threshold/timeout/heartbeat/manual)
        message: 告警消息
        labels: 标签字典，用于区分同一规则的不同实例
        current_value: 当前指标值（阈值场景）
        consecutive_hits: 连续触发次数（用于达到 consecutive_count）
        consecutive_misses: 连续恢复次数（用于从 FIRING 变为 RESOLVED）
        fired_at: 首次触发时间
        resolved_at: 恢复时间（仅 RESOLVED 状态）
        silenced_until: 静默结束时间（仅 SILENCED 状态）
        escalated_at: 升级时间（仅 ESCALATED 状态）
        escalation_level: 当前升级级别（0 表示未升级）
    """
    id: int | None = None
    rule_name: str = ""
    dedup_key: str = ""
    state: str = "pending"
    severity: str = "error"
    stage: str = "threshold"
    message: str = ""
    labels: dict[str, Any] = field(default_factory=dict)
    current_value: float | None = None
    consecutive_hits: int = 0
    consecutive_misses: int = 0
    fired_at: datetime = field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    silenced_until: datetime | None = None
    escalated_at: datetime | None = None
    escalation_level: int = 0


@dataclass(slots=True)
class RunRecord:
    """任务执行记录。
    
    跟踪单个监控任务或心跳 ping 的执行情况。每次执行创建一条记录。
    
    属性:
        id: 数据库主键（自动生成）
        rule_name: 规则名称
        dedup_key: 去重键
        status: 执行状态 (running/success/failed/timeout)
        message: 执行消息
        error: 错误信息（如果有）
        labels: 标签字典
        started_at: 开始时间
        finished_at: 结束时间（None 表示仍在运行）
    """
    id: int | None = None
    rule_name: str = ""
    dedup_key: str = ""
    status: str = "running"
    message: str = ""
    error: str | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_utcnow)
    finished_at: datetime | None = None
    
    @property
    def duration_ms(self) -> float:
        """计算执行时长（毫秒）。
        
        返回:
            执行时长，如果未结束则返回 0.0
        """
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds() * 1000


@dataclass(slots=True)
class Notification:
    """通知记录。
    
    记录每次通知发送的详情，用于审计和排查。
    
    属性:
        id: 数据库主键（自动生成）
        alert_event_id: 关联的告警事件 ID
        rule_name: 规则名称
        dedup_key: 去重键
        status: 发送状态 (pending/sent/failed)
        state: 触发时的告警状态
        message: 通知消息内容
        severity: 严重程度
        labels: 标签字典
        stage: 触发机制
        notifier_name: 通知器名称（如 "dingtalk", "email"）
        sent_at: 发送时间
    """
    id: int | None = None
    alert_event_id: int = 0
    rule_name: str = ""
    dedup_key: str = ""
    status: str = "pending"
    state: str = ""
    message: str = ""
    severity: str = ""
    labels: dict[str, Any] = field(default_factory=dict)
    stage: str = ""
    notifier_name: str = ""
    sent_at: datetime = field(default_factory=_utcnow)
