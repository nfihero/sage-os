"""A fresh install's first run, checked on the build machines (F1): `sage-os-hub --self-check OUT [--with-engine]`.

Runs the packaged hub against an empty data folder, the way a new user's first start does, and writes what it found
to OUT as JSON (the bundled app has no console on Windows). It fails (exit 1) when anything a first run needs is
missing: the bundled files, the first-run state (no AI connected, no chats), the OS keychain, the price list, and,
with --with-engine, downloading llama.cpp for this computer and running it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path


def run(out: Path, with_engine: bool) -> int:
    checks: list[dict] = []

    def check(name: str, fn):
        t = time.time()
        try:
            detail = fn()
            checks.append({"check": name, "ok": True, "detail": detail, "s": round(time.time() - t, 1)})
        except Exception as exc:                          # noqa: BLE001 -- every failure is reported
            checks.append({"check": name, "ok": False, "detail": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1500:], "s": round(time.time() - t, 1)})

    data = Path(tempfile.mkdtemp(prefix="sage-os-selfcheck-"))
    os.environ["SAGE_OS_DATA"] = str(data)
    from fastapi.testclient import TestClient

    from . import __version__
    from .app import create_app
    from .config import load

    state: dict = {}

    def start():
        cfg = load()
        state["app"] = create_app(cfg, start_adapters=False)
        state["client"] = TestClient(state["app"], base_url="http://127.0.0.1")
        state["client"].__enter__()
        return {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)), "data": str(cfg.data_dir)}
    check("the hub starts on an empty data folder", start)
    c = state.get("client")
    if c is not None:
        def first_run():
            from .config import ROOT
            if not getattr(sys, "frozen", False) and (ROOT / "config.local.toml").exists():
                return "skipped: running from source with a developer config.local.toml"
            ais = c.get("/api/ais").json()["ais"]
            threads = c.get("/api/threads").json()
            ready = [a for a in ais if a.get("ready") is not False]
            assert not ready, f"a fresh install should have no AI ready, found {[a['label'] for a in ready]}"
            assert threads == [], "a fresh install should have no chats"
            return {"ais": len(ais), "chats": 0}
        check("first run: nothing connected, no chats", first_run)

        def ui():
            r = c.get("/")
            assert r.status_code == 200 and "Sage OS" in r.text, "the UI isn't bundled"
            return "served"
        check("the screen is bundled", ui)

        def catalog():
            e = c.get("/api/engine").json()
            models = [m for m in e.get("catalog", []) if not m.get("micro")]
            assert models, "the model catalog is missing"
            fits = [m["id"] for m in models if m.get("fit") == "fits"]
            return {"models": len(models), "fit_here": fits[:4], "hardware": e.get("hardware")}
        check("the model catalog and this computer's hardware", catalog)

        def pricing():
            p = c.get("/api/pricing").json()
            assert len(p["models"]) > 5, "the price list is missing"
            return {"prices": len(p["models"]), "as_of": p["as_of"]}
        check("the price list", pricing)

        def keychain():
            import keyring
            kr = keyring.get_keyring()
            name = type(kr).__name__
            assert "fail" not in name.lower() and "null" not in name.lower(), f"no OS keychain backend ({name})"
            kr.get_password("Sage OS self-check", "none")
            return name
        check("the OS keychain", keychain)

        def pairing_key():
            k = state["app"].state.hub.device_key
            assert k is not None, "this device made no pairing key"
            from .sync.devicekey import DeviceKey
            assert DeviceKey.verify(k.public_b64, k.sign(b"self-check"), b"self-check"), "the pairing key can't sign"
            return k.fingerprint
        check("this device's pairing key (in the keychain)", pairing_key)

        def sync_listener():
            hub = state["app"].state.hub
            hub.sync.host, hub.sync.port, hub.sync.mdns = "127.0.0.1", 0, False      # this computer only, for the check
            r = c.post("/api/devices/pairing", headers={"X-Sage-OS": "1"})
            assert r.status_code == 200 and r.json()["listening"], f"the sync listener didn't open: {r.text[:200]}"
            from .sync.listener import Peer
            p = Peer(f"127.0.0.1:{hub.sync.bound}", expect_key=hub.device_key.public_b64)   # TLS + the signed hello
            p.close()
            port = hub.sync.bound
            c.post("/api/devices/pairing/cancel", headers={"X-Sage-OS": "1"})
            assert hub.sync.task is None, "the sync listener stayed open after the pairing was cancelled"
            return {"port": port, "tls": p.tls_fpr[:16], "closed_after": True}
        check("the sync listener opens and proves who it is", sync_listener)

        def report():
            text = c.post("/api/report/preview", json={"description": "self-check"}, headers={"X-Sage-OS": "1"}).json()["text"]
            assert "SAGE OS PROBLEM REPORT" in text
            return text.splitlines()[11:16]
        check("a problem report can be made", report)

        if with_engine:
            def engine():
                hub = state["app"].state.hub
                hub.engine.install_binary()
                job = hub.engine.jobs.get("binary")
                assert job and job.state == "done", f"llama.cpp didn't install: {job and job.error}"
                b = hub.engine.binary()
                r = subprocess.run([str(b), "--version"], capture_output=True, text=True, timeout=60)
                line = (r.stdout + r.stderr).strip().splitlines()
                assert r.returncode == 0, f"llama-server didn't run: {line[-3:]}"
                return {"binary": b.name, "version": [x for x in line if "version" in x.lower()][:1]}
            check("llama.cpp downloads and runs here", engine)
        state["client"].__exit__(None, None, None)

    import logging
    import shutil
    if state.get("app") is not None:              # the throwaway install's own secrets leave this computer's keychain
        hub = state["app"].state.hub
        hub.keys.delete(f"device-key:{hub.device.id}")
    logging.shutdown()                                     # let go of the temporary folder's files, then remove it
    shutil.rmtree(data, ignore_errors=True)
    ok = all(x["ok"] for x in checks)
    out.write_text(json.dumps({"ok": ok, "platform": sys.platform, "checks": checks}, indent=2), encoding="utf-8")
    return 0 if ok else 1
