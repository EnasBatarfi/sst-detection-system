# Quick Start: Python Runtime-Level Tracking

## What Changed?

The tracking system now works at the **Python runtime level** instead of requiring Flask app integration. This means:

- ✅ **Zero code changes** to your application logic
- ✅ Works automatically via Python import hooks
- ✅ Can be enabled/disabled via environment variable
- ✅ Works for any Python application, not just Flask

## How to Enable

### Option 1: Environment Variable (Easiest)

```bash
export PYTHON_TRACKING_ENABLED=1
python app.py
```

### Option 2: PYTHONPATH

```bash
export PYTHONPATH=/workspace/budget_tracker:$PYTHONPATH
python app.py
```

The `sitecustomize.py` file will automatically load and enable tracking.

### Option 3: Explicit Import

Add to the top of `app.py`:

```python
import python_runtime_tracking
python_runtime_tracking.enable_runtime_tracking()
```

## What Gets Tracked Automatically

Once enabled, the system automatically tracks:

1. **HTTP Requests** (`requests` library)
   - All `requests.post()`, `requests.get()` calls
   - Logs destination URL and data sent

2. **AI API Calls** (OpenAI/Groq)
   - All `client.responses.create()` calls
   - Tracks prompts containing user data

3. **Flask Requests**
   - Automatically tags PII from `request.form`, `request.json`, `request.args`
   - No code changes needed!

4. **Database Operations**
   - SQLAlchemy INSERT/UPDATE operations
   - Tracks when PII is written to database

## Minimal App Changes

Your `app.py` only needs these 6 lines (already added):

```python
with app.app_context():
    db.create_all()
    try:
        import python_runtime_tracking
        python_runtime_tracking.instrument_flask_app(app)
        tracker = python_runtime_tracking.get_tracker()
        tracker.db_session = db.session
        tracker.DataTagModel = DataTag
        tracker.DataSharingEvent = DataSharingEvent
        tracker.DataLineage = DataLineage
    except:
        pass
```

This just connects the runtime tracker to your database. All tracking happens automatically!

## Verify It's Working

1. Start your app with tracking enabled
2. Register a new user
3. Add some expenses
4. View AI insights
5. Check `/provenance` route - you should see all tracking events!

## Disable Tracking

```bash
export PYTHON_TRACKING_ENABLED=0
python app.py
```

Or in code:

```python
import python_runtime_tracking
python_runtime_tracking.disable_runtime_tracking()
```

## Files

- `python_runtime_tracking.py` - Main runtime instrumentation
- `sitecustomize.py` - Auto-loads on Python startup
- `PYTHON_RUNTIME_TRACKING_README.md` - Full documentation

## Key Advantages

| Feature | Runtime-Level | App-Level |
|---------|--------------|-----------|
| Code Changes | 0-6 lines | 2+ lines |
| Works for all apps | ✅ | ❌ |
| Auto-instruments | ✅ | ❌ |
| Environment control | ✅ | ❌ |

## Troubleshooting

**Not tracking?** Check:
1. `PYTHON_TRACKING_ENABLED=1` is set
2. `python_runtime_tracking` module is importable
3. Check console for "[Runtime Tracking] ENABLED" message

**Database not connected?** The tracker works in-memory if database isn't available. The 6 lines in `app.py` connect it to your database.

That's it! The system now works completely at the Python runtime level with minimal changes to your application.
