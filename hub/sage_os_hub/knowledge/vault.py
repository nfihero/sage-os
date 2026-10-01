"""Reads the vault: markdown notes with YAML frontmatter (vault contract v1, DECISIONS D9).

K1 is read-only. Writes arrive with K3 and go only through propose -> inbox approval -> a
single writer (BookShelf I1, I2, I9). Notes that break the contract are still listed, with
their problems named, never hidden or silently fixed.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from .screen import screen

REQUIRED = ("uid", "title", "created", "updated", "type", "status", "origin")
ORIGINS = ("human", "imported", "scanned", "captured", "agent")
ATTACHMENTS, ARCHIVE = "Attachments", "Archive"
ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Windows drive, UNC, POSIX root, home-relative or file: URL -- all forbidden in the vault (I8)
ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/|~[\\/]|file:)", re.I)
MD_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)")


def split_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """-> (frontmatter or None, body, error). Frontmatter is a leading `---` ... `---` block."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text, None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() in ("---", "..."):
            raw, body = "".join(lines[1:i]), "".join(lines[i + 1:])
            try:
                data = yaml.safe_load(raw) if raw.strip() else {}
            except yaml.YAMLError as exc:
                return None, body, f"frontmatter is not valid YAML ({str(exc).splitlines()[0]})"
            if not isinstance(data, dict):
                return None, body, "frontmatter is not a key: value mapping"
            return data, body, None
    return None, text, "frontmatter starts with --- but never ends"


def jsonable(v):
    """YAML gives dates and datetimes; the browser gets ISO strings."""
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _strings(x)


def _list(v) -> list[str]:
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]


@dataclass
class Note:
    path: str                          # relative to the vault, forward slashes
    folder: str                        # top-level folder, "" for the vault root
    title: str
    uid: str | None = None
    type: str | None = None
    status: str | None = None
    origin: str | None = None
    agent: str | None = None           # who wrote it, when origin is "agent"
    created: str | None = None
    updated: str | None = None
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)   # uids (I8)
    archived: bool = False
    problems: list[str] = field(default_factory=list)
    sensitive: str | None = None       # screening category (K4): the file stays, its text skips the index
    size: int = 0
    mtime: float = 0.0

    @property
    def ref(self) -> str:
        """How the UI asks for this note: its uid when that is valid and unique, else its path."""
        usable = self.uid and ULID.match(self.uid) and not any(p.startswith("duplicate uid") for p in self.problems)
        return self.uid if usable else self.path


