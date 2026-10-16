import hashlib
import unittest
from datetime import datetime, timezone

from app.repositories.community import (
    CommunityCooldownActive,
    CommunityConfirmationCapacityReached,
    CommunityGroupHidden,
    CommunityRepository,
    CommunityRepositoryUnavailable,
    CommunitySelfConfirmationNotAllowed,
    CommunitySourceBlocked,
    MAX_REPORTS,
    REPUTATION_RETENTION_SECONDS,
)


class FakeSnapshot:
    def __init__(self, payload=None):
        self.payload = payload
        self.exists = payload is not None

    def to_dict(self):
        return dict(self.payload or {})


class FakeStreamDocument(FakeSnapshot):
    def __init__(self, document_id, payload):
        super().__init__(payload)
        self.id = document_id


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    def set(self, payload, merge=False):
        current = self.collection.records.get(self.id, {}) if merge else {}
        self.collection.records[self.id] = {**current, **dict(payload)}

    def update(self, payload):
        if self.id not in self.collection.records:
            raise RuntimeError("firestore document not found")
        current = self.collection.records[self.id]
        self.collection.records[self.id] = {**current, **dict(payload)}

    def get(self, transaction=None):
        if transaction is not None and not transaction.active:
            raise ValueError("Transaction not in progress")
        self.collection.firestore.read_log.append(
            (self.collection, self.id, transaction)
        )
        if self.collection.firestore.fail_reads:
            raise RuntimeError("firestore read failed")
        return FakeSnapshot(self.collection.records.get(self.id))

    def delete(self):
        self.collection.records.pop(self.id, None)


class FakeQuery:
    def __init__(self, collection):
        self.collection = collection
        self.filters = []
        self.limit_count = None
        self.order_direction = None
        self.order_field = None

    def where(self, field_path=None, op_string=None, value=None, *, filter=None):
        if filter is not None:
            field_path = filter.field_path
            op_string = filter.op_string
            value = filter.value
        self.filters.append((field_path, op_string, value))
        return self

    def order_by(self, field_path, direction="ASCENDING"):
        self.order_field = field_path
        self.order_direction = direction
        return self

    def limit(self, count):
        self.limit_count = int(count)
        return self

    def stream(self, transaction=None):
        firestore = self.collection.firestore
        if transaction is not None and not transaction.active:
            raise ValueError("Transaction not in progress")
        if firestore.fail_reads:
            raise RuntimeError("firestore query failed")

        records = list(self.collection.records.items())
        for field_path, operator, expected in self.filters:
            if operator == ">":
                records = [
                    (document_id, payload)
                    for document_id, payload in records
                    if payload.get(field_path) is not None
                    and payload[field_path] > expected
                ]
            elif operator == "==":
                records = [
                    (document_id, payload)
                    for document_id, payload in records
                    if payload.get(field_path) == expected
                ]
            else:
                raise AssertionError(f"unsupported fake query operator: {operator}")
        if self.order_field:
            records.sort(
                key=lambda item: item[1].get(self.order_field),
                reverse=self.order_direction == "DESCENDING",
            )
        if self.limit_count is not None:
            records = records[:self.limit_count]

        firestore.last_query = self
        firestore.last_query_transaction = transaction
        firestore.query_stream_calls += 1
        firestore.query_documents_returned += len(records)
        return [
            FakeStreamDocument(document_id, payload)
            for document_id, payload in records
        ]


class FakeCollection:
    def __init__(self, firestore):
        self.firestore = firestore
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def where(self, field_path=None, op_string=None, value=None, *, filter=None):
        return FakeQuery(self).where(
            field_path,
            op_string,
            value,
            filter=filter,
        )

    def stream(self):
        if self.firestore.fail_reads:
            raise RuntimeError("firestore stream failed")
        self.firestore.unbounded_stream_calls += 1
        return [
            FakeStreamDocument(document_id, payload)
            for document_id, payload in self.records.items()
        ]


class FakeWriteBatch:
    def __init__(self, firestore, *, is_transaction=False):
        self.firestore = firestore
        self.is_transaction = is_transaction
        self.active = False
        self.committed_operations = []
        self.operations = []

    def begin(self):
        self.active = True

    def rollback(self):
        self.active = False
        self.operations = []

    def set(self, document, payload, merge=False):
        self.operations.append(("set", document, dict(payload), merge))

    def update(self, document, payload):
        self.operations.append(("update", document, dict(payload), True))

    def delete(self, document):
        self.operations.append(("delete", document, None, False))

    def commit(self):
        if self.is_transaction and not self.active:
            raise ValueError("Transaction not in progress")
        if self.firestore.fail_commit:
            raise RuntimeError("firestore commit failed")
        for operation, document, payload, merge in self.operations:
            if operation == "set":
                document.set(payload, merge=merge)
            elif operation == "update":
                document.update(payload)
            else:
                document.delete()
        self.committed_operations = list(self.operations)
        self.active = False


class FakeFirestore:
    def __init__(self, *, fail_commit=False, fail_reads=False):
        self.collections = {}
        self.fail_commit = fail_commit
        self.fail_reads = fail_reads
        self.last_query = None
        self.last_query_transaction = None
        self.query_documents_returned = 0
        self.query_stream_calls = 0
        self.unbounded_stream_calls = 0
        self.transactions = []
        self.read_log = []

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection(self))

    def transaction(self):
        transaction = FakeWriteBatch(self, is_transaction=True)
        self.transactions.append(transaction)
        return transaction

    def batch(self):
        return FakeWriteBatch(self)


def fake_transactional(operation):
    def run(transaction, *args, **kwargs):
        transaction.begin()
        try:
            result = operation(transaction, *args, **kwargs)
            transaction.commit()
            return result
        except BaseException:
            transaction.rollback()
            raise

    return run


