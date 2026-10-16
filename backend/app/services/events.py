from __future__ import annotations

from app.contracts.events import LocalEventDetailResponse, LocalEventsResponse
from app.events import engine


class EventsService:
    def get_event_detail(self, source: str, url: str) -> LocalEventDetailResponse:
        normalized_source = str(source or "").strip().casefold()
        normalized_url = str(url or "").strip()

        if normalized_source != "turismofvg":
            raise ValueError("unsupported_event_source")
        if not engine.is_trusted_turismofvg_event_url(normalized_url):
            raise ValueError("invalid_event_url")

        detail = engine.fetch_turismofvg_event_detail(
            normalized_url,
            {"User-Agent": "Meteo-Friul-App/1.0"},
        )
        return LocalEventDetailResponse.model_validate(
            {
                "source": "TurismoFVG",
                "url": normalized_url,
                "description": detail.get("description"),
                "event_city": detail.get("event_city"),
                "place": detail.get("place"),
                "venue": detail.get("venue"),
                "address": detail.get("address"),
                "maps_url": detail.get("maps_url"),
                "lat": detail.get("lat"),
                "lon": detail.get("lon"),
                "location_confidence": detail.get("location_confidence"),
            }
        )

    def get_local_events(
        self,
        city: str,
        limit: int = 3,
        lat: float | None = None,
        lon: float | None = None,
    ) -> LocalEventsResponse:
        collection_limit = engine.local_events_collection_limit(limit)
        key = engine.local_events_cache_key(city, collection_limit, lat, lon)
        entry = engine.load_best_local_events_cache_entry(key)

        if entry and entry[0]:
            data, _ = entry
            age = engine.cache_age_seconds(entry)
            cached_status = str((data.get("cache") or {}).get("status") or "")

            if age is None:
                engine.local_events_response_cache.pop(key, None)
            elif cached_status == "partial" and age <= engine.EVENTS_STALE_TTL:
                engine.schedule_local_events_refresh(city, collection_limit, lat, lon)
                return self._validate(
                    engine.limit_local_events_response(
                        engine.clone_local_events_response_with_cache(
                            data,
                            "partial",
                            age,
                            "memory",
                        ),
                        limit,
                    )
                )
            elif age <= engine.EVENTS_CACHE_TTL:
                return self._validate(
                    engine.limit_local_events_response(
                        engine.clone_local_events_response_with_cache(
                            data,
                            "fresh",
                            age,
                            "memory",
                        ),
                        limit,
                    )
                )

            if age is not None and age <= engine.EVENTS_PERSISTENT_STALE_TTL:
                engine.schedule_local_events_refresh(city, collection_limit, lat, lon)
                return self._validate(
                    engine.limit_local_events_response(
                        engine.clone_local_events_response_with_cache(
                            data,
                            "stale",
                            age,
                            "best_cache",
                        ),
                        limit,
                    )
                )

        recent_outcome = engine.local_events_recent_refresh_outcome(key)
        if recent_outcome in {"source_empty", "source_unavailable"}:
            return self._validate(
                {
                    "city": city,
                    "events": [],
                    "events_scope": "none",
                    "source": None,
                    "sources": [],
                    "is_real": False,
                    "cache": {
                        "status": recent_outcome,
                        "event_contract_version": engine.EVENTS_RESPONSE_CONTRACT_VERSION,
                    },
                }
            )

        if not engine.local_events_refresh_in_progress(key):
            engine.schedule_local_events_refresh(city, collection_limit, lat, lon)

        return self._validate(
            {
                "city": city,
                "events": [],
                "events_scope": "refreshing",
                "source": None,
                "sources": [],
                "is_real": False,
                "cache": {
                    "status": "refreshing",
                    "event_contract_version": engine.EVENTS_RESPONSE_CONTRACT_VERSION,
                },
            }
        )

    @staticmethod
    def _validate(payload: dict) -> LocalEventsResponse:
        return LocalEventsResponse.model_validate(payload)
