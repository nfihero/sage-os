"""Y1.7, the gate (D27, D28): two hubs on one computer, acting as two devices, each make chats, approvals,
undos and deletes; their change logs are exchanged as files and replayed. Both must end up with the same
synced records, nothing lost or duplicated, deletes respected, whatever order the entries arrive in."""
import json
import random
from pathlib import Path

import pytest

from sage_os_hub.app import create_app
from sage_os_hub.config import Config
from sage_os_hub.sync import manifest, new_id

AGENT = "claude:cs_test"


def device(tmp_path: Path, name: str):
    cfg = Config(data_dir=tmp_path / name, hermes_home=tmp_path, claude_enabled=False, hermes_profiles=[],
                 engine_enabled=False)
    return create_app(cfg, start_adapters=False).state.hub


def note(title, body="Some text."):
    return {"op": "create", "folder": "Finance", "title": title, "body": body}


def work(hub, tag: str) -> dict:
    """A day's use on one device: chats, messages, a renamed and a deleted chat, proposals approved,
    rejected and undone, a briefing setting."""
    made = {}
    chat = hub.store.upsert_chat_session
    a = {"id": new_id("ch_"), "title": f"{tag} plan", "provider": "engine", "model": "m", "created": 1.0, "updated": 1.0}
    chat(a)
    for text in ("first", "second", "third"):
        hub.store.add_chat_item(a["id"], "user", {"text": f"{tag} {text}"})
    chat(a | {"title": f"{tag} plan, renamed", "updated": 2.0})
    gone = a | {"id": new_id("ch_"), "title": "scratch"}
    chat(gone)
    hub.store.delete_chat_session(gone["id"])
    kept = hub.writer.propose(AGENT, f"{tag} kept", [note(f"{tag} WACC")])
    hub.writer.approve(kept["id"])
    undone = hub.writer.propose(AGENT, f"{tag} undone", [note(f"{tag} DCF")])
    batch = hub.writer.approve(undone["id"])
    hub.writer.undo(batch["id"])
    dropped = hub.writer.propose(AGENT, f"{tag} dropped", [note(f"{tag} CAPM")])
    hub.writer.reject(dropped["id"], "not now")
    hub.briefings.set_enabled(f"chat:{a['id']}", False)
    made.update(chat=a["id"], deleted=gone["id"], kept=kept["id"], undone=undone["id"], dropped=dropped["id"])
    return made


def export(hub, path: Path) -> Path:
    """What sync will carry: each database's log, as a file."""
    path.write_text(json.dumps({db: log.entries() for db, log in hub.changelogs.items()}), encoding="utf-8")
    return path


def replay(hub, path: Path, order=None) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for db, entries in data.items():
        if order:
            entries = order(entries)
        n += hub.changelogs[db].apply(entries)
    return n


def synced_state(hub) -> dict:
    """Every synced table, row by row, in key order."""
    out = {}
    for db, tables in manifest.synced_tables().items():
        con = hub.changelogs[db].con
        for t in tables:
            key = ", ".join(manifest.KEYS[t])
            cur = con.execute(f"SELECT * FROM {t} ORDER BY {key}")
            names = [d[0] for d in cur.description]
            out[t] = [dict(zip(names, r)) for r in cur.fetchall()]
    return out


def shuffled(seed):
    def order(entries):
        entries = list(entries)
        random.Random(seed).shuffle(entries)
        return entries
    return order


@pytest.mark.parametrize("order", [None, lambda es: list(reversed(es)), shuffled(1), shuffled(2)],
                         ids=["in order", "reversed", "shuffled 1", "shuffled 2"])
