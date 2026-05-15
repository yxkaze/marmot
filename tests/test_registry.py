"""
测试注册表。
"""
import pytest
from marmot.runtime.registry import RuleRegistry, SinkRegistry
from marmot.domain.models.rules import ThresholdRule, Rule, ThresholdLevel
from marmot.domain.models.enums import Severity


# ── RuleRegistry ────────────────────────────────────────


def test_register_and_get_threshold_rule():
    """应该能注册和获取阈值规则。"""
    registry = RuleRegistry()
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    registry.register_threshold_rule(rule)
    
    retrieved = registry.get_threshold_rule("cpu_high")
    assert retrieved is not None
    assert retrieved.name == "cpu_high"


def test_get_threshold_rule_not_found():
    """获取不存在的规则应该返回 None。"""
    registry = RuleRegistry()
    assert registry.get_threshold_rule("nonexistent") is None


def test_list_threshold_rules():
    """应该能列出所有阈值规则。"""
    registry = RuleRegistry()
    rule1 = ThresholdRule(
        name="rule1",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    rule2 = ThresholdRule(
        name="rule2",
        thresholds=[ThresholdLevel(value=90.0, severity=Severity.ERROR)],
        consecutive_count=2,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    registry.register_threshold_rule(rule1)
    registry.register_threshold_rule(rule2)
    
    rules = registry.list_threshold_rules()
    assert len(rules) == 2


def test_register_and_get_rule():
    """应该能注册和获取通用规则。"""
    registry = RuleRegistry()
    rule = Rule(
        name="heartbeat_check",
        expected_interval_seconds=60,
        timeout_seconds=120,
        silence_seconds=300,
        severity=Severity.ERROR,
        notify_targets=["console"],
    )
    
    registry.register_rule(rule)
    
    retrieved = registry.get_rule("heartbeat_check")
    assert retrieved is not None
    assert retrieved.name == "heartbeat_check"


def test_get_rule_not_found():
    """获取不存在的通用规则应该返回 None。"""
    registry = RuleRegistry()
    assert registry.get_rule("nonexistent") is None


# ── SinkRegistry ────────────────────────────────────


def test_register_and_get_sink():
    """应该能注册和获取 sink（任意 callable）。"""
    registry = SinkRegistry()

    sink = lambda n: True
    registry.register("console", sink)

    assert registry.get("console") is sink


def test_get_sink_not_found():
    """获取不存在的 sink 应该返回 None。"""
    registry = SinkRegistry()
    assert registry.get("nonexistent") is None


def test_list_sink_names():
    """应该能列出所有 sink 名称。"""
    registry = SinkRegistry()

    registry.register("console", lambda n: True)
    registry.register("webhook", lambda n: True)

    names = registry.list()
    assert "console" in names
    assert "webhook" in names
