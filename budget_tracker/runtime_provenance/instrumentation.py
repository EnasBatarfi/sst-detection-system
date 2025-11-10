from __future__ import annotations

import contextvars
import logging
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

logger = logging.getLogger("runtime_provenance")

from .config import Settings, load_settings
from .recorder import ProvenanceRecorder
from .tagging import TagManager, TagRecord
from .utils import flatten_items, short_preview, hash_preview


class RequestContext:
    __slots__ = (
        "request_id",
        "start_time",
        "field_tags",
        "tag_records",
        "status_code",
        "_token",
        "_hash_cache",
    )

    def __init__(self, request_id: str):
        self.request_id = request_id
        self.start_time = datetime.utcnow()
        self.field_tags: Dict[str, Dict[str, List[TagRecord]]] = {}
        self.tag_records: List[TagRecord] = []
        self.status_code: Optional[int] = None
        self._token: Optional[contextvars.Token] = None
        self._hash_cache: Dict[str, List[TagRecord]] | None = None

    def register_tag(self, source: str, field: str, tag_record: TagRecord) -> None:
        self.field_tags.setdefault(source, {}).setdefault(field, []).append(tag_record)
        self.tag_records.append(tag_record)
        self._hash_cache = None

    def get_tags(self, source: str, field: str) -> Sequence[TagRecord]:
        return self.field_tags.get(source, {}).get(field, [])

    def iter_all_tags(self) -> Iterable[TagRecord]:
        return list(self.tag_records)

    def tags_by_hash(self) -> Dict[str, List[TagRecord]]:
        if self._hash_cache is None:
            index: Dict[str, List[TagRecord]] = {}
            for record in self.tag_records:
                index.setdefault(record.value_hash, []).append(record)
            self._hash_cache = index
        return self._hash_cache

    def attach_token(self, token: contextvars.Token) -> None:
        self._token = token

    def reset(self, ctx_var: contextvars.ContextVar) -> None:
        if self._token is not None:
            ctx_var.reset(self._token)
            self._token = None


_CTX: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    "runtime_provenance_ctx", default=None
)

_INITIALIZED = False
_SETTINGS: Settings | None = None
_RECORDER: ProvenanceRecorder | None = None
_TAG_MANAGER: TagManager | None = None

_FLASK_PATCHED = False
_SQLALCHEMY_PATCHED = False
_REQUESTS_PATCHED = False


def get_ctx() -> RequestContext | None:
    return _CTX.get()


def initialize() -> None:
    global _INITIALIZED, _SETTINGS, _RECORDER, _TAG_MANAGER
    if _INITIALIZED:
        return

    _SETTINGS = load_settings()
    if not _SETTINGS.enabled:
        logger.info("Runtime provenance instrumentation disabled via environment flag.")
        _INITIALIZED = True
        return

    logging.basicConfig(level=_SETTINGS.log_level)

    _RECORDER = ProvenanceRecorder(_SETTINGS.db_path)
    _TAG_MANAGER = TagManager(_SETTINGS.hash_salt, _SETTINGS.capture_limit)

    setup_flask_instrumentation()
    setup_sqlalchemy_instrumentation()
    setup_requests_instrumentation()

    _INITIALIZED = True
    logger.info(
        "Runtime provenance instrumentation initialized (db=%s)",
        _SETTINGS.db_path,
    )


def require_initialized() -> Tuple[Settings, ProvenanceRecorder, TagManager]:
    if not _INITIALIZED or _SETTINGS is None or _RECORDER is None or _TAG_MANAGER is None:
        raise RuntimeError("Runtime provenance instrumentation not initialized")
    return _SETTINGS, _RECORDER, _TAG_MANAGER


def setup_flask_instrumentation() -> None:
    global _FLASK_PATCHED
    if _FLASK_PATCHED:
        return

    try:
        from flask import Flask  # type: ignore
    except Exception as exc:  # pragma: no cover - Flask must be available
        logger.warning("Flask not available, skipping Flask instrumentation: %s", exc)
        return

    original_init = Flask.__init__

    @wraps(original_init)
    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if getattr(self, "_runtime_provenance_hooks_installed", False):
            return
        install_flask_hooks(self)
        setattr(self, "_runtime_provenance_hooks_installed", True)

    Flask.__init__ = wrapped_init  # type: ignore[assignment]
    _FLASK_PATCHED = True


