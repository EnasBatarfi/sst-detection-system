# SST Detection System - Runtime-Level Instrumentation

This system provides **true runtime-level instrumentation** for detecting Server-Side Tracking (SST) by modifying Python's execution at the interpreter level, **without monkey patching**.

## Architecture

The system uses three complementary techniques:

### 1. Execution Tracing (`execution_tracer.py`)
Uses `sys.settrace` to trace Python execution at runtime:
- Tracks function calls and returns
- Monitors variable assignments
- Detects external API calls
- Tracks data flow through operations

### 2. Import Hooks (`import_hook.py`)
Uses `sys.meta_path` to intercept module imports:
- Intercepts module loading
- Injects tracking code at import time
- Works before code execution

### 3. AST Transformation (`ast_transformer.py`)
Rewrites Python code at import time:
- Transforms Abstract Syntax Tree
- Injects tagging calls
- Wraps external API calls
- Adds data operation tracking

## Key Differences from Monkey Patching

| Monkey Patching | Runtime Instrumentation |
|----------------|------------------------|
| Modifies objects after import | Modifies code at import time |
| Replaces function references | Injects code into AST |
| Can be bypassed | Harder to bypass |
| Runtime overhead | Compile-time transformation |
| Requires patching each library | Works automatically |

## Installation

```python
from sst_detection_system.integration import setup_instrumentation

# In your Flask app
app = Flask(__name__)

# Set up instrumentation (before any imports that need tracking)
setup_instrumentation(
    app=app,
    enable_tracing=True,
    enable_import_hook=True,
    instrument_user_code=True
)
```

## How It Works

### Execution Tracing

When enabled, `sys.settrace` is set to trace every:
- Function call
- Line execution
- Return statement
- Exception

The tracer:
1. Detects when external APIs are called
2. Checks if arguments contain tagged data
3. Logs data sharing events
4. Tracks data flow through operations

### Import Hooks

When a module is imported:
1. Import hook intercepts the import
2. AST transformer rewrites the code
3. Tracking calls are injected
4. Modified code is executed

Example transformation:

**Original code:**
```python
def get_insights(income, expenses):
    prompt = f"Income: {income}, Expenses: {expenses}"
    response = client.responses.create(input=prompt)
    return response
```

**Transformed code:**
```python
def get_insights(income, expenses):
    _check_and_tag(income)  # Injected
    _check_and_tag(expenses)  # Injected
    prompt = f"Income: {income}, Expenses: {expenses}"
    _check_and_tag(prompt)  # Injected
    response = _track_external_call(client.responses.create(input=prompt))  # Wrapped
    return response
```

### AST Transformation

The AST transformer:
- Visits all function definitions
- Adds parameter tagging
- Wraps external API calls
- Tags assignments with personal data
- Injects tracking for data operations

## Usage

### Basic Setup

```python
from sst_detection_system.integration import setup_instrumentation
from flask import Flask

app = Flask(__name__)

# Set up before importing other modules
setup_instrumentation(app)

# Now your code is automatically instrumented
from your_module import your_function
```

### Configuration

```python
setup_instrumentation(
    app=app,
    enable_tracing=True,          # Use sys.settrace
    enable_import_hook=True,       # Use import hooks
    instrument_user_code=True,     # Instrument all user code
    excluded_modules=[             # Modules to exclude
        'pytest',
        'unittest',
        'flask',
    ]
)
```

### Manual Control

```python
from sst_detection_system.runtime_instrumentation import RuntimeInstrumentation

instrumentation = RuntimeInstrumentation(
    enable_tracing=True,
    enable_import_hook=True
)

instrumentation.start()
# Your code here
instrumentation.stop()
```

## What Gets Tracked

### Automatic Tagging
- Function parameters containing personal data
- String values matching personal data patterns
- Variables assigned from tagged sources

### External API Detection
- `requests.post/get/put/delete`
- `urllib.request.urlopen`
- `openai.OpenAI` calls
- Any function in external libraries

### Data Operations
- Database writes (`db.session.add`, `db.session.commit`)
- File writes (`open(..., 'w')`)
- Any operation that persists data

## Performance Considerations

### Execution Tracing (`sys.settrace`)
- **Overhead**: High - traces every line
- **Use**: For detailed debugging and development
- **Production**: Consider disabling or using selectively

### Import Hooks + AST Transformation
- **Overhead**: Low - one-time transformation at import
- **Use**: For production deployments
- **Benefit**: No runtime overhead after import

### Recommended Configuration

**Development:**
```python
setup_instrumentation(
    enable_tracing=True,      # Detailed tracking
    enable_import_hook=True   # Code transformation
)
```

**Production:**
```python
setup_instrumentation(
    enable_tracing=False,     # Lower overhead
    enable_import_hook=True   # Still transform code
)
```

## Integration with Existing System

The runtime instrumentation works alongside the existing provenance tracking:

1. **Runtime Tagger** (`runtime_tagger.py`) - Functions injected into code
2. **Provenance Tracker** - Tracks tagged data
3. **Audit Logger** - Logs data sharing events
4. **Database Models** - Stores provenance and audit logs

## Example: Tracking AI API Call

**Original code:**
```python
def generate_insight(income, expenses):
    prompt = f"User income: ${income}"
    return client.responses.create(input=prompt)
```

**What happens:**
1. AST transformer adds `_check_and_tag(income)` at function start
2. AST transformer wraps `client.responses.create` with `_track_external_call`
3. At runtime, `income` is tagged with provenance metadata
4. When API is called, execution tracer detects it
5. Audit log entry is created automatically

**Result:**
- No code changes needed
- Automatic tracking
- Complete audit trail

## Limitations

1. **C Extensions**: Cannot instrument C extension modules
2. **Dynamic Code**: `eval()` and `exec()` with strings are harder to track
3. **Performance**: Execution tracing has significant overhead
4. **Complexity**: AST transformation can break some code patterns

## Troubleshooting

### Code not being instrumented
- Check that import hook is installed before imports
- Verify module is not in excluded_modules
- Check that module is in instrumented_modules (if specified)

### Performance issues
- Disable execution tracing in production
- Use import hooks only (lower overhead)
- Exclude performance-critical modules

### Import errors
- Ensure `runtime_tagger.py` is importable
- Check that provenance/audit_logger modules are available
- Verify Python path includes necessary directories

## Advanced Usage

### Custom AST Transformers

```python
from sst_detection_system.ast_transformer import SSTASTTransformer

class CustomTransformer(SSTASTTransformer):
    def visit_Call(self, node):
        # Custom transformation logic
        return super().visit_Call(node)
```

### Selective Instrumentation

```python
# Only instrument specific modules
setup_instrumentation(
    instrumented_modules=['budget_tracker', 'ai_insights'],
    excluded_modules=['tests', 'utils']
)
```

## Comparison with Monkey Patching

| Feature | Monkey Patching | Runtime Instrumentation |
|---------|----------------|------------------------|
| Code Changes | None | None |
| Library Support | Must patch each | Automatic |
| Bypass Risk | Higher | Lower |
| Performance | Low overhead | Medium (tracing) / Low (AST) |
| Complexity | Medium | Higher |
| Production Ready | Yes | Yes (with AST only) |

## References

- Python `sys.settrace`: https://docs.python.org/3/library/sys.html#sys.settrace
- Import Hooks: https://docs.python.org/3/reference/import.html
- AST Module: https://docs.python.org/3/library/ast.html
