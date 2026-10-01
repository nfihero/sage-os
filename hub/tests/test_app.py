"""Write routes demand the Sage OS header and a local origin; foreign hosts are refused."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sage_os_hub.app import create_app
from sage_os_hub.config import Config


def make(tmp_path):
    cfg = Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "index.db", vault_journal=tmp_path / "journal.db", claude_workspaces=[str(tmp_path)])
    return create_app(cfg, start_adapters=False)


def write_routes(app):
    for r in app.routes:
        methods = (getattr(r, "methods", None) or set()) - {"GET", "HEAD"}
        if methods:
            yield r.path.replace("{sid}", "x").replace("{profile}", "sage").replace("{item_id}", "x").replace("{agent_id}", "claude")


def test_every_write_route_needs_the_header(tmp_path):
    app = make(tmp_path)
    paths = list(write_routes(app))
    assert len(paths) >= 7
    with TestClient(app, base_url="http://127.0.0.1") as c:
        for p in paths:
            assert c.post(p, json={"text": "x", "choice": "x"}).status_code == 403, p
            r = c.post(p, json={"text": "x", "choice": "x"},
                       headers={"x-sage-os": "1", "origin": "https://evil.example"})
            assert r.status_code == 403, p


def test_claude_session_create_with_header(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        r = c.post("/api/claude/sessions", json={"title": "t"}, headers={"x-sage-os": "1"})
        assert r.status_code == 200 and r.json()["cwd"] == str(tmp_path)
        bad = c.post("/api/claude/sessions", json={"cwd": str(tmp_path / "nope")}, headers={"x-sage-os": "1"})
        assert bad.status_code == 400


def test_inbox_unknown_item(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        r = c.post("/api/inbox/nope", json={"choice": "deny"}, headers={"x-sage-os": "1"})
        assert r.status_code == 404


def test_state_and_foreign_host(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        assert "inbox" in c.get("/api/state").json()["panels"]
    assert TestClient(make(tmp_path), base_url="http://evil.example").get("/api/state").status_code == 400


def test_ws_rejects_foreign_origin(tmp_path):
    with TestClient(make(tmp_path), base_url="http://127.0.0.1") as c:
        with c.websocket_connect("ws://127.0.0.1/ws", headers={"origin": "http://127.0.0.1:5173"}) as ws:
            assert ws.receive_json()["t"] == "hello"
        with pytest.raises(WebSocketDisconnect) as exc:
            with c.websocket_connect("ws://127.0.0.1/ws", headers={"origin": "https://evil.example"}) as ws:
                ws.receive_json()
        assert exc.value.code == 4403
