"""Meaning-based search (K14, DECISIONS D37): notes and source documents searched by meaning as well as words.

  * A small embedding model (EmbeddingGemma 300M) turns each note, and each passage of each source document, into
    a vector; a question is turned into one the same way, and the nearest vectors are the passages that mean the
    most similar thing, whatever words they use. It runs on the CPU in its own llama-server (engine.EmbedEngine).
  * The vectors are a cache on this computer (semantic.db, LOCAL in the sync manifest, D27.4): rebuilt from the
    Library and the source copies, never synced. Delete it and it is rebuilt.
  * Search is hybrid: keyword results (D10, FTS5) and meaning results are merged by reciprocal rank, so an exact
    term ("ASC 606") still wins and a paraphrase now finds its note. Without the model (not downloaded, still
    indexing, a game holding the computer), search is keyword-only and says so.
  * Briefing packs (K8) ask how close each candidate is to the message: wordy matches that mean something else stay
    out, and a note that answers the question in other words can come in.
  * Screened-sensitive notes (D12) are embedded by title only, as they are indexed by title only.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import sqlite3
import threading
import time
from pathlib import Path

import httpx
import numpy as np

log = logging.getLogger("sage_os.semantic")

QUERY = "task: search result | query: {}"          # EmbeddingGemma's prompts for retrieval
DOC = "title: {} | text: {}"
NOTE_CHARS = 2000            # a note is embedded from its title, tags and first 2,000 characters
CHUNK, OVERLAP = 1200, 150   # source documents are embedded in overlapping passages
MAX_CHUNKS = 4000            # per document (about 4.8 million characters)
BATCH = 16                   # texts per request
RRF_K = 60                   # reciprocal-rank fusion constant
# Calibrated on the owner's library (12 Oct 2026, D37): right answers scored 0.31-0.77 (median 0.50) against their
# question; the best match for questions the library can't answer scored at most 0.35.
SEM_MIN = 0.30               # a search hit found only by meaning must be at least this close (near misses are harmless)
PACK_MIN = 0.40              # a briefing-pack candidate found by its words must be at least this close in meaning
PACK_STRONG = 0.45           # ... and one found only by meaning, at least this close


def _hash(*parts) -> str:
    return hashlib.sha1("\x1f".join(str(p) for p in parts).encode("utf-8", "surrogateescape")).hexdigest()


def chunks(text: str) -> list[tuple[int, str]]:
    """Overlapping passages of a document, broken at a paragraph or sentence where one is near. -> (offset, text)"""
    out, start, n = [], 0, len(text)
    while start < n and len(out) < MAX_CHUNKS:
        end = min(n, start + CHUNK)
        if end < n:
            cut = max(text.rfind("\n\n", start + CHUNK // 2, end), text.rfind(". ", start + CHUNK // 2, end))
            end = cut + 1 if cut > 0 else end
        piece = text[start:end].strip()
        if piece:
            out.append((start, piece))
        if end >= n:
            break
        start = max(end - OVERLAP, start + 1)
    return out


def lean(query: str) -> float:
    """Short queries are usually exact terms ("LIFO reserve"): words and meaning count the same. A question written
    as a sentence matches filler words by keyword, so meaning counts double."""
    return 2.0 if len(re.findall(r"\w+", query)) >= 4 else 1.0


def preview(text: str, n: int = 220) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"[#*_`>|]+", " ", text or "")).strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


class VectorStore:
    """The vectors and what they belong to, with an in-memory matrix per kind for brute-force nearest neighbours
    (a few thousand notes and tens of thousands of passages: milliseconds with numpy)."""

    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript("""
              CREATE TABLE IF NOT EXISTS vecs(kind TEXT NOT NULL, ref TEXT NOT NULL, chunk INTEGER NOT NULL,
                title TEXT, folder TEXT, path TEXT, archived INTEGER NOT NULL DEFAULT 0, hash TEXT NOT NULL,
                preview TEXT, vec BLOB NOT NULL, PRIMARY KEY(kind, ref, chunk));
              CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            """)
            self.db.commit()
        self._cache: dict[str, tuple[np.ndarray, list[dict]]] = {}

    def model(self) -> str | None:
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key='model'").fetchone()
        return row[0] if row else None

    def set_model(self, model: str) -> None:
        """A different model's vectors can't be compared with this one's: start over."""
        if self.model() == model:
            return
        with self.lock:
            self.db.execute("DELETE FROM vecs")
            self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('model', ?)", (model,))
            self.db.commit()
            self._cache.clear()

    def hashes(self, kind: str) -> dict[str, str]:
        """ref -> hash of what was embedded (a document's hash is on every one of its passages)."""
        with self.lock:
            return dict(self.db.execute("SELECT ref, hash FROM vecs WHERE kind=? GROUP BY ref", (kind,)).fetchall())

    def put(self, kind: str, ref: str, rows: list[dict], vecs: np.ndarray) -> None:
        with self.lock:
            self.db.execute("DELETE FROM vecs WHERE kind=? AND ref=?", (kind, ref))
            self.db.executemany(
                "INSERT INTO vecs(kind, ref, chunk, title, folder, path, archived, hash, preview, vec) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(kind, ref, r["chunk"], r.get("title"), r.get("folder"), r.get("path"), int(r.get("archived", False)),
                  r["hash"], r.get("preview"), np.asarray(v, dtype=np.float32).tobytes()) for r, v in zip(rows, vecs)])
            self.db.commit()
            self._cache.pop(kind, None)

    def delete(self, kind: str, refs: list[str]) -> None:
        if not refs:
            return
        with self.lock:
            self.db.executemany("DELETE FROM vecs WHERE kind=? AND ref=?", [(kind, r) for r in refs])
            self.db.commit()
            self._cache.pop(kind, None)

    def count(self, kind: str) -> int:
        with self.lock:
            return self.db.execute("SELECT COUNT(DISTINCT ref) FROM vecs WHERE kind=?", (kind,)).fetchone()[0]

    def _matrix(self, kind: str) -> tuple[np.ndarray, list[dict]]:
        with self.lock:
            if kind not in self._cache:
                rows = self.db.execute("SELECT ref, chunk, title, folder, path, archived, preview, vec FROM vecs "
                                       "WHERE kind=? ORDER BY ref, chunk", (kind,)).fetchall()
                meta = [{"ref": r, "chunk": c, "title": t, "folder": f, "path": p, "archived": bool(a), "preview": pv}
                        for r, c, t, f, p, a, pv, _ in rows]
                m = (np.frombuffer(b"".join(row[7] for row in rows), dtype=np.float32).reshape(len(rows), -1)
                     if rows else np.zeros((0, 1), dtype=np.float32))
                self._cache[kind] = (m, meta)
            return self._cache[kind]

    def nearest(self, kind: str, q: np.ndarray, k: int = 30, archived: bool = False,
                only: set[str] | None = None) -> list[tuple[float, dict]]:
        """The k closest items (best passage per document), best first. -> (cosine, meta)"""
        m, meta = self._matrix(kind)
        if not len(meta):
            return []
        sims = m @ q
        best: dict[str, tuple[float, dict]] = {}
        for i in np.argsort(-sims):
            it = meta[i]
            if (it["archived"] and not archived) or (only is not None and it["ref"] not in only) or it["ref"] in best:
                continue
            best[it["ref"]] = (float(sims[i]), it)
            if only is None and len(best) >= k:
                break
        return sorted(best.values(), key=lambda x: -x[0])[:k] if only is None else list(best.values())

    def close(self):
        with self.lock:
            self.db.close()


