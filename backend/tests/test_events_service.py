import unittest
from unittest.mock import patch

from app.events import engine
from app.services.events import EventsService


def response_payload(status="fresh"):
    return {
        "city": "Pordenone",
        "events": [
            {
                "title": "Sagra dell'Assunta",
                "place": "Porcia",
                "event_city": "Porcia",
                "date": "dal 31 luglio al 16 agosto 2026",
                "source": "TurismoFVG",
                "url": "https://www.turismofvg.it/eventi/sagra-dell-assunta-498528",
                "lat": 45.96301,
                "lon": 12.61642,
                "is_real": True,
                "category": "sagra",
                "category_label": "Sagra / festa locale",
            }
        ],
        "events_scope": "nearby",
        "source": "TurismoFVG",
        "sources": ["TurismoFVG"],
        "is_real": True,
        "cache": {"status": status},
    }


class EventsServiceTests(unittest.TestCase):
    def test_event_detail_fetches_verified_copy_and_location_from_trusted_turismofvg_page(self):
        event_url = "https://www.turismofvg.it/eventi/armonie-in-citta"

        with patch.object(
            engine,
            "fetch_turismofvg_event_detail",
            return_value={
                "date": "18 agosto 2026",
                "description": "Concerto inserito nella rassegna Armonie in città.",
                "event_city": "Udine",
                "place": "Teatro Palamostre",
                "venue": "Teatro Palamostre",
                "address": "Piazzale Paolo Diacono, 21",
            },
        ) as fetch_detail:
            response = EventsService().get_event_detail("TurismoFVG", event_url)

        self.assertEqual(response.source, "TurismoFVG")
        self.assertEqual(response.url, event_url)
        self.assertEqual(
            response.description,
            "Concerto inserito nella rassegna Armonie in città.",
        )
        self.assertEqual(response.event_city, "Udine")
        self.assertEqual(response.venue, "Teatro Palamostre")
        self.assertEqual(response.address, "Piazzale Paolo Diacono, 21")
        fetch_detail.assert_called_once_with(
            event_url,
            {"User-Agent": "Meteo-Friul-App/1.0"},
        )

    def test_event_detail_rejects_unsupported_source_and_untrusted_url(self):
        service = EventsService()

        with self.assertRaisesRegex(ValueError, "unsupported_event_source"):
            service.get_event_detail(
                "Eventbrite",
                "https://www.turismofvg.it/eventi/armonie-in-citta",
            )

        with self.assertRaisesRegex(ValueError, "invalid_event_url"):
            service.get_event_detail(
                "TurismoFVG",
                "https://example.org/eventi/armonie-in-citta",
            )

    def test_uncached_request_starts_background_refresh_without_waiting_for_sources(self):
        with (
            patch.object(engine, "load_best_local_events_cache_entry", return_value=None),
            patch.object(engine, "local_events_recent_refresh_outcome", return_value=None),
            patch.object(engine, "local_events_refresh_in_progress", return_value=False),
            patch.object(engine, "schedule_local_events_refresh") as schedule_refresh,
            patch.object(engine, "refresh_local_events_cache") as synchronous_refresh,
        ):
            response = EventsService().get_local_events(
                "Pordenone",
                limit=100,
                lat=45.9567,
                lon=12.6605,
            )

        self.assertEqual(response.cache.status, "refreshing")
        self.assertEqual(
            response.cache.model_extra["event_contract_version"],
            engine.EVENTS_RESPONSE_CONTRACT_VERSION,
        )
        self.assertEqual(response.events, [])
        schedule_refresh.assert_called_once_with("Pordenone", 100, 45.9567, 12.6605)
        synchronous_refresh.assert_not_called()

    def test_recent_source_failure_returns_explicit_empty_state_without_retry_storm(self):
        with (
            patch.object(engine, "load_best_local_events_cache_entry", return_value=None),
            patch.object(
                engine,
                "local_events_recent_refresh_outcome",
                return_value="source_unavailable",
            ),
            patch.object(engine, "schedule_local_events_refresh") as schedule_refresh,
        ):
            response = EventsService().get_local_events("Pordenone", limit=100)

        self.assertEqual(response.events, [])
        self.assertEqual(response.events_scope, "none")
        self.assertEqual(response.cache.status, "source_unavailable")
        schedule_refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
