"""Hẹn giờ chính xác cho tải open-loop (Part 11) trên Windows / Linux.

Đo trên máy Core Ultra 5 125H + Windows 11 (workflow vbench-verify-research, 22/09):
- time.sleep tới deadline: p99 trễ 1,6–4,7 ms (tệ hơn khi process không ở foreground).
- EcoQoS (power throttling) của Windows trên CPU hybrid làm cả sleep+spin p99 4,8–32 ms → phải TẮT throttling EXECUTION_SPEED
  (SetProcessInformation(ProcessPowerThrottling)) và nâng HIGH_PRIORITY_CLASS: sleep+spin p99 còn ~0,02 ms.
- sleep tới (deadline − spin) rồi spin trên perf_counter_ns.
"""
from __future__ import annotations

import os
import sys
import time

SPIN_NS = 3_000_000       # spin 3 ms cuối (đo: p99 0,08–0,62 ms khi EcoQoS tắt)
BLAS_ENV = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


def limit_blas_threads() -> None:
    """Phải gọi TRƯỚC khi spawn worker: mỗi process import numpy commit ~540 MB bộ đệm OpenBLAS theo số CPU."""
    for k in BLAS_ENV:
        os.environ.setdefault(k, "1")


def disable_power_throttling() -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    class PPTS(ctypes.Structure):   # PROCESS_POWER_THROTTLING_STATE
        _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.SetProcessInformation.restype = wintypes.BOOL
    st = PPTS(1, 0x1, 0)            # CURRENT_VERSION=1, ControlMask=EXECUTION_SPEED, StateMask=0 → HighQoS
    return bool(k.SetProcessInformation(k.GetCurrentProcess(), 4, ctypes.byref(st), ctypes.sizeof(st)))   # 4 = ProcessPowerThrottling


def raise_priority() -> bool:
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            HIGH_PRIORITY_CLASS = 0x80
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.GetCurrentProcess.restype = wintypes.HANDLE          # HANDLE 64-bit: để mặc định int sẽ cắt thành handle sai
            k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            k.SetPriorityClass.restype = wintypes.BOOL
            return bool(k.SetPriorityClass(k.GetCurrentProcess(), HIGH_PRIORITY_CLASS))
        os.nice(-5)
        return True
    except Exception:  # noqa: BLE001
        return False


def tune_process() -> dict:
    return {"power_throttling_off": disable_power_throttling(), "high_priority": raise_priority()}


def sleep_until_ns(deadline_ns: int, spin_ns: int = SPIN_NS) -> None:
    while True:
        rem = deadline_ns - time.perf_counter_ns()
        if rem <= 0:
            return
        if rem > spin_ns:
            time.sleep((rem - spin_ns) / 1e9)
        else:
            time.sleep(0)       # spin nhưng nhường GIL (thread khác của process không bị chặn tới 5 ms switch interval)
