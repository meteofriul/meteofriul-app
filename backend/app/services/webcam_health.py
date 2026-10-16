from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Literal
from urllib.parse import unquote, urlsplit

import requests

from app.contracts.live import WebcamRecord


DEFAULT_HEALTH_TIMEOUT_SECONDS = 6.0
DEFAULT_SAMPLE_BYTES = 64 * 1024
HEALTH_USER_AGENT = "Meteo-Friul-Webcam-Check/1.0 (+https://meteofriul.it)"
GENERIC_SOURCE_PATHS = frozenset({
    "",
    "/home",
    "/homepage",
    "/index",
    "/index.htm",
    "/index.html",
    "/it",
    "/en",
})
CAMERA_TEXT_PATTERN = re.compile(
    r"\bweb\s*cam(?:s)?\b|\blive\s*cam\b|\btelecamera\b|"
    r"\bvideo\s*camera\b|\bcamera\s+(?:live|in\s+diretta)\b"
)
PLAYER_TEXT_PATTERN = re.compile(
    r"\.m3u8\b|\bjwplayer\b|\bvideo[\s_-]*js\b|\bhls(?:\.js)?\b|"
    r"\bpanomax\b|\bwhatsupcams\b|\bweathercam\b|\bsnapshot\b"
)
CAMERA_EMBED_PATTERN = re.compile(
    r"<(?:iframe|video|source|img|script)\b[^>]{0,1200}"
    r"(?:web\s*cam|live\s*cam|panomax|whatsupcams|weathercam|"
    r"snapshot|\.m3u8|jwplayer|video[\s_-]*js|hls(?:\.js)?)",
    re.IGNORECASE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme.lower() == "https" and bool(parsed.hostname)
    except ValueError:
        return False


def _normalized_url_identity(value: str) -> tuple[str, str, str]:
    parsed = urlsplit(value)
    path = unquote(parsed.path or "/").lower().rstrip("/")
    return (str(parsed.hostname or "").lower(), path, parsed.query)


def _is_generic_source_url(value: str) -> bool:
    try:
        hostname, path, query = _normalized_url_identity(value)
    except ValueError:
        return True
    dedicated_root = (
        hostname.endswith(".panomax.com")
        and hostname not in {"panomax.com", "www.panomax.com"}
    ) or hostname in {"cervignanometeo.org", "www.cervignanometeo.org"}
    if dedicated_root or (path or "") not in GENERIC_SOURCE_PATHS:
        return False
    return not CAMERA_TEXT_PATTERN.search(unquote(query).lower())


def _url_path_contains_id(value: str, expected_id: str) -> bool:
    try:
        segments = {
            unquote(segment).strip()
            for segment in urlsplit(value).path.split("/")
            if segment.strip()
        }
    except ValueError:
        return False
    return expected_id in segments


def _source_page_is_verified_by_api(
    *,
    source_page: str,
    source_check_url: str,
    expected_id: str | None,
    page_result: dict[str, Any],
    api_result: dict[str, Any],
) -> bool:
    """Allow an otherwise generic SPA shell only behind a matching, healthy API."""

    if (
        expected_id is None
        or page_result.get("status") != "source_signal_missing"
        or not api_result.get("ok")
    ):
        return False
    final_url = page_result.get("final_url")
    if not isinstance(final_url, str):
        return False
    try:
        source_host = (urlsplit(source_page).hostname or "").lower()
        check_host = (urlsplit(source_check_url).hostname or "").lower()
        final_host = (urlsplit(final_url).hostname or "").lower()
    except ValueError:
        return False
    return bool(
        source_host
        and source_host == check_host == final_host
        and _url_path_contains_id(source_page, expected_id)
        and _url_path_contains_id(final_url, expected_id)
        and _url_path_contains_id(source_check_url, expected_id)
    )


def _has_source_camera_signal(sample: bytes) -> bool:
    decoded = sample.decode("utf-8", errors="ignore")
    searchable = "".join(
        char
        for char in unicodedata.normalize("NFKD", decoded).lower()
        if not unicodedata.combining(char)
    )
    return bool(
        CAMERA_TEXT_PATTERN.search(searchable)
        or PLAYER_TEXT_PATTERN.search(searchable)
        or CAMERA_EMBED_PATTERN.search(decoded)
    )


def _is_image_sample(sample: bytes) -> bool:
    return (
        sample.startswith(b"\xff\xd8\xff")
        or sample.startswith(b"\x89PNG\r\n\x1a\n")
        or sample.startswith((b"GIF87a", b"GIF89a"))
        or sample.startswith(b"BM")
        or (len(sample) >= 12 and sample.startswith(b"RIFF") and sample[8:12] == b"WEBP")
        or (len(sample) >= 12 and sample[4:8] == b"ftyp")
    )


def _read_response_sample(response: Any, maximum: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(chunk_size=min(8192, maximum)):
        if not chunk:
            continue
        remaining = maximum - size
        chunks.append(bytes(chunk[:remaining]))
        size += min(len(chunk), remaining)
        if size >= maximum:
            break
    return b"".join(chunks)


def _normalized_source_api_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return None


def _source_api_payload_status(sample: bytes, *, expected_id: str | None) -> str:
    try:
        payload = json.loads(sample.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "source_api_invalid_json"
    if not isinstance(payload, dict):
        return "source_api_invalid_payload"
    if payload.get("result") != "OK":
        return "source_api_result_not_ok"
    webcam = payload.get("webcam")
    if not isinstance(webcam, dict):
        return "source_api_invalid_webcam"
    webcam_id = _normalized_source_api_id(webcam.get("id"))
    if webcam_id is None:
        return "source_api_invalid_webcam"
    webcam_name = webcam.get("name")
    if not isinstance(webcam_name, str) or not webcam_name.strip():
        return "source_api_invalid_webcam"
    if expected_id is None:
        return "source_api_expected_identity_missing"
    if webcam_id != expected_id:
        return "source_api_identity_mismatch"
    return "ok"


def _remote_check(
    url: str,
    *,
    expected: Literal["image", "source_api", "source_page"],
    session: requests.Session,
    timeout_seconds: float,
    sample_bytes: int,
    expected_source_api_id: str | None = None,
) -> dict[str, Any]:
    accept = "image/avif,image/webp,image/*,*/*;q=0.8"
    if expected == "source_api":
        accept = "application/json"
    elif expected == "source_page":
        accept = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.2"
    headers = {"Accept": accept, "User-Agent": HEALTH_USER_AGENT}
    if expected == "image":
        headers["Range"] = f"bytes=0-{sample_bytes - 1}"

    response = None
    try:
        response = session.get(
            url,
            headers=headers,
            timeout=timeout_seconds,
            allow_redirects=True,
            stream=True,
        )
        status_code = int(response.status_code)
        final_url = str(response.url or url)
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if not 200 <= status_code < 300:
            return {
                "ok": False,
                "status": "http_error",
                "http_status": status_code,
                "content_type": content_type,
                "final_url": final_url,
                "sample_bytes": 0,
            }
        if not _is_https_url(final_url):
            return {
                "ok": False,
                "status": "https_downgrade",
                "http_status": status_code,
                "content_type": content_type,
                "final_url": final_url,
                "sample_bytes": 0,
            }
        if (
            expected == "source_page"
            and _normalized_url_identity(final_url) != _normalized_url_identity(url)
            and _is_generic_source_url(final_url)
        ):
            return {
                "ok": False,
                "status": "source_redirected_to_generic",
                "http_status": status_code,
                "content_type": content_type,
                "final_url": final_url,
                "sample_bytes": 0,
            }

        sample = _read_response_sample(response, sample_bytes)
        if expected == "image":
            valid_content = content_type.startswith("image/") and _is_image_sample(sample)
            failure = "not_an_image"
        elif expected == "source_api":
            if content_type != "application/json":
                valid_content = False
                failure = "source_api_invalid_content_type"
            else:
                payload_status = _source_api_payload_status(
                    sample,
                    expected_id=expected_source_api_id,
                )
                valid_content = payload_status == "ok"
                failure = payload_status
        else:
            lowered = sample[:4096].lower()
            valid_image = content_type.startswith("image/") and _is_image_sample(sample)
            valid_html = (
                content_type in {"text/html", "application/xhtml+xml"}
                and bool(sample)
                and (b"<html" in lowered or b"<!doctype html" in lowered)
            )
            valid_content = valid_image or (
                valid_html and _has_source_camera_signal(sample)
            )
            if valid_image:
                failure = "ok"
            elif valid_html:
                failure = "source_signal_missing"
            else:
                failure = "not_source_resource"
        return {
            "ok": valid_content,
            "status": "ok" if valid_content else failure,
            "http_status": status_code,
            "content_type": content_type,
            "final_url": final_url,
            "sample_bytes": len(sample),
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": "request_error",
            "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            "sample_bytes": 0,
        }
    finally:
        if response is not None:
            response.close()


def _local_asset_check(
    web_path: str,
    *,
    asset_root: Path,
    sample_bytes: int,
) -> dict[str, Any]:
    root = asset_root.resolve()
    parsed = urlsplit(web_path)
    candidate = (root / parsed.path.lstrip("/")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return {
            "ok": False,
            "status": "local_asset_outside_root",
            "path": web_path,
            "sample_bytes": 0,
        }

    try:
        with candidate.open("rb") as source:
            sample = source.read(sample_bytes)
    except OSError as exc:
        return {
            "ok": False,
            "status": "local_asset_unreadable",
            "path": web_path,
            "error": f"{type(exc).__name__}: {str(exc)[:160]}",
            "sample_bytes": 0,
        }
    valid_content = _is_image_sample(sample)
    return {
        "ok": valid_content,
        "status": "ok" if valid_content else "not_an_image",
        "path": web_path,
        "sample_bytes": len(sample),
    }


def check_webcam_health(
    records: Iterable[WebcamRecord],
    *,
    mode: str,
    asset_root: Path,
    session: requests.Session | None = None,
    timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
    sample_bytes: int = DEFAULT_SAMPLE_BYTES,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    """Check reachability and file signatures, not stream freshness or embed rights."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds_must_be_positive")
    if sample_bytes < 12:
        raise ValueError("sample_bytes_too_small")

    http = session or requests.Session()
    results: list[dict[str, Any]] = []
    for record in records:
        checks: list[dict[str, Any]] = []
        feed_result = None
        fallback_result = None
        source_results: list[dict[str, Any]] = []

        if record.imageUrl:
            feed_result = _remote_check(
                record.imageUrl,
                expected="image",
                session=http,
                timeout_seconds=timeout_seconds,
                sample_bytes=sample_bytes,
            )
            checks.append({"target": "imageUrl", "url": record.imageUrl, **feed_result})

        if record.fallbackImageUrl:
            if record.fallbackImageUrl.startswith("/"):
                fallback_result = _local_asset_check(
                    record.fallbackImageUrl,
                    asset_root=asset_root,
                    sample_bytes=sample_bytes,
                )
            else:
                fallback_result = _remote_check(
                    record.fallbackImageUrl,
                    expected="image",
                    session=http,
                    timeout_seconds=timeout_seconds,
                    sample_bytes=sample_bytes,
                )
            checks.append(
                {
                    "target": "fallbackImageUrl",
                    "url": record.fallbackImageUrl,
                    **fallback_result,
                }
            )

        source_page_result = _remote_check(
            record.sourcePage,
            expected="source_page",
            session=http,
            timeout_seconds=timeout_seconds,
            sample_bytes=min(sample_bytes, 16 * 1024),
        )
        source_api_result = None
        if record.sourceCheckUrl:
            source_api_result = _remote_check(
                record.sourceCheckUrl,
                expected="source_api",
                session=http,
                timeout_seconds=timeout_seconds,
                sample_bytes=min(sample_bytes, 16 * 1024),
                expected_source_api_id=record.sourceCheckExpectedId,
            )
            source_results.append(source_api_result)

            if _source_page_is_verified_by_api(
                source_page=record.sourcePage,
                source_check_url=record.sourceCheckUrl,
                expected_id=record.sourceCheckExpectedId,
                page_result=source_page_result,
                api_result=source_api_result,
            ):
                source_page_result = {
                    **source_page_result,
                    "ok": True,
                    "status": "ok",
                    "verification": "source_api_identity",
                }

        source_results.insert(0, source_page_result)
        checks.append(
            {
                "target": "sourcePage",
                "url": record.sourcePage,
                **source_page_result,
            }
        )
        if record.sourceCheckUrl and source_api_result is not None:
            checks.append(
                {
                    "target": "sourceCheckUrl",
                    "url": record.sourceCheckUrl,
                    **source_api_result,
                }
            )

        media_ok = bool(
            (feed_result and feed_result["ok"])
            or (fallback_result and fallback_result["ok"])
        )
        fallback_rescues_feed = bool(
            feed_result
            and not feed_result["ok"]
            and fallback_result
            and fallback_result["ok"]
        )
        if not media_ok:
            status = "failed"
        elif fallback_rescues_feed or any(not result["ok"] for result in source_results):
            status = "degraded"
        else:
            status = "ok"

        results.append(
            {
                "id": record.id,
                "name": record.name,
                "status": status,
                "external_only": record.imageUrl is None,
                "stream_freshness": "not_verified",
                "checks": checks,
            }
        )

    counts = {
        state: sum(1 for item in results if item["status"] == state)
        for state in ("ok", "degraded", "failed")
    }
    if counts["failed"]:
        status = "failed"
    elif counts["degraded"]:
        status = "degraded"
    else:
        status = "ok"
    return {
        "schema_version": "webcam-health.v1",
        "mode": mode,
        "publish": False,
        "verification_scope": "configured_assets_and_source_reachability",
        "not_verified": ["stream_freshness", "viewpoint_identity", "embedding_permission"],
        "generated_at": now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "counts": {"total": len(results), **counts},
        "results": results,
    }
