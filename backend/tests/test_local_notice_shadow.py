import copy
import unittest
from datetime import datetime, timedelta

from app.weather import local_notice_shadow as shadow
from app.services.fvg_geography import FvgGeographyCatalog


ROME = shadow.FVG_ZONE
NOW = datetime(2026, 8, 14, 10, 15, tzinfo=ROME)


def build_snapshot(
    *,
    municipality="Pordenone",
    now=NOW,
    slot_count=6,
    locality=None,
    **hourly_overrides,
):
    requested_location = shadow.canonical_weather_request(
        municipality,
        locality=locality,
    )
    first_slot = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    fetched_at = now - timedelta(minutes=5)
    hourly = {
        "time": [
            (first_slot + timedelta(hours=index)).replace(tzinfo=None).isoformat(
                timespec="minutes"
            )
            for index in range(slot_count)
        ],
        "temperature_2m": [24.0] * slot_count,
        "apparent_temperature": [24.0] * slot_count,
        "precipitation_probability": [0.0] * slot_count,
        "precipitation": [0.0] * slot_count,
        "rain": [0.0] * slot_count,
        "showers": [0.0] * slot_count,
        "snowfall": [0.0] * slot_count,
        "weather_code": [1] * slot_count,
        "wind_gusts_10m": [20.0] * slot_count,
    }
    hourly.update(hourly_overrides)
    return {
        "source": shadow.SOURCE_ID,
        "fetched_at": fetched_at.isoformat(timespec="minutes"),
        "timezone": shadow.FVG_TIMEZONE,
        "utc_offset_seconds": int(fetched_at.utcoffset().total_seconds()),
        "requested_location": requested_location,
        "hourly_units": dict(shadow.EXPECTED_HOURLY_UNITS),
        "hourly": hourly,
    }


def evaluate(snapshot, *, municipality="Pordenone", now=NOW, locality=None):
    return shadow.evaluate_local_notice_shadow(
        municipality,
        snapshot,
        now=now,
        locality=locality,
    )


def candidate_for(result, kind):
    return next(
        (candidate for candidate in result["candidates"] if candidate["kind"] == kind),
        None,
    )


