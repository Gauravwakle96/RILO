"""Resource-limited parser subprocess for an explicitly supplied local upload."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def limit_resources() -> None:
    if sys.platform != "win32":
        import importlib

        resource: Any = importlib.import_module("resource")

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
        return
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("min_ws", ctypes.c_size_t),
            ("max_ws", ctypes.c_size_t),
            ("active", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class IO(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "read_ops",
                "write_ops",
                "other_ops",
                "read_bytes",
                "write_bytes",
                "other_bytes",
            )
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", IO),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.basic.flags = 0x100 | 0x2
    limits.basic.process_time = 20 * 10_000_000
    limits.process_memory = 512 * 1024 * 1024
    if (
        not handle
        or not kernel.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        or not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess())
    ):
        raise RuntimeError("Unable to enforce parser resource limits.")


def main():
    limit_resources()
    from .documents import extract

    path, name, kind = sys.argv[1:]
    result: dict[str, Any]
    try:
        result = {"sources": extract(name, kind, Path(path).read_bytes())}
    except Exception as exc:
        result = {
            "error": str(exc)
            if isinstance(exc, ValueError)
            else f"Document extraction failed ({type(exc).__name__})."
        }
    sys.stdout.buffer.write(json.dumps(result).encode("utf-8"))


if __name__ == "__main__":
    main()
