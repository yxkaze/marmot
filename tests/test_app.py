"""Tests for Marmot core: report, fire, ping, job, resolve."""
from __future__ import annotations

import time
import pytest

from marmot.models import (
    AlertState, AlertEvent, ThresholdRule, ThresholdLevel,
    Rule, RunRecord, Notification,
    Severity, AlertStage, RunStatus,
)
from marmot.storage import SQLiteStorage
from marmot.app import MarmotApp
from marmot.notifiers import ConsoleNotifier, Notifier


class FakeNotifier(Notifier):
    """Capture all sent notifications for assertion."""
    def __init__(self):
        self.sent: list[Notification] = []

    def send(self, n: Notification) -> bool:
        self.sent.append(n)
        return True


@pytest.fixture
def app():
    a = MarmotApp(":memory:")
    fake = FakeNotifier()
    a.register_notifier("fake", fake)
    a.register_notifier("console", ConsoleNotifier())
    return a


class TestReport:
    def test_no_rule_skips(self, app):
        result = app.report("nonexistent", 99.0)
        assert result is None

    def test_single_hit_fires(self, app):
        app.register_threshold_rule(ThresholdRule(
            name="cpu",
            thresholds=[ThresholdLevel(value=80, severity="warning")],
            consecutive_count=1,
            notify_targets=["fake"],
        ))
        event = app.report("cpu", 90.0)
        assert event is not None
        assert event.state == AlertState.FIRING.value
        assert len(app.notifiers["fake"].sent) == 1

    def test_consecutive_count(self, app):
        app.register_threshold_rule(ThresholdRule(
            name="cpu",
            thresholds=[ThresholdLevel(value=80, severity="critical")],
            consecutive_count=3,
            notify_targets=["fake"],
        ))
        # First two hits → pending
        e1 = app.report("cpu", 90.0)
        assert e1.state == AlertState.PENDING.value
        assert len(app.notifiers["fake"].sent) == 0

        e2 = app.report("cpu", 91.0)
        assert e2.state == AlertState.PENDING.value
        assert len(app.notifiers["fake"].sent) == 0

        # Third hit → fires
        e3 = app.report("cpu", 92.0)
        assert e3.state == AlertState.FIRING.value
        assert len(app.notifiers["fake"].sent) == 1

    def test_normal_value_resolves(self, app):
        app.register_threshold_rule(ThresholdRule(
            name="cpu",
            thresholds=[ThresholdLevel(value=80, severity="warning")],
            consecutive_count=1,
            notify_targets=["fake"],
        ))
        # Fire
        app.report("cpu", 90.0)
        app.notifiers["fake"].sent.clear()

        # Normal value → resolves
        event = app.report("cpu", 50.0)
        assert event is not None
        assert event.state == AlertState.RESOLVED.value
        assert len(app.notifiers["fake"].sent) == 1

    def test_dedup_by_labels(self, app):
        app.register_threshold_rule(ThresholdRule(
            name="cpu",
            thresholds=[ThresholdLevel(value=80, severity="warning")],
            consecutive_count=1,
            notify_targets=["fake"],
        ))
        e1 = app.report("cpu", 90.0, labels={"host": "a"})
        e2 = app.report("cpu", 90.0, labels={"host": "b"})
        assert e1.dedup_key != e2.dedup_key
        # Two separate alerts created
        active = app.storage.list_active_alerts()
        assert len(active) == 2

    def test_multi_level_threshold(self, app):
        app.register_threshold_rule(ThresholdRule(
            name="cpu",
            thresholds=[
                ThresholdLevel(value=80, severity="warning"),
                ThresholdLevel(value=95, severity="critical"),
            ],
            consecutive_count=1,
            notify_targets=["fake"],
        ))
        e1 = app.report("cpu", 85.0)
        assert e1.severity == "warning"

        # Upgrade severity while firing
        e2 = app.report("cpu", 97.0)
        assert e2.severity == "critical"


