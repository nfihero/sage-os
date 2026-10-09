"""Google Drive connector (D22.5): consent with PKCE, path lookup, export into the source library."""
import io
import json
import time
import zipfile
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from sage_os_hub.knowledge import gdrive
from sage_os_hub.knowledge.gdrive import DriveError, GoogleDrive
from sage_os_hub.knowledge.sources import SourceLibrary, SourceSpec


def docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>")
    return buf.getvalue()


@pytest.fixture
def drive(tmp_path, monkeypatch):
    (tmp_path / "client.json").write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))
    calls = []
    tree = {("root", "Deal Club"): "F1", ("root", "Resume/CV"): "F2"}
    docs = {("F1", "Pitch Framework"): "D1", ("F1", "Acme Industrial: Initial M&A Pitch"): "D2", ("F2", "Cover Letter"): "D3"}

    def post(url, data=None, timeout=None):
        calls.append(("POST", url, data))
        if url == gdrive.TOKEN_URL and data["grant_type"] == "authorization_code":
            return httpx.Response(200, json={"access_token": "A1", "refresh_token": "R1", "expires_in": 3600})
        if url == gdrive.TOKEN_URL:
            return httpx.Response(200, json={"access_token": "A2", "expires_in": 3600})
        return httpx.Response(200)

    def get(url, params=None, headers=None, timeout=None):
        calls.append(("GET", url, params))
        assert headers["Authorization"].startswith("Bearer ")
        if url.endswith("/about"):
            return httpx.Response(200, json={"user": {"emailAddress": "me@example.com"}})
        if url.endswith("/files"):
            q = params["q"]
            parent, table = q.split("'")[1], tree if "folder" in q else docs
            if "name = '" not in q:                       # listing a folder's children
                return httpx.Response(200, json={"files": [{"id": i, "name": n} for (p, n), i in table.items() if p == parent]})
            name = q.split("name = '")[1].rsplit("'", 1)[0]
            fid = table.get((parent, name))
            return httpx.Response(200, json={"files": [{"id": fid, "name": name}] if fid else []})
        if url.endswith("/export"):
            return httpx.Response(200, content=docx("Sell-side pitch: buyer universe and valuation range"))
        return httpx.Response(404)

    monkeypatch.setattr(gdrive.httpx, "post", post)
    monkeypatch.setattr(gdrive.httpx, "get", get)
    d = GoogleDrive(tmp_path / "client.json", tmp_path / "token.json")
    d.calls = calls
    return d


def connect(d):
    url = d.start("http://127.0.0.1:8787/api/google/callback")
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"] and q["scope"] == [gdrive.SCOPE] and q["access_type"] == ["offline"]
    d.finish("CODE", q["state"][0])
    return q


def test_consent_stores_a_refresh_token_and_rejects_unknown_state(drive, tmp_path):
    assert drive.status() == {"configured": True, "connected": False, "client_file": str(tmp_path / "client.json"), "account": None}
    q = connect(drive)
    sent = [c for c in drive.calls if c[0] == "POST"][0][2]
    assert sent["code_verifier"] and sent["code"] == "CODE"
    st = drive.status()
    assert st["connected"] and st["account"] == "me@example.com" and "R1" not in json.dumps(st)
    with pytest.raises(DriveError):
        drive.finish("CODE", q["state"][0])            # a state works once
    with pytest.raises(DriveError):
        drive.finish("CODE", "forged")


def test_no_client_file_means_not_configured(tmp_path):
    d = GoogleDrive(tmp_path / "missing.json", tmp_path / "token.json")
    assert d.status()["configured"] is False
    with pytest.raises(DriveError):
        d.start("http://127.0.0.1:1/cb")


