"""Claude Code sessions through the Claude Agent SDK, using the user's subscription login.

Every tool call Claude's own permission rules don't already allow goes through `can_use_tool`,
which parks it in the approvals inbox until the user answers. Subscription usage comes from
the CLI's rate_limit_event messages.
"""
from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import replace
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
                              PermissionResultAllow, PermissionResultDeny, ResultMessage,
                              SystemMessage, TextBlock, ThinkingBlock, ToolResultBlock,
                              ToolUseBlock, UserMessage)
from claude_agent_sdk.types import RateLimitEvent, StreamEvent

from .inbox import Inbox, future_resolver

log = logging.getLogger("sage_os")

SYSTEM_APPEND = """
You are running inside Sage OS, the owner's local workspace where you (Claude Code) are the
orchestrator and reviewer for local Hermes agents running on an RTX 5070 Ti.
- Local agent: "Hermes", i.e. the Hermes profile `default` (default model Qwen3.6-35B-A3B); assign
  kanban work to `default`. "Sage OS" is this workspace, not an agent. The kanban board lives in
  Hermes (`hermes kanban ...`; HERMES_BIN points at the CLI).
- Your tool requests are answered by the owner from the Sage OS approvals inbox; ask in chat when a
  decision is his, and keep requests specific.
- Google Drive (G:\\) is read-only. Private bank data lives in data-private/ folders: never commit
  or upload it.
"""


CLI_GLOBS = [
    # The Store (MSIX) build of the desktop app writes %APPDATA% into its package folder; this is
    # where a normal terminal finds it.
    r"%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe",
    # Non-Store installs, and processes running inside the app's own container, see it here.
    r"%APPDATA%\Claude\claude-code\*\claude.exe",
]


def find_cli() -> str | None:
    """Newest claude.exe shipped with the Claude desktop app, else one on PATH."""
    if os.environ.get("SAGE_OS_CLAUDE_CLI"):
        return os.environ["SAGE_OS_CLAUDE_CLI"]
    found = [p for g in CLI_GLOBS for p in glob.glob(os.path.expandvars(g))]

    def ver(p):
        try:
            return [int(x) for x in Path(p).parent.name.split(".")]
        except ValueError:
            return [0]
    if found:
        return max(found, key=ver)
    return shutil.which("claude.exe")


def summarize_input(tool: str, inp: dict) -> str:
    if tool == "Bash":
        return inp.get("command", "")
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return inp.get("file_path") or inp.get("notebook_path", "")
    if tool in ("WebFetch",):
        return inp.get("url", "")
    s = ", ".join(f"{k}={str(v)[:80]}" for k, v in inp.items())
    return s[:400]


