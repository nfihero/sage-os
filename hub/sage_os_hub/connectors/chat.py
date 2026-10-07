"""Chat with any OpenAI-compatible model (DECISIONS D22.2): Sage OS's own local engine, ChatGPT (OpenAI),
Gemini (Google's OpenAI-compatible endpoint), Ollama, LM Studio. One connector, many providers.

The model gets the Bookshelf tools as function calls (read freely, write only by proposing, I1). Sage OS
runs the tool loop itself, so the model can't do anything those tools don't allow: no shell, no files.
Transcripts live in hub.db like Claude's.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

import httpx

from ..knowledge.tools import (INSTRUCTIONS, LIST_DESC, PROPOSE_DESC, READ_DESC, READ_SOURCE_DESC, SEARCH_DESC,
                               SEARCH_SOURCES_DESC, as_text)
from .base import AgentBusy, AgentConnector, AgentError, InvalidRequest, SessionNotFound

log = logging.getLogger("sage_os")
MAX_ROUNDS = 8            # tool calls per message before Sage OS stops the loop
HISTORY = 40              # past messages sent with each turn

SYSTEM = f"""You are an assistant inside Sage OS, the user's personal knowledge hub. The user's notes (the
Bookshelf) and their documents (the source library) are reachable through your tools; messages may also
carry excerpts Sage OS picked for them. {INSTRUCTIONS}
Answer from the user's own material when it is relevant and say which note or document you used. If the
material doesn't cover something, say so rather than guessing."""


def _fn(name, desc, props, required=()):
    return {"type": "function", "function": {"name": name, "description": desc,
                                             "parameters": {"type": "object", "properties": props, "required": list(required)}}}


