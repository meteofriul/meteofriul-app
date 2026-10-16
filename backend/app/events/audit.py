from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit


AUDIT_CONTRACT_VERSION = "event-source-audit-v1"

DECISION_READY = "ready_for_manual_approval"
DECISION_BLOCKED = "blocked_incomplete"
DECISION_CONFLICT = "blocked_conflict"
DECISION_DUPLICATE = "confirmed_duplicate_existing"
DECISION_REVIEW_DUPLICATE = "manual_review_duplicate"
DECISION_CONSOLIDATED = "consolidated_into_primary"

REVIEWED_EVENT_IDENTITIES = (
    {
        "canonical_urls": (
            "https://villamanin.it/evento/cena-in-bianco",
            "https://turismofvg.it/eventi/cena-in-bianco-2026",
        ),
        "reviewed_on": "2026-08-19",
        "primary_source": "Villa Manin",
        "basis": (
            "official_titles_related",
            "exact_event_date",
            "exact_municipality",
            "official_venue_and_organizer",
            "erpac_canonical_villa_link",
        ),
    },
    {
        "canonical_urls": (
            "https://villamanin.it/evento/klimt-semi-darte",
            "https://turismofvg.it/eventi/semi-d-arte-accoglienza-museale-a-villa-manin",
        ),
        "reviewed_on": "2026-08-19",
        "primary_source": "Villa Manin",
        "basis": (
            "official_titles_related",
            "exact_occurrences",
            "exact_municipality",
            "official_venue_and_organizer",
        ),
    },
    {
        "canonical_urls": (
            "https://villamanin.it/evento/nuda-veritas",
            "https://turismofvg.it/eventi/nuda-veritas-klimt-un-capolavoro-a-villa-manin",
        ),
        "reviewed_on": "2026-08-19",
        "primary_source": "Villa Manin",
        "basis": (
            "official_titles_related",
            "exact_date_range",
            "exact_municipality",
            "official_venue_and_organizer",
        ),
    },
    {
        "canonical_urls": (
            "https://villamanin.it/evento/a-ruota-libera",
            "https://turismofvg.it/eventi/ruota-libera-la-bici-nell-evoluzione-sociale-dell-italia",
        ),
        "reviewed_on": "2026-08-19",
        "primary_source": "Villa Manin",
        "basis": (
            "official_titles_related",
            "exact_date_range",
            "exact_municipality",
            "official_venue_and_organizer",
        ),
    },
    {
        "canonical_urls": (
            "https://villamanin.it/evento/sebastian-di-bin-2",
            "https://turismofvg.it/eventi/sebastian-di-bin-in-concerto",
        ),
        "reviewed_on": "2026-08-30",
        "primary_source": "Villa Manin",
        "basis": (
            "official_titles_related",
            "exact_event_date",
            "exact_municipality",
            "same_artist_program_and_time",
        ),
    },
    {
        "canonical_urls": (
            "https://villamanin.it/evento/nel-giardino-del-doge-manin-5-6-settembre-2026",
            "https://turismofvg.it/eventi/23-ed-nel-giardino-del-doge-manin",
        ),
        "reviewed_on": "2026-08-30",
        "primary_source": "Villa Manin",
        "basis": (
            "official_titles_related",
            "same_23rd_edition",
            "contained_event_schedule",
            "exact_municipality",
        ),
    },
)

CRITICAL_FIELDS = (
    "title",
    "start_date",
    "end_date",
    "event_city",
    "venue",
    "time",
    "status",
)

_TITLE_STOPWORDS = {
    "a",
    "al",
    "alla",
    "arte",
    "da",
    "dal",
    "dell",
    "della",
    "delle",
    "di",
    "e",
    "evento",
    "fvg",
    "friuli",
    "giulia",
    "il",
    "in",
    "la",
    "le",
    "lo",
    "manin",
    "mostra",
    "per",
    "un",
    "una",
    "venezia",
    "villa",
}