class ShadowContractTests(unittest.TestCase):
    def test_rome_timezone_has_expected_winter_and_summer_offsets(self):
        winter = datetime(2026, 1, 14, 12, 0, tzinfo=ROME)
        summer = datetime(2026, 8, 14, 12, 0, tzinfo=ROME)

        self.assertEqual(winter.utcoffset(), timedelta(hours=1))
        self.assertEqual(summer.utcoffset(), timedelta(hours=2))

    def test_istat_reference_uses_registry_identity_and_canonical_coordinates(self):
        request = shadow.canonical_weather_request("Pordenone")
        snapshot = build_snapshot(municipality="Pordenone")

        result = evaluate(snapshot, municipality=request["istat_code"])

        self.assertEqual(result["status"], "no_candidate")
        self.assertEqual(result["municipality"]["istat_code"], request["istat_code"])
        self.assertEqual(result["municipality"]["latitude"], request["latitude"])
        self.assertEqual(result["municipality"]["longitude"], request["longitude"])
        self.assertFalse(result["can_send"])
        self.assertTrue(result["shadow_only"])

    def test_noncanonical_requested_coordinates_are_rejected(self):
        snapshot = build_snapshot()
        snapshot["requested_location"]["latitude"] += 0.01

        result = evaluate(snapshot)

        self.assertEqual(result["status"], "rejected")
        self.assertIn(
            "requested_location_coordinates_not_canonical",
            result["validation_errors"],
        )
        self.assertEqual(result["candidates"], [])

    def test_locality_coordinates_and_identity_drive_candidate_dedupe(self):
        locality = FvgGeographyCatalog().match_locality_id(
            "irdat-5000:DBPRIOR_0411_LOCAL_PUNT.3931"
        )
        self.assertIsNotNone(locality)
        snapshot = build_snapshot(
            municipality="093022",
            locality=locality,
            wind_gusts_10m=[70.0] * 6,
        )

        result = evaluate(
            snapshot,
            municipality="093022",
            locality=locality,
        )

        self.assertEqual(result["status"], "candidates")
        self.assertEqual(result["locality"]["name"], "Vigonovo")
        candidate = candidate_for(result, "wind")
        self.assertEqual(candidate["locality"]["id"], locality.id)
        self.assertIn(locality.id, candidate["dedupe"]["event_key"])

    def test_requested_city_must_match_registry_identity(self):
        snapshot = build_snapshot()
        snapshot["requested_location"]["city"] = "Udine"

        result = evaluate(snapshot)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("requested_location_city_mismatch", result["validation_errors"])

    def test_stale_snapshot_is_rejected(self):
        snapshot = build_snapshot()
        snapshot["fetched_at"] = (NOW - timedelta(minutes=46)).isoformat(
            timespec="minutes"
        )

        result = evaluate(snapshot)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("snapshot_stale", result["validation_errors"])

    def test_wrong_timezone_and_units_are_rejected(self):
        snapshot = build_snapshot()
        snapshot["timezone"] = "UTC"
        snapshot["hourly_units"]["wind_gusts_10m"] = "m/s"

        result = evaluate(snapshot)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("invalid_timezone", result["validation_errors"])
        self.assertIn("invalid_unit:wind_gusts_10m", result["validation_errors"])

    def test_empty_future_horizon_is_rejected_instead_of_becoming_no_candidate(self):
        snapshot = build_snapshot()
        snapshot["hourly"]["time"] = [
            (NOW - timedelta(hours=index + 1)).replace(tzinfo=None).isoformat(
                timespec="minutes"
            )
            for index in range(6)
        ][::-1]

        result = evaluate(snapshot)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("insufficient_future_slots", result["validation_errors"])

    def test_null_or_out_of_range_values_block_only_dependent_phenomena(self):
        null_snapshot = build_snapshot()
        null_snapshot["hourly"]["rain"][1] = None
        invalid_probability = build_snapshot()
        invalid_probability["hourly"]["precipitation_probability"][2] = 101

        null_result = evaluate(null_snapshot)
        range_result = evaluate(invalid_probability)

        for result, reason in ((null_result, "missing"), (range_result, "out_of_range")):
            self.assertEqual(result["status"], "partial_evaluation")
            self.assertEqual(result["validation_errors"], [])
            outcome = result["data_quality"]["phenomena"]["rain"]
            self.assertEqual(outcome["state"], "not_evaluable")
            self.assertIn(reason, [r["reason"] for r in outcome["reasons"]])
            self.assertEqual(result["data_quality"]["phenomena"]["wind"]["state"], "evaluated_no_candidate")



