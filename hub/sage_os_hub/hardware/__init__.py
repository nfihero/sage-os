"""What the computer's graphics hardware is doing, on any vendor (G1, D29.1).

`gpus()` lists the graphics cards (for the engine's hardware check); `Probe().read()` takes one reading of who is
using them, for game mode:

  * Windows: DirectX + Windows' own GPU counters (per adapter and per program), the full-screen-game state and the
    program in front. NVIDIA, AMD and Intel alike.
  * macOS: memory is shared, and there's no per-program GPU memory, so a reading is memory pressure, the app in
    front and how much memory it holds.
  * Elsewhere: nothing yet (Linux later, from the driver's per-program counters).
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time

import psutil

log = logging.getLogger("sage_os.hardware")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def gpus() -> list[dict]:
    """Graphics cards, largest memory first: [{name, vendor, vram_bytes, driver, luid}]."""
    if sys.platform == "win32":
        try:
            from . import windows
            return windows.adapters()
        except (OSError, ImportError, AttributeError) as exc:
            log.warning("couldn't list graphics cards: %s", exc)
            return []
    return []


def _name(pid: int, cache: dict[int, str]) -> str:
    if pid not in cache:
        try:
            cache[pid] = psutil.Process(pid).name()
        except (psutil.Error, OSError):
            cache[pid] = f"pid {pid}"
    return cache[pid]


class Probe:
    """Readings of who uses the graphics hardware. Cheap (a few ms); keep one open and read every few seconds."""

    def __init__(self):
        self.os = {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)
        self._names: dict[int, str] = {}
        self._counters = None
        self._gpus: list[dict] = []
        if self.os == "windows":
            try:
                from . import windows
                self._win = windows
                self._gpus = windows.adapters()
                self._counters = windows.Counters()
            except (OSError, ImportError, AttributeError) as exc:
                log.warning("GPU counters unavailable: %s", exc)

    def read(self) -> dict:
        if self.os == "windows" and self._counters is not None:
            return self._read_windows()
        if self.os == "macos":
            return self._read_macos()
        return {"os": self.os, "adapters": [], "programs": [], "fullscreen": False, "foreground": None,
                "ts": time.time()}

    def _read_windows(self) -> dict:
        w = self._win
        raw = self._counters.read()
        adapters = [{**g, "used_bytes": int(raw["adapters"].get(g["luid"], 0))} for g in self._gpus]
        programs = []
        for pid, per in raw["processes"].items():
            for luid, u in per.items():
                if u["vram"] <= 0 and u["busy"] <= 0:
                    continue
                programs.append({"pid": pid, "name": _name(pid, self._names), "adapter": luid,
                                 "vram_bytes": int(u["vram"]), "busy": round(u["busy"], 1)})
        if len(self._names) > 2000:
            self._names.clear()
        fg = w.foreground_pid()
        return {"os": "windows", "adapters": adapters, "programs": sorted(programs, key=lambda p: -p["vram_bytes"]),
                "fullscreen": w.fullscreen_game(),
                "foreground": {"pid": fg, "name": _name(fg, self._names)} if fg else None, "ts": raw["ts"]}

    def _read_macos(self) -> dict:
        vm = psutil.virtual_memory()
        free_pct = macos_free_pct()
        front = macos_front_app()
        programs = []
        if front:
            rss = 0
            for p in psutil.process_iter(["name", "memory_info"]):
                try:
                    if p.info["name"] == front and p.info["memory_info"]:
                        rss += p.info["memory_info"].rss
                except (psutil.Error, AttributeError):
                    continue
            programs.append({"pid": None, "name": front, "adapter": "unified", "vram_bytes": rss, "busy": None})
        return {"os": "macos",
                "adapters": [{"name": "Apple Silicon (shared memory)", "vendor": "apple", "vram_bytes": vm.total,
                              "used_bytes": vm.total - vm.available, "luid": "unified"}],
                "programs": programs, "fullscreen": False,
                "foreground": {"pid": None, "name": front} if front else None,
                "memory_free_pct": free_pct, "ts": time.time()}

    def close(self):
        if self._counters is not None:
            self._counters.close()
            self._counters = None


def macos_free_pct() -> float | None:
    """The kernel's own measure of free memory, 0-100 (low = memory pressure)."""
    try:
        out = subprocess.run(["sysctl", "-n", "kern.memorystatus_level"], capture_output=True, text=True, timeout=2)
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def macos_front_app() -> str | None:
    """The app in front, without asking for Automation permission (lsappinfo, not AppleScript)."""
    try:
        asn = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True, timeout=2).stdout.strip()
        if not asn:
            return None
        out = subprocess.run(["lsappinfo", "info", "-only", "executablepath", asn], capture_output=True, text=True,
                             timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    # "LSExecutablePath"="/Applications/Some Game.app/Contents/MacOS/Some Game"
    path = out.split("=", 1)[-1].strip().strip('"')
    return path.rsplit("/", 1)[-1] or None
