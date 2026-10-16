"""Tests for the read-only Bulletin display payload audit."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "backend_dryrun_staging"
sys.path.insert(0, str(STAGING))

import bulletin_display_payload_audit as display_audit  # noqa: E402


def areas9(source_kind: str = "structured_xml") -> dict:
    return {
        area_id: {
            "id": area_id,
            "source_kind": source_kind,
            "attendibilita": 70,
            "sintesi": f"Area {area_id}",
        }
        for area_id in display_audit.AREA_IDS
    }


def fasce4() -> dict:
    return {
        fascia_id: {
            "id": fascia_id,
            "sintesi": f"Fascia {fascia_id}",
        }
        for fascia_id in display_audit.FASCE_IDS
    }


def structured_day(
    valid_date: str = "2026-06-27",
    source_kind: str = "structured_xml",
    area_map: dict | None = None,
) -> dict:
    return {
        "valid_date": valid_date,
        "source_kind": source_kind,
        "areas9": area_map if area_map is not None else areas9(source_kind),
        "fasce4": fasce4(),
    }


def payload_with_structured_day(
    *,
    source_kind: str = "structured_xml",
    source_status: str = "merged_xml_window",
    area_map: dict | None = None,
) -> dict:
    return {
        "city": "Pordenone",
        "forecast": {
            "official": {
                "it": {
                    "updated_at": "2026-06-27T08:00:00+02:00",
                    "forecasts": [
                        {
                            "date": "2026-06-27",
                            "date_label": "Oggi",
                            "emission": "Aggiornato 27/06 - 08:00",
                            "text": "Giornata stabile con nubi alte sui monti.",
                        }
                    ],
                }
            },
            "forecast": [
                {
                    "date": "2026-06-27",
                    "text": "Fallback modello da non preferire.",
                }
            ],
            "osmer_structured": {
                "source_kind": source_kind,
                "source_status": source_status,
                "data_emissione": "2026-06-27T11:38:00Z",
                "source_date": "2026-06-27",
                "days": [
                    structured_day(
                        "2026-06-27",
                        source_kind=source_kind,
                        area_map=area_map,
                    )
                ],
            },
        },
        "official_alerts": {
            "source_mode": "regional_fvg_primary",
            "cache": {"status": "fresh"},
            "alerts": [],
        },
    }


def rows_by_field(report: dict) -> dict:
    rows = report["payloads"][0]["rows"]
    return {row["ui_field"]: row for row in rows}


class BulletinDisplayPayloadAuditTest(unittest.TestCase):
    def test_build_city_url_encodes_spaces(self) -> None:
        url = display_audit.build_city_url(
            "http://127.0.0.1:5173/api/weather/bootstrap",
            "Lignano Sabbiadoro",
        )

        self.assertEqual(
            "http://127.0.0.1:5173/api/weather/bootstrap?city=Lignano+Sabbiadoro",
            url,
        )

    def test_ready_structured_payload_maps_ui_fields(self) -> None:
        report = display_audit.build_report_from_payloads([payload_with_structured_day()])
        rows = rows_by_field(report)
        summary = report["payloads"][0]["summary"]

        self.assertEqual(1, summary["official_text_days"])
        self.assertEqual(1, summary["native_map_days"])
        self.assertTrue(rows["source.title"]["safe_to_show"])
        self.assertTrue(rows["source.updatedLabel"]["safe_to_show"])
        self.assertEqual("2026-06-27T08:00:00+02:00", rows["source.updatedLabel"]["value"])
        self.assertEqual("ready", rows["days[today].officialText"]["state"])
        self.assertTrue(rows["days[today].officialText"]["safe_to_show"])
        self.assertEqual("ready", rows["days[today].nativeMap"]["state"])
        self.assertTrue(rows["days[today].nativeMap"]["safe_to_show"])
        self.assertTrue(rows["days[today].reliability"]["safe_to_show"])
        self.assertEqual("inactive_or_empty", rows["alert.banner"]["state"])
        self.assertFalse(rows["alert.banner"]["safe_to_show"])

    def test_projected_day_does_not_enable_native_map(self) -> None:
        report = display_audit.build_report_from_payloads([
            payload_with_structured_day(source_kind="official_projected")
        ])
        rows = rows_by_field(report)

        self.assertTrue(rows["days[today].officialText"]["safe_to_show"])
        self.assertEqual("ready", rows["days[today].nativeMap"]["state"])
        self.assertFalse(rows["days[today].nativeMap"]["safe_to_show"])
        self.assertIn(
            "source_kind=official_projected",
            rows["days[today].nativeMap"]["reason"],
        )

    def test_incomplete_areas_block_native_map(self) -> None:
        incomplete = areas9()
        incomplete.pop("A9")
        report = display_audit.build_report_from_payloads([
            payload_with_structured_day(area_map=incomplete)
        ])
        rows = rows_by_field(report)

        self.assertEqual("partial", rows["days[today].nativeMap"]["state"])
        self.assertFalse(rows["days[today].nativeMap"]["safe_to_show"])
        self.assertIn("aree=8/9", rows["days[today].nativeMap"]["reason"])
        self.assertFalse(rows["days[today].reliability"]["safe_to_show"])

    def test_dpc_unverified_alert_is_diagnostic_not_banner(self) -> None:
        payload = payload_with_structured_day()
        payload["official_alerts"] = {
            "source_mode": "github_actions_dpc_national_criticity_no_active_fvg_unverified",
            "cache": {"status": "fresh"},
            "alerts": [],
        }

        report = display_audit.build_report_from_payloads([payload])
        alert = rows_by_field(report)["alert.banner"]

        self.assertEqual("diagnostic", alert["state"])
        self.assertFalse(alert["safe_to_show"])
        self.assertIn("DPC diagnostico", alert["reason"])

    def test_updated_label_falls_back_to_structured_emission_not_day_emission(self) -> None:
        payload = payload_with_structured_day()
        payload["forecast"]["official"]["it"].pop("updated_at")

        report = display_audit.build_report_from_payloads([payload])
        updated = rows_by_field(report)["source.updatedLabel"]

        self.assertEqual("2026-06-27T11:38:00Z", updated["value"])

    def test_fifth_not_yet_emitted_day_stays_pending_on_calendar_date(self) -> None:
        official_dates = ["2026-06-28", "2026-06-29", "2026-06-30", "2026-07-01"]
        payload = payload_with_structured_day()
        payload["forecast"]["official"]["it"]["forecasts"] = [
            {
                "date": date_key,
                "date_label": date_key,
                "text": f"Bollettino ufficiale {date_key}.",
            }
            for date_key in official_dates
        ]
        payload["forecast"]["forecast"] = [
            {"date": "2026-06-29", "text": "Modello lunedi."},
            {"date": "2026-06-30", "text": "Modello martedi."},
            {"date": "2026-07-01", "text": "Modello mercoledi."},
            {"date": "2026-07-02", "text": "Modello giovedi."},
            {"date": "2026-07-03", "text": "Modello venerdi da non usare."},
        ]
        payload["forecast"]["osmer_structured"]["days"] = [
            structured_day(date_key) for date_key in official_dates
        ]

        report = display_audit.build_report_from_payloads([payload])
        rows = rows_by_field(report)
        summary = report["payloads"][0]["summary"]

        self.assertEqual(4, summary["official_text_days"])
        self.assertEqual(4, summary["native_map_days"])
        self.assertEqual(1, summary["pending_days"])
        self.assertEqual("2026-07-02", rows["days[plus4].tabLabel"]["value"])
        self.assertEqual("pending", rows["days[plus4].officialText"]["state"])
        self.assertEqual("UI copy", rows["days[plus4].officialText"]["source"])
        self.assertTrue(rows["days[plus4].officialText"]["safe_to_show"])
        self.assertEqual("Bollettino non ancora emesso.", rows["days[plus4].officialText"]["value"])
        self.assertEqual("pending", rows["days[plus4].nativeMap"]["state"])
        self.assertFalse(rows["days[plus4].nativeMap"]["safe_to_show"])
        self.assertIn("non ancora emesso", rows["days[plus4].nativeMap"]["reason"])

    def test_fur_audit_uses_calendar_window_when_translated_forecasts_are_stale(self) -> None:
        payload = payload_with_structured_day()
        payload["forecast"]["official"]["it"]["forecasts"] = [
            {
                "date": date_key,
                "text": f"Bollettino italiano {date_key}.",
            }
            for date_key in ["2026-06-28", "2026-06-29", "2026-06-30", "2026-07-01"]
        ]
        payload["forecast"]["official"]["fur"] = {
            "forecasts": [
                {"date": "2026-06-27", "date_label": "domenie 28 Jugn", "text": "Boletin furlan 28."},
                {"date": "2026-06-28", "date_label": "lunis 29 Jugn", "text": "Boletin furlan 29."},
                {"date": "2026-06-29", "date_label": "martars 30 Jugn", "text": "Boletin furlan 30."},
                {"date": "2026-06-30", "date_label": "tindince par miercus 01 Lui", "text": "Boletin furlan 01."},
            ]
        }
        payload["forecast"]["osmer_structured"]["days"] = []

        report = display_audit.build_report_from_payloads([payload], language="fur")
        rows = rows_by_field(report)
        summary = report["payloads"][0]["summary"]

        self.assertEqual(4, summary["official_text_days"])
        self.assertEqual(1, summary["pending_days"])
        self.assertEqual("domenie 28 Jugn", rows["days[today].tabLabel"]["value"])
        self.assertEqual("Boletin furlan 28.", rows["days[today].officialText"]["value"])
        self.assertEqual("Boletin furlan 01.", rows["days[plus3].officialText"]["value"])
        self.assertEqual("2026-07-02", rows["days[plus4].tabLabel"]["value"])
        self.assertEqual("pending", rows["days[plus4].officialText"]["state"])

    def test_stale_source_blocks_map_and_reliability(self) -> None:
        report = display_audit.build_report_from_payloads([
            payload_with_structured_day(source_status="source_unavailable")
        ])
        rows = rows_by_field(report)

        self.assertEqual("stale", rows["days[today].nativeMap"]["state"])
        self.assertFalse(rows["days[today].nativeMap"]["safe_to_show"])
        self.assertFalse(rows["days[today].reliability"]["safe_to_show"])

    def test_text_report_contains_field_table(self) -> None:
        report = display_audit.build_report_from_payloads([payload_with_structured_day()])
        text = display_audit.format_text_report(report)

        self.assertIn("Audit visualizzazione Bollettino", text)
        self.assertIn("Pordenone | righe=", text)
        self.assertIn("| Campo UI | Stato | Show | Fonte | Path | Motivo |", text)
        self.assertIn("days[today].nativeMap", text)
        self.assertIn("Firestore=no, FCM=no, workflow=no, writes=no", text)


if __name__ == "__main__":
    unittest.main()
