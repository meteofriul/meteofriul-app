import hashlib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from tools import moderate_community_reports as moderation_tool

from tools.moderate_community_reports import (
    MAX_BLOCK_HOURS,
    MAX_ADMIN_BATCH_WRITES,
    block_source,
    hide_group,
    inspect_group,
    owner_key_from_moderation_snapshot,
    remove_group,
    require_expected_project,
    require_single_batch_capacity,
    restore_group,
    summarize_moderation,
    unblock_source,
)


class FakeSnapshot:
    def __init__(self, payload=None, *, reference=None, document_id=""):
        self.payload = payload
        self.exists = payload is not None
        self.reference = reference
        self.id = document_id

    def to_dict(self):
        return dict(self.payload or {})


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id
        self.id = document_id

    def get(self, transaction=None):
        return FakeSnapshot(
            self.collection.records.get(self.document_id),
            reference=self,
            document_id=self.document_id,
        )

    def set(self, payload, merge=False):
        current = dict(self.collection.records.get(self.document_id) or {})
        self.collection.records[self.document_id] = (
            {**current, **payload} if merge else dict(payload)
        )

    def delete(self):
        self.collection.records.pop(self.document_id, None)


class FakeQuery:
    def __init__(self, collection, filters=None):
        self.collection = collection
        self.filters = list(filters or [])
        self.limit_count = None

    def where(self, *, filter):
        return FakeQuery(
            self.collection,
            [*self.filters, (filter.field_path, filter.op_string, filter.value)],
        )

    def limit(self, count):
        self.limit_count = int(count)
        return self

    def stream(self, transaction=None):
        rows = []
        for document_id, payload in self.collection.records.items():
            accepted = True
            for field, operator, expected in self.filters:
                value = payload.get(field)
                if operator == "==":
                    accepted = value == expected
                elif operator == "array_contains":
                    accepted = expected in list(value or [])
                else:
                    raise AssertionError(f"unsupported operator {operator}")
                if not accepted:
                    break
            if accepted:
                document = FakeDocument(self.collection, document_id)
                rows.append(FakeSnapshot(
                    payload,
                    reference=document,
                    document_id=document_id,
                ))
        return rows[: self.limit_count] if self.limit_count is not None else rows


class FakeCollection:
    def __init__(self):
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def where(self, *, filter):
        return FakeQuery(self).where(filter=filter)

    def stream(self):
        return FakeQuery(self).stream()


class FakeBatch:
    def __init__(self, *, is_transaction=False):
        self.operations = []
        self.is_transaction = is_transaction
        self.active = False

    def begin(self):
        self.active = True

    def rollback(self):
        self.active = False
        self.operations = []

    def set(self, document, payload, merge=False):
        self.operations.append(("set", document, dict(payload), merge))

    def delete(self, document):
        self.operations.append(("delete", document, None, False))

    def commit(self):
        for operation, document, payload, merge in self.operations:
            if operation == "set":
                document.set(payload, merge=merge)
            else:
                document.delete()
        self.active = False


class FakeFirestore:
    def __init__(self, project="meteo-friul"):
        self.collections = {}
        self.project = project

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())

    def batch(self):
        return FakeBatch()

    def transaction(self):
        return FakeBatch(is_transaction=True)


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


