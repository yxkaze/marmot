"""
SQLite 持久化存储实现。

基于 stdlib `sqlite3`，零依赖。与 MemoryStorage 完全同契约。

设计要点:
- 单个 sqlite3.Connection（check_same_thread=False, isolation_level=None）
- 使用 RLock 串行化所有读写，避免 SQLite 多线程写竞争
- 文件路径下启用 WAL + synchronous=NORMAL 提升并发性能
- 枚举字段持久化为字符串（.value），datetime 走 ISO-8601，labels 走 JSON
- update_* 找不到 id 抛 ValueError（与 MemoryStorage 行为一致）

Schema、SQL 语句和序列化 helper 见 `_sqlite_sql.py`。
"""
from __future__ import annotations

import sqlite3
from os import PathLike
from threading import RLock

from ..domain.models.enums import AlertState
from ..domain.models.events import AlertEvent, Notification, RunRecord
from . import _sqlite_sql as _S


class SQLiteStorage:
    """基于 SQLite 的持久化存储实现（线程安全）。"""

    def __init__(self, db_path: str | PathLike[str]):
        self._db_path = str(db_path)
        self._lock = RLock()
        # isolation_level=None → autocommit；check_same_thread=False 配合 RLock
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            if self._db_path != ":memory:":
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.executescript(_S.SCHEMA_SQL)

    def close(self) -> None:
        """关闭底层连接。"""
        with self._lock:
            self._conn.close()

    # ── AlertEvent ──────────────────────────────────────

    def create_alert_event(self, event: AlertEvent) -> AlertEvent:
        with self._lock:
            cur = self._conn.execute(_S.INSERT_ALERT, _S.alert_params(event))
            event.id = cur.lastrowid
            return event

    def update_alert_event(self, event: AlertEvent) -> None:
        if event.id is None:
            raise ValueError("Alert event id is None")
        with self._lock:
            cur = self._conn.execute(
                _S.UPDATE_ALERT, (*_S.alert_params(event), event.id)
            )
            if cur.rowcount == 0:
                raise ValueError(f"Alert event {event.id} not found")

    def get_alert(self, alert_id: int) -> AlertEvent | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM alert_events WHERE id = ?", (alert_id,)
            ).fetchone()
            return _S.row_to_alert(row) if row else None

    def get_active_alert(self, dedup_key: str) -> AlertEvent | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM alert_events "
                "WHERE dedup_key = ? AND state != ? "
                "ORDER BY id DESC LIMIT 1",
                (dedup_key, AlertState.RESOLVED.value),
            ).fetchone()
            return _S.row_to_alert(row) if row else None

    def list_active_alerts(self) -> list[AlertEvent]:
        placeholders = ",".join(["?"] * len(_S.ACTIVE_STATES))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM alert_events "
                f"WHERE state IN ({placeholders}) "
                f"ORDER BY fired_at DESC, id DESC",
                _S.ACTIVE_STATES,
            ).fetchall()
            return [_S.row_to_alert(r) for r in rows]

    def list_alert_history(self, limit: int = 100) -> list[AlertEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM alert_events WHERE state = ? "
                "ORDER BY fired_at DESC, id DESC LIMIT ?",
                (AlertState.RESOLVED.value, limit),
            ).fetchall()
            return [_S.row_to_alert(r) for r in rows]

    # ── RunRecord ───────────────────────────────────────

    def create_run(self, run: RunRecord) -> RunRecord:
        with self._lock:
            cur = self._conn.execute(_S.INSERT_RUN, _S.run_params(run))
            run.id = cur.lastrowid
            return run

    def update_run(self, run: RunRecord) -> None:
        if run.id is None:
            raise ValueError("Run record id is None")
        with self._lock:
            cur = self._conn.execute(
                _S.UPDATE_RUN, (*_S.run_params(run), run.id)
            )
            if cur.rowcount == 0:
                raise ValueError(f"Run record {run.id} not found")

    def get_run(self, run_id: int) -> RunRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM run_records WHERE id = ?", (run_id,)
            ).fetchone()
            return _S.row_to_run(row) if row else None

    def get_latest_run(self, dedup_key: str) -> RunRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM run_records WHERE dedup_key = ? "
                "ORDER BY started_at DESC, id DESC LIMIT 1",
                (dedup_key,),
            ).fetchone()
            return _S.row_to_run(row) if row else None

    def list_runs(self, limit: int = 100) -> list[RunRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM run_records "
                "ORDER BY started_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [_S.row_to_run(r) for r in rows]

    # ── Notification ────────────────────────────────────

    def record_notification(self, n: Notification) -> int:
        with self._lock:
            cur = self._conn.execute(_S.INSERT_NOTIF, _S.notif_params(n))
            assert cur.lastrowid is not None  # AUTOINCREMENT 保证非 None
            n.id = cur.lastrowid
            return n.id

    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 200,
    ) -> list[Notification]:
        with self._lock:
            if alert_event_id is None:
                rows = self._conn.execute(
                    "SELECT * FROM notifications "
                    "ORDER BY sent_at DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM notifications WHERE alert_event_id = ? "
                    "ORDER BY sent_at DESC, id DESC LIMIT ?",
                    (alert_event_id, limit),
                ).fetchall()
            return [_S.row_to_notif(r) for r in rows]
