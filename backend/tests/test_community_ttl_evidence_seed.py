import io
import json
import time
import unittest
from contextlib import redirect_stdout

from tools import seed_community_ttl_evidence_live as ttl_seed


TAGGED_API_BASE = (
    "https://qa---meteofriul-api-contract.a.run.app/api"
)


class FakeSnapshot:
    def __init__(self, payload=None):
        self.exists = payload is not None
        self._payload = dict(payload or {})

    def to_dict(self):
        return dict(self._payload)


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def get(self, transaction=None):
        return FakeSnapshot(self.collection.records.get(self.document_id))

    def delete(self):
        raise AssertionError("cleanup must use a Firestore transaction")


class FakeCollection:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)


class FakeBatch:
    def __init__(self, db):
        self.db = db
        self.creates = []

    def create(self, document, payload):
        self.creates.append((document, dict(payload)))

    def commit(self):
        callback = self.db.before_batch_commit
        self.db.before_batch_commit = None
        if callback is not None:
            callback()
        if any(
            document.document_id in document.collection.records
            for document, _payload in self.creates
        ):
            raise RuntimeError("already_exists")
        for document, payload in self.creates:
            document.collection.records[document.document_id] = dict(payload)
            self.db.history.append((
                "create",
                document.collection.name,
                document.document_id,
            ))


class FakeTransaction:
    def __init__(self, db):
        self.db = db
        self.deletes = []

    def delete(self, document):
        self.deletes.append(document)

    def commit(self):
        callback = self.db.before_transaction_commit
        self.db.before_transaction_commit = None
        if callback is not None:
            callback()
            raise RuntimeError("transaction_conflict")
        for document in self.deletes:
            document.collection.records.pop(document.document_id, None)
            self.db.history.append((
                "transaction_delete",
                document.collection.name,
                document.document_id,
            ))


class FakeFirestore:
    def __init__(self, project="meteo-friul"):
        self.project = project
        self.collections = {}
        self.history = []
        self.before_batch_commit = None
        self.before_transaction_commit = None

    def collection(self, name):
        return self.collections.setdefault(
            name,
            FakeCollection(self, name),
        )

    def batch(self):
        return FakeBatch(self)

    def transaction(self):
        return FakeTransaction(self)


def immediate_transaction(operation):
    def execute(transaction):
        result = operation(transaction)
        transaction.commit()
        return result

    return execute


class PublicSurfaceProbe:
    def __init__(self, db):
        self.db = db
        self.phases = []

    def __call__(self, phase, identity, now):
        self.phases.append(phase)
        reports = self.db.collection(ttl_seed.REPORTS_COLLECTION).records
        for document_id, payload in reports.items():
            is_target = (
                document_id == identity.report_id
                or payload.get("group_id") == identity.group_id
            )
            is_visible = (
                ttl_seed._timestamp(payload.get("expires_at_timestamp")) > now
                and not bool(payload.get("moderation_hidden"))
            )
            if is_target and is_visible:
                raise ttl_seed.CommunityTtlEvidenceSeedError(
                    "public_report_visible"
                )


