"""Notes from sources (K6, DECISIONS D17): a vault starts from whatever the user has provided.

Two layers, both ending in the inbox as proposals (I1):
  1. Starter notes, deterministic, no model: markdown files in a source are imported as notes (the
     user's own text, structure kept), and every folder of documents gets a *collection* note that
     lists its documents with their headings / slide titles, frequent terms, and source paths.
     Nothing is summarised or invented (I7 intent): it's an index the user can trust.
  2. Concept notes, on request: an agent reads a collection through read_source and proposes notes
     that cite their source documents (see Hub.draft_notes).

Every note records `source:` (a vault-relative path under sources/), which makes re-runs idempotent:
anything already in the vault or waiting in the inbox is skipped.
"""
from __future__ import annotations

import collections
import math
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .proposals import IMPORTER, ProposalError, normalize, plan
from .screen import screen
from .sources import SourceLibrary, SourceSpec
from .vault import Vault, split_frontmatter

MIN_COLLECTION = 3                     # smaller folders roll up into the nearest larger one
MAX_LISTED = 150                       # documents listed in one collection note
STOP = set("""the and for that with this from are was were have has had not but you your our their they them can will
would should could into than then there these those what when where which while who whom why how all any each about
also been being both does doing done more most other some such only own same very just over under after before above
below between again further here once because until upon within without across among page pages slide slides figure table
true false null public private static void class return import package string int double new else https http www com
html pdf docx xlsx pptx question questions homework answer answers equal points chapter problem problems exam quiz
name write yeah gonna wanna kinda okay like really actually something everybody somebody anybody webvtt
thing things stuff""".split())


@dataclass
class Collection:
    dir: str                                    # folder in the source ("" = the source root)
    docs: list[str] = field(default_factory=list)
    markdown: list[str] = field(default_factory=list)
    root_title: str = "Sources"                 # what the source root is called (its notes folder)

    @property
    def title(self) -> str:
        return PurePosixPath(self.dir).name or self.root_title


def _parent(rel: str) -> str:
    """Folder of a source file, "" for the root; a trailing /src (code projects) counts as its parent."""
    d = str(PurePosixPath(rel).parent)
    return "" if d == "." else re.sub(r"/src$", "", d)


def source_path(name: str, rel: str) -> str:
    """How notes cite a source file or folder: vault-relative, e.g. sources/drive/My Drive/x.pdf."""
    return f"sources/{name}/{rel}".rstrip("/")


def _clean_part(part: str) -> str:
    part = re.sub(r'[<>:"|?*\\]', "-", part).strip(" .")
    return part or "untitled"


