"""
Domain models 测试。
"""

import pytest
from datetime import datetime, UTC, timedelta

from marmot.domain.models import (
    AlertState,
    Severity,
    AlertStage,
    RunStatus,
    NotificationStatus,
    AggregateFn,
    EscalationStep,
    ThresholdLevel,
    AggregateConfig,
    Rule,
    ThresholdRule,
    AlertEvent,
    RunRecord,
    Notification,
    utcnow,
    to_iso,
    from_iso,
    parse_duration,
    build_dedup_key,
    normalize_notify,
)


class TestEnums:
    """枚举类测试"""
    
    def test_alert_state_values(self):
        """测试告警状态枚举值"""
        assert AlertState.PENDING.value == "pending"
        assert AlertState.FIRING.value == "firing"
        assert AlertState.SILENCED.value == "silenced"
        assert AlertState.ESCALATED.value == "escalated"
        assert AlertState.RESOLVING.value == "resolving"
        assert AlertState.RESOLVED.value == "resolved"
    
    def test_severity_values(self):
        """测试严重程度枚举值"""
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"
    
    def test_alert_stage_values(self):
        """测试触发机制枚举值"""
        assert AlertStage.THRESHOLD.value == "threshold"
        assert AlertStage.TIMEOUT.value == "timeout"
        assert AlertStage.HEARTBEAT.value == "heartbeat"
        assert AlertStage.MANUAL.value == "manual"
    
    def test_run_status_values(self):
        """测试任务状态枚举值"""
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.SUCCESS.value == "success"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.TIMEOUT.value == "timeout"
    
    def test_notification_status_values(self):
        """测试通知状态枚举值"""
        assert NotificationStatus.PENDING.value == "pending"
        assert NotificationStatus.SENT.value == "sent"
        assert NotificationStatus.FAILED.value == "failed"
    
    def test_aggregate_fn_values(self):
        """测试聚合函数枚举值"""
        assert AggregateFn.AVG.value == "avg"
        assert AggregateFn.MAX.value == "max"
        assert AggregateFn.MIN.value == "min"
        assert AggregateFn.SUM.value == "sum"
        assert AggregateFn.COUNT.value == "count"


class TestRuleClasses:
    """Rule 相关数据类测试"""
    
    def test_escalation_step(self):
        """测试升级步骤"""
        # 不指定 severity
        step = EscalationStep(after_seconds=300, notify=["sms", "phone"])
        assert step.after_seconds == 300
        assert step.notify == ["sms", "phone"]
        assert step.severity is None
        
        # 用字符串指定 severity
        step2 = EscalationStep(after_seconds=600, severity="critical", notify=["manager"])
        assert step2.severity == Severity.CRITICAL
        
        # 用枚举指定 severity
        step3 = EscalationStep(after_seconds=900, severity=Severity.ERROR)
        assert step3.severity == Severity.ERROR
    
    def test_threshold_level(self):
        """测试阈值等级"""
        # 用枚举
        level = ThresholdLevel(value=80, severity=Severity.WARNING)
        assert level.value == 80
        assert level.severity == Severity.WARNING
        assert level.notify == []
        assert level.silence_seconds == 0
        
        # 用字符串
        level2 = ThresholdLevel(value=95, severity="critical")
        assert level2.severity == Severity.CRITICAL
    
    def test_aggregate_config(self):
        """测试聚合配置"""
        # 用枚举
        config = AggregateConfig(fn=AggregateFn.AVG, window=300)
        assert config.fn == AggregateFn.AVG
        assert config.window == 300
        
        # 用字符串
        config2 = AggregateConfig(fn="max", window=60)
        assert config2.fn == AggregateFn.MAX
    
    def test_rule(self):
        """测试通用规则"""
        rule = Rule(
            name="heartbeat",
            expected_interval_seconds=30,
            timeout_seconds=60,
            silence_seconds=300,
        )
        assert rule.name == "heartbeat"
        assert rule.expected_interval_seconds == 30
        assert rule.timeout_seconds == 60
        assert rule.silence_seconds == 300
        assert rule.severity == Severity.ERROR  # 默认值
        
        # 用字符串设置 severity
        rule2 = Rule(name="test", severity="warning")
        assert rule2.severity == Severity.WARNING
    
    def test_threshold_rule_evaluate(self):
        """测试阈值规则评估"""
        rule = ThresholdRule(
            name="cpu_usage",
            thresholds=[
                ThresholdLevel(value=80, severity=Severity.WARNING),
                ThresholdLevel(value=95, severity=Severity.CRITICAL),
            ],
        )
        
        # 未超过阈值
        assert rule.evaluate(50.0) is None
        
        # 超过 warning
        level = rule.evaluate(85.0)
        assert level is not None
        assert level.value == 80
        assert level.severity == Severity.WARNING
        
        # 超过 critical
        level = rule.evaluate(96.0)
        assert level is not None
        assert level.value == 95
        assert level.severity == Severity.CRITICAL


