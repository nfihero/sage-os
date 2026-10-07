import { useEffect, useMemo, useState } from "react";
import { get, post } from "../api";
import type { BuildResult, GoogleStatus, SourceCollection, SourceDoc, SourceHit, SourceInfo, SourcesPanel } from "../types";
import { ago, useNow } from "../util";

/** The source library (D15): read-only copies of chosen folders, searchable, citable, never edited. */
export default function Sources({ panel, doc }: { panel?: SourcesPanel; doc?: { source: string; path: string } | null }) {
  const [fetched, setFetched] = useState<SourcesPanel | null>(null);
  const data = panel ?? fetched;
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ ms: number; results: SourceHit[] } | null>(null);
  // `doc`: a document to show on arrival, e.g. the one a note cites
  const [open, setOpen] = useState<SourceHit | null>(() => doc
    ? { source: doc.source, path: doc.path, title: doc.path.split("/").pop() ?? doc.path, snippet: "", score: 0 } : null);

  useEffect(() => { if (!panel) get<SourcesPanel>("/api/sources").then(setFetched).catch(() => {}); }, []);
  useEffect(() => {
    if (!q.trim()) { setHits(null); return; }
    let alive = true;
    const t = setTimeout(() => {
      get<{ ms: number; results: SourceHit[] }>(`/api/sources/search?q=${encodeURIComponent(q)}`).then((r) => alive && setHits(r)).catch(() => {});
    }, 150);
    return () => { alive = false; clearTimeout(t); };
  }, [q, data]);

  const sources = data?.sources ?? [];
  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <aside className={`flex min-h-0 flex-col border-cyan/20 md:w-[380px] md:shrink-0 md:border-r ${open ? "hidden md:flex" : "flex flex-1 md:flex-none"}`}>
        <div className="border-b border-cyan/20 p-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your documents…" aria-label="Search sources"
            className="w-full border border-cyan/35 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
        </div>
        <div className="panel-body text-[12.5px]">
          {sources.length === 0 && (
            <p className="text-mute">No sources configured. Add a <code>[[sources]]</code> entry to config.toml (DECISIONS D15).</p>
          )}
          {!q.trim() && data?.google && sources.some((s) => s.google) && <GoogleCard g={data.google} />}
          {!q.trim() && sources.map((s) => <SourceCard key={s.name} s={s} />)}
          {q.trim() && hits && (
            <div className="flex flex-col gap-1.5">
              <div className="text-[11px] text-mute">{hits.results.length === 0 ? "Nothing in your sources matches." : `${hits.results.length} match${hits.results.length === 1 ? "" : "es"}`} · {hits.ms} ms</div>
              {hits.results.map((h) => (
                <button key={h.source + h.path} onClick={() => setOpen(h)}
                  className={`border-l-2 py-1 pl-2 text-left ${open?.path === h.path ? "border-cyan bg-cyan/10" : "border-transparent hover:border-cyan/40"}`}>
                  <div className="truncate text-ink">{h.title}</div>
                  <div className="truncate font-mono text-[10px] text-mute">{h.path}</div>
                  <div className="line-clamp-2 text-[11.5px] text-ink/65"><Snippet text={h.snippet} /></div>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>
      <section className={`min-h-0 min-w-0 flex-1 flex-col ${open ? "flex" : "hidden md:flex"}`}>
        {open ? <DocView hit={open} onBack={() => setOpen(null)} />
          : <div className="m-auto max-w-md p-6 text-center text-[12.5px] text-mute">Search your documents, then pick one to read its text. Agents search and cite these too; nobody edits them here.</div>}
      </section>
    </div>
  );
}

/** Google Docs, Sheets and Slides come through the Drive API (D22): read-only consent in the user's browser. */
function GoogleCard({ g }: { g: GoogleStatus }) {
  const [err, setErr] = useState<string | null>(null);
  const connect = async () => {
    setErr(null);
    const tab = window.open("about:blank", "_blank");     // opened in the click, so it isn't blocked
    if (tab) tab.opener = null;                            // the sign-in page can't reach back into Sage OS
    try {
      const { url } = await post<{ url: string }>("/api/google/connect");
      if (!url.startsWith("https://accounts.google.com/")) throw new Error("unexpected sign-in address");
      if (tab) tab.location.href = url; else window.location.href = url;
    } catch (e) { tab?.close(); setErr(String((e as Error).message ?? e)); }
  };
  const disconnect = async () => {
    setErr(null);
    try { await post("/api/google/disconnect"); } catch (e) { setErr(String((e as Error).message ?? e)); }
  };
  return (
    <div className="mb-3 border border-cyan/20 p-2 text-[11.5px]">
      <div className="flex items-center gap-2">
        <span className="display text-[12px] text-cyan">Google Drive</span>
        <span className={`light ${g.connected ? "up" : "idle"}`} />
        <span className="min-w-0 flex-1 truncate text-mute">{g.connected ? `connected, read-only${g.account ? ` · ${g.account}` : ""}` : "not connected"}</span>
      </div>
      <p className="mt-1 text-ink/75">
        {g.connected ? "Google Docs, Sheets and Slides are exported and indexed on each sync. Drive is never changed."
          : g.configured ? "Connect to bring in Google Docs, Sheets and Slides. Google asks you to sign in and allow read-only access."
          : <>To include Google Docs, Sheets and Slides, save a Google OAuth client (Desktop app) as <code className="break-all">{g.client_file}</code>, then connect.</>}
      </p>
      <div className="mt-1.5 flex gap-1.5">
        {!g.connected && <button className="chip" disabled={!g.configured} onClick={connect}>CONNECT GOOGLE DRIVE</button>}
        {g.connected && <button className="chip mute" onClick={disconnect} title="Revoke Sage OS's access and forget the token">DISCONNECT</button>}
      </div>
      {err && <div className="mt-1 text-red">{err}</div>}
    </div>
  );
}

function SourceCard({ s }: { s: SourceInfo }) {
  const now = useNow(10000);
  const [err, setErr] = useState<string | null>(null);
  const [showSkipped, setShowSkipped] = useState(false);
  const byReason = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const x of s.skipped) m.set(x.reason, [...(m.get(x.reason) ?? []), x.path]);
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [s.skipped]);
  const run = async (what: "sync" | "open") => {
    setErr(null);
    try { await post(`/api/sources/${encodeURIComponent(s.name)}/${what}`); } catch (e) { setErr(String((e as Error).message ?? e)); }
  };
  const st = s.last_stats;
  return (
    <div className="mb-3 border border-cyan/20 p-2">
      <div className="flex items-baseline gap-2">
        <span className="display text-[12px] text-cyan">{s.name}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-[10.5px] text-mute" title={`${s.path} → ${s.copy}`}>{s.path} → copy</span>
      </div>
      <div className="mt-1 text-[11.5px] text-ink/80">
        {s.files} files copied, {s.indexed} searchable · {s.last_sync ? `synced ${ago(s.last_sync, now)} ago` : "never synced"}
        {st && <span className="text-mute"> · last run {st.copied} new/changed, {st.removed} removed{st.private_content ? `, ${st.private_content} private by content` : ""}</span>}
      </div>
      {s.syncing && <div className="mt-1 text-[11.5px] glow-cyan">syncing{s.progress ? ` ${s.progress.done}/${s.progress.total}` : ""}<span className="dots" /></div>}
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        <button className="chip" disabled={s.syncing} onClick={() => run("sync")} title="Copy new and changed files from the original (read-only) and index their text">SYNC NOW</button>
        <button className="chip mute" onClick={() => run("open")} title="Show the copy in Explorer">OPEN COPY</button>
        {s.skipped.length > 0 && <button className="chip mute" onClick={() => setShowSkipped(!showSkipped)}>{s.skipped.length} left out {showSkipped ? "▾" : "▸"}</button>}
      </div>
      {err && <div className="mt-1 text-[11.5px] text-red">{err}</div>}
      {showSkipped && (
        <div className="mt-1.5 max-h-72 overflow-auto text-[11px]">
          {byReason.map(([reason, paths]) => (
            <details key={reason} className="mb-1" open={/private|contains/.test(reason)}>
              <summary className={`cursor-pointer ${/private|contains/.test(reason) ? "text-amber" : "text-mute"}`}>{reason} ({paths.length})</summary>
              <ul className="ml-3 font-mono text-[10.5px] text-ink/70">{paths.map((p) => <li key={p} className="truncate" title={p}>{p}</li>)}</ul>
            </details>
          ))}
        </div>
      )}
      {s.include.length > 0 && <div className="mt-1.5 text-[10.5px] text-mute" title={s.include.join("\n")}>{s.include.length} folders selected in config.toml</div>}
      {s.files > 0 && <BuildNotes name={s.name} synced={s.last_sync} />}
    </div>
  );
}

/** K6: start the vault from this source. Starter notes are proposals; agents draft concept notes on request. */
function BuildNotes({ name, synced }: { name: string; synced: number | null }) {
  const [cols, setCols] = useState<SourceCollection[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const load = () => get<SourceCollection[]>(`/api/sources/${encodeURIComponent(name)}/collections`).then(setCols).catch(() => {});
  useEffect(() => { load(); }, [name, synced]);
  const build = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await post<BuildResult>(`/api/sources/${encodeURIComponent(name)}/build`);
      const parts = [r.proposed ? `${r.notes} starter notes proposed in ${r.proposed} inbox card${r.proposed === 1 ? "" : "s"}` : "No new starter notes"];
      if (r.already) parts.push(`${r.already} already built or waiting`);
      if (r.left_out.length) parts.push(`${r.left_out.length} left out (${r.left_out.map((x) => x.reason).slice(0, 2).join("; ")})`);
      if (r.not_sent.length) parts.push(`${r.not_sent.length} wait for earlier cards to be decided`);
      setMsg({ tone: "ok", text: parts.join(" · ") + (r.proposed ? ". Approve the ones you want in the inbox." : ".") });
    } catch (e) { setMsg({ tone: "err", text: String((e as Error).message ?? e) }); }
    setBusy(false); load();
  };
  const draft = async (c: SourceCollection) => {
    setMsg(null);
    try {
      const r = await post<{ agent: string; title: string }>(`/api/sources/${encodeURIComponent(name)}/draft`, { folder: c.dir });
      setMsg({ tone: "ok", text: `${r.agent} is drafting concept notes for ${r.title} in the chat "Bookshelf: draft notes for ${r.title}". Its proposals arrive in the inbox.` });
    } catch (e) { setMsg({ tone: "err", text: String((e as Error).message ?? e) }); }
  };
  const fresh = cols?.filter((c) => c.status === "new").length ?? 0;
  return (
    <div className="mt-2 border-t border-cyan/15 pt-2">
      <div className="display mb-1 text-[10px] text-cyan/80">Build notes from this source</div>
      <p className="text-[11.5px] text-ink/75">Starter notes: your markdown files as notes, plus one index note per folder of documents. Everything arrives in the inbox for you to approve.</p>
      <button className="chip mt-1.5" disabled={busy || fresh === 0} onClick={build}
        title={fresh === 0 ? "Every collection is already built or waiting in the inbox" : "Propose starter notes for every collection not built yet"}>
        {busy ? "PROPOSING…" : `PROPOSE STARTER NOTES${fresh ? ` (${fresh})` : ""}`}
      </button>
      {msg && <div className={`mt-1 text-[11.5px] ${msg.tone === "err" ? "text-red" : "text-ink/80"}`}>{msg.text}</div>}
      {cols && cols.length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {cols.map((c) => (
            <div key={c.dir} className="flex items-baseline gap-1.5 text-[11.5px]">
              <span className="min-w-0 flex-1 truncate text-ink/85" title={`${c.dir || "(source root)"} → ${c.folder}`}>{c.title}</span>
              <span className="shrink-0 text-[10px] text-mute">{c.docs} docs{c.markdown ? ` · ${c.markdown} md` : ""}</span>
              <span className={`chip shrink-0 ${c.status === "built" ? "" : c.status === "pending" ? "amber" : "mute"}`}>{c.status === "built" ? "in vault" : c.status === "pending" ? "in inbox" : "new"}</span>
              <button className="chip shrink-0" disabled={c.docs === 0} onClick={() => draft(c)}
                title="Ask an agent (Hermes by default, free and local) to read these documents and propose concept notes that cite them">DRAFT</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DocView({ hit, onBack }: { hit: SourceHit; onBack: () => void }) {
  const [pages, setPages] = useState<SourceDoc[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = (offset: number) =>
    get<SourceDoc>(`/api/sources/read?source=${encodeURIComponent(hit.source)}&path=${encodeURIComponent(hit.path)}&offset=${offset}`)
      .then((d) => setPages((p) => (offset === 0 ? [d] : [...p, d]))).catch((e) => setErr(String(e.message ?? e)));
  useEffect(() => { setPages([]); setErr(null); load(0); }, [hit.source, hit.path]);
  const last = pages[pages.length - 1];
  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5 border-b border-cyan/20 px-3 py-2 text-[11px]">
        <span className="md:hidden"><button className="chip" onClick={onBack}>← sources</button></span>
        <h2 className="display mr-2 min-w-0 truncate text-[14px] text-ink" title={hit.path}>{hit.title}</h2>
        <span className="chip mute">{hit.source}</span>
        {last && <span className="text-mute">{last.chars.toLocaleString()} characters of text</span>}
        <span className="ml-auto truncate font-mono text-mute" title={hit.path}>{hit.path}</span>
      </div>
      <div className="panel-body">
        {err && <div className="text-red">{err}</div>}
        {pages[0]?.note && <div className="mb-2 text-[12px] text-amber">{pages[0].note}</div>}
        <pre className="whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-ink/85">{pages.map((p) => p.text).join("")}</pre>
        {last?.more && <button className="chip mt-2" onClick={() => load(last.offset + last.text.length)}>LOAD MORE</button>}
      </div>
    </>
  );
}

function Snippet({ text }: { text: string }) {
  return <>{text.split("\x02").map((part, i) => {
    if (i === 0) return <span key={i}>{part}</span>;
    const [hit, rest = ""] = part.split("\x03");
    return <span key={i}><mark className="bg-cyan/25 text-ink">{hit}</mark>{rest}</span>;
  })}</>;
}