_LOCATION_STOPWORDS = {
    "auditorium",
    "centro",
    "civico",
    "comune",
    "del",
    "della",
    "delle",
    "di",
    "galleria",
    "palazzo",
    "regione",
    "sala",
    "teatro",
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", _clean(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def canonical_url(value: object) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.casefold()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(("https", host, path, "", ""))


def _reviewed_event_identity(left_url: str | None, right_url: str | None) -> dict | None:
    if not left_url or not right_url:
        return None
    compared_urls = {left_url, right_url}
    for identity in REVIEWED_EVENT_IDENTITIES:
        if compared_urls == set(identity["canonical_urls"]):
            return {
                "canonical_urls": list(identity["canonical_urls"]),
                "reviewed_on": identity["reviewed_on"],
                "primary_source": identity["primary_source"],
                "basis": list(identity["basis"]),
            }
    return None


def _iso_date(value: object) -> date | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def date_intervals(record: dict) -> list[tuple[date, date]]:
    occurrences = []
    for value in record.get("occurrences") or []:
        parsed = _iso_date(value)
        if parsed:
            occurrences.append((parsed, parsed))
    if occurrences:
        return sorted(set(occurrences))

    start = _iso_date(record.get("start_date"))
    end = _iso_date(record.get("end_date")) or start
    if not start:
        return []
    if end and end < start:
        return []
    return [(start, end or start)]


def _date_relation(left: dict, right: dict) -> str:
    left_intervals = date_intervals(left)
    right_intervals = date_intervals(right)
    if not left_intervals or not right_intervals:
        return "unavailable"
    if left_intervals == right_intervals:
        return "exact"
    left_contained = all(
        any(
            start_right <= start_left and end_left <= end_right
            for start_right, end_right in right_intervals
        )
        for start_left, end_left in left_intervals
    )
    right_contained = all(
        any(
            start_left <= start_right and end_right <= end_left
            for start_left, end_left in left_intervals
        )
        for start_right, end_right in right_intervals
    )
    if left_contained or right_contained:
        return "contained_schedule"
    if any(
        start_left <= end_right and start_right <= end_left
        for start_left, end_left in left_intervals
        for start_right, end_right in right_intervals
    ):
        return "overlap"

    minimum_gap = min(
        min(abs((start_left - end_right).days), abs((start_right - end_left).days))
        for start_left, end_left in left_intervals
        for start_right, end_right in right_intervals
    )
    return "near_one_day" if minimum_gap <= 1 else "different"


def _tokens(value: object, stopwords: set[str]) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) > 2
        and token not in stopwords
        and not re.fullmatch(r"20\d{2}", token)
    }


def _titles_related(left: dict, right: dict) -> tuple[bool, str]:
    left_title = normalize_text(left.get("title"))
    right_title = normalize_text(right.get("title"))
    if not left_title or not right_title:
        return False, "unavailable"
    if left_title == right_title:
        return True, "exact"

    left_tokens = _tokens(left_title, _TITLE_STOPWORDS)
    right_tokens = _tokens(right_title, _TITLE_STOPWORDS)
    shared = left_tokens & right_tokens
    if not shared:
        return False, "different"
    smallest = min(len(left_tokens), len(right_tokens))
    largest = max(len(left_tokens), len(right_tokens))
    coverage = len(shared) / smallest if smallest else 0
    broad_coverage = len(shared) / largest if largest else 0
    related = len(shared) >= 2 and coverage >= 0.6 and broad_coverage >= 0.4
    if smallest <= 2 and coverage == 1:
        related = True
    return related, "related" if related else "weak"


def _location_values(record: dict) -> list[str]:
    values = []
    for field in ("event_city", "venue", "place"):
        normalized = normalize_text(record.get(field))
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def _location_relation(left: dict, right: dict) -> str:
    city_left = normalize_text(left.get("event_city"))
    city_right = normalize_text(right.get("event_city"))
    if city_left and city_right:
        return "exact_city" if city_left == city_right else "different_city"

    values_left = _location_values(left)
    values_right = _location_values(right)
    if not values_left or not values_right:
        return "unavailable"
    for value_left in values_left:
        for value_right in values_right:
            if value_left == value_right or value_left in value_right or value_right in value_left:
                return "related"
            tokens_left = _tokens(value_left, _LOCATION_STOPWORDS)
            tokens_right = _tokens(value_right, _LOCATION_STOPWORDS)
            if tokens_left & tokens_right:
                return "related"
    return "different"


def _normalized_status(record: dict) -> str | None:
    status = normalize_text(record.get("status") or record.get("event_status"))
    if not status:
        return None
    if any(value in status for value in ("annull", "cancel")):
        return "cancelled"
    if any(value in status for value in ("rinvi", "postpon")):
        return "postponed"
    return status


