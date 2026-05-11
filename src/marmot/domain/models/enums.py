"""
枚举类型定义。

包含告警系统中使用的所有枚举类型。
"""

from enum import Enum


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
