"""
SQLite 存储层的 schema、SQL 常量与序列化 helper。

将 schema/SQL/序列化抽离出来，让 `sqlite.py` 聚焦在连接管理与 CRUD 实现上。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..domain.models.enums import (
    AlertStage,
    AlertState,
    NotificationStatus,
    RunStatus,
    Severity,
)
from ..domain.models.events import AlertEvent, Notification, RunRecord
from ..domain.models.time_utils import from_iso, to_iso


ACTIVE_STATES: tuple[str, ...] = (
    AlertState.PENDING.value,
    AlertState.FIRING.value,
    AlertState.SILENCED.value,
    AlertState.ESCALATED.value,
    AlertState.RESOLVING.value,
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS alert_events (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name          TEXT    NOT NULL,
    dedup_key          TEXT    NOT NULL,
    state              TEXT    NOT NULL,
    severity           TEXT,
    stage              TEXT,
    message            TEXT    NOT NULL DEFAULT '',
    labels             TEXT    NOT NULL DEFAULT '{}',
    current_value      REAL,
    consecutive_hits   INTEGER NOT NULL DEFAULT 0,
    consecutive_misses INTEGER NOT NULL DEFAULT 0,
    fired_at           TEXT    NOT NULL,
    resolved_at        TEXT,
    silenced_until     TEXT,
    escalated_at       TEXT,
    escalation_level   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alert_events_dedup_state
    ON alert_events(dedup_key, state);
CREATE INDEX IF NOT EXISTS idx_alert_events_state_fired
    ON alert_events(state, fired_at);

CREATE TABLE IF NOT EXISTS run_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name    TEXT    NOT NULL,
    dedup_key    TEXT    NOT NULL,
    status       TEXT    NOT NULL,
    message      TEXT    NOT NULL DEFAULT '',
    error        TEXT,
    labels       TEXT    NOT NULL DEFAULT '{}',
    started_at   TEXT    NOT NULL,
    finished_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_run_records_dedup_started
    ON run_records(dedup_key, started_at);
CREATE INDEX IF NOT EXISTS idx_run_records_started
    ON run_records(started_at);

CREATE TABLE IF NOT EXISTS notifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_event_id  INTEGER NOT NULL REFERENCES alert_events(id) ON DELETE CASCADE,
    rule_name       TEXT    NOT NULL,
    dedup_key       TEXT    NOT NULL,
    status          TEXT    NOT NULL,
    state           TEXT,
    message         TEXT    NOT NULL DEFAULT '',
    severity        TEXT,
    labels          TEXT    NOT NULL DEFAULT '{}',
    stage           TEXT,
    sink_name       TEXT    NOT NULL DEFAULT '',
    sent_at         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_alert
    ON notifications(alert_event_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_notifications_sent
    ON notifications(sent_at);
"""


INSERT_ALERT = """
INSERT INTO alert_events (
    rule_name, dedup_key, state, severity, stage, message, labels,
    current_value, consecutive_hits, consecutive_misses,
    fired_at, resolved_at, silenced_until, escalated_at, escalation_level
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

UPDATE_ALERT = """
UPDATE alert_events SET
    rule_name=?, dedup_key=?, state=?, severity=?, stage=?, message=?, labels=?,
    current_value=?, consecutive_hits=?, consecutive_misses=?,
    fired_at=?, resolved_at=?, silenced_until=?, escalated_at=?, escalation_level=?
WHERE id=?
"""

INSERT_RUN = """
INSERT INTO run_records (
    rule_name, dedup_key, status, message, error, labels, started_at, finished_at
) VALUES (?,?,?,?,?,?,?,?)
"""

UPDATE_RUN = """
UPDATE run_records SET
    rule_name=?, dedup_key=?, status=?, message=?, error=?, labels=?,
    started_at=?, finished_at=?
WHERE id=?
"""

INSERT_NOTIF = """
INSERT INTO notifications (
    alert_event_id, rule_name, dedup_key, status, state, message,
    severity, labels, stage, sink_name, sent_at
) VALUES (?,?,?,?,?,?,?,?,?,?,?)
"""


def _enum_value(v: Any) -> str | None:
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)


def _dumps_labels(labels: dict[str, Any] | None) -> str:
    return json.dumps(labels or {}, ensure_ascii=False)


def _loads_labels(s: str | None) -> dict[str, Any]:
    return json.loads(s) if s else {}


def alert_params(e: AlertEvent) -> tuple:
    return (
        e.rule_name,
        e.dedup_key,
        _enum_value(e.state),
        _enum_value(e.severity),
        _enum_value(e.stage),
        e.message,
        _dumps_labels(e.labels),
        e.current_value,
        e.consecutive_hits,
        e.consecutive_misses,
        to_iso(e.fired_at),
        to_iso(e.resolved_at),
        to_iso(e.silenced_until),
        to_iso(e.escalated_at),
        e.escalation_level,
    )


def row_to_alert(row: sqlite3.Row) -> AlertEvent:
    return AlertEvent(
        id=row["id"],
        rule_name=row["rule_name"],
        dedup_key=row["dedup_key"],
        state=AlertState(row["state"]),
        severity=Severity(row["severity"]) if row["severity"] else None,
        stage=AlertStage(row["stage"]) if row["stage"] else None,
        message=row["message"] or "",
        labels=_loads_labels(row["labels"]),
        current_value=row["current_value"],
        consecutive_hits=row["consecutive_hits"],
        consecutive_misses=row["consecutive_misses"],
        fired_at=from_iso(row["fired_at"]),
        resolved_at=from_iso(row["resolved_at"]),
        silenced_until=from_iso(row["silenced_until"]),
        escalated_at=from_iso(row["escalated_at"]),
        escalation_level=row["escalation_level"],
    )


def run_params(r: RunRecord) -> tuple:
    return (
        r.rule_name,
        r.dedup_key,
        _enum_value(r.status),
        r.message,
        r.error,
        _dumps_labels(r.labels),
        to_iso(r.started_at),
        to_iso(r.finished_at),
    )


def row_to_run(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        id=row["id"],
        rule_name=row["rule_name"],
        dedup_key=row["dedup_key"],
        status=RunStatus(row["status"]),
        message=row["message"] or "",
        error=row["error"],
        labels=_loads_labels(row["labels"]),
        started_at=from_iso(row["started_at"]),
        finished_at=from_iso(row["finished_at"]),
    )


def notif_params(n: Notification) -> tuple:
    return (
        n.alert_event_id,
        n.rule_name,
        n.dedup_key,
        _enum_value(n.status),
        _enum_value(n.state),
        n.message,
        _enum_value(n.severity),
        _dumps_labels(n.labels),
        _enum_value(n.stage),
        n.sink_name,
        to_iso(n.sent_at),
    )


def row_to_notif(row: sqlite3.Row) -> Notification:
    return Notification(
        id=row["id"],
        alert_event_id=row["alert_event_id"],
        rule_name=row["rule_name"],
        dedup_key=row["dedup_key"],
        status=NotificationStatus(row["status"]),
        state=AlertState(row["state"]) if row["state"] else None,
        message=row["message"] or "",
        severity=Severity(row["severity"]) if row["severity"] else None,
        labels=_loads_labels(row["labels"]),
        stage=AlertStage(row["stage"]) if row["stage"] else None,
        sink_name=row["sink_name"] or "",
        sent_at=from_iso(row["sent_at"]),
    )
