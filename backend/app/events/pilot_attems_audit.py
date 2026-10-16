"""Read-only coverage audit for the public Palazzo Attems inventories.

This tool deliberately does not publish events or inspect poster/PDF contents.
It exits nonzero while a current event has no textual venue or programme.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import html
import json
import re
from time import sleep

import requests


BASE = "https://palazzoattems.regione.fvg.it"
CORE = BASE + "/core/"
SITE = "erpac_palazzoattems"
MAX_BYTES = 2 * 1024 * 1024
MONTHS = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
          "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
          "novembre": 11, "dicembre": 12}
REVIEWED_NEWS_2026 = {
    # The 15 October Mister Fantasy listing is represented by TurismoFVG's
    # verified October programme (505824); Attems omits a textual venue.
    233853: '2026-10-09T12:03:31',
    # News 233783 (library consultation hours, not an event) was removed from
    # the official inventory on 2026-10-08; reappearance must trigger review.
    233740: '2026-10-07T11:51:35', 233617: '2026-10-05T10:59:54',
    233571: '2026-10-06T16:48:10', 233609: '2026-10-05T09:43:00',
    233408: '2026-09-30T10:57:00', 232612: '2026-09-30T10:44:34',
    232806: '2026-09-17T13:02:39', 233570: '2026-10-02T12:26:06',
    232691: '2026-09-16T11:40:50', 232689: '2026-09-16T11:45:56',
    232601: '2026-09-15T10:53:20', 232556: '2026-09-18T13:54:37',
    232271: '2026-09-07T13:03:27', 232514: '2026-09-17T12:47:46',
    232356: '2026-09-08T14:16:47', 232100: '2026-09-04T10:45:16',
    231399: '2026-08-27T14:16:47', 231297: '2026-08-11T13:40:15',
    231255: '2026-08-10T14:15:28', 231154: '2026-08-06T13:26:37',
    231001: '2026-08-04T09:40:38', 230759: '2026-07-29T13:46:01',
    230295: '2026-07-27T12:30:55', 230382: '2026-07-20T15:02:29',
    229925: '2026-07-09T08:53:48', 230065: '2026-07-13T12:23:07',
    230064: '2026-07-14T16:21:06', 230294: '2026-07-14T16:21:06',
    229755: '2026-07-08T13:41:02', 229630: '2026-07-06T09:33:03',
    229656: '2026-07-02T14:06:26', 229541: '2026-06-30T13:47:38',
    229437: '2026-06-29T13:00:57', 229456: '2026-06-29T14:48:14',
    223997: '2026-03-19T10:20:14', 223863: '2026-03-14T11:15:22',
    223606: '2026-03-14T11:16:10', 223483: '2026-03-06T16:34:19',
    223240: '2026-03-03T11:31:57', 221578: '2026-02-26T13:32:11',
    222940: '2026-02-26T13:50:13',
}
REVIEWED_HISTORICAL_NEWS_UPDATES = {217906: '2026-02-26T13:34:33'}
REVIEWED_EVENT_IDS = {
    285626, 611426, 611429, 611592, 612069, 612475, 612620,
    613103, 613290, 613403, 613664, 614015, 614165, 614281,
    614488, 616043, 616168, 616382, 616807, 616864, 617270,
    617278, 617444, 618493, 618818, 618887, 618899, 619247,
}
REVIEWED_DETAIL_VERSIONS = {
    174560: '2026-10-09T12:04:24',
    174333: '2026-10-05T11:00:50',
    174290: '2026-10-06T16:49:03',
    173302: '2026-10-07T14:45:49',
    165450: '2026-10-06T16:48:51',
    174454: '2026-10-07T11:52:31',
    174327: '2026-10-05T09:43:57',
}
REVIEWED_EXHIBITION_PATHS = {'/it/italia-settanta-165450'}


def _fetch(url: str) -> bytes:
    if not url.startswith(BASE + "/"):
        raise ValueError("untrusted Palazzo Attems URL")
    for attempt in range(3):
        with requests.get(url, timeout=(3, 12), stream=True, allow_redirects=False) as response:
            if response.status_code not in {502, 503, 504} or attempt == 2:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError("unexpected Palazzo Attems response")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("oversized Palazzo Attems response")
                    chunks.append(chunk)
                return b"".join(chunks)
        sleep(2 * (attempt + 1))
    raise AssertionError("unreachable Palazzo Attems retry state")


def _page_id(path: str) -> int:
    match = re.fullmatch(r"/(?:it/)?[a-z0-9-]+-(\d+)", path or "")
    if not match:
        raise ValueError("unexpected Palazzo Attems detail path")
    return int(match.group(1))


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value or ""))).strip()


def _text_date(value: str, year: int) -> date | None:
    match = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\b",
                      _plain(value).casefold())
    if not match:
        return None
    try:
        return date(year, MONTHS[match.group(2)], int(match.group(1)))
    except ValueError:
        return None


def _rows(payload: dict, label: str) -> list[dict]:
    rows = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid Palazzo Attems " + label + " inventory")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(item, int) for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("invalid Palazzo Attems " + label + " ids")
    return rows


def audit_payloads(*, events: dict, event_category: dict, news: dict,
                   exhibitions: dict, concluded: dict, homepage: str,
                   event_list: str, details: dict[int, dict], today: date,
                   reviewed_news: dict[int, str] = REVIEWED_NEWS_2026) -> dict:
    """Reconcile the current inventories; return blockers rather than guess data."""
    event_rows = _rows(events, "events")
    category_rows = _rows(event_category, "event category")
    news_rows = _rows(news, "news")
    exhibition_rows = _rows(exhibitions, "exhibition category")
    concluded_rows = _rows(concluded, "concluded exhibitions")
    if (event_category.get("id") != 15308 or news.get("id") != 15309
            or exhibitions.get("id") != 13463 or concluded.get("id") != 14035):
        raise ValueError("Palazzo Attems category identity changed")
    if any(str(row.get("published_date", ""))[:4] >= str(today.year) or
           str(row.get("modified", ""))[:4] >= str(today.year)
           for row in exhibition_rows):
        raise ValueError("Palazzo Attems exhibition category has unreviewed current content")

    listed_count = re.search(r"<strong>\s*\d+\s*</strong>\s*di\s*<strong>\s*(\d+)\s*</strong>\s*risultati", event_list)
    if not listed_count or int(listed_count.group(1)) != len(event_rows):
        raise ValueError("Palazzo Attems Eventi list/API count mismatch")
    event_paths = {row.get("full_url") for row in event_rows}
    category_only = [row for row in category_rows if row.get("full_url") not in event_paths]
    if any(str(row.get("published_date", ""))[:4] >= str(today.year) or
           str(row.get("modified", ""))[:4] >= str(today.year)
           for row in category_only):
        raise ValueError("Palazzo Attems current category event missing from API")

    active, undated = [], []
    for row in event_rows:
        end = str(row.get("end_event_date") or "")[:10]
        if not end:
            undated.append(row)
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
            raise ValueError("Palazzo Attems event without end date")
        if date.fromisoformat(end) >= today:
            active.append(row)

    exhibition_paths = set(re.findall(
        r'href="(/it/[a-z0-9-]+-\d+)"[^>]*>\s*vai alla mostra\s*</a>',
        homepage, re.IGNORECASE))
    if not exhibition_paths:
        raise ValueError("Palazzo Attems current exhibition inventory missing")
    if {path.removeprefix("/it") for path in exhibition_paths} & {
            row.get("full_url") for row in concluded_rows}:
        raise ValueError("Palazzo Attems current/concluded exhibition conflict")

    blockers, verified, past_undated = [], [], []
    for row in undated:
        page = details.get(_page_id(row.get("full_url")))
        attribute = page.get("attribute") if isinstance(page, dict) else None
        if not isinstance(attribute, dict) or attribute.get("full_url") != row.get("full_url"):
            raise ValueError("Palazzo Attems undated detail missing")
        text = " ".join(str(attribute.get(key) or "") for key in
                        ("title", "intro", "description"))
        published = str(attribute.get("published_date") or "")
        try:
            dated = _text_date(text, int(published[:4]))
        except ValueError:
            dated = None
        item = {"title": _plain(attribute.get("title")),
                "url": BASE + "/it" + row["full_url"]}
        if dated and dated < today and published[:4] == str(today.year):
            past_undated.append({**item, "text_date": dated.isoformat()})
        else:
            blockers.append({**item, "reasons": ["undated_event_requires_review"]})
    for row in active:
        end = str(row.get("end_event_date"))[:10]
        page_id = _page_id(row.get("full_url"))
        page = details.get(page_id)
        attribute = page.get("attribute") if isinstance(page, dict) else None
        modules = page.get("modules") if isinstance(page, dict) else None
        if (not isinstance(attribute, dict) or attribute.get("full_url") != row.get("full_url")
                or attribute.get("published") is not True or not isinstance(modules, list)):
            raise ValueError("Palazzo Attems active event detail mismatch")
        if (attribute.get("start_event_date_formatted", "")[:10] != str(row.get("start_event_date"))[:10]
                or attribute.get("end_event_date_formatted", "")[:10] != str(row.get("end_event_date"))[:10]):
            raise ValueError("Palazzo Attems event dates disagree")
        event_modules = [module for module in modules if module.get("module_type") == "event"]
        if len(event_modules) != 1:
            raise ValueError("Palazzo Attems event module missing")
        module = event_modules[0]
        if (str(module.get("start_event_date"))[:10] != str(row.get("start_event_date"))[:10]
                or str(module.get("end_event_date"))[:10] != end):
            raise ValueError("Palazzo Attems event module dates disagree")
        title = _plain(attribute.get("title"))
        url = BASE + "/it" + row["full_url"]
        text = _plain(" ".join(str(value or "") for value in (
            module.get("intro"), module.get("description"), attribute.get("intro"))))
        reason = []
        multi_site = "Spazzapan" in text or "Spazzapan" in _plain(attribute.get("description"))
        structured_venue = _plain(row.get("event_location") or module.get("event_location"))
        if multi_site:
            reason.append("multi_site_without_text_schedule")
        elif ("Palazzo Attems Petzenstein" not in text and
              "Palazzo Attems Petzenstein" not in structured_venue):
            reason.append("venue_not_in_event_text")
        description = _plain(module.get("description"))
        if multi_site and not description and "<img" in str(module.get("description") or ""):
            reason.append("programme_image_only")
        attribute_description = _plain(attribute.get("description"))
        if (attribute_description and "25 settembre" in attribute_description
                and "8 ottobre" in text):
            reason.append("conflicting_reused_description")
        item = {"title": title, "url": url,
                "start_date": str(row.get("start_event_date"))[:10], "end_date": end}
        if reason:
            blockers.append({**item, "reasons": sorted(set(reason))})
        else:
            verified.append(item)

    for path in exhibition_paths:
        page = details.get(_page_id(path))
        attribute = page.get("attribute") if isinstance(page, dict) else None
        modules = page.get("modules") if isinstance(page, dict) else None
        if (not isinstance(attribute, dict) or attribute.get("published") is not True
                or attribute.get("full_url") != path.removeprefix("/it")
                or not isinstance(modules, list)):
            raise ValueError("Palazzo Attems current exhibition detail missing")
        local_modules = [module for module in modules if
                         "Palazzo Attems Petzenstein" in _plain(module.get("description"))
                         and "Gorizia" in _plain(module.get("description"))]
        dated = []
        for module in local_modules:
            match = re.search(
                r"\b(?:dal\s+)?(\d{1,2})\s+(" + "|".join(MONTHS) +
                r")\s+al\s+(\d{1,2})\s+(" + "|".join(MONTHS) +
                r")\s+(20\d{2})\b", _plain(module.get("description")).casefold())
            if match:
                try:
                    start = date(int(match.group(5)), MONTHS[match.group(2)], int(match.group(1)))
                    end = date(int(match.group(5)), MONTHS[match.group(4)], int(match.group(3)))
                    if start <= today <= end:
                        dated.append((start, end))
                except ValueError:
                    pass
        if len(dated) != 1:
            blockers.append({"url": BASE + path, "reasons": ["exhibition_date_or_venue_missing"]})
        else:
            verified.append({"title": _plain(attribute.get("title")), "url": BASE + path,
                             "kind": "exhibition", "start_date": dated[0][0].isoformat(),
                             "end_date": dated[0][1].isoformat()})

    current_news = [row for row in news_rows if
                    str(row.get("published_date", ""))[:4] == str(today.year)]
    historical_updates = [row for row in news_rows if
                          str(row.get("published_date", ""))[:4] < str(today.year)
                          and str(row.get("modified", ""))[:4] >= str(today.year)]
    changed_historical = sorted(row['id'] for row in historical_updates if
                                REVIEWED_HISTORICAL_NEWS_UPDATES.get(row['id']) !=
                                row.get('modified'))
    if changed_historical:
        blockers.append({"reasons": ["unreviewed_historical_news_update"],
                         "article_ids": changed_historical})
    news_versions = {row['id']: row.get('modified') for row in current_news}
    changed_news = sorted((set(news_versions) ^ set(reviewed_news)) |
                          {article_id for article_id in news_versions.keys() & reviewed_news.keys()
                           if news_versions[article_id] != reviewed_news[article_id]})
    if changed_news:
        blockers.append({"reasons": ["unreviewed_current_year_news"],
                         "article_ids": changed_news})
    recent_news = [row for row in current_news if
                   str(row.get("published_date", ""))[:10] >=
                   date(today.year, max(1, today.month - 1), 1).isoformat()]
    cancellations = []
    for row in recent_news:
        if not re.search(r"annullat|cancellat", _plain(row.get("title")) + " " +
                         _plain(row.get("intro")), re.IGNORECASE):
            continue
        path = row["full_url"]
        page = details.get(_page_id(path))
        attribute = page.get("attribute") if isinstance(page, dict) else None
        if not isinstance(attribute, dict) or attribute.get("full_url") != path:
            raise ValueError("Palazzo Attems cancellation detail missing")
        year = int(str(attribute.get("published_date"))[:4])
        dated = _text_date(attribute.get("description"), year)
        item = {"title": _plain(row.get("title")), "url": BASE + "/it" + path,
                "intro": _plain(row.get("intro")),
                "event_date": dated.isoformat() if dated else None}
        cancellations.append(item)
        if dated is None or dated >= today:
            blockers.append({"url": item["url"],
                             "reasons": ["cancellation_requires_reconciliation"]})
    return {"source": "Palazzo Attems Petzenstein", "as_of": today.isoformat(),
            "source_complete": not blockers, "event_api_count": len(event_rows),
            "event_api_ids": sorted(row['id'] for row in event_rows),
            "event_list_count": int(listed_count.group(1)),
            "event_category_count": len(category_rows), "active_event_count": len(active),
            "historical_category_only_count": len(category_only),
            "past_undated_events": past_undated,
            "current_exhibition_count": len(exhibition_paths),
            "current_exhibition_paths": sorted(exhibition_paths),
            "historical_exhibition_category_count": len(exhibition_rows),
            "concluded_exhibition_count": len(concluded_rows),
            "news_count": len(news_rows), "current_year_news_count": len(current_news),
            "reviewed_historical_news_updates": len(historical_updates) - len(changed_historical),
            "reviewed_current_year_news_count": sum(
                news_versions.get(article_id) == modified
                for article_id, modified in reviewed_news.items()),
            "verified": verified, "blockers": blockers, "recent_cancellations": cancellations,
            "detail_versions": {str(page_id): page.get('attribute', {}).get('modified')
                                for page_id, page in details.items()}}


def watch_changes(report: dict) -> list[str]:
    """Alert on newly published or changed material without re-reporting known gaps."""
    changed = []
    if report.get('source_complete') is True:
        changed.append('source_ready_for_integration_review')
    if str(report.get('as_of', ''))[:4] != '2026':
        changed.append('edition_requires_review')
    if set(report.get('event_api_ids') or []) != REVIEWED_EVENT_IDS:
        changed.append('event_inventory_changed')
    if set(report.get('current_exhibition_paths') or []) != REVIEWED_EXHIBITION_PATHS:
        changed.append('exhibition_inventory_changed')
    versions = report.get('detail_versions') or {}
    for page_id, expected in REVIEWED_DETAIL_VERSIONS.items():
        if str(page_id) in versions and versions[str(page_id)] != expected:
            changed.append('detail_changed:' + str(page_id))
    for blocker in report.get('blockers') or []:
        if set(blocker.get('reasons') or []) & {
                'unreviewed_current_year_news',
                'unreviewed_historical_news_update',
                'undated_event_requires_review',
                'exhibition_date_or_venue_missing'}:
            changed.append('new_review_required')
            break
    return sorted(set(changed))


def collect_audit(today: date) -> dict:
    urls = {
        "events": CORE + f"events/{SITE}/it/",
        "event_category": CORE + f"categories/{SITE}/it/15308/",
        "news": CORE + f"categories/{SITE}/it/15309/",
        "exhibitions": CORE + f"categories/{SITE}/it/13463/",
        "concluded": CORE + f"categories/{SITE}/it/14035/",
        "homepage": BASE + "/it/?_escaped_fragment_=",
        "event_list": BASE + "/it/events?_escaped_fragment_=",
    }
    with ThreadPoolExecutor(max_workers=6) as pool:
        raw = dict(zip(urls, pool.map(_fetch, urls.values())))
    payloads = {key: json.loads(raw[key]) for key in
                ("events", "event_category", "news", "exhibitions", "concluded")}
    homepage = raw["homepage"].decode("utf-8", errors="replace")
    event_list = raw["event_list"].decode("utf-8", errors="replace")
    event_rows = _rows(payloads["events"], "events")
    paths = {row["full_url"] for row in event_rows if
             not row.get("end_event_date") or
             date.fromisoformat(str(row.get("end_event_date"))[:10]) >= today}
    news_rows = _rows(payloads["news"], "news")
    paths.update(row["full_url"] for row in news_rows if
                 str(row.get("published_date", ""))[:4] == str(today.year) and
                 re.search(r"annullat|cancellat", _plain(row.get("title")) + " " +
                           _plain(row.get("intro")), re.IGNORECASE))
    paths.update(re.findall(
        r'href="(/it/[a-z0-9-]+-\d+)"[^>]*>\s*vai alla mostra\s*</a>',
        homepage, re.IGNORECASE))
    detail_urls = {path: CORE + f"page/{SITE}/{_page_id(path)}/it/" for path in paths}
    with ThreadPoolExecutor(max_workers=6) as pool:
        details = {_page_id(path): json.loads(body) for path, body in
                   zip(detail_urls, pool.map(_fetch, detail_urls.values()))}
    return audit_payloads(**payloads, homepage=homepage, event_list=event_list,
                          details=details, today=today)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit read-only delle schede Palazzo Attems")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    report = collect_audit(args.as_of)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["source_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
