from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from .events import DataTag
from .utils import create_fingerprint


@dataclass
class RequestContext:
    request_id: str
    user_id: Optional[str]
    path: str
    method: str
    client_ip: Optional[str] = None
    tags_by_fingerprint: Dict[str, DataTag] = field(default_factory=dict)

    def register_tag(self, *, field: str, category: str, description: str, value: object, owner: Optional[str], source: str) -> DataTag:
        fingerprint = create_fingerprint(value)
        preview = str(value)[:100] if value is not None else None
        tag = DataTag(
            fingerprint=fingerprint,
            field=field,
            category=category,
            description=description,
            owner=owner,
            source=source,
            preview=preview,
        )
        self.tags_by_fingerprint[fingerprint] = tag
        return tag

    def find_tags(self, fingerprints: Iterable[str]) -> List[DataTag]:
        return [self.tags_by_fingerprint[f] for f in fingerprints if f in self.tags_by_fingerprint]


_request_ctx: contextvars.ContextVar[Optional[RequestContext]] = contextvars.ContextVar("runtime_tracking_request_ctx", default=None)


def start_request(*, user_id: Optional[str], path: str, method: str, client_ip: Optional[str]) -> RequestContext:
    ctx = RequestContext(
        request_id=str(uuid4()),
        user_id=user_id,
        path=path,
        method=method,
        client_ip=client_ip,
    )
    _request_ctx.set(ctx)
    return ctx


def get_request() -> Optional[RequestContext]:
    return _request_ctx.get()


def end_request() -> None:
    _request_ctx.set(None)
