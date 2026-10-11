import { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { get, post } from "../api";
import type { Batch, DigestJob, NoteFull, NoteMeta, SearchResult, SourcesPanel, VaultPanel } from "../types";
import Sources from "./Sources";
import Digests from "./Digests";
import Storage from "./Storage";
import { ago, useNow } from "../util";

/** The Bookshelf reader: browse (K1) and search (K2) the vault, read-only. Writes arrive with K3 via the inbox. */
export default function Bookshelf({ panel, sources, digests, proposals = 0, onClose }: {
  panel?: VaultPanel; sources?: SourcesPanel; digests?: { jobs: DigestJob[] }; proposals?: number; onClose: () => void;
}) {
  const [fetched, setFetched] = useState<VaultPanel | null>(null);
  const vault = panel ?? fetched;
  const [ref, setRef] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [archived, setArchived] = useState(false);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [openErr, setOpenErr] = useState<string | null>(null);
  const [hits, setHits] = useState<SearchResult | null>(null);
  const [searchErr, setSearchErr] = useState<string | null>(null);
  const searching = q.trim().length > 0;
  const [view, setView] = useState<"notes" | "history" | "sources" | "digests" | "storage">("notes");
  const [cited, setCited] = useState<{ source: string; path: string } | null>(null);
  const showSource = (doc: { source: string; path: string } | null) => { setCited(doc); setView("sources"); };

  useEffect(() => {
    if (!panel) get<VaultPanel>("/api/vault").then(setFetched).catch(() => {});
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  // Search as you type (debounced); re-run when the vault changes so results stay current.
  useEffect(() => {
    if (!searching) { setHits(null); setSearchErr(null); return; }
    let alive = true;
    const t = setTimeout(() => {
      get<SearchResult>(`/api/vault/search?q=${encodeURIComponent(q)}&archived=${archived}`)
        .then((r) => { if (alive) { setHits(r); setSearchErr(null); } })
        .catch((e) => alive && setSearchErr(String(e.message ?? e)));
    }, 150);
    return () => { alive = false; clearTimeout(t); };
  }, [q, archived, vault?.indexed, vault?.notes]);

  const notes = vault?.notes ?? [];
  const shown = useMemo(() => notes.filter((n) => (archived || !n.archived) && (!onlyProblems || n.problems.length > 0)),
    [notes, archived, onlyProblems]);
  const groups = useMemo(() => {
    const g = new Map<string, NoteMeta[]>();
    for (const n of [...shown].sort((a, b) => a.title.localeCompare(b.title))) g.set(n.folder, [...(g.get(n.folder) ?? []), n]);
    return [...g.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [shown]);
  const current = notes.find((n) => n.ref === ref) ?? null;

  const openVault = async () => {
    setOpenErr(null);
    try { await post("/api/vault/open"); } catch (e) { setOpenErr(String((e as Error).message ?? e)); }
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[1400px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="bookshelf">
        <div className="panel-head flex-wrap gap-y-1">
          <span className="tab">BOOKSHELF</span>
          <span className="text-mute normal-case tracking-normal">{vault ? `${vault.count} note${vault.count === 1 ? "" : "s"}` : "loading…"}</span>
          {vault && vault.problems > 0 && (
            <button className={`chip amber normal-case tracking-normal ${onlyProblems ? "pulse-amber" : ""}`} onClick={() => setOnlyProblems(!onlyProblems)}
              title="Notes that don't match the note format (missing fields, bad uid, absolute paths…). Click to show only these.">⚠ {vault.problems} with problems</button>
          )}
          <span className="flex gap-1">
            <button className={`htab ${view === "notes" ? "on" : ""}`} onClick={() => setView("notes")}>NOTES</button>
            <button className={`htab ${view === "history" ? "on" : ""}`} onClick={() => setView("history")}>HISTORY</button>
            <button className={`htab ${view === "sources" ? "on" : ""}`} onClick={() => showSource(null)}>SOURCES</button>
            <button className={`htab ${view === "digests" ? "on" : ""}`} onClick={() => setView("digests")} title="Long documents turned into notes, section by section">DIGESTS</button>
            <button className={`htab ${view === "storage" ? "on" : ""}`} onClick={() => setView("storage")} title="Where your notes and files live, syncing them between devices, export">STORAGE</button>
          </span>
          <span className="ml-auto flex min-w-0 items-center gap-2">
            {vault && <span className="hidden min-w-0 truncate font-mono text-[11px] normal-case tracking-normal text-mute md:inline" title={vault.root}>{vault.root}</span>}
            <button className="chip" onClick={openVault} title="Show the vault folder in Explorer">OPEN VAULT</button>
            <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
          </span>
        </div>
        {openErr && <div className="border-b border-red/40 px-3 py-1 text-[12px] text-red">{openErr}</div>}

        {view === "storage" ? <Storage /> : view === "digests" ? <Digests jobs={digests?.jobs ?? []} /> : view === "sources" ? <Sources key={cited ? cited.source + cited.path : ""} panel={sources} doc={cited} /> : view === "history" ? <History changed={vault?.notes} /> : <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside className={`flex min-h-0 flex-col border-cyan/20 md:w-[330px] md:shrink-0 md:border-r ${current ? "hidden md:flex" : "flex flex-1 md:flex-none"}`}>
            <div className="flex items-center gap-2 border-b border-cyan/20 p-2">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notes…" aria-label="Search notes"
                className="min-w-0 flex-1 border border-cyan/35 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
              <label className="flex items-center gap-1 text-[11px] text-mute" title="Archive holds retired notes; nothing is deleted">
                <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} /> archive
              </label>
            </div>
            <div className="panel-body text-[12.5px]">
              {vault && vault.count === 0 && !searching && <EmptyVault onOpen={openVault} onSources={() => showSource(null)} proposals={proposals} />}
              {searching && <SearchResults hits={hits} err={searchErr} current={ref} onPick={setRef} />}
              {!searching && vault && vault.count > 0 && shown.length === 0 && <div className="text-mute">No notes match.</div>}
              {!searching && groups.map(([folder, list]) => (
                <div key={folder} className="mb-2">
                  <div className="display mb-1 text-[11px] text-cyan/80">{folder || "vault root"} <span className="text-mute">{list.length}</span></div>
                  {list.map((n) => (
                    <button key={n.ref} onClick={() => setRef(n.ref)}
                      className={`flex w-full items-baseline gap-1.5 border-l-2 py-0.5 pl-2 text-left ${n.ref === ref ? "border-cyan bg-cyan/10 text-ink" : "border-transparent text-ink/80 hover:border-cyan/40"}`}>
                      <span className="min-w-0 flex-1 truncate">{n.title}</span>
                      {n.origin === "agent" && <span className="text-[11px] text-orange" title={`written by ${n.agent ?? "an agent"}`}>AI</span>}
                      {n.sensitive && <span className="text-[11px]" title={`Looks like it contains ${n.sensitive}; its text is left out of search`}>🔒</span>}
                      {n.problems.length > 0 && <span className="text-[11px] text-amber" title={n.problems.join("\n")}>⚠</span>}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </aside>

          <section className={`min-h-0 min-w-0 flex-1 flex-col ${current ? "flex" : "hidden md:flex"}`}>
            {current ? <NoteView meta={current} onBack={() => setRef(null)} onOpen={(uid) => setRef(uid)} onSource={showSource} known={new Set(notes.map((n) => n.ref))} />
              : vault && vault.count > 0 ? <div className="m-auto p-6 text-center text-[12.5px] text-mute">Pick a note to read it.</div>
              : <HowNotesArrive onSources={() => showSource(null)} />}
          </section>
        </div>}
      </div>
    </div>
  );
}

/** Every batch the writer applied, newest first, with exact undo (K3). */
function History({ changed }: { changed: unknown }) {
  const now = useNow(10000);
  const [batches, setBatches] = useState<Batch[] | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => get<Batch[]>("/api/vault/history").then(setBatches).catch((e) => setErr(String(e.message ?? e)));
  useEffect(() => { load(); }, [changed]);
  const undo = async (id: string) => {
    setErr(null); setConfirm(null);
    try { await post(`/api/vault/batches/${id}/undo`); } catch (e) { setErr(String((e as Error).message ?? e)); }
    load();
  };
  return (
    <div className="panel-body text-[12.5px]">
      <p className="mb-2 text-[11.5px] text-mute">Every change Sage OS made to the vault, applied only after you approved it in the inbox. Undo puts the files back exactly as they were; it refuses if a file was edited since.</p>
      {err && <div className="mb-2 border border-red/40 bg-red/5 p-1.5 text-red">{err}</div>}
      {batches?.length === 0 && <div className="text-mute">Nothing written yet.</div>}
      {batches?.map((b) => (
        <div key={b.id} className={`mb-2 border-l-2 py-1 pl-2 ${b.status === "applied" ? "border-cyan/50" : "border-mute/40 opacity-70"}`}>
          <div className="flex flex-wrap items-baseline gap-x-2 text-[11.5px]">
            <span className="text-cyan">#{b.id}</span>
            <span className="text-ink">{b.agent}</span>
            <span className="text-mute">{ago(b.finished ?? b.started, now)}</span>
            <span className={`chip ${b.status === "applied" ? "" : "mute"}`}>{b.status.replace("_", " ")}</span>
            {b.status === "applied" && (confirm === b.id
              ? <span className="ml-auto flex gap-1"><button className="chip red" onClick={() => undo(b.id)}>CONFIRM UNDO</button><button className="chip mute" onClick={() => setConfirm(null)}>keep</button></span>
              : <button className="chip ml-auto" onClick={() => setConfirm(b.id)}>UNDO</button>)}
          </div>
          {b.summary && <div className="text-ink/80">{b.summary}</div>}
          <ul className="mt-0.5 font-mono text-[11px] text-ink/70">
            {b.files.map((f) => <li key={f.path + f.op}><span className="text-mute">{f.op}</span> {f.path}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

function SearchResults({ hits, err, current, onPick }: {
  hits: SearchResult | null; err: string | null; current: string | null; onPick: (ref: string) => void;
}) {
  if (err) return <div className="text-red">{err}</div>;
  if (!hits) return <div className="text-mute">searching…</div>;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[11px] text-mute">{hits.results.length === 0 ? "Nothing in your notes matches."
        : hits.results.length >= 30 ? "top 30 matches" : `${hits.results.length} match${hits.results.length === 1 ? "" : "es"}`} · {hits.ms} ms</div>
      {hits.results.map((h) => (
        <button key={h.ref} onClick={() => onPick(h.ref)}
          className={`border-l-2 py-1 pl-2 text-left ${h.ref === current ? "border-cyan bg-cyan/10" : "border-transparent hover:border-cyan/40"}`}>
          <div className="flex items-baseline gap-1.5">
            <span className="min-w-0 flex-1 truncate text-ink">{h.title}</span>
            <span className="shrink-0 text-[11px] text-mute">{h.archived ? "archive" : h.folder || "root"}</span>
          </div>
          <div className="line-clamp-2 text-[11.5px] text-ink/65"><Snippet text={h.snippet} /></div>
        </button>
      ))}
    </div>
  );
}

/** The index marks matches with \x02 ... \x03; render them as highlights without any HTML parsing. */
function Snippet({ text }: { text: string }) {
  return <>{text.split("\x02").map((part, i) => {
    if (i === 0) return <span key={i}>{part}</span>;
    const [hit, rest = ""] = part.split("\x03");
    return <span key={i}><mark className="bg-cyan/25 text-ink">{hit}</mark>{rest}</span>;
  })}</>;
}

/** The path from your files to a note, shown while the vault is empty (D17, D11). */
const FLOW: [string, string][] = [
  ["Sources", "Sage OS keeps a read-only copy of the folders you chose and makes their text searchable. The originals are never touched."],
  ["Build notes", "It proposes starter notes: your markdown files as they are, plus one index note per folder listing what's in it. Draft asks an agent to write notes that cite the documents."],
  ["Inbox", "Every proposal waits for you with the exact change shown. Secret-looking text is held back. You approve or reject it."],
  ["Bookshelf", "Approved notes land here as plain markdown, searchable by you and by every agent. History can undo any batch exactly."],
];

/** Where a note came from (its `source:`, K6). A cited file opens in Sources; a folder (what collection
 *  notes cite, D17) is just named. */
function Cited({ source, folder, onOpen }: { source: string; folder: boolean; onOpen: (doc: { source: string; path: string }) => void }) {
  const m = /^sources\/([^/]+)\/(.+)$/.exec(source);
  const file = m && !folder;
  return (
    <div className="mt-2 flex items-baseline gap-1.5 text-[11px]">
      <span className="text-mute">Built from:</span>
      {m && file
        ? <button className="chip min-w-0 truncate normal-case tracking-normal" title="Open this document in Sources" onClick={() => onOpen({ source: m[1], path: m[2] })}>{m[2]}</button>
        : <span className="min-w-0 truncate font-mono text-ink/80" title={source}>{m ? `${m[2]}/ (folder in ${m[1]})` : source}</span>}
    </div>
  );
}

function HowNotesArrive({ onSources }: { onSources: () => void }) {
  return (
    <div className="m-auto flex max-w-[560px] flex-col gap-4 p-6" data-testid="how-notes">
      <div className="display text-[11px] text-mute">How notes get here</div>
      <ol className="flex flex-col gap-3">
        {FLOW.map(([step, what], i) => (
          <li key={step} className="flex gap-3">
            <span className="font-dot glow-cyan w-6 shrink-0 text-[20px] leading-none">{i + 1}</span>
            <span><span className="display text-[13px] text-cyan">{step}</span>
              <span className="mt-0.5 block text-[12.5px] leading-snug text-ink/85">{what}</span></span>
          </li>
        ))}
      </ol>
      <button className="chip self-start" onClick={onSources}>START WITH SOURCES →</button>
    </div>
  );
}

function EmptyVault({ onOpen, onSources, proposals }: { onOpen: () => void; onSources: () => void; proposals: number }) {
  return (
    <div className="flex flex-col gap-2 text-[12.5px] text-ink/80">
      <div className="display text-[11px] text-cyan">The vault is empty</div>
      <p>Notes are plain markdown files in this folder. Sage OS never writes one on its own. Agents propose notes and you approve them in the inbox, or you add files here yourself.</p>
      {proposals > 0 ? (
        <p className="border-l-2 border-amber/60 pl-2 text-amber">{proposals} note proposal{proposals === 1 ? " is" : "s are"} waiting in the inbox. Approve one and its notes appear here.</p>
      ) : (
        <p className="border-l-2 border-cyan/50 pl-2">To start from your own files: <b>Sources</b> → <b>Build notes</b> → <b>Propose starter notes</b>.</p>
      )}
      <span className="flex gap-2">
        <button className="chip md:hidden" onClick={onSources}>GO TO SOURCES</button>
        <button className="chip mute" onClick={onOpen}>OPEN VAULT</button>
      </span>
    </div>
  );
}

function NoteView({ meta, onBack, onOpen, onSource, known }: {
  meta: NoteMeta; onBack: () => void; onOpen: (uid: string) => void; onSource: (doc: { source: string; path: string }) => void; known: Set<string>;
}) {
  const [note, setNote] = useState<NoteFull | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [source, setSource] = useState(false);

  useEffect(() => {      // re-read when the file changes on disk (mtime comes with the live panel)
    let alive = true;
    setErr(null);
    get<NoteFull>(`/api/vault/note?ref=${encodeURIComponent(meta.ref)}`)
      .then((n) => alive && setNote(n)).catch((e) => alive && setErr(String(e.message ?? e)));
    return () => { alive = false; };
  }, [meta.ref, meta.mtime]);

  const n = note?.ref === meta.ref ? note : null;
  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5 border-b border-cyan/20 px-3 py-2 text-[11px]">
        <span className="md:hidden"><button className="chip" onClick={onBack}>← notes</button></span>
        <h2 className="display mr-2 min-w-0 text-[14px] text-ink">{meta.title}</h2>
        {meta.type && <span className="chip mute">{meta.type}</span>}
        {meta.status && <span className="chip mute">{meta.status}</span>}
        {meta.origin === "agent"
          ? <span className="chip orange" title="Written by an agent and approved by you">agent · {meta.agent ?? "unknown"}</span>
          : meta.origin && <span className="chip mute">{meta.origin}</span>}
        {meta.archived && <span className="chip mute">archived</span>}
        <span className="ml-auto flex gap-1">
          <button className={`htab ${!source ? "on" : ""}`} onClick={() => setSource(false)}>READ</button>
          <button className={`htab ${source ? "on" : ""}`} onClick={() => setSource(true)}>SOURCE</button>
        </span>
      </div>
      <div className="panel-body text-[13.5px] leading-relaxed">
        {meta.sensitive && (
          <div className="mb-3 border border-amber/50 bg-amber/5 p-2 text-[12px] text-amber">
            🔒 This note looks like it contains {meta.sensitive}. It stays in your file, but Sage OS leaves its text out of search.
            A password manager is a safer home for secrets.
          </div>
        )}
        {meta.problems.length > 0 && (
          <div className="mb-3 border border-amber/50 bg-amber/5 p-2 text-[12px]">
            <div className="display mb-1 text-[11px] text-amber">Doesn't match the note format</div>
            <ul className="list-disc pl-4 text-amber">{meta.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}
        {err && <div className="text-red">{err}</div>}
        {!n && !err && <div className="text-mute">loading…</div>}
        {n && (source
          ? <pre className="whitespace-pre-wrap font-mono text-[12px] text-ink/85">{n.text}</pre>
          : <div className="md"><Markdown remarkPlugins={[remarkGfm]} components={{
              a: ({ href, children }) => /^https?:\/\//.test(href ?? "")
                ? <a href={href} target="_blank" rel="noreferrer noopener">{children}</a> : <span title={href}>{children}</span>,
              img: ({ alt, src }) => <span className="text-mute" title={src}>[image: {alt || src}]</span>,
            }}>{n.body}</Markdown></div>)}
        <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-cyan/15 pt-2 text-[11px]">
          <span className="text-mute">Links to:</span>
          {meta.links.length === 0 && <span className="text-mute">nothing yet</span>}
          {meta.links.map((l) => known.has(l.uid)
            ? <button key={l.uid} className="chip" onClick={() => onOpen(l.uid)}>{l.title ?? l.uid}</button>
            : <span key={l.uid} className="chip mute" title={l.uid}>missing note</span>)}
          {meta.tags.map((t) => <span key={t} className="chip mute">#{t}</span>)}
          <span className="ml-auto font-mono text-mute" title={meta.uid ?? "no uid"}>{meta.path}</span>
        </div>
        {meta.source && <Cited source={meta.source} folder={meta.tags.includes("collection")} onOpen={onSource} />}
      </div>
    </>
  );
}
