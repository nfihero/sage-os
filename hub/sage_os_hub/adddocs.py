"""Adding your documents from the app (O0, D41.1): no config file and no Explorer needed.

  * ADD FILES: files picked in the app are saved into the Bookshelf's Files folder (D25) and indexed there.
  * ADD A FOLDER: the computer's own folder picker; the folder becomes a source (D15), copied read-only and indexed,
    and is remembered in this computer's config.local.toml.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from pathlib import Path

MAX_FILE = 500 * 2**20                # 500 MB a file
PICKING = threading.Lock()             # one folder picker at a time
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def safe_name(name: str) -> str:
    """A file name that is safe on Windows and macOS: no folders, no reserved names, no odd characters."""
    base = BAD.sub("_", Path(name.replace("\\", "/")).name).strip(" .")
    stem = base.split(".")[0].lower()
    if not base or stem in RESERVED:
        base = f"document_{base or 'file'}"
    return base[:180]


def unique(folder: Path, name: str) -> Path:
    """`name`, or `name (2)`, `name (3)`… when a different file already has it."""
    p = folder / name
    stem, suffix, n = p.stem, p.suffix, 2
    while p.exists():
        p = folder / f"{stem} ({n}){suffix}"
        n += 1
    return p


def source_name(folder: Path, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", folder.name.lower()).strip("-")[:40] or "folder"
    name, n = base, 2
    while name in taken or name == "library":
        name, n = f"{base}-{n}", n + 1
    return name


def remember_source(config_local: Path, name: str, path: Path) -> None:
    """Add a [[sources]] entry to this computer's config.local.toml, keeping everything else."""
    if "'" in str(path):
        raise ValueError("folder paths with ' aren't supported yet")
    text = config_local.read_text(encoding="utf-8-sig") if config_local.exists() else ""
    config_local.parent.mkdir(parents=True, exist_ok=True)
    block = f"\n[[sources]]   # added in the app\nname = '{name}'\npath = '{path}'\n"
    config_local.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")


def pick_folder(timeout: float = 600) -> str | None:
    """The computer's own folder picker, in front of other windows. -> a path, or None when cancelled."""
    if os.name == "nt":
        script = ("Add-Type -AssemblyName System.Windows.Forms;"
                  "$o=New-Object System.Windows.Forms.Form -Property @{TopMost=$true;ShowInTaskbar=$false};"
                  "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                  "$d.Description='Choose a folder of documents for Sage OS to read';$d.ShowNewFolderButton=$false;"
                  "if($d.ShowDialog($o) -eq 'OK'){[Console]::Out.Write($d.SelectedPath)}")
        cmd = ["powershell", "-NoProfile", "-STA", "-NonInteractive", "-Command", script]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    elif sys.platform == "darwin":
        cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choose a folder of documents for Sage OS to read")']
        flags = 0
    else:
        cmd = ["zenity", "--file-selection", "--directory", "--title=Choose a folder of documents for Sage OS to read"]
        flags = 0
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags)
    out = r.stdout.strip()
    return out.rstrip("/") or None if out else None
