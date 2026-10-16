import unittest

from app.weather.dpc_national_alerts import (
    DPC_NATIONAL_ALERTS_CONTRACT,
    DpcNationalAlertContractError,
    canonical_dpc_zone_id,
    parse_dpc_national_cap,
)


CAP_HEADER = """<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>DPC_BULLETIN_2026_09_24_7024</identifier>
  <sender>2.49.0.0.380.1</sender>
  <sent>2026-09-24T14:34:00+02:00</sent>
  <status>Actual</status><msgType>Alert</msgType><scope>Public</scope>
"""


def info(
    *,
    event="ORDINARIA CRITICITA' PER RISCHIO TEMPORALI / ALLERTA GIALLA:",
    description="all_GIALLA PER OGGI SU:",
    onset="2026-09-24T12:00:00+02:00",
    expires="2026-09-24T23:59:59+02:00",
    areas=(('Camp-1', 'Piana campana, Napoli, Isole e Area vesuviana'),),
):
    area_xml = "".join(
        f"""<area><areaDesc>{name}</areaDesc><geocode>
        <valueName>Zona di Allerta</valueName><value>{zone}</value>
        </geocode></area>"""
        for zone, name in areas
    )
    return f"""<info><category>Met</category><event>{event}</event>
    <onset>{onset}</onset><expires>{expires}</expires>
    <description>{description}</description>{area_xml}</info>"""


def cap(*items, header=CAP_HEADER):
    return header + "".join(items) + "</alert>"


class DpcNationalAlertsTests(unittest.TestCase):
    def test_parses_zone_risk_validity_without_claiming_omitted_zones_green(self):
        payload = parse_dpc_national_cap(
            cap(
                info(
                    areas=(
                        ("Camp-1", "Piana campana"),
                        ("Camp-4", "Alta Irpinia e Sannio"),
                    )
                )
            )
        )

        self.assertEqual(payload["contract"], DPC_NATIONAL_ALERTS_CONTRACT)
        self.assertTrue(payload["active"])
        self.assertFalse(payload["can_confirm_green"])
        self.assertEqual(payload["coverage"], "reported_zones_only")
        self.assertEqual(
            [record["zone_id"] for record in payload["records"]],
            ["DPC:Camp-1", "DPC:Camp-4"],
        )
        self.assertTrue(
            all(record["risk"] == "thunderstorm" for record in payload["records"])
        )
        self.assertTrue(
            all(record["level"] == "yellow" for record in payload["records"])
        )

    def test_fvg_dpc_zone_aliases_match_existing_regional_contract(self):
        self.assertEqual(canonical_dpc_zone_id("Friu-A"), "FVG-A")
        self.assertEqual(canonical_dpc_zone_id("friu-d"), "FVG-D")
        payload = parse_dpc_national_cap(
            cap(info(areas=(("Friu-C", "Bacino dell'Isonzo"),)))
        )
        record = payload["records"][0]
        self.assertEqual(record["zone_id"], "FVG-C")
        self.assertEqual(record["source_zone_id"], "Friu-C")

    def test_preserves_independent_risks_and_forecast_windows(self):
        payload = parse_dpc_national_cap(
            cap(
                info(areas=(("Cala-2", "Versante Tirrenico"),)),
                info(
                    event="MODERATA CRITICITA' PER RISCHIO IDRAULICO / ALLERTA ARANCIONE:",
                    description="all_ARANCIONE PER DOMANI SU:",
                    onset="2026-09-25T00:00:00+02:00",
                    expires="2026-09-25T23:59:59+02:00",
                    areas=(("Cala-2", "Versante Tirrenico"),),
                ),
            )
        )

        self.assertEqual(len(payload["records"]), 2)
        tomorrow = payload["records"][1]
        self.assertEqual(tomorrow["risk"], "hydraulic")
        self.assertEqual(tomorrow["level"], "orange")
        self.assertEqual(tomorrow["level_rank"], 2)
        self.assertEqual(tomorrow["valid_from"], "2026-09-25T00:00:00+02:00")

    def test_marks_not_transmitted_without_inventing_a_level(self):
        payload = parse_dpc_national_cap(
            cap(
                info(
                    event="VALUTAZIONE NON TRASMESSA PER RISCHIO IDROGEOLOGICO:",
                    description="VALUTAZIONE NON TRASMESSA",
                    areas=(("Sard-A", "Iglesiente"),),
                )
            )
        )

        record = payload["records"][0]
        self.assertIsNone(record["level"])
        self.assertIsNone(record["level_rank"])
        self.assertEqual(record["transmission_status"], "not_transmitted")
        self.assertFalse(payload["active"])

    def test_identical_duplicate_is_collapsed_but_conflict_is_rejected(self):
        item = info(areas=(("Camp-1", "Piana campana"),))
        payload = parse_dpc_national_cap(cap(item, item))
        self.assertEqual(len(payload["records"]), 1)

        conflicting = info(
            event="MODERATA CRITICITA' PER RISCHIO TEMPORALI / ALLERTA ARANCIONE:",
            description="all_ARANCIONE PER OGGI SU:",
            areas=(("Camp-1", "Piana campana"),),
        )
        with self.assertRaisesRegex(
            DpcNationalAlertContractError,
            "dpc_cap_conflicting_zone_record",
        ):
            parse_dpc_national_cap(cap(item, conflicting))

    def test_rejects_unsafe_or_non_public_documents(self):
        with self.assertRaisesRegex(
            DpcNationalAlertContractError, "dpc_cap_unsafe_xml"
        ):
            parse_dpc_national_cap(
                '<!DOCTYPE alert [<!ENTITY x "unsafe">]>' + cap(info())
            )
        with self.assertRaisesRegex(
            DpcNationalAlertContractError, "dpc_cap_not_public_actual"
        ):
            parse_dpc_national_cap(
                cap(
                    info(),
                    header=CAP_HEADER.replace(
                        "<status>Actual</status>", "<status>Test</status>"
                    ),
                )
            )

    def test_rejects_naive_time_invalid_zone_and_red_thunderstorm(self):
        for invalid in (
            info(onset="2026-09-24T12:00:00"),
            info(areas=(("bad zone", "Bad"),)),
            info(
                event="ELEVATA CRITICITA' PER RISCHIO TEMPORALI / ALLERTA ROSSA:",
                description="all_ROSSA PER OGGI SU:",
            ),
        ):
            with self.assertRaises(DpcNationalAlertContractError):
                parse_dpc_national_cap(cap(invalid))


if __name__ == "__main__":
    unittest.main()
