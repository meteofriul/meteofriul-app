import copy
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.markets.model import MarketError, encode, initial_record, publication_errors, validate_state
from app.markets.repository import SQLiteMarketRepository, configured_repository
from app.markets.seed import edition_id, load_seed, prepare_seed
from app.markets.service import MarketsService


def small_seed():
    return {"schemaVersion": 2, "checked": "2026-10-30", "validThrough": "2026-12-31", "drafts": [],
            "markets": [{"id": "M001", "name": "Mercato di prova", "comune": "Udine", "group": "occasional",
                         "status": "published", "publicationReady": True, "evidenceStatus": "documented",
                         "url": "https://example.test/mercato", "checked": "2026-10-30", "quality": "Documentato",
                         "validThrough": "2026-12-31",
                         "place": "Piazza", "weekdays": [], "weekdaysIso": [], "titleAliases": [], "auditNote": "INTERNAL-NOTE"}],
            "dates": [{"id": "edition-one", "marketId": "M001", "date": "2026-11-01", "status": "published",
                       "source": "https://example.test/edizione", "legacyDates": []}]}


class MarketsArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="mf-markets-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "archive.sqlite3"
        self.service = MarketsService(SQLiteMarketRepository(self.path, seed=small_seed()))
        self.serial = 0

    def mutate(self, action="save", state=None, revision=None, operation=None, service=None):
        service = service or self.service
        self.serial += 1
        return service.mutate(action=action, expected_revision=service.state()["revision"] if revision is None else revision,
                              operation_id=operation or f"operation-{self.serial}", reason="Test documentato", actor="test-owner", state=state)

    def test_packaged_seed_is_deterministic_and_preserves_the_59_cases(self):
        seed = load_seed()
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(seed, prepare_seed(root))
        self.assertEqual(len(seed["markets"]), 60)
        self.assertEqual(len(seed["dates"]), 176)
        self.assertEqual(len(seed["drafts"]), 59)
        self.assertEqual(sum(item["tier"] == "complete" for item in seed["drafts"]), 13)
        self.assertEqual(sum(item["tier"] == "limited" for item in seed["drafts"]), 46)
        self.assertEqual(sum(bool(item["linkedMarketIds"]) for item in seed["drafts"]), 19)
        for draft in seed["drafts"]:
            self.assertEqual(draft["status"], "draft")
            self.assertFalse(draft["suggestedMarket"]["publicationReady"])
            self.assertEqual(draft["suggestedMarket"]["status"], "draft")
            self.assertTrue(all(item["status"] == "draft" for item in draft["suggestedDates"]))
            if draft["validated"]["kind"] != "regular":
                self.assertEqual(draft["suggestedMarket"]["group"], "occasional")
                self.assertEqual(draft["suggestedMarket"]["weekdays"], [])
        initial = initial_record(seed)
        self.assertEqual(len(initial["catalogue"]["markets"]), 53)
        self.assertEqual(publication_errors(seed, initial["catalogue"]), [])
        self.assertNotIn("drafts", initial["catalogue"])
        self.assertEqual(len({item["id"] for item in seed["dates"]}), 176)

    def test_seed_and_provenance_are_stable_across_windows_and_linux_newlines(self):
        root = Path(__file__).resolve().parents[2]
        expected = prepare_seed(root)
        with TemporaryDirectory(prefix="mf-market-seed-newlines-") as directory:
            copy_root = Path(directory)
            for entry in expected["provenance"].values():
                relative = entry["path"]
                target = copy_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((root / relative).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
            self.assertEqual(prepare_seed(copy_root), expected)

    def test_full_seed_round_trip_and_market_edit_preserve_all_59_drafts(self):
        seed = load_seed()
        self.assertEqual(validate_state(seed, seed), {
            **seed, "markets": [{**market, "weekdaysIso": sorted(set(market["weekdaysIso"])),
                                  "weekdays": [day % 7 for day in sorted(set(market["weekdaysIso"]))],
                                  "previousSourceUrls": [], "previousMunicipalities": []} for market in seed["markets"]],
        })
        service = MarketsService(SQLiteMarketRepository(self.path.parent / "full.sqlite3", seed=seed))
        original_public = service.catalogue()
        state = service.state()
        original_drafts = copy.deepcopy(state["drafts"])
        state["markets"][0]["place"] = "Sede di prova per verifica editoriale"
        saved = self.mutate(state=state, service=service)
        self.assertEqual(saved["markets"][0]["place"], "Sede di prova per verifica editoriale")
        self.assertEqual(saved["drafts"], original_drafts)
        self.assertEqual(service.catalogue(), original_public)
        restarted = MarketsService(SQLiteMarketRepository(self.path.parent / "full.sqlite3"))
        self.assertEqual(restarted.state()["drafts"], original_drafts)
        self.assertEqual(len(restarted.state()["drafts"]), 59)

    def test_all_59_prepared_practices_save_without_duplicate_market_or_edition_ids(self):
        seed = load_seed()
        service = MarketsService(SQLiteMarketRepository(self.path.parent / "prepared.sqlite3", seed=seed))
        original_public = service.catalogue()
        original_dates = {item["id"] for item in seed["dates"]}
        state = service.state()
        # Equivalent to the panel's preparePractice + replaceMarketInState:
        # preserve an existing identity and its dates, otherwise use its stable R-ID.
        for practice in seed["drafts"]:
            target = next((key for key in practice["linkedMarketIds"] if any(item["id"] == key for item in state["markets"])), None)
            identifier = target or "R-" + practice["id"]
            existing = next((item for item in state["markets"] if item["id"] == identifier), None)
            market = {**(existing or {}), **copy.deepcopy(practice["suggestedMarket"]), "id": identifier,
                      "researchId": practice["id"], "status": "draft", "publicationReady": False}
            editions = ([item for item in state["dates"] if item["marketId"] == identifier] if existing else
                        [{**copy.deepcopy(item), "marketId": identifier} for item in practice["suggestedDates"]])
            candidate = {
                "markets": [market if item["id"] == identifier else item for item in state["markets"]] if existing else state["markets"] + [market],
                "dates": [item for item in state["dates"] if item["marketId"] != identifier] + editions,
                "drafts": state["drafts"],
            }
            state = self.mutate(state=candidate, service=service)
        self.assertEqual(state["revision"], 59)
        self.assertEqual(len(state["markets"]), 100)
        self.assertEqual(len({item["id"] for item in state["markets"]}), 100)
        self.assertEqual(len({item["id"] for item in state["dates"]}), len(state["dates"]))
        self.assertTrue(original_dates.issubset({item["id"] for item in state["dates"]}))
        self.assertEqual(state["drafts"], seed["drafts"])
        self.assertEqual(service.catalogue(), original_public)
        self.mutate(action="publish", service=service)
        published = service.catalogue()
        self.assertEqual({item["id"] for item in published["markets"]}, {item["id"] for item in original_public["markets"]})
        self.assertEqual({item["id"] for item in published["dates"]}, {item["id"] for item in original_public["dates"]})
        self.assertEqual(published["tombstones"], [])

    def test_municipality_and_source_aliases_survive_moves_and_withdrawal(self):
        state = self.service.state()
        state["markets"][0].update(comune="Pordenone", url="https://example.test/nuova-sede")
        self.mutate(state=state)
        self.mutate(action="publish")
        identity = self.service.catalogue()["identities"][0]
        self.assertEqual(identity["comune"], "Pordenone")
        self.assertEqual(identity["municipalityAliases"], ["Udine"])
        self.assertIn("https://example.test/mercato", identity["sourceUrls"])
        state = self.service.state()
        state["markets"][0].update(comune="Cordenons", status="archived", previousMunicipalities=[])
        self.mutate(state=state)
        self.mutate(action="publish")
        identity = self.service.catalogue()["identities"][0]
        self.assertEqual(identity["municipalityAliases"], ["Pordenone", "Udine"])
        self.assertEqual(identity["status"], "archived")

    def test_save_is_durable_and_does_not_publish(self):
        state = self.service.state()
        state["markets"][0]["place"] = "Nuova piazza"
        self.mutate(state=state)
        restarted = MarketsService(SQLiteMarketRepository(self.path))
        self.assertEqual(restarted.state()["markets"][0]["place"], "Nuova piazza")
        self.assertEqual(restarted.catalogue()["markets"][0]["place"], "Piazza")
        self.assertEqual(restarted.state()["publishedRevision"], 0)

    def test_concurrent_instances_cannot_silently_overwrite(self):
        state = self.service.state()
        def save(index):
            service = MarketsService(SQLiteMarketRepository(self.path))
            try:
                return self.mutate(state=state, revision=0, operation=f"concurrent-{index}", service=service)["revision"]
            except MarketError as error:
                return error.detail["code"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save, [1, 2]))
        self.assertCountEqual(outcomes, [1, "markets_revision_conflict"])

    def test_lost_response_replay_survives_restart_and_hash_conflict(self):
        state = self.service.state()
        first = self.mutate(state=state, revision=0, operation="replay-request")
        restarted = MarketsService(SQLiteMarketRepository(self.path))
        replay = self.mutate(state=state, revision=0, operation="replay-request", service=restarted)
        self.assertEqual(first["revision"], replay["revision"])
        self.assertTrue(replay["idempotentReplay"])
        state["markets"][0]["place"] = "Altra piazza"
        with self.assertRaisesRegex(MarketError, "markets_operation_conflict"):
            self.mutate(state=state, revision=0, operation="replay-request", service=restarted)

    def test_date_move_preserves_id_and_suppresses_old_feed_date(self):
        state = self.service.state()
        state["dates"][0].update(date="2026-11-08", venue={"id": "venue-new", "place": "Nuova sede", "directionsQuery": "Nuova sede, Udine"})
        self.mutate(state=state)
        self.assertEqual(self.service.catalogue()["dates"][0]["date"], "2026-11-01")
        self.mutate(action="publish")
        catalogue = self.service.catalogue()
        self.assertEqual(catalogue["dates"][0]["id"], "edition-one")
        self.assertEqual(catalogue["dates"][0]["legacyDates"], ["2026-11-01"])
        self.assertEqual(catalogue["dates"][0]["venue"]["directionsQuery"], "Nuova sede, Udine")
        self.assertEqual(catalogue["tombstones"][0]["date"], "2026-11-01")
        self.assertEqual(catalogue["tombstones"][0]["replacementDate"], "2026-11-08")
        self.assertTrue(any(item["legacyId"] == "market:M001:2026-11-01" for item in catalogue["editionAliases"]))

    def test_archive_and_restore_are_new_public_revisions(self):
        state = self.service.state()
        state["markets"][0]["status"] = "archived"
        self.mutate(state=state)
        self.mutate(action="publish")
        archived = self.service.catalogue()
        self.assertEqual(archived["markets"], [])
        self.assertEqual(archived["identities"][0]["marketId"], "M001")
        self.assertEqual(archived["tombstones"][0]["status"], "archived")
        state = self.service.state()
        state["markets"][0]["status"] = "published"
        self.mutate(state=state)
        self.mutate(action="publish")
        restored = self.service.catalogue()
        self.assertEqual(len(restored["markets"]), 1)
        self.assertEqual(restored["tombstones"], [])
        self.assertGreater(restored["revision"], archived["revision"])
        self.assertEqual(len(self.service.history()["audit"]), 4)

    def test_draft_market_and_edition_do_not_withdraw_previous_publication(self):
        original = self.service.catalogue()
        state = self.service.state()
        state["markets"][0].update(status="draft", name="Titolo non approvato", publicationReady=False)
        state["dates"][0].update(status="draft", date="2026-11-29")
        self.mutate(state=state)
        self.mutate(action="publish")
        current = self.service.catalogue()
        self.assertEqual(current["markets"], original["markets"])
        self.assertEqual(current["dates"], original["dates"])
        self.assertEqual(current["tombstones"], [])

    def test_new_draft_stays_private_and_publication_gate_is_enforced(self):
        state = self.service.state()
        new = {**state["markets"][0], "id": "NEW1", "name": "Altro mercato", "status": "draft", "publicationReady": False}
        state["markets"].append(new)
        self.mutate(state=state)
        self.mutate(action="publish")
        self.assertEqual(len(self.service.catalogue()["markets"]), 1)
        state = self.service.state()
        state["markets"][1]["status"] = "published"
        self.mutate(state=state)
        before = self.service.catalogue()
        with self.assertRaisesRegex(MarketError, "markets_publication_checks_required"):
            self.mutate(action="publish")
        self.assertEqual(self.service.catalogue(), before)

    def test_suspension_and_cancellation_have_tombstones(self):
        state = self.service.state()
        state["dates"][0]["status"] = "cancelled"
        self.mutate(state=state)
        self.mutate(action="publish")
        self.assertEqual(self.service.catalogue()["tombstones"][0]["status"], "cancelled")
        state = self.service.state()
        state["markets"][0]["status"] = "suspended"
        self.mutate(state=state)
        self.mutate(action="publish")
        self.assertEqual(self.service.catalogue()["markets"], [])
        self.assertTrue(any(item["status"] == "suspended" for item in self.service.catalogue()["tombstones"]))

    def test_publication_is_immutable_and_never_leaks_private_fields(self):
        public = self.service.catalogue()
        self.assertNotIn("INTERNAL-NOTE", encode(public).decode())
        self.assertNotIn("audit", public)
        self.assertNotIn("publicationReady", public["markets"][0])
        self.assertEqual(public["expiresAt"], "2026-12-31T23:00:00Z")
        self.assertEqual(self.service.catalogue(), public)

    def test_deletion_corruption_and_cloud_fallback_fail_closed(self):
        state = self.service.state()
        state["markets"] = []
        with self.assertRaisesRegex(MarketError, "markets_archive_instead_of_delete"):
            self.mutate(state=state)
        self.assertEqual(self.service.state()["revision"], 0)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE current_state SET checksum='corrupt'")
            db.commit()
        with self.assertRaisesRegex(MarketError, "markets_store_corrupt"):
            self.service.state()
        with patch.dict("os.environ", {"K_SERVICE": "deployed", "MARKETS_STORAGE": "sqlite"}):
            with self.assertRaisesRegex(MarketError, "markets_storage_configuration_invalid"):
                configured_repository()

    def test_iso_sunday_and_invalid_venue_are_validated(self):
        state = self.service.state()
        state["markets"][0]["weekdaysIso"] = [7]
        saved = self.mutate(state=state)
        self.assertEqual(saved["markets"][0]["weekdays"], [0])
        state["dates"][0]["venue"] = {"id": "venue", "place": "Piazza", "lat": 120, "lon": 12}
        with self.assertRaisesRegex(MarketError, "markets_invalid_venue_coordinates"):
            self.mutate(state=state)

    def test_two_cold_starts_initialize_one_archive(self):
        path = self.path.parent / "cold.sqlite3"
        def create(_index):
            return SQLiteMarketRepository(path, seed=small_seed()).read()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, [1, 2]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]["revision"], 0)

    def test_2027_extension_does_not_extend_other_market_evidence(self):
        state = self.service.state()
        other = {**state["markets"][0], "id": "M002", "name": "Secondo mercato", "group": "regular", "weekdaysIso": [7]}
        state["markets"].append(other)
        state["markets"][0]["validThrough"] = "2027-02-28"
        state["dates"][0]["date"] = "2027-02-07"
        self.mutate(state=state)
        self.mutate(action="publish")
        catalogue = self.service.catalogue()
        self.assertEqual(catalogue["validThrough"], "2027-02-28")
        self.assertEqual(catalogue["markets"][1]["validThrough"], "2026-12-31")


if __name__ == "__main__":
    unittest.main()
