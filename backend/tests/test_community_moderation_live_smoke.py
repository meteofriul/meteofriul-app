import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

from tools import smoke_community_moderation_live as live_smoke


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

    def create(self, payload):
        if self.document_id in self.collection.records:
            raise RuntimeError("already_exists")
        self.collection.records[self.document_id] = dict(payload)
        self.collection.db.history.append((
            "create",
            self.collection.name,
            self.document_id,
            dict(payload),
        ))

    def set(self, payload, merge=False):
        current = dict(self.collection.records.get(self.document_id) or {})
        stored = {**current, **payload} if merge else dict(payload)
        self.collection.records[self.document_id] = stored
        self.collection.db.history.append((
            "set",
            self.collection.name,
            self.document_id,
            dict(payload),
        ))

    def delete(self):
        self.collection.records.pop(self.document_id, None)
        self.collection.db.history.append((
            "delete",
            self.collection.name,
            self.document_id,
            None,
        ))


class FakeQuery:
    def __init__(self, collection, filters=None, limit_count=None):
        self.collection = collection
        self.filters = list(filters or [])
        self.limit_count = limit_count

    def where(self, *, filter):
        return FakeQuery(
            self.collection,
            [
                *self.filters,
                (filter.field_path, filter.op_string, filter.value),
            ],
            self.limit_count,
        )

    def limit(self, count):
        return FakeQuery(self.collection, self.filters, int(count))

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
                elif operator == ">":
                    accepted = value > expected
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
        if self.limit_count is not None:
            return rows[: self.limit_count]
        return rows


class FakeCollection:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.records = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def where(self, *, filter):
        return FakeQuery(self).where(filter=filter)

    def stream(self):
        return FakeQuery(self).stream()


class FakeBatch:
    def __init__(self):
        self.operations = []

    def create(self, document, payload):
        self.operations.append(("create", document, dict(payload), False))

    def set(self, document, payload, merge=False):
        self.operations.append(("set", document, dict(payload), merge))

    def delete(self, document):
        self.operations.append(("delete", document, None, False))

    def commit(self):
        # Firestore batches are atomic.  Check every create precondition before
        # applying any operation so collision tests model that guarantee.
        for operation, document, _payload, _merge in self.operations:
            if (
                operation == "create"
                and document.document_id in document.collection.records
            ):
                raise RuntimeError("already_exists")
        for operation, document, payload, merge in self.operations:
            if operation == "create":
                document.create(payload)
            elif operation == "set":
                document.set(payload, merge=merge)
            else:
                document.delete()


class FakeTransaction:
    def set(self, document, payload, merge=False):
        document.set(payload, merge=merge)

    def delete(self, document):
        document.delete()


class FakeFirestore:
    def __init__(self, project="meteo-friul"):
        self.project = project
        self.collections = {}
        self.history = []

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection(self, name))

    def batch(self):
        return FakeBatch()

    def transaction(self):
        return FakeTransaction()


def immediate_transaction(operation):
    return operation


