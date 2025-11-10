from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Dict

from .utils import hash_preview, short_preview


@dataclass
class TagRecord:
    request_id: str
    source: str
    field: str
    tag: str
    value_preview: str
    value_hash: str
    raw_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class TagManager:
    def __init__(self, hash_salt: str, capture_limit: int):
        self._hash_salt = hash_salt
        self._capture_limit = capture_limit
        self._counter = itertools.count()

    def make_tag(
        self,
        request_id: str,
        source: str,
        field: str,
        value: Any,
        *,
        metadata: Dict[str, Any] | None = None,
    ) -> TagRecord:
        index = next(self._counter)
        tag = f"{request_id}:{source}:{field}:{index}"
        preview = short_preview(value, self._capture_limit)
        hashed = hash_preview(value, self._hash_salt)
        combined_preview = f"{preview} | sha256:{hashed}"

        return TagRecord(
            request_id=request_id,
            source=source,
            field=field,
            tag=tag,
            value_preview=combined_preview,
            value_hash=hashed,
            raw_type=type(value).__name__,
            metadata=metadata or {},
        )
