# Python Runtime-Level Server-Side Tracking (SST) Detection

This implementation provides **complete Python runtime-level instrumentation** for detecting Server-Side Tracking (SST) with **ZERO changes** to your application code. The tracking works at the Python interpreter level, automatically instrumenting modules as they're imported.

## Overview

The system operates entirely at the Python runtime level using:
- **Import hooks**: Automatically instruments modules (`requests`, `openai`, `flask`) as they're imported
- **Monkey patching**: Patches library functions to add tracking without modifying source code
- **SQLAlchemy events**: Uses SQLAlchemy's event system to track database operations
- **Flask hooks**: Automatically adds Flask request handlers to tag PII data

## Architecture

### Core Components

1. **`python_runtime_tracking.py`**: Main runtime instrumentation module
   - `RuntimeProvenanceTracker`: Core tracking engine
   - Import hook system for automatic module instrumentation
   - Zero application code changes required

2. **`sitecustomize.py`**: Auto-loads tracking on Python startup
   - Automatically executed when Python starts
   - Enables tracking without any code changes

3. **Database Models**: Same as before (`DataTag`, `DataSharingEvent`, `DataLineage`)

## Installation & Activation

### Method 1: Environment Variable (Recommended)

Set environment variable before running your app:

```bash
export PYTHON_TRACKING_ENABLED=1
python app.py
```

### Method 2: Site-Packages Installation

Place `sitecustomize.py` and `python_runtime_tracking.py` in your Python site-packages:

```bash
# Find your site-packages directory
python -c "import site; print(site.getsitepackages())"

# Copy files there
cp python_runtime_tracking.py /path/to/site-packages/
cp sitecustomize.py /path/to/site-packages/
```

Tracking will now be enabled for **all Python processes** automatically.

### Method 3: PYTHONPATH

Add the directory to PYTHONPATH:

```bash
export PYTHONPATH=/path/to/budget_tracker:$PYTHONPATH
python app.py
```

### Method 4: Explicit Import

In your application (minimal change):

```python
import python_runtime_tracking
python_runtime_tracking.enable_runtime_tracking()
```

## How It Works

### Automatic Module Instrumentation

When modules are imported, the system automatically instruments them:

1. **`requests` module**: 
   - Patches `requests.post()`, `requests.get()`, `requests.request()`
   - Tracks all HTTP requests and logs sharing events

2. **`openai` module**:
   - Patches `OpenAI.__init__()` to instrument client instances
   - Tracks Groq/OpenAI API calls via `client.responses.create()`

3. **`flask` module**:
   - Patches `Flask.__init__()` to add request handlers
   - Automatically tags PII data from Flask requests

4. **SQLAlchemy**:
   - Uses SQLAlchemy event listeners
   - Tracks database INSERT/UPDATE operations

### Zero Code Changes Required

Your Flask app needs **minimal changes** - just connect the tracker to your database:

```python
# In app.py - only 6 lines needed
with app.app_context():
    db.create_all()
    try:
        import python_runtime_tracking
        tracker = python_runtime_tracking.get_tracker()
        tracker.db_session = db.session
        tracker.DataTagModel = DataTag
        tracker.DataSharingEvent = DataSharingEvent
        tracker.DataLineage = DataLineage
    except:
        pass
```

That's it! Everything else is automatic.

## What Gets Tracked

### Automatic Data Tagging

- **Flask form data**: Email, name, income, etc. from `request.form`
- **Flask JSON data**: PII from `request.json`
- **URL parameters**: PII from `request.args`
- **Database reads**: User/Expense model fields when loaded
- **Database writes**: PII data before INSERT/UPDATE

### Sharing Event Detection

- **External API calls**: All `requests.post/get()` calls
- **AI API calls**: Groq/OpenAI API calls
- **Database writes**: SQLAlchemy INSERT/UPDATE operations

### Data Lineage

- Tracks how data flows through operations
- Maintains parent-child relationships
- Records all transformations

