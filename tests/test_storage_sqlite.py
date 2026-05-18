"""
SQLiteStorage 专属测试。

覆盖持久化特性、WAL pragma、close、None 字段往返、labels JSON 往返。
"""
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marmot.storage.sqlite import SQLiteStorage
from marmot.domain.models.events import AlertEvent, RunRecord, Notification
from marmot.domain.models.enums import (
    AlertState, Severity, AlertStage, RunStatus, NotificationStatus,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def storage(db_path: Path) -> SQLiteStorage:
    s = SQLiteStorage(db_path)
    yield s
    s.close()


def test_memory_mode():
    """`:memory:` 模式可以正常使用。"""
    s = SQLiteStorage(":memory:")
    event = AlertEvent(
        rule_name="r", dedup_key="k", state=AlertState.FIRING,
        fired_at=datetime.now(UTC),
    )
    result = s.create_alert_event(event)
    assert result.id == 1
    s.close()


def test_wal_mode_on_file(db_path: Path):
    """文件模式下启用 WAL。"""
    s = SQLiteStorage(db_path)
    row = s._conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0] == "wal"
    s.close()


def test_close_then_error(storage: SQLiteStorage):
    """close 后操作应该报错。"""
    storage.close()
    with pytest.raises(Exception):
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k", state=AlertState.PENDING,
            fired_at=datetime.now(UTC),
        ))


def test_persistence_across_reopen(db_path: Path):
    """写入 → 关闭 → 重新打开 → 数据仍在。"""
    s1 = SQLiteStorage(db_path)
    s1.create_alert_event(AlertEvent(
        rule_name="cpu_high", dedup_key="cpu:host1",
        state=AlertState.FIRING, severity=Severity.ERROR,
        fired_at=datetime.now(UTC),
    ))
    s1.close()

    s2 = SQLiteStorage(db_path)
    alerts = s2.list_active_alerts()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "cpu_high"
    assert alerts[0].severity == Severity.ERROR
    s2.close()


def test_none_fields_roundtrip(storage: SQLiteStorage):
    """None 字段能正确往返。"""
    event = AlertEvent(
        rule_name="test", dedup_key="k",
        state=AlertState.PENDING,
        severity=None,
        stage=None,
        current_value=None,
        resolved_at=None,
        silenced_until=None,
        escalated_at=None,
        fired_at=datetime.now(UTC),
    )
    created = storage.create_alert_event(event)
    loaded = storage.get_alert(created.id)

    assert loaded.severity is None
    assert loaded.stage is None
    assert loaded.current_value is None
    assert loaded.resolved_at is None
    assert loaded.silenced_until is None
    assert loaded.escalated_at is None


def test_labels_json_roundtrip(storage: SQLiteStorage):
    """labels 字典能正确序列化和反序列化。"""
    labels = {"host": "server1", "region": "us-east", "count": 42}
    event = AlertEvent(
        rule_name="r", dedup_key="k", state=AlertState.FIRING,
        labels=labels, fired_at=datetime.now(UTC),
    )
    storage.create_alert_event(event)
    loaded = storage.get_alert(event.id)
    assert loaded.labels == labels


def test_labels_unicode(storage: SQLiteStorage):
    """labels 支持中文等 Unicode 字符。"""
    labels = {"主机": "服务器1", "区域": "华北"}
    event = AlertEvent(
        rule_name="r", dedup_key="k", state=AlertState.FIRING,
        labels=labels, fired_at=datetime.now(UTC),
    )
    storage.create_alert_event(event)
    loaded = storage.get_alert(event.id)
    assert loaded.labels == labels


def test_update_alert_not_found(storage: SQLiteStorage):
    """update 不存在的 id 抛 ValueError。"""
    event = AlertEvent(
        rule_name="r", dedup_key="k", state=AlertState.FIRING,
        fired_at=datetime.now(UTC),
    )
    event.id = 999
    with pytest.raises(ValueError):
        storage.update_alert_event(event)


def test_update_run_not_found(storage: SQLiteStorage):
    """update 不存在的 run id 抛 ValueError。"""
    run = RunRecord(
        rule_name="j", dedup_key="j", status=RunStatus.SUCCESS,
        started_at=datetime.now(UTC),
    )
    run.id = 999
    with pytest.raises(ValueError):
        storage.update_run(run)


def test_enum_roundtrip(storage: SQLiteStorage):
    """枚举字段能正确往返为枚举类型。"""
    now = datetime.now(UTC)
    event = AlertEvent(
        rule_name="r", dedup_key="k",
        state=AlertState.ESCALATED,
        severity=Severity.CRITICAL,
        stage=AlertStage.THRESHOLD,
        fired_at=now,
    )
    storage.create_alert_event(event)
    loaded = storage.get_alert(event.id)

    assert loaded.state is AlertState.ESCALATED
    assert loaded.severity is Severity.CRITICAL
    assert loaded.stage is AlertStage.THRESHOLD

    # RunRecord
    run = RunRecord(
        rule_name="j", dedup_key="j", status=RunStatus.FAILED,
        started_at=now,
    )
    storage.create_run(run)
    loaded_run = storage.get_run(run.id)
    assert loaded_run.status is RunStatus.FAILED

    # Notification
    n = Notification(
        alert_event_id=event.id, rule_name="r", dedup_key="k",
        status=NotificationStatus.SENT, state=AlertState.FIRING,
        severity=Severity.WARNING, stage=AlertStage.HEARTBEAT,
        sink_name="test", sent_at=now,
    )
    storage.record_notification(n)
    loaded_n = storage.list_notifications(alert_event_id=event.id)[0]
    assert loaded_n.status is NotificationStatus.SENT
    assert loaded_n.state is AlertState.FIRING
    assert loaded_n.severity is Severity.WARNING
    assert loaded_n.stage is AlertStage.HEARTBEAT