def _time_value(record: dict) -> str | None:
    values = [record.get("time"), record.get("start_time"), record.get("end_time")]
    cleaned = [_clean(value) for value in values if _clean(value)]
    return " - ".join(cleaned) or None


def _record_identity(record: dict, role: str) -> dict:
    return {
        "role": role,
        "source": record.get("source"),
        "source_id": record.get("source_id"),
        "title": record.get("title"),
        "url": record.get("url"),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
        "occurrences": list(record.get("occurrences") or []),
        "event_city": record.get("event_city"),
        "venue": record.get("venue"),
        "place": record.get("place"),
        "time": _time_value(record),
        "status": _normalized_status(record),
        "description": record.get("description"),
        "image": record.get("image"),
        "category": record.get("category"),
        "category_label": record.get("category_label"),
    }


def _critical_conflicts(left: dict, right: dict, *, date_relation: str, location_relation: str) -> list[dict]:
    conflicts = []
    if date_relation in {"overlap", "near_one_day", "different"}:
        conflicts.append(
            {
                "field": "date",
                "left": {
                    "start_date": left.get("start_date"),
                    "end_date": left.get("end_date"),
                    "occurrences": list(left.get("occurrences") or []),
                },
                "right": {
                    "start_date": right.get("start_date"),
                    "end_date": right.get("end_date"),
                    "occurrences": list(right.get("occurrences") or []),
                },
                "relation": date_relation,
                "blocking": True,
            }
        )
    if location_relation in {"different_city", "different"}:
        conflicts.append(
            {
                "field": "location",
                "left": {
                    "event_city": left.get("event_city"),
                    "venue": left.get("venue"),
                    "place": left.get("place"),
                },
                "right": {
                    "event_city": right.get("event_city"),
                    "venue": right.get("venue"),
                    "place": right.get("place"),
                },
                "relation": location_relation,
                "blocking": True,
            }
        )

    left_time = _time_value(left)
    right_time = _time_value(right)
    if left_time and right_time and normalize_text(left_time) != normalize_text(right_time):
        conflicts.append(
            {
                "field": "time",
                "left": left_time,
                "right": right_time,
                "relation": "different",
                "blocking": True,
            }
        )

    left_status = _normalized_status(left)
    right_status = _normalized_status(right)
    if left_status and right_status and left_status != right_status:
        conflicts.append(
            {
                "field": "status",
                "left": left_status,
                "right": right_status,
                "relation": "different",
                "blocking": True,
            }
        )
    return conflicts


def compare_event_records(left: dict, right: dict, *, right_role: str = "visible") -> dict | None:
    left_url = canonical_url(left.get("url"))
    right_url = canonical_url(right.get("url"))
    same_url = bool(left_url and right_url and left_url == right_url)
    reviewed_identity = _reviewed_event_identity(left_url, right_url)
    titles_related, title_relation = _titles_related(left, right)
    date_relation = _date_relation(left, right)
    location_relation = _location_relation(left, right)
    title_exact = title_relation == "exact"
    location_related = location_relation in {"exact_city", "related"}

    classification = None
    basis = None
    if reviewed_identity:
        classification = "confirmed_duplicate"
        basis = "reviewed_identity"
    elif same_url:
        classification = "confirmed_duplicate"
        basis = "canonical_url"
    elif title_exact and location_related and date_relation == "exact":
        classification = "confirmed_duplicate"
        basis = "exact_title_location_date"
    elif titles_related and location_related and date_relation in {
        "exact",
        "contained_schedule",
        "overlap",
        "near_one_day",
    }:
        classification = "possible_duplicate"
        basis = f"related_title_location_{date_relation}"
    elif title_exact and (
        location_related
        or date_relation in {"exact", "contained_schedule", "overlap", "near_one_day"}
    ):
        classification = "possible_duplicate"
        basis = "exact_title_with_critical_difference"

    if not classification:
        return None

    conflicts = _critical_conflicts(
        left,
        right,
        date_relation=date_relation,
        location_relation=location_relation,
    )
    return {
        "classification": classification,
        "basis": basis,
        "title_relation": title_relation,
        "date_relation": date_relation,
        "location_relation": location_relation,
        "identity_review": reviewed_identity,
        "conflicts": conflicts,
        "counterpart": _record_identity(right, right_role),
    }


