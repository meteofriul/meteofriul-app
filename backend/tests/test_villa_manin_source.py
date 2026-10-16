import copy
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from app.events import engine
from app.events.sources import villa_manin


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "villa_manin_events.json"


def load_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class VillaManinSourceTests(unittest.TestCase):
    def test_single_date_record_uses_only_explicit_official_fields(self):
        event = villa_manin.parse_villa_manin_record(load_fixture()[0])

        self.assertTrue(event["shadow"])
        self.assertEqual(event["source_id"], "27297")
        self.assertEqual(event["title"], "Cena in bianco")
        self.assertEqual(event["date"], "5 settembre 2026")
        self.assertEqual(event["start_date"], "2026-09-05")
        self.assertEqual(event["end_date"], "2026-09-05")
        self.assertEqual(event["date_confidence"], "explicit_single")
        self.assertEqual(event["venue"], "Villa Manin")
        self.assertEqual(event["event_city"], "Codroipo")
        self.assertIn("convivialità", event["description"])
        self.assertEqual(
            event["image"],
            "https://www.villamanin.it/wp-content/uploads/2026/08/"
            "villa_manin-1x1-cena_in_bianco.jpg",
        )
        self.assertEqual(event["provider_category_list"], ["Evento"])

    def test_written_range_skips_editorial_date_banner_as_description(self):
        event = villa_manin.parse_villa_manin_record(load_fixture()[1])

        self.assertEqual(
            event["date"],
            "dal 20 giugno 2026 al 5 settembre 2026",
        )
        self.assertEqual(event["start_date"], "2026-06-20")
        self.assertEqual(event["end_date"], "2026-09-05")
        self.assertEqual(
            event["description"],
            "Villa Manin vi aspetta al fresco delle sue sale e all’ombra "
            "degli alberi secolari del parco storico.",
        )
        self.assertEqual(event["event_city"], "Codroipo")
        self.assertEqual(event["place"], "Villa Manin - Codroipo")
        self.assertNotIn("event_city", event["missing_fields"])
        self.assertEqual(
            event["location_evidence"]["municipality_resolution"],
            "approved_canonical_venue",
        )
        self.assertEqual(
            event["canonical_venue"],
            {
                "venue": "Villa Manin",
                "locality": "Passariano di Codroipo",
                "municipality": "Codroipo",
                "address": "Piazza Manin 10",
            },
        )

    def test_numeric_range_is_parsed_without_locale_guessing(self):
        event = villa_manin.parse_villa_manin_record(load_fixture()[3])

        self.assertEqual(event["start_date"], "2026-05-21")
        self.assertEqual(event["end_date"], "2026-09-06")
        self.assertEqual(event["date_confidence"], "explicit_range")
        self.assertEqual(event["provider_category_list"], ["Evento", "Mostra"])

    def test_numeric_range_with_shared_year_is_not_split_into_occurrences(self):
        record = copy.deepcopy(load_fixture()[3])
        record["content"]["rendered"] = (
            "<h2>19.05 - 30.08.2026</h2>"
            "<p>La mostra racconta l’evoluzione della bicicletta dal 1815.</p>"
        )

        event = villa_manin.parse_villa_manin_record(record)

        self.assertEqual(event["date_confidence"], "explicit_range")
        self.assertEqual(event["start_date"], "2026-05-19")
        self.assertEqual(event["end_date"], "2026-08-30")
        self.assertEqual(event["occurrences"], [])

    def test_date_heading_wins_over_press_and_related_exhibition_dates(self):
        record = copy.deepcopy(load_fixture()[0])
        record["content"]["rendered"] = (
            "<h2>Giovedì 30.07 ore 19:00 - Sala Convegni</h2>"
            "<p>Passariano di Codroipo, 24 luglio 2026 – Presentazione "
            "dell’appuntamento del 30 luglio.</p>"
            "<p>La mostra collegata resta aperta fino al 30 agosto 2026.</p>"
        )

        event = villa_manin.parse_villa_manin_record(record)

        self.assertEqual(event["date"], "30 luglio 2026")
        self.assertEqual(event["occurrences"], [])

    def test_conflicting_years_in_date_headings_are_rejected(self):
        record = copy.deepcopy(load_fixture()[0])
        record["content"]["rendered"] = (
            "<h2>Venerdì 25.07.2025 - ore 21:00</h2>"
            "<h2>Venerdì 25 luglio 2026 - ore 21:00</h2>"
        )

        with self.assertRaises(villa_manin.VillaManinRecordRejected) as context:
            villa_manin.parse_villa_manin_record(record)

        self.assertEqual(context.exception.reason, "conflicting_header_dates")

    def test_discrete_occurrences_are_rejected_instead_of_becoming_a_range(self):
        with self.assertRaises(villa_manin.VillaManinRecordRejected) as context:
            villa_manin.parse_villa_manin_record(load_fixture()[2])

        self.assertEqual(context.exception.reason, "ambiguous_multiple_dates")

    def test_discrete_occurrences_with_explicit_years_remain_discrete(self):
        record = copy.deepcopy(load_fixture()[2])
        record["content"]["rendered"] = (
            "<h2>25.04, 02.06, 20.09, 01.11, 08.12 2026 "
            "06.01.2027 dalle 9:00 alle 17:30</h2>"
            "<p>Il mercatino propone sei appuntamenti distinti a Villa Manin.</p>"
        )
        record["_embedded"]["wp:term"] = [
            [
                {"id": 96, "name": "2026", "taxonomy": "anno"},
                {"id": 97, "name": "2027", "taxonomy": "anno"},
            ]
        ]

        event = villa_manin.parse_villa_manin_record(record)

        self.assertEqual(event["date_confidence"], "explicit_occurrences")
        self.assertEqual(
            event["occurrences"],
            [
                "2026-04-25",
                "2026-06-02",
                "2026-09-20",
                "2026-11-01",
                "2026-12-08",
                "2027-01-06",
            ],
        )
        self.assertNotIn("dal", event["date"])

    def test_year_taxonomy_resolves_multiple_written_occurrences(self):
        record = copy.deepcopy(load_fixture()[1])
        record["title"]["rendered"] = "Klimt – Semi d’Arte"
        record["content"]["rendered"] = (
            "<p>13 giugno ore 10.30 per bambini dai 2 ai 6 anni</p>"
            "<p>27 giugno, ore 10.30 per bambini dai 2 ai 6 anni</p>"
            "<p>18 luglio, ore 16.30 per bambini dai 5 ai 10 anni</p>"
            "<p>29 agosto, ore 16.30 per bambini dai 5 ai 10 anni</p>"
        )
        record["_embedded"]["wp:term"].append(
            [{"id": 96, "name": "2026", "taxonomy": "anno"}]
        )

        event = villa_manin.parse_villa_manin_record(record)

        self.assertEqual(event["date_confidence"], "explicit_occurrences")
        self.assertEqual(
            event["occurrences"],
            ["2026-06-13", "2026-06-27", "2026-07-18", "2026-08-29"],
        )

    def test_explicit_program_marker_allows_spaced_calendar_rows(self):
        record = copy.deepcopy(load_fixture()[1])
        record["content"]["rendered"] = (
            "<p>Presentazione del laboratorio per bambini.</p>" * 8
            + "<p>Di seguito il calendario completo degli appuntamenti.</p>"
            + "<p>PROGRAMMA</p>"
            + "<p>13 giugno ore 10.30 per bambini</p>"
            + "<p>Descrizione del primo laboratorio.</p>" * 4
            + "<p>29 agosto ore 16.30 per bambini</p>"
        )
        record["_embedded"]["wp:term"].append(
            [{"id": 96, "name": "2026", "taxonomy": "anno"}]
        )

        event = villa_manin.parse_villa_manin_record(record)

        self.assertEqual(event["occurrences"], ["2026-06-13", "2026-08-29"])

    def test_dot_separated_time_is_not_counted_as_another_date(self):
        record = copy.deepcopy(load_fixture()[0])
        record["content"]["rendered"] = (
            "<p>Domenica 9 agosto 2026, alle ore 21.30, il Parco di Villa "
            "Manin ospiterà una serata dedicata alla scoperta del cielo estivo.</p>"
        )

        event = villa_manin.parse_villa_manin_record(record)

        self.assertEqual(event["date"], "9 agosto 2026")
        self.assertEqual(event["date_confidence"], "explicit_single")

    def test_missing_location_is_not_inferred_from_source_identity(self):
        record = copy.deepcopy(load_fixture()[3])
        record["content"]["rendered"] = record["content"]["rendered"].replace(
            " a Villa Manin",
            "",
        )
        event = villa_manin.parse_villa_manin_record(record)

        self.assertIsNone(event["venue"])
        self.assertIsNone(event["event_city"])
        self.assertIsNone(event["place"])

    def test_canonical_city_requires_explicit_villa_manin_venue_evidence(self):
        record = copy.deepcopy(load_fixture()[1])
        record["content"]["rendered"] = (
            "<h2>Dal 20 giugno 2026 al 5 settembre 2026</h2>"
            "<p>La sede espositiva ospita un programma di visite tematiche "
            "dedicate alla storia e all'arte.</p>"
        )

        event = villa_manin.parse_villa_manin_record(record)

        self.assertIsNone(event["venue"])
        self.assertIsNone(event["event_city"])
        self.assertIsNone(event["canonical_venue"])

    def test_event_and_image_urls_are_fail_closed(self):
        self.assertTrue(
            villa_manin.is_trusted_villa_manin_event_url(
                "https://www.villamanin.it/evento/nuda-veritas/"
            )
        )
        self.assertFalse(
            villa_manin.is_trusted_villa_manin_event_url(
                "https://www.villamanin.it.evil.example/evento/nuda-veritas/"
            )
        )
        self.assertFalse(
            villa_manin.is_trusted_villa_manin_event_url(
                "https://www.villamanin.it/evento/nuda-veritas/?next=example.org"
            )
        )
        self.assertFalse(
            villa_manin.is_trusted_villa_manin_image_url(
                "https://images.example.org/nuda-veritas.jpg"
            )
        )

    def test_schema_drift_blocks_the_whole_shadow_report(self):
        payload = load_fixture()[:2]
        del payload[1]["content"]

        report = villa_manin.audit_villa_manin_payload(
            payload,
            as_of=date(2026, 8, 19),
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["counts"]["accepted"], 1)
        self.assertEqual(len(report["structure_errors"]), 1)
        self.assertIn("missing fields: content", report["structure_errors"][0])

    def test_legacy_untrusted_event_url_rejects_only_that_record(self):
        payload = load_fixture()[:1]
        payload[0]["link"] = "https://www.villamanin.it/?post_type=evento&p=27297"

        report = villa_manin.audit_villa_manin_payload(
            payload,
            as_of=date(2026, 8, 19),
        )

        self.assertEqual(report["status"], "ready_for_review")
        self.assertEqual(report["structure_errors"], [])
        self.assertEqual(report["rejected"][0]["reason"], "untrusted_event_url")

    def test_fixture_audit_keeps_ambiguous_record_out_of_candidates(self):
        report = villa_manin.audit_villa_manin_payload(
            load_fixture(),
            as_of=date(2026, 8, 19),
        )

        self.assertEqual(report["status"], "ready_for_review")
        self.assertEqual(
            report["counts"],
            {"received": 4, "accepted": 3, "rejected": 1, "inactive": 0},
        )
        self.assertEqual(report["rejected"][0]["reason"], "ambiguous_multiple_dates")
        self.assertTrue(report["rejected"][0]["title"])
        self.assertTrue(
            report["rejected"][0]["url"].startswith(
                "https://www.villamanin.it/evento/"
            )
        )

    def test_fetcher_is_shadow_only_and_uses_the_official_api(self):
        response = Mock()
        response.json.return_value = load_fixture()[:1]
        response.headers = {"X-WP-Total": "24", "X-WP-TotalPages": "1"}
        session = Mock()
        session.get.return_value = response

        report = villa_manin.fetch_villa_manin_shadow(
            session=session,
            as_of=date(2026, 8, 19),
        )

        session.get.assert_called_once_with(
            villa_manin.VILLA_MANIN_API_URL,
            params={"page": 1, "per_page": 100, "_embed": "1"},
            headers={"User-Agent": "Meteo-Friul-Source-Audit/1.0"},
            timeout=(4, 15),
        )
        response.raise_for_status.assert_called_once_with()
        self.assertTrue(report["shadow"])
        self.assertEqual(report["fetch"]["total"], "24")

    def test_fetcher_retries_one_transient_502_then_succeeds(self):
        failed = Mock(status_code=502)
        failed.raise_for_status.side_effect = requests.HTTPError(
            "bad gateway", response=failed
        )
        success = Mock()
        success.json.return_value = load_fixture()[:1]
        success.headers = {"X-WP-Total": "1", "X-WP-TotalPages": "1"}
        session = Mock()
        session.get.side_effect = [failed, success]

        with patch("app.events.http_client.time.sleep") as sleep:
            report = villa_manin.fetch_villa_manin_shadow(
                session=session,
                as_of=date(2026, 8, 19),
            )

        self.assertEqual(report["status"], "ready_for_review")
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once()

    def test_successful_but_invalid_payload_is_not_retried(self):
        response = Mock()
        response.json.return_value = {"unexpected": "shape"}
        response.headers = {}
        session = Mock()
        session.get.return_value = response

        report = villa_manin.fetch_villa_manin_shadow(session=session)

        self.assertEqual(report["status"], "blocked")
        session.get.assert_called_once()

    def test_missing_embedded_cover_is_a_missing_field_not_schema_drift(self):
        record = copy.deepcopy(load_fixture()[0])
        record["_embedded"].pop("wp:featuredmedia")

        event = villa_manin.parse_villa_manin_record(record)

        self.assertIsNone(event["image"])
        self.assertIn("image", event["missing_fields"])

    def test_catalog_fetches_every_reported_page_before_auditing(self):
        first = Mock()
        first.json.return_value = load_fixture()[:2]
        first.headers = {"X-WP-Total": "4", "X-WP-TotalPages": "2"}
        second = Mock()
        second.json.return_value = load_fixture()[2:]
        second.headers = {"X-WP-Total": "4", "X-WP-TotalPages": "2"}
        session = Mock()
        session.get.side_effect = [first, second]

        report = villa_manin.fetch_villa_manin_shadow_catalog(
            session=session,
            per_page=2,
            as_of=date(2026, 8, 19),
        )

        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(report["fetch"], {"pages": 2, "per_page": 2, "total": "4"})
        self.assertEqual(report["counts"]["received"], 4)
        self.assertEqual(report["counts"]["accepted"], 3)

    def test_duplicate_audit_reuses_the_existing_production_comparator(self):
        shadow = villa_manin.parse_villa_manin_record(load_fixture()[3])
        visible = {
            "source": "TurismoFVG",
            "title": "Nuda Veritas. Klimt",
            "date": "dal 21 maggio 2026 al 6 settembre 2026",
            "place": "Villa Manin - Codroipo",
            "url": "https://www.turismofvg.it/eventi/nuda-veritas-klimt",
        }

        matches = villa_manin.compare_villa_manin_with_visible_events(
            [shadow],
            [visible],
            comparator=engine.events_are_probable_duplicates,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["visible_source"], "TurismoFVG")

    def test_source_is_not_registered_in_the_visible_engine(self):
        engine_source = Path(engine.__file__).read_text(encoding="utf-8")

        self.assertNotIn("fetch_villa_manin_shadow", engine_source)
        self.assertNotIn('"villamanin"', engine_source)


if __name__ == "__main__":
    unittest.main()
