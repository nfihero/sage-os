"""What syncs and what stays on this computer (Y1.3, D27.4 (d), matching D25).

Every database table and every file or folder in app data is listed here. A test fails when a new one isn't,
so nothing new can be forgotten when sync arrives:

  * SYNCED: records every device should end up with (chats, decisions, the undo journal, digest progress,
    briefings). Their changes go to the change log (Y1.4) and they get ULIDs (Y1.6).
  * LOCAL: this computer only: live dashboard state, search indexes (each device rebuilds its own), copies of
    sources, the engine and its models, sign-ins and secrets, this device's identity.
  * LIBRARY: the notes and files folder, which moves between devices by itself (D25).
"""
from __future__ import annotations

from fnmatch import fnmatch

SYNCED, LOCAL, LIBRARY, LOG = "synced", "local", "library", "log"
LOG_TABLE = "changes"           # the change log itself, in each database with synced tables (Y1.4)

# database file -> table -> kind. A whole database can be one kind ("*").
TABLES: dict[str, dict[str, str]] = {
    "hub.db": {
        "chat_sessions": SYNCED,        # chats with any OpenAI-compatible model (D22.2)
        "chat_items": SYNCED,           # messages of those chats and of Claude sessions
        "claude_sessions": SYNCED,      # the session record; resuming it still needs the CLI on the computer that ran it
        "threads": SYNCED,              # the one chat space's conversations, each one or more AI sessions (W3, D39)
        "usage": SYNCED,                # tokens and cost per reply, so spend adds up across devices (D40)
        "price_overrides": SYNCED,      # the user's corrections to the price list (D40)
        "events": LOCAL,                # the live dashboard's catch-up feed, trimmed to the newest 5,000
        "panels": LOCAL,                # latest panel snapshots (GPU, board, health)
        "peers": LOCAL,                 # this device's paired devices; each keeps its own list (P1, D45)
    },
    "bookshelf.db": {                   # proposals, the user's decisions and the undo journal (D11, D24)
        "proposals": SYNCED,
        "batches": SYNCED,
        "entries": SYNCED,
        "trust": SYNCED,                # each agent's trust level and role, set by the user (K7, D36)
        "agent_log": SYNCED,            # everything each agent did, kept in full (K7)
    },
    "digest.db": {                      # long-document digests and their progress (D23)
        "jobs": SYNCED,
        "chapters": SYNCED,
        "secs": SYNCED,
    },
    "briefings.db": {                   # what each chat message was briefed with, and per-chat settings (D20)
        "briefings": SYNCED,
        "briefing_chats": SYNCED,
    },
    "bookshelf-index.db": {"*": LOCAL},     # keyword index of the notes, rebuilt from the Library (D10)
    "sources-index.db": {"*": LOCAL},       # index of source copies; each device keeps its own sources
    "semantic.db": {"*": LOCAL},            # meaning-vectors of notes and sources, rebuilt per device (K14, D27.4)
}

# each synced table's key: the columns that name one record across devices
KEYS: dict[str, tuple[str, ...]] = {
    "chat_sessions": ("id",), "chat_items": ("id",), "claude_sessions": ("id",), "threads": ("id",), "usage": ("id",),
    "price_overrides": ("provider", "model"),
    "proposals": ("id",), "batches": ("id",), "entries": ("batch_id", "seq"),
    "trust": ("key",), "agent_log": ("id",),
    "jobs": ("id",), "chapters": ("job", "chapter"), "secs": ("job", "idx"),
    "briefings": ("id",), "briefing_chats": ("chat",),
}

# SQLite's own bookkeeping, never ours to sync
INTERNAL_TABLES = ("sqlite_*",)

# top-level names in app data -> kind (glob patterns allowed)
FILES: dict[str, str] = {
    "Library": LIBRARY,
    "device.json": LOCAL,               # this install's identity (Y1.1)
    "device.damaged-*.json": LOCAL,
    "gamemode.json": LOCAL,             # game mode settings: a game on this computer (G1)
    "engine": LOCAL,                    # llama-server builds and models (D22.3)
    "sources": LOCAL,                   # read-only copies of source folders (D15)
    "google-token.json": LOCAL,         # Drive sign-in before 0.29: moved into the OS keychain on first start (Y2)
    "google-oauth-client.json": LOCAL,  # the user's own OAuth client
    "client_secret_*.json": LOCAL,      # the same, under the name Google downloads it with
    "backups": LOCAL,                   # database copies made before a migration (Y1.6)
    "*.db-wal": LOCAL,                  # SQLite's write-ahead files follow their database
    "*.db-shm": LOCAL,
    "*.db-journal": LOCAL,
}


def table_kind(db: str, table: str) -> str | None:
    """SYNCED / LOCAL for a table, or None when it isn't listed (a test treats that as a bug)."""
    if any(fnmatch(table, p) for p in INTERNAL_TABLES):
        return LOCAL
    if table == LOG_TABLE and any(k == SYNCED for k in TABLES.get(db, {}).values()):
        return LOG
    tables = TABLES.get(db)
    if tables is None:
        return None
    if table in tables:
        return tables[table]
    for pattern, kind in tables.items():
        if fnmatch(table, pattern):
            return kind
    return None


def file_kind(name: str) -> str | None:
    if name in TABLES:
        return TABLES[name].get("*", SYNCED)    # a database with synced tables syncs through the change log
    if name in FILES:
        return FILES[name]
    for pattern, kind in FILES.items():
        if fnmatch(name, pattern):
            return kind
    return None


def synced_tables() -> dict[str, list[str]]:
    return {db: [t for t, k in tables.items() if k == SYNCED and t != "*"]
            for db, tables in TABLES.items() if any(k == SYNCED for k in tables.values())}
