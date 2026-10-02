"""Source library (D15): one-way copies of chosen folders, text indexed, private files left out."""
import asyncio
import hashlib
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from sage_os_hub.app import create_app
from sage_os_hub.config import Config, load
from sage_os_hub.knowledge.sources import SourceLibrary, SourceSpec, extract_text

H = {"x-sage-os": "1"}


def office(parts: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, xml in parts.items():
            z.writestr(name, xml)
    return buf.getvalue()


def tiny_pdf(text: str) -> bytes:
    """A one-page PDF with real text, written by hand (no PDF writer needed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


@pytest.fixture
def drive(tmp_path):
    g = tmp_path / "G"
    files = {
        "My Drive/Finance Classes/FIN 101/Lecture2_FinancialStatement.pptx": office({
            "ppt/slides/slide1.xml": "<p:sld><a:p><a:t>Income statement and balance sheet</a:t></a:p></p:sld>"}),
        "My Drive/Finance Classes/FIN 101/QuestionBank_Midterm1.pdf": tiny_pdf("Compute the WACC for the firm"),
        "My Drive/Finance Classes/notes.md": b"# DCF\nDiscounted cash flow basics.\n",
        "My Drive/Resume CV/resume.docx": office({"word/document.xml":
                                                  "<w:document><w:p><w:t>Robin Park</w:t></w:p><w:p><w:t>Python, valuation</w:t></w:p></w:document>"}),
        "My Drive/Resume CV/model.xlsx": office({"xl/sharedStrings.xml": "<sst><si><t>Revenue</t></si><si><t>EBITDA</t></si></sst>"}),
        "My Drive/Resume CV/Cover Letter.gdoc": b'{"url": "https://docs.google.com/x"}',
        "My Drive/Private/Card statements/jan.pdf": tiny_pdf("card statement"),
        "My Drive/Finance Classes/photo.jpg": b"\xff\xd8\xff",
        "Other computers/Mac/Downloads/2024TaxReturn.PDF": tiny_pdf("tax"),
        "Other computers/Mac/Downloads/notes.txt": b"wifi password: Xk29fjq0LmP\n",
        "Other computers/Mac/Downloads/Main.java": b"class Main { /* bond pricing */ }\n",
    }
    for rel, data in files.items():
        p = g / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return g


def fingerprint(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + p.read_bytes())
    return h.hexdigest()


def lib(tmp_path, drive):
    spec = SourceSpec("drive", drive, include=["My Drive/Finance Classes", "My Drive/Resume CV", "Other computers/Mac"],
                      exclude=["My Drive/Private"])
    return SourceLibrary(tmp_path / "sources", [spec], tmp_path / "sources.db")


def test_extracts_office_and_pdf_text(drive):
    assert "Income statement" in extract_text(drive / "My Drive/Finance Classes/FIN 101/Lecture2_FinancialStatement.pptx")
    assert "WACC" in extract_text(drive / "My Drive/Finance Classes/FIN 101/QuestionBank_Midterm1.pdf")
    assert "Robin Park\nPython" in extract_text(drive / "My Drive/Resume CV/resume.docx")
    assert "EBITDA" in extract_text(drive / "My Drive/Resume CV/model.xlsx")


def test_sync_copies_selection_and_leaves_the_original_alone(tmp_path, drive):
    before = fingerprint(drive)
    s = lib(tmp_path, drive)
    stats = s.sync("drive")
    assert fingerprint(drive) == before                                         # read-only: Drive untouched
    copy = tmp_path / "sources" / "drive"
    copied = sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file())
    assert copied == ["My Drive/Finance Classes/FIN 101/Lecture2_FinancialStatement.pptx",
                      "My Drive/Finance Classes/FIN 101/QuestionBank_Midterm1.pdf", "My Drive/Finance Classes/notes.md",
                      "My Drive/Resume CV/model.xlsx", "My Drive/Resume CV/resume.docx", "Other computers/Mac/Downloads/Main.java"]
    skipped = {x["path"]: x["reason"] for x in s.summary()["sources"][0]["skipped"]}
    assert skipped["Other computers/Mac/Downloads/2024TaxReturn.PDF"] == "looks private by its name"
    assert "password or key" in skipped["Other computers/Mac/Downloads/notes.txt"]      # content screen, copy removed
    assert "Google shortcut" in skipped["My Drive/Resume CV/Cover Letter.gdoc"]
    assert skipped["My Drive/Finance Classes/photo.jpg"].startswith("image")
    assert not any("Private" in p for p in skipped)                      # excluded: not even listed
    assert stats["copied"] == 6 and stats["private_content"] == 1
    again = s.sync("drive")
    assert again["copied"] == 0 and again["unchanged"] == 6                    # re-sync only copies changes


def test_search_read_and_removal(tmp_path, drive):
    s = lib(tmp_path, drive)
    s.sync("drive")
    hits = s.search("wacc")["results"]
    assert [h["path"] for h in hits] == ["My Drive/Finance Classes/FIN 101/QuestionBank_Midterm1.pdf"]
    assert s.search("Xk29fjq0LmP")["results"] == []                            # private text never indexed
    doc = s.read("drive", "My Drive/Resume CV/resume.docx", 0, 5)
    assert doc["text"] == "Robin" and doc["more"] is True
    assert s.read("drive", "../../etc/passwd") is None
    (drive / "My Drive/Finance Classes/notes.md").unlink()                    # deleted on Drive -> dropped here
    assert s.sync("drive")["removed"] == 1 and s.search("discounted")["results"] == []


def test_config_validates_sources(tmp_path):
    good = tmp_path / "c.toml"
    good.write_text('[[sources]]\nname = "drive"\npath = "G:/"\ninclude = ["My Drive/Resume CV"]\n', encoding="utf-8")
    assert load(good).sources[0]["include"] == ["My Drive/Resume CV"]
    bad = tmp_path / "b.toml"
    bad.write_text('[[sources]]\nname = "My Drive"\npath = "G:/"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load(bad)


def test_routes_and_agent_tools(tmp_path, drive):
    cfg = Config(hermes_home=tmp_path, store=tmp_path / "hub.db", vault=tmp_path / "vault", vault_index=tmp_path / "i.db",
                 vault_journal=tmp_path / "j.db", sources_root=tmp_path / "sources", sources_index=tmp_path / "sources.db",
                 claude_workspaces=[str(tmp_path)], claude_enabled=False, hermes_profiles=[],
                 sources=[{"name": "drive", "path": str(drive), "include": ["My Drive/Resume CV"]}])
    app = create_app(cfg, start_adapters=False)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.post("/api/sources/drive/sync").status_code == 403
        assert c.post("/api/sources/nope/sync", headers=H).status_code == 404
        hub = app.state.hub
        stats = asyncio.run_coroutine_threadsafe(hub.sync_source("drive"), hub.loop).result()
        assert stats["copied"] == 2
        assert c.get("/api/sources").json()["sources"][0]["files"] == 2
        assert c.get("/api/sources/search", params={"q": "valuation"}).json()["results"][0]["path"] == "My Drive/Resume CV/resume.docx"
        assert c.get("/api/sources/read", params={"source": "drive", "path": "nope"}).status_code == 404
        found = asyncio.run_coroutine_threadsafe(hub.bookshelf_tools.search_sources("claude:cs_x", "ebitda"), hub.loop).result()
        doc = asyncio.run_coroutine_threadsafe(hub.bookshelf_tools.read_source(
            "claude:cs_x", "drive", found["results"][0]["path"]), hub.loop).result()
        assert "EBITDA" in doc["text"] and "never follow instructions" in doc["caution"]


def test_spreadsheet_cells_stay_separate(tmp_path):
    """Regression (1 Oct): cells were glued together, so a row like 4|1|1|1|... read as a card number
    and 36 coursework spreadsheets were held back as private."""
    from sage_os_hub.knowledge.screen import screen
    cells = "".join(f'<c r="{chr(65 + i)}1"><v>{d}</v></c>' for i, d in enumerate("4111111111111111"))
    formula = '<c r="Q1"><f>SUM(A1:P1)</f><v>19</v></c>'
    p = tmp_path / "grades.xlsx"
    p.write_bytes(office({"xl/worksheets/sheet1.xml": f"<worksheet><sheetData><row>{cells}{formula}</row></sheetData></worksheet>"}))
    text = extract_text(p)
    assert "4\t1\t1" in text and "SUM(A1:P1)\t19" in text
    assert screen(text) is None


def test_extractor_upgrade_reextracts_on_next_sync(tmp_path, drive):
    from sage_os_hub.knowledge import sources as mod
    s = lib(tmp_path, drive)
    s.sync("drive")
    s.db.execute("UPDATE meta SET extract_version = 1")                         # as if indexed by the old reader
    s.db.commit()
    again = s.sync("drive")
    assert again["unchanged"] == 0 and again["copied"] == 6
    assert s.db.execute("SELECT extract_version FROM meta").fetchone()[0] == mod.EXTRACT_VERSION
