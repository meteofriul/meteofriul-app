import json
import unittest
from copy import deepcopy
from datetime import timedelta

from app.services.national_alert_push_dry_run import (
    NationalAlertDryRunPolicy,
    NationalAlertDryRunUnavailable,
    evaluate_national_alert_push_dry_run,
)
from tests.test_national_official_alerts import NOW, reconciled_snapshot


ANDROID_APP_ID = "1:49007668366:android:725bf6f8b339177a852ddf"
POLICY = NationalAlertDryRunPolicy(
    enrollment_generation="play-beta-v1",
    android_app_ids=frozenset({ANDROID_APP_ID}),
    min_app_version_code=300029,
)


def device(
    *,
    device_id="device-one",
    token="test-fcm-target-one",
    istat="041067",
    name="Urbino",
    version="0.1.12+300029",
    location_mode="manual_selection",
    alerts=True,
):
    return {
        "device_id": device_id,
        "active": True,
        "platform": "android",
        "schema_version": "2.1",
        "enrollment_generation": "play-beta-v1",
        "app_check_app_id": ANDROID_APP_ID,
        "app_version": version,
        "location_mode": location_mode,
        "municipality": {"istat": istat, "name": name},
        "preferences": {"official_alerts": alerts},
        "target_kind": "fcm_token",
        "target_value": token,
    }


def evaluate(snapshot=None, devices=(), *, now=NOW, storage="firestore"):
    return evaluate_national_alert_push_dry_run(
        snapshot if snapshot is not None else reconciled_snapshot(),
        devices,
        storage=storage,
        policy=POLICY,
        now=now,
        expected_zone_count=100,  # The deterministic DPC fixture has 100 zones.
    )


class NationalAlertPushDryRunTests(unittest.TestCase):
    def test_manual_national_candidate_is_limited_to_matching_zone(self):
        rows = [
            device(),
            device(device_id="fvg", token="test-fcm-fvg", istat="093033", name="Pordenone"),
            device(device_id="gps", token="test-fcm-gps", location_mode="automatic_gps"),
            device(device_id="off", token="test-fcm-off", alerts=False),
            device(device_id="old", token="test-fcm-old", version="0.1.11+300028"),
            device(device_id="bad", token="test-fcm-bad", name="Wrong name"),
        ]
        result = evaluate(devices=rows)

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["candidate_status"], "candidate")
        self.assertEqual(result["devices_seen"], 6)
        self.assertEqual(result["eligible_manual_devices"], 1)
        self.assertEqual(result["candidate_devices"], 1)
        self.assertEqual(result["candidate_records"], 1)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["outbox_writes"], 0)
        self.assertEqual(result["excluded"], {
            "fvg_uses_regional_dispatcher": 1,
            "municipality_unresolved": 1,
            "not_manual_selection": 1,
            "play_policy_not_met": 1,
            "preference_disabled": 1,
        })
        rendered = json.dumps(result)
        for sensitive in ("device-one", "test-fcm-target-one", "Urbino", "041067"):
            self.assertNotIn(sensitive, rendered)

    def test_future_play_versions_remain_eligible(self):
        result = evaluate(devices=[device(version="0.2.0+300050")])
        self.assertEqual(result["candidate_devices"], 1)
        self.assertEqual(result["candidate_records"], 1)

    def test_authoritative_green_is_not_a_delivery_candidate(self):
        snapshot = deepcopy(reconciled_snapshot())
        for record in snapshot["records"]:
            if record["level"] in {"yellow", "orange", "red"}:
                record["level"] = "green"
        result = evaluate(snapshot, [device()])
        self.assertEqual(result["candidate_status"], "no_candidate")
        self.assertEqual(result["eligible_manual_devices"], 1)
        self.assertEqual(result["candidate_devices"], 0)
        self.assertEqual(result["sent"], 0)

    def test_empty_audience_does_not_make_invalid_revision_look_healthy(self):
        snapshot = deepcopy(reconciled_snapshot())
        snapshot["cap_revision"]["id"] = ""
        with self.assertRaisesRegex(
            NationalAlertDryRunUnavailable, "stale_or_invalid"
        ):
            evaluate(snapshot, [])

    def test_duplicate_fcm_target_fails_closed(self):
        with self.assertRaisesRegex(
            NationalAlertDryRunUnavailable, "duplicate_delivery_target"
        ):
            evaluate(devices=[device(), device(device_id="device-two")])

    def test_source_must_be_persistent_current_complete_and_reconciled(self):
        snapshot = reconciled_snapshot()
        with self.assertRaisesRegex(
            NationalAlertDryRunUnavailable, "not_persistent"
        ):
            evaluate(snapshot, [device()], storage="memory_fallback")
        with self.assertRaisesRegex(
            NationalAlertDryRunUnavailable, "stale_or_invalid"
        ):
            evaluate(snapshot, [device()], now=NOW + timedelta(hours=37))
        candidate = deepcopy(snapshot)
        candidate["records"].pop()
        with self.assertRaisesRegex(
            NationalAlertDryRunUnavailable, "unverified"
        ):
            evaluate(candidate, [device()])
        candidate = deepcopy(snapshot)
        candidate["reconciled"] = False
        with self.assertRaisesRegex(
            NationalAlertDryRunUnavailable, "unverified"
        ):
            evaluate(candidate, [device()])

    def test_partial_official_state_does_not_count_as_candidate(self):
        snapshot = deepcopy(reconciled_snapshot())
        for record in snapshot["records"]:
            if record["zone_id"] == "DPC:Marc-2" and record["risk"] == "hydraulic":
                record["transmission_status"] = "not_transmitted"
                record["level"] = None
                break
        result = evaluate(snapshot, [device()])
        self.assertEqual(result["eligible_manual_devices"], 1)
        self.assertEqual(result["candidate_devices"], 0)
        self.assertEqual(result["candidate_records"], 0)
        self.assertEqual(result["excluded"], {"official_state_partial": 1})


if __name__ == "__main__":
    unittest.main()
