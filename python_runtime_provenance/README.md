# Python Runtime Provenance Tracking

A standalone Python package for runtime-level Server-Side Tracking (SST) detection that works at the Python interpreter level, requiring **zero application code changes**.

## Installation

### Option 1: Install as Python Package (Recommended)

```bash
cd python_runtime_provenance
pip install -e .
```

This installs the package system-wide and automatically enables tracking via `sitecustomize.py`.

### Option 2: Manual Installation

Copy to Python site-packages:

```bash
# Find site-packages
python -c "import site; print(site.getsitepackages())"

# Copy package
cp -r python_runtime_provenance /path/to/site-packages/
cp sitecustomize.py /path/to/site-packages/
```

## Usage

### Enable Tracking

Set environment variable:

```bash
export PYTHON_TRACKING_ENABLED=1
python your_app.py
```

Or use CLI:

```bash
enable-provenance-tracking
```

### Disable Tracking

```bash
export PYTHON_TRACKING_ENABLED=0
python your_app.py
```

Or:

```bash
disable-provenance-tracking
```

## Integration with Your App

The tracking works automatically for any Python application. To connect it to your database (optional):

```python
# In your Flask app (or any app)
from python_runtime_provenance import get_tracker

# Connect to your database
with app.app_context():
    tracker = get_tracker()
    tracker.connect_database(
        db_session=db.session,
        DataTagModel=DataTag,
        DataSharingEvent=DataSharingEvent,
        DataLineage=DataLineage
    )
```

If database is not connected, tracking works in-memory only.

## What Gets Tracked

- **HTTP Requests** (`requests` library)
- **AI API Calls** (OpenAI/Groq)
- **Flask Requests** (PII from forms/JSON)
- **Database Operations** (SQLAlchemy INSERT/UPDATE)

## Files

- `python_runtime_provenance/` - Main package
- `sitecustomize.py` - Auto-loads on Python startup
- `setup.py` - Installation script

## License

Based on research proposal: "Detecting Server-Side Tracking (SST) via Runtime-Level Instrumentation Approach"
