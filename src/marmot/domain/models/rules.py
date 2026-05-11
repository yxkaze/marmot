"""
规则相关数据类。

包含告警规则的定义，包括阈值规则、心跳规则、升级策略等。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import AggregateFn, Severity
from .time_utils import utcnow


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
        severity: 该阈值的严重程度
        notify: 该等级触发时的通知目标（可选，为空时使用规则默认配置）
        silence_seconds: 该等级触发后的静默时间（可选，为空时使用规则默认配置）
        
    示例:
        ThresholdLevel(value=80, severity=Severity.WARNING)  # CPU > 80% 触发警告
        ThresholdLevel(value=95, severity=Severity.CRITICAL)  # CPU > 95% 触发严重告警
    """
    value: float
    severity: Severity
    notify: list[str] = field(default_factory=list)
    silence_seconds: float = 0


@dataclass(slots=True)
class AggregateConfig:
    """指标聚合配置。
    
    当附加到 ThresholdRule 时，多次 report() 调用的指标会被收集到滑动窗口中，
    在阈值评估前进行聚合。适用于监控一组实例的整体健康状况。
    
    属性:
        fn: 聚合函数
        window: 滑动窗口大小（秒），只计算窗口内的数据点
        
    示例:
        AggregateConfig(fn=AggregateFn.AVG, window=300)  # 5分钟平均值
        AggregateConfig(fn=AggregateFn.MAX, window=60)   # 1分钟最大值
    """
    fn: AggregateFn
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
    severity: Severity = Severity.ERROR
    notify_targets: list[str] = field(default_factory=list)
    escalation_steps: list[EscalationStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)


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
