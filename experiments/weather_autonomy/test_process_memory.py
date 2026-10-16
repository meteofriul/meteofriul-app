"""Offline Windows-ABI stubs and a read-only live check; no app or network.

python -B -m unittest discover -s experiments/weather_autonomy -p test_process_memory.py -v
"""

import ctypes
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

try:
    from . import process_memory
except ImportError:
    import process_memory


class ProcessMemoryTests(unittest.TestCase):
    def stub_apis(self, *, working, peak, succeeded=1):
        pseudo_handle = ctypes.c_void_p(-1).value
        kernel32 = SimpleNamespace(GetCurrentProcess=Mock(return_value=pseudo_handle))

        def populate(handle, pointer, cb):
            self.assertEqual(handle, pseudo_handle)
            counters = ctypes.cast(
                pointer, ctypes.POINTER(process_memory._ProcessMemoryCounters)
            ).contents
            self.assertEqual(cb, ctypes.sizeof(process_memory._ProcessMemoryCounters))
            self.assertEqual(counters.cb, cb)
            counters.WorkingSetSize = working
            counters.PeakWorkingSetSize = peak
            return succeeded

        psapi = SimpleNamespace(GetProcessMemoryInfo=Mock(side_effect=populate))
        return kernel32, psapi

    def test_working_set_and_lifetime_peak_are_separate_json_integers(self):
        apis = self.stub_apis(working=12_345_678, peak=98_765_432)
        with patch.object(process_memory.sys, "platform", "win32"), patch.object(
            process_memory, "_load_windows_apis", return_value=apis
        ):
            result = process_memory.process_memory_bytes()
        self.assertEqual(result, {
            "working_set_bytes": 12_345_678,
            "peak_working_set_bytes": 98_765_432,
        })
        self.assertEqual(json.loads(json.dumps(result)), result)
        self.assertTrue(all(type(value) is int for value in result.values()))

    @unittest.skipUnless(ctypes.sizeof(ctypes.c_void_p) == 8, "64-bit ABI check")
    def test_sizes_above_four_gib_are_not_truncated(self):
        apis = self.stub_apis(working=5 * 1024**3 + 17, peak=9 * 1024**3 + 31)
        with patch.object(process_memory.sys, "platform", "win32"), patch.object(
            process_memory, "_load_windows_apis", return_value=apis
        ):
            result = process_memory.process_memory_bytes()
        self.assertEqual(result["working_set_bytes"], 5 * 1024**3 + 17)
        self.assertEqual(result["peak_working_set_bytes"], 9 * 1024**3 + 31)

    def test_windows_structure_width_and_alignment(self):
        structure = process_memory._ProcessMemoryCounters
        self.assertEqual(structure.PeakWorkingSetSize.offset, 8)
        self.assertEqual(structure.WorkingSetSize.offset, 8 + ctypes.sizeof(ctypes.c_size_t))
        self.assertEqual(ctypes.sizeof(structure), 8 + 8 * ctypes.sizeof(ctypes.c_size_t))

    def test_function_signatures_preserve_pointer_width(self):
        kernel32, psapi = self.stub_apis(working=1, peak=2)
        with patch.object(process_memory.sys, "platform", "win32"), patch.object(
            process_memory, "_load_windows_apis", return_value=(kernel32, psapi)
        ):
            process_memory.process_memory_bytes()
        self.assertIs(kernel32.GetCurrentProcess.restype, ctypes.c_void_p)
        self.assertEqual(kernel32.GetCurrentProcess.argtypes, [])
        self.assertIs(psapi.GetProcessMemoryInfo.argtypes[0], ctypes.c_void_p)
        self.assertIs(psapi.GetProcessMemoryInfo.argtypes[2], ctypes.c_uint32)
        self.assertIs(psapi.GetProcessMemoryInfo.restype, ctypes.c_int32)

    def test_failed_api_raises_instead_of_returning_zero(self):
        apis = self.stub_apis(working=0, peak=0, succeeded=0)
        error = OSError(5, "Access is denied")
        with patch.object(process_memory.sys, "platform", "win32"), patch.object(
            process_memory, "_load_windows_apis", return_value=apis
        ), patch.object(ctypes, "get_last_error", return_value=5, create=True), patch.object(
            ctypes, "WinError", return_value=error, create=True
        ) as win_error:
            with self.assertRaises(OSError) as caught:
                process_memory.process_memory_bytes()
        self.assertIs(caught.exception, error)
        win_error.assert_called_once_with(5)

    def test_non_windows_fails_explicitly_without_loading_dlls(self):
        with patch.object(process_memory.sys, "platform", "unsupported"), patch.object(
            process_memory, "_load_windows_apis"
        ) as load:
            with self.assertRaises(NotImplementedError):
                process_memory.process_memory_bytes()
        load.assert_not_called()

    def test_linux_reads_resident_counters_in_bytes(self):
        with patch.object(process_memory.sys, "platform", "linux"), patch.object(
            process_memory.Path, "read_text", return_value="Name: python\nVmRSS: 1024 kB\nVmHWM: 2048 kB\n"
        ):
            self.assertEqual(process_memory.process_memory_bytes(), {
                "working_set_bytes": 1048576, "peak_working_set_bytes": 2097152,
            })

    def test_linux_missing_counters_fail_closed(self):
        with patch.object(process_memory.sys, "platform", "linux"), patch.object(
            process_memory.Path, "read_text", return_value="Name: python\n"
        ):
            with self.assertRaises(OSError):
                process_memory.process_memory_bytes()

    @unittest.skipUnless(sys.platform == "win32", "Windows live read-only check")
    def test_live_process_memory_is_positive_with_peak_not_below_current(self):
        result = process_memory.process_memory_bytes()
        self.assertGreater(result["working_set_bytes"], 0)
        self.assertGreaterEqual(result["peak_working_set_bytes"], result["working_set_bytes"])


if __name__ == "__main__":
    unittest.main()