class Semantic:
    """The embedding server, the vector store and the background indexer, plus the hybrid search everyone uses."""

    def __init__(self, hub, path: Path, engine):
        self.hub, self.engine = hub, engine           # engine: EmbedEngine, or None where embeddings are off
        self.store = VectorStore(path)
        self.wake = asyncio.Event()
        self.state: dict = {"state": "off"}
        self._last_publish = 0.0
        self._seen: dict[str, tuple] = {}            # note ref -> (path, mtime, size, archived) when last hashed

    # -- status ---------------------------------------------------------------------------------------
    @property
    def ready(self) -> bool:
        """Queries can be answered by meaning (the server is up; the index may still be filling)."""
        e = self.engine
        return bool(e and e.serving and e.serving.get("ready") and self.store.count("note"))

    def status(self) -> dict:
        e = self.engine
        job = e.jobs.get("model:embed") if e else None
        return {**self.state, "installed": bool(e and e.installed()), "download": job.public() if job else None,
                "notes": self.store.count("note"), "documents": self.store.count("source"),
                "model": "EmbeddingGemma 300M", "size": 333590944}

    def publish(self, force: bool = False):
        now = time.time()
        if force or now - self._last_publish > 1.5:
            self._last_publish = now
            self.hub.panel("semantic", self.status())

    def _set(self, **kw):
        changed = any(self.state.get(k) != v for k, v in kw.items())
        self.state = {**self.state, **kw}
        if changed:
            self.publish(force=True)

    # -- embedding --------------------------------------------------------------------------------------
    def _post(self, texts: list[str]) -> np.ndarray:
        e = self.engine
        r = httpx.post(f"{e.base_url}/embeddings", json={"model": "embed", "input": texts},
                       headers={"Authorization": f"Bearer {e.api_key}"}, timeout=httpx.Timeout(10, read=300))
        if r.status_code >= 400:
            raise RuntimeError(f"embedding server: HTTP {r.status_code}: {r.text[:200]}")
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        v = np.asarray([d["embedding"] for d in data], dtype=np.float32)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)

    def embed_query(self, text: str) -> np.ndarray | None:
        """The question as a vector, or None when meaning-based search isn't available right now."""
        if not self.ready:
            return None
        try:
            return self._post([QUERY.format(text.strip()[:2000])])[0]
        except Exception as exc:                      # noqa: BLE001 -- search falls back to keywords
            log.warning("query embedding failed: %s", exc)
            return None

    # -- hybrid search --------------------------------------------------------------------------------
    @staticmethod
    def fuse(keyword: list[dict], meaning: list[tuple[float, dict]], key: str, limit: int, lean: float = 1.0) -> list[dict]:
        """Reciprocal-rank fusion of keyword hits and meaning hits (cosine >= SEM_MIN). Each result keeps its
        keyword fields when it has them and says how it matched: words, meaning or both. `lean` > 1 weighs meaning
        more (a question in a sentence), < 1 words more."""
        scores: dict[str, float] = {}
        out: dict[str, dict] = {}
        for rank, r in enumerate(keyword):
            k = r[key]
            scores[k] = scores.get(k, 0) + 1 / (RRF_K + rank)
            out[k] = {**r, "match": "words"}
        for rank, (sim, m) in enumerate(x for x in meaning if x[0] >= SEM_MIN):
            k = m["ref"]
            scores[k] = scores.get(k, 0) + lean / (RRF_K + rank)
            if k in out:
                out[k] |= {"match": "both", "similarity": round(sim, 3)}
            else:
                out[k] = {"_meta": m, "match": "meaning", "similarity": round(sim, 3)}
        return [out[k] | {"rank_score": round(scores[k], 5)} for k in sorted(scores, key=lambda k: -scores[k])][:limit]

    def search_notes(self, text: str, limit: int = 30, archived: bool = False) -> dict:
        """Keyword search (D10) merged with meaning. Same shape as SearchIndex.search, plus `mode` and per-result
        `match` (words / meaning / both)."""
        t0 = time.perf_counter()
        kw = self.hub.index.search(text, limit=max(limit, 30), archived=archived)
        q = self.embed_query(text)
        if q is None:
            return kw | {"mode": "words"}
        near = self.store.nearest("note", q, max(limit, 30), archived)
        results = []
        for r in self.fuse(kw["results"], near, "ref", limit, lean(text)):
            m = r.pop("_meta", None)
            if m is not None:
                r |= {"path": m["path"], "ref": m["ref"], "title": m["title"], "folder": m["folder"],
                      "archived": m["archived"], "snippet": m["preview"] or "", "score": 0.0}
            results.append(r)
        return {"q": text, "ms": round((time.perf_counter() - t0) * 1000, 1), "results": results, "mode": "both"}

    def search_sources(self, text: str, limit: int = 20) -> dict:
        t0 = time.perf_counter()
        kw = self.hub.sources.search(text, max(limit, 20))
        q = self.embed_query(text)
        if q is None:
            return kw | {"mode": "words"}
        for r in kw["results"]:
            r["ref"] = f"{r['source']}/{r['path']}"
        near = self.store.nearest("source", q, max(limit, 20))
        results = []
        for r in self.fuse(kw["results"], near, "ref", limit, lean(text)):
            m = r.pop("_meta", None)
            if m is not None:
                source, rel = m["ref"].split("/", 1)
                r |= {"source": source, "path": rel, "title": Path(rel).name, "snippet": m["preview"] or "", "score": 0.0}
            r.pop("ref", None)
            results.append(r)
        return {"q": text, "ms": round((time.perf_counter() - t0) * 1000, 1), "results": results, "mode": "both"}

    def closeness(self, q: np.ndarray, kind: str, refs: set[str]) -> dict[str, float]:
        """How close each of these items is to the question (best passage per document)."""
        return {m["ref"]: s for s, m in self.store.nearest(kind, q, archived=True, only=refs)}

    # -- indexing -------------------------------------------------------------------------------------
    def _note_work(self) -> tuple[list[tuple[str, list[dict], list[str]]], list[str]]:
        """Notes whose text changed since they were embedded, and refs to forget."""
        hub = self.hub
        have = self.store.hashes("note")
        todo, live = [], set()
        for n in hub.vault.scan():
            if not n.uid or any(p.startswith("duplicate uid") for p in n.problems):
                continue
            ref = n.ref
            live.add(ref)
            stamp = (n.path, n.mtime, n.size, n.archived, bool(n.sensitive))
            if ref in have and self._seen.get(ref) == stamp:  # file untouched since it was last read: skip it
                continue
            body = "" if n.sensitive else (hub.vault.read_body(n.path) or "")[:NOTE_CHARS]
            tags = ", ".join(n.tags or [])
            h = _hash(n.title, tags, body, n.path, n.archived)
            if have.get(ref) == h:
                self._seen[ref] = stamp
                continue
            text = DOC.format(n.title, (f"tags: {tags}. " if tags else "") + body if body or tags else n.title)
            todo.append((ref, [{"chunk": 0, "title": n.title, "folder": n.folder, "path": n.path,
                                "archived": n.archived, "hash": h, "preview": preview(body)}], [text]))
        return todo, [r for r in have if r not in live]

    def _source_work(self, limit: int = 5) -> tuple[list[tuple[str, list[dict], list[str]]], list[str], int]:
        """The next few changed documents, split into passages (only those are read), refs to forget, and how
        many documents are still to do."""
        hub = self.hub
        have = self.store.hashes("source")
        todo, live, waiting = [], set(), 0
        for (source, rel), fp in hub.sources.fingerprints().items():
            ref = f"{source}/{rel}"
            live.add(ref)
            h = _hash(fp, CHUNK, OVERLAP)
            if have.get(ref) == h:
                continue
            waiting += 1
            if len(todo) >= limit:
                continue
            text = hub.sources.full_text(source, rel) or ""
            title = Path(rel).stem.replace("_", " ")
            parts = chunks(text)
            if not parts:
                continue
            todo.append((ref, [{"chunk": i, "title": Path(rel).name, "folder": source, "path": rel, "hash": h,
                                "preview": preview(p)} for i, (_, p) in enumerate(parts)],
                         [DOC.format(title, p) for _, p in parts]))
        return todo, [r for r in have if r not in live], waiting

    def _paused(self) -> str | None:
        gm = getattr(self.hub, "gamemode", None)
        return gm.reason() if gm and gm.paused else None

    async def _ensure_server(self) -> bool:
        """Start the embedding server if it isn't running, and wait (up to a minute) until it answers."""
        e = self.engine
        if not (e.serving and e.proc and e.proc.poll() is None):
            await asyncio.to_thread(e.start)
        if e.serving and e.serving.get("ready"):
            return True
        for _ in range(60):
            if await asyncio.to_thread(e.check_ready):     # raises if the process died
                return True
            await asyncio.sleep(1)
        raise RuntimeError("the search model didn't start in a minute; see engine/embed/server.log")

    async def _embed_items(self, kind: str, items: list, label: str) -> None:
        total = sum(len(t) for _, _, t in items)
        done = 0
        self._set(state="indexing", reason=None, what=label, done=0, total=total)
        for ref, rows, texts in items:
            if self._paused():
                return
            vecs = []
            for i in range(0, len(texts), BATCH):
                vecs.append(await asyncio.to_thread(self._post, texts[i:i + BATCH]))
                done += len(texts[i:i + BATCH])
                self.state.update(done=done)
                self.publish()
            await asyncio.to_thread(self.store.put, kind, ref, rows, np.vstack(vecs))
            if kind == "note":
                self._seen.pop(ref, None)            # re-checked (and remembered) on the next pass

    async def run(self):
        """Keeps the vectors in step with the Library and the source copies. Never dies; waits while a game has
        the computer (G1) and while the search model isn't downloaded."""
        if self.engine is None:
            self._set(state="off", reason="the local engine is turned off in config")
            return
        await asyncio.to_thread(self.engine.reap_orphan)
        self.store.set_model(f"{self.engine.model_path.name}|{QUERY}|{DOC}|{CHUNK}")
        while True:
            try:
                if not self.engine.installed():
                    self._set(state="off", reason="download the search model to search by meaning")
                elif (why := self._paused()):
                    self._set(state="paused", reason=why)
                    if self.engine.serving:
                        await asyncio.to_thread(self.engine.stop)
                else:
                    await self._ensure_server()
                    notes, gone = await asyncio.to_thread(self._note_work)
                    await asyncio.to_thread(self.store.delete, "note", gone)
                    if notes:
                        await self._embed_items("note", notes, "notes")
                        continue
                    docs, gone, waiting = await asyncio.to_thread(self._source_work)
                    await asyncio.to_thread(self.store.delete, "source", gone)
                    if docs:                                  # a few at a time, so new notes go first
                        self._set(documents_left=waiting)
                        await self._embed_items("source", docs, "documents")
                        continue
                    self._set(state="ready", reason=None, what=None, documents_left=0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:                  # noqa: BLE001 -- shown in the status; tried again later
                log.warning("semantic index: %s", exc)
                self._set(state="error", reason=str(exc)[:300])
            self.wake.clear()
            try:
                await asyncio.wait_for(self.wake.wait(), 60)
            except asyncio.TimeoutError:
                pass

    def close(self):
        if self.engine:
            self.engine.stop()
        self.store.close()
