"""
Marmot Alert Framework — Core Application Engine

The central orchestrator: state machine, threshold evaluation,
heartbeat monitoring, job tracking, silence/dedup/escalation,
and the background escalation checker thread.
"""
from __future__ import annotations

import functools
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .models import (
    Rule,
    ThresholdRule,
    ThresholdLevel,
    EscalationStep,
    AlertEvent,
    RunRecord,
    Notification,
    AlertState,
    Severity,
    AlertStage,
    RunStatus,
    NotificationStatus,
    AggregateConfig,
    utcnow,
    to_iso,
    build_dedup_key,
    parse_duration,
)
from .storage import SQLiteStorage
from .notifiers import Notifier
from .bucket import MetricBucket

logger = logging.getLogger("marmot")

UTC = timezone.utc


# ═══════════════════════════════════════════════════════════════════════════
# Alert State Machine (pure logic, no I/O)
# ═══════════════════════════════════════════════════════════════════════════

class AlertStateMachine:
    """Deterministic state machine for alert lifecycle.

    Transitions::

        PENDING   ──(hits >= threshold)──► FIRING
        FIRING    ──(silence window)──────► SILENCED
        FIRING    ──(escalation timer)───► ESCALATED
        FIRING    ──(misses >= threshold)─► RESOLVING
        RESOLVING ──(confirmed normal)────► RESOLVED
        SILENCED  ──(window expired)──────► FIRING
        ESCALATED ──(misses >= threshold)─► RESOLVING

    All transition decisions are pure functions of the current state
    and the incoming event.  The machine returns the new state and
    a list of actions to take (notify, silence, etc.).
    """

    @staticmethod
    def transition(
        event: AlertEvent,
        hit: bool = False,
        miss: bool = False,
        force_fire: bool = False,
    ) -> tuple[str, list[str]]:
        """Compute next state and list of side-effect actions.

        Parameters
        ----------
        event : AlertEvent
            Current alert event (will be mutated by caller).
        hit : bool
            The value still exceeds the threshold.
        miss : bool
            The value is back to normal.
        force_fire : bool
            Force immediate transition to firing (for fire() / timeout).

        Returns
        -------
        tuple[str, list[str]]
            (new_state, [action1, action2, ...])  where actions are
            ``"notify_firing"``, ``"notify_resolved"``, ``"notify_escalation"``,
            ``"enter_silence"``, ``"enter_resolving"``.
        """
        current = event.state
        actions: list[str] = []

        if force_fire:
            event.state = AlertState.FIRING.value
            event.consecutive_hits = max(event.consecutive_hits, 1)
            actions.append("notify_firing")
            return AlertState.FIRING.value, actions

        if hit:
            event.consecutive_hits += 1
            event.consecutive_misses = 0
        elif miss:
            event.consecutive_misses += 1

        # ---- PENDING: waiting for consecutive hits ----
        if current == AlertState.PENDING.value:
            if hit:
                actions.append("notify_firing")
                return AlertState.FIRING.value, actions
            if miss:
                # Reset counter — was a fluke
                event.consecutive_hits = 0
            return current, actions

        # ---- FIRING ----
        if current == AlertState.FIRING.value:
            if miss:
                actions.append("enter_resolving")
                return AlertState.RESOLVING.value, actions
            # Still hitting — check silence
            if event.silenced_until and utcnow() < event.silenced_until:
                if current != AlertState.SILENCED.value:
                    return AlertState.SILENCED.value, actions
            return current, actions

        # ---- SILENCED: in silence window ----
        if current == AlertState.SILENCED.value:
            if event.silenced_until and utcnow() >= event.silenced_until:
                # Silence expired, back to firing
                actions.append("notify_firing")
                return AlertState.FIRING.value, actions
            if miss:
                actions.append("enter_resolving")
                return AlertState.RESOLVING.value, actions
            return current, actions

        # ---- ESCALATED ----
        if current == AlertState.ESCALATED.value:
            if miss:
                actions.append("enter_resolving")
                return AlertState.RESOLVING.value, actions
            return current, actions

        # ---- RESOLVING: confirming recovery ----
        if current == AlertState.RESOLVING.value:
            if hit:
                # Back to firing — was a transient recovery
                event.consecutive_misses = 0
                return AlertState.FIRING.value, actions
            actions.append("notify_resolved")
            return AlertState.RESOLVED.value, actions

        # ---- RESOLVED: terminal ----
        return current, actions


# ═══════════════════════════════════════════════════════════════════════════
# MarmotApp — Central Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

class MarmotApp:
    """The main application object.

    Typical usage::

        import marmot

        app = marmot.MarmotApp("my_app.db")
        app.register_notifier("ding", marmot.DingTalkNotifier(
            webhook_url="...", secret="...",
        ))
        app.register_threshold_rule(marmot.ThresholdRule(
            name="cpu_usage",
            thresholds=[
                marmot.ThresholdLevel(value=80, severity="warning"),
                marmot.ThresholdLevel(value=95, severity="critical"),
            ],
            consecutive_count=3,
            silence_seconds=300,
            notify_targets=["ding"],
        ))
        app.report("cpu_usage", 92.5, labels={"host": "prod-1"})
    """

    def __init__(self, db_path: str = "marmot.db"):
        self.storage = SQLiteStorage(db_path)
        self.rules: dict[str, Rule] = {}
        self.threshold_rules: dict[str, ThresholdRule] = {}
        self.notifiers: dict[str, Notifier] = {}
        self._bucket = MetricBucket()

        self.lock = threading.RLock()

        # Resolve misses after how many normal readings
        self._resolve_count: int = 3

        # Background escalation checker
        self._escalation_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_rule(self, rule: Rule) -> None:
        with self.lock:
            self.rules[rule.name] = rule
            self.storage.upsert_rule(rule)

    def register_threshold_rule(self, rule: ThresholdRule) -> None:
        with self.lock:
            self.threshold_rules[rule.name] = rule
            self.storage.upsert_threshold_rule(rule)

    def register_notifier(self, name: str, notifier: Notifier) -> None:
        self.notifiers[name] = notifier

    def unregister_notifier(self, name: str) -> None:
        self.notifiers.pop(name, None)

    # ------------------------------------------------------------------
    # Report (threshold-based)
    # ------------------------------------------------------------------

    def report(
        self,
        metric: str,
        value: float,
        *,
        labels: dict[str, Any] | None = None,
    ) -> AlertEvent | None:
        """Report a metric value.  The framework decides whether to alert.

        Parameters
        ----------
        metric : str
            Name of the threshold rule.
        value : float
            Current metric value.
        labels : dict
            Optional labels for dedup grouping (e.g. ``{"host": "prod-1"}``).
            When the rule has ``aggregate`` configured, labels identify the
            individual data source but do not affect dedup — the aggregated
            alert uses the rule name as its dedup key.

        Returns
        -------
        AlertEvent | None
            The alert event (may be new or updated), or None if no rule matched.
        """
        labels = labels or {}
        rule = self.threshold_rules.get(metric)
        if not rule:
            logger.debug("No threshold rule for metric=%s, skipping.", metric)
            return None

        # ── Aggregation mode ──────────────────────────────────────────
        if rule.aggregate is not None:
            return self._report_aggregated(rule, value)

        # ── Standard (per-instance) mode ──────────────────────────────
        dedup_key = build_dedup_key(metric, labels)
        matched_level = rule.evaluate(value)

        with self.lock:
            event = self.storage.get_active_alert(dedup_key)
            now = utcnow()

            if matched_level is None:
                # Value is normal
                if event and event.state in (
                    AlertState.FIRING.value,
                    AlertState.SILENCED.value,
                    AlertState.ESCALATED.value,
                    AlertState.RESOLVING.value,
                ):
                    event.current_value = value
                    event.consecutive_misses += 1
                    event.updated_at = now

                    new_state, actions = AlertStateMachine.transition(
                        event, miss=True,
                    )

                    if "enter_resolving" in actions:
                        event.state = new_state
                        # For consecutive_count <= 1, resolve immediately
                        if rule.consecutive_count <= 1:
                            event.state = AlertState.RESOLVED.value
                            event.resolved_at = now
                            event.updated_at = now
                            self.storage.update_alert_event(event)
                            self._do_notify(event, rule.notify_targets, "resolved")
                            return event
                        else:
                            self.storage.update_alert_event(event)

                    elif "notify_resolved" in actions:
                        event.state = AlertState.RESOLVED.value
                        event.resolved_at = now
                        event.updated_at = now
                        self.storage.update_alert_event(event)
                        self._do_notify(
                            event, rule.notify_targets, "resolved",
                        )
                        return event

                # Also handle the case where alert is PENDING and we get a normal value
                if event and event.state == AlertState.PENDING.value:
                    # Reset the pending counter
                    event.consecutive_hits = 0
                    event.updated_at = now
                    self.storage.update_alert_event(event)

                return event

            # ---- Threshold matched ----
            severity = matched_level.severity
            notify_targets = matched_level.notify or rule.notify_targets
            silence_seconds = matched_level.silence_seconds or rule.silence_seconds

            if event is None:
                # First hit — create PENDING event
                event = AlertEvent(
                    rule_name=metric,
                    dedup_key=dedup_key,
                    state=AlertState.PENDING.value,
                    severity=severity,
                    stage=AlertStage.THRESHOLD.value,
                    message=f"{metric} = {value} ({severity})",
                    labels=labels,
                    current_value=value,
                    consecutive_hits=1,
                    fired_at=now,
                    updated_at=now,
                )
                event = self.storage.create_alert_event(event)

                # If consecutive_count == 1, auto-fire
                if rule.consecutive_count <= 1:
                    new_state, actions = AlertStateMachine.transition(
                        event, hit=True,
                    )
                    event.state = new_state
                    event.message = f"{metric} = {value} ({severity})"
                    event.silenced_until = (
                        now + timedelta(seconds=silence_seconds)
                        if silence_seconds > 0 else None
                    )
                    event.updated_at = now
                    self.storage.update_alert_event(event)
                    if "notify_firing" in actions:
                        self._do_notify(event, notify_targets, "firing")
                return event

            # ---- Existing event ----
            event.current_value = value
            event.severity = severity
            event.message = f"{metric} = {value} ({severity})"
            event.updated_at = now

            if event.state == AlertState.RESOLVED.value:
                # Resolved alert firing again — create a new event
                event = AlertEvent(
                    rule_name=metric,
                    dedup_key=dedup_key,
                    state=AlertState.PENDING.value,
                    severity=severity,
                    stage=AlertStage.THRESHOLD.value,
                    message=f"{metric} = {value} ({severity})",
                    labels=labels,
                    current_value=value,
                    consecutive_hits=1,
                    fired_at=now,
                    updated_at=now,
                )
                event = self.storage.create_alert_event(event)

                if rule.consecutive_count <= 1:
                    new_state, actions = AlertStateMachine.transition(
                        event, hit=True,
                    )
                    event.state = new_state
                    event.silenced_until = (
                        now + timedelta(seconds=silence_seconds)
                        if silence_seconds > 0 else None
                    )
                    event.updated_at = now
                    self.storage.update_alert_event(event)
                    if "notify_firing" in actions:
                        self._do_notify(event, notify_targets, "firing")
                return event

            if event.state == AlertState.PENDING.value:
                event.consecutive_hits += 1
                if event.consecutive_hits >= rule.consecutive_count:
                    new_state, actions = AlertStateMachine.transition(
                        event, hit=True,
                    )
                    event.state = new_state
                    event.silenced_until = (
                        now + timedelta(seconds=silence_seconds)
                        if silence_seconds > 0 else None
                    )
                    event.updated_at = now
                    self.storage.update_alert_event(event)
                    if "notify_firing" in actions:
                        self._do_notify(event, notify_targets, "firing")
                else:
                    self.storage.update_alert_event(event)
                return event

            # Already FIRING / SILENCED / ESCALATED / RESOLVING
            new_state, actions = AlertStateMachine.transition(
                event, hit=True,
            )
            event.state = new_state
            event.updated_at = now
            self.storage.update_alert_event(event)

            if "notify_firing" in actions:
                self._do_notify(event, notify_targets, "firing")

            return event

    # ------------------------------------------------------------------
    # Report — Aggregation mode
    # ------------------------------------------------------------------

    def _report_aggregated(
        self, rule: ThresholdRule, value: float,
    ) -> AlertEvent | None:
        """Handle a ``report()`` call when the rule has aggregation enabled.

        Flow:
            1. Add the raw value to the MetricBucket.
            2. Compute the aggregate over the configured window.
            3. If no data yet, return None.
            4. Evaluate the aggregate value against the rule's thresholds.
            5. Create / update / resolve the aggregated alert (dedup by rule name).

        The aggregated alert carries ``labels`` with ``aggregate_fn`` and
        ``sample_count`` so that downstream consumers can inspect how the
        value was derived.
        """
        metric = rule.name
        agg_cfg = rule.aggregate

        # 1. Collect the data point
        self._bucket.add(metric, value)

        # 2. Compute aggregate
        agg_value, sample_count = self._bucket.compute(
            metric, agg_cfg.fn, agg_cfg.window,
        )
        if agg_value is None:
            return None

        # 3. Evaluate against thresholds
        matched_level = rule.evaluate(agg_value)

        # 4. Build context
        dedup_key = metric  # aggregated alert deduplicates by rule name only
        agg_labels: dict[str, Any] = {
            "aggregate_fn": agg_cfg.fn,
            "sample_count": sample_count,
        }

        now = utcnow()

        with self.lock:
            event = self.storage.get_active_alert(dedup_key)

            if matched_level is None:
                # Aggregate is normal — attempt resolve
                if event and event.state in (
                    AlertState.FIRING.value,
                    AlertState.SILENCED.value,
                    AlertState.ESCALATED.value,
                    AlertState.RESOLVING.value,
                ):
                    event.current_value = agg_value
                    event.labels = agg_labels
                    event.consecutive_misses += 1
                    event.updated_at = now

                    new_state, actions = AlertStateMachine.transition(
                        event, miss=True,
                    )

                    if "enter_resolving" in actions:
                        event.state = new_state
                        if rule.consecutive_count <= 1:
                            event.state = AlertState.RESOLVED.value
                            event.resolved_at = now
                            event.updated_at = now
                            self.storage.update_alert_event(event)
                            self._do_notify(event, rule.notify_targets, "resolved")
                            return event
                        else:
                            self.storage.update_alert_event(event)

                    elif "notify_resolved" in actions:
                        event.state = AlertState.RESOLVED.value
                        event.resolved_at = now
                        event.updated_at = now
                        self.storage.update_alert_event(event)
                        self._do_notify(event, rule.notify_targets, "resolved")
                        return event

                if event and event.state == AlertState.PENDING.value:
                    event.consecutive_hits = 0
                    event.current_value = agg_value
                    event.labels = agg_labels
                    event.updated_at = now
                    self.storage.update_alert_event(event)

                return event

            # ── Threshold matched ──
            severity = matched_level.severity
            notify_targets = matched_level.notify or rule.notify_targets
            silence_seconds = matched_level.silence_seconds or rule.silence_seconds
            message = (
                f"{metric} {agg_cfg.fn}={agg_value:.2f}, "
                f"{sample_count} samples ({severity})"
            )

            if event is None:
                event = AlertEvent(
                    rule_name=metric,
                    dedup_key=dedup_key,
                    state=AlertState.PENDING.value,
                    severity=severity,
                    stage=AlertStage.THRESHOLD.value,
                    message=message,
                    labels=agg_labels,
                    current_value=agg_value,
                    consecutive_hits=1,
                    fired_at=now,
                    updated_at=now,
                )
                event = self.storage.create_alert_event(event)

                if rule.consecutive_count <= 1:
                    new_state, actions = AlertStateMachine.transition(
                        event, hit=True,
                    )
                    event.state = new_state
                    event.message = message
                    event.silenced_until = (
                        now + timedelta(seconds=silence_seconds)
                        if silence_seconds > 0 else None
                    )
                    event.updated_at = now
                    self.storage.update_alert_event(event)
                    if "notify_firing" in actions:
                        self._do_notify(event, notify_targets, "firing")
                return event

            # ── Existing event ──
            event.current_value = agg_value
            event.severity = severity
            event.message = message
            event.labels = agg_labels
            event.updated_at = now

            if event.state == AlertState.RESOLVED.value:
                # Re-fire resolved alert
                event = AlertEvent(
                    rule_name=metric,
                    dedup_key=dedup_key,
                    state=AlertState.PENDING.value,
                    severity=severity,
                    stage=AlertStage.THRESHOLD.value,
                    message=message,
                    labels=agg_labels,
                    current_value=agg_value,
                    consecutive_hits=1,
                    fired_at=now,
                    updated_at=now,
                )
                event = self.storage.create_alert_event(event)

                if rule.consecutive_count <= 1:
                    new_state, actions = AlertStateMachine.transition(
                        event, hit=True,
                    )
                    event.state = new_state
                    event.silenced_until = (
                        now + timedelta(seconds=silence_seconds)
                        if silence_seconds > 0 else None
                    )
                    event.updated_at = now
                    self.storage.update_alert_event(event)
                    if "notify_firing" in actions:
                        self._do_notify(event, notify_targets, "firing")
                return event

            if event.state == AlertState.PENDING.value:
                event.consecutive_hits += 1
                if event.consecutive_hits >= rule.consecutive_count:
                    new_state, actions = AlertStateMachine.transition(
                        event, hit=True,
                    )
                    event.state = new_state
                    event.silenced_until = (
                        now + timedelta(seconds=silence_seconds)
                        if silence_seconds > 0 else None
                    )
                    event.updated_at = now
                    self.storage.update_alert_event(event)
                    if "notify_firing" in actions:
                        self._do_notify(event, notify_targets, "firing")
                else:
                    self.storage.update_alert_event(event)
                return event

            # Already FIRING / SILENCED / ESCALATED / RESOLVING
            new_state, actions = AlertStateMachine.transition(
                event, hit=True,
            )
            event.state = new_state
            event.updated_at = now
            self.storage.update_alert_event(event)

            if "notify_firing" in actions:
                self._do_notify(event, notify_targets, "firing")

            return event

    # ------------------------------------------------------------------
    # Manual Fire
    # ------------------------------------------------------------------

    def fire(
        self,
        name: str,
        message: str,
        *,
        severity: str = Severity.ERROR.value,
        labels: dict[str, Any] | None = None,
        notify_targets: list[str] | None = None,
    ) -> AlertEvent:
        """Manually trigger an alert (bypass threshold evaluation).

        Parameters
        ----------
        name : str
            Alert identifier.
        message : str
            Human-readable description.
        severity : str
            ``"info"``, ``"warning"``, ``"error"``, ``"critical"``.
        labels : dict
            Optional dedup labels.
        notify_targets : list[str]
            Notifier names to use.  Falls back to the rule's targets.

        Returns
        -------
        AlertEvent
        """
        labels = labels or {}
        dedup_key = build_dedup_key(name, labels)
        now = utcnow()

        with self.lock:
            # Check if there's already an active alert
            event = self.storage.get_active_alert(dedup_key)
            if event and event.state not in (
                AlertState.RESOLVED.value,
            ):
                # Update existing
                event.message = message
                event.severity = severity
                event.updated_at = now
                new_state, actions = AlertStateMachine.transition(
                    event, force_fire=True,
                )
                event.state = new_state
                self.storage.update_alert_event(event)
                targets = notify_targets or self._get_notify_targets(name)
                if "notify_firing" in actions:
                    self._do_notify(event, targets, "firing")
                return event

            # Create new
            rule = self.rules.get(name)
            silence = rule.silence_seconds if rule else 0

            event = AlertEvent(
                rule_name=name,
                dedup_key=dedup_key,
                state=AlertState.FIRING.value,
                severity=severity,
                stage=AlertStage.MANUAL.value,
                message=message,
                labels=labels,
                fired_at=now,
                silenced_until=(
                    now + timedelta(seconds=silence) if silence > 0 else None
                ),
                updated_at=now,
            )
            event = self.storage.create_alert_event(event)
            targets = notify_targets or self._get_notify_targets(name)
            self._do_notify(event, targets, "firing")
            return event

    # ------------------------------------------------------------------
    # Ping (heartbeat / async task)
    # ------------------------------------------------------------------

    def ping(
        self,
        name: str,
        *,
        labels: dict[str, Any] | None = None,
        message: str = "",
    ) -> None:
        """Signal that a heartbeat / async task is alive.

        If the task has a registered Rule with ``expected_interval``
        and/or ``timeout``, Marmot will automatically fire an alert
        when the heartbeat is missed.

        Parameters
        ----------
        name : str
            Name matching a registered Rule.
        labels : dict
            Optional dedup labels.
        message : str
            Optional status message.
        """
        labels = labels or {}
        dedup_key = build_dedup_key(name, labels)
        now = utcnow()

        with self.lock:
            run = RunRecord(
                rule_name=name,
                dedup_key=dedup_key,
                status=RunStatus.SUCCESS.value,
                message=message or "heartbeat ok",
                labels=labels,
                started_at=now,
                finished_at=now,
            )
            self.storage.create_run(run)

            # Resolve any active alert for this heartbeat
            event = self.storage.get_active_alert(dedup_key)
            if event and event.state in (
                AlertState.FIRING.value,
                AlertState.ESCALATED.value,
                AlertState.RESOLVING.value,
            ):
                event.state = AlertState.RESOLVED.value
                event.resolved_at = now
                event.updated_at = now
                self.storage.update_alert_event(event)
                targets = self._get_notify_targets(name)
                self._do_notify(event, targets, "resolved")

    # ------------------------------------------------------------------
    # Job decorator & context manager
    # ------------------------------------------------------------------

    def job(
        self,
        name: str,
        *,
        expected_interval: str | float | None = None,
        timeout: str | float | None = None,
        notify: str | list[str] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> Callable:
        """Decorator to monitor a function as a recurring job.

        Parameters
        ----------
        name : str
            Job name (registered as a Rule internally).
        expected_interval : str | float
            Expected interval between runs (e.g. ``"5m"``).
        timeout : str | float
            Maximum allowed duration (e.g. ``"10m"``).
        notify : str | list[str]
            Notifier name(s) for alerts.
        labels : dict
            Extra labels attached to all runs.

        Example::

            @app.job("data_pipeline", expected_interval="5m", timeout="10m",
                     notify="ding")
            def run_pipeline():
                ...
        """
        def decorator(func: Callable) -> Callable:
            # Auto-register rule
            rule = Rule.from_inputs(
                name=name,
                expected_interval=expected_interval,
                timeout=timeout,
                notify=notify,
            )
            self.register_rule(rule)
            _labels = labels or {}

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any):
                return self._run_job(func, name, rule, _labels, args, kwargs)
            return wrapper

        return decorator

    def run_job(
        self,
        func: Callable,
        name: str,
        *,
        expected_interval: str | float | None = None,
        timeout: str | float | None = None,
        notify: str | list[str] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> Any:
        """Non-decorator API: run a function as a monitored job.

        Example::

            result = app.run_job(my_func, "cleanup",
                                 timeout="30m", notify="ding")
        """
        rule = Rule.from_inputs(
            name=name,
            expected_interval=expected_interval,
            timeout=timeout,
            notify=notify,
        )
        self.register_rule(rule)
        _labels = labels or {}
        return self._run_job(func, name, rule, _labels, (), {})

    def _run_job(
        self,
        func: Callable,
        name: str,
        rule: Rule,
        labels: dict[str, Any],
        args: tuple,
        kwargs: dict,
    ) -> Any:
        dedup_key = build_dedup_key(name, labels)
        now = utcnow()

        run = RunRecord(
            rule_name=name,
            dedup_key=dedup_key,
            status=RunStatus.RUNNING.value,
            message=f"job {name} started",
            labels=labels,
            started_at=now,
        )
        run = self.storage.create_run(run)

        try:
            result = func(*args, **kwargs)
            run.status = RunStatus.SUCCESS.value
            run.message = f"job {name} succeeded"
            run.finished_at = utcnow()
            self.storage.update_run(run)

            # Resolve alert if exists
            event = self.storage.get_active_alert(dedup_key)
            if event and event.state in (
                AlertState.FIRING.value,
                AlertState.ESCALATED.value,
                AlertState.RESOLVING.value,
            ):
                event.state = AlertState.RESOLVED.value
                event.resolved_at = utcnow()
                event.updated_at = utcnow()
                self.storage.update_alert_event(event)
                targets = rule.notify_targets
                self._do_notify(event, targets, "resolved")
            return result

        except Exception as exc:
            run.status = RunStatus.FAILED.value
            run.error = str(exc)
            run.message = f"job {name} failed: {exc}"
            run.finished_at = utcnow()
            self.storage.update_run(run)

            # Fire alert
            self.fire(
                name,
                message=f"Job {name} failed: {exc}",
                severity=rule.severity,
                labels=labels,
                notify_targets=rule.notify_targets,
            )
            raise

    # ------------------------------------------------------------------
    # Resolve (manual)
    # ------------------------------------------------------------------

    def resolve(
        self,
        name: str,
        *,
        labels: dict[str, Any] | None = None,
        message: str = "",
    ) -> AlertEvent | None:
        """Manually resolve an active alert."""
        labels = labels or {}
        dedup_key = build_dedup_key(name, labels)
        now = utcnow()

        with self.lock:
            event = self.storage.get_active_alert(dedup_key)
            if event is None or event.state == AlertState.RESOLVED.value:
                return event

            event.state = AlertState.RESOLVED.value
            event.resolved_at = now
            event.message = message or event.message
            event.updated_at = now
            self.storage.update_alert_event(event)

            targets = self._get_notify_targets(name)
            # Always notify on resolve if we have any notifiers registered
            if not targets and self.notifiers:
                targets = list(self.notifiers.keys())
            self._do_notify(event, targets, "resolved")
            return event

    # ------------------------------------------------------------------
    # Escalation Checker (background thread)
    # ------------------------------------------------------------------

    def start_escalation_checker(self, interval_seconds: float = 10.0) -> None:
        """Start a background thread that checks for escalation opportunities.

        The thread scans all firing alerts and checks if any registered rule
        has escalation steps whose ``after_seconds`` threshold has been crossed.

        Parameters
        ----------
        interval_seconds : float
            How often to scan (default 10s).
        """
        if self._escalation_thread is not None and self._escalation_thread.is_alive():
            return

        self._stop_event.clear()

        def _loop():
            while not self._stop_event.wait(interval_seconds):
                try:
                    self._check_escalations()
                except Exception:
                    logger.exception("Escalation checker error")

        self._escalation_thread = threading.Thread(
            target=_loop, daemon=True, name="marmot-escalation",
        )
        self._escalation_thread.start()

    def stop_escalation_checker(self) -> None:
        self._stop_event.set()
        if self._escalation_thread:
            self._escalation_thread.join(timeout=5)
            self._escalation_thread = None

    def _check_escalations(self) -> None:
        with self.lock:
            alerts = self.storage.list_escalatable_alerts()

        for event in alerts:
            rule = self._find_rule_for_event(event)
            if not rule or not rule.escalation_steps:
                continue

            elapsed = (utcnow() - event.fired_at).total_seconds()

            for step in rule.escalation_steps:
                if elapsed >= step.after_seconds:
                    targets = step.notify or rule.notify_targets
                    event.state = AlertState.ESCALATED.value
                    event.escalated_at = utcnow()
                    event.updated_at = utcnow()
                    self.storage.update_alert_event(event)
                    self._do_notify(event, targets, "escalated")
                    break

    def _find_rule_for_event(self, event: AlertEvent) -> Rule | ThresholdRule | None:
        rule = self.rules.get(event.rule_name)
        if rule:
            return rule
        return self.threshold_rules.get(event.rule_name)

    # ------------------------------------------------------------------
    # Notification dispatch
    # ------------------------------------------------------------------

    def _do_notify(
        self,
        event: AlertEvent,
        targets: list[str],
        action: str,
    ) -> None:
        """Send notifications to all targets for the given alert event."""
        now = utcnow()

        for name in targets:
            notifier = self.notifiers.get(name)
            if notifier is None:
                logger.warning("Notifier %r not registered, skipping.", name)
                continue

            n = Notification(
                alert_event_id=event.id or 0,
                rule_name=event.rule_name,
                dedup_key=event.dedup_key,
                status=NotificationStatus.PENDING.value,
                state=event.state,
                message=event.message,
                severity=event.severity,
                labels=event.labels,
                stage=action,
                notifier_name=name,
                sent_at=now,
            )

            try:
                notifier.send(n)
                n.status = NotificationStatus.SENT.value
            except Exception:
                logger.exception(
                    "Notifier %r failed for alert %s", name, event.dedup_key,
                )
                n.status = NotificationStatus.FAILED.value

            try:
                self.storage.record_notification(n)
            except Exception:
                logger.exception("Failed to record notification")

        # Update event metadata
        event.last_notified_at = now
        event.notification_count += len(targets)
        try:
            self.storage.update_alert_event(event)
        except Exception:
            logger.exception("Failed to update event after notification")

    def _get_notify_targets(self, rule_name: str) -> list[str]:
        rule = self.rules.get(rule_name)
        if rule:
            return rule.notify_targets
        tr = self.threshold_rules.get(rule_name)
        if tr:
            return tr.notify_targets
        return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Gracefully stop all background threads and close storage."""
        self.stop_escalation_checker()
        self.storage.close()


# ═══════════════════════════════════════════════════════════════════════════
# Module-level singleton API (convenience)
# ═══════════════════════════════════════════════════════════════════════════

_default_app: MarmotApp | None = None


def configure(db_path: str = "marmot.db", *, start_escalation: bool = True) -> MarmotApp:
    """Initialize the default MarmotApp singleton.

    Parameters
    ----------
    db_path : str
        SQLite database path.
    start_escalation : bool
        Whether to auto-start the escalation checker.

    Returns
    -------
    MarmotApp
    """
    global _default_app
    _default_app = MarmotApp(db_path)
    if start_escalation:
        _default_app.start_escalation_checker()
    return _default_app


def get_app() -> MarmotApp:
    """Return the current default MarmotApp, raising if not configured."""
    if _default_app is None:
        raise RuntimeError("Marmot not configured. Call marmot.configure() first.")
    return _default_app


def register_rule(rule: Rule) -> None:
    """Register a rule on the default app."""
    get_app().register_rule(rule)


def register_threshold_rule(rule: ThresholdRule) -> None:
    """Register a threshold rule on the default app."""
    get_app().register_threshold_rule(rule)


def register_notifier(name: str, notifier: Notifier) -> None:
    """Register a notifier on the default app."""
    get_app().register_notifier(name, notifier)


def report(metric: str, value: float, *, labels: dict[str, Any] | None = None) -> AlertEvent | None:
    """Report a metric value on the default app."""
    return get_app().report(metric, value, labels=labels)


def fire(
    name: str,
    message: str,
    *,
    severity: str = Severity.ERROR.value,
    labels: dict[str, Any] | None = None,
    notify_targets: list[str] | None = None,
) -> AlertEvent:
    """Manually fire an alert on the default app."""
    return get_app().fire(name, message, severity=severity, labels=labels,
                          notify_targets=notify_targets)


def ping(name: str, *, labels: dict[str, Any] | None = None, message: str = "") -> None:
    """Send a heartbeat ping on the default app."""
    get_app().ping(name, labels=labels, message=message)


def resolve(
    name: str,
    *,
    labels: dict[str, Any] | None = None,
    message: str = "",
) -> AlertEvent | None:
    """Manually resolve an alert on the default app."""
    return get_app().resolve(name, labels=labels, message=message)


def job(
    name: str,
    *,
    expected_interval: str | float | None = None,
    timeout: str | float | None = None,
    notify: str | list[str] | None = None,
    labels: dict[str, Any] | None = None,
) -> Callable:
    """Decorator for monitoring a job on the default app."""
    return get_app().job(
        name,
        expected_interval=expected_interval,
        timeout=timeout,
        notify=notify,
        labels=labels,
    )


def shutdown() -> None:
    """Shutdown the default app."""
    if _default_app is not None:
        _default_app.shutdown()
