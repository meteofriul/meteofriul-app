"""Offline tests for the official ISTAT capoluogo-point resolver."""

from __future__ import annotations

import csv
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

from experiments.weather_autonomy import resolve_istat_capoluogo_points as resolver
from experiments.weather_autonomy.local_pipeline import (
    national_forecast_points as forecast_points,
)


XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOCUMENT_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
LOCALITY_HEADERS = (
    "COD_REG",
    "COD_UTS",
    "PRO_COM",
    "LOC_ID",
    "LOC",
    "TIPO_LOC",
    "NOME",
    "CENTRO_CL",
    "ALTITUDINE",
    "POP21",
    "FAM21",
    "ABI21",
    "EDI21",
    "POINT_X",
    "POINT_Y",
)


def _canonical_json_bytes(value) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _catalog(*codes_and_names: tuple[str, str]) -> dict:
    municipalities = [
        {"istat_code": code, "name": name} for code, name in codes_and_names
    ]
    codes = sorted(record["istat_code"] for record in municipalities)
    content = {
        "catalog_version": "synthetic-capoluogo-v1",
        "kind": "meteofriul.weather.national_municipality_catalog",
        "municipalities": municipalities,
        "municipality_codes_sha256": _sha256(_canonical_json_bytes(codes)),
        "municipality_count": len(municipalities),
    }
    document = dict(content)
    document["catalog_sha256"] = _sha256(_canonical_json_bytes(content))
    return document


def _xlsx_bytes(rows: list[dict[str, str]]) -> bytes:
    """Build the sparse E/F/P/Q shape used by the current ISTAT registry."""

    ElementTree.register_namespace("", XLSX_NS)
    worksheet = ElementTree.Element(f"{{{XLSX_NS}}}worksheet")
    sheet_data = ElementTree.SubElement(worksheet, f"{{{XLSX_NS}}}sheetData")
    strings: list[str] = []
    string_indexes: dict[str, int] = {}

    values = [
        {
            "E": "Codice Comune formato alfanumerico",
            "F": "Denominazione (Italiana e straniera)",
            "P": "Codice Comune formato numerico",
            "Q": "Codice Comune numerico con 107 Province (dal 2017 al 2025)",
        },
        *rows,
    ]
    for row_number, record in enumerate(values, 1):
        row = ElementTree.SubElement(
            sheet_data, f"{{{XLSX_NS}}}row", {"r": str(row_number)}
        )
        for column in ("E", "F", "P", "Q"):
            value = record.get(column, "")
            if value == "":
                continue
            if value not in string_indexes:
                string_indexes[value] = len(strings)
                strings.append(value)
            cell = ElementTree.SubElement(
                row,
                f"{{{XLSX_NS}}}c",
                {"r": f"{column}{row_number}", "t": "s"},
            )
            ElementTree.SubElement(cell, f"{{{XLSX_NS}}}v").text = str(
                string_indexes[value]
            )

    shared = ElementTree.Element(
        f"{{{XLSX_NS}}}sst",
        {"count": str(len(strings)), "uniqueCount": str(len(strings))},
    )
    for value in strings:
        item = ElementTree.SubElement(shared, f"{{{XLSX_NS}}}si")
        ElementTree.SubElement(item, f"{{{XLSX_NS}}}t").text = value

    ElementTree.register_namespace("r", DOCUMENT_REL_NS)
    workbook = ElementTree.Element(f"{{{XLSX_NS}}}workbook")
    sheets = ElementTree.SubElement(workbook, f"{{{XLSX_NS}}}sheets")
    ElementTree.SubElement(
        sheets,
        f"{{{XLSX_NS}}}sheet",
        {
            "name": "Comuni",
            "sheetId": "1",
            f"{{{DOCUMENT_REL_NS}}}id": "rId1",
        },
    )
    relationships = ElementTree.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
    ElementTree.SubElement(
        relationships,
        f"{{{PACKAGE_REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{DOCUMENT_REL_NS}/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            ElementTree.tostring(workbook, encoding="utf-8", xml_declaration=True),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            ElementTree.tostring(
                relationships, encoding="utf-8", xml_declaration=True
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            ElementTree.tostring(worksheet, encoding="utf-8", xml_declaration=True),
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            ElementTree.tostring(shared, encoding="utf-8", xml_declaration=True),
        )
    return output.getvalue()


