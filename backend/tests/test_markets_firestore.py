"""Provider contract with a transactional fake. Does not access cloud resources."""
import copy
import unittest
from unittest.mock import patch

from app.markets.model import MarketError
from app.markets.repository import FirestoreMarketRepository
from app.markets.bootstrap import main as bootstrap
from app.markets.service import MarketsService
from tests.test_markets_archive import small_seed


class Snapshot:
    def __init__(self, value):
        self.value = copy.deepcopy(value)
        self.exists = value is not None

    def to_dict(self):
        return copy.deepcopy(self.value)


class Reference:
    def __init__(self, db, key):
        self.db, self.key = db, key

    def get(self, *, transaction=None, timeout=None):
        if transaction and transaction.writes:
            raise AssertionError("read after write inside transaction")
        return Snapshot(self.db.documents.get(self.key))


class Collection:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def document(self, name):
        return Reference(self.db, self.name + "/" + name)


class Transaction:
    def __init__(self, db):
        self.db, self.writes = db, []

    def create(self, reference, value):
        self.writes.append(("create", reference.key, copy.deepcopy(value)))

    def set(self, reference, value):
        self.writes.append(("set", reference.key, copy.deepcopy(value)))

    def commit(self):
        if self.db.fail_before:
            self.db.fail_before = False
            raise OSError("failed commit")
        proposed = copy.deepcopy(self.db.documents)
        for operation, key, value in self.writes:
            if operation == "create" and key in proposed:
                raise AssertionError("immutable revision overwritten")
            proposed[key] = value
        self.db.documents = proposed
        if self.db.fail_after:
            self.db.fail_after = False
            raise OSError("lost acknowledgement")


class FakeFirestore:
    def __init__(self):
        self.documents = {}
        self.fail_before = self.fail_after = False

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return Transaction(self)


def transactional(function):
    def run(transaction):
        result = function(transaction)
        transaction.commit()
        return result
    return run


class MarketsFirestoreTests(unittest.TestCase):
    def setUp(self):
        decorator = patch("google.cloud.firestore.transactional", transactional)
        decorator.start()
        self.addCleanup(decorator.stop)
        self.db = FakeFirestore()
        self.repo = FirestoreMarketRepository(self.db)

    def command(self, service, state, operation="firestore-save"):
        return service.mutate(action="save", expected_revision=0, operation_id=operation,
                              reason="Verifica persistenza", actor="fake-owner", state=state)

    def test_runtime_does_not_initialize_a_missing_archive(self):
        with self.assertRaisesRegex(MarketError, "markets_archive_not_initialized"):
            self.repo.read()
        self.assertEqual(self.db.documents, {})

    def test_chunked_revisions_are_immutable_and_replay_survives_restart(self):
        seed = small_seed()
        seed["markets"][0]["internalNotes"] = "à" * 210_000
        self.repo.initialize(seed)
        self.assertGreater(self.db.documents["markets_archive/current"]["chunkCount"], 1)
        old_chunks = {key: copy.deepcopy(value) for key, value in self.db.documents.items() if "revision-0-" in key}
        service = MarketsService(self.repo)
        state = service.state()
        state["markets"][0]["place"] = "Nuova piazza"
        saved = self.command(service, state)
        self.assertEqual(saved["revision"], 1)
        restarted = MarketsService(FirestoreMarketRepository(self.db))
        replay = self.command(restarted, state)
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(restarted.state()["markets"][0]["place"], "Nuova piazza")
        self.assertEqual(old_chunks, {key: value for key, value in self.db.documents.items() if key in old_chunks})
        with self.assertRaisesRegex(MarketError, "markets_revision_conflict"):
            self.command(restarted, state, "second-operation")

    def test_failed_commit_does_not_advance_pointer_or_receipt(self):
        self.repo.initialize(small_seed())
        service = MarketsService(self.repo)
        before = copy.deepcopy(self.db.documents)
        self.db.fail_before = True
        with self.assertRaisesRegex(MarketError, "markets_storage_unavailable"):
            self.command(service, service.state())
        self.assertEqual(self.db.documents, before)
        self.assertEqual(service.state()["revision"], 0)

    def test_lost_commit_acknowledgement_reconciles_from_durable_receipt(self):
        self.repo.initialize(small_seed())
        service = MarketsService(self.repo)
        state = service.state()
        self.db.fail_after = True
        with self.assertRaisesRegex(MarketError, "markets_storage_unavailable"):
            self.command(service, state)
        restarted = MarketsService(FirestoreMarketRepository(self.db))
        replay = self.command(restarted, state)
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(replay["revision"], 1)
        self.assertEqual(len(replay["audit"]), 1)

    def test_corrupt_chunk_and_reinitialization_fail_closed(self):
        self.repo.initialize(small_seed())
        with self.assertRaisesRegex(MarketError, "markets_archive_already_initialized"):
            self.repo.initialize(small_seed())
        self.db.documents["markets_archive/revision-0-0"]["payload"] = b"corrupt"
        with self.assertRaisesRegex(MarketError, "markets_store_corrupt"):
            self.repo.read()

    def test_bootstrap_rejects_mismatched_project_before_loading_any_provider(self):
        with patch.dict("os.environ", {"MARKETS_STORAGE": "firestore", "MARKETS_FIREBASE_PROJECT_ID": "expected-project"}), patch(
            "app.markets.bootstrap.configured_repository",
        ) as provider:
            with self.assertRaisesRegex(MarketError, "markets_bootstrap_configuration_mismatch"):
                bootstrap(["--confirm-project", "another-project"])
        provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
