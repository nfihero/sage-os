"""Connector layer (A1): agents and model providers come from config, behind one interface."""
import json

import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config, load

H = {"x-sage-os": "1"}


def fake_hermes(home, *, key=True, pinned=True):
    (home / ".env").write_text("API_SERVER_KEY=secret-key-123\n" if key else "", encoding="utf-8")
    (home / "config.yaml").write_text(
        "model:\n  default: qwen-test\n  provider: llamacpp\n" if pinned else "model:\n  provider: auto\n",
        encoding="utf-8")
    (home / "runtimes" / "llamacpp").mkdir(parents=True)
    (home / "runtimes" / "llamacpp" / "server.json").write_text(json.dumps({"api_key": "router-key-456"}))


def make(tmp_path, **kw):
    cfg = Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "index.db", vault_journal=tmp_path / "journal.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db", claude_workspaces=[str(tmp_path)],
                 profile_labels={"default": "Hermes"}, **kw)
    return create_app(cfg, start_adapters=False)


def test_agents_listed_with_capabilities(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        body = c.get("/api/agents").json()
    assert body["lead"] == "claude"
    by_id = {a["id"]: a for a in body["agents"]}
    assert set(by_id) == {"claude", "hermes:default"}
    assert by_id["claude"]["kind"] == "cloud" and "approvals" in by_id["claude"]["capabilities"]
    assert by_id["hermes:default"]["label"] == "Hermes" and by_id["hermes:default"]["profile"] == "default"


def test_agents_can_be_turned_off(tmp_path):
    app = make(tmp_path, claude_enabled=False, hermes_profiles=[])
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/agents").json()["agents"] == []
        assert c.get("/api/state").status_code == 200
        r = c.post("/api/claude/sessions", json={}, headers=H)
        assert r.status_code == 404
    lead = [r for r in app.state.hub.run_smoke() if r["check"] == "lead agent connected"]
    assert lead and not lead[0]["ok"]


def test_generic_routes_reach_the_same_connector(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        s = c.post("/api/agents/claude/sessions", json={"title": "t"}, headers=H).json()
        assert s["cwd"] == str(tmp_path)
        assert c.get(f"/api/agents/claude/sessions/{s['id']}/history").json() == []
        assert c.get(f"/api/claude/sessions/{s['id']}/items").json() == []
        assert c.post("/api/agents/claude/sessions/nope/send", json={"text": "hi"}, headers=H).status_code == 404
        assert c.post("/api/agents/claude/sessions", json={"cwd": str(tmp_path / "nope")}, headers=H).status_code == 400
        assert c.post("/api/agents/ghost/sessions", json={}, headers=H).status_code == 404


def test_hermes_smoke_names_missing_key_and_pin(tmp_path):
    fake_hermes(tmp_path)
    ok = {r["check"]: r["ok"] for r in make(tmp_path).state.hub.run_smoke() if r["adapter"] == "hermes:default"}
    assert ok == {"default API key readable": True, "default model pinned per turn": True}

    bare = tmp_path / "bare"
    bare.mkdir()
    fake_hermes(bare, key=False, pinned=False)
    app = create_app(Config(hermes_home=bare, store=bare / "hub.db", vault=bare / "vault", vault_index=bare / "index.db", vault_journal=bare / "journal.db", sources_root=bare / "sources", sources_index=bare / "sources.db", claude_workspaces=[str(bare)]), start_adapters=False)
    ok = {r["check"]: r["ok"] for r in app.state.hub.run_smoke() if r["adapter"] == "hermes:default"}
    assert ok == {"default API key readable": False, "default model pinned per turn": False}


def test_keys_never_reach_the_browser(tmp_path, monkeypatch):
    fake_hermes(tmp_path)
    monkeypatch.setenv("SAGE_TEST_KEY", "env-key-789")
    app = make(tmp_path, router="http://127.0.0.1:9", model_providers=[
        {"id": "extra", "base_url": "http://127.0.0.1:9/v1", "api_key_env": "SAGE_TEST_KEY"}])
    with TestClient(app, base_url="http://127.0.0.1") as c:
        text = c.get("/api/models").text + c.get("/api/agents").text + c.get("/api/state").text
        providers = {p["id"]: p for p in c.get("/api/models").json()["providers"]}
    for secret in ("secret-key-123", "router-key-456", "env-key-789"):
        assert secret not in text
    assert providers["hermes-router"]["key_present"] is True
    assert providers["extra"]["key_source"] == "env SAGE_TEST_KEY" and providers["extra"]["key_present"] is True
    assert providers["extra"]["models"] == [] and providers["extra"]["error"]    # unreachable, reported


def test_config_parses_agents_and_refuses_inline_keys(tmp_path):
    good = tmp_path / "good.toml"
    good.write_text('[agents]\nlead = "hermes:default"\nclaude = false\nhermes = ["default"]\n\n'
                    '[[models]]\nid = "ollama"\nbase_url = "http://127.0.0.1:11434/v1"\n', encoding="utf-8")
    cfg = load(good)
    assert (cfg.lead_agent, cfg.claude_enabled, cfg.hermes_profiles) == ("hermes:default", False, ["default"])
    assert cfg.model_providers[0]["id"] == "ollama"

    bad = tmp_path / "bad.toml"
    bad.write_text('[[models]]\nid = "x"\nbase_url = "http://h/v1"\napi_key = "sk-oops"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="environment variable"):
        load(bad)


def test_hermes_session_titles_must_be_unique(tmp_path, monkeypatch):
    """Hermes refuses a taken title; the connector numbers it instead of failing every '+ new chat'."""
    import asyncio
    import httpx
    from sage_os_hub.connectors import hermes_api
    taken = {"Sage OS chat"}

    def handler(request):
        title = json.loads(request.content).get("title")
        if title == "boom":
            return httpx.Response(400, json={"error": {"message": "model not configured", "code": "bad"}})
        if title in taken:
            return httpx.Response(400, json={"error": {"message": f"Title already in use by session x", "code": "invalid_title"}})
        taken.add(title)
        return httpx.Response(200, json={"session": {"id": "api_1", "title": title}})
    real = httpx.AsyncClient
    monkeypatch.setattr(hermes_api.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    api = hermes_api.HermesAPI("http://hermes.test", tmp_path)
    assert asyncio.run(api.create_session("default", "Sage OS chat"))["title"] == "Sage OS chat 2"
    assert asyncio.run(api.create_session("default", "Sage OS chat"))["title"] == "Sage OS chat 3"
    with pytest.raises(RuntimeError, match="model not configured"):            # Hermes' own message, not "400"
        asyncio.run(api.create_session("default", "boom"))
