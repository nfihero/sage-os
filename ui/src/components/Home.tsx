import { useEffect, useMemo, useRef, useState } from "react";
import { get, post } from "../api";
import type { ClaudePanel, Panels, SearchResult, SourceHit } from "../types";
import { shortModel, useNow } from "../util";
import Orb from "./LazyOrb";
import { Snippet } from "./Bookshelf";
import { Ago, Meter, Num, Row } from "./Readout";
import { UsageBars } from "./Usage";

/** W2 (D35): the library-first home. Left, the agent side panel (planet, model, where it runs, usage) and the
 *  agents you can switch between; centre, search over your library and the conversation; right, what waits for you.
 *  The board, GPU lane and safety feed live under Systems. */

export type AgentKey = "local" | "claude";

const GB = 1024;

/** Left: the agent answering you, as a planet with its facts, then the others to switch to or connect. */
export function AgentPanel({ agent, setAgent, panels, lowPower, claudeReady, onConnectClaude, onModels }: {
  agent: AgentKey; setAgent: (a: AgentKey) => void; panels: Panels; lowPower?: boolean; claudeReady: boolean;
  onConnectClaude: () => void; onModels: () => void;
}) {
  const engine = panels.engine?.serving;
  const chats = panels.chat?.sessions ?? [];
  const g = panels.gpu?.gpu;
  const claude: ClaudePanel | undefined = panels.claude;
  const latest = [...(claude?.sessions ?? [])].sort((a, b) => b.updated - a.updated)[0];
  const game = panels.gamemode;
  const aside = game?.state === "aside" || game?.state === "micro";

  const state = agent === "claude"
    ? (claude?.sessions.some((s) => s.status === "waiting") ? "waiting" : claude?.sessions.some((s) => s.status === "running") ? "streaming" : "idle")
    : (chats.some((s) => s.status === "running") ? "streaming" : engine && !engine.ready ? "thinking" : "idle");
  const label = agent === "claude"
    ? (state === "waiting" ? "WAITING ON YOU" : state === "streaming" ? "WORKING" : "IDLE")
    : (aside ? "PAUSED FOR A GAME" : !engine ? "NOT LOADED" : state === "thinking" ? "LOADING" : state === "streaming" ? "ANSWERING" : "IDLE");

  return (
    <div className="flex min-h-0 flex-col gap-3" data-tour="agent">
      <section className={`panel min-h-0 ${agent === "claude" ? "claude" : ""}`} style={{ flex: "none" }}>
        <div className="panel-head"><span className="tab">{agent === "claude" ? "Claude Code" : "Local model"}</span></div>
        <div className="panel-body flex flex-col items-center gap-3 [--orb:min(200px,22vh)]">
          <Orb id={agent === "claude" ? "claude" : "local"} state={state} tone={agent === "claude" ? "claude" : "accent"} size="var(--orb)" lowPower={lowPower} />
          <div className="readout w-full text-[12px]">
            <Row k="State" v={label} hot={label !== "IDLE" && label !== "NOT LOADED"} />
            {agent === "claude" ? <>
              <Row k="Model" v={latest?.model ?? "default"} />
              <Row k="Folder" v={latest ? latest.cwd.split(/[\\/]/).slice(-2).join("/") : "none yet"} />
              <Row k="Turns" v={String(latest?.turns ?? 0)} />
            </> : <>
              <Row k="Model" v={engine ? shortModel(engine.id) : game?.previous ? shortModel(game.previous) : "none loaded"} />
              <Row k="Where" v={g ? "this PC, on the GPU" : "this PC"} />
              <Row k="Chats" v={String(chats.length)} />
            </>}
          </div>
          {agent === "local" && (
            <div className="flex w-full flex-wrap gap-1">
              {["search notes", "read sources", "propose notes"].map((t) => <span key={t} className="chip mute">{t}</span>)}
            </div>
          )}
          <div className="w-full border-t border-cyan/15 pt-2">
            {agent === "claude" ? <>
              <div className="kicker"><span>Subscription</span><span>usage</span></div>
              <UsageBars usage={panels.claude_usage} />
            </> : g ? <>
              <div className="kicker"><span className="truncate" title={g.name}>{g.name.replace(/^NVIDIA GeForce |^AMD Radeon\(TM\) /, "")}</span><span>usage</span></div>
              <Meter label="memory" value={(g.vram_used_mb / GB).toFixed(1)} of={`${(g.vram_total_mb / GB).toFixed(1)} GB`} pct={(g.vram_used_mb / g.vram_total_mb) * 100} />
              <Meter label="busy" value={String(Math.round(g.util_pct ?? 0))} unit="%" pct={g.util_pct ?? 0} />
            </> : <p className="text-mute">No graphics card reading yet; models run on the processor.</p>}
          </div>
          {agent === "local" && !engine && !aside && (
            <button className="chip w-full justify-center" onClick={onModels}>START A MODEL (MODELS)</button>
          )}
        </div>
      </section>

      <div className="flex min-h-0 flex-col gap-1.5">
        <div className="kicker"><span>Agents</span><span>switch</span></div>
        <AgentSlot active={agent === "local"} name="Local model" detail="private, works offline" onClick={() => setAgent("local")} />
        {claudeReady
          ? <AgentSlot active={agent === "claude"} name="Claude Code" detail="plans and edits files" tone="claude" onClick={() => setAgent("claude")} />
          : <AgentSlot empty name="Connect Claude" detail="sign in once" onClick={onConnectClaude} />}
        <AgentSlot empty name="Connect ChatGPT or Gemini" detail="an API key, in MODELS" onClick={onModels} />
      </div>
    </div>
  );
}

