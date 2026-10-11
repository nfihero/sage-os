"""What the graphics cards are doing on Windows, for any vendor (G1, D29.1). No nvidia-smi.

  * Adapters: DirectX (DXGI) lists every graphics card with its name, vendor, dedicated memory and LUID (the ID
    Windows' counters use). The registry adds the driver version, which picks the CUDA build (engine).
  * Usage: Windows' own GPU performance counters (what Task Manager shows) give graphics memory and engine
    activity per adapter and per program, for NVIDIA, AMD and Intel alike, integrated graphics included.
  * Full screen: the shell says when a full-screen Direct3D program (a game) is running.
"""
from __future__ import annotations

import ctypes
import re
import time
import winreg
from ctypes import wintypes

VENDORS = {0x10DE: "nvidia", 0x1002: "amd", 0x1022: "amd", 0x8086: "intel", 0x1414: "microsoft", 0x5143: "qualcomm"}
GPU_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


# -- adapters (DXGI) ------------------------------------------------------------------------------------------
class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class DXGI_ADAPTER_DESC1(ctypes.Structure):
    _fields_ = [("Description", ctypes.c_wchar * 128), ("VendorId", ctypes.c_uint), ("DeviceId", ctypes.c_uint),
                ("SubSysId", ctypes.c_uint), ("Revision", ctypes.c_uint), ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t), ("SharedSystemMemory", ctypes.c_size_t),
                ("AdapterLuid", LUID), ("Flags", ctypes.c_uint)]


IID_IDXGIFactory1 = GUID(0x770AAE78, 0xF26F, 0x4DBA, (ctypes.c_ubyte * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87))
DXGI_ERROR_NOT_FOUND = 0x887A0002
DXGI_ADAPTER_FLAG_SOFTWARE = 2


def _method(obj, index, restype, *argtypes):
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[index])


def _release(obj):
    _method(obj, 2, ctypes.c_ulong)(obj)


def luid_key(low: int, high: int) -> str:
    """The form Windows' counters use: luid_0x00000000_0x0000cd37."""
    return f"luid_0x{high & 0xFFFFFFFF:08x}_0x{low & 0xFFFFFFFF:08x}"


def adapters() -> list[dict]:
    """Every hardware graphics card: [{name, vendor, vendor_id, vram_bytes, luid, driver}], largest memory first."""
    factory = ctypes.c_void_p()
    if ctypes.windll.dxgi.CreateDXGIFactory1(ctypes.byref(IID_IDXGIFactory1), ctypes.byref(factory)) != 0:
        return []
    out = []
    try:
        enum = _method(factory, 12, ctypes.HRESULT, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))   # EnumAdapters1
        i = 0
        while True:
            adapter = ctypes.c_void_p()
            try:
                enum(factory, i, ctypes.byref(adapter))
            except OSError as exc:
                if (exc.winerror or 0) & 0xFFFFFFFF == DXGI_ERROR_NOT_FOUND:
                    break
                raise
            try:
                desc = DXGI_ADAPTER_DESC1()
                _method(adapter, 10, ctypes.HRESULT, ctypes.POINTER(DXGI_ADAPTER_DESC1))(adapter, ctypes.byref(desc))
                if not desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE:
                    out.append({"name": desc.Description, "vendor_id": desc.VendorId,
                                "vendor": VENDORS.get(desc.VendorId, "other"),
                                "vram_bytes": int(desc.DedicatedVideoMemory),
                                "luid": luid_key(desc.AdapterLuid.LowPart, desc.AdapterLuid.HighPart)})
            finally:
                _release(adapter)
            i += 1
    finally:
        _release(factory)
    drivers = _registry_drivers()
    for a in out:
        reg = drivers.get(a["name"].strip().lower(), {})
        a["driver"] = nvidia_driver(reg["driver_version"]) if a["vendor"] == "nvidia" and reg else reg.get("driver_version")
        if reg.get("vram_bytes", 0) > a["vram_bytes"]:      # DXGI caps at 4 GB on some 32-bit paths; trust the larger
            a["vram_bytes"] = reg["vram_bytes"]
    return sorted(out, key=lambda a: -a["vram_bytes"])


def _registry_drivers() -> dict[str, dict]:
    """Display adapters' driver versions from the registry, by description (lower-case)."""
    out = {}
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, GPU_CLASS)
    except OSError:
        return out
    with root:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            if not re.fullmatch(r"\d{4}", sub):
                continue
            try:
                with winreg.OpenKey(root, sub) as k:
                    desc = winreg.QueryValueEx(k, "DriverDesc")[0]
                    ver = winreg.QueryValueEx(k, "DriverVersion")[0]
                    try:
                        mem = int(winreg.QueryValueEx(k, "HardwareInformation.qwMemorySize")[0])
                    except (OSError, ValueError, TypeError):
                        mem = 0
            except OSError:
                continue
            out[str(desc).strip().lower()] = {"driver_version": ver, "vram_bytes": mem}
    return out


