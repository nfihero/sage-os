"""D40: API keys connected in the app (OS keychain), tokens recorded per reply, a dated price list with the user's
corrections, and spend."""
import datetime as dt
import sqlite3
import threading

import httpx
import pytest

from sage_os_hub.usage import Usage
from test_engine import H, chat, wait_idle  # noqa: F401  (a hub with a stand-in local model)


@pytest.fixture
def u():
    return Usage(sqlite3.connect(":memory:", check_same_thread=False), threading.Lock())


def ts(day: str) -> float:
    return dt.datetime.fromisoformat(day + "T12:00:00").timestamp()


def test_prices_match_the_longest_prefix_and_dated_changes(u):
    assert u.price("openai", "gpt-5.4-mini")["in"] == 0.75 and u.price("openai", "gpt-5.4")["in"] == 2.50
    assert u.price("openai", "gpt-5.4-2026-03-05")["match"] == "gpt-5.4"                    # dated ids
    assert u.price("gemini", "models/gemini-3.8-flash", ts("2026-10-14"))["in"] == 0.75
    assert u.price("gemini", "gemini-3.8-flash", ts("2027-01-02"))["in"] == 1.50            # the announced rise
    assert u.price("claude", "claude-opus-4-8")["in"] == 5.00 and u.price("openai", "mystery-model") is None
    u.set_price("openai", "gpt-5.4", 3.0, 16.0)
    assert u.price("openai", "gpt-5.4")["source"] == "yours" and u.price("openai", "gpt-5.4")["in"] == 3.0
    u.reset_price("openai", "gpt-5.4")
    assert u.price("openai", "gpt-5.4")["source"] == "list"
    with pytest.raises(ValueError):
        u.set_price("openai", "x", -1, 2)


def test_recorded_replies_are_billed_by_kind(u):
    api = u.record("chat", "openai", "gpt-5.4-mini", "chat:a", 1_000_000, 100_000)
    assert api["billing"] == "api" and api["cost"] == pytest.approx(0.75 + 0.45)
    free = u.record("chat", "engine", "gemma", "chat:b", 5000, 900)
    assert free["billing"] == "free" and free["cost"] == 0
    plan = u.record("claude", None, None, "claude:c", 20000, 3000, cost=0.42)
    assert plan["billing"] == "plan" and plan["cost"] == 0.42                                # Claude Code's own figure
    unknown = u.record("chat", "openai", "mystery-model", "chat:d", 10, 10)
    assert unknown["cost"] is None
    s = u.summary()
    assert s["spent"]["today"] == pytest.approx(1.2)                                          # only API keys cost money
    by = {(a["agent"], a["model"]): a for a in s["ais"]}
    assert by[("chat", "gpt-5.4-mini")]["today"]["tokens_in"] == 1_000_000 and by[("chat", "mystery-model")]["unpriced"]
    assert by[("claude", None)]["billing"] == "plan" and by[("chat", "gemma")]["price"] is None
    t = u.for_chats(["chat:a", "claude:c"])
    assert t["cost"] == pytest.approx(1.2) and t["plan_value"] == 0.42 and t["tokens_in"] == 1_020_000


def test_rate_limit_headers_are_kept(u):
    u.note_limits("openai", {"x-ratelimit-remaining-tokens": "149000", "x-ratelimit-limit-tokens": "150000"})
    assert u.limits["openai"]["remaining_tokens"] == "149000"
    u.note_limits("gemini", {})
    assert "gemini" not in u.limits


def test_a_chat_turn_records_its_tokens(chat):
    hub, client, rounds = chat
    t = client.post("/api/threads", json={"agent": "chat", "provider": "engine", "model": "qwen"}, headers=H).json()
    client.post(f"/api/threads/{t['id']}/send", json={"text": "What is enterprise value in my DCF notes?"}, headers=H)
    wait_idle(hub, t["parts"][0]["sid"])
    assert rounds[0]["stream_options"] == {"include_usage": True}
    full = client.get(f"/api/threads/{t['id']}").json()
    assert full["usage"]["tokens_in"] > 0 and full["usage"]["estimated"]           # the stand-in reports nothing
    assert full["usage"]["cost"] == 0 and full["usage"]["billing"] == ["free"]
    s = client.get("/api/usage").json()
    assert s["ais"][0]["agent"] == "chat" and s["ais"][0]["billing"] == "free"


