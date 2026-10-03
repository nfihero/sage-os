import { useEffect, useLayoutEffect, useState } from "react";
import type { Panels } from "../types";

/**
 * The guide (D18): why Sage OS exists, then a tour that points at each panel. Opens on a first visit
 * (or with `?guide` in the URL) and from the GUIDE chip. Facts here come from DECISIONS.md; keep them
 * in step when a decision changes.
 */

const SEEN = "sageos.guide.seen";

export function guideSeen(): boolean {
  try { return !!localStorage.getItem(SEEN) && !new URLSearchParams(location.search).has("guide"); } catch { return false; }
}
function markSeen() {
  try { localStorage.setItem(SEEN, "1"); } catch { /* private mode */ }
}

const TEAM: [string, string, string][] = [
  ["A manager who signs off", "Inbox", "Agents propose; nothing reaches your notes or runs unchecked until you approve it."],
  ["A shared wiki", "Bookshelf", "Plain markdown notes on your disk that every agent can search, read and cite."],
  ["A task board", "Board", "Work handed to agents, by stage. A blocked task asks its question in the inbox."],
  ["Teammates", "Claude + Hermes", "Claude leads and answers by default; Hermes runs a model on your own GPU. Any OpenAI-compatible model can plug in."],
  ["Office rules", "Safety", "Proposals are screened for secrets, every change can be undone, the guard log shows what was blocked."],
];

const RULES: [string, string][] = [
  ["Agents propose, you decide.", "An agent can't write a note. It sends a proposal with a diff to your inbox (D11)."],
  ["Your files stay on this machine.", "Notes, copies of your documents and history live in sage-os/data. Google Drive is only read (D6, D15)."],
  ["Bring your own AI.", "Claude Code and Hermes today, any OpenAI-compatible endpoint as a model. Hermes is optional (D4)."],
  ["Everything is undoable.", "Each approved batch is journalled byte for byte; undo restores the files exactly (D11)."],
];

type Step = { target: string; title: string; body: string };
const STEPS: Step[] = [
  { target: '[data-tour="claude"]', title: "Claude: the lead agent",
    body: "Ask it to plan, research or write. It searches your Bookshelf and your documents, and proposes notes. It can't file them; you do. Tabs across the top are separate conversations." },
  { target: '[data-tour="local"]', title: "Hermes: the local agent",
    body: "A second agent running a model on your GPU: free and private, good for reading through a pile of files. Same tools, same rules as Claude." },
  { target: '[data-tour="inbox"]', title: "Inbox: everything that needs you",
    body: "Permission requests, questions from agents, and note proposals with the exact change shown. Approve, reject, or answer. Proposals that look like they contain a secret are held back until you decide." },
  { target: '[data-tour="board"]', title: "Board: the work in flight",
    body: "Tasks handed to agents, from triage to done. Click a card to see its history. A blocked card means an agent is waiting on your answer in the inbox." },
  { target: '[data-tour="gpu"]', title: "System: the machine underneath",
    body: "What's loaded on the GPU and how much memory it uses. Blocks by the safety guard show up in SAFETY at the top." },
  { target: '[data-testid="bookshelf-open"]', title: "Bookshelf: your notes",
    body: "Start here if your notes are empty. Sources holds read-only copies of folders you chose; Build notes turns them into starter notes and asks an agent to draft more. All of it arrives as proposals." },
  { target: '[data-tour="guide"]', title: "That's the tour",
    body: "The status lights at the top show which services are up. Open GUIDE any time to see this again." },
];