class NoteBuilder:
    def __init__(self, vault: Vault, sources: SourceLibrary):
        self.vault, self.sources = vault, sources
        self._source_df: dict[str, tuple] = {}      # per source: word -> number of documents (for _terms)
        self._words_cache: dict[tuple, set] = {}     # (source, file) -> its words, for one build

    # -- where things go -----------------------------------------------------------------------
    def vault_folder(self, spec: SourceSpec, source_dir: str) -> str:
        rel = source_dir
        for prefix in spec.strip:
            if rel == prefix or rel.startswith(prefix + "/"):
                rel = rel[len(prefix):].lstrip("/")
                break
        parts = [spec.notes_folder or spec.name.title()] + [_clean_part(p) for p in rel.split("/") if p]
        return "/".join(parts)

    # -- what's there ----------------------------------------------------------------------------
    def collections(self, name: str) -> list[Collection]:
        """Group the source's indexed files into collections; tiny folders roll up into their parent."""
        files = [rel for rel, status in self.sources.files(name) if status in ("indexed", "copied")]
        files = [f for f in files if not re.search(r"\.app/|/node_modules/|/__MACOSX/", f)]
        folder_of = {f: _parent(f) for f in files}
        counts = collections.Counter(d for f, d in folder_of.items() if not f.lower().endswith(".md"))
        big = {d for d, n in counts.items() if n >= MIN_COLLECTION}

        def home(d: str) -> str:
            while d and d not in big:
                d = str(PurePosixPath(d).parent)
                d = "" if d == "." else d
            return d                             # "" = the source root collects whatever is left
        out: dict[str, Collection] = {}
        for f, d in sorted(folder_of.items()):
            h = home(d)
            c = out.setdefault(h, Collection(h, root_title=self.sources.specs[name].notes_folder or name.title()))
            (c.markdown if f.lower().endswith(".md") else c.docs).append(f)
        return sorted(out.values(), key=lambda c: c.dir)

    def built_sources(self) -> set[str]:
        """`source:` paths of notes already in the vault (pending proposals are the caller's to add)."""
        return {n.source for n in self.vault.scan() if n.source}

    def candidates(self, name: str, c: Collection) -> list[str]:
        """Source paths a collection turns into notes: its collection note (if it has documents) and
        each markdown file."""
        return ([source_path(name, c.dir)] if c.docs else []) + [source_path(name, rel) for rel in c.markdown]

    # -- starter notes -----------------------------------------------------------------------------
    def _excerpt(self, name: str, rel: str) -> str:
        doc = self.sources.read(name, rel, 0, 6000) or {}
        text = doc.get("text", "")
        if rel.lower().endswith(".pptx"):
            titles = []
            for block in re.split(r"\[slide \d+\]", text)[1:]:
                line = next((ln.strip() for ln in block.splitlines() if ln.strip()), "")
                if line and line not in titles:
                    titles.append(line[:80])
                if len(titles) == 6:
                    break
            return "slides: " + "; ".join(titles) if titles else ""
        lines = []
        for ln in text.splitlines():
            had_blanks = "___" in ln
            ln = re.sub(r"\s+", " ", re.sub(r"_{3,}", " ", ln)).strip(" :/-")
            # fill-in form headers ("Name ____ School ID ____") say nothing about the document
            if len(ln) > 3 and re.search(r"[A-Za-z]{3}", ln) and not (had_blanks and len(ln.split()) <= 4):
                lines.append(ln)
        return " / ".join(ln[:120] for ln in lines[:2])

    def _words(self, name: str, rel: str) -> set[str]:
        key = (name, rel)
        if key not in self._words_cache:
            doc = self.sources.read(name, rel, 0, 50_000) or {}
            self._words_cache[key] = self._tokens(doc.get("text", ""))
        return self._words_cache[key]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z]{2,}(?:-[a-z]{2,})*", text.lower()) if len(w) >= 4 and w not in STOP}

    def _terms(self, name: str, docs: list[str]) -> list[str]:
        """Words distinctive to this collection: frequent here, rare across the whole source (tf-idf on
        document counts), so a finance folder surfaces "wacc", not "question"."""
        if name not in self._source_df:
            df, n = collections.Counter(), 0
            for rel, status in self.sources.files(name):
                if status == "indexed":
                    df.update(self._words(name, rel))
                    n += 1
            self._source_df[name] = (df, max(n, 1))
        source_df, n_docs = self._source_df[name]
        here = collections.Counter()
        for rel in docs[:60]:
            here.update(self._words(name, rel))
        floor = 2 if len(docs) > 1 else 1
        score = {w: c * math.log(n_docs / source_df.get(w, 1)) for w, c in here.items()
                 if c >= floor and source_df.get(w, 1) <= n_docs / 2}
        return [w for w, _ in sorted(score.items(), key=lambda x: (-x[1], x[0]))[:15]]

    def collection_note(self, spec: SourceSpec, c: Collection) -> dict:
        where = c.dir or "(source root)"
        lines = [f"Documents in `{where}` from your **{spec.name}** source. Each line shows how a document starts; "
                 "nothing here is summarised. Open a document in Bookshelf → Sources to read it.",
                 "", f"## Documents ({len(c.docs)})", ""]
        for rel in c.docs[:MAX_LISTED]:
            sub = str(PurePosixPath(rel).relative_to(c.dir)) if c.dir else rel
            ex = self._excerpt(spec.name, rel)
            lines.append(f"- **{sub}**" + (f" · {ex}" if ex else ""))
            lines.append(f"  `sources/{spec.name}/{rel}`")
        if len(c.docs) > MAX_LISTED:
            lines.append(f"- … and {len(c.docs) - MAX_LISTED} more (search them in Bookshelf → Sources)")
        terms = self._terms(spec.name, c.docs)
        if terms:
            lines += ["", "## Distinctive terms", "", " · ".join(terms)]
        return {"op": "create", "folder": self.vault_folder(spec, c.dir), "title": c.title, "type": "collection",
                "status": "active", "tags": ["collection", spec.name], "source": source_path(spec.name, c.dir),
                "body": "\n".join(lines) + "\n", "origin": "agent"}

    def markdown_note(self, spec: SourceSpec, rel: str) -> dict:
        doc = self.sources.read(spec.name, rel, 0, 200_000) or {}
        fm, body, _ = split_frontmatter(doc.get("text", ""))
        fm = fm or {}
        heading = next((ln[2:].strip() for ln in body.splitlines() if ln.startswith("# ")), None)
        title = str(fm.get("title") or heading or PurePosixPath(rel).stem).replace("\n", " ")[:200]
        tags = [str(t)[:80] for t in (fm.get("tags") or []) if isinstance(t, (str, int))][:50] if isinstance(fm.get("tags"), list) else []
        parent = str(PurePosixPath(rel).parent)
        change = {"op": "create", "folder": self.vault_folder(spec, "" if parent == "." else parent),
                  "title": title, "type": str(fm.get("type") or "note")[:80], "status": "active",
                  "source": source_path(spec.name, rel), "body": body if body.strip() else f"(empty file `{rel}`)\n",
                  "origin": "imported"}
        if tags:
            change["tags"] = tags
        return change

    def starter_plan(self, name: str, pending_sources: set[str] = frozenset()) -> dict:
        """-> {"proposals": [{"collection", "summary", "changes"}], "already": n, "left_out": [{path, reason}]}."""
        spec = self.sources.specs[name]
        self._source_df.pop(name, None)              # recount: the source may have been re-synced
        self._words_cache.clear()
        notes = self.vault.scan()                    # one scan for validating every candidate
        done = self.built_sources() | set(pending_sources)
        groups: dict[str, dict] = {}            # one inbox card per area (two folder levels below the notes folder)
        left_out, already = [], 0
        for c in self.collections(name):
            changes = []
            candidates = ([("collection", c.dir, lambda c=c: self.collection_note(spec, c))] if c.docs else []) + \
                         [("markdown", rel, lambda rel=rel: self.markdown_note(spec, rel)) for rel in c.markdown]
            for kind, rel, make in candidates:
                src = source_path(name, rel)
                if src in done:
                    already += 1
                    continue
                change = make()
                bad = next((screen(str(change.get(k, ""))) for k in ("title", "body") if screen(str(change.get(k, "")))), None)
                if bad:
                    left_out.append({"path": rel, "reason": f"looks like it contains {bad}"})
                    continue
                try:
                    plan(self.vault, normalize([change]), IMPORTER, notes=notes)
                except ProposalError as exc:
                    left_out.append({"path": rel, "reason": str(exc)})
                    continue
                changes.append(change)
            if changes:
                area = "/".join(self.vault_folder(spec, c.dir).split("/")[:3])
                g = groups.setdefault(area, {"collection": c.dir, "titles": [], "changes": []})
                g["titles"].append(c.title)
                g["changes"] += changes
        proposals = []
        for area, g in groups.items():
            for i in range(0, len(g["changes"]), 50):
                chunk = g["changes"][i:i + 50]
                n_col = sum(ch.get("type") == "collection" for ch in chunk)
                n_md = sum(ch.get("origin") == "imported" for ch in chunk)
                what = ([f"{n_col} collection note{'s' if n_col != 1 else ''}"] if n_col else []) + \
                       ([f"{n_md} markdown note{'s' if n_md != 1 else ''}"] if n_md else [])
                names = ", ".join(g["titles"][:6]) + (f" and {len(g['titles']) - 6} more" if len(g["titles"]) > 6 else "")
                proposals.append({"collection": g["collection"], "changes": chunk,
                                  "summary": f"Starter notes for {area}: {' + '.join(what)} ({names}) from your {name} source"})
        return {"proposals": proposals, "already": already, "left_out": left_out}
