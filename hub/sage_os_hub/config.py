"""Loads config.toml. The file lives at the sage-os root, one level above hub/."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8787
    store: Path = ROOT / "data" / "hub.db"
    keep_events: int = 5000
    hermes_home: Path = Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes"))
    gateway: str = "http://127.0.0.1:8642"
    router: str = "http://127.0.0.1:18434"
    sidecar: str = "http://127.0.0.1:18435"
    poll: dict[str, float] = field(default_factory=lambda: {
        "board": 5, "gpu": 3, "health": 2, "safety": 1, "sessions": 30})
    pinned_profiles: list[str] = field(default_factory=lambda: ["default"])
    hidden_profiles: list[str] = field(default_factory=list)
    profile_labels: dict[str, str] = field(default_factory=dict)
    safety_feed_size: int = 200
    claude_workspaces: list[str] = field(default_factory=lambda: [str(Path.home() / "hermes-workspace")])


def load(path: Path | None = None) -> Config:
    path = path or Path(os.environ.get("SAGE_OS_CONFIG", ROOT / "config.toml"))
    cfg = Config()
    if not path.exists():
        return cfg
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    hub, hermes, ui = raw.get("hub", {}), raw.get("hermes", {}), raw.get("ui", {})
    cfg.host = hub.get("host", cfg.host)
    cfg.port = int(hub.get("port", cfg.port))
    if "store" in hub:
        store = Path(hub["store"])
        cfg.store = store if store.is_absolute() else ROOT / store
    cfg.keep_events = int(hub.get("keep_events", cfg.keep_events))
    if "home" in hermes:
        cfg.hermes_home = Path(hermes["home"])
    cfg.gateway = hermes.get("gateway", cfg.gateway).rstrip("/")
    cfg.router = hermes.get("router", cfg.router).rstrip("/")
    cfg.sidecar = hermes.get("sidecar", cfg.sidecar).rstrip("/")
    cfg.poll.update({k: float(v) for k, v in raw.get("poll", {}).items()})
    cfg.pinned_profiles = list(ui.get("pinned_profiles", cfg.pinned_profiles))
    cfg.hidden_profiles = list(ui.get("hidden_profiles", cfg.hidden_profiles))
    cfg.profile_labels = dict(ui.get("profile_labels", cfg.profile_labels))
    cfg.safety_feed_size = int(ui.get("safety_feed_size", cfg.safety_feed_size))
    cfg.claude_workspaces = list(raw.get("claude", {}).get("workspaces", cfg.claude_workspaces))
    return cfg
