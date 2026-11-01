"""Bounded, read-only collectors for already censused market sources.

Only explicit single-day JSON-LD Events, Pro Sacile's delimited calendar and
Pro Loco FVG's labelled event details are interpreted. Missing fields, ranges and unsupported documents never imply
deletion, closure, a weekly rule or an extended validity period.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit


MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_SOURCES = 4
SOURCE_DEADLINE_SECONDS = 20
MONTHS = {name: number for number, name in enumerate(
    ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
     "agosto", "settembre", "ottobre", "novembre", "dicembre"), 1)}


class SourceError(ValueError):
    pass


def _normal(value):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", str(value)).encode(
        "ascii", "ignore").decode().casefold()).strip()


def _url(value):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
        raise SourceError("unsafe_source_url")
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
        if (parsed.scheme != "https" or parsed.username or parsed.password or
                parsed.port not in (None, 443) or not host or "." not in host or
                host.endswith((".localhost", ".local", ".internal"))):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
        return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))
    except (ValueError, UnicodeError) as error:
        raise SourceError("unsafe_source_url") from error


def _public_addresses(host):
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(
        host, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(item).is_global for item in addresses):
        raise SourceError("unsafe_source_address")
    return addresses


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect only to the validated IP; TLS still validates the original host."""
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.public_address = address

    def connect(self):
        raw = socket.create_connection((self.public_address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def fetch_source(url):
    """HTTPS, no proxy/cookies/auth, validated pinned DNS, same-host redirects."""
    target = _url(url)
    original_host = urlsplit(target).hostname
    deadline = time.monotonic() + SOURCE_DEADLINE_SECONDS
    for _ in range(3):
        parsed = urlsplit(target)
        address = _public_addresses(parsed.hostname)[0]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SourceError("source_timeout")
        connection = _PinnedHTTPSConnection(parsed.hostname, address, min(8, remaining))
        try:
            connection.request("GET", urlunsplit(("", "", parsed.path, parsed.query, "")), headers={
                "User-Agent": "MeteoFriul-Mercati/1.0 (+https://meteofriul.it)",
                "Accept": "text/html, application/xhtml+xml", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = _url(urljoin(target, response.getheader("Location", "")))
                if urlsplit(target).hostname != original_host:
                    raise SourceError("cross_host_redirect")
                continue
            if response.status != 200:
                raise SourceError("source_http_" + str(response.status))
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].lower()
            if content_type not in ("text/html", "application/xhtml+xml"):
                raise SourceError("unsupported_source_format")
            if response.getheader("Content-Encoding", "identity").lower() not in ("identity", ""):
                raise SourceError("unsupported_source_encoding")
            size = response.getheader("Content-Length", "")
            if size.isdigit() and int(size) > MAX_SOURCE_BYTES:
                raise SourceError("source_too_large")
            chunks, total = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise SourceError("source_timeout")
                # read1 returns after a single socket read, so slow trickle
                # traffic cannot defer the wall-clock check until 32 KiB arrive.
                chunk = response.read1(32768)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SOURCE_BYTES:
                    raise SourceError("source_too_large")
                chunks.append(chunk)
            body = b"".join(chunks)
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                html = body.decode(charset, errors="replace")
            except LookupError:
                html = body.decode("utf-8", errors="replace")
            return {"url": target, "html": html, "contentHash": hashlib.sha256(body).hexdigest(),
                    "retrievedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        finally:
            connection.close()
    raise SourceError("source_redirect_limit")


class _Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.scripts, self.text, self.script = [], [], None
        self.hidden = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
            if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
                self.script = []
        if tag in ("p", "li", "br", "div", "h1", "h2", "h3", "section") and not self.hidden:
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
        if tag in ("p", "li", "div", "h1", "h2", "h3", "section") and not self.hidden:
            self.text.append("\n")

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        elif not self.hidden:
            self.text.append(data)

    @property
    def lines(self):
        return [re.sub(r"\s+", " ", item).strip() for item in "".join(self.text).splitlines()
                if item.strip()]


def _objects(value, depth=0):
    if depth > 12:
        return
    if isinstance(value, dict):
        yield value
        for key in ("@graph", "subEvent", "subEvents", "itemListElement", "item"):
            yield from _objects(value.get(key), depth + 1)
    elif isinstance(value, list):
        for item in value[:500]:
            yield from _objects(item, depth + 1)


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", value):
        raise SourceError("invalid_source_date")
    try:
        if "T" in value:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError as error:
        raise SourceError("invalid_source_date") from error


def _types(item):
    raw = item.get("@type", [])
    return [value.rsplit("/", 1)[-1] for value in ([raw] if isinstance(raw, str) else raw)
            if isinstance(value, str)] if isinstance(raw, (str, list)) else []


def _event_matches(item, market, url):
    location = item.get("location")
    if not isinstance(location, dict):
        return False
    address = location.get("address")
    if not isinstance(address, dict) or _normal(address.get("addressLocality", "")) != _normal(market.get("comune", "")):
        return False
    names = [market.get("name", ""), *market.get("titleAliases", [])]
    actual = set(_normal(item.get("name", "")).split())
    if not actual or not any((tokens := set(_normal(name).split())) and
                             (tokens == actual or (len(tokens) >= 3 and tokens.issubset(actual))) for name in names):
        return False
    event_url = item.get("url")
    if event_url:
        try:
            if _url(event_url).rstrip("/") != _url(url).rstrip("/"):
                return False
        except SourceError:
            return False
    return True


def _jsonld(page, market, url, as_of):
    matches, issues = [], []
    for script in page.scripts[:50]:
        try:
            objects = _objects(json.loads(script))
            matches.extend(item for item in objects if any(kind.endswith("Event") for kind in _types(item))
                           and _event_matches(item, market, url))
        except (ValueError, RecursionError):
            issues.append("invalid_structured_data")
    # Duplicate graph references are common; contradictory references are not.
    unique = {json.dumps(item, sort_keys=True, ensure_ascii=False): item for item in matches}
    matches = list(unique.values())
    if not matches:
        return [], issues
    if len(matches) > 100:
        return [], issues + ["ambiguous_event_identity"]
    result = []
    for item in matches:
        try:
            start = _day(item.get("startDate"))
            end = _day(item.get("endDate", start))
            if start != end:
                issues.append("multi_day_event_requires_explicit_editions")
                continue
            if date.fromisoformat(start) < as_of:
                issues.append("historical_source_calendar")
                continue
            status_raw = str(item.get("eventStatus", "EventScheduled")).rsplit("/", 1)[-1]
            statuses = {"EventScheduled": "published", "EventCancelled": "cancelled",
                        "EventPostponed": "postponed", "EventRescheduled": "published"}
            if status_raw not in statuses:
                issues.append("unsupported_event_status")
                continue
            edition = {"date": start, "status": statuses[status_raw], "source": url}
            event_id = item.get("@id")
            if isinstance(event_id, str) and event_id:
                edition["sourceKey"] = event_id[:500]
            elif len(matches) == 1:
                edition["sourceKey"] = url
            # No array-order identifier: absent IDs use date matching in merge.
            if item.get("previousStartDate"):
                edition["previousDate"] = _day(item["previousStartDate"])
            elif status_raw == "EventRescheduled":
                issues.append("reschedule_without_previous_date")
                continue
            location = item["location"]
            address = location["address"]
            place = ", ".join(dict.fromkeys(value.strip() for value in
                                           (location.get("name"), address.get("streetAddress"))
                                           if isinstance(value, str) and value.strip()))
            evidence = [{"field": "editions", "value": edition, "excerpt": json.dumps({key: item[key] for key in
                         ("name", "startDate", "endDate", "eventStatus", "previousStartDate", "location")
                         if key in item}, ensure_ascii=False)[:1800]}]
            if place:
                edition["venue"] = {"id": "source-venue-" + hashlib.sha256(
                    (url + "|" + place).encode()).hexdigest()[:20], "place": place,
                    "directionsQuery": place + ", " + market["comune"]}
            if isinstance(item.get("description"), str) and item["description"].strip():
                evidence.append({"field": "calendarConsiderations", "value": item["description"][:1800],
                                 "excerpt": item["description"][:1800]})
            observation = {"fields": {}, "editions": [edition], "evidence": evidence,
                           "completeCalendar": False}
            if item.get("dateModified"):
                modified = _day(item["dateModified"])
                if modified > as_of.isoformat():
                    issues.append("future_source_update_date")
                    continue
                observation["sourceUpdatedAt"] = modified
            result.append(observation)
        except (SourceError, TypeError, KeyError, ValueError):
            issues.append("invalid_structured_event")
    # A stable key cannot identify two different editions in the same response.
    keys = [entry["editions"][0].get("sourceKey") for entry in result]
    if any(key and keys.count(key) > 1 for key in keys):
        return [], issues + ["ambiguous_event_identity"]
    if not result:
        return [], issues
    combined = {"fields": {}, "editions": [edition for entry in result for edition in entry["editions"]],
                "evidence": [proof for entry in result for proof in entry["evidence"]], "completeCalendar": False}
    updates = [entry["sourceUpdatedAt"] for entry in result if entry.get("sourceUpdatedAt")]
    if updates:
        # A newer event in the same page must not make an older one look fresh.
        combined["sourceUpdatedAt"] = min(updates)
    return [combined], issues


def _prosacile(page, market, url, as_of):
    if (urlsplit(url).hostname not in ("www.prosacile.it", "prosacile.it") or
            urlsplit(url).path.rstrip("/") != "/antiquariato" or
            _normal(market.get("comune")) != "sacile" or
            "sacellum" not in _normal(market.get("name"))):
        return [], []
    lines = page.lines
    start = next((i for i, line in enumerate(lines) if "nelle seguenti date" in line.casefold()
                  and "mercatino" in line.casefold()), None)
    if start is None:
        return [], ["calendar_section_not_found"]
    editions, evidence, issues, notes = [], [], [], []
    # Only the list directly following the explicitly labelled calendar.
    for line in lines[start + 1:start + 35]:
        if "disponibile per la consultazione" in line.casefold() or "regolamento" in line.casefold():
            break
        normalized = re.sub(r"dic\s+embre", "dicembre", line.casefold())
        match = re.fullmatch(r"[-–•]?\s*(\d{1,2})\s+(" + "|".join(MONTHS) +
                             r")\s+(20\d{2})\s*((?:\(\*{1,2}\)\s*)*)", normalized)
        if match:
            try:
                day = date(int(match[3]), MONTHS[match[2]], int(match[1]))
            except ValueError:
                issues.append("invalid_calendar_date")
                continue
            if day.year < as_of.year:
                issues.append("historical_source_calendar")
                continue
            # The double asterisk explicitly says the date may change.
            if "(**)" in match[4]:
                issues.append("provisional_calendar_date")
                notes.append(line)
                continue
            edition = {"date": day.isoformat(), "status": "published", "source": url}
            editions.append(edition)
            evidence.append({"field": "editions", "value": edition, "excerpt": line[:500]})
        elif "si avverte" in normalized or "potrebbe" in normalized or "modifiche" in normalized:
            notes.append(line)
    if notes:
        evidence.append({"field": "calendarConsiderations", "value": notes,
                         "excerpt": " ".join(notes)[:1800]})
    if not editions:
        return [], issues + ["no_supported_calendar_dates"]
    return [{"fields": {}, "editions": editions, "evidence": evidence,
             "completeCalendar": False}], issues


class _ProlocoDetails(HTMLParser):
    """Collect labelled list items and the event title, never page-wide dates."""
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.groups, self.stack, self.titles = [], [], []
        self.title = None
        self.title_tag = None
        self.hidden = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if self.hidden:
            return
        if tag == "ul":
            self.stack.append({"items": [], "current": None})
        elif tag == "li" and self.stack:
            self.stack[-1]["current"] = []
        elif tag == "br" and self.stack and self.stack[-1]["current"] is not None:
            self.stack[-1]["current"].append(", ")
        if tag in ("h1", "h2") and "event-title" in attributes.get("class", "").split():
            self.title, self.title_tag = [], tag

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
        if self.hidden:
            return
        if tag == self.title_tag:
            self.titles.append(re.sub(r"\s+", " ", "".join(self.title)).strip())
            self.title, self.title_tag = None, None
        if tag == "li" and self.stack and self.stack[-1]["current"] is not None:
            self.stack[-1]["items"].append(re.sub(r"\s+", " ", "".join(self.stack[-1]["current"])).strip())
            self.stack[-1]["current"] = None
        elif tag == "ul" and self.stack:
            self.groups.append(self.stack.pop()["items"])

    def handle_data(self, data):
        if self.hidden:
            return
        if self.stack and self.stack[-1]["current"] is not None:
            self.stack[-1]["current"].append(data)
        if self.title is not None:
            self.title.append(data)


def _proloco(html, market, url, as_of):
    if (urlsplit(url).hostname not in ("prolocoregionefvg.it", "www.prolocoregionefvg.it") or
            not urlsplit(url).path.startswith("/eventi-delle-associate/")):
        return [], []
    details = _ProlocoDetails(html)
    labelled = {}
    for group in details.groups:
        if group and _normal(group[0]) in ("citta", "indirizzo", "quando", "orari"):
            key = _normal(group[0])
            if key in labelled:
                return [], ["ambiguous_event_identity"]
            labelled[key] = [value for value in group[1:] if value]
    if len(details.titles) != 1 or len(labelled.get("citta", [])) != 1:
        return [], ["event_identity_not_verified"]
    actual = set(_normal(details.titles[0]).split())
    names = [market.get("name", ""), *market.get("titleAliases", [])]
    if (_normal(labelled["citta"][0]) != _normal(market.get("comune", "")) or
            not any((tokens := set(_normal(name).split())) and (tokens == actual or
                    (len(tokens) >= 3 and tokens.issubset(actual))) for name in names)):
        return [], ["event_identity_not_verified"]
    if not labelled.get("quando"):
        return [], ["calendar_section_not_found"]
    editions, evidence, issues = [], [], []
    for text in labelled["quando"][:400]:
        match = re.fullmatch(r"(\d{2})/(\d{2})/(20\d{2})", text)
        if not match:
            issues.append("calendar_entry_requires_explicit_date")
            evidence.append({"field": "calendarConsiderations", "value": text,
                             "excerpt": "Quando: " + text[:1600]})
            continue
        try:
            day = date(int(match[3]), int(match[2]), int(match[1]))
        except ValueError:
            issues.append("invalid_calendar_date")
            continue
        if day < as_of:
            continue
        edition = {"date": day.isoformat(), "status": "published", "source": url}
        if any(entry["date"] == edition["date"] for entry in editions):
            continue
        editions.append(edition)
        evidence.append({"field": "editions", "value": edition,
                         "excerpt": details.titles[0] + " — " + labelled["citta"][0] + "; Quando: " + text})
    if not editions:
        return [], issues + ["no_supported_calendar_dates"]
    fields = {}
    # Address is inside the identified event's labelled metadata, not the
    # association's footer/contact block. It applies to the listed editions.
    if len(labelled.get("indirizzo", [])) == 1:
        place = labelled["indirizzo"][0]
        if len(place) <= 1000:
            fields["place"] = place
            fields["directionsQuery"] = place + ", " + market["comune"]
            for field, value in fields.items():
                evidence.append({"field": field, "value": value,
                                 "excerpt": "Città: " + labelled["citta"][0] + "; Indirizzo: " + place})
            for edition in editions:
                edition["venue"] = {"id": "source-venue-" + hashlib.sha256((url + "|" + place).encode()).hexdigest()[:20],
                                    "place": place, "directionsQuery": fields["directionsQuery"]}
    if len(labelled.get("orari", [])) == 1:
        hours = labelled["orari"][0]
        if re.fullmatch(r"(?:dalle\s+)?\d{1,2}[.:]\d{2}\s*(?:-|–|alle)\s*\d{1,2}[.:]\d{2}", hours, re.I):
            fields["hours"] = hours
            evidence.append({"field": "hours", "value": hours, "excerpt": "Orari: " + hours})
    # The maximum explicitly listed date supports this horizon, not an
    # invented annual extension. Do not shorten other documented validity.
    horizon = max(entry["date"] for entry in editions)
    if horizon > (market.get("validThrough") or ""):
        fields["validThrough"] = horizon
        evidence.append({"field": "validThrough", "value": horizon,
                         "excerpt": "Quando: " + ", ".join(labelled["quando"])[:1600]})
    return [{"fields": fields, "editions": editions, "evidence": evidence,
             "completeCalendar": False}], issues


def collect_market(market, editions, sources, *, as_of, fetch=None):
    """Collect supported facts without mutating any record or publishing data.

    ``fetch(url)`` may inject a HTML string or a dict with html/url/retrievedAt/
    contentHash for fixture tests. The real transport never follows links to
    other hosts. Issue strings are stable codes; they contain no source body.
    """
    as_of = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    urls, issues, observations = [], [], []
    candidates = [market.get("url"), *[item.get("url") for item in sources if isinstance(item, dict)],
                  *[item.get("source") for item in editions if isinstance(item, dict)]]
    for value in candidates:
        if not value:
            continue
        try:
            normalized = _url(value)
            if normalized not in urls:
                urls.append(normalized)
        except SourceError as error:
            issues.append(str(error))
    if len(urls) > MAX_SOURCES:
        issues.append("source_limit_reached")
    if not urls:
        issues.append("source_missing")
    for url in urls[:MAX_SOURCES]:
        try:
            response = (fetch or fetch_source)(url)
            if isinstance(response, str):
                response = {"html": response, "url": url}
            html = response["html"]
            if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_SOURCE_BYTES:
                raise SourceError("source_too_large")
            final_url = _url(response.get("url", url))
            if urlsplit(final_url).hostname != urlsplit(url).hostname:
                raise SourceError("cross_host_redirect")
            page = _Page(html)
            found, parse_issues = _prosacile(page, market, final_url, as_of)
            if not found:
                found, proloco_issues = _proloco(html, market, final_url, as_of)
                parse_issues += proloco_issues
            if not found:
                found, structured_issues = _jsonld(page, market, final_url, as_of)
                parse_issues += structured_issues
            issues.extend(parse_issues)
            if not found:
                issues.append("source_format_not_supported")
            for observation in found:
                observations.append({"sourceUrl": final_url,
                    "retrievedAt": response.get("retrievedAt") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "contentHash": response.get("contentHash") or hashlib.sha256(html.encode()).hexdigest(),
                    **observation})
        except SourceError as error:
            issues.append(str(error))
        except (OSError, TimeoutError, http.client.HTTPException):
            issues.append("source_unavailable")
        except (ValueError, TypeError, KeyError, RecursionError):
            issues.append("source_parse_error")
    return {"marketId": market["id"], "observations": observations, "issues": sorted(set(issues))}
