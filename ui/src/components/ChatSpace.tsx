import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { get, onChat, post } from "../api";
import type { AI, ChatItem, ChatUsage, EngineModel, EngineState, Panels, Thread, ThreadRow } from "../types";
import type { ConnectSection } from "./Connect";
import { fitWords, goodFor, shortModel, useNow } from "../util";
import AddDocs from "./AddDocs";
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

export default function ChatSpace({ panels, openId, onOpen, onAnswering, onModels, onConnect, onUsage, aisVersion, pickAsk, onPickDone }: {
  panels: Panels; openId: string | null; onOpen: (id: string | null) => void; onAnswering: (a: Answering) => void; onModels: () => void;
  onConnect: (s?: ConnectSection) => void; onUsage: () => void; aisVersion: number; pickAsk: boolean; onPickDone: () => void;
}) {
  const now = useNow(30000);
  const [rows, setRows] = useState<ThreadRow[] | null>(null);
  const [ais, setAis] = useState<AI[] | null>(null);
  const [q, setQ] = useState("");
  const [archived, setArchived] = useState(false);
  const [inArchive, setInArchive] = useState(0);          // shown when the chat list is empty (Mac test, D42)
  const [starting, setStarting] = useState(false);       // the "new chat with…" menu
  const [rail, setRail] = useState(false);                // phone: the history list instead of the conversation
  const [err, setErr] = useState<string | null>(null);

  const loadList = useCallback(() => {
    get<ThreadRow[]>(`/api/threads?q=${encodeURIComponent(q.trim())}&archived=${archived}`).then((r) => {
      setRows(r);
      if (!archived && r.length === 0) get<ThreadRow[]>("/api/threads?archived=true").then((a) => setInArchive(a.length)).catch(() => {});
    }).catch((e) => setErr(String(e.message)));
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
  // the left card's "Switch or connect an AI" (D42): no chat open -> the "new chat with" menu; nothing at all -> CONNECT
  // a request survives this panel mounting later (on a phone the chat appears only once Home is shown)
  useEffect(() => {
    if (!pickAsk || rows === null || ais === null) return;
    if (nothing) { onPickDone(); onConnect(); }
    else if (!openId) { onPickDone(); setStarting(true); }      // else the open conversation takes it
  }, [pickAsk, rows === null, ais === null, openId]);
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
          {rows?.length === 0 && <p className="copy px-2 py-2 text-[12px] text-mute">{q ? "No chat matches." : archived ? "Nothing archived." : inArchive ? "" : "No chats yet. Start one above."}</p>}
          {rows?.length === 0 && !q && !archived && inArchive > 0 && (
            <button className="copy mx-2 text-left text-[12px] text-amber hover:underline" onClick={() => setArchived(true)}>
              No chats here, but {inArchive} {inArchive === 1 ? "is" : "are"} in the Archive. Show {inArchive === 1 ? "it" : "them"} →</button>
          )}
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
          ? <Conversation key={openId} id={openId} ais={ais ?? []} onChanged={loadList} onAnswering={onAnswering} onConnect={onConnect} onUsage={onUsage} pickAsk={pickAsk} onPickDone={onPickDone} onRail={() => setRail(true)}
              onGone={() => onOpen(null)} />
          : <div className="m-auto max-w-[420px] p-6 text-center">
              <p className="copy text-[14px] text-ink/80">Pick a chat on the left, or start a new one with any AI you have.</p>
              <button className="chip mt-3 h-8 px-4" onClick={() => setStarting(true)}>+ NEW CHAT</button>
            </div>}
      </div>
    </section>
  );
}

/** Where an AI runs, grouped the way a person thinks about it (D50): what it costs and who sees the questions. */
type Group = { key: string; name: string; hint: string; connect?: ConnectSection };
const GROUPS: Group[] = [
  { key: "computer", name: "On this computer", hint: "free · private · works offline", connect: "computer" },
  { key: "claude", name: "Claude", hint: "your Claude plan", connect: "claude" },
  { key: "openai", name: "ChatGPT", hint: "pay per use, with your API key", connect: "openai" },
  { key: "gemini", name: "Gemini", hint: "free tier, then pay per use", connect: "gemini" },
  { key: "hermes", name: "Hermes", hint: "your Hermes setup" },
];
const ADD_HINT: Record<string, string> = {
  computer: "free and private; a download of a few GB", claude: "sign in with your Claude plan",
  openai: "paste an OpenAI API key", gemini: "paste a free Google AI key",
};
function groupOf(a: AI): string {
  if (a.agent === "claude") return "claude";
  if (a.agent.startsWith("hermes:")) return "hermes";
  if (a.provider === "engine" || a.provider === "ollama" || a.kind === "local") return "computer";
  return a.provider ?? a.where;
}
const aiName = (a: AI) => (a.agent === "chat" ? (a.name ?? shortModel(a.model ?? "")) : a.label);

