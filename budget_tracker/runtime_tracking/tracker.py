from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .config import FieldConfig, InstrumentationConfig, ModelConfig
from .context import get_request
from .events import DataTag, ProvenanceEvent
from .storage import ProvenanceStorage
from .utils import create_fingerprint, flatten_payload, redact_preview


@dataclass
class GlobalRegistry:
    tags: Dict[str, DataTag] = field(default_factory=dict)

    def register(self, tag: DataTag) -> None:
        if tag.fingerprint not in self.tags:
            self.tags[tag.fingerprint] = tag

    def match_fingerprints(self, fingerprints: Iterable[str]) -> List[DataTag]:
        return [self.tags[f] for f in fingerprints if f in self.tags]


class RuntimeTracker:
    def __init__(self, *, storage: ProvenanceStorage, config: InstrumentationConfig) -> None:
        self.storage = storage
        self.config = config
        self.registry = GlobalRegistry()

    # ---------------- Tag registration ----------------

    def register_input(self, *, field: str, description: str, category: str, value: Any, owner: Optional[str], source: str) -> DataTag:
        ctx = get_request()
        tag = None
        if ctx:
            tag = ctx.register_tag(field=field, description=description, category=category, value=value, owner=owner, source=source)
        else:
            tag = DataTag(
                fingerprint=create_fingerprint(value),
                field=field,
                category=category,
                description=description,
                owner=owner,
                source=source,
                preview=str(value)[:100],
            )
        self.registry.register(tag)
        self.storage.upsert_fingerprint(tag)
        return tag

    # ---------------- Event recording -----------------

    def record_event(self, event: ProvenanceEvent) -> None:
        self.storage.record_event(event)
        for tag in event.matched_tags:
            self.storage.upsert_fingerprint(tag, event_id=event.event_id)
            self.registry.register(tag)

    def record_collection(self, data: Dict[str, Any]) -> None:
        ctx = get_request()
        matched_tags: List[DataTag] = []
        for key, value in data.items():
            fingerprint = create_fingerprint(value)
            tags = self.registry.match_fingerprints([fingerprint])
            matched_tags.extend(tags)

        event = ProvenanceEvent(
            event_type="DATA_COLLECTION",
            actor="flask.request",
            target="application",
            payload=data,
            request_id=ctx.request_id if ctx else None,
            user_id=ctx.user_id if ctx else None,
            matched_tags=matched_tags,
        )
        self.record_event(event)

    def record_storage_event(self, *, model_name: str, action: str, instance_id: Optional[str], field_values: Dict[str, Any], owner: Optional[str]) -> None:
        ctx = get_request()
        matched = self.match_payload(field_values)
        event = ProvenanceEvent(
            event_type="DATA_STORAGE",
            actor=model_name,
            target=action,
            payload={"fields": field_values, "instance_id": instance_id},
            request_id=ctx.request_id if ctx else None,
            user_id=ctx.user_id if ctx else owner,
            matched_tags=matched,
            extras={"owner": owner},
        )
        self.record_event(event)

    def record_share_event(self, *, method: str, url: str, payload: Dict[str, Any], response_status: Optional[int]) -> None:
        ctx = get_request()
        matched = self.match_payload(payload)
        event = ProvenanceEvent(
            event_type="DATA_SHARE",
            actor="requests",
            target=url,
            payload={"method": method, "payload": payload, "response_status": response_status},
            request_id=ctx.request_id if ctx else None,
            user_id=ctx.user_id if ctx else None,
            matched_tags=matched,
        )
        self.record_event(event)

    # ---------------- Matching helpers ----------------

    def match_payload(self, payload: Dict[str, Any]) -> List[DataTag]:
        fingerprints = []
        for _, value in flatten_payload(payload):
            fingerprints.append(create_fingerprint(value))
        ctx = get_request()
        matched: List[DataTag] = []
        if ctx:
            matched.extend(ctx.find_tags(fingerprints))
        matched.extend(self.registry.match_fingerprints(fingerprints))
        # remove duplicates while preserving order
        unique = []
        seen = set()
        for tag in matched:
            if tag.fingerprint not in seen:
                unique.append(tag)
                seen.add(tag.fingerprint)
        return unique

    # ---------------- Config inspection ----------------

    def model_config(self, model_name: str) -> Optional[ModelConfig]:
        return self.config.tracked_models.get(model_name)

    def field_config(self, model_name: str, field_name: str) -> Optional[FieldConfig]:
        model = self.model_config(model_name)
        if not model:
            return None
        return model.fields.get(field_name)

    # ---------------- Diagnostics ----------------

    def describe(self) -> Dict[str, Any]:
        return {
            "registry_size": len(self.registry.tags),
            "storage_path": str(self.storage.path),
            "tracked_models": list(self.config.tracked_models.keys()),
            "input_fields": list(self.config.input_fields.keys()),
        }
