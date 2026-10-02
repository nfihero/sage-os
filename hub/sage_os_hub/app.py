"""Sage OS hub: FastAPI app, WebSocket event stream, adapters, chat and the approvals inbox.

Reads come from adapters polling Hermes' files read-only. Agents and model servers plug in
through connectors (connectors/, DECISIONS D4); writes go only through their public surfaces --
the Claude Agent SDK, Hermes' gateway API -- and the `hermes` CLI for the kanban board. Every
write route requires the X-Sage-OS header, a local Host and a local Origin. Run: python -m sage_os_hub
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import webbrowser
import logging
import time
import uuid
from pathlib import Path
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, hermes_cli
from .adapters.kanban import KanbanAdapter
from .adapters.safety import SafetyAdapter
from .adapters.sessions import SessionsAdapter
from .adapters.system import GpuAdapter, HealthAdapter
from .adapters.vault import VaultAdapter
from .config import ROOT, Config, load
from .connectors import build_agents, build_providers
from .connectors.base import AgentBusy, AgentConnector, AgentError, InvalidRequest, SessionNotFound
from .inbox import Inbox
from .knowledge import ProposalError, SearchIndex, SensitiveContent, Vault, Writer
from .knowledge.mcp_http import build_server, mcp_path
from .knowledge.tools import BookshelfTools
from .store import Store

log = logging.getLogger("sage_os")
LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
MAX_PENDING_PER_AGENT = 25      # Bookshelf proposals waiting for the user, per agent
MAX_HELD_PER_AGENT = 10         # screened (secret-looking) proposals held in memory, per agent
LOCAL_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "::1"}


def open_folder(path: Path) -> None:
    """Show a folder in the desktop's file manager (Explorer on Windows)."""
    if os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _local_origin(origin: str | None, remote_hosts: frozenset[str] = frozenset()) -> bool:
    """No Origin (non-browser client) or this machine, or a remote host named in config.toml.
    Never a wildcard: anyone can publish a page on *.ts.net with Tailscale Funnel."""
    if not origin:
        return True
    host = urlparse(origin).hostname or ""
    return host in LOCAL_ORIGIN_HOSTS or host in remote_hosts


def security_headers(host: str) -> dict[str, str]:
    """Same-origin everything; nothing may frame the hub (a framed inbox could be click-jacked into
    "Approve" or "Save anyway"); no remote images (an agent's markdown can't beacon data out)."""
    return {
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                   "img-src 'self' data: blob:; font-src 'self' data:; "
                                   f"connect-src 'self' ws://{host} wss://{host}; object-src 'none'; "
                                   "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
    }


