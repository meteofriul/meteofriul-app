"""Read current/peak resident memory on Windows or Linux, without dependencies.

These are operating-system process counters: native allocations from ecCodes,
NumPy and other DLLs count when resident, unlike Python-only ``tracemalloc``.
The peak is the process-lifetime peak, not a peak reset at the start of a probe
or the difference from a baseline. Working set is resident memory, not committed
memory, total allocation, file sizes or a promise about cloud memory usage.

Windows API reference:
https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo
https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters

No process is opened, modified or closed: GetCurrentProcess supplies a pseudo
handle. Linux reads VmRSS/VmHWM from /proc/self/status in KiB and converts to
bytes. Other operating systems fail explicitly instead of reporting zeros.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def _linux_memory_bytes():
    fields = {}
    for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
        parts = line.split()
        if parts and parts[0] in ("VmRSS:", "VmHWM:"):
            if len(parts) != 3 or parts[2] != "kB":
                raise OSError("Unsupported Linux resident-memory units")
            fields[parts[0]] = int(parts[1]) * 1024
    current, peak = fields.get("VmRSS:", 0), fields.get("VmHWM:", 0)
    if current <= 0 or peak < current:
        raise OSError("Incomplete Linux resident-memory counters")
    return {"working_set_bytes": current, "peak_working_set_bytes": peak}


class _ProcessMemoryCounters(ctypes.Structure):
    # Windows DWORD remains 32 bits; SIZE_T and HANDLE follow pointer width.
    # Do not use c_ulong for DWORD, because its width varies on other platforms
    # used by the stub tests. Default native alignment matches the Windows ABI.
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _load_windows_apis():
    """Load only when requested on Windows; importing this module is portable."""
    return (
        ctypes.WinDLL("kernel32", use_last_error=True),
        ctypes.WinDLL("psapi", use_last_error=True),
    )


def process_memory_bytes() -> dict[str, int]:
    """Return current and process-lifetime peak working-set sizes in bytes.

    The exact keys are ``working_set_bytes`` and ``peak_working_set_bytes``.
    Raises OSError for missing OS counters, and NotImplementedError on unsupported
    platforms; callers must not treat missing measurements as zero memory.
    """
    if sys.platform == "linux":
        return _linux_memory_bytes()
    if sys.platform != "win32":
        raise NotImplementedError("Process working-set measurement requires Windows")

    kernel32, psapi = _load_windows_apis()
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.argtypes = []
    get_current_process.restype = ctypes.c_void_p

    get_process_memory_info = psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_ProcessMemoryCounters),
        ctypes.c_uint32,
    ]
    get_process_memory_info.restype = ctypes.c_int32

    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    succeeded = get_process_memory_info(
        get_current_process(), ctypes.byref(counters), counters.cb
    )
    if not succeeded:
        raise ctypes.WinError(ctypes.get_last_error())

    return {
        "working_set_bytes": int(counters.WorkingSetSize),
        "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
    }
