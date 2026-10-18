"""D42, from the first Mac test: cloud model lists cut to chat models with readable names, thinking text hidden,
cut-off replies said plainly, and no kanban noise without Hermes."""
import json

import httpx

from sage_os_hub import modelnames
from sage_os_hub.adapters.kanban import KanbanAdapter
from sage_os_hub.connectors.chat import ThinkFilter
from test_engine import H, chat, sse, wait_idle  # noqa: F401

GEMINI = ["models/gemini-2.5-flash", "models/gemini-2.5-pro", "models/gemini-2.5-flash-preview-tts",
          "models/gemini-2.5-pro-preview-tts", "models/gemini-2.5-flash-image", "models/nano-banana-pro-preview",
          "models/lyria-realtime-exp", "models/gemini-robotics-er-1.5-preview", "models/gemini-2.5-computer-use-preview-10-2025",
          "models/gemma-4-31b-it", "models/gemini-2.5-flash-lite", "models/gemini-embedding-001",
          "models/gemini-2.5-flash-native-audio-latest", "models/gemini-live-2.5-flash-preview"]


def test_only_chat_models_with_the_best_known_first():
    rows = modelnames.arrange("gemini", GEMINI, ["gemini-3.8-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite", "gemini-2.5-flash"])
    ids = [r["id"] for r in rows]
    assert ids == ["models/gemini-2.5-pro", "models/gemini-2.5-flash-lite", "models/gemini-2.5-flash", "models/gemma-4-31b-it"]
    assert [r["name"] for r in rows][:1] == ["Gemini 2.5 Pro"] and rows[-1]["name"] == "Gemma 4 31B IT"
    assert rows[0]["first"] and not rows[-1]["first"] and rows[2]["note"] == "fast, low cost, has a free tier"
    assert modelnames.describe("models/gemini-2.5-pro", "gemini").startswith("the best")     # "gemini" isn't "mini"
    assert modelnames.friendly("gpt-5.4-mini") == "GPT-5.4 mini"
    assert not modelnames.is_chat("gpt-4o-mini-tts") and not modelnames.is_chat("gpt-image-1") and modelnames.is_chat("o3")


def test_the_ai_list_offers_a_cloud_service_s_chat_models_only(chat, monkeypatch):
    hub, client, rounds = chat
    from sage_os_hub.connectors.models import ModelProvider

    async def models(self, timeout=3.0):
        return [{"id": m, "state": None} for m in GEMINI]
    monkeypatch.setattr(ModelProvider, "models", models)
    hub.providers["gemini"] = ModelProvider("gemini", "Gemini (Google)", "https://example.invalid/v1", "cloud", "keychain", lambda: "k")
    ais = [a for a in client.get("/api/ais").json()["ais"] if a["provider"] == "gemini"]
    assert len(ais) == 4 and all("tts" not in a["model"] and "image" not in a["model"] for a in ais)
    assert ais[0]["name"].startswith("Gemini") and ais[0]["first"] and ais[0]["label"].startswith("Gemini (Google) · Gemini")


def test_thinking_is_hidden_even_when_a_tag_is_split():
    f = ThinkFilter()
    out = "".join(f.feed(p) for p in ["Hel", "lo <tho", "ught>a plan</th", "ought> world <b>x</b> <thi", "nk>more</think>!"])
    assert out + f.flush() == "Hello  world <b>x</b> !" and f.thought == "a planmore"
    g = ThinkFilter()
    assert g.feed("<thought>never closed") + g.flush() == "" and g.thought == "never closed"


def test_a_reply_cut_off_while_thinking_says_so(chat, monkeypatch):
    hub, client, rounds = chat

    def handler(request):
        rounds.append(json.loads(request.content))
        return httpx.Response(200, text=sse({"choices": [{"delta": {"content": "<thought>Let me consider the DCF"}}]},
                                            {"choices": [{"delta": {}, "finish_reason": "length"}]}))
    real = httpx._client.AsyncClient
    monkeypatch.setattr("sage_os_hub.connectors.chat.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    s = client.post("/api/agents/chat/sessions", json={"provider": "engine", "model": "qwen"}, headers=H).json()
    client.post(f"/api/agents/chat/sessions/{s['id']}/send", json={"text": "hi"}, headers=H)
    wait_idle(hub, s["id"])
    items = client.get(f"/api/agents/chat/sessions/{s['id']}/history").json()
    assert not any(i["kind"] == "text" for i in items)                       # no raw <thought> shown as the answer
    err = next(i for i in items if i["kind"] == "error")
    assert "cut off" in err["data"]["text"] and "still thinking" in err["data"]["text"]


def test_no_kanban_noise_without_hermes(tmp_path):
    panels = {}

    class Emit:
        def panel(self, name, data):
            panels[name] = data
    a = KanbanAdapter(Emit(), tmp_path / "no-hermes")
    a.poll()
    a.poll()                                       # quietly, again: no exception, no log line
    assert panels["board"] == {"tasks": [], "archived": 0, "links": []}


def test_a_chat_with_a_cloud_model_is_labelled_by_its_readable_name(chat):
    hub, client, rounds = chat
    from sage_os_hub.connectors.models import ModelProvider
    hub.providers["gemini"] = ModelProvider("gemini", "Gemini (Google)", "https://example.invalid/v1", "cloud", "keychain", lambda: "k")
    t = client.post("/api/threads", json={"agent": "chat", "provider": "gemini", "model": "models/gemini-2.5-flash"}, headers=H).json()
    assert t["parts"][0]["label"] == "Gemini (Google) · Gemini 2.5 Flash"
