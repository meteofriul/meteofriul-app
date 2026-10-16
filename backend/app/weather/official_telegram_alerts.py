"""Fail-closed reader for the public Protezione Civile FVG Telegram channel.

Telegram is a positive-only source here: a recognized channel post can add or
revise an official alert, but the absence of such a post can never prove that
there is no active alert. Clearing is delegated to a separately confirmed
ARPA/OSMER mirror state or to the alert validity deadline.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


OFFICIAL_TELEGRAM_CHANNEL = "ProtCivileFVG"
OFFICIAL_TELEGRAM_URL = f"https://t.me/s/{OFFICIAL_TELEGRAM_CHANNEL}"
OFFICIAL_TELEGRAM_TIMEOUT = (5, 25)
OFFICIAL_TELEGRAM_ATTEMPTS = 2
OFFICIAL_TELEGRAM_PDF_TIMEOUT = (5, 12)
OFFICIAL_TELEGRAM_PDF_HOST = "cfd.protezionecivile.fvg.it"
OFFICIAL_TELEGRAM_PDF_PATH_PREFIX = "/docs/alerts/"
OFFICIAL_TELEGRAM_USER_AGENT = "MeteoFriul/3.0 (+https://meteofriul.app/)"
OFFICIAL_TELEGRAM_MAX_PDF_BYTES = 12 * 1024 * 1024
OFFICIAL_TELEGRAM_MIN_PDF_BYTES = 512
OFFICIAL_TELEGRAM_MAX_VALIDITY = timedelta(days=7)
OFFICIAL_TELEGRAM_MAX_PUBLICATION_DISTANCE = timedelta(days=7)


class OfficialTelegramParserError(ValueError):
    """The public channel page was reachable but not safely recognizable."""


class _TelegramChannelHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._div_depth = 0
        self._current = None
        self._text_depth = None
        self.messages: list[dict] = []

    def handle_starttag(self, tag, attrs):
        tag_name = str(tag).lower()
        attributes = {str(key).lower(): value for key, value in attrs}

        if tag_name == "div":
            self._div_depth += 1
            post = str(attributes.get("data-post") or "").strip()
            if self._current is None and post:
                self._current = {
                    "depth": self._div_depth,
                    "post": post,
                    "text": [],
                    "links": [],
                    "published_at": "",
                    "closed": False,
                }
                self.messages.append(self._current)

            if self._current is not None:
                classes = set(str(attributes.get("class") or "").split())
                if "js-message_text" in classes and self._text_depth is None:
                    self._text_depth = self._div_depth

        if self._current is None:
            return

        if tag_name == "br" and self._text_depth is not None:
            self._current["text"].append("\n")

        if tag_name == "a" and self._text_depth is not None:
            href = str(attributes.get("href") or "").strip()
            if href:
                self._current["text"].append(" ")
                self._current["links"].append(href)

        if tag_name == "time":
            published_at = str(attributes.get("datetime") or "").strip()
            if published_at:
                self._current["published_at"] = published_at

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self._current is not None and self._text_depth is not None:
            self._current["text"].append(data)

    def handle_endtag(self, tag):
        if str(tag).lower() != "div":
            return

        if self._current is not None and self._text_depth == self._div_depth:
            self._text_depth = None

        if self._current is not None and self._current["depth"] == self._div_depth:
            self._current["closed"] = True
            self._current = None
            self._text_depth = None

        self._div_depth = max(0, self._div_depth - 1)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _official_pdf_url(links) -> str:
    for value in links or []:
        parsed = urlparse(str(value or "").strip())
        if (
            parsed.scheme == "https"
            and parsed.hostname == OFFICIAL_TELEGRAM_PDF_HOST
            and parsed.path.startswith(OFFICIAL_TELEGRAM_PDF_PATH_PREFIX)
            and parsed.path.lower().endswith(".pdf")
        ):
            return parsed.geturl()
    return ""


def _official_pdf_matches_alert_identity(
    pdf_url: str,
    *,
    alert_number: int,
    alert_year: int,
) -> bool:
    filename = unquote(urlparse(str(pdf_url or "")).path.rsplit("/", 1)[-1])
    return re.fullmatch(
        rf"Allerta_regionale_{alert_number}-{alert_year}(?:_[^/]*)?\.pdf",
        filename,
        re.I,
    ) is not None


def _alert_levels(text: str) -> list[str]:
    normalized = _normalize_text(text).lower()
    rank = {"verde": 0, "gialla": 1, "arancione": 2, "rossa": 3}
    aliases = {
        "verde": "verde",
        "gialla": "gialla",
        "giallo": "gialla",
        "arancione": "arancione",
        "arancio": "arancione",
        "rossa": "rossa",
        "rosso": "rossa",
    }
    return sorted(
        {
            canonical
            for token, canonical in aliases.items()
            if re.search(rf"\b{re.escape(token)}\b", normalized)
        },
        key=rank.get,
        reverse=True,
    )


def _alert_level(text: str) -> str:
    levels = _alert_levels(text)
    return levels[0] if levels else ""


def _alert_risks(text: str) -> list[str]:
    normalized = _normalize_text(text).lower()
    matches = []
    for needle, label in (
        ("idrogeologic", "idrogeologico"),
        ("idraulic", "idraulico"),
        ("temporal", "temporali"),
        ("meteorologic", "meteorologico"),
        ("vento", "vento"),
        ("neve", "neve"),
        ("ghiaccio", "ghiaccio"),
        ("valang", "valanghe"),
        ("costier", "costiero"),
        ("mareggiat", "mareggiata"),
        ("acqua alta", "acqua_alta"),
    ):
        if needle in normalized and label not in matches:
            matches.append(label)
    return matches


def _alert_zones(text: str) -> tuple[list[str], str]:
    normalized = _normalize_text(text)
    zone_letters = set()
    for match in re.finditer(
        r"\bFVG(?:\s*-\s*|\s+)([A-D](?:\s*-\s*[A-D])*)\b",
        normalized,
        re.I,
    ):
        zone_letters.update(re.findall(r"[A-D]", match.group(1).upper()))
    zones = [f"FVG-{letter}" for letter in sorted(zone_letters)]
    if re.search(
        r"\b(?:SU\s+)?TUTT(?:A|E)\s+(?:LA\s+REGIONE|IL\s+FVG|LE\s+ZONE)\b",
        normalized,
        re.I,
    ):
        return ["FVG-A", "FVG-B", "FVG-C", "FVG-D"], "Tutta la regione"
    if zones:
        return zones, ", ".join(f"zona {zone}" for zone in zones)
    return [], ""


def _local_datetime(day: str, month: str, year: int, hour: str, minute: str) -> str:
    day_value = int(day)
    month_value = int(month)
    hour_value = int(hour)
    if hour_value == 24:
        hour_value = 0
        base = datetime(year, month_value, day_value, hour_value, int(minute))
        base += timedelta(days=1)
    else:
        base = datetime(year, month_value, day_value, hour_value, int(minute))
    try:
        fvg_timezone = ZoneInfo("Europe/Rome")
    except ZoneInfoNotFoundError:
        # Windows Python installations may not ship the IANA database.  The
        # EU rule is sufficient for these civil alert boundaries: summer time
        # runs from the last Sunday in March to the last Sunday in October.
        last_sunday_march = max(
            day
            for day in range(25, calendar.monthrange(base.year, 3)[1] + 1)
            if datetime(base.year, 3, day).weekday() == 6
        )
        last_sunday_october = max(
            day
            for day in range(25, calendar.monthrange(base.year, 10)[1] + 1)
            if datetime(base.year, 10, day).weekday() == 6
        )
        is_summer = (
            4 <= base.month <= 9
            or (
                base.month == 3
                and (base.day > last_sunday_march or (base.day == last_sunday_march and base.hour >= 3))
            )
            or (
                base.month == 10
                and (base.day < last_sunday_october or (base.day == last_sunday_october and base.hour < 3))
            )
        )
        fvg_timezone = timezone(timedelta(hours=2 if is_summer else 1))
    base = base.replace(tzinfo=fvg_timezone)
    return base.isoformat(timespec="seconds")


def _published_fvg_datetime(value: datetime) -> datetime:
    try:
        fvg_timezone = ZoneInfo("Europe/Rome")
    except ZoneInfoNotFoundError:
        # Calendar-year coherence is only sensitive around New Year, when
        # Friuli-Venezia Giulia is always on standard time (UTC+1).
        fvg_timezone = timezone(timedelta(hours=1))
    return value.astimezone(fvg_timezone)


def _identity_year_is_coherent(alert_year: int, published_at: datetime) -> bool:
    published_local = _published_fvg_datetime(published_at)
    if alert_year == published_local.year:
        return True
    if (
        published_local.month == 12
        and published_local.day >= 25
        and alert_year == published_local.year + 1
    ):
        return True
    if (
        published_local.month == 1
        and published_local.day <= 7
        and alert_year == published_local.year - 1
    ):
        return True
    return False


def _expand_explicit_year(value: str | None, *, reference_year: int) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 2:
        return (reference_year // 100) * 100 + int(text)
    return int(text)


def _ordered_local_window(
    *,
    start_day: str,
    start_month: str,
    start_hour: str,
    start_minute: str,
    end_day: str,
    end_month: str,
    end_hour: str,
    end_minute: str,
    year: int,
    published_at: datetime,
    explicit_start_year: str | None = None,
    explicit_end_year: str | None = None,
) -> tuple[str, str]:
    candidates = []
    explicit_start_year_value = _expand_explicit_year(
        explicit_start_year,
        reference_year=year,
    )
    explicit_end_year_value = _expand_explicit_year(
        explicit_end_year,
        reference_year=year,
    )
    start_years = (
        (explicit_start_year_value,)
        if explicit_start_year_value is not None
        else range(year - 1, year + 2)
    )
    for start_year in start_years:
        try:
            start = _local_datetime(
                start_day, start_month, start_year, start_hour, start_minute
            )
        except (OverflowError, ValueError):
            continue
        start_value = _parse_iso_datetime(start)
        if start_value is None:
            continue

        end_years = (
            (explicit_end_year_value,)
            if explicit_end_year_value is not None
            else (start_year, start_year + 1)
        )
        for end_year in end_years:
            try:
                end = _local_datetime(
                    end_day, end_month, end_year, end_hour, end_minute
                )
            except (OverflowError, ValueError):
                continue
            end_value = _parse_iso_datetime(end)
            if end_value is None or end_value <= start_value:
                continue

            duration = end_value - start_value
            if duration > OFFICIAL_TELEGRAM_MAX_VALIDITY:
                continue
            if published_at > end_value:
                continue
            if (
                abs(start_value - published_at)
                > OFFICIAL_TELEGRAM_MAX_PUBLICATION_DISTANCE
                or abs(end_value - published_at)
                > OFFICIAL_TELEGRAM_MAX_PUBLICATION_DISTANCE
            ):
                continue

            candidates.append(
                (
                    abs(start_value - published_at),
                    abs(end_value - published_at),
                    start_value,
                    start,
                    end,
                )
            )

    if not candidates:
        return "", ""
    _, _, _, start, end = min(candidates, key=lambda candidate: candidate[:3])
    return start, end


def _validity_window(
    text: str,
    *,
    year: int,
    published_at: datetime,
) -> tuple[str, str]:
    normalized = _normalize_text(text).upper().replace("’", "'")
    date_intro = r"(?:DEL|DI)(?:\s+[A-ZÀ-ÖØ-Þ']+)?"
    full = re.search(
        rf"DALLE\s+(?:ORE\s+)?(\d{{1,2}})(?:(?::|\.)(\d{{2}}))?\s+{date_intro}\s+"
        r"(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?\s+ALLE\s+"
        rf"(?:ORE\s+)?(\d{{1,2}})(?:(?::|\.)(\d{{2}}))?\s+{date_intro}\s+"
        r"(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?",
        normalized,
    )
    if full:
        sh, sm, sd, smo, sy, eh, em, ed, emo, ey = full.groups()
        sm = sm or "00"
        em = em or "00"
        return _ordered_local_window(
            start_day=sd,
            start_month=smo,
            start_hour=sh,
            start_minute=sm,
            end_day=ed,
            end_month=emo,
            end_hour=eh,
            end_minute=em,
            year=year,
            published_at=published_at,
            explicit_start_year=sy,
            explicit_end_year=ey,
        )

    same_day = re.search(
        r"DALLE\s+(?:ORE\s+)?(\d{1,2})(?:(?::|\.)(\d{2}))?\s+ALLE\s+"
        r"(?:ORE\s+)?(\d{1,2})(?:(?::|\.)(\d{2}))?\s+"
        rf"{date_intro}\s+(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{4}}|\d{{2}}))?",
        normalized,
    )
    if same_day:
        sh, sm, eh, em, day, month, explicit_year = same_day.groups()
        sm = sm or "00"
        em = em or "00"
        return _ordered_local_window(
            start_day=day,
            start_month=month,
            start_hour=sh,
            start_minute=sm,
            end_day=day,
            end_month=month,
            end_hour=eh,
            end_minute=em,
            year=year,
            published_at=published_at,
            explicit_start_year=explicit_year,
            explicit_end_year=explicit_year,
        )
    return "", ""


def _parse_alert_message(message: dict) -> dict | None:
    post = str(message.get("post") or "").strip()
    match = re.fullmatch(rf"{OFFICIAL_TELEGRAM_CHANNEL}/(\d+)", post)
    if not match:
        return None

    text = _normalize_text("".join(message.get("text") or []))
    if not re.search(r"#AllertameteoFVG\b", text, re.I):
        return None

    identity = re.search(
        r"ALLERTA\s+REGIONALE(?:\s+N\.)?\s*(\d+)\s*(?:DEL|/)\s*(\d{4})",
        text,
        re.I,
    )
    published = _parse_iso_datetime(message.get("published_at"))
    pdf_url = _official_pdf_url(message.get("links"))
    level = _alert_level(text)
    if identity is None or published is None or not pdf_url or not level:
        raise OfficialTelegramParserError("unrecognized_official_alert_post")

    alert_number, alert_year = (int(value) for value in identity.groups())
    if alert_number <= 0 or not _identity_year_is_coherent(alert_year, published):
        raise OfficialTelegramParserError("unrecognized_official_alert_identity")
    if not _official_pdf_matches_alert_identity(
        pdf_url,
        alert_number=alert_number,
        alert_year=alert_year,
    ):
        raise OfficialTelegramParserError("unrecognized_official_alert_pdf_identity")
    try:
        valid_from, valid_to = _validity_window(
            text,
            year=alert_year,
            published_at=published,
        )
    except (OverflowError, ValueError) as error:
        raise OfficialTelegramParserError(
            "unrecognized_official_alert_validity"
        ) from error
    if not valid_from or not valid_to:
        raise OfficialTelegramParserError("unrecognized_official_alert_validity")

    zones, area = _alert_zones(text)
    levels = _alert_levels(text)
    content_hash = hashlib.sha256(
        f"{alert_year}:{alert_number}:{text}:{pdf_url}".encode("utf-8")
    ).hexdigest()
    return {
        "id": f"allerta-regionale-{alert_number}-{alert_year}",
        "alert_number": alert_number,
        "alert_year": alert_year,
        "level": level,
        "levels": levels,
        "mixed_levels": len(levels) > 1,
        "risks": _alert_risks(text),
        "zones": zones,
        "area": area,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "official_text": text,
        "pdf_url": pdf_url,
        "telegram_post_id": int(match.group(1)),
        "telegram_post_url": f"https://t.me/{OFFICIAL_TELEGRAM_CHANNEL}/{match.group(1)}",
        "published_at": published.isoformat(timespec="seconds"),
        "revision_hash": content_hash,
    }


def parse_official_telegram_channel(html: str) -> dict:
    parser = _TelegramChannelHtmlParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception as error:
        raise OfficialTelegramParserError("invalid_channel_html") from error

    own_channel_messages = [
        message
        for message in parser.messages
        if re.fullmatch(
            rf"{OFFICIAL_TELEGRAM_CHANNEL}/\d+", str(message.get("post") or "")
        )
    ]
    if not own_channel_messages:
        raise OfficialTelegramParserError("unrecognized_channel_page")
    if any(not message.get("closed") for message in own_channel_messages):
        raise OfficialTelegramParserError("invalid_channel_html")
    recognized_messages = own_channel_messages

    alerts_by_identity = {}
    for message in recognized_messages:
        alert = _parse_alert_message(message)
        if alert is None:
            continue
        key = (alert["alert_year"], alert["alert_number"])
        previous = alerts_by_identity.get(key)
        if previous is None or (
            alert["published_at"], alert["telegram_post_id"]
        ) > (
            previous["published_at"],
            previous["telegram_post_id"],
        ):
            alerts_by_identity[key] = alert

    latest_post_id = max(
        int(str(message["post"]).rsplit("/", 1)[1]) for message in recognized_messages
    )
    return {
        "source": {
            "id": "protezione_civile_fvg_telegram",
            "name": "Protezione Civile FVG · Telegram",
            "url": OFFICIAL_TELEGRAM_URL,
        },
        "source_mode": "official_telegram_positive_only",
        "latest_post_id": latest_post_id,
        "alerts": sorted(
            alerts_by_identity.values(),
            key=lambda item: (item["published_at"], item["telegram_post_id"]),
        ),
        "can_confirm_inactive": False,
    }


def _verify_official_pdf(
    alert: dict,
    *,
    getter,
    verified_at: datetime,
) -> dict:
    requested_url = str(alert.get("pdf_url") or "").strip()
    response = getter(
        requested_url,
        headers={
            "User-Agent": OFFICIAL_TELEGRAM_USER_AGENT,
            "Accept": "application/pdf,application/octet-stream;q=0.8",
        },
        timeout=OFFICIAL_TELEGRAM_PDF_TIMEOUT,
        stream=True,
        allow_redirects=True,
    )
    try:
        response.raise_for_status()
        final_url = str(getattr(response, "url", None) or requested_url).strip()
        if (
            _official_pdf_url([final_url]) != final_url
            or not _official_pdf_matches_alert_identity(
                final_url,
                alert_number=int(alert.get("alert_number") or 0),
                alert_year=int(alert.get("alert_year") or 0),
            )
        ):
            raise OfficialTelegramParserError("unexpected_official_pdf_redirect")

        content_type = str((getattr(response, "headers", {}) or {}).get(
            "Content-Type", ""
        )).split(";", 1)[0].strip().lower()
        if content_type not in {"application/pdf", "application/octet-stream"}:
            raise OfficialTelegramParserError("unexpected_official_pdf_content_type")

        raw_length = str((getattr(response, "headers", {}) or {}).get(
            "Content-Length", ""
        )).strip()
        declared_length = None
        if raw_length:
            try:
                declared_length = int(raw_length)
            except ValueError as error:
                raise OfficialTelegramParserError(
                    "invalid_official_pdf_content_length"
                ) from error
            if declared_length <= 0 or declared_length > OFFICIAL_TELEGRAM_MAX_PDF_BYTES:
                raise OfficialTelegramParserError("official_pdf_size_out_of_bounds")

        digest = hashlib.sha256()
        total = 0
        prefix = bytearray()
        tail = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > OFFICIAL_TELEGRAM_MAX_PDF_BYTES:
                raise OfficialTelegramParserError("official_pdf_size_out_of_bounds")
            if len(prefix) < 5:
                prefix.extend(chunk[: 5 - len(prefix)])
            tail.extend(chunk)
            if len(tail) > 2048:
                del tail[:-2048]
            digest.update(chunk)
        if declared_length is not None and declared_length != total:
            raise OfficialTelegramParserError("official_pdf_content_length_mismatch")
        if (
            total < OFFICIAL_TELEGRAM_MIN_PDF_BYTES
            or bytes(prefix) != b"%PDF-"
            or b"%%EOF" not in bytes(tail)
        ):
            raise OfficialTelegramParserError("invalid_official_pdf_content")

        verified = dict(alert)
        verified["pdf_url"] = final_url
        verified["pdf_sha256"] = digest.hexdigest()
        verified["pdf_size_bytes"] = total
        verified["pdf_verified_at"] = verified_at.astimezone(timezone.utc).isoformat(
            timespec="seconds"
        )
        return verified
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def fetch_official_telegram_channel(
    *,
    session=None,
    now=lambda: datetime.now(timezone.utc),
    verify_active_pdfs: bool = True,
) -> dict:
    client = session or requests
    response = None
    for attempt in range(OFFICIAL_TELEGRAM_ATTEMPTS):
        try:
            response = client.get(
                OFFICIAL_TELEGRAM_URL,
                headers={
                    "User-Agent": OFFICIAL_TELEGRAM_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "it-IT,it;q=0.9",
                },
                timeout=OFFICIAL_TELEGRAM_TIMEOUT,
            )
            break
        except (requests.Timeout, requests.ConnectionError):
            if attempt + 1 >= OFFICIAL_TELEGRAM_ATTEMPTS:
                raise
    if response is None:
        raise requests.ConnectionError("official Telegram channel unavailable")
    try:
        response.raise_for_status()
        page_html = response.text
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    parsed = parse_official_telegram_channel(page_html)
    fetched_at = now()
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    fetched_at = fetched_at.astimezone(timezone.utc)
    verified_alerts = []
    for alert in parsed.get("alerts") or []:
        valid_from = _parse_iso_datetime(alert.get("valid_from"))
        valid_to = _parse_iso_datetime(alert.get("valid_to"))
        published_at = _parse_iso_datetime(alert.get("published_at"))
        if (
            verify_active_pdfs
            and valid_from is not None
            and valid_to is not None
            and valid_to > fetched_at
            and published_at is not None
            and published_at <= fetched_at + timedelta(minutes=5)
        ):
            verified_alerts.append(
                _verify_official_pdf(
                    alert,
                    getter=client.get,
                    verified_at=fetched_at,
                )
            )
        else:
            verified_alerts.append(alert)
    parsed["alerts"] = verified_alerts
    parsed["fetched_at"] = fetched_at.isoformat(timespec="seconds")
    return parsed