def nvidia_driver(windows_version: str) -> str:
    """NVIDIA's own driver number from the Windows driver version: 32.0.16.1742 -> 617.42 (the last five digits)."""
    digits = re.sub(r"\D", "", str(windows_version or ""))[-5:]
    return f"{digits[:3]}.{digits[3:]}" if len(digits) == 5 else str(windows_version or "")


# -- usage (performance counters) ---------------------------------------------------------------------------
class _PDH_VALUE(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class _PDH_ITEM(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", _PDH_VALUE)]


PDH_FMT_DOUBLE = 0x00000200
PDH_FMT_NOCAP100 = 0x00008000
PDH_MORE_DATA = 0x800007D2
PDH_CSTATUS_VALID = (0, 1)        # valid data, new data
_INSTANCE = re.compile(r"pid_(\d+)_(luid_0x[0-9a-f]+_0x[0-9a-f]+)_phys_\d+(?:_eng_\d+_engtype_(.*))?", re.I)
_ADAPTER = re.compile(r"(luid_0x[0-9a-f]+_0x[0-9a-f]+)_phys_\d+", re.I)


class Counters:
    """One open query over the GPU counters. Engine activity is a rate, so read it at least twice (the first
    read after opening has no activity yet); new programs show up on the next read."""

    PATHS = {"proc_mem": r"\GPU Process Memory(*)\Dedicated Usage",
             "engine": r"\GPU Engine(*)\Utilization Percentage",
             "adapter_mem": r"\GPU Adapter Memory(*)\Dedicated Usage"}

    def __init__(self):
        self.pdh = ctypes.windll.pdh
        self.query = wintypes.HANDLE()
        if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.query)) != 0:
            raise OSError("couldn't open the GPU performance counters")
        self.counters = {}
        for key, path in self.PATHS.items():
            h = wintypes.HANDLE()
            if self.pdh.PdhAddEnglishCounterW(self.query, path, None, ctypes.byref(h)) == 0:
                self.counters[key] = h
        self.pdh.PdhCollectQueryData(self.query)

    def _array(self, key: str) -> list[tuple[str, float]]:
        h = self.counters.get(key)
        if h is None:
            return []
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        flags = PDH_FMT_DOUBLE | PDH_FMT_NOCAP100
        rc = self.pdh.PdhGetFormattedCounterArrayW(h, flags, ctypes.byref(size), ctypes.byref(count), None)
        if rc & 0xFFFFFFFF != PDH_MORE_DATA or not size.value:
            return []
        buf = (ctypes.c_byte * size.value)()
        if self.pdh.PdhGetFormattedCounterArrayW(h, flags, ctypes.byref(size), ctypes.byref(count), buf) != 0:
            return []
        items = ctypes.cast(buf, ctypes.POINTER(_PDH_ITEM))
        return [(items[i].szName, items[i].FmtValue.doubleValue) for i in range(count.value)
                if items[i].FmtValue.CStatus in PDH_CSTATUS_VALID]

    def read(self) -> dict:
        """-> {"adapters": {luid: used_bytes}, "processes": {pid: {luid: {"vram": bytes, "busy": pct}}}}"""
        self.pdh.PdhCollectQueryData(self.query)
        adapters: dict[str, float] = {}
        for name, v in self._array("adapter_mem"):
            m = _ADAPTER.fullmatch(name)
            if m:
                adapters[m.group(1).lower()] = adapters.get(m.group(1).lower(), 0) + v
        procs: dict[int, dict] = {}
        for name, v in self._array("proc_mem"):
            m = _INSTANCE.fullmatch(name)
            if m:
                slot = procs.setdefault(int(m.group(1)), {}).setdefault(m.group(2).lower(), {"vram": 0.0, "busy": 0.0})
                slot["vram"] += v
        for name, v in self._array("engine"):
            m = _INSTANCE.fullmatch(name)
            if m and not (m.group(3) or "").lower().startswith(("video", "copy", "security")):
                # 3D and compute only: a screen recorder's encoder or a video player isn't a game
                slot = procs.setdefault(int(m.group(1)), {}).setdefault(m.group(2).lower(), {"vram": 0.0, "busy": 0.0})
                slot["busy"] = max(slot["busy"], v)        # the busiest engine (3D, compute, video) of the program
        return {"adapters": adapters, "processes": procs, "ts": time.time()}

    def close(self):
        if self.query:
            self.pdh.PdhCloseQuery(self.query)
            self.query = wintypes.HANDLE()


# -- what's in front ----------------------------------------------------------------------------------------
QUNS_RUNNING_D3D_FULL_SCREEN = 3


def fullscreen_game() -> bool:
    """True while a full-screen Direct3D program (a game) runs."""
    state = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except OSError:
        return False
    return state.value == QUNS_RUNNING_D3D_FULL_SCREEN


def foreground_pid() -> int | None:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD(0)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None
