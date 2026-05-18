"""
API 层。

提供 MarmotApp 门面和模块级便捷函数。
"""
from typing import Any

from .domain.models.enums import AlertStage, AlertState, Severity
from .domain.models.rules import ThresholdRule, Rule
from .domain.models.events import AlertEvent
from .domain.evaluator import ThresholdEvaluator
from .domain.state_machine import AlertStateMachine
from .domain.decisions import NotifyFiring, NotifyResolved
from .domain.models.keys import build_dedup_key
from .storage.memory import MemoryStorage
from .runtime.clock import Clock, SystemClock
from .runtime.registry import RuleRegistry, SinkRegistry
from .runtime.dispatcher import Dispatcher
from .sinks.types import NotificationSink

_app: "MarmotApp | None" = None


class MarmotApp:
    """Marmot 应用门面。
    
    组装所有组件，提供 report / fire / resolve 等方法。
    """
    
    def __init__(
        self,
        storage: Any = None,
        clock: Clock | None = None,
    ):
        self.storage = storage or MemoryStorage()
        self.clock = clock or SystemClock()
        self.rule_registry = RuleRegistry()
        self.sink_registry = SinkRegistry()
        self.evaluator = ThresholdEvaluator()
        self.dispatcher = Dispatcher(
            self.storage,
            self.sink_registry,
            self.clock,
        )
    
    def register_threshold_rule(self, rule: ThresholdRule) -> None:
        """注册阈值规则。"""
        self.rule_registry.register_threshold_rule(rule)
    
    def register_rule(self, rule: Rule) -> None:
        """注册通用规则。"""
        self.rule_registry.register_rule(rule)
    
    def register_sink(self, name: str, sink: NotificationSink) -> None:
        """注册 Sink（``Callable[[Notification], bool]``）。"""
        self.sink_registry.register(name, sink)
    
    def report(
        self,
        name: str,
        value: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """上报指标值。
        
        完整流程：
        1. 获取规则
        2. 获取 prior_event
        3. evaluator 评估 → Observation
        4. state_machine 转换 → Decision
        5. dispatcher 应用 → 更新存储 + 发通知
        """
        labels = labels or {}
        
        # 1. 获取规则
        rule = self.rule_registry.get_threshold_rule(name)
        if not rule:
            raise ValueError(f"Rule '{name}' not found")
        
        # 2. 计算 dedup_key，查找 prior_event
        dedup_key = build_dedup_key(name, labels)
        prior_event = self.storage.get_active_alert(dedup_key)
        
        # 3. 评估
        observation = self.evaluator.evaluate(rule, value, labels, prior_event)
        
        # 4. 如果没有 prior_event，创建新的
        if not prior_event:
            prior_event = self.storage.create_alert_event(AlertEvent(
                rule_name=name,
                dedup_key=dedup_key,
                state=AlertState.PENDING,
                severity=observation.matched_severity,
                stage=AlertStage.THRESHOLD,
                labels=labels,
                current_value=value,
                fired_at=self.clock.now(),
            ))
        
        # 5. 状态机转换
        decision = AlertStateMachine.transition(
            event=prior_event,
            hit=observation.hit,
            consecutive_count=rule.consecutive_count,
            now=self.clock.now(),
            silence_seconds=rule.silence_seconds,
        )
        
        # 6. 把 Observation 的 notify_targets 注入 Decision 的 actions
        for action in decision.actions:
            if isinstance(action, (NotifyFiring, NotifyResolved)):
                if not action.notify_targets:
                    action.notify_targets = observation.notify_targets
        
        # 7. 应用决策
        self.dispatcher.apply(prior_event, decision)
    
    def list_active_alerts(self) -> list[AlertEvent]:
        """列出活跃告警。"""
        return self.storage.list_active_alerts()
    
    def list_alert_history(self, limit: int = 100) -> list[AlertEvent]:
        """列出告警历史。"""
        return self.storage.list_alert_history(limit=limit)
    
    def get_alert(self, alert_id: int) -> AlertEvent | None:
        """获取单个告警。"""
        return self.storage.get_alert(alert_id)
    
    def shutdown(self) -> None:
        """关闭应用。"""
        close = getattr(self.storage, "close", None)
        if close is not None:
            close()


def configure(
    storage: Any = "memory",
    clock: Clock | None = None,
) -> MarmotApp:
    """配置并初始化 MarmotApp。"""
    global _app
    
    if storage == "memory":
        storage_impl = MemoryStorage()
    else:
        storage_impl = storage
    
    _app = MarmotApp(storage=storage_impl, clock=clock)
    return _app


def get_app() -> MarmotApp:
    """获取全局应用实例。"""
    if _app is None:
        raise RuntimeError("Marmot not configured. Call configure() first.")
    return _app


def register_threshold_rule(rule: ThresholdRule) -> None:
    """注册阈值规则（模块级便捷函数）。"""
    get_app().register_threshold_rule(rule)


def register_sink(name: str, sink: NotificationSink) -> None:
    """注册 Sink（模块级便捷函数）。"""
    get_app().register_sink(name, sink)


def report(name: str, value: float, labels: dict[str, Any] | None = None) -> None:
    """上报指标值（模块级便捷函数）。"""
    get_app().report(name, value, labels)


def shutdown() -> None:
    """关闭应用（模块级便捷函数）。"""
    get_app().shutdown()
