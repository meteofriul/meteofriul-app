import unittest
from array import array

from tools.build_official_alert_zone_catalog import (
    REGION_ZONE_PREFIX,
    _PreparedGeometry,
    _point_location,
    _positive_overlap,
)


def square(x1, y1, x2, y2):
    return (
        array("d", (x1, y1, x2, y1, x2, y2, x1, y2, x1, y1)),
    )


class OfficialAlertZoneCatalogBuilderTests(unittest.TestCase):
    def test_every_italian_region_has_one_explicit_dpc_prefix(self):
        self.assertEqual(len(REGION_ZONE_PREFIX), 20)
        self.assertEqual(len(set(REGION_ZONE_PREFIX.values())), 20)
        self.assertEqual(REGION_ZONE_PREFIX["IT-36"], "Friu")

    def test_point_location_distinguishes_inside_boundary_and_outside(self):
        rings = square(0, 0, 2, 2)
        self.assertEqual(_point_location(rings, 1, 1), 1)
        self.assertEqual(_point_location(rings, 0, 1), 0)
        self.assertEqual(_point_location(rings, 3, 1), -1)
        prepared = _PreparedGeometry(rings)
        self.assertEqual(prepared.point_location(1, 1), 1)
        self.assertEqual(prepared.point_location(0, 1), 0)
        self.assertEqual(prepared.point_location(3, 1), -1)

    def test_positive_overlap_keeps_crossing_zone(self):
        municipality = _PreparedGeometry(square(0, 0, 2, 2))
        zone = _PreparedGeometry(square(1, -1, 3, 3))
        self.assertTrue(
            _positive_overlap(municipality, zone, public_point=(0.5, 1))
        )

    def test_positive_overlap_rejects_boundary_only_contact(self):
        municipality = _PreparedGeometry(square(0, 0, 2, 2))
        zone = _PreparedGeometry(square(2, 0, 4, 2))
        self.assertFalse(
            _positive_overlap(municipality, zone, public_point=(1, 1))
        )

    def test_positive_overlap_detects_zone_enclosed_by_municipality(self):
        municipality = _PreparedGeometry(square(0, 0, 4, 4))
        zone = _PreparedGeometry(square(1, 1, 2, 2))
        self.assertTrue(
            _positive_overlap(municipality, zone, public_point=(3, 3))
        )

    def test_positive_overlap_uses_public_interior_for_identical_boundary(self):
        municipality = _PreparedGeometry(square(0, 0, 2, 2))
        zone = _PreparedGeometry(square(0, 0, 2, 2))
        self.assertTrue(
            _positive_overlap(municipality, zone, public_point=(1, 1))
        )


if __name__ == "__main__":
    unittest.main()
