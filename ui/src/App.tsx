import { useEffect, useRef, useState } from "react";
import { useHub } from "./useHub";
import { useTheme } from "./theme";
import TopBar from "./components/TopBar";
import ChatSpace, { type Answering } from "./components/ChatSpace";
import LocalPane from "./components/LocalPane";
import Inbox from "./components/Inbox";
import Agents from "./components/Agents";
import BoardView from "./components/Board";
import GpuLane from "./components/GpuLane";
import TaskDrawer from "./components/TaskDrawer";
import DotGrid, { type Ripple } from "./components/DotGrid";
import Handoffs, { handoff, ORB } from "./components/Handoffs";
import ScreenFx from "./components/ScreenFx";
import BootScreen from "./components/BootScreen";
import { SafetyDrawer, SafetyToast, useSafety } from "./components/Safety";
import Bookshelf from "./components/Bookshelf";
import Models from "./components/Models";
import Guide, { guideSeen } from "./components/Guide";
import Connect, { type ConnectSection } from "./components/Connect";
import UsageScreen from "./components/UsageScreen";
import Report from "./components/Report";
import { AgentPanel, DigestStrip, LibrarySearch, RecentNotes, SystemsStrip, askLocal, type AgentKey } from "./components/Home";

type Tab = "home" | "agent" | "inbox" | "systems";
type Area = "agent" | "centre" | "inbox" | "board" | "gpu" | "local";

// What each panel is, in plain words (left) and its role (right).
const KICKERS: Record<Area, [string, string]> = {
  agent: ["Answering", "Your AI"], centre: ["Ask", "Your bookshelf"], inbox: ["Inbox", "Needs you"],
  board: ["Task board", "Work in flight"], gpu: ["System", "GPU · memory"], local: ["Hermes", "Local agent"],
};
const LOW_POWER_MB = 14.5 * 1024;   // orbs drop to ~12 fps when a model nearly fills VRAM

function useMedia(q: string) {
  const [m, setM] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return m;
}

