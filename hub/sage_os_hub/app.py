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
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
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
from .knowledge import Vault
from .store import Store

log = logging.getLogger("sage_os")
LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
LOCAL_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "::1"}


def open_folder(path: Path) -> None:
    """Show a folder in the desktop's file manager (Explorer on Windows)."""
    if os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _local_origin(origin: str | None) -> bool:
    if not origin:
        return True
    host = urlparse(origin).hostname or ""
    return host in LOCAL_ORIGIN_HOSTS or host.endswith(".ts.net")


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
        self.adapters = [self.kanban, GpuAdapter(self, cfg), HealthAdapter(self, cfg),
                         SafetyAdapter(self, cfg), SessionsAdapter(self, cfg),
                         VaultAdapter(self, self.vault, cfg.poll["vault"])]
        self.inbox = Inbox(self.publish, self.event)
        self.agents: dict[str, AgentConnector] = build_agents(self, cfg)
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
        tasks = []
        if hub.claude:
            hub.claude.publish_sessions()
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
        hub.store.close()

    app = FastAPI(title="Sage OS hub", version=__version__, lifespan=lifespan)
    app.state.hub = hub
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS + ["*.ts.net"])

    def local_write(request: Request):
        """CSRF guard: a custom header forces a CORS preflight, which this app never grants."""
        if request.headers.get("x-sage-os") != "1" or not _local_origin(request.headers.get("origin")):
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

    @app.get("/api/vault/note")
    async def vault_note(ref: str):
        note = await asyncio.to_thread(hub.vault.read, ref)
        if note is None:
            raise HTTPException(404, "no such note in the vault")
        return note

    @app.get("/api/agents")
    def agents():
        return {"lead": cfg.lead_agent, "agents": [a.info() for a in hub.agents.values()]}

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
        if not _local_origin(sock.headers.get("origin")):
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
