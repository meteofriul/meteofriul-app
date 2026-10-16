"""Shared Android Play release policy for push enrollment and delivery."""

from __future__ import annotations

import re


_PLAY_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}\+([1-9][0-9]*)$")
MAX_PLAY_VERSION_CODE = 2_147_483_647


def parse_min_play_version_code(value: str) -> int | None:
    """Parse the optional server-side floor, rejecting malformed settings."""

    raw = str(value or "").strip()
    if not raw:
        return None
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        raise ValueError("invalid minimum Play versionCode")
    version_code = int(raw)
    if version_code > MAX_PLAY_VERSION_CODE:
        raise ValueError("minimum Play versionCode is too large")
    return version_code


def parse_play_version_code(app_version: str) -> int | None:
    """Read the native versionCode from ``versionName+versionCode``."""

    match = _PLAY_VERSION_RE.fullmatch(str(app_version or "").strip().lower())
    if match is None:
        return None
    version_code = int(match.group(1))
    return version_code if version_code <= MAX_PLAY_VERSION_CODE else None


def android_app_version_allowed(
    app_version: str,
    *,
    allowed_app_versions: frozenset[str],
    min_app_version_code: int | None,
) -> bool:
    normalized = str(app_version or "").strip().lower()
    if min_app_version_code is not None:
        version_code = parse_play_version_code(normalized)
        return version_code is not None and version_code >= min_app_version_code
    return normalized in allowed_app_versions
