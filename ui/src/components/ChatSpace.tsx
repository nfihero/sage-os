import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { get, onChat, post } from "../api";
import type { AI, ChatItem, ChatUsage, EngineModel, EngineState, Panels, Thread, ThreadRow } from "../types";
import type { ConnectSection } from "./Connect";
import { shortModel, useNow } from "../util";
import ChatView from "./ChatView";
import { toItems } from "./LocalPane";
import { Ago, Num } from "./Readout";

/** W3 (D39): one chat space for every AI. A history rail of every conversation (whichever AI it was with), and the
 *  open conversation with a picker that hands the next reply to another AI, who is given the conversation so far.
 *  On a fresh install with no AI at all, the first-run canvas instead. */
export type Answering = { agent: string; label: string; model: string | null; local: boolean } | null;

const DAY = 86400;
const SOLID = { background: "var(--color-cyan)", color: "var(--color-void)" };   // .chip (unlayered) would win over bg-/text- utilities
const isLocal = (label: string) => label.startsWith("Local") || label.startsWith("Ollama");
function dot(agent: string, label: string): string {
  if (agent === "claude") return "bg-orange shadow-[0_0_6px_var(--color-orange)]";
  if (agent.startsWith("hermes:")) return "bg-[#c79bff] shadow-[0_0_6px_#c79bff]";
  if (isLocal(label)) return "bg-cyan shadow-[0_0_6px_var(--color-cyan)]";
  return "bg-[#7cc8ff] shadow-[0_0_6px_#7cc8ff]";
}
const aiKey = (a: { agent: string; provider?: string | null; model?: string | null }) =>
  a.agent === "chat" ? `chat|${a.provider ?? ""}|${a.model ?? ""}` : a.agent;

function group(rows: ThreadRow[], now: number): [string, ThreadRow[]][] {
  const start = new Date(now * 1000); start.setHours(0, 0, 0, 0);
  const today = start.getTime() / 1000;
  const g: Record<string, ThreadRow[]> = { Pinned: [], Today: [], Yesterday: [], "This week": [], Older: [] };
  for (const r of rows) {
    const k = r.pinned ? "Pinned" : r.updated >= today ? "Today" : r.updated >= today - DAY ? "Yesterday"
      : r.updated >= today - 6 * DAY ? "This week" : "Older";
    g[k].push(r);
  }
  return Object.entries(g).filter(([, v]) => v.length);
}

