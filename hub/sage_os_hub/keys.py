"""Secrets in the OS keychain (Windows Credential Manager, macOS Keychain) under "Sage OS": never in a file, never
synced, never sent to the browser.

  * API keys pasted into the app (D40), tested against the provider before they're saved.
  * The Google sign-in token (Y2), moved here from google-token.json.
  * Each device's own pairing key (Y2, for P1; see sync/devicekey.py).
The engine's key needs no keeping: a new one is made each time the engine starts and lives only in memory.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("sage_os.keys")
SERVICE = "Sage OS"

# The services a key can connect, with where users get one (shown in the Connect guide)
CLOUD = {
    "openai": {"label": "ChatGPT (OpenAI)", "base_url": "https://api.openai.com/v1",
               "key_url": "https://platform.openai.com/api-keys", "prefix": "sk-",
               "billing": "Paid per use, separate from a ChatGPT Plus subscription: add a payment method or credit at platform.openai.com → Billing."},
    "gemini": {"label": "Gemini (Google)", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "key_url": "https://aistudio.google.com/apikey", "prefix": "",
               "billing": "Google AI Studio keys start on a free tier with daily limits; turning on billing raises them."},
}


class Keys:
    def __init__(self, backend=None):
        self._kr = backend
        self._cache: dict[str, str | None] = {}

    @property
    def kr(self):
        if self._kr is None:
            import keyring
            self._kr = keyring
        return self._kr

    def get(self, service: str) -> str | None:
        if service not in self._cache:
            try:
                self._cache[service] = self.kr.get_password(SERVICE, service)
            except Exception as exc:                  # noqa: BLE001 -- no keychain here: behave as not connected
                log.warning("keychain unavailable: %s", exc)
                self._cache[service] = None
        return self._cache[service]

    def set(self, service: str, key: str) -> None:
        self.kr.set_password(SERVICE, service, key)
        self._cache[service] = key

    def delete(self, service: str) -> None:
        try:
            self.kr.delete_password(SERVICE, service)
        except Exception:                             # noqa: BLE001 -- already gone
            pass
        self._cache[service] = None


def usable(keys: "Keys") -> bool:
    """Whether this computer has a working OS keychain (a Linux box without one doesn't)."""
    try:
        keys.kr.get_password(SERVICE, "__probe__")
        return True
    except Exception:                                 # noqa: BLE001 -- no backend
        return False


class KeychainJSON:
    """A JSON secret (the Google sign-in token, Y2) kept in the OS keychain, moved there from the plain file that
    held it before. Without a keychain it stays in the file (owner-only permissions), and the log says so."""
    LIMIT = 1200                                       # Windows Credential Manager holds 2,560 bytes (1,280 characters)

    def __init__(self, keys: "Keys", name: str, legacy: "Path | None" = None, droppable: tuple[str, ...] = ()):
        self.keys, self.name, self.legacy, self.droppable = keys, name, legacy, droppable
        self.in_keychain = usable(keys)
        if self.in_keychain:
            self.migrate()
        else:
            log.warning("no OS keychain: %s stays in %s", name, legacy)

    def migrate(self) -> None:
        if not (self.legacy and self.legacy.exists()):
            return
        try:
            obj = json.loads(self.legacy.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.set(obj)
        if self.get() == self._fit(obj):
            self.legacy.unlink(missing_ok=True)
            log.info("moved %s from %s into the OS keychain", self.name, self.legacy.name)

    def _fit(self, obj: dict) -> dict:
        """Drop what can be fetched again (an access token) if the whole thing won't fit in the keychain."""
        if len(json.dumps(obj)) <= self.LIMIT:
            return obj
        return {k: v for k, v in obj.items() if k not in self.droppable}

    def get(self) -> dict | None:
        if self.in_keychain:
            raw = self.keys.get(self.name)
            return json.loads(raw) if raw else None
        try:
            return json.loads(self.legacy.read_text(encoding="utf-8")) if self.legacy else None
        except (OSError, ValueError):
            return None

    def set(self, obj: dict) -> None:
        if self.in_keychain:
            self.keys.set(self.name, json.dumps(self._fit(obj)))
            return
        assert self.legacy is not None
        self.legacy.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.legacy.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.legacy)

    def delete(self) -> None:
        if self.in_keychain:
            self.keys.delete(self.name)
        if self.legacy:
            self.legacy.unlink(missing_ok=True)
