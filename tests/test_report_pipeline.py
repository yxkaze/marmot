"""
测试完整的 report() 管线。
"""
from datetime import datetime

from marmot import configure, shutdown
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import Severity


def test_report_triggers_alert():
    """连续 report 超过阈值应该触发告警。"""
    app = configure(storage="memory")
    from marmot.notifiers.console import ConsoleNotifier
    app.register_notifier("console", ConsoleNotifier())
    
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=0,
        notify_targets=["console"],
    )
    app.register_threshold_rule(rule)
    
    app.report("cpu_high", 85.0, {"host": "server1"})
    app.report("cpu_high", 86.0, {"host": "server1"})
    app.report("cpu_high", 87.0, {"host": "server1"})
    
    alerts = app.list_active_alerts()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "cpu_high"
    
    shutdown()


def test_report_resolves_alert():
    """连续 report 低于阈值应该恢复告警。"""
    app = configure(storage="memory")
    from marmot.notifiers.console import ConsoleNotifier
    app.register_notifier("console", ConsoleNotifier())
    
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=2,
        silence_seconds=0,
        notify_targets=["console"],
    )
    app.register_threshold_rule(rule)
    
    # 触发
    app.report("cpu_high", 85.0, {"host": "server1"})
    app.report("cpu_high", 86.0, {"host": "server1"})
    
    alerts = app.list_active_alerts()
    assert len(alerts) == 1
    
    # 恢复
    app.report("cpu_high", 75.0, {"host": "server1"})
    app.report("cpu_high", 74.0, {"host": "server1"})
    
    alerts = app.list_active_alerts()
    assert len(alerts) == 0
    
    shutdown()


def test_report_unknown_rule():
    """上报未知规则应该报错。"""
    app = configure(storage="memory")
    
    import pytest
    with pytest.raises(ValueError, match="not found"):
        app.report("nonexistent", 85.0)
    
    shutdown()
