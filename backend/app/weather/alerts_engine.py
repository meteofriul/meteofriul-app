"""Direct, cache-aware access to official Protezione Civile FVG alerts."""

from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.9+ always provides it.
    ZoneInfo = None


PROTEZIONE_CIVILE_ALERTS_URL = "https://www.protezionecivile.fvg.it/it/allerte"

PROTEZIONE_CIVILE_ALERTS_WIDGET_URL = "https://pianiemergenza.protezionecivile.fvg.it/api/alerts.jsonp"

PROTEZIONE_CIVILE_ALERTS_TIMEOUT = (10, 12)

HTTP_USER_AGENT = "MeteoFriul/3.0 (+https://meteofriul.it)"

PCFVG_BROWSER_USER_AGENT = os.getenv(
    "PCFVG_BROWSER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36",
).strip()

def normalize_push_language(value: str) -> str:
    return "fur" if str(value or "").strip().lower() == "fur" else "it"

def make_cache_key(*parts):
    return "|".join(str(part).strip().lower() for part in parts)

PROTEZIONE_CIVILE_ALERTS_SOURCE = {
    "id": "protezione_civile_fvg_alerts",
    "name": "Protezione Civile FVG",
    "type": "official_alert_source",
    "url": PROTEZIONE_CIVILE_ALERTS_URL,
}

OFFICIAL_ALERTS_UPSTREAM_FAILURE_CATEGORIES = frozenset(
    {"http", "dns", "timeout", "connection", "parser"}
)
OFFICIAL_ALERTS_UPSTREAM_FAILURE_SOURCES = frozenset(
    {"widget", "html", "telegram", "arpa_pcr", "unknown"}
)


class OfficialAlertsParserError(ValueError):
    """An upstream response was reachable but could not be safely classified."""


def sanitize_official_alerts_upstream_failure(value) -> dict | None:
    """Return only the allowlisted diagnostic fields safe for API/job output."""

    if not isinstance(value, dict) or not isinstance(value.get("attempts"), list):
        return None

    attempts = []
    for raw_attempt in value["attempts"][:4]:
        if not isinstance(raw_attempt, dict):
            continue

        source = str(raw_attempt.get("source") or "").strip().lower()
        category = str(raw_attempt.get("category") or "").strip().lower()
        if source not in OFFICIAL_ALERTS_UPSTREAM_FAILURE_SOURCES:
            continue
        if category not in OFFICIAL_ALERTS_UPSTREAM_FAILURE_CATEGORIES:
            continue

        attempt = {"source": source, "category": category}
        status_code = raw_attempt.get("status_code")
        if category == "http" and not isinstance(status_code, bool):
            try:
                status_code = int(status_code)
            except (TypeError, ValueError):
                status_code = None
            if status_code is not None and 100 <= status_code <= 599:
                attempt["status_code"] = status_code
        phase = raw_attempt.get("phase")
        if category == "timeout" and phase in {"connect", "read"}:
            attempt["phase"] = phase
        attempts.append(attempt)

    return {"attempts": attempts} if attempts else None


class OfficialAlertsUpstreamError(requests.RequestException):
    """A sanitized aggregate failure across the official upstream sources."""

    def __init__(self, attempts: list[dict]):
        diagnostic = sanitize_official_alerts_upstream_failure(
            {"attempts": attempts}
        ) or {"attempts": [{"source": "unknown", "category": "connection"}]}
        self.diagnostic = diagnostic
        super().__init__("official_alerts_upstream_failed")


def _exception_chain_contains_dns_error(error: BaseException) -> bool:
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if not isinstance(current, BaseException) or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, socket.gaierror):
            return True
        if current.__class__.__name__ == "NameResolutionError":
            return True

        pending.extend(
            candidate
            for candidate in (
                current.__cause__,
                current.__context__,
                getattr(current, "reason", None),
                *current.args,
            )
            if isinstance(candidate, BaseException)
        )
    return False


def _request_failure_attempt(source: str, error: requests.RequestException) -> dict:
    if isinstance(error, requests.HTTPError):
        attempt = {"source": source, "category": "http"}
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if not isinstance(status_code, bool):
            try:
                status_code = int(status_code)
            except (TypeError, ValueError):
                status_code = None
            if status_code is not None and 100 <= status_code <= 599:
                attempt["status_code"] = status_code
        return attempt
    if isinstance(error, requests.Timeout):
        return {"source": source, "category": "timeout"}
    if _exception_chain_contains_dns_error(error):
        return {"source": source, "category": "dns"}
    return {"source": source, "category": "connection"}


