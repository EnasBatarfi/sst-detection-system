"""
Integration module for Flask applications
Provides easy setup for runtime instrumentation
"""
import sys
import os

# Ensure we can import from budget_tracker
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from runtime_instrumentation import RuntimeInstrumentation
except ImportError:
    from sst_detection_system.runtime_instrumentation import RuntimeInstrumentation


# Global instrumentation instance
_instrumentation = None


def setup_instrumentation(app=None, 
                         enable_tracing=True,
                         enable_import_hook=True,
                         instrument_user_code=True,
                         excluded_modules=None):
    """
    Set up runtime instrumentation for a Flask application
    
    Args:
        app: Flask application instance (optional)
        enable_tracing: Enable execution tracing with sys.settrace
        enable_import_hook: Enable import hooks for AST transformation
        instrument_user_code: Whether to instrument user code (not just libraries)
        excluded_modules: List of module patterns to exclude from instrumentation
    """
    global _instrumentation
    
    # Default exclusions
    default_exclusions = [
        'site-packages',
        'dist-packages',
        '__pycache__',
        'pytest',
        'unittest',
        'flask',
        'werkzeug',
    ]
    
    if excluded_modules:
        default_exclusions.extend(excluded_modules)
    
    # Determine which modules to instrument
    instrumented_modules = None
    if instrument_user_code:
        # Instrument all user code (not site-packages)
        instrumented_modules = None
    else:
        # Only instrument specific modules
        instrumented_modules = ['budget_tracker']
    
    # Create instrumentation instance
    _instrumentation = RuntimeInstrumentation(
        enable_tracing=enable_tracing,
        enable_import_hook=enable_import_hook,
        enable_ast_transformation=enable_import_hook,
        instrumented_modules=instrumented_modules,
        excluded_modules=default_exclusions
    )
    
    # Start instrumentation
    _instrumentation.start()
    
    # If Flask app provided, add teardown handler
    if app:
        @app.teardown_appcontext
        def shutdown_instrumentation(error):
            """Shutdown instrumentation on app teardown"""
            # Don't actually stop here, just log
            pass
    
    return _instrumentation


def get_instrumentation():
    """Get the global instrumentation instance"""
    return _instrumentation


def shutdown_instrumentation():
    """Shutdown runtime instrumentation"""
    global _instrumentation
    if _instrumentation:
        _instrumentation.stop()
        _instrumentation = None
