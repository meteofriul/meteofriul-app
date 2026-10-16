import unittest
from copy import deepcopy
from datetime import datetime

from app.services.national_official_alerts import (
    NATIONAL_LOCATION_ALERTS_CONTRACT,
    NationalOfficialAlertsProjectionError,
    project_national_official_alerts,
)
from app.weather.dpc_national_alerts import parse_dpc_national_cap
from app.weather.dpc_national_zone_snapshot import (
    parse_dpc_national_zone_zip,
    reconcile_dpc_cap_and_zone_snapshot,
)

from tests.test_dpc_national_alerts import cap, info
from tests.test_dpc_national_zone_snapshot import enough_rows, row, zone_zip


NOW = datetime.fromisoformat("2026-09-24T15:00:00+02:00")


def reconciled_snapshot(zone="Marc-2", *, level="yellow"):
    keyword = {
        "yellow": "ORDINARIA CRITICITA' PER RISCHIO TEMPORALI / ALLERTA GIALLA:",
        "orange": "MODERATA CRITICITA' PER RISCHIO IDRAULICO / ALLERTA ARANCIONE:",
    }[level]
    risk = "thunderstorm" if level == "yellow" else "hydraulic"
    kwargs = {risk: "Ordinaria criticita / ALLERTA GIALLA"}
    if level == "orange":
        kwargs[risk] = "Moderata criticita / ALLERTA ARANCIONE"
    if zone.startswith("Marc-"):
        today_overrides = (
            row("Marc-1", "Marche zona 1"),
            row("Marc-2", "Marche zona 2", **kwargs),
        )
        tomorrow_overrides = (
            row("Marc-1", "Marche zona 1"),
            row("Marc-2", "Marche zona 2"),
        )
    else:
        today_overrides = (row(zone, "Zona test", **kwargs),)
        tomorrow_overrides = (row(zone, "Zona test"),)
    today = enough_rows(today_overrides)
    tomorrow = enough_rows(tomorrow_overrides)
    zone_state = parse_dpc_national_zone_zip(zone_zip(today, tomorrow))
    cap_state = parse_dpc_national_cap(
        cap(
            info(
                event=keyword,
                description=(
                    "all_GIALLA PER OGGI SU:"
                    if level == "yellow"
                    else "all_ARANCIONE PER OGGI SU:"
                ),
                areas=((zone, "Zona test"),),
            )
        )
    )
    return reconcile_dpc_cap_and_zone_snapshot(cap_state, zone_state)


class NationalOfficialAlertsProjectionTests(unittest.TestCase):
    def test_projects_one_national_municipality_and_preserves_risks(self):
        snapshot = reconciled_snapshot()
        result = project_national_official_alerts(
            snapshot, "041067", now=NOW  # Urbino, Marche
        )

        self.assertEqual(result["contract"], NATIONAL_LOCATION_ALERTS_CONTRACT)
        self.assertEqual(result["municipality"]["name"], "Urbino")
        self.assertEqual(result["zones"], ["DPC:Marc-1", "DPC:Marc-2"])
        self.assertTrue(result["conservative_multi_zone_display"])
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["highest_level"], "yellow")
        self.assertTrue(result["standalone_display_allowed"])
        self.assertFalse(result["regional_detail"]["required"])
        self.assertEqual(
            {record["risk"] for record in result["records"]},
            {"hydrogeological", "thunderstorm", "hydraulic"},
        )

    def test_fvg_projection_cannot_replace_regional_detail(self):
        snapshot = reconciled_snapshot(zone="Friu-A")
        result = project_national_official_alerts(snapshot, "093033", now=NOW)

        self.assertEqual(result["zones"], ["FVG-A"])
        self.assertFalse(result["conservative_multi_zone_display"])
        self.assertFalse(result["standalone_display_allowed"])
        self.assertTrue(result["regional_detail"]["required"])
        self.assertFalse(result["regional_detail"]["reconciled"])

    def test_rejects_unverified_stale_or_incomplete_snapshots(self):
        snapshot = reconciled_snapshot()
        def remove_selected_risk(item):
            item["records"] = [
                record
                for record in item["records"]
                if not (
                    record["zone_id"] == "DPC:Marc-1"
                    and record["risk"] == "hydraulic"
                    and record["forecast_day"] == "2026-09-24"
                )
            ]

        for mutate, expected in (
            (lambda item: item.update(reconciled=False), "unverified"),
            (remove_selected_risk, "coverage_incomplete"),
        ):
            with self.subTest(expected=expected):
                candidate = deepcopy(snapshot)
                mutate(candidate)
                with self.assertRaisesRegex(
                    NationalOfficialAlertsProjectionError, expected
                ):
                    project_national_official_alerts(candidate, "041067", now=NOW)

        with self.assertRaisesRegex(
            NationalOfficialAlertsProjectionError, "stale"
        ):
            project_national_official_alerts(
                snapshot,
                "041067",
                now=datetime.fromisoformat("2026-09-26T08:00:00+02:00"),
            )

    def test_unknown_municipality_fails_closed(self):
        with self.assertRaisesRegex(
            NationalOfficialAlertsProjectionError, "municipality_unresolved"
        ):
            project_national_official_alerts(
                reconciled_snapshot(), "999999", now=NOW
            )


if __name__ == "__main__":
    unittest.main()
