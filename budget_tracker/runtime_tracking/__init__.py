"""
Runtime-level instrumentation entry point for provenance-aware tracking.

`init_runtime_tracking` bootstraps the system and wires hooks into Flask,
SQLAlchemy, and outbound HTTP client libraries while keeping the host
application changes minimal (ideally just an import + init call).
"""

from __future__ import annotations

from typing import Optional

from . import instrumentation


_INITIALISED = False


def init_runtime_tracking(*, app=None, db=None, config_path: Optional[str] = None) -> None:
    """
    Initialise runtime tracking once per interpreter process.

    Parameters
    ----------
    app:
        Optional Flask application instance to hook into.
    db:
        Optional SQLAlchemy database object (the same instance used by the app).
    config_path:
        Optional path to a YAML/JSON configuration file overriding defaults.
    """
    global _INITIALISED
    if _INITIALISED:
        return

    instrumentation.bootstrap(app=app, db=db, config_path=config_path)
    _INITIALISED = True
