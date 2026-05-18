"""
存储层共享契约测试。

用 parametrize 让 MemoryStorage 和 SQLiteStorage 跑同一份行为测试，
确保两者对 Protocol 的语义完全等价。
"""
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from marmot.storage.memory import MemoryStorage
from marmot.storage.sqlite import SQLiteStorage
from marmot.domain.models.events import AlertEvent, RunRecord, Notification
from marmot.domain.models.enums import (
    AlertState, Severity, AlertStage, RunStatus, NotificationStatus,
)


@pytest.fixture(params=["memory", "sqlite"])
def storage(request, tmp_path) -> Iterator:
    """提供两种存储实现。"""
    if request.param == "memory":
        yield MemoryStorage()
    else:
        s = SQLiteStorage(tmp_path / "contract.db")
        yield s
        s.close()


def _now():
    return datetime.now(UTC)


# ── AlertEvent ─────────────────────────────────────────────


class TestAlertEventContract:
    def test_create_and_get(self, storage):
        event = AlertEvent(
            rule_name="cpu", dedup_key="cpu:h1",
            state=AlertState.PENDING, severity=Severity.WARNING,
            fired_at=_now(),
        )
        created = storage.create_alert_event(event)
        assert created.id is not None

        loaded = storage.get_alert(created.id)
        assert loaded is not None
        assert loaded.rule_name == "cpu"
        assert loaded.dedup_key == "cpu:h1"

    def test_get_not_found(self, storage):
        assert storage.get_alert(999) is None

    def test_get_active_alert(self, storage):
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k1",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        assert storage.get_active_alert("k1") is not None
        assert storage.get_active_alert("nonexistent") is None

    def test_get_active_alert_ignores_resolved(self, storage):
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k1",
            state=AlertState.RESOLVED, fired_at=_now(),
        ))
        assert storage.get_active_alert("k1") is None

    def test_get_active_alert_returns_latest_when_multiple(self, storage):
        """同一 dedup_key 存在多条活跃记录时，返回最新创建的（id 最大）。"""
        first = storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        second = storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k",
            state=AlertState.PENDING, fired_at=_now(),
        ))
        active = storage.get_active_alert("k")
        assert active is not None
        assert active.id == second.id
        assert active.id != first.id

    def test_update(self, storage):
        event = storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k",
            state=AlertState.PENDING, fired_at=_now(),
        ))
        event.state = AlertState.FIRING
        event.consecutive_hits = 5
        storage.update_alert_event(event)

        loaded = storage.get_alert(event.id)
        assert loaded.state == AlertState.FIRING
        assert loaded.consecutive_hits == 5

    def test_update_not_found(self, storage):
        event = AlertEvent(
            rule_name="r", dedup_key="k",
            state=AlertState.FIRING, fired_at=_now(),
        )
        event.id = 999
        with pytest.raises(ValueError):
            storage.update_alert_event(event)

    def test_list_active_alerts(self, storage):
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k1",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k2",
            state=AlertState.PENDING, fired_at=_now(),
        ))
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k3",
            state=AlertState.RESOLVED, fired_at=_now(),
        ))
        active = storage.list_active_alerts()
        assert len(active) == 2

    def test_list_alert_history(self, storage):
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k1",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k2",
            state=AlertState.RESOLVED, fired_at=_now(),
        ))
        history = storage.list_alert_history()
        assert len(history) == 1


# ── RunRecord ──────────────────────────────────────────────


class TestRunRecordContract:
    def test_create_and_get(self, storage):
        run = RunRecord(
            rule_name="job1", dedup_key="job1",
            status=RunStatus.SUCCESS, started_at=_now(),
        )
        created = storage.create_run(run)
        assert created.id is not None

        loaded = storage.get_run(created.id)
        assert loaded is not None
        assert loaded.rule_name == "job1"

    def test_get_not_found(self, storage):
        assert storage.get_run(999) is None

    def test_update(self, storage):
        run = storage.create_run(RunRecord(
            rule_name="j", dedup_key="j",
            status=RunStatus.RUNNING, started_at=_now(),
        ))
        run.status = RunStatus.SUCCESS
        run.finished_at = _now()
        storage.update_run(run)

        loaded = storage.get_run(run.id)
        assert loaded.status == RunStatus.SUCCESS
        assert loaded.finished_at is not None

    def test_update_not_found(self, storage):
        run = RunRecord(
            rule_name="j", dedup_key="j",
            status=RunStatus.SUCCESS, started_at=_now(),
        )
        run.id = 999
        with pytest.raises(ValueError):
            storage.update_run(run)

    def test_get_latest_run(self, storage):
        storage.create_run(RunRecord(
            rule_name="j", dedup_key="j",
            status=RunStatus.FAILED, started_at=datetime(2024, 1, 1, tzinfo=UTC),
        ))
        storage.create_run(RunRecord(
            rule_name="j", dedup_key="j",
            status=RunStatus.SUCCESS, started_at=datetime(2024, 1, 2, tzinfo=UTC),
        ))
        latest = storage.get_latest_run("j")
        assert latest is not None
        assert latest.status == RunStatus.SUCCESS

    def test_list_runs(self, storage):
        storage.create_run(RunRecord(
            rule_name="j1", dedup_key="j1",
            status=RunStatus.SUCCESS, started_at=_now(),
        ))
        storage.create_run(RunRecord(
            rule_name="j2", dedup_key="j2",
            status=RunStatus.FAILED, started_at=_now(),
        ))
        runs = storage.list_runs()
        assert len(runs) == 2

    def test_list_runs_limit(self, storage):
        for i in range(5):
            storage.create_run(RunRecord(
                rule_name=f"j{i}", dedup_key=f"j{i}",
                status=RunStatus.SUCCESS, started_at=_now(),
            ))
        runs = storage.list_runs(limit=3)
        assert len(runs) == 3


# ── Notification ───────────────────────────────────────────


class TestNotificationContract:
    def test_record_and_list(self, storage):
        event = storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        n = Notification(
            alert_event_id=event.id, rule_name="r", dedup_key="k",
            status=NotificationStatus.SENT, state=AlertState.FIRING,
            severity=Severity.WARNING, sink_name="console",
            sent_at=_now(),
        )
        n_id = storage.record_notification(n)
        assert n_id is not None

        results = storage.list_notifications(alert_event_id=event.id)
        assert len(results) == 1
        assert results[0].sink_name == "console"

    def test_list_notifications_all(self, storage):
        event = storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        for i in range(3):
            storage.record_notification(Notification(
                alert_event_id=event.id, rule_name="r", dedup_key="k",
                status=NotificationStatus.SENT,
                sink_name=f"sink{i}", sent_at=_now(),
            ))
        all_notifs = storage.list_notifications()
        assert len(all_notifs) == 3

    def test_list_notifications_filter(self, storage):
        e1 = storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k1",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        e2 = storage.create_alert_event(AlertEvent(
            rule_name="r", dedup_key="k2",
            state=AlertState.FIRING, fired_at=_now(),
        ))
        storage.record_notification(Notification(
            alert_event_id=e1.id, rule_name="r", dedup_key="k1",
            status=NotificationStatus.SENT, sink_name="s", sent_at=_now(),
        ))
        storage.record_notification(Notification(
            alert_event_id=e2.id, rule_name="r", dedup_key="k2",
            status=NotificationStatus.SENT, sink_name="s", sent_at=_now(),
        ))
        assert len(storage.list_notifications(alert_event_id=e1.id)) == 1
        assert len(storage.list_notifications(alert_event_id=e2.id)) == 1
