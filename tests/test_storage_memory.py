"""
测试内存存储实现。
"""
from datetime import datetime

from marmot.storage.memory import MemoryStorage
from marmot.domain.models.events import AlertEvent, RunRecord, Notification
from marmot.domain.models.enums import AlertState, Severity, RunStatus


def _make_event(**overrides) -> AlertEvent:
    """创建测试用 AlertEvent。"""
    defaults = dict(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
        severity=Severity.WARNING.value,
        message="",
        labels={},
        fired_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    return AlertEvent(**defaults)


# ── AlertEvent CRUD ─────────────────────────────────────


def test_create_alert_event():
    """应该能创建告警事件。"""
    storage = MemoryStorage()
    event = _make_event()
    result = storage.create_alert_event(event)
    
    assert result.id is not None
    assert result.rule_name == "test_rule"
    assert result.dedup_key == "test_key"
    assert result.state == AlertState.PENDING.value


def test_get_alert():
    """应该能通过 ID 获取告警事件。"""
    storage = MemoryStorage()
    event = storage.create_alert_event(_make_event())
    
    found = storage.get_alert(event.id)
    assert found is not None
    assert found.id == event.id


def test_get_alert_not_found():
    """获取不存在的 ID 应该返回 None。"""
    storage = MemoryStorage()
    assert storage.get_alert(999) is None


def test_get_active_alert():
    """应该能通过 dedup_key 获取活跃告警。"""
    storage = MemoryStorage()
    storage.create_alert_event(_make_event(dedup_key="cpu:server1"))
    
    found = storage.get_active_alert("cpu:server1")
    assert found is not None
    assert found.dedup_key == "cpu:server1"


def test_get_active_alert_resolved():
    """已恢复的告警不应该被 get_active_alert 找到。"""
    storage = MemoryStorage()
    storage.create_alert_event(_make_event(
        dedup_key="cpu:server1",
        state=AlertState.RESOLVED.value,
    ))
    
    assert storage.get_active_alert("cpu:server1") is None


def test_get_active_alert_not_found():
    """不存在的 dedup_key 应该返回 None。"""
    storage = MemoryStorage()
    assert storage.get_active_alert("nonexistent") is None


def test_update_alert_event():
    """应该能更新告警事件。"""
    storage = MemoryStorage()
    event = storage.create_alert_event(_make_event())
    
    event.state = AlertState.FIRING.value
    event.consecutive_hits = 3
    storage.update_alert_event(event)
    
    updated = storage.get_alert(event.id)
    assert updated.state == AlertState.FIRING.value
    assert updated.consecutive_hits == 3


def test_update_alert_event_not_found():
    """更新不存在的 ID 应该抛出异常。"""
    storage = MemoryStorage()
    event = _make_event()
    event.id = 999
    
    import pytest
    with pytest.raises(ValueError):
        storage.update_alert_event(event)


def test_list_active_alerts():
    """应该能列出活跃告警。"""
    storage = MemoryStorage()
    storage.create_alert_event(_make_event(dedup_key="key1", state=AlertState.FIRING.value))
    storage.create_alert_event(_make_event(dedup_key="key2", state=AlertState.PENDING.value))
    storage.create_alert_event(_make_event(dedup_key="key3", state=AlertState.RESOLVED.value))
    
    active = storage.list_active_alerts()
    assert len(active) == 2


def test_list_alert_history():
    """应该能列出已恢复的告警历史。"""
    storage = MemoryStorage()
    storage.create_alert_event(_make_event(dedup_key="key1", state=AlertState.FIRING.value))
    storage.create_alert_event(_make_event(dedup_key="key2", state=AlertState.RESOLVED.value))
    
    history = storage.list_alert_history()
    assert len(history) == 1


# ── RunRecord CRUD ──────────────────────────────────────


def test_create_run():
    """应该能创建运行记录。"""
    storage = MemoryStorage()
    run = RunRecord(
        rule_name="backup_job",
        dedup_key="backup_job",
        status=RunStatus.SUCCESS.value,
        message="done",
        labels={},
        started_at=datetime.utcnow(),
    )
    
    result = storage.create_run(run)
    assert result.id is not None
    assert result.rule_name == "backup_job"


def test_get_run():
    """应该能通过 ID 获取运行记录。"""
    storage = MemoryStorage()
    run = storage.create_run(RunRecord(
        rule_name="backup_job",
        dedup_key="backup_job",
        status=RunStatus.SUCCESS.value,
        labels={},
        started_at=datetime.utcnow(),
    ))
    
    found = storage.get_run(run.id)
    assert found is not None
    assert found.id == run.id


def test_get_latest_run():
    """应该能通过 dedup_key 获取最近一条运行记录。"""
    storage = MemoryStorage()
    storage.create_run(RunRecord(
        rule_name="backup_job",
        dedup_key="backup_job",
        status=RunStatus.FAILED.value,
        labels={},
        started_at=datetime.utcnow(),
    ))
    storage.create_run(RunRecord(
        rule_name="backup_job",
        dedup_key="backup_job",
        status=RunStatus.SUCCESS.value,
        labels={},
        started_at=datetime.utcnow(),
    ))
    
    latest = storage.get_latest_run("backup_job")
    assert latest is not None
    assert latest.status == RunStatus.SUCCESS.value


def test_list_runs():
    """应该能列出运行记录。"""
    storage = MemoryStorage()
    storage.create_run(RunRecord(
        rule_name="job1",
        dedup_key="job1",
        status=RunStatus.SUCCESS.value,
        labels={},
        started_at=datetime.utcnow(),
    ))
    storage.create_run(RunRecord(
        rule_name="job2",
        dedup_key="job2",
        status=RunStatus.FAILED.value,
        labels={},
        started_at=datetime.utcnow(),
    ))
    
    runs = storage.list_runs()
    assert len(runs) == 2


# ── Notification ────────────────────────────────────────


def test_record_notification():
    """应该能记录通知。"""
    storage = MemoryStorage()
    event = storage.create_alert_event(_make_event())
    
    n = Notification(
        alert_event_id=event.id,
        rule_name="test_rule",
        dedup_key="test_key",
        status="sent",
        state=AlertState.FIRING.value,
        severity=Severity.WARNING.value,
        message="CPU high",
        labels={},
        stage="threshold",
        notifier_name="console",
        sent_at=datetime.utcnow(),
    )
    
    n_id = storage.record_notification(n)
    assert n_id is not None


def test_list_notifications():
    """应该能列出通知记录。"""
    storage = MemoryStorage()
    event = storage.create_alert_event(_make_event())
    
    n = Notification(
        alert_event_id=event.id,
        rule_name="test_rule",
        dedup_key="test_key",
        status="sent",
        state=AlertState.FIRING.value,
        severity=Severity.WARNING.value,
        message="CPU high",
        labels={},
        stage="threshold",
        notifier_name="console",
        sent_at=datetime.utcnow(),
    )
    storage.record_notification(n)
    
    notifications = storage.list_notifications(alert_event_id=event.id)
    assert len(notifications) == 1
