"""Opt-in red diagnostics for confirmed community and push invariants.

The filename intentionally does not match pytest's ordinary ``test_*.py``
discovery. Run it through ``pytest.social-geo-diagnostics.ini``. These tests
must become green only when the corresponding production invariant is fixed;
they are not expected-failure tests.
"""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Barrier, BrokenBarrierError, Event

import pytest

from app.contracts.live import (
    CommunityReportConfirmationCreate,
    CommunityReportCreate,
    CommunityReportDelete,
    CommunityReportFlagCreate,
)
from app.repositories.community import (
    COOLDOWNS_COLLECTION,
    CONFIRMATIONS_COLLECTION,
    FLAGS_COLLECTION,
    MODERATION_COLLECTION,
    RATE_LIMITS_COLLECTION,
    REPORTS_COLLECTION,
    CommunityMutationTargetUnavailable,
    CommunityRepository,
)
from app.repositories.push import (
    PUSH_DEVICES_COLLECTION,
    PushDeviceRepository,
    hash_installation_id,
)
from app.services.community import (
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    CommunityService,
    CommunityServiceError,
)
from app.services.location import LocationCatalog
from tests.test_community_repository import (
    FakeCollection as CommunityFakeCollection,
    FakeFirestore as CommunityFakeFirestore,
    FakeQuery as CommunityFakeQuery,
    fake_transactional as community_fake_transactional,
)
from tests.test_push_repository import (
    FakeFirestore as PushFakeFirestore,
    fake_transactional as push_fake_transactional,
)
from tools.moderate_community_reports import hide_group, remove_group


NOW = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
COMMUNITY_NOW = NOW.timestamp()
DEVICE_ID = hash_installation_id("0123456789abcdef0123456789abcdef")
APP_CHECK_APP_ID = "1:1234567890:android:diagnostic"


class _ModerationCompatibleCommunityQuery(CommunityFakeQuery):
    """Add document references needed by the real moderation delete helper."""

    def stream(self):
        snapshots = super().stream()
        for snapshot in snapshots:
            snapshot.reference = self.collection.document(snapshot.id)
        return snapshots


class _ModerationCompatibleCommunityCollection(CommunityFakeCollection):
    def where(self, field_path=None, op_string=None, value=None, *, filter=None):
        return _ModerationCompatibleCommunityQuery(self).where(
            field_path,
            op_string,
            value,
            filter=filter,
        )


class _ModerationCompatibleCommunityFirestore(CommunityFakeFirestore):
    def collection(self, name):
        return self.collections.setdefault(
            name,
            _ModerationCompatibleCommunityCollection(self),
        )


