"""Bookshelf proposals (K3): what an agent asks to change in the vault, checked and rendered before
anyone approves it. Nothing here writes to the vault; only the Writer does, and only on approval.

A proposal is one batch of changes, approved or rejected as a unit (BookShelf I9):
  {"op": "create",  "folder", "title", "body", "type"?, "status"?, "tags"?, "links"?}
  {"op": "update",  "uid", "title"?, "body"?, "type"?, "status"?, "tags"?, "links"?}
  {"op": "archive", "uid"}       -- moves the note under Archive/; nothing is deleted
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import os
import re
import time
from dataclasses import dataclass

import yaml

from .vault import ARCHIVE, ATTACHMENTS, ULID, Vault, parse_note, split_frontmatter

OPS = ("create", "update", "archive")
EDITABLE = ("title", "type", "status", "tags", "links")
MAX_CHANGES, MAX_BODY, MAX_DIFF = 50, 200_000, 20_000
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class ProposalError(ValueError):
    """The proposal can't be accepted as written (shown to whoever proposed or approved it)."""


class StaleProposal(ProposalError):
    """A note it changes was edited after the proposal was made."""


def new_ulid(ms: int | None = None) -> str:
    ms = int(time.time() * 1000) if ms is None else ms
    n = (ms << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(CROCKFORD[(n >> (5 * i)) & 31] for i in range(25, -1, -1))


def slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower().encode("ascii", "ignore").decode()).strip("-")
    return s[:80].rstrip("-") or "note"


def sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _dump(data: dict) -> str:
    """One `key: value` block per key; plain lists inline (tags: [a, b]), the way people write them."""
    out = []
    for k, v in data.items():
        if isinstance(v, list) and not any(isinstance(x, (list, dict)) for x in v):
            key = yaml.safe_dump({k: 0}, allow_unicode=True).rsplit(":", 1)[0]
            out.append(f"{key}: {yaml.safe_dump(v, default_flow_style=True, allow_unicode=True, width=1000).strip()}\n")
        else:
            out.append(yaml.safe_dump({k: v}, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000))
    return "".join(out)


def compose(fm: dict, body: str) -> bytes:
    body = body if body.endswith("\n") else body + "\n"
    return f"---\n{_dump(fm)}---\n{body}".encode("utf-8")


TOP_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:")


def edit_frontmatter(raw: str, updates: dict) -> str:
    """Rewrite only the keys in `updates`; every other line stays byte for byte (comments, quoting,
    the user's own list style, plugin keys). Falls back to a full rewrite if the result wouldn't
    read back as exactly the intended data."""
    blocks: list[list] = []                         # [top-level key or None, lines]
    for ln in raw.splitlines(keepends=True):
        m = TOP_KEY.match(ln)
        if m:
            blocks.append([m.group(1), [ln]])
        elif blocks and blocks[-1][0] is not None and (ln[:1] in (" ", "\t", "-") or not ln.strip()):
            blocks[-1][1].append(ln)                # the key's continuation: list items, indented values
        else:
            blocks.append([None, [ln]])
    for b in blocks:
        if b[0] in updates:
            b[1] = [_dump({b[0]: updates[b[0]]})]
    out = "".join("".join(b[1]) for b in blocks)
    if out and not out.endswith("\n"):
        out += "\n"
    out += "".join(_dump({k: v}) for k, v in updates.items() if k not in {b[0] for b in blocks})
    expected = {**(yaml.safe_load(raw) or {}), **updates}
    try:
        if yaml.safe_load(out) == expected:
            return out
    except yaml.YAMLError:
        pass
    return _dump(expected)


def _raw_split(text: str) -> tuple[str, str]:
    """-> (raw frontmatter between the --- lines, body) for a note known to have frontmatter."""
    lines = text.splitlines(keepends=True)
    end = next(i for i, ln in enumerate(lines[1:], 1) if ln.strip() in ("---", "..."))
    return "".join(lines[1:end]), "".join(lines[end + 1:])


def _text(v, name, limit=300) -> str:
    if not isinstance(v, str) or not v.strip() or len(v) > limit or "\n" in v:
        raise ProposalError(f"{name} must be one line of text (1-{limit} characters)")
    return v.strip()


def _clean_folder(folder) -> str:
    parts = [p for p in re.split(r"[\\/]+", _text(folder, "folder", 200)) if p]
    if not parts or any(p in (".", "..") or p.startswith(".") or ":" in p for p in parts):
        raise ProposalError("folder must be a vault-relative path like 'Finance' or 'Finance/Valuation'")
    if parts[0] in (ARCHIVE, ATTACHMENTS):
        raise ProposalError(f"new notes can't go in {parts[0]}/")
    return "/".join(parts)


def _clean_fields(change: dict) -> dict:
    out = {}
    for k in ("title", "type", "status"):
        if k in change:
            out[k] = _text(change[k], k)
    for k in ("tags", "links"):
        if k in change:
            v = change[k]
            if not isinstance(v, list) or len(v) > 50:
                raise ProposalError(f"{k} must be a list (at most 50)")
            out[k] = [_text(x, k[:-1], 80) for x in v]
    if any(not ULID.match(u) for u in out.get("links", [])):
        raise ProposalError("links must be note uids (ULIDs)")
    if "body" in change:
        if not isinstance(change["body"], str) or len(change["body"]) > MAX_BODY:
            raise ProposalError(f"body must be text up to {MAX_BODY} characters")
        out["body"] = change["body"]
    return out


