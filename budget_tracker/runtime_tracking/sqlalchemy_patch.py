from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import event

from .tracker import RuntimeTracker


def instrument_sqlalchemy(db, tracker: RuntimeTracker) -> None:
    session = db.session

    @event.listens_for(session, "before_flush")
    def _before_flush(session, flush_context, instances):
        for obj in session.new:
            _process_instance(tracker, obj, action="insert")
        for obj in session.dirty:
            if session.is_modified(obj, include_collections=False):
                _process_instance(tracker, obj, action="update")


def _process_instance(tracker: RuntimeTracker, obj: Any, *, action: str) -> None:
    model_name = obj.__class__.__name__
    model_config = tracker.model_config(model_name)
    if not model_config:
        return

    owner = None
    field_values: Dict[str, Any] = {}

    for field_name, field_config in model_config.fields.items():
        try:
            value = getattr(obj, field_name)
        except AttributeError:
            continue
        field_values[field_name] = value
        if field_config.owner_attribute:
            try:
                owner = getattr(obj, field_config.owner_attribute)
            except AttributeError:
                owner = None
        if value is None:
            continue
        if field_config.pii:
            tracker.register_input(
                field=f"{model_name}.{field_name}",
                description=field_config.description,
                category=field_config.category,
                value=value,
                owner=owner,
                source=f"model:{model_name}",
            )

    instance_id = getattr(obj, "id", None) or getattr(obj, "uuid", None)
    tracker.record_storage_event(
        model_name=model_name,
        action=action,
        instance_id=str(instance_id) if instance_id is not None else None,
        field_values=field_values,
        owner=str(owner) if owner is not None else None,
    )