def _event_context(records: list[dict]) -> str:
    urls = [canonical_url(record.get("url")) or "" for record in records]
    locations = " ".join(
        normalize_text(record.get(field))
        for record in records
        for field in ("venue", "place")
    )
    if any("villamanin.it" in value for value in urls) or "villa manin" in locations:
        return "villa_manin"
    if any("magazzinodelleidee.it" in value for value in urls):
        return "magazzino_delle_idee"
    if any("erpac.regione.fvg.it" in value or ".regione.fvg.it" in value for value in urls):
        return "erpac_direct"
    return "regional"


def _source_key(record: dict) -> str:
    source = normalize_text(record.get("source"))
    url = canonical_url(record.get("url")) or ""
    if "villamanin.it" in url or source == "villa manin":
        return "villa_manin"
    if "magazzinodelleidee.it" in url:
        return "erpac_fvg"
    if "erpac" in source or "regione.fvg.it" in url:
        return "erpac_fvg"
    if source == "turismofvg":
        return "turismofvg"
    return source or "unknown"


def _authority_rank(source_key: str, context: str, field: str) -> int:
    if field in {"category", "category_label"}:
        return {"turismofvg": 100, "villa_manin": 80, "erpac_fvg": 80}.get(source_key, 40)
    if context == "villa_manin":
        return {"villa_manin": 100, "erpac_fvg": 85, "turismofvg": 75}.get(source_key, 40)
    if context in {"magazzino_delle_idee", "erpac_direct"}:
        return {"erpac_fvg": 100, "turismofvg": 80, "villa_manin": 60}.get(source_key, 40)
    return {"erpac_fvg": 90, "villa_manin": 90, "turismofvg": 85}.get(source_key, 40)


def _field_authority(candidate: dict, matches: list[dict]) -> dict:
    records = [candidate]
    for match in matches:
        counterpart = match["counterpart"]
        records.append(counterpart)
    context = _event_context(records)
    fields = (
        "title",
        "start_date",
        "end_date",
        "event_city",
        "venue",
        "description",
        "image",
        "category",
        "category_label",
    )
    result = {}
    for field in fields:
        evidence = []
        for record in records:
            value = record.get(field)
            if value in (None, "", []):
                continue
            evidence.append(
                {
                    "source": record.get("source"),
                    "url": record.get("url"),
                    "value": value,
                    "rank": _authority_rank(_source_key(record), context, field),
                }
            )
        evidence.sort(key=lambda item: (-item["rank"], normalize_text(item["source"])))
        result[field] = {
            "preferred_source": evidence[0]["source"] if evidence else None,
            "evidence": evidence,
            "preference_resolves_conflicts": False,
        }
    return {"context": context, "fields": result}


def _candidate_blockers(record: dict, source_report: dict, *, catalog_complete: bool) -> list[str]:
    blockers = []
    if source_report.get("structure_errors"):
        blockers.append("source_report_blocked")
    if not catalog_complete:
        blockers.append("visible_catalog_incomplete")
    if not _clean(record.get("title")):
        blockers.append("missing_title")
    if not canonical_url(record.get("url")):
        blockers.append("missing_or_invalid_url")
    if not date_intervals(record):
        blockers.append("missing_or_invalid_date")
    if not _clean(record.get("event_city")):
        blockers.append("missing_event_city")
    if record.get("eligible_for_review") is False:
        flags = record.get("manual_review_flags") or []
        blockers.extend(f"source_flag:{value}" for value in flags)
        if not flags:
            blockers.append("source_not_eligible_for_review")
    return list(dict.fromkeys(blockers))


def _quality_gaps(record: dict) -> list[str]:
    fields = set(record.get("missing_fields") or [])
    for field in ("description", "image", "venue"):
        if not record.get(field):
            fields.add(field)
    return sorted(fields)


def _candidate_key(record: dict) -> tuple[str, str, str]:
    return (
        normalize_text(record.get("source")),
        _clean(record.get("source_id")),
        canonical_url(record.get("url")) or "",
    )


