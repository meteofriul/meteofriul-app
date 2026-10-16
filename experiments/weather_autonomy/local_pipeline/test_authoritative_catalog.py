"""Offline tests for the ISTAT/IRDAT authoritative representative-point audit."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest

from local_pipeline.authoritative_catalog import (
    AuthoritativeCatalogError,
    DEFAULT_GEOGRAPHY_PATH,
    DEFAULT_MUNICIPALITY_PATH,
    build_authoritative_catalog,
    deterministic_point_on_surface,
    load_authoritative_catalog,
    normalize_municipality_name,
    point_in_polygons,
    verify_catalog_hash,
)


def sources():
    return (
        json.loads(Path(DEFAULT_GEOGRAPHY_PATH).read_text(encoding="utf-8")),
        json.loads(Path(DEFAULT_MUNICIPALITY_PATH).read_text(encoding="utf-8")),
    )


class ForbiddenLegacyCoordinates(dict):
    """Fail immediately if a builder attempts to read old point coordinates."""

    def get(self, key, default=None):
        if key in {"latitude", "longitude"}:
            raise AssertionError("legacy municipality coordinate was read")
        return super().get(key, default)

    def __getitem__(self, key):
        if key in {"latitude", "longitude"}:
            raise AssertionError("legacy municipality coordinate was read")
        return super().__getitem__(key)


class RealCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geography, cls.metadata = sources()
        cls.document = build_authoritative_catalog(cls.geography, cls.metadata)

    def test_real_product_has_215_unique_istat_records_and_stable_hash(self):
        records = self.document["municipalities"]
        self.assertEqual(self.document["municipality_count"], 215)
        self.assertEqual(len(records), 215)
        self.assertEqual(len({record["istat_code"] for record in records}), 215)
        self.assertEqual([record["istat_code"] for record in records], sorted(record["istat_code"] for record in records))
        self.assertTrue(verify_catalog_hash(self.document))
        self.assertEqual(self.document, load_authoritative_catalog())

    def test_policy_uses_seat_then_exact_name_then_polygon_fallback(self):
        counts = Counter(record["representative_point"]["method"] for record in self.document["municipalities"])
        self.assertEqual(
            counts,
            {
                "irdat_unique_municipal_seat": 27,
                "irdat_unique_normalized_municipality_name": 177,
                "istat_deterministic_point_on_surface": 11,
            },
        )
        self.assertEqual(self.document["method_counts"], dict(sorted(counts.items())))
        self.assertFalse(self.document["policy"]["legacy_coordinate_fields_consumed"])

    def test_every_representative_point_is_inside_its_istat_polygon(self):
        polygons = {item["istatCode"]: item["polygons"] for item in self.geography["municipalities"]}
        for record in self.document["municipalities"]:
            point = record["representative_point"]
            with self.subTest(istat=record["istat_code"], method=point["method"]):
                self.assertTrue(point_in_polygons(point["longitude"], point["latitude"], polygons[record["istat_code"]]))
                self.assertEqual(set(point["source"]) >= {"authority", "dataset", "license"}, True)

    def test_builder_never_reads_or_derives_from_legacy_municipality_coordinates(self):
        guarded = deepcopy(self.metadata)
        guarded["municipalities"] = [ForbiddenLegacyCoordinates(record) for record in guarded["municipalities"]]
        guarded["source"]["coordinates"] = "forbidden sentinel that must not be copied"
        result = build_authoritative_catalog(self.geography, guarded)
        self.assertEqual(result, self.document)
        serialized = json.dumps(result, ensure_ascii=False).casefold()
        self.assertNotIn("open-meteo", serialized)
        self.assertNotIn("open_meteo", serialized)
        self.assertNotIn("forbidden sentinel", serialized)

    def test_hash_and_points_are_stable_when_all_input_collections_are_reordered(self):
        geography = deepcopy(self.geography)
        metadata = deepcopy(self.metadata)
        geography["municipalities"].reverse()
        geography["localities"].reverse()
        metadata["municipalities"].reverse()
        for municipality in geography["municipalities"]:
            municipality["polygons"].reverse()
            for polygon in municipality["polygons"]:
                for ring in polygon:
                    ring.reverse()
        reordered = build_authoritative_catalog(geography, metadata)
        self.assertEqual(reordered, self.document)
        self.assertEqual(reordered["catalog_sha256"], self.document["catalog_sha256"])


class GeometryPolicyTests(unittest.TestCase):
    def test_point_on_surface_does_not_return_an_outside_bbox_centre(self):
        # The centre (2, 2) is in the missing upper-right part of this L shape.
        polygon = ((((0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4), (0, 0)),),)
        longitude, latitude = deterministic_point_on_surface(polygon)
        self.assertNotEqual((longitude, latitude), (2, 2))
        self.assertTrue(point_in_polygons(longitude, latitude, polygon, boundary_is_inside=False))

    def test_hole_is_never_selected_as_surface(self):
        polygon = ((
            ((0, 0), (6, 0), (6, 6), (0, 6), (0, 0)),
            ((2, 2), (2, 4), (4, 4), (4, 2), (2, 2)),
        ),)
        longitude, latitude = deterministic_point_on_surface(polygon)
        self.assertTrue(point_in_polygons(longitude, latitude, polygon, boundary_is_inside=False))
        self.assertFalse(2 < longitude < 4 and 2 < latitude < 4)

    def test_name_normalization_is_exact_but_case_unicode_and_whitespace_stable(self):
        self.assertEqual(normalize_municipality_name("  SAN   VITO  "), "san vito")
        self.assertEqual(normalize_municipality_name("Ｓａｎ Vito"), "san vito")
        self.assertNotEqual(normalize_municipality_name("Forni di Sopra"), normalize_municipality_name("Forni Sopra"))


class FailClosedTests(unittest.TestCase):
    def test_duplicate_istat_and_outside_selected_locality_are_rejected(self):
        geography, metadata = sources()
        duplicate = deepcopy(metadata)
        duplicate["municipalities"][1]["istatCode"] = duplicate["municipalities"][0]["istatCode"]
        with self.assertRaisesRegex(AuthoritativeCatalogError, "duplicate ISTAT"):
            build_authoritative_catalog(geography, duplicate)

        outside = deepcopy(geography)
        selected = next(item for item in outside["localities"] if item["kind"] == "municipal_seat")
        selected["latitude"] = 0
        selected["longitude"] = 0
        with self.assertRaisesRegex(AuthoritativeCatalogError, "outside"):
            build_authoritative_catalog(outside, metadata)


if __name__ == "__main__":
    unittest.main()
