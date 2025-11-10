# Installation Guide: Python Runtime Provenance Tracking

## Quick Install

```bash
cd /workspace/python_runtime_provenance
pip install -e .
```

This installs the package system-wide and automatically enables tracking.

## Manual Installation Steps

### 1. Install the Package

```bash
cd /workspace/python_runtime_provenance
pip install -e .
```

Or install in development mode:

```bash
pip install -e /workspace/python_runtime_provenance
```

### 2. Verify Installation

```bash
python -c "import python_runtime_provenance; print('Installed!')"
```

### 3. Enable Tracking

Set environment variable:

```bash
export PYTHON_TRACKING_ENABLED=1
```

Or add to your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
export PYTHON_TRACKING_ENABLED=1
```

### 4. Test with Your App

```bash
cd /workspace/budget_tracker
export PYTHON_TRACKING_ENABLED=1
python app.py
```

You should see:
```
[Runtime Tracking] Python runtime instrumentation ENABLED
[Runtime Tracking] Tracking: HTTP requests, API calls, database operations, Flask requests
```

## How It Works

1. **Package Installation**: Installs `python_runtime_provenance` package and `sitecustomize.py`
2. **Auto-Load**: `sitecustomize.py` automatically runs when Python starts
3. **Import Hooks**: Patches Python's `__import__` to instrument modules
4. **Zero Code Changes**: Works automatically for any Python application

## Disable Tracking

```bash
export PYTHON_TRACKING_ENABLED=0
```

Or uninstall:

```bash
pip uninstall python-runtime-provenance
```

## Integration with Budget Tracker

The budget tracker app automatically connects to the runtime tracking if the package is installed. No code changes needed - just install the package and set the environment variable.

## Troubleshooting

**Not tracking?**
1. Check package is installed: `pip list | grep python-runtime-provenance`
2. Check environment variable: `echo $PYTHON_TRACKING_ENABLED`
3. Check Python can import: `python -c "import python_runtime_provenance"`

**Database not connected?**
- The tracker works in-memory if database models aren't available
- Check that your app connects the tracker (see `app.py`)

## Files Installed

- `python_runtime_provenance/` → Python site-packages
- `sitecustomize.py` → Python site-packages (auto-loads)

That's it! The tracking now works completely independently of your application code.