function AgentSlot({ name, detail, active, empty, tone, onClick }: {
  name: string; detail: string; active?: boolean; empty?: boolean; tone?: "claude"; onClick: () => void;
}) {
  const look = empty ? "border-dashed border-mute/45 hover:border-mute"
    : tone === "claude" ? (active ? "border-orange/60 bg-orange/10" : "border-orange/25 hover:bg-orange/5")
    : (active ? "border-cyan/60 bg-cyan/10" : "border-cyan/25 hover:bg-cyan/5");
  return (
    <button onClick={onClick} aria-pressed={active} className={`flex items-center gap-2.5 border px-2 py-1.5 text-left transition-colors ${look}`}>
      <span aria-hidden className={`grid h-6 w-6 flex-none place-items-center rounded-full ${empty
        ? "border border-dashed border-mute/60 text-mute"
        : tone === "claude" ? "bg-orange/70 shadow-[0_0_12px_var(--color-orange)]" : "bg-cyan/70 shadow-[0_0_12px_var(--color-cyan)]"}`}>{empty ? "+" : ""}</span>
      <span className="min-w-0">
        <span className={`display block text-[13px] ${empty ? "text-mute" : tone === "claude" ? "text-orange" : "text-cyan"}`}>{name}</span>
        <span className="copy block truncate text-[11.5px] text-mute">{detail}</span>
      </span>
    </button>
  );
}

