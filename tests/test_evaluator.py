"""
测试阈值评估器。
"""
import pytest
from datetime import datetime

from marmot.domain.evaluator import ThresholdEvaluator, Observation
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import Severity
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState


def test_hit_when_value_exceeds_threshold():
    """超过阈值应该 hit。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {"host": "server1"}, None)
    
    assert obs.hit is True
    assert obs.miss is False
    assert obs.matched_severity == Severity.WARNING


def test_miss_when_value_below_threshold():
    """低于阈值应该 miss。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 75.0, {"host": "server1"}, None)
    
    assert obs.hit is False
    assert obs.miss is True
    assert obs.matched_severity is None


def test_highest_severity_wins():
    """多个阈值匹配时，应该选最高严重程度。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
            ThresholdLevel(value=90.0, severity=Severity.ERROR),
            ThresholdLevel(value=95.0, severity=Severity.CRITICAL),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    
    obs1 = evaluator.evaluate(rule, 85.0, {}, None)
    assert obs1.matched_severity == Severity.WARNING
    
    obs2 = evaluator.evaluate(rule, 92.0, {}, None)
    assert obs2.matched_severity == Severity.ERROR
    
    obs3 = evaluator.evaluate(rule, 98.0, {}, None)
    assert obs3.matched_severity == Severity.CRITICAL


def test_dedup_key_from_labels():
    """应该根据规则名和标签生成 dedup_key。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {"host": "server1"}, None)
    
    assert obs.dedup_key == "cpu_high:host=server1"


def test_dedup_key_reused_from_prior_event():
    """有 prior_event 时应该复用其 dedup_key。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    prior = AlertEvent(
        id=1,
        rule_name="cpu_high",
        dedup_key="cpu_high:host=server1",
        state=AlertState.PENDING.value,
        labels={"host": "server1"},
        fired_at=datetime.utcnow(),
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {"host": "server1"}, prior)
    
    assert obs.dedup_key == "cpu_high:host=server1"


def test_notify_targets_from_matched_level():
    """应该返回匹配到的阈值等级的通知目标。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING, notify=["console"]),
            ThresholdLevel(value=90.0, severity=Severity.ERROR, notify=["console", "webhook"]),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    
    obs1 = evaluator.evaluate(rule, 85.0, {}, None)
    assert obs1.notify_targets == ["console"]
    
    obs2 = evaluator.evaluate(rule, 92.0, {}, None)
    assert obs2.notify_targets == ["console", "webhook"]


def test_notify_targets_fallback_to_rule():
    """匹配的等级没有指定 notify 时，应该用规则的 notify_targets。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console", "email"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {}, None)
    
    assert obs.notify_targets == ["console", "email"]