class ShadowThresholdTests(unittest.TestCase):
    def test_rain_requires_fifteen_mm_in_three_hours_and_seventy_percent(self):
        wet = build_snapshot(
            rain=[5.0, 5.0, 5.0, 0.0, 0.0, 0.0],
            precipitation_probability=[70.0, 60.0, 60.0, 0.0, 0.0, 0.0],
        )
        low_probability = copy.deepcopy(wet)
        low_probability["hourly"]["precipitation_probability"][0] = 69.0
        low_accumulation = copy.deepcopy(wet)
        low_accumulation["hourly"]["rain"][2] = 4.9

        wet_result = evaluate(wet)
        low_probability_result = evaluate(low_probability)
        low_accumulation_result = evaluate(low_accumulation)

        rain = candidate_for(wet_result, "rain")
        self.assertIsNotNone(rain)
        self.assertEqual(rain["evidence"][0]["value"], 15.0)
        self.assertEqual(rain["evidence"][0]["unit"], "mm")
        self.assertEqual(rain["evidence"][1]["value"], 70.0)
        self.assertIsNone(candidate_for(low_probability_result, "rain"))
        self.assertIsNone(candidate_for(low_accumulation_result, "rain"))

    def test_rain_probability_must_align_with_a_meaningfully_wet_slot(self):
        misaligned = build_snapshot(
            rain=[15.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            precipitation_probability=[20.0, 70.0, 0.0, 0.0, 0.0, 0.0],
        )

        self.assertIsNone(candidate_for(evaluate(misaligned), "rain"))

    def test_storm_uses_only_explicit_wmo_codes(self):
        for code in (95, 96, 99):
            with self.subTest(code=code):
                snapshot = build_snapshot(weather_code=[code, 1, 1, 1, 1, 1])
                storm = candidate_for(evaluate(snapshot), "storm")
                self.assertIsNotNone(storm)
                self.assertEqual(storm["evidence"][0]["value"], code)
                self.assertEqual(storm["confidence"]["level"], "single_slot_unconfirmed")
                self.assertFalse(storm["confidence"]["send_eligible"])

        self.assertIsNone(
            candidate_for(
                evaluate(build_snapshot(weather_code=[82, 82, 82, 82, 82, 82])),
                "storm",
            )
        )

    def test_storm_requires_probability_and_liquid_corroboration(self):
        consecutive_only = build_snapshot(weather_code=[95, 96, 1, 1, 1, 1])
        probability_and_liquid = build_snapshot(
            weather_code=[95, 1, 1, 1, 1, 1],
            precipitation_probability=[70.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            rain=[0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
        )

        consecutive_storm = candidate_for(evaluate(consecutive_only), "storm")
        liquid_storm = candidate_for(evaluate(probability_and_liquid), "storm")

        self.assertEqual(
            consecutive_storm["confidence"]["level"],
            "single_slot_unconfirmed",
        )
        self.assertTrue(
            consecutive_storm["evidence"][1]["two_consecutive_storm_slots"]
        )
        self.assertEqual(liquid_storm["confidence"]["level"], "corroborated")
        self.assertTrue(liquid_storm["evidence"][1]["probability_and_liquid"])

    def test_snow_requires_moderate_code_or_two_cm_with_high_probability(self):
        slight = build_snapshot(
            weather_code=[71, 71, 71, 1, 1, 1],
            snowfall=[0.7, 0.7, 0.6, 0.0, 0.0, 0.0],
        )
        weak_shower = build_snapshot(weather_code=[85, 1, 1, 1, 1, 1])
        moderate = build_snapshot(weather_code=[73, 1, 1, 1, 1, 1])
        accumulated = build_snapshot(
            snowfall=[0.7, 0.7, 0.6, 0.0, 0.0, 0.0],
            precipitation_probability=[70.0, 60.0, 60.0, 0.0, 0.0, 0.0],
        )
        low_probability = copy.deepcopy(accumulated)
        low_probability["hourly"]["precipitation_probability"][0] = 69.0

        self.assertIsNone(candidate_for(evaluate(slight), "snow"))
        self.assertIsNone(candidate_for(evaluate(weak_shower), "snow"))
        self.assertEqual(
            candidate_for(evaluate(moderate), "snow")["evidence"][0]["value"],
            73,
        )
        snow = candidate_for(evaluate(accumulated), "snow")
        self.assertEqual(snow["evidence"][0]["value"], 2.0)
        self.assertEqual(snow["evidence"][0]["unit"], "cm")
        self.assertEqual(snow["evidence"][1]["value"], 70.0)
        self.assertIsNone(candidate_for(evaluate(low_probability), "snow"))

    def test_ice_requires_explicit_freezing_precipitation_code(self):
        inferred_only = build_snapshot(
            temperature_2m=[-2.0] * 6,
            rain=[1.0] * 6,
            weather_code=[61] * 6,
        )
        explicit = build_snapshot(weather_code=[66, 1, 1, 1, 1, 1])

        self.assertIsNone(candidate_for(evaluate(inferred_only), "ice"))
        ice = candidate_for(evaluate(explicit), "ice")
        self.assertIsNotNone(ice)
        self.assertEqual(ice["evidence"][0]["value"], 66)

    def test_wind_gust_threshold_is_inclusive_at_seventy_kmh(self):
        below = build_snapshot(wind_gusts_10m=[69.9] * 6)
        threshold = build_snapshot(
            wind_gusts_10m=[70.0, 20.0, 20.0, 20.0, 20.0, 20.0]
        )

        self.assertIsNone(candidate_for(evaluate(below), "wind"))
        wind = candidate_for(evaluate(threshold), "wind")
        self.assertEqual(wind["evidence"][0]["value"], 70.0)

    def test_heat_temperature_requires_two_consecutive_slots_at_35(self):
        one_slot = build_snapshot(
            temperature_2m=[35.0, 34.0, 34.0, 34.0, 34.0, 34.0]
        )
        two_slots = build_snapshot(
            temperature_2m=[35.0, 35.0, 34.0, 34.0, 34.0, 34.0]
        )

        self.assertIsNone(candidate_for(evaluate(one_slot), "heat"))
        heat = candidate_for(evaluate(two_slots), "heat")
        self.assertEqual(heat["evidence"][0]["metric"], "temperature_2m")
        self.assertEqual(heat["evidence"][0]["values"], [35.0, 35.0])

    def test_apparent_heat_requires_two_consecutive_slots_at_38(self):
        watch_only = build_snapshot(
            apparent_temperature=[37.0, 37.5, 36.0, 36.0, 36.0, 36.0]
        )
        candidate = build_snapshot(
            apparent_temperature=[38.0, 38.5, 36.0, 36.0, 36.0, 36.0]
        )

        watch_result = evaluate(watch_only)
        candidate_result = evaluate(candidate)

        self.assertIsNone(candidate_for(watch_result, "heat"))
        self.assertEqual(watch_result["observations"][0]["kind"], "heat_watch")
        heat = candidate_for(candidate_result, "heat")
        self.assertEqual(heat["evidence"][0]["metric"], "apparent_temperature")
        self.assertEqual(heat["evidence"][0]["values"], [38.0, 38.5])

    def test_onset_beyond_one_hour_is_observed_but_not_a_candidate(self):
        snapshot = build_snapshot(
            wind_gusts_10m=[20.0, 70.0, 20.0, 20.0, 20.0, 20.0]
        )

        result = evaluate(snapshot)

        self.assertIsNone(candidate_for(result, "wind"))
        deferred = next(
            item
            for item in result["observations"]
            if item.get("kind") == "wind"
        )
        self.assertEqual(deferred["reason"], "onset_beyond_notice_window")
        self.assertEqual(deferred["maximum_lead_minutes"], 60)

    def test_heat_uses_the_earliest_qualifying_metric_window(self):
        snapshot = build_snapshot(
            temperature_2m=[30.0, 30.0, 35.0, 35.0, 30.0, 30.0],
            apparent_temperature=[38.0, 38.0, 32.0, 32.0, 32.0, 32.0],
        )

        heat = candidate_for(evaluate(snapshot), "heat")

        self.assertEqual(heat["evidence"][0]["metric"], "apparent_temperature")
        self.assertTrue(heat["event_at"].endswith("11:00+02:00"))


class ShadowDedupeTests(unittest.TestCase):
    def test_same_event_bucket_keeps_stable_key_when_snapshot_changes(self):
        first_now = datetime(2026, 8, 14, 8, 15, tzinfo=ROME)
        second_now = datetime(2026, 8, 14, 9, 15, tzinfo=ROME)
        first = build_snapshot(
            now=first_now,
            weather_code=[95, 1, 1, 1, 1, 1],
        )
        second = build_snapshot(
            now=second_now,
            weather_code=[99, 1, 1, 1, 1, 1],
        )

        first_storm = candidate_for(evaluate(first, now=first_now), "storm")
        second_storm = candidate_for(evaluate(second, now=second_now), "storm")

        self.assertEqual(first_storm["dedupe"], second_storm["dedupe"])
        self.assertNotEqual(first_storm["event_at"], second_storm["event_at"])
        self.assertNotEqual(first_storm["evidence"], second_storm["evidence"])

    def test_night_candidate_is_not_suppressed_by_quiet_hours(self):
        night_now = datetime(2026, 8, 15, 0, 15, tzinfo=ROME)
        snapshot = build_snapshot(
            now=night_now,
            weather_code=[95, 1, 1, 1, 1, 1],
        )

        result = evaluate(snapshot, now=night_now)

        storm = candidate_for(result, "storm")
        self.assertIsNotNone(storm)
        self.assertTrue(storm["event_at"].endswith("+02:00"))
        self.assertFalse(storm["can_notify"])


if __name__ == "__main__":
    unittest.main()
