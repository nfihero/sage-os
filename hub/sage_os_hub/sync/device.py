"""This install's identity (Y1.1): a permanent ID and a name, kept in app data as device.json.

App data is per computer and never synced (D25), so two computers sharing one Library still have different
IDs. Every change will be stamped with the ID; the name is only for people ("Sam's PC").
"""
from __future__ import annotations

import json
import logging
import os
import platform
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .ids import is_id, new_id

log = logging.getLogger("sage_os.sync")

PREFIX = "dv_"
FILE = "device.json"
MAX_NAME = 60


@dataclass
class Device:
    id: str
    name: str
    created: float
    path: Path | None = None

    @classmethod
    def load(cls, data_dir: Path) -> "Device":
        """Read device.json, or make one on first start. A damaged file is set aside (never deleted) and a
        new identity made: the old one can't be trusted to be unique if we guess at it."""
        path = Path(data_dir) / FILE
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8-sig"))
                if is_id(raw.get("id", ""), PREFIX) and isinstance(raw.get("name"), str):
                    return cls(raw["id"], clean_name(raw["name"]) or default_name(), float(raw.get("created", 0)), path)
            except (OSError, ValueError, TypeError):
                pass
            bad = path.with_name(f"device.damaged-{int(time.time())}.json")
            path.replace(bad)
            log.warning("device.json was damaged; kept as %s and made a new device identity", bad.name)
        dev = cls(new_id(PREFIX), default_name(), time.time(), path)
        dev.save()
        return dev

    def rename(self, name: str) -> None:
        name = clean_name(name)
        if not name:
            raise ValueError("give the device a name")
        self.name = name
        self.save()

    def save(self) -> None:
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(self).items() if k != "path"}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".device.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "created": self.created}


def clean_name(name: str) -> str:
    return " ".join(str(name).split())[:MAX_NAME]


def default_name() -> str:
    return clean_name(platform.node()) or "This computer"
