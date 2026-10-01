"""GPU lane and service health: llama.cpp router, guardian sidecar, Hermes gateway, nvidia-smi."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from .base import Adapter

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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


def nvidia_smi() -> dict | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    out = subprocess.run(
        [exe, "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
         "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
        creationflags=NO_WINDOW).stdout.strip().splitlines()
    if not out:
        return None
    name, used, total, util, temp, power = [p.strip() for p in out[0].split(",")]

    def num(x):
        try:
            return float(x)
        except ValueError:
            return None
    return {"name": name, "vram_used_mb": num(used), "vram_total_mb": num(total),
            "util_pct": num(util), "temp_c": num(temp), "power_w": num(power)}


class GpuAdapter(Adapter):
    name = "gpu"

    def __init__(self, emit, cfg):
        super().__init__(emit)
        self.cfg, self.interval = cfg, cfg.poll["gpu"]
        self._loaded: tuple | None = None

    def smoke(self):
        info = router_info(self.cfg.hermes_home)
        return [("router server.json readable", bool(info.get("api_key")), "ok" if info else "missing"),
                ("nvidia-smi on PATH", shutil.which("nvidia-smi") is not None, "")]

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
        gpu = nvidia_smi()
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


class HealthAdapter(Adapter):
    name = "health"

    def __init__(self, emit, cfg):
        super().__init__(emit)
        self.cfg, self.interval = cfg, cfg.poll["health"]
        self._state: dict[str, bool] = {}
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
