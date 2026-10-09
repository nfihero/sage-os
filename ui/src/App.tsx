import { useEffect, useRef, useState } from "react";
import { useHub } from "./useHub";
import { useTheme } from "./theme";
import TopBar from "./components/TopBar";
import ClaudePane from "./components/ClaudePane";
import LocalPane from "./components/LocalPane";
import Inbox from "./components/Inbox";
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

type Tab = "claude" | "local" | "inbox" | "board" | "system";
type Area = "claude" | "local" | "inbox" | "board" | "gpu";

// What each panel is, in plain words (left) and its role on the team (right).
const KICKERS: Record<Area, [string, string]> = {
  claude: ["Lead agent", "Answers by default"], local: ["Chat", "Local or cloud models"], inbox: ["Inbox", "Needs you"],
  board: ["Task board", "Work in flight"], gpu: ["System", "GPU · memory"],
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
  const wide = useMedia("(min-width: 1500px)");
  const [openTask, setOpenTask] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("claude");
  const [shelf, setShelf] = useState(false);
  const [models, setModels] = useState(false);
  const [guide, setGuide] = useState<"why" | "tour" | null>(() => (guideSeen() ? null : "why"));
  const [booting, setBooting] = useState(true);   // the guide waits, so keys that skip the boot don't reach it
  const { panels } = hub;
  const safety = useSafety(panels.safety ?? []);
  const inbox = panels.inbox ?? [];
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

  const claude = <ClaudePane panel={panels.claude} usage={panels.claude_usage} inboxCount={inbox.length} lowPower={lowPower} />;
  const local = <LocalPane sessions={panels.sessions ?? []} board={panels.board} runs={panels.hermes_runs ?? {}} compact={phone} lowPower={lowPower}
    chats={panels.chat?.sessions} onModels={() => setModels(true)} />;
  const inboxView = <Inbox items={inbox} onOpenTask={setOpenTask} />;
  const board = <BoardView board={panels.board} events={hub.events} onOpen={setOpenTask} compact={phone} />;
  const gpu = <GpuLane gpu={panels.gpu} health={panels.health} events={hub.events} />;
  const cell = (a: Area, node: React.ReactNode) => (
    <div ref={(el) => { areas.current[a] = el; }} className="flex min-h-0 flex-col" style={{ gridArea: a }} data-tour={a}>
      <div className={`kicker ${a === "claude" ? "text-orange/70" : ""}`}><span>{KICKERS[a][0]}</span><span>{KICKERS[a][1]}</span></div>
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
        <TopBar hub={hub} inboxCount={inbox.length} compact={phone} unseen={safety.unseen} onSafety={safety.toggle} theme={theme} onLogo={() => setBoot((b) => b + 1)} onBookshelf={() => setShelf(true)} onGuide={() => setGuide("why")} />
        {phone ? (
          <>
            <main className="flex min-h-0 flex-1 flex-col p-2">
              {tab === "claude" && claude}
              {tab === "local" && local}
              {tab === "inbox" && inboxView}
              {tab === "board" && board}
              {tab === "system" && gpu}
            </main>
            <nav className="grid grid-cols-5 border-t border-cyan/30 bg-void/90 pb-[env(safe-area-inset-bottom)]">
              {([["claude", "Claude", 0], ["local", "Local", 0], ["inbox", "Inbox", inbox.length], ["board", "Board", 0], ["system", "GPU", 0]] as const)
                .map(([k, label, badge]) => (
                  <button key={k} onClick={() => setTab(k)}
                    className={`display relative py-3 text-[11px] ${tab === k ? (k === "claude" ? "glow-orange" : "glow-cyan") : "text-mute"}`}>
                    {label}
                    {badge > 0 && <span className="pulse-amber absolute right-2 top-2 rounded-full bg-amber px-1.5 text-[9px] text-void">{badge}</span>}
                  </button>
                ))}
            </nav>
          </>
        ) : (
          <main className="grid min-h-0 flex-1 gap-x-4 gap-y-3 px-4 pb-4 pt-2" style={wide ? {
            gridTemplateColumns: "minmax(0,1fr) clamp(340px, 24vw, 460px) clamp(300px, 19vw, 380px)",
            gridTemplateRows: "minmax(0,1fr) minmax(0,34%)",
            gridTemplateAreas: `"claude local inbox" "board board gpu"`,
          } : {
            gridTemplateColumns: "minmax(0,1fr) clamp(300px, 34vw, 400px)",
            gridTemplateRows: "minmax(0,1.3fr) minmax(0,1fr) minmax(0,32%)",
            gridTemplateAreas: `"claude local" "claude inbox" "board gpu"`,
          }}>
            {cell("claude", claude)}
            {cell("local", local)}
            {cell("inbox", inboxView)}
            {cell("board", board)}
            {cell("gpu", gpu)}
          </main>
        )}
      </div>
      <SafetyDrawer open={safety.open} safety={panels.safety ?? []} events={hub.events} onClose={safety.close} onOpenTask={setOpenTask} />
      <SafetyToast unseen={safety.unseen} open={safety.open} onOpen={safety.toggle} />
      {shelf && <Bookshelf panel={panels.vault} sources={panels.sources} digests={panels.digests} proposals={inbox.filter((i) => i.source === "bookshelf").length} onClose={() => setShelf(false)} />}
      {models && <Models panel={panels.engine} onClose={() => setModels(false)} />}
      <Guide open={booting ? null : guide} panels={panels} onClose={() => setGuide(null)} onBookshelf={() => setShelf(true)} />
      {openTask && <TaskDrawer id={openTask} onClose={() => setOpenTask(null)} onOpen={setOpenTask} />}
    </>
  );
}
