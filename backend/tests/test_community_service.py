import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, RLock
from unittest.mock import Mock

from app.contracts.live import (
    CommunityReportConfirmationCreate,
    CommunityReportCreate,
    CommunityReportDelete,
    CommunityReportFlagCreate,
)
from app.repositories.community import CommunityRepository, CommunityRepositoryUnavailable
from app.services.community import (
    COMMUNITY_GUIDELINES_POLICY_VERSION,
    CommunityService,
    CommunityServiceError,
    CommunitySafetyContractDrift,
    REPORT_GLOBAL_WINDOW_LIMIT,
    FLAG_CLIENT_WINDOW_LIMIT,
    FLAG_RETENTION_SECONDS,
    PUBLIC_SOURCE_KEY_BUCKET_SECONDS,
    PUBLIC_FEED_CACHE_SECONDS,
    GROUP_MUTATION_MAX_REPORTS,
)
from app.services.location import LocationCatalog


NOW = 1786269600.0
EXPECTED_LOCATION_CATALOG_SHA256 = (
    "a387ff7f1f704695361597b054556ff82a6a8739373eb0af465b81b1f3b89dae"
)
EXPECTED_CREATE_FIELDS = (
    "type_id",
    "lat",
    "lon",
    "selected_place",
    "client_id",
    "accepted_terms",
    "policy_version",
    "identity",
)
EXPECTED_CONFIRMATION_CREATE_FIELDS = (
    "vote",
    "client_id",
    "accepted_terms",
    "policy_version",
)
EXPECTED_PUBLIC_REPORT_FIELDS = (
    "id",
    "typeId",
    "typeCategory",
    "groupId",
    "place",
    "lat",
    "lon",
    "locationPrecision",
    "x",
    "y",
    "createdAt",
    "expiresAt",
    "time",
    "source",
    "sourceKey",
    "identity",
)
EXPECTED_PUBLIC_GROUP_FIELDS = EXPECTED_PUBLIC_REPORT_FIELDS + (
    "reportIds",
    "sourceKeys",
    "identities",
    "count",
    "confirmations",
)


class MutableClock:
    def __init__(self, value=NOW):
        self.value = value

    def __call__(self):
        return self.value