def _upstream_failure_diagnostic(error: requests.RequestException) -> dict:
    if isinstance(error, OfficialAlertsUpstreamError):
        return error.diagnostic
    return {
        "attempts": [_request_failure_attempt("unknown", error)],
    }


class _CivilProtectionAlertsHtmlStateParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._div_depth = 0
        self._open_views = []
        self.views = []

    def handle_starttag(self, tag, attrs):
        if str(tag).lower() != "div":
            return

        self._div_depth += 1
        attributes = {str(key).lower(): value for key, value in attrs}
        classes = set(str(attributes.get("class") or "").split())
        if "view-allerte" in classes:
            state = {
                "depth": self._div_depth,
                "closed": False,
                "has_content": False,
                "empty_depth": None,
                "empty_closed": False,
                "empty_text": [],
                "view_text": [],
            }
            self.views.append(state)
            self._open_views.append(state)

        if not self._open_views:
            return

        state = self._open_views[-1]
        if "view-content" in classes:
            state["has_content"] = True
        if (
            "view-empty" in classes
            and self._div_depth == state["depth"] + 1
            and state["empty_depth"] is None
        ):
            state["empty_depth"] = self._div_depth

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        for state in self._open_views:
            state["view_text"].append(data)
            if state["empty_depth"] is not None:
                state["empty_text"].append(data)

    def handle_endtag(self, tag):
        if str(tag).lower() != "div":
            return

        for state in self._open_views:
            if state["empty_depth"] == self._div_depth:
                state["empty_depth"] = None
                state["empty_closed"] = True

        if self._open_views and self._open_views[-1]["depth"] == self._div_depth:
            self._open_views[-1]["closed"] = True
            self._open_views.pop()
        self._div_depth = max(0, self._div_depth - 1)


def html_confirms_no_active_alerts(html: str) -> bool:
    parser = _CivilProtectionAlertsHtmlStateParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        return False

    for state in parser.views:
        empty_text = normalize_for_search(" ".join(state["empty_text"]))
        view_text = normalize_for_search(" ".join(state["view_text"]))
        if (
            state["closed"]
            and state["empty_closed"]
            and not state["has_content"]
            and empty_text == "nessuna allerta in corso"
            and view_text == empty_text
        ):
            return True
    return False

def html_to_lines(html: str) -> list[str]:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html or "")
    text = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return [line.strip() for line in text.splitlines() if line.strip()]

def parse_civil_protection_datetime(value: str) -> str:
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\d{1,2}):(\d{2})", value or "")
    if not match:
        return ""

    day, month, year, hour, minute = match.groups()
    try:
        parsed = datetime(
            int(year), int(month), int(day), int(hour), int(minute),
            tzinfo=get_fvg_timezone(),
        )
    except ValueError:
        return ""
    return parsed.isoformat(timespec="seconds")

def extract_alert_level(text: str) -> str:
    normalized = normalize_for_search(text)

    if "ross" in normalized:
        return "rossa"
    if "aranc" in normalized:
        return "arancione"
    if "giall" in normalized:
        return "gialla"
    if "verde" in normalized:
        return "verde"

    return ""

def extract_alert_risks(text: str) -> list[str]:
    normalized = normalize_for_search(text)
    risks = []
    candidates = [
        ("idrogeologic", "idrogeologico"),
        ("idraulic", "idraulico"),
        ("temporal", "temporali"),
        ("meteorologic", "meteorologico"),
        ("vento", "vento"),
        ("neve", "neve"),
        ("valang", "valanghe"),
        ("costier", "costiero"),
    ]

    for needle, label in candidates:
        if needle in normalized and label not in risks:
            risks.append(label)

    return risks