/** Centre, top: search the library (notes and source files) as you type; or ask the local model. */
export function LibrarySearch({ panels, onOpenNote, onOpenSource, onAsk }: {
  panels: Panels; onOpenNote: (ref: string) => void; onOpenSource: (doc: { source: string; path: string }) => void;
  onAsk: (q: string) => void;
}) {
  const [q, setQ] = useState("");
  const [notes, setNotes] = useState<SearchResult | null>(null);
  const [files, setFiles] = useState<SourceHit[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const box = useRef<HTMLInputElement>(null);
  const query = q.trim();

  useEffect(() => {      // Ctrl+K anywhere puts you in the search box
    const key = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); box.current?.focus(); } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (!query) { setNotes(null); setFiles(null); setErr(null); return; }
    let alive = true;
    const t = setTimeout(() => {
      get<SearchResult>(`/api/vault/search?q=${encodeURIComponent(query)}`).then((r) => { if (alive) { setNotes(r); setErr(null); } }).catch((e) => alive && setErr(String(e.message ?? e)));
      get<{ results: SourceHit[] }>(`/api/sources/search?q=${encodeURIComponent(query)}`).then((r) => alive && setFiles(r.results)).catch(() => alive && setFiles([]));
    }, 160);
    return () => { alive = false; clearTimeout(t); };
  }, [query]);

  const count = panels.vault?.count ?? 0;
  const fileCount = (panels.sources?.sources ?? []).reduce((n, s) => n + (s.files ?? 0), 0);
  const close = () => setQ("");
  const loading = !!query && notes === null && !err;

  return (
    <div className="relative flex-none" data-tour="search">
      <section className="panel" style={{ flex: "none" }}>
      <div className="panel-head">
        <span className="tab">Search</span>
        <span className="ml-auto flex items-baseline gap-3 normal-case tracking-normal text-mute">
          <span><Num className="text-[16px]">{count}</Num> notes</span>
          {fileCount > 0 && <span><Num className="text-[16px]">{fileCount}</Num> files</span>}
        </span>
      </div>
      <label className="flex items-center gap-3 px-3.5 py-2.5 focus-within:bg-cyan/5">
        <span aria-hidden className="glow-cyan font-dot text-[16px]">&gt;</span>
        <input ref={box} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search your notes and files, or ask a question"
          onKeyDown={(e) => {
            if (e.key === "Escape") { e.stopPropagation(); close(); }
            if (e.key === "Enter" && query) { onAsk(query); close(); }
          }}
          placeholder="Search your notes and files, or ask a question"
          className="copy min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-mute" />
        <span className="chip mute hidden sm:inline-flex">CTRL K</span>
      </label>
      <div className="border-t border-dashed border-cyan/10 px-3.5 py-1 text-[11px] uppercase tracking-[.16em] text-mute">Enter asks your agent · results open in the Library</div>
      </section>
      {query && (
        <div className="panel absolute inset-x-0 top-[calc(100%+4px)] z-20 max-h-[60vh] overflow-auto" style={{ flex: "none" }} role="listbox" aria-label="Search results">
          <div className="panel-body flex flex-col gap-1">
            <button className="card text-left" onClick={() => { onAsk(query); close(); }}>
              <span className="text-cyan">Ask about it:</span> <span className="copy text-ink">"{query}"</span>
            </button>
            {err && <div className="text-red">{err}</div>}
            {loading && <div className="text-mute">searching<span className="dots" /></div>}
            {notes && notes.results.length === 0 && (files?.length ?? 0) === 0 && <div className="py-2 text-mute">Nothing in your notes or files matches. Enter asks the agent anyway.</div>}
            {notes && notes.results.slice(0, 8).map((h) => (
              <button key={h.ref} className="card text-left" onClick={() => { onOpenNote(h.ref); close(); }}>
                <div className="flex items-baseline gap-2"><span className="copy min-w-0 flex-1 truncate text-[13.5px] text-ink">{h.title}</span><span className="text-[11px] text-mute">note · {h.folder}</span></div>
                {h.snippet && <div className="copy mt-0.5 line-clamp-2 text-[12px] text-ink/70"><Snippet text={h.snippet} /></div>}
              </button>
            ))}
            {files && files.slice(0, 5).map((h) => (
              <button key={h.source + h.path} className="card text-left" onClick={() => { onOpenSource({ source: h.source, path: h.path }); close(); }}>
                <div className="flex items-baseline gap-2"><span className="copy min-w-0 flex-1 truncate text-[13.5px] text-ink">{h.title}</span><span className="text-[11px] text-mute">file · {h.source}</span></div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Right: the digest in progress and the latest notes. (The inbox sits above them.) */
export function DigestStrip({ panels }: { panels: Panels }) {
  const jobs = (panels.digests?.jobs ?? []).filter((j) => j.status === "running" || j.status === "paused");
  if (!jobs.length) return null;
  return (
    <section className="panel" style={{ flex: "none" }}>
      <div className="panel-head"><span className="tab">Digesting</span></div>
      <div className="panel-body flex flex-col gap-2">
        {jobs.map((j) => {
          const pct = j.chapters_total ? (j.chapters_done / j.chapters_total) * 100 : 0;
          const drafted = (j.counts.drafted ?? 0) + (j.counts.empty ?? 0);      // failed sections aren't drafted
          const failed = j.counts.failed ?? 0;
          return (
            <div key={j.id}>
              <Row k="Book" v={j.title.replace(/_/g, " ").split(" -- ")[0]} />
              <Row k="Sections" v={`${drafted} / ${j.sections_total} drafted${failed ? `, ${failed} failed` : ""}`} hot={failed > 0} />
              <div className="mt-2"><Meter label={j.status === "paused" ? "chapters out · paused" : "chapters out for review"} value={String(j.chapters_done)} of={String(j.chapters_total)} pct={pct} /></div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** "Books/Intermediate_Accounting__18th_Edition_…/Chapter 7 Valuation of Inventories" -> "Books · Chapter 7 Valuation of Inventories" */
function shelf(folder: string): string {
  const parts = folder.split("/").filter(Boolean);
  if (parts.length <= 1) return folder;
  return `${parts[0]} · ${parts[parts.length - 1].replace(/_+/g, " ").trim()}`;
}

export function RecentNotes({ panels, onOpenNote, onLibrary }: { panels: Panels; onOpenNote: (ref: string) => void; onLibrary: () => void }) {
  const now = useNow(60000);
  const notes = useMemo(() => [...(panels.vault?.notes ?? [])].filter((n) => !n.archived)
    .sort((a, b) => (Date.parse(b.updated ?? b.created ?? "") || 0) - (Date.parse(a.updated ?? a.created ?? "") || 0)).slice(0, 6), [panels.vault?.notes]);
  return (
    <section className="panel min-h-0">
      <div className="panel-head"><span className="tab">Recent notes</span><button className="chip mute ml-auto normal-case tracking-normal" onClick={onLibrary}>library</button></div>
      <div className="panel-body">
        {notes.length === 0 && <p className="text-mute">No notes yet. Add documents in Library, or approve a proposal from the inbox.</p>}
        {notes.map((n) => {
          const when = Date.parse(n.updated ?? n.created ?? "");
          return (
            <button key={n.ref} onClick={() => onOpenNote(n.ref)} className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-b border-dashed border-cyan/10 px-0.5 py-1.5 text-left hover:bg-cyan/5">
              <span className="copy truncate text-[13.5px] text-ink">{n.title}</span>
              <span className="row-span-2 self-center">{when ? <Ago ts={when / 1000} now={now} /> : null}</span>
              <span className="truncate text-[11px] uppercase tracking-[.12em] text-mute" title={n.folder}>{shelf(n.folder)}{n.origin === "agent" ? " · by an agent" : ""}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

/** Bottom: the machine in one line; the full dashboard is under Systems. */
export function SystemsStrip({ panels, onSystems }: { panels: Panels; onSystems: () => void }) {
  const g = panels.gpu?.gpu;
  const e = panels.engine?.serving;
  const game = panels.gamemode;
  const lib = panels.vault;
  const hermes = panels.health?.gateway.state;
  const item = (k: string, v: React.ReactNode) => (
    <span className="flex items-baseline gap-2"><span className="text-[11px] uppercase tracking-[.16em] text-mute">{k}</span><span className="font-mono text-[12px] text-ink/90">{v}</span></span>
  );
  return (
    <section className="panel flex-wrap items-center gap-x-6 gap-y-1 px-3.5 py-1.5 text-[12px]" style={{ flex: "none", flexDirection: "row" }} data-tour="systems-strip">
      {g && (
        <span className="flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-[.16em] text-mute">GPU</span>
          <span className="vram-bar w-20"><span className={`vram-fill ${g.vram_used_mb / g.vram_total_mb > .92 ? "hot" : ""}`} style={{ width: `${(g.vram_used_mb / g.vram_total_mb) * 100}%` }} /></span>
          <span className="text-[12px] text-mute"><Num className="text-[15px]">{(g.vram_used_mb / GB).toFixed(1)}</Num> / {(g.vram_total_mb / GB).toFixed(1)} GB</span>
        </span>
      )}
      {item("Engine", e ? <><span className={`light ${e.ready ? "up" : "idle"} mr-1`} />{shortModel(e.id)}</> : <span className="text-mute">off</span>)}
      {game && item("Game mode", game.state === "aside" || game.state === "micro" ? <span className="text-amber">stepped aside</span> : game.mode === "never" ? "off" : "watching")}
      {lib && item("Library", <><Num className="text-[15px]">{lib.count}</Num> notes</>)}
      {hermes && hermes !== "absent" && item("Hermes", hermes === "up" ? "running" : <span className={hermes === "down" ? "text-red" : "text-mute"}>{hermes === "down" ? "stopped" : "not running"}</span>)}
      <button className="chip mute ml-auto" onClick={onSystems}>SYSTEMS: BOARD, GPU, SAFETY</button>
    </section>
  );
}

/** Start a chat with the local model on a question (search's "ask"). -> the new chat's id, or an error to show. */
export async function askLocal(panels: Panels, text: string): Promise<{ id?: string; error?: string }> {
  const e = panels.engine?.serving;
  if (!e?.ready) return { error: "Load a model first (MODELS), or connect a cloud AI." };
  try {
    const s = await post<{ id: string }>("/api/agents/chat/sessions", { provider: "engine", model: e.id });
    await post(`/api/agents/chat/sessions/${s.id}/send`, { text });
    return { id: s.id };
  } catch (err) {
    return { error: String((err as Error).message ?? err) };
  }
}
