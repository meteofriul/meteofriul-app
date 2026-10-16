import json
import tempfile
import unittest
from pathlib import Path

from app.services.fvg_geography import FvgGeographyCatalog


class FvgGeographyCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = FvgGeographyCatalog()

    def test_catalog_contains_complete_versioned_offline_sources(self):
        self.assertEqual(len(self.catalog.boundaries), 215)
        self.assertEqual(len(self.catalog.localities), 2397)
        self.assertEqual(self.catalog.municipality_dataset_version, "2026-01-01")
        self.assertEqual(self.catalog.locality_dataset_version, "2006")
        self.assertEqual(
            self.catalog.sources["municipalities"]["license"],
            "CC BY 4.0",
        )
        self.assertEqual(
            self.catalog.sources["localities"]["license"],
            "IODL 2.0",
        )
        self.assertRegex(
            self.catalog.sources["municipalities"]["sha256"],
            r"^[0-9a-f]{64}$",
        )
        self.assertRegex(
            self.catalog.sources["localities"]["sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_point_in_polygon_resolves_required_municipalities(self):
        cases = (
            (45.9892108, 12.5473156, "093022"),  # Vigonovo / Fontanafredda
            (46.2479446, 12.4703415, "093015"),  # Cellino di Sopra / Claut
            (46.1440410, 12.6372055, "093027"),  # Malnisio / Montereale
            (46.1507328, 12.6490079, "093027"),  # Grizzo / Montereale
        )
        for latitude, longitude, expected_istat in cases:
            with self.subTest(latitude=latitude, longitude=longitude):
                self.assertEqual(
                    self.catalog.resolve_municipality_istat(latitude, longitude),
                    expected_istat,
                )

    def test_locality_requires_irdat_name_corroboration_in_same_municipality(self):
        cases = (
            (
                "093022",
                ("Talmasson", "Vigonovo", "Fontanafredda"),
                45.9892108,
                12.5473156,
                "Vigonovo",
            ),
            (
                "093015",
                ("Cellino di Sopra", "Pinedo"),
                46.2479446,
                12.4703415,
                "Cellino di Sopra",
            ),
            (
                "093027",
                ("Cao Malnisio", "Malnisio"),
                46.1440410,
                12.6372055,
                "Malnisio",
            ),
            (
                "093027",
                ("Borgo Alzetta", "Grizzo"),
                46.1507328,
                12.6490079,
                "Grizzo",
            ),
        )
        for municipality, candidates, latitude, longitude, expected_name in cases:
            with self.subTest(expected_name=expected_name):
                locality = self.catalog.resolve_locality(
                    municipality_istat=municipality,
                    candidate_names=candidates,
                    latitude=latitude,
                    longitude=longitude,
                )
                self.assertIsNotNone(locality)
                self.assertEqual(locality.name, expected_name)
                self.assertEqual(locality.municipality_istat, municipality)
                self.assertEqual(
                    locality.to_public_dict(),
                    {
                        "id": locality.id,
                        "name": expected_name,
                        "kind": locality.kind,
                        "source": "rafvg_irdat_5000",
                        "datasetVersion": "2006",
                    },
                )

        self.assertIsNone(
            self.catalog.resolve_locality(
                municipality_istat="093015",
                candidate_names=("Vigonovo",),
                latitude=46.2479446,
                longitude=12.4703415,
            )
        )

    def test_parent_municipality_name_does_not_replace_vigonovo(self):
        self.assertIsNone(
            self.catalog.resolve_locality(
                municipality_istat="093022",
                candidate_names=("Fontanafredda",),
                latitude=45.9892108,
                longitude=12.5473156,
            )
        )

    def test_structured_name_match_reports_distance_and_distinct_runner_up(self):
        result = self.catalog.resolve_locality_resolution(
            municipality_istat="093022",
            candidate_names=("Talmasson", "Vigonovo", "Vinuf"),
            latitude=45.9892108,
            longitude=12.5473156,
            allow_nearest=True,
            nearest_accuracy_m=20,
        )

        self.assertIsNotNone(result.locality)
        self.assertEqual(result.locality.name, "Vigonovo")
        self.assertEqual(result.match_method, "name")
        self.assertAlmostEqual(result.distance_m, 99.5, places=1)
        self.assertAlmostEqual(result.runner_up_distance_m, 396.8, places=1)

    def test_structured_nearest_cellino_requires_accuracy_and_runner_up_gap(self):
        precise = self.catalog.resolve_locality_resolution(
            municipality_istat="093015",
            candidate_names=(),
            latitude=46.2479446,
            longitude=12.4703415,
            allow_nearest=True,
            nearest_accuracy_m=30,
        )
        ambiguous = self.catalog.resolve_locality_resolution(
            municipality_istat="093015",
            candidate_names=(),
            latitude=46.2479446,
            longitude=12.4703415,
            allow_nearest=True,
            nearest_accuracy_m=32,
        )
        missing_accuracy = self.catalog.resolve_locality_resolution(
            municipality_istat="093015",
            candidate_names=(),
            latitude=46.2479446,
            longitude=12.4703415,
            allow_nearest=True,
        )

        self.assertIsNotNone(precise.locality)
        self.assertEqual(precise.locality.name, "Cellino di Sopra")
        self.assertEqual(precise.match_method, "nearest")
        self.assertAlmostEqual(precise.distance_m, 55.8, places=1)
        self.assertAlmostEqual(precise.runner_up_distance_m, 138.3, places=1)
        self.assertIsNone(ambiguous.locality)
        self.assertIsNone(missing_accuracy.locality)

    def test_explicit_uncorroborated_name_never_falls_through_to_nearest(self):
        result = self.catalog.resolve_locality_resolution(
            municipality_istat="093015",
            candidate_names=("Nome esterno al catalogo",),
            latitude=46.2479446,
            longitude=12.4703415,
            allow_nearest=True,
            nearest_accuracy_m=1,
        )

        self.assertIsNone(result.locality)
        self.assertIsNone(result.match_method)

    def test_nearest_distance_gate_includes_accuracy_and_safety_margin(self):
        accepted = self.catalog.resolve_locality_resolution(
            municipality_istat="093027",
            candidate_names=(),
            latitude=46.1440410,
            longitude=12.6372055,
            allow_nearest=True,
            nearest_accuracy_m=49,
        )
        rejected = self.catalog.resolve_locality_resolution(
            municipality_istat="093027",
            candidate_names=(),
            latitude=46.1440410,
            longitude=12.6372055,
            allow_nearest=True,
            nearest_accuracy_m=50,
        )

        self.assertEqual(accepted.locality.name, "Malnisio")
        self.assertIsNone(rejected.locality)

    def test_nearest_fails_closed_without_a_distinct_named_runner_up(self):
        result = self.catalog.resolve_locality_resolution(
            municipality_istat="030002",
            candidate_names=(),
            latitude=46.377287,
            longitude=13.097227,
            allow_nearest=True,
            nearest_accuracy_m=0,
        )

        self.assertIsNone(result.locality)
        self.assertIsNone(result.runner_up_distance_m)

    def test_boundary_distance_is_positive_only_inside_matching_municipality(self):
        distance = self.catalog.municipality_boundary_distance_m(
            municipality_istat="093022",
            latitude=45.9892108,
            longitude=12.5473156,
        )

        self.assertIsNotNone(distance)
        self.assertGreater(distance, 250)
        self.assertIsNone(
            self.catalog.municipality_boundary_distance_m(
                municipality_istat="093015",
                latitude=45.9892108,
                longitude=12.5473156,
            )
        )

    def test_shared_boundary_is_ambiguous_and_fails_closed(self):
        payload = {
            "schemaVersion": "fvg-geography.v1",
            "sources": {
                "municipalities": {"validAt": "2026-01-01"},
                "localities": {"edition": "2006"},
            },
            "municipalityCount": 2,
            "localityCount": 0,
            "municipalities": [
                {
                    "istatCode": "000001",
                    "name": "First",
                    "bbox": [0, 0, 1, 1],
                    "polygons": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]],
                },
                {
                    "istatCode": "000002",
                    "name": "Second",
                    "bbox": [1, 0, 2, 1],
                    "polygons": [[[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]]],
                },
            ],
            "localities": [],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "geography.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            catalog = FvgGeographyCatalog(path)

        self.assertIsNone(catalog.resolve_municipality_istat(0.5, 1.0))


if __name__ == "__main__":
    unittest.main()
