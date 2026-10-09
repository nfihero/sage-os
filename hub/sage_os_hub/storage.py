"""Where Sage OS keeps things (DECISIONS D25).

  * App data (per computer, never synced): databases, indexes, copies of sources, models, sign-ins. In the
    OS's app-data folder, so updating or reinstalling the app never touches it.
  * The Library (what moves between a user's devices): Notes/ (the markdown notes agents search) and Files/
    (any documents the user drops in, indexed where they are). By default inside app data; the user can
    point it at a folder their sync service already syncs (OneDrive, iCloud Drive, Dropbox, Syncthing).
    Each device builds its own indexes from it.

Sync services resolve clashes by keeping both copies under a new name ("note-DESKTOP-AB12.md", "note 2.md",
"note (conflicted copy).md", "note.sync-conflict-…md"); those are listed so the user can pick one.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import socket
import tempfile
import time
import zipfile
from pathlib import Path

# Syncthing ".sync-conflict-20261009-101500-ABC", Dropbox "(… conflicted copy …)", OneDrive "-DESKTOP-AB12C" (the
# computer's name in capitals), iCloud " 2". A name only counts when the plain-named file sits next to it.
CONFLICT = re.compile(r"(\.sync-conflict-\d{8}-\d{6}(?:-[A-Z0-9]+)?|\s?\((?i:[^)]*conflicted copy[^)]*)\)"
                      r"|-(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{2,14}(?=\.\w+$)| \d+(?=\.\w+$))")
SYNC_HINTS = {"onedrive": "OneDrive", "icloud": "iCloud Drive", "mobile documents": "iCloud Drive", "dropbox": "Dropbox",
              "google drive": "Google Drive", "my drive": "Google Drive", "sync": "Syncthing"}


def folder_size(path: Path, limit: int = 200_000) -> tuple[int, int]:
    """(bytes, files) under path, giving up after `limit` files."""
    total = n = 0
    for dp, _, fns in os.walk(path):
        for f in fns:
            try:
                total += (Path(dp) / f).stat().st_size
            except OSError:
                continue
            n += 1
            if n >= limit:
                return total, n
    return total, n


def sync_service(path: Path) -> str | None:
    low = str(path).lower()
    return next((name for hint, name in SYNC_HINTS.items() if hint in low), None)


def conflicts(library: Path) -> list[str]:
    """Files a sync service kept as a second copy (both edited on two devices), relative to the Library."""
    out = []
    for sub in ("Notes", "Files"):
        root = library / sub
        if not root.is_dir():
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if not d.startswith(".")]
            for f in fns:
                stem = Path(f).stem
                original = CONFLICT.sub("", f)
                if f != original and (Path(dp) / original).exists():   # only when the plain-named file is there too
                    out.append((Path(dp) / f).relative_to(library).as_posix())
                elif ".sync-conflict-" in f or "conflicted copy" in stem.lower():
                    out.append((Path(dp) / f).relative_to(library).as_posix())
    return sorted(set(out))


def export_notes(notes: Path, files: Path | None = None) -> Path:
    """A zip of the notes (markdown + attachments), and the Library's files if given. -> the zip's path."""
    stamp = time.strftime("%Y-%m-%d")
    out = Path(tempfile.mkdtemp(prefix="sage-export-")) / f"Sage OS notes {stamp}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, prefix in ((notes, "Notes"), (files, "Files")):
            if not base or not base.is_dir():
                continue
            for dp, dns, fns in os.walk(base):
                dns[:] = [d for d in dns if not d.startswith(".")]
                for f in fns:
                    if f.startswith(".") or f.endswith(".tmp"):
                        continue
                    p = Path(dp) / f
                    z.write(p, f"{prefix}/{p.relative_to(base).as_posix()}")
    return out


def merge_into(src: Path, dst: Path) -> dict:
    """Copy everything in src into dst without overwriting: a file that exists in both with different bytes
    is copied as "<name> (from <this computer>).<ext>" so nothing is lost. -> counts."""
    host = re.sub(r"[^A-Za-z0-9-]", "", socket.gethostname())[:20] or "this computer"
    copied = same = kept_both = 0
    if not src.is_dir():
        return {"copied": 0, "same": 0, "kept_both": 0}
    for dp, _, fns in os.walk(src):
        for f in fns:
            a = Path(dp) / f
            b = dst / a.relative_to(src)
            b.parent.mkdir(parents=True, exist_ok=True)
            if not b.exists():
                shutil.copy2(a, b)
                copied += 1
            elif a.read_bytes() == b.read_bytes():
                same += 1
            else:
                alt = b.with_name(f"{b.stem} (from {host}){b.suffix}")
                if not alt.exists():
                    shutil.copy2(a, alt)
                kept_both += 1
    return {"copied": copied, "same": same, "kept_both": kept_both}


def set_local_setting(config_local: Path, section: str, key: str, value: str) -> None:
    """Write `key = 'value'` under [section] in config.local.toml (per computer, untracked), keeping the rest."""
    text = config_local.read_text(encoding="utf-8-sig") if config_local.exists() else ""
    line = f"{key} = '{value}'"                     # literal string: Windows backslashes stay as they are
    if "'" in value:
        raise ValueError("folder paths with ' aren't supported")
    head = re.search(rf"(?m)^\[{re.escape(section)}\]\s*$", text)
    if not head:
        text = text.rstrip("\n") + f"\n\n[{section}]\n{line}\n"
    else:
        start = head.end()
        nxt = re.search(r"(?m)^\[", text[start:])
        end = start + nxt.start() if nxt else len(text)
        body = text[start:end]
        if re.search(rf"(?m)^{re.escape(key)}\s*=", body):
            body = re.sub(rf"(?m)^{re.escape(key)}\s*=.*$", lambda _: line, body)   # literal: paths have backslashes
        else:
            body = "\n" + line + body
        text = text[:start] + body + text[end:]
    config_local.write_text(text, encoding="utf-8")


# -- moving an install from before D25 (data/ next to the code) into app data -------------------------
def move_legacy(old: Path, new: Path) -> dict:
    """Copy data/ into app data (the vault becoming Library/Notes), check every file, then rename data/ to
    data.moved-<date> (kept until the user deletes it). The hub must be stopped first."""
    if not (old / "hub.db").exists():
        raise SystemExit(f"nothing to move: {old} isn't a Sage OS data folder")
    if (new / "hub.db").exists():
        raise SystemExit(f"{new} already holds Sage OS data; not overwriting it")
    plan = []
    for dp, _, fns in os.walk(old):
        for f in fns:
            a = Path(dp) / f
            rel = a.relative_to(old)
            parts = rel.parts
            target = new / "Library" / "Notes" / Path(*parts[1:]) if parts[0] == "vault" else new / rel
            plan.append((a, target))
    for a, b in plan:
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(a, b)
    bad = [str(a) for a, b in plan if hashlib.sha256(a.read_bytes()).digest() != hashlib.sha256(b.read_bytes()).digest()]
    if bad:
        raise SystemExit(f"{len(bad)} files didn't copy exactly (e.g. {bad[0]}); {old} is untouched")
    (new / "Library" / "Files").mkdir(parents=True, exist_ok=True)
    moved = old.with_name(f"{old.name}.moved-{time.strftime('%Y%m%d-%H%M%S')}")
    old.rename(moved)
    return {"files": len(plan), "to": str(new), "old_kept_as": str(moved)}