export default function App() {
  const hub = useHub();
  const theme = useTheme();
  const phone = useMedia("(max-width: 900px)");
  const [openTask, setOpenTask] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("home");                     // phone
  const [view, setView] = useState<"home" | "systems">("home");    // desktop (W2)
  const [answering, setAnswering] = useState<Answering>(null);   // the AI answering the open chat (W3)
  const [chatOpen, setChatOpen] = useState<string | null>(null);
  const [askErr, setAskErr] = useState<string | null>(null);
  const [shelfAt, setShelfAt] = useState<{ ref?: string; source?: { source: string; path: string } } | null>(null);
  const [shelf, setShelf] = useState(false);
  const [models, setModels] = useState(false);
  const [connect, setConnect] = useState<ConnectSection | "any" | null>(null);   // D40: connect guides
  const [usage, setUsage] = useState(false);
  const [reporting, setReporting] = useState(false);     // F1: Report a problem
  const [aisVersion, setAisVersion] = useState(0);
  const [pickAsk, setPickAsk] = useState(false);            // D42: the left card asks the chat to open its AI picker
  const [agentsOpen, setAgentsOpen] = useState(false);      // K7: trust, roles, activity
  const [guide, setGuide] = useState<"why" | "tour" | null>(() => (guideSeen() ? null : "why"));
  const [booting, setBooting] = useState(true);   // the guide waits, so keys that skip the boot don't reach it
  const { panels } = hub;
  const safety = useSafety(panels.safety ?? []);
  const inbox = panels.inbox ?? [];
  // K7: a chapter's parts are one card, so every count shows cards, not parts
  const cards = new Set(inbox.map((i) => (i.source === "bookshelf" && i.context.group ? `g:${i.context.group}` : i.id))).size;
  const lowPower = (panels.gpu?.gpu?.vram_used_mb ?? 0) > LOW_POWER_MB;
  const [boot, setBoot] = useState(0);

  // Agent activity ripples across the background from the panel it happened in.
  const ripples = useRef<Ripple[]>([]);
  const areas = useRef<Partial<Record<Area, HTMLDivElement | null>>>({});
  const seen = useRef<string | null>(null);
  useEffect(() => {
    const ev = hub.events[0];
    if (!ev) return;
    const key = `${ev.id}-${ev.ts}-${ev.type}`;
    if (seen.current === null) { seen.current = key; return; }   // skip history on load
    if (key === seen.current) return;
    seen.current = key;
    const css = (t: string) => getComputedStyle(document.documentElement).getPropertyValue(t).trim();
    let area: Area | null = null, color = css("--color-cyan");
    if (ev.kind === "task" && ev.type !== "task.heartbeat") area = "board";
    else if (ev.type === "approval.requested") { area = "inbox"; color = css("--color-amber"); }
    else if (ev.type === "gpu.model") area = "gpu";
    else if (ev.type === "guard.block") { area = "gpu"; color = css("--color-red"); }
    else if (ev.type === "session.activity") area = "local";
    else if (ev.kind === "message" || ev.type.startsWith("chat.")) area = "centre";
    // Work changing hands on the board flies between the agents' orbs.
    if (ev.kind === "task") {
      const owner = panels.board?.tasks.find((t) => t.id === ev.data?.task_id)?.assignee;
      if (owner) {
        if (ev.type === "task.spawned") handoff('[data-testid="board"]', ORB(owner));
        else if (ev.type === "task.completed") handoff(ORB(owner), ORB("claude"));
        else if (ev.type === "task.blocked") handoff(ORB(owner), '[data-testid="inbox"]', { color: css("--color-amber") });
      }
    }
    const el = area && areas.current[area];
    if (!el) return;
    const r = el.getBoundingClientRect();
    ripples.current.push({ x: r.left + r.width / 2, y: r.top + r.height / 2, t: performance.now(), color });
  }, [hub.events]);

  const openNote = (ref: string) => { setShelfAt({ ref }); setShelf(true); };
  const openSource = (source: { source: string; path: string }) => { setShelfAt({ source }); setShelf(true); };
  const ask = async (q: string) => {
    setAskErr(null);
    // asking from search goes to the local model (Claude has its own message box); switch to show the answer
    const r = await askLocal(panels, q);
    if (r.id) { setChatOpen(r.id); setTab("home"); } else setAskErr(r.error ?? "couldn't start the chat");
  };
  // W3 (D39): one chat space for every AI; the left panel follows whichever AI answers the open chat
  const shown: AgentKey = answering?.agent === "claude" ? "claude" : "local";
  const conversation = (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      {askErr && <div className="border border-amber/50 px-2 py-1 text-[12px] text-amber">{askErr} <button className="chip ml-1" onClick={() => setModels(true)}>MODELS</button></div>}
      <ChatSpace panels={panels} openId={chatOpen} onOpen={setChatOpen} onAnswering={setAnswering} onModels={() => setModels(true)}
        onConnect={(s) => setConnect(s ?? "any")} onUsage={() => setUsage(true)} aisVersion={aisVersion} pickAsk={pickAsk} onPickDone={() => setPickAsk(false)} />
    </div>
  );
  const agentPanel = <AgentPanel agent={shown} answering={answering} panels={panels} lowPower={lowPower} onModels={() => setModels(true)}
    onSwitch={() => { setTab("home"); setPickAsk(true); }} onConnect={() => setConnect("any")} />;
  const search = <LibrarySearch panels={panels} onOpenNote={openNote} onOpenSource={openSource} onAsk={ask} />;
  const hermesRan = panels.health?.gateway.state === "up" || panels.health?.gateway.state === "down";
  const local = <LocalPane sessions={panels.sessions ?? []} board={panels.board} runs={panels.hermes_runs ?? {}} compact={phone} lowPower={lowPower}
    chats={panels.chat?.sessions} game={panels.gamemode} hermes={panels.health?.gateway.state} onModels={() => setModels(true)} />;
  const inboxView = <Inbox items={inbox} onOpenTask={setOpenTask} events={hub.events} auto={panels.agents_trust?.auto} onAgents={() => setAgentsOpen(true)} />;
  const board = <BoardView board={panels.board} events={hub.events} onOpen={setOpenTask} compact={phone} />;
  const gpu = <GpuLane gpu={panels.gpu} health={panels.health} events={hub.events} engine={panels.engine} />;
  const cell = (a: Area, node: React.ReactNode) => (
    <div ref={(el) => { areas.current[a] = el; }} className="flex min-h-0 flex-col" style={{ gridArea: a }} data-tour={a}>
      <div className={`kicker ${a === "agent" && shown === "claude" ? "text-orange/70" : ""}`}><span>{KICKERS[a][0]}</span><span>{KICKERS[a][1]}</span></div>
      {node}
    </div>
  );

  return (
    <>
      <DotGrid ripples={ripples} />
      <div className="vignette" />
      <BootScreen hub={hub} replay={boot} onShowing={setBooting} />
      <ScreenFx />
      <Handoffs />
      <div className="relative z-10 flex h-full flex-col">
        <TopBar hub={hub} inboxCount={cards} compact={phone} unseen={safety.unseen} onSafety={safety.toggle} theme={theme} onLogo={() => setBoot((b) => b + 1)} onBookshelf={() => setShelf(true)} onGuide={() => setGuide("why")} onModels={() => setModels(true)} onUsage={() => setUsage(true)} onReport={() => setReporting(true)} />
        {phone ? (
          <>
            <main className="flex min-h-0 flex-1 flex-col gap-2 p-2">
              {tab === "home" && <>{search}<div className="flex min-h-0 flex-1 flex-col">{conversation}</div></>}
              {tab === "agent" && <div className="min-h-0 flex-1 overflow-auto">{agentPanel}</div>}
              {tab === "inbox" && inboxView}
              {tab === "systems" && <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto"><div className="flex min-h-[60%] flex-col">{board}</div>{gpu}</div>}
            </main>
            <nav className="grid grid-cols-4 border-t border-cyan/30 bg-void/90 pb-[env(safe-area-inset-bottom)]">
              {([["home", "Home", 0], ["agent", "AI", 0], ["inbox", "Inbox", cards], ["systems", "Systems", 0]] as const)
                .map(([k, label, badge]) => (
                  <button key={k} onClick={() => setTab(k)}
                    className={`display relative py-3 text-[11px] ${tab === k ? "glow-cyan" : "text-mute"}`}>
                    {label}
                    {badge > 0 && <span className="pulse-amber absolute right-2 top-2 rounded-full bg-amber px-1.5 text-[11px] text-void">{badge}</span>}
                  </button>
                ))}
            </nav>
          </>
        ) : (
          <>
            <div className="flex items-end px-4 pt-2" role="tablist" aria-label="Views">
              <button role="tab" aria-selected={view === "home"} className={`htab !ml-0 [clip-path:polygon(0_0,100%_0,calc(100%-14px)_100%,0_100%)] ${view === "home" ? "on" : ""}`} onClick={() => setView("home")}>Home</button>
              <button className="htab" onClick={() => { setShelfAt(null); setShelf(true); }}>Bookshelf</button>
              <button role="tab" aria-selected={view === "systems"} data-tour="systems-tab" className={`htab ${view === "systems" ? "on" : ""}`} onClick={() => setView("systems")}>Systems</button>
            </div>
            {view === "home" ? (
              <main className="grid min-h-0 flex-1 gap-x-4 gap-y-3 px-4 pb-4 pt-2" style={{
                gridTemplateColumns: "clamp(240px, 18vw, 300px) minmax(0,1fr) clamp(300px, 23vw, 400px)",
                gridTemplateRows: "minmax(0,1fr) auto",
                gridTemplateAreas: `"agent centre inbox" "sys sys sys"`,
              }}>
                {cell("agent", <div className="min-h-0 flex-1 overflow-auto">{agentPanel}</div>)}
                {cell("centre", <div className="flex min-h-0 flex-1 flex-col gap-3">{search}<div className="flex min-h-0 flex-1 flex-col">{conversation}</div></div>)}
                {cell("inbox", <div className="flex min-h-0 flex-1 flex-col gap-3"><div className="flex min-h-[40%] flex-1 flex-col">{inboxView}</div><DigestStrip panels={panels} /><div className="flex max-h-[34%] min-h-0 flex-col"><RecentNotes panels={panels} onOpenNote={openNote} onLibrary={() => { setShelfAt(null); setShelf(true); }} /></div></div>)}
                <div style={{ gridArea: "sys" }}><SystemsStrip panels={panels} onSystems={() => setView("systems")} /></div>
              </main>
            ) : (
              <main className="grid min-h-0 flex-1 gap-x-4 gap-y-3 px-4 pb-4 pt-2" style={{
                gridTemplateColumns: "minmax(0,1fr) clamp(300px, 26vw, 440px)",
                gridTemplateRows: hermesRan ? "minmax(0,1fr) minmax(0,1fr)" : "minmax(0,1fr)",
                gridTemplateAreas: hermesRan ? `"board gpu" "board local"` : `"board gpu"`,
              }}>
                {cell("board", board)}
                {cell("gpu", gpu)}
                {hermesRan && cell("local", local)}
              </main>
            )}
          </>
        )}
      </div>
      <SafetyDrawer open={safety.open} safety={panels.safety ?? []} events={hub.events} onClose={safety.close} onOpenTask={setOpenTask} />
      <SafetyToast unseen={safety.unseen} open={safety.open} onOpen={safety.toggle} />
      {shelf && <Bookshelf panel={panels.vault} sources={panels.sources} digests={panels.digests} proposals={inbox.filter((i) => i.source === "bookshelf").length}
        initialRef={shelfAt?.ref} initialSource={shelfAt?.source} onClose={() => { setShelf(false); setShelfAt(null); }} />}
      {connect && <Connect focus={connect === "any" ? null : connect} onClose={() => { setConnect(null); setAisVersion((v) => v + 1); }}
        onModels={() => { setConnect(null); setModels(true); }} onUsage={() => { setConnect(null); setUsage(true); }} />}
      {reporting && <Report onClose={() => setReporting(false)} />}
      {usage && <UsageScreen onClose={() => setUsage(false)} onConnect={() => { setUsage(false); setConnect("any"); }} />}
      {models && <Models panel={panels.engine} game={panels.gamemode} onClose={() => setModels(false)} />}
      {agentsOpen && <Agents panel={panels.agents_trust} librarian={panels.librarian} onClose={() => setAgentsOpen(false)} />}
      <Guide open={booting ? null : guide} panels={panels} onClose={() => setGuide(null)} onBookshelf={() => setShelf(true)} />
      {openTask && <TaskDrawer id={openTask} onClose={() => setOpenTask(null)} onOpen={setOpenTask} />}
    </>
  );
}
