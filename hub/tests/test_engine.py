"""Local engine (D22.3) and the OpenAI-compatible model chat (D22.2)."""
import asyncio
import hashlib
import io
import json
import tarfile
import time
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from sage_os_hub import engine as eng
from sage_os_hub.app import create_app
from sage_os_hub.engine import EngineError, LocalEngine, fit, pick_asset, safe_extract

from test_agent_tools import cfg, seed

H = {"x-sage-os": "1"}
GB = 2**30
NVIDIA = {"os": "windows", "arch": "amd64", "ram_gb": 31.0, "backend": "cuda",
          "gpu": {"vendor": "nvidia", "name": "RTX", "vram_gb": 15.9, "driver": "617.42"}}
LAPTOP = {"os": "windows", "arch": "amd64", "ram_gb": 8.0, "backend": "vulkan", "gpu": None}
MAC = {"os": "macos", "arch": "arm64", "ram_gb": 16.0, "backend": "metal", "gpu": {"vendor": "apple", "vram_gb": 16.0}}


def test_fit_depends_on_the_machine():
    assert fit(3 * GB, LAPTOP)[0] == "fits"            # a 4B model on a laptop
    assert fit(12 * GB, LAPTOP)[0] == "too big"
    assert fit(12 * GB, NVIDIA)[0] == "fits"
    assert fit(22 * GB, NVIDIA)[0] == "tight"          # runs, partly on the CPU
    assert fit(7 * GB, MAC)[0] == "fits" and fit(14 * GB, MAC)[0] == "too big"


def test_pick_asset_per_platform():
    names = ["llama-b1-bin-win-cuda-13.4-x64.zip", "cudart-llama-bin-win-cuda-13.4-x64.zip", "llama-b1-bin-win-vulkan-x64.zip",
             "llama-b1-bin-macos-arm64.tar.gz", "llama-b1-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"]
    assets = [{"name": n} for n in names]
    assert [a["name"] for a in pick_asset(assets, "b1", NVIDIA)] == names[:2]
    old = {**NVIDIA, "gpu": {**NVIDIA["gpu"], "driver": "551.0"}}
    assert [a["name"] for a in pick_asset(assets, "b1", old)] == names[4:]
    assert [a["name"] for a in pick_asset(assets, "b1", LAPTOP)] == ["llama-b1-bin-win-vulkan-x64.zip"]
    assert [a["name"] for a in pick_asset(assets, "b1", MAC)] == ["llama-b1-bin-macos-arm64.tar.gz"]
    assert pick_asset(assets[:1], "b1", NVIDIA) == []    # no runtime -> not this release


def test_safe_extract_refuses_escaping_paths(tmp_path):
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../evil.txt", "x")
    with pytest.raises(EngineError):
        safe_extract(z, tmp_path / "out")
    t = tmp_path / "ok.tar.gz"
    with tarfile.open(t, "w:gz") as f:
        data = b"#!/bin/sh\n"
        info = tarfile.TarInfo("build/bin/llama-server")
        info.size = len(data)
        f.addfile(info, io.BytesIO(data))
    safe_extract(t, tmp_path / "out")
    assert (tmp_path / "out" / "build" / "bin" / "llama-server").exists()


