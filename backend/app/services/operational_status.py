"""Small, owner-facing interpretation of existing operational evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from app.events.pilot_catalog import source_age_failure


ROME = ZoneInfo("Europe/Rome")


_FORECASTS = {
    "morning": ("Sintesi mattutina", "07:30"),
    "evening": ("Anticipazione serale", "20:45"),
}


def _instant(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def _number(value: Any) -> int:
    return value if type(value) is int and value >= 0 else 0


def _forecast_runs(entries: list[Mapping[str, Any]], kind: str) -> list[dict[str, Any]]:
    runs = []
    for entry in entries:
        payload = entry.get("jsonPayload")
        if not isinstance(payload, dict):
            continue
        context = payload.get("execution_context")
        if not isinstance(context, dict) or context.get("kind") != kind:
            continue
        completed = _instant(context.get("completed_at"))
        if completed is None or not isinstance(payload.get("status"), str):
            continue
        runs.append({
            "at": completed,
            "date": context.get("invocation_local_date") or completed.astimezone(ROME).date().isoformat(),
            "status": payload["status"],
            "eligible": _number(payload.get("eligible_devices")),
            "sent": _number(payload.get("sent")),
            "deduplicated": _number(payload.get("deduplicated")),
            "failed": _number(payload.get("failed")),
            "source_failed": _number(payload.get("source_failed")),
            "quality_limited": _number(payload.get("quality_limited_groups")),
        })
    return sorted(runs, key=lambda run: run["at"], reverse=True)


def _delivered(run: Mapping[str, Any]) -> bool:
    return run["sent"] > 0 or run["deduplicated"] > 0


def _completed(run: Mapping[str, Any]) -> bool:
    if _delivered(run):
        return (run["sent"] + run["deduplicated"] >= max(1, run["eligible"] * 0.8)
                and run["failed"] <= max(2, run["eligible"] * 0.1))
    return run["status"] in {
        "no_eligible_device", "opted_out", "retired_targets", "location_changed"
    }


def _forecast_issue(kind: str, runs: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    label, scheduled = _FORECASTS[kind]
    local_now = now.astimezone(ROME)
    hour, minute = map(int, scheduled.split(":"))
    latest_due = local_now.date()
    if (local_now.hour, local_now.minute) < (hour, minute + 15):
        latest_due -= timedelta(days=1)
    misses = 0
    latest = None
    for offset in range(7):
        day = (latest_due - timedelta(days=offset)).isoformat()
        run = next((item for item in runs if item["date"] == day), None)
        if offset == 0:
            latest = run
        if run and _completed(run):
            break
        misses += 1
    if misses == 0:
        return None
    last_success = next((run["at"] for run in runs if _completed(run)), None)
    if latest is None:
        detail = f"Nessuna corsa verificabile per l'invio delle {scheduled}."
        advice = "Controlla la pianificazione e l'ultima esecuzione del job."
    else:
        detail = ("Invio riuscito solo per una parte dei dispositivi."
                  if _delivered(latest) else "Nessuna notifica inviata nell'ultima corsa.")
        advice = ("La fonte meteo non ha dati sufficienti: attendi la prossima corsa o verifica ICON."
                  if latest["source_failed"] else
                  "Controlla il riepilogo del job e il servizio di invio.")
    return {
        "id": f"forecast:{kind}", "section": "operations",
        "severity": "urgent" if misses >= 2 else "check",
        "title": label, "detail": detail, "advice": advice,
        "lastCheckedAt": latest["at"].isoformat() if latest else None,
        "lastSuccessAt": last_success.isoformat() if last_success else None,
        "missedRuns": misses,
    }


def build_operational_status(
    *,
    entries: list[Mapping[str, Any]] | None,
    catalog: Mapping[str, Any] | None,
    now: datetime,
    paused_sources: set[str] | None = None,
) -> dict[str, Any]:
    """Return actionable items; absent evidence is never interpreted as green."""

    current = now.astimezone(timezone.utc)
    issues: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    coverage = {"forecasts": entries is not None, "events": catalog is not None}

    if entries is None:
        issues.append({
            "id": "operations:forecasts-unavailable", "section": "operations",
            "severity": "check", "title": "Stato notifiche non disponibile",
            "detail": "Il pannello non riesce a leggere i riepiloghi dei job.",
            "advice": "Riprova l'aggiornamento; gli avvisi email restano attivi.",
            "lastCheckedAt": None,
        })
    else:
        for kind in _FORECASTS:
            issue = _forecast_issue(kind, _forecast_runs(entries, kind), current)
            if issue:
                issues.append(issue)

    if catalog is None or catalog.get("schema") != "pilot-events-v1":
        coverage["events"] = False
        issues.append({
            "id": "events:catalog-unavailable", "section": "events",
            "severity": "check", "title": "Stato Eventi non disponibile",
            "detail": "Il catalogo non è stato letto dal pannello.",
            "advice": "Apri Eventi e riprova l'aggiornamento delle fonti.",
            "lastCheckedAt": None,
        })
    else:
        paused = paused_sources if paused_sources is not None else set(catalog.get("paused_sources") or [])
        sources = catalog.get("sources") or {}
        unavailable_sources = []
        for name, source in sorted(sources.items()):
            if name in paused or not isinstance(source, dict):
                continue
            expired = (source.get("status") in {"fresh", "partial"}
                       and source_age_failure(source, now=current))
            if source.get("status") not in {"stale", "unavailable"} and not expired:
                continue
            unavailable_sources.append(name)
        if unavailable_sources:
            names = ", ".join(unavailable_sources[:3])
            if len(unavailable_sources) > 3:
                names += f" e altre {len(unavailable_sources) - 3}"
            issues.append({
                "id": "events:sources", "section": "events", "severity": "check",
                "title": (f"Eventi · {len(unavailable_sources)} "
                          f"{'fonte' if len(unavailable_sources) == 1 else 'fonti'} da controllare"),
                "detail": f"{names}. Le schede di queste fonti non sono visibili nell'app.",
                "advice": "Apri Fonti Eventi per vedere la causa e avviare una verifica mirata.",
                "lastCheckedAt": catalog.get("attempted_at"),
            })
        for name, monitor in sorted((catalog.get("monitors") or {}).items()):
            if isinstance(monitor, dict) and monitor.get("status") == "review_required":
                reviews.append({
                    "id": f"events:review:{name}", "section": "events",
                    "title": f"Da valutare · {name}",
                    "detail": "Fonte candidata: revisione editoriale, non guasto dell'app.",
                })

    return {
        "checkedAt": current.isoformat(), "coverage": coverage,
        "count": len(issues), "urgentCount": sum(item["severity"] == "urgent" for item in issues),
        "issues": issues, "reviews": reviews,
    }
