"""Tests for Marmot models."""
from __future__ import annotations

import time
import pytest

from marmot.models import (
    AlertState, Severity, AlertStage, RunStatus, NotificationStatus,
    Rule, ThresholdRule, ThresholdLevel, EscalationStep,
    AlertEvent, RunRecord, Notification,
    utcnow, to_iso, from_iso, parse_duration, build_dedup_key,
    json_dumps, json_loads, normalize_notify,
)


# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_utcnow_returns_aware(self):
        dt = utcnow()
        assert dt.tzinfo is not None

    def test_to_from_iso_roundtrip(self):
        dt = utcnow()
        assert from_iso(to_iso(dt)) == dt

    def test_to_iso_none(self):
        assert to_iso(None) is None

    def test_from_iso_none(self):
        assert from_iso(None) is None
        assert from_iso("") is None

    def test_parse_duration_seconds(self):
        assert parse_duration(10) == 10.0
        assert parse_duration("10") == 10.0
        assert parse_duration("10s") == 10.0

    def test_parse_duration_units(self):
        assert parse_duration("500ms") == pytest.approx(0.5)
        assert parse_duration("1m") == 60.0
        assert parse_duration("2h") == 7200.0
        assert parse_duration("1d") == 86400.0

    def test_parse_duration_none(self):
        assert parse_duration(None) is None

    def test_normalize_notify_string(self):
        assert normalize_notify("ding,email") == ["ding", "email"]
        assert normalize_notify("  ding , email  ") == ["ding", "email"]

    def test_normalize_notify_list(self):
        assert normalize_notify(["ding", "email"]) == ["ding", "email"]

    def test_normalize_notify_none(self):
        assert normalize_notify(None) == []

    def test_build_dedup_key(self):
        assert build_dedup_key("cpu") == "cpu"
        assert build_dedup_key("cpu", {"host": "a"}) == "cpu:host=a"
        # Sorted labels
        assert build_dedup_key("x", {"z": "1", "a": "2"}) == "x:a=2,z=1"

    def test_json_dumps_loads(self):
        data = {"key": "value", "n": 42}
        assert json_loads(json_dumps(data), {}) == data


# ───────────────────────────────────────────────────────────────────
# ThresholdRule
# ───────────────────────────────────────────────────────────────────

class TestThresholdRule:
    def test_evaluate_hit(self):
        rule = ThresholdRule(
            name="cpu",
            thresholds=[
                ThresholdLevel(value=80, severity="warning"),
                ThresholdLevel(value=95, severity="critical"),
            ],
        )
        assert rule.evaluate(50) is None
        assert rule.evaluate(80).severity == "warning"
        assert rule.evaluate(90).severity == "warning"
        assert rule.evaluate(95).severity == "critical"
        assert rule.evaluate(100).severity == "critical"

    def test_evaluate_empty(self):
        rule = ThresholdRule(name="empty", thresholds=[])
        assert rule.evaluate(99) is None


# ───────────────────────────────────────────────────────────────────
# AlertEvent
# ───────────────────────────────────────────────────────────────────

class TestAlertEvent:
    def test_to_dict_keys(self):
        e = AlertEvent(rule_name="test", dedup_key="test")
        d = e.to_dict()
        assert d["rule_name"] == "test"
        assert d["state"] == "pending"
        assert d["id"] is None
        assert "fired_at" in d
        assert "updated_at" in d

    def test_from_row(self):
        row = {
            "id": 1,
            "rule_name": "cpu",
            "dedup_key": "cpu:host=a",
            "state": "firing",
            "severity": "critical",
            "stage": "threshold",
            "message": "cpu=99",
            "labels": '{"host":"a"}',
            "current_value": 99.0,
            "consecutive_hits": 3,
            "consecutive_misses": 0,
            "fired_at": to_iso(utcnow()),
            "resolved_at": None,
            "silenced_until": None,
            "escalated_at": None,
            "last_notified_at": None,
            "notification_count": 1,
            "updated_at": to_iso(utcnow()),
        }
        e = AlertEvent.from_row(row)
        assert e.id == 1
        assert e.rule_name == "cpu"
        assert e.labels == {"host": "a"}
        assert e.current_value == 99.0


# ───────────────────────────────────────────────────────────────────
# RunRecord
# ───────────────────────────────────────────────────────────────────

class TestRunRecord:
    def test_duration_running(self):
        r = RunRecord(rule_name="job", dedup_key="job", status="running")
        assert r.duration_ms == 0.0

    def test_to_dict(self):
        r = RunRecord(rule_name="job", dedup_key="job", status="success")
        d = r.to_dict()
        assert d["status"] == "success"
        assert "duration_ms" in d


# ───────────────────────────────────────────────────────────────────
# Notification
# ───────────────────────────────────────────────────────────────────

class TestNotification:
    def test_to_dict(self):
        n = Notification(
            alert_event_id=1, rule_name="cpu", dedup_key="cpu",
            status="sent", state="firing", message="cpu=99",
            severity="critical", labels={}, stage="threshold",
            notifier_name="console",
        )
        d = n.to_dict()
        assert d["notifier_name"] == "console"
        assert d["severity"] == "critical"