export default function ChatSpace({ panels, openId, onOpen, onAnswering, onModels, onConnect, onUsage, aisVersion }: {
  panels: Panels; openId: string | null; onOpen: (id: string | null) => void; onAnswering: (a: Answering) => void; onModels: () => void;
  onConnect: (s?: ConnectSection) => void; onUsage: () => void; aisVersion: number;
}) {
  const now = useNow(30000);
  const [rows, setRows] = useState<ThreadRow[] | null>(null);
  const [ais, setAis] = useState<AI[] | null>(null);
  const [q, setQ] = useState("");
  const [archived, setArchived] = useState(false);
  const [starting, setStarting] = useState(false);       // the "new chat with…" menu
  const [rail, setRail] = useState(false);                // phone: the history list instead of the conversation
  const [err, setErr] = useState<string | null>(null);

  const loadList = useCallback(() => {
    get<ThreadRow[]>(`/api/threads?q=${encodeURIComponent(q.trim())}&archived=${archived}`).then(setRows).catch((e) => setErr(String(e.message)));
  }, [q, archived]);
  const loadAis = useCallback(() => { get<{ ais: AI[] }>("/api/ais").then((r) => setAis(r.ais)).catch(() => setAis([])); }, []);
  useEffect(() => { const t = setTimeout(loadList, q ? 200 : 0); return () => clearTimeout(t); },
    [loadList, panels.chat, panels.claude, panels.sessions]);
  useEffect(loadAis, [loadAis, aisVersion, panels.engine?.serving?.ready, panels.engine?.serving?.id, panels.claude?.logged_in, panels.claude?.cli]);

  // the newest chat opens by itself, so the home screen never shows an empty conversation
  useEffect(() => { if (!openId && rows && rows.length && !archived && !q) onOpen(rows[0].id); }, [rows]);

  const [folderFor, setFolderFor] = useState<AI | null>(null);    // Claude Code: which folder it works in
  const start = async (ai: AI, cwd?: string) => {
    setErr(null); setStarting(false);
    const spaces = panels.claude?.workspaces ?? [];
    if (ai.agent === "claude" && cwd === undefined && spaces.length > 1) { setFolderFor(ai); return; }
    setFolderFor(null);
    try {
      const t = await post<{ id: string }>("/api/threads", { agent: ai.agent, provider: ai.provider, model: ai.model, cwd: cwd ?? null });
      loadList(); onOpen(t.id);
    } catch (e) { setErr(String((e as Error).message)); }
  };

  const nothing = rows !== null && ais !== null && rows.length === 0 && !q && !archived && ais.filter((a) => a.ready !== false).length === 0;
  useEffect(() => { if (nothing) onAnswering(null); }, [nothing]);
  // the first AI arrived on a fresh install (a model finished setting up, Claude signed in): open a first chat with it
  const wasNothing = useRef(false);
  useEffect(() => {
    if (nothing) { wasNothing.current = true; return; }
    const first = (ais ?? []).find((a) => a.ready !== false && a.agent === "chat") ?? (ais ?? []).find((a) => a.ready !== false);
    if (wasNothing.current && rows?.length === 0 && first) { wasNothing.current = false; start(first); }
  }, [nothing, ais, rows]);
  if (rows !== null && rows.length === 0 && ais === null && !q && !archived) {      // a fresh start: wait for the AI list
    return <section className="panel min-h-0 flex-1"><div className="m-auto text-mute">looking for AIs<span className="dots" /></div></section>;
  }
  if (nothing) return <FirstRun panels={panels} onModels={onModels} onConnect={onConnect} onConnected={loadAis} />;

  return (
    <section className="panel min-h-0 flex-1" style={{ flexDirection: "row" }} data-testid="chat-space">
      <aside className={`flex w-[250px] flex-none flex-col border-r border-cyan/20 ${rail || !openId ? "max-md:w-full max-md:border-r-0" : "max-md:hidden"}`} aria-label="Chat history">
        <div className="panel-head">
          <span className="tab">{archived ? "Archive" : "Chats"}</span>
          <Num className="text-[14px]">{rows?.length ?? ""}</Num>
        </div>
        <div className="relative flex gap-1.5 px-2.5 pb-1.5 pt-2.5">
          <button className="chip h-7 flex-1 justify-center font-semibold" style={SOLID} onClick={() => setStarting(!starting)}
            aria-haspopup="menu" aria-expanded={starting}>+ NEW CHAT</button>
          <button className={`chip h-7 ${archived ? "" : "mute"}`} onClick={() => { setArchived(!archived); onOpen(null); }}
            title={archived ? "Back to your chats" : "Archived chats"}>{archived ? "← CHATS" : "ARCHIVE"}</button>
          {starting && <AiMenu ais={ais ?? []} title="New chat with" onPick={(a) => start(a)} onClose={() => setStarting(false)} onConnect={onConnect} />}
          {folderFor && (
            <div role="menu" className="absolute left-2.5 top-[calc(100%+2px)] z-30 w-[300px] border border-orange/50 bg-[#020f07] p-1.5">
              <div className="kicker mx-1 mb-1"><span>Claude Code works in</span><button onClick={() => setFolderFor(null)}>✕</button></div>
              {(panels.claude?.workspaces ?? []).map((w) => (
                <button key={w} role="menuitem" className="block w-full truncate px-2 py-1.5 text-left font-mono text-[12px] text-ink hover:bg-orange/10"
                  title={w} onClick={() => start(folderFor, w)}>{w.split(/[\\/]/).slice(-2).join("/")}</button>
              ))}
            </div>
          )}
        </div>
        <label className="mx-2.5 mb-1.5 flex items-center gap-1.5 border border-cyan/25 px-2 py-1 focus-within:border-cyan">
          <span className="text-mute" aria-hidden>⌕</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search chats" aria-label="Search chats"
            className="copy min-w-0 flex-1 bg-transparent text-[12.5px] text-ink outline-none placeholder:text-mute" />
        </label>
        <div className="min-h-0 flex-1 overflow-auto px-1.5 pb-2">
          {rows === null && <p className="px-2 text-mute">loading…</p>}
          {rows?.length === 0 && <p className="copy px-2 py-2 text-[12px] text-mute">{q ? "No chat matches." : archived ? "Nothing archived." : "No chats yet. Start one above."}</p>}
          {rows && group(rows, now).map(([name, list]) => (
            <div key={name}>
              <div className="display mx-1.5 mb-1 mt-2.5 text-[10.5px] tracking-[.2em] text-mute">{name}</div>
              {list.map((r) => (
                <button key={r.id} onClick={() => { onOpen(r.id); setRail(false); }} aria-current={r.id === openId}
                  className={`grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-px border-l-2 px-1.5 py-1.5 text-left ${r.id === openId ? "border-cyan bg-cyan/10" : "border-transparent hover:bg-cyan/5"}`}>
                  <span className={`h-2 w-2 rounded-full ${dot(r.current.agent, r.current.label)} ${r.busy ? "pulse-amber" : ""}`} aria-hidden />
                  <span className="copy truncate text-[13px] text-ink">{r.title}</span>
                  <Ago ts={r.updated} now={now} />
                  <span />
                  <span className="col-span-2 truncate text-[10.5px] text-mute">
                    {r.pinned && <span className="text-amber">★ </span>}{r.snippet ?? (r.ais.length > 1 ? r.ais.join(" → ") : r.current.label)}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </aside>
      <div className={`relative flex min-h-0 min-w-0 flex-1 flex-col ${rail || !openId ? "max-md:hidden" : ""}`}>
        {err && <div className="mx-3 mt-2 border border-amber/50 px-2 py-1 text-[12px] text-amber">{err}</div>}
        {openId
          ? <Conversation key={openId} id={openId} ais={ais ?? []} onChanged={loadList} onAnswering={onAnswering} onConnect={onConnect} onUsage={onUsage} onRail={() => setRail(true)}
              onGone={() => onOpen(null)} />
          : <div className="m-auto max-w-[420px] p-6 text-center">
              <p className="copy text-[14px] text-ink/80">Pick a chat on the left, or start a new one with any AI you have.</p>
              <button className="chip mt-3 h-8 px-4" onClick={() => setStarting(true)}>+ NEW CHAT</button>
            </div>}
      </div>
    </section>
  );
}

/** Every AI there is to talk to, for a new chat or the next reply. */
function AiMenu({ ais, title, current, onPick, onClose, onConnect }: {
  ais: AI[]; title: string; current?: string; onPick: (ai: AI) => void; onClose: () => void; onConnect: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) onClose(); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    setTimeout(() => document.addEventListener("mousedown", away));
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, []);
  return (
    <div ref={box} role="menu" className="absolute left-2.5 top-[calc(100%+2px)] z-30 w-[300px] border border-cyan/45 bg-[#020f07] p-1.5 shadow-[0_12px_40px_rgba(0,0,0,.6)]">
      <div className="kicker mx-1 mb-1"><span>{title}</span><span>{ais.length ? "" : "none yet"}</span></div>
      {ais.map((a) => {
        const off = a.ready === false;
        return (
          <button key={aiKey(a)} role="menuitem" disabled={off} onClick={() => onPick(a)}
            className={`grid w-full grid-cols-[auto_1fr_auto] items-center gap-x-2.5 px-2 py-1.5 text-left hover:bg-cyan/10 disabled:opacity-45 ${current === aiKey(a) ? "bg-cyan/10" : ""}`}>
            <span className={`h-2 w-2 rounded-full ${dot(a.agent, a.label)}`} aria-hidden />
            <span className="copy truncate text-[13px] text-ink">{a.agent === "chat" ? shortModel(a.model ?? "") : a.label}</span>
            <span className="text-[10.5px] text-mute">{off ? "sign in first" : a.where}</span>
          </button>
        );
      })}
      <div className="my-1 border-t border-dashed border-cyan/20" />
      <button role="menuitem" className="w-full px-2 py-1.5 text-left text-[12px] text-mute hover:bg-cyan/10" onClick={() => { onClose(); onConnect(); }}>
        Install or connect another… <span className="float-right">CONNECT</span>
      </button>
    </div>
  );
}

function Conversation({ id, ais, onChanged, onAnswering, onConnect, onUsage, onGone, onRail }: {
  id: string; ais: AI[]; onChanged: () => void; onAnswering: (a: Answering) => void; onConnect: () => void; onUsage: () => void; onGone: () => void;
  onRail: () => void;
}) {
  const [t, setT] = useState<Thread | null>(null);
  const [live, setLive] = useState("");
  const [busy, setBusy] = useState(false);
  const [next, setNext] = useState<AI | null>(null);        // another AI picked for the next reply
  const [picking, setPicking] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => get<Thread>(`/api/threads/${id}`).then((x) => { setT(x); setBusy(x.parts[x.parts.length - 1]?.busy ?? false); })
    .catch((e) => { if (String(e.message).includes("no such")) onGone(); else setErr(String(e.message)); }), [id]);
  useEffect(() => { setT(null); setLive(""); setNext(null); load(); }, [id]);

  const cur = t?.parts[t.parts.length - 1];
  const hermes = !!cur?.agent.startsWith("hermes:");
  useEffect(() => {
    if (!cur) return;
    onAnswering({ agent: (next ?? cur).agent, label: (next ?? cur).label, model: (next ?? cur).model, local: isLocal((next ?? cur).label) });
  }, [cur?.agent, cur?.label, next]);
  useEffect(() => {
    if (!cur?.pane) return;
    return onChat((f) => {
      if (f.pane !== cur.pane) return;
      if (f.op === "delta") { setLive((l) => l + f.text); setBusy(true); }
      else if (f.op === "item") {
        setT((x) => x && { ...x, parts: x.parts.map((p, i) => i === x.parts.length - 1 ? { ...p, items: [...p.items, f.item] } : p) });
        if (f.item.kind === "text" || f.item.kind === "tool_use" || f.item.data?.turn_end) setLive("");
        if (f.item.data?.turn_end) { setBusy(false); onChanged(); }
      } else if (f.op === "status") {
        const done = f.status === "idle";
        setBusy(!done);
        if (done) { setLive(""); load(); onChanged(); }
      } else if (f.op === "error") { setBusy(false); load(); }
    });
  }, [cur?.pane]);

  // every part's messages in order, with a line where another AI took over
  const items = useMemo<ChatItem[]>(() => {
    if (!t) return [];
    const out: ChatItem[] = [];
    t.parts.forEach((p, i) => {
      if (i > 0) out.push({ id: `switch-${i}`, ts: p.started, kind: "note", data: { text: `${p.label} took over here · it was given the conversation so far` } });
      if (p.error) out.push({ id: `err-${i}`, ts: p.started, kind: "error", data: { text: p.error } });
      out.push(...(p.agent.startsWith("hermes:") ? toItems(p.items) : p.items as ChatItem[]));
    });
    return out;
  }, [t]);

  if (!t || !cur) return <div className="p-4 text-mute">{err ?? "loading…"}</div>;
  const edit = async (body: Record<string, unknown>) => {
    setErr(null);
    try { await post(`/api/threads/${id}/edit`, body); await load(); onChanged(); } catch (e) { setErr(String((e as Error).message)); }
  };
  const showAi = next ?? cur;
  const claude = showAi.agent === "claude";
  const banner = (
    <div className="relative flex flex-wrap items-center gap-2 border-b border-cyan/20 px-3 py-1.5">
      <div className="md:hidden"><button className="chip h-7" onClick={onRail} aria-label="Your chats">☰ CHATS</button></div>
      <button onClick={() => setPicking(!picking)} aria-haspopup="menu" aria-expanded={picking}
        className="copy flex h-7 items-center gap-2 border border-cyan/40 bg-void/80 px-2.5 text-[12.5px] text-ink hover:border-cyan"
        title="Which AI answers the next message">
        <span className={`h-2 w-2 rounded-full ${dot(showAi.agent, showAi.label)}`} aria-hidden />
        {showAi.label}<span className="text-mute">▾</span>
      </button>
      {next && <span className="text-[11px] text-amber">next reply · <button className="underline" onClick={() => setNext(null)}>keep {cur.label}</button></span>}
      {renaming !== null
        ? <input autoFocus value={renaming} onChange={(e) => setRenaming(e.target.value)} aria-label="chat title"
            onKeyDown={(e) => { if (e.key === "Enter") { edit({ title: renaming }); setRenaming(null); } if (e.key === "Escape") setRenaming(null); }}
            onBlur={() => setRenaming(null)}
            className="copy min-w-0 flex-1 border border-cyan/40 bg-void/80 px-2 py-0.5 text-[13px] text-ink outline-none" />
        : <span className="copy min-w-0 flex-1 truncate text-[13px] text-mute" title={t.title}>{t.title}</span>}
      <span className="flex gap-1.5">
        <Spend u={t.usage} onClick={onUsage} />
        <button className="chip mute" onClick={() => setRenaming(t.title)}>RENAME</button>
        <button className={`chip ${t.pinned ? "amber" : "mute"}`} onClick={() => edit({ pinned: !t.pinned })}>{t.pinned ? "★ PINNED" : "☆ PIN"}</button>
        <button className="chip mute" onClick={() => edit({ archived: !t.archived })}>{t.archived ? "UNARCHIVE" : "ARCHIVE"}</button>
      </span>
      {picking && (
        <AiMenu ais={ais.filter((a) => a.switch_into !== false || aiKey(a) === aiKey(cur))} title="Answer with" current={aiKey(showAi)}
          onPick={(a) => { setPicking(false); setNext(aiKey(a) === aiKey(cur) ? null : a); }} onClose={() => setPicking(false)} onConnect={onConnect} />
      )}
      {err && <span className="w-full text-[11.5px] text-red">{err}</span>}
    </div>
  );
  return (
    <ChatView items={items} live={live} busy={busy} tone={claude ? "orange" : "cyan"} banner={banner} chat={cur.pane}
      placeholder={`Message ${showAi.agent === "chat" ? shortModel(showAi.model ?? "") : showAi.label}… (Enter to send)`}
      onSend={async (text) => {
        const switching = next;
        await post(`/api/threads/${id}/send`, switching ? { text, ai: { agent: switching.agent, provider: switching.provider, model: switching.model } } : { text });
        setBusy(true);
        if (switching) { setNext(null); await load(); }
        onChanged();
      }}
      onStop={hermes ? undefined : () => { post(`/api/agents/${cur.agent}/sessions/${cur.sid}/interrupt`).catch(() => {}); }} />
  );
}

/** A fresh install (D39): nothing to talk to yet. Install the model that fits this computer best and start, or connect
 *  an AI the user already has. The app's own helpers (llama.cpp, the search model) arrive by themselves underneath. */
function FirstRun({ panels, onModels, onConnect, onConnected }: {
  panels: Panels; onModels: () => void; onConnect: (s: ConnectSection) => void; onConnected: () => void;
}) {
  const [eng, setEng] = useState<EngineState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { get<EngineState>("/api/engine").then(setEng).catch(() => setEng(null)); }, [panels.engine]);
  const setup = eng?.setup;
  useEffect(() => { if (setup?.error) setBusy(null); }, [setup?.error]);     // a failed setup can be tried again
  // when the model is up, the AI list changes and the chat space opens a first chat with it (see ChatSpace)

  const models = (eng?.catalog ?? []).filter((m) => !(m as any).micro);
  const order = { fits: 0, tight: 1, "too big": 2 } as const;
  // the best first model: the largest that fits and downloads in reasonable time; else the smallest that fits or nearly
  const fits = models.filter((m) => m.fit === "fits");
  const rec = [...fits].filter((m) => m.size <= 8e9).sort((a, b) => b.size - a.size)[0]
    ?? [...fits].sort((a, b) => a.size - b.size)[0]
    ?? [...models].filter((m) => m.fit === "tight").sort((a, b) => a.size - b.size)[0];
  const others = models.filter((m) => m !== rec).sort((a, b) => order[a.fit] - order[b.fit] || a.size - b.size).slice(0, 4);
  const hw = eng?.hardware;
  const go = async (m: EngineModel) => {
    setErr(null); setBusy(m.id);
    try { await post("/api/engine/setup", { model: m.id }); } catch (e) { setErr(String((e as Error).message)); setBusy(null); }
  };
  const ollama = async () => {
    setErr(null);
    const r = await post<{ found: boolean }>("/api/providers/find-ollama").catch(() => ({ found: false }));
    setNote(r.found ? null : "Ollama isn't running here. Start it, then press this again.");
    onConnected();
  };
  const job = (k: string) => eng?.jobs?.[k];
  const pct = (k: string) => { const j = job(k); return j && j.total ? Math.round((j.done / j.total) * 100) : 0; };
  const s = panels.semantic;
  const step = setup && !setup.error && setup.step !== "ready" ? setup : null;

  return (
    <section className="panel min-h-0 flex-1" data-testid="first-run">
      <div className="panel-head"><span className="tab">Start</span><span className="normal-case tracking-normal text-mute">nothing installed yet</span></div>
      <div className="panel-body flex flex-col gap-5 px-6 py-6">
        <div>
          <h1 className="display m-0 text-[28px] normal-case tracking-[.06em] text-ink">Give Sage a mind, then say hello.</h1>
          <p className="copy mt-2 max-w-[620px] text-[14.5px] text-ink/80">Sage OS runs AI models on this computer, privately, or talks to the AIs you
            already use. Pick one to start; you can add others any time, and every chat keeps its history here.</p>
        </div>
        {hw && (
          <div className="flex flex-wrap gap-x-6 gap-y-1 border border-dashed border-cyan/25 px-3 py-2 text-[12px]">
            <span><span className="kicker !m-0 !inline">This computer </span>{({ windows: "Windows", darwin: "macOS", macos: "macOS", linux: "Linux" } as Record<string, string>)[hw.os] ?? hw.os} · {Math.round(hw.ram_gb)} GB memory</span>
            <span><span className="kicker !m-0 !inline">Graphics </span>{hw.gpu ? `${hw.gpu.name.replace(/^NVIDIA GeForce |^AMD Radeon\(TM\) /, "")} · ${hw.gpu.vram_gb} GB` : "none: models run on the processor"}</span>
          </div>
        )}
        {step ? (
          <div className="border border-cyan bg-cyan/5 p-4" role="status">
            <div className="display text-[18px] tracking-[.06em] text-ink">Setting up {rec && step.model === rec.id ? rec.label : step.model}…</div>
            <div className="copy mt-2 text-[13px] text-ink/80">
              {step.step === "engine" && <>Getting llama.cpp, the program that runs models: <Num className="text-[14px]">{pct("binary")}</Num>%</>}
              {step.step === "model" && <>Downloading the model: <Num className="text-[14px]">{pct(`model:${step.model}`)}</Num>% of {Math.round((job(`model:${step.model}`)?.total ?? 0) / 1e9 * 10) / 10} GB</>}
              {(step.step === "start" || step.step === "loading") && <>Loading it into memory; your first chat opens when it's ready.</>}
            </div>
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            {rec ? (
              <div className="relative border border-cyan bg-cyan/5 p-4 shadow-[0_0_28px_rgba(61,255,139,.12)]">
                <span className="display absolute -top-2.5 left-3 bg-cyan px-2 text-[11px] tracking-[.18em] text-void">BEST FIT FOR THIS COMPUTER</span>
                <div className="display mt-1 text-[22px] tracking-[.06em] text-ink">{rec.label}</div>
                <p className="copy mb-3 mt-1 text-[13.5px] text-ink/80">{rec.note ? `${rec.note[0].toUpperCase()}${rec.note.slice(1)}. ` : ""}Runs on this computer; nothing you ask leaves it.</p>
                <div className="mb-3 flex gap-5 text-[11px] text-mute">
                  <span><Num className="block text-[18px]">{(rec.size / 1e9).toFixed(1)}</Num>GB download</span>
                  <span><Num className="block text-[18px]">{rec.need_gb}</Num>GB of memory</span>
                </div>
                <button className="chip h-8 px-4 font-semibold" style={SOLID} disabled={!!busy} onClick={() => go(rec)}>INSTALL AND START →</button>
              </div>
            ) : <p className="copy text-mute">{eng ? "No model in the catalog fits this computer; connect an AI below." : "Looking at this computer…"}</p>}
            <div>
              <div className="kicker"><span>Other models</span><span>fit</span></div>
              {others.map((m) => (
                <div key={m.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 border-b border-cyan/10 py-1.5">
                  <span className="copy truncate text-[13px] text-ink">{m.label}</span>
                  <span className={`row-span-2 text-[10.5px] uppercase tracking-[.1em] ${m.fit === "fits" ? "text-cyan" : m.fit === "tight" ? "text-amber" : "text-mute"}`}>{m.fit}</span>
                  <button className="chip mute row-span-2" disabled={!!busy || m.fit === "too big"} onClick={() => go(m)}>install</button>
                  <span className="text-[10.5px] text-mute">{(m.size / 1e9).toFixed(1)} GB{m.note ? ` · ${m.note}` : ""}</span>
                </div>
              ))}
              <button className="chip mute mt-2" onClick={onModels}>ALL MODELS →</button>
            </div>
          </div>
        )}
        {setup?.error && <div className="border border-amber/50 px-3 py-2 text-[12.5px] text-amber">Setup stopped: {setup.error}</div>}
        <div>
          <div className="kicker"><span>Or connect an AI you already use</span><span>bring your own</span></div>
          <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(190px,1fr))]">
            <Connect dot="bg-orange" name="Claude Code" detail="sign in with your Claude plan" onClick={() => onConnect("claude")} />
            <Connect dot="bg-[#7cc8ff]" name="ChatGPT" detail="paste an OpenAI API key" onClick={() => onConnect("openai")} />
            <Connect dot="bg-[#c79bff]" name="Gemini" detail="paste a Google AI key (free tier)" onClick={() => onConnect("gemini")} />
            <Connect dot="bg-cyan" name="Ollama" detail="running here? found automatically" onClick={ollama} />
          </div>
          {note && <p className="copy mt-2 text-[12.5px] text-amber">{note}</p>}
          {err && <p className="mt-2 text-[12.5px] text-red">{err}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-dashed border-cyan/15 pt-3 text-[11.5px] text-mute">
          <span className="display tracking-[.18em]">GETTING SAGE READY</span>
          <span>llama.cpp {eng?.binary ? "✓" : job("binary") ? <><Num className="text-[13px]">{pct("binary")}</Num>%</> : "…"}</span>
          <span>search model {s?.installed ? "✓" : s?.download ? <><Num className="text-[13px]">{s.download.total ? Math.round((s.download.done / s.download.total) * 100) : 0}</Num>%</> : "…"}</span>
          {!s?.installed && <span>search works by words until it's done</span>}
        </div>
      </div>
    </section>
  );
}

function Connect({ dot: d, name, detail, onClick }: { dot: string; name: string; detail: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-center gap-2.5 border border-dashed border-mute/55 px-3 py-2.5 text-left hover:border-solid hover:border-cyan">
      <span className={`h-2 w-2 flex-none rounded-full ${d}`} aria-hidden />
      <span className="min-w-0"><span className="display block text-[13px] tracking-[.1em] text-ink">{name}</span>
        <span className="copy block truncate text-[11.5px] text-mute">{detail}</span></span>
    </button>
  );
}

/** What this chat has used (D40): tokens, and what they cost (API keys), were worth (Claude plan) or nothing (this computer). */
function Spend({ u, onClick }: { u?: ChatUsage; onClick: () => void }) {
  if (!u || u.tokens_in + u.tokens_out === 0) return null;
  const k = (n: number) => n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(n);
  const money = (n: number) => n < 0.01 ? (n > 0 ? "<$0.01" : "$0") : `$${n.toFixed(2)}`;
  const parts = [`${k(u.tokens_in + u.tokens_out)} tokens${u.estimated ? " (some estimated)" : ""}`];
  if (u.billing.includes("api")) parts.push(u.priced ? money(u.cost) : `${money(u.cost)}+ (a model has no price)`);
  if (u.billing.includes("plan")) parts.push(`plan · API value ${money(u.plan_value ?? 0)}`);
  if (u.billing.length === 1 && u.billing[0] === "free") parts.push("free");
  return <button className="chip mute" onClick={onClick} data-testid="chat-spend"
    title={`${u.tokens_in.toLocaleString()} in · ${u.tokens_out.toLocaleString()} out. Click for usage and costs.`}>{parts.join(" · ")}</button>;
}
