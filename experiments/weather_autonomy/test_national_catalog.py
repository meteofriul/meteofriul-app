from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from experiments.weather_autonomy.national_catalog import (
    BOUNDARIES_SOURCE_SHA256,
    EXPECTED_MUNICIPALITY_COUNT,
    NationalCatalogError,
    REGISTRY_SOURCE_SHA256,
    RegistryMunicipality,
    _interior_point,
    _point_in_polygon,
    _utm32n_to_wgs84,
    audit_source_alignment,
    canonical_json_bytes,
    validate_catalog,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "backend" / "app" / "data" / "italy_municipalities_2026.json"


class NationalCatalogTests(unittest.TestCase):
    def test_checked_in_catalog_is_complete_and_self_verifying(self):
        document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

        validate_catalog(document)

        self.assertEqual(document["municipality_count"], EXPECTED_MUNICIPALITY_COUNT)
        expected_codes_hash = hashlib.sha256(
            json.dumps(
                sorted(item["istat_code"] for item in document["municipalities"]),
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(document["municipality_codes_sha256"], expected_codes_hash)
        self.assertEqual(
            document["sources"]["registry"]["sha256"], REGISTRY_SOURCE_SHA256
        )
        self.assertEqual(
            document["sources"]["boundaries"]["sha256"],
            BOUNDARIES_SOURCE_SHA256,
        )
        by_name = {item["name"]: item for item in document["municipalities"]}
        self.assertEqual(by_name["Urbino"]["istat_code"], "041067")
        self.assertEqual(by_name["Urbino"]["region_iso"], "IT-57")
        self.assertEqual(
            by_name["Castegnero Nanto"]["representative_point"]["source_boundary_codes"],
            ["024027", "024071"],
        )
        self.assertEqual(
            by_name["Montalto Pavese"]["representative_point"]["source_boundary_codes"],
            ["018094", "018082"],
        )

    def test_catalog_hash_rejects_tampering(self):
        document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        document["municipalities"][0]["name"] = "Alterato"

        with self.assertRaisesRegex(NationalCatalogError, "hash"):
            validate_catalog(document)

    def test_semantic_validation_rejects_self_consistent_wrong_region(self):
        document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        document["municipalities"][0]["region_iso"] = "IT-99"
        content = dict(document)
        content.pop("catalog_sha256")
        document["catalog_sha256"] = hashlib.sha256(
            canonical_json_bytes(content)
        ).hexdigest()

        with self.assertRaisesRegex(NationalCatalogError, "identity"):
            validate_catalog(document)

    def test_inverse_utm32_is_stable_on_the_central_meridian(self):
        latitude, longitude = _utm32n_to_wgs84(500_000.0, 4_649_776.22482)

        self.assertAlmostEqual(latitude, 42.0, places=5)
        self.assertAlmostEqual(longitude, 9.0, places=7)

    def test_interior_point_avoids_a_polygon_hole(self):
        exterior = ((0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0), (0.0, 0.0))
        hole = ((4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0), (4.0, 4.0))

        x, y, area = _interior_point((exterior, hole))

        self.assertTrue(_point_in_polygon(x, y, (exterior, hole)))
        self.assertGreater(area, 0)
        self.assertFalse(4.0 < x < 6.0 and 4.0 < y < 6.0)

    def test_source_alignment_exposes_only_explicit_identity_changes(self):
        base = RegistryMunicipality(
            istat_code="024129",
            name="Castegnero Nanto",
            italian_name="Castegnero Nanto",
            alternate_name="",
            region_istat="05",
            region_iso="IT-34",
            region_name="Veneto",
            uts_istat="024",
            province_historical_istat="024",
            uts_name="Vicenza",
            province_abbreviation="VI",
            cadastral_code="M439",
        )
        registry = (base, replace(base, istat_code="041067", name="Urbino", italian_name="Urbino"))
        boundaries = (
            {"istat_code": "024027", "name": "Castegnero"},
            {"istat_code": "024071", "name": "Nanto"},
            {"istat_code": "041067", "name": "Urbino"},
        )

        result = audit_source_alignment(registry, boundaries)

        self.assertEqual(
            [item["istat_code"] for item in result["missing_boundaries"]],
            ["024129"],
        )
        self.assertEqual(
            [item["istat_code"] for item in result["retired_boundaries"]],
            ["024027", "024071"],
        )
        self.assertEqual(result["name_mismatches"], [])


if __name__ == "__main__":
    unittest.main()
