from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Sequence

from .utils import ensure_json, isoformat


class ProvenanceRecorder:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            method TEXT,
            path TEXT,
            remote_addr TEXT,
            user_agent TEXT,
            user_id TEXT,
            start_time TEXT,
            end_time TEXT,
            status_code INTEGER,
            exception TEXT
        );

        CREATE TABLE IF NOT EXISTS data_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            event_type TEXT,
            tag TEXT,
            source TEXT,
            field TEXT,
            value_preview TEXT,
            raw_type TEXT,
            metadata TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS storage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            operation TEXT,
            model TEXT,
            field TEXT,
            tag TEXT,
            value_preview TEXT,
            metadata TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS share_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            tag_matches TEXT,
            destination TEXT,
            method TEXT,
            url TEXT,
            payload_preview TEXT,
            metadata TEXT,
            created_at TEXT
        );
        """
        with self._lock, self._conn:
            self._conn.executescript(schema)

    def record_request_start(
        self,
        request_id: str,
        *,
        method: str,
        path: str,
        remote_addr: str,
        user_agent: str | None,
        start_time: datetime,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO requests (
                    id, method, path, remote_addr, user_agent, start_time
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    method,
                    path,
                    remote_addr,
                    user_agent or "",
                    isoformat(start_time),
                ),
            )

    def record_request_end(
        self,
        request_id: str,
        *,
        status_code: int | None,
        end_time: datetime,
        user_id: str | None,
        exception: str | None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE requests
                SET status_code = ?, end_time = ?, user_id = ?, exception = ?
                WHERE id = ?
                """,
                (
                    status_code,
                    isoformat(end_time),
                    user_id,
                    exception,
                    request_id,
                ),
            )

    def record_data_event(
        self,
        request_id: str,
        *,
        event_type: str,
        tag: str,
        source: str,
        field: str,
        value_preview: str,
        raw_type: str,
        metadata: Dict[str, Any],
        created_at: datetime,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO data_events (
                    request_id, event_type, tag, source, field,
                    value_preview, raw_type, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    event_type,
                    tag,
                    source,
                    field,
                    value_preview,
                    raw_type,
                    ensure_json(metadata),
                    isoformat(created_at),
                ),
            )

    def record_storage_event(
        self,
        request_id: str,
        *,
        operation: str,
        model: str,
        field: str,
        tag: str | None,
        value_preview: str,
        metadata: Dict[str, Any],
        created_at: datetime,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO storage_events (
                    request_id, operation, model, field, tag,
                    value_preview, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    operation,
                    model,
                    field,
                    tag,
                    value_preview,
                    ensure_json(metadata),
                    isoformat(created_at),
                ),
            )

    def record_share_event(
        self,
        request_id: str,
        *,
        tag_matches: Sequence[str],
        destination: str,
        method: str,
        url: str,
        payload_preview: str,
        metadata: Dict[str, Any],
        created_at: datetime,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO share_events (
                    request_id, tag_matches, destination, method, url,
                    payload_preview, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    ",".join(tag_matches),
                    destination,
                    method,
                    url,
                    payload_preview,
                    ensure_json(metadata),
                    isoformat(created_at),
                ),
            )
