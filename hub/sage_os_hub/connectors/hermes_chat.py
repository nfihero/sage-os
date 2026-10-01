"""Chat with local Hermes profiles through the gateway's sessions API.

Hermes keeps the transcript; the hub only relays the live stream to the browser and turns
Hermes' approval.request events into inbox items.
"""
from __future__ import annotations

import asyncio
import logging

from .hermes_api import HermesAPI
from ..inbox import Inbox

log = logging.getLogger("sage_os")
CHOICE_LABELS = {"once": "allow_once", "session": "allow_session", "always": "allow_always", "deny": "deny"}


class HermesChat:
    def __init__(self, hub, api: HermesAPI, inbox: Inbox):
        self.hub, self.api, self.inbox = hub, api, inbox
        self.runs: dict[str, dict] = {}        # pane -> {"run_id", "task", "profile"}

    def _emit(self, pane: str, op: str, **kw):
        self.hub.publish({"t": "chat", "pane": pane, "op": op, **kw})

    def status(self) -> dict:
        return {pane: {"run_id": r.get("run_id"), "profile": r["profile"]} for pane, r in self.runs.items()}

    async def send(self, profile: str, session_id: str, text: str):
        pane = f"hermes:{profile}:{session_id}"
        if pane in self.runs:
            raise RuntimeError(f"{profile} is still working on the previous message")
        self.runs[pane] = {"profile": profile, "run_id": None}
        self.runs[pane]["task"] = asyncio.create_task(self._run(pane, profile, session_id, text))
        self.hub.panel("hermes_runs", self.status())

    async def _run(self, pane, profile, session_id, text):
        run = self.runs[pane]
        self._emit(pane, "status", status="running")
        try:
            async for name, p in self.api.chat_stream(profile, session_id, text):
                run_id = p.get("run_id")
                if run_id and not run.get("run_id"):
                    run["run_id"] = run_id
                    self.hub.panel("hermes_runs", self.status())
                if name == "assistant.delta":
                    self._emit(pane, "delta", text=p.get("delta", ""))
                elif name in ("tool.started", "tool.completed", "tool.failed"):
                    self._emit(pane, "tool", event=name, tool=p.get("tool_name"), preview=p.get("preview"))
                elif name == "tool.progress" and p.get("tool_name") == "_thinking":
                    self._emit(pane, "thinking", text=p.get("delta", ""))
                elif name == "assistant.commentary":
                    self._emit(pane, "commentary", text=p.get("text", ""))
                elif name == "approval.request":
                    self._approval(pane, profile, p)
                elif name == "assistant.completed":
                    self._emit(pane, "completed", content=p.get("content", ""))
                elif name in ("run.failed", "error"):
                    self._emit(pane, "error", text=str(p.get("error") or p))
        except Exception as exc:
            log.warning("hermes chat %s failed: %s", pane, exc)
            self._emit(pane, "error", text=str(exc))
        finally:
            for k in self.inbox.keys(f"hermes:{pane}:"):
                self.inbox.drop(k)
            self.runs.pop(pane, None)
            self.hub.panel("hermes_runs", self.status())
            self._emit(pane, "status", status="idle")

    def _approval(self, pane, profile, p):
        run_id, request_id = p.get("run_id"), p.get("request_id") or p.get("id")
        choices = [CHOICE_LABELS.get(c, c) for c in p.get("choices", ["once", "deny"])]
        reverse = {v: k for k, v in CHOICE_LABELS.items()}

        async def resolver(choice, note):
            await self.api.approve(profile, run_id, reverse.get(choice, choice), request_id)

        detail = p.get("command") or p.get("description") or p.get("reason") or ""
        self.inbox.add(source="hermes", title=f"{profile} wants approval", detail=str(detail),
                       choices=choices, resolver=resolver, key=f"hermes:{pane}:{request_id or run_id}",
                       context={"profile": profile, "pane": pane, "run_id": run_id,
                                "reason": p.get("description") or p.get("pattern_key")})

    async def stop(self, profile: str, session_id: str):
        run = self.runs.get(f"hermes:{profile}:{session_id}")
        if run and run.get("run_id"):
            await self.api.stop(profile, run["run_id"])
