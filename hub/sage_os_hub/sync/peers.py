"""Paired devices and how they prove who they are (P1, D43, D45). No outside service: two of your devices pair with
a one-time code and from then on talk to each other directly, over TLS, each request signed.

  * **Identity:** each device's Ed25519 key (Y2, devicekey.py). The other device stores its public half when they pair.
  * **The channel:** TLS with a certificate made fresh each start (tls.py). A device proves the certificate is its own
    by signing the certificate's fingerprint with its identity key (`hello`), so a stranger in the middle can't stand
    in for it.
  * **Requests:** every request carries the sender's device ID, a time, a one-use nonce and an Ed25519 signature over
    the method, path, body and the *receiving* side's certificate fingerprint. A request relayed through someone else's
    TLS connection names the wrong certificate and is refused; a replay reuses a nonce and is refused.
  * **Pairing:** the host shows a 12-character code, good for 10 minutes and 5 tries. Each side proves it knows the code
    with an HMAC over both identity keys and the host's certificate, so the code itself never travels and a stranger
    can't swap in their own key. Both screens then show both fingerprints for a person to compare.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time

from .devicekey import DeviceKey, fingerprint, _unb64
from .ids import is_id

CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"     # no 0/O, 1/I/L: easy to read out and type
CODE_LEN = 12                                        # ~59 bits, for 10 minutes and 5 tries
CODE_TTL = 600
CODE_TRIES = 5
SKEW = 300                                           # seconds a signed request may be early or late
SCHEMA = """
CREATE TABLE IF NOT EXISTS peers (
    id        TEXT PRIMARY KEY,       -- the other device's ID (dv_…)
    name      TEXT NOT NULL,
    pubkey    TEXT NOT NULL,          -- its Ed25519 public key, base64url
    address   TEXT,                   -- where it was last reached (host:port), if this side ever connected to it
    added     REAL NOT NULL,
    last_seen REAL,
    removed   REAL                    -- removed: refused from then on (kept, so the log of who it was stays)
);
"""


class PairingError(Exception):
    """Shown to the person as it is."""


def code_norm(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def new_code() -> str:
    raw = "".join(secrets.choice(CODE_CHARS) for _ in range(CODE_LEN))
    return "-".join(raw[i:i + 4] for i in range(0, CODE_LEN, 4))


def proof(code: str, role: str, *parts: str) -> str:
    """HMAC with the pairing code over who's pairing with whom; `role` keeps the two directions apart."""
    msg = "\n".join(("sage-os-pair", role, *parts)).encode()
    return hmac.new(code_norm(code).encode(), msg, hashlib.sha256).hexdigest()


