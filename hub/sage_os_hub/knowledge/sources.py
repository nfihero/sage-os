"""Source library (DECISIONS D15): read-only copies of chosen folders (Google Drive first), kept outside
the vault, with their text extracted and indexed so the user and agents can search and cite them.

  * One-way: the original (e.g. G:\\) is only ever read. The copy lives in data/sources/<name>/.
  * Curated vault stays curated: knowledge moves from a source into a note only through an approved
    proposal (I1). Sources are cited, never edited.
  * Private-looking files never get copied: by name (statements, tax, passport, ...) or by content
    (the K4 screener). They are listed for the user, by path only.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .gdrive import NATIVE, DriveError, GoogleDrive
from .index import HIT_END, HIT_START, fts_query
from .screen import screen

TEXT = {".md", ".txt", ".csv", ".tsv", ".json", ".tex", ".rtf", ".py", ".java", ".js", ".ts", ".tsx", ".c", ".cpp",
        ".h", ".cs", ".r", ".m", ".sql", ".sh", ".yaml", ".yml", ".toml", ".xml", ".vtt", ".srt"}
RICH = {".pdf", ".docx", ".pptx", ".xlsx", ".xlsm", ".html", ".htm", ".ipynb", ".epub"}
SKIP_REASONS = {                      # extension -> why it isn't copied
    **dict.fromkeys((".mp4", ".mov", ".m4a", ".mp3", ".wav", ".avi", ".mkv"), "media"),
    **dict.fromkeys((".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".bmp", ".svg"), "image (no text yet)"),
    **dict.fromkeys((".zip", ".7z", ".rar", ".dmg", ".pkg", ".exe", ".msi", ".iso", ".jar"), "archive or installer"),
    **dict.fromkeys((".class", ".o", ".pyc", ".dll", ".so", ".blend", ".psd"), "binary"),
    **dict.fromkeys((".gdoc", ".gsheet", ".gslides", ".gform", ".gdraw", ".gmap", ".gsite"),
                    "Google shortcut (text lives online; export it to copy)"),
    **dict.fromkeys((".ini", ".iml", ".strings", ".plist", ".lnk", ".ds_store", ".localized"), "system or IDE file"),
}
# Specific phrases, not bare words: "QuestionBank", "Bankruptcy", "FinancialStatement" lectures, "Hw2"
# and "syntax" are coursework and must not be caught. The K4 content screen backs this up after copying.
PRIVATE_NAME = re.compile(
    r"(bank|card|credit|account|brokerage|e)[ _-]?statements?|statement[ _-]?of[ _-]?account|"
    r"\bbank[ _-]?(account|details|letter)|tax[ _-]?(return|transcript|form)|(?<![a-z0-9])(w-?2|1040|1099)(?![a-z0-9])|"
    r"pay[ _-]?(stub|slip)|salary[ _-]?slip|passport|aadhaa?r|(?<![a-z])(pan|ssn)(?![a-z])|social[ _-]?security|"
    r"driv\w*[ _-]?licen[cs]e|(?<![a-z])visa(?![a-z])|invoice|receipt|medical|insurance|"
    r"(?<![a-z])passwords?(?![a-z])|credentials?|secrets?(?![a-z])|\.env\b|data-private", re.I)
MAX_FILE = 50 * 1024 * 1024           # bigger files are skipped (too big to be useful text)...
MAX_BOOK = 400 * 1024 * 1024          # ...except PDFs and EPUBs, where textbooks with images are often far bigger (K12)
MAX_TEXT = 20_000_000                 # characters of extracted text kept per file (a long textbook is ~3M)


@dataclass
class SourceSpec:
    name: str                         # folder name under data/sources/
    path: Path                        # the original, read-only
    include: list[str] = field(default_factory=list)    # sub-paths to copy (empty = everything)
    exclude: list[str] = field(default_factory=list)    # sub-paths never copied
    notes_folder: str | None = None   # vault folder for notes built from this source (K6); default: Name
    strip: list[str] = field(default_factory=list)      # leading source folders dropped in vault paths
    google: bool = False              # a Drive for desktop folder: Google Docs/Sheets/Slides come through the API (D22)
    copy: bool = True                 # False: index the files where they are (the Library's Files/, D25); never
                                      # copied, and sync never deletes or changes them
    api: bool = False                 # `path` is a Drive path ("My Drive"), read through the Drive API: no local copy of
                                      # Drive needed, so it works on any computer once Drive is connected (D22.5)


@dataclass
class RemoteFile:
    """A file listed through the Drive API, shaped like what sync uses from a local Path."""
    id: str
    mime: str
    st_size: int
    st_mtime: float
    suffix: str

    def stat(self) -> "RemoteFile":
        return self


# -- text extraction ------------------------------------------------------------------------------
EXTRACT_VERSION = 3   # bump when extraction changes, so the next sync re-extracts every file
# 2: spreadsheet cells (and Word table cells) are tab-separated. Version 1 glued neighbouring cells
#    together ("4","1","1","1" -> "4111"), which made long digit runs look like card or ID numbers.
# 3: headings in Word, HTML and EPUB become markdown `#` lines (chapters for K12); EPUB read; no PDF page cap.

HTML_HEAD = re.compile(r"(?is)<h([1-3])\b[^>]*>(.*?)</h\1>")


def _html_text(raw: str) -> str:
    """HTML to text, keeping h1-h3 as markdown headings."""
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", raw)
    raw = HTML_HEAD.sub(lambda m: "\n\n" + "#" * int(m.group(1)) + " "
                        + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip() + "\n\n", raw)
    raw = re.sub(r"(?i)</(p|div|li|tr|br|h[4-6])>|<br\s*/?>", "\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def _epub_text(z: zipfile.ZipFile) -> str:
    """An EPUB's chapters in reading order (its spine), headings kept."""
    names = z.namelist()
    container = z.read("META-INF/container.xml").decode("utf-8", "replace") if "META-INF/container.xml" in names else ""
    m = re.search(r'full-path="([^"]+)"', container)
    order = []
    if m and m.group(1) in names:
        opf_path = m.group(1)
        opf = z.read(opf_path).decode("utf-8", "replace")
        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        items = dict(re.findall(r'<item\b[^>]*\bid="([^"]+)"[^>]*\bhref="([^"]+)"', opf))
        items |= {i: h for h, i in re.findall(r'<item\b[^>]*\bhref="([^"]+)"[^>]*\bid="([^"]+)"', opf)}
        order = [base + items[i] for i in re.findall(r'<itemref\b[^>]*\bidref="([^"]+)"', opf) if i in items]
    order = [n for n in order if n in names] or sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))
    return "\n\n".join(_html_text(z.read(n).decode("utf-8", "replace")) for n in order)