class TestEventClasses:
    """Event 相关数据类测试"""
    
    def test_alert_event(self):
        """测试告警事件"""
        event = AlertEvent(
            rule_name="cpu_usage",
            dedup_key="cpu_usage:host=prod-1",
            state=AlertState.FIRING,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
        )
        assert event.rule_name == "cpu_usage"
        assert event.dedup_key == "cpu_usage:host=prod-1"
        assert event.state == AlertState.FIRING
        assert event.severity == Severity.ERROR
        assert event.stage == AlertStage.THRESHOLD
        assert event.consecutive_hits == 0
    
    def test_run_record(self):
        """测试任务执行记录"""
        now = datetime.now(UTC)
        record = RunRecord(
            rule_name="backup",
            status=RunStatus.SUCCESS,
            started_at=now,
            finished_at=now + timedelta(seconds=5),
        )
        assert record.status == RunStatus.SUCCESS
        assert record.duration_ms == pytest.approx(5000.0, rel=0.01)
    
    def test_run_record_not_finished(self):
        """测试未结束的任务记录"""
        record = RunRecord(rule_name="backup")
        assert record.duration_ms == 0.0
    
    def test_notification(self):
        """测试通知记录"""
        notification = Notification(
            alert_event_id=1,
            rule_name="cpu_usage",
            notifier_name="dingtalk",
            status=NotificationStatus.SENT,
        )
        assert notification.alert_event_id == 1
        assert notification.notifier_name == "dingtalk"
        assert notification.status == NotificationStatus.SENT


class TestTimeUtils:
    """时间工具测试"""
    
    def test_utcnow(self):
        """测试获取 UTC 时间"""
        now = utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo == UTC
    
    def test_to_iso(self):
        """测试 datetime 转 ISO 字符串"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        iso = to_iso(dt)
        assert iso == "2024-01-01T12:00:00+00:00"
    
    def test_to_iso_none(self):
        """测试 None 转 ISO"""
        assert to_iso(None) is None
    
    def test_from_iso(self):
        """测试 ISO 字符串转 datetime"""
        dt = from_iso("2024-01-01T12:00:00+00:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1
    
    def test_from_iso_none(self):
        """测试空字符串转 datetime"""
        assert from_iso(None) is None
        assert from_iso("") is None
    
    def test_parse_duration_number(self):
        """测试解析数字时长"""
        assert parse_duration(300) == 300.0
        assert parse_duration(300.5) == 300.5
    
    def test_parse_duration_string(self):
        """测试解析字符串时长"""
        assert parse_duration("300") == 300.0
        assert parse_duration("5m") == 300.0
        assert parse_duration("2h") == 7200.0
        assert parse_duration("1d") == 86400.0
        assert parse_duration("500ms") == 0.5
    
    def test_parse_duration_none(self):
        """测试解析 None"""
        assert parse_duration(None) is None
    
    def test_parse_duration_invalid(self):
        """测试解析无效字符串"""
        assert parse_duration("invalid") is None


class TestKeys:
    """键工具测试"""
    
    def test_build_dedup_key_no_labels(self):
        """测试无标签的去重键"""
        key = build_dedup_key("heartbeat")
        assert key == "heartbeat"
    
    def test_build_dedup_key_with_labels(self):
        """测试有标签的去重键"""
        key = build_dedup_key("cpu_usage", {"host": "prod-1", "region": "us-east"})
        assert key == "cpu_usage:host=prod-1,region=us-east"
    
    def test_build_dedup_key_sorted(self):
        """测试标签排序"""
        key1 = build_dedup_key("cpu", {"b": "2", "a": "1"})
        key2 = build_dedup_key("cpu", {"a": "1", "b": "2"})
        assert key1 == key2
        assert key1 == "cpu:a=1,b=2"
    
    def test_normalize_notify_none(self):
        """测试规范化 None"""
        assert normalize_notify(None) == []
    
    def test_normalize_notify_string(self):
        """测试规范化字符串"""
        assert normalize_notify("dingtalk") == ["dingtalk"]
        assert normalize_notify("dingtalk, email, sms") == ["dingtalk", "email", "sms"]
    
    def test_normalize_notify_list(self):
        """测试规范化列表"""
        assert normalize_notify(["dingtalk", "email"]) == ["dingtalk", "email"]
    
    def test_normalize_notify_with_spaces(self):
        """测试规范化带空格"""
        assert normalize_notify("  dingtalk  ,  email  ") == ["dingtalk", "email"]
