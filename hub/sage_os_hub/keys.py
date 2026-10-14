"""AI services connected with an API key pasted into the app (D40). Keys live in the OS keychain (Windows Credential
Manager, macOS Keychain) under "Sage OS"; never in a file, never synced, never sent to the browser. A key is tested
against the provider before it is saved.
"""
from __future__ import annotations

import logging

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
