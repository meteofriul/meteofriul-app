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

    def read():
        response = get(*args, **kwargs)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            if error.response is None:
                error.response = response
            close = getattr(response, "close", None)
            if close is not None:
                close()
            raise
        return response

    return read_with_single_transient_retry(read, sleep=sleep)


def read_with_single_transient_retry(read: Callable[[], Any], *, sleep=None):
    """Retry one complete read; parsers and size/identity checks remain fail-closed.

    Source workers retain their outer wall-clock budgets. A retry cannot extend
    that budget, and partial bytes from a failed read are never reused.
    """
    pause = sleep or time.sleep
    for attempt in range(2):
        try:
            return read()
        except (requests.Timeout, requests.ConnectionError):
            if attempt:
                raise
        except requests.HTTPError as error:
            error_response = getattr(error, "response", None)
            status_code = getattr(error_response, "status_code", None)
            if attempt or status_code not in EVENT_SOURCE_TRANSIENT_STATUS_CODES:
                raise
        pause(EVENT_SOURCE_RETRY_DELAY_SECONDS)

    raise RuntimeError("event_source_retry_unreachable")


__all__ = [
    "EVENT_SOURCE_RETRY_DELAY_SECONDS",
    "EVENT_SOURCE_TRANSIENT_STATUS_CODES",
    "get_with_single_transient_retry",
    "read_with_single_transient_retry",
]