class ClaudeSession:
    def __init__(self, mgr: "ClaudeManager", row: dict):
        self.mgr, self.row = mgr, row
        self.client: ClaudeSDKClient | None = None
        self.task: asyncio.Task | None = None
        self.status = "idle"               # idle | running | waiting | error
        self.pending: set[str] = set()     # inbox ids
        self._last_text: str | None = None

    @property
    def id(self):
        return self.row["id"]

    def info(self) -> dict:
        return {**self.row, "status": self.status, "pending": len(self.pending)}

    def _options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            cli_path=self.mgr.cli, cwd=self.row["cwd"], model=self.row.get("model") or None,
            resume=self.row.get("sdk_session_id"), permission_mode="default",
            can_use_tool=self._can_use_tool, include_partial_messages=True,
            setting_sources=["user", "project", "local"],
            system_prompt={"type": "preset", "preset": "claude_code", "append": SYSTEM_APPEND},
            disallowed_tools=["AskUserQuestion"])

    async def _can_use_tool(self, tool, inp, ctx):
        fut = asyncio.get_running_loop().create_future()
        detail = summarize_input(tool, inp)
        reason = getattr(ctx, "decision_reason", None)
        item = self.mgr.inbox.add(
            source="claude", title=f"Claude wants to use {tool}", detail=detail,
            choices=["allow_once", "allow_session", "deny"], resolver=future_resolver(fut),
            context={"session_id": self.id, "session_title": self.row["title"], "tool": tool,
                     "cwd": self.row["cwd"], "reason": reason, "input": inp})
        self.pending.add(item)
        self._set_status("waiting")
        self.mgr.item(self.id, "note", {"text": f"Waiting for your approval: {tool} {detail[:120]}", "approval": item})
        try:
            choice, note = await fut
        finally:
            self.pending.discard(item)
            self._set_status("running")
        if choice == "deny":
            return PermissionResultDeny(message=note or "Denied by the owner from the Sage OS inbox.")
        perms = None
        if choice == "allow_session":
            perms = [replace(s, destination="session") for s in (ctx.suggestions or [])] or None
        return PermissionResultAllow(updated_input=inp, updated_permissions=perms)

    def _set_status(self, st):
        self.status = st
        self.mgr.publish_sessions()

    async def send(self, text: str):
        if self.task and not self.task.done():
            raise RuntimeError("Claude is still working on the previous message")
        self.mgr.item(self.id, "user", {"text": text})
        self.task = asyncio.create_task(self._run(text))

    async def _run(self, text: str):
        self._set_status("running")
        try:
            if self.client is None:
                self.client = ClaudeSDKClient(self._options())
                await self.client.connect()
            await self.client.query(text)
            async for msg in self.client.receive_response():
                self._handle(msg)
            self._set_status("idle")
        except Exception as exc:  # surface everything in the pane
            log.warning("claude session %s failed: %s", self.id, exc)
            self.mgr.item(self.id, "error", {"text": str(exc)})
            await self._drop_client()
            self._set_status("error")

    def _handle(self, msg):
        sid = self.id
        if isinstance(msg, StreamEvent):
            ev = msg.event or {}
            if ev.get("type") == "content_block_delta":
                d = ev.get("delta", {})
                if d.get("type") == "text_delta":
                    self.mgr.delta(sid, d.get("text", ""))
            return
        if isinstance(msg, SystemMessage):
            data = msg.data if isinstance(msg.data, dict) else {}
            if msg.subtype == "init" and data.get("session_id"):
                self.row["sdk_session_id"] = data["session_id"]
                self.row["model_used"] = data.get("model")
                self.mgr.save(self.row)
            return
        if isinstance(msg, RateLimitEvent):
            self.mgr.rate_limit(msg.rate_limit_info)
            return
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock) and b.text.strip():
                    self._last_text = b.text
                    self.mgr.item(sid, "text", {"text": b.text})
                elif isinstance(b, ThinkingBlock) and b.thinking.strip():
                    self.mgr.item(sid, "thinking", {"text": b.thinking})
                elif isinstance(b, ToolUseBlock):
                    self.mgr.item(sid, "tool_use", {"id": b.id, "tool": b.name,
                                                    "summary": summarize_input(b.name, b.input), "input": b.input})
            return
        if isinstance(msg, UserMessage) and isinstance(msg.content, list):
            for b in msg.content:
                if isinstance(b, ToolResultBlock):
                    content = b.content
                    if isinstance(content, list):
                        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
                    self.mgr.item(sid, "tool_result", {"id": b.tool_use_id, "error": bool(b.is_error),
                                                       "text": str(content or "")[:6000]})
            return
        if isinstance(msg, ResultMessage):
            self.row["turns"] = (self.row.get("turns") or 0) + 1
            self.row["updated"] = time.time()
            if msg.session_id:
                self.row["sdk_session_id"] = msg.session_id
            self.mgr.save(self.row)
            if msg.is_error and str(msg.result or "").strip() != (self._last_text or "").strip():
                self.mgr.item(sid, "error", {"text": str(msg.result or msg.subtype)})
            self._last_text = None
            usage = msg.usage or {}
            self.mgr.item(sid, "note", {"text": "turn complete", "turn_end": True,
                                        "ms": msg.duration_ms, "in": usage.get("input_tokens"),
                                        "out": usage.get("output_tokens")})

    async def interrupt(self):
        if self.client and self.status in ("running", "waiting"):
            for item in list(self.pending):   # a pending approval would otherwise hang the turn
                await self.mgr.inbox.resolve(item, "deny", "Interrupted")
            await self.client.interrupt()

    async def _drop_client(self):
        client, self.client = self.client, None
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass


