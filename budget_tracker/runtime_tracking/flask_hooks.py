from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, request, session

from .config import InstrumentationConfig
from .context import end_request, start_request
from .tracker import RuntimeTracker


AUDIT_BLUEPRINT_NAME = "runtime_audit"


def register_flask_hooks(app, tracker: RuntimeTracker) -> None:
    config: InstrumentationConfig = tracker.config

    if app.blueprints.get(AUDIT_BLUEPRINT_NAME) is None:
        app.register_blueprint(_create_audit_blueprint(tracker), url_prefix="/runtime-audit")

    @app.before_request
    def _rt_before_request() -> None:
        user_id = session.get("user_id") or session.get("user_email")
        ctx = start_request(
            user_id=str(user_id) if user_id else None,
            path=request.path,
            method=request.method,
            client_ip=request.headers.get("X-Forwarded-For", request.remote_addr),
        )
        payload = _extract_request_payload()

        for key, value in payload.items():
            input_config = config.input_fields.get(key)
            description = input_config.description if input_config else f"Form field {key}"
            category = input_config.category if input_config else "unknown"
            tracker.register_input(
                field=key,
                description=description,
                category=category,
                value=value,
                owner=ctx.user_id,
                source=f"HTTP {request.method} {request.path}",
            )

        tracker.record_collection(payload)

    @app.after_request
    def _rt_after_request(response: Response) -> Response:
        return response

    @app.teardown_request
    def _rt_teardown(exception: Optional[BaseException]) -> None:
        end_request()


def _extract_request_payload() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    # Combine form and args
    for key in request.values:
        payload[key] = request.values.get(key)
    if request.is_json:
        try:
            data = request.get_json(silent=True) or {}
            for key, value in data.items():
                payload[key] = value
        except Exception:
            pass
    return payload


def _create_audit_blueprint(tracker: RuntimeTracker) -> Blueprint:
    bp = Blueprint(AUDIT_BLUEPRINT_NAME, __name__)

    def require_token():
        expected = tracker.config.audit_token
        if not expected:
            return True
        provided = request.headers.get("X-Audit-Token") or request.args.get("audit_token")
        return provided == expected

    @bp.before_request
    def _check_access():
        if not require_token():
            return jsonify({"error": "unauthorised"}), 401

    @bp.get("/events")
    def list_events():
        limit = min(int(request.args.get("limit", 100)), 500)
        event_type = request.args.get("event_type")
        events = tracker.storage.fetch_events(limit=limit, event_type=event_type)
        return jsonify({"events": events})

    @bp.get("/fingerprints")
    def list_fingerprints():
        return jsonify({"fingerprints": tracker.storage.fetch_fingerprints()})

    @bp.get("/status")
    def status():
        return jsonify(tracker.describe())

    return bp
