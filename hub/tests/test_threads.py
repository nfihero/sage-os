"""W3 one chat space (D39): threads over every AI's sessions, history, search, and switching AI mid-chat."""
from test_engine import H, chat, wait_idle  # noqa: F401  (the chat fixture: a hub with a stand-in local model)


def new_thread(client, model="qwen"):
    r = client.post("/api/threads", json={"agent": "chat", "provider": "engine", "model": model}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_new_chat_is_a_thread_titled_by_its_first_message(chat):
    hub, client, rounds = chat
    assert client.post("/api/threads", json={"agent": "chat", "provider": "engine", "model": "qwen"}).status_code == 403
    t = new_thread(client)
    assert t["title"] == "New chat" and t["parts"][0]["label"] == "Local · qwen"
    r = client.post(f"/api/threads/{t['id']}/send", json={"text": "What is enterprise value in my DCF notes?"}, headers=H)
    assert r.status_code == 200
    wait_idle(hub, t["parts"][0]["sid"])
    listing = client.get("/api/threads").json()
    assert [x["title"] for x in listing] == ["What is enterprise value in my DCF notes?"]
    assert listing[0]["current"]["label"] == "Local · qwen" and listing[0]["busy"] is False
    full = client.get(f"/api/threads/{t['id']}").json()
    kinds = [i["kind"] for i in full["parts"][0]["items"]]
    assert kinds[0] == "user" and "text" in kinds and full["parts"][0]["pane"] == f"chat:{t['parts'][0]['sid']}"


def test_chats_from_before_get_a_thread_and_nothing_is_lost(chat):
    hub, client, rounds = chat
    s = client.post("/api/agents/chat/sessions", json={"provider": "engine", "model": "qwen"}, headers=H).json()
    listing = client.get("/api/threads").json()
    assert len(listing) == 1 and listing[0]["current"]["agent"] == "chat"
    assert hub.threads.thread_of("chat", s["id"])["id"] == listing[0]["id"]
    assert len(client.get("/api/threads").json()) == 1                        # adopted once


def test_switching_ai_mid_chat_hands_over_the_conversation(chat):
    hub, client, rounds = chat
    t = new_thread(client)
    client.post(f"/api/threads/{t['id']}/send", json={"text": "What is enterprise value in my DCF notes?"}, headers=H)
    wait_idle(hub, t["parts"][0]["sid"])
    r = client.post(f"/api/threads/{t['id']}/send", headers=H,
                    json={"text": "Now give me one practice problem.", "ai": {"agent": "chat", "provider": "engine", "model": "bigger"}})
    assert r.status_code == 200 and r.json()["part"]["label"] == "Local · bigger"
    part = r.json()["part"]
    wait_idle(hub, part["sid"])
    system = rounds[-1]["messages"][0]["content"]
    assert "The conversation so far" in system and "Enterprise value is the sum of discounted free cash flows" in system
    assert "User: What is enterprise value in my DCF notes?" in system
    assert rounds[-1]["model"] == "bigger"
    full = client.get(f"/api/threads/{t['id']}").json()
    assert [p["label"] for p in full["parts"]] == ["Local · qwen", "Local · bigger"]
    assert all(p["context"] is None for p in full["parts"])                    # what the AI was told isn't sent back
    listing = client.get("/api/threads").json()
    assert len(listing) == 1 and listing[0]["ais"] == ["Local · qwen", "Local · bigger"]
    # the next turn in the new part still carries the hand-over (the model chat has no memory of its own)
    client.post(f"/api/threads/{t['id']}/send", json={"text": "And the answer?"}, headers=H)
    wait_idle(hub, part["sid"])
    assert "The conversation so far" in rounds[-1]["messages"][0]["content"]


def test_rename_pin_archive_and_search(chat):
    hub, client, rounds = chat
    a, b = new_thread(client), new_thread(client)
    client.post(f"/api/threads/{a['id']}/send", json={"text": "What is enterprise value in my DCF notes?"}, headers=H)
    wait_idle(hub, a["parts"][0]["sid"])
    assert client.post(f"/api/threads/{b['id']}/edit", json={"title": "  "}, headers=H).status_code == 400
    client.post(f"/api/threads/{b['id']}/edit", json={"title": "Study plan", "pinned": True}, headers=H)
    assert [x["title"] for x in client.get("/api/threads").json()][0] == "Study plan"      # pinned first
    hits = client.get("/api/threads", params={"q": "discounted free cash"}).json()
    assert [x["id"] for x in hits] == [a["id"]] and "discounted free cash" in hits[0]["snippet"]
    assert [x["id"] for x in client.get("/api/threads", params={"q": "study"}).json()] == [b["id"]]   # by title
    client.post(f"/api/threads/{a['id']}/edit", json={"archived": True}, headers=H)
    assert [x["id"] for x in client.get("/api/threads").json()] == [b["id"]]
    assert [x["id"] for x in client.get("/api/threads", params={"archived": True}).json()] == [a["id"]]
    assert client.post("/api/threads/th_nope/edit", json={"pinned": True}, headers=H).status_code == 404


def test_unknown_or_disconnected_ais_are_refused(chat):
    hub, client, rounds = chat
    assert client.post("/api/threads", json={"agent": "claude"}, headers=H).status_code == 400
    t = new_thread(client)
    r = client.post(f"/api/threads/{t['id']}/send", json={"text": "hi", "ai": {"agent": "hermes:default"}}, headers=H)
    assert r.status_code == 400
    ais = client.get("/api/ais").json()["ais"]
    assert all(a["agent"] == "chat" for a in ais)                              # only what is connected here