def test_two_devices_converge(tmp_path, order):
    a, b = device(tmp_path, "a"), device(tmp_path, "b")
    made_a, made_b = work(a, "pc"), work(b, "mac")
    fa, fb = export(a, tmp_path / "a.json"), export(b, tmp_path / "b.json")
    assert replay(b, fa, order) > 0 and replay(a, fb, order) > 0
    sa, sb = synced_state(a), synced_state(b)
    assert sa == sb
    # nothing lost or duplicated: each device's records are all there, once
    for made in (made_a, made_b):
        ids = [r["id"] for r in sa["proposals"]]
        for p in ("kept", "undone", "dropped"):
            assert ids.count(made[p]) == 1
        statuses = {r["id"]: r["status"] for r in sa["proposals"]}
        assert statuses[made["kept"]] == "applied" and statuses[made["dropped"]] == "rejected"
        assert [x["status"] for x in sa["batches"] if x["proposal_id"] == made["undone"]] == ["undone"]
        assert len([x for x in sa["chat_items"] if x["session_id"] == made["chat"]]) == 3
    # deletes respected on both
    for hub in (a, b):
        live = {s["id"] for s in hub.store.chat_sessions()}
        assert {made_a["chat"], made_b["chat"]} <= live and not {made_a["deleted"], made_b["deleted"]} & live
    assert len(sa["chat_items"]) == 6 and len({r["id"] for r in sa["chat_items"]}) == 6
    # replaying again changes nothing
    assert replay(b, fa) == 0 and synced_state(b) == sb


def test_edits_to_the_same_record_on_both_devices_settle_on_the_later_one(tmp_path):
    a, b = device(tmp_path, "a"), device(tmp_path, "b")
    cid = work(a, "pc")["chat"]
    replay(b, export(a, tmp_path / "a1.json"))
    row = {s["id"]: s for s in b.store.chat_sessions()}[cid]
    a.store.upsert_chat_session(row | {"title": "renamed on the PC"})
    b.store.upsert_chat_session(row | {"title": "renamed on the Mac"})       # later
    fa, fb = export(a, tmp_path / "a2.json"), export(b, tmp_path / "b2.json")
    replay(a, fb), replay(b, fa)
    assert synced_state(a) == synced_state(b)
    assert {s["id"]: s for s in a.store.chat_sessions()}[cid]["title"] == "renamed on the Mac"


def test_a_delete_wins_over_an_earlier_edit_from_the_other_device(tmp_path):
    a, b = device(tmp_path, "a"), device(tmp_path, "b")
    cid = work(a, "pc")["chat"]
    replay(b, export(a, tmp_path / "a1.json"))
    row = {s["id"]: s for s in a.store.chat_sessions()}[cid]
    a.store.upsert_chat_session(row | {"title": "edited"})
    b.store.delete_chat_session(cid)                                          # later
    fa, fb = export(a, tmp_path / "a2.json"), export(b, tmp_path / "b2.json")
    replay(a, fb), replay(b, fa)
    assert synced_state(a) == synced_state(b)
    assert cid not in {s["id"] for s in a.store.chat_sessions()}


@pytest.mark.parametrize("first", ["a", "b"])
def test_a_later_edit_on_the_other_device_doesnt_bring_a_deleted_chat_back(tmp_path, first):
    a, b = device(tmp_path, "a"), device(tmp_path, "b")
    cid = work(a, "pc")["chat"]
    replay(b, export(a, tmp_path / "a1.json"))
    row = {s["id"]: s for s in b.store.chat_sessions()}[cid]
    a.store.delete_chat_session(cid)
    b.store.upsert_chat_session(row | {"title": "renamed on the Mac, later"})
    fa, fb = export(a, tmp_path / "a2.json"), export(b, tmp_path / "b2.json")
    if first == "a":
        replay(a, fb), replay(b, fa)
    else:
        replay(b, fa), replay(a, fb)
    assert synced_state(a) == synced_state(b)
    for hub in (a, b):
        assert cid not in {s["id"] for s in hub.store.chat_sessions()}


def test_both_devices_deleting_keep_the_earliest_delete_time(tmp_path):
    a, b = device(tmp_path, "a"), device(tmp_path, "b")
    cid = work(a, "pc")["chat"]
    replay(b, export(a, tmp_path / "a1.json"))
    a.store.delete_chat_session(cid)
    b.store.delete_chat_session(cid)
    fa, fb = export(a, tmp_path / "a2.json"), export(b, tmp_path / "b2.json")
    replay(a, fb), replay(b, fa)
    assert synced_state(a) == synced_state(b)
