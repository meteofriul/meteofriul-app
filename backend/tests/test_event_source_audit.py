import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.events import audit
from tools import audit_event_sources


def candidate(**overrides):
    record = {
        "shadow": True,
        "eligible_for_review": True,
        "source": "Villa Manin",
        "source_id": "vm-1",
        "title": "Nuda Veritas. Klimt",
        "url": "https://www.villamanin.it/evento/nuda-veritas/",
        "start_date": "2026-05-21",
        "end_date": "2026-09-06",
        "occurrences": [],
        "event_city": "Codroipo",
        "venue": "Villa Manin",
        "place": "Villa Manin - Codroipo",
        "description": "Descrizione ufficiale della mostra.",
        "image": "https://www.villamanin.it/wp-content/uploads/nuda.jpg",
        "missing_fields": [],
    }
    record.update(overrides)
    return record


def visible(**overrides):
    record = {
        "source": "TurismoFVG",
        "title": "Nuda Veritas. Klimt",
        "url": "https://www.turismofvg.it/eventi/nuda-veritas-klimt",
        "start_date": "2026-05-21",
        "end_date": "2026-09-06",
        "occurrences": [],
        "event_city": "Codroipo",
        "venue": "Villa Manin",
        "place": "Villa Manin - Codroipo",
        "description": "Descrizione regionale della mostra.",
        "image": "https://www.turismofvg.it/nuda.jpg",
        "category": "cultura",
        "category_label": "Cultura",
    }
    record.update(overrides)
    return record


def source_report(record, **overrides):
    report = {
        "status": "ready_for_review",
        "shadow": True,
        "source": record["source"],
        "parser_version": "fixture-v1",
        "records": [record],
        "rejected": [],
        "structure_errors": [],
        "counts": {"received": 1, "accepted": 1, "rejected": 0, "inactive": 0},
    }
    report.update(overrides)
    return report


