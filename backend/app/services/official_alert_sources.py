"""Reconcile official FVG alerts from Telegram and the ARPA/OSMER PCR mirror.

Telegram is a positive-only fast signal.  The ARPA PCR panel can confirm the
same state and can clear it, but its public page may be cached for one hour.
Consequently an ARPA inactive observation never clears a newer Telegram alert
on first sight: clearance requires an observed active->inactive transition or
two inactive observations separated by the advertised cache window.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

import requests

from app.weather import alerts_engine
from app.weather.arpa_osmer_risks import (
    ArpaOsmerRisksSource,
    ArpaOsmerRisksUnavailable,
)
from app.weather.official_telegram_alerts import (
    OfficialTelegramParserError,
    fetch_official_telegram_channel,
)


TELEGRAM_VERIFIED_SOURCE_MODE = "official_telegram_pdf_verified"
WIDGET_ARPA_CORROBORATED_SOURCE_MODE = "official_fvg_widget_arpa_corroborated"
OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE = "official_page_arpa_corroborated"
TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE = "official_telegram_arpa_corroborated"
ARPA_PCR_SOURCE_MODE = "arpa_pcr_mirror"
OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE = "official_validity_expired"
ARPA_INACTIVE_MINIMUM_CONFIRMATION_SECONDS = 65 * 60
SOURCE_CLOCK_SKEW_SECONDS = 5 * 60
MAX_VERIFIED_PDF_BYTES = 12 * 1024 * 1024
CLEARANCE_RETENTION = timedelta(days=8)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CFD_ALERT_DOCUMENT_RE = re.compile(
    r"^/docs/alerts/(?P<year>\d{4})/"
    r"Allerta_regionale_(?P<number>\d+)-(?P=year)(?:_[^/]*)?\.pdf$",
    re.IGNORECASE,
)
_PCR_ALERT_DOCUMENT_RE = re.compile(
    r"^/alerts/(?P<number>\d+)_(?P<year>\d{4})\.pdf$",
    re.IGNORECASE,
)
_OFFICIAL_PAGE_ALERT_DOCUMENT_RE = re.compile(
    r"^/sites/default/files/allerta/allerta_regionale_"
    r"(?P<number>\d+)_del_(?P<year>\d{4})\.pdf$",
    re.IGNORECASE,
)
_WIDGET_ALERT_TITLE_RE = re.compile(
    r"^ALLERTA\s+REGIONALE\s+(?P<number>\d+)\s+DEL\s+(?P<year>\d{4})$",
    re.IGNORECASE,
)
_LEVEL_VALUE = {"verde": 0, "gialla": 1, "arancione": 2, "rossa": 3, "nera": 4}
_ITALIAN_WEEKDAYS = (
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _request_failure(source: str, error: BaseException) -> dict[str, Any]:
    attempt: dict[str, Any] = {"source": source, "category": "connection"}
    if isinstance(error, requests.Timeout):
        attempt["category"] = "timeout"
        if isinstance(error, requests.ConnectTimeout):
            attempt["phase"] = "connect"
        elif isinstance(error, requests.ReadTimeout):
            attempt["phase"] = "read"
    elif isinstance(error, requests.HTTPError):
        attempt["category"] = "http"
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and 100 <= status_code <= 599:
            attempt["status_code"] = status_code
    elif isinstance(
        error,
        (OfficialTelegramParserError, alerts_engine.OfficialAlertsParserError),
    ):
        attempt["category"] = "parser"
    elif isinstance(error, ArpaOsmerRisksUnavailable):
        code = str(getattr(error, "code", ""))
        if code == "source_timeout":
            attempt["category"] = "timeout"
        elif "unrecognized" in code:
            attempt["category"] = "parser"
    return attempt


def _fetch_telegram_metadata() -> dict[str, Any]:
    return fetch_official_telegram_channel(verify_active_pdfs=False)


def _structured_official_page_alerts(html: str) -> list[dict[str, Any]]:
    parsed = alerts_engine.parse_civil_protection_alerts(html)
    if not parsed:
        if alerts_engine.html_confirms_no_active_alerts(html):
            return []
        raise alerts_engine.OfficialAlertsParserError("unclassified_html_response")

    normalized: list[dict[str, Any]] = []
    for alert in parsed:
        if _official_metadata_alert_identity(alert) is None:
            raise alerts_engine.OfficialAlertsParserError("invalid_html_alert_identity")
        level = str(alert.get("level") or "").strip().lower()
        if level not in _LEVEL_VALUE:
            raise alerts_engine.OfficialAlertsParserError("invalid_html_alert_level")
        official_text = str(alert.get("official_text") or "").strip()
        start = _parse_datetime(alert.get("valid_from"))
        end = _parse_datetime(alert.get("valid_to"))
        if not official_text or start is None or end is None or end <= start:
            raise alerts_engine.OfficialAlertsParserError("invalid_html_alert_window")
        zones = sorted(set(re.findall(r"\bFVG-[ABCD]\b", official_text.upper())))
        if not zones and re.search(r"\bTUTTA\s+LA\s+REGIONE\b", official_text.upper()):
            zones = ["FVG-A", "FVG-B", "FVG-C", "FVG-D"]
        if not zones:
            raise alerts_engine.OfficialAlertsParserError("invalid_html_alert_zones")
        area = (
            "Tutta la regione"
            if len(zones) == 4
            else ", ".join(f"zona {zone}" for zone in zones)
        )
        window = _time_window(str(alert["valid_from"]), str(alert["valid_to"]))
        risks = alert.get("risks") or []
        normalized.append(
            {
                **alert,
                "zones": zones,
                "area": area,
                "time_window": window,
                "source_mode": "official_page",
                "push_body": alerts_engine.build_official_alert_push_body(
                    level, risks, window, area
                ),
                "push_body_i18n": {
                    language: alerts_engine.build_official_alert_push_body(
                        level, risks, window, area, language
                    )
                    for language in ("it", "fur")
                },
            }
        )
    return normalized


def fetch_official_alert_observations(
    *,
    force: bool = False,
    telegram_fetcher: Callable[[], dict[str, Any]] = _fetch_telegram_metadata,
    widget_fetcher: Callable[[], str] = (
        alerts_engine.fetch_civil_protection_widget_alerts_jsonp
    ),
    html_fetcher: Callable[[], str] | None = (
        alerts_engine.fetch_civil_protection_alerts_html
    ),
    arpa_source: ArpaOsmerRisksSource | Any | None = None,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    """Fetch both sources without treating either failure as no-alert."""

    del force
    observed_at = now()
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observations: dict[str, Any] = {
        "fetched_at": _iso(observed_at),
        "widget": None,
        "html": None,
        "telegram": None,
        "arpa_pcr": None,
        "failures": [],
    }

    try:
        widget_alerts = alerts_engine.parse_civil_protection_widget_alerts(
            widget_fetcher()
        )
        observations["widget"] = {
            "source_mode": "official_widget",
            "alerts": widget_alerts,
            "can_confirm_inactive": not any(
                alerts_engine.is_actionable_official_alert(alert)
                for alert in widget_alerts
            ),
        }
    except alerts_engine.OfficialAlertsParserError as error:
        observations["failures"].append(_request_failure("widget", error))
    except requests.RequestException as error:
        observations["failures"].append(_request_failure("widget", error))

    if observations["widget"] is None and html_fetcher is not None:
        try:
            html_alerts = _structured_official_page_alerts(html_fetcher())
            observations["html"] = {
                "source_mode": "official_page",
                "alerts": html_alerts,
                "can_confirm_inactive": not any(
                    alerts_engine.is_actionable_official_alert(alert)
                    for alert in html_alerts
                ),
            }
        except alerts_engine.OfficialAlertsParserError as error:
            observations["failures"].append(_request_failure("html", error))
        except requests.RequestException as error:
            observations["failures"].append(_request_failure("html", error))

    try:
        observations["telegram"] = telegram_fetcher()
    except (OfficialTelegramParserError, requests.RequestException) as error:
        observations["failures"].append(_request_failure("telegram", error))

    source = arpa_source or ArpaOsmerRisksSource(now=lambda: observed_at)
    try:
        observations["arpa_pcr"] = source.fetch_pcr()
    except (ArpaOsmerRisksUnavailable, requests.RequestException) as error:
        observations["failures"].append(_request_failure("arpa_pcr", error))

    return observations


def _time_window(valid_from: str, valid_to: str) -> str:
    start = _parse_datetime(valid_from)
    end = _parse_datetime(valid_to)
    if start is None or end is None:
        return ""
    local_timezone = alerts_engine.get_fvg_timezone()
    start = start.astimezone(local_timezone)
    end = end.astimezone(local_timezone)
    return f"{start:%H:%M} {start:%d/%m}-{end:%H:%M} {end:%d/%m}"


def _telegram_alert_to_runtime(alert: dict[str, Any]) -> dict[str, Any]:
    level = str(alert.get("level") or "").strip().lower()
    risks = [str(item) for item in alert.get("risks") or [] if str(item)]
    zones = [str(item) for item in alert.get("zones") or [] if str(item)]
    area = (
        ""
        if alert.get("mixed_levels") is True
        else str(alert.get("area") or "").strip()
    )
    valid_from = str(alert.get("valid_from") or "").strip()
    valid_to = str(alert.get("valid_to") or "").strip()
    window = _time_window(valid_from, valid_to)
    alert_number = alert.get("alert_number")
    alert_year = alert.get("alert_year")
    title = (
        f"Allerta regionale n. {alert_number}/{alert_year}"
        if alert_number and alert_year
        else "Allerta regionale"
    )
    body_it = alerts_engine.build_official_alert_push_body(
        level, risks, window, area, "it"
    )
    body_fur = alerts_engine.build_official_alert_push_body(
        level, risks, window, area, "fur"
    )
    return {
        "id": str(alert.get("id") or "").strip(),
        "event_id": str(alert.get("id") or "").strip(),
        "alert_number": alert_number,
        "alert_year": alert_year,
        "title": title,
        "level": level,
        "levels": [str(item) for item in alert.get("levels") or [] if str(item)],
        "mixed_levels": alert.get("mixed_levels") is True,
        "risks": risks,
        "zones": zones,
        "area": area,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "time_window": window,
        "official_text": str(alert.get("official_text") or "").strip(),
        "pdf_url": str(alert.get("pdf_url") or "").strip(),
        "pdf_sha256": str(alert.get("pdf_sha256") or "").strip().lower(),
        "pdf_size_bytes": alert.get("pdf_size_bytes"),
        "pdf_verified_at": str(alert.get("pdf_verified_at") or "").strip(),
        "revision_hash": str(alert.get("revision_hash") or "").strip().lower(),
        "published_at": str(alert.get("published_at") or "").strip(),
        "telegram_post_id": alert.get("telegram_post_id"),
        "telegram_post_url": str(alert.get("telegram_post_url") or "").strip(),
        "source": alerts_engine.PROTEZIONE_CIVILE_ALERTS_SOURCE,
        "source_mode": TELEGRAM_VERIFIED_SOURCE_MODE,
        "push_title": "Meteo Friûl",
        "push_body": body_it,
        "push_title_i18n": {"it": "Meteo Friûl", "fur": "Meteo Friûl"},
        "push_body_i18n": {"it": body_it, "fur": body_fur},
    }


def _alert_revision_key(alert: dict[str, Any]) -> str:
    pdf_sha256 = str(alert.get("pdf_sha256") or "").strip().lower()
    canonical: dict[str, Any] = {
        "id": str(alert.get("id") or alert.get("event_id") or "").strip(),
    }
    if pdf_sha256:
        # The verified document bytes are the authoritative revision.  Telegram
        # copy edits must not resurrect an alert that ARPA already cleared.
        canonical["pdf_sha256"] = pdf_sha256
    else:
        canonical.update(
            {
                "pdf_url": str(alert.get("pdf_url") or "").strip(),
                "revision_hash": str(alert.get("revision_hash") or "")
                .strip()
                .lower(),
                "valid_from": str(alert.get("valid_from") or "").strip(),
                "valid_to": str(alert.get("valid_to") or "").strip(),
            }
        )
    return hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _event_signature(alerts: list[dict[str, Any]]) -> str:
    canonical = sorted(_alert_revision_key(alert) for alert in alerts)
    return hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _active_clearances(
    verification: dict[str, Any], *, now: datetime
) -> list[dict[str, Any]]:
    clearances = []
    for item in verification.get("cleared_alerts") or []:
        if not isinstance(item, dict):
            continue
        revision_key = str(item.get("revision_key") or "").strip().lower()
        retain_until = _parse_datetime(item.get("retain_until"))
        valid_to = _parse_datetime(item.get("valid_to"))
        expiry = retain_until or valid_to
        if not revision_key or (expiry is not None and expiry <= now):
            continue
        clearances.append(deepcopy(item))
    return clearances


def _filter_cleared_alerts(
    alerts: list[dict[str, Any]],
    *,
    previous: dict[str, Any] | None,
    pcr: dict[str, Any] | None,
    now: datetime,
) -> list[dict[str, Any]]:
    clearances = _active_clearances(_verification(previous), now=now)
    if not clearances:
        return alerts
    return [
        alert
        for alert in alerts
        if not _clearances_block_alert(
            alert,
            clearances=clearances,
            pcr=pcr,
            now=now,
        )
    ]


def _clearances_block_alert(
    alert: dict[str, Any],
    *,
    clearances: list[dict[str, Any]],
    pcr: dict[str, Any] | None,
    now: datetime,
) -> bool:
    revision_key = _alert_revision_key(alert)
    identity = _alert_identity(alert)
    published_at = _parse_datetime(alert.get("published_at"))
    for clearance in clearances:
        if revision_key == str(clearance.get("revision_key") or "").strip().lower():
            if _arpa_relists_clearance(
                alert=alert,
                clearance=clearance,
                pcr=pcr,
                now=now,
            ):
                # This exact ARPA clearance may be reversed, but a newer
                # clearance for the same event still has to be evaluated.
                continue
            return True
        if clearance.get("exact_revision_only") is True:
            # Legacy structured hashes did not bind publication ordering.  A
            # retirement derived from one may suppress only the exact covered
            # revision, never a different revision with the same event id.
            continue
        cleared_identity = str(clearance.get("event_id") or "").strip()
        if not identity or not cleared_identity or identity != cleared_identity:
            continue
        revision_floor_at = _parse_datetime(
            clearance.get("revision_floor_at") or clearance.get("cleared_at")
        )
        try:
            candidate_post_id = int(alert.get("telegram_post_id") or 0)
            floor_post_id = int(clearance.get("telegram_post_id") or 0)
        except (TypeError, ValueError):
            candidate_post_id = 0
            floor_post_id = 0
        if revision_floor_at is not None and (
            published_at is None
            or published_at < revision_floor_at
            or (
                published_at == revision_floor_at
                and candidate_post_id <= floor_post_id
            )
        ):
            if (
                _alert_observation_order(alert)
                > _alert_observation_order(clearance)
                and _arpa_relists_clearance(
                    alert=alert,
                    clearance=clearance,
                    pcr=pcr,
                    now=now,
                )
            ):
                # Telegram may expose a verified revision only after ARPA removed
                # the previous one.  A complete, newer PCR panel that lists this
                # exact PDF can override the poll-time floor only when the post
                # order is also strictly newer than the cleared revision.
                continue
            # A different PDF for the same event is not automatically newer.
            # Require a strictly newer official post after the clearance so a
            # Telegram/cache rollback cannot resurrect an older revision.
            return True
    return False


def _arpa_relists_clearance(
    *,
    alert: dict[str, Any],
    clearance: dict[str, Any],
    pcr: dict[str, Any] | None,
    now: datetime,
) -> bool:
    if not str(clearance.get("reason") or "").startswith("arpa_pcr_"):
        return False
    if not _pcr_document_membership_complete(pcr):
        return False
    if not _document_urls_contain_alert(alert, _pcr_document_urls(pcr)):
        return False
    source_at = _pcr_source_content_at(pcr)
    floor = _parse_datetime(
        clearance.get("revision_floor_at") or clearance.get("cleared_at")
    )
    return bool(
        source_at is not None
        and floor is not None
        and source_at <= now
        and source_at > floor
    )


def _alert_identity(alert: dict[str, Any]) -> str:
    identity = str(alert.get("id") or alert.get("event_id") or "").strip()
    if identity:
        return identity
    return ":".join(
        (
            str(alert.get("alert_year") or "").strip(),
            str(alert.get("alert_number") or "").strip(),
        )
    )


def _merge_positive_alerts(
    previous_alerts: list[dict[str, Any]],
    observed_alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = {
        _alert_identity(alert): deepcopy(alert)
        for alert in previous_alerts
        if _alert_identity(alert)
    }
    for alert in observed_alerts:
        identity = _alert_identity(alert)
        if identity:
            existing = merged.get(identity)
            observed_order = _alert_observation_order(alert)
            existing_order = _alert_observation_order(existing or {})
            if existing is None or observed_order > existing_order or (
                observed_order == existing_order
                and _alert_revision_key(alert) == _alert_revision_key(existing)
            ):
                merged[identity] = deepcopy(alert)
    return sorted(
        merged.values(),
        key=lambda alert: (str(alert.get("valid_from") or ""), _alert_identity(alert)),
    )


def _alert_observation_order(alert: dict[str, Any]) -> tuple[datetime, int]:
    published_at = _parse_datetime(alert.get("published_at")) or datetime.min.replace(
        tzinfo=timezone.utc
    )
    try:
        post_id = int(alert.get("telegram_post_id") or 0)
    except (TypeError, ValueError):
        post_id = 0
    return published_at, post_id


def _has_newer_observed_revision(
    alert: dict[str, Any], observed_alerts: list[dict[str, Any]]
) -> bool:
    identity = _alert_identity(alert)
    revision_key = _alert_revision_key(alert)
    order = _alert_observation_order(alert)
    return any(
        _alert_identity(candidate) == identity
        and _alert_revision_key(candidate) != revision_key
        and _alert_observation_order(candidate) > order
        for candidate in observed_alerts
    )


def _latest_published_at(alerts: list[dict[str, Any]]) -> str:
    parsed = [
        (_parse_datetime(alert.get("published_at")), str(alert.get("published_at") or ""))
        for alert in alerts
    ]
    valid = [item for item in parsed if item[0] is not None]
    if not valid:
        return ""
    return max(valid, key=lambda item: item[0])[1]


def _verification(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    cache = payload.get("cache")
    if not isinstance(cache, dict):
        return {}
    value = cache.get("verification")
    return deepcopy(value) if isinstance(value, dict) else {}


def _pcr_observation(
    observations: dict[str, Any], *, observed_at: datetime
) -> dict[str, Any] | None:
    raw = observations.get("arpa_pcr")
    if not isinstance(raw, dict) or raw.get("status") != "available":
        return None
    pcr = raw.get("pcr")
    if not isinstance(pcr, dict) or pcr.get("status") not in {"active", "inactive"}:
        return None
    response_at = _pcr_response_at(raw)
    source_content_at = _pcr_source_content_at(raw)
    if (
        response_at is None
        or source_content_at is None
        or response_at > observed_at + timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS)
        or source_content_at
        > observed_at + timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS)
    ):
        return None
    freshness_window = max(
        ARPA_INACTIVE_MINIMUM_CONFIRMATION_SECONDS,
        _cache_max_age_seconds(raw) + SOURCE_CLOCK_SKEW_SECONDS,
    )
    if (observed_at - response_at).total_seconds() > freshness_window:
        return None
    return raw


def _active_telegram_alerts(
    observations: dict[str, Any], *, now: datetime
) -> list[dict[str, Any]]:
    raw = observations.get("telegram")
    if not isinstance(raw, dict):
        return []
    result = []
    for candidate in raw.get("alerts") or []:
        if not isinstance(candidate, dict):
            continue
        valid_to = _parse_datetime(candidate.get("valid_to"))
        published_at = _parse_datetime(candidate.get("published_at"))
        if valid_to is None or valid_to <= now:
            continue
        if published_at is None or published_at > now + timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS):
            continue
        if not _has_verified_pdf(candidate, now=now, published_at=published_at):
            continue
        converted = _telegram_alert_to_runtime(candidate)
        if alerts_engine.is_actionable_official_alert(converted):
            result.append(converted)
    return sorted(result, key=lambda alert: (str(alert.get("valid_from")), str(alert.get("id"))))


def _official_metadata_alert_identity(
    alert: dict[str, Any],
) -> tuple[int, int] | None:
    try:
        identity = (int(alert.get("alert_year")), int(alert.get("alert_number")))
    except (TypeError, ValueError):
        title = " ".join(str(alert.get("title") or "").strip().split())
        match = _WIDGET_ALERT_TITLE_RE.fullmatch(title)
        if match is None:
            return None
        identity = (int(match.group("year")), int(match.group("number")))
    document_identity = _document_url_identity(
        str(alert.get("pdf_url") or "").strip()
    )
    return identity if document_identity == identity else None


def _pcr_panel_level_map(panel: dict[str, Any]) -> dict[str, int] | None:
    values: dict[str, int] = {}
    for item in panel.get("zone_levels") or []:
        if not isinstance(item, dict):
            return None
        zone = str(item.get("zone") or "").strip().upper()
        level = item.get("level")
        if zone in values or zone not in {"FVG-A", "FVG-B", "FVG-C", "FVG-D"}:
            return None
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 4:
            return None
        values[zone] = level
    return values if set(values) == {"FVG-A", "FVG-B", "FVG-C", "FVG-D"} else None


def _pcr_panel_identities(panel: dict[str, Any]) -> set[tuple[int, int]] | None:
    urls = [str(url or "").strip() for url in panel.get("document_urls") or []]
    if not urls or any(not url for url in urls):
        return None
    identities: set[tuple[int, int]] = set()
    for url in urls:
        identity = _document_url_identity(url)
        if identity is None:
            return None
        identities.add(identity)
    return identities


def _pcr_panel_matches_alert_window(
    panel: dict[str, Any], alert: dict[str, Any]
) -> bool:
    start = _parse_datetime(alert.get("valid_from"))
    end = _parse_datetime(alert.get("valid_to"))
    if start is None or end is None or end <= start:
        return False
    local_timezone = alerts_engine.get_fvg_timezone()
    start = start.astimezone(local_timezone)
    end = end.astimezone(local_timezone)
    if (
        str(panel.get("start_weekday") or "").strip().lower()
        != _ITALIAN_WEEKDAYS[start.weekday()]
        or str(panel.get("start_time") or "").strip() != start.strftime("%H:%M")
    ):
        return False
    end_time = str(panel.get("end_time") or "").strip()
    if end.strftime("%H:%M") == "00:00" and end_time in {"23:59", "24:00"}:
        reference = end - timedelta(minutes=1)
        return bool(
            str(panel.get("end_weekday") or "").strip().lower()
            == _ITALIAN_WEEKDAYS[reference.weekday()]
        )
    return bool(
        str(panel.get("end_weekday") or "").strip().lower()
        == _ITALIAN_WEEKDAYS[end.weekday()]
        and end_time == end.strftime("%H:%M")
    )


def _pcr_panel_corroborates_metadata_alert(
    panel: dict[str, Any], alert: dict[str, Any]
) -> bool:
    identity = _official_metadata_alert_identity(alert)
    if identity is None:
        return False
    candidate = {
        **alert,
        "alert_year": identity[0],
        "alert_number": identity[1],
    }
    documents = {
        str(url or "").strip()
        for url in panel.get("document_urls") or []
        if str(url or "").strip()
    }
    if not documents or not _document_urls_contain_alert(candidate, documents):
        return False
    levels = _pcr_panel_level_map(panel)
    expected_level = _LEVEL_VALUE.get(str(alert.get("level") or "").strip().lower())
    expected_zones = {
        str(zone or "").strip().upper()
        for zone in alert.get("zones") or []
        if str(zone or "").strip()
    }
    if levels is None or expected_level is None or expected_level <= 0:
        return False
    if expected_zones != {zone for zone, level in levels.items() if level > 0}:
        return False
    if any(level != expected_level for zone, level in levels.items() if zone in expected_zones):
        return False
    return _pcr_panel_matches_alert_window(panel, alert)


def _pcr_panel_document_url(
    panel: dict[str, Any], identity: tuple[int, int]
) -> str | None:
    urls = sorted(
        {
            str(url or "").strip()
            for url in panel.get("document_urls") or []
            if str(url or "").strip()
            and _document_url_identity(str(url or "").strip()) == identity
        }
    )
    return urls[0] if len(urls) == 1 else None


STRUCTURED_CORROBORATION_REVISION_SCHEMA = "runtime-v2"


def _legacy_structured_corroboration_revision_hash(
    alert: dict[str, Any],
    *,
    identity: tuple[int, int],
    pcr_revision: str,
) -> str:
    year, number = identity
    return hashlib.sha256(
        json.dumps(
            {
                "identity": [year, number],
                "level": alert.get("level"),
                "zones": sorted(alert.get("zones") or []),
                "valid_from": alert.get("valid_from"),
                "valid_to": alert.get("valid_to"),
                "pdf_url": alert.get("pdf_url"),
                "official_text": alert.get("official_text"),
                "pcr_revision": pcr_revision,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _structured_corroboration_revision_hash(
    alert: dict[str, Any],
    *,
    identity: tuple[int, int],
    pcr_revision: str,
) -> str:
    """Bind a structured two-source decision to its complete runtime meaning.

    The previous revision hash predated its use as a durable provenance proof
    and covered only the alert window and a small subset of the display data.
    This schema also binds ordering/clearance inputs and every runtime field
    consumed by the public response or push preparation.
    """

    year, number = identity
    corroboration = alert.get("corroboration")
    if not isinstance(corroboration, dict):
        raise ValueError("invalid structured corroboration")

    def normalized_strings(value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError("invalid structured alert string list")
        return sorted(item.strip() for item in value if item.strip())

    return hashlib.sha256(
        json.dumps(
            {
                "schema": STRUCTURED_CORROBORATION_REVISION_SCHEMA,
                "identity": [year, number],
                "id": alert.get("id"),
                "event_id": alert.get("event_id"),
                "alert_number": alert.get("alert_number"),
                "alert_year": alert.get("alert_year"),
                "title": alert.get("title"),
                "level": alert.get("level"),
                "levels": normalized_strings(alert.get("levels")),
                "mixed_levels": alert.get("mixed_levels"),
                "risks": normalized_strings(alert.get("risks")),
                "zones": normalized_strings(alert.get("zones")),
                "area": alert.get("area"),
                "valid_from": alert.get("valid_from"),
                "valid_to": alert.get("valid_to"),
                "time_window": alert.get("time_window"),
                "official_text": alert.get("official_text"),
                "pdf_url": alert.get("pdf_url"),
                "metadata_document_url": alert.get("metadata_document_url"),
                "published_at": alert.get("published_at"),
                "telegram_post_id": alert.get("telegram_post_id"),
                "telegram_post_url": alert.get("telegram_post_url"),
                "source": alert.get("source"),
                "source_mode": alert.get("source_mode"),
                "corroborated_at": alert.get("corroborated_at"),
                "corroboration": {
                    "method": corroboration.get("method"),
                    "identity": corroboration.get("identity"),
                    "pcr_revision": pcr_revision,
                    "revision_hash_schema": corroboration.get(
                        "revision_hash_schema"
                    ),
                },
                "push_title": alert.get("push_title"),
                "push_body": alert.get("push_body"),
                "push_title_i18n": alert.get("push_title_i18n"),
                "push_body_i18n": alert.get("push_body_i18n"),
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _corroborated_alert_to_runtime(
    alert: dict[str, Any],
    *,
    panel: dict[str, Any],
    metadata_source: str,
    observed_at: datetime,
    pcr_revision: str,
) -> dict[str, Any]:
    identity = _official_metadata_alert_identity(alert)
    if identity is None:
        raise ValueError("uncorroborated official metadata alert")
    year, number = identity
    document_url = _pcr_panel_document_url(panel, identity)
    if document_url is None:
        raise ValueError("uncorroborated official document")
    if metadata_source == "widget":
        runtime = deepcopy(alert)
        source_mode = WIDGET_ARPA_CORROBORATED_SOURCE_MODE
        method = "official_fvg_widget_arpa"
    elif metadata_source == "html":
        runtime = deepcopy(alert)
        source_mode = OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE
        method = "official_fvg_page_arpa"
    elif metadata_source == "telegram":
        runtime = _telegram_alert_to_runtime(alert)
        source_mode = TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE
        method = "official_telegram_arpa"
    else:
        raise ValueError("unknown official metadata source")
    metadata_document_url = str(runtime.get("pdf_url") or "").strip()
    runtime = {
        **runtime,
        "id": f"allerta-regionale-{number}-{year}",
        "event_id": f"allerta-regionale-{number}-{year}",
        "alert_number": number,
        "alert_year": year,
        "pdf_url": document_url,
        "metadata_document_url": metadata_document_url,
        "source": alerts_engine.PROTEZIONE_CIVILE_ALERTS_SOURCE,
        "source_mode": source_mode,
        "corroborated_at": _iso(observed_at),
        "corroboration": {
            "method": method,
            "identity": f"{year}:{number}",
            "pcr_revision": pcr_revision,
            "revision_hash_schema": STRUCTURED_CORROBORATION_REVISION_SCHEMA,
        },
    }
    runtime.pop("pdf_sha256", None)
    runtime.pop("pdf_size_bytes", None)
    runtime.pop("pdf_verified_at", None)
    runtime["revision_hash"] = _structured_corroboration_revision_hash(
        runtime,
        identity=identity,
        pcr_revision=pcr_revision,
    )
    return runtime


def _structured_metadata_pcr_payload(
    observations: dict[str, Any],
    *,
    pcr: dict[str, Any] | None,
    observed_at: datetime,
    failures: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if pcr is None:
        return None
    pcr_state = str((pcr.get("pcr") or {}).get("status") or "")
    widget = observations.get("widget")
    html = observations.get("html")
    html_has_current_alert = isinstance(html, dict) and any(
        isinstance(alert, dict)
        and alerts_engine.is_actionable_official_alert(alert)
        and (
            (valid_to := _parse_datetime(alert.get("valid_to"))) is not None
            and valid_to > observed_at
        )
        for alert in html.get("alerts") or []
    )
    structured = (
        widget
        if isinstance(widget, dict)
        else html if html_has_current_alert else None
    )
    metadata_source = ""
    metadata_alerts: list[dict[str, Any]] = []
    source_mode = ""
    if isinstance(structured, dict):
        metadata_source = "widget" if structured is widget else "html"
        source_mode = (
            WIDGET_ARPA_CORROBORATED_SOURCE_MODE
            if metadata_source == "widget"
            else OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE
        )
        metadata_alerts = [
            alert
            for alert in structured.get("alerts") or []
            if isinstance(alert, dict)
            and alerts_engine.is_actionable_official_alert(alert)
            and (
                (valid_to := _parse_datetime(alert.get("valid_to"))) is not None
                and valid_to > observed_at
            )
        ]
        if (
            not metadata_alerts
            and structured.get("can_confirm_inactive") is True
            and pcr_state == "inactive"
        ):
            return _inactive_payload(
                fetched_at=_iso(observed_at),
                verification={
                    metadata_source: {
                        "status": "inactive", "observed_at": _iso(observed_at)
                    },
                    "arpa_pcr": {"status": "inactive", "observed_at": _iso(observed_at)},
                },
                source_mode=ARPA_PCR_SOURCE_MODE,
                failures=failures,
            )
        if not metadata_alerts:
            return _unavailable_payload(
                observations, reason="official_structured_sources_disagree"
            )
    else:
        telegram = observations.get("telegram")
        if not isinstance(telegram, dict):
            return None
        telegram_candidates = [
            alert
            for alert in telegram.get("alerts") or []
            if isinstance(alert, dict)
        ]
        if any(
            (published_at := _parse_datetime(alert.get("published_at"))) is not None
            and _has_verified_pdf(
                alert,
                now=observed_at,
                published_at=published_at,
            )
            for alert in telegram_candidates
        ):
            # Preserve the stronger downloaded-PDF path when it is available.
            return None
        metadata_source = "telegram"
        source_mode = TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE
        for alert in telegram_candidates:
            valid_to = _parse_datetime(alert.get("valid_to"))
            published_at = _parse_datetime(alert.get("published_at"))
            if (
                valid_to is None
                or valid_to <= observed_at
                or published_at is None
                or published_at
                > observed_at + timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS)
                or _official_metadata_alert_identity(alert) is None
                or not alerts_engine.is_actionable_official_alert(alert)
            ):
                continue
            metadata_alerts.append(alert)
        if not metadata_alerts:
            return None
    if pcr_state != "active" or not _pcr_document_membership_complete(pcr):
        return _unavailable_payload(
            observations, reason="official_structured_sources_disagree"
        )

    panels = [
        panel
        for panel in (pcr.get("pcr") or {}).get("alerts") or []
        if isinstance(panel, dict)
    ]
    identities = [_official_metadata_alert_identity(alert) for alert in metadata_alerts]
    if None in identities or len(set(identities)) != len(identities):
        return _unavailable_payload(
            observations, reason="official_structured_sources_disagree"
        )

    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    matched_panel_indexes: set[int] = set()
    for alert in metadata_alerts:
        matching_panels = [
            (index, panel)
            for index, panel in enumerate(panels)
            if _pcr_panel_corroborates_metadata_alert(panel, alert)
        ]
        if len(matching_panels) != 1:
            return _unavailable_payload(
                observations, reason="official_structured_sources_disagree"
            )
        panel_index, panel = matching_panels[0]
        if panel_index in matched_panel_indexes:
            return _unavailable_payload(
                observations, reason="official_structured_sources_disagree"
            )
        matches.append((alert, panel))
        matched_panel_indexes.add(panel_index)

    matched_maximum = max(
        _LEVEL_VALUE[str(alert.get("level") or "").strip().lower()]
        for alert, _panel in matches
    )
    oldest_matched_identity = min(
        identity for identity in identities if identity is not None
    )
    for panel_index, panel in enumerate(panels):
        if panel_index in matched_panel_indexes:
            continue
        levels = _pcr_panel_level_map(panel)
        panel_identities = _pcr_panel_identities(panel)
        if (
            levels is None
            or max(levels.values(), default=0) >= matched_maximum
            or panel_identities is None
            or any(identity >= oldest_matched_identity for identity in panel_identities)
        ):
            return _unavailable_payload(
                observations, reason="official_structured_sources_disagree"
            )

    pcr_revision = str((pcr.get("pcr") or {}).get("revision") or "").lower()
    if _SHA256_RE.fullmatch(pcr_revision) is None:
        return _unavailable_payload(
            observations, reason="official_structured_sources_disagree"
        )
    runtime_alerts = [
        _corroborated_alert_to_runtime(
            alert,
            panel=panel,
            metadata_source=metadata_source,
            observed_at=observed_at,
            pcr_revision=pcr_revision,
        )
        for alert, panel in matches
    ]
    verification = {
        metadata_source: {
            "status": "active",
            "observed_at": _iso(observed_at),
            "event_signature": _event_signature(runtime_alerts),
        },
        "arpa_pcr": {
            "status": "active",
            "observed_at": _iso(observed_at),
            "revision": pcr_revision,
            "document_urls": sorted(_pcr_document_urls(pcr)),
            "document_membership_complete": True,
        },
    }
    return _active_payload(
        runtime_alerts,
        fetched_at=_iso(observed_at),
        verification=verification,
        failures=failures,
        source_mode=source_mode,
    )


def _has_verified_pdf(
    alert: dict[str, Any],
    *,
    now: datetime,
    published_at: datetime | None = None,
) -> bool:
    pdf_verified_at = _parse_datetime(alert.get("pdf_verified_at"))
    pdf_sha256 = str(alert.get("pdf_sha256") or "").strip().lower()
    published = published_at or _parse_datetime(alert.get("published_at"))
    try:
        pdf_size_bytes = int(alert.get("pdf_size_bytes") or 0)
    except (TypeError, ValueError):
        return False
    return bool(
        _SHA256_RE.fullmatch(pdf_sha256)
        and 0 < pdf_size_bytes <= MAX_VERIFIED_PDF_BYTES
        and pdf_verified_at is not None
        and published is not None
        and pdf_verified_at
        >= published - timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS)
        and pdf_verified_at <= now + timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS)
    )


def _persisted_structured_corroboration_kind(
    alert: dict[str, Any],
    *,
    now: datetime,
) -> str | None:
    """Recognize a previously persisted two-source structured decision.

    This is deliberately distinct from PDF verification: ``current`` validates
    the complete durable proof emitted by ``_corroborated_alert_to_runtime``;
    ``legacy_expired`` is a compatibility state usable only to retire that
    exact expired revision.  Neither manufactures ``pdf_verified_at`` or a
    document hash.
    """

    mode = str(alert.get("source_mode") or "").strip()
    expected_method = {
        WIDGET_ARPA_CORROBORATED_SOURCE_MODE: "official_fvg_widget_arpa",
        OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE: "official_fvg_page_arpa",
        TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE: "official_telegram_arpa",
    }.get(mode)
    if expected_method is None:
        return None

    identity = _alert_document_identity(alert)
    if identity is None:
        return None
    year, number = identity
    if _document_url_identity(str(alert.get("pdf_url") or "").strip()) != identity:
        return None
    expected_event_id = f"allerta-regionale-{number}-{year}"
    if (
        str(alert.get("id") or "").strip() != expected_event_id
        or str(alert.get("event_id") or "").strip() != expected_event_id
    ):
        return None

    corroborated_at = _parse_datetime(alert.get("corroborated_at"))
    corroboration = alert.get("corroboration")
    if corroborated_at is None or not isinstance(corroboration, dict):
        return None
    if corroborated_at > now + timedelta(seconds=SOURCE_CLOCK_SKEW_SECONDS):
        return None

    pcr_revision = str(corroboration.get("pcr_revision") or "").strip().lower()
    revision_hash = str(alert.get("revision_hash") or "").strip().lower()
    if (
        str(corroboration.get("method") or "").strip() != expected_method
        or str(corroboration.get("identity") or "").strip()
        != f"{year}:{number}"
        or _SHA256_RE.fullmatch(pcr_revision) is None
        or _SHA256_RE.fullmatch(revision_hash) is None
    ):
        return None

    schema = str(corroboration.get("revision_hash_schema") or "").strip()
    try:
        if schema == STRUCTURED_CORROBORATION_REVISION_SCHEMA:
            expected_revision_hash = _structured_corroboration_revision_hash(
                alert,
                identity=identity,
                pcr_revision=pcr_revision,
            )
            kind = "current"
        elif not schema:
            # Deployed records created before runtime-v2 did not bind ordering,
            # clearance or presentation fields.  They may therefore only
            # authorize retirement of their exact, already-expired revision;
            # they can never authorize presentation or retention.
            valid_to = _parse_datetime(alert.get("valid_to"))
            if valid_to is None or valid_to > now:
                return None
            expected_revision_hash = _legacy_structured_corroboration_revision_hash(
                alert,
                identity=identity,
                pcr_revision=pcr_revision,
            )
            kind = "legacy_expired"
        else:
            return None
    except (TypeError, ValueError):
        return None
    return kind if revision_hash == expected_revision_hash else None


def _has_persisted_structured_corroboration(
    alert: dict[str, Any],
    *,
    now: datetime,
) -> bool:
    return _persisted_structured_corroboration_kind(alert, now=now) is not None


def _has_persisted_authoritative_provenance(
    alert: dict[str, Any],
    *,
    now: datetime,
) -> bool:
    return _has_verified_pdf(alert, now=now) or _has_persisted_structured_corroboration(
        alert,
        now=now,
    )


def _maximum_expiry(alerts: list[dict[str, Any]]) -> str:
    values = [
        str(alert.get("valid_to") or "")
        for alert in alerts
        if _parse_datetime(alert.get("valid_to")) is not None
    ]
    return max(values, default="")


def _cache_max_age_seconds(value: dict[str, Any] | None) -> int:
    timing = (value or {}).get("source_timing")
    raw = (
        (timing or {}).get("cache_max_age_seconds")
        if isinstance(timing, dict)
        else (value or {}).get("cache_max_age_seconds")
    )
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _observation_interval_seconds(
    pcr: dict[str, Any] | None,
    previous_pcr: dict[str, Any] | None,
) -> int:
    max_age = max(
        _cache_max_age_seconds(pcr),
        _cache_max_age_seconds(previous_pcr),
    )
    return max(ARPA_INACTIVE_MINIMUM_CONFIRMATION_SECONDS, max_age + 5 * 60)


def _pcr_source_content_at(pcr: dict[str, Any] | None) -> datetime | None:
    timing = (pcr or {}).get("source_timing")
    if not isinstance(timing, dict):
        return None
    last_modified = _parse_datetime(timing.get("last_modified"))
    if last_modified is not None:
        return last_modified
    http_date = _parse_datetime(timing.get("http_date"))
    if http_date is None:
        return None
    try:
        age_seconds = max(0, int(timing.get("age_seconds") or 0))
    except (TypeError, ValueError):
        return None
    return http_date - timedelta(seconds=age_seconds)


def _pcr_response_at(pcr: dict[str, Any] | None) -> datetime | None:
    timing = (pcr or {}).get("source_timing")
    if not isinstance(timing, dict):
        return None
    http_date = _parse_datetime(timing.get("http_date"))
    if http_date is not None:
        try:
            age_seconds = max(0, int(timing.get("age_seconds") or 0))
        except (TypeError, ValueError):
            return None
        return http_date - timedelta(seconds=age_seconds)
    return _parse_datetime(timing.get("last_modified"))


def _pcr_matches_event(
    pcr: dict[str, Any] | None, alerts: list[dict[str, Any]]
) -> bool:
    mirror_urls = _pcr_document_urls(pcr)
    return bool(
        _pcr_document_membership_complete(pcr)
        and alerts
        and mirror_urls
        and all(_document_urls_contain_alert(alert, mirror_urls) for alert in alerts)
    )


def _alert_document_identity(alert: dict[str, Any]) -> tuple[int, int] | None:
    try:
        year = int(alert.get("alert_year"))
        number = int(alert.get("alert_number"))
    except (TypeError, ValueError):
        return None
    if not 2000 <= year <= 2100 or number <= 0:
        return None
    identity = (year, number)
    document_identity = _document_url_identity(
        str(alert.get("pdf_url") or "").strip()
    )
    if document_identity is not None and document_identity != identity:
        return None
    return identity


def _document_url_identity(url: str) -> tuple[int, int] | None:
    """Return an alert identity only for exact, known official PDF URL forms."""

    try:
        parsed = urlsplit(str(url or "").strip())
    except ValueError:
        return None
    if parsed.scheme.lower() != "https" or parsed.query or parsed.fragment:
        return None
    host = (parsed.hostname or "").lower()
    path = unquote(parsed.path)
    pattern = None
    if host == "cfd.protezionecivile.fvg.it":
        pattern = _CFD_ALERT_DOCUMENT_RE
    elif host == "pianiemergenza.protezionecivile.fvg.it":
        pattern = _PCR_ALERT_DOCUMENT_RE
    elif host == "www.protezionecivile.fvg.it":
        pattern = _OFFICIAL_PAGE_ALERT_DOCUMENT_RE
    if pattern is None or (match := pattern.fullmatch(path)) is None:
        return None
    year = int(match.group("year"))
    number = int(match.group("number"))
    if not 2000 <= year <= 2100 or number <= 0:
        return None
    return year, number


def _document_urls_contain_alert(
    alert: dict[str, Any], document_urls: set[str]
) -> bool:
    official_url = str(alert.get("pdf_url") or "").strip()
    if official_url and official_url in document_urls:
        return True
    identity = _alert_document_identity(alert)
    return bool(
        identity is not None
        and any(_document_url_identity(url) == identity for url in document_urls)
    )


def _pcr_document_urls(pcr: dict[str, Any] | None) -> set[str]:
    return {
        str(url or "").strip()
        for panel in ((pcr or {}).get("pcr") or {}).get("alerts") or []
        if isinstance(panel, dict)
        for url in panel.get("document_urls") or []
        if str(url or "").strip()
    }


def _pcr_document_membership_complete(pcr: dict[str, Any] | None) -> bool:
    panels = ((pcr or {}).get("pcr") or {}).get("alerts") or []
    return bool(panels) and all(
        isinstance(panel, dict)
        and any(str(url or "").strip() for url in panel.get("document_urls") or [])
        for panel in panels
    )


def _verification_document_urls(value: dict[str, Any] | None) -> set[str]:
    return {
        str(url or "").strip()
        for url in (value or {}).get("document_urls") or []
        if str(url or "").strip()
    }


def _missing_document_map(value: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("url") or "").strip(): deepcopy(item)
        for item in (value or {}).get("missing_documents") or []
        if isinstance(item, dict) and str(item.get("url") or "").strip()
    }


def _build_verification(
    *,
    previous: dict[str, Any] | None,
    pcr: dict[str, Any] | None,
    event_signature: str,
    published_at: str,
    alerts: list[dict[str, Any]],
    observed_at: datetime,
) -> dict[str, Any]:
    previous_verification = _verification(previous)
    previous_pcr = previous_verification.get("arpa_pcr")
    if not isinstance(previous_pcr, dict):
        previous_pcr = {}
    previous_telegram = previous_verification.get("telegram")
    if not isinstance(previous_telegram, dict):
        previous_telegram = {}
    same_event = previous_telegram.get("event_signature") == event_signature

    pcr_state = str(((pcr or {}).get("pcr") or {}).get("status") or "unavailable")
    source_content_at = _pcr_source_content_at(pcr)
    pcr_meta: dict[str, Any] = {
        "status": pcr_state,
        "observed_at": _iso(observed_at),
        "revision": str(((pcr or {}).get("pcr") or {}).get("revision") or ""),
        "cache_max_age_seconds": ((pcr or {}).get("source_timing") or {}).get(
            "cache_max_age_seconds"
        ),
    }
    if source_content_at is not None:
        pcr_meta["source_content_at"] = _iso(source_content_at)
    if pcr_state == "active":
        document_urls = _pcr_document_urls(pcr)
        pcr_meta["document_urls"] = sorted(document_urls)
        pcr_meta["document_membership_complete"] = (
            _pcr_document_membership_complete(pcr)
        )
        pcr_meta["last_active_observed_at"] = _iso(observed_at)
        if _pcr_matches_event(pcr, alerts):
            pcr_meta["matched_event_signature"] = event_signature
        # A PDF disappearing from an otherwise valid active PCR panel is a
        # per-alert signal.  Persist the first absence so a cached response can
        # never clear a Telegram/PDF alert on first sight.
        if document_urls and _pcr_document_membership_complete(pcr):
            previous_missing = _missing_document_map(previous_pcr)
            missing_documents = []
            for alert in alerts:
                url = str(alert.get("pdf_url") or "").strip()
                if not url or _document_urls_contain_alert(alert, document_urls):
                    continue
                prior = previous_missing.get(url) or {}
                event_id = _alert_identity(alert)
                revision_key = _alert_revision_key(alert)
                if (
                    str(prior.get("event_id") or "").strip() != event_id
                    or str(prior.get("revision_key") or "").strip().lower()
                    != revision_key
                ):
                    prior = {}
                missing_documents.append(
                    {
                        "url": url,
                        "event_id": event_id,
                        "revision_key": revision_key,
                        "since_observed_at": str(
                            prior.get("since_observed_at") or _iso(observed_at)
                        ),
                        "since_source_at": str(
                            prior.get("since_source_at")
                            or (_iso(source_content_at) if source_content_at else "")
                        ),
                        "first_cache_max_age_seconds": (
                            prior.get("first_cache_max_age_seconds")
                            if prior.get("first_cache_max_age_seconds") is not None
                            else _cache_max_age_seconds(pcr)
                        ),
                    }
                )
            if missing_documents:
                pcr_meta["missing_documents"] = sorted(
                    missing_documents, key=lambda item: item["url"]
                )
    elif pcr_state == "inactive":
        published_value = _parse_datetime(published_at)
        if (
            source_content_at is not None
            and published_value is not None
            and source_content_at > published_value
        ):
            inactive_since = None
            inactive_source_since = None
            if same_event and previous_pcr.get("status") == "inactive":
                inactive_since = _parse_datetime(previous_pcr.get("inactive_since"))
                inactive_source_since = _parse_datetime(
                    previous_pcr.get("inactive_source_since")
                )
            pcr_meta["inactive_since"] = _iso(inactive_since or observed_at)
            pcr_meta["inactive_source_since"] = _iso(
                inactive_source_since or source_content_at
            )
        if same_event and previous_pcr.get("last_active_observed_at"):
            pcr_meta["last_active_observed_at"] = previous_pcr[
                "last_active_observed_at"
            ]

    result = {
        "telegram": {
            "event_signature": event_signature,
            "published_at": published_at,
            "observed_at": _iso(observed_at),
        },
        "arpa_pcr": pcr_meta,
    }
    cleared_alerts = _active_clearances(previous_verification, now=observed_at)
    restored_revisions = {
        _alert_revision_key(alert)
        for alert in alerts
        for clearance in cleared_alerts
        if _alert_revision_key(alert)
        == str(clearance.get("revision_key") or "").strip().lower()
        and _arpa_relists_clearance(
            alert=alert,
            clearance=clearance,
            pcr=pcr,
            now=observed_at,
        )
        and not _clearances_block_alert(
            alert,
            clearances=cleared_alerts,
            pcr=pcr,
            now=observed_at,
        )
    }
    previous_clearance = previous_verification.get("clearance")
    if (
        not restored_revisions
        and same_event
        and isinstance(previous_clearance, dict)
        and previous_clearance.get("event_signature") == event_signature
    ):
        result["clearance"] = deepcopy(previous_clearance)
    cleared_alerts = [
        clearance
        for clearance in cleared_alerts
        if str(clearance.get("revision_key") or "").strip().lower()
        not in restored_revisions
    ]
    if cleared_alerts:
        result["cleared_alerts"] = cleared_alerts
    return result


def _partial_arpa_clearances(
    *,
    previous: dict[str, Any] | None,
    verification: dict[str, Any],
    pcr: dict[str, Any] | None,
    alerts: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    """Return only alerts whose PDF disappeared from a fresh active PCR panel."""

    current_pcr = verification.get("arpa_pcr") or {}
    if current_pcr.get("status") != "active":
        return []
    if current_pcr.get("document_membership_complete") is not True:
        return []
    current_documents = _verification_document_urls(current_pcr)
    if not current_documents:
        # Some valid active panels have no PDF link.  Such a panel can confirm
        # that *something* is active, but not membership of individual alerts.
        return []
    current_source_at = _parse_datetime(current_pcr.get("source_content_at"))
    if current_source_at is None or current_source_at > now:
        return []

    previous_pcr = (_verification(previous).get("arpa_pcr") or {})
    previous_documents = _verification_document_urls(previous_pcr)
    previous_source_at = _parse_datetime(previous_pcr.get("source_content_at"))
    previous_missing = _missing_document_map(previous_pcr)
    current_missing = _missing_document_map(current_pcr)
    interval = _observation_interval_seconds(pcr, previous_pcr)
    removed = []

    for alert in alerts:
        url = str(alert.get("pdf_url") or "").strip()
        published_at = _parse_datetime(alert.get("published_at"))
        if (
            not url
            or _document_urls_contain_alert(alert, current_documents)
            or published_at is None
            or current_source_at <= published_at
        ):
            continue

        # Strong case: the same official page was observed listing this PDF and
        # a strictly newer source representation no longer lists it.
        if (
            previous_pcr.get("status") == "active"
            and _document_urls_contain_alert(alert, previous_documents)
            and previous_source_at is not None
            and current_source_at > previous_source_at
        ):
            removed.append(alert)
            continue

        # Baseline/rollout case: require two source-distinct absences separated
        # by at least the largest advertised cache window plus skew.
        first = previous_missing.get(url)
        latest = current_missing.get(url)
        identity = _alert_identity(alert)
        revision_key = _alert_revision_key(alert)
        if (
            not first
            or not latest
            or str(first.get("event_id") or "").strip() != identity
            or str(latest.get("event_id") or "").strip() != identity
            or str(first.get("revision_key") or "").strip().lower()
            != revision_key
            or str(latest.get("revision_key") or "").strip().lower()
            != revision_key
        ):
            continue
        first_observed_at = _parse_datetime(first.get("since_observed_at"))
        first_source_at = _parse_datetime(first.get("since_source_at"))
        try:
            first_cache_max_age = max(
                0, int(first.get("first_cache_max_age_seconds") or 0)
            )
        except (TypeError, ValueError):
            first_cache_max_age = 0
        required_interval = max(interval, first_cache_max_age + 5 * 60)
        if (
            first_observed_at is None
            or first_source_at is None
            or first_source_at <= published_at
            or current_source_at <= first_source_at
            or (now - first_observed_at).total_seconds() < required_interval
        ):
            continue
        removed.append(alert)

    return removed


def _pcr_has_unmapped_documents(
    verification: dict[str, Any], alerts: list[dict[str, Any]]
) -> bool:
    pcr_meta = verification.get("arpa_pcr") or {}
    if pcr_meta.get("status") != "active":
        return False
    known_documents = {
        str(alert.get("pdf_url") or "").strip()
        for alert in alerts
        if str(alert.get("pdf_url") or "").strip()
    }
    known_identities = {
        identity
        for alert in alerts
        if (identity := _alert_document_identity(alert)) is not None
    }
    return any(
        document not in known_documents
        and _document_url_identity(document) not in known_identities
        for document in _verification_document_urls(pcr_meta)
    )


def _rebase_verification_alerts(
    verification: dict[str, Any],
    *,
    alerts: list[dict[str, Any]],
    observed_at: datetime,
) -> dict[str, Any]:
    rebased = deepcopy(verification)
    signature = _event_signature(alerts) if alerts else ""
    rebased["telegram"] = {
        "event_signature": signature,
        "published_at": _latest_published_at(alerts) if alerts else "",
        "observed_at": _iso(observed_at),
    }
    pcr_meta = rebased.get("arpa_pcr")
    if isinstance(pcr_meta, dict):
        pcr_meta.pop("matched_event_signature", None)
        documents = _verification_document_urls(pcr_meta)
        if any(_document_urls_contain_alert(alert, documents) for alert in alerts):
            pcr_meta["matched_event_signature"] = signature
    return rebased


def _apply_partial_arpa_clearance(
    *,
    previous: dict[str, Any] | None,
    verification: dict[str, Any],
    pcr: dict[str, Any] | None,
    alerts: list[dict[str, Any]],
    now: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    removed = _partial_arpa_clearances(
        previous=previous,
        verification=verification,
        pcr=pcr,
        alerts=alerts,
        now=now,
    )
    if not removed:
        return alerts, verification
    removed_revisions = {_alert_revision_key(alert) for alert in removed}
    remaining = [
        alert for alert in alerts if _alert_revision_key(alert) not in removed_revisions
    ]
    marked = _mark_clearance(
        verification,
        alerts=removed,
        reason="arpa_pcr_document_removed",
        cleared_at=now,
    )
    # This is a membership change, not a clearance of the whole A+B state.
    marked.pop("clearance", None)
    return remaining, _rebase_verification_alerts(
        marked, alerts=remaining, observed_at=now
    )


def _arpa_can_clear(
    *,
    previous: dict[str, Any] | None,
    verification: dict[str, Any],
    pcr: dict[str, Any] | None,
    now: datetime,
) -> bool:
    current_pcr = verification.get("arpa_pcr") or {}
    if current_pcr.get("status") != "inactive":
        return False
    previous_verification = _verification(previous)
    previous_pcr = previous_verification.get("arpa_pcr") or {}
    previous_telegram = previous_verification.get("telegram") or {}
    current_telegram = verification.get("telegram") or {}
    event_signature = current_telegram.get("event_signature")
    if previous_telegram.get("event_signature") != event_signature:
        return False

    published_at = _parse_datetime(current_telegram.get("published_at"))
    current_source_at = _parse_datetime(current_pcr.get("source_content_at"))
    if (
        published_at is None
        or current_source_at is None
        or current_source_at > now
        or current_source_at <= published_at
    ):
        return False

    if previous_pcr.get("status") == "active":
        previous_source_at = _parse_datetime(previous_pcr.get("source_content_at"))
        return (
            previous_pcr.get("matched_event_signature") == event_signature
            and previous_source_at is not None
            and current_source_at > previous_source_at
        )

    if previous_pcr.get("status") != "inactive":
        return False
    first_inactive = _parse_datetime(previous_pcr.get("inactive_since"))
    first_source_at = _parse_datetime(previous_pcr.get("inactive_source_since"))
    if (
        first_inactive is None
        or first_source_at is None
        or first_source_at <= published_at
        or current_source_at <= first_source_at
    ):
        return False
    return (now - first_inactive).total_seconds() >= _observation_interval_seconds(
        pcr, previous_pcr
    )


def _mark_clearance(
    verification: dict[str, Any],
    *,
    alerts: list[dict[str, Any]],
    reason: str,
    cleared_at: datetime,
) -> dict[str, Any]:
    marked = deepcopy(verification)
    arpa_source_at = _parse_datetime(
        ((marked.get("arpa_pcr") or {}).get("source_content_at"))
    )
    event_signature = str((marked.get("telegram") or {}).get("event_signature") or "")
    if event_signature:
        marked["clearance"] = {
            "event_signature": event_signature,
            "reason": reason,
            "cleared_at": _iso(cleared_at),
        }
    clearances = {
        str(item.get("revision_key") or "").strip().lower(): deepcopy(item)
        for item in _active_clearances(marked, now=cleared_at)
    }
    for alert in alerts:
        revision_key = _alert_revision_key(alert)
        published_at = _parse_datetime(alert.get("published_at"))
        legacy_expiry_only = bool(
            reason == "official_validity_expired"
            and _persisted_structured_corroboration_kind(
                alert, now=cleared_at
            )
            == "legacy_expired"
        )
        revision_floor_at = (
            published_at
            if (
                reason == "official_validity_expired"
                and published_at is not None
                and not legacy_expiry_only
            )
            else (
                arpa_source_at
                if reason.startswith("arpa_pcr_") and arpa_source_at is not None
                else cleared_at
            )
        )
        clearances[revision_key] = {
            "event_id": str(alert.get("id") or alert.get("event_id") or "").strip(),
            "revision_key": revision_key,
            "pdf_sha256": str(alert.get("pdf_sha256") or "").strip().lower(),
            "published_at": (
                ""
                if legacy_expiry_only
                else str(alert.get("published_at") or "").strip()
            ),
            "telegram_post_id": (
                None if legacy_expiry_only else alert.get("telegram_post_id")
            ),
            "revision_floor_at": _iso(revision_floor_at),
            "valid_to": str(alert.get("valid_to") or "").strip(),
            "retain_until": _iso(cleared_at + CLEARANCE_RETENTION),
            "reason": reason,
            "cleared_at": _iso(cleared_at),
        }
        if legacy_expiry_only:
            clearances[revision_key]["exact_revision_only"] = True
    if clearances:
        marked["cleared_alerts"] = sorted(
            clearances.values(), key=lambda item: str(item.get("revision_key") or "")
        )
    return marked


def _fresh_cache(
    *, verification: dict[str, Any], failures: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    cache: dict[str, Any] = {
        "status": "fresh",
        "ttl_seconds": alerts_engine.OFFICIAL_ALERTS_CACHE_TTL_SECONDS,
        "verification": verification,
    }
    if failures:
        cache["upstream_failure"] = {"attempts": deepcopy(failures)}
    return cache


def _active_payload(
    alerts: list[dict[str, Any]],
    *,
    fetched_at: str,
    verification: dict[str, Any],
    failures: list[dict[str, Any]],
    source_mode: str = TELEGRAM_VERIFIED_SOURCE_MODE,
) -> dict[str, Any]:
    return {
        "active": True,
        "count": len(alerts),
        "alerts": alerts,
        "source": alerts_engine.PROTEZIONE_CIVILE_ALERTS_SOURCE,
        "source_mode": source_mode,
        "fetched_at": fetched_at,
        "expires_at": _maximum_expiry(alerts),
        "cache": _fresh_cache(verification=verification, failures=failures),
    }


def _inactive_payload(
    *,
    fetched_at: str,
    verification: dict[str, Any],
    source_mode: str,
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "active": False,
        "count": 0,
        "alerts": [],
        "source": alerts_engine.PROTEZIONE_CIVILE_ALERTS_SOURCE,
        "source_mode": source_mode,
        "fetched_at": fetched_at,
        "expires_at": "",
        "cache": _fresh_cache(verification=verification, failures=failures),
    }


def _unavailable_payload(
    observations: dict[str, Any], *, reason: str
) -> dict[str, Any]:
    payload = alerts_engine.build_official_alerts_unavailable_response(reason)
    failures = observations.get("failures")
    if isinstance(failures, list) and failures:
        payload["cache"] = {
            **(payload.get("cache") or {}),
            "upstream_failure": {"attempts": deepcopy(failures)},
        }
    return payload


def _previous_active_alerts(
    previous: dict[str, Any] | None, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    if not isinstance(previous, dict) or previous.get("active") is not True:
        return []
    alerts = []
    for alert in previous.get("alerts") or []:
        if not isinstance(alert, dict):
            continue
        valid_to = _parse_datetime(alert.get("valid_to"))
        if now is not None:
            if valid_to is None or valid_to <= now:
                continue
        alerts.append(deepcopy(alert))
    return alerts


def reconcile_official_alert_observations(
    previous: dict[str, Any] | None,
    observations: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a public alert payload from raw positive/verification sources."""

    current = now or _parse_datetime(observations.get("fetched_at")) or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    fetched_at = _iso(current)
    failures = [
        deepcopy(item)
        for item in observations.get("failures") or []
        if isinstance(item, dict)
    ]
    pcr = _pcr_observation(observations, observed_at=current)
    structured_payload = _structured_metadata_pcr_payload(
        observations,
        pcr=pcr,
        observed_at=current,
        failures=failures,
    )
    if structured_payload is not None:
        return structured_payload
    raw_telegram_alerts = _active_telegram_alerts(observations, now=current)
    all_previous_alerts = _previous_active_alerts(previous)
    unverified_previous_alerts = [
        alert
        for alert in all_previous_alerts
        if not _has_persisted_authoritative_provenance(alert, now=current)
    ]
    if unverified_previous_alerts:
        observed_identities = {
            _alert_identity(alert) for alert in raw_telegram_alerts if _alert_identity(alert)
        }
        if any(
            _alert_identity(alert) not in observed_identities
            for alert in unverified_previous_alerts
        ):
            return _unavailable_payload(
                observations, reason="official_previous_alert_unverified"
            )
        all_previous_alerts = [
            alert
            for alert in all_previous_alerts
            if _has_persisted_authoritative_provenance(alert, now=current)
        ]
    expired_previous_alerts = [
        alert
        for alert in all_previous_alerts
        if (
            (valid_to := _parse_datetime(alert.get("valid_to"))) is not None
            and valid_to <= current
        )
    ]
    if expired_previous_alerts:
        current_pcr_status = str(((pcr or {}).get("pcr") or {}).get("status") or "")
        current_pcr_documents = _pcr_document_urls(pcr)
        current_pcr_membership_complete = _pcr_document_membership_complete(pcr)
        still_claimed_by_arpa = [
            alert
            for alert in expired_previous_alerts
            if current_pcr_status == "active"
            and (
                not current_pcr_membership_complete
                or not current_pcr_documents
                or not str(alert.get("pdf_url") or "").strip()
                or _document_urls_contain_alert(alert, current_pcr_documents)
            )
            and not _has_newer_observed_revision(alert, raw_telegram_alerts)
        ]
        if still_claimed_by_arpa:
            return _unavailable_payload(
                observations, reason="official_active_details_unavailable"
            )
        previous = deepcopy(previous)
        previous_cache = dict((previous or {}).get("cache") or {})
        previous_cache["verification"] = _mark_clearance(
            _verification(previous),
            alerts=expired_previous_alerts,
            reason="official_validity_expired",
            cleared_at=current,
        )
        previous["cache"] = previous_cache
    observed_telegram_alerts = _filter_cleared_alerts(
        raw_telegram_alerts,
        previous=previous,
        pcr=pcr,
        now=current,
    )
    previous_alerts = _filter_cleared_alerts(
        _previous_active_alerts(previous, now=current),
        previous=previous,
        pcr=pcr,
        now=current,
    )
    telegram_alerts = (
        _merge_positive_alerts(
            [
                alert
                for alert in previous_alerts
                if _has_verified_pdf(alert, now=current)
            ],
            observed_telegram_alerts,
        )
        if observed_telegram_alerts
        else []
    )

    if telegram_alerts:
        event_signature = _event_signature(telegram_alerts)
        published_at = _latest_published_at(telegram_alerts)
        verification = _build_verification(
            previous=previous,
            pcr=pcr,
            event_signature=event_signature,
            published_at=published_at,
            alerts=telegram_alerts,
            observed_at=current,
        )
        if _pcr_has_unmapped_documents(verification, telegram_alerts):
            return _unavailable_payload(
                observations, reason="official_active_details_unavailable"
            )
        telegram_alerts, verification = _apply_partial_arpa_clearance(
            previous=previous,
            verification=verification,
            pcr=pcr,
            alerts=telegram_alerts,
            now=current,
        )
        if not telegram_alerts:
            if pcr is not None and pcr.get("pcr", {}).get("status") == "active":
                return _unavailable_payload(
                    observations, reason="official_active_details_unavailable"
                )
            return _inactive_payload(
                fetched_at=fetched_at,
                verification=verification,
                source_mode=ARPA_PCR_SOURCE_MODE,
                failures=failures,
            )
        if _arpa_can_clear(
            previous=previous,
            verification=verification,
            pcr=pcr,
            now=current,
        ):
            return _inactive_payload(
                fetched_at=fetched_at,
                verification=_mark_clearance(
                    verification,
                    alerts=telegram_alerts,
                    reason="arpa_pcr_inactive",
                    cleared_at=current,
                ),
                source_mode=ARPA_PCR_SOURCE_MODE,
                failures=failures,
            )
        return _active_payload(
            telegram_alerts,
            fetched_at=fetched_at,
            verification=verification,
            failures=failures,
        )

    if (
        raw_telegram_alerts
        and not observed_telegram_alerts
        and not previous_alerts
        and not all_previous_alerts
    ):
        if pcr is not None and pcr.get("pcr", {}).get("status") == "active":
            return _unavailable_payload(
                observations, reason="official_active_details_unavailable"
            )
        previous_mode = str((previous or {}).get("source_mode") or "")
        verification = _build_verification(
            previous=previous,
            pcr=pcr,
            event_signature=_event_signature(raw_telegram_alerts),
            published_at=_latest_published_at(raw_telegram_alerts),
            alerts=raw_telegram_alerts,
            observed_at=current,
        )
        return _inactive_payload(
            fetched_at=fetched_at,
            verification=verification,
            source_mode=(
                previous_mode
                if previous_mode
                in {ARPA_PCR_SOURCE_MODE, OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE}
                else ARPA_PCR_SOURCE_MODE
            ),
            failures=failures,
        )

    if all_previous_alerts and not previous_alerts:
        if pcr is not None and pcr.get("pcr", {}).get("status") == "active":
            return _unavailable_payload(
                observations, reason="official_active_details_unavailable"
            )
        if any(_parse_datetime(alert.get("valid_to")) is None for alert in all_previous_alerts):
            return _unavailable_payload(
                observations, reason="official_previous_validity_invalid"
            )
        previous_verification = _verification(previous)
        return _inactive_payload(
            fetched_at=fetched_at,
            verification=_mark_clearance(
                previous_verification,
                alerts=all_previous_alerts,
                reason="official_validity_expired",
                cleared_at=current,
            ),
            source_mode=OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE,
            failures=failures,
        )

    if previous_alerts:
        if len(previous_alerts) != len(all_previous_alerts):
            previous = deepcopy(previous)
            previous["alerts"] = deepcopy(previous_alerts)
            previous["count"] = len(previous_alerts)
            previous["expires_at"] = _maximum_expiry(previous_alerts)
        expiry = max(
            (
                value
                for value in (
                    _parse_datetime(alert.get("valid_to"))
                    for alert in previous_alerts
                )
                if value is not None
            ),
            default=None,
        )
        if expiry is not None and expiry <= current:
            previous_verification = _verification(previous)
            return _inactive_payload(
                fetched_at=fetched_at,
                verification=_mark_clearance(
                    previous_verification,
                    alerts=previous_alerts,
                    reason="official_validity_expired",
                    cleared_at=current,
                ),
                source_mode=OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE,
                failures=failures,
            )

        event_signature = _event_signature(previous_alerts)
        published_at = _latest_published_at(previous_alerts)
        verification = _build_verification(
            previous=previous,
            pcr=pcr,
            event_signature=event_signature,
            published_at=published_at,
            alerts=previous_alerts,
            observed_at=current,
        )
        if _pcr_has_unmapped_documents(verification, previous_alerts):
            return _unavailable_payload(
                observations, reason="official_active_details_unavailable"
            )
        previous_alerts, verification = _apply_partial_arpa_clearance(
            previous=previous,
            verification=verification,
            pcr=pcr,
            alerts=previous_alerts,
            now=current,
        )
        if not previous_alerts:
            if pcr is not None and pcr.get("pcr", {}).get("status") == "active":
                return _unavailable_payload(
                    observations, reason="official_active_details_unavailable"
                )
            return _inactive_payload(
                fetched_at=fetched_at,
                verification=verification,
                source_mode=ARPA_PCR_SOURCE_MODE,
                failures=failures,
            )
        if len(previous_alerts) != int((previous or {}).get("count") or 0):
            previous = deepcopy(previous)
            previous["alerts"] = deepcopy(previous_alerts)
            previous["count"] = len(previous_alerts)
            previous["expires_at"] = _maximum_expiry(previous_alerts)
        if _arpa_can_clear(
            previous=previous,
            verification=verification,
            pcr=pcr,
            now=current,
        ):
            return _inactive_payload(
                fetched_at=fetched_at,
                verification=_mark_clearance(
                    verification,
                    alerts=previous_alerts,
                    reason="arpa_pcr_inactive",
                    cleared_at=current,
                ),
                source_mode=ARPA_PCR_SOURCE_MODE,
                failures=failures,
            )
        if pcr is not None and pcr.get("pcr", {}).get("status") == "active":
            retained = deepcopy(previous)
            retained["fetched_at"] = fetched_at
            retained["cache"] = _fresh_cache(
                verification=verification, failures=failures
            )
            return retained
        if pcr is not None and pcr.get("pcr", {}).get("status") == "inactive":
            retained = deepcopy(previous)
            retained["fetched_at"] = fetched_at
            retained["cache"] = _fresh_cache(
                verification=verification, failures=failures
            )
            return retained
        return _unavailable_payload(observations, reason="official_sources_unavailable")

    if pcr is not None and pcr.get("pcr", {}).get("status") == "inactive":
        verification = _build_verification(
            previous=previous,
            pcr=pcr,
            event_signature="",
            published_at="",
            alerts=[],
            observed_at=current,
        )
        return _inactive_payload(
            fetched_at=fetched_at,
            verification=verification,
            source_mode=ARPA_PCR_SOURCE_MODE,
            failures=failures,
        )

    return _unavailable_payload(observations, reason="official_sources_unavailable")


__all__ = [
    "ARPA_PCR_SOURCE_MODE",
    "OFFICIAL_PAGE_ARPA_CORROBORATED_SOURCE_MODE",
    "OFFICIAL_VALIDITY_EXPIRED_SOURCE_MODE",
    "TELEGRAM_ARPA_CORROBORATED_SOURCE_MODE",
    "TELEGRAM_VERIFIED_SOURCE_MODE",
    "WIDGET_ARPA_CORROBORATED_SOURCE_MODE",
    "fetch_official_alert_observations",
    "reconcile_official_alert_observations",
]
