# Runtime Provenance Instrumentation

This package injects runtime-level instrumentation into the Flask
application. Data collection, transformation, persistence, and outbound
sharing are tracked without modifying application code. Instrumentation is
activated automatically via `sitecustomize.py`.

## Features

- **Automatic request tagging**: Query parameters, form fields, JSON bodies,
  and cookies are tagged at ingress with per-request identifiers.
- **Database auditing**: Inserts and updates captured via SQLAlchemy session
  hooks, linking ORM field assignments back to ingress tags.
- **Outgoing HTTP monitoring**: `requests.Session.request` patched to capture
  exfiltration attempts and associate payloads with ingress tags when hashes
  match.
- **Centralized storage**: Events persisted in `runtime_provenance.db`
  (configurable through `PROVENANCE_DB_PATH`).
- **Zero app modifications**: Flask hooks installed by wrapping
  `Flask.__init__`; no decorators or blueprint changes are required.

## Configuration

Environment variables:

- `PROVENANCE_DISABLE=1` – disable instrumentation
- `PROVENANCE_DB_PATH=/custom/path.db` – override database location
- `PROVENANCE_LOG_LEVEL=DEBUG|INFO|...`
- `PROVENANCE_CAPTURE_LIMIT=2048` – preview length used for stored payloads
- `PROVENANCE_HASH_SALT=...` – optional salt for hashing tagged values

## Inspecting Logs

Use the CLI helper to inspect captured provenance records:

```bash
python3 -m runtime_provenance.cli requests --limit 10
python3 -m runtime_provenance.cli data --request-id <uuid>
python3 -m runtime_provenance.cli share --limit 5
```

The SQLite schema contains:

- `requests` – per-request metadata (method, path, user, response)
- `data_events` – ingress tags assigned to user-provided data
- `storage_events` – ORM persistence operations referencing tags
- `share_events` – outgoing network requests with tag matches, if any

## Extending

- Add new boundary detectors by registering additional hooks in
  `setup_sqlalchemy_instrumentation` or patching other client libraries
  (e.g., SMTP).
- Use `match_tags` as a reference for hashing strategies when adding new
  sinks/sources; the same hashing primitive ensures deterministic matching.
- Integration tests can query `runtime_provenance.db` to assert compliance.
