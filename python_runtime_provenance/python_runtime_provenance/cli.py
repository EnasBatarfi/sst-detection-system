"""Command-line interface for runtime provenance tracking."""

import sys
import os


def enable():
    """Enable runtime tracking."""
    os.environ['PYTHON_TRACKING_ENABLED'] = '1'
    print("Runtime tracking enabled. Restart Python to activate.")


def disable():
    """Disable runtime tracking."""
    os.environ['PYTHON_TRACKING_ENABLED'] = '0'
    print("Runtime tracking disabled. Restart Python to deactivate.")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'disable':
        disable()
    else:
        enable()
