from __future__ import annotations

import json
import hashlib
from datetime import datetime
from typing import Any, Dict, Iterable, Tuple


def isoformat(dt: datetime) -> str:
    return dt.replace(microsecond=int(dt.microsecond / 1000) * 1000).isoformat()


def hash_preview(value: Any, salt: str = "", limit: int = 32) -> str:
    try:
        text = json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(value)
    digest = hashlib.sha256((salt + text).encode("utf-8")).hexdigest()
    return digest[:limit]


def short_preview(value: Any, limit: int) -> str:
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, sort_keys=True, default=str)
        except (TypeError, ValueError):
            text = str(value)
    else:
        text = str(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def flatten_items(data: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten_items(value, new_prefix)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            new_prefix = f"{prefix}[{index}]"
            yield from flatten_items(value, new_prefix)
    else:
        yield prefix, data


def ensure_json(data: Dict[str, Any]) -> str:
    try:
        return json.dumps(data, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return json.dumps({"warning": "unserializable metadata", "repr": repr(data)})