def install_flask_hooks(app) -> None:
    _, recorder, tag_manager = require_initialized()

    from flask import request, session
    from flask import has_request_context

    @app.before_request
    def _runtime_provenance_before_request():  # type: ignore[no-redef]
        if not has_request_context():
            return

        request_id = str(uuid4())
        ctx = RequestContext(request_id)
        token = _CTX.set(ctx)
        ctx.attach_token(token)

        recorder.record_request_start(
            request_id,
            method=request.method,
            path=request.path,
            remote_addr=request.remote_addr or "",
            user_agent=request.headers.get("User-Agent"),
            start_time=ctx.start_time,
        )

        now = datetime.utcnow()
        collect_and_tag_request_data(ctx, request, tag_manager, recorder, now)

    @app.after_request
    def _runtime_provenance_after_request(response):  # type: ignore[no-redef]
        ctx = get_ctx()
        if ctx is not None:
            ctx.status_code = getattr(response, "status_code", None)
        return response

    @app.teardown_request
    def _runtime_provenance_teardown(exception):  # type: ignore[no-redef]
        ctx = get_ctx()
        if ctx is None:
            return

        status_code: int | None = ctx.status_code
        if status_code is None:
            status_code = getattr(exception, "code", None) if exception else 200

        try:
            user_id = session.get("user_id")
        except Exception:  # When session is unavailable
            user_id = None

        recorder.record_request_end(
            ctx.request_id,
            status_code=status_code,
            end_time=datetime.utcnow(),
            user_id=str(user_id) if user_id is not None else None,
            exception=repr(exception) if exception else None,
        )

        ctx.reset(_CTX)


def collect_and_tag_request_data(
    ctx: RequestContext,
    request,
    tag_manager: TagManager,
    recorder: ProvenanceRecorder,
    timestamp: datetime,
) -> None:
    # Query parameters
    for key in request.args:
        values = request.args.getlist(key)
        for index, value in enumerate(values):
            tag = tag_manager.make_tag(
                ctx.request_id,
                source="query",
                field=key,
                value=value,
                metadata={"index": index},
            )
            ctx.register_tag("query", key, tag)
            recorder.record_data_event(
                ctx.request_id,
                event_type="ingress",
                tag=tag.tag,
                source="query",
                field=key,
                value_preview=tag.value_preview,
                raw_type=tag.raw_type,
                metadata={**tag.metadata, "value_hash": tag.value_hash},
                created_at=timestamp,
            )

    # Form data
    if request.form:
        for key in request.form:
            values = request.form.getlist(key)
            for index, value in enumerate(values):
                tag = tag_manager.make_tag(
                    ctx.request_id,
                    source="form",
                    field=key,
                    value=value,
                    metadata={"index": index},
                )
                ctx.register_tag("form", key, tag)
                recorder.record_data_event(
                    ctx.request_id,
                    event_type="ingress",
                    tag=tag.tag,
                    source="form",
                    field=key,
                    value_preview=tag.value_preview,
                    raw_type=tag.raw_type,
                    metadata={**tag.metadata, "value_hash": tag.value_hash},
                    created_at=timestamp,
                )

    # JSON payload
    payload = request.get_json(silent=True)
    if payload:
        for path, value in flatten_items(payload):
            tag = tag_manager.make_tag(
                ctx.request_id,
                source="json",
                field=path or "<root>",
                value=value,
            )
            ctx.register_tag("json", path or "<root>", tag)
            recorder.record_data_event(
                ctx.request_id,
                event_type="ingress",
                tag=tag.tag,
                source="json",
                field=path or "<root>",
                value_preview=tag.value_preview,
                raw_type=tag.raw_type,
                metadata={**tag.metadata, "value_hash": tag.value_hash},
                created_at=timestamp,
            )

    # Cookies (potential identifiers)
    if request.cookies:
        for key, value in request.cookies.items():
            tag = tag_manager.make_tag(
                ctx.request_id,
                source="cookie",
                field=key,
                value=value,
            )
            ctx.register_tag("cookie", key, tag)
            recorder.record_data_event(
                ctx.request_id,
                event_type="ingress",
                tag=tag.tag,
                source="cookie",
                field=key,
                value_preview=tag.value_preview,
                raw_type=tag.raw_type,
                metadata={**tag.metadata, "value_hash": tag.value_hash},
                created_at=timestamp,
            )


