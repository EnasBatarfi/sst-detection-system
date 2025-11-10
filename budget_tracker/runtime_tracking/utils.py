from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Iterator, Tuple


def create_fingerprint(value: Any) -> str:
    """
    Generate a deterministic fingerprint for any serialisable value.
    """
    try:
        serialised = json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        serialised = repr(value)
    hasher = hashlib.sha256()
    hasher.update(serialised.encode("utf-8", errors="replace"))
    return hasher.hexdigest()


def flatten_payload(payload: Any) -> Iterator[Tuple[str, Any]]:
    """
    Yield dotted-path -> value mappings from nested dictionaries/lists.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            sub_key = str(key)
            for nested_key, nested_value in flatten_payload(value):
                if nested_key:
                    yield f"{sub_key}.{nested_key}", nested_value
                else:
                    yield sub_key, nested_value
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            for nested_key, nested_value in flatten_payload(value):
                if nested_key:
                    yield f"{index}.{nested_key}", nested_value
                else:
                    yield str(index), nested_value
    else:
        yield "", payload


def redact_preview(value: Any, max_length: int = 80) -> str:
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