class ClaudeManager:
    def __init__(self, hub, inbox: Inbox, workspaces: list[str]):
        self.hub, self.inbox, self.workspaces = hub, inbox, workspaces
        self.cli = find_cli()
        self.sessions: dict[str, ClaudeSession] = {s["id"]: ClaudeSession(self, s) for s in hub.store.claude_sessions()}
        self.usage: dict = hub.store.load_panels().get("claude_usage", {})
        self.logged_in: bool | None = None     # None = not checked yet

    async def check_auth(self) -> bool | None:
        """`claude auth status` (JSON, no secrets) -> loggedIn. Runs without touching credentials."""
        if not self.cli:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli, "auth", "status", "--json", stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            out, _ = await asyncio.wait_for(proc.communicate(), 30)
            state = bool(json.loads(out.decode("utf-8", "replace")).get("loggedIn"))
        except Exception as exc:
            log.warning("claude auth status failed: %s", exc)
            return self.logged_in
        if state != self.logged_in:
            self.logged_in = state
            self.publish_sessions()
        return state

    async def watch_auth(self):
        """Re-check often while logged out, so the banner clears soon after `auth login`."""
        while True:
            state = await self.check_auth()
            await asyncio.sleep(15 if not state else 600)

    # -- publishing ----------------------------------------------------------------------------
    def publish_sessions(self):
        data = {"sessions": [s.info() for s in sorted(self.sessions.values(), key=lambda s: -s.row["updated"])],
                "cli": self.cli, "workspaces": self.workspaces, "logged_in": self.logged_in}
        self.hub.panel("claude", data)

    def item(self, sid: str, kind: str, data: dict):
        it = self.hub.store.add_chat_item(sid, kind, data)
        self.hub.publish({"t": "chat", "pane": f"claude:{sid}", "op": "item", "item": it})

    def delta(self, sid: str, text: str):
        self.hub.publish({"t": "chat", "pane": f"claude:{sid}", "op": "delta", "text": text})

    def rate_limit(self, info):
        kind = info.rate_limit_type or "unknown"
        # The CLI only includes `utilization` once a window nears its limit; below that it
        # reports status "allowed" and the reset time.
        self.usage[kind] = {"utilization": info.utilization, "status": info.status,
                            "resets_at": info.resets_at, "seen": time.time(), "raw": info.raw or {}}
        self.hub.panel("claude_usage", self.usage)
        self.hub.store.save_panel("claude_usage", self.usage)

    def save(self, row: dict):
        self.hub.store.upsert_claude_session(row)
        self.publish_sessions()

    # -- API ------------------------------------------------------------------------------------
    def create(self, title: str | None, cwd: str | None, model: str | None) -> dict:
        cwd = cwd or self.workspaces[0]
        if not Path(cwd).is_dir():
            raise ValueError(f"not a folder: {cwd}")
        now = time.time()
        row = {"id": f"cs_{uuid.uuid4().hex[:10]}", "title": title or "New session", "cwd": cwd,
               "model": model or None, "sdk_session_id": None, "created": now, "updated": now,
               "cost_usd": 0, "turns": 0}
        self.sessions[row["id"]] = ClaudeSession(self, row)
        self.save(row)
        return row

    def get(self, sid: str) -> ClaudeSession:
        if sid not in self.sessions:
            raise KeyError(sid)
        return self.sessions[sid]

    async def send(self, sid: str, text: str):
        s = self.get(sid)
        if s.row["title"] == "New session":
            s.row["title"] = text.strip().splitlines()[0][:60] or "New session"
        s.row["updated"] = time.time()
        self.save(s.row)
        await s.send(text)

    async def shutdown(self):
        for s in self.sessions.values():
            await s._drop_client()
