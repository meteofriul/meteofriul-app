"""Independent behavioral checks for the unattended Markets refresh.

All writes use temporary SQLite archives; no live source, archive or scheduler.
"""
from __future__ import annotations

import copy
from contextlib import closing, redirect_stdout
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.markets.model import MarketError
from app.markets.repository import FirestoreMarketRepository, SQLiteMarketRepository
from app.markets.refresh_job import main as refresh_main
from app.markets.service import MarketsService
from tests.test_markets_archive import small_seed
from tests.test_markets_firestore import FakeFirestore, transactional


SOURCE = "https://example.test/mercato"
SECOND_SOURCE = "https://example.test/organizzatore"


def observation(fields=None, *, source=SOURCE, updated="2026-11-01", editions=None,
                excerpt="Comunicazione ufficiale: aggiornamento del mercato."):
    fields = copy.deepcopy(fields or {})
    editions = copy.deepcopy(editions or [])
    evidence = [{"field": key, "value": copy.deepcopy(value), "excerpt": excerpt}
                for key, value in fields.items()]
    if editions:
        evidence.append({"field": "editions", "value": editions, "excerpt": excerpt})
    content = json.dumps([fields, editions, excerpt], sort_keys=True).encode()
    result = {"sourceUrl": source, "retrievedAt": "2026-11-01T10:00:00Z",
              "contentHash": hashlib.sha256(content).hexdigest(), "fields": fields,
              "editions": editions, "evidence": evidence, "completeCalendar": False}
    if updated:
        result["sourceUpdatedAt"] = updated
    return result


def source_result(*observations, issues=None):
    return {"marketId": "M001", "observations": list(observations), "issues": issues or []}


class MarketsRefreshContractTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="mf-market-refresh-contract-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "archive.sqlite3"
        self.seed = small_seed()
        self.seed["markets"][0].update({
            "scheduleNote": "Verificare gli avvisi per le festività.",
            "internalNotes": "La piazza alternativa va valutata in caso di lavori.",
            "descriptionFur": "Testo friulano già revisionato.",
            "sources": [{"url": SOURCE}, {"url": SECOND_SOURCE}],
        })
        self.seed["dates"][0]["publicReason"] = "Accesso dal lato sud."
        self.seed["drafts"] = [{
            "id": "practice-one", "status": "prepared", "linkedMarketIds": ["M001"],
            "editorialNotes": "Conservare il riscontro telefonico.",
            "review": {"outstanding": ["Eccezione dei festivi ancora da verificare."]},
            "sources": [{"url": SOURCE, "excerpt": "Primo riscontro conservato."}],
        }]
        self.repo = SQLiteMarketRepository(self.path, seed=self.seed)
        self.service = MarketsService(self.repo)
        self.serial = 0

    def refresh(self, results, *, operation=None, revision=None, as_of=date(2026, 11, 1)):
        self.serial += 1
        return self.service.refresh(
            results,
            expected_revision=self.service.state()["revision"] if revision is None else revision,
            operation_id=operation or f"contract-refresh-{self.serial}", as_of=as_of,
        )

    def manual_save(self, **fields):
        self.serial += 1
        state = self.service.state()
        state["markets"][0].update(fields)
        return self.service.mutate(
            action="save", expected_revision=state["revision"],
            operation_id=f"contract-manual-{self.serial}", reason="Correzione dal pannello",
            actor="test-owner", state=state,
        )

    def test_documented_new_value_replaces_existing_and_preserves_context(self):
        public_before = self.service.catalogue()
        before = self.service.state()
        result = self.refresh([source_result(observation({"place": "Piazza nuova"}))])
        market = result["markets"][0]
        self.assertEqual(market["place"], "Piazza nuova")
        for field in ("scheduleNote", "internalNotes", "descriptionFur", "auditNote"):
            self.assertEqual(market[field], before["markets"][0][field])
        self.assertEqual(result["drafts"], before["drafts"])
        self.assertEqual(result["dates"], before["dates"])
        self.assertEqual(self.service.catalogue(), public_before)
        self.assertEqual(result["publishedRevision"], before["publishedRevision"])

    def test_old_value_and_grounding_remain_in_history_and_immutable_snapshot(self):
        excerpt = "Dal 1 novembre il mercato si sposta in Piazza nuova."
        self.refresh([source_result(observation({"place": "Piazza nuova"}, excerpt=excerpt))])
        audit = json.dumps(self.service.history()["audit"], ensure_ascii=False)
        for value in ("Piazza", "Piazza nuova", SOURCE, excerpt):
            self.assertIn(value, audit)
        with closing(sqlite3.connect(self.path)) as connection:
            payload = connection.execute("SELECT payload FROM revisions WHERE revision=0").fetchone()[0]
        original = json.loads(payload)
        self.assertEqual(original["state"]["markets"][0]["place"], "Piazza")
        self.assertEqual(original["state"]["drafts"], self.seed["drafts"])
        restarted = MarketsService(SQLiteMarketRepository(self.path))
        self.assertEqual(restarted.state()["markets"][0]["place"], "Piazza nuova")

    def test_same_fact_does_not_undo_a_later_manual_correction(self):
        first = observation({"place": "Piazza nuova"})
        self.refresh([source_result(first)])
        self.manual_save(place="Piazza corretta dal proprietario")
        repeated = copy.deepcopy(first)
        repeated["retrievedAt"] = "2026-11-02T10:00:00Z"
        repeated["contentHash"] = "a" * 64  # Unrelated page changes are not a new fact.
        result = self.refresh([source_result(repeated)], as_of=date(2026, 11, 2))
        self.assertEqual(result["markets"][0]["place"], "Piazza corretta dal proprietario")

    def test_changed_documented_fact_supersedes_even_a_manual_correction(self):
        self.refresh([source_result(observation({"place": "Piazza nuova"}))])
        self.manual_save(place="Piazza corretta dal proprietario")
        later = observation({"place": "Sede definitiva"}, updated="2026-11-03")
        later["retrievedAt"] = "2026-11-03T10:00:00Z"
        result = self.refresh([source_result(later)], as_of=date(2026, 11, 3))
        self.assertEqual(result["markets"][0]["place"], "Sede definitiva")
        audit = json.dumps(result["audit"], ensure_ascii=False)
        self.assertIn("Piazza corretta dal proprietario", audit)
        self.assertIn("Sede definitiva", audit)
        self.assertEqual(result["markets"][0]["internalNotes"], self.seed["markets"][0]["internalNotes"])

    def test_older_source_version_does_not_roll_back_newer_fact(self):
        self.refresh([source_result(observation({"place": "Sede corrente"}))])
        old = observation({"place": "Vecchia sede riproposta"}, updated="2026-10-01")
        old["retrievedAt"] = "2026-11-02T10:00:00Z"
        result = self.refresh([source_result(old)], as_of=date(2026, 11, 2))
        self.assertEqual(result["markets"][0]["place"], "Sede corrente")

    def test_first_source_older_than_existing_verification_does_not_replace_current_fact(self):
        result = self.refresh([source_result(observation({"place": "Sede storica"},
                                                        updated="2026-10-01"))])
        self.assertEqual(result["markets"][0]["place"], self.seed["markets"][0]["place"])

    def test_malformed_source_result_is_isolated_from_other_markets(self):
        seed = copy.deepcopy(self.seed)
        seed["markets"].append({**copy.deepcopy(seed["markets"][0]),
                                "id": "M002", "name": "Secondo mercato"})
        repository = SQLiteMarketRepository(self.path.parent / "two-markets.sqlite3", seed=seed)
        service = MarketsService(repository)
        malformed = observation()
        malformed["editions"] = [None]
        valid = source_result(observation({"place": "Piazza del secondo mercato"}))
        valid["marketId"] = "M002"
        result = service.refresh([source_result(malformed), valid], expected_revision=0,
                                 operation_id="contract-isolated-result", as_of=date(2026, 11, 1))
        markets = {market["id"]: market for market in result["markets"]}
        self.assertEqual(markets["M001"]["place"], self.seed["markets"][0]["place"])
        self.assertEqual(markets["M002"]["place"], "Piazza del secondo mercato")

    def test_conflicting_sources_leave_current_value_unchanged(self):
        result = self.refresh([source_result(
            observation({"place": "Piazza A"}),
            observation({"place": "Piazza B"}, source=SECOND_SOURCE),
        )])
        self.assertEqual(result["markets"][0]["place"], self.seed["markets"][0]["place"])

    def test_known_calendar_conflict_preserves_dates_cadence_and_validity_but_allows_other_facts(self):
        for index, (evidence_status, quality) in enumerate((("conflict", "Da verificare"),
                                                          ("unverified", "Conflitto"))):
            with self.subTest(evidence_status=evidence_status, quality=quality):
                self.manual_save(evidenceStatus=evidence_status, quality=quality,
                                 cadence="Date da verificare", weekdaysIso=[],
                                 auditNote="La lista automatica contraddice la descrizione della fonte.")
                before = self.service.state()
                incoming = {"sourceKey": "conflicting-calendar-edition", "date": "2026-11-08",
                            "previousDate": "2026-11-01", "status": "published", "source": SOURCE}
                result = self.refresh([source_result(observation({
                    "place": f"Nuova sede documentata {index}", "cadence": "Ogni domenica",
                    "weekdaysIso": [7], "validFrom": "2026-11-01", "validThrough": "2027-12-31",
                }, editions=[incoming]))])
                market = result["markets"][0]
                self.assertEqual(market["place"], f"Nuova sede documentata {index}")
                for field in ("cadence", "weekdaysIso", "validFrom", "validThrough", "auditNote", "scheduleNote"):
                    self.assertEqual(market.get(field), before["markets"][0].get(field))
                self.assertEqual(result["dates"], before["dates"])
                self.assertIn("known_calendar_conflict", result["automation"]["reports"][0]["issues"])

    def test_less_specific_source_keeps_market_address_details(self):
        detailed_place = "Villa Manin, Passariano; Esedra e piazza Tonda"
        detailed_directions = "Villa Manin, Passariano; Esedra e piazza Tonda, Codroipo"
        self.manual_save(place=detailed_place, directionsQuery=detailed_directions)
        for place, directions in (("Villa Manin", "Villa Manin, Codroipo"), ("Passariano", "Codroipo")):
            with self.subTest(place=place, directions=directions):
                result = self.refresh([source_result(observation({
                    "place": place, "directionsQuery": directions, "hours": "09:00–18:00",
                }))])
                market = result["markets"][0]
                self.assertEqual(market["place"], detailed_place)
                self.assertEqual(market["directionsQuery"], detailed_directions)
                self.assertEqual(market["hours"], "09:00–18:00")
                issues = result["automation"]["reports"][0]["issues"]
                self.assertIn("less_specific_source:market:place", issues)
                self.assertIn("less_specific_source:market:directionsQuery", issues)

    def test_generic_edition_venue_does_not_override_more_specific_market_location(self):
        detailed_place = "Villa Manin, Passariano; Esedra e piazza Tonda"
        self.manual_save(place=detailed_place)
        incoming = {"sourceKey": "edition-with-generic-venue", "date": "2026-11-08",
                    "previousDate": "2026-11-01", "status": "published", "source": SOURCE,
                    "venue": {"place": "Villa Manin", "directionsQuery": "Villa Manin"}}
        result = self.refresh([source_result(observation(editions=[incoming]))])
        edition = result["dates"][0]
        self.assertEqual(edition["id"], "edition-one")
        self.assertEqual(edition["date"], "2026-11-08")
        self.assertNotIn("venue", edition)
        self.assertEqual(edition["publicReason"], "Accesso dal lato sud.")
        self.assertEqual(result["markets"][0]["place"], detailed_place)

    def test_different_documented_location_replaces_old_detailed_address(self):
        self.manual_save(place="Villa Manin, Passariano; Esedra e piazza Tonda")
        result = self.refresh([source_result(observation({"place": "Piazza Libertà, centro cittadino"}))])
        self.assertEqual(result["markets"][0]["place"], "Piazza Libertà, centro cittadino")
        self.assertIn("Villa Manin, Passariano; Esedra e piazza Tonda", json.dumps(result["audit"], ensure_ascii=False))

    def test_source_considerations_survive_later_observations_without_replacing_editorial_notes(self):
        excerpt = "La data di dicembre potrebbe cambiare per esigenze comunali."
        first = observation()
        first["evidence"].append({"field": "calendarConsiderations", "value": [excerpt], "excerpt": excerpt})
        self.refresh([source_result(first)])
        repeated = copy.deepcopy(first)
        repeated["retrievedAt"] = "2026-11-02T10:00:00Z"
        self.refresh([source_result(repeated)], as_of=date(2026, 11, 2))
        later = observation()
        later["retrievedAt"] = "2026-11-03T10:00:00Z"
        result = self.refresh([source_result(later)], as_of=date(2026, 11, 3))
        saved = self.repo.read()["refreshLedger"]["M001"]["considerations"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["excerpt"], excerpt)
        self.assertEqual(saved[0]["sourceUrl"], SOURCE)
        self.assertEqual(saved[0]["firstSeen"], "2026-11-01")
        self.assertEqual(saved[0]["lastSeen"], "2026-11-02")
        self.assertEqual(result["automation"]["reports"][0]["considerations"], saved)
        self.assertIn(excerpt, json.dumps(result["audit"], ensure_ascii=False))
        for field in ("scheduleNote", "internalNotes", "auditNote"):
            self.assertEqual(result["markets"][0][field], self.seed["markets"][0][field])

    def test_conflicting_edition_dates_do_not_apply_a_venue_to_the_wrong_date(self):
        before = self.service.state()["dates"]
        first = {"sourceKey": "organizer-one", "date": "2026-11-08",
                 "previousDate": "2026-11-01", "status": "published", "source": SOURCE,
                 "venue": {"place": "Piazza riservata all'edizione dell'otto"}}
        second = {"sourceKey": "organizer-two", "date": "2026-11-15",
                  "previousDate": "2026-11-01", "status": "published", "source": SECOND_SOURCE}
        result = self.refresh([source_result(observation(editions=[first]),
                                            observation(editions=[second], source=SECOND_SOURCE))])
        self.assertEqual(result["dates"], before)

    def test_conflicting_confirmation_and_cancellation_do_not_create_confirmed_edition(self):
        before = self.service.state()["dates"]
        first = {"sourceKey": "new-edition-one", "date": "2026-11-22",
                 "status": "published", "source": SOURCE}
        second = {"sourceKey": "new-edition-two", "date": "2026-11-22",
                  "status": "cancelled", "source": SECOND_SOURCE}
        result = self.refresh([source_result(observation(editions=[first]),
                                            observation(editions=[second], source=SECOND_SOURCE))])
        self.assertEqual(result["dates"], before)

    def test_failed_fetch_and_empty_observation_never_remove_data_or_extend_validity(self):
        before = self.service.state()
        self.refresh([source_result(issues=["source_unavailable"])])
        result = self.refresh([source_result(observation())])
        self.assertEqual(result["dates"], before["dates"])
        self.assertEqual(result["drafts"], before["drafts"])
        market = result["markets"][0]
        for field in ("place", "scheduleNote", "internalNotes", "validThrough", "checked", "status"):
            self.assertEqual(market[field], before["markets"][0][field])

    def test_explicit_move_keeps_edition_identity_and_previous_date(self):
        moved = {"sourceKey": "stable-organizer-edition", "date": "2026-11-08",
                 "previousDate": "2026-11-01", "status": "published", "source": SOURCE}
        result = self.refresh([source_result(observation(editions=[moved]))])
        self.assertEqual(len(result["dates"]), 1)
        edition = result["dates"][0]
        self.assertEqual(edition["id"], "edition-one")
        self.assertEqual(edition["date"], "2026-11-08")
        self.assertIn("2026-11-01", edition["legacyDates"])
        self.assertEqual(edition["publicReason"], "Accesso dal lato sud.")

    def test_empty_later_calendar_does_not_remove_existing_editions(self):
        self.refresh([source_result(observation(editions=[{
            "sourceKey": "stable-organizer-edition", "date": "2026-11-01",
            "status": "published", "source": SOURCE,
        }]))])
        before = self.service.state()["dates"]
        result = self.refresh([source_result(observation())])
        self.assertEqual(result["dates"], before)

    def test_archived_market_is_not_reactivated_by_a_source(self):
        self.manual_save(status="archived")
        result = self.refresh([source_result(observation({"place": "Piazza nuova"}))])
        self.assertEqual(result["markets"][0]["status"], "archived")

    def test_manual_save_cannot_delete_or_forge_source_bindings_and_refresh_ledger(self):
        self.refresh([source_result(observation(editions=[{
            "sourceKey": "stable-organizer-edition", "date": "2026-11-01",
            "status": "published", "source": SOURCE,
        }]))])
        before = self.repo.read()
        state = self.service.state()
        state["automation"] = {"changes": 9999, "publicationEnabled": True}
        state["refreshLedger"] = {"M001": {"sources": {}}}
        state["dates"][0]["refreshSourceKeys"] = [{"sourceUrl": SECOND_SOURCE,
                                                  "sourceKey": "forged-edition"}]
        self.service.mutate(action="save", expected_revision=state["revision"],
                            operation_id="contract-forged-metadata", reason="Modifica manuale",
                            actor="test-owner", state=state)
        record = self.repo.read()
        self.assertEqual(record["refreshLedger"], before["refreshLedger"])
        self.assertEqual(record["automation"], before["automation"])
        self.assertEqual(record["state"]["dates"][0]["refreshSourceKeys"],
                         before["state"]["dates"][0]["refreshSourceKeys"])
        moved = {"sourceKey": "stable-organizer-edition", "date": "2026-11-08",
                 "status": "published", "source": SOURCE}
        result = self.refresh([source_result(observation(editions=[moved]))])
        self.assertEqual(len(result["dates"]), 1)
        self.assertEqual(result["dates"][0]["id"], "edition-one")
        self.assertEqual(result["dates"][0]["date"], "2026-11-08")

    def test_concurrent_save_is_not_overwritten_by_stale_refresh(self):
        expected = self.service.state()["revision"]
        self.manual_save(place="Correzione concorrente")
        with self.assertRaisesRegex(MarketError, "markets_revision_conflict"):
            self.refresh([source_result(observation({"place": "Nuova fonte"}))], revision=expected)
        self.assertEqual(self.service.state()["markets"][0]["place"], "Correzione concorrente")

    def test_retry_is_idempotent_and_changed_payload_cannot_reuse_operation(self):
        results = [source_result(observation({"place": "Nuova fonte"}))]
        first = self.refresh(results, operation="contract-replay-once", revision=0)
        restarted = MarketsService(SQLiteMarketRepository(self.path))
        replay = restarted.refresh(results, expected_revision=0,
                                   operation_id="contract-replay-once", as_of=date(2026, 11, 1))
        self.assertEqual(replay["revision"], first["revision"])
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(len(restarted.history()["audit"]), len(first["audit"]))
        with self.assertRaisesRegex(MarketError, "markets_operation_conflict"):
            self.refresh([source_result(observation({"place": "Altro dato"}))],
                         operation="contract-replay-once", revision=0)

    def test_firestore_refresh_commits_and_replays_after_lost_acknowledgement(self):
        database = FakeFirestore()
        repository = FirestoreMarketRepository(database)
        with patch("google.cloud.firestore.transactional", transactional):
            repository.initialize(self.seed)
            service = MarketsService(repository)
            before = service.catalogue()
            results = [source_result(observation({"place": "Nuova sede documentata"}))]
            database.fail_after = True
            with self.assertRaisesRegex(MarketError, "markets_storage_unavailable"):
                service.refresh(results, expected_revision=0, operation_id="firestore-refresh-replay",
                                as_of=date(2026, 11, 1))
            replay = service.refresh(results, expected_revision=0, operation_id="firestore-refresh-replay",
                                     as_of=date(2026, 11, 1))
            self.assertTrue(replay["idempotentReplay"])
            self.assertEqual(replay["revision"], 1)
            self.assertEqual(replay["markets"][0]["place"], "Nuova sede documentata")
            self.assertEqual(len(replay["audit"]), 1)
            self.assertEqual(replay["drafts"], self.seed["drafts"])
            self.assertEqual(service.catalogue(), before)

    def test_cli_cloud_job_cannot_fall_back_to_an_ephemeral_local_seed(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"CLOUD_RUN_JOB": "test-refresh"}, clear=True), \
                patch("app.markets.refresh_job.configured_repository") as configured, \
                redirect_stdout(output):
            result = refresh_main(["--apply"])
        configured.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(report["issue"], "markets_refresh_cloud_configuration_invalid")
        self.assertFalse(report["applied"])

    def test_cli_missing_local_archive_does_not_initialize_a_seed(self):
        path = self.path.parent / "never-created.sqlite3"
        output = io.StringIO()
        environment = {"MARKETS_STORAGE": "sqlite", "MARKETS_SQLITE_PATH": str(path)}
        with patch.dict(os.environ, environment, clear=True), \
                patch("app.markets.refresh_job.configured_repository") as configured, \
                redirect_stdout(output):
            result = refresh_main(["--apply"])
        configured.assert_not_called()
        self.assertFalse(path.exists())
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())["issue"], "markets_refresh_archive_missing")

    def test_cli_lost_commit_response_does_not_report_a_certain_no_write(self):
        output = io.StringIO()
        environment = {"MARKETS_STORAGE": "sqlite", "MARKETS_SQLITE_PATH": str(self.path)}
        with patch.dict(os.environ, environment, clear=True), \
                patch("app.markets.refresh_job.configured_repository", return_value=self.repo), \
                patch("app.markets.refresh_job.run", side_effect=MarketError("markets_storage_unavailable", 503)), \
                redirect_stdout(output):
            result = refresh_main(["--apply"])
        report = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertIsNone(report["applied"])
        self.assertTrue(report["commitUnknown"])

    def test_cli_without_confirmed_facts_is_not_a_green_refresh(self):
        output = io.StringIO()
        environment = {"MARKETS_STORAGE": "sqlite", "MARKETS_SQLITE_PATH": str(self.path)}
        with patch.dict(os.environ, environment, clear=True), \
                patch("app.markets.refresh_job.configured_repository", return_value=self.repo), \
                patch("app.markets.refresh_job.run", return_value={"status": "completed_without_facts"}), \
                redirect_stdout(output):
            result = refresh_main([])
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
