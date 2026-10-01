"""Bookshelf panel: re-reads the vault so notes added or edited outside Sage OS show up."""
from __future__ import annotations

import json

from ..knowledge import Vault
from .base import Adapter


class VaultAdapter(Adapter):
    name = "vault"

    def __init__(self, emit, vault: Vault, interval: float):
        super().__init__(emit)
        self.vault, self.interval = vault, interval
        self._fp = None

    def smoke(self):
        root = self.vault.root
        return [("vault folder exists", root.is_dir(), str(root))]

    def poll(self):
        data = self.vault.summary()
        fp = json.dumps(data, sort_keys=True, default=str)
        if fp != self._fp:
            if self._fp is not None:
                self.emit.event("knowledge", self.name, "vault.changed", {"count": data["count"]}, persist=False)
            self._fp = fp
            self.emit.panel("vault", data)
