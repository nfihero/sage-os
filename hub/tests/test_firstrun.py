"""U2 (D47): five minutes to value. A fresh install measures how long it takes to an AI, a first document and a first
answer (kept on this computer, shown in a problem report); first questions come from the person's own documents;
the catalog marks a quick starter model."""
import json
import time

from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.engine import CATALOG
from sage_os_hub.firstrun import FirstRun, starter_questions

H = {"X-Sage-OS": "1"}


def fresh(tmp_path, name="d"):
    c = Config(data_dir=tmp_path / name, local_config=tmp_path / name / "config.local.toml", claude_enabled=False,
               hermes_profiles=[], engine_root=tmp_path / name / "engine", sync_mdns=False)
    return create_app(c, start_adapters=False)


def wait_for(cond, s=10):
    for _ in range(int(s / 0.1)):
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_a_fresh_install_times_its_firsts(tmp_path):
    app = fresh(tmp_path)
    hub = app.state.hub
    assert hub.firstrun.measuring and hub.firstrun.summary() == {}
    with TestClient(app, base_url="http://127.0.0.1") as client:
        r = client.post("/api/bookshelf/files?name=memo.md", content=b"# Acme memo\nThe Acme deal closes in March.", headers=H)
        assert r.status_code == 200
        assert wait_for(lambda: "first_document" in (hub.firstrun.summary() or {}))
        hub.usage.record("chat", "engine", "qwen", "chat:x", 120, 0)          # no words out: not an answer yet
        assert "first_answer" not in hub.firstrun.summary()
        hub.usage.record("chat", "engine", "qwen", "chat:x", 120, 40)
        s = hub.firstrun.summary()
        assert set(s) >= {"first_document", "first_answer"} and all(v >= 0 for v in s.values())
        text = client.post("/api/report/preview", json={"description": "x"}, headers=H).json()["text"]
        assert "First run" in text and "first answer:" in text
        q = client.get("/api/starters").json()
        assert q["questions"][0] == "What are the main points of “memo”?" and q["firstrun"]["first_answer"] >= 0
    first = json.loads((tmp_path / "d" / "firstrun.json").read_text())["first_answer"]
    hub.firstrun.mark("first_answer")                                         # only the first time counts
    assert json.loads((tmp_path / "d" / "firstrun.json").read_text())["first_answer"] == first


def test_an_install_from_before_isnt_measured(tmp_path):
    fresh(tmp_path)                                                           # it existed before this version
    (tmp_path / "d" / "firstrun.json").unlink()
    hub = fresh(tmp_path).state.hub                                           # hub.db already there
    assert not hub.firstrun.measuring and hub.firstrun.summary() is None
    hub.firstrun.mark("first_answer")
    assert not (tmp_path / "d" / "firstrun.json").exists()


def test_first_questions_fall_back_gracefully(tmp_path):
    hub = fresh(tmp_path).state.hub
    assert starter_questions(hub.sources, notes=0) == ["What can you help me with?", "How do I give you my documents?"]
    assert starter_questions(hub.sources, notes=3)[0] == "What's in my notes?"


def test_the_catalog_has_one_quick_starter_model():
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    starters = [r for r in rows if r.get("starter")]
    assert len(starters) == 1 and starters[0]["size"] < 3.5e9 and not starters[0].get("micro")
    assert FirstRun  # imported for the module's presence