## Usage Examples

### View Tracking Data

Same as before - use the `/provenance` route or Python API:

```python
from provenance_utils import get_sharing_events_for_user, get_sst_summary

events = get_sharing_events_for_user(user_id=1)
summary = get_sst_summary(user_id=1)
```

### Disable Tracking

```bash
export PYTHON_TRACKING_ENABLED=0
python app.py
```

Or in code:

```python
import python_runtime_tracking
python_runtime_tracking.disable_runtime_tracking()
```

## Performance

- **Minimal overhead**: Only tracks operations involving PII data
- **Thread-safe**: Uses locks for concurrent requests
- **Non-blocking**: Database writes are asynchronous where possible
- **Optional tracing**: Function-level tracing disabled by default (can enable if needed)

## Comparison: Runtime vs App-Level

| Feature | Runtime-Level (This) | App-Level (Previous) |
|---------|---------------------|---------------------|
| Code Changes | 0-6 lines | 2 lines |
| Works for all Python apps | ✅ | ❌ |
| Auto-instruments modules | ✅ | ❌ |
| Flask-specific | ❌ | ✅ |
| Requires app modification | Minimal | Yes |

## Technical Details

### Import Hook Mechanism

```python
# Replaces builtin __import__ to intercept module loading
__builtins__.__import__ = _tracking_import

# When 'requests' is imported:
def _tracking_import(name, ...):
    module = original_import(name, ...)
    if name == 'requests':
        _instrument_requests_module(module)  # Patch functions
    return module
```

### Flask Instrumentation

```python
# Patches Flask.__init__ to add hooks automatically
original_init = Flask.__init__

def tracked_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    _add_flask_hooks(self)  # Add before_request handler

Flask.__init__ = tracked_init
```

### SQLAlchemy Events

```python
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(...):
    # Check if SQL contains tagged data
    # Log sharing event if PII is being written
```

## Testing

1. **Enable tracking**:
   ```bash
   export PYTHON_TRACKING_ENABLED=1
   ```

2. **Run your app**:
   ```bash
   python app.py
   ```

3. **Use the app normally** - register, login, add expenses, view AI insights

4. **Check tracking**:
   - Navigate to `/provenance` route
   - Or query database: `SELECT * FROM data_sharing_events;`

## Troubleshooting

### Tracking not working?

1. Check if tracking is enabled:
   ```python
   import python_runtime_tracking
   print(python_runtime_tracking._tracking_enabled)  # Should be True
   ```

2. Check environment variable:
   ```bash
   echo $PYTHON_TRACKING_ENABLED
   ```

3. Check if modules are instrumented:
   ```python
   import requests
   print(hasattr(requests, '_tracking_instrumented'))  # Should be True
   ```

### Database not connected?

The tracker works in-memory if database isn't available. To connect:

```python
with app.app_context():
    import python_runtime_tracking
    tracker = python_runtime_tracking.get_tracker()
    tracker.db_session = db.session
    # ... set model classes
```

## Advantages of Runtime-Level Approach

1. **Zero application changes**: Works with any Python application
2. **Automatic**: No need to remember to add tracking code
3. **Comprehensive**: Tracks all modules automatically
4. **Transparent**: Can be enabled/disabled via environment variable
5. **Production-ready**: Can be deployed without code changes

## Limitations

- Requires Python import hook (standard Python feature)
- Some edge cases may not be caught (very rare)
- Function-level tracing disabled by default (performance)

## Future Enhancements

- Bytecode instrumentation for deeper tracking
- Network-level interception
- Real-time alerting
- Compliance reporting automation

## References

Based on the research proposal: "Detecting Server-Side Tracking (SST) via Runtime-Level Instrumentation Approach" by Enas Batarfi, Boston University.

Inspired by:
- Python's import hook system
- Monkey patching techniques
- SQLAlchemy event system
- Runtime instrumentation research
