from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, Tuple

DEFAULT_DB = Path(__file__).resolve().parent.parent / "runtime_provenance.db"


def query(conn: sqlite3.Connection, sql: str, params: Tuple = ()) -> Iterable[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    return cur.fetchall()


def format_row(row: sqlite3.Row) -> str:
    return ", ".join(f"{key}={row[key]}" for key in row.keys())


def list_requests(conn: sqlite3.Connection, limit: int) -> None:
    rows = query(
        conn,
        """
        SELECT id, method, path, user_id, status_code, start_time, end_time, exception
        FROM requests
        ORDER BY start_time DESC
        LIMIT ?
        """,
        (limit,),
    )
    for row in rows:
        print(format_row(row))


def list_events(conn: sqlite3.Connection, table: str, limit: int, request_id: str | None) -> None:
    sql = f"SELECT * FROM {table}"
    params: Tuple = ()
    if request_id:
        sql += " WHERE request_id = ?"
        params = (request_id,)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params = params + (limit,)
    rows = query(conn, sql, params)
    for row in rows:
        print(format_row(row))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect runtime provenance logs captured by the instrumentation layer.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"Path to provenance SQLite database (default: {DEFAULT_DB})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    requests_parser = subparsers.add_parser("requests", help="List instrumented HTTP requests.")
    requests_parser.add_argument("--limit", type=int, default=20)

    data_parser = subparsers.add_parser("data", help="List tagged data ingress events.")
    data_parser.add_argument("--limit", type=int, default=20)
    data_parser.add_argument("--request-id", help="Filter by request identifier.")

    storage_parser = subparsers.add_parser("storage", help="List database storage events.")
    storage_parser.add_argument("--limit", type=int, default=20)
    storage_parser.add_argument("--request-id", help="Filter by request identifier.")

    share_parser = subparsers.add_parser("share", help="List outgoing share events.")
    share_parser.add_argument("--limit", type=int, default=20)
    share_parser.add_argument("--request-id", help="Filter by request identifier.")

    args = parser.parse_args()
    conn = sqlite3.connect(args.db)

    try:
        if args.command == "requests":
            list_requests(conn, args.limit)
        elif args.command == "data":
            list_events(conn, "data_events", args.limit, args.request_id)
        elif args.command == "storage":
            list_events(conn, "storage_events", args.limit, args.request_id)
        elif args.command == "share":
            list_events(conn, "share_events", args.limit, args.request_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
