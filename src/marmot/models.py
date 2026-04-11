"""
Marmot Alert Framework — Data Models

All domain models for the alert framework: state machine enums,
alert events, run records, rules, threshold rules, and notifications.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable
import json
import re

UTC = timezone.utc

_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)(ms|s|m|h|d)?\s*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat()


def from_iso(v: str | None) -> datetime | None:
    if not v:
        return None
    return datetime.fromisoformat(v)


class _MarmotEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return to_iso(o)
        return super().default(o)


def json_dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, cls=_MarmotEncoder)


def json_loads(v: str | None, default: Any):
    if not v:
        return default
    return json.loads(v)


def normalize_notify(v: str | Iterable[str] | None) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x).strip() for x in v if str(x).strip()]


def parse_duration(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()

    m = _DURATION_RE.match(s)
    if m:
        num = float(m.group(1))
        unit = m.group(2) or "s"
        return num * {
            "ms": 0.001,
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
        }[unit]

    return None


def build_dedup_key(rule_name: str, labels: dict[str, Any] | None = None) -> str:
    """Build a deterministic dedup key from rule name + sorted labels.

    Examples::

        >>> build_dedup_key("cpu_usage", {"instance": "prod-1"})
        'cpu_usage:instance=prod-1'

        >>> build_dedup_key("heartbeat")
        'heartbeat'
    """
    if not labels:
        return rule_name
    parts = [f"{k}={v}" for k, v in sorted(labels.items())]
    return f"{rule_name}:{','.join(parts)}"


# ---------------------------------------------------------------------------
# Alert State Machine
# ---------------------------------------------------------------------------

class AlertState(str, Enum):
    """Alert lifecycle states.

    State transitions::

        ──── report() ────► PENDING ──── report() ────► FIRING
                  │              (count reached)          │
                  │                                      │  report(normal)
                  │                                      ▼
                  │                                   RESOLVING ──► RESOLVED
                  │
                  │  fire() / timeout / escalation timer
                  └─────────────────────────────────────► FIRING
    """
    PENDING   = "pending"
    FIRING    = "firing"
    SILENCED  = "silenced"
    ESCALATED = "escalated"
    RESOLVING = "resolving"
    RESOLVED  = "resolved"


class Severity(str, Enum):
    """Standard severity levels."""
    INFO      = "info"
    WARNING   = "warning"
    ERROR     = "error"
    CRITICAL  = "critical"


class AlertStage(str, Enum):
    """Which mechanism triggered the alert."""
    THRESHOLD = "threshold"     # value crossed a ThresholdRule
    TIMEOUT   = "timeout"       # job/heartbeat exceeded timeout
    HEARTBEAT = "heartbeat"     # missed heartbeat
    MANUAL    = "manual"        # fire() called directly


class RunStatus(str, Enum):
    """Execution status of a monitored job."""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED  = "failed"
    TIMEOUT = "timeout"


class NotificationStatus(str, Enum):
    """Delivery status of a notification."""
    PENDING  = "pending"
    SENT     = "sent"
    FAILED   = "failed"


class AggregateFn(str, Enum):
    """Supported aggregation functions for metric bucket."""
    AVG   = "avg"
    MAX   = "max"
    MIN   = "min"
    SUM   = "sum"
    COUNT = "count"


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EscalationStep:
    after_seconds: float
    notify: list[str] = field(default_factory=list)

    @classmethod
    def from_value(cls, v: Any):
        if isinstance(v, EscalationStep):
            return v
        if isinstance(v, dict):
            return cls(
                after_seconds=parse_duration(v.get("after")) or 0,
                notify=normalize_notify(v.get("notify")),
            )
        return cls(float(v[0]), normalize_notify(v[1]))


# ---------------------------------------------------------------------------
# Aggregate Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AggregateConfig:
    """Configuration for metric aggregation.

    When attached to a ``ThresholdRule``, multiple ``report()`` calls
    are collected into a sliding window and aggregated before threshold
    evaluation.  This is useful for monitoring the overall health of a
    group of instances — e.g. average disk usage across 100 ES clusters.

    Parameters
    ----------
    fn : str
        Aggregation function: ``"avg"``, ``"max"``, ``"min"``, ``"sum"``, ``"count"``.
    window : float
        Sliding window size in seconds.  Only data points within this
        window are included in the computation.

    Example::

        AggregateConfig(fn="avg", window=300)   # 5-minute average
    """
    fn: str = AggregateFn.AVG.value
    window: float = 300.0


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Rule:
    name: str
    expected_interval_seconds: float | None = None
    timeout_seconds: float | None = None
    silence_seconds: float = 0
    group_key: str | None = None
    severity: str = "error"
    notify_targets: list[str] = field(default_factory=list)
    escalation_steps: list[EscalationStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def from_inputs(cls, *, name: str, **kwargs):
        return cls(
            name=name,
            expected_interval_seconds=parse_duration(kwargs.get("expected_interval")),
            timeout_seconds=parse_duration(kwargs.get("timeout")),
            silence_seconds=parse_duration(kwargs.get("silence")) or 0,
            group_key=kwargs.get("group_by"),
            severity=kwargs.get("severity", "error"),
            notify_targets=normalize_notify(kwargs.get("notify")),
            escalation_steps=[
                EscalationStep.from_value(x) for x in kwargs.get("escalate", [])
            ],
        )


@dataclass(slots=True)
class ThresholdLevel:
    value: float
    severity: str
    notify: list[str] = field(default_factory=list)
    silence_seconds: float = 0


@dataclass(slots=True)
class ThresholdRule:
    name: str
    thresholds: list[ThresholdLevel]
    consecutive_count: int = 1
    silence_seconds: float = 300
    notify_targets: list[str] = field(default_factory=list)
    escalation_steps: list[EscalationStep] = field(default_factory=list)
    group_key: str | None = None
    aggregate: AggregateConfig | None = None

    def evaluate(self, value: float) -> ThresholdLevel | None:
        """Return the highest matched threshold level, or None."""
        for t in reversed(sorted(self.thresholds, key=lambda x: x.value)):
            if value >= t.value:
                return t
        return None


# ---------------------------------------------------------------------------
# Alert Event  (core entity persisted in alert_events table)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AlertEvent:
    """Represents one active or historical alert.

    An AlertEvent is created the first time a rule fires for a given dedup key
    and is updated as the state machine progresses.
    """
    id: int | None = None
    rule_name: str = ""
    dedup_key: str = ""
    state: str = AlertState.PENDING.value
    severity: str = Severity.ERROR.value
    stage: str = AlertStage.THRESHOLD.value
    message: str = ""
    labels: dict[str, Any] = field(default_factory=dict)
    current_value: float | None = None
    consecutive_hits: int = 0
    consecutive_misses: int = 0
    fired_at: datetime = field(default_factory=utcnow)
    resolved_at: datetime | None = None
    silenced_until: datetime | None = None
    escalated_at: datetime | None = None
    last_notified_at: datetime | None = None
    notification_count: int = 0
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "rule_name": self.rule_name,
            "dedup_key": self.dedup_key,
            "state": self.state,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "labels": self.labels,
            "current_value": self.current_value,
            "consecutive_hits": self.consecutive_hits,
            "consecutive_misses": self.consecutive_misses,
            "fired_at": to_iso(self.fired_at),
            "resolved_at": to_iso(self.resolved_at),
            "silenced_until": to_iso(self.silenced_until),
            "escalated_at": to_iso(self.escalated_at),
            "last_notified_at": to_iso(self.last_notified_at),
            "notification_count": self.notification_count,
            "updated_at": to_iso(self.updated_at),
        }
        return d

    @classmethod
    def from_row(cls, row: Any) -> AlertEvent:
        """Construct from a SQLite Row or dict."""
        data = dict(row) if hasattr(row, "keys") else row
        return cls(
            id=data.get("id"),
            rule_name=data.get("rule_name", ""),
            dedup_key=data.get("dedup_key", ""),
            state=data.get("state", AlertState.PENDING.value),
            severity=data.get("severity", Severity.ERROR.value),
            stage=data.get("stage", AlertStage.THRESHOLD.value),
            message=data.get("message", ""),
            labels=json_loads(data.get("labels"), {}),
            current_value=data.get("current_value"),
            consecutive_hits=data.get("consecutive_hits", 0),
            consecutive_misses=data.get("consecutive_misses", 0),
            fired_at=from_iso(data.get("fired_at")) or utcnow(),
            resolved_at=from_iso(data.get("resolved_at")),
            silenced_until=from_iso(data.get("silenced_until")),
            escalated_at=from_iso(data.get("escalated_at")),
            last_notified_at=from_iso(data.get("last_notified_at")),
            notification_count=data.get("notification_count", 0),
            updated_at=from_iso(data.get("updated_at")) or utcnow(),
        )

    def to_event(self) -> AlertEvent:
        """Alias for web layer compatibility."""
        return self


# ---------------------------------------------------------------------------
# Run Record  (job / heartbeat execution tracking)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RunRecord:
    """Tracks a single execution of a monitored job or heartbeat ping."""
    id: int | None = None
    rule_name: str = ""
    dedup_key: str = ""
    status: str = RunStatus.RUNNING.value
    message: str = ""
    error: str | None = None
    labels: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None

    @property
    def duration_ms(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "dedup_key": self.dedup_key,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "labels": self.labels,
            "started_at": to_iso(self.started_at),
            "finished_at": to_iso(self.finished_at),
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_row(cls, row: Any) -> RunRecord:
        data = dict(row) if hasattr(row, "keys") else row
        return cls(
            id=data.get("id"),
            rule_name=data.get("rule_name", ""),
            dedup_key=data.get("dedup_key", ""),
            status=data.get("status", RunStatus.RUNNING.value),
            message=data.get("message", ""),
            error=data.get("error"),
            labels=json_loads(data.get("labels"), {}),
            started_at=from_iso(data.get("started_at")) or utcnow(),
            finished_at=from_iso(data.get("finished_at")),
        )


# ---------------------------------------------------------------------------
# Notification Record
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Notification:
    alert_event_id: int
    rule_name: str
    dedup_key: str
    status: str
    state: str
    message: str
    severity: str
    labels: dict[str, Any]
    stage: str
    notifier_name: str = ""
    sent_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sent_at"] = to_iso(self.sent_at)
        return d