class CommunityModerationToolTests(unittest.TestCase):
    def test_summary_contains_counts_but_never_private_flagger_keys(self):
        expires_at = datetime.fromtimestamp(5000, timezone.utc)
        private_a = "a" * 64
        private_b = "b" * 64
        summary = summarize_moderation({
            "group_id": "group-rain:pordenone:1",
            "flaggers": {
                private_a: "inaccurate",
                private_b: "misuse",
            },
            "hidden": False,
            "expires_at_timestamp": expires_at,
        }, now=1000)

        self.assertEqual(summary["flag_count"], 2)
        self.assertEqual(summary["reasons"], {"inaccurate": 1, "misuse": 1})
        self.assertEqual(
            summary["group_ref"],
            hashlib.sha256(
                b"group-rain:pordenone:1"
            ).hexdigest()[:24],
        )
        self.assertNotIn(private_a, str(summary))
        self.assertNotIn(private_b, str(summary))

    def test_block_source_uses_report_id_without_returning_owner_key(self):
        firestore = FakeFirestore()
        private_owner = "private-owner-hash"
        firestore.collection("community_reports").records["report-1"] = {
            "id": "report-1",
            "owner_key": private_owner,
        }

        preview = block_source(
            firestore,
            "report-1",
            hours=24,
            now=1000,
            apply=False,
        )
        applied = block_source(
            firestore,
            "report-1",
            hours=24,
            now=1000,
            apply=True,
        )

        self.assertFalse(preview["applied"])
        self.assertTrue(applied["applied"])
        self.assertNotIn(private_owner, str(preview))
        self.assertNotIn(private_owner, str(applied))
        self.assertEqual(
            len(firestore.collection("community_source_blocks").records),
            1,
        )

    def test_block_duration_is_bounded(self):
        firestore = FakeFirestore()
        firestore.collection("community_reports").records["report-1"] = {
            "owner_key": "private-owner-hash",
        }

        with self.assertRaises(ValueError):
            block_source(
                firestore,
                "report-1",
                hours=MAX_BLOCK_HOURS + 1,
                now=1000,
                apply=False,
            )

    def test_project_guard_rejects_mismatch_and_unknown(self):
        self.assertEqual(
            require_expected_project(FakeFirestore("meteo-friul")),
            "meteo-friul",
        )
        for project in ("other-project", ""):
            with self.subTest(project=project):
                with self.assertRaisesRegex(RuntimeError, "firestore_project_mismatch"):
                    require_expected_project(FakeFirestore(project))

    def test_batch_guard_fails_before_oversized_admin_write(self):
        require_single_batch_capacity("hide", MAX_ADMIN_BATCH_WRITES)
        with self.assertRaisesRegex(
            RuntimeError,
            "community_moderation_batch_limit_exceeded",
        ):
            require_single_batch_capacity("hide", MAX_ADMIN_BATCH_WRITES + 1)

    def test_expired_report_source_can_be_resolved_from_private_snapshot(self):
        private_owner = "private-owner-hash"
        moderation = {
            "report_ids": ["expired-report"],
            "owner_keys": [private_owner],
            "report_sources": {"expired-report": private_owner},
        }

        resolved = owner_key_from_moderation_snapshot(
            "expired-report",
            moderation,
        )

        self.assertEqual(resolved, private_owner)
        summary = summarize_moderation({
            **moderation,
            "group_id": "group-expired",
            "flag_count": 1,
            "flaggers": {"flagger-private": "misuse"},
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }, now=1000)
        self.assertEqual(summary["source_count"], 1)
        self.assertEqual(summary["report_count"], 1)
        self.assertNotIn(private_owner, str(summary))

    def test_block_and_unblock_source_work_after_report_expiry_via_snapshot(self):
        firestore = FakeFirestore()
        private_owner = "private-owner-hash"
        moderation_id = hashlib.sha256(b"group-one").hexdigest()
        firestore.collection("community_report_moderation").records[moderation_id] = {
            "group_id": "group-expired",
            "report_ids": ["expired-report"],
            "owner_keys": [private_owner],
            "report_sources": {"expired-report": private_owner},
        }

        blocked = block_source(
            firestore,
            "expired-report",
            hours=24,
            now=1000,
            apply=True,
        )
        unblocked = unblock_source(
            firestore,
            "expired-report",
            apply=True,
        )

        self.assertTrue(blocked["applied"])
        self.assertTrue(unblocked["applied"])
        self.assertEqual(firestore.collection("community_source_blocks").records, {})
        self.assertNotIn(private_owner, str(blocked))
        self.assertNotIn(private_owner, str(unblocked))

    def test_inspect_exposes_report_ids_but_never_private_sources(self):
        firestore = FakeFirestore()
        private_owner = "private-owner-hash"
        group_id = "group-one"
        moderation_id = hashlib.sha256(group_id.encode()).hexdigest()
        firestore.collection("community_report_moderation").records[moderation_id] = {
            "group_id": "group-one",
            "flaggers": {"private-flagger": "duplicate"},
            "flag_count": 1,
            "report_ids": ["report-one"],
            "owner_keys": [private_owner],
            "report_sources": {"report-one": private_owner},
            "hidden": False,
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }

        result = inspect_group(firestore, group_id, now=1000)

        self.assertEqual(result["report_ids"], ["report-one"])
        self.assertEqual(result["reasons"], {"duplicate": 1})
        self.assertEqual(result["source_count"], 1)
        self.assertNotIn(private_owner, str(result))
        self.assertNotIn("private-flagger", str(result))

    def test_restore_clears_flags_and_materialized_hidden_state(self):
        firestore = FakeFirestore()
        group_id = "group-one"
        firestore.collection("community_reports").records["report-one"] = {
            "group_id": group_id,
            "moderation_hidden": True,
        }
        firestore.collection("community_report_flags").records["flag-one"] = {
            "group_id": group_id,
            "reason": "misuse",
        }
        moderation_id = hashlib.sha256(group_id.encode()).hexdigest()
        firestore.collection("community_report_moderation").records[moderation_id] = {
            "group_id": group_id,
            "flaggers": {"flagger": "misuse"},
            "flag_count": 1,
            "hidden": True,
            "expires_at_timestamp": datetime.fromtimestamp(5000, timezone.utc),
        }

        result = restore_group(
            firestore,
            group_id,
            now=1000,
            apply=True,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(firestore.collection("community_report_flags").records, {})
        self.assertFalse(
            firestore.collection("community_reports").records["report-one"][
                "moderation_hidden"
            ]
        )
        moderation = next(iter(
            firestore.collection("community_report_moderation").records.values()
        ))
        self.assertEqual(moderation["flag_count"], 0)
        self.assertFalse(moderation["hidden"])

    def test_hide_and_remove_revoke_reputation_idempotently(self):
        for action in (hide_group, remove_group):
            with self.subTest(action=action.__name__):
                firestore = FakeFirestore()
                group_id = f"group-{action.__name__}"
                owner_key = "private-owner-hash"
                report_id = "report-one"
                episode_key = hashlib.sha256(
                    f"community-episode-v1:{group_id}".encode()
                ).hexdigest()
                award_id = hashlib.sha256(
                    f"community-award-v1:{group_id}:{owner_key}".encode()
                ).hexdigest()
                reputation_id = hashlib.sha256(
                    f"community-reputation-v1:{owner_key}".encode()
                ).hexdigest()
                firestore.collection("community_reports").records[report_id] = {
                    "id": report_id,
                    "group_id": group_id,
                    "owner_key": owner_key,
                    "validity_status": "verified",
                }
                firestore.collection("community_reputation_awards").records[
                    award_id
                ] = {
                    "episode_key": episode_key,
                    "owner_key": owner_key,
                    "status": "awarded",
                    "points_delta": 1,
                    "award_day": "1970-01-01",
                    "expires_at_timestamp": datetime.fromtimestamp(
                        5000,
                        timezone.utc,
                    ),
                }
                firestore.collection("community_reputation").records[
                    reputation_id
                ] = {
                    "owner_key": owner_key,
                    "points": 1,
                    "validated_reports": 1,
                    "revoked_reports": 0,
                    "daily_award_day": "1970-01-01",
                    "daily_awards": 1,
                    "expires_at_timestamp": datetime.fromtimestamp(
                        5000,
                        timezone.utc,
                    ),
                }

                first = action(
                    firestore,
                    group_id,
                    now=1000,
                    apply=True,
                    transactional_decorator=fake_transactional,
                )
                second = action(
                    firestore,
                    group_id,
                    now=1001,
                    apply=True,
                    transactional_decorator=fake_transactional,
                )

                self.assertEqual(first["reputation_revoked"], 1)
                self.assertEqual(second["reputation_revoked"], 0)
                award = firestore.collection(
                    "community_reputation_awards"
                ).records[award_id]
                summary = firestore.collection("community_reputation").records[
                    reputation_id
                ]
                confirmation = firestore.collection(
                    "community_report_confirmations"
                ).records[hashlib.sha256(group_id.encode()).hexdigest()]
                self.assertEqual(award["status"], "revoked")
                self.assertEqual(summary["points"], 0)
                self.assertEqual(summary["validated_reports"], 0)
                self.assertEqual(summary["revoked_reports"], 1)
                self.assertEqual(confirmation["validity_status"], "rejected")
                self.assertEqual(confirmation["group_id"], group_id)
                self.assertEqual(
                    confirmation["expires_at_timestamp"],
                    datetime.fromtimestamp(
                        1001 + moderation_tool.MODERATION_RETENTION_SECONDS,
                        timezone.utc,
                    ),
                )
                if action is hide_group:
                    self.assertEqual(
                        firestore.collection("community_reports").records[
                            report_id
                        ]["validity_status"],
                        "rejected",
                    )

    def test_hide_writes_group_gate_before_the_materialization_query(self):
        firestore = FakeFirestore()
        group_id = "group-race"
        firestore.collection("community_reports").records["report-one"] = {
            "group_id": group_id,
            "owner_key": "private-owner",
        }
        observations = []
        original_lookup = moderation_tool._documents_for_group

        def observed_lookup(db, collection, selected_group_id):
            if collection == "community_reports":
                moderation_id = hashlib.sha256(group_id.encode()).hexdigest()
                gate = db.collection("community_report_moderation").records.get(
                    moderation_id,
                    {},
                )
                observations.append(bool(gate.get("hidden", False)))
            return original_lookup(db, collection, selected_group_id)

        with patch.object(
            moderation_tool,
            "_documents_for_group",
            side_effect=observed_lookup,
        ):
            result = hide_group(
                firestore,
                group_id,
                now=1000,
                apply=True,
            )

        self.assertTrue(result["applied"])
        self.assertEqual(observations, [False, True])
        self.assertTrue(
            firestore.collection("community_reports").records["report-one"][
                "moderation_hidden"
            ]
        )

    def test_zero_report_guard_never_writes_report_appearing_on_second_query(self):
        firestore = FakeFirestore()
        group_id = "group-qa-race"
        moderation_id = hashlib.sha256(group_id.encode()).hexdigest()
        firestore.collection(
            "community_report_moderation"
        ).records[moderation_id] = {
            "group_id": group_id,
            "hidden": False,
        }
        original_lookup = moderation_tool._documents_for_group
        report_queries = 0
        late_report = {
            "group_id": group_id,
            "owner_key": "late-private-owner",
            "public_field": "unchanged",
        }

        def inject_on_second_query(db, collection, selected_group_id):
            nonlocal report_queries
            if collection == "community_reports":
                report_queries += 1
                if report_queries == 2:
                    db.collection(collection).records["late-report"] = dict(
                        late_report
                    )
            return original_lookup(db, collection, selected_group_id)

        with patch.object(
            moderation_tool,
            "_documents_for_group",
            side_effect=inject_on_second_query,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "community_report_set_changed",
            ):
                hide_group(
                    firestore,
                    group_id,
                    now=1000,
                    apply=True,
                    expected_report_count=0,
                )

        self.assertEqual(report_queries, 2)
        self.assertEqual(
            firestore.collection("community_reports").records["late-report"],
            late_report,
        )

    def test_restore_zero_report_guard_fails_before_batch_mutation(self):
        firestore = FakeFirestore()
        group_id = "group-qa-restore-race"
        report = {
            "group_id": group_id,
            "owner_key": "late-private-owner",
            "public_field": "unchanged",
        }
        firestore.collection("community_reports").records["late-report"] = dict(
            report
        )
        firestore.collection("community_report_flags").records["qa-flag"] = {
            "group_id": group_id,
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "community_report_set_changed",
        ):
            restore_group(
                firestore,
                group_id,
                now=1000,
                apply=True,
                expected_report_count=0,
            )

        self.assertEqual(
            firestore.collection("community_reports").records["late-report"],
            report,
        )
        self.assertIn(
            "qa-flag",
            firestore.collection("community_report_flags").records,
        )

    def test_explicit_source_guard_cannot_be_redirected_by_public_report(self):
        firestore = FakeFirestore()
        report_id = "qa-private-report-link"
        expected_owner = "qa-private-owner"
        moderation_id = hashlib.sha256(b"group-qa-source").hexdigest()
        firestore.collection(
            "community_report_moderation"
        ).records[moderation_id] = {
            "group_id": "group-qa-source",
            "report_ids": [report_id],
            "report_sources": {report_id: expected_owner},
        }
        public_report = {
            "owner_key": "different-public-owner",
            "public_field": "unchanged",
        }
        firestore.collection("community_reports").records[report_id] = dict(
            public_report
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "community_public_report_unexpected",
        ):
            block_source(
                firestore,
                report_id,
                hours=24,
                now=1000,
                apply=True,
                expected_owner_key=expected_owner,
                require_report_absent=True,
            )

        self.assertEqual(
            firestore.collection("community_reports").records[report_id],
            public_report,
        )
        self.assertEqual(
            firestore.collection("community_source_blocks").records,
            {},
        )

    def test_ambiguous_private_source_never_blocks_or_unblocks(self):
        firestore = FakeFirestore()
        report_id = "qa-ambiguous-private-report"
        for group_id, owner_key in (
            ("group-qa-ambiguous-one", "qa-private-owner-one"),
            ("group-qa-ambiguous-two", "qa-private-owner-two"),
        ):
            moderation_id = hashlib.sha256(group_id.encode()).hexdigest()
            firestore.collection(
                "community_report_moderation"
            ).records[moderation_id] = {
                "group_id": group_id,
                "report_ids": [report_id],
                "report_sources": {report_id: owner_key},
            }

        for action in (
            lambda: block_source(
                firestore,
                report_id,
                hours=24,
                now=1000,
                apply=True,
            ),
            lambda: unblock_source(
                firestore,
                report_id,
                apply=True,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "community_private_source_ambiguous",
            ):
                action()

        self.assertEqual(
            firestore.collection("community_source_blocks").records,
            {},
        )

    def test_remove_writes_group_gate_before_the_deletion_query(self):
        firestore = FakeFirestore()
        group_id = "group-race"
        firestore.collection("community_reports").records["report-one"] = {
            "group_id": group_id,
            "owner_key": "private-owner",
        }
        observations = []
        original_lookup = moderation_tool._documents_for_group

        def observed_lookup(db, collection, selected_group_id):
            moderation_id = hashlib.sha256(group_id.encode()).hexdigest()
            gate = db.collection("community_report_moderation").records.get(
                moderation_id,
                {},
            )
            observations.append((collection, bool(gate.get("hidden", False))))
            return original_lookup(db, collection, selected_group_id)

        with patch.object(
            moderation_tool,
            "_documents_for_group",
            side_effect=observed_lookup,
        ):
            result = remove_group(
                firestore,
                group_id,
                now=1000,
                apply=True,
            )

        self.assertTrue(result["applied"])
        self.assertIn(("community_reports", False), observations)
        self.assertIn(("community_reports", True), observations)
        self.assertEqual(firestore.collection("community_reports").records, {})
        moderation = next(iter(
            firestore.collection("community_report_moderation").records.values()
        ))
        self.assertTrue(moderation["hidden"])

    def test_hide_and_remove_chunk_groups_larger_than_one_firestore_batch(self):
        group_id = "group-large"
        firestore = FakeFirestore()
        for index in range(MAX_ADMIN_BATCH_WRITES + 1):
            firestore.collection("community_reports").records[f"report-{index}"] = {
                "group_id": group_id,
                "owner_key": f"owner-{index}",
            }

        hidden = hide_group(
            firestore,
            group_id,
            now=1000,
            apply=True,
        )
        removed = remove_group(
            firestore,
            group_id,
            now=1001,
            apply=True,
        )

        self.assertEqual(hidden["reports"], MAX_ADMIN_BATCH_WRITES + 1)
        self.assertEqual(removed["reports"], MAX_ADMIN_BATCH_WRITES + 1)
        self.assertEqual(firestore.collection("community_reports").records, {})

    def test_remove_keeps_private_snapshot_for_24_hours(self):
        firestore = FakeFirestore()
        group_id = "group-one"
        private_owner = "private-owner-hash"
        firestore.collection("community_reports").records["report-one"] = {
            "group_id": group_id,
            "owner_key": private_owner,
        }

        result = remove_group(
            firestore,
            group_id,
            now=1000,
            apply=True,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(firestore.collection("community_reports").records, {})
        moderation = next(iter(
            firestore.collection("community_report_moderation").records.values()
        ))
        self.assertEqual(moderation["report_ids"], ["report-one"])
        self.assertEqual(moderation["report_sources"]["report-one"], private_owner)
        self.assertNotIn(private_owner, str(result))
        inspected = inspect_group(firestore, group_id, now=1001)
        self.assertEqual(inspected["report_ids"], ["report-one"])
        self.assertEqual(inspected["flag_count"], 0)
        self.assertNotIn(private_owner, str(inspected))


if __name__ == "__main__":
    unittest.main()
