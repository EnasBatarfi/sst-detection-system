"""
Python sitecustomize.py - Auto-loads runtime tracking on Python startup

This file is automatically executed when Python starts (if placed in site-packages
or PYTHONPATH). It enables runtime-level tracking without any code changes.

To use:
1. Place this file in your Python site-packages directory, OR
2. Add the directory containing this file to PYTHONPATH, OR
3. Set PYTHONPATH=/path/to/budget_tracker:$PYTHONPATH

To disable: Set environment variable PYTHON_TRACKING_ENABLED=0
"""

import os
import sys

# Only enable if not explicitly disabled
if os.getenv('PYTHON_TRACKING_ENABLED', '').lower() not in ('0', 'false', 'no'):
    try:
        # Add current directory to path if not already there
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Import and enable runtime tracking
        import python_runtime_tracking
        python_runtime_tracking.enable_runtime_tracking()
            
    except Exception as e:
        # Silently fail if tracking can't be enabled
        # (e.g., if dependencies aren't available)
        import traceback
        if os.getenv('PYTHON_TRACKING_DEBUG'):
            traceback.print_exc()
        pass