class Hub:
    """Implements the adapters' Emitter: keeps panel state, persists events, fans out to sockets."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = Store(cfg.store, cfg.keep_events)
        self.panels: dict = {}
        self.subscribers: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.kanban = KanbanAdapter(self, cfg.hermes_home, cfg.poll["board"])
        self.vault = Vault(cfg.vault)
        self.vault.ensure()
        self.index = SearchIndex(cfg.vault_index)
        self.writer = Writer(self.vault, cfg.vault_journal)
        for batch in self.writer.recover():
            log.warning("Bookshelf: batch %s was interrupted by a crash and has been rolled back", batch)
        self.vault_adapter = VaultAdapter(self, self.vault, self.index, cfg.poll["vault"])
        self.adapters = [self.kanban, GpuAdapter(self, cfg), HealthAdapter(self, cfg),
                         SafetyAdapter(self, cfg), SessionsAdapter(self, cfg), self.vault_adapter]
        self.inbox = Inbox(self.publish, self.event)
        self.bookshelf_tools = BookshelfTools(self)
        self.agents: dict[str, AgentConnector] = build_agents(self, cfg)
        # Bookshelf over MCP (K5): Claude gets an in-process server per session; every other agent
        # gets a Streamable HTTP endpoint whose path fixes the agent id.
        self.mcp = {a.id: build_server(self.bookshelf_tools, a.id, cfg.port)
                    for a in self.agents.values() if a.vendor != "claude-code"}
        self.claude = self.agents.get("claude")
        self.providers = build_providers(cfg)
        self.smoke_results: list[dict] = []
        self.started = time.time()
        usage = self.store.load_panels().get("claude_usage")
        if usage:
            self.panels["claude_usage"] = usage

    # -- Emitter -----------------------------------------------------------------------------
    def panel(self, name, data, *, broadcast=True):
        self.panels[name] = data
        if broadcast:
            self.publish({"t": "panel", "name": name, "data": data})
        if name == "board" and self.loop:
            self.loop.call_soon_threadsafe(self._sync_kanban_inbox, data)

    def event(self, kind, source, type_, data, *, persist=True, ts=None):
        if persist:
            ev = self.store.add_event(kind, source, type_, data, ts)
        else:
            ev = {"id": None, "ts": ts or time.time(), "kind": kind, "source": source,
                  "type": type_, "data": data}
        self.publish({"t": "event", "event": ev})

    def publish(self, msg):
        if self.loop is None:
            return
        for q in list(self.subscribers):
            self.loop.call_soon_threadsafe(_offer, q, msg)

    # -- kanban blocks -> inbox ----------------------------------------------------------------
    def _sync_kanban_inbox(self, board):
        home = self.cfg.hermes_home
        live = set()
        for t in board.get("tasks", []):
            if t["status"] != "blocked":
                continue
            key = f"kanban:{t['id']}"
            live.add(key)

            async def resolver(choice, note, task_id=t["id"]):
                if not note.strip():
                    raise ValueError("write an answer for the worker first")
                await hermes_cli.comment(home, task_id, note)
                if choice == "reply_unblock":
                    await hermes_cli.unblock(home, task_id)

            self.inbox.add(source="kanban", key=key, title=f"{t['assignee'] or 'worker'} asks: {t['title']}",
                           detail=t.get("block_reason") or "blocked", choices=["reply_unblock", "reply_only"],
                           resolver=resolver, context={"task_id": t["id"], "block_kind": t.get("block_kind")})
        for key in self.inbox.keys("kanban:"):
            if key not in live:
                self.inbox.drop(key)

    # -- Bookshelf proposals -> inbox (K3) ------------------------------------------------------
    def offer_proposal(self, p: dict, preview: list[dict] | None = None, problem: str | None = None):
        """Put a pending proposal in the inbox. Approving it is the only way it reaches the vault (I1)."""
        pid = p["id"]

        async def resolver(choice, note):
            if choice == "approve":
                batch = await asyncio.to_thread(self.writer.approve, pid, note)
                self.event("knowledge", "bookshelf", "proposal.applied",
                           {"proposal": pid, "batch": batch["id"], "agent": p["agent"], "files": batch["files"]})
            else:
                await asyncio.to_thread(self.writer.reject, pid, note)
                self.event("knowledge", "bookshelf", "proposal.rejected", {"proposal": pid, "agent": p["agent"], "note": note})
            self.refresh_vault()

        n = len(p["changes"])
        self.inbox.add(source="bookshelf", key=f"bookshelf:{pid}",
                       title=f"{p['agent']} proposes {n} change{'' if n == 1 else 's'} to the Bookshelf",
                       detail=p["summary"] or "", choices=["approve", "reject"], resolver=resolver,
                       context={"proposal_id": pid, "agent": p["agent"], "changes": preview or [], "problem": problem})

    def offer_pending_proposals(self):
        for p in self.writer.proposals("pending"):
            try:
                self.offer_proposal(p, self.writer.preview(p["id"]))
            except ProposalError as exc:      # e.g. the note was edited while the hub was down
                self.offer_proposal(p, problem=str(exc))

    async def submit_proposal(self, agent: str, summary: str, changes: list) -> dict:
        """The one way a proposal enters Sage OS (HTTP route and agent tools alike).
        -> {"status": "pending", "proposal"} | {"status": "held", "message"} | {"status": "refused", "error"}"""
        waiting = sum(1 for p in await asyncio.to_thread(self.writer.proposals, "pending", 1000) if p["agent"] == agent)
        if waiting >= MAX_PENDING_PER_AGENT:
            return {"status": "refused", "error": f"{waiting} of your proposals are already waiting for the user. "
                    "Wait for their decisions (list_proposals) before proposing more."}
        held = sum(1 for i in self.inbox.items() if i["context"].get("held") and i["context"].get("agent") == agent)
        if held >= MAX_HELD_PER_AGENT:
            return {"status": "refused", "error": "Too many of your proposals are held for looking like they contain "
                    "secrets. Never put secrets in notes."}
        try:
            p = await asyncio.to_thread(self.writer.propose, agent, summary, changes)
        except SensitiveContent as exc:
            # The event says who, where and what kind -- never the content (I4). If the agent name
            # itself tripped the screen, it isn't recorded either.
            who = "(withheld)" if exc.where == "the agent name" else agent
            self.event("knowledge", "bookshelf", "proposal.screened", {"agent": who, "where": exc.where, "category": exc.category})
            try:
                preview = await asyncio.to_thread(self.writer.render, agent, summary, changes)
            except ProposalError as invalid:          # not worth holding: it couldn't be filed anyway
                return {"status": "refused", "error": f"{exc} Also: {invalid}"}
            self.hold_screened(agent, summary, changes, exc, preview)
            return {"status": "held", "message": f"{exc} It is held for the user's review; only they can save it anyway."}
        except ProposalError as exc:
            return {"status": "refused", "error": str(exc)}
        self.offer_proposal(p, p.pop("preview"))
        self.event("knowledge", "bookshelf", "proposal.created", {"proposal": p["id"], "agent": p["agent"]})
        return {"status": "pending", "proposal": p}

    def hold_screened(self, agent: str, summary: str, changes: list, exc, preview: list[dict]):
        """K4 manual override: a screened proposal waits in the inbox, in memory only (never on disk),
        until the user rejects it or chooses "Save anyway". A hub restart drops it."""
        who = "(withheld)" if exc.where == "the agent name" else agent
        key = f"held:{uuid.uuid4().hex[:10]}"

        async def resolver(choice, note):
            info = {"agent": who, "where": exc.where, "category": exc.category}
            if choice != "save_anyway":
                self.event("knowledge", "bookshelf", "proposal.held_rejected", info)
                return
            p = await asyncio.to_thread(lambda: self.writer.propose(agent, summary, changes, override=exc.category))
            self.event("knowledge", "bookshelf", "proposal.override", info | {"proposal": p["id"]})
            try:
                batch = await asyncio.to_thread(self.writer.approve, p["id"], note)
            except ProposalError as err:          # e.g. a note changed meanwhile: it stays as a normal proposal
                self.offer_proposal(p, problem=str(err))
                return
            self.event("knowledge", "bookshelf", "proposal.applied",
                       {"proposal": p["id"], "batch": batch["id"], "agent": who, "files": batch["files"]})
            self.refresh_vault()

        self.inbox.add(source="bookshelf", key=key, title=f"Held: a Bookshelf proposal looks like it contains {exc.category}",
                       detail=f"{exc.where} looks like it contains {exc.category}. Nothing has been stored. "
                              "Reject it, or save it anyway if you're sure it belongs in your notes.",
                       choices=["reject", "save_anyway"], resolver=resolver,
                       context={"held": True, "agent": who, "where": exc.where, "category": exc.category, "changes": preview})

    def refresh_vault(self):
        """Re-read the vault now instead of waiting for the next poll (after an apply or undo)."""
        if self.loop:
            self.loop.create_task(asyncio.to_thread(self.vault_adapter.poll))

    # -- lifecycle ---------------------------------------------------------------------------
    def run_smoke(self):
        results = []
        for a in self.adapters:
            try:
                results += [{"adapter": a.name, "check": c, "ok": ok, "detail": d} for c, ok, d in a.smoke()]
            except Exception as exc:
                results.append({"adapter": a.name, "check": "smoke", "ok": False, "detail": repr(exc)})
        for a in self.agents.values():
            try:
                results += [{"adapter": a.id, "check": c, "ok": ok, "detail": d} for c, ok, d in a.smoke()]
            except Exception as exc:
                results.append({"adapter": a.id, "check": "smoke", "ok": False, "detail": repr(exc)})
        for agent_id in self.mcp:
            results.append({"adapter": "bookshelf", "check": f"MCP endpoint for {agent_id}", "ok": True,
                            "detail": f"http://{self.cfg.host}:{self.cfg.port}{mcp_path(agent_id)}/"})
        lead = self.cfg.lead_agent
        results.append({"adapter": "agents", "check": "lead agent connected", "ok": lead in self.agents,
                        "detail": lead if lead in self.agents else f"{lead!r} is not among {sorted(self.agents)}"})
        self.smoke_results = results
        for r in results:
            if not r["ok"]:
                log.warning("SMOKE FAIL %s / %s: %s", r["adapter"], r["check"], r["detail"])
        return results

    def snapshot(self):
        recent = self.store.recent_events(150)
        return {"panels": self.panels | {"inbox": self.inbox.items()}, "smoke": self.smoke_results,
                "events": recent,
                "hub": {"version": __version__, "read_only": False, "started": self.started,
                        "pinned_profiles": self.cfg.pinned_profiles, "lead_agent": self.cfg.lead_agent,
                        "agents": [a.info() for a in self.agents.values()]}}


RESYNC = {"t": "resync"}


def _offer(q: asyncio.Queue, msg):
    try:
        q.put_nowait(msg)
    except asyncio.QueueFull:          # a stalled tab: tell it to reload state instead
        while not q.empty():
            q.get_nowait()
        q.put_nowait(RESYNC)


# -- request bodies ------------------------------------------------------------------------------
class NewSession(BaseModel):
    title: str | None = None
    cwd: str | None = None             # agents with the "workspaces" capability
    model: str | None = None           # agents with the "model_pick" capability


class NewProposal(BaseModel):
    agent: str = Field(min_length=1, max_length=200)    # who proposes: claude:<session>, hermes:default:<session>, ...
    summary: str = Field(default="", max_length=500)
    changes: list[dict] = Field(min_length=1, max_length=50)


class Send(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


class Decision(BaseModel):
    choice: str
    note: str = Field(default="", max_length=20_000)


def create_app(cfg: Config | None = None, start_adapters: bool = True) -> FastAPI:
    cfg = cfg or load()
    hub = Hub(cfg)

    @asynccontextmanager
    async def lifespan(app):
        hub.loop = asyncio.get_running_loop()
        mcp_stack = AsyncExitStack()
        for _, manager in hub.mcp.values():
            await mcp_stack.enter_async_context(manager.run())
        tasks = []
        if hub.claude:
            hub.claude.publish_sessions()
        hub.offer_pending_proposals()
        if start_adapters:
            results = await asyncio.to_thread(hub.run_smoke)
            tasks = [asyncio.create_task(a.run(), name=a.name) for a in hub.adapters]
            tasks += [asyncio.create_task(c, name=f"{a.id}-bg") for a in hub.agents.values() for c in a.background()]
            bad = [r for r in results if not r["ok"]]
            url = f"http://{cfg.host}:{cfg.port}"
            log.info("READY  %s  (smoke: %d/%d checks ok%s)  Ctrl+C to stop", url, len(results) - len(bad),
                     len(results), "" if not bad else " - see warnings above")
            if os.environ.get("SAGE_OS_OPEN") == "1":
                webbrowser.open(url)
        yield
        for t in tasks:
            t.cancel()
        for a in hub.agents.values():
            await a.shutdown()
        await mcp_stack.aclose()
        hub.index.close()
        hub.writer.close()
        hub.store.close()

    # No /docs, /redoc or /openapi.json: nothing to browse the API with but the UI.
    app = FastAPI(title="Sage OS hub", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.hub = hub
    remote = frozenset(cfg.remote_hosts)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS + sorted(remote))

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        for k, v in security_headers(request.headers.get("host", "127.0.0.1")).items():
            response.headers.setdefault(k, v)
        return response

    def local_write(request: Request):
        """CSRF guard: a custom header forces a CORS preflight, which this app never grants."""
        if request.headers.get("x-sage-os") != "1" or not _local_origin(request.headers.get("origin"), remote):
            raise HTTPException(403, "write requests must come from the Sage OS UI")

    W = [Depends(local_write)]

    def agent(agent_id: str) -> AgentConnector:
        if agent_id not in hub.agents:
            raise HTTPException(404, f"no agent {agent_id!r} is connected")
        return hub.agents[agent_id]

    @contextmanager
    def agent_errors():
        try:
            yield
        except SessionNotFound:
            raise HTTPException(404, "no such session")
        except AgentBusy as exc:
            raise HTTPException(409, str(exc))
        except InvalidRequest as exc:
            raise HTTPException(400, str(exc))
        except AgentError as exc:
            raise HTTPException(502, str(exc))

    # -- reads -----------------------------------------------------------------------------------
    @app.get("/api/state")
    def state():
        return hub.snapshot()

    @app.get("/api/tasks/{task_id}")
    def task(task_id: str):
        detail = hub.kanban.task_detail(task_id)
        if detail is None:
            raise HTTPException(404, "no such task")
        return detail

    @app.get("/api/events")
    def events(after: int = 0, limit: int = 500):
        return hub.store.events_after(after, min(limit, 2000))

    @app.get("/api/smoke")
    def smoke():
        return hub.run_smoke()

    @app.get("/api/ping")
    def ping():
        return {"ok": True, "version": __version__}

    @app.get("/api/vault")
    async def vault():
        return await asyncio.to_thread(hub.vault.summary)

    @app.get("/api/vault/search")
    async def vault_search(q: str, archived: bool = False, limit: int = 30):
        def run():
            if hub.index.synced_at is None:          # first search before the watcher's first pass
                hub.index.sync(hub.vault.scan(), hub.vault.read_body)
            return hub.index.search(q, archived=archived, limit=max(1, min(limit, 100)))
        return await asyncio.to_thread(run)

    @app.get("/api/vault/proposals")
    def vault_proposals(status: str | None = None, limit: int = 100):
        return hub.writer.proposals(status, max(1, min(limit, 500)))

    @app.get("/api/vault/history")
    def vault_history(limit: int = 100):
        return hub.writer.history(max(1, min(limit, 500)))

    @app.get("/api/vault/note")
    async def vault_note(ref: str):
        note = await asyncio.to_thread(hub.vault.read, ref)
        if note is None:
            raise HTTPException(404, "no such note in the vault")
        return note

    @app.get("/api/agents")
    def agents():
        def mcp_info(a):
            if a.id in hub.mcp:
                return {"bookshelf_mcp": f"http://{cfg.host}:{cfg.port}{mcp_path(a.id)}/"}
            return {"bookshelf_mcp": "in-process"} if a.vendor == "claude-code" else {}
        return {"lead": cfg.lead_agent, "agents": [a.info() | mcp_info(a) for a in hub.agents.values()]}

    @app.get("/api/models")
    async def models():
        async def one(p):
            try:
                return p.info() | {"models": await p.models(), "error": None}
            except Exception as exc:
                return p.info() | {"models": [], "error": f"{type(exc).__name__}: {exc}"}
        return {"providers": await asyncio.gather(*(one(p) for p in hub.providers.values()))}

    @app.get("/api/agents/{agent_id}/sessions/{sid}/history")
    async def agent_history(agent_id: str, sid: str):
        with agent_errors():
            return await agent(agent_id).history(sid)

    # Pre-A1 routes, still used by the Claude and Hermes panes; same connector calls.
    @app.get("/api/claude/sessions/{sid}/items")
    async def claude_items(sid: str):
        return await agent_history("claude", sid)

    @app.get("/api/hermes/{profile}/sessions/{sid}/messages")
    async def hermes_messages(profile: str, sid: str):
        return await agent_history(f"hermes:{profile}", sid)

    # -- writes ----------------------------------------------------------------------------------
    @app.post("/api/vault/open", dependencies=W)
    def vault_open():
        # Only ever the configured vault: the browser can't name a path to open.
        hub.vault.ensure()
        try:
            open_folder(hub.vault.root)
        except OSError as exc:
            raise HTTPException(500, f"couldn't open the vault folder: {exc}")
        return {"ok": True, "path": str(hub.vault.root)}

    @app.post("/api/vault/proposals", dependencies=W)
    async def vault_propose(body: NewProposal):
        """Store a proposal and put it in the inbox. Nothing is written to the vault here (I1)."""
        r = await hub.submit_proposal(body.agent, body.summary, body.changes)
        if r["status"] == "held":
            return JSONResponse({"status": "held", "detail": r["message"]}, status_code=202)
        if r["status"] == "refused":
            raise HTTPException(400, r["error"])
        return r["proposal"]

    @app.post("/api/vault/batches/{batch_id}/undo", dependencies=W)
    async def vault_undo(batch_id: int):
        try:
            b = await asyncio.to_thread(hub.writer.undo, batch_id)
        except ProposalError as exc:
            raise HTTPException(409, str(exc))
        hub.event("knowledge", "bookshelf", "batch.undone", {"batch": batch_id, "files": b["files"]})
        hub.refresh_vault()
        return b

    @app.post("/api/vault/reindex", dependencies=W)
    async def vault_reindex():
        """Rebuild the search index from the notes (it is only a cache)."""
        stats = await asyncio.to_thread(lambda: hub.index.rebuild(hub.vault.scan(), hub.vault.read_body))
        return stats | {"indexed": hub.index.count()}

    @app.post("/api/agents/{agent_id}/sessions", dependencies=W)
    async def agent_new(agent_id: str, body: NewSession):
        with agent_errors():
            return await agent(agent_id).create_session(body.title, cwd=body.cwd, model=body.model)

    @app.post("/api/agents/{agent_id}/sessions/{sid}/send", dependencies=W)
    async def agent_send(agent_id: str, sid: str, body: Send):
        with agent_errors():
            await agent(agent_id).send(sid, body.text)
        return {"ok": True}

    @app.post("/api/agents/{agent_id}/sessions/{sid}/interrupt", dependencies=W)
    async def agent_interrupt(agent_id: str, sid: str):
        with agent_errors():
            await agent(agent_id).interrupt(sid)
        return {"ok": True}

    # Pre-A1 routes, still used by the Claude and Hermes panes; same connector calls.
    @app.post("/api/claude/sessions", dependencies=W)
    async def claude_new(body: NewSession):
        return await agent_new("claude", body)

    @app.post("/api/claude/sessions/{sid}/send", dependencies=W)
    async def claude_send(sid: str, body: Send):
        return await agent_send("claude", sid, body)

    @app.post("/api/claude/sessions/{sid}/interrupt", dependencies=W)
    async def claude_interrupt(sid: str):
        return await agent_interrupt("claude", sid)

    @app.post("/api/hermes/{profile}/sessions", dependencies=W)
    async def hermes_new(profile: str, body: NewSession):
        return await agent_new(f"hermes:{profile}", body)

    @app.post("/api/hermes/{profile}/sessions/{sid}/send", dependencies=W)
    async def hermes_send(profile: str, sid: str, body: Send):
        return await agent_send(f"hermes:{profile}", sid, body)

    @app.post("/api/hermes/{profile}/sessions/{sid}/stop", dependencies=W)
    async def hermes_stop(profile: str, sid: str):
        return await agent_interrupt(f"hermes:{profile}", sid)

    @app.post("/api/inbox/{item_id}", dependencies=W)
    async def inbox_decide(item_id: str, body: Decision):
        try:
            return await hub.inbox.resolve(item_id, body.choice, body.note)
        except KeyError:
            raise HTTPException(404, "already answered or expired")
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except Exception as exc:
            raise HTTPException(502, str(exc))

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        if not _local_origin(sock.headers.get("origin"), remote):
            await sock.close(code=4403)
            return
        await sock.accept()
        q: asyncio.Queue = asyncio.Queue(maxsize=5000)
        hub.subscribers.add(q)
        try:
            await sock.send_json({"t": "hello", "state": hub.snapshot()})
            while True:
                msg = await q.get()
                if msg is RESYNC:
                    msg = {"t": "hello", "state": hub.snapshot()}
                await sock.send_json(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.subscribers.discard(q)

    for agent_id, (mcp_app, _) in hub.mcp.items():
        app.mount(mcp_path(agent_id), mcp_app)

    dist = ROOT / "ui" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            f = dist / path
            if path and f.is_file() and dist in f.resolve().parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")
    else:
        @app.get("/")
        def no_ui():
            return JSONResponse({"hub": "running", "ui": "not built - run: npm run build in ui/"})

    return app
