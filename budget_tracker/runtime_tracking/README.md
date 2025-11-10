# Runtime Provenance Instrumentation

This package embeds server-side tracking detection directly into the Python runtime of the budget tracker application. It provides end-to-end provenance for data as it flows from HTTP entry points through persistence, computation, and outbound network interactions.

## Capabilities

- **Automatic request tagging** – All incoming request parameters are tagged with provenance metadata (category, field, owner, source). Tags propagate via a runtime registry that records fingerprints (SHA-256 hashes) of raw and derived values.
- **Database instrumentation** – SQLAlchemy flush events are intercepted to log storage and update operations. Tracked models/fields are defined in `config.py` (or an optional external YAML/JSON config). Every persistence event is recorded with associated provenance tags.
- **Outbound network monitoring** – The `requests` library is monkey-patched to log payloads sent to third parties, detect personal data within the payload, and persist share events with provenance context.
- **Audit API** – A self-contained Flask blueprint at `/runtime-audit` exposes JSON endpoints (`/events`, `/fingerprints`, `/status`) for auditing. Use an optional token via the `RUNTIME_TRACKING_AUDIT_TOKEN` environment variable to protect access.
- **Persistent evidence** – Events and fingerprints are stored in `runtime_provenance.db` (SQLite). The schema is created automatically on startup.

## Usage

Only a single line needs to be added in the host Flask application:

```python
from runtime_tracking import init_runtime_tracking

init_runtime_tracking(app=app, db=db)
```

Optional configuration can be supplied via a JSON or YAML file pointed to by the `RUNTIME_TRACKING_CONFIG` environment variable. Any unspecified values fall back to `config.InstrumentationConfig.default()`.

### Configuration Schema

```yaml
storage_path: runtime_provenance.db
audit_token: ""  # protects /runtime-audit endpoints when set
ignored_hosts:
  - localhost
input_fields:
  email:
    category: contact.email
    description: Email address
    pii: true
tracked_models:
  User:
    fields:
      email:
        category: contact.email
        description: User email
        owner_attribute: email
```

### Audit Endpoints

- `GET /runtime-audit/status` – high-level tracker diagnostics.
- `GET /runtime-audit/events?limit=50&event_type=DATA_SHARE` – recent provenance events.
- `GET /runtime-audit/fingerprints` – known PII fingerprints (SHA-256).

When `RUNTIME_TRACKING_AUDIT_TOKEN` is set, supply the same value via `X-Audit-Token` header or an `audit_token` query parameter.

## Extending

- Add or refine tracked models/fields by editing `config.py` or providing an external config file.
- Implement custom sinks by patching additional client libraries (e.g., SMTP, message queues) following the approach used in `requests_patch.py`.
- Emit manual provenance events by importing `runtime_tracking.instrumentation.get_tracker()` and calling `record_event`.

## Limitations

This runtime approach prioritises low-touch integration. It provides best-effort provenance tagging and matching based on value fingerprints; highly transformed or encrypted data may evade detection unless additional instrumentation is added. Consider extending the registry to hook into domain-specific computation hotspots (e.g., analytics or export functions) to attain full lineage coverage.
