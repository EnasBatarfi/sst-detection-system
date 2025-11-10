"""
Automatic runtime instrumentation bootstrap.

Python imports this module automatically (when reachable on ``sys.path``)
after the interpreter is initialized. Importing ``runtime_provenance``
installs the server-side tracking detection hooks without modifying the
application code.
"""

try:
    import runtime_provenance  # noqa: F401
except Exception as exc:  # pragma: no cover - instrumentation should not break runtime
    import logging

    logging.getLogger("runtime_provenance").exception(
        "Failed to initialize runtime provenance instrumentation: %s", exc
    )
