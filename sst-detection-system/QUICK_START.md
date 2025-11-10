# Quick Start - Runtime Instrumentation (No Monkey Patching)

## What Changed

The system now uses **true runtime-level instrumentation** instead of monkey patching:

1. **Execution Tracing** (`sys.settrace`) - Traces Python execution at runtime
2. **Import Hooks** (`sys.meta_path`) - Intercepts module imports
3. **AST Transformation** - Rewrites code at import time

## Key Benefits

✅ **No Monkey Patching** - Code is modified at import time, not after
✅ **Harder to Bypass** - Instrumentation happens before code execution
✅ **Automatic** - Works for all imported modules (when enabled)
✅ **Lower Overhead** - AST transformation has minimal runtime cost

## Usage in Flask App

The Flask app (`budget_tracker/app.py`) has been updated to use the new system:

```python
from integration import setup_instrumentation

# Set up before other imports
setup_instrumentation(
    app=app,
    enable_tracing=True,      # Use sys.settrace
    enable_import_hook=True,   # Use import hooks + AST
    instrument_user_code=True
)
```

## How It Works

### 1. Import Hooks
When a module is imported:
- Import hook intercepts it
- AST transformer rewrites the code
- Tracking calls are injected
- Modified code executes

### 2. Execution Tracing
During execution:
- `sys.settrace` monitors every function call
- Detects external API calls
- Checks for tagged data
- Logs data sharing events

### 3. AST Transformation
Code is transformed:
```python
# Original
def get_insight(income):
    return client.create(input=f"Income: {income}")

# Transformed
def get_insight(income):
    _check_and_tag(income)  # Injected
    return _track_external_call(client.create(input=f"Income: {income}"))  # Wrapped
```

## Configuration

### Development (Full Tracking)
```python
setup_instrumentation(
    enable_tracing=True,      # Detailed execution tracing
    enable_import_hook=True   # Code transformation
)
```

### Production (Lower Overhead)
```python
setup_instrumentation(
    enable_tracing=False,     # Disable tracing (high overhead)
    enable_import_hook=True   # Keep AST transformation (low overhead)
)
```

## Files Created

- `execution_tracer.py` - sys.settrace implementation
- `import_hook.py` - Import hook for module interception
- `ast_transformer.py` - AST code transformation
- `runtime_tagger.py` - Functions injected into code
- `runtime_instrumentation.py` - Main orchestration class
- `integration.py` - Flask integration helper

## Testing

The system is integrated into your Flask app. When you run:

```bash
python budget_tracker/app.py
```

The instrumentation will:
1. Start execution tracing
2. Install import hooks
3. Transform imported modules
4. Track all data sharing events

## Comparison

| Feature | Old (Monkey Patch) | New (Runtime Instrumentation) |
|---------|-------------------|------------------------------|
| Method | Replace functions | Transform code at import |
| Bypass Risk | Medium | Low |
| Performance | Low overhead | Medium (tracing) / Low (AST) |
| Code Changes | None | None |
| Automatic | Per-library | All modules |

## Next Steps

1. Run your Flask app - instrumentation starts automatically
2. Use the app normally - tracking happens transparently
3. Check audit logs at `/provenance/dashboard`
4. Adjust configuration based on performance needs
