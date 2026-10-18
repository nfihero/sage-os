"""Five minutes to value, measured (U2, D47): how long a fresh install takes to reach each first, and the first
questions to suggest from a person's own documents.

The milestones stay on this computer (`firstrun.json` in app data, LOCAL) and are only ever seen by the person: on
the screen and in a problem report they choose to send. No analytics (D43).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

FILE = "firstrun.json"
MILESTONES = ("ai_ready", "first_document", "first_answer")


class FirstRun:
    def __init__(self, data_dir: Path, fresh: bool):
        """`fresh`: this app data folder had no databases yet, so this start is the install's first."""
        self.path = Path(data_dir) / FILE
        self.lock = threading.Lock()
        self.data: dict = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}
        elif fresh:
            self.data = {"started": time.time()}
            self._save()

    @property
    def measuring(self) -> bool:
        return "started" in self.data

    def mark(self, name: str) -> None:
        """Record a milestone the first time it happens (only on an install that started fresh)."""
        if not self.measuring or name in self.data:
            return
        with self.lock:
            if name in self.data:
                return
            self.data[name] = time.time()
            self._save()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data), encoding="utf-8")
        except OSError:
            pass

    def summary(self) -> dict | None:
        """-> {"ai_ready": seconds after start, …} for the milestones reached, or None on an install measured before."""
        if not self.measuring:
            return None
        t0 = self.data["started"]
        return {m: round(self.data[m] - t0) for m in MILESTONES if m in self.data}


def minutes(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def starter_questions(sources, notes: int, limit: int = 4) -> list[str]:
    """First questions built from the person's newest documents, so the first answer is about their own work."""
    with sources.lock:
        rows = sources.db.execute("SELECT rel FROM files WHERE status='indexed' ORDER BY mtime DESC LIMIT 6").fetchall()
    titles = []
    for (rel,) in rows:
        stem = Path(rel).stem.replace("_", " ").replace("-", " ").strip()
        if stem and stem.lower() not in (t.lower() for t in titles):
            titles.append(stem[:70])
    out = []
    if titles:
        out.append(f"What are the main points of “{titles[0]}”?")
    if len(titles) > 1:
        out.append(f"How does “{titles[1]}” relate to “{titles[0]}”?")
    if titles:
        out.append("Summarize what's in my documents in five bullet points.")
        out.append("What should I follow up on, based on my documents?")
    elif notes:
        out += ["What's in my notes?", "Summarize my most recent notes."]
    else:
        out += ["What can you help me with?", "How do I give you my documents?"]
    return out[:limit]
