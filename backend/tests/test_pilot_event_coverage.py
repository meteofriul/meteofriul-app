import unittest
from app.events import engine


class PilotCoverageTests(unittest.TestCase):
    def test_legacy_default_remains_twelve_towns(self):
        towns = engine.nearby_fvg_municipalities("Udine", 46.0711, 13.2346)
        self.assertLessEqual(len(towns), 12)
        for town in towns:
            self.assertLessEqual(engine.haversine_km(46.0711, 13.2346, town.latitude, town.longitude), 20)

    def test_explicit_fifty_km_includes_more_towns(self):
        towns = engine.nearby_fvg_municipalities("Udine", 46.0711, 13.2346, 50, 215)
        self.assertGreater(len(towns), 12)
        self.assertTrue(any(engine.haversine_km(46.0711, 13.2346, t.latitude, t.longitude) > 20 for t in towns))
        self.assertTrue(all(engine.haversine_km(46.0711, 13.2346, t.latitude, t.longitude) <= 50 for t in towns))

    def test_rejects_unbounded_work(self):
        with self.assertRaises(ValueError):
            engine.nearby_fvg_municipalities("Udine", radius_km=500)
