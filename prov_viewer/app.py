"""
Provenance dashboard 

Run with:
    FLASK_APP=prov_viewer/app.py flask run

It reads ../prov.log, shows an HTML dashboard, and exposes /api/events.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request

APP_DIR = Path(__file__).resolve().parent
LOG_PATH = APP_DIR.parent / "prov.log"

app = Flask(__name__, template_folder=str(APP_DIR / "templates"), static_folder=None)


def _parse_log(path: Path) -> List[Dict[str, Any]]:
    """Parse prov.log (pretty-printed JSON blocks)."""
    events: List[Dict[str, Any]] = []
    if not path.exists():
        return events

    buf: List[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.lstrip().startswith("{") and buf and buf[-1].rstrip().endswith("}"):
                    raw = "".join(buf).strip()
                    if raw:
                        try:
                            events.append(json.loads(raw))
                        except Exception:
                            pass
                    buf = []
                buf.append(line)
        raw = "".join(buf).strip()
        if raw:
            try:
                events.append(json.loads(raw))
            except Exception:
                pass
    except Exception:
        return []
    return events


def _enrich(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add derived fields to events."""
    sink_label = {
        "stdout": "Console (stdout)",
        "stderr": "Console (stderr)",
        "file_write": "File write",
        "socket_send": "Network send",
    }
    enriched: List[Dict[str, Any]] = []
    for e in events:
        owners = e.get("owners") or []
        if isinstance(owners, list):
            owners_str = ", ".join(owners)
        else:
            owners_str = str(owners)
        enriched.append(
            {
                "ts": e.get("ts", ""),
                "sink": e.get("sink", ""),
                "dest": e.get("dest", ""),
                "owners": owners,
                "owners_str": owners_str,
                "data": e.get("data", ""),
                "source": e.get("source", ""),
                "channel": sink_label.get(e.get("sink", ""), e.get("sink", "")),
            }
        )
    enriched.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return enriched


@app.route("/")
def dashboard():
    q = (request.args.get("q") or "").strip()
    events = _enrich(_parse_log(LOG_PATH))

    filtered = []
    searched = bool(q)
    if searched:
        q_lower = q.lower()
        filtered = [
            e
            for e in events
            if any((o or "").lower() == q_lower for o in e.get("owners", []))
        ]

    return render_template(
        "prov_dashboard.html",
        events=filtered,
        query=q,
        searched=searched,
        matched=len(filtered),
    )


@app.route("/api/events")
def api_events():
    events = _enrich(_parse_log(LOG_PATH))
    return jsonify(events)


if __name__ == "__main__":
    app.run(debug=True)
