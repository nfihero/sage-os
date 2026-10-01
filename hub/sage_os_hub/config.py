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
        "board": 5, "gpu": 3, "health": 2, "safety": 1, "sessions": 30, "vault": 5})
    vault: Path = ROOT / "data" / "vault"         # [bookshelf] vault (D6)
    vault_index: Path = ROOT / "data" / "bookshelf-index.db"   # [bookshelf] index: a rebuildable cache (D10)
    pinned_profiles: list[str] = field(default_factory=lambda: ["default"])
    hidden_profiles: list[str] = field(default_factory=list)
    profile_labels: dict[str, str] = field(default_factory=dict)
    safety_feed_size: int = 200
    claude_workspaces: list[str] = field(default_factory=lambda: [str(Path.home() / "hermes-workspace")])
    # [agents]: which connectors run (D4) and who answers team chat by default (D8)
    lead_agent: str = "claude"
    claude_enabled: bool = True
    hermes_profiles: list[str] = field(default_factory=lambda: ["default"])
    # [[models]]: extra OpenAI-compatible endpoints ({id, label, base_url, kind, api_key_env})
    model_providers: list[dict] = field(default_factory=list)


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
    shelf = raw.get("bookshelf", {})
    if "vault" in shelf:
        vault = Path(shelf["vault"])
        cfg.vault = vault if vault.is_absolute() else ROOT / vault
    if "index" in shelf:
        index = Path(shelf["index"])
        cfg.vault_index = index if index.is_absolute() else ROOT / index
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
    agents = raw.get("agents", {})
    cfg.lead_agent = agents.get("lead", cfg.lead_agent)
    cfg.claude_enabled = bool(agents.get("claude", cfg.claude_enabled))
    cfg.hermes_profiles = list(agents.get("hermes", cfg.hermes_profiles))
    for m in raw.get("models", []):
        if not m.get("id") or not m.get("base_url"):
            raise ValueError(f"config.toml [[models]] entry needs id and base_url: {m}")
        if "api_key" in m:
            raise ValueError(f"config.toml [[models]] {m['id']}: put the key in an environment variable "
                             "and name it with api_key_env; keys don't belong in this file")
    cfg.model_providers = [dict(m) for m in raw.get("models", [])]
    return cfg
