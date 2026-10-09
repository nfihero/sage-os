"""Splitting a long document into chapters and sections (K12, DECISIONS D23).

The rule that makes "nothing missed" checkable: the sections **tile** the document's text. Every character
belongs to exactly one section, in order, with no gaps or overlaps, so a section that has notes plus a
section that doesn't adds up to the whole book.

Where the structure comes from, best first:
  1. A PDF's bookmarks (its outline), mapped to the pages they point at.
  2. Headings in the text: markdown `#` lines (Word, EPUB and HTML headings are written that way during
     extraction), "Chapter 3", "Part II", "3.2 Present value", short ALL-CAPS lines.
  3. Nothing usable: paragraph-boundary chunks of a steady size.
Then tiny sections are merged into a neighbour and oversized ones split at paragraph boundaries, so each
piece fits comfortably in a small local model's context.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

TARGET = 9_000          # characters per section a small model handles well (~2,300 tokens)
MAX = 12_000            # split above this
MIN = 1_500             # merge below this
CHAPTER_SECTIONS = 8    # with no chapter-level structure, group this many sections per chapter
CHAPTER_MIN = 6_000     # a heading level is the chapter level only if its parts average this much text


@dataclass
class Section:
    idx: int
    chapter: str                 # top-level part this section belongs to (one inbox card per chapter)
    title: str
    start: int                   # character offsets into the document's text: [start, end)
    end: int
    pages: list[int] = field(default_factory=list)   # [first, last], 1-based, when known
    level: int = 1

    def public(self) -> dict:
        return asdict(self)


# -- headings in plain text ---------------------------------------------------------------------------
MD = re.compile(r"^(#{1,3})\s+(\S.{0,118})$")
CHAPTER = re.compile(r"^(chapter|part|unit|module|lecture|section|appendix)\s+([0-9]+|[ivxlc]+|[a-z])\b[.:\-–— ]*(.{0,100})$", re.I)
NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+([A-Z][^.!?]{2,90})$")


def heading(line: str) -> tuple[int, str] | None:
    """(level, title) if a line looks like a heading, else None. Level 1 = chapter."""
    s = line.strip()
    if not s or len(s) > 120:
        return None
    if m := MD.match(s):
        return len(m.group(1)), m.group(2).strip()
    if m := CHAPTER.match(s):
        return 1, s.rstrip(" .:")
    if m := NUMBERED.match(s):
        return min(3, m.group(1).count(".") + 1), s
    words = s.split()
    if 2 <= len(words) <= 8 and s.isupper() and sum(c.isalpha() for c in s) >= 6 and not s.endswith((".", ",")):
        return 2, s.title()
    return None


def text_markers(text: str) -> list[tuple[int, int, str]]:
    """(offset, level, title) for each heading line in text."""
    out, pos = [], 0
    for line in text.splitlines(keepends=True):
        h = heading(line)
        if h:
            out.append((pos, h[0], h[1]))
        pos += len(line)
    return out


# -- PDFs -------------------------------------------------------------------------------------------
def pdf_pages(path: Path) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError("encrypted PDF")
    return [(p.extract_text() or "") for p in reader.pages]


def pdf_outline(path: Path) -> list[tuple[int, int, str]]:
    """(page index, level, title) of a PDF's bookmarks, in reading order."""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    out = []

    def walk(items, level):
        for it in items:
            if isinstance(it, list):
                walk(it, level + 1)
                continue
            try:
                page = reader.get_destination_page_number(it)
            except Exception:                    # noqa: BLE001 -- a broken bookmark is skipped, not fatal
                continue
            title = str(getattr(it, "title", "") or "").strip()
            if title and page is not None and page >= 0:
                out.append((page, level, title[:120]))
    try:
        walk(reader.outline, 1)
    except Exception:                            # noqa: BLE001
        return []
    out.sort(key=lambda x: (x[0], x[1]))
    return out