def setup_sqlalchemy_instrumentation() -> None:
    global _SQLALCHEMY_PATCHED
    if _SQLALCHEMY_PATCHED:
        return

    try:
        from sqlalchemy.orm import Session
        from sqlalchemy import inspect as sqlalchemy_inspect
    except Exception as exc:  # pragma: no cover
        logger.warning("SQLAlchemy not available, skipping instrumentation: %s", exc)
        return

    _, recorder, _ = require_initialized()

    def before_flush(session, flush_context, instances):  # type: ignore[no-redef]
        ctx = get_ctx()
        if ctx is None:
            return

        timestamp = datetime.utcnow()

        for obj in session.new:
            log_model_event(
                ctx,
                obj,
                operation="insert",
                timestamp=timestamp,
                recorder=recorder,
                inspector=sqlalchemy_inspect,
            )

        for obj in session.dirty:
            if session.is_modified(obj, include_collections=False):
                log_model_event(
                    ctx,
                    obj,
                    operation="update",
                    timestamp=timestamp,
                    recorder=recorder,
                    inspector=sqlalchemy_inspect,
                )

    from sqlalchemy import event

    event.listen(Session, "before_flush", before_flush, retval=False)
    _SQLALCHEMY_PATCHED = True


def log_model_event(
    ctx: RequestContext,
    obj: Any,
    *,
    operation: str,
    timestamp: datetime,
    recorder: ProvenanceRecorder,
    inspector,
) -> None:
    try:
        mapper = inspector(obj.__class__)
    except Exception as exc:  # pragma: no cover - only triggered for non-mapped objects
        logger.debug("Skipping non-mapped object %r: %s", obj, exc)
        return
    model_name = mapper.class_.__name__

    for column in mapper.columns:
        field = column.key
        try:
            value = getattr(obj, field)
        except AttributeError:
            continue
        if value is None:
            continue

        # Match against recorded tags by field name across sources
        tag_records = (
            list(ctx.get_tags("form", field))
            + list(ctx.get_tags("query", field))
            + list(ctx.get_tags("json", field))
        )

        if not tag_records:
            salt = _SETTINGS.hash_salt if _SETTINGS else ""
            value_hash = hash_preview(value, salt)
            tag_records = ctx.tags_by_hash().get(value_hash, [])

        matched_tag = tag_records[0] if tag_records else None

        recorder.record_storage_event(
            ctx.request_id,
            operation=operation,
            model=model_name,
            field=field,
            tag=matched_tag.tag if matched_tag else None,
            value_preview=short_preview(value, 200),
            metadata={
                "value_hash": matched_tag.value_hash if matched_tag else None,
                "sources": [t.source for t in tag_records],
            },
            created_at=timestamp,
        )


def setup_requests_instrumentation() -> None:
    global _REQUESTS_PATCHED
    if _REQUESTS_PATCHED:
        return

    try:
        import requests  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("requests library not available, skipping HTTP instrumentation: %s", exc)
        return

    _, recorder, _ = require_initialized()

    original_request = requests.Session.request

    @wraps(original_request)
    def wrapped_request(self, method, url, *args, **kwargs):  # type: ignore[override]
        ctx = get_ctx()
        timestamp = datetime.utcnow()
        tag_matches: List[str] = []

        if ctx is not None:
            payload_candidates = extract_payload_values(kwargs)
            tag_matches = match_tags(ctx, payload_candidates)

            recorder.record_share_event(
                ctx.request_id,
                tag_matches=tag_matches,
                destination=kwargs.get("headers", {}).get("Host", ""),
                method=str(method).upper(),
                url=url,
                payload_preview=short_preview(payload_candidates, 512),
                metadata={
                    "has_body": "data" in kwargs or "json" in kwargs,
                    "has_params": "params" in kwargs,
                },
                created_at=timestamp,
            )

        return original_request(self, method, url, *args, **kwargs)

    requests.Session.request = wrapped_request  # type: ignore[assignment]
    _REQUESTS_PATCHED = True


def extract_payload_values(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if "params" in kwargs and kwargs["params"]:
        payload["params"] = kwargs["params"]
    if "json" in kwargs and kwargs["json"]:
        payload["json"] = kwargs["json"]
    if "data" in kwargs and kwargs["data"]:
        payload["data"] = kwargs["data"]
    return payload


def match_tags(ctx: RequestContext, payload: Dict[str, Any]) -> List[str]:
    if not payload:
        return []

    hash_index = ctx.tags_by_hash()
    salt = _SETTINGS.hash_salt if _SETTINGS else ""
    matched: Dict[str, None] = {}
    for _, value in flatten_items(payload):
        hashed = hash_preview(value, salt)
        for tag_record in hash_index.get(hashed, []):
            matched[tag_record.tag] = None
    return list(matched.keys())
