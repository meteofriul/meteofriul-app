RULESET_VERSION = "osmer-reading-2026-06-07"
TRACE_SCHEMA_VERSION = 1


def projection_rule_id(projection_source: str | None) -> str:
    source = str(projection_source or "region").strip() or "region"
    return f"official_projected.{source}.v1"


def build_structured_xml_passthrough_trace(day: dict) -> dict:
    areas9 = day.get("areas9") or {}
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "mode": "passthrough",
        "source_kind": "structured_xml",
        "reason": "structured_xml_a1_a9_available",
        "valid_date": day.get("valid_date"),
        "date_source": "xml_valid_date",
        "protected_area_count": len(areas9),
        "learning_enabled": False,
        "projection_enabled": False,
    }


def build_official_projected_area_trace(
    *,
    area_id: str,
    candidate: dict,
    projection_source: str,
    block: dict,
    fallback_used: bool = False,
) -> dict:
    overlays = candidate.get("overlays") or []
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "mode": "projection",
        "source_kind": "official_projected",
        "rule_id": projection_rule_id(projection_source),
        "valid_date": block.get("date"),
        "date_source": block.get("date_source"),
        "area_id": area_id,
        "selected_condition": candidate.get("condition"),
        "projection_source": projection_source,
        "risk_index": candidate.get("risk_index"),
        "source_text": candidate.get("text") or "",
        "official_text": block.get("text") or "",
        "locked": bool(candidate.get("locked")),
        "fallback_used": bool(fallback_used),
        "wind_overlay_count": len(overlays),
        "learning_enabled": False,
        "projection_enabled": True,
    }


def build_official_projected_day_trace(
    *,
    block: dict,
    areas9: dict,
    candidate_count: int,
) -> dict:
    rule_ids = sorted({
        ((area.get("decision_trace") or {}).get("rule_id"))
        for area in (areas9 or {}).values()
        if (area.get("decision_trace") or {}).get("rule_id")
    })
    projected_sources = sorted({
        area.get("projection_source")
        for area in (areas9 or {}).values()
        if area.get("projection_source")
    })
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "mode": "projection",
        "source_kind": "official_projected",
        "valid_date": block.get("date"),
        "date_source": block.get("date_source"),
        "area_count": len(areas9 or {}),
        "candidate_count": candidate_count,
        "rule_ids": rule_ids,
        "projection_sources": projected_sources,
        "learning_enabled": False,
        "projection_enabled": True,
    }


def build_projection_merge_trace(
    *,
    existing_dates,
    projected_days,
    added_days,
) -> dict:
    projected_dates = [
        day.get("valid_date")
        for day in (projected_days or [])
        if day.get("valid_date")
    ]
    added_dates = [
        day.get("valid_date")
        for day in (added_days or [])
        if day.get("valid_date")
    ]
    existing_date_set = {
        date
        for date in (existing_dates or set())
        if date
    }
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "mode": "complete_missing_dates_only",
        "source_kind": "official_projected",
        "added_dates": sorted(added_dates),
        "skipped_dates": sorted(date for date in projected_dates if date in existing_date_set),
        "structured_xml_dates": sorted(existing_date_set),
        "learning_enabled": False,
    }
