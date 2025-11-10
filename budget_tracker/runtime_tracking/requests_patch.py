from __future__ import annotations

import json
from typing import Any, Dict
from urllib.parse import parse_qsl

import requests

from .tracker import RuntimeTracker

_ORIGINAL_REQUEST = None
_PATCHED = False


def patch_requests(tracker: RuntimeTracker) -> None:
    global _PATCHED, _ORIGINAL_REQUEST
    if _PATCHED:
        return

    _ORIGINAL_REQUEST = requests.sessions.Session.request

    def instrumented_request(self, method, url, **kwargs):
        payload_dict = _normalise_payload(kwargs)
        response = None
        error = None
        try:
            response = _ORIGINAL_REQUEST(self, method, url, **kwargs)
            return response
        except Exception as exc:
            error = exc
            raise
        finally:
            if tracker.config.ignored_hosts:
                from urllib.parse import urlparse

                hostname = urlparse(url).hostname
                if hostname and hostname in tracker.config.ignored_hosts:
                    return
            status_code = response.status_code if response is not None else None
            tracker.record_share_event(
                method=method,
                url=url,
                payload=payload_dict,
                response_status=status_code,
            )

    requests.sessions.Session.request = instrumented_request
    _PATCHED = True


def _normalise_payload(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if "json" in kwargs and kwargs["json"] is not None:
        payload["json"] = kwargs["json"]
    if "data" in kwargs and kwargs["data"] is not None:
        data = kwargs["data"]
        if isinstance(data, (dict, list)):
            payload["data"] = data
        else:
            try:
                payload["data"] = json.loads(data)
            except Exception:
                payload["data"] = dict(parse_qsl(str(data)))
    if "params" in kwargs and kwargs["params"] is not None:
        payload["params"] = kwargs["params"]
    if "headers" in kwargs and kwargs["headers"] is not None:
        payload["headers"] = {
            key: value for key, value in kwargs["headers"].items() if key.lower().startswith("x-")
        }
    return payload
