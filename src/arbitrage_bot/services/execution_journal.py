"""SQLite-backed execution journal and duplicate-submission guard.

The journal deliberately has no signing or networking responsibilities. A
trade key must be persisted before either leg is submitted; retrying an existing
key is rejected to avoid accidental duplicate orders.
"""
import sqlite3
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone


class DuplicateExecutionError(RuntimeError):
    pass


class ExecutionJournal:
    def __init__(self, path: str = "data/execution_journal.sqlite3") -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    trade_key TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT ''
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def reserve(self, trade_key: str, details: str = "") -> None:
        if not trade_key or len(trade_key) > 200:
            raise ValueError("trade_key must contain 1-200 characters")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO executions(trade_key,status,created_at,updated_at,details) VALUES(?,?,?,?,?)",
                    (trade_key, "RESERVED", now, now, details[:2000]),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateExecutionError(f"trade key already reserved: {trade_key}") from exc

    def update(self, trade_key: str, status: str, details: str = "") -> None:
        allowed = {
            "PREFLIGHT_PASSED", "LEG_1_SUBMITTED", "LEG_1_CONFIRMED",
            "LEG_2_SUBMITTED", "COMPLETED", "FAILED",
            "PARTIAL_EXECUTION_REQUIRES_RECONCILIATION",
        }
        if status not in allowed:
            raise ValueError(f"unsupported execution status: {status}")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            cursor = db.execute(
                "UPDATE executions SET status=?, updated_at=?, details=? WHERE trade_key=?",
                (status, now, details[:2000], trade_key),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown trade key: {trade_key}")

    def get(self, trade_key: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT trade_key,status,created_at,updated_at,details FROM executions WHERE trade_key=?",
                (trade_key,),
            ).fetchone()
        if row is None:
            return None
        return dict(zip(("trade_key", "status", "created_at", "updated_at", "details"), row))