class CommunityTtlEvidenceSeedTests(unittest.TestCase):
    RUN_TOKEN = "a" * 24

    def setUp(self):
        self.now = time.time()
        self.firestore = FakeFirestore()
        self.public_probe = PublicSurfaceProbe(self.firestore)

    def run_seed(self, **overrides):
        arguments = {
            "api_base": TAGGED_API_BASE,
            "apply": True,
            "now": self.now,
            "run_token": self.RUN_TOKEN,
            "transactional_decorator": immediate_transaction,
            "evidence_emitter": lambda _payload: None,
            "sleep_fn": lambda _seconds: None,
            "public_probe": self.public_probe,
        }
        arguments.update(overrides)
        return ttl_seed.run_seed(self.firestore, **arguments)

    def assert_no_seed_documents(self):
        for collection in (
            ttl_seed.REPORTS_COLLECTION,
            ttl_seed.COOLDOWNS_COLLECTION,
            ttl_seed.CONFIRMATIONS_COLLECTION,
            ttl_seed.RATE_LIMITS_COLLECTION,
            ttl_seed.REPUTATION_COLLECTION,
            ttl_seed.REPUTATION_AWARDS_COLLECTION,
        ):
            self.assertEqual(
                self.firestore.collection(collection).records,
                {},
                collection,
            )

    def test_preview_is_read_only_and_probes_public_surface(self):
        result = self.run_seed(apply=False)

        self.assertEqual(result["mode"], "dry-run")
        self.assertFalse(result["applied"])
        self.assertEqual(self.public_probe.phases, ["before"])
        self.assertEqual(self.firestore.history, [])
        self.assert_no_seed_documents()

    def test_apply_holds_six_valid_private_samples_then_cleans(self):
        ready_payloads = []

        def inspect_ready(payload):
            ready_payloads.append(dict(payload))
            identity = ttl_seed._qa_identity(self.RUN_TOKEN, now=self.now)
            refs = ttl_seed._document_refs(self.firestore, identity)
            ttl_seed._require_owned_seed(
                refs,
                identity,
                now=self.now,
            )
            report = refs["report"].get().to_dict()
            self.assertTrue(report["moderation_hidden"])
            self.assertLess(
                ttl_seed._timestamp(report["expires_at_timestamp"]),
                self.now,
            )

        result = self.run_seed(
            hold_seconds=11,
            evidence_emitter=inspect_ready,
        )

        self.assertEqual(result["temporary_collection_count"], 6)
        self.assertEqual(result["public_absence_check_count"], 6)
        self.assertEqual(
            self.public_probe.phases,
            [
                "before",
                "after_seed",
                "during_hold",
                "during_hold",
                "during_hold",
                "after_cleanup",
            ],
        )
        self.assertEqual(len(ready_payloads), 1)
        serialized = json.dumps([ready_payloads[0], result], sort_keys=True)
        self.assertNotIn(self.RUN_TOKEN, serialized)
        self.assertNotIn("qa_ttl_evidence_marker", serialized)
        self.assertFalse(ready_payloads[0]["contains_document_identifiers"])
        self.assertFalse(result["contains_private_data"])
        self.assert_no_seed_documents()
        self.assertEqual(
            len([
                row for row in self.firestore.history
                if row[0] == "transaction_delete"
            ]),
            6,
        )

    def test_evidence_emitter_crash_still_cleans_and_checks_after(self):
        def crash(_payload):
            raise RuntimeError("simulated_crash")

        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "evidence_ready_emit_failed",
        ):
            self.run_seed(evidence_emitter=crash)

        self.assertEqual(
            self.public_probe.phases,
            ["before", "after_seed", "after_cleanup"],
        )
        self.assert_no_seed_documents()

    def test_hold_crash_still_cleans_and_checks_after(self):
        def crash(_seconds):
            raise RuntimeError("simulated_hold_crash")

        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "evidence_hold_failed",
        ):
            self.run_seed(hold_seconds=5, sleep_fn=crash)

        self.assertEqual(
            self.public_probe.phases,
            ["before", "after_seed", "after_cleanup"],
        )
        self.assert_no_seed_documents()

    def test_create_race_never_overwrites_or_deletes_non_owned_document(self):
        identity = ttl_seed._qa_identity(self.RUN_TOKEN, now=self.now)
        foreign = {
            "expires_at_timestamp": ttl_seed._datetime(self.now + 300),
            "updated_at": ttl_seed._datetime(self.now),
        }

        def collide():
            self.firestore.collection(
                ttl_seed.COOLDOWNS_COLLECTION
            ).records[identity.client_key] = dict(foreign)

        self.firestore.before_batch_commit = collide
        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "qa_document_ownership_lost",
        ):
            self.run_seed()

        stored = self.firestore.collection(
            ttl_seed.COOLDOWNS_COLLECTION
        ).records[identity.client_key]
        self.assertEqual(stored, foreign)
        self.assertFalse(any(row[0] == "transaction_delete" for row in self.firestore.history))

    def test_cleanup_commit_race_preserves_replacement(self):
        identity = ttl_seed._qa_identity(self.RUN_TOKEN, now=self.now)
        foreign = {
            "expires_at_timestamp": ttl_seed._datetime(self.now + 300),
            "updated_at": ttl_seed._datetime(self.now),
        }

        def replace_before_commit():
            self.firestore.collection(
                ttl_seed.COOLDOWNS_COLLECTION
            ).records[identity.client_key] = dict(foreign)

        self.firestore.before_transaction_commit = replace_before_commit
        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "qa_cleanup_transaction_failed",
        ):
            self.run_seed()

        self.assertEqual(
            self.firestore.collection(
                ttl_seed.COOLDOWNS_COLLECTION
            ).records[identity.client_key],
            foreign,
        )
        self.assertFalse(any(row[0] == "transaction_delete" for row in self.firestore.history))

    def test_late_public_collision_is_detected_and_never_deleted(self):
        identity = ttl_seed._qa_identity(self.RUN_TOKEN, now=self.now)
        late_public = {
            "id": identity.report_id,
            "group_id": identity.group_id,
            "created_at_timestamp": ttl_seed._datetime(self.now),
            "expires_at_timestamp": ttl_seed._datetime(self.now + 3600),
            "moderation_hidden": False,
        }

        def replace_report(_seconds):
            self.firestore.collection(
                ttl_seed.REPORTS_COLLECTION
            ).records[identity.report_id] = dict(late_public)

        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "public_report_visible",
        ):
            self.run_seed(hold_seconds=5, sleep_fn=replace_report)

        self.assertEqual(
            self.firestore.collection(
                ttl_seed.REPORTS_COLLECTION
            ).records[identity.report_id],
            late_public,
        )
        self.assertFalse(any(row[0] == "transaction_delete" for row in self.firestore.history))

    def test_public_payload_contract_detects_report_group_and_nested_ids(self):
        identity = ttl_seed._qa_identity(self.RUN_TOKEN, now=self.now)
        self.assertTrue(ttl_seed._public_payload_contains_identity(
            {"reports": [{"id": identity.report_id}]},
            identity,
        ))
        self.assertTrue(ttl_seed._public_payload_contains_identity(
            {"map_groups": [{"groupId": identity.group_id}]},
            identity,
        ))
        self.assertTrue(ttl_seed._public_payload_contains_identity(
            {"groups": [{"reportIds": [identity.report_id]}]},
            identity,
        ))
        self.assertFalse(ttl_seed._public_payload_contains_identity(
            {"reports": [], "map_groups": []},
            identity,
        ))

    def test_wrong_project_bad_endpoint_and_excessive_hold_fail_closed(self):
        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "firestore_project_mismatch",
        ):
            ttl_seed.run_seed(
                FakeFirestore(project="other-project"),
                api_base=TAGGED_API_BASE,
                apply=False,
                public_probe=lambda *_args: None,
            )
        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "tagged_api_base_invalid",
        ):
            self.run_seed(api_base="https://example.test/api")
        with self.assertRaisesRegex(
            ttl_seed.CommunityTtlEvidenceSeedError,
            "hold_seconds_out_of_bounds",
        ):
            self.run_seed(hold_seconds=121)
        self.assert_no_seed_documents()

    def test_main_outputs_aggregate_json_without_identifiers(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = ttl_seed.main(
                ["--api-base", TAGGED_API_BASE, "--apply"],
                db=self.firestore,
                now=self.now,
                run_token=self.RUN_TOKEN,
                transactional_decorator=immediate_transaction,
                public_probe=self.public_probe,
                sleep_fn=lambda _seconds: None,
            )

        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["event"], "community_ttl_evidence_seed_ready")
        self.assertEqual(rows[1]["event"], "community_ttl_evidence_seed_completed")
        self.assertNotIn(self.RUN_TOKEN, output.getvalue())
        self.assertNotIn("community-ttl-evidence-seed", output.getvalue())
        self.assert_no_seed_documents()


if __name__ == "__main__":
    unittest.main()
