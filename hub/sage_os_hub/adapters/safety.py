"""Safety feed: tails the guardian-gate and write-guard JSONL logs (read-only)."""
from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from pathlib import Path

from .base import Adapter

LOGS = {"guardian": "guardian-gate.log", "write-guard": "write-guard.log"}
QUIET = {"allow", "sidecar_revived"}      # streamed live, not stored as events
TAIL_BYTES = 512 * 1024


def _epoch(ts) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except ValueError:
        return 0.0


def normalize(gate: str, rec: dict) -> dict:
    targets = rec.get("targets")
    detail = rec.get("text") or ("\n".join(map(str, targets)) if isinstance(targets, list) else targets)
    return {"gate": gate, "event": rec.get("event", "?"), "tool": rec.get("tool"),
            "ts": _epoch(rec.get("ts")), "detail": detail or "", "reason": rec.get("reason"),
            "error": rec.get("error"), "ms": rec.get("ms"), "fail_closed": rec.get("fail_closed")}


class LogTail:
    """Follows one append-only log, surviving truncation and partial trailing lines."""

    def __init__(self, path: Path):
        self.path, self.offset, self.partial = path, 0, b""

    def initial(self, limit: int) -> list[dict]:
        if not self.path.exists():
            return []
        size = self.path.stat().st_size
        with self.path.open("rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            data = f.read()
        self.offset = size
        lines = data.split(b"\n")
        if size > TAIL_BYTES:
            lines = lines[1:]             # first line is probably cut
        return self._parse(lines[-limit - 1:])

    def read_new(self) -> list[dict]:
        if not self.path.exists():
            return []
        size = self.path.stat().st_size
        if size < self.offset:            # rotated or truncated
            self.offset, self.partial = 0, b""
        if size == self.offset:
            return []
        with self.path.open("rb") as f:
            f.seek(self.offset)
            data = f.read(size - self.offset)
        self.offset = size
        lines = (self.partial + data).split(b"\n")
        self.partial = lines.pop()        # '' when the chunk ended with a newline
        return self._parse(lines)

    @staticmethod
    def _parse(lines) -> list[dict]:
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
        return out


class SafetyAdapter(Adapter):
    name = "safety"

    def __init__(self, emit, cfg):
        super().__init__(emit)
        self.interval, self.size = cfg.poll["safety"], cfg.safety_feed_size
        self.tails = {g: LogTail(cfg.hermes_home / "logs" / f) for g, f in LOGS.items()}
        self.feed: deque | None = None

    def smoke(self):
        return [(f"{g} log present", t.path.exists(), str(t.path)) for g, t in self.tails.items()]

    def poll(self):
        if self.feed is None:
            items = [normalize(g, r) for g, t in self.tails.items() for r in t.initial(self.size)]
            items.sort(key=lambda e: e["ts"])
            self.feed = deque(items[-self.size:], maxlen=self.size)
            self.emit.panel("safety", list(self.feed))
            return
        new = [normalize(g, r) for g, t in self.tails.items() for r in t.read_new()]
        if not new:
            return
        new.sort(key=lambda e: e["ts"])
        for e in new:
            self.feed.append(e)
            self.emit.event("system", self.name, f"guard.{e['event']}", e,
                            persist=e["event"] not in QUIET, ts=e["ts"] or None)
        self.emit.panel("safety", list(self.feed), broadcast=False)
