from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Callable

from app.events import engine
from app.events.audit import build_event_source_audit, canonical_url
from app.events.sources import erpac, villa_manin


ACTIVE_SOURCE_NAMES = (
    "TurismoFVG",
    "SagreFVG",
    "Pro Loco FVG",
    "Paesi in Festa",
    "EventiFVG",
)


def failed_source_report(source: str, parser_version: str, exc: Exception) -> dict:
    return {
        "status": "blocked",
        "shadow": True,
        "source": source,
        "parser_version": parser_version,
        "records": [],
        "rejected": [],
        "structure_errors": [f"source_fetch_failed: {type(exc).__name__}: {exc}"],
        "counts": {"received": 0, "accepted": 0, "rejected": 0, "inactive": 0},
    }


def normalize_visible_event(event: dict) -> dict:
    normalized = dict(event)
    parsed_occurrences = set()
    for value in normalized.get("occurrences") or []:
        try:
            parsed_occurrences.add(date.fromisoformat(str(value or "")[:10]))
        except ValueError:
            continue
    occurrences = [value.isoformat() for value in sorted(parsed_occurrences)]
    if occurrences:
        normalized["occurrences"] = occurrences
        normalized["start_date"] = occurrences[0]
        normalized["end_date"] = occurrences[-1]
    elif not normalized.get("start_date"):
        start, end = engine.parse_event_date_range(normalized.get("date"))
        if start:
            normalized["start_date"] = start.isoformat()
            normalized["end_date"] = (end or start).isoformat()
    normalized.setdefault("occurrences", [])
    return normalized


def visible_event_key(event: dict) -> tuple[str, str, str, str]:
    return (
        str(event.get("source") or "").casefold(),
        canonical_url(event.get("url")) or "",
        str(event.get("title") or "").casefold(),
        str(event.get("start_date") or ""),
    )


def source_fetchers(
    city: str,
    limit: int,
    lat: float | None,
    lon: float | None,
    candidate_titles: list[str] | None = None,
) -> dict[str, Callable[[], list[dict]]]:
    return {
        "TurismoFVG": lambda: engine.fetch_turismofvg_events(
            city,
            limit,
            lat,
            lon,
            search_queries=candidate_titles,
            strict=True,
        ),
        "SagreFVG": lambda: engine.fetch_sagrefvg_events(city, limit),
        "Pro Loco FVG": lambda: engine.fetch_prolocofvg_events(city, limit),
        "Paesi in Festa": lambda: engine.fetch_paesiinfesta_events(city, limit),
        "EventiFVG": lambda: engine.fetch_eventifvg_events(city, limit),
    }


