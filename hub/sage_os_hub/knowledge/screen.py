"""Secret screening (K4, BookShelf I4): content that looks like a credential or a sensitive number
never enters the journal, the vault or the search index through Sage OS.

`screen` returns a coarse category ("a password or key", ...) or None. It never returns, logs or
echoes the matched value: naming what was found would itself be a leak (BookShelf DESIGN §7).
False positives are expected; the proposer can rephrase. Checksums (Luhn, Verhoeff, IBAN mod 97)
keep ordinary numbers from tripping the number rules.
"""
from __future__ import annotations

import re

CREDENTIAL = "a password or key"
CARD = "a payment card number"
GOV_ID = "a government ID number"
BANK = "a bank account number"

_PLACEHOLDER = re.compile(r"^(<.*>|\$\{.*\}|\{\{.*\}\}|x+|\*+|\.+|•+|your[_-]?\w*|example\w*|placeholder|redacted|"
                          r"none|null|changeme|todo|tbd|n/?a|hidden|secret|password)$", re.I)

_TOKENS = [re.compile(p) for p in (
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----",
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",                          # AWS access key id
    r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", r"\bgithub_pat_[A-Za-z0-9_]{22,}\b",
    r"\bsk-ant-[A-Za-z0-9_-]{20,}", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}",   # Anthropic, OpenAI
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}", r"\bAIza[0-9A-Za-z_-]{35}\b",       # Slack, Google
    r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{16,}\b",                       # Stripe
    r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",  # JWT
    r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@/]{3,}@[^\s/]+",               # scheme://user:password@host
)]
# password: hunter2 · api_key = "..." (the value must look like a real value, not a placeholder or code)
_ASSIGN = re.compile(r"(?i)\b(?:password|passwd|pwd|passphrase|pin|secret|api[_ -]?key|access[_ -]?token|auth[_ -]?token|"
                     r"client[_ -]?secret|private[_ -]?key)\b\s*[:=]\s*[\"'`]?([^\s\"'`,;]{6,})")
# API_SERVER_KEY=... in env-file style: upper case only, so SQL's primary_key = id doesn't trip it
_ENV = re.compile(r"\b[A-Z0-9_]*_(?:KEY|TOKEN|SECRET|PASSWORD)\s*=\s*[\"']?([^\s\"'`,;]{8,})")
_CODE = re.compile(r"[(\[{$]|^(?:os|process|env|config|settings|self|this)\.")
_CARD = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
_SSN = re.compile(r"(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])")
_AADHAAR = re.compile(r"(?<!\d)(?<!\d )[2-9]\d{3} \d{4} \d{4}(?!\d)(?! \d)|(?<!\d)[2-9]\d{11}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch) * (2 if i % 2 else 1)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


_V_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_V_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def _verhoeff(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _V_D[c][_V_P[i % 8][int(ch)]]
    return c == 0


def _iban_ok(s: str) -> bool:
    s = s.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    n = "".join(str(int(ch, 36)) for ch in s[4:] + s[:4])
    return int(n) % 97 == 1


def screen(text: str | None) -> str | None:
    """-> the category of the first sensitive thing found, or None. Never the value itself."""
    if not text:
        return None
    if any(p.search(text) for p in _TOKENS):
        return CREDENTIAL
    for rx in (_ASSIGN, _ENV):
        for m in rx.finditer(text):
            value = m.group(1)
            if not _PLACEHOLDER.match(value) and not _CODE.search(value):
                return CREDENTIAL
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and digits[0] in "3456" and _luhn(digits):
            return CARD
    if _SSN.search(text):
        return GOV_ID
    for m in _AADHAAR.finditer(text):
        if _verhoeff(m.group().replace(" ", "")):
            return GOV_ID
    for m in _IBAN.finditer(text):
        if _iban_ok(m.group()):
            return BANK
    return None