def _docx_text(data: bytes) -> str:
    """Word XML to text: Heading 1-3 paragraphs become markdown headings; table cells tab-separated."""
    s = data.decode("utf-8", "replace")

    def para(m):
        p = m.group(0)
        style = re.search(r'<w:pStyle w:val="(?:Heading|heading|Titre|berschrift) ?([1-3])"', p)
        text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"</w:tc>", "\t", p)))
        return ("#" * int(style.group(1)) + " " + text.strip() + "\n") if style and text.strip() else text + "\n"
    return re.sub(r"(?s)<w:p\b.*?</w:p>", para, s.replace("</w:tc>", "\t</w:tc>"))


def _xml_text(data: bytes, para_tags: tuple[str, ...], cell_tags: tuple[str, ...] = ()) -> str:
    s = data.decode("utf-8", "replace")
    for t in cell_tags:
        s = re.sub(rf"</{t}>", "\t", s)
    for t in para_tags:
        s = re.sub(rf"</{t}>", "\n", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def extract_text(path: Path) -> str:
    """Plain text of a document, best effort. Raises on files that can't be read at all."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ValueError("encrypted PDF")
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    if ext in (".docx", ".pptx", ".xlsx", ".xlsm", ".epub"):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if ext == ".epub":
                return _epub_text(z)
            if ext == ".docx":
                parts = [n for n in names if re.match(r"word/(document|footnotes|endnotes)\d*\.xml$", n)]
                return "\n".join(re.sub(r"<[^>]+>", "", _docx_text(z.read(n))) for n in parts)
            if ext == ".pptx":
                slides = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                                key=lambda n: int(re.findall(r"\d+", n)[-1]))
                return "\n\n".join(f"[slide {i}]\n" + _xml_text(z.read(n), ("a:p",)) for i, n in enumerate(slides, 1))
            strings = _xml_text(z.read("xl/sharedStrings.xml"), ("si",)) if "xl/sharedStrings.xml" in names else ""
            inline = "\n".join(_xml_text(z.read(n), ("row",), ("c", "f")) for n in names
                               if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
            return strings + "\n" + re.sub(r"\t+", "\t", re.sub(r" +", " ", inline))
    raw = path.read_bytes()[:MAX_TEXT * 2].decode("utf-8", "replace")
    if ext == ".ipynb":
        cells = json.loads(raw).get("cells", [])
        return "\n\n".join("".join(c.get("source", "")) for c in cells)
    if ext in (".html", ".htm"):
        return _html_text(raw)
    return raw


# -- the library ----------------------------------------------------------------------------------
def copy_name(rel: str) -> str:
    """Where a file lives in the copy: the same path, except Google stubs, which are stored exported
    ("Draft Email.gdoc" -> "Draft Email.gdoc.docx") so they open in Word, Excel or PowerPoint."""
    ext = Path(rel).suffix.lower()
    return rel + NATIVE[ext][2] if ext in NATIVE else rel


class SourceLibrary:
    def __init__(self, root: Path, specs: list[SourceSpec], index_path: Path, drive: GoogleDrive | None = None):
        self.drive = drive
        self.root, self.specs = Path(root), {s.name: s for s in specs}
        self.root.mkdir(parents=True, exist_ok=True)
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(index_path, check_same_thread=False)
        self.lock = threading.RLock()
        self.syncing: str | None = None
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, source TEXT, rel TEXT, size INTEGER, mtime REAL,
            status TEXT, reason TEXT, chars INTEGER, UNIQUE(source, rel));
          CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, path, body, tokenize='porter unicode61 remove_diacritics 2');
          CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, source TEXT, started REAL, finished REAL, stats TEXT);
          CREATE TABLE IF NOT EXISTS meta(source TEXT PRIMARY KEY, extract_version INTEGER);
        """)

    # -- selection -------------------------------------------------------------------------------
    def plan(self, spec: SourceSpec) -> tuple[list[tuple[Path, str]], list[tuple[str, str]]]:
        """-> (files to copy as (original, relative path), skipped as (relative path, reason))."""
        if spec.api:
            return self._plan_api(spec)
        take, skipped = [], []
        google = spec.google and self.drive is not None and self.drive.connected
        roots = [spec.path / i for i in spec.include] if spec.include else [spec.path]
        excl = [e.replace("\\", "/").strip("/").lower() for e in spec.exclude]
        for top in roots:
            if not top.exists():
                skipped.append((str(top.relative_to(spec.path)).replace("\\", "/"), "folder not found"))
                continue
            for dp, dns, fns in os.walk(top):
                dns[:] = sorted(d for d in dns if not d.startswith((".", "$", "~")) and d != "node_modules")
                for f in sorted(fns):
                    p = Path(dp) / f
                    rel = p.relative_to(spec.path).as_posix()
                    low, ext = rel.lower(), p.suffix.lower()
                    if any(low == e or low.startswith(e + "/") for e in excl):
                        continue                                   # excluded by the user: not even listed
                    if f.startswith((".", "~$")):
                        continue
                    if PRIVATE_NAME.search(rel):
                        skipped.append((rel, "looks private by its name"))
                    elif ext in NATIVE and google:
                        take.append((p, rel))                     # exported through the Drive API in sync
                    elif ext in NATIVE and spec.google:
                        skipped.append((rel, "Google file: connect Google Drive in Sources to include it"))
                    elif ext in SKIP_REASONS:
                        skipped.append((rel, SKIP_REASONS[ext]))
                    elif ext not in TEXT | RICH:
                        skipped.append((rel, f"unsupported type ({ext or 'no extension'})"))
                    else:
                        try:
                            limit = MAX_BOOK if ext in (".pdf", ".epub") else MAX_FILE
                            if p.stat().st_size > limit:
                                skipped.append((rel, f"larger than {limit // 2**20} MB"))
                                continue
                        except OSError:
                            skipped.append((rel, "can't be read"))
                            continue
                        take.append((p, rel))
        return take, skipped

    def _plan_api(self, spec: SourceSpec) -> tuple[list, list[tuple[str, str]]]:
        """The same selection rules as a local folder, over a Drive folder listed through the API."""
        take, skipped = [], []
        if self.drive is None or not self.drive.connected:
            return [], [("", "connect Google Drive in Sources to read this source")]
        excl = [e.replace("\\", "/").strip("/").lower() for e in spec.exclude]
        root = spec.path.as_posix()
        for inc in spec.include or [""]:
            inc = inc.replace("\\", "/").strip("/")
            try:
                files = self.drive.walk(self.drive.folder_id(f"{root}/{inc}" if inc else root), f"{inc}/" if inc else "")
            except DriveError as exc:
                skipped.append((inc, f"Drive folder not read: {exc}"))
                continue
            for f in files:
                rel, low = f["rel"], f["rel"].lower()
                ext = Path(rel).suffix.lower()
                name = rel.rsplit("/", 1)[-1]
                if any(low == e or low.startswith(e + "/") for e in excl) or name.startswith((".", "~$")):
                    continue
                if PRIVATE_NAME.search(rel):
                    skipped.append((rel, "looks private by its name"))
                elif ext in SKIP_REASONS and ext not in NATIVE:
                    skipped.append((rel, SKIP_REASONS[ext]))
                elif ext not in TEXT | RICH and ext not in NATIVE:
                    skipped.append((rel, f"unsupported type ({ext or 'no extension'})"))
                elif f["size"] > (MAX_BOOK if ext in (".pdf", ".epub") else MAX_FILE):
                    skipped.append((rel, "too large"))
                else:
                    take.append((RemoteFile(f["id"], f["mimeType"], f["size"], f["mtime"], ext), rel))
        return take, skipped

    # -- sync --------------------------------------------------------------------------------------
    def sync(self, name: str, progress=None) -> dict:
        """Copy new and changed files, drop copies no longer selected, re-extract changed text."""
        spec = self.specs[name]
        dest = self.root / name
        started = time.time()
        take, skipped = self.plan(spec)
        if self.drive:
            self.drive.begin_sync()
        stats = {"copied": 0, "unchanged": 0, "removed": 0, "indexed": 0, "private_content": 0, "errors": 0}
        with self.lock:
            self.syncing = name
            have = {rel: (fid, size, mtime) for fid, rel, size, mtime in
                    self.db.execute("SELECT id, rel, size, mtime FROM files WHERE source=? AND status != 'skipped'", (name,))}
            row = self.db.execute("SELECT extract_version FROM meta WHERE source=?", (name,)).fetchone()
            stale = (row[0] if row else None) != EXTRACT_VERSION    # extraction changed: re-read every file
        try:
            keep = set()
            for i, (src, rel) in enumerate(take):
                if progress and i % 25 == 0:
                    progress(name, i, len(take))
                try:
                    st = src.stat()
                    old = have.get(rel)
                    target = src if not spec.copy else dest / copy_name(rel)
                    if not stale and old and old[1] == st.st_size and old[2] == st.st_mtime and target.exists():
                        stats["unchanged"] += 1
                        keep.add(rel)
                        continue
                    if spec.copy:
                        target.parent.mkdir(parents=True, exist_ok=True)
                    if not spec.copy:
                        pass                                       # indexed where it is
                    elif isinstance(src, RemoteFile) and src.suffix not in NATIVE:      # a file in Drive: download it
                        try:
                            self.drive.download(src.id, target, MAX_BOOK if src.suffix in (".pdf", ".epub") else MAX_FILE)
                        except DriveError as exc:
                            stats["errors"] += 1
                            if old:
                                keep.add(rel)
                            else:
                                skipped.append((rel, f"not downloaded from Drive: {exc}"))
                            continue
                    elif src.suffix.lower() in NATIVE:             # Google file: export it (Drive is only read)
                        try:
                            fid = src.id if isinstance(src, RemoteFile) else self.drive.resolve(rel)["id"]
                            data = self.drive.export(fid, src.suffix.lower())
                        except DriveError as exc:
                            stats["errors"] += 1
                            if old:
                                keep.add(rel)                      # keep the last good copy (its row stays indexed)
                            else:
                                skipped.append((rel, f"Google file not exported: {exc}"))
                            continue
                        target.write_bytes(data)
                        stats["google"] = stats.get("google", 0) + 1
                    else:
                        shutil.copy2(src, target)                  # reads the original; never writes it
                    try:
                        text = extract_text(target)[:MAX_TEXT]
                    except Exception as exc:                     # noqa: BLE001 -- a bad file never stops a sync
                        text, status, reason = "", "copied", f"text not readable ({type(exc).__name__})"
                    else:
                        status, reason = "indexed", None
                    category = screen(text) if text else None
                    if category:                                 # K4: private content never stays in the copy
                        if spec.copy:                            # (a file indexed in place is the user's: left alone)
                            target.unlink(missing_ok=True)
                        skipped.append((rel, f"looks like it contains {category}"))
                        stats["private_content"] += 1
                        self._forget(name, rel)
                        continue
                    self._store(name, rel, st, status, reason, text)
                    stats["copied"] += 1
                    stats["indexed"] += status == "indexed"
                    keep.add(rel)
                except OSError as exc:
                    skipped.append((rel, f"copy failed ({exc.strerror or type(exc).__name__})"))
                    stats["errors"] += 1
            for rel in set(have) - keep:                         # deselected, deleted on Drive, or now private
                if spec.copy:
                    (dest / copy_name(rel)).unlink(missing_ok=True)
                self._forget(name, rel)
                stats["removed"] += 1
            if spec.copy:
                self._prune_dirs(dest)
            stats["skipped"] = len(skipped)
            with self.lock:
                self.db.execute("DELETE FROM files WHERE source=? AND status='skipped'", (name,))
                self.db.executemany("INSERT OR REPLACE INTO files(source, rel, status, reason) VALUES (?,?, 'skipped', ?)",
                                    [(name, rel, reason) for rel, reason in skipped])
                self.db.execute("INSERT INTO runs(source, started, finished, stats) VALUES (?,?,?,?)",
                                (name, started, time.time(), json.dumps(stats)))
                self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (name, EXTRACT_VERSION))
                self.db.commit()
        finally:
            self.syncing = None
        return stats | {"seconds": round(time.time() - started, 1)}

    def _store(self, name, rel, st, status, reason, text):
        with self.lock:
            self._forget(name, rel, commit=False)
            fid = self.db.execute("INSERT INTO files(source, rel, size, mtime, status, reason, chars) VALUES (?,?,?,?,?,?,?)",
                                  (name, rel, st.st_size, st.st_mtime, status, reason, len(text))).lastrowid
            self.db.execute("INSERT INTO fts(rowid, title, path, body) VALUES (?,?,?,?)",
                            (fid, Path(rel).stem.replace("_", " ").replace("-", " "), rel, text))
            self.db.commit()

    def _forget(self, name, rel, commit=True):
        with self.lock:
            row = self.db.execute("SELECT id FROM files WHERE source=? AND rel=?", (name, rel)).fetchone()
            if row:
                self.db.execute("DELETE FROM fts WHERE rowid=?", (row[0],))
                self.db.execute("DELETE FROM files WHERE id=?", (row[0],))
            if commit:
                self.db.commit()

    @staticmethod
    def _prune_dirs(dest: Path):
        if not dest.exists():
            return
        for dp, _, _ in sorted(os.walk(dest), key=lambda t: -len(t[0])):
            if Path(dp) != dest and not any(Path(dp).iterdir()):
                Path(dp).rmdir()

    # -- reading -----------------------------------------------------------------------------------
    def files(self, name: str) -> list[tuple[str, str]]:
        """(relative path, status) of every file the library knows for a source."""
        with self.lock:
            return self.db.execute("SELECT rel, status FROM files WHERE source=? ORDER BY rel", (name,)).fetchall()

    def summary(self) -> dict:
        with self.lock:
            out = []
            for name, spec in self.specs.items():
                counts = dict(self.db.execute("SELECT status, COUNT(*) FROM files WHERE source=? GROUP BY status", (name,)).fetchall())
                last = self.db.execute("SELECT finished, stats FROM runs WHERE source=? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
                skipped = self.db.execute("SELECT rel, reason FROM files WHERE source=? AND status='skipped' ORDER BY rel", (name,)).fetchall()
                out.append({"name": name, "path": str(spec.path), "copy": str(self.root / name),
                            "in_place": not spec.copy, "include": spec.include, "files": counts.get("indexed", 0) + counts.get("copied", 0),
                            "indexed": counts.get("indexed", 0), "last_sync": last[0] if last else None,
                            "last_stats": json.loads(last[1]) if last else None,
                            "skipped": [{"path": r, "reason": why} for r, why in skipped],
                            "syncing": self.syncing == name, "google": spec.google})
            return {"sources": out, "google": self.drive.status() if self.drive else None}

    def search(self, text: str, limit: int = 20) -> dict:
        return self._search(text, fts_query(text), limit)

    def doc_freq(self, term: str) -> tuple[int, int]:
        """-> (documents containing the term or a word starting with it, all indexed documents)."""
        q = fts_query(term)
        with self.lock:
            n = self.db.execute("SELECT COUNT(*) FROM fts WHERE fts MATCH ?", (q,)).fetchone()[0] if q else 0
            return n, self.db.execute("SELECT COUNT(*) FROM fts").fetchone()[0]

    def search_raw(self, query: str, limit: int = 20) -> list[dict]:
        """An FTS5 query built by the caller (briefing packs use OR across key terms)."""
        return self._search(query, query, limit)["results"]

    def _search(self, text: str, q: str | None, limit: int) -> dict:
        t0 = time.perf_counter()
        rows = []
        if q:
            with self.lock:
                rows = self.db.execute("""
                  SELECT f.source, f.rel, snippet(fts, 2, ?, ?, '…', 16), bm25(fts, 6.0, 3.0, 1.0)
                  FROM fts JOIN files f ON f.id = fts.rowid WHERE fts MATCH ? ORDER BY 4 LIMIT ?""",
                                       (HIT_START, HIT_END, q, max(1, min(limit, 50)))).fetchall()
        return {"q": text, "ms": round((time.perf_counter() - t0) * 1000, 1),
                "results": [{"source": s, "path": r, "title": Path(r).name, "snippet": sn, "score": round(-sc, 3)}
                            for s, r, sn, sc in rows]}

    def file_path(self, source: str, rel: str) -> Path:
        """Where a library file is on disk: its copy, or the original for a source indexed in place."""
        spec = self.specs[source]
        return (spec.path / rel) if not spec.copy else self.root / source / copy_name(rel)

    def folder(self, source: str) -> Path:
        spec = self.specs[source]
        return spec.path if not spec.copy else self.root / source

    def full_text(self, source: str, rel: str) -> str | None:
        """A document's whole extracted text (read() pages it out 50,000 characters at a time)."""
        with self.lock:
            row = self.db.execute("SELECT fts.body FROM files f JOIN fts ON fts.rowid = f.id WHERE f.source=? AND f.rel=?",
                                  (source, rel)).fetchone()
        return row[0] if row else None

    def read(self, source: str, rel: str, offset: int = 0, limit: int = 20_000) -> dict | None:
        with self.lock:
            row = self.db.execute("SELECT f.id, f.size, f.status, f.reason, fts.body FROM files f JOIN fts ON fts.rowid = f.id "
                                  "WHERE f.source=? AND f.rel=?", (source, rel)).fetchone()
        if row is None:
            return None
        _, size, status, reason, body = row
        offset, limit = max(0, int(offset)), max(1, min(int(limit), 50_000))
        return {"source": source, "path": rel, "size": size, "status": status, "note": reason,
                "chars": len(body), "offset": offset, "text": body[offset:offset + limit],
                "more": offset + limit < len(body)}

    def close(self):
        with self.lock:
            self.db.close()
