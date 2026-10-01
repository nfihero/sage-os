"""Hermes Agent as one optional connector (D4): each Hermes profile is an agent ("hermes:<profile>").

Profiles share one gateway client and one chat relay; Hermes keeps the transcripts.
"""
from __future__ import annotations

from .base import AgentBusy, AgentConnector, AgentError
from .hermes_api import HermesAPI
from .hermes_chat import HermesChat


class HermesConnector(AgentConnector):
    kind, vendor = "local", "hermes"
    capabilities = frozenset({"chat", "interrupt", "approvals", "history"})

    def __init__(self, profile: str, label: str, api: HermesAPI, chat: HermesChat):
        self.profile, self.api, self.chat = profile, api, chat
        self.id, self.label = f"hermes:{profile}", label

    def info(self) -> dict:
        return super().info() | {"profile": self.profile}

    def smoke(self):
        pin = self.api._runtime_pin(self.profile)
        return [(f"{self.profile} API key readable", bool(self.api._key(self.profile)), "API_SERVER_KEY in .env"),
                (f"{self.profile} model pinned per turn", bool(pin),
                 pin.get("model", "") or "config.yaml model.default/provider missing: turn 2+ may fail with 401")]

    def pane(self, session_id: str) -> str:
        return f"hermes:{self.profile}:{session_id}"

    async def create_session(self, title: str | None = None, **options) -> dict:
        try:
            return await self.api.create_session(self.profile, title)
        except Exception as exc:
            raise AgentError(f"Hermes: {exc}") from exc

    async def send(self, session_id: str, text: str) -> None:
        try:
            await self.chat.send(self.profile, session_id, text)
        except RuntimeError as exc:
            raise AgentBusy(str(exc)) from exc

    async def interrupt(self, session_id: str) -> None:
        await self.chat.stop(self.profile, session_id)

    async def history(self, session_id: str) -> list[dict]:
        try:
            return await self.api.messages(self.profile, session_id)
        except Exception as exc:
            raise AgentError(f"Hermes: {exc}") from exc