/** Every AI there is to talk to, for a new chat or the next reply (D42, redesigned in D50): grouped by where it runs,
 *  each group saying what it costs; the one answering now on top; a group's extra models one click away inside it;
 *  what isn't set up yet at the bottom. Drawn above every panel, never past the window, arrow keys move through it. */
function AiMenu({ ais, title, current, onPick, onClose, onConnect }: {
  ais: AI[]; title: string; current?: string; onPick: (ai: AI) => void; onClose: () => void; onConnect: (s?: ConnectSection) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number; width: number; maxH: number } | null>(null);
  const [more, setMore] = useState<Record<string, boolean>>({});
  const [q, setQ] = useState("");
  const list = useRef<HTMLDivElement>(null);
  const [below, setBelow] = useState(false);              // more of the list is out of sight: say so
  const look = () => { const el = list.current; setBelow(!!el && el.scrollHeight - el.scrollTop - el.clientHeight > 6); };
  useEffect(() => {
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) onClose(); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    const fit = () => {
      const host = anchor.current?.parentElement?.getBoundingClientRect();
      if (!host) return;
      const width = Math.min(380, window.innerWidth - 16);
      const left = Math.max(8, Math.min(host.left + 10, window.innerWidth - width - 8));
      const top = Math.min(host.bottom + 4, window.innerHeight - 240);
      setPos({ left, top, width, maxH: Math.max(220, window.innerHeight - top - 10) });
    };
    fit();
    const again = setTimeout(fit, 120);                    // once the page around it has settled
    setTimeout(() => document.addEventListener("mousedown", away));
    document.addEventListener("keydown", esc);
    window.addEventListener("resize", fit);
    return () => { clearTimeout(again); document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); window.removeEventListener("resize", fit); };
  }, []);
  useEffect(look);
  useEffect(() => {      // focus the AI answering now (or the first), so the keyboard starts in the right place
    if (!pos) return;
    const el = box.current?.querySelector<HTMLElement>("[data-current=true]:not(:disabled)") ?? box.current?.querySelector<HTMLElement>("[role=menuitem]:not(:disabled)");
    el?.focus({ preventScroll: false });
  }, [!!pos]);
  const keys = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const items = [...(box.current?.querySelectorAll<HTMLElement>("[role=menuitem]:not(:disabled)") ?? [])];
    const i = items.indexOf(document.activeElement as HTMLElement);
    items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length]?.focus();
    e.preventDefault();
  };

  const needle = q.trim().toLowerCase();
  const shown = needle ? ais.filter((a) => `${aiName(a)} ${a.where} ${a.note ?? ""}`.toLowerCase().includes(needle)) : ais;
  const known = new Set(GROUPS.map((g) => g.key));
  const extra: Group[] = [...new Set(shown.map(groupOf))].filter((k) => !known.has(k)).map((k) => ({ key: k, name: shown.find((a) => groupOf(a) === k)?.where ?? k, hint: "" }));
  const groups = [...GROUPS, ...extra].map((g) => ({ g, list: shown.filter((a) => groupOf(a) === g.key) })).filter((x) => x.list.length);
  const missing = GROUPS.filter((g) => g.connect && !ais.some((a) => groupOf(a) === g.key));
  const cur = ais.find((a) => aiKey(a) === current);

  const row = (a: AI) => {
    const off = a.ready === false;
    const on = current === aiKey(a);
    return (
      <button key={aiKey(a)} role="menuitem" disabled={off} data-current={on} onClick={() => onPick(a)}
        className={`group/row flex w-full items-start gap-3 px-3 py-2 text-left outline-none hover:bg-cyan/10 focus-visible:bg-cyan/10 disabled:cursor-not-allowed ${on ? "bg-cyan/[.07]" : ""}`}>
        <span className={`mt-[7px] h-2 w-2 flex-none rounded-full ${off ? "bg-mute/50" : dot(a.agent, a.label)}`} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className={`copy block text-[13.5px] leading-snug [overflow-wrap:anywhere] ${off ? "text-mute" : "text-ink"}`}>{aiName(a)}</span>
          {(a.note || off) && <span className="copy block text-[11.5px] leading-snug text-mute">{off ? "sign in first: CONNECT → Claude Code" : a.note}</span>}
        </span>
        {on && <span className="mt-0.5 flex-none text-[10.5px] uppercase tracking-[.14em] text-cyan">✓ answering</span>}
      </button>
    );
  };

  return <><span ref={anchor} hidden />{pos && createPortal(
    <div ref={box} role="menu" aria-label={title} onKeyDown={keys}
      className="flex flex-col border border-cyan/45 bg-[#020f07] shadow-[0_16px_48px_rgba(0,0,0,.65)]"
      style={{ position: "fixed", left: pos.left, top: pos.top, width: pos.width, maxHeight: pos.maxH, zIndex: 70 }} data-testid="ai-menu">
      <div className="flex items-baseline gap-2 border-b border-cyan/15 px-3 pb-2 pt-2.5">
        <span className="display text-[12px] uppercase tracking-[.16em] text-ink">{title}</span>
        {cur && <span className="copy min-w-0 flex-1 truncate text-right text-[11.5px] text-mute">now: {aiName(cur)}</span>}
      </div>
      {ais.length > 8 && (
        <div className="border-b border-cyan/10 px-3 py-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find an AI or model" aria-label="Find an AI or model"
            onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); box.current?.querySelector<HTMLElement>("[role=menuitem]:not(:disabled)")?.focus(); } }}
            className="copy w-full border border-cyan/25 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
        </div>
      )}
      <div className="relative flex min-h-0 flex-1 flex-col">
      <div ref={list} onScroll={look} className="min-h-0 flex-1 overflow-y-auto py-1">
        {groups.length === 0 && <p className="copy m-0 px-3 py-3 text-[12.5px] text-mute">{needle ? "Nothing matches." : "No AI is ready yet."}</p>}
        {groups.map(({ g, list }) => {
          const top = needle ? list : list.filter((a) => a.first !== false || aiKey(a) === current);
          const rest = needle ? [] : list.filter((a) => !top.includes(a));
          return (
            <section key={g.key} className="pb-1" aria-label={g.name}>
              <div className="flex items-baseline gap-2 px-3 pb-0.5 pt-2">
                <span className="display text-[11.5px] uppercase tracking-[.16em] text-cyan/80">{g.name}</span>
                {g.hint && <span className="copy truncate text-[11px] text-mute">{g.hint}</span>}
              </div>
              {top.map(row)}
              {rest.length > 0 && (more[g.key] ? rest.map(row) : (
                <button role="menuitem" className="copy w-full px-3 py-1.5 pl-8 text-left text-[12px] text-cyan/75 outline-none hover:bg-cyan/10 hover:text-cyan focus-visible:bg-cyan/10"
                  onClick={() => setMore({ ...more, [g.key]: true })}>{rest.length} more {g.name} model{rest.length === 1 ? "" : "s"}</button>
              ))}
            </section>
          );
        })}
      </div>
      {below && <button tabIndex={-1} aria-hidden onClick={() => list.current?.scrollBy({ top: 160, behavior: "smooth" })}
        className="copy absolute inset-x-0 bottom-0 flex h-12 items-end justify-center bg-gradient-to-t from-[#020f07] from-45% to-transparent pb-1.5 text-[11px] text-cyan/80">more below ↓</button>}
      </div>
      <div className="border-t border-dashed border-cyan/20 py-1" data-testid="ai-menu-missing">
        {missing.length > 0 && <div className="display px-3 pb-0.5 pt-1.5 text-[11.5px] uppercase tracking-[.16em] text-mute">Add another AI</div>}
        {missing.map((g) => (
          <button key={g.key} role="menuitem" onClick={() => { onClose(); onConnect(g.connect); }}
            className="flex w-full items-baseline gap-3 px-3 py-1.5 text-left outline-none hover:bg-cyan/10 focus-visible:bg-cyan/10">
            <span className="w-2 flex-none text-center text-cyan" aria-hidden>+</span>
            <span className="copy text-[13px] text-ink/90">{g.name === "On this computer" ? "A model on this computer" : g.name}</span>
            <span className="copy min-w-0 flex-1 truncate text-[11.5px] text-mute">{ADD_HINT[g.key]}</span>
          </button>
        ))}
        <button role="menuitem" onClick={() => { onClose(); onConnect(); }}
          className="copy w-full px-3 py-1.5 pl-8 text-left text-[12px] text-mute outline-none hover:bg-cyan/10 hover:text-ink focus-visible:bg-cyan/10">
          All the ways to connect an AI →</button>
      </div>
    </div>, document.body)}</>;
}