def test_connect_a_key_tests_it_and_keeps_it_in_the_keychain(chat, monkeypatch, memory_keychain):
    hub, client, rounds = chat
    seen = []

    def models(request):
        seen.append(request.headers.get("authorization"))
        ok = request.headers.get("authorization") == "Bearer sk-good-key-0123456789abcdef"
        return httpx.Response(200 if ok else 401, json={"data": [{"id": "gpt-5.4-mini"}]} if ok else {"error": "bad"})
    real = httpx._client.AsyncClient                    # the chat fixture already patched httpx.AsyncClient
    monkeypatch.setattr("sage_os_hub.app.httpx.AsyncClient",
                        lambda **kw: real(**{**kw, "transport": httpx.MockTransport(models)}))
    assert client.post("/api/connections/openai", json={"key": "sk-good-key-0123456789abcdef"}).status_code == 403
    assert client.post("/api/connections/openai", json={"key": "not a key"}, headers=H).status_code == 400
    r = client.post("/api/connections/openai", json={"key": "sk-wrong-key-0123456789abcdef"}, headers=H)
    assert r.status_code == 400 and "didn't accept" in r.text and "openai" not in hub.providers
    r = client.post("/api/connections/openai", json={"key": "sk-good-key-0123456789abcdef"}, headers=H)
    assert r.status_code == 200 and r.json()["models"] == 1
    assert memory_keychain.get_password("Sage OS", "openai") == "sk-good-key-0123456789abcdef"
    assert hub.providers["openai"].key() == "sk-good-key-0123456789abcdef"
    listing = client.get("/api/connections").json()
    openai = next(c for c in listing["cloud"] if c["id"] == "openai")
    assert openai["connected"] and openai["key_source"] == "keychain" and "sk-good" not in str(listing)
    client.post("/api/connections/openai/remove", headers=H)
    assert "openai" not in hub.providers and memory_keychain.get_password("Sage OS", "openai") is None
    assert client.post("/api/connections/nope", json={"key": "x" * 30}, headers=H).status_code == 404


def test_price_corrections_through_the_api(chat):
    hub, client, rounds = chat
    r = client.post("/api/pricing", json={"provider": "gemini", "model": "gemini-3.8-flash", "in_price": 0.5, "out_price": 3}, headers=H)
    row = next(m for m in r.json()["models"] if m["model"] == "gemini-3.8-flash")
    assert row["yours"]["in"] == 0.5
    r = client.post("/api/pricing/reset", json={"provider": "gemini", "model": "gemini-3.8-flash"}, headers=H)
    assert next(m for m in r.json()["models"] if m["model"] == "gemini-3.8-flash")["yours"] is None
    assert client.post("/api/pricing", json={"provider": "x", "model": "y", "in_price": -2}, headers=H).status_code == 400


def test_a_correction_covers_dated_model_ids_too(u):
    u.set_price("openai", "gpt-5.4", 3.0, 16.0)
    assert u.price("openai", "gpt-5.4-2026-03-05")["source"] == "yours"          # the id the API reports
    assert u.price("openai", "gpt-5.4-mini")["source"] == "list"                  # a closer list entry still wins
    u.set_price("gemini", "models/gemini-3.8-flash", 0.5, 3)
    assert u.price("gemini", "gemini-3.8-flash")["in"] == 0.5


def test_a_server_that_refuses_the_usage_option_is_asked_without_it(monkeypatch):
    import asyncio
    import json as _json
    from sage_os_hub.connectors import chat as chatmod
    from sage_os_hub.connectors.chat import ChatConnector
    from sage_os_hub.connectors.models import ModelProvider
    seen = []

    def handler(request):
        body = _json.loads(request.content)
        seen.append(body)
        if "stream_options" in body:
            return httpx.Response(400, json={"error": "unknown field stream_options"})
        return httpx.Response(200, text='data: {"choices": [{"delta": {"content": "hello there"}}]}\n\ndata: [DONE]\n\n')
    real = httpx._client.AsyncClient
    monkeypatch.setattr("sage_os_hub.connectors.chat.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(chatmod, "NO_USAGE", set())
    conn = ChatConnector.__new__(ChatConnector)
    conn.hub, conn.tasks = None, {}
    spent = {"in": 0, "out": 0, "estimated": False}
    p = ModelProvider("old", "Old server", "http://127.0.0.1:1/v1", "local", None, lambda: None)
    text, _ = asyncio.run(conn._complete(p, "m", [{"role": "user", "content": "hi" * 40}], None, spent))
    assert text == "hello there" and len(seen) == 2 and "stream_options" not in seen[1]
    assert spent["estimated"] and spent["in"] == 20 and "old" in chatmod.NO_USAGE


def test_a_key_does_not_replace_a_service_set_in_config(chat):
    hub, client, rounds = chat
    hub.providers["openai"] = hub.cloud_provider("openai")
    hub.providers["openai"].key_source = "env:OPENAI_API_KEY"
    r = client.post("/api/connections/openai", json={"key": "sk-good-key-0123456789abcdef"}, headers=H)
    assert r.status_code == 400 and "config.local.toml" in r.text