def collect_active_catalog(
    cities: list[str],
    *,
    limit: int = 100,
    candidate_titles_by_city: dict[str, list[str]] | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict], dict]:
    events_by_key: dict[tuple[str, str, str, str], dict] = {}
    coverage = {"complete": True, "cities": {}, "warnings": []}
    for city in cities:
        if progress:
            progress(f"raccolta fonti attive per {city}")
        lat = lon = None
        try:
            lat, lon = engine.geocode_city(city)
        except Exception as exc:
            coverage["warnings"].append(
                f"{city}: geocode non disponibile: {type(exc).__name__}: {exc}"
            )

        candidate_titles = (candidate_titles_by_city or {}).get(city) or []
        city_status = {
            "sources": {},
            "complete": True,
            "targeted_turismofvg_queries": len(candidate_titles),
        }
        fetchers = source_fetchers(city, limit, lat, lon, candidate_titles)
        with ThreadPoolExecutor(max_workers=len(fetchers)) as executor:
            futures = {
                executor.submit(fetcher): source
                for source, fetcher in fetchers.items()
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    source_events = future.result() or []
                    city_status["sources"][source] = {
                        "status": "ok",
                        "count": len(source_events),
                    }
                    for event in source_events:
                        normalized = normalize_visible_event(event)
                        events_by_key.setdefault(
                            visible_event_key(normalized),
                            normalized,
                        )
                except Exception as exc:
                    city_status["complete"] = False
                    coverage["complete"] = False
                    message = f"{city}/{source}: {type(exc).__name__}: {exc}"
                    coverage["warnings"].append(message)
                    city_status["sources"][source] = {
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }

        missing = sorted(set(ACTIVE_SOURCE_NAMES) - set(city_status["sources"]))
        if missing:
            city_status["complete"] = False
            coverage["complete"] = False
            coverage["warnings"].append(
                f"{city}: fonti non eseguite: {', '.join(missing)}"
            )
        coverage["cities"][city] = city_status
    return list(events_by_key.values()), coverage


def candidate_cities(source_reports: list[dict]) -> list[str]:
    cities = {
        str(record.get("event_city") or "").strip()
        for report in source_reports
        for record in report.get("records") or []
        if str(record.get("event_city") or "").strip()
    }
    return sorted(cities, key=str.casefold)


def candidate_titles_by_city(source_reports: list[dict]) -> dict[str, list[str]]:
    titles_by_city: dict[str, set[str]] = {}
    for report in source_reports:
        for record in report.get("records") or []:
            city = str(record.get("event_city") or "").strip()
            title = str(record.get("title") or "").strip()
            if city and title:
                titles_by_city.setdefault(city, set()).add(title)
    return {
        city: sorted(titles, key=str.casefold)
        for city, titles in titles_by_city.items()
    }


def collect_shadow_source_reports(
    *,
    as_of: date,
    villa_fetcher: Callable[..., dict] | None = None,
    erpac_fetcher: Callable[..., dict] | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[dict]:
    if progress:
        progress("acquisizione Villa Manin in ombra")
    try:
        villa_report = (villa_fetcher or villa_manin.fetch_villa_manin_shadow_catalog)(
            as_of=as_of
        )
    except Exception as exc:
        villa_report = failed_source_report(
            villa_manin.VILLA_MANIN_SOURCE,
            villa_manin.VILLA_MANIN_PARSER_VERSION,
            exc,
        )

    if progress:
        progress("acquisizione ERPAC in ombra")
    try:
        erpac_report = (erpac_fetcher or erpac.fetch_erpac_home_shadow)(
            as_of=as_of,
            include_details=True,
        )
    except Exception as exc:
        erpac_report = failed_source_report(
            erpac.ERPAC_SOURCE,
            erpac.ERPAC_PARSER_VERSION,
            exc,
        )
    return [villa_report, erpac_report]


def build_live_event_source_audit(
    *,
    as_of: date,
    active_limit: int = 100,
    progress: Callable[[str], None] | None = None,
    source_reports: list[dict] | None = None,
) -> dict:
    reports = source_reports or collect_shadow_source_reports(
        as_of=as_of,
        progress=progress,
    )
    cities = candidate_cities(reports)
    visible_events, coverage = collect_active_catalog(
        cities,
        limit=active_limit,
        candidate_titles_by_city=candidate_titles_by_city(reports),
        progress=progress,
    )
    incomplete_catalog_cities = [
        city
        for city, city_status in coverage["cities"].items()
        if not city_status.get("complete")
    ]
    report = build_event_source_audit(
        reports,
        visible_events,
        as_of=as_of,
        visible_catalog_complete=coverage["complete"],
        incomplete_catalog_cities=incomplete_catalog_cities,
        collection_warnings=coverage["warnings"],
    )
    report["active_catalog_coverage"] = coverage
    return report


__all__ = [
    "ACTIVE_SOURCE_NAMES",
    "build_live_event_source_audit",
    "candidate_cities",
    "candidate_titles_by_city",
    "collect_active_catalog",
    "collect_shadow_source_reports",
    "failed_source_report",
    "normalize_visible_event",
    "source_fetchers",
    "visible_event_key",
]
