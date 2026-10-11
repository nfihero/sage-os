"""G1 (D29): game mode, with made-up hardware readings, a fake engine and a fake clock."""
import asyncio

import pytest

from sage_os_hub.gamemode import GB, Detector, GameMode, Rules
from sage_os_hub.hardware.windows import nvidia_driver
from sage_os_hub.inbox import Inbox
from sage_os_hub.adapters.system import gpu_lane

CARD = {"name": "RTX", "vendor": "nvidia", "vram_bytes": 16 * GB, "luid": "luid_main"}
IGPU = {"name": "Radeon", "vendor": "amd", "vram_bytes": GB // 2, "luid": "luid_igpu"}


def reading(*programs, used_gb=1.0, fullscreen=False, fg=None, os="windows", free_pct=None):
    """programs: (name, pid, vram_gb, busy[, adapter])"""
    progs = [{"name": p[0], "pid": p[1], "vram_bytes": int(p[2] * GB), "busy": p[3],
              "adapter": p[4] if len(p) > 4 else "luid_main"} for p in programs]
    return {"os": os, "adapters": [{**CARD, "used_bytes": int(used_gb * GB)}, {**IGPU, "used_bytes": 0}],
            "programs": progs, "fullscreen": fullscreen, "memory_free_pct": free_pct,
            "foreground": {"pid": None, "name": fg} if fg else None}


# -- the detector -------------------------------------------------------------------------------------------
def test_a_full_screen_game_counts_at_once():
    d = Detector()
    need = d.update(reading(("Cyberpunk2077.exe", 50, 9, 95), fullscreen=True, fg="Cyberpunk2077.exe"), now=0)
    assert need["name"] == "Cyberpunk2077.exe" and need["why"] == "full-screen game"


def test_a_heavy_busy_program_counts_after_thirty_seconds():
    d = Detector()
    heavy = reading(("Blender.exe", 50, 6, 70))
    assert d.update(heavy, now=0) is None and d.update(heavy, now=20) is None
    assert d.update(heavy, now=31)["name"] == "Blender.exe"
    assert d.update(reading(), now=40) is None                                  # closed: forgotten
    assert d.update(heavy, now=41) is None                                      # and the clock starts again


@pytest.mark.parametrize("prog", [("chrome.exe", 5, 2.5, 3), ("dwm.exe", 6, 3, 60), ("Medal.exe", 7, 0.1, 5)],
                         ids=["idle browser with memory", "Windows itself", "a recorder"])
def test_ordinary_programs_dont_count(prog):
    d = Detector()
    assert d.update(reading(prog), now=0) is None and d.update(reading(prog), now=100) is None


def test_sage_os_and_programs_on_another_card_dont_count():
    d = Detector()
    own = reading(("llama-server.exe", 99, 11, 100))
    other_card = reading(("Game.exe", 50, 0.4, 99, "luid_igpu"))
    for r in (own, other_card):
        d.update(r, now=0, own_pids={99})
        assert d.update(r, now=100, own_pids={99}) is None


def test_always_and_never_rules():
    d = Detector()
    assert d.update(reading(("Photoshop.exe", 5, 0.5, 1)), now=0, always={"photoshop.exe"})["why"] == "marked always"
    game = reading(("Game.exe", 50, 9, 95), fullscreen=True, fg="Game.exe")
    assert d.update(game, now=0, never={"Game.exe"}) is None


def test_mac_counts_memory_pressure_with_a_big_front_app():
    d = Detector()
    r = reading(("Baldur's Gate 3", None, 9, None, "unified"), os="macos", free_pct=12)
    r["adapters"][0]["luid"] = "unified"
    d.update(r, now=0)
    assert d.update(r, now=31)["name"] == "Baldur's Gate 3"
    r["memory_free_pct"] = 60
    assert d.update(r, now=62) is None


def test_nvidia_driver_number_and_gpu_lane():
    assert nvidia_driver("32.0.16.1742") == "617.42"
    lane = gpu_lane(reading(("Game.exe", 50, 9, 87), used_gb=10))
    assert lane["name"] == "RTX" and lane["util_pct"] == 87 and round(lane["vram_used_mb"]) == 10 * 1024
    assert lane["temp_c"] is None and gpu_lane({"adapters": []}) is None


# -- the controller -----------------------------------------------------------------------------------------
class FakeEngine:
    def __init__(self, installed=True):
        self.serving = {"id": "file:gemma-12b", "ready": True, "pid": 99}
        self.started, self.stopped, self.downloads = [], 0, []
        self.installed = installed

    def catalog(self):
        return [{"id": "gemma-4-e2b", "label": "Gemma 4 E2B", "size": int(2.84 * GB), "micro": True,
                 "installed": self.installed}]

    def binary(self):
        return "llama-server"

    def stop(self):
        self.stopped += 1
        self.serving = None

    def start(self, model_id, small=False):
        self.started.append((model_id, small))
        self.serving = {"id": model_id, "ready": True, "pid": 100 if small else 99}

    def status(self):
        return {"serving": self.serving}

    def claim(self, *a):
        pass

    def download_model(self, model_id):
        self.downloads.append(model_id)
        self.installed = True


class FakeDigests:
    def __init__(self):
        self.nudges = 0

    def nudge(self):
        self.nudges += 1


class FakeHub:
    def __init__(self, engine):
        self.engine, self.digests = engine, FakeDigests()
        self.events, self.panels = [], {}
        self.inbox = Inbox(lambda m: None, lambda *a, **k: None)

    def event(self, kind, source, type_, data, **kw):
        self.events.append(type_)

    def panel(self, name, data, **kw):
        self.panels[name] = data


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


GAME = ("Cyberpunk2077.exe", 50, 9, 95)


def make(tmp_path, installed=True, mode="always"):
    hub, clock = FakeHub(FakeEngine(installed)), Clock()
    gm = GameMode(hub, tmp_path / "gamemode.json", probe=object(), rules=Rules(), clock=clock)
    gm.settings.mode = mode
    return gm, hub, clock


def run(coro):
    return asyncio.run(coro)


def playing(used_gb=10.0):
    return reading(GAME, used_gb=used_gb, fullscreen=True, fg="Cyberpunk2077.exe")


async def _choose(hub, key, choice):
    await hub.inbox.resolve(key, choice)


def test_steps_aside_offers_the_micro_model_and_comes_back(tmp_path):
    gm, hub, clock = make(tmp_path)

    async def go():
        await gm.tick(playing(used_gb=20))                    # main model still loaded beside the game
        assert gm.paused and hub.engine.serving is None and gm.previous == "file:gemma-12b"
        assert "gamemode.aside" in hub.events and hub.digests.nudges == 1
        await gm.tick(playing(used_gb=9.5))                    # main model gone: 6.5 GB free
        [item] = hub.inbox.items()
        assert item["id"] == "gamemode:micro" and item["choices"][0] == "Keep working"
        await _choose(hub, "gamemode:micro", "Keep working")
        assert gm.state == "micro" and hub.engine.started == [("gemma-4-e2b", True)]
        await gm.tick(playing(used_gb=13))                     # micro running: still 3 GB free
        assert gm.state == "micro"
        await gm.tick(reading(used_gb=4))                      # game closed
        clock.t += 100
        await gm.tick(reading(used_gb=4))
        assert gm.paused                                       # not yet: waits a few minutes
        clock.t += 100
        await gm.tick(reading(used_gb=4))
        assert gm.state == "watching" and hub.engine.serving["id"] == "file:gemma-12b"
        assert "gamemode.resumed" in hub.events and hub.inbox.items() == []
    run(go())


def test_the_micro_model_stops_when_the_game_needs_the_room(tmp_path):
    gm, hub, _ = make(tmp_path)
    gm.settings.set_program("Cyberpunk2077.exe", micro="keep")       # remembered: no question

    async def go():
        await gm.tick(playing(used_gb=20))
        await gm.tick(playing(used_gb=9.5))
        assert gm.state == "micro" and hub.inbox.items() == []
        await gm.tick(playing(used_gb=15.6))                   # the game grew into the margin
        assert gm.state == "aside" and hub.engine.serving is None and "stopped the small model" in gm.note
        await gm.tick(playing(used_gb=12))                     # no second offer this time
        assert hub.inbox.items() == [] and gm.state == "aside"
    run(go())


def test_no_offer_without_room_or_when_told_to_pause(tmp_path):
    gm, hub, _ = make(tmp_path)

    async def go():
        await gm.tick(playing(used_gb=20))
        await gm.tick(playing(used_gb=13))                     # 3 GB free: not enough with the margin
        assert hub.inbox.items() == [] and "not enough free graphics memory" in gm.note
    run(go())
    gm2, hub2, _ = make(tmp_path / "b")
    gm2.settings.set_program("Cyberpunk2077.exe", micro="pause")

    async def go2():
        await gm2.tick(playing(used_gb=20))
        await gm2.tick(playing(used_gb=9))
        assert hub2.inbox.items() == [] and gm2.state == "aside"
    run(go2())


def test_keep_working_downloads_the_micro_model_first(tmp_path):
    gm, hub, _ = make(tmp_path, installed=False)

    async def go():
        await gm.tick(playing(used_gb=20))
        await gm.tick(playing(used_gb=9))
        assert "downloads once" in hub.inbox.items()[0]["detail"]
        await _choose(hub, "gamemode:micro", "Keep working, always for Cyberpunk2077.exe")
        assert gm.downloading and gm.settings.programs["cyberpunk2077.exe"]["micro"] == "keep"
        for _ in range(50):
            if hub.engine.installed:
                break
            await asyncio.sleep(0.01)
        await gm.tick(playing(used_gb=9))
        assert gm.state == "micro" and hub.engine.downloads == ["gemma-4-e2b"]
    run(go())


def test_ask_mode_asks_first_and_keep_running_holds_until_it_closes(tmp_path):
    gm, hub, _ = make(tmp_path, mode="ask")

    async def go():
        await gm.tick(playing())
        assert gm.state == "asking" and hub.engine.serving is not None
        await _choose(hub, "gamemode:aside", "Keep running")
        await gm.tick(playing())
        assert gm.state == "watching" and hub.inbox.items() == []          # not asked again while it runs
        await gm.tick(reading())                                           # closed
        await gm.tick(playing())
        assert gm.state == "asking"                                        # a new session asks again
        await _choose(hub, "gamemode:aside", "Always for Cyberpunk2077.exe")
        assert gm.paused and gm.settings.programs["cyberpunk2077.exe"]["counts"] == "always"
    run(go())


def test_never_mode_and_manual_pause(tmp_path):
    gm, hub, clock = make(tmp_path, mode="never")

    async def go():
        await gm.tick(playing())
        assert gm.state == "watching" and hub.engine.serving is not None
        await gm.pause(True)
        assert gm.paused and hub.engine.serving is None
        clock.t += 1000
        await gm.tick(reading())
        assert gm.paused                                       # a manual pause waits for Resume
        await gm.pause(False)
        assert gm.state == "watching" and hub.engine.serving["id"] == "file:gemma-12b"
    run(go())


def test_starting_a_model_yourself_takes_over(tmp_path):
    gm, hub, _ = make(tmp_path)

    async def go():
        await gm.tick(playing(used_gb=20))
        hub.engine.start("file:other-model")
        await gm.tick(playing())
        assert gm.state == "watching" and "you started a model" in gm.note
        await gm.tick(playing())
        assert gm.state == "watching"                          # not again until the game closes
    run(go())


def test_settings_survive_a_restart(tmp_path):
    gm, _, _ = make(tmp_path)
    gm.set_mode("ask")
    gm.set_program("Valorant.exe", counts="never")
    again = GameMode(FakeHub(FakeEngine()), tmp_path / "gamemode.json", probe=object())
    assert again.settings.mode == "ask" and again.settings.programs == {"valorant.exe": {"counts": "never"}}
    with pytest.raises(ValueError):
        gm.set_mode("sometimes")


def test_gamemode_api(tmp_path):
    from fastapi.testclient import TestClient
    from sage_os_hub.app import create_app
    from sage_os_hub.config import Config
    cfg = Config(data_dir=tmp_path / "data", hermes_home=tmp_path, claude_enabled=False, hermes_profiles=[])
    with TestClient(create_app(cfg, start_adapters=False), base_url="http://127.0.0.1") as c:
        H = {"X-Sage-OS": "1"}
        assert c.get("/api/gamemode").json()["mode"] == "always"
        assert c.post("/api/gamemode/settings", json={"mode": "ask"}).status_code == 403
        assert c.post("/api/gamemode/settings", json={"mode": "sometimes"}, headers=H).status_code == 422
        assert c.post("/api/gamemode/settings", json={"mode": "ask"}, headers=H).json()["mode"] == "ask"
        r = c.post("/api/gamemode/program", json={"name": "Valorant.exe", "counts": "never"}, headers=H).json()
        assert r["programs"] == {"valorant.exe": {"counts": "never"}}
        r = c.post("/api/gamemode/program", json={"name": "Valorant.exe", "clear": True}, headers=H).json()
        assert r["programs"] == {}
        assert c.post("/api/gamemode/pause", json={"on": True}, headers=H).json()["state"] == "aside"
        assert c.post("/api/gamemode/pause", json={"on": False}, headers=H).json()["state"] == "watching"
        assert (cfg.data_dir / "gamemode.json").exists()


def test_the_note_says_when_the_model_is_back(tmp_path):
    gm, hub, clock = make(tmp_path)

    async def go():
        await gm.tick(playing(used_gb=20))
        await gm.tick(reading())                               # the game closed
        clock.t += 200
        await gm.tick(reading())                               # resumes: the model starts loading
        assert gm.state == "watching" and "is loading again" in gm.note
        await gm.tick(reading())                               # ready on the next reading
        assert gm.note == "file:gemma-12b is back"
    run(go())
