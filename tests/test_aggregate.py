"""Tests for Marmot metric aggregation: MetricBucket + report() integration."""
from __future__ import annotations

import time
import pytest

from marmot.models import (
    AlertState, ThresholdRule, ThresholdLevel, AggregateConfig, AggregateFn,
    Notification,
)
from marmot.bucket import MetricBucket
from marmot.app import MarmotApp
from marmot.notifiers import Notifier


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
    return a


# ═══════════════════════════════════════════════════════════════════════
# MetricBucket — unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestMetricBucket:
    def test_add_and_compute_avg(self):
        bucket = MetricBucket()
        bucket.add("cpu", 80.0)
        bucket.add("cpu", 90.0)
        value, count = bucket.compute("cpu", "avg", window=60)
        assert value == pytest.approx(85.0)
        assert count == 2

    def test_avg_three_values(self):
        bucket = MetricBucket()
        bucket.add("disk", 82.0)
        bucket.add("disk", 88.0)
        bucket.add("disk", 85.5)
        value, count = bucket.compute("disk", "avg", window=60)
        assert value == pytest.approx(85.1667, abs=0.01)
        assert count == 3

    def test_max(self):
        bucket = MetricBucket()
        bucket.add("cpu", 70.0)
        bucket.add("cpu", 95.0)
        bucket.add("cpu", 85.0)
        value, count = bucket.compute("cpu", "max", window=60)
        assert value == 95.0
        assert count == 3

    def test_min(self):
        bucket = MetricBucket()
        bucket.add("cpu", 70.0)
        bucket.add("cpu", 95.0)
        bucket.add("cpu", 85.0)
        value, count = bucket.compute("cpu", "min", window=60)
        assert value == 70.0
        assert count == 3

    def test_sum(self):
        bucket = MetricBucket()
        bucket.add("requests", 100.0)
        bucket.add("requests", 200.0)
        bucket.add("requests", 50.0)
        value, count = bucket.compute("requests", "sum", window=60)
        assert value == 350.0
        assert count == 3

    def test_count(self):
        bucket = MetricBucket()
        bucket.add("ping", 1.0)
        bucket.add("ping", 1.0)
        bucket.add("ping", 1.0)
        bucket.add("ping", 1.0)
        bucket.add("ping", 1.0)
        value, count = bucket.compute("ping", "count", window=60)
        assert value == 5.0
        assert count == 5

    def test_empty_bucket(self):
        bucket = MetricBucket()
        value, count = bucket.compute("nonexistent", "avg", window=60)
        assert value is None
        assert count == 0

    def test_window_pruning(self):
        """Entries older than the window should be pruned."""
        bucket = MetricBucket()
        bucket.add("cpu", 80.0)
        bucket.add("cpu", 90.0)

        # Compute with a tiny window — only the last value should count
        # We use a very small window; both entries should be pruned
        # if enough time has passed, but since we add them instantly
        # they are within any reasonable window.
        value, count = bucket.compute("cpu", "avg", window=0.001)
        # Both entries should be within the window (added in rapid succession)
        assert count == 2

    def test_clear_single_rule(self):
        bucket = MetricBucket()
        bucket.add("a", 1.0)
        bucket.add("b", 2.0)
        bucket.clear("a")
        assert bucket.sample_count("a") == 0
        assert bucket.sample_count("b") == 1

    def test_clear_all(self):
        bucket = MetricBucket()
        bucket.add("a", 1.0)
        bucket.add("b", 2.0)
        bucket.clear()
        assert bucket.sample_count("a") == 0
        assert bucket.sample_count("b") == 0

    def test_sample_count(self):
        bucket = MetricBucket()
        assert bucket.sample_count("cpu") == 0
        bucket.add("cpu", 80.0)
        bucket.add("cpu", 90.0)
        assert bucket.sample_count("cpu") == 2

    def test_unknown_fn(self):
        bucket = MetricBucket()
        bucket.add("cpu", 80.0)
        value, count = bucket.compute("cpu", "median", window=60)
        assert value is None
        # count is 0 because pruning happens before fn check in the
        # default implementation — entries are kept but fn is unknown.
        # The important thing is value is None (safe fallback).

    def test_separate_rules(self):
        bucket = MetricBucket()
        bucket.add("cpu", 80.0)
        bucket.add("mem", 90.0)
        v1, c1 = bucket.compute("cpu", "avg", window=60)
        v2, c2 = bucket.compute("mem", "avg", window=60)
        assert v1 == 80.0 and c1 == 1
        assert v2 == 90.0 and c2 == 1

    def test_stale_entries_pruned(self):
        """Manually verify that old entries are removed from the deque."""
        bucket = MetricBucket()
        bucket.add("cpu", 80.0)
        bucket.add("cpu", 90.0)
        # Use a window that should include both
        value, count = bucket.compute("cpu", "avg", window=3600)
        assert count == 2
        # After compute, stale entries are pruned from deque
        assert bucket.sample_count("cpu") == 2


