"""
Marmot Alert Framework — SQLite Storage

Lightweight, zero-dependency persistence layer using SQLite.
Thread-safe via reentrant locks.  All schema migrations happen
automatically on first connection.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from dataclasses import asdict
from .models import (
    Rule,
    ThresholdRule,
    AlertEvent,
    RunRecord,
    Notification,
    AlertState,
    Severity,
    RunStatus,
    json_dumps,
    json_loads,
    to_iso,
    from_iso,
    utcnow,
    build_dedup_key,
)

UTC = timezone.utc


class SQLiteStorage:
    """SQLite-backed storage for alert events, run records, and notifications.

    Parameters
    ----------
    path : str
        Path to the SQLite database file.  Use ``":memory:"`` for testing.
    """

    def __init__(self, path: str = "marmot.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.lock = threading.RLock()
        self._migrate()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        with self.lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS rules (
                name       TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS threshold_rules (
                name       TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alert_events (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name            TEXT    NOT NULL,
                dedup_key            TEXT    NOT NULL,
                state                TEXT    NOT NULL DEFAULT 'pending',
                severity             TEXT    NOT NULL DEFAULT 'error',
                stage                TEXT    NOT NULL DEFAULT 'threshold',
                message              TEXT    NOT NULL DEFAULT '',
                labels               TEXT    NOT NULL DEFAULT '{}',
                current_value        REAL,
                consecutive_hits     INTEGER NOT NULL DEFAULT 0,
                consecutive_misses  INTEGER NOT NULL DEFAULT 0,
                fired_at             TEXT    NOT NULL,
                resolved_at          TEXT,
                silenced_until       TEXT,
                escalated_at         TEXT,
                last_notified_at     TEXT,
                notification_count   INTEGER NOT NULL DEFAULT 0,
                updated_at           TEXT    NOT NULL,
                UNIQUE(dedup_key, resolved_at)
            );

            CREATE INDEX IF NOT EXISTS idx_alert_events_dedup
                ON alert_events(dedup_key, resolved_at);

            CREATE INDEX IF NOT EXISTS idx_alert_events_state
                ON alert_events(state);

            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name   TEXT    NOT NULL,
                dedup_key   TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'running',
                message     TEXT    NOT NULL DEFAULT '',
                error       TEXT,
                labels      TEXT    NOT NULL DEFAULT '{}',
                started_at  TEXT    NOT NULL,
                finished_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_runs_dedup
                ON runs(dedup_key, started_at DESC);

            CREATE TABLE IF NOT EXISTS notifications (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_event_id   INTEGER,
                rule_name        TEXT    NOT NULL,
                dedup_key        TEXT    NOT NULL,
                notifier_name    TEXT    NOT NULL DEFAULT '',
                status           TEXT    NOT NULL DEFAULT 'pending',
                state            TEXT    NOT NULL,
                severity         TEXT    NOT NULL,
                stage            TEXT    NOT NULL,
                message          TEXT    NOT NULL,
                labels           TEXT    NOT NULL DEFAULT '{}',
                sent_at          TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notifications_event
                ON notifications(alert_event_id);
            """)
            self.conn.commit()

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def upsert_rule(self, rule: Rule) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO rules(name, data, created_at) VALUES(?, ?, ?)",
                (rule.name, json_dumps(asdict(rule)), to_iso(rule.created_at)),
            )
            self.conn.commit()

    def get_rule(self, name: str) -> Rule | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT data FROM rules WHERE name = ?", (name,)
            ).fetchone()
        if row is None:
            return None
        d = json_loads(row["data"], {})
        return Rule(**{k: v for k, v in d.items() if k in Rule.__dataclass_fields__})

    def list_rules(self) -> list[Rule]:
        with self.lock:
            rows = self.conn.execute("SELECT data FROM rules").fetchall()
        return [self._row_to_rule(r) for r in rows]

    def delete_rule(self, name: str) -> bool:
        with self.lock:
            cursor = self.conn.execute(
                "DELETE FROM rules WHERE name = ?", (name,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Threshold Rules
    # ------------------------------------------------------------------

    def upsert_threshold_rule(self, rule: ThresholdRule) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO threshold_rules(name, data) VALUES(?, ?)",
                (rule.name, json_dumps(asdict(rule))),
            )
            self.conn.commit()

    def get_threshold_rule(self, name: str) -> ThresholdRule | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT data FROM threshold_rules WHERE name = ?", (name,)
            ).fetchone()
        if row is None:
            return None
        d = json_loads(row["data"], {})
        # Reconstruct nested objects
        d["thresholds"] = [
            ThresholdLevel(**t) if isinstance(t, dict) else t
            for t in d.get("thresholds", [])
        ]
        d["escalation_steps"] = [
            EscalationStep.from_value(s) if isinstance(s, (dict, list)) else s
            for s in d.get("escalation_steps", [])
        ]
        return ThresholdRule(**{k: v for k, v in d.items()
                                 if k in ThresholdRule.__dataclass_fields__})

    def list_threshold_rules(self) -> list[ThresholdRule]:
        with self.lock:
            rows = self.conn.execute("SELECT data FROM threshold_rules").fetchall()
        return [self._row_to_threshold_rule(r) for r in rows]

    def delete_threshold_rule(self, name: str) -> bool:
        with self.lock:
            cursor = self.conn.execute(
                "DELETE FROM threshold_rules WHERE name = ?", (name,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Alert Events
    # ------------------------------------------------------------------

    def create_alert_event(self, event: AlertEvent) -> AlertEvent:
        with self.lock:
            cursor = self.conn.execute(
                """INSERT INTO alert_events
                   (rule_name, dedup_key, state, severity, stage, message,
                    labels, current_value, consecutive_hits, consecutive_misses,
                    fired_at, resolved_at, silenced_until, escalated_at,
                    last_notified_at, notification_count, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.rule_name,
                    event.dedup_key,
                    event.state,
                    event.severity,
                    event.stage,
                    event.message,
                    json_dumps(event.labels),
                    event.current_value,
                    event.consecutive_hits,
                    event.consecutive_misses,
                    to_iso(event.fired_at),
                    to_iso(event.resolved_at),
                    to_iso(event.silenced_until),
                    to_iso(event.escalated_at),
                    to_iso(event.last_notified_at),
                    event.notification_count,
                    to_iso(event.updated_at),
                ),
            )
            self.conn.commit()
            event.id = cursor.lastrowid
            return event

    def update_alert_event(self, event: AlertEvent) -> None:
        with self.lock:
            self.conn.execute(
                """UPDATE alert_events SET
                     state = ?, severity = ?, stage = ?, message = ?,
                     labels = ?, current_value = ?,
                     consecutive_hits = ?, consecutive_misses = ?,
                     resolved_at = ?, silenced_until = ?, escalated_at = ?,
                     last_notified_at = ?, notification_count = ?,
                     updated_at = ?
                   WHERE id = ?""",
                (
                    event.state,
                    event.severity,
                    event.stage,
                    event.message,
                    json_dumps(event.labels),
                    event.current_value,
                    event.consecutive_hits,
                    event.consecutive_misses,
                    to_iso(event.resolved_at),
                    to_iso(event.silenced_until),
                    to_iso(event.escalated_at),
                    to_iso(event.last_notified_at),
                    event.notification_count,
                    to_iso(event.updated_at),
                    event.id,
                ),
            )
            self.conn.commit()

    def get_alert(self, alert_id: int) -> AlertEvent | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM alert_events WHERE id = ?", (alert_id,)
            ).fetchone()
        if row is None:
            return None
        return AlertEvent.from_row(row)

    def get_active_alert(self, dedup_key: str) -> AlertEvent | None:
        """Return the currently active (unresolved) alert for a dedup key."""
        with self.lock:
            row = self.conn.execute(
                """SELECT * FROM alert_events
                   WHERE dedup_key = ? AND resolved_at IS NULL
                   ORDER BY id DESC LIMIT 1""",
                (dedup_key,),
            ).fetchone()
        if row is None:
            return None
        return AlertEvent.from_row(row)

    def list_active_alerts(self) -> list[AlertEvent]:
        """Return all unresolved alerts."""
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM alert_events
                   WHERE resolved_at IS NULL
                   ORDER BY updated_at DESC"""
            ).fetchall()
        return [AlertEvent.from_row(r) for r in rows]

    def list_alert_history(self, limit: int = 100) -> list[AlertEvent]:
        """Return resolved alerts, most recent first."""
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM alert_events
                   WHERE resolved_at IS NOT NULL
                   ORDER BY resolved_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [AlertEvent.from_row(r) for r in rows]

    def list_silenced_alerts(self) -> list[AlertEvent]:
        """Return alerts currently within their silence window."""
        now = to_iso(utcnow())
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM alert_events
                   WHERE resolved_at IS NULL
                     AND silenced_until IS NOT NULL
                     AND silenced_until > ?
                   ORDER BY updated_at DESC""",
                (now,),
            ).fetchall()
        return [AlertEvent.from_row(r) for r in rows]

    def list_escalatable_alerts(self, now: datetime | None = None) -> list[AlertEvent]:
        """Return firing alerts that have not been escalated yet and
        have been firing long enough to warrant escalation."""
        if now is None:
            now = utcnow()
        now_iso = to_iso(now)
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM alert_events
                   WHERE state IN ('firing', 'escalated')
                     AND resolved_at IS NULL
                     AND escalated_at IS NULL
                   ORDER BY fired_at ASC"""
            ).fetchall()
        return [AlertEvent.from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(self, run: RunRecord) -> RunRecord:
        with self.lock:
            cursor = self.conn.execute(
                """INSERT INTO runs
                   (rule_name, dedup_key, status, message, error, labels,
                    started_at, finished_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    run.rule_name,
                    run.dedup_key,
                    run.status,
                    run.message,
                    run.error,
                    json_dumps(run.labels),
                    to_iso(run.started_at),
                    to_iso(run.finished_at),
                ),
            )
            self.conn.commit()
            run.id = cursor.lastrowid
            return run

    def update_run(self, run: RunRecord) -> None:
        with self.lock:
            self.conn.execute(
                """UPDATE runs SET
                     status = ?, message = ?, error = ?,
                     finished_at = ?
                   WHERE id = ?""",
                (run.status, run.message, run.error,
                 to_iso(run.finished_at), run.id),
            )
            self.conn.commit()

    def get_run(self, run_id: int) -> RunRecord | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return RunRecord.from_row(row)

    def get_latest_run(self, dedup_key: str) -> RunRecord | None:
        with self.lock:
            row = self.conn.execute(
                """SELECT * FROM runs
                   WHERE dedup_key = ?
                   ORDER BY started_at DESC LIMIT 1""",
                (dedup_key,),
            ).fetchone()
        if row is None:
            return None
        return RunRecord.from_row(row)

    def list_runs(self, limit: int = 100) -> list[RunRecord]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [RunRecord.from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def record_notification(self, n: Notification) -> int:
        with self.lock:
            cursor = self.conn.execute(
                """INSERT INTO notifications
                   (alert_event_id, rule_name, dedup_key, notifier_name,
                    status, state, severity, stage, message, labels, sent_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    n.alert_event_id,
                    n.rule_name,
                    n.dedup_key,
                    n.notifier_name,
                    n.status,
                    n.state,
                    n.severity,
                    n.stage,
                    n.message,
                    json_dumps(n.labels),
                    to_iso(n.sent_at),
                ),
            )
            self.conn.commit()
            return cursor.lastrowid

    def list_notifications(self, alert_event_id: int | None = None,
                           limit: int = 200) -> list[dict[str, Any]]:
        with self.lock:
            if alert_event_id is not None:
                rows = self.conn.execute(
                    """SELECT * FROM notifications
                       WHERE alert_event_id = ?
                       ORDER BY sent_at DESC LIMIT ?""",
                    (alert_event_id, limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT * FROM notifications
                       ORDER BY sent_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_rule(self, row: Any) -> Rule:
        d = json_loads(row["data"], {})
        d["escalation_steps"] = [
            EscalationStep.from_value(s) if isinstance(s, (dict, list)) else s
            for s in d.get("escalation_steps", [])
        ]
        return Rule(**{k: v for k, v in d.items() if k in Rule.__dataclass_fields__})

    def _row_to_threshold_rule(self, row: Any) -> ThresholdRule:
        d = json_loads(row["data"], {})
        d["thresholds"] = [
            ThresholdLevel(**t) if isinstance(t, dict) else t
            for t in d.get("thresholds", [])
        ]
        d["escalation_steps"] = [
            EscalationStep.from_value(s) if isinstance(s, (dict, list)) else s
            for s in d.get("escalation_steps", [])
        ]
        return ThresholdRule(**{k: v for k, v in d.items()
                                 if k in ThresholdRule.__dataclass_fields__})

    def close(self) -> None:
        self.conn.close()


# Need these imports for deserialization
from .models import ThresholdLevel, EscalationStep
