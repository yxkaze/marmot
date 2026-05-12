"""
测试内存存储实现。
"""
import pytest
from datetime import datetime
from marmot.storage.memory import MemoryStorage
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState, Severity


def test_create_alert_event():
    """应该能创建告警事件。"""
    storage = MemoryStorage()
    event, created = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
        severity=Severity.WARNING.value,
    )
    
    assert created is True
    assert event.rule_name == "test_rule"
    assert event.dedup_key == "test_key"
    assert event.state == AlertState.PENDING.value


def test_get_existing_alert_event():
    """应该能获取已存在的事件。"""
    storage = MemoryStorage()
    event1, created1 = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
    )
    
    event2, created2 = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.FIRING.value,  # 这个值会被忽略
    )
    
    assert created1 is True
    assert created2 is False
    assert event1.id == event2.id


def test_update_alert_event():
    """应该能更新告警事件。"""
    storage = MemoryStorage()
    event, _ = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
    )
    
    storage.update_alert_event(event.id, state=AlertState.FIRING.value)
    
    updated = storage.get_alert_event(event.id)
    assert updated.state == AlertState.FIRING.value


def test_list_active_alerts():
    """应该能列出活跃告警。"""
    storage = MemoryStorage()
    
    # 创建活跃告警
    storage.get_or_create_alert_event(
        rule_name="rule1",
        dedup_key="key1",
        state=AlertState.FIRING.value,
    )
    storage.get_or_create_alert_event(
        rule_name="rule2",
        dedup_key="key2",
        state=AlertState.PENDING.value,
    )
    
    # 创建已恢复告警
    event3, _ = storage.get_or_create_alert_event(
        rule_name="rule3",
        dedup_key="key3",
        state=AlertState.RESOLVED.value,
    )
    
    active = storage.list_active_alerts()
    assert len(active) == 2
    
    active_rule1 = storage.list_active_alerts(rule_name="rule1")
    assert len(active_rule1) == 1


def test_create_run_record():
    """应该能创建运行记录。"""
    storage = MemoryStorage()
    now = datetime.utcnow()
    
    record_id = storage.create_run_record(
        rule_name="test_job",
        status="success",
        message="Job completed",
        started_at=now,
        finished_at=now,
    )
    
    assert record_id == 1
    
    records = storage.list_recent_runs()
    assert len(records) == 1
    assert records[0].rule_name == "test_job"


def test_create_notification():
    """应该能创建通知记录。"""
    storage = MemoryStorage()
    event, _ = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.FIRING.value,
    )
    
    now = datetime.utcnow()
    notification_id = storage.create_notification(
        alert_event_id=event.id,
        rule_name="test_rule",
        dedup_key="test_key",
        status="sent",
        state=AlertState.FIRING.value,
        notifier_name="console",
        sent_at=now,
    )
    
    # notification_id 应该是 event.id + 1（因为 event 使用了第一个 ID）
    assert notification_id == event.id + 1
    
    notifications = storage.list_notifications(alert_event_id=event.id)
    assert len(notifications) == 1
