"""W3 / D39: a fresh install connects nothing; the first screen installs and starts a model in one click, connects
Claude Code on request, finds Ollama by itself; the app's own helpers fetch themselves."""
import asyncio
import tomllib

import pytest
from fastapi.testclient import TestClient

from sage_os_hub import config
from sage_os_hub.app import create_app
from sage_os_hub.config import Config

from test_agent_tools import cfg

H = {"x-sage-os": "1"}


def test_the_shipped_config_connects_no_agent():
    shipped = tomllib.loads((config.ROOT / "config.toml").read_text(encoding="utf-8"))
    agents = shipped.get("agents", {})
    assert not agents.get("claude") and not agents.get("hermes") and not agents.get("lead")
    c = Config()
    assert (c.claude_enabled, c.hermes_profiles, c.lead_agent) == (False, [], "")


@pytest.fixture
def env(tmp_path):
    c = cfg(tmp_path, hermes_profiles=[], engine_enabled=False)
    c.hermes_home = tmp_path / "no-hermes"                                 # a computer without Hermes
    app = create_app(c, start_adapters=False)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield app.state.hub, client


def test_fresh_install_passes_its_checks_with_nothing_connected(env):
    hub, client = env
    bad = [(r["adapter"], r["check"], r["detail"]) for r in hub.run_smoke() if not r["ok"]]
    assert sorted(hub.agents) == ["chat"] and bad == []


def test_connect_claude_from_the_chat_space(env, monkeypatch):
    hub, client = env
    from sage_os_hub.connectors import claude as claude_mod
    monkeypatch.setattr(claude_mod, "find_cli", lambda: None)              # no CLI here: connected, not signed in
    assert client.post("/api/agents/claude/connect").status_code == 403
    r = client.post("/api/agents/claude/connect", headers=H).json()
    assert r["connected"] is True and "claude" in hub.agents
    saved = tomllib.loads(hub.cfg.local_config.read_text(encoding="utf-8"))
    assert saved["agents"]["claude"] is True                               # remembered for next start
    assert any(a["agent"] == "claude" for a in client.get("/api/ais").json()["ais"])
    assert client.post("/api/agents/claude/connect", headers=H).status_code == 200      # twice is fine


class FakeEngine:
    def __init__(self):
        self.calls, self.bin, self.models, self.serving, self.jobs = [], None, set(), None, {}

    def binary(self):
        return self.bin

    def install_binary(self):
        self.calls.append("install")
        self.bin = "llama-server.exe"

    def catalog(self):
        return [{"id": "small", "label": "Small", "installed": "small" in self.models}]

    def download_model(self, mid):
        self.calls.append(f"download {mid}")
        self.models.add(mid)

    def start(self, mid, small=False):
        self.calls.append(f"start {mid}")
        self.serving = {"id": mid, "ready": False}

    def check_ready(self):
        self.serving["ready"] = True
        return True

    def status(self):
        return {"serving": self.serving}

    def stop(self):
        pass


def test_install_and_start_in_one_click(env):
    hub, client = env
    hub.engine = FakeEngine()
    asyncio.run_coroutine_threadsafe(hub.setup_model("small"), hub.loop).result()
    assert hub.engine.calls == ["install", "download small", "start small"]
    assert hub.setup_state == {"model": "small", "step": "ready", "error": None}
    hub.engine.calls.clear()
    asyncio.run_coroutine_threadsafe(hub.setup_model("small"), hub.loop).result()      # already here: just start
    assert hub.engine.calls == ["start small"]


def test_a_failed_setup_says_why(env):
    hub, client = env
    hub.engine = FakeEngine()
    hub.engine.install_binary = lambda: None                                # the download didn't produce a binary
    asyncio.run_coroutine_threadsafe(hub.setup_model("small"), hub.loop).result()
    assert hub.setup_state["error"] and hub.setup_state["step"] == "engine"


def test_ollama_running_here_becomes_a_provider(env, monkeypatch):
    hub, client = env
    import httpx
    real = httpx.AsyncClient
    monkeypatch.setattr("sage_os_hub.app.httpx.AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": []})), **kw))
    asyncio.run_coroutine_threadsafe(hub.find_ollama(), hub.loop).result()
    assert hub.providers["ollama"].base_url == "http://127.0.0.1:11434/v1"


def test_ollama_not_running_changes_nothing(env, monkeypatch):
    hub, client = env
    import httpx
    real = httpx.AsyncClient

    def refuse(request):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr("sage_os_hub.app.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(refuse), **kw))
    asyncio.run_coroutine_threadsafe(hub.find_ollama(), hub.loop).result()
    assert "ollama" not in hub.providers


def test_the_search_helper_fetches_itself(env):
    hub, client = env

    class Embed:
        def __init__(self):
            self.calls, self.jobs = [], {}

        def binary(self):
            return None

        def claim(self, *a):
            self.calls.append(("claim",) + a)

        def download(self):
            self.calls.append("download")

        def stop(self):
            pass

    class Main:
        def __init__(self):
            self.calls = []

        def claim(self, *a):
            self.calls.append("claim")

        def install_binary(self):
            self.calls.append("install")

        def stop(self):
            pass

    hub.engine, hub.semantic.engine = Main(), Embed()
    asyncio.run_coroutine_threadsafe(hub.semantic.fetch_helpers(), hub.loop).result()
    assert hub.engine.calls == ["claim", "install"] and "download" in hub.semantic.engine.calls
