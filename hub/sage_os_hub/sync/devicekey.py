"""Each device's own key pair (Y2, for pairing in P1; D43). The private half lives in the OS keychain and never
leaves this computer; the public half is what another device checks when the two pair, and its short fingerprint is
what a person compares on the two screens.
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from ..keys import Keys, usable

log = logging.getLogger("sage_os.sync")


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def fingerprint(public: bytes) -> str:
    """Twelve characters a person can compare: 'K3F9-2QXA-7MLD'."""
    h = base64.b32encode(hashlib.sha256(public).digest()).decode()[:12]
    return "-".join(h[i:i + 4] for i in range(0, 12, 4))


class DeviceKey:
    def __init__(self, private: Ed25519PrivateKey):
        self._private = private
        self.public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    @property
    def public_b64(self) -> str:
        return _b64(self.public)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.public)

    def sign(self, data: bytes) -> bytes:
        return self._private.sign(data)

    @staticmethod
    def verify(public_b64: str, signature: bytes, data: bytes) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(_unb64(public_b64)).verify(signature, data)
            return True
        except Exception:                             # noqa: BLE001 -- any failure is "not verified"
            return False

    @classmethod
    def load(cls, keys: Keys, device_id: str) -> "DeviceKey | None":
        """This device's key, made on first start. None (and pairing unavailable) without an OS keychain."""
        if not usable(keys):
            log.warning("no OS keychain: this device has no pairing key, so it can't pair with others yet")
            return None
        name = f"device-key:{device_id}"
        raw = keys.get(name)
        if raw:
            try:
                return cls(Ed25519PrivateKey.from_private_bytes(_unb64(raw)))
            except ValueError:
                log.warning("the pairing key in the keychain was damaged; making a new one")
        private = Ed25519PrivateKey.generate()
        keys.set(name, _b64(private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                  serialization.NoEncryption())))
        return cls(private)
