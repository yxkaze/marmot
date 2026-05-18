"""
测试完整的 report() 管线。
"""
import sqlite3
from datetime import datetime

import pytest

from marmot import configure, shutdown
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import AlertStage, Severity
from marmot.storage.sqlite import SQLiteStorage


def test_report_triggers_alert():
    """连续 report 超过阈值应该触发告警。"""
    app = configure(storage="memory")
    from marmot.sinks.console import console_sink
    app.register_sink("console", console_sink)
    
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
    assert alerts[0].stage is AlertStage.THRESHOLD
    
    shutdown()


def test_report_resolves_alert():
    """连续 report 低于阈值应该恢复告警。"""
    app = configure(storage="memory")
    from marmot.sinks.console import console_sink
    app.register_sink("console", console_sink)
    
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
    
    with pytest.raises(ValueError, match="not found"):
        app.report("nonexistent", 85.0)
    
    shutdown()


def test_report_with_sqlite_and_silence(tmp_path):
    """SQLite + silence_seconds 应正常持久化静默时间。"""
    app = configure(storage=SQLiteStorage(tmp_path / "marmot.db"))
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=1,
        silence_seconds=300,
    )
    app.register_threshold_rule(rule)

    app.report("cpu_high", 85.0, {"host": "server1"})
    app.report("cpu_high", 86.0, {"host": "server1"})

    alerts = app.list_active_alerts()
    assert len(alerts) == 1
    assert alerts[0].silenced_until is not None

    shutdown()
    with pytest.raises(sqlite3.ProgrammingError):
        app.storage.list_active_alerts()
