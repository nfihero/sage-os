"""Adapter interface. Each adapter polls one outside system and reports through an Emitter.

Adapters only read. Two things come out of them:
  * panel(name, data)  -- the latest full state of a UI panel (board, gpu, health, ...)
  * event(kind, type, data, persist) -- something that happened, for the live stream
"""
from __future__ import annotations

import asyncio
import logging
from typing import Protocol

log = logging.getLogger("sage_os")


class Emitter(Protocol):
    def panel(self, name: str, data, *, broadcast: bool = True) -> None: ...
    def event(self, kind: str, source: str, type_: str, data: dict, *,
              persist: bool = True, ts: float | None = None) -> None: ...


class Adapter:
    name = "adapter"
    interval = 5.0

    def __init__(self, emit: Emitter):
        self.emit = emit
        self.last_error: str | None = None

    def poll(self) -> None:
        """One synchronous poll. Runs in a worker thread so slow I/O never blocks the loop."""
        raise NotImplementedError

    def smoke(self) -> list[tuple[str, bool, str]]:
        """Startup checks: (check name, ok, detail). Used to name what a Hermes update broke."""
        return []

    async def run(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.poll)
                if self.last_error:
                    log.info("%s recovered", self.name)
                self.last_error = None
            except Exception as exc:  # keep polling; surface the error in the UI
                msg = f"{type(exc).__name__}: {exc}"
                if msg != self.last_error:
                    log.warning("%s poll failed: %s", self.name, msg)
                    self.emit.event("system", self.name, "adapter.error", {"error": msg}, persist=False)
                self.last_error = msg
            await asyncio.sleep(self.interval)