def extract_alert_time_window(text: str) -> str:
    match = re.search(
        r"DALLE\s+(?:ORE\s+)?(\d{1,2}:\d{2})\s+DEL\s+(\d{1,2}/\d{1,2})\s+ALLE\s+(?:ORE\s+)?(\d{1,2}:\d{2})\s+DEL\s+(\d{1,2}/\d{1,2})",
        text or "",
        re.IGNORECASE,
    )

    if not match:
        return ""

    start_time, start_day, end_time, end_day = match.groups()
    return f"{start_time} {start_day}-{end_time} {end_day}"

def extract_alert_area(text: str) -> str:
    normalized_text = re.sub(r"\s+", " ", text or "").strip()
    areas = []

    if re.search(r"\bSU\s+TUTTA\s+LA\s+REGIONE\b", normalized_text, re.IGNORECASE):
        areas.append("Tutta la regione")

    for zone in re.findall(r"\bZONA\s+(FVG-[A-Z])\b", normalized_text, re.IGNORECASE):
        label = f"zona {zone.upper()}"
        if label not in areas:
            areas.append(label)

    return ", ".join(areas)

def build_official_alert_push_body(level: str, risks: list[str], time_window: str, area: str, language: str = "it") -> str:
    language = normalize_push_language(language)
    level_label = level.strip().lower() if level else ""
    adjectives = []
    qualifiers = []

    if language == "fur":
        level_label = {
            "gialla": "zale",
            "arancione": "naranç",
            "rossa": "rosse",
        }.get(level_label, level_label)

        if "idrogeologico" in risks:
            adjectives.append("idrogeologjiche")

        if "idraulico" in risks and "costiero" in risks:
            adjectives.append("idrauliche costiere")
        elif "idraulico" in risks:
            adjectives.append("idrauliche")
        elif "costiero" in risks:
            adjectives.append("costiere")

        if "meteorologico" in risks and not adjectives:
            adjectives.append("meteorologjiche")

        qualifier_map = {
            "temporali": "par temporâi",
            "vento": "par vint",
            "neve": "par nêf",
            "valanghe": "par valanghis",
        }
        for risk in ("temporali", "vento", "neve", "valanghe"):
            if risk in risks:
                qualifiers.append(qualifier_map[risk])

        risk_label_map = {
            "idrogeologico": "idrogeologjiche",
            "idraulico": "idrauliche",
            "costiero": "costiere",
            "meteorologico": "meteorologjiche",
        }
        joiner = " e "
        alert_sentence = f"Alerte {level_label}" if level_label else "Alerte meteo"
        time_prefix = "Des"
        time_middle = "dai"
        time_to = "aes"
        skip_region_label = "tutta la regione"
    else:
        if "idrogeologico" in risks:
            adjectives.append("idrogeologica")

        if "idraulico" in risks and "costiero" in risks:
            adjectives.append("idraulica costiera")
        elif "idraulico" in risks:
            adjectives.append("idraulica")
        elif "costiero" in risks:
            adjectives.append("costiera")

        if "meteorologico" in risks and not adjectives:
            adjectives.append("meteorologica")
        if "temporali" in risks:
            qualifiers.append("per temporali")
        if "vento" in risks:
            qualifiers.append("per vento")
        if "neve" in risks:
            qualifiers.append("per neve")
        if "valanghe" in risks:
            qualifiers.append("per valanghe")

        risk_label_map = {
            "idrogeologico": "idrogeologica",
            "idraulico": "idraulica",
            "costiero": "costiera",
            "meteorologico": "meteorologica",
        }
        joiner = " e "
        alert_sentence = f"Allerta {level_label}" if level_label else "Allerta meteo"
        time_prefix = "Dalle"
        time_middle = "del"
        time_to = "alle"
        skip_region_label = "tutta la regione"

    for risk in risks:
        label = risk_label_map.get(risk, risk)
        if label in ("temporali", "vento", "neve", "valanghe"):
            continue
        if label not in adjectives and len(adjectives) < 3:
            adjectives.append(label)

    if adjectives:
        selected_adjectives = adjectives[:3]
        alert_sentence += " " + (
            ", ".join(selected_adjectives[:-1]) + f"{joiner}{selected_adjectives[-1]}"
            if len(selected_adjectives) > 1
            else selected_adjectives[0]
        )
    elif not level_label:
        alert_sentence += " FVG"

    if qualifiers:
        alert_sentence += " " + joiner.join(qualifiers[:2])

    parts = []
    time_match = re.match(
        r"(\d{1,2}:\d{2})\s+(\d{1,2}/\d{1,2})-(\d{1,2}:\d{2})\s+(\d{1,2}/\d{1,2})",
        time_window or "",
    )
    if time_match:
        start_time, start_day, end_time, end_day = time_match.groups()
        parts.append(f"{time_prefix} {start_time} {time_middle} {start_day} {time_to} {end_time} {time_middle} {end_day}")

    parts.append(alert_sentence)
    if area and skip_region_label not in area.lower():
        localized_area = area
        if language == "fur":
            localized_area = re.sub(r"\bzona\b", "zone", area, flags=re.IGNORECASE)
        parts.append(localized_area)

    return ". ".join(parts) + "."

