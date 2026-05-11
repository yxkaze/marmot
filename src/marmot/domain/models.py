"""
Domain models - dataclasses and enums.

This module contains all data structures used throughout marmot.
No I/O, no threads, pure data definitions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class AlertState(str, Enum):
    """告警生命周期状态。
    
    状态转换流程::
    
        report()首次触发 → PENDING (计数中)
        report()连续N次触发 → FIRING (已触发)
        FIRING + silence配置 → SILENCED (静默中)
        FIRING + 升级超时 → ESCALATED (已升级)
        report()连续N次正常 → RESOLVING (恢复中)
        RESOLVING + 确认 → RESOLVED (已恢复)
    
    属性:
        PENDING: 等待确认，正在计数连续触发次数
        FIRING: 已触发告警，正在发送通知
        SILENCED: 静默中，不发送重复通知
        ESCALATED: 已升级，通知更高级别
        RESOLVING: 恢复确认中，正在计数连续恢复次数
        RESOLVED: 已恢复，告警结束
    """
    PENDING = "pending"
    FIRING = "firing"
    SILENCED = "silenced"
    ESCALATED = "escalated"
    RESOLVING = "resolving"
    RESOLVED = "resolved"


class Severity(str, Enum):
    """告警严重程度等级。
    
    从低到高依次为:
        INFO: 信息级别，通常不需要立即处理
        WARNING: 警告级别，需要关注但不紧急
        ERROR: 错误级别，需要尽快处理
        CRITICAL: 严重级别，需要立即处理
    """
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStage(str, Enum):
    """告警触发机制类型。
    
    标识告警是通过哪种机制触发的:
        THRESHOLD: 阈值触发，指标值超过预设阈值
        TIMEOUT: 超时触发，任务执行超时或心跳超时
        HEARTBEAT: 心跳触发，预期时间内未收到心跳
        MANUAL: 手动触发，通过 fire() 手动触发
    """
    THRESHOLD = "threshold"
    TIMEOUT = "timeout"
    HEARTBEAT = "heartbeat"
    MANUAL = "manual"


class RunStatus(str, Enum):
    """任务执行状态。
    
    用于 @job 装饰器监控的任务执行状态:
        RUNNING: 正在执行
        SUCCESS: 执行成功
        FAILED: 执行失败
        TIMEOUT: 执行超时
    """
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class NotificationStatus(str, Enum):
    """通知发送状态。
    
    标识通知的发送结果:
        PENDING: 等待发送
        SENT: 发送成功
        FAILED: 发送失败
    """
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AggregateFn(str, Enum):
    """指标聚合函数。
    
    用于配置滑动窗口内的指标聚合方式:
        AVG: 平均值
        MAX: 最大值
        MIN: 最小值
        SUM: 求和
        COUNT: 计数
    
    示例:
        AggregateFn.AVG - 计算5分钟内所有上报值的平均数
        AggregateFn.MAX - 取窗口内的最大值
    """
    AVG = "avg"
    MAX = "max"
    MIN = "min"
    SUM = "sum"
    COUNT = "count"


# ---------------------------------------------------------------------------
# Rule 相关数据类
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EscalationStep:
    """升级步骤配置。
    
    当告警处于 FIRING 状态超过 after_seconds 秒后，会升级并发送通知到 notify 列表中的通道。
    
    属性:
        after_seconds: 触发升级所需的秒数
        notify: 升级后发送通知的目标列表
        
    示例:
        EscalationStep(after_seconds=300, notify=["sms", "phone"])  # 5分钟后升级到短信和电话
    """
    after_seconds: float
    notify: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ThresholdLevel:
    """单个阈值等级配置。
    
    定义一个具体的阈值点及其对应的严重程度。
    
    属性:
        value: 阈值数值
        severity: 该阈值的严重程度 (info/warning/error/critical)
        notify: 该等级触发时的通知目标（可选，为空时使用规则默认配置）
        silence_seconds: 该等级触发后的静默时间（可选，为空时使用规则默认配置）
        
    示例:
        ThresholdLevel(value=80, severity="warning")  # CPU > 80% 触发警告
        ThresholdLevel(value=95, severity="critical")  # CPU > 95% 触发严重告警
    """
    value: float
    severity: str
    notify: list[str] = field(default_factory=list)
    silence_seconds: float = 0


@dataclass(slots=True)
class AggregateConfig:
    """指标聚合配置。
    
    当附加到 ThresholdRule 时，多次 report() 调用的指标会被收集到滑动窗口中，
    在阈值评估前进行聚合。适用于监控一组实例的整体健康状况。
    
    属性:
        fn: 聚合函数 (avg/max/min/sum/count)
        window: 滑动窗口大小（秒），只计算窗口内的数据点
        
    示例:
        AggregateConfig(fn="avg", window=300)  # 5分钟平均值
        AggregateConfig(fn="max", window=60)   # 1分钟最大值
    """
    fn: str
    window: float


@dataclass(slots=True)
class Rule:
    """通用告警规则（用于心跳、Job 监控等）。
    
    适用于不需要阈值判断的场景，如：
    - 心跳监控：预期每隔 N 秒收到一次 ping
    - Job 监控：监控定时任务的执行状态
    
    属性:
        name: 规则名称，唯一标识
        expected_interval_seconds: 预期间隔秒数（心跳场景）
        timeout_seconds: 超时秒数，超过后触发告警
        silence_seconds: 触发后的静默时间，避免重复告警
        group_key: 分组键，用于聚合相同标签的告警
        severity: 默认严重程度
        notify_targets: 通知目标列表
        escalation_steps: 升级策略列表
        created_at: 规则创建时间
    """
    name: str
    expected_interval_seconds: float | None = None
    timeout_seconds: float | None = None
    silence_seconds: float = 0
    group_key: str | None = None
    severity: str = "error"
    notify_targets: list[str] = field(default_factory=list)
    escalation_steps: list[EscalationStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ThresholdRule:
    """阈值告警规则。
    
    用于监控指标值是否超过预设阈值。支持多等级阈值、连续次数确认、
    聚合计算等高级功能。
    
    属性:
        name: 规则名称
        thresholds: 阈值等级列表（按 value 升序排列，评估时取最高匹配）
        consecutive_count: 连续触发次数，达到后才真正触发告警（防止抖动）
        silence_seconds: 触发后的静默时间
        notify_targets: 默认通知目标列表
        escalation_steps: 升级策略列表
        group_key: 分组键
        aggregate: 聚合配置（可选）
        
    示例:
        ThresholdRule(
            name="cpu_usage",
            thresholds=[
                ThresholdLevel(value=80, severity="warning"),
                ThresholdLevel(value=95, severity="critical"),
            ],
            consecutive_count=3,
            silence_seconds=300,
            notify_targets=["dingtalk"],
        )
    """
    name: str
    thresholds: list[ThresholdLevel]
    consecutive_count: int = 1
    silence_seconds: float = 300
    notify_targets: list[str] = field(default_factory=list)
    escalation_steps: list[EscalationStep] = field(default_factory=list)
    group_key: str | None = None
    aggregate: AggregateConfig | None = None
    
    def evaluate(self, value: float) -> ThresholdLevel | None:
        """评估指标值，返回匹配的最高阈值等级。
        
        参数:
            value: 待评估的指标值
            
        返回:
            匹配的 ThresholdLevel，如果没有超过任何阈值则返回 None
            
        示例:
            rule = ThresholdRule(
                name="cpu",
                thresholds=[
                    ThresholdLevel(value=80, severity="warning"),
                    ThresholdLevel(value=95, severity="critical"),
                ]
            )
            rule.evaluate(92.5)  # 返回 severity="warning" 的 ThresholdLevel
            rule.evaluate(50.0)  # 返回 None
        """
        for t in reversed(sorted(self.thresholds, key=lambda x: x.value)):
            if value >= t.value:
                return t
        return None


# ---------------------------------------------------------------------------
# Event 相关数据类
# ---------------------------------------------------------------------------

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
    state: str = AlertState.PENDING.value
    severity: str = Severity.ERROR.value
    stage: str = AlertStage.THRESHOLD.value
    message: str = ""
    labels: dict[str, Any] = field(default_factory=dict)
    current_value: float | None = None
    consecutive_hits: int = 0
    consecutive_misses: int = 0
    fired_at: datetime = field(default_factory=datetime.utcnow)
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
    status: str = RunStatus.RUNNING.value
    message: str = ""
    error: str | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
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
    status: str = NotificationStatus.PENDING.value
    state: str = ""
    message: str = ""
    severity: str = ""
    labels: dict[str, Any] = field(default_factory=dict)
    stage: str = ""
    notifier_name: str = ""
    sent_at: datetime = field(default_factory=datetime.utcnow)
