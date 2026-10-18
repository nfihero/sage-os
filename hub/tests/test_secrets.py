"""Y2: no secret is a plain file in app data. The Google sign-in token moves into the OS keychain, each device gets
its own pairing key there, and the engine's key was never written down."""
import json

from fastapi.testclient import TestClient

from sage_os_hub import keys
from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.sync.devicekey import DeviceKey

H = {"X-Sage-OS": "1"}
TOKEN = {"access_token": "ya29.secret-access", "refresh_token": "1//refresh-secret-xyz", "expires_at": 9e9,
         "account": "someone@example.com"}


def hub_on(tmp_path):
    c = Config(data_dir=tmp_path / "d", local_config=tmp_path / "d" / "config.local.toml", claude_enabled=False,
               hermes_profiles=[], engine_root=tmp_path / "d" / "engine")
    return create_app(c, start_adapters=False)


def files_containing(root, *needles):
    hits = []
    for p in root.rglob("*"):
        if p.is_file():
            data = p.read_bytes()
            hits += [str(p) for n in needles if n.encode() in data]
    return hits


def test_the_google_token_moves_into_the_keychain(tmp_path, memory_keychain):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "google-token.json").write_text(json.dumps(TOKEN), encoding="utf-8")   # how 0.28 kept it
    hub = hub_on(tmp_path).state.hub
    assert not (tmp_path / "d" / "google-token.json").exists()
    assert json.loads(memory_keychain.get_password("Sage OS", "google-token")) == TOKEN
    assert hub.drive.status()["connected"] and hub.drive.status()["account"] == "someone@example.com"
    hub.drive._save_token(TOKEN | {"access_token": "ya29.new"})            # a refresh writes to the keychain, not a file
    assert not (tmp_path / "d" / "google-token.json").exists()
    assert json.loads(memory_keychain.get_password("Sage OS", "google-token"))["access_token"] == "ya29.new"


def test_a_token_too_big_for_the_keychain_drops_what_can_be_fetched_again(tmp_path, memory_keychain):
    hub = hub_on(tmp_path).state.hub
    hub.drive._save_token(TOKEN | {"access_token": "x" * 2000})
    kept = json.loads(memory_keychain.get_password("Sage OS", "google-token"))
    assert kept["refresh_token"] == TOKEN["refresh_token"] and "access_token" not in kept


def test_disconnecting_google_removes_the_token(tmp_path, memory_keychain, monkeypatch):
    hub = hub_on(tmp_path).state.hub
    hub.drive._save_token(TOKEN)
    monkeypatch.setattr("sage_os_hub.knowledge.gdrive.httpx.post", lambda *a, **k: None)
    hub.drive.disconnect()
    assert memory_keychain.get_password("Sage OS", "google-token") is None and not hub.drive.status()["connected"]


def test_without_a_keychain_the_token_stays_in_its_file(tmp_path, monkeypatch):
    class Broken:
        def get_password(self, *a):
            raise RuntimeError("no keychain backend")

        def set_password(self, *a):
            raise RuntimeError("no keychain backend")
    real = keys.Keys.__init__
    monkeypatch.setattr(keys.Keys, "__init__", lambda self, backend=None: real(self, Broken()))
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "google-token.json").write_text(json.dumps(TOKEN), encoding="utf-8")
    hub = hub_on(tmp_path).state.hub
    assert (tmp_path / "d" / "google-token.json").exists() and hub.drive.status()["connected"]
    assert hub.device_key is None


def test_each_device_has_a_stable_pairing_key(tmp_path, memory_keychain):
    a = hub_on(tmp_path)
    hub = a.state.hub
    k1 = hub.device_key
    assert k1 is not None and len(k1.fingerprint) == 14 and k1.fingerprint.count("-") == 2
    assert DeviceKey.verify(k1.public_b64, k1.sign(b"hello"), b"hello") and not DeviceKey.verify(k1.public_b64, k1.sign(b"hello"), b"other")
    again = hub_on(tmp_path).state.hub.device_key                          # a restart: the same key
    assert again.public_b64 == k1.public_b64
    with TestClient(a, base_url="http://127.0.0.1") as client:
        s = client.get("/api/storage").json()
        assert s["device"]["pairing_key"] == k1.fingerprint and s["secrets"] == "keychain"


def test_no_secret_is_a_plain_file_in_app_data(tmp_path, memory_keychain):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "google-token.json").write_text(json.dumps(TOKEN), encoding="utf-8")
    hub = hub_on(tmp_path).state.hub
    private = memory_keychain.get_password("Sage OS", f"device-key:{hub.device.id}")
    assert private
    assert files_containing(tmp_path / "d", TOKEN["refresh_token"], TOKEN["access_token"], private) == []
