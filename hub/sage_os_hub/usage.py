"""What each AI costs (D40): tokens per reply, a dated price list, and spend.

  * Every reply records its tokens: the model chat asks the provider to report usage (OpenAI-compatible
    `stream_options.include_usage`), Claude Code reports it with each turn. When a provider doesn't report, the
    tokens are estimated from the text (about four characters a token) and marked as estimated.
  * Prices come from pricing.json (each provider's own page, dated) and the user's corrections, kept in hub.db so
    they follow the user's devices. A model id matches the longest listed prefix; dated price changes apply from
    their date.
  * Billing: an API key is charged per token ("api"); Claude Code runs on the user's plan ("plan": the API price is
    shown as what the same work would cost, not as spend); models on this computer are free ("free").
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import time
from pathlib import Path

from .sync import new_id

PRICES = Path(__file__).with_name("pricing.json")
FAMILY = {"openai": "openai", "gemini": "gemini", "claude": "anthropic", "anthropic": "anthropic"}
FREE = {"engine", "ollama", "hermes-router"}
DAY = 86400
SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id         TEXT PRIMARY KEY,           -- us_ + ULID
    ts         REAL NOT NULL,
    agent      TEXT NOT NULL,              -- chat | claude | hermes:<profile>
    provider   TEXT,                       -- engine | openai | gemini | ollama | ... (claude: none)
    model      TEXT,
    chat       TEXT,                       -- the pane: chat:<sid> | claude:<sid>
    tokens_in  INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost       REAL,                       -- at the API price on that day (null: no price known)
    billing    TEXT NOT NULL,              -- api | plan | free
    estimated  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS usage_ts ON usage (ts);
CREATE INDEX IF NOT EXISTS usage_chat ON usage (chat);
CREATE TABLE IF NOT EXISTS price_overrides (
    provider TEXT NOT NULL,
    model    TEXT NOT NULL,
    in_price  REAL NOT NULL,
    out_price REAL NOT NULL,
    updated  REAL NOT NULL,
    deleted  REAL,                     -- a reset correction is a tombstone, so it syncs (Y1.5)
    PRIMARY KEY (provider, model)
);
"""


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text or "") / 4)) if text else 0