TOOLS = [
    _fn("search_notes", SEARCH_DESC, {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    _fn("read_note", READ_DESC, {"uid": {"type": "string"}}, ["uid"]),
    _fn("search_sources", SEARCH_SOURCES_DESC, {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    _fn("read_source", READ_SOURCE_DESC, {"source": {"type": "string"}, "path": {"type": "string"},
                                          "offset": {"type": "integer"}}, ["source", "path"]),
    _fn("propose_note", PROPOSE_DESC, {"changes": {"type": "array", "items": {"type": "object"}},
                                       "summary": {"type": "string"}}, ["changes"]),
    _fn("list_proposals", LIST_DESC, {"status": {"type": "string", "enum": ["pending", "applied", "rejected"]}}),
]


class ChatConnector(AgentConnector):
    id, label, kind, vendor = "chat", "Chat", "local", "openai-compatible"
    capabilities = frozenset({"chat", "interrupt", "history", "model_pick"})

    def __init__(self, hub):
        self.hub = hub
        self.tasks: dict[str, asyncio.Task] = {}

    def info(self) -> dict:
        return super().info() | {"providers": [p.info() for p in self.hub.providers.values()]}

    def pane(self, session_id: str) -> str:
        return f"chat:{session_id}"

    # -- sessions ------------------------------------------------------------------------------------
    def sessions(self) -> list[dict]:
        return [s | {"status": "running" if self.busy(s["id"]) else "idle"} for s in self.hub.store.chat_sessions()]

    def publish(self):
        self.hub.panel("chat", {"sessions": self.sessions()})

    def _get(self, sid: str) -> dict:
        s = self.hub.store.chat_session(sid)
        if not s:
            raise SessionNotFound(sid)
        return s

    async def create_session(self, title: str | None = None, **options) -> dict:
        provider, model = options.get("provider"), options.get("model")
        if provider not in self.hub.providers:
            raise InvalidRequest(f"no model provider {provider!r}; connect one first")
        if not model:
            raise InvalidRequest("pick a model")
        now = time.time()
        row = {"id": f"ch_{uuid.uuid4().hex[:10]}", "title": title or "New chat", "provider": provider,
               "model": str(model)[:200], "created": now, "updated": now}
        self.hub.store.upsert_chat_session(row)
        self.publish()
        return row

    def busy(self, session_id: str) -> bool:
        t = self.tasks.get(session_id)
        return bool(t and not t.done())

    async def history(self, session_id: str) -> list[dict]:
        self._get(session_id)
        return self.hub.store.chat_items(session_id)

    # -- a turn ----------------------------------------------------------------------------------------
    def _item(self, sid, kind, data):
        it = self.hub.store.add_chat_item(sid, kind, data)
        self.hub.publish({"t": "chat", "pane": self.pane(sid), "op": "item", "item": it})

    async def send(self, session_id: str, text: str, shown: str | None = None) -> None:
        s = self._get(session_id)
        if self.busy(session_id):
            raise AgentBusy("still answering the previous message")
        past = [i for i in self.hub.store.chat_items(session_id) if i["kind"] in ("user", "text")][-HISTORY:]
        if s["title"] == "New chat":
            s["title"] = (shown or text).strip().splitlines()[0][:60] or "New chat"
        s["updated"] = time.time()
        self.hub.store.upsert_chat_session(s)
        self._item(session_id, "user", {"text": shown if shown is not None else text})
        msgs = [{"role": "system", "content": SYSTEM}]
        msgs += [{"role": "user" if i["kind"] == "user" else "assistant", "content": i["data"].get("text", "")} for i in past]
        msgs.append({"role": "user", "content": text})
        self.tasks[session_id] = asyncio.create_task(self._run(s, msgs))
        self.publish()

    async def interrupt(self, session_id: str) -> None:
        t = self.tasks.get(session_id)
        if t and not t.done():
            t.cancel()

    async def _run(self, s: dict, msgs: list[dict]):
        sid, started = s["id"], time.time()
        provider = self.hub.providers.get(s["provider"])
        tools = TOOLS
        try:
            if provider is None:
                raise AgentError(f"model provider {s['provider']!r} is no longer configured")
            for _ in range(MAX_ROUNDS):
                try:
                    text, calls = await self._complete(provider, s["model"], msgs, tools)
                except _ToolsUnsupported:
                    tools = None                     # some models/servers can't do function calls: answer without
                    text, calls = await self._complete(provider, s["model"], msgs, None)
                if text.strip():
                    self._item(sid, "text", {"text": text})
                if not calls:
                    break
                msgs.append({"role": "assistant", "content": text or None, "tool_calls": calls})
                for c in calls:
                    name, raw = c["function"]["name"], c["function"].get("arguments") or "{}"
                    try:
                        args = json.loads(raw) if raw.strip() else {}
                    except ValueError:
                        args = {}
                    self._item(sid, "tool_use", {"id": c["id"], "tool": name, "summary": raw[:160], "input": args})
                    result = await self._tool(sid, name, args)
                    self._item(sid, "tool_result", {"id": c["id"], "tool": name, "text": result[:6000]})
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": result})
            else:
                self._item(sid, "note", {"text": f"Stopped after {MAX_ROUNDS} rounds of tool calls."})
        except asyncio.CancelledError:
            self._item(sid, "note", {"text": "Stopped."})
        except Exception as exc:                     # noqa: BLE001 -- shown in the pane
            log.warning("chat %s failed: %s", sid, exc)
            self._item(sid, "error", {"text": str(exc)})
        finally:
            self._item(sid, "note", {"text": "turn complete", "turn_end": True, "ms": int((time.time() - started) * 1000)})
            self.tasks.pop(sid, None)
            self.publish()

    async def _complete(self, provider, model: str, msgs: list[dict], tools) -> tuple[str, list[dict]]:
        """One streamed completion. -> (assistant text, tool calls). Text deltas stream to the pane."""
        key = provider.key()
        body = {"model": model, "messages": msgs, "stream": True}
        if tools:
            body["tools"] = tools
        text, calls = "", {}
        sid = next((k for k, t in self.tasks.items() if t is asyncio.current_task()), None)
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=600)) as c:
            async with c.stream("POST", f"{provider.base_url.rstrip('/')}/chat/completions", json=body,
                                headers={"Authorization": f"Bearer {key}"} if key else {}) as r:
                if r.status_code >= 400:
                    detail = (await r.aread()).decode("utf-8", "replace")[:400]
                    if tools and r.status_code in (400, 422, 500) and "tool" in detail.lower():
                        raise _ToolsUnsupported()
                    raise AgentError(f"{provider.label}: HTTP {r.status_code}: {detail}")
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    for ch in chunk.get("choices") or []:
                        d = ch.get("delta") or {}
                        if d.get("content"):
                            text += d["content"]
                            if sid:
                                self.hub.publish({"t": "chat", "pane": self.pane(sid), "op": "delta", "text": d["content"]})
                        for tc in d.get("tool_calls") or []:
                            # OpenAI streams pieces keyed by index; some servers (Gemini) send whole calls without one
                            idx = tc["index"] if "index" in tc else (len(calls) if tc.get("id") or not calls else len(calls) - 1)
                            slot = calls.setdefault(idx, {"id": tc.get("id") or f"call_{idx}",
                                                          "type": "function", "function": {"name": "", "arguments": ""}})
                            fn = tc.get("function") or {}
                            slot["function"]["name"] += fn.get("name") or ""
                            slot["function"]["arguments"] += fn.get("arguments") or ""
        return text, [calls[i] for i in sorted(calls)]

    async def _tool(self, sid: str, name: str, a: dict) -> str:
        t, agent = self.hub.bookshelf_tools, self.pane(sid)    # the agent id is the chat: Sage OS sets it, not the model
        try:
            if name == "search_notes":
                r = await t.search(agent, str(a.get("query", "")), int(a.get("limit") or 10))
            elif name == "read_note":
                r = await t.read(agent, str(a.get("uid", "")))
            elif name == "search_sources":
                r = await t.search_sources(agent, str(a.get("query", "")), int(a.get("limit") or 10))
            elif name == "read_source":
                r = await t.read_source(agent, str(a.get("source", "")), str(a.get("path", "")), int(a.get("offset") or 0))
            elif name == "propose_note":
                ch = a.get("changes")
                if not isinstance(ch, list) or not ch:
                    r = {"error": "changes must be a non-empty list"}
                else:
                    r = await t.propose(agent, ch[:50], str(a.get("summary", ""))[:500])
            elif name == "list_proposals":
                r = await t.proposals(agent, a.get("status"))
            else:
                r = {"error": f"no tool {name!r}"}
        except (TypeError, ValueError) as exc:
            r = {"error": f"bad arguments: {exc}"}
        return as_text(r)


class _ToolsUnsupported(Exception):
    pass
