# Deep Python Runtime Instrumentation

This system uses **deep Python runtime instrumentation** instead of monkey patching. It hooks into Python's execution at the interpreter level.

## How It Works

### 1. sys.settrace - Function Call Tracing

Hooks into Python's trace function to track:
- Function calls (`event == 'call'`)
- Line execution (`event == 'line'`)
- Function returns (`event == 'return'`)

```python
sys.settrace(self._trace_calls)
```

This allows us to:
- Track every function call
- Inspect function arguments
- Check local variables for PII
- Track data flow through the program

### 2. sys.setprofile - Function Profiling

Hooks into Python's profile function to track:
- Function entry (with arguments)
- Function exit (with return value)

```python
sys.setprofile(self._profile_calls)
```

This allows us to:
- Detect API calls (requests.post, openai calls, etc.)
- Extract data from function arguments
- Track return values
- Log sharing events automatically

### 3. Import Hooks

Uses Python's import hook system to instrument modules:

```python
__builtins__.__import__ = _tracking_import
```

This allows us to:
- Intercept module imports
- Add instrumentation at import time
- Work with any Python module

### 4. SQLAlchemy Events

Uses SQLAlchemy's event system (not monkey patching):

```python
@event.listens_for(Engine, "before_cursor_execute")
```

This allows us to:
- Track database operations
- Detect PII in SQL parameters
- Log database writes

## Key Differences from Monkey Patching

| Aspect | Monkey Patching | Deep Instrumentation |
|--------|----------------|---------------------|
| Method | Replace functions | Hook into Python runtime |
| Coverage | Only patched functions | All function calls |
| Performance | Low overhead | Medium overhead |
| Transparency | Visible in code | Invisible to code |
| Detection | Function-specific | Universal |

## What Gets Tracked

### Automatic Detection

1. **Function Calls**: Every function call is traced
2. **PII Data Access**: Local variables checked for PII fields
3. **API Calls**: Automatically detects:
   - `requests.post()`, `requests.get()`, etc.
   - `openai.OpenAI().responses.create()`
   - Any HTTP/API function calls
4. **Data Flow**: Tracks how data moves through functions
5. **Return Values**: Checks return values for tagged data

### Example Flow

```python
# User code (no changes needed)
def signup():
    email = request.form['email']  # ← Detected via sys.settrace
    name = request.form['name']    # ← Detected via sys.settrace
    requests.post('https://api.example.com', json={'email': email})  # ← Detected via sys.setprofile
```

The instrumentation automatically:
1. Tags `email` and `name` when assigned
2. Detects the `requests.post` call
3. Extracts `email` from the JSON argument
4. Logs a sharing event

## Performance Considerations

### Overhead

- **sys.settrace**: ~10-30% overhead (tracks every line)
- **sys.setprofile**: ~5-15% overhead (tracks function calls)
- **Combined**: ~15-40% overhead

### Optimization

- Depth limiting: Only traces up to `max_depth` levels
- Selective tracing: Can be disabled for specific modules
- Lazy evaluation: Only processes PII fields

## Configuration

### Enable Deep Instrumentation

```python
from python_runtime_provenance import enable_deep_instrumentation
enable_deep_instrumentation()
```

Or via environment:

```bash
export PYTHON_TRACKING_ENABLED=1
```

### Disable Deep Instrumentation

```python
from python_runtime_provenance import disable_deep_instrumentation
disable_deep_instrumentation()
```

## Advantages

1. **No Code Changes**: Works with any Python code
2. **Universal Coverage**: Tracks all function calls, not just patched ones
3. **Transparent**: Invisible to application code
4. **Comprehensive**: Catches everything, not just known APIs
5. **Future-Proof**: Works with new libraries automatically

## Limitations

1. **Performance**: Adds overhead to all function calls
2. **Depth**: Can't trace into C extensions deeply
3. **Complexity**: More complex than monkey patching
4. **Debugging**: Can make debugging harder

## Use Cases

- **Research**: Understanding data flow in applications
- **Security**: Detecting data leaks
- **Compliance**: GDPR/CCPA auditing
- **Debugging**: Tracing data through complex systems

## Technical Details

### Trace Function Signature

```python
def trace_calls(frame, event, arg):
    # frame: Current execution frame
    # event: 'call', 'line', 'return', 'exception'
    # arg: Event-specific argument
    return trace_calls  # Return function to continue tracing
```

### Profile Function Signature

```python
def profile_calls(frame, event, arg):
    # frame: Current execution frame
    # event: 'call', 'return', 'c_call', 'c_return'
    # arg: Event-specific argument
```

### Frame Inspection

```python
frame.f_code.co_name      # Function name
frame.f_code.co_filename  # File name
frame.f_locals           # Local variables
frame.f_globals          # Global variables
frame.f_lineno           # Line number
```

This deep instrumentation approach provides comprehensive tracking at the Python interpreter level, without requiring any monkey patching or code modifications.