def _rejected_evidence_matches(record: dict, evidence: dict) -> dict | None:
    record_url = canonical_url(record.get("url"))
    evidence_url = canonical_url(evidence.get("url"))
    record_title = normalize_text(record.get("title"))
    evidence_title = normalize_text(evidence.get("title"))
    basis = None
    if record_url and evidence_url and record_url == evidence_url:
        basis = "canonical_url"
    elif record_title and evidence_title and record_title == evidence_title:
        basis = "exact_title"
    if not basis:
        return None
    return {
        "source": evidence.get("source"),
        "title": evidence.get("title"),
        "url": evidence.get("url"),
        "reason": evidence.get("reason"),
        "summary": evidence.get("summary"),
        "basis": basis,
        "publishable": False,
    }


def _is_villa_primary_canonical_evidence(record: dict, evidence: dict) -> bool:
    counterpart = evidence.get("counterpart") or evidence
    return (
        normalize_text(record.get("source")) == "villa manin"
        and normalize_text(counterpart.get("source")) == "erpac fvg"
        and evidence.get("basis") == "canonical_url"
    )


def _consolidated_source_evidence(record: dict, matches: list[dict], rejected: list[dict]) -> list[dict]:
    consolidated = []
    for match in matches:
        counterpart = match.get("counterpart") or {}
        if counterpart.get("role") != "shadow":
            continue
        if not _is_villa_primary_canonical_evidence(record, match):
            continue
        consolidated.append(
            {
                "source": counterpart.get("source"),
                "title": counterpart.get("title"),
                "url": counterpart.get("url"),
                "basis": match.get("basis"),
                "evidence_role": "shadow_record",
                "primary_source": "Villa Manin",
                "publishable_separately": False,
            }
        )
    for evidence in rejected:
        if not _is_villa_primary_canonical_evidence(record, evidence):
            continue
        consolidated.append(
            {
                "source": evidence.get("source"),
                "title": evidence.get("title"),
                "url": evidence.get("url"),
                "basis": evidence.get("basis"),
                "evidence_role": "rejected_source_card",
                "reason": evidence.get("reason"),
                "primary_source": "Villa Manin",
                "publishable_separately": False,
            }
        )
    return consolidated


def _secondary_record_consolidation(record: dict, matches: list[dict]) -> dict | None:
    if normalize_text(record.get("source")) != "erpac fvg":
        return None
    primary_matches = []
    for match in matches:
        counterpart = match.get("counterpart") or {}
        if (
            counterpart.get("role") == "shadow"
            and normalize_text(counterpart.get("source")) == "villa manin"
            and match.get("basis") == "canonical_url"
        ):
            primary_matches.append(counterpart)
    if primary_matches:
        primary = min(
            primary_matches,
            key=lambda item: (
                canonical_url(item.get("url")) or "",
                normalize_text(item.get("title")),
                _clean(item.get("source_id")),
            ),
        )
        return {
            "primary_source": "Villa Manin",
            "primary_title": primary.get("title"),
            "primary_url": primary.get("url"),
            "primary_record_available": True,
            "basis": "canonical_url",
        }

    # ERPAC sometimes republishes a Villa Manin card by linking directly to
    # the canonical Villa page. The ERPAC parser marks these records as
    # secondary evidence before attempting any detail extraction. If the
    # Villa API is temporarily unavailable, keep the ERPAC copy quarantined
    # inside the Villa identity instead of turning it into a new candidate or
    # a false incomplete-record incident. Critical conflicts found against a
    # visible record are still evaluated before this consolidation.
    canonical = canonical_url(record.get("url"))
    parsed = urlsplit(canonical or "")
    flags = set(record.get("manual_review_flags") or [])
    if (
        parsed.hostname == "villamanin.it"
        and parsed.path.startswith("/evento/")
        and "duplicate_source_villa_manin" in flags
    ):
        return {
            "primary_source": "Villa Manin",
            "primary_title": None,
            "primary_url": canonical,
            "primary_record_available": False,
            "basis": "erpac_canonical_villa_link",
        }
    return None


