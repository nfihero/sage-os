"""Bookshelf panel: re-reads the vault so notes added or edited outside Sage OS show up, and keeps
the search index in step with it."""
from __future__ import annotations

import json

from ..knowledge import SearchIndex, Vault
from .base import Adapter


class VaultAdapter(Adapter):
    name = "vault"

    def __init__(self, emit, vault: Vault, index: SearchIndex, interval: float):
        super().__init__(emit)
        self.vault, self.index, self.interval = vault, index, interval
        self._fp = None

    def smoke(self):
        root = self.vault.root
        return [("vault folder exists", root.is_dir(), str(root)),
                ("search index (SQLite FTS5) opens", self.index.count() >= 0, str(self.index.path))]

    def poll(self):
        notes = self.vault.scan()
        self.index.sync(notes, self.vault.read_body)
        data = self.vault.summary(notes) | {"indexed": self.index.count()}
        fp = json.dumps(data, sort_keys=True, default=str)
        if fp != self._fp:
            if self._fp is not None:
                self.emit.event("knowledge", self.name, "vault.changed", {"count": data["count"]}, persist=False)
            self._fp = fp
            self.emit.panel("vault", data)