function Conversation({ id, ais, onChanged, onAnswering, onConnect, onUsage, pickAsk, onPickDone, onGone, onRail }: {
  id: string; ais: AI[]; onChanged: () => void; onAnswering: (a: Answering) => void; onConnect: (s?: ConnectSection) => void; onUsage: () => void; pickAsk: boolean; onPickDone: () => void; onGone: () => void;
  onRail: () => void;
}) {
  const [t, setT] = useState<Thread | null>(null);
  const [live, setLive] = useState("");
  const [busy, setBusy] = useState(false);
  const [next, setNext] = useState<AI | null>(null);        // another AI picked for the next reply
  const [picking, setPicking] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [starters, setStarters] = useState<string[]>([]);   // U2: first questions from the person's own documents
  useEffect(() => { if (pickAsk && t) { onPickDone(); setPicking(true); } }, [pickAsk, !!t]);
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

  const empty = !!t && items.length === 0;
  useEffect(() => {
    if (empty) get<{ questions: string[] }>("/api/starters").then((r) => setStarters(r.questions)).catch(() => setStarters([]));
  }, [empty, id]);
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
      {t.archived && <span className="w-full text-[11.5px] text-amber">This chat is in the Archive, so it isn't in your chat list. <button className="underline" onClick={() => edit({ archived: false })}>Put it back</button></span>}
      {err && <span className="w-full text-[11.5px] text-red">{err}</span>}
    </div>
  );
  return (
    <ChatView items={items} live={live} busy={busy} tone={claude ? "orange" : "cyan"} banner={banner} chat={cur.pane} suggestions={starters}
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
  // U2 (D47): start with the starter model, small enough to be answering in minutes; the best fit for this computer
  // (the largest that fits in a reasonable download) is offered as the upgrade for later
  const fits = models.filter((m) => m.fit === "fits");
  const best = [...fits].filter((m) => m.size <= 8e9).sort((a, b) => b.size - a.size)[0]
    ?? [...fits].sort((a, b) => a.size - b.size)[0]
    ?? [...models].filter((m) => m.fit === "tight").sort((a, b) => a.size - b.size)[0];
  const starter = models.find((m) => m.starter && m.fit !== "too big");
  const rec = starter ?? best;
  const later = best && rec && best.id !== rec.id && best.size > rec.size ? best : null;
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
  // time left at the speed so far (U2): "about 3 min left"
  const eta = (k: string) => {
    const j = job(k);
    if (!j || !j.total || !j.done || !j.started) return "";
    const rate = j.done / Math.max(1, Date.now() / 1000 - j.started);
    const left = (j.total - j.done) / Math.max(1, rate);
    return left > 90 ? ` · about ${Math.round(left / 60)} min left` : left > 5 ? " · less than two minutes left" : "";
  };
  const pct = (k: string) => { const j = job(k); return j && j.total ? Math.round((j.done / j.total) * 100) : 0; };
  const s = panels.semantic;
  const step = setup && !setup.error && setup.step !== "ready" ? setup : null;

  return (
    <section className="panel min-h-0 flex-1" data-testid="first-run">
      <div className="panel-head"><span className="tab">Start</span><span className="normal-case tracking-normal text-mute">nothing installed yet</span></div>
      <div className="panel-body flex flex-col gap-5 px-6 py-6">
        <div>
          <h1 className="display m-0 text-[28px] normal-case tracking-[.06em] text-ink">Give Sage a mind, then say hello.</h1>
          <p className="copy mt-2 max-w-[640px] text-[14.5px] text-ink/80">Two steps, about five minutes: pick an AI, and give it your documents
            while it gets ready. Then ask it about them.</p>
          {hw && <p className="copy m-0 mt-1 text-[12px] text-mute" title="what the models below are rated for">
            This computer: {({ windows: "Windows", darwin: "macOS", macos: "macOS", linux: "Linux" } as Record<string, string>)[hw.os] ?? hw.os} · {Math.round(hw.ram_gb)} GB memory · {hw.gpu ? `${hw.gpu.name.replace(/^NVIDIA GeForce |^AMD Radeon\(TM\) /, "")}, ${hw.gpu.vram_gb} GB` : "no graphics card: models run on the processor"}</p>}
        </div>
        {setup?.error && <div className="border border-amber/50 px-3 py-2 text-[12.5px] text-amber">Setup stopped: {setup.error}</div>}
        {/* both steps side by side, so step 2 is in view on a 1366×768 laptop (O0/U2 polish) */}
        <div className="grid items-start gap-5 lg:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-2">
            {step ? (
          <div className="border border-cyan bg-cyan/5 p-4" role="status">
            <div className="display text-[18px] tracking-[.06em] text-ink">Setting up {rec && step.model === rec.id ? rec.label : step.model}…</div>
            <div className="copy mt-2 text-[13px] text-ink/80">
              {step.step === "engine" && <>Getting llama.cpp, the program that runs models: <Num className="text-[14px]">{pct("binary")}</Num>%{eta("binary")}</>}
              {step.step === "model" && <>Downloading the model: <Num className="text-[14px]">{pct(`model:${step.model}`)}</Num>% of {Math.round((job(`model:${step.model}`)?.total ?? 0) / 1e9 * 10) / 10} GB{eta(`model:${step.model}`)}</>}
              {(step.step === "start" || step.step === "loading") && <>Loading it into memory; your first chat opens when it's ready.</>}
            </div>
          </div>
            ) : rec ? (
              <div className="relative border border-cyan bg-cyan/5 p-4 shadow-[0_0_28px_rgba(61,255,139,.12)]">
                <span className="display absolute -top-2.5 left-3 bg-cyan px-2 text-[11px] tracking-[.18em] text-void">{rec.starter ? "1 · QUICK START" : "1 · BEST FIT FOR THIS COMPUTER"}</span>
                <div className="display mt-1 text-[22px] tracking-[.06em] text-ink">{rec.label}</div>
                <p className="copy mb-3 mt-1 text-[13.5px] text-ink/80">{rec.starter ? "Ready in a few minutes. Good for everyday questions about your documents. " : goodFor(rec.note) ? `${goodFor(rec.note)}. ` : ""}Runs on this computer, free; nothing you ask leaves it.</p>
                <div className="mb-3 flex gap-5 text-[11px] text-mute">
                  <span><Num className="block text-[18px]">{(rec.size / 1e9).toFixed(1)}</Num>GB download</span>
                  <span><Num className="block text-[18px]">{rec.need_gb}</Num>GB of memory</span>
                </div>
                <button className="chip h-8 px-4 font-semibold" style={SOLID} disabled={!!busy} onClick={() => go(rec)}>INSTALL AND START →</button>
                <p className="copy mb-0 mt-3 text-[12.5px] text-ink/75">No download? <button className="text-cyan underline underline-offset-2" onClick={() => onConnect("gemini")}>Use Gemini instead</button>: free
                  with a Google account, ready in a minute; your questions go to Google.</p>
                {later && <p className="copy mb-0 mt-1.5 text-[12px] text-mute">Later, for better answers: {later.label} ({(later.size / 1e9).toFixed(1)} GB), in MODELS.</p>}
              </div>
            ) : <p className="copy text-mute">{eng ? "No model in the catalog fits this computer; use an AI you already have, below." : "Looking at this computer…"}</p>}
            {!step && others.length > 0 && (
              <details className="group">
                <summary className="cursor-pointer list-none text-[12px] text-cyan/80 hover:text-cyan"><span className="inline-block transition-transform group-open:rotate-90">▸</span> Other models for this computer ({others.length})</summary>
                <div className="mt-1">
              {others.map((m) => (
                    <div key={m.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 border-b border-cyan/10 py-1.5">
                      <span className="copy truncate text-[13px] text-ink">{m.label}</span>
                      <span className={`row-span-2 text-[10.5px] uppercase tracking-[.1em] ${m.fit === "fits" ? "text-cyan" : m.fit === "tight" ? "text-amber" : "text-mute"}`}>{fitWords(m.fit)}</span>
                      <button className="chip mute row-span-2" disabled={!!busy || m.fit === "too big"} onClick={() => go(m)}>install</button>
                      <span className="text-[10.5px] text-mute">{goodFor(m.note) || m.note} · {(m.size / 1e9).toFixed(1)} GB</span>
                    </div>
                  ))}
                  <button className="chip mute mt-2" onClick={onModels}>ALL MODELS →</button>
                </div>
              </details>
            )}
          </div>
          <div className="flex min-w-0 flex-col gap-2">
            <h2 className="display m-0 text-[14px] text-ink">2 · Give it your documents <span className="normal-case tracking-normal text-mute">{step ? "while it gets ready" : "now or later"}</span></h2>
            <AddDocs />
            <p className="copy m-0 text-[12px] text-mute">They stay on this computer. Sage reads them so its answers come from your own work, and shows where each
              answer came from.</p>
          </div>
        </div>
        <div>
          <div className="kicker"><span>Or use an AI you already have</span><span>instead of step 1</span></div>
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
