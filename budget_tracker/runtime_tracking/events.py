from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DataTag:
    fingerprint: str
    field: str
    category: str
    description: str
    owner: Optional[str]
    source: str
    preview: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ProvenanceEvent:
    event_type: str
    actor: str
    target: str
    payload: Dict[str, Any]
    request_id: Optional[str]
    user_id: Optional[str]
    matched_tags: List[DataTag] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now_iso)

    def as_record(self) -> Dict[str, Any]:
        data = dataclasses.asdict(self)
        data["matched_tags"] = [tag.as_dict() for tag in self.matched_tags]
        return data