class Usage:
    def __init__(self, db, lock: threading.RLock):
        self.db, self.lock = db, lock
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()
        self.list = json.loads(PRICES.read_text(encoding="utf-8"))
        self.limits: dict[str, dict] = {}            # provider -> rate-limit headers seen last (this run only)

    # -- prices ---------------------------------------------------------------------------------------------
    def overrides(self) -> dict[tuple[str, str], dict]:
        with self.lock:
            rows = self.db.execute("SELECT provider, model, in_price, out_price, updated FROM price_overrides "
                                   "WHERE deleted IS NULL").fetchall()
        return {(p, m): {"in": i, "out": o, "updated": u} for p, m, i, o, u in rows}

    def price(self, provider: str | None, model: str | None, when: float | None = None) -> dict | None:
        """-> {"in", "out", "source": "list" | "yours", "as_of"} per million tokens, or None when unknown."""
        if not model:
            return None
        family = FAMILY.get(provider or "", provider or "")
        m = model.removeprefix("models/").lower()
        best = None
        for row in self.list["models"]:
            if row["provider"] == family and m.startswith(row["model"]) and (best is None or len(row["model"]) > len(best["model"])):
                best = row
        # the user's correction wins when it names this model at least as closely as the list does (D40)
        mine = max(((name, v) for (p, name), v in self.overrides().items() if p == family and m.startswith(name.lower())),
                   key=lambda x: len(x[0]), default=None)
        if mine and (best is None or len(mine[0]) >= len(best["model"])):
            return {"in": mine[1]["in"], "out": mine[1]["out"], "source": "yours", "as_of": mine[1]["updated"], "match": mine[0]}
        if best is None:
            return None
        day = dt.date.fromtimestamp(when or time.time()).isoformat()
        p = {"in": best["in"], "out": best["out"]}
        for ch in sorted(best.get("changes", []), key=lambda c: c["from"]):
            if day >= ch["from"]:
                p = {"in": ch["in"], "out": ch["out"]}
        return p | {"source": "list", "as_of": self.list["as_of"], "match": best["model"], "note": best.get("note"),
                    "changes": best.get("changes")}

    def set_price(self, provider: str, model: str, in_price: float, out_price: float) -> None:
        if in_price < 0 or out_price < 0 or in_price > 10_000 or out_price > 10_000:
            raise ValueError("prices are dollars per million tokens, between 0 and 10,000")
        with self.lock:
            self.db.execute("INSERT INTO price_overrides(provider, model, in_price, out_price, updated) VALUES (?,?,?,?,?) "
                            "ON CONFLICT(provider, model) DO UPDATE SET in_price=excluded.in_price, "
                            "out_price=excluded.out_price, updated=excluded.updated, deleted=NULL",
                            (FAMILY.get(provider, provider), model.removeprefix("models/").lower(), in_price, out_price, time.time()))
            self.db.commit()

    def reset_price(self, provider: str, model: str) -> None:
        with self.lock:
            self.db.execute("UPDATE price_overrides SET deleted=?, updated=? WHERE provider=? AND model=?",
                            (time.time(), time.time(), FAMILY.get(provider, provider), model.removeprefix("models/").lower()))
            self.db.commit()

    # -- recording -----------------------------------------------------------------------------------------
    @staticmethod
    def billing(agent: str, provider: str | None) -> str:
        if agent == "claude":
            return "plan"
        if agent.startswith("hermes:") or provider in FREE:
            return "free"
        return "api"

    def record(self, agent: str, provider: str | None, model: str | None, chat: str | None, tokens_in: int,
               tokens_out: int, estimated: bool = False, cost: float | None = None) -> dict:
        """`cost`: a figure the AI reported itself (Claude Code's, which knows cache prices) instead of the list."""
        billing = self.billing(agent, provider)
        p = None if billing == "free" or cost is not None else self.price("anthropic" if agent == "claude" else provider, model)
        if cost is None and p is not None:
            cost = round((tokens_in * p["in"] + tokens_out * p["out"]) / 1e6, 6)
        if billing == "free":
            cost = 0.0
        row = {"id": new_id("us_"), "ts": time.time(), "agent": agent, "provider": provider, "model": model, "chat": chat,
               "tokens_in": int(tokens_in or 0), "tokens_out": int(tokens_out or 0), "cost": cost, "billing": billing,
               "estimated": bool(estimated)}
        with self.lock:
            self.db.execute("INSERT INTO usage(id, ts, agent, provider, model, chat, tokens_in, tokens_out, cost, billing, estimated) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (row["id"], row["ts"], agent, provider, model, chat, row["tokens_in"],
                                                                row["tokens_out"], cost, billing, int(estimated)))
            self.db.commit()
        return row

    def note_limits(self, provider: str, headers) -> None:
        """OpenAI-style rate-limit headers, when a provider sends them."""
        keys = {"limit_requests": "x-ratelimit-limit-requests", "remaining_requests": "x-ratelimit-remaining-requests",
                "limit_tokens": "x-ratelimit-limit-tokens", "remaining_tokens": "x-ratelimit-remaining-tokens",
                "reset_requests": "x-ratelimit-reset-requests", "reset_tokens": "x-ratelimit-reset-tokens"}
        seen = {k: headers.get(h) for k, h in keys.items() if headers.get(h) is not None}
        if seen:
            self.limits[provider] = seen | {"seen": time.time()}

    # -- reading ---------------------------------------------------------------------------------------------
    def for_chats(self, panes: list[str]) -> dict:
        """Totals for a conversation's sessions."""
        if not panes:
            return {"tokens_in": 0, "tokens_out": 0, "cost": 0.0, "billing": [], "estimated": False, "priced": True}
        q = ",".join("?" for _ in panes)
        with self.lock:
            rows = self.db.execute(f"SELECT tokens_in, tokens_out, cost, billing, estimated FROM usage WHERE chat IN ({q})", panes).fetchall()
        return {"tokens_in": sum(r[0] for r in rows), "tokens_out": sum(r[1] for r in rows),
                "cost": round(sum(r[2] or 0 for r in rows if r[3] == "api"), 6),
                "plan_value": round(sum(r[2] or 0 for r in rows if r[3] == "plan"), 6),
                "billing": sorted({r[3] for r in rows}), "estimated": any(r[4] for r in rows),
                "priced": all(r[2] is not None for r in rows)}

    def summary(self, now: float | None = None) -> dict:
        """Per AI (agent, provider, model): tokens and cost today, this week, this month; and a daily series."""
        now = now or time.time()
        start = dt.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        since = start - 29 * DAY
        with self.lock:
            rows = self.db.execute("SELECT ts, agent, provider, model, tokens_in, tokens_out, cost, billing, estimated "
                                   "FROM usage WHERE ts >= ? ORDER BY ts", (since,)).fetchall()
        per: dict[tuple, dict] = {}
        days: dict[str, dict] = {}
        for ts, agent, provider, model, tin, tout, cost, billing, est in rows:
            k = (agent, provider or "", model or "")
            a = per.setdefault(k, {"agent": agent, "provider": provider, "model": model, "billing": billing,
                                   "today": [0, 0, 0.0], "week": [0, 0, 0.0], "month": [0, 0, 0.0],
                                   "estimated": False, "unpriced": False})
            for span, lo in (("today", start), ("week", start - 6 * DAY), ("month", since)):
                if ts >= lo:
                    a[span][0] += tin
                    a[span][1] += tout
                    a[span][2] += cost or 0
            a["estimated"] |= bool(est)
            a["unpriced"] |= cost is None
            d = days.setdefault(dt.date.fromtimestamp(ts).isoformat(), {"tokens": 0, "spent": 0.0})
            d["tokens"] += tin + tout
            if billing == "api":
                d["spent"] += cost or 0
        ais = sorted(per.values(), key=lambda a: -(a["month"][0] + a["month"][1]))
        for a in ais:
            for span in ("today", "week", "month"):
                a[span] = {"tokens_in": a[span][0], "tokens_out": a[span][1], "cost": round(a[span][2], 4)}
            a["price"] = self.price("anthropic" if a["agent"] == "claude" else a["provider"], a["model"]) if a["billing"] != "free" else None
        spent = {span: round(sum(a[span]["cost"] for a in ais if a["billing"] == "api"), 4) for span in ("today", "week", "month")}
        return {"ais": ais, "spent": spent, "days": [{"day": k} | v for k, v in sorted(days.items())],
                "limits": self.limits, "as_of": self.list["as_of"]}

    def price_list(self) -> dict:
        ov = self.overrides()
        rows = [r | {"yours": ov.get((r["provider"], r["model"]))} for r in self.list["models"]]
        extra = [{"provider": p, "model": m, "in": v["in"], "out": v["out"], "yours": v}
                 for (p, m), v in ov.items() if not any(r["provider"] == p and r["model"] == m for r in self.list["models"])]
        return {"as_of": self.list["as_of"], "sources": self.list["sources"], "models": rows + extra}
