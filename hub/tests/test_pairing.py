"""P1 (D45): two devices pair with a one-time code and then talk directly, over TLS, every request signed. Anything
else is refused: an unpaired device, a wrong code, a replay, a request relayed through another connection, and a
device that was removed."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.sync.listener import Peer
from sage_os_hub.sync.peers import Peers, new_code

H = {"X-Sage-OS": "1"}


def device(tmp_path, name):
    c = Config(data_dir=tmp_path / name, local_config=tmp_path / name / "config.local.toml", claude_enabled=False,
               hermes_profiles=[], engine_root=tmp_path / name / "engine", sync_port=0, sync_mdns=False)
    app = create_app(c, start_adapters=False)
    hub = app.state.hub
    hub.sync.host = "127.0.0.1"                       # tests stay on this computer
    hub.device.rename(name)
    return app, hub


@pytest.fixture
def two(tmp_path):
    a_app, a = device(tmp_path, "PC")
    b_app, b = device(tmp_path, "Mac")
    with TestClient(a_app, base_url="http://127.0.0.1") as ac, TestClient(b_app, base_url="http://127.0.0.1") as bc:
        yield a, ac, b, bc


def addr(hub):
    return f"127.0.0.1:{hub.sync.bound}"


def test_two_devices_pair_with_a_code(two):
    a, ac, b, bc = two
    assert ac.get("/api/devices").json()["listening"] is False          # nothing paired: no listener at all
    shown = ac.post("/api/devices/pairing", headers=H).json()
    code = shown["pairing"]["code"]
    assert shown["listening"] and len(code.replace("-", "")) == 12
    r = bc.post("/api/devices/join", json={"address": addr(a), "code": code.lower().replace("-", " ")}, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["paired"]["name"] == "PC" and r.json()["paired"]["fingerprint"] == a.device_key.fingerprint
    pa = ac.get("/api/devices").json()
    assert pa["pairing"] is None and [p["name"] for p in pa["peers"]] == ["Mac"]
    assert pa["peers"][0]["fingerprint"] == b.device_key.fingerprint and "pubkey" not in pa["peers"][0]
    assert bc.get("/api/devices").json()["listening"]                    # the Mac now has a paired device too
    ok = bc.post(f"/api/devices/{a.device.id}/check", headers=H)
    assert ok.status_code == 200 and ok.json()["name"] == "PC" and ok.json()["you"] == b.device.id


def test_a_wrong_code_pairs_nothing_and_five_end_the_session(two):
    a, ac, b, bc = two
    code = ac.post("/api/devices/pairing", headers=H).json()["pairing"]["code"]
    wrong = new_code()
    for i in range(5):
        r = bc.post("/api/devices/join", json={"address": addr(a), "code": wrong}, headers=H)
        assert r.status_code == 400 and "isn't right" in r.text
    r = bc.post("/api/devices/join", json={"address": addr(a), "code": code}, headers=H)
    assert r.status_code == 400 and ("too many" in r.text or "isn't pairing" in r.text)
    assert ac.get("/api/devices").json()["peers"] == [] and bc.get("/api/devices").json()["peers"] == []


def test_strangers_replays_and_relays_are_refused(two, tmp_path):
    a, ac, b, bc = two
    code = ac.post("/api/devices/pairing", headers=H).json()["pairing"]["code"]
    bc.post("/api/devices/join", json={"address": addr(a), "code": code}, headers=H)
    p = Peer(addr(a), expect_key=a.device_key.public_b64)
    try:
        assert p.client.post("/sync/ping", content=b"{}").status_code == 401                     # not signed
        stranger_app, stranger = device(tmp_path, "Stranger")
        with pytest.raises(Exception, match="not a paired device"):
            p.post("/sync/ping", {}, stranger.peers)                                          # signed, but unknown
        raw = json.dumps({}).encode()
        headers = b.peers.sign("POST", "/sync/ping", raw, p.tls_fpr) | {"Content-Type": "application/json"}
        assert p.client.post("/sync/ping", content=raw, headers=headers).status_code == 200
        assert p.client.post("/sync/ping", content=raw, headers=headers).status_code == 401      # the same again: replay
        relayed = b.peers.sign("POST", "/sync/ping", raw, "f" * 64)                             # signed for another connection
        assert p.client.post("/sync/ping", content=raw, headers=relayed | {"Content-Type": "application/json"}).status_code == 401
    finally:
        p.close()
    with pytest.raises(PermissionError, match="different key"):
        Peer(addr(a), expect_key=b.device_key.public_b64)                                       # not the PC we paired with


def test_a_removed_device_cannot_connect_again(two):
    a, ac, b, bc = two
    code = ac.post("/api/devices/pairing", headers=H).json()["pairing"]["code"]
    bc.post("/api/devices/join", json={"address": addr(a), "code": code}, headers=H)
    r = ac.post(f"/api/devices/{b.device.id}/remove", headers=H).json()
    assert r["peers"] == [] and r["listening"] is False                  # the PC's last device: its listener closes
    assert bc.post(f"/api/devices/{a.device.id}/check", headers=H).status_code == 400
    # the PC pairs again with someone else later: the removed Mac is still refused on the new listener
    ac.post("/api/devices/pairing", headers=H)
    p = Peer(addr(a), expect_key=a.device_key.public_b64)
    try:
        with pytest.raises(Exception, match="not a paired device"):
            p.post("/sync/ping", {}, b.peers)
    finally:
        p.close()


def test_the_codes_are_readable_and_single_use(tmp_path):
    import sqlite3
    import threading
    from sage_os_hub.keys import Keys
    from sage_os_hub.sync.devicekey import DeviceKey
    me = DeviceKey.load(Keys(), "dv_01TEST")
    peers = Peers(sqlite3.connect(":memory:", check_same_thread=False), threading.RLock(), me, "dv_01TEST", lambda: "PC")
    codes = {peers.start_pairing()["code"] for _ in range(50)}
    assert len(codes) == 50 and all(not set(c) & set("01ILO") for c in codes)
