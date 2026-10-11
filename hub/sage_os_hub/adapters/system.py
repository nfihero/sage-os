"""GPU lane and service health: llama.cpp router, guardian sidecar, Hermes gateway, graphics cards (any vendor)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ..hardware import Probe, gpus
from .base import Adapter



def http_json(url: str, key: str | None = None, timeout: float = 2.0):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"} if key else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    try:
        return r.status, json.loads(body)
    except ValueError:
        return r.status, body.decode(errors="replace")


def router_info(hermes_home) -> dict:
    """server.json is Hermes' record of the managed router (read-only): url, key, pid."""
    try:
        return json.loads((hermes_home / "runtimes" / "llamacpp" / "server.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _arg(args: list[str], *flags: str):
    for i, a in enumerate(args):
        if a in flags and i + 1 < len(args):
            return args[i + 1]
    return None


def summarize_model(m: dict) -> dict:
    st = m.get("status") or {}
    args = st.get("args") or []
    return {"id": m.get("id"), "state": st.get("value", "unknown"),
            "ctx": _arg(args, "--ctx-size", "-c"),
            "n_cpu_moe": _arg(args, "--n-cpu-moe"),
            "offload": _arg(args, "--override-tensor", "-ot")}


def ram() -> dict | None:
    """System RAM, plus what llama.cpp holds in RAM (the CPU-offloaded experts live here)."""
    try:
        import psutil
    except ImportError:
        return None
    vm = psutil.virtual_memory()
    llama = 0
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (p.info["name"] or "").lower()
            rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
        except (psutil.Error, AttributeError):
            continue
        if name.startswith("llama-server"):
            llama += rss
    gb = 1024 ** 3
    return {"total_gb": vm.total / gb, "used_gb": (vm.total - vm.available) / gb,
            "llama_gb": llama / gb, "pct": vm.percent}


def gpu_lane(reading: dict) -> dict | None:
    """The main graphics card's memory and activity from a hardware reading (any vendor; G1). Temperature and
    power aren't available the same way for every vendor, so they're left out."""
    cards = reading.get("adapters") or []
    if not cards:
        return None
    g = cards[0]
    busy = [p["busy"] for p in reading.get("programs", []) if p.get("adapter") == g.get("luid") and p.get("busy") is not None]
    return {"name": g["name"], "vram_used_mb": g.get("used_bytes", 0) / 2**20, "vram_total_mb": g["vram_bytes"] / 2**20,
            "util_pct": round(max(busy)) if busy else 0, "temp_c": None, "power_w": None}


class GpuAdapter(Adapter):
    name = "gpu"

    def __init__(self, emit, cfg):
        super().__init__(emit)
        self.cfg, self.interval = cfg, cfg.poll["gpu"]
        self._loaded: tuple | None = None
        self._probe = None

    def _gpu(self) -> dict | None:
        if self._probe is None:
            self._probe = Probe()
        return gpu_lane(self._probe.read())

    def smoke(self):
        info = router_info(self.cfg.hermes_home)
        return [("router server.json readable", bool(info.get("api_key")), "ok" if info else "missing"),
                ("graphics cards readable", True, ", ".join(g["name"] for g in gpus()) or "none found (models run on the CPU)")]

    def poll(self):
        info = router_info(self.cfg.hermes_home)
        models, err = [], None
        try:
            _, body = http_json(f"{self.cfg.router}/models", info.get("api_key"))
            models = [summarize_model(m) for m in body.get("data", [])]
        except (urllib.error.URLError, OSError, AttributeError) as exc:
            err = str(exc)
        guardian = []
        try:
            _, body = http_json(f"{self.cfg.sidecar}/models")
            guardian = [summarize_model(m) for m in body.get("data", [])]
        except (urllib.error.URLError, OSError, AttributeError):
            pass
        active = [m for m in models if m["state"] in ("loaded", "loading")]
        gpu = self._gpu()
        self.emit.panel("gpu", {"gpu": gpu, "ram": ram(), "models": models, "active": active,
                                "guardian": guardian, "router_error": err,
                                "router_pid": info.get("pid"), "ts": time.time()})
        key = tuple((m["id"], m["state"]) for m in active)
        if key != self._loaded:
            if self._loaded is not None:
                self.emit.event("system", self.name, "gpu.model",
                                {"active": [dict(zip(("id", "state"), k)) for k in key],
                                 "previous": [dict(zip(("id", "state"), k)) for k in self._loaded]})
            self._loaded = key


def hermes_installed(cfg) -> bool:
    """Hermes is optional (D22): is it on this computer at all?"""
    try:
        return cfg.hermes_home.is_dir()
    except OSError:
        return False


class HealthAdapter(Adapter):
    name = "health"

    def __init__(self, emit, cfg):
        super().__init__(emit)
        self.cfg, self.interval = cfg, cfg.poll["health"]
        self._state: dict[str, bool] = {}
        self._seen: set[str] = set()          # services seen up since the hub started
        self._router_pid = None

    def _check(self, url):
        t = time.perf_counter()
        try:
            status, body = http_json(url, timeout=1.5)
            return {"up": status == 200, "ms": round((time.perf_counter() - t) * 1000),
                    "version": body.get("version") if isinstance(body, dict) else None}
        except (urllib.error.URLError, OSError) as exc:
            return {"up": False, "ms": None, "error": str(getattr(exc, "reason", exc))}

    def poll(self):
        services = {"gateway": self._check(f"{self.cfg.gateway}/health"),
                    "router": self._check(f"{self.cfg.router}/health"),
                    "sidecar": self._check(f"{self.cfg.sidecar}/health")}
        pid = router_info(self.cfg.hermes_home).get("pid")
        restarted = self._router_pid is not None and pid and pid != self._router_pid
        if pid:
            self._router_pid = pid
        services["router"]["pid"] = pid
        installed = hermes_installed(self.cfg)
        for name, svc in services.items():
            if svc["up"]:
                self._seen.add(name)
            # D22.1: something never set up reads "not set up", something not started "off"; red ("down")
            # only when it was running earlier and stopped
            svc["state"] = ("up" if svc["up"] else "down" if name in self._seen
                            else "off" if installed else "absent")
        self.emit.panel("health", services)
        for name, s in services.items():
            prev = self._state.get(name)
            if prev is not None and prev != s["up"]:
                self.emit.event("system", self.name, "health.up" if s["up"] else "health.down",
                                {"service": name, **s})
            self._state[name] = s["up"]
        # The supervisor respawns the router in ~3 s, faster than a poll can see it down.
        if restarted and services["router"]["up"]:
            self.emit.event("system", self.name, "health.restarted", {"service": "router", "pid": pid})
