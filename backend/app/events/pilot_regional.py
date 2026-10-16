"""Regional TurismoFVG collection: paginated once, no per-town scraping."""
from datetime import datetime
from urllib.parse import urlsplit
import re
import requests
from . import engine
from .source_pipeline import normalize_visible_event
from .http_client import get_with_single_transient_retry
from .pilot_discovery import highlighted_candidates
from .pilot_programmes import annotate_reviewed_regional_programme


def declared_result_total(html):
    match = re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bc-events_result__total\b[^"\']*["\'][^>]*>'
        r'.*?<span\b[^>]*>\s*([\d.,]+)\s+(?:eventi trovati|events found)\s*</span>',
        html, re.I | re.S,
    )
    if not match:
        raise ValueError("TurismoFVG: missing declared result total")
    return int(re.sub(r'\D', '', match[1]))


def collect_regional(*, get=requests.get, max_pages=128):
    if not 1 <= max_pages <= 128:
        raise ValueError("invalid page budget")
    url = engine.TURISMOFVG_EVENTS_URL
    visited, seen, events = set(), set(), []
    rejected, review, candidates = 0, [], {}
    expected_total, cards_seen = None, 0
    listing_days = {}
    for _ in range(max_pages):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "www.turismofvg.it" or url in visited:
            raise ValueError("unsafe or looping pagination")
        visited.add(url)
        response = get_with_single_transient_retry(get, url, timeout=(4, 15),
            headers={"User-Agent": "Meteo-Friul-Pilot-Catalog/1.0"})
        if urlsplit(response.url).hostname != "www.turismofvg.it":
            raise ValueError("unexpected redirect")
        for candidate in highlighted_candidates(response.text):
            candidates.setdefault(candidate['url'], candidate)
        page_total = declared_result_total(response.text)
        if expected_total is None:
            expected_total = page_total
        elif page_total != expected_total:
            raise ValueError("TurismoFVG: result total changed during pagination")
        cards = engine.extract_turismofvg_card_links(response.text, require_explicit_year=True)
        if not cards:
            raise ValueError("unrecognized or empty catalog page")
        cards_seen += len(cards)
        if cards_seen > expected_total:
            raise ValueError("TurismoFVG: more cards than declared results")
        for card in cards:
            if card.get('listing_day_month'):
                listing_days.setdefault(card['url'], set()).add(card['listing_day_month'])
            key = (card["url"], card.get("extracted_date"))
            if key in seen:
                continue
            seen.add(key)
            event = normalize_visible_event({"title": card["title"], "url": card["url"],
                "date": card.get("extracted_date"), "place": card.get("place"),
                "event_city": card.get("place"), "source": "TurismoFVG", "is_real": True,
                "date_evidence_kind": "event_schedule", "date_evidence": card.get("extracted_date"),
                "image": card.get("image"), "occurrences": card.get("occurrences", []),
                **(card.get("classification") or {})})
            if not event.get("start_date"):
                rejected += 1
                review.append({'url': card['url'], 'reason': 'missing_explicit_event_date'})
                candidate = candidates.setdefault(card['url'], {'source': 'TurismoFVG', 'url': card['url'],
                    'title': card['title'], 'event_city': card.get('place'),
                    'discovery_kind': 'listing', 'review_reason': 'missing_explicit_event_date'})
                # A verified detail can recover the schedule later. Keep the
                # listing artwork/classification so promotion does not turn a
                # previously illustrated card into a generic fallback.
                for key, value in {'image': card.get('image'),
                                   **(card.get('classification') or {})}.items():
                    if value and not candidate.get(key):
                        candidate[key] = value
                continue
            town = engine.fvg_municipality_catalog.match_names(card.get("place") or "")
            event.update(lat=town.latitude if town else None, lon=town.longitude if town else None,
                         location_confidence="municipality" if town else "unknown")
            events.append(annotate_reviewed_regional_programme(event))
        next_url = engine.extract_turismofvg_next_page_url(response.text, response.url)
        if not next_url:
            if "carica altri eventi" in engine.normalize_for_search(response.text):
                raise ValueError("unrecognized pagination; refusing incomplete publication")
            if cards_seen != expected_total:
                raise ValueError("TurismoFVG: card count differs from declared results")
            for event in events:
                event['listing_day_months'] = sorted(listing_days.get(event['url'], ()))
            for candidate in candidates.values():
                candidate['listing_day_months'] = sorted(listing_days.get(candidate['url'], ()))
            return {"status": "ok", "events": events, "pages": len(visited), "rejected_dates": rejected,
                    "declared_results": expected_total, "cards_seen": cards_seen,
                    "review_required": review,
                    "detail_candidates": list(candidates.values()),
                    "coverage": "regional-paginated-listing-details-not-guaranteed"}
        url = next_url
    raise ValueError("page budget exceeded; refusing incomplete publication")


if __name__ == "__main__":
    import json
    start = datetime.now()
    result = collect_regional()
    print(json.dumps({"status": result["status"], "pages": result["pages"],
        "records": len(result["events"]), "rejected_dates": result["rejected_dates"],
        "located": sum(e["lat"] is not None for e in result["events"]),
        "seconds": (datetime.now()-start).total_seconds()}, indent=2))