def _locality_row(
    pro_com: str,
    loc_id: str,
    name: str,
    point_x: str,
    point_y: str,
    *,
    centro_cl: str = "1",
    tipo_loc: str = "1",
) -> dict[str, str]:
    return {
        "COD_REG": pro_com[:2],
        "COD_UTS": pro_com[:3],
        "PRO_COM": pro_com,
        "LOC_ID": loc_id,
        "LOC": "0001",
        "TIPO_LOC": tipo_loc,
        "NOME": name,
        "CENTRO_CL": centro_cl,
        "ALTITUDINE": "100",
        "POP21": "1000",
        "FAM21": "400",
        "ABI21": "800",
        "EDI21": "300",
        "POINT_X": point_x,
        "POINT_Y": point_y,
    }


def _localities_zip_bytes(rows: list[dict[str, str]]) -> bytes:
    text = StringIO(newline="")
    writer = csv.DictWriter(
        text,
        fieldnames=LOCALITY_HEADERS,
        delimiter="\t",
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "official/Localita_2021_Point.csv",
            text.getvalue().encode("cp1252"),
        )
    return output.getvalue()


def _registry_rows() -> list[dict[str, str]]:
    return [
        {"E": "000001", "F": "Comune Diretto", "P": "000001", "Q": "000001"},
        {"E": "000002", "F": "Comune Corrente", "P": "000002", "Q": "000009"},
        {
            "E": "005122",
            "F": "Moransengo-Tonengo",
            "P": "005122",
            "Q": "005122",
        },
    ]


def _locality_rows() -> list[dict[str, str]]:
    return [
        # This is a locality, but not the selected municipal centre.
        _locality_row(
            "000001",
            "100100099",
            "Frazione da ignorare",
            "499999,00",
            "4999999,00",
            centro_cl="0",
        ),
        _locality_row(
            "000001",
            "100100001",
            "Città Diretta",
            "500000,25",
            "5000000,75",
        ),
        # TIPO_LOC=2 is intentional: CENTRO_CL, not TIPO_LOC, selects a seat.
        _locality_row(
            "000009",
            "900100001",
            "Città Storica",
            "510000,50",
            "5010000,50",
            tipo_loc="2",
        ),
        _locality_row(
            "005110",
            "511010001",
            "Tonengo",
            "520000,00",
            "5020000,00",
        ),
    ]


def _three_municipality_catalog() -> dict:
    return _catalog(
        ("000001", "Comune Diretto"),
        ("000002", "Comune Corrente"),
        ("005122", "Moransengo-Tonengo"),
    )


def _square_geometry(easting: float, northing: float, half_size: float = 100.0):
    ring = (
        (easting - half_size, northing - half_size),
        (easting + half_size, northing - half_size),
        (easting + half_size, northing + half_size),
        (easting - half_size, northing + half_size),
        (easting - half_size, northing - half_size),
    )
    return SimpleNamespace(rings=(ring,))


def _boundary_geometries():
    return {
        "000001": _square_geometry(500000.25, 5000000.75),
        "000002": _square_geometry(510000.5, 5010000.5),
        "005122": _square_geometry(520000.0, 5020000.0),
    }


def _boundaries_zip_bytes() -> bytes:
    """Opaque reviewed boundary snapshot; geometry decoding is injected in IO tests."""

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("fixture/README.txt", b"synthetic boundary snapshot")
    return output.getvalue()


class RecordingTransformer:
    """A pyproj-compatible injected transform with deterministic WGS84 output."""

    OUTPUTS = {
        (500000.25, 5000000.75): (8.1000001, 45.1000001),
        (510000.5, 5010000.5): (8.2000002, 45.2000002),
        (520000.0, 5020000.0): (8.3000003, 45.3000003),
    }

    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def transform(self, easting: float, northing: float) -> tuple[float, float]:
        key = (easting, northing)
        self.calls.append(key)
        return self.OUTPUTS[key]  # longitude, latitude (`always_xy=True`)


def _resolved_fixture_document() -> dict:
    return resolver.resolve_istat_capoluogo_points(
        _three_municipality_catalog(),
        resolver.parse_registry_xlsx_bytes(_xlsx_bytes(_registry_rows())),
        resolver.parse_coordinate_zip_bytes(_localities_zip_bytes(_locality_rows())),
        boundary_geometries=_boundary_geometries(),
        transformer=RecordingTransformer(),
        pyproj_version="test-pyproj",
        proj_version="test-proj",
        expected_count=3,
    )


