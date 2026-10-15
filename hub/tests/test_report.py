"""F1 (D32.6): Report a problem writes a readable report with no notes or chat text, saves it and opens an email."""
import logging
from pathlib import Path

from sage_os_hub import report
from test_engine import H, chat, wait_idle  # noqa: F401  (a hub with a stand-in local model)


def test_the_report_has_what_helps_and_nothing_private(chat, tmp_path, monkeypatch):
    hub, client, rounds = chat
    t = client.post("/api/threads", json={"agent": "chat", "provider": "engine", "model": "qwen"}, headers=H).json()
    client.post(f"/api/threads/{t['id']}/send", json={"text": "What is enterprise value in my DCF notes?"}, headers=H)
    wait_idle(hub, t["parts"][0]["sid"])
    home = str(Path.home())
    logging.getLogger("sage_os").warning("engine failed to load %s/models/x.gguf for someone@example.com with sk-abcdefghijklmnop", home)
    assert client.post("/api/report/preview", json={"description": "x"}).status_code == 403
    text = client.post("/api/report/preview", json={"description": "The chat froze", "doing": "asking a question"}, headers=H).json()["text"]
    assert "The chat froze" in text and "asking a question" in text and "Sage OS" in text and "engine failed" in text
    assert home not in text and "someone@example.com" not in text and "sk-abcdefghijklmnop" not in text
    assert "enterprise value" not in text and "discounted free cash flows" not in text      # no chat text
    assert "DCF formula sheet" not in text                                                  # no note titles


def test_send_saves_the_file_and_opens_an_email(chat, tmp_path, monkeypatch):
    hub, client, rounds = chat
    opened = []
    monkeypatch.setattr(report, "folder", lambda: tmp_path)
    monkeypatch.setattr(report, "open_email", opened.append)
    monkeypatch.setattr("sage_os_hub.app.open_folder", lambda p: opened.append(str(p)))
    r = client.post("/api/report/send", json={"description": "Search shows nothing\nsecond line"}, headers=H).json()
    path = Path(r["path"])
    assert path.parent == tmp_path and path.read_text(encoding="utf-8").startswith("SAGE OS PROBLEM REPORT")
    assert opened[0].startswith("mailto:roundederror@gmail.com?subject=Sage%20OS%20problem%3A%20Search%20shows%20nothing")
    assert path.name in opened[0] and opened[1] == str(tmp_path) and r["opened"]


def test_no_mail_app_still_leaves_the_file(chat, tmp_path, monkeypatch):
    hub, client, rounds = chat
    monkeypatch.setattr(report, "folder", lambda: tmp_path)

    def broken(url):
        raise OSError("no mail app")
    monkeypatch.setattr(report, "open_email", broken)
    r = client.post("/api/report/send", json={}, headers=H).json()
    assert not r["opened"] and Path(r["path"]).exists() and r["to"] == "roundederror@gmail.com"
