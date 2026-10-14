"""Loads config.toml from the sage-os root (one level above hub/), then config.local.toml on top of it if
present. The local file is per machine and untracked: paths that differ between the PC and a Mac go there
(D21)."""
from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Bundled in the desktop app (PyInstaller, F1): config.toml and ui/dist sit inside the bundle, read-only and replaced by
# every update, so this computer's own settings (config.local.toml) live in app data instead.
FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parents[2]


def local_config_path() -> Path:
    return default_data_dir() / "config.local.toml" if FROZEN else ROOT / "config.local.toml"


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8787
    remote_hosts: list[str] = field(default_factory=list)     # [hub] remote_hosts: exact names (Phase 3)
    # [storage] (D25): app data is per computer and never synced; the Library (Notes/ + Files/) is what moves
    # between a user's devices. Paths left as None are derived from them in __post_init__.
    data_dir: Path | None = None
    library: Path | None = None
    local_config: Path = field(default_factory=lambda: local_config_path())   # per-computer settings (the Library, …)
    store: Path | None = None
    keep_events: int = 5000
    hermes_home: Path = field(default_factory=lambda: default_hermes_home())
    gateway: str = "http://127.0.0.1:8642"
    router: str = "http://127.0.0.1:18434"
    sidecar: str = "http://127.0.0.1:18435"
    poll: dict[str, float] = field(default_factory=lambda: {
        "board": 5, "gpu": 3, "health": 2, "safety": 1, "sessions": 30, "vault": 5})
    vault: Path | None = None                     # [bookshelf] vault (D6): Library/Notes (D25)
    vault_index: Path | None = None               # [bookshelf] index: a rebuildable cache (D10)
    vault_journal: Path | None = None             # [bookshelf] journal: proposals + undo history (D11)
    # [[sources]]: read-only copies of folders, searchable by the user and agents (D15)
    sources: list[dict] = field(default_factory=list)
    sources_root: Path | None = None
    sources_index: Path | None = None
    # [google]: the user's own OAuth client (Desktop app) and where the read-only Drive token is kept (D22)
    google_client: Path | None = None
    google_token: Path | None = None
    pinned_profiles: list[str] = field(default_factory=lambda: ["default"])
    hidden_profiles: list[str] = field(default_factory=list)
    profile_labels: dict[str, str] = field(default_factory=dict)
    safety_feed_size: int = 200
    claude_workspaces: list[str] = field(default_factory=lambda: [str(Path.home() / "hermes-workspace")])
    # [agents]: which connectors run (D4) and who answers team chat by default (D8)
    lead_agent: str = ""                                    # none until the user picks one (D39: ships empty)
    claude_enabled: bool = False
    hermes_profiles: list[str] = field(default_factory=list)
    # [[models]]: extra OpenAI-compatible endpoints ({id, label, base_url, kind, api_key_env})
    model_providers: list[dict] = field(default_factory=list)
    chat_enabled: bool = True                                  # [agents] chat: the OpenAI-compatible chat (D22.2)
    # [engine]: Sage OS's own llama-server (D22.3)
    engine_enabled: bool = True
    engine_root: Path | None = None
    engine_port: int = 8790
    engine_binary: str | None = None                           # an existing llama-server instead of a download
    engine_model_dirs: list[str] = field(default_factory=list)  # folders with GGUF files already on this computer


    def __post_init__(self):
        d = self.data_dir = Path(self.data_dir) if self.data_dir else default_data_dir()
        for name, default in (("store", d / "hub.db"), ("vault_index", d / "bookshelf-index.db"),
                              ("vault_journal", d / "bookshelf.db"), ("sources_root", d / "sources"),
                              ("sources_index", d / "sources-index.db"), ("google_client", d / "google-oauth-client.json"),
                              ("google_token", d / "google-token.json"), ("engine_root", d / "engine")):
            if getattr(self, name) is None:
                setattr(self, name, default)
        if self.vault is None:
            if self.library is None and (d / "vault").is_dir():
                self.vault = d / "vault"                  # an install from before D25 (data/vault): until it is moved
            else:
                self.library = Path(self.library) if self.library else d / "Library"
                self.vault = self.library / "Notes"
        elif self.library is not None:
            self.library = Path(self.library)


def app_data_dir() -> Path:
    """Where an installed app keeps a user's data on this OS (D25)."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Sage OS"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Sage OS"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "sage-os"


def default_data_dir() -> Path:
    """SAGE_OS_DATA, else an existing pre-D25 data/ folder next to the code (until it is moved), else app data."""
    if os.environ.get("SAGE_OS_DATA"):
        return Path(os.environ["SAGE_OS_DATA"]).expanduser()
    legacy = ROOT / "data"
    if (legacy / "hub.db").exists():
        return legacy
    return app_data_dir()


def default_hermes_home() -> Path:
    """Where Hermes keeps its state when config.toml doesn't say ([hermes] home)."""
    if sys.platform == "win32":
        return Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes"))
    return Path.home() / ".hermes"


