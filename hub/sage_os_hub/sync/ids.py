"""ULIDs (Y1.2): 48 bits of milliseconds + 80 random bits, written as 26 Crockford base-32 characters.

They sort by creation time as plain strings, and two devices making IDs at the same moment won't clash. IDs
made in the same millisecond on one device stay in order: the random part is incremented instead of redrawn.
Records keep a short type prefix ("ch_", "dg_", …) so an ID still says what it names.
"""
from __future__ import annotations

import os
import re
import threading
import time

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_RAND_MAX = (1 << 80) - 1
_ULID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")


def _encode(n: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(ALPHABET[n & 31])
        n >>= 5
    return "".join(reversed(out))


class Generator:
    """Makes ULIDs that never go backwards on this device, even within one millisecond or when the clock
    steps back. One shared instance serves the hub; tests make their own."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_ms = -1
        self._last_rand = 0

    def __call__(self, now_ms: int | None = None) -> str:
        ms = int(time.time() * 1000) if now_ms is None else now_ms
        with self._lock:
            if ms <= self._last_ms:
                # same millisecond (or the clock stepped back): stay after the last ID instead of before it
                ms = self._last_ms
                if self._last_rand >= _RAND_MAX:
                    ms += 1
                    rand = int.from_bytes(os.urandom(10), "big")
                else:
                    rand = self._last_rand + 1
            else:
                rand = int.from_bytes(os.urandom(10), "big")
            self._last_ms, self._last_rand = ms, rand
        return _encode(ms, 10) + _encode(rand, 16)


ulid = Generator()


def new_id(prefix: str = "") -> str:
    """A ULID with an optional type prefix: new_id("ch_") -> "ch_01J9…"."""
    return prefix + ulid()


def is_id(value: str, prefix: str = "") -> bool:
    return isinstance(value, str) and value.startswith(prefix) and bool(_ULID.fullmatch(value[len(prefix):]))


def id_time(value: str) -> float:
    """When an ID was made (seconds since the epoch), read back from its first 10 characters."""
    ms = 0
    for ch in value[-26:][:10]:
        ms = ms * 32 + ALPHABET.index(ch)
    return ms / 1000