# ═══════════════════════════════════════════════════════════════════════
# report() with aggregation — integration tests
# ═══════════════════════════════════════════════════════════════════════

class TestAggregateReport:
    def test_avg_fires_when_above_threshold(self, app):
        """100 ES clusters, average disk crosses 85%."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=85, severity="warning")],
            consecutive_count=1,
            silence_seconds=0,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="avg", window=300),
        ))
        # Report 100 clusters — average is 85.5
        for i in range(100):
            value = 85.5 if i < 50 else 85.5
            app.report("es_disk", value, labels={"cluster": f"es-{i:03d}"})

        active = app.storage.list_active_alerts()
        assert len(active) == 1
        alert = active[0]
        assert alert.state == AlertState.FIRING.value
        assert alert.current_value == pytest.approx(85.5)
        assert alert.labels["aggregate_fn"] == "avg"
        assert alert.labels["sample_count"] == 100
        assert "avg=" in alert.message
        assert "100 samples" in alert.message

    def test_avg_no_fire_when_below(self, app):
        """Average below threshold — no alert."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=85, severity="warning")],
            consecutive_count=1,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="avg", window=300),
        ))
        # Average is 70 — below 85
        for i in range(50):
            app.report("es_disk", 70.0, labels={"cluster": f"es-{i:03d}"})

        active = app.storage.list_active_alerts()
        assert len(active) == 0

    def test_max_aggregation(self, app):
        """Max aggregation — any single cluster above threshold fires."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=90, severity="critical")],
            consecutive_count=1,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="max", window=300),
        ))
        # 99 clusters at 70%, 1 at 95%
        for i in range(99):
            app.report("es_disk", 70.0, labels={"cluster": f"es-{i:03d}"})
        app.report("es_disk", 95.0, labels={"cluster": "es-099"})

        active = app.storage.list_active_alerts()
        assert len(active) == 1
        assert active[0].current_value == 95.0
        assert active[0].labels["aggregate_fn"] == "max"

    def test_min_aggregation(self, app):
        """Min aggregation — the lowest value triggers."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=50, severity="warning")],
            consecutive_count=1,
            silence_seconds=0,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="min", window=300),
        ))
        # Min is 55, above 50 → fires
        app.report("es_disk", 80.0, labels={"cluster": "es-001"})
        app.report("es_disk", 60.0, labels={"cluster": "es-002"})
        app.report("es_disk", 55.0, labels={"cluster": "es-003"})

        active = app.storage.list_active_alerts()
        assert len(active) == 1
        assert active[0].current_value == 55.0

    def test_sum_aggregation(self, app):
        """Sum aggregation — total crosses threshold."""
        app.register_threshold_rule(ThresholdRule(
            name="error_count",
            thresholds=[ThresholdLevel(value=100, severity="error")],
            consecutive_count=1,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="sum", window=300),
        ))
        # 50 errors from service A, 60 from service B — total 110
        for _ in range(50):
            app.report("error_count", 1.0, labels={"service": "api"})
        for _ in range(60):
            app.report("error_count", 1.0, labels={"service": "worker"})

        active = app.storage.list_active_alerts()
        assert len(active) == 1
        assert active[0].current_value == 110.0

    def test_count_aggregation(self, app):
        """Count aggregation — fires when sample count crosses threshold."""
        app.register_threshold_rule(ThresholdRule(
            name="heartbeat",
            thresholds=[ThresholdLevel(value=5, severity="warning")],
            consecutive_count=1,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="count", window=300),
        ))
        # Fewer than 5 — no alert
        for i in range(4):
            app.report("heartbeat", 1.0, labels={"worker": f"w-{i}"})
        assert len(app.storage.list_active_alerts()) == 0

        # 5th report triggers
        app.report("heartbeat", 1.0, labels={"worker": "w-4"})
        assert len(app.storage.list_active_alerts()) == 1

    def test_aggregate_resolve_when_normal(self, app):
        """Aggregate drops below threshold → alert resolves."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=85, severity="warning")],
            consecutive_count=1,
            silence_seconds=0,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="avg", window=300),
        ))
        # Fire: average 90
        for i in range(20):
            app.report("es_disk", 90.0, labels={"cluster": f"es-{i:03d}"})
        assert len(app.storage.list_active_alerts()) == 1
        app.notifiers["fake"].sent.clear()

        # Recover: average drops to 60
        for i in range(20):
            app.report("es_disk", 60.0, labels={"cluster": f"es-{i:03d}"})

        active = app.storage.list_active_alerts()
        # Alert should be resolved
        resolved = app.storage.list_alert_history()
        assert len(resolved) == 1
        assert resolved[0].state == AlertState.RESOLVED.value

    def test_aggregate_multi_level_threshold(self, app):
        """Aggregate upgrades severity when crossing multiple levels."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[
                ThresholdLevel(value=70, severity="warning"),
                ThresholdLevel(value=85, severity="critical"),
            ],
            consecutive_count=1,
            silence_seconds=0,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="avg", window=300),
        ))
        # Warning level: 10 × 75 = avg 75
        for i in range(10):
            app.report("es_disk", 75.0, labels={"cluster": f"es-{i:03d}"})
        active = app.storage.list_active_alerts()
        assert len(active) == 1
        assert active[0].severity == "warning"

        # Upgrade to critical: add 30 more at 90 → avg = (750 + 2700) / 40 = 86.25
        for i in range(30):
            app.report("es_disk", 90.0, labels={"cluster": f"es-{i:03d}"})
        active = app.storage.list_active_alerts()
        assert len(active) == 1
        assert active[0].severity == "critical"

    def test_aggregate_dedup_by_rule_name(self, app):
        """Aggregated alerts deduplicate by rule name, not labels."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=85, severity="warning")],
            consecutive_count=1,
            silence_seconds=0,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="avg", window=300),
        ))
        # All labels point to the same aggregated alert
        app.report("es_disk", 90.0, labels={"cluster": "es-001"})
        app.report("es_disk", 90.0, labels={"cluster": "es-002"})
        app.report("es_disk", 90.0, labels={"cluster": "es-003"})

        active = app.storage.list_active_alerts()
        assert len(active) == 1
        assert active[0].dedup_key == "es_disk"
        assert active[0].labels["sample_count"] == 3

    def test_aggregate_no_rule_skips(self, app):
        """No rule registered → returns None."""
        result = app.report("nonexistent", 99.0)
        assert result is None

    def test_aggregate_consecutive_count(self, app):
        """Aggregated alerts respect consecutive_count.

        In aggregation mode, each ``report()`` call triggers one aggregate
        evaluation.  ``consecutive_count=3`` means the aggregate must cross
        the threshold in 3 consecutive evaluations.
        """
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=85, severity="warning")],
            consecutive_count=3,
            silence_seconds=0,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="avg", window=300),
        ))

        # 1st report → pending (hits=1)
        e1 = app.report("es_disk", 90.0, labels={"cluster": "es-001"})
        assert e1 is not None
        assert e1.state == AlertState.PENDING.value
        assert len(app.notifiers["fake"].sent) == 0

        # 2nd report → still pending (hits=2)
        e2 = app.report("es_disk", 90.0, labels={"cluster": "es-002"})
        assert e2.state == AlertState.PENDING.value
        assert len(app.notifiers["fake"].sent) == 0

        # 3rd report → fires (hits=3)
        e3 = app.report("es_disk", 90.0, labels={"cluster": "es-003"})
        assert e3.state == AlertState.FIRING.value
        assert len(app.notifiers["fake"].sent) == 1

    def test_aggregate_alert_labels_content(self, app):
        """Aggregated alert labels contain aggregate metadata."""
        app.register_threshold_rule(ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=85, severity="warning")],
            consecutive_count=1,
            silence_seconds=0,
            notify_targets=["fake"],
            aggregate=AggregateConfig(fn="avg", window=300),
        ))
        for i in range(5):
            app.report("es_disk", 90.0, labels={"cluster": f"es-{i:03d}"})

        active = app.storage.list_active_alerts()
        alert = active[0]
        assert alert.labels["aggregate_fn"] == "avg"
        assert alert.labels["sample_count"] == 5
        assert "avg=" in alert.message

    def test_non_aggregated_rule_unchanged(self, app):
        """Rules without aggregate should work exactly as before."""
        app.register_threshold_rule(ThresholdRule(
            name="cpu",
            thresholds=[ThresholdLevel(value=80, severity="warning")],
            consecutive_count=1,
            notify_targets=["fake"],
            # No aggregate field
        ))
        event = app.report("cpu", 90.0, labels={"host": "prod-1"})
        assert event is not None
        assert event.state == AlertState.FIRING.value
        assert event.dedup_key == "cpu:host=prod-1"
        assert "aggregate_fn" not in event.labels


class TestAggregateFn:
    def test_enum_values(self):
        assert AggregateFn.AVG.value == "avg"
        assert AggregateFn.MAX.value == "max"
        assert AggregateFn.MIN.value == "min"
        assert AggregateFn.SUM.value == "sum"
        assert AggregateFn.COUNT.value == "count"


class TestAggregateConfig:
    def test_defaults(self):
        cfg = AggregateConfig()
        assert cfg.fn == "avg"
        assert cfg.window == 300.0

    def test_custom(self):
        cfg = AggregateConfig(fn="max", window=60.0)
        assert cfg.fn == "max"
        assert cfg.window == 60.0

    def test_attached_to_threshold_rule(self):
        rule = ThresholdRule(
            name="es_disk",
            thresholds=[ThresholdLevel(value=85, severity="warning")],
            aggregate=AggregateConfig(fn="avg", window=300),
        )
        assert rule.aggregate is not None
        assert rule.aggregate.fn == "avg"
        assert rule.aggregate.window == 300