def here(value: str) -> Path:
    """A path setting: `~` is the user's home on any OS; relative paths are relative to the sage-os root."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def merge(base: dict, over: dict) -> dict:
    """config.local.toml over config.toml: tables merge key by key; lists ([[sources]], [[models]]) and
    plain values are replaced whole."""
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path: Path | None = None) -> Config:
    default = path is None and not os.environ.get("SAGE_OS_CONFIG")
    path = path or Path(os.environ.get("SAGE_OS_CONFIG", ROOT / "config.toml"))
    local = local_config_path() if default and FROZEN else path.with_name(path.stem + ".local.toml")
    if not path.exists() and not local.exists():
        return Config()
    # utf-8-sig: Windows Notepad (and PowerShell 5) save UTF-8 with a byte-order mark, which TOML rejects
    raw = tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    if local.exists():
        raw = merge(raw, tomllib.loads(local.read_text(encoding="utf-8-sig")))
    hub, hermes, ui = raw.get("hub", {}), raw.get("hermes", {}), raw.get("ui", {})
    storage, shelf0 = raw.get("storage", {}), raw.get("bookshelf", {})
    # Storage first: every data path not set explicitly is derived from these (D25).
    cfg = Config(data_dir=here(storage["data"]) if storage.get("data") else None,
                 library=here(storage["library"]) if storage.get("library") else None,
                 vault=here(shelf0["vault"]) if shelf0.get("vault") else None,
                 store=here(hub["store"]) if hub.get("store") else None, local_config=local)
    cfg.host = hub.get("host", cfg.host)
    cfg.port = int(hub.get("port", cfg.port))
    cfg.remote_hosts = [str(h).lower() for h in hub.get("remote_hosts", cfg.remote_hosts)]
    if any("*" in h for h in cfg.remote_hosts):
        raise ValueError("config.toml [hub] remote_hosts takes exact host names, no wildcards")
    cfg.keep_events = int(hub.get("keep_events", cfg.keep_events))
    shelf = shelf0
    for s in raw.get("sources", []):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", str(s.get("name", ""))) or not s.get("path"):
            raise ValueError(f"config.toml [[sources]] needs a lower-case name (letters, digits, -) and a path: {s}")
    cfg.sources = [dict(s) | {"path": os.path.expanduser(str(s["path"]))} for s in raw.get("sources", [])]
    for key, attr in (("index", "vault_index"), ("journal", "vault_journal")):
        if key in shelf:
            setattr(cfg, attr, here(shelf[key]))
    google = raw.get("google", {})
    for key, attr in (("client", "google_client"), ("token", "google_token")):
        if key in google:
            setattr(cfg, attr, here(google[key]))
    if "home" in hermes:
        cfg.hermes_home = Path(hermes["home"]).expanduser()
    cfg.gateway = hermes.get("gateway", cfg.gateway).rstrip("/")
    cfg.router = hermes.get("router", cfg.router).rstrip("/")
    cfg.sidecar = hermes.get("sidecar", cfg.sidecar).rstrip("/")
    cfg.poll.update({k: float(v) for k, v in raw.get("poll", {}).items()})
    cfg.pinned_profiles = list(ui.get("pinned_profiles", cfg.pinned_profiles))
    cfg.hidden_profiles = list(ui.get("hidden_profiles", cfg.hidden_profiles))
    cfg.profile_labels = dict(ui.get("profile_labels", cfg.profile_labels))
    cfg.safety_feed_size = int(ui.get("safety_feed_size", cfg.safety_feed_size))
    cfg.claude_workspaces = [os.path.expanduser(str(w)) for w in raw.get("claude", {}).get("workspaces", cfg.claude_workspaces)]
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
    cfg.chat_enabled = bool(agents.get("chat", cfg.chat_enabled))
    eng = raw.get("engine", {})
    cfg.engine_enabled = bool(eng.get("enabled", cfg.engine_enabled))
    if "root" in eng:
        cfg.engine_root = here(eng["root"])
    cfg.engine_port = int(eng.get("port", cfg.engine_port))
    cfg.engine_binary = str(here(eng["binary"])) if eng.get("binary") else None
    cfg.engine_model_dirs = [str(here(d)) for d in eng.get("model_dirs", [])]
    return cfg
