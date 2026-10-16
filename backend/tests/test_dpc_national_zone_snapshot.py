import struct
import unittest
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.weather.dpc_national_alerts import parse_dpc_national_cap
from app.weather.dpc_national_zone_snapshot import (
    DpcNationalZoneSnapshotError,
    parse_dpc_national_zone_zip,
    reconcile_dpc_cap_and_zone_snapshot,
)

from tests.test_dpc_national_alerts import cap, info


FIELDS = (
    ("Zona_all", 80),
    ("Nome_zona", 146),
    ("Criticita", 80),
    ("Idrogeo", 80),
    ("Temporali", 80),
    ("Idraulico", 80),
)
GREEN = "Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA"
YELLOW = "Ordinaria criticita / ALLERTA GIALLA"
ORANGE = "Moderata criticita / ALLERTA ARANCIONE"
NOT_TRANSMITTED = "VALUTAZIONE NON TRASMESSA"


def dbf(rows):
    header_length = 32 + len(FIELDS) * 32 + 1
    record_length = 1 + sum(length for _, length in FIELDS)
    header = bytearray(header_length)
    header[0] = 0x03
    struct.pack_into("<I", header, 4, len(rows))
    struct.pack_into("<HH", header, 8, header_length, record_length)
    value_offset = 1
    for index, (name, length) in enumerate(FIELDS):
        offset = 32 + index * 32
        encoded_name = name.encode("ascii")
        header[offset : offset + len(encoded_name)] = encoded_name
        header[offset + 11] = ord("C")
        header[offset + 16] = length
        value_offset += length
    header[-1] = 0x0D
    output = bytearray(header)
    for row in rows:
        record = bytearray(b" " * record_length)
        offset = 1
        for name, length in FIELDS:
            encoded = row[name].encode("cp1252")
            record[offset : offset + len(encoded)] = encoded
            offset += length
        output.extend(record)
    output.append(0x1A)
    return bytes(output)