def test_model_download_resumes_and_checks_the_hash(tmp_path, monkeypatch):
    blob = b"GGUF" + b"x" * 5000
    e = LocalEngine(tmp_path)
    monkeypatch.setattr(e, "catalog", lambda: [{"id": "tiny", "label": "Tiny", "repo": "r", "file": "tiny.gguf",
                                               "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}])
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "tiny.gguf.part").write_bytes(blob[:1000])      # an interrupted download
    seen = {}

    class Resp:
        def __init__(self, start):
            self.status_code, self.start = 206, start
            self.headers = {"content-length": str(len(blob) - start)}

        def iter_bytes(self, n):
            yield blob[self.start:]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def stream(method, url, headers=None, **kw):
        seen["range"] = headers.get("Range")
        return Resp(int(headers["Range"].split("=")[1].rstrip("-")))
    monkeypatch.setattr(eng.httpx, "stream", stream)
    e.download_model("tiny")
    assert seen["range"] == "bytes=1000-" and e.jobs["model:tiny"].state == "done"
    assert (tmp_path / "models" / "tiny.gguf").read_bytes() == blob

    monkeypatch.setattr(e, "catalog", lambda: [{"id": "tiny", "label": "Tiny", "repo": "r", "file": "bad.gguf",
                                               "size": len(blob), "sha256": "0" * 64}])
    (tmp_path / "models" / "bad.gguf.part").write_bytes(blob[:1000])
    e.download_model("tiny")
    assert e.jobs["model:tiny"].state == "failed" and "checksum" in e.jobs["model:tiny"].error
    assert not (tmp_path / "models" / "bad.gguf").exists() and not (tmp_path / "models" / "bad.gguf.part").exists()


def test_orphan_reaped_only_if_it_is_llama_server(tmp_path, monkeypatch):
    e = LocalEngine(tmp_path)
    (tmp_path / "server.pid").write_text("4242")
    killed = []

    class P:
        def __init__(self, pid, name):
            self.pid, self._name = pid, name

        def name(self):
            return self._name

        def terminate(self):
            killed.append(self.pid)

        def wait(self, t):
            pass
    monkeypatch.setattr(eng.psutil, "Process", lambda pid: P(pid, "python.exe"))
    assert e.reap_orphan() is None and killed == []          # the pid was reused by something else: left alone
    (tmp_path / "server.pid").write_text("4242")
    monkeypatch.setattr(eng.psutil, "Process", lambda pid: P(pid, eng.EXE))
    assert e.reap_orphan() == 4242 and killed == [4242] and not (tmp_path / "server.pid").exists()


def test_engine_starts_locked_down(tmp_path, monkeypatch):
    """llama-server answers any web page by default; Sage OS starts it with a per-start key (in the
    environment, not the command line), no web UI and no CORS origin."""
    binp = tmp_path / "bin" / eng.EXE
    binp.parent.mkdir(parents=True)
    binp.write_bytes(b"")
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "x.gguf").write_bytes(b"GGUF")
    seen = {}

    class FakeProc:
        pid = 1

        def poll(self):
            return None

    def popen(args, env=None, **kw):
        seen["args"], seen["env"] = args, env
        return FakeProc()
    monkeypatch.setattr(eng.subprocess, "Popen", popen)
    e = LocalEngine(tmp_path / "engine", binary=str(binp), model_dirs=[tmp_path / "m"])
    monkeypatch.setattr(e, "hardware", lambda refresh=False: NVIDIA)
    e.start("file:x")
    key = seen["env"]["LLAMA_API_KEY"]
    assert len(key) > 30 and key == e.api_key and key not in " ".join(seen["args"])
    assert "--no-webui" in seen["args"] and seen["args"][seen["args"].index("--cors-origins") + 1] != "*"
    assert seen["args"][seen["args"].index("--host") + 1] == "127.0.0.1"


def test_install_refuses_a_build_without_a_checksum(tmp_path, monkeypatch):
    e = LocalEngine(tmp_path)
    monkeypatch.setattr(e, "hardware", lambda refresh=False: LAPTOP)
    rel = [{"tag_name": "b1", "assets": [{"name": "llama-b1-bin-win-vulkan-x64.zip", "browser_download_url": "u", "size": 1}]}]
    monkeypatch.setattr(eng.httpx, "get", lambda *a, **k: httpx.Response(200, json=rel))
    e.install_binary()
    assert e.jobs["binary"].state == "failed" and "SHA-256" in e.jobs["binary"].error


def test_local_models_found_and_start_needs_a_binary(tmp_path):
    d = tmp_path / "elsewhere"
    d.mkdir()
    (d / "my-model-Q4.gguf").write_bytes(b"GGUF")
    (d / "mmproj-x.gguf").write_bytes(b"GGUF")
    e = LocalEngine(tmp_path / "engine", model_dirs=[d])
    assert [m["id"] for m in e.local_models()] == ["file:my-model-Q4"]
    with pytest.raises(EngineError, match="isn't installed"):
        e.start("file:my-model-Q4")


# -- the model chat --------------------------------------------------------------------------------
def sse(*chunks):
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


@pytest.fixture
def chat(tmp_path, monkeypatch):
    c = cfg(tmp_path, claude_enabled=False, hermes_profiles=[], engine_root=tmp_path / "engine")
    app = create_app(c, start_adapters=False)
    seed(tmp_path / "vault")
    hub = app.state.hub
    rounds = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        rounds.append(body)
        if len(rounds) == 1:     # first round: the model searches the notes
            return httpx.Response(200, text=sse(
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "search_notes", "arguments": ""}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\"query\": \"discounted\"}"}}]}}]}))
        return httpx.Response(200, text=sse({"choices": [{"delta": {"content": "Enterprise value is the sum of "}}]},
                                            {"choices": [{"delta": {"content": "discounted free cash flows."}}]}))
    real = httpx.AsyncClient
    monkeypatch.setattr("sage_os_hub.connectors.chat.httpx.AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield hub, client, rounds


def wait_idle(hub, sid):
    for _ in range(100):
        if not hub.agents["chat"].busy(sid):
            return
        time.sleep(0.05)


def test_chat_runs_the_tool_loop_and_keeps_the_transcript(chat):
    hub, client, rounds = chat
    assert client.post("/api/agents/chat/sessions", json={"provider": "nope", "model": "m"}, headers=H).status_code == 400
    s = client.post("/api/agents/chat/sessions", json={"provider": "engine", "model": "qwen"}, headers=H).json()
    r = client.post(f"/api/agents/chat/sessions/{s['id']}/send", json={"text": "What is enterprise value in my DCF notes?"}, headers=H)
    assert r.status_code == 200 and r.json()["briefing"]["items"][0]["title"] == "DCF formula sheet"
    wait_idle(hub, s["id"])
    kinds = [i["kind"] for i in client.get(f"/api/agents/chat/sessions/{s['id']}/history").json()]
    assert kinds == ["user", "tool_use", "tool_result", "text", "note"]
    assert rounds[0]["tools"] and rounds[0]["messages"][0]["role"] == "system"
    assert "⟦Sage OS reading pack⟧" in rounds[0]["messages"][-1]["content"]          # the pack went to the model
    assert rounds[1]["messages"][-1]["role"] == "tool" and "DCF formula sheet" in rounds[1]["messages"][-1]["content"]
    items = hub.store.chat_items(s["id"])
    assert items[0]["data"]["text"] == "What is enterprise value in my DCF notes?"      # the transcript shows what was typed
    assert hub.store.chat_session(s["id"])["title"].startswith("What is enterprise value")
