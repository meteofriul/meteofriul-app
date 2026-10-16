import json
import tempfile
import unittest
from pathlib import Path

from app.services.official_alert_zone_catalog import (
    ALERT_ZONE_CATALOG_SHA256,
    FVG_ZONE_IDS,
    OfficialAlertZoneCatalog,
    OfficialAlertZoneCatalogError,
    get_default_official_alert_zone_catalog,
)


class OfficialAlertZoneCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = get_default_official_alert_zone_catalog()

    def test_default_catalog_is_complete_pinned_and_cached(self):
        self.assertIs(
            get_default_official_alert_zone_catalog(),
            get_default_official_alert_zone_catalog(),
        )
        self.assertEqual(self.catalog.catalog_sha256, ALERT_ZONE_CATALOG_SHA256)
        self.assertEqual(self.catalog.source_revision, "20260924_1434")
        self.assertEqual(len(self.catalog.zones), 187)
        self.assertEqual(self.catalog.multi_zone_municipality_count, 2814)

    def test_fvg_reference_municipalities_keep_the_expected_zones(self):
        expected = {
            "093033": ("FVG-A",),  # Pordenone
            "093018": ("FVG-A",),  # Erto e Casso
            "030040": ("FVG-B",),  # Forni Avoltri
            "030129": ("FVG-C",),  # Udine
            "031007": ("FVG-C",),  # Gorizia
            "032006": ("FVG-D",),  # Trieste
        }
        for istat_code, zones in expected.items():
            with self.subTest(istat_code=istat_code):
                mapping = self.catalog.match_istat(istat_code)
                self.assertIsNotNone(mapping)
                self.assertEqual(mapping.zone_ids, zones)
                self.assertTrue(set(mapping.zone_ids).issubset(FVG_ZONE_IDS))

    def test_multi_zone_municipality_preserves_every_intersection(self):
        mapping = self.catalog.match_istat("030006")
        self.assertEqual(mapping.zone_ids, ("FVG-B", "FVG-C"))
        self.assertEqual(mapping.representative_point_zone_id, "FVG-C")

    def test_national_reference_municipalities_are_resolved_by_istat(self):
        for istat_code in ("041067", "058091", "082053"):
            with self.subTest(istat_code=istat_code):
                mapping = self.catalog.match_istat(istat_code)
                self.assertIsNotNone(mapping)
                self.assertTrue(mapping.zone_ids)
                self.assertTrue(
                    all(zone_id.startswith("DPC:") for zone_id in mapping.zone_ids)
                )
        self.assertIsNone(self.catalog.match_istat("58091"))

    def test_tampered_catalog_fails_closed(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "data"
            / "official_alert_zone_catalog.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zones.json"
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["mappings"][0]["zone_ids"] = ["DPC:invented"]
            target.write_text(json.dumps(payload), encoding="utf-8")
            catalog = OfficialAlertZoneCatalog(target)
            with self.assertRaisesRegex(OfficialAlertZoneCatalogError, "hash"):
                catalog.match_istat("001001")

    def test_construction_is_lazy_and_missing_catalog_fails_closed(self):
        missing = Path(tempfile.gettempdir()) / "missing-alert-zone-catalog.json"
        catalog = OfficialAlertZoneCatalog(missing)
        self.assertFalse(catalog.is_loaded)
        with self.assertRaisesRegex(OfficialAlertZoneCatalogError, "cannot be loaded"):
            catalog.match_istat("001001")


if __name__ == "__main__":
    unittest.main()
