import unittest
from uv_conversion import uv_index


class UvConversionTests(unittest.TestCase):
    def test_documented_conversion(self):
        self.assertEqual(uv_index(0.025, unit="W m-2"), 1)
        self.assertEqual(uv_index(0.15, unit="W m-2"), 6)

    def test_zero_is_not_missing(self):
        self.assertEqual(uv_index(0, unit="W m-2"), 0)
        self.assertIsNone(uv_index(None, unit="W m-2"))

    def test_reject_wrong_units(self):
        with self.assertRaises(ValueError):
            uv_index(150, unit="J m-2")

    def test_invalid_values(self):
        for value in (-1, float("nan"), float("inf"), True, "0.15"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                uv_index(value, unit="W m-2")
