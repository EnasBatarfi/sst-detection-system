"""
Python sitecustomize.py - Auto-loads runtime tracking on Python startup

This file is automatically executed when Python starts (if installed in site-packages).
It enables runtime-level tracking without any code changes.

To disable: Set environment variable PYTHON_TRACKING_ENABLED=0
"""

import os

# Only enable if not explicitly disabled
if os.getenv('PYTHON_TRACKING_ENABLED', '').lower() not in ('0', 'false', 'no'):
    try:
        # Import and enable runtime tracking from installed package
        import python_runtime_provenance
        python_runtime_provenance.enable_runtime_tracking()
    except ImportError:
        # Package not installed, silently fail
        pass
    except Exception as e:
        # Silently fail if tracking can't be enabled
        if os.getenv('PYTHON_TRACKING_DEBUG'):
            import traceback
            traceback.print_exc()
