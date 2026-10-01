import { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { get, post } from "../api";
import type { NoteFull, NoteMeta, SearchResult, VaultPanel } from "../types";

/** The Bookshelf reader: browse (K1) and search (K2) the vault, read-only. Writes arrive with K3 via the inbox. */
export default function Bookshelf({ panel, onClose }: { panel?: VaultPanel; onClose: () => void }) {
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
              title="Notes that don't follow the vault contract. Click to show only these.">⚠ {vault.problems} with problems</button>
          )}
          <span className="ml-auto flex min-w-0 items-center gap-2">
            {vault && <span className="hidden min-w-0 truncate font-mono text-[11px] normal-case tracking-normal text-mute md:inline" title={vault.root}>{vault.root}</span>}
            <button className="chip" onClick={openVault} title="Show the vault folder in Explorer">OPEN VAULT</button>
            <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
          </span>
        </div>
        {openErr && <div className="border-b border-red/40 px-3 py-1 text-[12px] text-red">{openErr}</div>}

        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside className={`flex min-h-0 flex-col border-cyan/20 md:w-[330px] md:shrink-0 md:border-r ${current ? "hidden md:flex" : "flex flex-1 md:flex-none"}`}>
            <div className="flex items-center gap-2 border-b border-cyan/20 p-2">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notes…" aria-label="Search notes"
                className="min-w-0 flex-1 border border-cyan/35 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
              <label className="flex items-center gap-1 text-[11px] text-mute" title="Archive holds retired notes; nothing is deleted">
                <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} /> archive
              </label>
            </div>
            <div className="panel-body text-[12.5px]">
              {vault && vault.count === 0 && !searching && <EmptyVault onOpen={openVault} />}
              {searching && <SearchResults hits={hits} err={searchErr} current={ref} onPick={setRef} />}
              {!searching && vault && vault.count > 0 && shown.length === 0 && <div className="text-mute">No notes match.</div>}
              {!searching && groups.map(([folder, list]) => (
                <div key={folder} className="mb-2">
                  <div className="display mb-1 text-[10px] text-cyan/80">{folder || "vault root"} <span className="text-mute">{list.length}</span></div>
                  {list.map((n) => (
                    <button key={n.ref} onClick={() => setRef(n.ref)}
                      className={`flex w-full items-baseline gap-1.5 border-l-2 py-0.5 pl-2 text-left ${n.ref === ref ? "border-cyan bg-cyan/10 text-ink" : "border-transparent text-ink/80 hover:border-cyan/40"}`}>
                      <span className="min-w-0 flex-1 truncate">{n.title}</span>
                      {n.origin === "agent" && <span className="text-[10px] text-orange" title={`written by ${n.agent ?? "an agent"}`}>AI</span>}
                      {n.problems.length > 0 && <span className="text-[10px] text-amber" title={n.problems.join("\n")}>⚠</span>}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </aside>

          <section className={`min-h-0 min-w-0 flex-1 flex-col ${current ? "flex" : "hidden md:flex"}`}>
            {current ? <NoteView meta={current} onBack={() => setRef(null)} onOpen={(uid) => setRef(uid)} known={new Set(notes.map((n) => n.ref))} />
              : <div className="m-auto p-6 text-center text-[12.5px] text-mute">{vault && vault.count > 0 ? "Pick a note to read it." : ""}</div>}
          </section>
        </div>
      </div>
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
            <span className="shrink-0 text-[10px] text-mute">{h.archived ? "archive" : h.folder || "root"}</span>
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

function EmptyVault({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="flex flex-col gap-2 text-[12.5px] text-ink/80">
      <div className="display text-[11px] text-cyan">The vault is empty</div>
      <p>Notes are plain markdown files in this folder. Sage OS never writes them on its own: they arrive as agent proposals you approve in the inbox (coming in K3), through imports (K6), or as files you add yourself.</p>
      <button className="chip self-start" onClick={onOpen}>OPEN VAULT</button>
    </div>
  );
}

function NoteView({ meta, onBack, onOpen, known }: { meta: NoteMeta; onBack: () => void; onOpen: (uid: string) => void; known: Set<string> }) {
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
        {meta.problems.length > 0 && (
          <div className="mb-3 border border-amber/50 bg-amber/5 p-2 text-[12px]">
            <div className="display mb-1 text-[10px] text-amber">Doesn't follow the vault contract</div>
            <ul className="list-disc pl-4 text-amber">{meta.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}
        {err && <div className="text-red">{err}</div>}
        {!n && !err && <div className="text-mute">loading…</div>}
        {n && (source
          ? <pre className="whitespace-pre-wrap font-mono text-[12px] text-ink/85">{n.source}</pre>
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
      </div>
    </>
  );
}
