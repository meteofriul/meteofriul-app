from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests


EVENT_SOURCE_TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
EVENT_SOURCE_RETRY_DELAY_SECONDS = 0.5


def get_with_single_transient_retry(
    get: Callable[..., Any],
    *args: Any,
    sleep: Callable[[float], None] | None = None,
    **kwargs: Any,
):
    """Perform a GET with one bounded retry for transport-only failures."""

    pause = sleep or time.sleep
    for attempt in range(2):
        response = None
        try:
            response = get(*args, **kwargs)
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError):
            if attempt:
                raise
        except requests.HTTPError as error:
            error_response = getattr(error, "response", None)
            if error_response is None:
                error_response = response
            status_code = getattr(error_response, "status_code", None)
            if attempt or status_code not in EVENT_SOURCE_TRANSIENT_STATUS_CODES:
                raise
        pause(EVENT_SOURCE_RETRY_DELAY_SECONDS)

    raise RuntimeError("event_source_retry_unreachable")


__all__ = [
    "EVENT_SOURCE_RETRY_DELAY_SECONDS",
    "EVENT_SOURCE_TRANSIENT_STATUS_CODES",
    "get_with_single_transient_retry",
]