class TestFire:
    def test_manual_fire(self, app):
        event = app.fire("manual_alert", "something broke", severity="critical",
                        notify_targets=["fake"])
        assert event.state == AlertState.FIRING.value
        assert event.stage == AlertStage.MANUAL.value
        assert len(app.notifiers["fake"].sent) == 1

    def test_fire_idempotent(self, app):
        e1 = app.fire("dup", "first", notify_targets=["fake"])
        app.notifiers["fake"].sent.clear()
        e2 = app.fire("dup", "updated", notify_targets=["fake"])
        assert e1.id == e2.id
        assert e2.message == "updated"


class TestPing:
    def test_ping_resolves_alert(self, app):
        app.register_rule(Rule.from_inputs(
            name="heartbeat", notify="fake",
        ))
        # Fire first
        app.fire("heartbeat", "missed", labels={"worker": "1"},
                 notify_targets=["fake"])
        app.notifiers["fake"].sent.clear()

        # Ping should resolve
        app.ping("heartbeat", labels={"worker": "1"})
        active = app.storage.list_active_alerts()
        assert len(active) == 0


class TestJob:
    def test_job_success(self, app):
        app.register_rule(Rule.from_inputs(
            name="pipeline", notify="fake",
        ))

        @app.job("pipeline", notify="fake")
        def ok_job():
            return 42

        result = ok_job()
        assert result == 42
        runs = app.storage.list_runs()
        assert len(runs) == 1
        assert runs[0].status == RunStatus.SUCCESS.value

    def test_job_failure_fires_alert(self, app):
        @app.job("fail_job", notify="fake")
        def bad_job():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            bad_job()

        assert len(app.notifiers["fake"].sent) >= 1
        runs = app.storage.list_runs()
        assert runs[0].status == RunStatus.FAILED.value
        assert "boom" in runs[0].error


class TestResolve:
    def test_manual_resolve(self, app):
        app.fire("x", "fired", notify_targets=["fake"])
        app.notifiers["fake"].sent.clear()
        event = app.resolve("x")
        assert event.state == AlertState.RESOLVED.value
        assert len(app.notifiers["fake"].sent) == 1

    def test_resolve_nonexistent(self, app):
        result = app.resolve("nonexistent")
        assert result is None


class TestModuleLevelAPI:
    def test_configure_and_use(self):
        import marmot as app_module

        # Reset singleton
        app_module._default_app = None

        a = app_module.configure(":memory:", start_escalation=False)
        a.register_notifier("console", ConsoleNotifier())
        app_module.register_threshold_rule(ThresholdRule(
            name="mem",
            thresholds=[ThresholdLevel(value=90, severity="warning")],
            consecutive_count=1,
            notify_targets=["console"],
        ))
        event = app_module.report("mem", 95.0)
        assert event.state == AlertState.FIRING.value

        app_module.shutdown()
        app_module._default_app = None


class TestStorage:
    def test_create_and_get_alert(self, app):
        e = AlertEvent(rule_name="test", dedup_key="test", state="firing")
        app.storage.create_alert_event(e)
        assert e.id is not None
        fetched = app.storage.get_alert(e.id)
        assert fetched.rule_name == "test"

    def test_active_alert_dedup(self, app):
        e1 = AlertEvent(rule_name="cpu", dedup_key="cpu:host=a", state="firing")
        app.storage.create_alert_event(e1)
        e2 = AlertEvent(rule_name="cpu", dedup_key="cpu:host=b", state="firing")
        app.storage.create_alert_event(e2)

        active = app.storage.list_active_alerts()
        assert len(active) == 2

        got = app.storage.get_active_alert("cpu:host=a")
        assert got is not None
        assert got.id == e1.id

    def test_run_lifecycle(self, app):
        r = RunRecord(rule_name="job", dedup_key="job", status="running")
        app.storage.create_run(r)
        assert r.id is not None

        r.status = "success"
        r.finished_at = r.started_at
        app.storage.update_run(r)

        got = app.storage.get_run(r.id)
        assert got.status == "success"

    def test_notification_record(self, app):
        n = Notification(
            alert_event_id=1, rule_name="test", dedup_key="test",
            status="sent", state="firing", message="test",
            severity="warning", labels={}, stage="firing",
            notifier_name="console",
        )
        app.storage.record_notification(n)
        notifs = app.storage.list_notifications()
        assert len(notifs) == 1
        assert notifs[0]["notifier_name"] == "console"