def parse_note(rel: str, text: str, size: int = 0, mtime: float = 0.0) -> tuple[Note, dict, str]:
    """-> (note summary, frontmatter, body). Validates against the vault contract."""
    fm, body, err = split_frontmatter(text)
    parts = rel.split("/")
    stem = parts[-1][:-3]
    heading = next((ln[2:].strip() for ln in body.splitlines() if ln.startswith("# ")), None)
    problems = [err] if err else []
    has_block = fm is not None
    fm = fm or {}
    if not err and not has_block:
        problems.append("no frontmatter")
    missing = [k for k in REQUIRED if fm.get(k) in (None, "")]
    if has_block and missing:
        problems.append("missing " + ", ".join(missing))
    uid = str(fm["uid"]) if fm.get("uid") not in (None, "") else None
    if uid and not ULID.match(uid):
        problems.append("uid is not a ULID (26 characters, Crockford base32)")
    origin = str(fm["origin"]) if fm.get("origin") else None
    if origin and origin not in ORIGINS:
        problems.append(f"origin must be one of {', '.join(ORIGINS)}")
    if origin == "agent" and not fm.get("agent"):
        problems.append("origin: agent needs an `agent` id saying who wrote it")
    if any(ABSOLUTE.match(s.strip()) for s in _strings(fm)):
        problems.append("absolute path in frontmatter (links and sources must be vault-relative or uids)")
    if any(ABSOLUTE.match(t) for t in MD_LINK.findall(body)):
        problems.append("absolute path in a link")
    if not SLUG.match(stem):
        problems.append("file name isn't a slug (lowercase letters, digits, hyphens)")
    note = Note(path=rel, folder=parts[0] if len(parts) > 1 else "", title=str(fm.get("title") or heading or stem),
                uid=uid, type=fm.get("type") and str(fm["type"]), status=fm.get("status") and str(fm["status"]),
                origin=origin, agent=fm.get("agent") and str(fm["agent"]),
                created=jsonable(fm.get("created")), updated=jsonable(fm.get("updated")),
                tags=_list(fm.get("tags")), links=_list(fm.get("links")), archived=parts[0] == ARCHIVE,
                problems=problems, sensitive=screen(text), size=size, mtime=mtime)
    return note, fm, body


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._cache: dict[str, tuple[tuple[int, int], Note]] = {}

    def ensure(self) -> None:
        """Create the vault skeleton. Only folders: the app never authors notes (BookShelf I7)."""
        for d in (self.root, self.root / ATTACHMENTS, self.root / ARCHIVE):
            d.mkdir(parents=True, exist_ok=True)

    def _files(self):
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and
                             not (Path(dirpath) == self.root and d == ATTACHMENTS))
            for f in sorted(files):
                if f.lower().endswith(".md") and not f.startswith("."):
                    yield Path(dirpath) / f

    def scan(self) -> list[Note]:
        """All notes, re-parsing only files whose size or mtime changed."""
        notes, seen = [], set()
        for p in self._files():
            rel = p.relative_to(self.root).as_posix()
            try:
                st = p.stat()
                key = (st.st_mtime_ns, st.st_size)
                hit = self._cache.get(rel)
                if hit and hit[0] == key:
                    note = hit[1]
                else:
                    note = parse_note(rel, p.read_text(encoding="utf-8", errors="replace"), st.st_size, st.st_mtime)[0]
                    self._cache[rel] = (key, note)
            except OSError:
                continue
            seen.add(rel)
            notes.append(Note(**{**asdict(note), "problems": list(note.problems)}))
        for rel in set(self._cache) - seen:
            del self._cache[rel]
        by_uid: dict[str, Note] = {}
        for n in notes:
            if n.uid:
                if n.uid in by_uid:
                    n.problems.append(f"duplicate uid (also {by_uid[n.uid].path})")
                    by_uid[n.uid].problems.append(f"duplicate uid (also {n.path})")
                else:
                    by_uid[n.uid] = n
        return notes

    def read_body(self, rel: str) -> str | None:
        """A note's body (frontmatter stripped), or None if it is gone or outside the vault."""
        p = (self.root / rel).resolve()
        if self.root.resolve() not in p.parents:
            return None
        try:
            return split_frontmatter(p.read_text(encoding="utf-8", errors="replace"))[1]
        except OSError:
            return None

    def summary(self, notes: list[Note] | None = None) -> dict:
        """The Bookshelf panel: every note's metadata (no bodies), links resolved to titles."""
        notes = self.scan() if notes is None else notes
        titles = {n.uid: n.title for n in notes if n.uid}
        rows = []
        for n in notes:
            row = asdict(n) | {"ref": n.ref}
            row["links"] = [{"uid": u, "title": titles.get(u)} for u in n.links]
            rows.append(row)
        folders = sorted({n.folder for n in notes})
        return {"root": str(self.root), "exists": self.root.is_dir(), "count": len(notes),
                "problems": sum(1 for n in notes if n.problems), "folders": folders, "notes": rows}

    def read(self, ref: str) -> dict | None:
        """One note by uid, or by vault-relative path for notes without a usable uid."""
        notes = self.scan()
        match = next((n for n in notes if n.ref == ref), None)
        if match is None:
            return None
        p = (self.root / match.path).resolve()
        if self.root.resolve() not in p.parents:
            return None
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        note, fm, body = parse_note(match.path, text, match.size, match.mtime)
        titles = {n.uid: n.title for n in notes if n.uid}
        return asdict(note) | {"ref": match.ref, "problems": match.problems, "frontmatter": jsonable(fm),
                               "body": body, "source": text,
                               "links": [{"uid": u, "title": titles.get(u)} for u in note.links]}