class CommunityRepositoryTests(unittest.TestCase):
    def test_firestore_uses_legacy_compatible_collections_with_memory_fallback(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(lambda: firestore)
        report = {
            "id": "report-1",
            "type_id": "rain",
            "place": "Pordenone",
            "lat": 45.95689,
            "lon": 12.66051,
            "created_at": 1000,
            "expires_at": 4600,
        }

        self.assertEqual(repository.save_report(report), "firestore")
        reports, storage = repository.list_reports(1100)
        self.assertEqual(storage, "firestore")
        self.assertEqual(reports[0]["id"], "report-1")
        self.assertIn("community_reports", firestore.collections)

        self.assertEqual(repository.set_cooldown("client", 2000), "firestore")
        self.assertEqual(repository.get_cooldown("client", 1100), 2000)
        self.assertIn("community_report_cooldowns", firestore.collections)

        state = {"yes": 1, "no": 0, "votes": {"client": "yes"}}
        self.assertEqual(repository.save_confirmation("group-1", state, 4600), "firestore")
        self.assertEqual(repository.get_confirmation("group-1")["yes"], 1)
        self.assertIn("community_report_confirmations", firestore.collections)

        self.assertEqual(repository.delete_report("report-1"), "firestore")
        self.assertEqual(repository.list_reports(1100)[0], [])

    def test_report_identity_snapshot_is_deep_copied_at_repository_boundaries(self):
        repository = CommunityRepository()
        report = {
            "id": "report-identity",
            "type_id": "rain",
            "place": "Pordenone",
            "created_at": 1000,
            "expires_at": 4600,
            "identity": {
                "version": 1,
                "alias": "Clâf di Pordenon",
                "subject_id": "claf",
                "avatar": {
                    "palette_id": "sky",
                    "pattern_id": "diagonal",
                    "variant": 2,
                    "angle": 135,
                },
            },
        }

        repository.save_report(report)
        report["identity"]["alias"] = "Ors di Udin"
        first_read = repository.list_reports(1100)[0][0]
        first_read["identity"]["avatar"]["palette_id"] = "gold"
        second_read = repository.list_reports(1100)[0][0]

        self.assertEqual(second_read["identity"]["alias"], "Clâf di Pordenon")
        self.assertEqual(second_read["identity"]["avatar"]["palette_id"], "sky")

    def test_memory_confirmations_are_pruned_after_expiry(self):
        repository = CommunityRepository()
        repository.save_confirmation(
            "group-1",
            {"yes": 1, "no": 0, "votes": {"client": "yes"}},
            1200,
        )
        self.assertEqual(repository.get_confirmation("group-1")["yes"], 1)

        repository.list_reports(1201)
        self.assertEqual(
            repository.get_confirmation("group-1"),
            {"yes": 0, "no": 0, "votes": {}},
        )

    def test_strict_create_atomically_writes_report_and_cooldown(self):
        firestore = FakeFirestore()
        inactive_transaction = firestore.transaction()
        cooldown_document = firestore.collection(
            "community_report_cooldowns"
        ).document("inactive-client")
        with self.assertRaisesRegex(ValueError, "Transaction not in progress"):
            cooldown_document.get(transaction=inactive_transaction)

        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        report = {
            "id": "strict-report-1",
            "group_id": "group-strict-report",
            "type_id": "rain",
            "place": "Pordenone",
            "lat": 45.95689,
            "lon": 12.66051,
            "created_at": 1000,
            "expires_at": 4600,
        }

        repository.create_report_strict(
            report,
            client_key="client",
            cooldown_until=2000,
            global_limit=20,
            global_window_seconds=60,
            now=1000,
        )

        self.assertIn("strict-report-1", firestore.collections["community_reports"].records)
        cooldown = firestore.collections[
            "community_report_cooldowns"
        ].records["client"]
        self.assertEqual(cooldown["cooldown_until"], 2000)
        self.assertEqual(cooldown["report_id"], "strict-report-1")
        confirmation_id = hashlib.sha256(b"group-strict-report").hexdigest()
        confirmation = firestore.collections[
            "community_report_confirmations"
        ].records[confirmation_id]
        self.assertEqual(confirmation["report_ids"], ["strict-report-1"])

        with self.assertRaises(CommunityCooldownActive):
            repository.create_report_strict(
                {**report, "id": "strict-report-2"},
                client_key="client",
                cooldown_until=2100,
                global_limit=20,
                global_window_seconds=60,
                now=1100,
            )
        self.assertNotIn("strict-report-2", firestore.collections["community_reports"].records)

    def test_strict_undo_accepts_owned_legacy_cooldown_without_report_id(self):
        firestore = FakeFirestore()
        report = {
            "id": "legacy-report",
            "group_id": "legacy-group",
            "owner_key": "legacy-client",
            "created_at": 1000,
            "expires_at": 4600,
        }
        cooldown = {
            "client_key": "legacy-client",
            "cooldown_until": 2000,
        }
        firestore.collection("community_reports").records[report["id"]] = dict(
            report
        )
        firestore.collection("community_report_cooldowns").records[
            "legacy-client"
        ] = dict(cooldown)
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        repository._reports[report["id"]] = dict(report)
        repository._cooldowns["legacy-client"] = cooldown["cooldown_until"]

        repository.delete_report_and_cooldown_strict(
            report["id"],
            client_key="legacy-client",
        )

        self.assertNotIn(
            report["id"],
            firestore.collection("community_reports").records,
        )
        self.assertNotIn(
            "legacy-client",
            firestore.collection("community_report_cooldowns").records,
        )
        self.assertNotIn(report["id"], repository._reports)
        self.assertNotIn("legacy-client", repository._cooldowns)

    def test_stale_undo_preserves_ambiguous_legacy_cooldown(self):
        firestore = FakeFirestore()
        cooldown = {
            "client_key": "legacy-client",
            "cooldown_until": 2000,
        }
        firestore.collection("community_report_cooldowns").records[
            "legacy-client"
        ] = dict(cooldown)
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        repository._cooldowns["legacy-client"] = cooldown["cooldown_until"]

        repository.delete_report_and_cooldown_strict(
            "already-absent-report",
            client_key="legacy-client",
        )

        self.assertEqual(
            firestore.collection("community_report_cooldowns").records[
                "legacy-client"
            ],
            cooldown,
        )
        self.assertEqual(repository._cooldowns["legacy-client"], 2000)

    def test_strict_confirmation_updates_are_transactional_and_idempotent(self):
        firestore = FakeFirestore()
        firestore.collection("community_reports").records["report-1"] = {
            "id": "report-1",
            "group_id": "group-1",
            "created_at": 1000,
            "expires_at": 4600,
        }
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )

        first = repository.update_confirmation_strict(
            "group-1",
            report_ids=["report-1"],
            client_key="client-1",
            vote="yes",
            expires_at=4600,
            global_limit=60,
            global_window_seconds=60,
            max_voters=500,
            now=1000,
        )
        repeated = repository.update_confirmation_strict(
            "group-1",
            report_ids=["report-1"],
            client_key="client-1",
            vote="yes",
            expires_at=4600,
            global_limit=60,
            global_window_seconds=60,
            max_voters=500,
            now=1001,
        )
        second_client = repository.update_confirmation_strict(
            "group-1",
            report_ids=["report-1"],
            client_key="client-2",
            vote="yes",
            expires_at=4600,
            global_limit=60,
            global_window_seconds=60,
            max_voters=500,
            now=1002,
        )
        changed = repository.update_confirmation_strict(
            "group-1",
            report_ids=["report-1"],
            client_key="client-1",
            vote="no",
            expires_at=4600,
            global_limit=60,
            global_window_seconds=60,
            max_voters=500,
            now=1003,
        )

        self.assertEqual((first["yes"], first["no"]), (1, 0))
        self.assertEqual((repeated["yes"], repeated["no"]), (1, 0))
        self.assertEqual((second_client["yes"], second_client["no"]), (2, 0))
        self.assertEqual((changed["yes"], changed["no"]), (1, 1))
        self.assertTrue(first["_written"])
        self.assertFalse(repeated["_written"])
        confirmation_writes = [
            operation
            for transaction in firestore.transactions
            for operation in transaction.committed_operations
            if operation[0] == "set"
            and operation[1].collection is firestore.collections[
                "community_report_confirmations"
            ]
        ]
        self.assertEqual(len(confirmation_writes), 3)
        self.assertEqual(
            firestore.collections["community_reports"].records["report-1"][
                "confirmation_yes"
            ],
            1,
        )
        self.assertEqual(
            firestore.collections["community_reports"].records["report-1"][
                "confirmation_no"
            ],
            1,
        )

    def test_strict_denials_are_sticky_and_materialize_threshold_and_full_count(self):
        firestore = FakeFirestore()
        report = {
            "id": "report-denial",
            "group_id": "group-denial",
            "owner_key": "owner",
            "created_at": 1000,
            "expires_at": 4600,
            "expires_at_timestamp": datetime.fromtimestamp(4600, timezone.utc),
        }
        firestore.collection("community_reports").records["report-denial"] = dict(
            report
        )
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        repository._reports["report-denial"] = dict(report)
        common = {
            "report_ids": ["report-denial"],
            "expires_at": 4600,
            "global_limit": 60,
            "global_window_seconds": 60,
            "max_voters": 500,
        }

        first = repository.update_confirmation_strict(
            "group-denial",
            client_key="denier-1",
            vote="no",
            now=1000,
            **common,
        )
        retry = repository.update_confirmation_strict(
            "group-denial",
            client_key="denier-1",
            vote="no",
            now=1001,
            **common,
        )
        attempted_restore = repository.update_confirmation_strict(
            "group-denial",
            client_key="denier-1",
            vote="yes",
            now=1002,
            **common,
        )
        second = repository.update_confirmation_strict(
            "group-denial",
            client_key="denier-2",
            vote="no",
            now=1003,
            **common,
        )

        durable_report = firestore.collection("community_reports").records[
            "report-denial"
        ]
        self.assertEqual((first["yes"], first["no"]), (0, 1))
        self.assertEqual((retry["yes"], retry["no"]), (0, 1))
        self.assertEqual(
            (attempted_restore["yes"], attempted_restore["no"]),
            (0, 1),
        )
        self.assertEqual(attempted_restore["_effective_vote"], "no")
        self.assertFalse(retry["_written"])
        self.assertFalse(attempted_restore["_written"])
        self.assertEqual((second["yes"], second["no"]), (0, 2))
        self.assertFalse(durable_report["map_withdrawn"])

        third = repository.update_confirmation_strict(
            "group-denial",
            client_key="denier-3",
            vote="no",
            now=1004,
            **common,
        )
        confirmation_id = hashlib.sha256(b"group-denial").hexdigest()
        durable_confirmation = firestore.collection(
            "community_report_confirmations"
        ).records[confirmation_id]
        durable_report = firestore.collection("community_reports").records[
            "report-denial"
        ]
        withdrawal_timestamp = durable_confirmation.get("map_withdrawn_at")
        self.assertEqual((third["yes"], third["no"]), (0, 3))
        self.assertTrue(third["map_withdrawn"])
        self.assertIsNotNone(withdrawal_timestamp)
        self.assertTrue(durable_report["map_withdrawn"])
        self.assertEqual(durable_report["denial_count"], 3)

        fourth = repository.update_confirmation_strict(
            "group-denial",
            client_key="denier-4",
            vote="no",
            now=1005,
            **common,
        )
        durable_confirmation = firestore.collection(
            "community_report_confirmations"
        ).records[confirmation_id]
        durable_report = firestore.collection("community_reports").records[
            "report-denial"
        ]
        self.assertEqual((fourth["yes"], fourth["no"]), (0, 4))
        self.assertTrue(fourth["map_withdrawn"])
        self.assertEqual(durable_confirmation["no"], 4)
        self.assertEqual(len(durable_confirmation["votes"]), 4)
        self.assertEqual(
            durable_confirmation.get("map_withdrawn_at"),
            withdrawal_timestamp,
        )
        self.assertEqual(
            durable_confirmation["expires_at_timestamp"].timestamp(),
            4600,
        )
        self.assertEqual(durable_report["confirmation_no"], 4)
        self.assertEqual(durable_report["denial_count"], 4)
        self.assertTrue(durable_report["map_withdrawn"])
        self.assertEqual(durable_report["created_at"], 1000)
        self.assertEqual(durable_report["expires_at"], 4600)
        self.assertEqual(repository._reports["report-denial"]["denial_count"], 4)
        self.assertTrue(repository._reports["report-denial"]["map_withdrawn"])

        confirmation_writes = [
            operation
            for transaction in firestore.transactions
            for operation in transaction.committed_operations
            if operation[0] == "set"
            and operation[1].collection
            is firestore.collections["community_report_confirmations"]
        ]
        self.assertEqual(len(confirmation_writes), 4)
        rate_limit_counts = [
            payload["count"]
            for payload in firestore.collection(
                "community_report_rate_limits"
            ).records.values()
        ]
        self.assertEqual(rate_limit_counts, [4])

    def test_strict_denial_materializes_a_report_added_after_the_service_snapshot(self):
        firestore = FakeFirestore()
        group_id = "group-coordinated-denial"
        confirmation_id = hashlib.sha256(group_id.encode("utf-8")).hexdigest()
        old_report = {
            "id": "report-old",
            "group_id": group_id,
            "owner_key": "owner-old",
            "type_id": "rain",
            "place": "Pordenone",
            "created_at": 1000,
            "expires_at": 4600,
            "expires_at_timestamp": datetime.fromtimestamp(4600, timezone.utc),
            "confirmation_yes": 0,
            "confirmation_no": 2,
        }
        firestore.collection("community_reports").records[old_report["id"]] = dict(
            old_report
        )
        firestore.collection("community_report_confirmations").records[
            confirmation_id
        ] = {
            "group_id": group_id,
            "yes": 0,
            "no": 2,
            "votes": {"denier-1": "no", "denier-2": "no"},
            "report_ids": [old_report["id"]],
            "expires_at_timestamp": datetime.fromtimestamp(4600, timezone.utc),
        }
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        repository._reports[old_report["id"]] = dict(old_report)

        new_report = {
            "id": "report-new",
            "group_id": group_id,
            "owner_key": "owner-new",
            "type_id": "rain",
            "place": "Pordenone",
            "lat": 45.95689,
            "lon": 12.66051,
            "created_at": 1100,
            "expires_at": 4700,
        }
        repository.create_report_strict(
            new_report,
            client_key="owner-new",
            cooldown_until=1400,
            global_limit=20,
            global_window_seconds=60,
            now=1100,
        )

        coordinated = firestore.collection(
            "community_report_confirmations"
        ).records[confirmation_id]
        self.assertEqual(
            set(coordinated["report_ids"]),
            {"report-old", "report-new"},
        )
        self.assertEqual(
            firestore.collection("community_reports").records["report-new"][
                "confirmation_no"
            ],
            2,
        )

        result = repository.update_confirmation_strict(
            group_id,
            # This deliberately represents the stale list captured by another
            # service instance before report-new committed.
            report_ids=["report-old"],
            client_key="denier-3",
            vote="no",
            expires_at=4600,
            global_limit=60,
            global_window_seconds=60,
            max_voters=500,
            now=1200,
        )

        self.assertEqual(result["no"], 3)
        self.assertTrue(result["map_withdrawn"])
        for report_id in ("report-old", "report-new"):
            durable_report = firestore.collection("community_reports").records[
                report_id
            ]
            self.assertEqual(durable_report["confirmation_no"], 3)
            self.assertEqual(durable_report["denial_count"], 3)
            self.assertTrue(durable_report["map_withdrawn"])
        self.assertEqual(
            set(
                firestore.collection("community_report_confirmations").records[
                    confirmation_id
                ]["report_ids"]
            ),
            {"report-old", "report-new"},
        )

        firestore.collection("community_report_confirmations").records[
            confirmation_id
        ]["report_ids"].append("report-already-expired")
        firestore.collection("community_reports").records["report-new"].update({
            "confirmation_no": 2,
            "denial_count": 2,
            "map_withdrawn": False,
        })
        retry = repository.update_confirmation_strict(
            group_id,
            report_ids=["report-new"],
            client_key="denier-3",
            vote="no",
            expires_at=4700,
            global_limit=60,
            global_window_seconds=60,
            max_voters=500,
            now=1201,
        )

        self.assertEqual(retry["no"], 3)
        self.assertFalse(retry["_written"])
        self.assertEqual(
            set(
                firestore.collection("community_report_confirmations").records[
                    confirmation_id
                ]["report_ids"]
            ),
            {"report-old", "report-new"},
        )
        repaired_report = firestore.collection("community_reports").records[
            "report-new"
        ]
        self.assertEqual(repaired_report["confirmation_no"], 3)
        self.assertEqual(repaired_report["denial_count"], 3)
        self.assertTrue(repaired_report["map_withdrawn"])

    def test_identical_confirmation_is_a_read_only_idempotent_retry(self):
        firestore = FakeFirestore()
        report = {
            "id": "report-repeat",
            "group_id": "group-repeat",
            "created_at": 1000,
            "expires_at": 4600,
        }
        firestore.collection("community_reports").records["report-repeat"] = dict(
            report
        )
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        repository._reports["report-repeat"] = dict(report)
        arguments = {
            "client_key": "client-1",
            "vote": "yes",
            "expires_at": 4600,
            "global_limit": 2,
            "global_window_seconds": 60,
            "max_voters": 500,
            "report_ids": ["report-repeat"],
        }
        repository.update_confirmation_strict("group-repeat", now=1000, **arguments)
        confirmation_id = hashlib.sha256(b"group-repeat").hexdigest()
        durable_confirmation = dict(
            firestore.collection("community_report_confirmations").records[
                confirmation_id
            ]
        )
        memory_report = dict(repository._reports["report-repeat"])
        repository._confirmations["group-repeat"] = {"stale": True}
        repeated = repository.update_confirmation_strict(
            "group-repeat",
            now=1001,
            **arguments,
        )
        third = repository.update_confirmation_strict(
            "group-repeat",
            now=1002,
            **arguments,
        )

        self.assertFalse(repeated["_written"])
        self.assertFalse(third["_written"])
        self.assertEqual(
            firestore.collection("community_report_confirmations").records[
                confirmation_id
            ],
            durable_confirmation,
        )
        self.assertEqual(
            repository._confirmations["group-repeat"],
            durable_confirmation,
        )
        self.assertEqual(repository._reports["report-repeat"], memory_report)
        confirmation_writes = [
            operation
            for transaction in firestore.transactions
            for operation in transaction.committed_operations
            if operation[0] == "set"
            and operation[1].collection is firestore.collections[
                "community_report_confirmations"
            ]
        ]
        self.assertEqual(len(confirmation_writes), 1)
        self.assertEqual(
            next(iter(firestore.collections["community_report_rate_limits"].records.values()))[
                "count"
            ],
            1,
        )

    def test_strict_confirmation_budget_and_voter_cap_are_bounded(self):
        firestore = FakeFirestore()
        firestore.collection("community_reports").records.update({
            "report-budget": {
                "id": "report-budget",
                "group_id": "group-budget",
                "created_at": 1000,
                "expires_at": 4600,
            },
            "report-cap": {
                "id": "report-cap",
                "group_id": "group-cap",
                "created_at": 1000,
                "expires_at": 4600,
            },
        })
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )

        for index in range(2):
            repository.update_confirmation_strict(
                "group-budget",
                client_key=f"client-{index}",
                vote="yes",
                expires_at=4600,
                global_limit=2,
                global_window_seconds=60,
                max_voters=500,
                now=1000 + index,
                report_ids=["report-budget"],
            )
        with self.assertRaises(CommunityCooldownActive):
            repository.update_confirmation_strict(
                "group-budget",
                client_key="client-2",
                vote="yes",
                expires_at=4600,
                global_limit=2,
                global_window_seconds=60,
                max_voters=500,
                now=1002,
                report_ids=["report-budget"],
            )

        capped_repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        capped_repository.update_confirmation_strict(
            "group-cap",
            client_key="only-client",
            vote="yes",
            expires_at=4600,
            global_limit=60,
            global_window_seconds=60,
            max_voters=1,
            now=1060,
            report_ids=["report-cap"],
        )
        with self.assertRaises(CommunityConfirmationCapacityReached):
            capped_repository.update_confirmation_strict(
                "group-cap",
                client_key="rotated-client",
                vote="yes",
                expires_at=4600,
                global_limit=60,
                global_window_seconds=60,
                max_voters=1,
                now=1061,
                report_ids=["report-cap"],
            )

    def test_strict_create_commit_failure_leaves_no_partial_write(self):
        firestore = FakeFirestore(fail_commit=True)
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        report = {
            "id": "strict-report-1",
            "type_id": "rain",
            "place": "Pordenone",
            "lat": 45.95689,
            "lon": 12.66051,
            "created_at": 1000,
            "expires_at": 4600,
        }

        with self.assertRaises(CommunityRepositoryUnavailable):
            repository.create_report_strict(
                report,
                client_key="client",
                cooldown_until=2000,
                global_limit=20,
                global_window_seconds=60,
                now=1000,
            )

        self.assertEqual(firestore.collections["community_reports"].records, {})
        self.assertEqual(firestore.collections["community_report_cooldowns"].records, {})

    def test_strict_global_window_budget_blocks_rotating_client_ids_atomically(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        report = {
            "id": "strict-report-1",
            "type_id": "rain",
            "place": "Pordenone",
            "lat": 45.95689,
            "lon": 12.66051,
            "created_at": 1000,
            "expires_at": 4600,
        }

        repository.create_report_strict(
            report,
            client_key="client-1",
            cooldown_until=2000,
            global_limit=2,
            global_window_seconds=60,
            now=1000,
        )
        repository.create_report_strict(
            {**report, "id": "strict-report-2"},
            client_key="client-2",
            cooldown_until=2000,
            global_limit=2,
            global_window_seconds=60,
            now=1001,
        )
        with self.assertRaises(CommunityCooldownActive) as blocked:
            repository.create_report_strict(
                {**report, "id": "strict-report-3"},
                client_key="client-3",
                cooldown_until=2000,
                global_limit=2,
                global_window_seconds=60,
                now=1002,
            )

        self.assertEqual(blocked.exception.cooldown_until, 1020)
        self.assertNotIn("strict-report-3", firestore.collections["community_reports"].records)
        self.assertEqual(
            next(iter(firestore.collections["community_report_rate_limits"].records.values()))[
                "count"
            ],
            2,
        )

    def test_strict_reads_never_fall_back_to_memory(self):
        firestore = FakeFirestore(fail_reads=True)
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        repository._reports["memory-only"] = {
            "id": "memory-only",
            "created_at": 1000,
            "expires_at": 4600,
        }

        with self.assertRaises(CommunityRepositoryUnavailable):
            repository.list_reports(1100)
        with self.assertRaises(CommunityRepositoryUnavailable):
            repository.get_confirmation("group-1")

    def test_strict_list_queries_only_the_latest_200_active_reports(self):
        firestore = FakeFirestore()
        collection = firestore.collection("community_reports")
        for index in range(250):
            created_at = 1000 + index
            expires_at = created_at + 3600
            collection.records[f"active-{index:03d}"] = {
                "id": f"active-{index:03d}",
                "created_at": created_at,
                "created_at_timestamp": datetime.fromtimestamp(
                    created_at,
                    timezone.utc,
                ),
                "expires_at": expires_at,
                "expires_at_timestamp": datetime.fromtimestamp(
                    expires_at,
                    timezone.utc,
                ),
            }
        for index in range(10):
            collection.records[f"expired-{index:03d}"] = {
                "id": f"expired-{index:03d}",
                "created_at": 2000 + index,
                "created_at_timestamp": datetime.fromtimestamp(
                    2000 + index,
                    timezone.utc,
                ),
                "expires_at": 900,
                "expires_at_timestamp": datetime.fromtimestamp(900, timezone.utc),
            }

        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        reports, storage = repository.list_reports(1000)

        self.assertEqual(storage, "firestore")
        self.assertEqual(len(reports), 200)
        self.assertEqual(reports[0]["id"], "active-249")
        self.assertEqual(reports[-1]["id"], "active-050")
        self.assertEqual(firestore.unbounded_stream_calls, 0)
        self.assertEqual(firestore.query_stream_calls, 1)
        self.assertEqual(firestore.query_documents_returned, 200)
        self.assertEqual(firestore.last_query.limit_count, 200)
        self.assertEqual(
            firestore.last_query.filters[0][:2],
            ("expires_at_timestamp", ">"),
        )
        self.assertEqual(firestore.last_query.order_field, "expires_at_timestamp")
        self.assertEqual(firestore.last_query.order_direction, "DESCENDING")
        self.assertIn("expired-000", collection.records)

    def test_group_lookup_detects_oversized_groups_without_composite_index(self):
        firestore = FakeFirestore()
        collection = firestore.collection("community_reports")
        group_id = "group-rain:pordenone:1"
        for index in range(250):
            collection.records[f"group-report-{index:03d}"] = {
                "id": f"group-report-{index:03d}",
                "group_id": group_id,
                "created_at": 1000 + index,
                "expires_at": 5000,
                "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
            }
        collection.records["expired-same-group"] = {
            "id": "expired-same-group",
            "group_id": group_id,
            "created_at": 900,
            "expires_at": 999,
            "expires_at_timestamp": datetime.fromtimestamp(999, timezone.utc),
        }
        collection.records["other-report"] = {
            "id": "other-report",
            "group_id": "group-other",
            "created_at": 1300,
            "expires_at": 5000,
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )

        reports, storage = repository.list_group_reports(group_id, 1000)
        direct, direct_storage = repository.get_report("group-report-000", 1000)

        self.assertEqual(storage, "firestore")
        self.assertEqual(len(reports), 201)
        self.assertEqual(direct_storage, "firestore")
        self.assertEqual(direct["id"], "group-report-000")
        self.assertEqual(firestore.last_query.limit_count, 201)
        self.assertEqual(
            firestore.last_query.filters,
            [("group_id", "==", group_id)],
        )

    def test_hidden_group_lookup_is_one_feed_level_query(self):
        firestore = FakeFirestore()
        moderation = firestore.collection("community_report_moderation")
        moderation.records["active-hidden"] = {
            "group_id": "group-hidden",
            "hidden": True,
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }
        moderation.records["expired-hidden"] = {
            "group_id": "group-expired",
            "hidden": True,
            "expires_at_timestamp": datetime.fromtimestamp(900, timezone.utc),
        }
        moderation.records["visible"] = {
            "group_id": "group-visible",
            "hidden": False,
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )

        hidden = repository.list_hidden_group_ids(1000)

        self.assertEqual(hidden, {"group-hidden"})
        self.assertEqual(firestore.last_query.filters, [("hidden", "==", True)])

    def test_auto_storage_is_strict_and_never_uses_memory_fallback(self):
        repository = CommunityRepository(storage_mode="auto")

        self.assertTrue(repository.requires_firestore)
        with self.assertRaises(CommunityRepositoryUnavailable):
            repository.list_reports(1000)
        with self.assertRaises(CommunityRepositoryUnavailable):
            repository.save_report({
                "id": "no-fallback",
                "created_at": 1000,
                "expires_at": 4600,
            })

    def test_strict_create_extends_existing_confirmation_to_new_report_expiry(self):
        firestore = FakeFirestore()
        group_id = "group-rain:pordenone:1"
        confirmation_id = hashlib.sha256(group_id.encode()).hexdigest()
        firestore.collection("community_report_confirmations").records[
            confirmation_id
        ] = {
            "group_id": group_id,
            "yes": 1,
            "no": 0,
            "votes": {"voter": "yes"},
            "expires_at_timestamp": datetime.fromtimestamp(3000, timezone.utc),
        }
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        report = {
            "id": "later-report",
            "type_id": "rain",
            "place": "Pordenone",
            "group_id": group_id,
            "created_at": 2000,
            "expires_at": 5600,
        }

        repository.create_report_strict(
            report,
            client_key="later-owner",
            cooldown_until=4700,
            global_limit=20,
            global_window_seconds=60,
            now=2000,
        )

        stored_confirmation = firestore.collection(
            "community_report_confirmations"
        ).records[confirmation_id]
        self.assertEqual(
            stored_confirmation["expires_at_timestamp"].timestamp(),
            5600,
        )
        stored_report = firestore.collection("community_reports").records[
            "later-report"
        ]
        self.assertEqual(stored_report["confirmation_yes"], 1)
        self.assertEqual(stored_report["confirmation_no"], 0)

    def test_strict_flags_are_idempotent_but_require_admin_for_global_hide(self):
        firestore = FakeFirestore()
        reports = firestore.collection("community_reports")
        for report_id in ("report-a", "report-b"):
            reports.records[report_id] = {
                "id": report_id,
                "group_id": "group-rain:pordenone:1",
                "created_at": 1000,
                "expires_at": 4600,
            }
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        arguments = {
            "group_id": "group-rain:pordenone:1",
            "report_ids": ["report-a", "report-b"],
            "owner_keys": ["owner-a", "owner-b"],
            "report_sources": {
                "report-a": "owner-a",
                "report-b": "owner-b",
            },
            "expires_at": 87400,
            "global_limit": 60,
            "global_window_seconds": 60,
            "client_limit": 10,
            "client_window_seconds": 3600,
            "max_flaggers": 50,
        }

        first = repository.flag_group_strict(
            client_key="flagger-a",
            reason="inaccurate",
            now=1000,
            **arguments,
        )
        moderation_id = hashlib.sha256(
            b"group-rain:pordenone:1"
        ).hexdigest()
        flag_id = hashlib.sha256(
            b"group-rain:pordenone:1:flagger-a"
        ).hexdigest()
        durable_moderation = dict(
            firestore.collection("community_report_moderation").records[
                moderation_id
            ]
        )
        durable_flag = dict(
            firestore.collection("community_report_flags").records[flag_id]
        )
        repository._moderation["group-rain:pordenone:1"] = {"stale": True}
        repository._flags[flag_id] = {"stale": True}
        repeated = repository.flag_group_strict(
            client_key="flagger-a",
            reason="misuse",
            now=1001,
            **arguments,
        )
        self.assertEqual(
            firestore.collection("community_report_moderation").records[
                moderation_id
            ],
            durable_moderation,
        )
        self.assertEqual(
            firestore.collection("community_report_flags").records[flag_id],
            durable_flag,
        )
        self.assertEqual(
            repository._moderation["group-rain:pordenone:1"],
            durable_moderation,
        )
        self.assertEqual(repository._flags[flag_id], durable_flag)
        second = repository.flag_group_strict(
            client_key="flagger-b",
            reason="duplicate",
            now=1002,
            **arguments,
        )
        third = repository.flag_group_strict(
            client_key="flagger-c",
            reason="misuse",
            now=1003,
            **arguments,
        )

        self.assertEqual(first["flag_count"], 1)
        self.assertTrue(repeated["_already_reported"])
        self.assertEqual(repeated["_reason"], "inaccurate")
        self.assertEqual(second["flag_count"], 2)
        self.assertEqual(third["flag_count"], 3)
        self.assertFalse(third["hidden"])
        self.assertEqual(third["report_ids"], ["report-a", "report-b"])
        self.assertEqual(third["owner_keys"], ["owner-a", "owner-b"])
        self.assertEqual(third["report_sources"]["report-a"], "owner-a")
        self.assertNotIn("moderation_hidden", reports.records["report-a"])
        self.assertNotIn("moderation_hidden", reports.records["report-b"])
        self.assertEqual(
            len(firestore.collections["community_report_flags"].records),
            3,
        )
        global_windows = [
            payload
            for document_id, payload in firestore.collections[
                "community_report_rate_limits"
            ].records.items()
            if document_id.startswith("global-flag-")
        ]
        self.assertEqual(sum(int(item["count"]) for item in global_windows), 3)

    def test_idempotent_flag_refreshes_a_later_report_snapshot_without_rate_cost(self):
        firestore = FakeFirestore()
        reports = firestore.collection("community_reports").records
        reports["report-a"] = {
            "id": "report-a",
            "group_id": "group-rain:pordenone:1",
            "owner_key": "owner-a",
            "created_at": 1000,
            "expires_at": 4600,
        }
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        common = {
            "group_id": "group-rain:pordenone:1",
            "client_key": "flagger-a",
            "reason": "inaccurate",
            "expires_at": 87400,
            "global_limit": 60,
            "global_window_seconds": 60,
            "client_limit": 10,
            "client_window_seconds": 3600,
            "max_flaggers": 50,
        }

        repository.flag_group_strict(
            report_ids=["report-a"],
            owner_keys=["owner-a"],
            report_sources={"report-a": "owner-a"},
            now=1000,
            **common,
        )
        reports["report-later"] = {
            "id": "report-later",
            "group_id": "group-rain:pordenone:1",
            "owner_key": "owner-later",
            "created_at": 1001,
            "expires_at": 4600,
        }
        repeated = repository.flag_group_strict(
            report_ids=["report-a", "report-later"],
            owner_keys=["owner-a", "owner-later"],
            report_sources={
                "report-a": "owner-a",
                "report-later": "owner-later",
            },
            now=1001,
            **common,
        )

        self.assertTrue(repeated["_already_reported"])
        self.assertEqual(
            repeated["report_ids"],
            ["report-a", "report-later"],
        )
        flag = next(iter(
            firestore.collection("community_report_flags").records.values()
        ))
        self.assertEqual(flag["report_ids"], ["report-a", "report-later"])
        moderation = next(iter(
            firestore.collection("community_report_moderation").records.values()
        ))
        flag_id = next(iter(
            firestore.collection("community_report_flags").records
        ))
        self.assertEqual(
            repository._moderation["group-rain:pordenone:1"],
            moderation,
        )
        self.assertEqual(repository._flags[flag_id], flag)
        global_windows = [
            payload
            for document_id, payload in firestore.collection(
                "community_report_rate_limits"
            ).records.items()
            if document_id.startswith("global-flag-")
        ]
        self.assertEqual(sum(int(item["count"]) for item in global_windows), 1)

    def test_strict_create_rejects_an_administratively_hidden_group(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        group_id = "group-rain:pordenone:1"
        moderation_id = hashlib.sha256(group_id.encode()).hexdigest()
        firestore.collection("community_report_moderation").records[moderation_id] = {
            "group_id": group_id,
            "hidden": True,
            "hidden_reason": "administrative_moderation",
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }
        report = {
            "id": "late-report",
            "type_id": "rain",
            "place": "Pordenone",
            "group_id": group_id,
            "created_at": 1000,
            "expires_at": 4600,
        }

        with self.assertRaises(CommunityGroupHidden):
            repository.create_report_strict(
                report,
                client_key="new-owner",
                cooldown_until=2000,
                global_limit=20,
                global_window_seconds=60,
                now=1000,
            )

        self.assertNotIn("late-report", firestore.collections["community_reports"].records)

    def test_strict_create_rejects_a_temporarily_blocked_source(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        repository.set_source_block(
            "blocked-owner",
            blocked_until=5000,
            reason="confirmed_misuse",
            report_id="report-abuse",
        )
        report = {
            "id": "blocked-report",
            "type_id": "rain",
            "place": "Pordenone",
            "lat": 45.95689,
            "lon": 12.66051,
            "created_at": 1000,
            "expires_at": 4600,
        }

        with self.assertRaises(CommunitySourceBlocked) as blocked:
            repository.create_report_strict(
                report,
                client_key="blocked-owner",
                cooldown_until=2000,
                global_limit=20,
                global_window_seconds=60,
                now=1000,
            )

        self.assertEqual(blocked.exception.blocked_until, 5000)
        self.assertNotIn("blocked-report", firestore.collections["community_reports"].records)

    def test_strict_second_author_validates_and_awards_both_atomically(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        group_id = "group-rain:pordenone:1"
        base = {
            "type_id": "rain",
            "place": "Pordenone",
            "group_id": group_id,
            "created_at": 1000,
            "expires_at": 5000,
        }

        repository.create_report_strict(
            {**base, "id": "report-a", "owner_key": "owner-a"},
            client_key="owner-a",
            cooldown_until=2000,
            global_limit=20,
            global_window_seconds=60,
            now=1000,
            reputation_award_day="1970-01-01",
            reputation_daily_limit=3,
        )
        pending_summary = next(iter(
            firestore.collection("community_reputation").records.values()
        ))
        self.assertEqual(
            (
                pending_summary["points"],
                pending_summary["validated_reports"],
                pending_summary["total_reports"],
            ),
            (0, 0, 1),
        )

        repository.create_report_strict(
            {
                **base,
                "id": "report-b",
                "owner_key": "owner-b",
                "created_at": 1001,
            },
            client_key="owner-b",
            cooldown_until=2001,
            global_limit=20,
            global_window_seconds=60,
            now=1001,
            reputation_award_day="1970-01-01",
            reputation_daily_limit=3,
        )

        summaries = list(
            firestore.collection("community_reputation").records.values()
        )
        awards = list(
            firestore.collection("community_reputation_awards").records.values()
        )
        self.assertEqual(len(summaries), 2)
        self.assertEqual(len(awards), 2)
        self.assertTrue(all(item["points"] == 1 for item in summaries))
        self.assertTrue(all(item["validated_reports"] == 1 for item in summaries))
        self.assertTrue(all(item["total_reports"] == 1 for item in summaries))
        self.assertTrue(all("group_id" not in item for item in awards))
        self.assertNotIn(group_id, str(awards))
        self.assertTrue(all(
            item["expires_at_timestamp"]
            == datetime.fromtimestamp(
                1001 + REPUTATION_RETENTION_SECONDS,
                timezone.utc,
            )
            for item in awards
        ))
        self.assertTrue(all(
            report["validity_status"] == "verified"
            for report in firestore.collection("community_reports").records.values()
        ))

    def test_strict_revocation_preserves_current_day_counter_and_is_idempotent(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        owner_key = "owner-a"
        old_group = "group-rain:pordenone:old"
        new_group = "group-rain:pordenone:new"
        for index, (group_id, award_day, now) in enumerate((
            (old_group, "1970-01-01", 1000),
            (new_group, "1970-01-02", 2000),
        )):
            repository._record_reputation_awards_memory(
                group_id=group_id,
                owner_keys=[owner_key],
                award_day=award_day,
                daily_limit=3,
                reason="independent_confirmation",
                now=now,
            )
            award_id = next(reversed(repository._reputation_awards))
            reputation_id = next(iter(repository._reputations))
            firestore.collection("community_reputation_awards").records[
                award_id
            ] = dict(repository._reputation_awards[award_id])
            firestore.collection("community_reputation").records[
                reputation_id
            ] = dict(repository._reputations[reputation_id])

        revoked = repository.revoke_group_reputation_strict(
            old_group,
            now=2001,
            reason="administrative_moderation",
        )
        repeated = repository.revoke_group_reputation_strict(
            old_group,
            now=2002,
            reason="administrative_moderation",
        )

        summary = next(iter(
            firestore.collection("community_reputation").records.values()
        ))
        self.assertEqual((revoked, repeated), (1, 0))
        self.assertEqual(summary["points"], 1)
        self.assertEqual(summary["validated_reports"], 1)
        self.assertEqual(summary["daily_award_day"], "1970-01-02")
        self.assertEqual(summary["daily_awards"], 1)

    def test_strict_confirmation_rechecks_owner_inside_transaction(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        report = {
            "id": "owned-report",
            "type_id": "rain",
            "place": "Pordenone",
            "group_id": "group-rain:pordenone:1",
            "owner_key": "same-owner",
            "created_at": 1000,
            "expires_at": 5000,
        }
        repository.create_report_strict(
            report,
            client_key="same-owner",
            cooldown_until=2000,
            global_limit=20,
            global_window_seconds=60,
            now=1000,
        )

        with self.assertRaises(CommunitySelfConfirmationNotAllowed):
            repository.update_confirmation_strict(
                report["group_id"],
                report_ids=[report["id"]],
                client_key="confirmation-scope-key",
                voter_owner_key="same-owner",
                vote="yes",
                expires_at=5000,
                global_limit=60,
                global_window_seconds=60,
                max_voters=500,
                now=1001,
            )

        summary = next(iter(
            firestore.collection("community_reputation").records.values()
        ))
        self.assertEqual(
            (
                summary["points"],
                summary["validated_reports"],
                summary["total_reports"],
            ),
            (0, 0, 1),
        )

    def test_strict_reputation_pending_query_is_scoped_to_owner(self):
        firestore = FakeFirestore()
        repository = CommunityRepository(
            lambda: firestore,
            storage_mode="firestore",
            transactional_decorator=fake_transactional,
        )
        reports = firestore.collection("community_reports").records
        for index in range(MAX_REPORTS + 1):
            reports[f"other-{index:03d}"] = {
                "id": f"other-{index:03d}",
                "group_id": f"other-group-{index:03d}",
                "owner_key": "other-owner",
                "type_id": "rain",
                "expires_at_timestamp": datetime.fromtimestamp(
                    5000,
                    timezone.utc,
                ),
            }
        reports["owned-active"] = {
            "id": "owned-active",
            "group_id": "owned-active-group",
            "owner_key": "selected-owner",
            "type_id": "rain",
            "validity_status": "unverified",
            "temporal_status": "active",
            "confirmation_yes": 0,
            "confirmation_no": 0,
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }

        summary, storage = repository.get_reputation(
            "selected-owner",
            now=1000,
        )

        self.assertEqual(storage, "firestore")
        self.assertEqual(summary["pending_reports"], 1)
        self.assertEqual(summary["total_reports"], 0)
        self.assertEqual(
            firestore.last_query.filters,
            [("owner_key", "==", "selected-owner")],
        )
        self.assertEqual(firestore.last_query.limit_count, MAX_REPORTS)
        self.assertIsNone(firestore.last_query.order_field)
        self.assertIsNotNone(firestore.last_query_transaction)


if __name__ == "__main__":
    unittest.main()