def shape_header(*, records, index=False):
    size = 100 + records * 8 if index else 100
    header = bytearray(size)
    struct.pack_into(">I", header, 0, 9994)
    struct.pack_into(">I", header, 24, size // 2)
    struct.pack_into("<I", header, 28, 1000)
    struct.pack_into("<I", header, 32, 5)
    return bytes(header)


def row(zone, name, *, hydro=GREEN, thunderstorm=GREEN, hydraulic=GREEN):
    levels = (hydro, thunderstorm, hydraulic)
    rank = {GREEN: 0, YELLOW: 1, ORANGE: 2, NOT_TRANSMITTED: -1}
    transmitted = [value for value in levels if value != NOT_TRANSMITTED]
    summary = max(transmitted, key=rank.get) if transmitted else NOT_TRANSMITTED
    return {
        "Zona_all": zone,
        "Nome_zona": name,
        "Criticita": summary,
        "Idrogeo": hydro,
        "Temporali": thunderstorm,
        "Idraulico": hydraulic,
    }


def zone_zip(today, tomorrow=None, revision="20260924_1434"):
    tomorrow = today if tomorrow is None else tomorrow
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        for period, rows in (("today", today), ("tomorrow", tomorrow)):
            prefix = f"{revision}_{period}"
            archive.writestr(f"{prefix}.dbf", dbf(rows))
            archive.writestr(f"{prefix}.prj", "GEOGCS[\"WGS 84\"]")
            archive.writestr(
                f"{prefix}.shp", shape_header(records=len(rows), index=False)
            )
            archive.writestr(
                f"{prefix}.shx", shape_header(records=len(rows), index=True)
            )
        archive.writestr("README.txt", "fixture")
        archive.writestr("BCR_shape_RNDT.xml", "<metadata />")
    return stream.getvalue()


def enough_rows(overrides=()):
    rows = [
        row(f"Test-{index:03d}", f"Zona {index:03d}")
        for index in range(100)
    ]
    for index, value in enumerate(overrides):
        rows[index] = value
    return rows


class DpcNationalZoneSnapshotTests(unittest.TestCase):
    def test_complete_snapshot_preserves_green_active_and_not_transmitted(self):
        rows = enough_rows(
            (
                row("Friu-A", "Bacino del Livenza", thunderstorm=YELLOW),
                row("Cala-2", "Versante Tirrenico", hydraulic=ORANGE),
                row(
                    "Sard-A",
                    "Iglesiente",
                    hydro=NOT_TRANSMITTED,
                    thunderstorm=NOT_TRANSMITTED,
                    hydraulic=NOT_TRANSMITTED,
                ),
            )
        )
        payload = parse_dpc_national_zone_zip(zone_zip(rows))

        self.assertTrue(payload["can_confirm_green"])
        self.assertEqual(payload["coverage"], "all_zones_two_days")
        self.assertEqual(payload["zone_count"], 100)
        self.assertEqual(len(payload["records"]), 600)
        self.assertTrue(payload["active"])
        fvg = [record for record in payload["records"] if record["zone_id"] == "FVG-A"]
        self.assertEqual(len(fvg), 6)
        self.assertIn("yellow", {record["level"] for record in fvg})
        sardinia = [
            record for record in payload["records"] if record["source_zone_id"] == "Sard-A"
        ]
        self.assertTrue(all(record["level"] is None for record in sardinia))

    def test_reconciles_cap_only_when_revision_and_every_active_state_match(self):
        today = enough_rows(
            (row("Camp-1", "Piana campana", thunderstorm=YELLOW),)
        )
        tomorrow = enough_rows(
            (row("Camp-1", "Piana campana"),)
        )
        complete = parse_dpc_national_zone_zip(zone_zip(today, tomorrow))
        cap_payload = parse_dpc_national_cap(
            cap(info(areas=(("Camp-1", "Piana campana"),)))
        )

        reconciled = reconcile_dpc_cap_and_zone_snapshot(cap_payload, complete)
        self.assertTrue(reconciled["reconciled"])
        self.assertTrue(reconciled["active"])
        self.assertEqual(reconciled["cap_revision"]["id"], cap_payload["revision"]["id"])

        wrong_state = parse_dpc_national_zone_zip(
            zone_zip(enough_rows((row("Camp-1", "Piana campana", hydraulic=YELLOW),)), tomorrow)
        )
        with self.assertRaisesRegex(
            DpcNationalZoneSnapshotError, "dpc_zone_cap_state_mismatch"
        ):
            reconcile_dpc_cap_and_zone_snapshot(cap_payload, wrong_state)

    def test_rejects_unreported_active_zone_and_revision_mismatch(self):
        complete = parse_dpc_national_zone_zip(
            zone_zip(enough_rows((row("Camp-1", "Piana campana", thunderstorm=YELLOW),)))
        )
        empty_cap = parse_dpc_national_cap(cap())
        with self.assertRaisesRegex(
            DpcNationalZoneSnapshotError, "dpc_zone_cap_coverage_mismatch"
        ):
            reconcile_dpc_cap_and_zone_snapshot(empty_cap, complete)

        different_revision = parse_dpc_national_zone_zip(
            zone_zip(enough_rows(), revision="20260924_1435")
        )
        with self.assertRaisesRegex(
            DpcNationalZoneSnapshotError, "dpc_zone_revision_mismatch"
        ):
            reconcile_dpc_cap_and_zone_snapshot(empty_cap, different_revision)

    def test_rejects_incomplete_or_mixed_period_catalog(self):
        rows = enough_rows()
        with self.assertRaisesRegex(
            DpcNationalZoneSnapshotError, "dpc_zone_incomplete_zip"
        ):
            data = zone_zip(rows)
            source = ZipFile(BytesIO(data))
            stream = BytesIO()
            with source, ZipFile(stream, "w", ZIP_DEFLATED) as target:
                for member in source.infolist():
                    if not member.filename.endswith("tomorrow.shx"):
                        target.writestr(member, source.read(member))
            parse_dpc_national_zone_zip(stream.getvalue())

        with self.assertRaisesRegex(
            DpcNationalZoneSnapshotError, "dpc_zone_period_catalog_mismatch"
        ):
            parse_dpc_national_zone_zip(
                zone_zip(rows, enough_rows((row("Other-1", "Other"),)))
            )

    def test_rejects_summary_that_disagrees_with_risk_fields(self):
        rows = enough_rows()
        rows[0]["Criticita"] = ORANGE
        with self.assertRaisesRegex(
            DpcNationalZoneSnapshotError, "dpc_zone_summary_risk_mismatch"
        ):
            parse_dpc_national_zone_zip(zone_zip(rows))


if __name__ == "__main__":
    unittest.main()
