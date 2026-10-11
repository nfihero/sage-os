"""Game mode (G1, D29): Sage OS notices when another program needs the graphics card and steps aside.

  * Detect (any vendor, sage_os_hub.hardware): a full-screen game, a program marked "always", or a program that
    holds a lot of graphics memory while keeping the GPU busy, or keeps it very busy, for about 30 seconds.
  * Step aside: local jobs pause (the digest waits; a section being drafted is redone later) and the local model
    is unloaded. Cloud AIs carry on: they don't use this computer's GPU.
  * Micro model: with the memory that's left, a micro model (Gemma 4 E2B) may run light work (chats) if the user
    says so, once per program or remembered. It stops at once if the program needs the room. Digests stay queued
    for the main model.
  * Come back: a few minutes after the program closes, the main model is reloaded and the digest carries on.
  * The user decides: step aside always / ask / never, per-program always / never, and a manual pause.

Settings are per computer (gamemode.json in app data): a game on this PC says nothing about the Mac.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("sage_os.gamemode")

GB = 2**30
# Windows' own processes and shells: they hold graphics memory but are never "a game"
SYSTEM = {"dwm.exe", "csrss.exe", "explorer.exe", "system", "idle", "searchhost.exe", "startmenuexperiencehost.exe",
          "textinputhost.exe", "shellexperiencehost.exe", "applicationframehost.exe", "lockapp.exe",
          "windowserver", "dock", "finder", "loginwindow", "systemuiserver"}
MODES = ("always", "ask", "never")


@dataclass
class Rules:
    memory_gb: float = 2.0          # a program holding this much graphics memory ...
    memory_share: float = 0.15      # ... (or this share of the card, if larger) ...
    busy_with_memory: float = 10.0  # ... while keeping the GPU at least this busy (%), or ...
    busy_alone: float = 40.0        # ... keeping it this busy whatever it holds ...
    sustain_s: float = 30.0         # ... for this long
    resume_after_s: float = 180.0   # back this long after the program closes
    margin_gb: float = 1.5          # free memory kept for the program when a micro model runs
    mac_free_pct: float = 25.0      # macOS: memory pressure (free below this) with ...
    mac_app_gb: float = 2.0         # ... the front app holding this much


class Detector:
    """Pure logic: readings in, "which program needs the GPU" out. Tested with made-up readings."""

    def __init__(self, rules: Rules | None = None):
        self.rules = rules or Rules()
        self._since: dict[str, float] = {}

    def candidates(self, reading: dict, own_pids: set[int], never: set[str]) -> dict[str, dict]:
        """Programs on the main card (not Sage OS, not Windows itself, not marked never), merged by name."""
        cards = reading.get("adapters") or []
        main = cards[0]["luid"] if cards else None
        out: dict[str, dict] = {}
        for p in reading.get("programs") or []:
            name = (p.get("name") or "").strip()
            key = name.lower()
            if not name or key in SYSTEM or key in never or (p.get("pid") in own_pids and p.get("pid") is not None):
                continue
            if main and p.get("adapter") not in (main, "unified"):
                continue
            c = out.setdefault(key, {"name": name, "pid": p.get("pid"), "vram_bytes": 0, "busy": 0.0})
            c["vram_bytes"] += p.get("vram_bytes") or 0
            c["busy"] = max(c["busy"], p.get("busy") or 0.0)
        return out

    def update(self, reading: dict, now: float, own_pids: set[int] = frozenset(), always: set[str] = frozenset(),
               never: set[str] = frozenset()) -> dict | None:
        """-> {name, pid, vram_bytes, why} for the program that needs the GPU now, or None."""
        r = self.rules
        cands = self.candidates(reading, set(own_pids), {n.lower() for n in never})
        fg = (reading.get("foreground") or {}).get("name") or ""
        always = {n.lower() for n in always}
        for key, c in cands.items():
            if key in always:
                return {**c, "why": "marked always"}
        if fg.lower() in always and fg.lower() not in {n.lower() for n in never}:
            return {"name": fg, "pid": None, "vram_bytes": 0, "busy": 0.0, "why": "marked always"}
        if reading.get("fullscreen") and fg and fg.lower() not in SYSTEM and fg.lower() not in {n.lower() for n in never}:
            c = cands.get(fg.lower(), {"name": fg, "pid": (reading.get("foreground") or {}).get("pid"),
                                       "vram_bytes": 0, "busy": 0.0})
            return {**c, "why": "full-screen game"}
        cards = reading.get("adapters") or []
        total = cards[0]["vram_bytes"] if cards else 0
        heavy_mem = max(r.memory_gb * GB, r.memory_share * total)
        hot = set()
        if reading.get("os") == "macos":
            free = reading.get("memory_free_pct")
            for key, c in cands.items():
                if free is not None and free < r.mac_free_pct and c["vram_bytes"] >= r.mac_app_gb * GB:
                    hot.add(key)
        else:
            for key, c in cands.items():
                if (c["vram_bytes"] >= heavy_mem and c["busy"] >= r.busy_with_memory) or c["busy"] >= r.busy_alone:
                    hot.add(key)
        for key in list(self._since):
            if key not in hot:
                del self._since[key]
        best = None
        for key in hot:
            first = self._since.setdefault(key, now)
            if now - first >= r.sustain_s and (best is None or cands[key]["vram_bytes"] > best["vram_bytes"]):
                best = {**cands[key], "why": "using the graphics card"}
        return best


class Settings:
    """gamemode.json in app data: {"mode": always|ask|never, "programs": {name: {"counts": always|never,
    "micro": keep|pause}}}. Per computer."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.mode, self.programs = "always", {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("mode") in MODES:
                self.mode = raw["mode"]
            self.programs = {str(k).lower(): dict(v) for k, v in (raw.get("programs") or {}).items() if isinstance(v, dict)}
        except (OSError, ValueError, AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".gamemode.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"mode": self.mode, "programs": self.programs}, f, indent=2)
        os.replace(tmp, self.path)

    def names(self, field: str, value: str) -> set[str]:
        return {n for n, p in self.programs.items() if p.get(field) == value}

    def set_program(self, name: str, **kw):
        p = self.programs.setdefault(name.strip().lower(), {})
        for k, v in kw.items():
            if v is None:
                p.pop(k, None)
            else:
                p[k] = v
        if not p:
            self.programs.pop(name.strip().lower(), None)
        self.save()


class GameMode:
    """Watches the hardware and steps the local engine aside. One instance per hub; `tick` is the whole policy,
    `run` the loop that feeds it readings."""

    INTERVAL = 3.0

    def __init__(self, hub, settings_path: Path, probe=None, rules: Rules | None = None, clock=time.time):
        self.hub, self.clock = hub, clock
        self.settings = Settings(settings_path)
        self.detector = Detector(rules)
        self.rules = self.detector.rules
        self._probe = probe
        self.state = "watching"        # watching | asking | aside | micro
        self.program: dict | None = None
        self.since: float | None = None
        self.previous: str | None = None       # the model to bring back
        self.clear_since: float | None = None
        self.manual = False
        self.dismissed: str | None = None      # "keep running" for this program until it closes
        self.offered = False                   # the micro question was settled for this episode
        self.downloading = False
        self.note: str | None = None
        self.reading: dict | None = None
        self.loading_back: str | None = None   # the main model reloading after a program closed

    # -- what others ask ---------------------------------------------------------------------------------
    @property
    def paused(self) -> bool:
        """Local jobs wait (digests always; chats unless the micro model is up)."""
        return self.state in ("aside", "micro")

    def reason(self) -> str:
        name = (self.program or {}).get("name") or "another program"
        return f"paused while {name} uses the graphics card"

    def public(self) -> dict:
        r = self.reading or {}
        cards = r.get("adapters") or []
        own = self._own_pids()
        cands = self.detector.candidates(r, own, set()) if r else {}
        seen = sorted((c for c in cands.values() if c["vram_bytes"] >= 0.2 * GB or (c["busy"] or 0) >= 5),
                      key=lambda c: -c["vram_bytes"])[:6]
        return {"mode": self.settings.mode, "state": self.state, "manual": self.manual, "program": self.program,
                "since": self.since, "previous": self.previous, "note": self.note,
                "resume_in": max(0, round(self.rules.resume_after_s - (self.clock() - self.clear_since)))
                if self.clear_since and self.paused else None,
                "card": {"name": cards[0]["name"], "vendor": cards[0].get("vendor"),
                         "total_gb": round(cards[0]["vram_bytes"] / GB, 1),
                         "used_gb": round(cards[0].get("used_bytes", 0) / GB, 1)} if cards else None,
                "seen": [{"name": c["name"], "vram_gb": round(c["vram_bytes"] / GB, 2), "busy": c["busy"]} for c in seen],
                "programs": self.settings.programs, "os": r.get("os")}

    # -- settings ----------------------------------------------------------------------------------------
    def set_mode(self, mode: str):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {', '.join(MODES)}")
        self.settings.mode = mode
        self.settings.save()
        self._publish()

    def set_program(self, name: str, counts: str | None = None, micro: str | None = None, clear: bool = False):
        if not name.strip():
            raise ValueError("name the program")
        if counts not in (None, "always", "never") or micro not in (None, "keep", "pause"):
            raise ValueError("counts: always / never; micro: keep / pause")
        if clear:
            self.settings.set_program(name, counts=None, micro=None)
        else:
            self.settings.set_program(name, **{k: v for k, v in (("counts", counts), ("micro", micro)) if v})
        self._publish()

    async def pause(self, on: bool):
        """The manual "Pause for a game" button, and its Resume."""
        self.manual = on
        if on and not self.paused:
            await self.step_aside({"name": "a game", "pid": None, "vram_bytes": 0, "why": "paused by you"})
        elif not on and self.paused and (self.program or {}).get("why") == "paused by you":
            await self.resume()
        self._publish()

    # -- the loop ----------------------------------------------------------------------------------------
    def _own_pids(self) -> set[int]:
        own = {os.getpid()}
        e = self.hub.engine
        if e and e.serving and e.serving.get("pid"):
            own.add(e.serving["pid"])
        return own

    async def run(self):
        if self._probe is None:
            from .hardware import Probe
            self._probe = await asyncio.to_thread(Probe)
        while True:
            try:
                reading = await asyncio.to_thread(self._probe.read)
                await self.tick(reading)
            except Exception as exc:                   # noqa: BLE001 -- the watcher never dies
                log.warning("game mode: %s", exc)
            await asyncio.sleep(self.INTERVAL)

    async def tick(self, reading: dict):
        self.reading = reading
        now = self.clock()
        s = self.settings
        need = self.detector.update(reading, now, self._own_pids(), s.names("counts", "always"), s.names("counts", "never"))
        if self.manual and need is None:
            need = self.program or {"name": "a game", "pid": None, "vram_bytes": 0, "why": "paused by you"}
        if need is None and self.dismissed:
            self.dismissed = None                      # the program closed: ask again next time
        e = self.hub.engine
        if self.loading_back and e and e.serving and e.serving["id"] == self.loading_back and e.serving.get("ready"):
            self.note, self.loading_back = f"{self.loading_back} is back", None
        if self.state == "watching":
            if need and s.mode != "never" and need["name"].lower() != (self.dismissed or "").lower():
                if s.mode == "ask" and need.get("why") != "paused by you":
                    self._ask_step_aside(need)
                else:
                    await self.step_aside(need)
        elif self.state == "asking":
            if need is None:
                self._drop("gamemode:aside")
                self.state, self.program = "watching", None
        elif self.paused:
            await self._while_aside(need, reading, now)
        self._publish()

    async def _while_aside(self, need: dict | None, reading: dict, now: float):
        e = self.hub.engine
        if e and e.serving and e.serving["id"] != self._micro_id() and self.state in ("aside", "micro"):
            # the user started a model themselves: they've taken over until the program closes
            self.note = "you started a model, so game mode stepped back"
            self._drop("gamemode:micro")
            self.dismissed = (self.program or {}).get("name")
            self.state, self.program, self.previous, self.clear_since = "watching", None, None, None
            self.hub.event("system", "gamemode", "gamemode.override", {"model": e.serving["id"]})
            return
        if need:
            self.clear_since = None
            if self.state == "micro" and self._free_bytes(reading) < self.rules.margin_gb * GB / 2:
                await self._stop_micro(f"{self.program['name']} needed the memory")
            elif self.state == "aside" and not self.offered:
                await self._offer_micro(reading)
            elif self.state == "aside" and self.downloading and self._micro_installed():
                self.downloading = False
                await self._start_micro(reading)
            return
        if self.clear_since is None:
            self.clear_since = now
        elif now - self.clear_since >= self.rules.resume_after_s:
            await self.resume()

    # -- stepping aside and back ---------------------------------------------------------------------------
    def _ask_step_aside(self, need: dict):
        name = need["name"]
        self.state, self.program, self.since = "asking", need, self.clock()

        async def resolver(choice, note):
            if choice.startswith("Never"):
                self.settings.set_program(name, counts="never")
            if choice.startswith(("Step aside", "Always")):
                if choice.startswith("Always"):
                    self.settings.set_program(name, counts="always")
                await self.step_aside(need)
            else:
                self.dismissed = name
                self.state, self.program = "watching", None
            self._publish()
        gb = need.get("vram_bytes", 0) / GB
        self.hub.inbox.add(source="gamemode", key="gamemode:aside",
                           title=f"{name} is using the graphics card",
                           detail=(f"It holds {gb:.1f} GB of graphics memory. " if gb >= 0.1 else "")
                           + "Step aside? Sage OS pauses its local work and unloads the local model until it closes; "
                             "cloud AIs keep working.",
                           choices=["Step aside", f"Always for {name}", "Keep running", f"Never for {name}"],
                           resolver=resolver, context={"program": name})

    async def step_aside(self, need: dict):
        e = self.hub.engine
        self.previous = e.serving["id"] if e and e.serving and e.serving["id"] != self._micro_id() else self.previous
        self.state, self.program, self.since = "aside", need, self.clock()
        self.offered, self.downloading, self.clear_since, self.note = False, False, None, None
        if e and e.serving:
            await asyncio.to_thread(e.stop)
            self.hub.panel("engine", e.status())
        if not self.previous:
            self.offered = True                        # nothing was running: nothing to offer instead
        self.hub.event("system", "gamemode", "gamemode.aside",
                       {"program": need["name"], "why": need.get("why"), "unloaded": self.previous})
        self.hub.digests.nudge()

    async def resume(self):
        e = self.hub.engine
        self._drop("gamemode:micro")
        self._drop("gamemode:aside")
        prev, name = self.previous, (self.program or {}).get("name")
        self.state, self.program, self.since, self.clear_since = "watching", None, None, None
        self.manual, self.offered, self.downloading, self.note = False, False, False, None
        self.previous = None
        if e and e.serving and e.serving["id"] == self._micro_id():
            await asyncio.to_thread(e.stop)
        if e and prev:
            try:
                await asyncio.to_thread(e.start, prev)
                self.note, self.loading_back = f"{name} closed; {prev} is loading again", prev
            except Exception as exc:                   # noqa: BLE001 -- the model may have been removed
                self.note = f"couldn't load {prev} again: {exc}"
            self.hub.panel("engine", e.status())
        self.hub.event("system", "gamemode", "gamemode.resumed", {"program": name, "model": prev})
        self.hub.digests.nudge()

    # -- the micro model -----------------------------------------------------------------------------------
    def _micro(self) -> dict | None:
        e = self.hub.engine
        if not e:
            return None
        return next((m for m in e.catalog() if m.get("micro")), None)

    def _micro_id(self) -> str | None:
        m = self._micro()
        return m["id"] if m else None

    def _micro_installed(self) -> bool:
        m = self._micro()
        return bool(m and m.get("installed"))

    def micro_need_bytes(self) -> float:
        m = self._micro()
        return (m["size"] * 1.1 + 0.8 * GB) if m else float("inf")      # weights + one 8K slot + runtime

    def _free_bytes(self, reading: dict) -> float:
        cards = reading.get("adapters") or []
        if not cards:
            return 0
        if reading.get("os") == "macos":
            return cards[0]["vram_bytes"] * 0.65 - cards[0].get("used_bytes", 0)
        return cards[0]["vram_bytes"] - cards[0].get("used_bytes", 0)

    async def _offer_micro(self, reading: dict):
        """Once per episode, after the main model is gone (its memory shows as free on this reading)."""
        self.offered = True
        e, m = self.hub.engine, self._micro()
        if not e or not m or not e.binary():
            return
        free, need = self._free_bytes(reading), self.micro_need_bytes()
        if free < need + self.rules.margin_gb * GB:
            self.note = f"not enough free graphics memory for {m['label']} beside {self.program['name']}"
            return
        name = self.program["name"]
        remembered = self.settings.programs.get(name.lower(), {}).get("micro")
        if remembered == "keep":
            await self._keep_working(reading)
            return
        if remembered == "pause":
            return

        async def resolver(choice, note):
            if "always" in choice.lower():
                self.settings.set_program(name, micro="keep" if choice.startswith("Keep") else "pause")
            if choice.startswith("Keep") and self.state == "aside":
                await self._keep_working(self.reading or reading)
            self._publish()
        size = m["size"] / GB
        dl = "" if m.get("installed") else f" It downloads once ({size:.1f} GB)."
        self.hub.inbox.add(source="gamemode", key="gamemode:micro",
                           title=f"Keep working in the background while {name} runs?",
                           detail=f"A small model ({m['label']}, about {need / GB:.1f} GB) fits beside it with room to "
                                  f"spare. It handles chats and light work; digests wait for {self.previous}. It stops "
                                  f"at once if {name} needs the memory.{dl}",
                           choices=["Keep working", f"Keep working, always for {name}", "Pause until I'm done",
                                    f"Always pause for {name}"],
                           resolver=resolver, context={"program": name, "model": m["id"]})

    async def _keep_working(self, reading: dict):
        e, m = self.hub.engine, self._micro()
        if not m["installed"]:
            try:
                e.claim(f"model:{m['id']}", "model", m["label"])
            except Exception:                          # noqa: BLE001 -- already downloading
                pass
            else:
                asyncio.get_running_loop().run_in_executor(None, e.download_model, m["id"])
            self.downloading = True
            self.note = f"downloading {m['label']}; it starts when it's ready"
            return
        await self._start_micro(reading)

    async def _start_micro(self, reading: dict):
        e, m = self.hub.engine, self._micro()
        if self._free_bytes(reading) < self.micro_need_bytes() + self.rules.margin_gb * GB:
            self.note = f"{self.program['name']} grew; {m['label']} didn't start"
            return
        await asyncio.to_thread(e.start, m["id"], True)
        self.state, self.note = "micro", f"{m['label']} is handling light work"
        self.hub.panel("engine", e.status())
        self.hub.event("system", "gamemode", "gamemode.micro", {"program": self.program["name"], "model": m["id"]})

    async def _stop_micro(self, why: str):
        e = self.hub.engine
        if e and e.serving:
            await asyncio.to_thread(e.stop)
            self.hub.panel("engine", e.status())
        self.state, self.note = "aside", f"stopped the small model: {why}"
        self.hub.event("system", "gamemode", "gamemode.micro_stopped", {"why": why})

    # -- plumbing ------------------------------------------------------------------------------------------
    def _drop(self, key: str):
        self.hub.inbox.drop(key)

    def _publish(self):
        self.hub.panel("gamemode", self.public())