def build_event_source_audit(
    source_reports: list[dict],
    visible_events: list[dict],
    *,
    as_of: date | None = None,
    visible_catalog_complete: bool = True,
    incomplete_catalog_cities: list[str] | None = None,
    collection_warnings: list[str] | None = None,
) -> dict:
    as_of = as_of or date.today()
    shadow_records = []
    report_by_key = {}
    rejected_records = []
    for source_report in source_reports:
        for record in source_report.get("records") or []:
            shadow_records.append(record)
            report_by_key[_candidate_key(record)] = source_report
        for rejected in source_report.get("rejected") or []:
            rejected_records.append(
                {
                    **rejected,
                    "source": source_report.get("source"),
                }
            )

    candidates = []
    normalized_incomplete_cities = {
        normalize_text(city)
        for city in incomplete_catalog_cities or []
        if normalize_text(city)
    }
    for record in shadow_records:
        source_report = report_by_key[_candidate_key(record)]
        matches = []
        for visible in visible_events:
            match = compare_event_records(record, visible, right_role="visible")
            if match:
                matches.append(match)
        for other in shadow_records:
            if other is record:
                continue
            if _candidate_key(other) == _candidate_key(record):
                continue
            match = compare_event_records(record, other, right_role="shadow")
            if match:
                matches.append(match)

        conflicts = [
            {**conflict, "counterpart": match["counterpart"]}
            for match in matches
            for conflict in match["conflicts"]
            if conflict.get("blocking")
        ]
        record_city = normalize_text(record.get("event_city"))
        if visible_catalog_complete:
            candidate_catalog_complete = True
        elif incomplete_catalog_cities is None:
            candidate_catalog_complete = False
        else:
            candidate_catalog_complete = bool(record_city) and (
                record_city not in normalized_incomplete_cities
            )
        blockers = _candidate_blockers(
            record,
            source_report,
            catalog_complete=candidate_catalog_complete,
        )
        quality_gaps = _quality_gaps(record)
        rejected_source_evidence = [
            match
            for evidence in rejected_records
            if (match := _rejected_evidence_matches(record, evidence))
        ]
        consolidated_source_evidence = _consolidated_source_evidence(
            record,
            matches,
            rejected_source_evidence,
        )
        consolidated_shadow_keys = {
            (item.get("source"), item.get("url"), item.get("basis"))
            for item in consolidated_source_evidence
            if item.get("evidence_role") == "shadow_record"
        }
        unresolved_rejected_evidence = [
            evidence
            for evidence in rejected_source_evidence
            if not _is_villa_primary_canonical_evidence(record, evidence)
        ]
        visible_confirmed = any(
            match["classification"] == "confirmed_duplicate"
            and match["counterpart"]["role"] == "visible"
            for match in matches
        )
        secondary_consolidation = _secondary_record_consolidation(record, matches)
        has_possible_or_shadow_match = any(
            (
                match["classification"] == "possible_duplicate"
                or match["counterpart"]["role"] == "shadow"
            )
            and (
                match["counterpart"].get("source"),
                match["counterpart"].get("url"),
                match.get("basis"),
            )
            not in consolidated_shadow_keys
            for match in matches
        )

        if conflicts:
            decision = DECISION_CONFLICT
        elif secondary_consolidation:
            decision = DECISION_CONSOLIDATED
        elif blockers:
            decision = DECISION_BLOCKED
        elif visible_confirmed:
            decision = DECISION_DUPLICATE
        elif has_possible_or_shadow_match or unresolved_rejected_evidence:
            decision = DECISION_REVIEW_DUPLICATE
        else:
            decision = DECISION_READY

        candidates.append(
            {
                "candidate": _record_identity(record, "shadow"),
                "decision": decision,
                "publish_automatically": False,
                "blockers": [] if secondary_consolidation else blockers,
                "quality_gaps": [] if secondary_consolidation else quality_gaps,
                "secondary_source_notes": (
                    sorted(set(blockers + quality_gaps))
                    if secondary_consolidation
                    else []
                ),
                "consolidated_into": secondary_consolidation,
                "matches": matches,
                "rejected_source_evidence": rejected_source_evidence,
                "consolidated_source_evidence": consolidated_source_evidence,
                "conflicts": conflicts,
                "field_authority": _field_authority(record, matches),
                "source_record": record,
            }
        )

    decision_counts = Counter(candidate["decision"] for candidate in candidates)
    source_summaries = []
    for report in source_reports:
        source_summaries.append(
            {
                "source": report.get("source"),
                "status": report.get("status"),
                "parser_version": report.get("parser_version"),
                "counts": report.get("counts") or {},
                "structure_errors": list(report.get("structure_errors") or []),
                "rejected": list(report.get("rejected") or []),
                "detail_errors": list(report.get("detail_errors") or []),
                "detail_rejected": list(report.get("detail_rejected") or []),
            }
        )

    warnings = list(collection_warnings or [])
    if not visible_catalog_complete and "visible_catalog_incomplete" not in warnings:
        warnings.append("visible_catalog_incomplete")
    status = "blocked" if any(
        report.get("status") == "blocked" for report in source_reports
    ) or not visible_catalog_complete else "ready_for_manual_review"
    return {
        "contract_version": AUDIT_CONTRACT_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "status": status,
        "shadow_only": True,
        "automatic_publication": False,
        "visible_catalog": {
            "complete": visible_catalog_complete,
            "event_count": len(visible_events),
            "incomplete_cities": sorted(incomplete_catalog_cities or [], key=str.casefold),
            "warnings": warnings,
        },
        "source_summaries": source_summaries,
        "counts": {
            "shadow_candidates": len(candidates),
            "visible_events_compared": len(visible_events),
            "decisions": dict(sorted(decision_counts.items())),
        },
        "candidates": candidates,
    }


