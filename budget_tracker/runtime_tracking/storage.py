from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from .events import DataTag, ProvenanceEvent


SCHEMA_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    target TEXT NOT NULL,
    payload TEXT,
    request_id TEXT,
    user_id TEXT,
    matched_tags TEXT,
    extras TEXT
);
"""


SCHEMA_FINGERPRINTS = """
CREATE TABLE IF NOT EXISTS fingerprints (
    fingerprint TEXT PRIMARY KEY,
    first_seen_event_id TEXT,
    last_seen_at TEXT,
    field TEXT,
    category TEXT,
    description TEXT,
    owner TEXT
);
"""


class ProvenanceStorage:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def initialise(self) -> None:
        with self._connect() as conn:
            conn.execute(SCHEMA_EVENTS)
            conn.execute(SCHEMA_FINGERPRINTS)
            conn.commit()

    def record_event(self, event: ProvenanceEvent) -> None:
        payload_text = json.dumps(event.payload, default=str)
        matched_text = json.dumps([tag.as_dict() for tag in event.matched_tags])
        extras_text = json.dumps(event.extras, default=str)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (id, created_at, event_type, actor, target, payload, request_id, user_id, matched_tags, extras)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.created_at,
                    event.event_type,
                    event.actor,
                    event.target,
                    payload_text,
                    event.request_id,
                    event.user_id,
                    matched_text,
                    extras_text,
                ),
            )
            conn.commit()

    def upsert_fingerprint(self, tag: DataTag, *, event_id: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fingerprints (fingerprint, first_seen_event_id, last_seen_at, field, category, description, owner)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    field=excluded.field,
                    category=excluded.category,
                    description=excluded.description,
                    owner=excluded.owner
                """,
                (
                    tag.fingerprint,
                    event_id,
                    tag.created_at,
                    tag.field,
                    tag.category,
                    tag.description,
                    tag.owner,
                ),
            )
            conn.commit()

    def fetch_events(self, limit: int = 100, *, event_type: Optional[str] = None) -> List[dict]:
        query = "SELECT id, created_at, event_type, actor, target, payload, request_id, user_id, matched_tags, extras FROM events"
        params: List[object] = []
        if event_type:
            query += " WHERE event_type = ?"
            params.append(event_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        events = []
        for row in rows:
            payload = json.loads(row[4]) if row[4] else {}
            matched_tags = json.loads(row[8]) if row[8] else []
            extras = json.loads(row[9]) if row[9] else {}
            events.append(
                {
                    "event_id": row[0],
                    "created_at": row[1],
                    "event_type": row[2],
                    "actor": row[3],
                    "target": row[4],
                    "payload": payload,
                    "request_id": row[5],
                    "user_id": row[6],
                    "matched_tags": matched_tags,
                    "extras": extras,
                }
            )
        return events

    def fetch_fingerprints(self) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT fingerprint, first_seen_event_id, last_seen_at, field, category, description, owner FROM fingerprints"
            ).fetchall()
        return [
            {
                "fingerprint": row[0],
                "first_seen_event_id": row[1],
                "last_seen_at": row[2],
                "field": row[3],
                "category": row[4],
                "description": row[5],
                "owner": row[6],
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn
