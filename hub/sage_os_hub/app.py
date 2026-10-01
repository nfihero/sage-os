"""Sage OS hub: FastAPI app, WebSocket event stream, adapters, chat and the approvals inbox.

Reads come from adapters polling Hermes' files read-only. Writes (Phase 2) go only through
public surfaces: the Claude Agent SDK, Hermes' gateway API and the `hermes` CLI. Every write
route requires the X-Sage-OS header, a local Host and a local Origin. Run: python -m sage_os_hub
"""
from __future__ import annotations

import asyncio
import os
import webbrowser
import logging
import time
from contextlib import asynccontextmanager
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
from .claude_agent import ClaudeManager
from .config import ROOT, Config, load
from .hermes_api import HermesAPI
from .hermes_chat import HermesChat
from .inbox import Inbox
from .store import Store

log = logging.getLogger("sage_os")
LOCAL_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
LOCAL_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "::1"}


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
        self.adapters = [self.kanban, GpuAdapter(self, cfg), HealthAdapter(self, cfg),
                         SafetyAdapter(self, cfg), SessionsAdapter(self, cfg)]
        self.inbox = Inbox(self.publish, self.event)
        self.hermes_api = HermesAPI(cfg.gateway, cfg.hermes_home)
        self.hermes_chat = HermesChat(self, self.hermes_api, self.inbox)
        self.claude = ClaudeManager(self, self.inbox, cfg.claude_workspaces)
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
        results.append({"adapter": "claude", "check": "claude.exe found", "ok": bool(self.claude.cli),
                        "detail": self.claude.cli or "install the Claude desktop app or set SAGE_OS_CLAUDE_CLI"})
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
                        "pinned_profiles": self.cfg.pinned_profiles}}


RESYNC = {"t": "resync"}


def _offer(q: asyncio.Queue, msg):
    try:
        q.put_nowait(msg)
    except asyncio.QueueFull:          # a stalled tab: tell it to reload state instead
        while not q.empty():
            q.get_nowait()
        q.put_nowait(RESYNC)


# -- request bodies ------------------------------------------------------------------------------
class NewClaudeSession(BaseModel):
    title: str | None = None
    cwd: str | None = None
    model: str | None = None


class Send(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


class NewHermesSession(BaseModel):
    title: str | None = None


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
        hub.claude.publish_sessions()
        if start_adapters:
            results = await asyncio.to_thread(hub.run_smoke)
            tasks = [asyncio.create_task(a.run(), name=a.name) for a in hub.adapters]
            tasks.append(asyncio.create_task(hub.claude.watch_auth(), name="claude-auth"))
            bad = [r for r in results if not r["ok"]]
            url = f"http://{cfg.host}:{cfg.port}"
            log.info("READY  %s  (smoke: %d/%d checks ok%s)  Ctrl+C to stop", url, len(results) - len(bad),
                     len(results), "" if not bad else " - see warnings above")
            if os.environ.get("SAGE_OS_OPEN") == "1":
                webbrowser.open(url)
        yield
        for t in tasks:
            t.cancel()
        await hub.claude.shutdown()
        hub.store.close()

    app = FastAPI(title="Sage OS hub", version=__version__, lifespan=lifespan)
    app.state.hub = hub
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS + ["*.ts.net"])

    def local_write(request: Request):
        """CSRF guard: a custom header forces a CORS preflight, which this app never grants."""
        if request.headers.get("x-sage-os") != "1" or not _local_origin(request.headers.get("origin")):
            raise HTTPException(403, "write requests must come from the Sage OS UI")

    W = [Depends(local_write)]

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

    @app.get("/api/claude/sessions/{sid}/items")
    def claude_items(sid: str):
        return hub.store.chat_items(sid)

    @app.get("/api/hermes/{profile}/sessions/{sid}/messages")
    async def hermes_messages(profile: str, sid: str):
        try:
            return await hub.hermes_api.messages(profile, sid)
        except Exception as exc:
            raise HTTPException(502, f"Hermes: {exc}")

    # -- writes ----------------------------------------------------------------------------------
    @app.post("/api/claude/sessions", dependencies=W)
    def claude_new(body: NewClaudeSession):
        try:
            return hub.claude.create(body.title, body.cwd, body.model)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/claude/sessions/{sid}/send", dependencies=W)
    async def claude_send(sid: str, body: Send):
        try:
            await hub.claude.send(sid, body.text)
        except KeyError:
            raise HTTPException(404, "no such session")
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        return {"ok": True}

    @app.post("/api/claude/sessions/{sid}/interrupt", dependencies=W)
    async def claude_interrupt(sid: str):
        try:
            await hub.claude.get(sid).interrupt()
        except KeyError:
            raise HTTPException(404, "no such session")
        return {"ok": True}

    @app.post("/api/hermes/{profile}/sessions", dependencies=W)
    async def hermes_new(profile: str, body: NewHermesSession):
        try:
            return await hub.hermes_api.create_session(profile, body.title)
        except Exception as exc:
            raise HTTPException(502, f"Hermes: {exc}")

    @app.post("/api/hermes/{profile}/sessions/{sid}/send", dependencies=W)
    async def hermes_send(profile: str, sid: str, body: Send):
        try:
            await hub.hermes_chat.send(profile, sid, body.text)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        return {"ok": True}

    @app.post("/api/hermes/{profile}/sessions/{sid}/stop", dependencies=W)
    async def hermes_stop(profile: str, sid: str):
        await hub.hermes_chat.stop(profile, sid)
        return {"ok": True}

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
