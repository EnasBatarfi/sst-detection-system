from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    enabled: bool
    db_path: Path
    log_level: str
    capture_limit: int
    hash_salt: str


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def load_settings() -> Settings:
    enabled = not _env_flag("PROVENANCE_DISABLE", default=False)

    default_db = (
        Path(os.environ.get("PROVENANCE_DB_PATH"))
        if os.environ.get("PROVENANCE_DB_PATH")
        else Path(__file__).resolve().parent.parent / "runtime_provenance.db"
    )

    return Settings(
        enabled=enabled,
        db_path=default_db,
        log_level=os.environ.get("PROVENANCE_LOG_LEVEL", "INFO").upper(),
        capture_limit=_env_int("PROVENANCE_CAPTURE_LIMIT", 2048),
        hash_salt=os.environ.get("PROVENANCE_HASH_SALT", ""),
    )