def normalize(changes: list) -> list[dict]:
    """Check the request's shape; give new notes their uid now so the preview and the file agree."""
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_CHANGES:
        raise ProposalError(f"a proposal has 1-{MAX_CHANGES} changes")
    out = []
    for ch in changes:
        op = ch.get("op") if isinstance(ch, dict) else None
        if op not in OPS:
            raise ProposalError(f"op must be one of {', '.join(OPS)}")
        if op == "create":
            fields = _clean_fields(ch)
            if "title" not in fields or "body" not in fields:
                raise ProposalError("create needs a title and a body")
            out.append({"op": op, "folder": _clean_folder(ch.get("folder", "Inbox")), "uid": new_ulid(), **fields})
        else:
            uid = ch.get("uid")
            if not isinstance(uid, str) or not ULID.match(uid):
                raise ProposalError(f"{op} needs the note's uid")
            fields = _clean_fields(ch) if op == "update" else {}
            if op == "update" and not fields:
                raise ProposalError("update changes nothing")
            out.append({"op": op, "uid": uid, **fields})
    uids = [c["uid"] for c in out if c["op"] != "create"]
    if len(uids) != len(set(uids)):
        raise ProposalError("each note may appear only once in a proposal")
    return out


@dataclass
class Entry:
    """One file change: bytes before and after (None = no file). The journal stores exactly these."""
    path: str
    before: bytes | None
    after: bytes | None


@dataclass
class Planned:
    change: dict
    entries: list[Entry]
    title: str
    path: str
    from_path: str | None = None

    def preview(self) -> dict:
        new = next((e.after for e in self.entries if e.after is not None), None)
        old = next((e.before for e in self.entries if e.before is not None), None)
        if self.change["op"] == "archive":
            diff = f"move {self.from_path}\n  -> {self.path}\n(content unchanged)"
        else:
            diff = "".join(difflib.unified_diff(
                (old or b"").decode("utf-8", "replace").splitlines(keepends=True),
                (new or b"").decode("utf-8", "replace").splitlines(keepends=True),
                fromfile="/dev/null" if old is None else self.path, tofile=self.path, n=2))
        if len(diff) > MAX_DIFF:
            diff = diff[:MAX_DIFF] + "\n… (diff truncated)"
        return {"op": self.change["op"], "uid": self.change["uid"], "title": self.title, "path": self.path,
                "from_path": self.from_path, "diff": diff}


def plan(vault: Vault, changes: list[dict], agent: str, bases: dict[str, str] | None = None) -> list[Planned]:
    """Render every change against the vault as it is now.

    `bases` (path -> sha256 at proposal time) makes this refuse notes edited since the proposal.
    Every rendered note must pass the vault contract, or nothing is planned (I9).
    """
    notes = vault.scan()
    by_uid = {}
    for n in notes:
        by_uid.setdefault(n.uid, []).append(n)
    taken = {n.path.lower() for n in notes}
    now = dt.datetime.now().replace(microsecond=0)
    out = []
    for ch in changes:
        if ch["op"] == "create":
            stem, i = slugify(ch["title"]), 1
            path = f"{ch['folder']}/{stem}.md"
            while path.lower() in taken or (vault.root / path).exists():
                i += 1
                path = f"{ch['folder']}/{stem}-{i}.md"
            fm = {"uid": ch["uid"], "title": ch["title"], "created": now, "updated": now,
                  "type": ch.get("type", "note"), "status": ch.get("status", "active"),
                  "origin": "agent", "agent": agent}
            for k in ("tags", "links"):
                if ch.get(k):
                    fm[k] = ch[k]
            after = compose(fm, ch["body"])
            entries, title, from_path = [Entry(path, None, after)], ch["title"], None
        else:
            found = by_uid.get(ch["uid"], [])
            if len(found) != 1:
                raise ProposalError(f"no single note has uid {ch['uid']}" if not found else f"uid {ch['uid']} is duplicated in the vault")
            note = found[0]
            before = (vault.root / note.path).read_bytes()
            if bases is not None and bases.get(note.path) != sha(before):
                raise StaleProposal(f"{note.path} changed after this was proposed; reject it and propose again")
            if note.problems:
                raise ProposalError(f"{note.path} doesn't follow the vault contract ({'; '.join(note.problems)}); fix it first")
            if ch["op"] == "archive":
                if note.archived:
                    raise ProposalError(f"{note.path} is already archived")
                path = f"{ARCHIVE}/{note.path}"
                if (vault.root / path).exists():
                    raise ProposalError(f"{path} already exists")
                entries, title, from_path = [Entry(path, None, before), Entry(note.path, before, None)], note.title, note.path
            else:
                text = before.decode("utf-8")
                fm = split_frontmatter(text)[0]
                raw, body = _raw_split(text.lstrip("﻿"))
                updates = {k: ch[k] for k in EDITABLE if k in ch} | {"updated": now}
                if not (fm.get("origin") == "agent" and fm.get("agent") == agent):
                    updates["edited_by"] = list(dict.fromkeys([*(fm.get("edited_by") or []), agent]))
                if "body" in ch:
                    body = ch["body"] if ch["body"].endswith("\n") else ch["body"] + "\n"
                after = f"---\n{edit_frontmatter(raw, updates)}---\n{body}".encode("utf-8")
                path, title, from_path = note.path, ch.get("title", note.title), None
                entries = [Entry(path, before, after)]
        taken.add(path.lower())             # later changes in this batch can't reuse the name
        for e in entries:
            if e.after is not None:
                problems = parse_note(e.path, e.after.decode("utf-8"))[0].problems
                if problems:
                    raise ProposalError(f"{e.path} would break the vault contract: {'; '.join(problems)}")
        out.append(Planned(ch, entries, title, path, from_path))
    return out