class _AfterGroupReadRepository(CommunityRepository):
    """Delegate real reads/writes while opening one controlled stale window."""

    def __init__(self, *args, events, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = events
        self.after_group_read = None

    def list_group_reports(self, group_id, now):
        result = super().list_group_reports(group_id, now)
        snapshot = deepcopy(result[0])
        self.events.append(("group-read", [report["id"] for report in snapshot]))
        hook = self.after_group_read
        self.after_group_read = None
        if hook is not None:
            hook(group_id, snapshot)
        return result

    def update_confirmation_strict(self, *args, **kwargs):
        self.events.append(("confirmation-strict-enter", None))
        result = super().update_confirmation_strict(*args, **kwargs)
        self.events.append(("confirmation-strict-return", None))
        return result

    def flag_group_strict(self, *args, **kwargs):
        self.events.append(("flag-strict-enter", None))
        result = super().flag_group_strict(*args, **kwargs)
        self.events.append(("flag-strict-return", None))
        return result


class _ControlledUndoRepository(CommunityRepository):
    """Coordinate two real service undo paths without timing assumptions."""

    def __init__(
        self,
        *args,
        read_barrier,
        strict_entered,
        strict_release,
        lane,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.read_barrier = read_barrier
        self.strict_entered = strict_entered
        self.strict_release = strict_release
        self.lane = lane
        self.read_barrier_used = False

    def get_report(self, report_id, now):
        result = super().get_report(report_id, now)
        if self.read_barrier_used:
            return result
        self.read_barrier_used = True
        try:
            self.read_barrier.wait(timeout=5)
        except BrokenBarrierError as error:
            raise AssertionError(
                f"undo_race_harness_timeout:precheck:{self.lane}"
            ) from error
        return result

    def delete_report_and_cooldown_strict(self, report_id, *, client_key):
        self.strict_entered.set()
        if not self.strict_release.wait(timeout=5):
            raise AssertionError(
                f"undo_race_harness_timeout:strict-release:{self.lane}"
            )
        return super().delete_report_and_cooldown_strict(
            report_id,
            client_key=client_key,
        )


def _community_repository(firestore, repository_type=CommunityRepository, **kwargs):
    return repository_type(
        lambda: firestore,
        storage_mode="firestore",
        transactional_decorator=community_fake_transactional,
        **kwargs,
    )


def _community_service(
    repository,
    *,
    report_id,
    now=COMMUNITY_NOW,
):
    return CommunityService(
        catalog=LocationCatalog(),
        repository=repository,
        now=lambda: now,
        report_id_factory=lambda: report_id,
    )


def _community_create_command(*, client_id="report-owner"):
    return CommunityReportCreate(
        type_id="rain",
        lat=45.95689,
        lon=12.66051,
        selected_place="Pordenone",
        client_id=client_id,
        accepted_terms=True,
        policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
    )


def _seed_community_report(
    firestore,
    *,
    report_id,
    client_id="report-owner",
    now=COMMUNITY_NOW,
):
    repository = _community_repository(firestore)
    service = _community_service(repository, report_id=report_id, now=now)
    created = service.create_report(
        _community_create_command(client_id=client_id),
        client_host="diagnostic-create-host",
    )
    return created, repository


def _moderation_removal_hook(firestore, events, *, now):
    def remove_after_service_read(group_id, reports):
        events.append(("moderation-remove-enter", [report["id"] for report in reports]))
        result = remove_group(
            firestore,
            group_id,
            now=now,
            apply=True,
        )
        events.append(("moderation-remove-return", result["reports"]))

    return remove_after_service_read


def _committed_report_writes(firestore, report_id, *, after_transaction):
    report_collection = firestore.collection(REPORTS_COLLECTION)
    return [
        (operation, payload, merge)
        for transaction in firestore.transactions[after_transaction:]
        for operation, document, payload, merge in transaction.committed_operations
        if operation in {"set", "update"}
        and document.collection is report_collection
        and document.id == report_id
    ]


def _transaction_reads_documents(
    firestore,
    transaction,
    expected_documents,
):
    observed = {
        (collection, document_id)
        for collection, document_id, selected_transaction in firestore.read_log
        if selected_transaction is transaction
    }
    return all(
        (firestore.collection(collection_name), document_id) in observed
        for collection_name, document_id in expected_documents
    )


def _without_fields(payload, *fields):
    return {
        key: value
        for key, value in payload.items()
        if key not in set(fields)
    }


def _push_repository(firestore):
    return PushDeviceRepository(
        lambda: firestore,
        transactional_decorator=push_fake_transactional,
    )


def _register_android(
    repository,
    *,
    now=NOW,
    municipality=None,
    location_mode="automatic_gps",
    location_evidence=None,
):
    return repository.upsert_device(
        device_id=DEVICE_ID,
        token="diagnostic-fcm-token-long-enough",
        platform="android",
        app_check_app_id=APP_CHECK_APP_ID,
        app_version="3.0.0-diagnostic",
        language="it",
        municipality=municipality or {"istat": "030129", "name": "Udine"},
        locality=None,
        location_mode=location_mode,
        location_evidence=location_evidence,
        preferences={"official_alerts": True, "weather_notices": True},
        max_devices=5,
        now=now,
    )


def test_confirmation_materialization_never_recreates_a_deleted_report():
    firestore = CommunityFakeFirestore()
    repository = _community_repository(firestore)
    deleted_report_id = "report-deleted-before-confirmation-commit"

    with pytest.raises(CommunityMutationTargetUnavailable):
        repository.update_confirmation_strict(
            "group-stale-snapshot",
            report_ids=[deleted_report_id],
            client_key="client-confirmation",
            vote="yes",
            expires_at=4_600,
            global_limit=60,
            global_window_seconds=60,
            max_voters=500,
            now=1_000,
        )

    reports = firestore.collection(REPORTS_COLLECTION).records
    assert deleted_report_id not in reports


def test_duplicate_undo_does_not_delete_the_cooldown_owned_by_a_newer_report():
    firestore = CommunityFakeFirestore()
    repository = _community_repository(firestore)
    client_key = "client-with-newer-report"
    newer_cooldown = {
        "client_key": client_key,
        "report_id": "newer-report",
        "until": 9_999,
    }
    firestore.collection(COOLDOWNS_COLLECTION).records[client_key] = dict(newer_cooldown)

    # Models the second copy of an old undo arriving after the first undo and
    # after a newer create has installed a replacement cooldown.
    repository.delete_report_and_cooldown_strict(
        "already-deleted-old-report",
        client_key=client_key,
    )

    assert firestore.collection(COOLDOWNS_COLLECTION).records.get(client_key) == newer_cooldown


def test_hidden_group_flag_never_recreates_report_deleted_after_snapshot():
    firestore = CommunityFakeFirestore()
    repository = _community_repository(firestore)
    group_id = "group-hidden-before-flag-commit"
    deleted_report_id = "report-deleted-before-hidden-flag-commit"
    moderation_id = hashlib.sha256(group_id.encode("utf-8")).hexdigest()
    firestore.collection(MODERATION_COLLECTION).records[moderation_id] = {
        "expires_at_timestamp": datetime.fromtimestamp(4_600, timezone.utc),
        "flaggers": {"earlier-flagger": "misuse"},
        "group_id": group_id,
        "hidden": True,
        "hidden_reason": "administrative_moderation",
        "owner_keys": ["owner-deleted-report"],
        "report_ids": [deleted_report_id],
        "report_sources": {deleted_report_id: "owner-deleted-report"},
    }

    # Models a report that the service observed before another request deleted
    # it. The strict transaction must not turn that stale ID into a new partial
    # report while materializing the already-hidden moderation state.
    repository.flag_group_strict(
        group_id,
        report_ids=[deleted_report_id],
        owner_keys=["owner-deleted-report"],
        report_sources={deleted_report_id: "owner-deleted-report"},
        client_key="later-flagger",
        reason="duplicate",
        expires_at=4_600,
        global_limit=30,
        global_window_seconds=60,
        client_limit=6,
        client_window_seconds=60,
        max_flaggers=500,
        now=1_000,
    )

    reports = firestore.collection(REPORTS_COLLECTION).records
    assert deleted_report_id not in reports


def test_service_confirmation_never_recreates_report_removed_after_group_read():
    firestore = _ModerationCompatibleCommunityFirestore()
    report_id = "report-a-late-confirmation"
    created, _seed_repository = _seed_community_report(
        firestore,
        report_id=report_id,
    )
    transaction_count = len(firestore.transactions)
    events = []
    repository = _community_repository(
        firestore,
        _AfterGroupReadRepository,
        events=events,
    )
    repository.after_group_read = _moderation_removal_hook(
        firestore,
        events,
        now=COMMUNITY_NOW + 1,
    )
    service = _community_service(
        repository,
        report_id="unused-confirmation-id",
        now=COMMUNITY_NOW + 2,
    )
    rate_limits_before = deepcopy(
        firestore.collection(RATE_LIMITS_COLLECTION).records
    )

    error = None
    try:
        service.confirm_report(
            created.report.groupId,
            CommunityReportConfirmationCreate(
                vote="yes",
                client_id="late-confirmation-voter",
                accepted_terms=True,
                policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
            ),
            client_host="diagnostic-confirm-host",
        )
    except CommunityServiceError as caught:
        error = caught

    reports = firestore.collection(REPORTS_COLLECTION).records
    moderation_id = hashlib.sha256(
        created.report.groupId.encode("utf-8")
    ).hexdigest()
    strict_transactions = firestore.transactions[transaction_count:]
    assert events[:4] == [
        ("group-read", [report_id]),
        ("moderation-remove-enter", [report_id]),
        ("moderation-remove-return", 1),
        ("confirmation-strict-enter", None),
    ]
    assert {
        "report_present": report_id in reports,
        "committed_report_writes": len(_committed_report_writes(
            firestore,
            report_id,
            after_transaction=transaction_count,
        )),
        "transaction_read_target_and_gate": any(
            _transaction_reads_documents(
                firestore,
                transaction,
                (
                    (REPORTS_COLLECTION, report_id),
                    (MODERATION_COLLECTION, moderation_id),
                ),
            )
            for transaction in strict_transactions
        ),
        "confirmation_documents": len(
            firestore.collection(CONFIRMATIONS_COLLECTION).records
        ),
        "committed_confirmation_writes": sum(
            1
            for transaction in strict_transactions
            for operation, document, _payload, _merge
            in transaction.committed_operations
            if operation in {"set", "update"}
            and document.collection
            is firestore.collection(CONFIRMATIONS_COLLECTION)
        ),
        "rate_limits_unchanged": (
            firestore.collection(RATE_LIMITS_COLLECTION).records
            == rate_limits_before
        ),
    } == {
        "report_present": False,
        "committed_report_writes": 0,
        "transaction_read_target_and_gate": True,
        "confirmation_documents": 1,
        "committed_confirmation_writes": 0,
        "rate_limits_unchanged": True,
    }
    assert error is not None
    assert error.status_code == 404
    moderation = firestore.collection(MODERATION_COLLECTION).records[moderation_id]
    assert moderation["hidden"] is True
    assert moderation["hidden_reason"] == "administrative_removal"
    confirmation = firestore.collection(CONFIRMATIONS_COLLECTION).records[
        moderation_id
    ]
    assert confirmation["validity_status"] == "rejected"
    assert confirmation["votes"] == {}
    assert repository._confirmations == {}


def test_service_flag_never_recreates_report_removed_after_group_read():
    firestore = _ModerationCompatibleCommunityFirestore()
    report_id = "report-a-late-flag"
    created, _seed_repository = _seed_community_report(
        firestore,
        report_id=report_id,
    )
    transaction_count = len(firestore.transactions)
    events = []
    repository = _community_repository(
        firestore,
        _AfterGroupReadRepository,
        events=events,
    )
    repository.after_group_read = _moderation_removal_hook(
        firestore,
        events,
        now=COMMUNITY_NOW + 1,
    )
    service = _community_service(
        repository,
        report_id="unused-flag-id",
        now=COMMUNITY_NOW + 2,
    )
    rate_limits_before = deepcopy(
        firestore.collection(RATE_LIMITS_COLLECTION).records
    )

    result = service.flag_report_group(
        created.report.groupId,
        CommunityReportFlagCreate(
            reason="duplicate",
            client_id="late-flagger",
        ),
        client_host="diagnostic-flag-host",
    )

    reports = firestore.collection(REPORTS_COLLECTION).records
    moderation_id = hashlib.sha256(
        created.report.groupId.encode("utf-8")
    ).hexdigest()
    strict_transactions = firestore.transactions[transaction_count:]
    assert events[:4] == [
        ("group-read", [report_id]),
        ("moderation-remove-enter", [report_id]),
        ("moderation-remove-return", 1),
        ("flag-strict-enter", None),
    ]
    assert {
        "report_present": report_id in reports,
        "committed_report_writes": len(_committed_report_writes(
            firestore,
            report_id,
            after_transaction=transaction_count,
        )),
        "transaction_read_target_and_gate": any(
            _transaction_reads_documents(
                firestore,
                transaction,
                (
                    (REPORTS_COLLECTION, report_id),
                    (MODERATION_COLLECTION, moderation_id),
                ),
            )
            for transaction in strict_transactions
        ),
        "flag_documents": len(firestore.collection(FLAGS_COLLECTION).records),
        "rate_limits_unchanged": (
            firestore.collection(RATE_LIMITS_COLLECTION).records
            == rate_limits_before
        ),
    } == {
        "report_present": False,
        "committed_report_writes": 0,
        "transaction_read_target_and_gate": True,
        "flag_documents": 0,
        "rate_limits_unchanged": True,
    }
    moderation = next(
        iter(firestore.collection(MODERATION_COLLECTION).records.values())
    )
    assert moderation["hidden"] is True
    assert moderation["hidden_reason"] == "administrative_removal"
    assert repository._moderation[created.report.groupId] == moderation
    assert repository._flags == {}
    assert result.ok is True
    assert result.hidden_global is True


def test_service_duplicate_undo_never_deletes_newer_report_cooldown():
    firestore = _ModerationCompatibleCommunityFirestore()
    owner_client_id = "duplicate-undo-owner"
    report_a_id = "report-a-duplicate-undo"
    created_a, _seed_repository = _seed_community_report(
        firestore,
        report_id=report_a_id,
        client_id=owner_client_id,
    )
    transaction_count = len(firestore.transactions)
    initial_cooldowns = firestore.collection(COOLDOWNS_COLLECTION).records
    assert len(initial_cooldowns) == 1
    initial_cooldown_key = next(iter(initial_cooldowns))
    read_barrier = Barrier(2)
    strict_entered = [Event(), Event()]
    strict_release = [Event(), Event()]
    repositories = [
        _community_repository(
            firestore,
            _ControlledUndoRepository,
            read_barrier=read_barrier,
            strict_entered=strict_entered[index],
            strict_release=strict_release[index],
            lane=index,
        )
        for index in range(2)
    ]
    services = [
        _community_service(
            repository,
            report_id=f"unused-undo-{index}",
            now=COMMUNITY_NOW + 10,
        )
        for index, repository in enumerate(repositories)
    ]
    undo_command = CommunityReportDelete(client_id=owner_client_id)
    executor = ThreadPoolExecutor(max_workers=2)
    futures = []
    try:
        futures = [
            executor.submit(
                service.delete_report,
                created_a.report.id,
                undo_command,
                client_host=f"diagnostic-undo-host-{index}",
            )
            for index, service in enumerate(services)
        ]
        for index, entered in enumerate(strict_entered):
            assert entered.wait(timeout=5), (
                f"undo_race_harness_timeout:strict-enter:{index}"
            )

        strict_release[0].set()
        first_result = futures[0].result(timeout=5)
        assert first_result.ok is True
        assert report_a_id not in firestore.collection(REPORTS_COLLECTION).records

        report_b_id = "report-b-after-first-undo"
        created_b, _newer_repository = _seed_community_report(
            firestore,
            report_id=report_b_id,
            client_id=owner_client_id,
            now=COMMUNITY_NOW + 11,
        )
        assert created_b.report.id == report_b_id
        report_b_before = deepcopy(
            firestore.collection(REPORTS_COLLECTION).records[report_b_id]
        )
        cooldowns = firestore.collection(COOLDOWNS_COLLECTION).records
        assert len(cooldowns) == 1
        cooldown_key = next(iter(cooldowns))
        assert cooldown_key == initial_cooldown_key
        cooldown_b_before = deepcopy(cooldowns[cooldown_key])
        assert cooldown_b_before["report_id"] == report_b_id

        strict_release[1].set()
        second_result = futures[1].result(timeout=5)
        assert second_result.ok is True

        assert {
            "report_b_unchanged": (
                firestore.collection(REPORTS_COLLECTION).records.get(report_b_id)
                == report_b_before
            ),
            "cooldown_b_unchanged": (
                firestore.collection(COOLDOWNS_COLLECTION).records.get(cooldown_key)
                == cooldown_b_before
            ),
            "transactional_undo_pair_reads": sum(
                _transaction_reads_documents(
                    firestore,
                    transaction,
                    (
                        (REPORTS_COLLECTION, report_a_id),
                        (COOLDOWNS_COLLECTION, cooldown_key),
                    ),
                )
                and not any(
                    operation in {"set", "update"}
                    for operation, _document, _payload, _merge
                    in transaction.committed_operations
                )
                for transaction in firestore.transactions[transaction_count:]
            ),
        } == {
            "report_b_unchanged": True,
            "cooldown_b_unchanged": True,
            "transactional_undo_pair_reads": 2,
        }
    finally:
        for release in strict_release:
            release.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_service_strict_confirmation_preserves_a_complete_active_report():
    firestore = _ModerationCompatibleCommunityFirestore()
    report_id = "report-positive-confirmation"
    created, repository = _seed_community_report(
        firestore,
        report_id=report_id,
    )
    memory_report_before = deepcopy(repository._reports[report_id])
    transaction_count = len(firestore.transactions)
    report_before = deepcopy(
        firestore.collection(REPORTS_COLLECTION).records[report_id]
    )
    service = _community_service(
        repository,
        report_id="unused-positive-confirmation",
        now=COMMUNITY_NOW + 1,
    )

    result = service.confirm_report(
        created.report.groupId,
        CommunityReportConfirmationCreate(
            vote="yes",
            client_id="positive-confirmation-voter",
            accepted_terms=True,
            policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
        ),
        client_host="diagnostic-positive-confirm-host",
    )

    report_after = firestore.collection(REPORTS_COLLECTION).records[report_id]
    materialized_confirmation_fields = (
        "confirmation_yes",
        "confirmation_no",
        "denial_count",
        "map_withdrawn",
        "validity_status",
        "temporal_status",
    )
    assert result.confirmations.yes == 1
    assert result.confirmations.no == 0
    assert _without_fields(
        report_after,
        *materialized_confirmation_fields,
    ) == _without_fields(
        report_before,
        *materialized_confirmation_fields,
    )
    assert {
        field: report_after.get(field)
        for field in materialized_confirmation_fields
    } == {
        "confirmation_yes": 1,
        "confirmation_no": 0,
        "denial_count": 0,
        "map_withdrawn": False,
        "validity_status": "verified",
        "temporal_status": "active",
    }
    assert [
        operation
        for operation, _payload, _merge in _committed_report_writes(
            firestore,
            report_id,
            after_transaction=transaction_count,
        )
    ] == ["update"]
    confirmation_id = hashlib.sha256(
        created.report.groupId.encode("utf-8")
    ).hexdigest()
    durable_confirmation = firestore.collection(
        CONFIRMATIONS_COLLECTION
    ).records[confirmation_id]
    assert repository._confirmations[created.report.groupId] == durable_confirmation
    memory_report_after = repository._reports[report_id]
    assert _without_fields(
        memory_report_after,
        *materialized_confirmation_fields,
    ) == _without_fields(
        memory_report_before,
        *materialized_confirmation_fields,
    )
    assert {
        field: memory_report_after.get(field)
        for field in materialized_confirmation_fields
    } == {
        "confirmation_yes": 1,
        "confirmation_no": 0,
        "denial_count": 0,
        "map_withdrawn": False,
        "validity_status": "verified",
        "temporal_status": "active",
    }


def test_service_strict_flag_preserves_a_complete_active_visible_report():
    firestore = _ModerationCompatibleCommunityFirestore()
    report_id = "report-positive-visible-flag"
    created, repository = _seed_community_report(
        firestore,
        report_id=report_id,
    )
    memory_report_before = deepcopy(repository._reports[report_id])
    transaction_count = len(firestore.transactions)
    report_before = deepcopy(
        firestore.collection(REPORTS_COLLECTION).records[report_id]
    )
    service = _community_service(
        repository,
        report_id="unused-positive-visible-flag",
        now=COMMUNITY_NOW + 1,
    )

    result = service.flag_report_group(
        created.report.groupId,
        CommunityReportFlagCreate(
            reason="inaccurate",
            client_id="positive-visible-flagger",
        ),
        client_host="diagnostic-positive-visible-flag-host",
    )

    report_after = firestore.collection(REPORTS_COLLECTION).records[report_id]
    assert result.ok is True
    assert result.hidden_global is False
    assert result.already_reported is False
    assert result.flag_count == 1
    assert report_after == report_before
    assert _committed_report_writes(
        firestore,
        report_id,
        after_transaction=transaction_count,
    ) == []
    moderation = next(
        iter(firestore.collection(MODERATION_COLLECTION).records.values())
    )
    assert moderation["hidden"] is False
    assert moderation["report_ids"] == [report_id]
    flags = firestore.collection(FLAGS_COLLECTION).records
    assert len(flags) == 1
    assert repository._reports[report_id] == memory_report_before
    assert repository._moderation[created.report.groupId] == moderation
    assert repository._flags == flags


def test_service_strict_flag_preserves_a_complete_active_hidden_report():
    firestore = _ModerationCompatibleCommunityFirestore()
    report_id = "report-positive-hidden-flag"
    created, repository = _seed_community_report(
        firestore,
        report_id=report_id,
    )
    memory_report_before = deepcopy(repository._reports[report_id])
    hidden = hide_group(
        firestore,
        created.report.groupId,
        now=COMMUNITY_NOW + 1,
        apply=True,
    )
    assert hidden["reports"] == 1
    report_before = deepcopy(
        firestore.collection(REPORTS_COLLECTION).records[report_id]
    )
    transaction_count = len(firestore.transactions)
    service = _community_service(
        repository,
        report_id="unused-positive-flag",
        now=COMMUNITY_NOW + 2,
    )

    result = service.flag_report_group(
        created.report.groupId,
        CommunityReportFlagCreate(
            reason="inaccurate",
            client_id="positive-hidden-flagger",
        ),
        client_host="diagnostic-positive-flag-host",
    )

    report_after = firestore.collection(REPORTS_COLLECTION).records[report_id]
    assert result.ok is True
    assert result.hidden_global is True
    assert _without_fields(
        report_after,
        "moderation_hidden",
        "moderation_hidden_at_timestamp",
        "moderation_reason",
    ) == _without_fields(
        report_before,
        "moderation_hidden",
        "moderation_hidden_at_timestamp",
        "moderation_reason",
    )
    assert report_after["moderation_hidden"] is True
    assert [
        operation
        for operation, _payload, _merge in _committed_report_writes(
            firestore,
            report_id,
            after_transaction=transaction_count,
        )
    ] == ["update"]
    moderation_id = hashlib.sha256(
        created.report.groupId.encode("utf-8")
    ).hexdigest()
    durable_moderation = firestore.collection(
        MODERATION_COLLECTION
    ).records[moderation_id]
    assert repository._moderation[created.report.groupId] == durable_moderation
    assert repository._flags == {}
    memory_report_after = repository._reports[report_id]
    assert _without_fields(
        memory_report_after,
        "moderation_hidden",
        "moderation_hidden_at",
        "moderation_reason",
    ) == _without_fields(
        memory_report_before,
        "moderation_hidden",
        "moderation_hidden_at",
        "moderation_reason",
    )
    assert memory_report_after["moderation_hidden"] is True
    assert memory_report_after["moderation_hidden_at"] == COMMUNITY_NOW + 2
    assert memory_report_after["moderation_reason"] == "administrative_moderation"


def test_service_strict_single_undo_allows_a_legitimate_replacement_report():
    firestore = _ModerationCompatibleCommunityFirestore()
    owner_client_id = "positive-undo-owner"
    report_a_id = "report-positive-undo-a"
    created_a, repository = _seed_community_report(
        firestore,
        report_id=report_a_id,
        client_id=owner_client_id,
    )
    service = _community_service(
        repository,
        report_id="unused-positive-undo",
        now=COMMUNITY_NOW + 10,
    )

    result = service.delete_report(
        created_a.report.id,
        CommunityReportDelete(client_id=owner_client_id),
        client_host="diagnostic-positive-undo-host",
    )

    assert result.ok is True
    assert report_a_id not in firestore.collection(REPORTS_COLLECTION).records
    assert firestore.collection(COOLDOWNS_COLLECTION).records == {}
    assert report_a_id not in repository._reports
    assert repository._cooldowns == {}

    report_b_id = "report-positive-undo-b"
    created_b, replacement_repository = _seed_community_report(
        firestore,
        report_id=report_b_id,
        client_id=owner_client_id,
        now=COMMUNITY_NOW + 11,
    )
    assert created_b.report.id == report_b_id
    assert report_b_id in firestore.collection(REPORTS_COLLECTION).records
    cooldowns = firestore.collection(COOLDOWNS_COLLECTION).records
    assert len(cooldowns) == 1
    assert next(iter(cooldowns.values()))["report_id"] == report_b_id
    assert replacement_repository._reports[report_b_id]["id"] == report_b_id
    assert len(replacement_repository._cooldowns) == 1


def test_older_location_evidence_cannot_overwrite_a_newer_push_target():
    firestore = PushFakeFirestore()
    repository = _push_repository(firestore)
    _register_android(repository)

    newer_capture = NOW + timedelta(minutes=5)
    older_capture = NOW
    repository.update_android_location_target(
        device_id=DEVICE_ID,
        app_check_app_id=APP_CHECK_APP_ID,
        municipality={"istat": "030129", "name": "Udine"},
        locality={"id": "irdat:udine", "name": "Udine"},
        location_evidence={
            "accuracy_m": 15.0,
            "captured_at": newer_capture,
            "received_at": NOW + timedelta(minutes=6),
            "trigger": "foreground",
        },
        now=NOW + timedelta(minutes=6),
    )
    repository.update_android_location_target(
        device_id=DEVICE_ID,
        app_check_app_id=APP_CHECK_APP_ID,
        municipality={"istat": "093033", "name": "Pordenone"},
        locality={"id": "irdat:pordenone", "name": "Pordenone"},
        location_evidence={
            "accuracy_m": 20.0,
            "captured_at": older_capture,
            "received_at": NOW + timedelta(minutes=7),
            "trigger": "periodic",
        },
        now=NOW + timedelta(minutes=7),
    )

    stored = firestore.collection(PUSH_DEVICES_COLLECTION).records[DEVICE_ID]
    assert stored["municipality"]["name"] == "Udine"
    assert stored["location_evidence"]["captured_at"] == newer_capture


def test_unregister_dominates_a_register_from_an_older_logical_revision():
    firestore = PushFakeFirestore()
    repository = _push_repository(firestore)
    _register_android(repository, now=NOW)
    repository.unregister_device(device_id=DEVICE_ID, now=NOW + timedelta(minutes=2))

    # ``now`` stands in for the older intent that the current contract cannot
    # carry: there is no client state revision/tombstone to distinguish this
    # delayed request from a fresh opt-in.
    _register_android(repository, now=NOW + timedelta(minutes=1))

    assert DEVICE_ID not in firestore.collection(PUSH_DEVICES_COLLECTION).records
