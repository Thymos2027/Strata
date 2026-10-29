"""Low-frequency Windows process/RAM, whole-card NVML, and system paging samples."""
import ctypes as C
from ctypes import wintypes as W
import threading
import time

import psutil


class MemInfo(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in ("total", "free", "used")]


class CounterValue(C.Structure):
    _fields_ = [("status", W.DWORD), ("value", C.c_double)]


class GroupAffinity(C.Structure):
    _fields_ = [("mask", C.c_ulonglong), ("group", W.WORD), ("reserved", W.WORD * 3)]


def thread_affinities(pid):
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenThread.restype = W.HANDLE
    kernel.GetThreadGroupAffinity.argtypes = [W.HANDLE, C.POINTER(GroupAffinity)]
    kernel.CloseHandle.argtypes = [W.HANDLE]
    records = []
    for thread in psutil.Process(pid).threads():
        handle = kernel.OpenThread(0x0800, False, thread.id)
        affinity = GroupAffinity()
        if handle:
            try:
                if kernel.GetThreadGroupAffinity(handle, C.byref(affinity)):
                    records.append({"tid": thread.id, "group": affinity.group, "mask": hex(affinity.mask)})
                else:
                    records.append({"tid": thread.id, "error": C.get_last_error()})
            finally:
                kernel.CloseHandle(handle)
        else:
            records.append({"tid": thread.id, "error": C.get_last_error()})
    return records


class Telemetry:
    def __init__(self, pid):
        self.process = psutil.Process(pid)
        self.nvml = C.WinDLL("nvml.dll")
        if self.nvml.nvmlInit_v2() != 0:
            raise RuntimeError("NVML initialization failed")
        self.device = C.c_void_p()
        self.nvml.nvmlDeviceGetHandleByIndex_v2.argtypes = [C.c_uint, C.POINTER(C.c_void_p)]
        self.nvml.nvmlDeviceGetMemoryInfo.argtypes = [C.c_void_p, C.POINTER(MemInfo)]
        if self.nvml.nvmlDeviceGetHandleByIndex_v2(0, C.byref(self.device)) != 0:
            raise RuntimeError("NVML GPU 0 is unavailable")
        self.pdh = C.WinDLL("pdh")
        self.pdh.PdhOpenQueryW.argtypes = [W.LPCWSTR, C.c_size_t, C.POINTER(W.HANDLE)]
        self.pdh.PdhAddEnglishCounterW.argtypes = [W.HANDLE, W.LPCWSTR, C.c_size_t, C.POINTER(W.HANDLE)]
        self.pdh.PdhCollectQueryData.argtypes = [W.HANDLE]
        self.pdh.PdhGetFormattedCounterValue.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.DWORD), C.POINTER(CounterValue)]
        self.pdh.PdhCloseQuery.argtypes = [W.HANDLE]
        self.query = W.HANDLE()
        code = self.pdh.PdhOpenQueryW(None, 0, C.byref(self.query))
        if code:
            raise RuntimeError(f"PDH query failed: {code}")
        self.counters = {}
        for name, path in (("system_pages_input_s", r"\Memory\Pages Input/sec"),
                           ("system_page_reads_s", r"\Memory\Page Reads/sec")):
            counter = W.HANDLE()
            code = self.pdh.PdhAddEnglishCounterW(self.query, path, 0, C.byref(counter))
            if code:
                raise RuntimeError(f"PDH counter failed: {name}: {code}")
            self.counters[name] = counter
        self.pdh.PdhCollectQueryData(self.query)
        self.stop = threading.Event()
        self.samples = []
        self.thread = None

    def sample(self):
        memory = self.process.memory_info()
        system = psutil.virtual_memory()
        gpu = MemInfo()
        if self.nvml.nvmlDeviceGetMemoryInfo(self.device, C.byref(gpu)) != 0:
            raise RuntimeError("NVML memory sample failed")
        row = {"monotonic_s": time.monotonic(), "rss_bytes": memory.rss,
               "private_bytes": memory.private, "process_page_faults": memory.num_page_faults,
               "system_available_bytes": system.available, "system_swap_used_bytes": psutil.swap_memory().used,
               "card_vram_used_bytes": gpu.used, "card_vram_total_bytes": gpu.total}
        self.pdh.PdhCollectQueryData(self.query)
        for name, counter in self.counters.items():
            value = CounterValue()
            code = self.pdh.PdhGetFormattedCounterValue(counter, 0x200, None, C.byref(value))
            row[name] = value.value if code == 0 and value.status in (0, 1) else None
        return row

    def begin(self):
        self.samples = [self.sample()]
        self.stop.clear()
        self.error = None

        def loop():
            while not self.stop.wait(0.5):
                try:
                    self.samples.append(self.sample())
                except Exception as exc:
                    self.error = repr(exc)
                    return

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

    def end(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.samples.append(self.sample())
        return {"sample_interval_s": 0.5, "samples": self.samples, "error": self.error,
                "rss_peak_bytes": max(x["rss_bytes"] for x in self.samples),
                "private_peak_bytes": max(x["private_bytes"] for x in self.samples),
                "card_vram_peak_bytes": max(x["card_vram_used_bytes"] for x in self.samples),
                "system_available_min_bytes": min(x["system_available_bytes"] for x in self.samples),
                "process_page_fault_delta": self.samples[-1]["process_page_faults"] - self.samples[0]["process_page_faults"]}

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.pdh.PdhCloseQuery(self.query)
        self.nvml.nvmlShutdown()