def get_fvg_timezone():
    if ZoneInfo:
        try:
            return ZoneInfo("Europe/Rome")
        except Exception:
            pass

    return timezone(timedelta(hours=2))

def parse_widget_alert_datetime(value: str) -> tuple[str, str]:
    if not value:
        return "", ""

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        local_dt = parsed.astimezone(get_fvg_timezone())
        label = local_dt.strftime("%d/%m/%Y - %H:%M")
        return local_dt.isoformat(timespec="seconds"), label
    except Exception:
        return str(value), ""

def extract_jsonp_payload(text: str) -> dict:
    match = re.search(r"\((\{.*\})\)\s*;?\s*$", text or "", re.DOTALL)
    if not match:
        raise OfficialAlertsParserError("invalid_jsonp_wrapper")

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise OfficialAlertsParserError("invalid_jsonp_payload") from error

    if not isinstance(payload, dict):
        raise OfficialAlertsParserError("invalid_jsonp_schema")
    return payload

def widget_alert_level(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if not re.fullmatch(r"[0-4]", text):
        return ""
    level = int(text)

    return {
        0: "verde",
        1: "gialla",
        2: "arancione",
        3: "rossa",
        4: "nera",
    }.get(level, "")

def parse_civil_protection_alerts(html: str) -> list[dict]:
    lines = html_to_lines(html)
    pdf_links = [
        urljoin(PROTEZIONE_CIVILE_ALERTS_URL, unescape(match.group(1)))
        for match in re.finditer(r'href=["\']([^"\']+\.pdf)["\']', html or "", re.IGNORECASE)
    ]
    alerts = []

    for index, line in enumerate(lines):
        if not line.upper().startswith("ALLERTA REGIONALE"):
            continue

        block = []
        for next_line in lines[index:index + 18]:
            if next_line.startswith("## ") and next_line != line:
                break
            block.append(next_line)

        valid_from_label = next((item for item in block if item.lower().startswith("da ")), "")
        valid_to_label = next((item for item in block if item.lower().startswith("a ")), "")
        official_text = next((item for item in block if "ALLERTA" in item.upper() and len(item) > 40), "")
        severity = ""
        category = ""

        for item in block:
            lower = item.lower()
            if lower.startswith("critic"):
                severity = item
            elif item in ("Meteorologica", "Idrogeologica", "Idraulica"):
                category = item

        level = extract_alert_level(official_text or line)
        risks = extract_alert_risks(official_text)
        time_window = extract_alert_time_window(official_text)
        area = extract_alert_area(official_text)
        pdf_url = pdf_links[len(alerts)] if len(alerts) < len(pdf_links) else ""

        alerts.append(
            {
                "id": normalize_for_search(line).replace(" ", "-"),
                "title": line,
                "level": level,
                "risks": risks,
                "severity": severity,
                "category": category,
                "area": area,
                "valid_from_label": valid_from_label.removeprefix("da ").strip(),
                "valid_to_label": valid_to_label.removeprefix("a ").strip(),
                "valid_from": parse_civil_protection_datetime(valid_from_label),
                "valid_to": parse_civil_protection_datetime(valid_to_label),
                "time_window": time_window,
                "official_text": official_text,
                "pdf_url": pdf_url,
                "source": PROTEZIONE_CIVILE_ALERTS_SOURCE,
                "push_title": "Meteo Friul",
                "push_body": build_official_alert_push_body(level, risks, time_window, area),
                "push_title_i18n": {"it": "Meteo Friul", "fur": "Meteo Friul"},
                "push_body_i18n": {
                    "it": build_official_alert_push_body(level, risks, time_window, area, "it"),
                    "fur": build_official_alert_push_body(level, risks, time_window, area, "fur"),
                },
            }
        )

    return alerts

def parse_civil_protection_widget_alerts(text: str) -> list[dict]:
    payload = extract_jsonp_payload(text)
    raw_alerts = payload.get("alerts")
    if not isinstance(raw_alerts, list) or not raw_alerts:
        raise OfficialAlertsParserError("invalid_widget_alerts")

    grouped = {}
    for item in raw_alerts:
        if not isinstance(item, dict):
            raise OfficialAlertsParserError("invalid_widget_alert")

        title = str(item.get("title") or "").strip()
        official_text = str(item.get("description") or "").strip()
        if (not title and not official_text) or not widget_alert_level(item.get("level")):
            raise OfficialAlertsParserError("unrecognized_widget_alert")

        key = make_cache_key(title, official_text, item.get("file_url"))
        group = grouped.setdefault(key, {"item": item, "zone_levels": {}})
        zone = str(item.get("zone") or "").strip().upper()
        if zone not in {"FVG-A", "FVG-B", "FVG-C", "FVG-D"}:
            raise OfficialAlertsParserError("invalid_widget_zone")
        if zone in group["zone_levels"]:
            raise OfficialAlertsParserError("duplicate_widget_zone")
        if any(
            item.get(field) != group["item"].get(field)
            for field in ("dt_start", "dt_end", "type")
        ):
            raise OfficialAlertsParserError("inconsistent_widget_alert")
        group["zone_levels"][zone] = widget_alert_level(item.get("level"))

    if not grouped:
        raise OfficialAlertsParserError("unrecognized_widget_alerts")

    alerts = []
    for group in grouped.values():
        item = group["item"]
        zone_levels = group["zone_levels"]
        actionable_levels = {level for level in zone_levels.values() if level != "verde"}
        ranked_levels = [
            value for value in ("nera", "rossa", "arancione", "gialla")
            if value in actionable_levels
        ]
        mixed_levels = len(ranked_levels) > 1
        level = ranked_levels[0] if ranked_levels else "verde"
        zones = sorted(
            zone for zone, zone_level in zone_levels.items()
            if zone_level != "verde" or not actionable_levels
        )
        title = str(item.get("title") or "").strip()
        official_text = str(item.get("description") or "").strip()
        risks = extract_alert_risks(official_text)
        time_window = extract_alert_time_window(official_text)
        # The zone records are authoritative for display and push targeting:
        # free text can also mention the green zones in a mixed alert.
        if set(zones) == {"FVG-A", "FVG-B", "FVG-C", "FVG-D"}:
            area = "Tutta la regione"
        else:
            area = ", ".join(f"zona {zone}" for zone in zones)

        bodies = {}
        for language in ("it", "fur"):
            if mixed_levels:
                # The widget supplies severities per zone, not risks per zone.
                # Do not assign every textual risk to every severity/zone.
                bodies[language] = " ".join(
                    build_official_alert_push_body(
                        value, [], time_window if index == 0 else "",
                        ", ".join(
                            f"zona {zone}" for zone in sorted(zone_levels)
                            if zone_levels[zone] == value
                        ), language,
                    )
                    for index, value in enumerate(ranked_levels)
                )
            else:
                bodies[language] = build_official_alert_push_body(
                    level, risks, time_window, area, language
                )
        # Existing clients use mixed_levels and the official text to avoid
        # attributing the regional maximum to all affected zones.
        if mixed_levels:
            area = ""

        valid_from, valid_from_label = parse_widget_alert_datetime(item.get("dt_start"))
        valid_to, valid_to_label = parse_widget_alert_datetime(item.get("dt_end"))

        alerts.append(
            {
                "id": normalize_for_search(title or official_text).replace(" ", "-"),
                "title": title,
                "level": level,
                "levels": ranked_levels or ["verde"],
                "mixed_levels": mixed_levels,
                "zone_levels": dict(sorted(zone_levels.items())),
                "risks": risks,
                "severity": "",
                "category": "Meteorologica" if str(item.get("type") or "").upper() == "METEO" else str(item.get("type") or ""),
                "area": area,
                "zones": zones,
                "valid_from_label": valid_from_label,
                "valid_to_label": valid_to_label,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "time_window": time_window,
                "official_text": official_text,
                "pdf_url": item.get("file_url") or "",
                "source": PROTEZIONE_CIVILE_ALERTS_SOURCE,
                "source_mode": "official_widget",
                "push_title": "Meteo Friul",
                "push_body": bodies["it"],
                "push_title_i18n": {"it": "Meteo Friul", "fur": "Meteo Friul"},
                "push_body_i18n": bodies,
            }
        )

    return alerts

def is_actionable_official_alert(alert: dict | None) -> bool:
    if not isinstance(alert, dict):
        return False

    return str(alert.get("level") or "").strip().lower() not in ("", "verde")

def actionable_official_alerts(alerts) -> list[dict]:
    if not isinstance(alerts, list):
        return []

    return [alert for alert in alerts if is_actionable_official_alert(alert)]

def build_official_alerts_unavailable_response(reason: str = "direct_fetch_deferred") -> dict:
    return {
        "active": False,
        "count": 0,
        "alerts": [],
        "source": PROTEZIONE_CIVILE_ALERTS_SOURCE,
        "source_mode": "official_alerts_unavailable_fast_fallback",
        "cache": {
            "status": "unavailable",
            "reason": reason,
        },
        "error": "official_alerts_unavailable",
    }

def civil_protection_fvg_headers(mode: str = "html") -> dict:
    headers = {
        "User-Agent": PCFVG_BROWSER_USER_AGENT or HTTP_USER_AGENT,
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    if mode == "widget":
        headers.update(
            {
                "Accept": "application/javascript,text/javascript,application/json,text/plain,*/*;q=0.8",
                "Referer": "https://www.protezionecivile.fvg.it/it/widget-allerta",
            }
        )
    else:
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://www.protezionecivile.fvg.it/",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    return headers

def fetch_civil_protection_alerts_html() -> str:
    last_error = None

    for attempt in range(2):
        try:
            res = requests.get(
                PROTEZIONE_CIVILE_ALERTS_URL,
                headers=civil_protection_fvg_headers("html"),
                timeout=PROTEZIONE_CIVILE_ALERTS_TIMEOUT,
            )
            res.raise_for_status()
            return res.text
        except requests.RequestException as error:
            last_error = error
            if attempt == 0:
                time.sleep(0.5)

    raise last_error or requests.RequestException("Protezione Civile FVG alerts unavailable")

def fetch_civil_protection_widget_alerts_jsonp() -> str:
    response = requests.get(
        PROTEZIONE_CIVILE_ALERTS_WIDGET_URL,
        params={"callback": "pcrfvgit_widget_setup"},
        headers=civil_protection_fvg_headers("widget"),
        timeout=PROTEZIONE_CIVILE_ALERTS_TIMEOUT,
    )
    response.raise_for_status()
    return response.text

def normalize_for_search(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


OFFICIAL_ALERTS_CACHE_TTL_SECONDS = 10 * 60
OFFICIAL_ALERTS_ACTIVE_STALE_TTL_SECONDS = 6 * 60 * 60

_official_alerts_cache: dict | None = None
_official_alerts_cached_at: float | None = None
_official_alerts_lock = threading.Lock()


def _cached_alerts(age_limit: int) -> tuple[dict, int] | None:
    if _official_alerts_cache is None or _official_alerts_cached_at is None:
        return None

    age = max(0, int(time.monotonic() - _official_alerts_cached_at))
    if age > age_limit:
        return None
    return dict(_official_alerts_cache), age


def _active_alert_cache_is_usable(payload: dict) -> bool:
    if not payload.get("active"):
        return False

    now = datetime.now(get_fvg_timezone())
    valid_to_values = []
    for alert in payload.get("alerts") or []:
        value = str((alert or {}).get("valid_to") or "").strip()
        if not value:
            return True
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=get_fvg_timezone())
            valid_to_values.append(parsed)
        except ValueError:
            return True

    return bool(valid_to_values and max(valid_to_values) + timedelta(hours=1) >= now)


def _build_alerts_payload(alerts: list[dict], source_mode: str) -> dict:
    active_alerts = actionable_official_alerts(alerts)
    expires_at = max(
        (
            str(alert.get("valid_to") or "")
            for alert in active_alerts
            if isinstance(alert, dict) and alert.get("valid_to")
        ),
        default="",
    )
    return {
        "active": bool(active_alerts),
        "count": len(active_alerts),
        "alerts": active_alerts,
        "source": PROTEZIONE_CIVILE_ALERTS_SOURCE,
        "source_mode": source_mode,
        "fetched_at": datetime.now(get_fvg_timezone()).isoformat(timespec="seconds"),
        "expires_at": expires_at,
        "cache": {"status": "fresh", "ttl_seconds": OFFICIAL_ALERTS_CACHE_TTL_SECONDS},
    }


def _fetch_confirmed_alerts() -> dict:
    attempts = []
    try:
        widget_payload = fetch_civil_protection_widget_alerts_jsonp()
        return _build_alerts_payload(
            parse_civil_protection_widget_alerts(widget_payload),
            "official_widget",
        )
    except OfficialAlertsParserError:
        attempts.append({"source": "widget", "category": "parser"})
    except requests.RequestException as widget_error:
        attempts.append(_request_failure_attempt("widget", widget_error))

    try:
        html = fetch_civil_protection_alerts_html()
        parsed = parse_civil_protection_alerts(html)
        if parsed:
            if any(
                str((alert or {}).get("level") or "").strip().lower()
                not in {"verde", "gialla", "arancione", "rossa", "nera"}
                for alert in parsed
            ):
                raise OfficialAlertsParserError("unrecognized_html_alert")
            return _build_alerts_payload(parsed, "official_page")
        if html_confirms_no_active_alerts(html):
            return _build_alerts_payload([], "official_page")
        raise OfficialAlertsParserError("unclassified_html_response")
    except OfficialAlertsParserError:
        attempts.append({"source": "html", "category": "parser"})
    except requests.RequestException as page_error:
        attempts.append(_request_failure_attempt("html", page_error))

    raise OfficialAlertsUpstreamError(attempts)


def fetch_official_alerts(*, force: bool = False) -> dict:
    """Return a confirmed FVG alert state without converting failures to no-alert."""

    global _official_alerts_cache, _official_alerts_cached_at

    if not force:
        cached = _cached_alerts(OFFICIAL_ALERTS_CACHE_TTL_SECONDS)
        if cached:
            payload, age = cached
            payload["cache"] = {
                **(payload.get("cache") or {}),
                "status": "fresh",
                "age_seconds": age,
            }
            return payload

    with _official_alerts_lock:
        if not force:
            cached = _cached_alerts(OFFICIAL_ALERTS_CACHE_TTL_SECONDS)
            if cached:
                payload, age = cached
                payload["cache"] = {
                    **(payload.get("cache") or {}),
                    "status": "fresh",
                    "age_seconds": age,
                }
                return payload

        try:
            payload = _fetch_confirmed_alerts()
            _official_alerts_cache = payload
            _official_alerts_cached_at = time.monotonic()
            return dict(payload)
        except requests.RequestException as error:
            upstream_failure = _upstream_failure_diagnostic(error)
            stale = _cached_alerts(OFFICIAL_ALERTS_ACTIVE_STALE_TTL_SECONDS)
            if stale and _active_alert_cache_is_usable(stale[0]):
                payload, age = stale
                payload["cache"] = {
                    **(payload.get("cache") or {}),
                    "status": "stale",
                    "reason": "official_alerts_refresh_failed",
                    "age_seconds": age,
                    "upstream_failure": upstream_failure,
                }
                payload["warning"] = "official_alerts_refresh_failed"
                return payload

            unavailable = build_official_alerts_unavailable_response(
                "official_alerts_refresh_failed"
            )
            unavailable["fetched_at"] = datetime.now(get_fvg_timezone()).isoformat(
                timespec="seconds"
            )
            unavailable["cache"]["upstream_failure"] = upstream_failure
            return unavailable


def clear_official_alerts_cache() -> None:
    global _official_alerts_cache, _official_alerts_cached_at

    with _official_alerts_lock:
        _official_alerts_cache = None
        _official_alerts_cached_at = None


def reset_official_alerts_cache_for_tests() -> None:
    clear_official_alerts_cache()
