"""
评估器。

根据规则评估数值，返回观测结果。
纯函数，无 I/O，不修改状态。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models.enums import Severity
from .models.events import AlertEvent
from .models.rules import ThresholdRule
from .models.keys import build_dedup_key


@dataclass
class Observation:
    """观测结果。
    
    一次 report() 的评估输出。
    """
    hit: bool
    miss: bool
    matched_severity: Severity | None
    dedup_key: str
    notify_targets: list[str] = field(default_factory=list)


class ThresholdEvaluator:
    """阈值评估器。"""
    
    def evaluate(
        self,
        rule: ThresholdRule,
        value: float,
        labels: dict[str, Any],
        prior_event: AlertEvent | None,
        now: datetime,
    ) -> Observation:
        """评估阈值。
        
        参数:
            rule: 阈值规则
            value: 当前值
            labels: 标签
            prior_event: 先前的告警事件
            now: 当前时间
        """
        matched_level = rule.evaluate(value)
        
        hit = matched_level is not None
        miss = not hit
        
        matched_severity = None
        notify_targets = rule.notify_targets
        
        if matched_level:
            severity = matched_level.severity
            if isinstance(severity, str):
                matched_severity = Severity(severity)
            else:
                matched_severity = severity
            
            if matched_level.notify:
                notify_targets = matched_level.notify
        
        if prior_event:
            dedup_key = prior_event.dedup_key
        else:
            dedup_key = build_dedup_key(rule.name, labels)
        
        return Observation(
            hit=hit,
            miss=miss,
            matched_severity=matched_severity,
            dedup_key=dedup_key,
            notify_targets=notify_targets,
        )
