"""
评估器。

根据规则评估数值，返回观测结果。
纯函数，无 I/O，不修改状态。
"""
from dataclasses import dataclass, field
from typing import Any

from .models.enums import Severity
from .models.events import AlertEvent
from .models.rules import ThresholdRule
from .models.keys import build_dedup_key


@dataclass
class Observation:
    """观测结果。
    
    一次 report() 的评估输出，描述"值是否超过阈值"。
    
    属性:
        hit: 是否超过阈值（触发）
        miss: 是否低于阈值（恢复）
        matched_severity: 匹配到的最高严重程度，未匹配时为 None
        dedup_key: 去重键，用于关联同一个告警的多次上报
        notify_targets: 通知目标列表，等级优先，无则用规则的
    """
    hit: bool
    miss: bool
    matched_severity: Severity | None
    dedup_key: str
    notify_targets: list[str] = field(default_factory=list)


class ThresholdEvaluator:
    """阈值评估器。
    
    纯函数，根据阈值规则评估数值：
    1. 用 rule.evaluate(value) 找到匹配的阈值等级
    2. 多等级匹配时，rule.evaluate 已返回最高严重程度
    3. 通知目标：等级有 notify 则用等级的，否则用规则的
    4. 去重键：有 prior_event 则复用，否则根据规则名+标签生成
    """
    
    def evaluate(
        self,
        rule: ThresholdRule,
        value: float,
        labels: dict[str, Any],
        prior_event: AlertEvent | None,
    ) -> Observation:
        """评估阈值。
        
        参数:
            rule: 阈值规则
            value: 当前值
            labels: 标签
            prior_event: 先前的告警事件
        """
        # 用规则的 evaluate 方法找到匹配的阈值等级
        matched_level = rule.evaluate(value)
        
        # hit/miss：是否超过阈值
        hit = matched_level is not None
        miss = not hit
        
        # 默认用规则的通知目标
        matched_severity = None
        notify_targets = rule.notify_targets
        
        if matched_level:
            # severity 在 __post_init__ 里已经转成枚举了，直接用
            matched_severity = matched_level.severity
            
            # 等级有自定义通知目标时，优先用等级的
            if matched_level.notify:
                notify_targets = matched_level.notify
        
        # 去重键：有先前事件则复用，否则新生成
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