def test_a_drive_folder_is_read_through_the_api(drive, tmp_path, monkeypatch):
    """No Drive for desktop: the folder is listed and files downloaded through the API (D22.5)."""
    import io as _io
    from pypdf import PdfWriter
    buf = _io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(100, 100)
    w.write(buf)
    pdf = buf.getvalue()
    listing = {"F1": [{"id": "B1", "name": "Big Book.pdf", "mimeType": "application/pdf", "size": str(len(pdf)),
                       "modifiedTime": "2026-10-09T07:18:55.095Z"},
                      {"id": "D1", "name": "Pitch Framework", "mimeType": "application/vnd.google-apps.document",
                       "modifiedTime": "2026-10-01T00:00:00Z"},
                      {"id": "S1", "name": "Sub", "mimeType": "application/vnd.google-apps.folder", "modifiedTime": "2026-10-01T00:00:00Z"}],
               "S1": [{"id": "T1", "name": "notes.md", "mimeType": "text/markdown", "size": "20", "modifiedTime": "2026-10-01T00:00:00Z"}]}
    real_get = gdrive.httpx.get

    def get(url, params=None, headers=None, timeout=None):
        q = (params or {}).get("q", "")
        if url.endswith("/files") and "name = '" not in q and "folder'" not in q:
            parent = q.split("'")[1]
            return httpx.Response(200, json={"files": listing.get(parent, [])})
        return real_get(url, params=params, headers=headers, timeout=timeout)
    monkeypatch.setattr(gdrive.httpx, "get", get)

    class Stream:
        def __init__(self, data):
            self.status_code, self.data = 200, data

        def iter_bytes(self, n):
            yield self.data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    downloads = []

    def stream(method, url, **kw):
        downloads.append(url)
        return Stream(pdf if "B1" in url else b"# Notes\nbuyer universe")
    monkeypatch.setattr(gdrive.httpx, "stream", stream)
    connect(drive)
    spec = SourceSpec("gdrive", __import__("pathlib").Path("My Drive"), ["Deal Club"], api=True)
    lib = SourceLibrary(tmp_path / "copy", [spec], tmp_path / "idx.db", drive)
    stats = lib.sync("gdrive")
    rels = sorted(r for r, st in lib.files("gdrive") if st != "skipped")
    assert rels == ["Deal Club/Big Book.pdf", "Deal Club/Pitch Framework.gdoc", "Deal Club/Sub/notes.md"]
    assert stats["google"] == 1 and (tmp_path / "copy" / "gdrive" / "Deal Club" / "Big Book.pdf").exists()
    n = len(downloads)
    lib.sync("gdrive")                                    # unchanged in Drive: nothing downloaded again
    assert len(downloads) == n


def test_googles_download_name_is_found(tmp_path):
    (tmp_path / "client_secret_123-abc.apps.googleusercontent.com.json").write_text(
        json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))
    d = GoogleDrive(tmp_path / "google-oauth-client.json", tmp_path / "token.json")
    assert d.status()["configured"] and d.status()["client_file"].endswith("googleusercontent.com.json")


def test_resolve_walks_the_path_and_refreshes_expired_tokens(drive):
    connect(drive)
    tok = json.loads(drive.token_path.read_text())
    tok["expires_at"] = time.time() - 1
    drive.token_path.write_text(json.dumps(tok))
    assert drive.resolve("My Drive/Deal Club/Pitch Framework.gdoc")["id"] == "D1"
    assert any(c[0] == "POST" and c[2]["grant_type"] == "refresh_token" for c in drive.calls)
    # Drive for desktop drops characters a file name can't hold: "Resume/CV" -> "Resume CV", ":" removed
    assert drive.resolve("My Drive/Deal Club/Acme Industrial Initial M&A Pitch.gdoc")["id"] == "D2"
    assert drive.resolve("My Drive/Resume CV/Cover Letter.gdoc")["id"] == "D3"
    with pytest.raises(DriveError):
        drive.resolve("My Drive/Nope/Pitch Framework.gdoc")
    with pytest.raises(DriveError):
        drive.resolve("Other computers/Mac/x.gdoc")


def test_sync_exports_google_files_only_when_connected(drive, tmp_path):
    orig = tmp_path / "G" / "My Drive" / "Deal Club"
    orig.mkdir(parents=True)
    (orig / "Pitch Framework.gdoc").write_text('{"stub": true}')
    (orig / "notes.md").write_text("plain markdown about the buyer universe")
    spec = SourceSpec("drive", tmp_path / "G", ["My Drive/Deal Club"], google=True)
    lib = SourceLibrary(tmp_path / "copy", [spec], tmp_path / "idx.db", drive)

    lib.sync("drive")                                    # not connected yet: listed, not copied
    skipped = {s["path"]: s["reason"] for s in lib.summary()["sources"][0]["skipped"]}
    assert "connect Google Drive" in skipped["My Drive/Deal Club/Pitch Framework.gdoc"]

    connect(drive)
    stats = lib.sync("drive")
    assert stats["google"] == 1
    copy = tmp_path / "copy" / "drive" / "My Drive" / "Deal Club" / "Pitch Framework.gdoc.docx"
    assert copy.exists()
    hits = lib.search("buyer universe valuation")["results"]
    assert [h["path"] for h in hits] == ["My Drive/Deal Club/Pitch Framework.gdoc"]
    assert lib.read("drive", hits[0]["path"])["text"].startswith("Sell-side pitch")
    assert (orig / "Pitch Framework.gdoc").read_text() == '{"stub": true}'      # the original is never written

    exports = sum(1 for c in drive.calls if c[1].endswith("/export"))
    lib.sync("drive")                                    # unchanged stub: no new export
    assert sum(1 for c in drive.calls if c[1].endswith("/export")) == exports
