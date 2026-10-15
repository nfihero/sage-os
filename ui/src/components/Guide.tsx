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

// Written for someone who has never used an AI agent (D41.1): what you do, in plain words, not how it's built.
const START: [string, string][] = [
  ["Pick an AI", "Use a free one that runs on this computer, or connect one you already use: ChatGPT, Claude or Gemini."],
  ["Add your documents", "Sage reads them, so answers come from your own work. Your files stay on this computer."],
  ["Ask, and approve what it saves", "When an AI wants to save a note, it asks in your Inbox first. You say yes or no."],
];

const RULES: [string, string][] = [
  ["It asks before it acts.", "Nothing is saved or changed until you approve it in the Inbox."],
  ["Your files stay here.", "Your documents and notes live on this computer. Google Drive is only read, never changed."],
  ["Use any AI.", "A free one on this computer, or ChatGPT, Claude or Gemini. $ USAGE shows what each one costs."],
  ["Everything can be undone.", "Bookshelf → History puts your notes back exactly as they were."],
];

type Step = { target: string; title: string; body: string };
const STEPS: Step[] = [
  { target: '[data-tour="agent"]', title: "Your AI",
    body: "The AI you're talking to. Its planet lights up when it's ready and moves while it answers." },
  { target: '[data-tour="search"]', title: "Search and ask",
    body: "Type to find something in your notes and documents. Press Enter to ask your AI instead; under its answer you'll see which notes it used." },
  { target: '[data-tour="inbox"]', title: "Inbox: things that need your OK",
    body: "When an AI wants to save a note or run something, it asks here. Approve it or say no. Nothing happens without you." },
  { target: '[data-tour="systems-tab"]', title: "Systems",
    body: "What's running behind the scenes, like the graphics card. You can ignore it." },
  { target: '[data-testid="bookshelf-open"]', title: "Bookshelf: your notes and documents",
    body: "Add your documents here. Sage turns them into notes, and each one waits for your OK in the Inbox first." },
  { target: '[data-tour="guide"]', title: "That's it",
    body: "Open GUIDE any time to see this again. If something isn't working, REPORT A PROBLEM is right next to it." },
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
          <span className="text-mute normal-case tracking-normal">what Sage OS does · how to start</span>
          <button onClick={close} className="ml-auto text-mute hover:text-cyan" aria-label="close guide">✕</button>
        </div>
        <div className="flex flex-col gap-6 p-5 sm:p-8">
          <header className="flex flex-col gap-3">
            <h1 id="guide-title" className="display glow-cyan text-[clamp(26px,4vw,40px)] leading-[1.05] tracking-[.06em]">
              An AI that knows your work
            </h1>
            <p className="guide-copy text-[14px] leading-relaxed text-ink/90">
              Sage OS is a place to talk to AI about your own work. Give it your documents and it answers from them, and
              it keeps what it learns as notes you can read. It never changes anything without asking you first.
            </p>
          </header>

          <section aria-labelledby="guide-start">
            <h2 id="guide-start" className="display mb-3 text-[11px] text-mute">How to start</h2>
            <ol className="m-0 grid list-none gap-4 p-0 sm:grid-cols-3">
              {START.map(([step, what], i) => (
                <li key={step} className="flex gap-3">
                  <span className="font-dot glow-cyan text-[22px] leading-none">{i + 1}</span>
                  <span><span className="copy block text-[14px] text-ink">{step}</span>
                    <span className="copy mt-1 block text-[12.5px] leading-snug text-ink/75">{what}</span></span>
                </li>
              ))}
            </ol>
          </section>

          <section aria-labelledby="guide-rules">
            <h2 id="guide-rules" className="display mb-2 text-[11px] text-mute">What you can count on</h2>
            <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              {RULES.map(([rule, why]) => (
                <li key={rule} className="border-l-2 border-cyan/40 pl-3">
                  <div className="copy text-[13px] text-ink">{rule}</div>
                  <div className="copy text-[12px] leading-snug text-mute">{why}</div>
                </li>
              ))}
            </ul>
            <p className="guide-copy mt-3 text-[12px] leading-snug text-mute">
              One exception: Claude Code, if you connect it, can run programs in a folder you give it. It asks you in the
              Inbox before each one.
            </p>
          </section>

          <section className="flex flex-col gap-3 border-t border-cyan/20 pt-4 sm:flex-row sm:items-center">
            <div className="readout flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink/85" data-testid="guide-now">
              <span><span className="font-dot text-[16px] text-cyan">{notes}</span> notes</span>
              <span><span className="font-dot text-[16px] text-cyan">{docs}</span> documents</span>
              <span><span className="font-dot text-[16px] text-amber">{waiting}</span> waiting for your OK{proposals ? ` (${proposals} notes to approve)` : ""}</span>
            </div>
            <div className="flex gap-2 sm:ml-auto">
              <button className="chip" onClick={() => { markSeen(); onClose(); onBookshelf(); }}
                title="Your notes and documents">OPEN BOOKSHELF</button>
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
          <div className="readout text-[11px] text-mute">STEP {i + 1} OF {STEPS.length}</div>
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