class EventSourceAuditTests(unittest.TestCase):
    def build(self, record, existing=None, **kwargs):
        return audit.build_event_source_audit(
            [source_report(record)],
            existing or [],
            as_of=date(2026, 8, 19),
            **kwargs,
        )

    def test_complete_official_event_can_enter_manual_review_without_turismofvg(self):
        report = self.build(candidate())

        self.assertEqual(report["status"], "ready_for_manual_review")
        self.assertEqual(report["candidates"][0]["decision"], audit.DECISION_READY)
        self.assertFalse(report["candidates"][0]["publish_automatically"])

    def test_exact_title_location_and_date_is_a_confirmed_existing_duplicate(self):
        report = self.build(candidate(), [visible()])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_DUPLICATE)
        self.assertEqual(item["matches"][0]["classification"], "confirmed_duplicate")
        self.assertEqual(item["matches"][0]["basis"], "exact_title_location_date")

    def test_catalog_match_survives_one_malformed_accent_in_provider_title(self):
        record = candidate(
            source="ERPAC FVG",
            title="Ila Bêka. Fotoni",
            event_city="Trieste",
            venue="Magazzino delle Idee",
            start_date="2026-06-27",
            end_date="2026-10-11",
        )
        existing = visible(
            title="Ila B�ka - Fotoni",
            event_city="Trieste",
            venue="Magazzino delle Idee",
            start_date="2026-06-27",
            end_date="2026-10-11",
        )

        report = self.build(record, [existing])

        self.assertEqual(
            report["candidates"][0]["decision"],
            audit.DECISION_REVIEW_DUPLICATE,
        )

    def test_canonical_url_confirms_identity_but_does_not_hide_date_conflict(self):
        existing = visible(
            source="ERPAC FVG",
            url="https://www.villamanin.it/evento/nuda-veritas",
            start_date="2026-05-22",
            end_date="2026-09-07",
        )

        report = self.build(candidate(), [existing])
        item = report["candidates"][0]

        self.assertEqual(item["matches"][0]["basis"], "canonical_url")
        self.assertEqual(item["decision"], audit.DECISION_CONFLICT)
        self.assertEqual(item["conflicts"][0]["field"], "date")

    def test_reviewed_url_pair_confirms_existing_villa_event(self):
        record = candidate(
            title="Klimt - Semi d'Arte",
            url="https://www.villamanin.it/evento/klimt-semi-darte/",
            start_date="2026-06-13",
            end_date="2026-08-29",
            occurrences=["2026-06-13", "2026-06-27", "2026-07-18", "2026-08-29"],
        )
        existing = visible(
            title="Semi d'Arte: accoglienza museale a Villa Manin",
            url=(
                "https://www.turismofvg.it/eventi/"
                "semi-d-arte-accoglienza-museale-a-villa-manin"
            ),
            start_date="2026-06-13",
            end_date="2026-08-29",
            occurrences=["2026-06-13", "2026-06-27", "2026-07-18", "2026-08-29"],
        )

        report = self.build(record, [existing])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_DUPLICATE)
        self.assertEqual(item["matches"][0]["basis"], "reviewed_identity")
        self.assertEqual(
            item["matches"][0]["identity_review"]["primary_source"],
            "Villa Manin",
        )

    def test_reviewed_cena_in_bianco_pair_uses_villa_manin_as_primary(self):
        record = candidate(
            source="Villa Manin",
            title="Cena in bianco",
            url="https://www.villamanin.it/evento/cena-in-bianco/",
            start_date="2026-09-05",
            end_date="2026-09-05",
            event_city="Codroipo",
            venue="Villa Manin",
        )
        existing = visible(
            source="TurismoFVG",
            title="Cena in Bianco 2026",
            url="https://www.turismofvg.it/eventi/cena-in-bianco-2026",
            start_date="2026-09-05",
            end_date="2026-09-05",
            event_city="Codroipo",
            venue="Piazza Tonda di Villa Manin",
        )

        report = self.build(record, [existing])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_DUPLICATE)
        self.assertEqual(item["matches"][0]["basis"], "reviewed_identity")
        self.assertEqual(
            item["matches"][0]["identity_review"]["primary_source"],
            "Villa Manin",
        )

    def test_reviewed_sebastian_di_bin_pair_is_a_confirmed_duplicate(self):
        record = candidate(
            title="Sebastian Di Bin",
            url="https://www.villamanin.it/evento/sebastian-di-bin-2/",
            start_date="2026-09-06",
            end_date="2026-09-06",
        )
        existing = visible(
            title="Sebastian Di Bin in concerto",
            url="https://www.turismofvg.it/eventi/sebastian-di-bin-in-concerto",
            start_date="2026-09-06",
            end_date="2026-09-06",
        )

        report = self.build(record, [existing])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_DUPLICATE)
        self.assertEqual(item["matches"][0]["basis"], "reviewed_identity")
        self.assertIn(
            "same_artist_program_and_time",
            item["matches"][0]["identity_review"]["basis"],
        )

    def test_reviewed_giardino_del_doge_pair_is_a_confirmed_duplicate(self):
        record = candidate(
            title="Nel Giardino del Doge Manin - 5 e 6 settembre 2026",
            url=(
                "https://www.villamanin.it/evento/"
                "nel-giardino-del-doge-manin-5-6-settembre-2026/"
            ),
            start_date="2026-09-06",
            end_date="2026-09-06",
        )
        existing = visible(
            title="23^ Ed. Nel giardino del Doge Manin",
            url="https://www.turismofvg.it/eventi/23-ed-nel-giardino-del-doge-manin",
            start_date="2026-09-05",
            end_date="2026-09-06",
        )

        report = self.build(record, [existing])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_DUPLICATE)
        self.assertEqual(item["matches"][0]["basis"], "reviewed_identity")
        self.assertEqual(item["matches"][0]["date_relation"], "contained_schedule")

    def test_reviewed_sebastian_di_bin_pair_does_not_hide_date_drift(self):
        record = candidate(
            title="Sebastian Di Bin",
            url="https://www.villamanin.it/evento/sebastian-di-bin-2/",
            start_date="2026-09-06",
            end_date="2026-09-06",
        )
        existing = visible(
            title="Sebastian Di Bin in concerto",
            url="https://www.turismofvg.it/eventi/sebastian-di-bin-in-concerto",
            start_date="2026-09-07",
            end_date="2026-09-07",
        )

        report = self.build(record, [existing])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_CONFLICT)
        self.assertTrue(
            any(conflict["field"] == "date" for conflict in item["conflicts"])
        )

    def test_reviewed_cena_in_bianco_pair_does_not_hide_date_drift(self):
        record = candidate(
            source="Villa Manin",
            title="Cena in bianco",
            url="https://www.villamanin.it/evento/cena-in-bianco/",
            start_date="2026-09-05",
            end_date="2026-09-05",
            event_city="Codroipo",
            venue="Villa Manin",
        )
        existing = visible(
            source="TurismoFVG",
            title="Cena in Bianco 2026",
            url="https://www.turismofvg.it/eventi/cena-in-bianco-2026",
            start_date="2026-09-06",
            end_date="2026-09-06",
            event_city="Codroipo",
            venue="Piazza Tonda di Villa Manin",
        )

        report = self.build(record, [existing])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_CONFLICT)
        self.assertTrue(
            any(conflict["field"] == "date" for conflict in item["conflicts"])
        )

    def test_reviewed_identity_does_not_hide_later_critical_drift(self):
        record = candidate(
            title="Nuda Veritas. Klimt",
            url="https://www.villamanin.it/evento/nuda-veritas/",
        )
        existing = visible(
            title="Nuda Veritas. Klimt, un capolavoro a Villa Manin",
            url=(
                "https://www.turismofvg.it/eventi/"
                "nuda-veritas-klimt-un-capolavoro-a-villa-manin"
            ),
            start_date="2026-05-22",
            end_date="2026-09-07",
        )

        report = self.build(record, [existing])
        item = report["candidates"][0]

        self.assertEqual(item["matches"][0]["basis"], "reviewed_identity")
        self.assertEqual(item["decision"], audit.DECISION_CONFLICT)
        self.assertTrue(any(conflict["field"] == "date" for conflict in item["conflicts"]))

    def test_one_day_tolerance_only_detects_and_never_merges(self):
        record = candidate(
            title="Cena in bianco",
            start_date="2026-09-05",
            end_date="2026-09-05",
            url="https://www.villamanin.it/evento/cena-in-bianco/",
        )
        existing = visible(
            title="Cena in bianco a Villa Manin",
            start_date="2026-09-06",
            end_date="2026-09-06",
            url="https://www.turismofvg.it/eventi/cena-in-bianco",
        )

        comparison = audit.compare_event_records(record, existing)

        self.assertEqual(comparison["classification"], "possible_duplicate")
        self.assertEqual(comparison["date_relation"], "near_one_day")
        self.assertTrue(comparison["conflicts"])

    def test_contained_occurrence_is_partial_schedule_not_a_false_conflict(self):
        record = candidate(
            title="Semi d'Arte",
            start_date="2026-06-13",
            end_date="2026-08-29",
            occurrences=["2026-06-13", "2026-06-27", "2026-07-18", "2026-08-29"],
            url="https://www.villamanin.it/evento/semi-darte/",
        )
        existing = visible(
            title="Semi d'Arte a Villa Manin",
            start_date="2026-08-29",
            end_date="2026-08-29",
            url="https://www.turismofvg.it/eventi/semi-darte",
        )

        comparison = audit.compare_event_records(record, existing)

        self.assertEqual(comparison["classification"], "possible_duplicate")
        self.assertEqual(comparison["date_relation"], "contained_schedule")
        self.assertEqual(comparison["conflicts"], [])

    def test_same_unique_title_and_date_with_different_city_is_blocked(self):
        report = self.build(candidate(), [visible(event_city="Trieste", place="Trieste")])
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_CONFLICT)
        self.assertTrue(any(value["field"] == "location" for value in item["conflicts"]))

    def test_title_similarity_without_date_or_location_evidence_is_not_a_match(self):
        comparison = audit.compare_event_records(
            candidate(),
            visible(start_date=None, end_date=None, event_city=None, venue=None, place=None),
        )

        self.assertIsNone(comparison)

    def test_missing_municipality_blocks_candidate_instead_of_inferring_codroipo(self):
        report = self.build(candidate(event_city=None, place="Villa Manin"))
        item = report["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_BLOCKED)
        self.assertIn("missing_event_city", item["blockers"])

    def test_incomplete_visible_catalog_blocks_standalone_approval(self):
        report = self.build(
            candidate(),
            visible_catalog_complete=False,
            collection_warnings=["SagreFVG non raggiungibile"],
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["candidates"][0]["decision"], audit.DECISION_BLOCKED)
        self.assertIn("visible_catalog_incomplete", report["candidates"][0]["blockers"])

    def test_catalog_failure_blocks_only_candidates_in_the_affected_city(self):
        codroipo = candidate(event_city="Codroipo")
        trieste = candidate(
            source="ERPAC FVG",
            source_id="erpac-trieste",
            title="Ila Bêka. Fotoni",
            url="https://magazzinodelleidee.it/evento/ila-beka-fotoni/",
            event_city="Trieste",
            venue="Magazzino delle Idee",
        )

        report = audit.build_event_source_audit(
            [source_report(codroipo), source_report(trieste)],
            [],
            as_of=date(2026, 8, 19),
            visible_catalog_complete=False,
            incomplete_catalog_cities=["Codroipo"],
            collection_warnings=["Codroipo/TurismoFVG non raggiungibile"],
        )
        decisions = {item["candidate"]["event_city"]: item for item in report["candidates"]}

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(decisions["Codroipo"]["decision"], audit.DECISION_BLOCKED)
        self.assertEqual(decisions["Trieste"]["decision"], audit.DECISION_READY)

    def test_transient_detail_error_blocks_only_the_affected_erpac_record(self):
        complete = candidate(
            source="ERPAC FVG",
            source_id="complete",
            title="FVG Settanta",
            url="https://galleriaspazzapan.regione.fvg.it/it/fvg-settanta-170166",
            event_city="Gradisca d'Isonzo",
            venue="Galleria Spazzapan",
        )
        failed = candidate(
            source="ERPAC FVG",
            source_id="failed",
            title="Flowers",
            url="https://galleriaspazzapan.regione.fvg.it/it/flowers-169385",
            event_city="Gradisca d'Isonzo",
            venue="Galleria Spazzapan",
            eligible_for_review=False,
            manual_review_flags=["detail_blocked"],
        )
        report = source_report(
            complete,
            status="blocked",
            records=[complete, failed],
            detail_errors=[{"source_id": "failed", "error": "HTTP 502"}],
        )

        result = audit.build_event_source_audit(
            [report],
            [],
            as_of=date(2026, 8, 19),
        )
        decisions = {item["candidate"]["source_id"]: item for item in result["candidates"]}

        self.assertEqual(decisions["complete"]["decision"], audit.DECISION_READY)
        self.assertEqual(decisions["failed"]["decision"], audit.DECISION_BLOCKED)
        self.assertIn("source_flag:detail_blocked", decisions["failed"]["blockers"])

    def test_rejected_same_title_is_preserved_as_non_publishable_evidence(self):
        record = candidate(title="Cena in bianco", url="https://www.villamanin.it/evento/cena/")
        report = source_report(
            record,
            rejected=[
                {
                    "title": "Cena in bianco",
                    "url": "https://erpac.regione.fvg.it/it/cena-in-bianco-123",
                    "reason": "date_year_missing",
                }
            ],
        )

        result = audit.build_event_source_audit(
            [report],
            [],
            as_of=date(2026, 8, 19),
        )
        item = result["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_REVIEW_DUPLICATE)
        self.assertEqual(item["rejected_source_evidence"][0]["basis"], "exact_title")
        self.assertFalse(item["rejected_source_evidence"][0]["publishable"])

    def test_rejected_erpac_card_with_villa_canonical_url_is_consolidated(self):
        record = candidate(title="Cena in bianco", url="https://www.villamanin.it/evento/cena-in-bianco/")
        erpac_report = source_report(
            candidate(source="ERPAC FVG", source_id="unused"),
            source="ERPAC FVG",
            records=[],
            rejected=[
                {
                    "title": "Cena in bianco",
                    "url": "https://www.villamanin.it/evento/cena-in-bianco/",
                    "reason": "date_year_missing",
                }
            ],
        )

        result = audit.build_event_source_audit(
            [source_report(record), erpac_report],
            [],
            as_of=date(2026, 8, 19),
        )
        item = result["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_READY)
        self.assertEqual(item["consolidated_source_evidence"][0]["source"], "ERPAC FVG")


    def test_villa_manin_is_contextual_authority_but_turismofvg_keeps_category(self):
        report = self.build(candidate(), [visible()])
        authority = report["candidates"][0]["field_authority"]

        self.assertEqual(authority["context"], "villa_manin")
        self.assertEqual(authority["fields"]["description"]["preferred_source"], "Villa Manin")
        self.assertEqual(authority["fields"]["category"]["preferred_source"], "TurismoFVG")
        self.assertFalse(authority["fields"]["start_date"]["preference_resolves_conflicts"])

    def test_erpac_complete_event_can_originate_without_turismofvg(self):
        record = candidate(
            source="ERPAC FVG",
            source_id="erpac-1",
            title="FVG Settanta",
            url="https://galleriaspazzapan.regione.fvg.it/it/fvg-settanta-170166",
            event_city="Gradisca d'Isonzo",
            venue="Galleria Spazzapan",
            place="Galleria Spazzapan - Gradisca d'Isonzo",
        )

        report = self.build(record)

        self.assertEqual(report["candidates"][0]["decision"], audit.DECISION_READY)
        self.assertEqual(
            report["candidates"][0]["field_authority"]["context"],
            "erpac_direct",
        )

    def test_shadow_sources_are_compared_with_each_other(self):
        villa = candidate(title="Semi d'Arte", url="https://www.villamanin.it/evento/semi-darte/")
        erpac_record = candidate(
            source="ERPAC FVG",
            source_id="erpac-semi",
            title="Semi d'Arte a Villa Manin",
            url="https://www.villamanin.it/evento/semi-darte/",
        )

        report = audit.build_event_source_audit(
            [source_report(villa), source_report(erpac_record)],
            [],
            as_of=date(2026, 8, 19),
        )

        self.assertTrue(all(item["matches"] for item in report["candidates"]))
        decisions = {item["candidate"]["source"]: item for item in report["candidates"]}
        self.assertEqual(decisions["Villa Manin"]["decision"], audit.DECISION_READY)
        self.assertEqual(
            decisions["Villa Manin"]["consolidated_source_evidence"][0]["source"],
            "ERPAC FVG",
        )
        self.assertEqual(
            decisions["ERPAC FVG"]["decision"],
            audit.DECISION_CONSOLIDATED,
        )

    def test_incomplete_erpac_copy_is_consolidated_when_villa_url_is_identical(self):
        villa = candidate(
            title="Nuda Veritas. Klimt",
            url="https://www.villamanin.it/evento/nuda-veritas/",
        )
        erpac_copy = candidate(
            source="ERPAC FVG",
            source_id="erpac-nuda",
            title="Nuda Veritas. Klimt, un capolavoro a Villa Manin",
            url="https://www.villamanin.it/evento/nuda-veritas/",
            description=None,
            eligible_for_review=False,
            missing_fields=["description"],
            manual_review_flags=["duplicate_source_villa_manin", "missing_description"],
        )

        report = audit.build_event_source_audit(
            [source_report(villa), source_report(erpac_copy)],
            [],
            as_of=date(2026, 8, 19),
        )
        erpac_item = next(
            item
            for item in report["candidates"]
            if item["candidate"]["source"] == "ERPAC FVG"
        )

        self.assertEqual(erpac_item["decision"], audit.DECISION_CONSOLIDATED)
        self.assertEqual(erpac_item["blockers"], [])
        self.assertEqual(erpac_item["consolidated_into"]["primary_source"], "Villa Manin")
        self.assertIn(
            "source_flag:missing_description",
            erpac_item["secondary_source_notes"],
        )

    def test_reviewed_villa_erpac_pairs_always_keep_villa_as_primary(self):
        reviewed_pairs = (
            {
                "villa": {
                    "source_id": "villa-semi",
                    "title": "Klimt – Semi d’Arte",
                    "url": "https://www.villamanin.it/evento/klimt-semi-darte/",
                    "start_date": "2026-06-13",
                    "end_date": "2026-08-29",
                    "occurrences": [
                        "2026-06-13",
                        "2026-06-27",
                        "2026-07-18",
                        "2026-08-29",
                    ],
                },
                "erpac": {
                    "source_id": "erpac-semi",
                    "title": "Semi d'Arte a Villa Manin",
                    "url": "https://www.villamanin.it/evento/klimt-semi-darte/",
                    "start_date": "2026-08-29",
                    "end_date": "2026-08-29",
                    "occurrences": ["2026-08-29"],
                },
            },
            {
                "villa": {
                    "source_id": "villa-scrigno",
                    "title": "Lo scrigno del Doge in Villa Manin",
                    "url": (
                        "https://www.villamanin.it/evento/"
                        "lo-scrigno-del-doge-in-villa-manin/"
                    ),
                    "start_date": "2026-04-25",
                    "end_date": "2027-01-06",
                    "occurrences": [
                        "2026-04-25",
                        "2026-06-02",
                        "2026-09-20",
                        "2026-11-01",
                        "2026-12-08",
                        "2027-01-06",
                    ],
                },
                "erpac": {
                    "source_id": "erpac-scrigno",
                    "title": "Lo scrigno del Doge in Villa Manin",
                    "url": (
                        "https://www.villamanin.it/evento/"
                        "lo-scrigno-del-doge-in-villa-manin/"
                    ),
                    "start_date": "2026-09-20",
                    "end_date": "2027-01-06",
                    "occurrences": [
                        "2026-09-20",
                        "2026-11-01",
                        "2026-12-08",
                        "2027-01-06",
                    ],
                },
            },
            {
                "villa": {
                    "source_id": "villa-nuda",
                    "title": "Nuda Veritas. Klimt",
                    "url": "https://www.villamanin.it/evento/nuda-veritas/",
                    "start_date": "2026-05-21",
                    "end_date": "2026-09-06",
                },
                "erpac": {
                    "source_id": "erpac-nuda",
                    "title": "Nuda Veritas. Klimt, un capolavoro a Villa Manin",
                    "url": "https://www.villamanin.it/evento/nuda-veritas/",
                    "start_date": "2026-05-21",
                    "end_date": "2026-09-06",
                },
            },
        )

        for pair in reviewed_pairs:
            villa = candidate(**pair["villa"])
            erpac_copy = candidate(
                source="ERPAC FVG",
                eligible_for_review=False,
                description=None,
                missing_fields=["description"],
                manual_review_flags=[
                    "duplicate_source_villa_manin",
                    "missing_description",
                ],
                **pair["erpac"],
            )
            for reports in (
                [source_report(villa), source_report(erpac_copy)],
                [source_report(erpac_copy), source_report(villa)],
            ):
                with self.subTest(
                    title=villa["title"],
                    order=[report["source"] for report in reports],
                ):
                    result = audit.build_event_source_audit(
                        reports,
                        [],
                        as_of=date(2026, 8, 19),
                    )
                    decisions = {
                        item["candidate"]["source"]: item
                        for item in result["candidates"]
                    }
                    villa_item = decisions["Villa Manin"]
                    erpac_item = decisions["ERPAC FVG"]

                    self.assertEqual(villa_item["decision"], audit.DECISION_READY)
                    self.assertEqual(
                        villa_item["consolidated_source_evidence"][0]["source"],
                        "ERPAC FVG",
                    )
                    self.assertFalse(
                        villa_item["consolidated_source_evidence"][0][
                            "publishable_separately"
                        ]
                    )
                    self.assertEqual(
                        erpac_item["decision"],
                        audit.DECISION_CONSOLIDATED,
                    )
                    self.assertEqual(erpac_item["blockers"], [])
                    self.assertEqual(
                        erpac_item["consolidated_into"]["primary_source"],
                        "Villa Manin",
                    )
                    self.assertEqual(
                        audit.canonical_url(
                            erpac_item["consolidated_into"]["primary_url"]
                        ),
                        audit.canonical_url(villa["url"]),
                    )

    def test_reviewed_villa_erpac_pair_does_not_consolidate_critical_drift(self):
        villa = candidate(
            source_id="villa-nuda",
            title="Nuda Veritas. Klimt",
            url="https://www.villamanin.it/evento/nuda-veritas/",
        )
        erpac_copy = candidate(
            source="ERPAC FVG",
            source_id="erpac-nuda",
            title="Nuda Veritas. Klimt, un capolavoro a Villa Manin",
            url="https://www.villamanin.it/evento/nuda-veritas/",
            start_date="2026-05-22",
            end_date="2026-09-07",
        )

        result = audit.build_event_source_audit(
            [source_report(villa), source_report(erpac_copy)],
            [],
            as_of=date(2026, 8, 19),
        )

        self.assertTrue(
            all(
                item["decision"] == audit.DECISION_CONFLICT
                for item in result["candidates"]
            )
        )
        self.assertTrue(
            all(item["conflicts"] for item in result["candidates"])
        )

    def test_erpac_villa_evidence_stays_secondary_when_villa_source_is_down(self):
        erpac_copies = (
            candidate(
                source="ERPAC FVG",
                source_id="erpac-semi",
                title="Semi d'Arte a Villa Manin",
                url="https://www.villamanin.it/evento/klimt-semi-darte/",
                start_date="2026-08-29",
                end_date="2026-08-29",
                occurrences=["2026-08-29"],
            ),
            candidate(
                source="ERPAC FVG",
                source_id="erpac-scrigno",
                title="Lo scrigno del Doge in Villa Manin",
                url=(
                    "https://www.villamanin.it/evento/"
                    "lo-scrigno-del-doge-in-villa-manin/"
                ),
                start_date="2026-09-20",
                end_date="2027-01-06",
                occurrences=[
                    "2026-09-20",
                    "2026-11-01",
                    "2026-12-08",
                    "2027-01-06",
                ],
            ),
            candidate(
                source="ERPAC FVG",
                source_id="erpac-nuda",
                title="Nuda Veritas. Klimt, un capolavoro a Villa Manin",
                url="https://www.villamanin.it/evento/nuda-veritas/",
            ),
        )
        for record in erpac_copies:
            record.update(
                eligible_for_review=False,
                description=None,
                missing_fields=["description"],
                manual_review_flags=[
                    "duplicate_source_villa_manin",
                    "missing_description",
                ],
            )
        villa_failure = source_report(
            candidate(),
            status="blocked",
            records=[],
            structure_errors=["source_fetch_failed: ReadTimeout"],
            counts={"received": 0, "accepted": 0, "rejected": 0, "inactive": 0},
        )
        erpac_report = source_report(
            erpac_copies[0],
            records=list(erpac_copies),
            counts={"received": 3, "accepted": 3, "rejected": 0, "inactive": 0},
        )
        visible_events = [
            visible(
                title="Semi d'Arte: accoglienza museale a Villa Manin",
                url="https://www.turismofvg.it/eventi/semi-darte",
                start_date="2026-08-29",
                end_date="2026-08-29",
            ),
            visible(
                title="Nuda Veritas. Klimt, un capolavoro a Villa Manin",
                url="https://www.turismofvg.it/eventi/nuda-veritas-klimt",
            ),
        ]

        result = audit.build_event_source_audit(
            [villa_failure, erpac_report],
            visible_events,
            as_of=date(2026, 8, 19),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(result["candidates"]), 3)
        for item in result["candidates"]:
            with self.subTest(title=item["candidate"]["title"]):
                self.assertEqual(item["decision"], audit.DECISION_CONSOLIDATED)
                self.assertEqual(item["blockers"], [])
                self.assertEqual(
                    item["consolidated_into"]["primary_source"],
                    "Villa Manin",
                )
                self.assertFalse(
                    item["consolidated_into"]["primary_record_available"]
                )
                self.assertEqual(
                    item["consolidated_into"]["basis"],
                    "erpac_canonical_villa_link",
                )
                self.assertEqual(
                    item["consolidated_into"]["primary_url"],
                    audit.canonical_url(item["candidate"]["url"]),
                )
        rendered = audit.render_event_source_audit_markdown(result)
        self.assertIn("Scheda primaria acquisita nel ciclo: **no**", rendered)
        self.assertIn("ERPAC resta soltanto un riscontro non pubblicabile", rendered)

    def test_orphan_erpac_villa_evidence_does_not_hide_visible_date_conflict(self):
        erpac_copy = candidate(
            source="ERPAC FVG",
            source_id="erpac-nuda",
            title="Nuda Veritas. Klimt, un capolavoro a Villa Manin",
            url="https://www.villamanin.it/evento/nuda-veritas/",
            eligible_for_review=False,
            manual_review_flags=["duplicate_source_villa_manin"],
        )
        conflicting_visible = visible(
            title="Nuda Veritas. Klimt, un capolavoro a Villa Manin",
            start_date="2026-05-22",
            end_date="2026-09-07",
        )

        result = self.build(erpac_copy, [conflicting_visible])
        item = result["candidates"][0]

        self.assertEqual(item["decision"], audit.DECISION_CONFLICT)
        self.assertTrue(
            any(conflict["field"] == "date" for conflict in item["conflicts"])
        )

    def test_unmarked_or_non_villa_erpac_record_is_never_silently_consolidated(self):
        records = (
            candidate(
                source="ERPAC FVG",
                source_id="erpac-unmarked",
                url="https://www.villamanin.it/evento/nuda-veritas/",
                eligible_for_review=False,
                manual_review_flags=["missing_description"],
            ),
            candidate(
                source="ERPAC FVG",
                source_id="erpac-other-host",
                url="https://erpac.regione.fvg.it/it/nuda-veritas-123",
                eligible_for_review=False,
                manual_review_flags=["duplicate_source_villa_manin"],
            ),
        )

        for record in records:
            with self.subTest(source_id=record["source_id"]):
                result = self.build(record)
                self.assertEqual(
                    result["candidates"][0]["decision"],
                    audit.DECISION_BLOCKED,
                )
                self.assertIsNone(result["candidates"][0]["consolidated_into"])

    def test_markdown_report_states_shadow_only_contract(self):
        rendered = audit.render_event_source_audit_markdown(self.build(candidate()))

        self.assertIn("solo ombra", rendered)
        self.assertIn("nessuna pubblicazione automatica", rendered)
        self.assertIn("Nuda Veritas. Klimt", rendered)

    def test_existing_report_directory_is_never_overwritten(self):
        with TemporaryDirectory() as directory:
            output_dir = Path(directory)
            (output_dir / "event-source-audit.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "non verrà sovrascritta"):
                audit_event_sources.run_audit(
                    as_of=date(2026, 8, 19),
                    output_dir=output_dir,
                )

    def test_audit_turismofvg_fetch_is_strict_and_uses_candidate_titles(self):
        with patch.object(
            audit_event_sources.engine,
            "fetch_turismofvg_events",
            return_value=[],
        ) as fetch:
            fetchers = audit_event_sources._source_fetchers(
                "Trieste",
                100,
                45.6495,
                13.7768,
                ["Ila Bêka. Fotoni"],
            )
            fetchers["TurismoFVG"]()

        fetch.assert_called_once_with(
            "Trieste",
            100,
            45.6495,
            13.7768,
            search_queries=["Ila Bêka. Fotoni"],
            strict=True,
        )

    def test_active_catalog_normalization_preserves_discrete_occurrences(self):
        normalized = audit_event_sources._normalize_visible_event(
            {
                "date": "13 e 27 giugno, 18 luglio, 29 agosto 2026",
                "occurrences": [
                    "2026-06-13",
                    "2026-06-27",
                    "2026-07-18",
                    "2026-08-29",
                ],
            }
        )

        self.assertEqual(normalized["start_date"], "2026-06-13")
        self.assertEqual(normalized["end_date"], "2026-08-29")
        self.assertEqual(len(normalized["occurrences"]), 4)


if __name__ == "__main__":
    unittest.main()
