from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .config import InstrumentationConfig, load_config
from .storage import ProvenanceStorage
from .tracker import RuntimeTracker
from . import flask_hooks, requests_patch, sqlalchemy_patch


_TRACKER: Optional[RuntimeTracker] = None


def get_tracker() -> RuntimeTracker:
    if _TRACKER is None:
        raise RuntimeError("Runtime tracker not initialised. Call init_runtime_tracking() first.")
    return _TRACKER


def bootstrap(*, app=None, db=None, config_path: Optional[str] = None) -> None:
    """
    Orchestrate initialisation of the runtime-level instrumentation.
    """
    config = _load_configuration(config_path)
    storage = ProvenanceStorage(config.storage_path)
    tracker = RuntimeTracker(storage=storage, config=config)

    global _TRACKER
    _TRACKER = tracker

    # Ensure persistent structures exist.
    storage.initialise()

    if app is not None:
        flask_hooks.register_flask_hooks(app, tracker)

    if db is not None:
        sqlalchemy_patch.instrument_sqlalchemy(db, tracker)

    requests_patch.patch_requests(tracker)


def _load_configuration(config_path: Optional[str]) -> InstrumentationConfig:
    if config_path:
        return load_config(Path(config_path))

    env_path = os.getenv("RUNTIME_TRACKING_CONFIG")
    if env_path:
        return load_config(Path(env_path))

    default_candidate = Path.cwd() / "runtime_tracking.yml"
    if default_candidate.exists():
        return load_config(default_candidate)

    return InstrumentationConfig.default()


def tracker_to_json() -> str:
    tracker = get_tracker()
    return json.dumps(tracker.describe(), indent=2)