class CommunityServiceTests(unittest.TestCase):
    def create_service(self, clock=None, report_id="community-test-1"):
        return CommunityService(
            catalog=LocationCatalog(),
            repository=CommunityRepository(),
            now=clock or (lambda: NOW),
            report_id_factory=lambda: report_id,
        )

    @staticmethod
    def command(**updates):
        values = {
            "type_id": "rain",
            "lat": 45.95689,
            "lon": 12.66051,
            "selected_place": "Pordenone",
            "client_id": "client-1",
            "accepted_terms": True,
            "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
        }
        values.update(updates)
        return CommunityReportCreate(**values)

    @staticmethod
    def identity(alias="Clâf di Pordenon", **updates):
        values = {
            "version": 1,
            "alias": alias,
            "subject_id": "claf",
            "avatar": {
                "palette_id": "sky",
                "pattern_id": "diagonal",
                "variant": 2,
                "angle": 135,
            },
        }
        values.update(updates)
        return values

    @staticmethod
    def confirmation_command(**updates):
        values = {
            "vote": "yes",
            "client_id": "voter",
            "accepted_terms": True,
            "policy_version": COMMUNITY_GUIDELINES_POLICY_VERSION,
        }
        values.update(updates)
        return CommunityReportConfirmationCreate(**values)

    def test_empty_runtime_uses_the_canonical_215_municipality_catalog(self):
        payload = self.create_service().get_reports()

        self.assertEqual(len(payload.locations), 215)
        self.assertEqual(len({item.place for item in payload.locations}), 215)
        self.assertEqual(payload.reports, [])
        self.assertEqual(payload.map_groups, [])
        self.assertEqual(payload.source.storage, "memory")

    def test_empty_feed_exposes_the_exact_revision_owned_safety_contract(self):
        payload = self.create_service().get_reports()
        contract = payload.contract

        self.assertEqual(contract.schema_version, "community-ephemeral-safety-v1")
        self.assertEqual(
            contract.guidelines_policy_version,
            COMMUNITY_GUIDELINES_POLICY_VERSION,
        )
        self.assertEqual(
            contract.allowed_report_types,
            ("fog", "hail", "ice", "quiet", "rain", "snow", "storm", "wind"),
        )
        self.assertEqual(contract.create_fields, EXPECTED_CREATE_FIELDS)
        self.assertEqual(
            tuple(CommunityReportConfirmationCreate.model_fields),
            EXPECTED_CONFIRMATION_CREATE_FIELDS,
        )
        self.assertEqual(
            contract.public_report_fields,
            EXPECTED_PUBLIC_REPORT_FIELDS,
        )
        self.assertEqual(contract.public_group_fields, EXPECTED_PUBLIC_GROUP_FIELDS)
        self.assertEqual(contract.confirmation_fields, ("yes", "no"))
        self.assertEqual(contract.location_fields, ("place", "lat", "lon"))
        self.assertEqual(
            contract.source_fields,
            ("id", "type", "verified", "storage", "cooldown_storage"),
        )
        self.assertEqual(
            contract.flag_reasons,
            ("inaccurate", "duplicate", "misuse"),
        )
        self.assertEqual(
            (contract.ttl_seconds, contract.cooldown_seconds, contract.max_distance_km),
            (3600, 2700, 5),
        )
        self.assertEqual(contract.location_catalog_count, 215)
        self.assertEqual(
            contract.location_catalog_sha256,
            EXPECTED_LOCATION_CATALOG_SHA256,
        )
        self.assertEqual(contract.location_precision, "zone")
        self.assertFalse(contract.accepts_free_text)
        self.assertFalse(contract.accepts_media)
        self.assertFalse(contract.requires_account)
        self.assertEqual(contract.user_flag_visibility, "local_only")
        self.assertFalse(contract.automatic_global_hide)
        self.assertEqual(
            contract.public_source_key.model_dump(),
            {
                "algorithm": "sha256-truncated-lower-hex",
                "pattern": "^[0-9a-f]{24}$",
                "length": 24,
                "rotation_bucket_seconds": 86400,
            },
        )

        canonical_lines = "".join(
            f"{location.place}\t{location.lat:.5f}\t{location.lon:.5f}\n"
            for location in payload.locations
        )
        self.assertEqual(
            hashlib.sha256(canonical_lines.encode("utf-8")).hexdigest(),
            contract.location_catalog_sha256,
        )

    def test_populated_feed_keeps_the_same_contract_and_exact_public_fields(self):
        empty_contract = self.create_service().get_reports().contract
        service = self.create_service()
        service.create_report(self.command(), client_host="127.0.0.1")

        payload = service.get_reports()

        self.assertEqual(payload.contract, empty_contract)
        self.assertEqual(len(payload.reports), 1)
        self.assertEqual(
            tuple(payload.reports[0].model_dump()),
            EXPECTED_PUBLIC_REPORT_FIELDS,
        )
        self.assertEqual(
            tuple(payload.map_groups[0].model_dump()),
            EXPECTED_PUBLIC_GROUP_FIELDS,
        )
        self.assertRegex(payload.reports[0].sourceKey or "", r"^[0-9a-f]{24}$")

    def test_contract_fails_closed_when_the_canonical_catalog_count_drifts(self):
        catalog = LocationCatalog()
        catalog.municipalities = catalog.municipalities[:-1]

        with self.assertRaisesRegex(
            CommunitySafetyContractDrift,
            "location_catalog_count_drift",
        ):
            CommunityService(catalog=catalog)

    def test_contract_digest_detects_catalog_order_drift(self):
        catalog = LocationCatalog()
        catalog.municipalities = tuple(reversed(catalog.municipalities))

        contract = CommunityService(catalog=catalog).get_reports().contract

        self.assertNotEqual(
            contract.location_catalog_sha256,
            EXPECTED_LOCATION_CATALOG_SHA256,
        )

    def test_public_feed_cache_collapses_reads_and_all_mutations_invalidate_it(self):
        clock = MutableClock()
        repository = CommunityRepository()
        original_list_reports = repository.list_reports
        original_list_hidden = repository.list_hidden_group_ids
        repository.list_reports = Mock(side_effect=original_list_reports)
        repository.list_hidden_group_ids = Mock(side_effect=original_list_hidden)
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=clock,
            report_id_factory=lambda: "cached-report",
        )

        first = service.get_reports()
        second = service.get_reports()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertEqual(repository.list_reports.call_count, 1)
        self.assertEqual(repository.list_hidden_group_ids.call_count, 1)

        created = service.create_report(self.command(), client_host="host")
        self.assertEqual(len(service.get_reports().reports), 1)
        self.assertEqual(repository.list_reports.call_count, 2)

        service.confirm_report(
            created.report.groupId,
            self.confirmation_command(),
            client_host="host",
        )
        self.assertEqual(service.get_reports().map_groups[0].confirmations.yes, 1)
        self.assertEqual(repository.list_reports.call_count, 3)

        service.flag_report_group(
            created.report.groupId,
            CommunityReportFlagCreate(reason="inaccurate", client_id="flagger"),
            client_host="host",
        )
        self.assertEqual(len(service.get_reports().reports), 1)
        self.assertEqual(repository.list_reports.call_count, 4)

        service.delete_report(
            created.report.id,
            CommunityReportDelete(client_id="client-1"),
            client_host="host",
        )
        self.assertEqual(service.get_reports().reports, [])
        self.assertEqual(repository.list_reports.call_count, 5)

    def test_public_feed_cache_expires_after_thirty_seconds(self):
        clock = MutableClock()
        repository = CommunityRepository()
        original_list_reports = repository.list_reports
        repository.list_reports = Mock(side_effect=original_list_reports)
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=clock,
        )

        service.get_reports()
        clock.value += PUBLIC_FEED_CACHE_SECONDS - 1
        service.get_reports()
        self.assertEqual(repository.list_reports.call_count, 1)
        clock.value += 2
        service.get_reports()
        self.assertEqual(repository.list_reports.call_count, 2)

    def test_public_feed_cache_never_outlives_the_next_report_expiry(self):
        clock = MutableClock(NOW + 3590)
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=clock,
        )
        municipality = service.catalog.match_names("Pordenone")
        self.assertIsNotNone(municipality)
        stored = service._build_report(
            type_id="rain",
            municipality=municipality,
            owner_key="owner-key",
            now=NOW,
        )
        repository.list_reports = Mock(return_value=([stored], "firestore"))

        self.assertEqual(len(service.get_reports().reports), 1)
        clock.value = NOW + 3599
        self.assertEqual(len(service.get_reports().reports), 1)
        self.assertEqual(repository.list_reports.call_count, 1)

        clock.value = NOW + 3601
        self.assertEqual(service.get_reports().reports, [])
        self.assertEqual(repository.list_reports.call_count, 2)

    def test_public_feed_discards_malformed_or_legacy_records_fail_closed(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
        )
        municipality = service.catalog.match_names("Pordenone")
        self.assertIsNotNone(municipality)
        valid = service._build_report(
            type_id="rain",
            municipality=municipality,
            owner_key="owner-key",
            now=NOW,
        )
        valid.update({
            "id": "valid-report",
            "lat": 0.123456,
            "lon": 0.654321,
            "x": 99.0,
            "y": 1.0,
        })

        invalid_records = []
        for identifier, updates in (
            ("unknown-type", {"type_id": "free-text"}),
            ("unknown-place", {"place": "Como"}),
            ("wrong-ttl", {"expires_at": NOW + 3599}),
            ("expired", {"created_at": NOW - 3600, "expires_at": NOW}),
            (
                "future",
                {"created_at": NOW + 1, "expires_at": NOW + 3601},
            ),
            ("missing-owner", {"owner_key": ""}),
        ):
            invalid_records.append({**valid, "id": identifier, **updates})
        repository.list_reports = Mock(
            return_value=([valid, *invalid_records], "firestore")
        )

        payload = service.get_reports()

        self.assertEqual([report.id for report in payload.reports], ["valid-report"])
        public = payload.reports[0]
        self.assertEqual(public.place, municipality.name)
        self.assertEqual(public.lat, municipality.latitude)
        self.assertEqual(public.lon, municipality.longitude)
        self.assertEqual(
            (public.x, public.y),
            service._map_position(municipality.latitude, municipality.longitude),
        )

    def test_create_report_publishes_zone_coordinates_and_group_contract(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="127.0.0.1")
        reports = service.get_reports()

        self.assertEqual(created.report.place, "Pordenone")
        self.assertEqual(created.report.lat, 45.95689)
        self.assertEqual(created.report.lon, 12.66051)
        self.assertEqual(created.report.locationPrecision, "zone")
        self.assertEqual((created.report.x, created.report.y), (22.85, 63.59))
        self.assertEqual(created.report.groupId, "group-rain:pordenone:496186")
        self.assertEqual(created.report.time, "")
        self.assertNotIn("gpsDistanceKm", created.report.model_dump())
        self.assertEqual(created.cooldown_until, 1786272300000)
        self.assertEqual(reports.map_groups[0].id, created.report.groupId)
        self.assertEqual(reports.map_groups[0].reportIds, ["community-test-1"])
        self.assertNotIn("accepted_terms", service.repository._reports["community-test-1"])
        self.assertNotIn("policy_version", service.repository._reports["community-test-1"])
        self.assertNotIn("gps_nearest_place", service.repository._reports["community-test-1"])
        self.assertNotIn("gps_distance_km", service.repository._reports["community-test-1"])

    def test_create_report_persists_and_publishes_an_allowlisted_identity_snapshot(self):
        service = self.create_service()
        snapshot = self.identity()

        created = service.create_report(
            self.command(identity=snapshot),
            client_host="127.0.0.1",
        )
        stored = service.repository._reports[created.report.id]
        feed = service.get_reports()

        self.assertEqual(created.report.identity.model_dump(), snapshot)
        self.assertEqual(stored["identity"], snapshot)
        self.assertEqual(feed.reports[0].identity.model_dump(), snapshot)
        self.assertEqual(
            [entry.model_dump() for entry in feed.map_groups[0].identities],
            [{"sourceKey": created.report.sourceKey, "identity": snapshot}],
        )
        self.assertNotIn("client_id", created.report.model_dump_json())
        self.assertNotIn("owner_key", created.report.model_dump_json())

    def test_report_identity_is_an_immutable_snapshot_when_input_changes(self):
        service = self.create_service()
        command = self.command(identity=self.identity())

        created = service.create_report(command, client_host="127.0.0.1")
        command.identity.alias = "Ors di Udin"
        command.identity.avatar.palette_id = "gold"

        stored = service.repository._reports[created.report.id]["identity"]
        self.assertEqual(stored["alias"], "Clâf di Pordenon")
        self.assertEqual(stored["avatar"]["palette_id"], "sky")
        self.assertEqual(
            service.get_reports().reports[0].identity.alias,
            "Clâf di Pordenon",
        )

    def test_legacy_report_keeps_source_key_fallback_without_identity(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="127.0.0.1")
        feed = service.get_reports()

        self.assertIsNone(created.report.identity)
        self.assertRegex(created.report.sourceKey or "", r"^[0-9a-f]{24}$")
        self.assertEqual(len(feed.map_groups[0].identities), 1)
        self.assertEqual(
            feed.map_groups[0].identities[0].model_dump(),
            {"sourceKey": created.report.sourceKey, "identity": None},
        )
        self.assertEqual(feed.map_groups[0].sourceKeys, [created.report.sourceKey])

    def test_malformed_stored_identity_is_omitted_without_dropping_legacy_report(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="127.0.0.1")
        service.repository._reports[created.report.id]["identity"] = {
            **self.identity(),
            "owner_key": "must-never-be-public",
        }
        service._invalidate_reports_cache()

        feed = service.get_reports()

        self.assertEqual(len(feed.reports), 1)
        self.assertIsNone(feed.reports[0].identity)
        self.assertNotIn("owner_key", feed.model_dump_json())

    def test_manual_location_correction_is_limited_to_five_kilometres(self):
        service = self.create_service()
        corrected = service.create_report(
            self.command(selected_place="Cordenons"),
            client_host="127.0.0.1",
        )
        self.assertEqual(corrected.report.place, "Cordenons")

        other_service = self.create_service(report_id="community-test-2")
        with self.assertRaises(CommunityServiceError) as context:
            other_service.create_report(
                self.command(selected_place="Udine"),
                client_host="127.0.0.1",
            )
        self.assertEqual(context.exception.status_code, 400)

    def test_strict_firestore_transaction_failure_becomes_503(self):
        repository = Mock()
        repository.lock = RLock()
        repository.requires_firestore = True
        repository.create_report_strict.side_effect = CommunityRepositoryUnavailable(
            "transaction failed"
        )
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
            report_id_factory=lambda: "community-strict-1",
        )

        with self.assertRaises(CommunityServiceError) as context:
            service.create_report(self.command(), client_host="host")

        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(
            context.exception.detail["code"],
            "community_storage_unavailable",
        )
        repository.create_report_strict.assert_called_once()
        self.assertEqual(
            repository.create_report_strict.call_args.kwargs["global_limit"],
            20,
        )
        self.assertEqual(REPORT_GLOBAL_WINDOW_LIMIT, 20)
        repository.delete_report.assert_not_called()
        repository.clear_cooldown.assert_not_called()

    def test_strict_firestore_without_a_client_never_returns_memory_success(self):
        repository = CommunityRepository(storage_mode="firestore")
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
            report_id_factory=lambda: "community-strict-3",
        )

        for _attempt in range(2):
            with self.assertRaises(CommunityServiceError) as context:
                service.create_report(self.command(), client_host="host")
            self.assertEqual(context.exception.status_code, 503)

        with self.assertRaises(CommunityRepositoryUnavailable):
            repository.list_reports(NOW)

    def test_strict_firestore_read_failures_are_503_for_get_undo_and_confirm(self):
        repository = Mock()
        repository.lock = RLock()
        repository.requires_firestore = True
        repository.list_reports.side_effect = CommunityRepositoryUnavailable("read failed")
        repository.get_report.side_effect = CommunityRepositoryUnavailable("read failed")
        repository.list_group_reports.side_effect = CommunityRepositoryUnavailable(
            "read failed"
        )
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
        )

        operations = (
            service.get_reports,
            lambda: service.delete_report(
                "report-1",
                CommunityReportDelete(client_id="client-1"),
                client_host="host",
            ),
            lambda: service.confirm_report(
                "group-1",
                self.confirmation_command(client_id="client-1"),
                client_host="host",
            ),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(CommunityServiceError) as context:
                    operation()
                self.assertEqual(context.exception.status_code, 503)

    def test_strict_firestore_mutation_failures_are_503_for_undo_and_confirm(self):
        seed_service = self.create_service()
        created = seed_service.create_report(self.command(), client_host="host")
        stored_report = dict(seed_service.repository._reports[created.report.id])

        undo_repository = Mock()
        undo_repository.lock = RLock()
        undo_repository.requires_firestore = True
        undo_repository.get_report.return_value = (stored_report, "firestore")
        undo_repository.delete_report_and_cooldown_strict.side_effect = (
            CommunityRepositoryUnavailable("batch failed")
        )
        undo_service = CommunityService(
            catalog=LocationCatalog(),
            repository=undo_repository,
            now=lambda: NOW,
        )
        with self.assertRaises(CommunityServiceError) as undo_error:
            undo_service.delete_report(
                created.report.id,
                CommunityReportDelete(client_id="client-1"),
                client_host="host",
            )
        self.assertEqual(undo_error.exception.status_code, 503)

        confirm_repository = Mock()
        confirm_repository.lock = RLock()
        confirm_repository.requires_firestore = True
        confirm_repository.list_group_reports.return_value = (
            [stored_report],
            "firestore",
        )
        confirm_repository.get_confirmation.return_value = {
            "yes": 0,
            "no": 0,
            "votes": {},
        }
        confirm_repository.update_confirmation_strict.side_effect = (
            CommunityRepositoryUnavailable("confirmation failed")
        )
        confirm_service = CommunityService(
            catalog=LocationCatalog(),
            repository=confirm_repository,
            now=lambda: NOW,
        )
        with self.assertRaises(CommunityServiceError) as confirm_error:
            confirm_service.confirm_report(
                created.report.groupId,
                self.confirmation_command(),
                client_host="vote-host",
            )
        self.assertEqual(confirm_error.exception.status_code, 503)

    def test_create_requires_current_explicit_community_consent(self):
        service = self.create_service()
        commands = (
            self.command(accepted_terms=False),
            self.command(policy_version="community-guidelines-old"),
        )

        for command in commands:
            with self.subTest(command=command):
                with self.assertRaises(CommunityServiceError) as context:
                    service.create_report(command, client_host="host")
                self.assertEqual(context.exception.status_code, 400)
                self.assertEqual(
                    context.exception.detail["code"],
                    "community_terms_required",
                )

    def test_confirmation_requires_current_explicit_community_consent(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="host")
        commands = (
            self.confirmation_command(accepted_terms=False),
            self.confirmation_command(policy_version="community-guidelines-old"),
            CommunityReportConfirmationCreate(
                vote="yes",
                client_id="voter",
                accepted_terms=True,
            ),
            CommunityReportConfirmationCreate(
                vote="yes",
                client_id="voter",
                policy_version=COMMUNITY_GUIDELINES_POLICY_VERSION,
            ),
        )

        for command in commands:
            with self.subTest(command=command):
                with self.assertRaises(CommunityServiceError) as context:
                    service.confirm_report(
                        created.report.groupId,
                        command,
                        client_host="host",
                    )
                self.assertEqual(context.exception.status_code, 400)
                self.assertEqual(
                    context.exception.detail["code"],
                    "community_terms_required",
                )
        self.assertNotIn(created.report.groupId, service.repository._confirmations)

    def test_confirmation_accepts_the_exact_play_300011_legacy_contract(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="host")

        result = service.confirm_report(
            created.report.groupId,
            CommunityReportConfirmationCreate(
                vote="yes",
                client_id="legacy-play-voter",
            ),
            client_host="legacy-play-host",
        )

        self.assertEqual(result.vote, "yes")
        self.assertEqual(result.confirmations.yes, 1)
        self.assertEqual(result.confirmations.no, 0)

    def test_rejects_unknown_types_and_outside_fvg_coordinates(self):
        service = self.create_service()
        with self.assertRaises(CommunityServiceError):
            service.create_report(self.command(type_id="unknown"), client_host="host")
        with self.assertRaises(CommunityServiceError) as context:
            service.create_report(
                self.command(lat=44.0, lon=12.0, selected_place=None),
                client_host="host",
            )
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail["code"],
            "community_region_not_enabled",
        )
        self.assertEqual(context.exception.detail["enabled_regions"], ["IT-36"])

    def test_rejects_cross_border_coordinates_inside_the_legacy_fvg_box(self):
        service = self.create_service()

        with self.assertRaises(CommunityServiceError) as context:
            service.create_report(
                self.command(
                    lat=45.956,
                    lon=13.648,
                    selected_place="Gorizia",
                ),
                client_host="host",
            )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail["code"],
            "community_region_not_enabled",
        )

    def test_cooldown_blocks_repeated_reports_for_the_same_client(self):
        service = self.create_service()
        service.create_report(self.command(), client_host="host")

        with self.assertRaises(CommunityServiceError) as context:
            service.create_report(self.command(), client_host="host")

        self.assertEqual(context.exception.status_code, 429)
        self.assertEqual(context.exception.detail["retry_after_seconds"], 2700)

    def test_owner_can_undo_within_one_minute_and_cooldown_is_cleared(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="proxy-host-a")
        deleted = service.delete_report(
            created.report.id,
            CommunityReportDelete(client_id="client-1"),
            client_host="proxy-host-b",
        )

        self.assertTrue(deleted.ok)
        self.assertEqual(service.get_reports().reports, [])
        recreated = service.create_report(
            self.command(),
            client_host="proxy-host-c",
        )
        self.assertEqual(recreated.report.id, "community-test-1")

    def test_other_client_cannot_undo_and_window_expires(self):
        clock = MutableClock()
        service = self.create_service(clock=clock)
        created = service.create_report(self.command(), client_host="proxy-host-a")

        with self.assertRaises(CommunityServiceError) as other_client:
            service.delete_report(
                created.report.id,
                CommunityReportDelete(client_id="client-id-2"),
                client_host="proxy-host-a",
            )
        self.assertEqual(other_client.exception.status_code, 403)

        clock.value += 61
        with self.assertRaises(CommunityServiceError) as expired:
            service.delete_report(
                created.report.id,
                CommunityReportDelete(client_id="client-1"),
                client_host="proxy-host-b",
            )
        self.assertEqual(expired.exception.status_code, 409)

    def test_confirmations_allow_yes_to_no_but_denial_is_sticky_and_idempotent(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="report-host")
        group_id = created.report.groupId

        first = service.confirm_report(
            group_id,
            self.confirmation_command(),
            client_host="vote-host",
        )
        repeated = service.confirm_report(
            group_id,
            self.confirmation_command(),
            client_host="vote-host",
        )
        denied = service.confirm_report(
            group_id,
            self.confirmation_command(vote="no"),
            client_host="vote-host",
        )
        repeated_denial = service.confirm_report(
            group_id,
            self.confirmation_command(vote="no"),
            client_host="vote-host",
        )
        attempted_restore = service.confirm_report(
            group_id,
            self.confirmation_command(vote="yes"),
            client_host="vote-host",
        )

        self.assertEqual(first.confirmations.model_dump(), {"yes": 1, "no": 0})
        self.assertEqual(repeated.confirmations.model_dump(), {"yes": 1, "no": 0})
        self.assertEqual(denied.confirmations.model_dump(), {"yes": 0, "no": 1})
        self.assertEqual(
            repeated_denial.confirmations.model_dump(),
            {"yes": 0, "no": 1},
        )
        self.assertEqual(
            attempted_restore.confirmations.model_dump(),
            {"yes": 0, "no": 1},
        )
        self.assertEqual(attempted_restore.vote, "no")
        self.assertEqual(denied.group.id, group_id)
        self.assertEqual(denied.group.confirmations.model_dump(), {"yes": 0, "no": 1})

    def test_distinct_denials_keep_the_group_public_and_preserve_full_count_and_expiry(self):
        service = self.create_service()
        empty_contract = service.get_reports().contract
        created = service.create_report(self.command(), client_host="report-host")
        group_id = created.report.groupId
        stored_report = service.repository._reports[created.report.id]
        original_created_at = stored_report["created_at"]
        original_expires_at = stored_report["expires_at"]
        original_public_expiry = created.report.expiresAt

        denial_steps = (
            ("denier-1", 1),
            ("denier-1", 1),  # idempotent retry from the same installation
            ("denier-2", 2),
            ("denier-3", 3),
            ("denier-4", 4),
        )
        withdrawal_timestamp = None
        for client_id, expected_count in denial_steps:
            response = service.confirm_report(
                group_id,
                self.confirmation_command(vote="no", client_id=client_id),
                client_host=f"host-{client_id}",
            )
            feed = service.get_reports()
            stored_report = service.repository._reports[created.report.id]
            confirmation = service.repository._confirmations[group_id]

            self.assertEqual(response.vote, "no")
            self.assertEqual(
                response.confirmations.model_dump(),
                {"yes": 0, "no": expected_count},
            )
            self.assertEqual(len(feed.reports), 1)
            self.assertEqual(len(feed.map_groups), 1)
            self.assertEqual(feed.map_groups[0].id, group_id)
            self.assertEqual(
                feed.map_groups[0].confirmations.model_dump(),
                {"yes": 0, "no": expected_count},
            )
            self.assertEqual(feed.contract, empty_contract)
            self.assertEqual(
                tuple(feed.reports[0].model_dump()),
                EXPECTED_PUBLIC_REPORT_FIELDS,
            )
            self.assertEqual(
                tuple(feed.map_groups[0].model_dump()),
                EXPECTED_PUBLIC_GROUP_FIELDS,
            )
            self.assertEqual(feed.reports[0].expiresAt, original_public_expiry)
            self.assertEqual(stored_report["created_at"], original_created_at)
            self.assertEqual(stored_report["expires_at"], original_expires_at)
            self.assertEqual(stored_report["confirmation_no"], expected_count)
            self.assertEqual(stored_report["denial_count"], expected_count)
            self.assertEqual(
                stored_report["map_withdrawn"],
                expected_count >= 3,
            )
            self.assertEqual(
                confirmation["map_withdrawn"],
                expected_count >= 3,
            )

            if expected_count == 3 and withdrawal_timestamp is None:
                withdrawal_timestamp = confirmation.get("map_withdrawn_at")
                self.assertIsNotNone(withdrawal_timestamp)
            if expected_count > 3:
                self.assertEqual(
                    confirmation.get("map_withdrawn_at"),
                    withdrawal_timestamp,
                )

        self.assertEqual(
            len(service.repository._confirmations[group_id]["votes"]),
            4,
        )

    def test_simultaneous_distinct_denials_are_atomic_in_memory(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="report-host")
        group_id = created.report.groupId
        start = Barrier(4)

        def deny(client_number):
            client_id = f"concurrent-denier-{client_number}"
            start.wait(timeout=5)
            return service.confirm_report(
                group_id,
                self.confirmation_command(vote="no", client_id=client_id),
                client_host=f"host-{client_id}",
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(deny, index) for index in range(4)]
            responses = [future.result(timeout=10) for future in futures]

        confirmation = service.repository._confirmations[group_id]
        stored_report = service.repository._reports[created.report.id]
        feed = service.get_reports()

        self.assertEqual(
            sorted(response.confirmations.no for response in responses),
            [1, 2, 3, 4],
        )
        self.assertEqual(confirmation["no"], 4)
        self.assertEqual(len(confirmation["votes"]), 4)
        self.assertEqual(set(confirmation["votes"].values()), {"no"})
        self.assertTrue(confirmation["map_withdrawn"])
        self.assertEqual(stored_report["denial_count"], 4)
        self.assertTrue(stored_report["map_withdrawn"])
        self.assertEqual(feed.map_groups[0].confirmations.no, 4)

    def test_confirmation_retention_never_outlives_the_active_group(self):
        clock = MutableClock()
        service = self.create_service(clock=clock)
        created = service.create_report(self.command(), client_host="host")
        report_expires_at = NOW + 3600
        clock.value = report_expires_at - 10

        service.confirm_report(
            created.report.groupId,
            self.confirmation_command(),
            client_host="host",
        )
        first_expiry = service.repository._confirmations[
            created.report.groupId
        ]["expires_at_timestamp"].timestamp()
        self.assertEqual(first_expiry, report_expires_at)

        clock.value += 5
        service.confirm_report(
            created.report.groupId,
            self.confirmation_command(vote="no"),
            client_host="host",
        )
        changed_expiry = service.repository._confirmations[
            created.report.groupId
        ]["expires_at_timestamp"].timestamp()
        self.assertEqual(changed_expiry, report_expires_at)

    def test_later_report_extends_existing_confirmation_to_group_lifetime(self):
        clock = MutableClock()
        report_ids = iter(("first-report", "later-report"))
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=CommunityRepository(),
            now=clock,
            report_id_factory=lambda: next(report_ids),
        )
        first = service.create_report(self.command(), client_host="host")
        service.confirm_report(
            first.report.groupId,
            self.confirmation_command(),
            client_host="host",
        )

        clock.value += 100
        later = service.create_report(
            self.command(client_id="second-owner"),
            client_host="host",
        )

        self.assertEqual(later.report.groupId, first.report.groupId)
        self.assertEqual(
            service.repository._confirmations[first.report.groupId][
                "expires_at_timestamp"
            ].timestamp(),
            NOW + 100 + 3600,
        )
        self.assertEqual(later.report.id, "later-report")

    def test_confirm_reads_only_the_target_group_confirmation(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
            report_id_factory=lambda: "community-target",
        )
        created = service.create_report(self.command(), client_host="host")
        for index in range(199):
            repository._reports[f"unrelated-{index}"] = {
                **repository._reports[created.report.id],
                "id": f"unrelated-{index}",
                "group_id": f"group-unrelated-{index}",
            }

        original_get_confirmation = repository.get_confirmation
        repository.get_confirmation = Mock(side_effect=original_get_confirmation)
        confirmed = service.confirm_report(
            created.report.groupId,
            self.confirmation_command(),
            client_host="host",
        )

        self.assertEqual(confirmed.confirmations.yes, 1)
        self.assertEqual(repository.get_confirmation.call_count, 1)
        repository.get_confirmation.assert_called_once_with(created.report.groupId)

    def test_expired_reports_are_pruned_after_one_hour(self):
        clock = MutableClock()
        service = self.create_service(clock=clock)
        service.create_report(self.command(), client_host="host")
        clock.value += 3601

        self.assertEqual(service.get_reports().reports, [])
        self.assertEqual(service.get_reports().map_groups, [])

    def test_public_source_keys_are_ephemeral_and_never_expose_owner_hash(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
        )
        owner_a = service._client_key("community-report", "client-a")
        owner_b = service._client_key("community-report", "client-b")
        base = {
            "id": "source-a-1",
            "type_id": "rain",
            "type_category": "phenomenon",
            "place": "Pordenone",
            "lat": 45.95689,
            "lon": 12.66051,
            "created_at": NOW,
            "expires_at": NOW + 3600,
            "group_id": "group-a",
            "owner_key": owner_a,
        }

        same_source = service._public_report({
            **base,
            "id": "source-a-2",
            "group_id": "group-b",
        }, NOW)
        first = service._public_report(base, NOW)
        other_source = service._public_report({
            **base,
            "id": "source-b",
            "owner_key": owner_b,
        }, NOW)
        next_bucket = service._public_report({
            **base,
            "id": "source-a-later",
            "created_at": NOW + PUBLIC_SOURCE_KEY_BUCKET_SECONDS,
        }, NOW)

        self.assertEqual(first.sourceKey, same_source.sourceKey)
        self.assertNotEqual(first.sourceKey, other_source.sourceKey)
        self.assertNotEqual(first.sourceKey, next_bucket.sourceKey)
        self.assertNotEqual(first.sourceKey, owner_a)
        self.assertEqual(len(first.sourceKey or ""), 24)

        group = service._group_from_reports(
            "group-a",
            [first, other_source, same_source],
            {"yes": 0, "no": 0},
        )
        self.assertEqual(
            group.sourceKeys,
            [first.sourceKey, other_source.sourceKey],
        )

    def test_group_identities_use_the_newest_immutable_snapshot_per_source(self):
        service = self.create_service()
        owner_a = service._client_key("community-report", "client-a")
        owner_b = service._client_key("community-report", "client-b")
        base = {
            "id": "source-a-old",
            "type_id": "rain",
            "place": "Pordenone",
            "created_at": NOW,
            "expires_at": NOW + 3600,
            "group_id": "group-a",
            "owner_key": owner_a,
            "identity": self.identity(),
        }
        old_identity = service._public_report(base, NOW)
        regenerated_snapshot = self.identity(
            "Ors di Udin",
            subject_id="ors",
            avatar={
                "palette_id": "gold",
                "pattern_id": "halo",
                "variant": 1,
                "angle": 90,
            },
        )
        newest_same_source = service._public_report({
            **base,
            "id": "source-a-new",
            "created_at": NOW + 2,
            "expires_at": NOW + 3602,
            "identity": regenerated_snapshot,
        }, NOW)
        other_source_same_display = service._public_report({
            **base,
            "id": "source-b",
            "created_at": NOW + 1,
            "expires_at": NOW + 3601,
            "owner_key": owner_b,
            "identity": regenerated_snapshot,
        }, NOW)

        group = service._group_from_reports(
            "group-a",
            [old_identity, other_source_same_display, newest_same_source],
            {"yes": 0, "no": 0},
        )

        self.assertEqual(len(group.sourceKeys), 2)
        self.assertEqual(
            [entry.model_dump() for entry in group.identities],
            [
                {
                    "sourceKey": newest_same_source.sourceKey,
                    "identity": regenerated_snapshot,
                },
                {
                    "sourceKey": other_source_same_display.sourceKey,
                    "identity": regenerated_snapshot,
                },
            ],
        )
        self.assertEqual(group.identity.model_dump(), regenerated_snapshot)

    def test_group_flags_are_idempotent_and_stay_in_moderation_queue(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="host")
        group_id = created.report.groupId

        first = service.flag_report_group(
            group_id,
            CommunityReportFlagCreate(reason="inaccurate", client_id="flagger-1"),
            client_host="host",
        )
        repeated = service.flag_report_group(
            group_id,
            CommunityReportFlagCreate(reason="misuse", client_id="flagger-1"),
            client_host="host",
        )
        second = service.flag_report_group(
            group_id,
            CommunityReportFlagCreate(reason="duplicate", client_id="flagger-2"),
            client_host="host",
        )
        third = service.flag_report_group(
            group_id,
            CommunityReportFlagCreate(reason="misuse", client_id="flagger-3"),
            client_host="host",
        )

        self.assertEqual(first.flag_count, 1)
        self.assertTrue(first.hidden)
        self.assertFalse(first.hidden_global)
        self.assertTrue(repeated.already_reported)
        self.assertEqual(repeated.reason, "inaccurate")
        self.assertEqual(repeated.flag_count, 1)
        self.assertEqual(second.flag_count, 2)
        self.assertEqual(third.flag_count, 3)
        self.assertTrue(third.hidden)
        self.assertFalse(third.hidden_global)
        self.assertEqual(third.retention_seconds, FLAG_RETENTION_SECONDS)
        self.assertEqual(len(service.get_reports().reports), 1)
        self.assertNotIn(
            "moderation_hidden",
            service.repository._reports[created.report.id],
        )
        moderation = service.repository._moderation[group_id]
        self.assertEqual(moderation["report_ids"], [created.report.id])
        self.assertEqual(len(moderation["owner_keys"]), 1)
        self.assertEqual(
            moderation["report_sources"][created.report.id],
            moderation["owner_keys"][0],
        )
        self.assertNotIn("owner_keys", third.model_dump())
        self.assertNotIn("report_sources", third.model_dump())

    def test_owner_cannot_flag_own_group(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="host")

        with self.assertRaises(CommunityServiceError) as context:
            service.flag_report_group(
                created.report.groupId,
                CommunityReportFlagCreate(
                    reason="inaccurate",
                    client_id="client-1",
                ),
                client_host="host",
            )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail["code"],
            "community_self_flag_not_allowed",
        )

    def test_owner_cannot_confirm_own_group(self):
        service = self.create_service()
        created = service.create_report(self.command(), client_host="host")

        with self.assertRaises(CommunityServiceError) as context:
            service.confirm_report(
                created.report.groupId,
                self.confirmation_command(client_id="client-1"),
                client_host="host",
            )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail["code"],
            "community_self_confirmation_not_allowed",
        )

    def test_flag_client_budget_is_bounded_and_idempotent_retries_do_not_consume_it(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
        )
        owner_key = service._client_key("community-report", "report-owner")
        group_ids = []
        for index in range(FLAG_CLIENT_WINDOW_LIMIT + 1):
            group_id = f"group-rain:pordenone:{index}"
            group_ids.append(group_id)
            repository._reports[f"report-{index}"] = {
                "id": f"report-{index}",
                "type_id": "rain",
                "type_category": "phenomenon",
                "place": "Pordenone",
                "lat": 45.95689,
                "lon": 12.66051,
                "created_at": NOW,
                "expires_at": NOW + 3600,
                "group_id": group_id,
                "owner_key": owner_key,
            }

        for index, group_id in enumerate(group_ids[:FLAG_CLIENT_WINDOW_LIMIT]):
            response = service.flag_report_group(
                group_id,
                CommunityReportFlagCreate(
                    reason="inaccurate",
                    client_id="bounded-flagger",
                ),
                client_host="host",
            )
            self.assertEqual(response.flag_count, 1)
            if index == 0:
                repeated = service.flag_report_group(
                    group_id,
                    CommunityReportFlagCreate(
                        reason="duplicate",
                        client_id="bounded-flagger",
                    ),
                    client_host="host",
                )
                self.assertTrue(repeated.already_reported)

        with self.assertRaises(CommunityServiceError) as blocked:
            service.flag_report_group(
                group_ids[-1],
                CommunityReportFlagCreate(
                    reason="misuse",
                    client_id="bounded-flagger",
                ),
                client_host="host",
            )
        self.assertEqual(blocked.exception.status_code, 429)

    def test_temporarily_blocked_source_cannot_create_new_reports(self):
        service = self.create_service()
        owner_key = service._client_key("community-report", "client-1")
        service.repository.set_source_block(
            owner_key,
            blocked_until=NOW + 7200,
            reason="confirmed_misuse",
        )

        with self.assertRaises(CommunityServiceError) as context:
            service.create_report(self.command(), client_host="host")

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail["code"],
            "community_source_temporarily_blocked",
        )

    def test_public_get_uses_materialized_visibility_without_moderation_n_plus_one(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
            report_id_factory=lambda: "visible-report",
        )
        service.create_report(self.command(), client_host="host")
        repository.get_group_moderation = Mock(
            side_effect=AssertionError("public GET must not query moderation per group")
        )
        repository.get_confirmation = Mock(
            side_effect=AssertionError("public GET must not query confirmations per group")
        )

        payload = service.get_reports()

        self.assertEqual(len(payload.reports), 1)
        repository.get_group_moderation.assert_not_called()
        repository.get_confirmation.assert_not_called()

    def test_public_get_honours_one_global_hidden_group_gate(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
            report_id_factory=lambda: "late-report",
        )
        created = service.create_report(self.command(), client_host="host")
        repository._moderation[created.report.groupId] = {
            "group_id": created.report.groupId,
            "hidden": True,
            "expires_at_timestamp": NOW + 86400,
        }
        original_list_hidden = repository.list_hidden_group_ids
        repository.list_hidden_group_ids = Mock(side_effect=original_list_hidden)

        payload = service.get_reports()

        self.assertEqual(payload.reports, [])
        self.assertEqual(repository.list_hidden_group_ids.call_count, 1)

    def test_oversized_group_is_fail_closed_before_confirmation_or_flag_writes(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
        )
        owner_key = service._client_key("community-report", "owner")
        group_id = "group-rain:pordenone:oversized"
        for index in range(GROUP_MUTATION_MAX_REPORTS + 1):
            repository._reports[f"report-{index}"] = {
                "id": f"report-{index}",
                "type_id": "rain",
                "type_category": "phenomenon",
                "place": "Pordenone",
                "lat": 45.95689,
                "lon": 12.66051,
                "created_at": NOW,
                "expires_at": NOW + 3600,
                "group_id": group_id,
                "owner_key": owner_key,
            }
        repository.save_confirmation = Mock(wraps=repository.save_confirmation)
        repository.flag_group = Mock(wraps=repository.flag_group)

        operations = (
            lambda: service.confirm_report(
                group_id,
                self.confirmation_command(),
                client_host="host",
            ),
            lambda: service.flag_report_group(
                group_id,
                CommunityReportFlagCreate(reason="misuse", client_id="flagger"),
                client_host="host",
            ),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(CommunityServiceError) as context:
                    operation()
                self.assertEqual(context.exception.status_code, 503)
                self.assertEqual(
                    context.exception.detail["code"],
                    "community_group_temporarily_too_large",
                )
        repository.save_confirmation.assert_not_called()
        repository.flag_group.assert_not_called()

    def test_public_get_uses_materialized_confirmation_counts(self):
        repository = CommunityRepository()
        service = CommunityService(
            catalog=LocationCatalog(),
            repository=repository,
            now=lambda: NOW,
            report_id_factory=lambda: "confirmed-report",
        )
        created = service.create_report(self.command(), client_host="host")
        service.confirm_report(
            created.report.groupId,
            self.confirmation_command(),
            client_host="host",
        )
        repository.get_confirmation = Mock(
            side_effect=AssertionError("public GET must use report materialization")
        )

        payload = service.get_reports()

        self.assertEqual(payload.map_groups[0].confirmations.yes, 1)
        self.assertEqual(payload.map_groups[0].confirmations.no, 0)
        repository.get_confirmation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
