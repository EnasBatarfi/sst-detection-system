"""
Python Runtime Provenance Tracking System

A runtime-level instrumentation system for detecting Server-Side Tracking (SST)
that works at the Python interpreter level, requiring zero application code changes.
"""

from .tracking import (
    enable_runtime_tracking,
    disable_runtime_tracking,
    get_tracker,
    instrument_flask_app,
    is_tracking_enabled
)
from .runtime_instrumentation import (
    enable_deep_instrumentation,
    disable_deep_instrumentation,
    is_deep_instrumentation_enabled
)

__version__ = '1.0.0'
__all__ = [
    'enable_runtime_tracking',
    'disable_runtime_tracking',
    'get_tracker',
    'instrument_flask_app',
    'is_tracking_enabled',
    'enable_deep_instrumentation',
    'disable_deep_instrumentation',
    'is_deep_instrumentation_enabled',
]