export default function Guide({ open, panels, onClose, onBookshelf }: {
  open: "why" | "tour" | null; panels: Panels; onClose: () => void; onBookshelf: () => void;
}) {
  const [mode, setMode] = useState<"why" | "tour" | null>(open);
  useEffect(() => setMode(open), [open]);
  useEffect(() => {
    if (!mode) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [mode]);
  const close = () => { markSeen(); onClose(); };

  if (!mode) return null;
  if (mode === "tour") return <Tour onDone={close} />;

  const notes = panels.vault?.count ?? 0;
  const docs = (panels.sources?.sources ?? []).reduce((n, s) => n + s.files, 0);
  const proposals = (panels.inbox ?? []).filter((i) => i.source === "bookshelf").length;
  const waiting = (panels.inbox ?? []).length;

  return (
    <div className="fixed inset-0 z-50 flex justify-center overflow-auto bg-void/75 p-3 backdrop-blur-sm sm:p-8" onClick={close}>
      <div className="panel guide my-auto h-auto w-full max-w-[920px] flex-none" onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true" aria-labelledby="guide-title" data-testid="guide">
        <div className="panel-head">
          <span className="tab">GUIDE</span>
          <span className="text-mute normal-case tracking-normal">why Sage OS exists · how to use it</span>
          <button onClick={close} className="ml-auto text-mute hover:text-cyan" aria-label="close guide">✕</button>
        </div>
        <div className="flex flex-col gap-6 p-5 sm:p-8">
          <header className="flex flex-col gap-3">
            <h1 id="guide-title" className="display glow-cyan text-[clamp(26px,4vw,40px)] leading-[1.05] tracking-[.06em]">
              Your own small agent team
            </h1>
            <p className="guide-copy text-[14px] leading-relaxed text-ink/90">
              Companies now run several AI agents as one team: a shared wiki they all read, a task board, and a person
              who signs off on what they produce. Sage OS gives one person that setup on their own PC, with the AI they
              already use.
            </p>
          </header>

          <section aria-labelledby="guide-team">
            <h2 id="guide-team" className="display mb-2 text-[11px] text-mute">What a team needs, and where it is here</h2>
            <div className="guide-grid">
              {TEAM.map(([need, here, what]) => (
                <div key={here} className="contents">
                  <div className="text-[12px] text-mute">{need}</div>
                  <div className="display text-[13px] text-cyan">{here}</div>
                  <div className="text-[12.5px] leading-snug text-ink/85">{what}</div>
                </div>
              ))}
            </div>
          </section>

          <section aria-labelledby="guide-rules">
            <h2 id="guide-rules" className="display mb-2 text-[11px] text-mute">The rules it runs on</h2>
            <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              {RULES.map(([rule, why]) => (
                <li key={rule} className="border-l-2 border-cyan/40 pl-3">
                  <div className="text-[13px] text-ink">{rule}</div>
                  <div className="text-[12px] leading-snug text-mute">{why}</div>
                </li>
              ))}
            </ul>
            <p className="guide-copy mt-3 text-[12px] leading-snug text-mute">
              The limit: Sage OS controls only what passes through it. A shell command an agent runs on its own is up to
              that agent's own safeguards (Claude Code's permissions, Hermes' guardian).
            </p>
          </section>

          <section className="flex flex-col gap-3 border-t border-cyan/20 pt-4 sm:flex-row sm:items-center">
            <div className="readout flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink/85" data-testid="guide-now">
              <span><span className="font-dot text-[16px] text-cyan">{notes}</span> notes</span>
              <span><span className="font-dot text-[16px] text-cyan">{docs}</span> source documents</span>
              <span><span className="font-dot text-[16px] text-amber">{waiting}</span> waiting for you{proposals ? ` (${proposals} note proposals)` : ""}</span>
            </div>
            <div className="flex gap-2 sm:ml-auto">
              <button className="chip" onClick={() => { markSeen(); onClose(); onBookshelf(); }}
                title="Open the Bookshelf on your notes and sources">OPEN BOOKSHELF</button>
              <button className="chip amber" onClick={() => setMode("tour")} data-testid="guide-tour" autoFocus>TAKE THE TOUR →</button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

/** Spotlights one panel at a time with a short explanation next to it. */
function Tour({ onDone }: { onDone: () => void }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  useLayoutEffect(() => {
    const measure = () => {
      const el = document.querySelector(step.target);
      const r = el?.getBoundingClientRect();
      setRect(r && r.width > 0 && r.height > 0 ? r : null);    // hidden on this layout (phone tabs): centre the card
    };
    measure();
    // panels slide in and the top bar can wrap as data arrives: follow the layout, not just the window
    const ro = new ResizeObserver(measure);
    ro.observe(document.body);
    const el = document.querySelector(step.target);
    if (el) ro.observe(el);
    const settle = setTimeout(measure, 600);
    window.addEventListener("resize", measure);
    return () => { ro.disconnect(); clearTimeout(settle); window.removeEventListener("resize", measure); };
  }, [i]);
  useEffect(() => {
    const keys = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.target as HTMLElement)?.closest?.("button")) return;   // the focused button handles it
      if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); last ? onDone() : setI(i + 1); }
      if (e.key === "ArrowLeft" && i > 0) setI(i - 1);
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, [i]);

  // Put the card beside the spotlight: right of it if there's room, else left, else below/above, else centred.
  const W = Math.min(340, window.innerWidth - 24), pad = 14;
  // (no CSS transform for centring: the panel's entrance animation owns `transform`)
  let style: React.CSSProperties = { left: (window.innerWidth - W) / 2, top: Math.max(12, window.innerHeight / 2 - 120), width: W };
  if (rect) {
    const vw = window.innerWidth, vh = window.innerHeight;
    const top = Math.min(Math.max(12, rect.top), vh - 260);
    if (rect.right + pad + W < vw) style = { left: rect.right + pad, top, width: W };
    else if (rect.left - pad - W > 0) style = { left: rect.left - pad - W, top, width: W };
    else if (rect.bottom + 220 < vh) style = { left: Math.min(Math.max(12, rect.left), vw - W - 12), top: rect.bottom + pad, width: W };
    else style = { left: Math.min(Math.max(12, rect.left), vw - W - 12), top: Math.max(12, rect.top - 230), width: W };
  }

  return (
    <div className="fixed inset-0 z-50" onClick={onDone} data-testid="tour">
      {rect ? (
        <div className="tour-spot" style={{ left: rect.left - 6, top: rect.top - 6, width: rect.width + 12, height: rect.height + 12 }} />
      ) : <div className="absolute inset-0 bg-void/75" />}
      <div key={i} className="panel tour-card absolute h-auto flex-none" style={style} onClick={(e) => e.stopPropagation()}
        role="dialog" aria-live="polite" aria-label={step.title}>
        <div className="flex flex-col gap-2 p-4">
          <div className="readout text-[10.5px] text-mute">STEP {i + 1} OF {STEPS.length}</div>
          <div className="display glow-cyan text-[15px]">{step.title}</div>
          <p className="text-[12.5px] leading-relaxed text-ink/90">{step.body}</p>
          <div className="mt-1 flex items-center gap-2">
            <button className="text-[11px] text-mute hover:text-cyan" onClick={onDone}>skip tour</button>
            <span className="ml-auto flex gap-2">
              {i > 0 && <button className="chip mute" onClick={() => setI(i - 1)}>← BACK</button>}
              <button className="chip amber" onClick={() => (last ? onDone() : setI(i + 1))} autoFocus data-testid="tour-next">
                {last ? "DONE" : "NEXT →"}
              </button>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
