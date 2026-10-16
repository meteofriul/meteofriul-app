import unittest
from unittest.mock import patch
from uv_cloud import decode

class UvDecodeTests(unittest.TestCase):
    def test_empty_is_not_a_forecast(self):
        import tempfile
        with tempfile.TemporaryFile() as stream:
            with patch('builtins.open', return_value=stream), patch('eccodes.codes_grib_new_from_file', return_value=None):
                with self.assertRaises(ValueError):
                    decode('unused', '2026-09-06')

    def test_clear_sky_is_rejected(self):
        import tempfile
        with tempfile.TemporaryFile() as stream:
            with patch('builtins.open', return_value=stream), patch('eccodes.codes_grib_new_from_file', return_value=1), patch('eccodes.codes_get', return_value=214003), patch('eccodes.codes_release'):
                with self.assertRaises(ValueError):
                    decode('unused', '2026-09-06')
