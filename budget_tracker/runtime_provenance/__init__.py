"""
Runtime provenance package.

Importing this package installs runtime-level instrumentation for
server-side tracking detection. Instrumentation can be disabled by
setting the environment variable ``PROVENANCE_DISABLE=1``.
"""

from .instrumentation import initialize

initialize()

__all__ = ["initialize"]
