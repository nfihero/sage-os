"""Report a problem (F1, D32.6): a plain-text report the user reads in full, saved as a file and attached to an email
to the project's address. It carries what helps fix a bug (the user's own words, versions, this computer, what is
connected, recent warnings and errors) and never notes, files, sources or chat text.
"""
from __future__ import annotations

import collections
import datetime as dt
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

from . import __version__
from .engine import hardware

ADDRESS = "roundederror@gmail.com"
KEEP = 60                       # warnings and errors kept in memory, newest last
SHOWN = 30                      # of those, how many go in a report
LINE = 400                      # characters per log line in a report
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
KEYLIKE = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,}|[A-Za-z0-9_-]{32,})\b")


class RecentProblems(logging.Handler):
    """The last warnings and errors this run, in memory only (a report needs no log file)."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.lines: collections.deque[str] = collections.deque(maxlen=KEEP)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        self._guard = threading.local()

    def emit(self, record):
        if getattr(self._guard, "busy", False):
            return
        self._guard.busy = True
        try:
            self.lines.append(self.format(record))
        except Exception:                                 # noqa: BLE001 -- logging never raises
            pass
        finally:
            self._guard.busy = False


PROBLEMS = RecentProblems()


def install() -> None:
    root = logging.getLogger()
    if PROBLEMS not in root.handlers:
        root.addHandler(PROBLEMS)


def scrub(text: str) -> str:
    """Take out what identifies the person or could be a secret: the home folder, user name, emails, key-like strings."""
    home = str(Path.home())
    for h in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
        text = text.replace(h, "~")
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if user and len(user) > 2:
        text = re.sub(rf"\b{re.escape(user)}\b", "<user>", text, flags=re.I)
    text = EMAIL.sub(lambda m: m.group() if m.group() == ADDRESS else "<email>", text)
    return KEYLIKE.sub("<hidden>", text)


def os_name() -> str:
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0] or '?'} ({platform.machine()})"
    if sys.platform == "win32":
        v = sys.getwindowsversion()
        return f"Windows {'11' if v.build >= 22000 else '10'} build {v.build} ({platform.machine()})"
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


def build(hub, description: str, doing: str) -> str:
    """The whole report, exactly as it will be saved."""
    e = hub.engine.status() if hub.engine else None
    try:
        hw = (e or {}).get("hardware") or hardware()
    except Exception:                                     # noqa: BLE001 -- a report is still worth sending without it
        hw = {}
    gpu = hw.get("gpu") or {}
    serving = (e or {}).get("serving")
    agents = sorted({"Claude Code" if a.vendor == "claude-code" else "Hermes" if a.vendor == "hermes" else "model chat"
                     for a in hub.agents.values()})
    providers = sorted(p.id for p in hub.providers.values())
    failed = [f"{k}: {j['error']}" for k, j in ((e or {}).get("jobs") or {}).items() if j.get("state") == "failed"]
    vault = hub.panels.get("vault") or {}
    sem = hub.panels.get("semantic") or {}
    lines = [
        "SAGE OS PROBLEM REPORT",
        f"Made: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "What happened (your words):",
        (description.strip() or "(nothing written)"),
        "",
        "What you were doing:",
        (doing.strip() or "(nothing written)"),
        "",
        "App",
        f"  Sage OS {__version__} · {'installed app' if getattr(sys, 'frozen', False) else 'from source'}",
        f"  Running for {round((time.time() - hub.started) / 60)} min",
        "",
        "This computer",
        f"  {os_name()}",
        f"  Memory {hw.get('ram_gb', '?')} GB · graphics {gpu.get('name', 'none')}"
        + (f" {gpu.get('vram_gb')} GB" if gpu.get("vram_gb") else "") + f" · runs models on {hw.get('backend', '?')}",
        "",
        "Connected",
        f"  AIs: {', '.join(agents) or 'none'} · model services: {', '.join(providers) or 'none'}",
        f"  Model on this computer: {serving['id'] + (' (ready)' if serving.get('ready') else ' (loading)') if serving else 'none running'}"
        + f" · llama.cpp {'installed' if (e or {}).get('binary') else 'not installed'}",
        f"  Search by meaning: {'ready' if sem.get('installed') else 'not ready'} · notes in the library: {vault.get('count', '?')}",
    ]
    if failed:
        lines += ["", "Downloads that failed", *[f"  {f}" for f in failed]]
    recent = list(PROBLEMS.lines)[-SHOWN:]
    lines += ["", f"Recent warnings and errors ({len(recent)})"]
    lines += [f"  {line[:LINE]}" for line in recent] or ["  none"]
    lines += ["", "Not included: your notes, documents, sources, chats and API keys."]
    return scrub("\n".join(lines)) + "\n"


def folder() -> Path:
    """Where the report file goes: Downloads when there is one, else the home folder."""
    d = Path.home() / "Downloads"
    return d if d.is_dir() else Path.home()


def save(text: str, where: Path | None = None) -> Path:
    where = where or folder()
    where.mkdir(parents=True, exist_ok=True)
    path = where / f"sage-os-report-{dt.datetime.now():%Y%m%d-%H%M%S}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def mailto(path: Path, description: str) -> str:
    first = (description.strip().splitlines() or ["problem report"])[0][:80]
    body = (f"Hi,\n\nSomething went wrong in Sage OS {__version__}: {first}\n\n"
            f"The report file is attached: {path.name} (saved in {scrub(str(path.parent))}).\n")
    q = urllib.parse.urlencode({"subject": f"Sage OS problem: {first}", "body": scrub(body)}, quote_via=urllib.parse.quote)
    return f"mailto:{ADDRESS}?{q}"


def open_email(url: str) -> None:
    if os.name == "nt":
        os.startfile(url)                                 # noqa: S606 -- the user's own mail app
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", url])
