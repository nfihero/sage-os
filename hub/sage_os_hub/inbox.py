"""The approvals inbox: everything that needs a human, whichever agent raised it.

An item carries the choices its source accepts and a resolver coroutine that delivers the
decision back to that source (Claude's permission callback, a Hermes run approval, a kanban
comment + unblock). Items live in memory: a pending Claude or Hermes request dies with its
run anyway, and kanban items are re-derived from the board on every poll.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable
from .sync import new_id

Resolver = Callable[[str, str], Awaitable[None]]   # (choice, note) -> delivered


class Inbox:
    def __init__(self, publish: Callable[[dict], None], event: Callable[..., None]):
        self._items: dict[str, dict] = {}
        self._resolvers: dict[str, Resolver] = {}
        self._publish = publish
        self._event = event

    def items(self) -> list[dict]:
        """Requests that hold an agent up (approvals, questions) newest first; note proposals after them, oldest
        first, so a digested book reads from its first chapter."""
        return sorted(self._items.values(),
                      key=lambda i: (1, i["created"]) if i["source"] == "bookshelf" else (0, -i["created"]))

    def _changed(self):
        self._publish({"t": "panel", "name": "inbox", "data": self.items()})

    def add(self, *, source: str, title: str, detail: str, choices: list[str], resolver: Resolver,
            context: dict | None = None, key: str | None = None, created: float | None = None) -> str:
        """`key` makes an item idempotent (kanban tasks re-announced on every poll)."""
        item_id = key or new_id("ib_")
        if item_id in self._items:
            return item_id
        self._items[item_id] = {"id": item_id, "source": source, "title": title, "detail": detail,
                                "choices": choices, "context": context or {}, "created": created or time.time()}
        self._resolvers[item_id] = resolver
        self._event("approval", source, "approval.requested", {"id": item_id, "title": title, "source": source})
        self._changed()
        return item_id

    def drop(self, item_id: str) -> None:
        """Withdraw an item whose request went away on its own (run ended, task unblocked elsewhere)."""
        if self._items.pop(item_id, None) is not None:
            self._resolvers.pop(item_id, None)
            self._changed()

    def update(self, item_id: str, context: dict) -> None:
        """Add to a waiting item's context (a reviewer's verdict arriving on a proposal card)."""
        item = self._items.get(item_id)
        if item is not None:
            item["context"] = {**item["context"], **context}
            self._changed()

    def get(self, item_id: str) -> dict | None:
        return self._items.get(item_id)

    def settle(self, item_ids: list[str], choice: str, note: str = "") -> None:
        """Remove items whose decision the hub has already carried out together (K7 batch decisions)."""
        for item_id in item_ids:
            item = self._items.pop(item_id, None)
            self._resolvers.pop(item_id, None)
            if item is not None:
                self._event("approval", item["source"], "approval.resolved",
                            {"id": item_id, "title": item["title"], "choice": choice, "note": note})
        self._changed()

    def keys(self, prefix: str) -> list[str]:
        return [k for k in self._items if k.startswith(prefix)]

    async def resolve(self, item_id: str, choice: str, note: str = "") -> dict:
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(item_id)
        if choice not in item["choices"]:
            raise ValueError(f"choice must be one of {item['choices']}")
        resolver = self._resolvers[item_id]
        await resolver(choice, note)
        self._items.pop(item_id, None)
        self._resolvers.pop(item_id, None)
        self._event("approval", item["source"], "approval.resolved",
                    {"id": item_id, "title": item["title"], "choice": choice, "note": note})
        self._changed()
        return item


def future_resolver(fut: asyncio.Future) -> Resolver:
    async def _resolve(choice: str, note: str) -> None:
        if not fut.done():
            fut.set_result((choice, note))
    return _resolve