class IstatCapoluogoPointResolverTests(unittest.TestCase):
    def test_parsers_resolve_direct_legacy_and_reviewed_override_deterministically(self):
        registry = resolver.parse_registry_xlsx_bytes(_xlsx_bytes(_registry_rows()))
        localities = resolver.parse_coordinate_zip_bytes(
            _localities_zip_bytes(_locality_rows())
        )
        transformer = RecordingTransformer()

        document = resolver.resolve_istat_capoluogo_points(
            _three_municipality_catalog(),
            registry,
            localities,
            boundary_geometries=_boundary_geometries(),
            transformer=transformer,
            pyproj_version="test-pyproj",
            proj_version="test-proj",
            expected_count=3,
        )

        records = document["records"]
        self.assertEqual(
            [record["istat_code"] for record in records],
            ["000001", "000002", "005122"],
        )
        self.assertEqual(
            [record["evidence"]["mapping_method"] for record in records],
            [
                "direct_current_istat_code_v1",
                "registry_2017_2025_code_v1",
                "reviewed_post_2021_seat_override_v1",
            ],
        )
        self.assertEqual(
            [record["evidence"]["source_istat_code"] for record in records],
            ["000001", "000009", "005110"],
        )
        self.assertEqual(
            [record["evidence"]["loc_id"] for record in records],
            ["100100001", "900100001", "511010001"],
        )
        self.assertEqual(records[1]["evidence"]["source_locality_type"], "2")
        self.assertEqual(records[1]["evidence"]["selection_field"], "CENTRO_CL")
        self.assertEqual(records[1]["evidence"]["selection_value"], "1")
        self.assertEqual(records[0]["evidence"]["source_locality_name"], "Città Diretta")
        self.assertEqual(
            transformer.calls,
            [
                (500000.25, 5000000.75),
                (510000.5, 5010000.5),
                (520000.0, 5020000.0),
            ],
        )
        self.assertEqual(
            document["summary"]["mapping_method_counts"],
            {
                "direct_current_istat_code_v1": 1,
                "registry_2017_2025_code_v1": 1,
                "reviewed_post_2021_seat_override_v1": 1,
            },
        )

        forecast_points = resolver.forecast_point_records(document)
        self.assertEqual(len(forecast_points), 3)
        self.assertEqual(
            set(forecast_points[0]),
            {"istat_code", "latitude", "longitude", "method", "quality", "source"},
        )
        self.assertEqual(
            {point["quality"] for point in forecast_points},
            {"official_istat_capoluogo"},
        )
        self.assertEqual(
            {point["method"] for point in forecast_points},
            {"official_istat_capoluogo_v1"},
        )
        self.assertEqual(
            [point["source"]["loc_id"] for point in forecast_points],
            ["100100001", "900100001", "511010001"],
        )
        self.assertNotIn("record_id", forecast_points[0]["source"])
        self.assertEqual(
            (forecast_points[1]["longitude"], forecast_points[1]["latitude"]),
            (8.2000002, 45.2000002),
        )

    def test_duplicate_registry_identity_and_duplicate_selected_centre_fail_closed(self):
        duplicate_registry = _registry_rows() + [dict(_registry_rows()[0])]
        with self.assertRaisesRegex(
            resolver.IstatCapoluogoResolutionError, "duplicate"
        ):
            resolver.parse_registry_xlsx_bytes(_xlsx_bytes(duplicate_registry))

        localities = _locality_rows()
        localities.append(
            _locality_row(
                "000001",
                "100100002",
                "Secondo centro ambiguo",
                "500001,00",
                "5000001,00",
            )
        )
        with self.assertRaisesRegex(
            resolver.IstatCapoluogoResolutionError, "duplicate|ambiguous"
        ):
            resolver.resolve_istat_capoluogo_points(
                _three_municipality_catalog(),
                resolver.parse_registry_xlsx_bytes(_xlsx_bytes(_registry_rows())),
                resolver.parse_coordinate_zip_bytes(
                    _localities_zip_bytes(localities)
                ),
                boundary_geometries=_boundary_geometries(),
                transformer=RecordingTransformer(),
                pyproj_version="test-pyproj",
                proj_version="test-proj",
                expected_count=3,
            )

    def test_missing_centre_and_unknown_unreviewed_mapping_are_rejected(self):
        localities = [
            row
            for row in _locality_rows()
            if row["PRO_COM"] not in {"000009", "005110"}
        ]
        with self.assertRaisesRegex(
            resolver.IstatCapoluogoResolutionError,
            "missing|unresolved|no reviewed ISTAT capoluogo mapping",
        ):
            resolver.resolve_istat_capoluogo_points(
                _three_municipality_catalog(),
                resolver.parse_registry_xlsx_bytes(_xlsx_bytes(_registry_rows())),
                resolver.parse_coordinate_zip_bytes(
                    _localities_zip_bytes(localities)
                ),
                boundary_geometries=_boundary_geometries(),
                transformer=RecordingTransformer(),
                pyproj_version="test-pyproj",
                proj_version="test-proj",
                expected_count=3,
            )

    def test_bounds_and_transformer_errors_fail_closed(self):
        registry = resolver.parse_registry_xlsx_bytes(
            _xlsx_bytes([_registry_rows()[0]])
        )
        localities = resolver.parse_coordinate_zip_bytes(
            _localities_zip_bytes([_locality_rows()[1]])
        )
        catalog = _catalog(("000001", "Comune Diretto"))

        class OutsideItaly:
            def transform(self, _easting, _northing):
                return 8.0, 34.9999999

        with self.assertRaisesRegex(
            resolver.IstatCapoluogoResolutionError, "bound|Italy|latitude"
        ):
            resolver.resolve_istat_capoluogo_points(
                catalog,
                registry,
                localities,
                boundary_geometries={
                    "000001": _square_geometry(500000.25, 5000000.75)
                },
                transformer=OutsideItaly(),
                pyproj_version="test-pyproj",
                proj_version="test-proj",
                expected_count=1,
            )

        class BrokenTransformer:
            def transform(self, _easting, _northing):
                raise RuntimeError("synthetic transformer failure")

        with self.assertRaisesRegex(
            resolver.IstatCapoluogoResolutionError, "transform"
        ):
            resolver.resolve_istat_capoluogo_points(
                catalog,
                registry,
                localities,
                boundary_geometries={
                    "000001": _square_geometry(500000.25, 5000000.75)
                },
                transformer=BrokenTransformer(),
                pyproj_version="test-pyproj",
                proj_version="test-proj",
                expected_count=1,
            )

    def test_source_capoluogo_must_lie_inside_current_municipality_boundary(self):
        registry = resolver.parse_registry_xlsx_bytes(
            _xlsx_bytes([_registry_rows()[0]])
        )
        localities = resolver.parse_coordinate_zip_bytes(
            _localities_zip_bytes([_locality_rows()[1]])
        )

        with self.assertRaisesRegex(
            resolver.IstatCapoluogoResolutionError,
            "outside.*municipality|outside.*boundar|boundary.*contain|containment",
        ):
            resolver.resolve_istat_capoluogo_points(
                _catalog(("000001", "Comune Diretto")),
                registry,
                localities,
                boundary_geometries={
                    "000001": _square_geometry(700000.0, 5300000.0)
                },
                transformer=RecordingTransformer(),
                pyproj_version="test-pyproj",
                proj_version="test-proj",
                expected_count=1,
            )

    def test_build_from_paths_binds_exact_source_hashes(self):
        catalog = _three_municipality_catalog()
        registry_raw = _xlsx_bytes(_registry_rows())
        localities_raw = _localities_zip_bytes(_locality_rows())
        boundaries_raw = _boundaries_zip_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "catalog.json"
            registry_path = root / "registry.xlsx"
            localities_path = root / "localities.zip"
            boundaries_path = root / "boundaries.zip"
            catalog_path.write_bytes(_canonical_json_bytes(catalog) + b"\n")
            registry_path.write_bytes(registry_raw)
            localities_path.write_bytes(localities_raw)
            boundaries_path.write_bytes(boundaries_raw)

            with patch.object(
                resolver,
                "read_boundary_geometry_zip",
                return_value=_boundary_geometries(),
            ):
                document = resolver.build_from_paths(
                    catalog_path,
                    registry_path,
                    localities_path,
                    boundaries_path,
                    transformer=RecordingTransformer(),
                    pyproj_version="test-pyproj",
                    proj_version="test-proj",
                    expected_count=3,
                    expected_registry_sha256=_sha256(registry_raw),
                    expected_localities_sha256=_sha256(localities_raw),
                    expected_boundaries_sha256=_sha256(boundaries_raw),
                    enforce_official_distribution=False,
                    expected_total_locality_rows=4,
                    expected_capoluogo_rows=3,
                )

        self.assertEqual(document["municipality_count"], 3)
        self.assertEqual(document["catalog_sha256"], catalog["catalog_sha256"])
        self.assertEqual(
            document["source_manifest"]["current_registry"]["sha256"],
            _sha256(registry_raw),
        )
        self.assertEqual(
            document["source_manifest"]["localities"]["sha256"],
            _sha256(localities_raw),
        )
        self.assertEqual(
            document["source_manifest"]["municipality_boundaries"]["sha256"],
            _sha256(boundaries_raw),
        )

    def test_build_from_paths_rejects_hash_mismatch_before_parsing_or_transforming(self):
        catalog = _three_municipality_catalog()
        registry_raw = _xlsx_bytes(_registry_rows())
        localities_raw = _localities_zip_bytes(_locality_rows())
        boundaries_raw = _boundaries_zip_bytes()

        class ForbiddenTransformer:
            def transform(self, _easting, _northing):  # pragma: no cover
                raise AssertionError("transformer must not run after a hash mismatch")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "catalog.json"
            registry_path = root / "registry.xlsx"
            localities_path = root / "localities.zip"
            boundaries_path = root / "boundaries.zip"
            catalog_path.write_bytes(_canonical_json_bytes(catalog))
            registry_path.write_bytes(registry_raw)
            localities_path.write_bytes(localities_raw)
            boundaries_path.write_bytes(boundaries_raw)

            with self.assertRaisesRegex(
                resolver.IstatCapoluogoResolutionError,
                "registry.*SHA-256",
            ):
                resolver.build_from_paths(
                    catalog_path,
                    registry_path,
                    localities_path,
                    boundaries_path,
                    transformer=ForbiddenTransformer(),
                    pyproj_version="test-pyproj",
                    proj_version="test-proj",
                    expected_count=3,
                    expected_registry_sha256="0" * 64,
                    expected_localities_sha256=_sha256(localities_raw),
                    expected_boundaries_sha256=_sha256(boundaries_raw),
                )

            with self.assertRaisesRegex(
                resolver.IstatCapoluogoResolutionError,
                "boundary.*SHA-256",
            ):
                resolver.build_from_paths(
                    catalog_path,
                    registry_path,
                    localities_path,
                    boundaries_path,
                    transformer=ForbiddenTransformer(),
                    pyproj_version="test-pyproj",
                    proj_version="test-proj",
                    expected_count=3,
                    expected_registry_sha256=_sha256(registry_raw),
                    expected_localities_sha256=_sha256(localities_raw),
                    expected_boundaries_sha256="0" * 64,
                )

    def test_resolution_document_create_only_round_trip_never_overwrites(self):
        document = _resolved_fixture_document()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "resolution.json"

            resolver.write_resolution_create_only(output, document)

            written = output.read_bytes()
            self.assertEqual(written, resolver.resolution_json_bytes(document))
            self.assertEqual(resolver.load_resolution_document(output), document)
            with self.assertRaisesRegex(
                resolver.IstatCapoluogoResolutionError, "create-only"
            ):
                resolver.write_resolution_create_only(output, document)
            self.assertEqual(output.read_bytes(), written)

    def test_resolved_records_build_an_approved_forecast_point_artifact(self):
        catalog = _three_municipality_catalog()
        document = _resolved_fixture_document()

        artifact = forecast_points.build_approved_forecast_points_artifact(
            catalog=catalog,
            points=resolver.forecast_point_records(document),
            boundary_sha256=document["source_manifest"][
                "municipality_boundaries"
            ]["sha256"],
            source_manifest_sha256=document["source_manifest_sha256"],
            resolution_policy_sha256=document["resolution_policy_sha256"],
        )

        forecast_points.validate_forecast_points_artifact(
            artifact, catalog=catalog
        )
        self.assertEqual(artifact["status"], forecast_points.APPROVED_POINTS_STATUS)
        self.assertEqual(artifact["point_count"], 3)
        self.assertEqual(
            artifact["quality_counts"][
                forecast_points.QUALITY_OFFICIAL_ISTAT_CAPOLUOGO
            ],
            3,
        )
        self.assertEqual(
            [point["source"]["loc_id"] for point in artifact["points"]],
            ["100100001", "900100001", "511010001"],
        )


if __name__ == "__main__":
    unittest.main()
