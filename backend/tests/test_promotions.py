import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.promotions import get_promotion_service
from app.main import create_app
from app.services.promotions import (
    PromotionRepository,
    PromotionService,
    PromotionAvailabilityConflict,
    PromotionStateConflict,
    PromotionValidationError,
    build_availability,
    build_public_catalog,
    default_admin_state,
    sanitize_admin_state,
    validate_campaign_availability,
)


NOW = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)


def active_campaign():
    return {
        "id": "ale-hair-pordenone",
        "status": "active",
        "businessName": "Ale Hair Studio",
        "businessAddress": "Via Roma 1",
        "city": "Pordenone",
        "category": "Salone",
        "cardDetails": ["city"],
        "title": "Tagli e colore su misura",
        "description": "Un trattamento pensato per i tuoi capelli.",
        "ctaLabel": "Scopri il salone",
        "destinationUrl": "https://example.com/ale-hair",
        "imageUrl": "https://firebasestorage.googleapis.com/example/image.webp",
        "placements": ["home", "events"],
        "placementAssignments": {
            "home": {"cardNumber": 1, "mode": "exclusive"},
            "events": {"cardNumber": 1, "mode": "rotation"},
        },
        "bookingMode": "mixed",
        "deliveryMode": "all_selected",
        "scheduleMode": "period",
        "startDate": "2026-09-01",
        "endDate": "2026-09-30",
        "activeDates": [],
        "maxPerDay": 1,
        "invoiceNumber": "RISERVATO-001",
        "internalNotes": "Non deve uscire nel catalogo pubblico.",
    }


def enabled_state():
    state = default_admin_state()
    state["adsEnabled"] = True
    state["campaigns"] = [active_campaign()]
    return state


def booking_campaign(
    campaign_id,
    *,
    placements=None,
    placement_assignments=None,
    booking_mode="exclusive",
    status="scheduled",
    start_date="2026-10-10",
    end_date="2026-10-10",
    start_time="",
    end_time="",
):
    campaign = {
        "id": campaign_id,
        "status": status,
        "businessName": f"Sponsor {campaign_id}",
        "placements": placements or ["home"],
        "bookingMode": booking_mode,
        "scheduleMode": "period",
        "startDate": start_date,
        "endDate": end_date,
        "startTime": start_time,
        "endTime": end_time,
    }
    if placement_assignments is not None:
        campaign["placementAssignments"] = placement_assignments
    return campaign


def state_with(*campaigns):
    state = default_admin_state()
    state["campaigns"] = list(campaigns)
    return state


class PromotionServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = PromotionRepository(lambda: None)
        self.service = PromotionService(self.repository)

    def test_default_catalog_is_explicitly_off(self):
        catalog = self.service.public_catalog()

        self.assertEqual(catalog["schemaVersion"], 2)
        self.assertEqual(catalog["timezone"], "Europe/Rome")
        self.assertEqual(catalog["placements"], ["discover", "events", "home"])
        self.assertEqual(catalog["placementRotationIntervals"], {
            "discover": 120,
            "events": 120,
            "home": 120,
        })
        self.assertEqual(catalog["rotationIntervalSeconds"], 120)
        self.assertEqual(catalog["maxRotationCampaigns"], 5)
        self.assertFalse(catalog["enabled"])
        self.assertEqual(catalog["revision"], 0)
        self.assertEqual(catalog["dailyCap"], 0)
        self.assertEqual(catalog["campaigns"], [])
        self.assertNotIn("storage", catalog)

    def test_admin_rotation_session_is_fixed_to_public_contract(self):
        self.assertEqual(default_admin_state()["sessionMinutes"], 2)

        legacy_state = default_admin_state()
        legacy_state["sessionMinutes"] = 60

        self.assertEqual(sanitize_admin_state(legacy_state)["sessionMinutes"], 2)

    def test_rotation_intervals_are_normalized_per_placement(self):
        state = default_admin_state()
        state["placementRotationIntervals"] = {
            "home": 30,
            "events": 60,
            "discover": 999,
        }

        sanitized = sanitize_admin_state(state)
        catalog = build_public_catalog(sanitized, revision=1, now=NOW)

        self.assertEqual(sanitized["placementRotationIntervals"], {
            "discover": 120,
            "events": 60,
            "home": 30,
        })
        self.assertEqual(catalog["placementRotationIntervals"], {
            "discover": 120,
            "events": 60,
            "home": 30,
        })
        self.assertEqual(catalog["rotationIntervalSeconds"], 30)

    def test_public_catalog_contains_only_sanitized_delivery_fields(self):
        state = sanitize_admin_state(enabled_state())
        catalog = build_public_catalog(state, revision=7, now=NOW)

        self.assertTrue(catalog["enabled"])
        self.assertEqual(catalog["schemaVersion"], 2)
        self.assertEqual(catalog["rotationIntervalSeconds"], 120)
        self.assertEqual(catalog["maxRotationCampaigns"], 5)
        self.assertEqual(catalog["revision"], 7)
        self.assertEqual(len(catalog["campaigns"]), 1)
        public_campaign = catalog["campaigns"][0]
        self.assertEqual(public_campaign["placements"], ["home", "events"])
        self.assertEqual(public_campaign["placementAssignments"], {
            "home": {"cardNumber": 1, "mode": "exclusive"},
            "events": {"cardNumber": 1, "mode": "rotation"},
        })
        self.assertEqual(public_campaign["bookingMode"], "mixed")
        self.assertEqual(public_campaign["deliveryMode"], "all_selected")
        self.assertEqual(public_campaign["title"], "Ale Hair Studio")
        self.assertEqual(public_campaign["headline"], "Tagli e colore su misura")
        self.assertEqual(public_campaign["location"], "Pordenone")
        self.assertEqual(public_campaign["businessAddress"], "")
        self.assertEqual(public_campaign["category"], "")
        self.assertEqual(public_campaign["scheduleMode"], "period")
        self.assertEqual(public_campaign["activeMonth"], "")
        self.assertEqual(public_campaign["startsAt"], "2026-09-01")
        self.assertEqual(public_campaign["endsAt"], "2026-09-30")
        self.assertNotIn("invoiceNumber", public_campaign)
        self.assertNotIn("internalNotes", public_campaign)
        self.assertNotIn("businessName", public_campaign)

    def test_category_and_address_visibility_are_explicit(self):
        state = enabled_state()
        campaign = state["campaigns"][0]
        campaign["category"] = "Marketing, comunicazione e media"
        campaign["businessAddress"] = "Via Roma 12"
        campaign["cardDetails"] = ["city"]
        hidden = build_public_catalog(sanitize_admin_state(state), revision=1, now=NOW)["campaigns"][0]
        self.assertEqual(hidden["category"], "")
        self.assertEqual(hidden["businessAddress"], "")

        campaign["cardDetails"] = ["category", "address"]
        visible = build_public_catalog(sanitize_admin_state(state), revision=2, now=NOW)["campaigns"][0]
        self.assertEqual(visible["category"], "Marketing, comunicazione e media")
        self.assertEqual(visible["businessAddress"], "Via Roma 12")

    def test_legacy_campaigns_gain_exclusive_full_day_defaults(self):
        campaign = active_campaign()
        campaign.pop("deliveryMode")
        campaign.pop("bookingMode")
        campaign.pop("placementAssignments")
        state = enabled_state()
        state["campaigns"] = [campaign]

        sanitized = sanitize_admin_state(state)

        self.assertEqual(sanitized["campaigns"][0]["bookingMode"], "exclusive")
        self.assertEqual(sanitized["campaigns"][0]["deliveryMode"], "all_selected")
        self.assertEqual(sanitized["campaigns"][0]["placementAssignments"], {
            "home": {"cardNumber": 1, "mode": "exclusive"},
            "events": {"cardNumber": 1, "mode": "exclusive"},
        })
        self.assertEqual(sanitized["campaigns"][0]["startTime"], "")
        self.assertEqual(sanitized["campaigns"][0]["endTime"], "")

    def test_mixed_mode_requires_explicit_assignments_for_every_page(self):
        campaign = booking_campaign(
            "invalid-mixed",
            placements=["home", "events"],
            booking_mode="mixed",
            placement_assignments={
                "home": {"cardNumber": 1, "mode": "exclusive"},
            },
        )

        with self.assertRaisesRegex(
            PromotionValidationError,
            "promotion_placement_assignment_invalid",
        ):
            sanitize_admin_state(state_with(campaign))

    def test_public_catalog_applies_optional_hours_in_rome_timezone(self):
        state = enabled_state()
        state["campaigns"][0]["startTime"] = "12:00"
        state["campaigns"][0]["endTime"] = "13:00"
        sanitized = sanitize_admin_state(state)

        before = build_public_catalog(
            sanitized,
            revision=1,
            now=datetime(2026, 9, 26, 9, 59, tzinfo=timezone.utc),
        )
        during = build_public_catalog(
            sanitized,
            revision=1,
            now=datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(before["enabled"])
        self.assertTrue(during["enabled"])
        self.assertEqual(during["campaigns"][0]["startTime"], "12:00")
        self.assertEqual(during["campaigns"][0]["endTime"], "13:00")

    def test_global_and_placement_switches_fail_closed(self):
        state = sanitize_admin_state(enabled_state())
        state["adsEnabled"] = False
        self.assertFalse(build_public_catalog(state, revision=1, now=NOW)["enabled"])

        state = sanitize_admin_state(enabled_state())
        state["placementEnabled"]["home"] = False
        catalog = build_public_catalog(state, revision=2, now=NOW)
        self.assertEqual(catalog["campaigns"][0]["placements"], ["events"])
        self.assertEqual(catalog["campaigns"][0]["placementAssignments"], {
            "events": {"cardNumber": 1, "mode": "rotation"},
        })
        self.assertEqual(catalog["campaigns"][0]["bookingMode"], "rotation")

    def test_active_campaign_rejects_base64_or_incomplete_delivery_data(self):
        state = enabled_state()
        state["campaigns"][0]["imageDataUrl"] = "data:image/png;base64,AA=="
        with self.assertRaisesRegex(
            PromotionValidationError,
            "promotion_base64_image_forbidden",
        ):
            sanitize_admin_state(state)

        state = enabled_state()
        state["campaigns"][0]["imageUrl"] = ""
        with self.assertRaisesRegex(
            PromotionValidationError,
            "promotion_active_campaign_incomplete",
        ):
            sanitize_admin_state(state)

    def test_revision_conflict_prevents_overwriting_another_admin_change(self):
        first = self.service.replace_state(
            enabled_state(),
            expected_revision=0,
            actor_uid="admin-1",
            actor_email="admin@example.com",
        )

        self.assertEqual(first["revision"], 1)
        with self.assertRaisesRegex(
            PromotionStateConflict,
            "promotion_revision_conflict",
        ):
            self.service.replace_state(
                enabled_state(),
                expected_revision=0,
                actor_uid="admin-2",
                actor_email="other@example.com",
            )

    @patch("app.services.promotions.datetime", wraps=datetime)
    def test_metrics_are_aggregate_and_reject_inactive_campaigns(self, mocked_datetime):
        mocked_datetime.now.return_value = NOW
        self.service.replace_state(
            enabled_state(),
            expected_revision=0,
            actor_uid="admin-1",
            actor_email="admin@example.com",
        )

        self.assertTrue(self.service.record_event({
            "campaignId": "ale-hair-pordenone",
            "placement": "home",
            "type": "impression",
        })["accepted"])
        metric = self.repository.read_metrics()[0]
        self.assertEqual(metric["impression"], 1)
        self.assertEqual(metric["open"], 0)
        self.assertNotIn("user", metric)
        self.assertNotIn("gps", metric)

        with self.assertRaisesRegex(
            PromotionValidationError,
            "promotion_event_campaign_inactive",
        ):
            self.service.record_event({
                "campaignId": "unknown",
                "placement": "home",
                "type": "open",
            })

    def test_drafts_do_not_reserve_but_paused_and_scheduled_campaigns_do(self):
        state = sanitize_admin_state(state_with(
            booking_campaign("draft", status="draft"),
            booking_campaign("paused", status="paused"),
        ))
        validate_campaign_availability(state)

        state["campaigns"].append(
            sanitize_admin_state(state_with(
                booking_campaign("scheduled", status="scheduled"),
            ))["campaigns"][0]
        )
        with self.assertRaises(PromotionAvailabilityConflict):
            validate_campaign_availability(state)

    def test_active_campaigns_reserve_their_pages(self):
        active = active_campaign()
        active.update({
            "bookingMode": "exclusive",
            "deliveryMode": "exclusive",
            "startDate": "2026-10-10",
            "endDate": "2026-10-10",
        })
        state = sanitize_admin_state(state_with(
            active,
            booking_campaign("scheduled", placements=["events"]),
        ))

        with self.assertRaises(PromotionAvailabilityConflict) as raised:
            validate_campaign_availability(state)
        self.assertEqual(raised.exception.page, "events")

    def test_master_switch_does_not_release_an_exclusive_reservation(self):
        state = state_with(
            booking_campaign("occupant", status="paused"),
            booking_campaign("incoming", status="scheduled"),
        )
        state["adsEnabled"] = False

        with self.assertRaises(PromotionAvailabilityConflict) as raised:
            validate_campaign_availability(sanitize_admin_state(state))

        self.assertEqual(raised.exception.page, "home")
        self.assertEqual(raised.exception.day, "2026-10-10")
        self.assertEqual(raised.exception.start_time, "00:00")
        self.assertEqual(raised.exception.end_time, "24:00")

    def test_touching_time_boundaries_do_not_overlap(self):
        state = sanitize_admin_state(state_with(
            booking_campaign("morning", start_time="08:00", end_time="12:00"),
            booking_campaign("afternoon", start_time="12:00", end_time="18:00"),
        ))

        validate_campaign_availability(state)

    def test_rotation_accepts_five_sponsors_and_rejects_the_sixth(self):
        five = sanitize_admin_state(state_with(*[
            booking_campaign(f"rotation-{index}", booking_mode="rotation")
            for index in range(5)
        ]))
        validate_campaign_availability(five)

        six = sanitize_admin_state(state_with(*[
            booking_campaign(f"rotation-{index}", booking_mode="rotation")
            for index in range(6)
        ]))
        with self.assertRaises(PromotionAvailabilityConflict) as raised:
            validate_campaign_availability(six)

        self.assertEqual(raised.exception.page, "home")
        self.assertEqual(raised.exception.day, "2026-10-10")

    def test_same_hours_on_different_pages_are_independent(self):
        independent = sanitize_admin_state(state_with(
            booking_campaign("home", placements=["home"]),
            booking_campaign("events", placements=["events"]),
            booking_campaign("discover", placements=["discover"]),
        ))
        validate_campaign_availability(independent)

        shared_page = sanitize_admin_state(state_with(
            booking_campaign("home-discover", placements=["home", "discover"]),
            booking_campaign("discover", placements=["discover"]),
        ))
        with self.assertRaises(PromotionAvailabilityConflict) as raised:
            validate_campaign_availability(shared_page)
        self.assertEqual(raised.exception.page, "discover")

    def test_mixed_campaign_modes_are_enforced_only_on_the_assigned_page(self):
        mixed = booking_campaign(
            "mixed",
            placements=["home", "events"],
            booking_mode="mixed",
            placement_assignments={
                "home": {"cardNumber": 1, "mode": "exclusive"},
                "events": {"cardNumber": 1, "mode": "rotation"},
            },
        )
        compatible = sanitize_admin_state(state_with(
            mixed,
            booking_campaign(
                "events-rotation",
                placements=["events"],
                booking_mode="rotation",
            ),
        ))
        validate_campaign_availability(compatible)

        conflicting = sanitize_admin_state(state_with(
            mixed,
            booking_campaign(
                "home-rotation",
                placements=["home"],
                booking_mode="rotation",
            ),
        ))
        with self.assertRaises(PromotionAvailabilityConflict) as raised:
            validate_campaign_availability(conflicting)

        self.assertEqual(raised.exception.page, "home")

    def test_availability_reports_open_and_occupied_intervals(self):
        state = sanitize_admin_state(state_with(
            booking_campaign(
                "lunch",
                placements=["events"],
                booking_mode="rotation",
                status="paused",
                start_time="12:00",
                end_time="14:00",
            ),
        ))

        availability = build_availability(
            state,
            start_date="2026-10-10",
            end_date="2026-10-10",
            placements=["events"],
        )

        self.assertEqual(availability["timezone"], "Europe/Rome")
        intervals = availability["days"][0]["intervals"]
        self.assertEqual(
            [(item["startTime"], item["endTime"]) for item in intervals],
            [("00:00", "12:00"), ("12:00", "14:00"), ("14:00", "24:00")],
        )
        self.assertTrue(intervals[0]["exclusiveAvailable"])
        self.assertFalse(intervals[1]["exclusiveAvailable"])
        self.assertEqual(intervals[1]["rotationSlotsAvailable"], 4)
        self.assertEqual(intervals[1]["reservations"][0]["campaignId"], "lunch")

    def test_concurrent_writes_cannot_double_book_a_slot(self):
        barrier = Barrier(2)

        def write(campaign_id):
            barrier.wait()
            try:
                result = self.service.replace_state(
                    state_with(booking_campaign(campaign_id)),
                    expected_revision=0,
                    actor_uid=campaign_id,
                    actor_email=f"{campaign_id}@example.test",
                )
                return ("stored", result["state"]["campaigns"][0]["id"])
            except PromotionAvailabilityConflict as error:
                return ("conflict", error.as_detail())

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(write, ["sponsor-a", "sponsor-b"]))

        self.assertEqual([item[0] for item in results].count("stored"), 1)
        self.assertEqual([item[0] for item in results].count("conflict"), 1)
        conflict = next(item[1] for item in results if item[0] == "conflict")
        self.assertEqual(conflict["code"], "promotion_availability_conflict")
        self.assertEqual(conflict["page"], "home")
        self.assertIn(conflict["occupyingCampaignId"], {"sponsor-a", "sponsor-b"})