# -- building the tiling -------------------------------------------------------------------------------
def _cut(text: str, start: int, end: int, size: int) -> list[int]:
    """Break points (exclusive ends) splitting [start, end) into pieces of about `size`, at paragraph or
    line boundaries when possible."""
    cuts, pos = [], start
    while end - pos > size * 1.3:
        target = pos + size
        window = text[target - size // 3: target + size // 3]
        para = window.rfind("\n\n")
        line = window.rfind("\n")
        brk = para if para > 0 else line if line > 0 else size // 3
        pos = target - size // 3 + brk + 1
        cuts.append(pos)
    cuts.append(end)
    return cuts


def tile(text: str, markers: list[tuple[int, int, str]], fallback_title: str) -> list[Section]:
    """Sections covering all of `text` from heading markers (offset, level, title)."""
    markers = sorted({m[0]: m for m in markers if 0 <= m[0] < len(text)}.values())
    if not markers or markers[0][0] > 0:
        markers = [(0, 1, fallback_title if not markers else "Opening")] + markers
    # Chapters are the shallowest heading level whose parts are substantial. One heading per slide, or a
    # numbered list of 30 short entries, isn't a chapter structure.
    chapter_level = None
    for lvl in sorted({m[1] for m in markers}):
        n = sum(1 for m in markers if m[1] <= lvl)
        if 2 <= n <= 80 and len(text) / n >= CHAPTER_MIN:
            chapter_level = lvl
            break
    raw, chapter = [], fallback_title
    for i, (off, level, title) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        if chapter_level is not None and level <= chapter_level:
            chapter = title
        raw.append([chapter, title, off, end, level])
    # short front matter (a title page, a copyright line) joins the first chapter instead of being its own
    if len(raw) > 1 and raw[0][1] in ("Opening", fallback_title) and raw[0][3] - raw[0][2] < MIN:
        first = raw.pop(0)
        raw[0][2] = first[2]
    # merge small neighbours in the same chapter into pieces of a useful size
    merged: list[list] = []
    for r in raw:
        if merged and merged[-1][0] == r[0]:
            prev, size = merged[-1], merged[-1][3] - merged[-1][2]
            if size < MIN or size + (r[3] - r[2]) <= TARGET * 0.6:
                first = prev[1].split(" → ")[0]
                prev[1] = first if prev[1] == r[1] else f"{first} → {r[1]}"
                prev[3], prev[4] = r[3], min(prev[4], r[4])
                continue
        merged.append(r)
    if len(merged) > 1 and merged[-1][3] - merged[-1][2] < MIN and merged[-2][0] == merged[-1][0]:
        last = merged.pop()
        merged[-1][3] = last[3]
    # split oversized pieces
    out: list[Section] = []
    for chapter, title, start, end, level in merged:
        if end - start <= MAX:
            out.append(Section(len(out), chapter, title, start, end, level=level))
            continue
        parts, pos = _cut(text, start, end, TARGET), start
        for k, stop in enumerate(parts, 1):
            out.append(Section(len(out), chapter, f"{title} (part {k} of {len(parts)})", pos, stop, level=level))
            pos = stop
    if chapter_level is None:                    # no chapter structure: group steady runs of sections
        for s in out:
            s.chapter = f"Part {s.idx // CHAPTER_SECTIONS + 1}"
    return out


def check_tiling(sections: list[Section], length: int) -> None:
    """The invariant: in order, contiguous, covering [0, length)."""
    pos = 0
    for s in sections:
        if s.start != pos or s.end <= s.start:
            raise AssertionError(f"section {s.idx} starts at {s.start}, expected {pos}")
        pos = s.end
    if pos != length:
        raise AssertionError(f"sections end at {pos}, document has {length} characters")


def split_document(copy_path: Path, text: str, title: str) -> tuple[str, list[Section]]:
    """-> (the text the sections index into, sections). For PDFs the text is rebuilt page by page so
    bookmarks can be placed exactly; otherwise it is the library's extracted text."""
    if copy_path.suffix.lower() == ".pdf":
        pages = pdf_pages(copy_path)
        offsets, buf, pos = [], [], 0
        for p in pages:
            offsets.append(pos)
            chunk = p + "\n\n"
            buf.append(chunk)
            pos += len(chunk)
        doc = "".join(buf)
        outline = pdf_outline(copy_path)
        # an outline with one bookmark per page (slide decks) or almost none says little about structure
        useful = len(outline) >= 2 and len({p for p, _, _ in outline}) > 1
        markers = [(offsets[p], lvl, t) for p, lvl, t in outline if p < len(offsets)] if useful else text_markers(doc)
        sections = tile(doc, markers, title)
        for s in sections:
            first = max(i for i, o in enumerate(offsets) if o <= s.start) + 1
            last = max(i for i, o in enumerate(offsets) if o < s.end) + 1
            s.pages = [first, last]
    else:
        doc = text
        sections = tile(doc, text_markers(doc), title)
    check_tiling(sections, len(doc))
    return doc, sections