def _markdown_value(value: object) -> str:
    text = _clean(value)
    return text.replace("|", "\\|") if text else "—"


def render_event_source_audit_markdown(report: dict) -> str:
    lines = [
        "# Audit locale fonti Eventi",
        "",
        f"- Contratto: `{report.get('contract_version')}`",
        f"- Data di riferimento: `{report.get('as_of')}`",
        f"- Stato: **{report.get('status')}**",
        "- Modalità: **solo ombra; nessuna pubblicazione automatica**",
        f"- Record del catalogo delle fonti attive confrontati: {report.get('counts', {}).get('visible_events_compared', 0)}",
        "",
        "## Riepilogo candidati",
        "",
        "| Fonte | Titolo | Data | Località | Decisione | Doppioni/conflitti |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    incomplete_cities = report.get("visible_catalog", {}).get("incomplete_cities") or []
    if incomplete_cities:
        lines[6:6] = [
            f"- Catalogo incompleto per: {', '.join(incomplete_cities)}",
        ]
    for item in report.get("candidates") or []:
        candidate = item["candidate"]
        date_value = candidate.get("start_date")
        if candidate.get("end_date") and candidate.get("end_date") != date_value:
            date_value = f"{date_value} → {candidate.get('end_date')}"
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_value(candidate.get("source")),
                    _markdown_value(candidate.get("title")),
                    _markdown_value(date_value),
                    _markdown_value(candidate.get("event_city")),
                    f"`{item.get('decision')}`",
                    str(
                        len(item.get("matches") or [])
                        + len(item.get("conflicts") or [])
                        + len(item.get("rejected_source_evidence") or [])
                    ),
                )
            )
            + " |"
        )

    lines.extend(["", "## Schede di verifica", ""])
    for index, item in enumerate(report.get("candidates") or [], start=1):
        candidate = item["candidate"]
        lines.extend(
            [
                f"### {index}. {_markdown_value(candidate.get('title'))}",
                "",
                f"- Fonte: **{_markdown_value(candidate.get('source'))}**",
                f"- URL ufficiale: {_markdown_value(candidate.get('url'))}",
                f"- Decisione: `{item.get('decision')}`",
                f"- Contesto di autorità: `{item.get('field_authority', {}).get('context')}`",
                f"- Blocchi: {_markdown_value(', '.join(item.get('blockers') or []))}",
                f"- Lacune qualitative: {_markdown_value(', '.join(item.get('quality_gaps') or []))}",
                "",
            ]
        )
        if item.get("consolidated_into"):
            consolidation = item["consolidated_into"]
            lines.extend(
                [
                    "**Scheda secondaria consolidata:**",
                    "",
                    f"- Scheda primaria: {_markdown_value(consolidation.get('primary_source'))} — {_markdown_value(consolidation.get('primary_title'))}",
                    f"- Base: `{consolidation.get('basis')}`",
                    (
                        "- Scheda primaria acquisita nel ciclo: **no**; "
                        "ERPAC resta soltanto un riscontro non pubblicabile."
                        if consolidation.get("primary_record_available") is False
                        else "- Scheda primaria acquisita nel ciclo: **sì**."
                    ),
                    f"- Note della copia non pubblicata: {_markdown_value(', '.join(item.get('secondary_source_notes') or []))}",
                    "",
                ]
            )
        review_resolution = item.get("source_record", {}).get("review_resolution")
        if review_resolution:
            lines.extend(
                [
                    "**Risoluzione manuale tracciata:**",
                    "",
                    f"- Data: `{review_resolution.get('reviewed_on')}`",
                    f"- Motivo: {_markdown_value(review_resolution.get('reason'))}",
                    "- Prove ufficiali:",
                ]
            )
            lines.extend(
                f"  - {_markdown_value(url)}"
                for url in review_resolution.get("evidence_urls") or []
            )
            lines.append("")
        matches = item.get("matches") or []
        if not matches:
            lines.extend(["Nessun possibile doppione rilevato nel catalogo confrontato.", ""])
        else:
            lines.extend(
                [
                    "| Tipo | Base | Fonte confronto | Titolo confronto | Data | Località |",
                    "| --- | --- | --- | --- | --- | --- |",
                ]
            )
            for match in matches:
                counterpart = match["counterpart"]
                lines.append(
                    "| "
                    + " | ".join(
                        (
                            _markdown_value(match.get("classification")),
                            _markdown_value(match.get("basis")),
                            _markdown_value(counterpart.get("source")),
                            _markdown_value(counterpart.get("title")),
                            _markdown_value(match.get("date_relation")),
                            _markdown_value(match.get("location_relation")),
                        )
                    )
                    + " |"
                )
            lines.append("")
        if item.get("conflicts"):
            lines.append("**Conflitti bloccanti:**")
            lines.append("")
            for conflict in item["conflicts"]:
                counterpart = conflict.get("counterpart") or {}
                lines.append(
                    f"- `{conflict.get('field')}` con "
                    f"{_markdown_value(counterpart.get('source'))}: "
                    f"relazione `{conflict.get('relation')}`."
                )
            lines.append("")
        consolidated_evidence = item.get("consolidated_source_evidence") or []
        if consolidated_evidence:
            lines.append("**Fonti ombra consolidate nella scheda Villa Manin:**")
            lines.append("")
            for evidence in consolidated_evidence:
                lines.append(
                    f"- {_markdown_value(evidence.get('source'))}: "
                    f"{_markdown_value(evidence.get('title'))} "
                    f"(base `{evidence.get('basis')}`; nessuna card separata)."
                )
            lines.append("")
        rejected_evidence = item.get("rejected_source_evidence") or []
        if rejected_evidence:
            lines.append("**Indizi presenti tra le card scartate:**")
            lines.append("")
            for evidence in rejected_evidence:
                lines.append(
                    f"- {_markdown_value(evidence.get('source'))}: "
                    f"{_markdown_value(evidence.get('title'))} "
                    f"(`{evidence.get('reason')}`, base `{evidence.get('basis')}`)."
                )
            lines.append("")

    lines.extend(
        [
            "## Regole applicate",
            "",
            "- URL canonico condiviso: doppione certo, ma gli eventuali conflitti restano bloccanti.",
            "- Titolo, località e data pienamente concordi: doppione certo.",
            "- Titolo correlato, stessa località e data sovrapposta, contenuta o distante al massimo un giorno: possibile doppione da controllare.",
            "- Una data contenuta in un calendario più ampio è segnalata come calendario parziale, non come conflitto.",
            "- Il margine di un giorno non autorizza mai un'unione automatica.",
            "- Un conflitto su data, orario, località o stato non viene risolto dall'ordine dei parser.",
            "- Anche una card scartata per dati incompleti resta un indizio di possibile doppione e viene mostrata nella scheda.",
            "- Se ERPAC rimanda allo stesso URL canonico Villa Manin, Villa Manin resta la scheda primaria e il record ERPAC non genera una card separata.",
            "- Se Villa Manin è temporaneamente irraggiungibile, una card ERPAC marcata dal parser e collegata direttamente alla pagina Villa resta solo evidenza secondaria; non viene promossa né pubblicata.",
            "- Una risoluzione manuale vale soltanto finché i campi critici usati come prova restano invariati; ogni deriva riapre il blocco.",
            "- Una fonte ufficiale completa può proporre un evento assente da TurismoFVG; resta comunque necessaria l'approvazione manuale.",
            "",
        ]
    )
    return "\n".join(lines)
