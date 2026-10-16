import inspect
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from app.events import engine
from app.events.sources import erpac


FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name):
    return json.loads(fixture_text(name))


class ErpacSourceTests(unittest.TestCase):
    def test_home_audit_extracts_only_precise_curated_records(self):
        report = erpac.audit_erpac_home_html(
            fixture_text("erpac_home.html"), as_of=date(2026, 8, 19)
        )

        self.assertEqual(report["status"], "ready_for_review")
        self.assertEqual(
            report["counts"],
            {"received": 7, "accepted": 6, "rejected": 1, "inactive": 0},
        )
        self.assertEqual(report["rejected"][0]["reason"], "non_event_resource")
        self.assertTrue(report["rejected"][0]["title"])
        self.assertIn("summary", report["rejected"][0])
        self.assertIn("url", report["rejected"][0])

        records = {record["title"]: record for record in report["records"]}
        self.assertEqual(records["Semi d'Arte a Villa Manin"]["start_date"], "2026-08-29")
        self.assertEqual(records["Semi d'Arte a Villa Manin"]["event_city"], "Codroipo")
        self.assertEqual(
            records["Lo scrigno del Doge in Villa Manin"]["occurrences"],
            ["2026-09-20", "2026-11-01", "2026-12-08", "2027-01-06"],
        )
        self.assertEqual(
            records["FVG Settanta. Arti visive in Friuli Venezia Giulia negli anni ’70"]["end_date"],
            "2027-01-15",
        )
        self.assertEqual(
            records["Italia Settanta. La creatività come antidoto. Arte Moda Design."]["start_date"],
            "2026-06-27",
        )
        self.assertEqual(records["Ila Bêka. Fotoni"]["end_date"], "2026-10-11")

    def test_open_ended_date_is_collected_but_never_auto_eligible(self):
        report = erpac.audit_erpac_home_html(
            fixture_text("erpac_home.html"), as_of=date(2026, 8, 19)
        )
        dag = next(record for record in report["records"] if record["title"].startswith("DAG"))

        self.assertEqual(dag["date_confidence"], "explicit_start_only")
        self.assertFalse(dag["eligible_for_review"])
        self.assertIn("open_ended_date", dag["manual_review_flags"])

    def test_home_requires_both_reviewed_sections(self):
        html = fixture_text("erpac_home.html").replace(
            '<h3 class="h4">Mostre</h3>', '<h3 class="h4">Esposizioni</h3>'
        )

        report = erpac.audit_erpac_home_html(html, as_of=date(2026, 8, 19))

        self.assertEqual(report["status"], "blocked")
        self.assertIn("missing section: mostre", report["structure_errors"])

    def test_invalid_encoding_is_rejected_instead_of_repaired_by_guessing(self):
        card = {
            "section": "mostre",
            "title": "Titolo � corrotto",
            "summary": "Dal 1 settembre al 2 settembre 2026",
            "url": "https://erpac.regione.fvg.it/it/titolo-123",
            "image": "/media/files/ERPAC/list/test.jpg",
        }

        with self.assertRaisesRegex(erpac.ErpacRecordRejected, "invalid_text_encoding"):
            erpac.parse_erpac_home_card(card)

    def test_content_and_image_allowlists_fail_closed(self):
        self.assertTrue(
            erpac.is_trusted_erpac_content_url(
                "https://magazzinodelleidee.it/evento/ila-beka-fotoni/"
            )
        )
        self.assertFalse(
            erpac.is_trusted_erpac_content_url(
                "https://magazzinodelleidee.it/evento/ila-beka-fotoni/?preview=1"
            )
        )
        self.assertFalse(
            erpac.is_trusted_erpac_content_url("https://example.com/it/evento-123")
        )
        self.assertTrue(
            erpac.is_trusted_erpac_image_url("/media/files/ERPAC/list/test.jpg")
        )
        self.assertFalse(
            erpac.is_trusted_erpac_image_url("https://example.com/image.jpg")
        )

    def test_regional_detail_uses_reviewed_fields_only(self):
        detail = erpac.parse_erpac_regional_detail_html(
            fixture_text("erpac_detail.html"),
            expected_url="https://galleriaspazzapan.regione.fvg.it/it/fvg-settanta-170166",
        )

        self.assertEqual(detail["detail_kind"], "regional_prerender")
        self.assertEqual(
            detail["title"],
            "FVG Settanta. Arti visive in Friuli Venezia Giulia negli anni ’70",
        )
        self.assertTrue(detail["description"].startswith("La mostra racconta"))
        self.assertEqual(detail["venue"], "Galleria Regionale d'Arte contemporanea Luigi Spazzapan")
        self.assertEqual(detail["event_city"], "Gradisca d'Isonzo")

    def test_regional_detail_blocks_canonical_drift(self):
        with self.assertRaisesRegex(erpac.ErpacStructureError, "canonical URL changed"):
            erpac.parse_erpac_regional_detail_html(
                fixture_text("erpac_detail.html"),
                expected_url="https://erpac.regione.fvg.it/it/another-event-123",
            )

    def test_detail_date_prefix_is_not_mistaken_for_the_venue(self):
        html = fixture_text("erpac_detail.html").replace(
            "Galleria Regionale d'Arte contemporanea Luigi Spazzapan, Gradisca d'Isonzo",
            "Dal 27 giugno 2026 al 15 gennaio 2027, Galleria Regionale d'Arte contemporanea Luigi Spazzapan, Gradisca d'Isonzo",
        )

        detail = erpac.parse_erpac_regional_detail_html(
            html,
            expected_url="https://galleriaspazzapan.regione.fvg.it/it/fvg-settanta-170166",
        )

        self.assertEqual(
            detail["venue"],
            "Galleria Regionale d'Arte contemporanea Luigi Spazzapan",
        )
        self.assertEqual(detail["event_city"], "Gradisca d'Isonzo")

    def test_conflicting_home_and_detail_dates_require_manual_review(self):
        home = next(
            record
            for record in erpac.audit_erpac_home_html(
                fixture_text("erpac_home.html"), as_of=date(2026, 8, 19)
            )["records"]
            if record["title"].startswith("Italia Settanta")
        )
        detail = {
            "detail_kind": "regional_prerender",
            "title": home["title"],
            "description": "Una descrizione ufficiale sufficientemente lunga per il controllo.",
            "provider_subtitle": "Dal 27 giugno al 28 novembre 2026, Palazzo Attems, Gorizia",
            "provider_place": "Palazzo Attems, Gorizia",
            "venue": "Palazzo Attems",
            "event_city": "Gorizia",
        }

        enriched = erpac.enrich_erpac_home_record(home, detail)

        self.assertFalse(enriched["eligible_for_review"])
        self.assertIn("date_conflict_detail", enriched["manual_review_flags"])

    def test_different_home_venue_and_detail_address_require_manual_review(self):
        home = {
            "shadow": True,
            "source": "ERPAC FVG",
            "source_id": "via-strade",
            "title": "VIA PER LE STRADE. Paolo Gasparini",
            "url": "https://museiprovincialigorizia.regione.fvg.it/it/via-per-le-strade-167022",
            "date": "dal 25 aprile al 27 settembre 2026",
            "date_confidence": "explicit_range",
            "start_date": "2026-04-25",
            "end_date": "2026-09-27",
            "occurrences": [],
            "description": None,
            "image": "https://erpac.regione.fvg.it/media/files/ERPAC/list/via.jpg",
            "provider_place": "Casa Morassi, Gorizia",
            "venue": "Casa Morassi",
            "event_city": "Gorizia",
            "place": "Gorizia",
            "manual_review_flags": ["missing_description"],
        }
        detail = {
            "detail_kind": "regional_prerender",
            "title": home["title"],
            "description": "Descrizione ufficiale della mostra nelle sale di Casa Morassi.",
            "provider_subtitle": "Borgo Castello 20, Gorizia",
            "provider_place": "Borgo Castello 20, Gorizia",
            "venue": "Borgo Castello 20",
            "event_city": "Gorizia",
        }

        enriched = erpac.enrich_erpac_home_record(home, detail)

        self.assertFalse(enriched["eligible_for_review"])
        self.assertIn("location_difference_detail", enriched["manual_review_flags"])
        self.assertEqual(enriched["provider_home_place"], "Casa Morassi, Gorizia")
        self.assertEqual(enriched["provider_detail_place"], "Borgo Castello 20, Gorizia")

    def test_reviewed_dag_resolution_uses_official_end_date_and_venue_alias(self):
        home = {
            "shadow": True,
            "source": "ERPAC FVG",
            "source_id": "dag",
            "title": "DAG - Digital Art Gallery Gorizia",
            "url": "https://erpac.regione.fvg.it/it/dag-digital-art-gallery-gorizia-165754",
            "date": "17 dicembre 2025",
            "date_confidence": "explicit_start_only",
            "start_date": "2025-12-17",
            "end_date": None,
            "occurrences": [],
            "description": None,
            "image": "https://erpac.regione.fvg.it/media/files/ERPAC/list/dag.jpg",
            "provider_place": "Galleria Bombi, Gorizia",
            "venue": "Galleria Bombi",
            "event_city": "Gorizia",
            "place": "Gorizia",
            "manual_review_flags": ["missing_description", "open_ended_date"],
        }
        detail = {
            "detail_kind": "regional_prerender",
            "title": home["title"],
            "description": "Descrizione ufficiale sufficientemente lunga della galleria digitale.",
            "provider_subtitle": "Galleria Giorgio Bombi, Gorizia",
            "provider_place": "Galleria Giorgio Bombi, Gorizia",
            "venue": "Galleria Giorgio Bombi",
            "event_city": "Gorizia",
        }

        enriched = erpac.enrich_erpac_home_record(home, detail)

        self.assertEqual(enriched["end_date"], "2026-12-31")
        self.assertEqual(enriched["venue"], "Galleria Giorgio Bombi")
        self.assertEqual(enriched["manual_review_flags"], [])
        self.assertEqual(enriched["review_resolution"]["reviewed_on"], "2026-08-19")

    def test_reviewed_italia_settanta_location_requires_explicit_detail_text(self):
        home = next(
            record
            for record in erpac.audit_erpac_home_html(
                fixture_text("erpac_home.html"), as_of=date(2026, 8, 19)
            )["records"]
            if record["title"].startswith("Italia Settanta")
        )
        detail = {
            "detail_kind": "regional_prerender",
            "title": home["title"],
            "description": (
                "Nel 2026, le sale di Palazzo Attems Petzenstein a Gorizia "
                "ospitano la mostra e il suo percorso espositivo."
            ),
            "provider_subtitle": "Dal 27 giugno al 29 novembre 2026",
            "provider_place": None,
            "venue": None,
            "event_city": None,
        }

        enriched = erpac.enrich_erpac_home_record(home, detail)

        self.assertEqual(enriched["venue"], "Palazzo Attems Petzenstein")
        self.assertEqual(enriched["event_city"], "Gorizia")
        self.assertEqual(enriched["manual_review_flags"], [])

        changed_detail = {**detail, "description": "Descrizione priva di sede esplicita."}
        changed = erpac.enrich_erpac_home_record(home, changed_detail)
        self.assertIn(
            "reviewed_resolution_evidence_changed",
            changed["manual_review_flags"],
        )

    def test_reviewed_via_per_le_strade_alias_keeps_raw_place_evidence(self):
        home = {
            "shadow": True,
            "source": "ERPAC FVG",
            "source_id": "via-strade-reviewed",
            "title": "VIA PER LE STRADE. Paolo Gasparini",
            "url": (
                "https://museiprovincialigorizia.regione.fvg.it/it/"
                "via-per-le-strade-paolo-gasparini-167022"
            ),
            "date": "dal 25 aprile al 27 settembre 2026",
            "date_confidence": "explicit_range",
            "start_date": "2026-04-25",
            "end_date": "2026-09-27",
            "occurrences": [],
            "description": None,
            "image": "https://erpac.regione.fvg.it/media/files/ERPAC/list/via.jpg",
            "provider_place": "Casa Morassi, Gorizia",
            "venue": "Casa Morassi",
            "event_city": "Gorizia",
            "place": "Gorizia",
            "manual_review_flags": ["missing_description"],
        }
        detail = {
            "detail_kind": "regional_prerender",
            "title": home["title"],
            "description": "Descrizione ufficiale della mostra nelle sale di Casa Morassi.",
            "provider_subtitle": "Dal 25 aprile al 27 settembre 2026, Borgo Castello 20, Gorizia",
            "provider_place": "Borgo Castello 20, Gorizia",
            "venue": "Borgo Castello 20",
            "event_city": "Gorizia",
        }

        enriched = erpac.enrich_erpac_home_record(home, detail)

        self.assertEqual(enriched["venue"], "Casa Panizzolo Morassi")
        self.assertEqual(enriched["provider_home_place"], "Casa Morassi, Gorizia")
        self.assertEqual(enriched["provider_detail_place"], "Borgo Castello 20, Gorizia")
        self.assertEqual(enriched["manual_review_flags"], [])

    def test_reviewed_intrecci_date_uses_detail_and_blocks_future_drift(self):
        home = {
            "shadow": True,
            "source": "ERPAC FVG",
            "source_id": "intrecci",
            "title": "Intrecci di segni e di fili",
            "url": "https://erpac.regione.fvg.it/it/mostra-intrecci-di-segni-e-di-fili-169817",
            "date": "dal 25 giugno al 27 settembre 2026",
            "date_confidence": "explicit_range",
            "date_source_text": "dal 25 giugno al 27 settembre 2026",
            "start_date": "2026-06-25",
            "end_date": "2026-09-27",
            "occurrences": [],
            "description": None,
            "image": "https://erpac.regione.fvg.it/media/files/ERPAC/list/intrecci.jpg",
            "provider_place": "Showroom Merletto goriziano",
            "venue": "Showroom Merletto goriziano",
            "event_city": "Gorizia",
            "place": "Gorizia",
            "manual_review_flags": ["missing_description"],
        }
        detail = {
            "detail_kind": "regional_prerender",
            "title": home["title"],
            "description": "Descrizione ufficiale sufficientemente lunga della mostra di merletto.",
            "provider_subtitle": (
                "Dal 25 giugno al 26 settembre, Showroom Merletto goriziano, Gorizia"
            ),
            "provider_place": "Showroom Merletto goriziano, Gorizia",
            "venue": "Showroom Merletto goriziano",
            "event_city": "Gorizia",
        }

        enriched = erpac.enrich_erpac_home_record(home, detail)

        self.assertEqual(enriched["end_date"], "2026-09-26")
        self.assertNotIn("date_conflict_detail", enriched["manual_review_flags"])

        changed_detail = {
            **detail,
            "provider_subtitle": (
                "Dal 25 giugno al 25 settembre, Showroom Merletto goriziano, Gorizia"
            ),
        }
        changed = erpac.enrich_erpac_home_record(home, changed_detail)
        self.assertIn("date_conflict_detail", changed["manual_review_flags"])
        self.assertIn(
            "reviewed_resolution_evidence_changed",
            changed["manual_review_flags"],
        )

    def test_magazzino_detail_uses_the_official_wordpress_event(self):
        detail = erpac.parse_erpac_magazzino_payload(
            fixture_json("erpac_magazzino_event.json"),
            expected_url="https://magazzinodelleidee.it/evento/ila-beka-fotoni/",
        )

        self.assertEqual(detail["detail_kind"], "magazzino_wordpress")
        self.assertEqual(detail["title"], "Ila Bêka")
        self.assertIn("prima personale", detail["description"])

    def test_magazzino_detail_does_not_replace_the_complete_home_title(self):
        home = next(
            record
            for record in erpac.audit_erpac_home_html(
                fixture_text("erpac_home.html"), as_of=date(2026, 8, 19)
            )["records"]
            if record["title"] == "Ila Bêka. Fotoni"
        )
        detail = erpac.parse_erpac_magazzino_payload(
            fixture_json("erpac_magazzino_event.json"), expected_url=home["url"]
        )

        enriched = erpac.enrich_erpac_home_record(home, detail)

        self.assertEqual(enriched["title"], "Ila Bêka. Fotoni")
        self.assertEqual(enriched["provider_detail_title"], "Ila Bêka")

    def test_fetch_uses_official_prerender_and_stays_shadow_only(self):
        response = Mock()
        response.content = fixture_text("erpac_home.html").encode("utf-8")
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        report = erpac.fetch_erpac_home_shadow(
            as_of=date(2026, 8, 19), session=session
        )

        self.assertTrue(report["shadow"])
        self.assertTrue(all(record["shadow"] for record in report["records"]))
        session.get.assert_called_once_with(
            erpac.ERPAC_HOME_URL,
            params={"_escaped_fragment_": ""},
            headers={"User-Agent": "Meteo-Friul-Source-Audit/1.0"},
            timeout=(4, 20),
        )

    def test_home_fetch_retries_one_transient_502_then_succeeds(self):
        failed = Mock(status_code=502)
        failed.raise_for_status.side_effect = requests.HTTPError(
            "bad gateway", response=failed
        )
        success = Mock()
        success.content = fixture_text("erpac_home.html").encode("utf-8")
        session = Mock()
        session.get.side_effect = [failed, success]

        with patch("app.events.http_client.time.sleep") as sleep:
            report = erpac.fetch_erpac_home_shadow(
                as_of=date(2026, 8, 19), session=session
            )

        self.assertEqual(report["status"], "ready_for_review")
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once()

    def test_detail_fetch_retries_one_transient_502_then_succeeds(self):
        failed = Mock(status_code=502)
        failed.raise_for_status.side_effect = requests.HTTPError(
            "bad gateway", response=failed
        )
        success = Mock()
        success.json.return_value = fixture_json("erpac_magazzino_event.json")
        session = Mock()
        session.get.side_effect = [failed, success]
        record = {
            "url": "https://magazzinodelleidee.it/evento/ila-beka-fotoni/"
        }

        with patch("app.events.http_client.time.sleep") as sleep:
            detail = erpac._fetch_erpac_detail(record, session=session)

        self.assertEqual(detail["detail_kind"], "magazzino_wordpress")
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once()

    def test_detail_404_rejects_only_that_record_not_the_whole_source(self):
        home_html = """
        <h3 class="h4">Eventi, rassegne e concerti</h3>
        <div class="splide__slide"><img src="/media/files/ERPAC/list/test.jpg">
        <h4><a href="https://erpac.regione.fvg.it/it/test-event-123">Test event</a></h4>
        <p><p>29 agosto 2026<br>Gorizia</p></p></div>
        <h3 class="h4">Mostre</h3>
        """
        home_response = Mock()
        home_response.content = home_html.encode("utf-8")
        home_response.raise_for_status.return_value = None
        detail_response = Mock()
        detail_response.status_code = 404
        detail_response.raise_for_status.side_effect = requests.HTTPError(
            "not found", response=detail_response
        )
        session = Mock()
        session.get.side_effect = [home_response, detail_response]

        report = erpac.fetch_erpac_home_shadow(
            as_of=date(2026, 8, 19), include_details=True, session=session
        )

        self.assertEqual(report["status"], "ready_for_review")
        self.assertEqual(report["counts"]["detail_rejected"], 1)
        self.assertEqual(report["records"][0]["detail_status"], "rejected_not_found")
        self.assertEqual(session.get.call_count, 2)

    def test_visible_engine_does_not_register_erpac(self):
        source = inspect.getsource(engine.build_local_events_response)

        self.assertNotIn("erpac", source.lower())
        self.assertNotIn("fetch_erpac_home_shadow", source)

    def test_duplicate_audit_uses_canonical_url_and_production_comparator(self):
        records = erpac.audit_erpac_home_html(
            fixture_text("erpac_home.html"), as_of=date(2026, 8, 19)
        )["records"]
        semi = next(record for record in records if record["title"].startswith("Semi"))
        scrigno = next(record for record in records if record["title"].startswith("Lo scrigno"))
        existing = [
            {
                "source": "Villa Manin",
                "title": "Semi d'Arte",
                "date": "29 agosto 2026",
                "event_city": "Codroipo",
                "place": "Villa Manin",
                "url": semi["url"],
            },
            {
                "source": "TurismoFVG",
                "title": "Lo scrigno del Doge",
                "date": "20 settembre 2026",
                "event_city": None,
                "place": "Villa Manin",
                "url": "https://www.turismofvg.it/evento/scrigno",
            },
            {
                "source": "TurismoFVG",
                "title": "Cantiere Donna - Arte, armonia e bellezza",
                "date": "29 agosto 2026",
                "event_city": "Codroipo",
                "place": "Villa Manin",
                "url": "https://www.turismofvg.it/eventi/cantiere-donna",
            },
        ]

        matches = erpac.compare_erpac_with_existing_events(
            [semi, scrigno], existing, comparator=engine.events_are_probable_duplicates
        )

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["match_basis"], "canonical_url")
        self.assertEqual(matches[1]["match_basis"], "production_comparator")


if __name__ == "__main__":
    unittest.main()