def body_hash(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def request_message(method: str, path: str, ts: str, nonce: str, body: bytes, server_tls: str) -> bytes:
    return "\n".join(("sage-os-request", method.upper(), path, ts, nonce, body_hash(body), server_tls)).encode()


def hello_message(device_id: str, tls_fpr: str) -> bytes:
    return f"sage-os-hello\n{device_id}\n{tls_fpr}".encode()


def tls_fingerprint(cert_der: bytes) -> str:
    return hashlib.sha256(cert_der).hexdigest()


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


class Peers:
    """This computer's list of paired devices (LOCAL: each device keeps its own list), the pairing session it's
    hosting, and the nonces it has seen."""

    def __init__(self, db, lock, me: DeviceKey | None, device_id: str, device_name):
        self.db, self.lock, self.me, self.device_id = db, lock, me, device_id
        self._name = device_name                     # a function: the device can be renamed
        self.session: dict | None = None             # {"code", "expires", "tries"}
        self._nonces: dict[str, float] = {}
        self._nlock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()

    @property
    def name(self) -> str:
        return self._name()

    # -- the list --------------------------------------------------------------------------------------------
    def all(self, include_removed: bool = False) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT id, name, pubkey, address, added, last_seen, removed FROM peers ORDER BY added").fetchall()
        out = [{"id": r[0], "name": r[1], "pubkey": r[2], "address": r[3], "added": r[4], "last_seen": r[5],
                "removed": r[6], "fingerprint": fingerprint(_unb64(r[2]))} for r in rows]
        return out if include_removed else [p for p in out if not p["removed"]]

    def get(self, device_id: str) -> dict | None:
        return next((p for p in self.all() if p["id"] == device_id), None)

    def add(self, device_id: str, name: str, pubkey: str, address: str | None = None) -> dict:
        if device_id == self.device_id:
            raise PairingError("that's this device")
        if not is_id(device_id, "dv_"):
            raise PairingError("that isn't a Sage OS device")
        try:
            if len(_unb64(pubkey)) != 32:
                raise ValueError
        except ValueError:
            raise PairingError("that device's key isn't valid")
        with self.lock:
            self.db.execute("INSERT INTO peers(id, name, pubkey, address, added) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE "
                            "SET name=excluded.name, pubkey=excluded.pubkey, address=COALESCE(excluded.address, peers.address), "
                            "added=excluded.added, removed=NULL", (device_id, name[:60], pubkey, address, time.time()))
            self.db.commit()
        return self.get(device_id)

    def seen(self, device_id: str, address: str | None = None) -> None:
        with self.lock:
            self.db.execute("UPDATE peers SET last_seen=?, address=COALESCE(?, address) WHERE id=?", (time.time(), address, device_id))
            self.db.commit()

    def remove(self, device_id: str) -> None:
        with self.lock:
            self.db.execute("UPDATE peers SET removed=? WHERE id=?", (time.time(), device_id))
            self.db.commit()

    # -- hosting a pairing ----------------------------------------------------------------------------------
    def start_pairing(self) -> dict:
        if self.me is None:
            raise PairingError("this computer has no keychain, so it has no pairing key")
        self.session = {"code": new_code(), "expires": time.time() + CODE_TTL, "tries": 0}
        return dict(self.session)

    def cancel_pairing(self) -> None:
        self.session = None

    def pairing(self) -> dict | None:
        s = self.session
        if s and s["expires"] < time.time():
            self.session = s = None
        return dict(s) if s else None

    def accept(self, req: dict, my_tls: str) -> dict:
        """The host's side: a device asks to pair with a proof made from the code. -> our answer, with our proof."""
        s = self.pairing()
        if not s:
            raise PairingError("this device isn't pairing right now; press ADD A DEVICE on it first")
        s_live = self.session
        s_live["tries"] += 1
        if s_live["tries"] > CODE_TRIES:
            self.session = None
            raise PairingError("too many wrong codes; press ADD A DEVICE again for a new one")
        try:
            their_id, their_name, their_key, their_proof = str(req["id"]), str(req["name"]), str(req["pubkey"]), str(req["proof"])
        except (KeyError, TypeError):
            raise PairingError("that pairing request was incomplete")
        want = proof(s["code"], "join", their_key, self.me.public_b64, my_tls)
        if not hmac.compare_digest(want, their_proof):
            raise PairingError("that code isn't right")
        self.session = None                           # one use
        self.add(their_id, their_name, their_key)
        self.seen(their_id)
        return {"id": self.device_id, "name": self.name, "pubkey": self.me.public_b64,
                "proof": proof(s["code"], "host", self.me.public_b64, their_key)}

    # -- signed requests ----------------------------------------------------------------------------------
    def sign(self, method: str, path: str, body: bytes, server_tls: str) -> dict:
        ts, nonce = str(int(time.time())), secrets.token_urlsafe(16)
        sig = self.me.sign(request_message(method, path, ts, nonce, body, server_tls))
        return {"X-Sage-Device": self.device_id, "X-Sage-Time": ts, "X-Sage-Nonce": nonce, "X-Sage-Sig": b64(sig)}

    def verify(self, method: str, path: str, headers, body: bytes, my_tls: str) -> dict:
        """-> the paired device that sent it, or PermissionError."""
        dev, ts, nonce, sig = (headers.get(h) for h in ("x-sage-device", "x-sage-time", "x-sage-nonce", "x-sage-sig"))
        if not all((dev, ts, nonce, sig)):
            raise PermissionError("not signed")
        peer = self.get(dev)
        if peer is None:
            raise PermissionError("not a paired device")
        try:
            when = int(ts)
        except ValueError:
            raise PermissionError("bad time")
        now = time.time()
        if abs(now - when) > SKEW:
            raise PermissionError("the two clocks are more than five minutes apart")
        if not DeviceKey.verify(peer["pubkey"], _unb64(sig), request_message(method, path, ts, nonce, body, my_tls)):
            raise PermissionError("bad signature")
        with self._nlock:
            for n, t in list(self._nonces.items()):
                if t < now - 2 * SKEW:
                    del self._nonces[n]
            if nonce in self._nonces:
                raise PermissionError("replayed")
            self._nonces[nonce] = now
        return peer
