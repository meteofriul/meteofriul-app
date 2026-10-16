import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.services.national_municipalities import (
    NATIONAL_MUNICIPALITY_CATALOG_KIND,
    NationalMunicipalityCatalog,
    NationalMunicipalityCatalogError,
    get_default_national_municipality_catalog,
)


def _canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _write_catalog(path, records):
    codes = sorted(record["istat_code"] for record in records)
    payload = {
        "kind": NATIONAL_MUNICIPALITY_CATALOG_KIND,
        "schema_version": 1,
        "catalog_version": "test-catalog-v1",
        "effective_at": "2026-01-01",
        "municipality_count": len(records),
        "municipality_codes_sha256": hashlib.sha256(
            _canonical_bytes(codes)
        ).hexdigest(),
        "municipalities": records,
    }
    payload["catalog_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    path.write_bytes(_canonical_bytes(payload) + b"\n")


def _record(istat, name, province_code, province_name):
    record = {
        "istat_code": istat,
        "name": name,
        "italian_name": name,
        "alternate_name": "",
        "province_abbreviation": province_code,
        "uts_name": province_name,
        "region_name": "Regione test",
        "region_iso": "IT-00",
        "representative_point": {"latitude": 42.0, "longitude": 12.0},
    }
    return record


class NationalMunicipalityCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = get_default_national_municipality_catalog()

    def test_checked_in_catalog_is_lazy_complete_and_cached(self):
        first = get_default_national_municipality_catalog()
        second = get_default_national_municipality_catalog()
        self.assertIs(first, second)
        self.assertEqual(len(first.municipalities), 7_894)
        self.assertTrue(first.is_loaded)

    def test_exact_istat_lookup_exposes_identity_and_representative_point(self):
        urbino = self.catalog.match_istat("041067")
        self.assertIsNotNone(urbino)
        self.assertEqual(urbino.name, "Urbino")
        self.assertEqual(urbino.province_code, "PU")
        self.assertEqual(urbino.province_name, "Pesaro e Urbino")
        self.assertEqual(urbino.region_name, "Marche")
        self.assertEqual(urbino.representative_coordinates, (43.739727, 12.6241909))
        self.assertIsNone(self.catalog.match_istat("41067"))
        self.assertEqual(
            self.catalog.catalog_version,
            "istat-2026-02-21-boundaries-2026-01-01-v1",
        )
        self.assertRegex(self.catalog.catalog_sha256, r"^[0-9a-f]{64}$")
        self.assertRegex(
            self.catalog.municipality_codes_sha256, r"^[0-9a-f]{64}$"
        )
        self.assertEqual(self.catalog.effective_at, "2026-02-21")

    def test_normalized_exact_name_and_province_code_or_name(self):
        by_code = self.catalog.match_name("  SÀMONE ", province="to")
        by_name = self.catalog.match_name("Samone", province="Torino")
        self.assertIsNotNone(by_code)
        self.assertEqual(by_code.istat_code, "001235")
        self.assertEqual(by_name, by_code)

    def test_shared_name_fails_closed_without_disambiguating_province(self):
        self.assertIsNone(self.catalog.match_name("Samone"))
        self.assertIsNone(self.catalog.match_name("Samone", province="XX"))
        trentino = self.catalog.match_name("Samone", province="Trento")
        self.assertIsNotNone(trentino)
        self.assertEqual(trentino.istat_code, "022165")

    def test_matching_remains_exact_not_fuzzy(self):
        self.assertIsNone(self.catalog.match_name("Urbin", province="PU"))
        self.assertEqual(
            self.catalog.match_name("Urbino", province="Pesaro e Urbino").istat_code,
            "041067",
        )

    def test_corrupt_catalog_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            _write_catalog(path, [_record("001001", "Comune test", "TT", "Test")])
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["municipalities"][0]["name"] = "Alterato"
            path.write_text(json.dumps(payload), encoding="utf-8")

            catalog = NationalMunicipalityCatalog(path, expected_count=1)
            with self.assertRaisesRegex(NationalMunicipalityCatalogError, "hash"):
                catalog.match_istat("001001")

    def test_custom_catalog_can_pin_its_release_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            records = [_record("001001", "Comune test", "TT", "Test")]
            _write_catalog(path, records)
            payload = json.loads(path.read_text(encoding="utf-8"))

            catalog = NationalMunicipalityCatalog(
                path,
                expected_count=1,
                expected_version="test-catalog-v1",
                expected_sha256=payload["catalog_sha256"],
                expected_codes_sha256=payload["municipality_codes_sha256"],
            )

            self.assertEqual(catalog.match_istat("001001").name, "Comune test")

    def test_construction_does_not_read_the_catalog(self):
        missing = Path(tempfile.gettempdir()) / "definitely-missing-meteofriul-catalog.json"
        catalog = NationalMunicipalityCatalog(missing, expected_count=1)
        self.assertFalse(catalog.is_loaded)
        with self.assertRaisesRegex(NationalMunicipalityCatalogError, "cannot be loaded"):
            catalog.match_istat("001001")


if __name__ == "__main__":
    unittest.main()
