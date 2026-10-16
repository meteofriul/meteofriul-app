from array import array
from contextlib import closing, contextmanager
from dataclasses import replace
import hashlib
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
import zlib

from app.services.national_municipalities import NationalMunicipality
from app.services.pilot_community_geography import (
    BOUNDARIES_SOURCE_SHA256,
    GEOGRAPHY_SCHEMA,
    PilotCommunityGeographyCatalog,
    PilotCommunityGeographyUnavailable,
    _contains_point,
    _pack_rings,
    _unpack_rings,
)


def ring(*points):
    return array("d", (value for point in points for value in point))


def square(west, south, east, north):
    return ring((west, south), (east, south), (east, north), (west, north), (west, south))


@contextmanager
def write_connection(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        yield connection


class PilotCommunityGeographyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "geography.sqlite3"
        first = NationalMunicipality("001001", "Comune", "AA", "Prima", "Regione", "IT-21", 44.005, 10.005)
        second = replace(first, istat_code="001002", province_code="BB", province_name="Seconda", longitude=10.015)
        self.identities = (first, second)
        self.catalog = SimpleNamespace(
            municipalities=self.identities,
            catalog_sha256="fixture-catalog",
            match_istat=lambda value: next((item for item in self.identities if item.istat_code == value), None),
            match_name=self.match_name,
        )
        with write_connection(self.path) as connection:
            connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.executemany("INSERT INTO metadata VALUES (?,?)", {
                "schema": GEOGRAPHY_SCHEMA,
                "source_sha256": BOUNDARIES_SOURCE_SHA256,
                "catalog_sha256": self.catalog.catalog_sha256,
                "crs": "EPSG:4326",
                "geometry_policy": "non_generalized_no_simplification",
            }.items())
            connection.execute(
                "CREATE TABLE municipalities (istat_code TEXT PRIMARY KEY, min_lon REAL, min_lat REAL, "
                "max_lon REAL, max_lat REAL, public_latitude REAL, public_longitude REAL, geometry BLOB, geometry_sha256 TEXT)"
            )
            for index, identity in enumerate(self.identities):
                west, east = 10 + index * 0.01, 10.01 + index * 0.01
                payload = _pack_rings((square(west, 44, east, 44.01),))
                connection.execute("INSERT INTO municipalities VALUES (?,?,?,?,?,?,?,?,?)", (
                    identity.istat_code, west, 44, east, 44.01, identity.latitude, identity.longitude,
                    zlib.compress(payload), hashlib.sha256(payload).hexdigest(),
                ))
        self.geography = PilotCommunityGeographyCatalog(self.path, catalog=self.catalog)

    def match_name(self, name, province=None):
        matches = [item for item in self.identities if item.name == name and (province is None or item.province_code == province)]
        return matches[0] if len(matches) == 1 else None

    def test_gps_resolves_only_containing_polygon_and_returns_fixed_public_point(self):
        actual = self.geography.resolve_municipality(44.001, 10.001)
        self.assertEqual(actual.istat_code, "001001")
        self.assertEqual(actual.region_iso, "IT-21")
        self.assertEqual((actual.latitude, actual.longitude), (44.005, 10.005))
        self.assertNotEqual((actual.latitude, actual.longitude), (44.001, 10.001))
        self.assertEqual(self.geography.resolve_municipality_istat(44.002, 10.016), "001002")

    def test_shared_border_is_ambiguous_and_outside_never_selects_nearest(self):
        self.assertIsNone(self.geography.resolve_municipality(44.005, 10.01))
        self.assertIsNone(self.geography.resolve_municipality(44.01001, 10.005))
        self.assertTrue(self.geography.nearby_municipalities(44.01001, 10.005))

    def test_exact_identity_and_ambiguous_names(self):
        self.assertEqual(self.geography.match_istat("001002").province, "BB")
        self.assertIsNone(self.geography.match_istat("1002"))
        self.assertIsNone(self.geography.match_name("Comune"))
        self.assertEqual(self.geography.match_name("Comune", province="AA").istat_code, "001001")
        self.assertEqual(len(self.geography.municipalities), 2)

    def test_holes_multipart_and_boundary_points_are_supported(self):
        rings = (square(0, 0, 3, 3), square(1, 1, 2, 2), square(4, 0, 5, 1))
        self.assertTrue(_contains_point(rings, 0.5, 0.5))
        self.assertFalse(_contains_point(rings, 1.5, 1.5))
        self.assertTrue(_contains_point(rings, 0.5, 4.5))
        self.assertFalse(_contains_point(rings, 0.5, 3.5))
        self.assertTrue(_contains_point(rings, 1.5, 1))
        self.assertEqual(_unpack_rings(_pack_rings(rings)), rings)

    def test_invalid_coordinates_and_unbounded_radius_are_rejected(self):
        for latitude, longitude in ((float("nan"), 10), (44, float("inf")), (91, 10), (True, 10), ("44", 10)):
            self.assertIsNone(self.geography.resolve_municipality(latitude, longitude))
        self.assertEqual(self.geography.nearby_municipalities(44, 10, radius_km=1000), ())
        self.assertEqual(self.geography.nearby_municipalities(44, 10, radius_km=float("nan")), ())
        self.assertEqual(self.geography.nearby_municipalities(44.005, 10.005, radius_km=0.1)[0].istat_code, "001001")
        self.assertEqual(len(self.geography.nearby_municipalities(44.005, 10.005, limit=1)), 1)

    def test_missing_artifact_fails_closed_without_creating_file(self):
        missing = self.path.with_name("missing.sqlite3")
        geography = PilotCommunityGeographyCatalog(missing, catalog=self.catalog)
        with self.assertRaises(PilotCommunityGeographyUnavailable):
            geography.resolve_municipality(44.005, 10.005)
        self.assertFalse(missing.exists())

    def test_wrong_provenance_or_incomplete_coverage_is_rejected(self):
        with write_connection(self.path) as connection:
            connection.execute("UPDATE metadata SET value='unknown' WHERE key='source_sha256'")
        with self.assertRaises(PilotCommunityGeographyUnavailable):
            self.geography.match_istat("001001")
        with write_connection(self.path) as connection:
            connection.execute("UPDATE metadata SET value=? WHERE key='source_sha256'", (BOUNDARIES_SOURCE_SHA256,))
            connection.execute("DELETE FROM municipalities WHERE istat_code='001002'")
        with self.assertRaises(PilotCommunityGeographyUnavailable):
            self.geography.match_istat("001001")

    def test_corrupt_geometry_is_rejected(self):
        with write_connection(self.path) as connection:
            connection.execute("UPDATE municipalities SET geometry_sha256='bad' WHERE istat_code='001001'")
        with self.assertRaises(PilotCommunityGeographyUnavailable):
            self.geography.resolve_municipality(44.005, 10.005)


class PilotCommunityRealGeographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geography = PilotCommunityGeographyCatalog()
        if not cls.geography.data_path.exists():
            raise unittest.SkipTest("optional local ISTAT pilot artifact has not been built")

    def test_real_gps_points_across_italy_and_foreign_enclaves(self):
        for latitude, longitude, expected in (
            (45.9567, 12.6605, "093033"),  # Pordenone
            (46.0711, 13.2346, "030129"),  # Udine
            (43.7262, 12.6363, "041067"),  # Urbino historic centre
            (41.9028, 12.4964, "058091"),  # Roma
            (38.1157, 13.3613, "082053"),  # Palermo
        ):
            with self.subTest(istat=expected):
                self.assertEqual(self.geography.resolve_municipality_istat(latitude, longitude), expected)
        for latitude, longitude in ((43.9367, 12.4464), (41.9029, 12.4534), (46.0569, 14.5058), (44.0, 14.0)):
            with self.subTest(outside=(latitude, longitude)):
                self.assertIsNone(self.geography.resolve_municipality(latitude, longitude))

    def test_all_current_municipalities_and_mergers_have_geometry(self):
        self.assertEqual(len(self.geography.municipalities), 7894)
        for code in ("018094", "024129", "041067", "093033"):
            municipality = self.geography.match_istat(code)
            self.assertEqual(self.geography.resolve_municipality_istat(municipality.latitude, municipality.longitude), code)
        self.assertIsNone(self.geography.match_istat("018082"))


if __name__ == "__main__":
    unittest.main()
