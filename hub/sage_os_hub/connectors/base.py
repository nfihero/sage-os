"""Connector interfaces (architecture track A1, DECISIONS D4).

Sage OS owns the core (board, inbox, Bookshelf, safety policy); agents and model servers plug in
behind these two interfaces, so no single agent app is required.

  * AgentConnector  -- something you chat with that can act: Claude Code, a Hermes profile, ...
  * ModelProvider   -- an OpenAI-compatible endpoint that serves models (models.py)

Each agent is addressed by a stable id ("claude", "hermes:default"). Live output goes to the
browser as chat frames on the agent's pane channel (see `pane`). The frame vocabulary is still
connector-specific; one shared vocabulary arrives with team chat (Phase 6, D8).

A connector must never widen what its agent may do: approvals go through the Sage OS inbox, and
the agent keeps its own safeguards (Claude Code permissions, Hermes guardian and write guard).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


# Errors a connector raises; app.py maps them to HTTP status codes. Each subclasses the builtin
# the hub caught before A1, so callers that catch KeyError/RuntimeError/ValueError still work.
class AgentError(Exception):
    """The agent's service failed or is unreachable (HTTP 502)."""


class SessionNotFound(AgentError, KeyError):
    """No such session for this agent (HTTP 404)."""


class AgentBusy(AgentError, RuntimeError):
    """The session is still working on the previous message (HTTP 409)."""


class InvalidRequest(AgentError, ValueError):
    """The request can't be served as given, e.g. an unknown folder (HTTP 400)."""


class AgentConnector(ABC):
    id: str = ""                 # stable address, e.g. "claude", "hermes:default"
    label: str = ""              # shown in the UI
    kind: str = "local"          # "local" (runs on this machine) | "cloud"
    vendor: str = ""             # which integration this is: "claude-code", "hermes", ...
    # What the UI may offer: chat, interrupt, approvals, history, workspaces, model_pick
    capabilities: frozenset[str] = frozenset({"chat"})

    def info(self) -> dict:
        """Public description for the UI. Never include credentials."""
        return {"id": self.id, "label": self.label, "kind": self.kind, "vendor": self.vendor,
                "capabilities": sorted(self.capabilities)}

    def smoke(self) -> list[tuple[str, bool, str]]:
        """Startup checks without network calls: (check, ok, detail)."""
        return []

    def background(self) -> list:
        """Coroutines to run for the hub's lifetime (e.g. a login watcher)."""
        return []

    async def shutdown(self) -> None:
        pass

    @abstractmethod
    def pane(self, session_id: str) -> str:
        """Channel name of the session's live chat frames."""

    @abstractmethod
    async def create_session(self, title: str | None = None, **options) -> dict:
        """Start a session; returns at least {"id": ...}."""

    @abstractmethod
    async def send(self, session_id: str, text: str) -> None:
        """Queue a user message; output streams as chat frames. Raises AgentBusy if mid-turn."""

    async def interrupt(self, session_id: str) -> None:
        raise InvalidRequest(f"{self.label} can't be interrupted")

    async def history(self, session_id: str) -> list[dict]:
        """Past messages of a session, in the connector's own item format."""
        return []
