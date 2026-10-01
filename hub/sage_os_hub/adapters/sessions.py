"""Recent Hermes sessions per profile, from each profile's state.db (read-only)."""
from __future__ import annotations

import json

from ..sqlite_ro import columns, connect_ro
from .base import Adapter

WANT = ["id", "source", "title", "model", "started_at", "ended_at", "last_activity_at",
        "last_activity_description", "message_count", "tool_call_count", "input_tokens",
        "output_tokens", "estimated_cost_usd", "pinned", "archived", "hidden", "parent_session_id"]
PER_PROFILE = 20


def profile_dbs(home) -> dict:
    dbs = {"default": home / "state.db"}
    pdir = home / "profiles"
    if pdir.is_dir():
        for p in sorted(pdir.iterdir()):
            if (p / "state.db").exists():
                dbs[p.name] = p / "state.db"
    return {k: v for k, v in dbs.items() if v.exists()}


class SessionsAdapter(Adapter):
    name = "sessions"

    def __init__(self, emit, cfg):
        super().__init__(emit)
        self.cfg, self.interval = cfg, cfg.poll["sessions"]
        self._last: dict[str, float] = {}
        self._fp = None

    def smoke(self):
        out = []
        for prof, db in profile_dbs(self.cfg.hermes_home).items():
            with connect_ro(db) as con:
                missing = {"id", "title", "model", "started_at"} - columns(con, "sessions")
            out.append((f"{prof} state.db sessions", not missing, "ok" if not missing else f"missing {missing}"))
        return out or [("any state.db", False, "none found")]

    def poll(self):
        profiles = []
        for prof, db in profile_dbs(self.cfg.hermes_home).items():
            if prof in self.cfg.hidden_profiles:
                continue
            with connect_ro(db) as con:
                have = columns(con, "sessions")
                cols = [c for c in WANT if c in have]
                order = "COALESCE(last_activity_at, started_at)" if "last_activity_at" in have else "started_at"
                conds = [f"COALESCE({c}, 0) = 0" for c in ("hidden", "archived") if c in have]
                where = ("WHERE " + " AND ".join(conds)) if conds else ""
                rows = [dict(r) for r in con.execute(
                    f"SELECT {', '.join(cols)} FROM sessions {where} ORDER BY {order} DESC LIMIT ?",
                    (PER_PROFILE,))]
                total = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            profiles.append({"profile": prof, "label": self.cfg.profile_labels.get(prof, prof), "pinned": prof in self.cfg.pinned_profiles,
                             "total": total, "sessions": rows})
        profiles.sort(key=lambda p: (not p["pinned"], p["profile"]))
        fp = json.dumps(profiles, sort_keys=True, default=str)
        if fp != self._fp:
            self._fp = fp
            self.emit.panel("sessions", profiles)
        for p in profiles:
            for s in p["sessions"]:
                act = s.get("last_activity_at") or s.get("started_at") or 0
                key = f"{p['profile']}:{s['id']}"
                prev = self._last.get(key)
                if prev is not None and act > prev:
                    self.emit.event("message", self.name, "session.activity", {
                        "profile": p["profile"], "session_id": s["id"], "title": s.get("title"),
                        "model": s.get("model"), "activity": s.get("last_activity_description")},
                        persist=False)
                self._last[key] = act