class CommunityModerationLiveSmokeTests(unittest.TestCase):
    NOW = 1_000_000
    RUN_TOKEN = "a" * 24

    def setUp(self):
        self.firestore = FakeFirestore()

    def run_smoke(
        self,
        *,
        apply,
        hold_seconds=0,
        evidence_emitter=None,
        sleep_fn=None,
    ):
        return live_smoke.run_smoke(
            self.firestore,
            apply=apply,
            now=self.NOW,
            run_token=self.RUN_TOKEN,
            hold_seconds=hold_seconds,
            transactional_decorator=immediate_transaction,
            evidence_emitter=evidence_emitter or (lambda _payload: None),
            sleep_fn=sleep_fn or (lambda _seconds: None),
        )

    def test_default_main_is_read_only_dry_run(self):
        output = io.StringIO()
        with patch.object(
            live_smoke.moderation_cli,
            "hide_group",
            wraps=live_smoke.moderation_cli.hide_group,
        ) as hide, redirect_stdout(output):
            exit_code = live_smoke.main(
                [],
                db=self.firestore,
                now=self.NOW,
                run_token=self.RUN_TOKEN,
                transactional_decorator=immediate_transaction,
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["planned_private_qa_documents"], 4)
        self.assertEqual(payload["community_reports_created"], 0)
        self.assertEqual(self.firestore.history, [])
        hide.assert_not_called()

    def test_hold_cli_default_bounds_and_apply_compatibility(self):
        self.assertEqual(
            live_smoke.build_parser().parse_args([]).hold_seconds,
            0,
        )
        for argv in (
            ["--hold-seconds", "0"],
            ["--hold-seconds", "1"],
            ["--apply", "--hold-seconds", "-1"],
            ["--apply", "--hold-seconds", "121"],
            ["--apply", "--hold-seconds", "1.5"],
        ):
            with self.subTest(argv=argv):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                    live_smoke.main(
                        argv,
                        db=self.firestore,
                        now=self.NOW,
                        run_token=self.RUN_TOKEN,
                    )
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(self.firestore.history, [])

        sleeps = []
        result = self.run_smoke(
            apply=True,
            hold_seconds=live_smoke.MAX_HOLD_SECONDS,
            sleep_fn=sleeps.append,
        )
        self.assertEqual(result["hold_seconds"], 120)
        self.assertEqual(sleeps, [120.0])

        with self.assertRaisesRegex(
            live_smoke.CommunityModerationLiveSmokeError,
            "hold_seconds_requires_apply",
        ):
            self.run_smoke(apply=False, hold_seconds=1)
        with self.assertRaisesRegex(
            live_smoke.CommunityModerationLiveSmokeError,
            "hold_seconds_out_of_bounds",
        ):
            self.run_smoke(apply=True, hold_seconds=121)

    def test_apply_uses_real_actions_twice_deduplicates_and_cleans(self):
        digest_document = self.firestore.collection(
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        ).document(live_smoke.digest_service.DIGEST_STATE_DOCUMENT)
        original_digest_state = {
            "last_digest_id": "preexisting-sanitized-id",
            "seen": {"existing-ref": "existing-fingerprint"},
            "flag_counts": {"existing-ref": 2},
            "updated_at_timestamp": datetime.fromtimestamp(
                self.NOW - 10,
                timezone.utc,
            ),
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW + 100_000,
                timezone.utc,
            ),
        }
        # Seed directly so setup writes do not obscure smoke-test history.
        digest_document.collection.records[
            digest_document.document_id
        ] = dict(original_digest_state)

        with patch.object(
            live_smoke.moderation_cli,
            "hide_group",
            wraps=live_smoke.moderation_cli.hide_group,
        ) as hide, patch.object(
            live_smoke.moderation_cli,
            "restore_group",
            wraps=live_smoke.moderation_cli.restore_group,
        ) as restore, patch.object(
            live_smoke.moderation_cli,
            "block_source",
            wraps=live_smoke.moderation_cli.block_source,
        ) as block, patch.object(
            live_smoke.moderation_cli,
            "unblock_source",
            wraps=live_smoke.moderation_cli.unblock_source,
        ) as unblock, patch.object(
            live_smoke.digest_service,
            "produce_moderation_digest",
            wraps=live_smoke.digest_service.produce_moderation_digest,
        ) as digest:
            result = self.run_smoke(apply=True)

        self.assertTrue(result["applied"])
        self.assertTrue(result["checks"]["digest_retry_deduplicated"])
        self.assertTrue(result["checks"]["digest_acknowledged"])
        self.assertTrue(result["checks"]["cleanup"])
        self.assertEqual(result["community_reports_created"], 0)
        self.assertFalse(result["contains_private_keys"])
        hide.assert_called_once()
        restore.assert_called_once()
        block.assert_called_once()
        unblock.assert_called_once()
        self.assertEqual(digest.call_count, 2)
        self.assertEqual(
            [call.kwargs["now"] for call in digest.call_args_list],
            [self.NOW, self.NOW],
        )

        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
            live_smoke.REPORTS_COLLECTION,
        ):
            self.assertEqual(
                self.firestore.collection(collection).records,
                {},
                collection,
            )
        self.assertEqual(
            digest_document.collection.records[digest_document.document_id],
            original_digest_state,
        )
        self.assertFalse(any(
            collection == live_smoke.REPORTS_COLLECTION
            for _operation, collection, _document_id, _payload
            in self.firestore.history
        ))

        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        self.assertEqual(
            [
                call.kwargs["state_document_id"]
                for call in digest.call_args_list
            ],
            [
                identity.digest_state_document_id,
                identity.digest_state_document_id,
            ],
        )
        self.assertTrue(all(
            call.kwargs["state_document_id"]
            != live_smoke.digest_service.DIGEST_STATE_DOCUMENT
            for call in digest.call_args_list
        ))
        serialized = json.dumps(result, sort_keys=True)
        for private_value in (
            identity.owner_key,
            identity.flagger_key,
            identity.report_id,
            identity.marker,
        ):
            self.assertNotIn(private_value, serialized)

    def test_applied_writes_have_timestamp_ttls_with_expected_horizons(self):
        self.run_smoke(apply=True)

        self.assertEqual(
            self.firestore.collection(
                live_smoke.digest_service.DIGEST_STATE_COLLECTION
            ).records,
            {},
        )

        flag_create = next(
            payload
            for operation, collection, _document_id, payload
            in self.firestore.history
            if operation == "create"
            and collection == live_smoke.FLAGS_COLLECTION
        )
        moderation_create = next(
            payload
            for operation, collection, _document_id, payload
            in self.firestore.history
            if operation == "create"
            and collection == live_smoke.MODERATION_COLLECTION
        )
        source_block_admin_write = next(
            payload
            for operation, collection, _document_id, payload
            in self.firestore.history
            if operation == "set"
            and collection == live_smoke.SOURCE_BLOCKS_COLLECTION
            and payload.get("reason") == "administrative_moderation"
        )
        digest_write = next(
            payload
            for operation, collection, _document_id, payload
            in self.firestore.history
            if operation == "set"
            and collection
            == live_smoke.digest_service.DIGEST_STATE_COLLECTION
            and "last_digest_id" in payload
        )

        for payload, origin_field, horizon in (
            (flag_create, "created_at_timestamp", 24 * 60 * 60),
            (moderation_create, "updated_at", 24 * 60 * 60),
            (source_block_admin_write, "updated_at", 24 * 60 * 60),
            (
                digest_write,
                "updated_at_timestamp",
                live_smoke.digest_service.DIGEST_STATE_RETENTION_SECONDS,
            ),
        ):
            self.assertIsInstance(payload["expires_at_timestamp"], datetime)
            self.assertEqual(
                payload["expires_at_timestamp"].timestamp()
                - payload[origin_field].timestamp(),
                horizon,
            )

        self.assertEqual(
            digest_write["last_delivered_at_timestamp"].timestamp(),
            self.NOW,
        )

    def test_evidence_ready_precedes_hold_and_finally_unblock(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        observations = []

        def emit(payload):
            observations.append(("event", dict(payload)))
            self.assertEqual(payload["ttl_sample_count"], 4)
            self.assertEqual(payload["hold_seconds"], 12)
            self.assertEqual(
                payload["event"],
                "community_moderation_live_smoke_evidence_ready",
            )
            for collection in (
                live_smoke.FLAGS_COLLECTION,
                live_smoke.MODERATION_COLLECTION,
                live_smoke.SOURCE_BLOCKS_COLLECTION,
                live_smoke.digest_service.DIGEST_STATE_COLLECTION,
            ):
                self.assertEqual(
                    len(self.firestore.collection(collection).records),
                    1,
                    collection,
                )
            serialized = json.dumps(payload, sort_keys=True)
            self.assertNotIn(identity.owner_key, serialized)
            self.assertNotIn(identity.flagger_key, serialized)
            self.assertNotIn(identity.report_id, serialized)

        def sleep(seconds):
            observations.append(("sleep", seconds))
            self.assertTrue(
                self.firestore.collection(
                    live_smoke.SOURCE_BLOCKS_COLLECTION
                ).records
            )

        with patch.object(
            live_smoke.moderation_cli,
            "unblock_source",
            wraps=live_smoke.moderation_cli.unblock_source,
        ) as unblock:
            result = self.run_smoke(
                apply=True,
                hold_seconds=12,
                evidence_emitter=emit,
                sleep_fn=sleep,
            )

        self.assertEqual(
            [item[0] for item in observations],
            ["event", "sleep"],
        )
        self.assertEqual(observations[1][1], 12.0)
        unblock.assert_called_once()
        self.assertEqual(result["hold_seconds"], 12)
        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
            live_smoke.digest_service.DIGEST_STATE_COLLECTION,
        ):
            self.assertEqual(self.firestore.collection(collection).records, {})

    def test_concurrent_shared_digest_write_during_hold_is_preserved(self):
        digest_collection = self.firestore.collection(
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        )
        singleton_id = live_smoke.digest_service.DIGEST_STATE_DOCUMENT
        baseline = {
            "last_digest_id": "production-before-hold",
            "seen": {},
            "flag_counts": {},
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW + 100_000,
                timezone.utc,
            ),
        }
        concurrent = {
            "last_digest_id": "production-concurrent-write",
            "seen": {"new-production": "fingerprint"},
            "flag_counts": {"new-production": 1},
            "last_emitted_at_timestamp": datetime.fromtimestamp(
                self.NOW + 1,
                timezone.utc,
            ),
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW + 100_001,
                timezone.utc,
            ),
        }
        digest_collection.records[singleton_id] = dict(baseline)

        def concurrent_write(_seconds):
            digest_collection.records[singleton_id] = dict(concurrent)

        result = self.run_smoke(
            apply=True,
            hold_seconds=1,
            sleep_fn=concurrent_write,
        )

        self.assertTrue(result["checks"]["shared_digest_state_untouched"])
        self.assertEqual(digest_collection.records[singleton_id], concurrent)
        self.assertEqual(set(digest_collection.records), {singleton_id})

    def test_evidence_event_print_is_explicitly_flushed(self):
        with patch("builtins.print") as print_mock:
            self.run_smoke(
                apply=True,
                evidence_emitter=live_smoke._print_evidence_ready,
            )

        print_mock.assert_called_once()
        serialized = print_mock.call_args.args[0]
        self.assertIn(
            "community_moderation_live_smoke_evidence_ready",
            serialized,
        )
        self.assertTrue(print_mock.call_args.kwargs["flush"])

    def test_crash_point_contains_only_inert_ttl_owned_qa_documents(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        captured = {}

        def capture_then_interrupt(_payload):
            for collection in (
                live_smoke.FLAGS_COLLECTION,
                live_smoke.MODERATION_COLLECTION,
                live_smoke.SOURCE_BLOCKS_COLLECTION,
                live_smoke.digest_service.DIGEST_STATE_COLLECTION,
            ):
                captured[collection] = {
                    document_id: dict(payload)
                    for document_id, payload in self.firestore.collection(
                        collection
                    ).records.items()
                }
            raise KeyboardInterrupt()

        with self.assertRaisesRegex(
            live_smoke.CommunityModerationLiveSmokeError,
            "unexpected_operation_failure",
        ):
            self.run_smoke(
                apply=True,
                evidence_emitter=capture_then_interrupt,
            )

        self.assertEqual(
            set(captured[live_smoke.FLAGS_COLLECTION]),
            {identity.flag_document_id},
        )
        self.assertEqual(
            set(captured[live_smoke.MODERATION_COLLECTION]),
            {identity.moderation_document_id},
        )
        self.assertEqual(
            set(captured[live_smoke.SOURCE_BLOCKS_COLLECTION]),
            {identity.source_block_document_id},
        )
        self.assertEqual(
            set(captured[live_smoke.digest_service.DIGEST_STATE_COLLECTION]),
            {identity.digest_state_document_id},
        )
        for collection, records in captured.items():
            payload = next(iter(records.values()))
            self.assertIsInstance(
                payload.get("expires_at_timestamp"),
                datetime,
                collection,
            )
        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
        ):
            payload = next(iter(captured[collection].values()))
            self.assertEqual(
                payload[live_smoke.QA_MARKER_FIELD],
                identity.marker,
            )
        digest_payload = next(iter(captured[
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        ].values()))
        self.assertEqual(
            digest_payload[
                live_smoke.digest_service.DIGEST_STATE_OWNER_MARKER_FIELD
            ],
            identity.marker,
        )
        self.assertEqual(
            self.firestore.collection(live_smoke.REPORTS_COLLECTION).records,
            {},
        )

    def test_hold_failure_cleans_qa_and_preserves_shared_digest(self):
        digest_collection = self.firestore.collection(
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        )
        original = {
            "last_digest_id": "before-hold",
            "seen": {},
            "flag_counts": {},
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW + 100_000,
                timezone.utc,
            ),
        }
        digest_collection.records[
            live_smoke.digest_service.DIGEST_STATE_DOCUMENT
        ] = dict(original)

        def fail_hold(_seconds):
            raise RuntimeError("private-hold-detail")

        with patch.object(
            live_smoke.moderation_cli,
            "unblock_source",
            wraps=live_smoke.moderation_cli.unblock_source,
        ) as unblock:
            with self.assertRaisesRegex(
                live_smoke.CommunityModerationLiveSmokeError,
                "evidence_hold_failed",
            ):
                self.run_smoke(
                    apply=True,
                    hold_seconds=5,
                    sleep_fn=fail_hold,
                )

        unblock.assert_called_once()
        self.assertEqual(
            digest_collection.records[
                live_smoke.digest_service.DIGEST_STATE_DOCUMENT
            ],
            original,
        )
        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
            live_smoke.REPORTS_COLLECTION,
        ):
            self.assertEqual(self.firestore.collection(collection).records, {})

    def test_active_shared_digest_guard_is_never_read_or_written(self):
        digest_collection = self.firestore.collection(
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        )
        shared_state = {
            "last_digest_id": "concurrent-production-state",
            "seen": {"production": "fingerprint"},
            "flag_counts": {"production": 1},
            "last_emitted_at_timestamp": datetime.fromtimestamp(
                self.NOW - 1,
                timezone.utc,
            ),
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW + 100_000,
                timezone.utc,
            ),
        }
        digest_collection.records[
            live_smoke.digest_service.DIGEST_STATE_DOCUMENT
        ] = dict(shared_state)

        result = self.run_smoke(apply=True)

        self.assertTrue(result["checks"]["shared_digest_state_untouched"])
        self.assertEqual(
            digest_collection.records[
                live_smoke.digest_service.DIGEST_STATE_DOCUMENT
            ],
            shared_state,
        )
        self.assertFalse(any(
            collection == live_smoke.digest_service.DIGEST_STATE_COLLECTION
            and document_id
            == live_smoke.digest_service.DIGEST_STATE_DOCUMENT
            for _operation, collection, document_id, _payload
            in self.firestore.history
        ))

    def test_cleanup_marker_check_and_delete_are_one_transaction(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        refs = live_smoke._document_refs(self.firestore, identity)
        refs["flag"].set({live_smoke.QA_MARKER_FIELD: identity.marker})
        refs["moderation"].set(
            {live_smoke.QA_MARKER_FIELD: "concurrent-replacement"}
        )
        refs["source_block"].set(
            {live_smoke.QA_MARKER_FIELD: identity.marker}
        )
        refs["digest_state"].set({
            live_smoke.digest_service.DIGEST_STATE_OWNER_MARKER_FIELD: (
                identity.marker
            )
        })

        with self.assertRaisesRegex(
            live_smoke.CommunityModerationLiveSmokeError,
            "smoke_cleanup_failed",
        ):
            live_smoke._cleanup(
                self.firestore,
                identity,
                refs,
                qa_write_attempted=True,
                source_unblock_required=False,
                transactional_decorator=immediate_transaction,
            )

        # Because every marker is checked before any transaction delete, the
        # foreign replacement prevents the entire cleanup from mutating state.
        for name in ("flag", "moderation", "source_block", "digest_state"):
            self.assertTrue(refs[name].get().exists, name)

    def test_guarded_actions_fail_closed_when_qa_documents_are_replaced(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )

        def replacement_decorator(document, replacement):
            def decorate(operation):
                def execute(transaction):
                    document.collection.records[document.document_id] = dict(
                        replacement
                    )
                    return operation(transaction)

                return execute

            return decorate

        replacement = {
            live_smoke.QA_MARKER_FIELD: "concurrent-replacement",
            "public_field": "must-remain-unchanged",
        }

        with self.subTest(action="hide"):
            firestore = FakeFirestore()
            refs = live_smoke._document_refs(firestore, identity)
            refs["moderation"].set(
                live_smoke._moderation_payload(identity, now=self.NOW)
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "community_qa_document_ownership_lost",
            ):
                live_smoke.moderation_cli.hide_group(
                    firestore,
                    identity.group_id,
                    now=self.NOW,
                    apply=True,
                    expected_report_count=0,
                    expected_marker=identity.marker,
                    marker_field=live_smoke.QA_MARKER_FIELD,
                    transactional_decorator=replacement_decorator(
                        refs["moderation"], replacement
                    ),
                )
            self.assertEqual(
                refs["moderation"].get().to_dict(),
                replacement,
            )

        with self.subTest(action="restore"):
            firestore = FakeFirestore()
            refs = live_smoke._document_refs(firestore, identity)
            refs["moderation"].set(
                live_smoke._moderation_payload(identity, now=self.NOW)
            )
            refs["flag"].set(
                live_smoke._flag_payload(identity, now=self.NOW)
            )
            moderation_before = refs["moderation"].get().to_dict()
            with self.assertRaisesRegex(
                RuntimeError,
                "community_qa_document_ownership_lost",
            ):
                live_smoke.moderation_cli.restore_group(
                    firestore,
                    identity.group_id,
                    now=self.NOW,
                    apply=True,
                    expected_report_count=0,
                    expected_marker=identity.marker,
                    marker_field=live_smoke.QA_MARKER_FIELD,
                    transactional_decorator=replacement_decorator(
                        refs["flag"], replacement
                    ),
                )
            self.assertEqual(refs["flag"].get().to_dict(), replacement)
            self.assertEqual(
                refs["moderation"].get().to_dict(),
                moderation_before,
            )

        for action in ("block", "unblock"):
            with self.subTest(action=action):
                firestore = FakeFirestore()
                refs = live_smoke._document_refs(firestore, identity)
                refs["moderation"].set(
                    live_smoke._moderation_payload(identity, now=self.NOW)
                )
                refs["source_block"].set(
                    live_smoke._source_block_reservation_payload(
                        identity,
                        now=self.NOW,
                    )
                )
                decorator = replacement_decorator(
                    refs["source_block"], replacement
                )
                with self.assertRaisesRegex(
                    RuntimeError,
                    "community_qa_document_ownership_lost",
                ):
                    if action == "block":
                        live_smoke.moderation_cli.block_source(
                            firestore,
                            identity.report_id,
                            hours=24,
                            now=self.NOW,
                            apply=True,
                            expected_owner_key=identity.owner_key,
                            require_report_absent=True,
                            expected_target_marker=identity.marker,
                            marker_field=live_smoke.QA_MARKER_FIELD,
                            transactional_decorator=decorator,
                        )
                    else:
                        live_smoke.moderation_cli.unblock_source(
                            firestore,
                            identity.report_id,
                            apply=True,
                            expected_owner_key=identity.owner_key,
                            require_report_absent=True,
                            expected_target_marker=identity.marker,
                            marker_field=live_smoke.QA_MARKER_FIELD,
                            transactional_decorator=decorator,
                        )
                self.assertEqual(
                    refs["source_block"].get().to_dict(),
                    replacement,
                )

    def test_cleanup_race_never_deletes_a_replaced_document(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        refs = live_smoke._document_refs(self.firestore, identity)
        for name in ("flag", "moderation", "source_block"):
            refs[name].set({live_smoke.QA_MARKER_FIELD: identity.marker})
        refs["digest_state"].set({
            live_smoke.digest_service.DIGEST_STATE_OWNER_MARKER_FIELD: (
                identity.marker
            )
        })
        replacement = {
            live_smoke.QA_MARKER_FIELD: "concurrent-replacement",
            "public_field": "must-remain-unchanged",
        }

        def replace_before_cleanup(operation):
            def execute(transaction):
                refs["moderation"].collection.records[
                    refs["moderation"].document_id
                ] = dict(replacement)
                return operation(transaction)

            return execute

        with self.assertRaisesRegex(
            live_smoke.CommunityModerationLiveSmokeError,
            "smoke_cleanup_failed",
        ):
            live_smoke._cleanup(
                self.firestore,
                identity,
                refs,
                qa_write_attempted=True,
                source_unblock_required=False,
                transactional_decorator=replace_before_cleanup,
            )

        self.assertEqual(
            refs["moderation"].get().to_dict(),
            replacement,
        )
        for name in ("flag", "source_block", "digest_state"):
            self.assertTrue(refs[name].get().exists, name)

    def test_expired_shared_digest_is_ignored_and_preserved(self):
        digest_collection = self.firestore.collection(
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        )
        original = {
            "last_digest_id": "expired-before-smoke",
            "last_emitted_at_timestamp": datetime.fromtimestamp(
                self.NOW - 1,
                timezone.utc,
            ),
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW - 1,
                timezone.utc,
            ),
        }
        digest_collection.records[
            live_smoke.digest_service.DIGEST_STATE_DOCUMENT
        ] = dict(original)

        self.run_smoke(apply=True)

        new_digest_write = next(
            payload
            for operation, collection, _document_id, payload
            in self.firestore.history
            if operation == "set"
            and collection
            == live_smoke.digest_service.DIGEST_STATE_COLLECTION
            and "last_delivered_at_timestamp" in payload
        )
        self.assertEqual(
            new_digest_write["last_delivered_at_timestamp"].timestamp(),
            self.NOW,
        )
        self.assertEqual(
            digest_collection.records[
                live_smoke.digest_service.DIGEST_STATE_DOCUMENT
            ],
            original,
        )

    def test_second_digest_failure_preserves_shared_and_cleans_qa(self):
        digest_collection = self.firestore.collection(
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        )
        original = {
            "last_digest_id": "before",
            "seen": {},
            "flag_counts": {},
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW + 100_000,
                timezone.utc,
            ),
        }
        digest_collection.records[
            live_smoke.digest_service.DIGEST_STATE_DOCUMENT
        ] = dict(original)
        real_producer = live_smoke.digest_service.produce_moderation_digest
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_producer(*args, **kwargs)
            raise RuntimeError("private-owner-must-not-escape")

        with patch.object(
            live_smoke.digest_service,
            "produce_moderation_digest",
            side_effect=fail_second,
        ):
            with self.assertRaisesRegex(
                live_smoke.CommunityModerationLiveSmokeError,
                "digest_second_apply_failed",
            ):
                self.run_smoke(apply=True)

        self.assertEqual(calls, 2)
        self.assertEqual(
            digest_collection.records[
                live_smoke.digest_service.DIGEST_STATE_DOCUMENT
            ],
            original,
        )
        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
            live_smoke.REPORTS_COLLECTION,
        ):
            self.assertEqual(self.firestore.collection(collection).records, {})

    def test_ambiguous_first_digest_commit_cleans_only_isolated_state(self):
        digest_collection = self.firestore.collection(
            live_smoke.digest_service.DIGEST_STATE_COLLECTION
        )
        singleton_id = live_smoke.digest_service.DIGEST_STATE_DOCUMENT
        singleton = {
            "last_digest_id": "production-before-ambiguous-commit",
            "seen": {"production": "fingerprint"},
            "flag_counts": {"production": 1},
            "expires_at_timestamp": datetime.fromtimestamp(
                self.NOW + 100_000,
                timezone.utc,
            ),
        }
        digest_collection.records[singleton_id] = dict(singleton)
        real_producer = live_smoke.digest_service.produce_moderation_digest
        calls = 0

        def commit_then_lose_ack(*args, **kwargs):
            nonlocal calls
            calls += 1
            real_producer(*args, **kwargs)
            raise RuntimeError("private-ambiguous-ack-detail")

        with patch.object(
            live_smoke.digest_service,
            "produce_moderation_digest",
            side_effect=commit_then_lose_ack,
        ):
            with self.assertRaisesRegex(
                live_smoke.CommunityModerationLiveSmokeError,
                "digest_first_apply_failed",
            ):
                self.run_smoke(apply=True)

        self.assertEqual(calls, 1)
        self.assertEqual(digest_collection.records, {singleton_id: singleton})
        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
            live_smoke.REPORTS_COLLECTION,
        ):
            self.assertEqual(self.firestore.collection(collection).records, {})

    def test_unblock_failure_still_deletes_source_block_and_seed(self):
        with patch.object(
            live_smoke.moderation_cli,
            "unblock_source",
            side_effect=RuntimeError("private-owner-must-not-escape"),
        ):
            with self.assertRaisesRegex(
                live_smoke.CommunityModerationLiveSmokeError,
                "smoke_cleanup_failed",
            ):
                self.run_smoke(apply=True)

        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
            live_smoke.REPORTS_COLLECTION,
        ):
            self.assertEqual(self.firestore.collection(collection).records, {})

    def test_preexisting_qa_document_collision_fails_without_mutation(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        cases = (
            (
                live_smoke.FLAGS_COLLECTION,
                identity.flag_document_id,
            ),
            (
                live_smoke.MODERATION_COLLECTION,
                identity.moderation_document_id,
            ),
            (
                live_smoke.SOURCE_BLOCKS_COLLECTION,
                identity.source_block_document_id,
            ),
            (
                live_smoke.digest_service.DIGEST_STATE_COLLECTION,
                identity.digest_state_document_id,
            ),
            (
                live_smoke.REPORTS_COLLECTION,
                identity.report_id,
            ),
        )
        for collection, document_id in cases:
            with self.subTest(collection=collection):
                firestore = FakeFirestore()
                firestore.collection(collection).records[document_id] = {
                    "preexisting": True,
                }
                with self.assertRaisesRegex(
                    live_smoke.CommunityModerationLiveSmokeError,
                    "qa_document_collision",
                ):
                    live_smoke.run_smoke(
                        firestore,
                        apply=True,
                        now=self.NOW,
                        run_token=self.RUN_TOKEN,
                        transactional_decorator=immediate_transaction,
                    )
                self.assertEqual(
                    firestore.collection(collection).records[document_id],
                    {"preexisting": True},
                )
                self.assertEqual(firestore.history, [])

    def test_group_and_private_snapshot_collisions_are_rejected(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        for payload in (
            {"group_id": identity.group_id},
            {"report_ids": [identity.report_id]},
        ):
            with self.subTest(payload=payload):
                firestore = FakeFirestore()
                firestore.collection(
                    live_smoke.MODERATION_COLLECTION
                ).records["noncanonical-preexisting-id"] = dict(payload)
                with self.assertRaisesRegex(
                    live_smoke.CommunityModerationLiveSmokeError,
                    "qa_document_collision",
                ):
                    live_smoke.run_smoke(
                        firestore,
                        apply=False,
                        now=self.NOW,
                        run_token=self.RUN_TOKEN,
                    )

    def test_report_appearing_after_hide_query_is_never_mutated_or_deleted(self):
        identity = live_smoke._qa_identity(
            self.RUN_TOKEN,
            now=self.NOW,
        )
        late_report_id = "late-public-report"
        late_report = {
            "group_id": identity.group_id,
            "owner_key": "late-public-private-owner",
            "public_field": "must-remain-unchanged",
        }
        real_lookup = live_smoke.moderation_cli._documents_for_group
        injected = False

        def inject_after_transaction_query(
            db,
            collection,
            group_id,
            *,
            transaction=None,
        ):
            nonlocal injected
            rows = real_lookup(
                db,
                collection,
                group_id,
                transaction=transaction,
            )
            if (
                not injected
                and collection == live_smoke.REPORTS_COLLECTION
                and transaction is not None
            ):
                injected = True
                db.collection(collection).records[late_report_id] = dict(
                    late_report
                )
            return rows

        with patch.object(
            live_smoke.moderation_cli,
            "_documents_for_group",
            side_effect=inject_after_transaction_query,
        ):
            with self.assertRaisesRegex(
                live_smoke.CommunityModerationLiveSmokeError,
                "community_report_collision",
            ):
                self.run_smoke(apply=True)

        self.assertEqual(
            self.firestore.collection(live_smoke.REPORTS_COLLECTION).records,
            {late_report_id: late_report},
        )
        self.assertFalse(any(
            collection == live_smoke.REPORTS_COLLECTION
            for _operation, collection, _document_id, _payload
            in self.firestore.history
        ))
        for collection in (
            live_smoke.FLAGS_COLLECTION,
            live_smoke.MODERATION_COLLECTION,
            live_smoke.SOURCE_BLOCKS_COLLECTION,
            live_smoke.digest_service.DIGEST_STATE_COLLECTION,
        ):
            self.assertEqual(self.firestore.collection(collection).records, {})

    def test_wrong_project_fails_before_any_read_or_write_action(self):
        firestore = FakeFirestore(project="not-meteo-friul")

        with self.assertRaisesRegex(
            live_smoke.CommunityModerationLiveSmokeError,
            "firestore_project_mismatch",
        ):
            live_smoke.run_smoke(
                firestore,
                apply=True,
                now=self.NOW,
                run_token=self.RUN_TOKEN,
                transactional_decorator=immediate_transaction,
            )

        self.assertEqual(firestore.collections, {})
        self.assertEqual(firestore.history, [])

    def test_cli_failure_output_never_echoes_private_exception_details(self):
        output = io.StringIO()
        with patch.object(
            live_smoke.moderation_cli,
            "hide_group",
            side_effect=RuntimeError(
                "owner=private-owner flagger=private-flagger report=private-report"
            ),
        ), redirect_stdout(output):
            exit_code = live_smoke.main(
                ["--apply"],
                db=self.firestore,
                now=self.NOW,
                run_token=self.RUN_TOKEN,
                transactional_decorator=immediate_transaction,
            )

        serialized = output.getvalue()
        payload = json.loads(serialized)
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "hide_action_failed")
        self.assertNotIn("private-owner", serialized)
        self.assertNotIn("private-flagger", serialized)
        self.assertNotIn("private-report", serialized)
        self.assertEqual(
            self.firestore.collection(live_smoke.FLAGS_COLLECTION).records,
            {},
        )
        self.assertEqual(
            self.firestore.collection(
                live_smoke.MODERATION_COLLECTION
            ).records,
            {},
        )


if __name__ == "__main__":
    unittest.main()