class PromotionApiTests(unittest.TestCase):
    def setUp(self):
        self.service = PromotionService(PromotionRepository(lambda: None))
        app = create_app()
        app.dependency_overrides[get_promotion_service] = lambda: self.service
        self.client = TestClient(app)

    def test_public_catalog_and_events_contract(self):
        catalog = self.client.get("/api/promotions/catalog")

        self.assertEqual(catalog.status_code, 200)
        self.assertFalse(catalog.json()["enabled"])
        self.assertEqual(catalog.headers["etag"], '"promotions-0"')
        rejected = self.client.post(
            "/api/promotions/events",
            json={"campaignId": "missing", "placement": "home", "type": "open"},
        )
        self.assertEqual(rejected.status_code, 422)

    def test_delivery_metrics_require_app_check_when_persistence_is_enabled(self):
        with patch.dict(os.environ, {
            "COMMUNITY_APP_CHECK_ALLOWED_APP_IDS": "official-android-app",
            "COMMUNITY_APP_CHECK_MODE": "enforce",
            "COMMUNITY_STORAGE": "firestore",
            "K_SERVICE": "",
        }):
            response = self.client.post(
                "/api/promotions/events",
                json={
                    "campaignId": "campaign-1",
                    "placement": "home",
                    "type": "impression",
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "app_check_required")

    def test_admin_requires_token_and_enforces_local_token(self):
        missing = self.client.get("/api/admin/promotions/state")
        self.assertEqual(missing.status_code, 401)

        with patch.dict(os.environ, {
            "ADS_ADMIN_AUTH_MODE": "local",
            "ADS_ADMIN_LOCAL_TOKEN": "test-secret-token",
            "K_SERVICE": "",
        }):
            forbidden = self.client.get(
                "/api/admin/promotions/state",
                headers={"Authorization": "Bearer wrong"},
            )
            accepted = self.client.get(
                "/api/admin/promotions/state",
                headers={"Authorization": "Bearer test-secret-token"},
            )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(accepted.status_code, 200)
        self.assertFalse(accepted.json()["state"]["adsEnabled"])

    def test_admin_write_increments_revision_and_keeps_catalog_off(self):
        payload = default_admin_state()
        with patch.dict(os.environ, {
            "ADS_ADMIN_AUTH_MODE": "local",
            "ADS_ADMIN_LOCAL_TOKEN": "test-secret-token",
            "K_SERVICE": "",
        }):
            response = self.client.put(
                "/api/admin/promotions/state",
                headers={"Authorization": "Bearer test-secret-token"},
                json={"expectedRevision": 0, "state": payload},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], 1)
        self.assertTrue(response.json()["updatedAt"])
        self.assertEqual(response.json()["updatedByEmail"], "local@meteofriul.invalid")
        reread = self.service.admin_state()
        self.assertEqual(reread["updatedAt"], response.json()["updatedAt"])
        self.assertEqual(reread["updatedByEmail"], response.json()["updatedByEmail"])
        self.assertFalse(response.json()["catalog"]["enabled"])

    def test_admin_availability_requires_auth_and_filters_pages(self):
        missing = self.client.get(
            "/api/admin/promotions/availability",
            params={"startDate": "2026-10-10", "endDate": "2026-10-10"},
        )
        self.assertEqual(missing.status_code, 401)

        self.service.replace_state(
            state_with(booking_campaign("events", placements=["events"])),
            expected_revision=0,
            actor_uid="admin",
            actor_email="admin@example.test",
        )
        with patch.dict(os.environ, {
            "ADS_ADMIN_AUTH_MODE": "local",
            "ADS_ADMIN_LOCAL_TOKEN": "test-secret-token",
            "K_SERVICE": "",
        }):
            response = self.client.get(
                "/api/admin/promotions/availability",
                headers={"Authorization": "Bearer test-secret-token"},
                params=[
                    ("startDate", "2026-10-10"),
                    ("endDate", "2026-10-10"),
                    ("page", "events"),
                ],
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["timezone"], "Europe/Rome")
        self.assertEqual(body["revision"], 1)
        self.assertEqual([item["page"] for item in body["days"]], ["events"])
        self.assertFalse(body["days"][0]["intervals"][0]["exclusiveAvailable"])

    def test_admin_write_returns_structured_availability_conflict(self):
        first = state_with(booking_campaign("occupant"))
        second = state_with(booking_campaign("incoming"))
        with patch.dict(os.environ, {
            "ADS_ADMIN_AUTH_MODE": "local",
            "ADS_ADMIN_LOCAL_TOKEN": "test-secret-token",
            "K_SERVICE": "",
        }):
            stored = self.client.put(
                "/api/admin/promotions/state",
                headers={"Authorization": "Bearer test-secret-token"},
                json={"expectedRevision": 0, "state": first},
            )
            conflict = self.client.put(
                "/api/admin/promotions/state",
                headers={"Authorization": "Bearer test-secret-token"},
                json={"expectedRevision": 0, "state": second},
            )

        self.assertEqual(stored.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        detail = conflict.json()["detail"]
        self.assertEqual(detail["code"], "promotion_availability_conflict")
        self.assertEqual(detail["page"], "home")
        self.assertEqual(detail["date"], "2026-10-10")
        self.assertEqual(detail["startTime"], "00:00")
        self.assertEqual(detail["endTime"], "24:00")
        self.assertEqual(detail["occupyingCampaignId"], "occupant")


if __name__ == "__main__":
    unittest.main()
