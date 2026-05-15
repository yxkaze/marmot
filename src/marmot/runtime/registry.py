"""
注册表。

管理规则和 Sink 的注册与查询。
"""
from typing import Any
from threading import RLock

from ..domain.models.rules import ThresholdRule, Rule
from ..sinks.types import NotificationSink


class RuleRegistry:
    """规则注册表（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._threshold_rules: dict[str, ThresholdRule] = {}
        self._rules: dict[str, Rule] = {}
    
    def register_threshold_rule(self, rule: ThresholdRule) -> None:
        """注册阈值规则。"""
        with self._lock:
            self._threshold_rules[rule.name] = rule
    
    def get_threshold_rule(self, name: str) -> ThresholdRule | None:
        """获取阈值规则。"""
        with self._lock:
            return self._threshold_rules.get(name)
    
    def list_threshold_rules(self) -> list[ThresholdRule]:
        """列出所有阈值规则。"""
        with self._lock:
            return list(self._threshold_rules.values())
    
    def register_rule(self, rule: Rule) -> None:
        """注册通用规则（心跳/Job）。"""
        with self._lock:
            self._rules[rule.name] = rule
    
    def get_rule(self, name: str) -> Rule | None:
        """获取通用规则。"""
        with self._lock:
            return self._rules.get(name)
    
    def list_rules(self) -> list[Rule]:
        """列出所有通用规则。"""
        with self._lock:
            return list(self._rules.values())


class SinkRegistry:
    """Sink 注册表（线程安全）。

    Sink 是 ``Callable[[Notification], bool]``，框架不强制为类。
    """
    
    def __init__(self):
        self._lock = RLock()
        self._sinks: dict[str, NotificationSink] = {}
    
    def register(self, name: str, sink: NotificationSink) -> None:
        """注册 sink。"""
        with self._lock:
            self._sinks[name] = sink
    
    def get(self, name: str) -> NotificationSink | None:
        """获取 sink。"""
        with self._lock:
            return self._sinks.get(name)
    
    def list(self) -> list[str]:
        """列出所有 sink 名称。"""
        with self._lock:
            return list(self._sinks.keys())

