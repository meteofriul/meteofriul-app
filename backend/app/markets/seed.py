"""Deterministic, reviewable migration. Runtime reads only the packaged seed."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


DATA_PATH = Path(__file__).with_name("data") / "seed.json"


def edition_id(market_id: str, day: str) -> str:
    # The date participates only in initial assignment, never in later updates.
    return "edition-" + hashlib.sha256(f"{market_id}:{day}".encode()).hexdigest()[:24]


def load_seed() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def prepare_seed(root: Path) -> dict:
    paths = {
        "catalogue": root / "frontend/src/data/markets/catalogue2026.json",
        "reviews": root / "docs/operations/evidence/MERCATI_REVISIONE_192_20261030.json",
        "research": root / "docs/operations/evidence/MERCATI_RICOGNIZIONE_COMUNI_20261030.json",
    }
    inputs = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()}
    catalogue, reviews, research = (inputs[key] for key in ("catalogue", "reviews", "research"))
    sources = {item["id"]: item for item in research["sources"] + reviews["new_sources"]}
    markets = copy.deepcopy(catalogue["markets"])
    for market in markets:
        documented = market["quality"] == "Documentato"
        market.update(status="published" if documented else "draft",
                      evidenceStatus="documented" if documented else "unverified",
                      publicationReady=documented,
                      validThrough=catalogue["validThrough"],
                      weekdaysIso=[day or 7 for day in market.get("weekdays", [])])
    market_ids = {item["id"] for item in markets}
    dates = [{**item, "id": edition_id(item["marketId"], item["date"]), "legacyDates": []}
             for item in catalogue["dates"]]
    drafts = []
    for review in reviews["reviews"]:
        if review["decision"] not in {"eligible_current", "eligible_with_limits"}:
            continue
        draft = copy.deepcopy(review)
        identity, validated, municipality = (review[key] for key in ("identity", "validated", "municipality"))
        linked = [identifier for identifier in identity["target_ids"] if identifier in market_ids]
        target_id = linked[0] if linked else "R-" + review["research_id"]
        resolved_sources = [copy.deepcopy(sources[key]) for key in review["source_ids"] if key in sources]
        source_url = next((item["url"] for item in resolved_sources if item.get("url", "").startswith("https://")), "")
        # Agricultural/seasonal/periodic weekday evidence is not a weekly rule.
        regular = validated.get("kind") == "regular"
        iso_days = list(validated.get("weekdays") or []) if regular else []
        suggested = {
            "id": target_id, "key": target_id.lower(), "name": identity["canonical_name"],
            "comune": municipality["name"], "prov": municipality["province"],
            "municipalityIstat": municipality["istat_code"], "kind": validated.get("kind") or "",
            "group": "regular" if regular else "occasional", "place": validated.get("place") or "",
            "hours": validated.get("hours") or "", "cadence": validated.get("recurrence_note") or "",
            "scheduleNote": validated.get("recurrence_note") or "", "url": source_url,
            "authority": resolved_sources[0].get("publisher", "") if resolved_sources else "",
            "checked": reviews["as_of"], "weekdaysIso": iso_days,
            "weekdays": [day % 7 for day in iso_days], "titleAliases": [], "directionsQuery": "",
            "quality": "Da verificare", "status": "draft", "publicationReady": False,
            "validFrom": "", "validThrough": "",
            "evidenceStatus": "documented" if review["decision"] == "eligible_current" else "unverified",
            "researchIds": [review["research_id"]], "sources": resolved_sources,
        }
        suggested_dates = []
        for item in validated.get("editions") or []:
            day = item.get("date")
            if not day:
                continue
            edition_sources = [sources[key] for key in item.get("source_ids", []) if key in sources]
            suggested_dates.append({
                "id": edition_id(target_id, day), "marketId": target_id, "date": day,
                "status": "draft", "evidenceStatus": item.get("status", "unverified"),
                "source": next((source["url"] for source in edition_sources if source.get("url")), ""),
                "sourceIds": item.get("source_ids", []), "legacyDates": [],
            })
        draft.update(id=review["research_id"], tier="complete" if review["decision"] == "eligible_current" else "limited",
                     status="draft", linkedMarketIds=linked, sources=resolved_sources,
                     suggestedMarket=suggested, suggestedDates=suggested_dates)
        drafts.append(draft)
    return {
        "schemaVersion": 2, "checked": catalogue["checked"], "validThrough": catalogue["validThrough"],
        "markets": markets, "dates": dates, "drafts": drafts,
        "provenance": {key: {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                       for key, path in paths.items()},
    }


if __name__ == "__main__":
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(prepare_seed(Path(__file__).resolve().parents[3]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
