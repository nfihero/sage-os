"""One chat space (W3, D39): every conversation with any AI is a *thread* in one history list.

A thread is one or more *parts*; each part is a session with one AI through its connector (the model chat for the
local engine, ChatGPT, Gemini, Ollama; Claude Code; a Hermes profile). Picking another AI mid-conversation starts a
new part, and that AI is given the conversation so far, so it carries on where the other left off.

Threads live in hub.db (`threads`, synced like the chats themselves). Sessions made before W3, or outside it (the
Claude and Hermes panes, Hermes' own apps), get a thread of their own the first time the list is read, so nothing
from before is lost.
"""
from __future__ import annotations

import json
import re
import threading
import time

from .sync import new_id

CONTEXT_TURNS, CONTEXT_CHARS = 30, 16_000      # how much of the conversation so far a new AI is given
SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id       TEXT PRIMARY KEY,            -- th_ + ULID
    title    TEXT NOT NULL,
    pinned   INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    created  REAL NOT NULL,
    updated  REAL NOT NULL,
    parts    TEXT NOT NULL                -- JSON: [{"agent", "sid", "label", "model", "started", "context"?}]
);
"""


def ai_label(agent: str, model: str | None, provider_label: str | None = None) -> str:
    if agent == "claude":
        return "Claude Code"
    if agent.startswith("hermes:"):
        return "Hermes"
    m = (model or "").removeprefix("file:")
    return f"{provider_label} · {m}" if provider_label and provider_label.lower() not in ("sage engine", "sage engine (on this computer)") \
        else f"Local · {m}" if m else "Local model"


class Threads:
    def __init__(self, hub, db, lock: threading.RLock):
        self.hub, self.db, self.lock = hub, db, lock
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()

    # -- rows --------------------------------------------------------------------------------------------------
    def _row(self, r) -> dict:
        keys = ("id", "title", "pinned", "archived", "created", "updated", "parts")
        t = dict(zip(keys, r))
        t["pinned"], t["archived"], t["parts"] = bool(t["pinned"]), bool(t["archived"]), json.loads(t["parts"])
        return t

    def get(self, tid: str) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT id, title, pinned, archived, created, updated, parts FROM threads WHERE id=?", (tid,)).fetchone()
        return self._row(r) if r else None

    def _save(self, t: dict) -> None:
        with self.lock:
            self.db.execute("INSERT INTO threads(id, title, pinned, archived, created, updated, parts) VALUES (?,?,?,?,?,?,?) "
                            "ON CONFLICT(id) DO UPDATE SET title=excluded.title, pinned=excluded.pinned, archived=excluded.archived, "
                            "updated=excluded.updated, parts=excluded.parts",
                            (t["id"], t["title"][:200], int(t["pinned"]), int(t["archived"]), t["created"], t["updated"],
                             json.dumps(t["parts"])))
            self.db.commit()

    def all(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT id, title, pinned, archived, created, updated, parts FROM threads").fetchall()
        return [self._row(r) for r in rows]

    def by_pane(self) -> dict[str, str]:
        """pane (agent:sid) -> thread id, for every part of every thread."""
        return {f"{p['agent']}|{p['sid']}": t["id"] for t in self.all() for p in t["parts"]}

    def thread_of(self, agent: str, sid: str) -> dict | None:
        tid = self.by_pane().get(f"{agent}|{sid}")
        return self.get(tid) if tid else None

    # -- every session has a thread ------------------------------------------------------------------------------
    def sessions(self) -> list[dict]:
        """Every session the connectors know: (agent, sid, title, updated, created, model, label)."""
        hub, out = self.hub, []
        providers = {p.id: p.label for p in hub.providers.values()}
        if "chat" in hub.agents:
            for s in hub.store.chat_sessions():
                out.append({"agent": "chat", "sid": s["id"], "title": s["title"], "updated": s["updated"], "created": s["created"],
                            "provider": s["provider"],
                            "model": s["model"], "label": ai_label("chat", s["model"], providers.get(s["provider"]))})
        if "claude" in hub.agents:
            for s in hub.store.claude_sessions():
                out.append({"agent": "claude", "sid": s["id"], "title": s["title"], "updated": s["updated"],
                            "created": s["created"], "model": s.get("model"), "label": "Claude Code"})
        for prof in (hub.panels.get("sessions") or []):
            agent = f"hermes:{prof['profile']}"
            if agent not in hub.agents:
                continue
            for s in prof.get("sessions", []):
                if s.get("archived"):
                    continue
                ts = float(s.get("last_activity_at") or s.get("started_at") or 0)
                out.append({"agent": agent, "sid": str(s["id"]), "title": s.get("title") or "untitled", "updated": ts,
                            "created": float(s.get("started_at") or ts), "model": s.get("model"),
                            "label": prof.get("label") or "Hermes"})
        return out

    def adopt(self) -> None:
        """Give every session without a thread its own (chats made before W3 or in the old panes)."""
        known = self.by_pane()
        for s in self.sessions():
            if f"{s['agent']}|{s['sid']}" in known:
                continue
            self._save({"id": new_id("th_"), "title": s["title"] or "New chat", "pinned": False, "archived": False,
                        "created": s["created"] or time.time(), "updated": s["updated"] or time.time(),
                        "parts": [{"agent": s["agent"], "sid": s["sid"], "label": s["label"], "model": s["model"],
                                   "provider": s.get("provider"),
                                   "started": s["created"] or time.time()}]})

    # -- the list -----------------------------------------------------------------------------------------------
    def listing(self, q: str = "", archived: bool = False) -> list[dict]:
        """Threads newest first (pinned on top), with the AI of their latest part, how busy they are, and turns."""
        self.adopt()
        live = {f"{s['agent']}|{s['sid']}": s for s in self.sessions()}
        q = q.strip().lower()
        hits = self._search(q) if q else None
        out = []
        for t in self.all():
            if t["archived"] != archived:
                continue
            if hits is not None and t["id"] not in hits and q not in t["title"].lower():
                continue
            parts = [p for p in t["parts"] if f"{p['agent']}|{p['sid']}" in live]
            if not parts:                       # every session behind it is gone (deleted, or its AI disconnected)
                continue
            cur = parts[-1]
            updated = max([t["updated"]] + [live[f"{p['agent']}|{p['sid']}"]["updated"] or 0 for p in parts])
            out.append({"id": t["id"], "title": t["title"], "pinned": t["pinned"], "archived": t["archived"],
                        "updated": updated, "created": t["created"],
                        "ais": list(dict.fromkeys(p["label"] for p in parts)),
                        "current": {"agent": cur["agent"], "label": cur["label"], "model": cur.get("model"),
                                    "provider": cur.get("provider")},
                        "busy": self._busy(cur), "snippet": (hits or {}).get(t["id"])})
        out.sort(key=lambda x: (not x["pinned"], -x["updated"]))
        return out

    def _busy(self, part: dict) -> bool:
        c = self.hub.agents.get(part["agent"])
        try:
            return bool(c and c.busy(part["sid"]))
        except Exception:                           # noqa: BLE001 -- a connector that can't tell isn't busy
            return False

    def _search(self, q: str) -> dict[str, str]:
        """thread id -> a snippet of the message that matched (messages of model and Claude chats)."""
        words = [w for w in re.findall(r"\w+", q) if len(w) > 1][:6]
        if not words:
            return {}
        where = " AND ".join("lower(data) LIKE ?" for _ in words)
        with self.hub.store.lock:
            rows = self.hub.store.db.execute(
                f"SELECT session_id, data FROM chat_items WHERE kind IN ('user','text') AND {where} ORDER BY ts DESC LIMIT 400",
                [f"%{w}%" for w in words]).fetchall()
        by_sid = {}
        for sid, data in rows:
            if sid not in by_sid:
                text = str(json.loads(data).get("text", ""))
                i = text.lower().find(words[0])
                by_sid[sid] = ("…" if i > 40 else "") + text[max(0, i - 40):i + 100].replace("\n", " ")
        out = {}
        for t in self.all():
            for p in t["parts"]:
                if p["sid"] in by_sid:
                    out.setdefault(t["id"], by_sid[p["sid"]])
        return out

    # -- changes ------------------------------------------------------------------------------------------------
    def create(self, agent: str, sid: str, label: str, model: str | None, title: str = "New chat",
               provider: str | None = None) -> dict:
        now = time.time()
        t = {"id": new_id("th_"), "title": title, "pinned": False, "archived": False, "created": now, "updated": now,
             "parts": [{"agent": agent, "sid": sid, "label": label, "model": model, "provider": provider, "started": now}]}
        self._save(t)
        return t

    def add_part(self, tid: str, agent: str, sid: str, label: str, model: str | None, context: str,
                 provider: str | None = None) -> dict:
        t = self.get(tid)
        t["parts"].append({"agent": agent, "sid": sid, "label": label, "model": model, "provider": provider, "started": time.time(),
                           "context": context})
        t["updated"] = time.time()
        self._save(t)
        return t

    def edit(self, tid: str, title: str | None = None, pinned: bool | None = None, archived: bool | None = None) -> dict:
        t = self.get(tid)
        if t is None:
            raise KeyError(tid)
        if title is not None:
            title = " ".join(title.split())[:200]
            if not title:
                raise ValueError("a chat needs a title")
            t["title"] = title
        if pinned is not None:
            t["pinned"] = bool(pinned)
        if archived is not None:
            t["archived"] = bool(archived)
        self._save(t)
        return t

    def touch(self, tid: str, first_message: str | None = None) -> None:
        t = self.get(tid)
        if t is None:
            return
        t["updated"] = time.time()
        if first_message and t["title"] == "New chat":
            t["title"] = first_message.strip().splitlines()[0][:60] or "New chat"
        self._save(t)

    def context_for(self, agent: str, sid: str) -> str | None:
        """What an AI that joined a conversation part-way was told about it (the model chat re-sends it each turn)."""
        t = self.thread_of(agent, sid)
        if not t:
            return None
        return next((p.get("context") for p in t["parts"] if p["agent"] == agent and p["sid"] == sid), None)

    @staticmethod
    def transcript(parts_items: list[tuple[str, list[dict]]]) -> str:
        """The conversation so far, as plain text for the next AI: the last turns, newest kept when it's long."""
        lines = []
        for label, items in parts_items:
            for it in items:
                if it["kind"] == "user":
                    lines.append(f"User: {it['data'].get('text', '')}")
                elif it["kind"] == "text":
                    lines.append(f"{label}: {it['data'].get('text', '')}")
        lines = lines[-CONTEXT_TURNS:]
        text = "\n\n".join(lines)
        return text[-CONTEXT_CHARS:]
