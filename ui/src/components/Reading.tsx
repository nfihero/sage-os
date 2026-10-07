import { useEffect, useState } from "react";
import { get, onChat, post } from "../api";
import type { Briefing, BriefingState, ReadingItem } from "../types";

/** K8 (D20): the briefings of one chat, live. `chat` is the pane id ("claude:cs_…", "hermes:default:…"). */
export function useReading(chat: string | null) {
  const [state, setState] = useState<BriefingState | null>(null);
  useEffect(() => {
    if (!chat) return;
    let alive = true;
    setState(null);
    get<BriefingState>(`/api/briefing?chat=${encodeURIComponent(chat)}`).then((s) => alive && setState(s)).catch(() => {});
    const off = onChat((f) => {
      if (f.pane !== chat || f.op !== "reading") return;
      const b = f.briefing as Briefing;
      setState((s) => s && ({ ...s, briefings: [...s.briefings.filter((x) => x.id !== b.id), b].sort((x, y) => x.id - y.id) }));
    });
    return () => { alive = false; off(); };
  }, [chat]);
  const toggle = async () => {
    if (!chat || !state) return;
    const settings = await post(`/api/briefing/settings`, { chat, enabled: !state.settings.enabled });
    setState({ ...state, settings });
  };
  return { state, toggle };
}

/** The briefing that went with a user message: the first one after `after` with that exact text, made
 *  within two minutes of it (a resent message gets the newer briefing; Hermes keeps its own timestamps). */
export function briefingFor(briefings: Briefing[] | undefined, text: string, ts: number, after: number): Briefing | undefined {
  const all = briefings ?? [];
  const hits = all.filter((x) => x.id > after && x.query === text && Math.abs(x.ts - ts) < 120);
  return hits[0];
}

export function ReadingToggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button onClick={onToggle} className={`chip h-9 px-2 normal-case tracking-normal ${enabled ? "" : "mute"}`}
      title={enabled ? "Sage OS attaches matching notes and documents to each message. Click to turn off for this chat."
        : "Reading packs are off for this chat. Click to turn on."}>
      {enabled ? "📖 on" : "📖 off"}
    </button>
  );
}

/** The Reading strip under a sent message: everything the answer was based on, each with ✕. */
export function ReadingStrip({ b, chat }: { b: Briefing; chat: string }) {
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  if (!b.items.length && !b.corrections.length) return null;
  const drop = async (it: ReadingItem) => {
    setErr(null);
    try { await post(`/api/briefing/drop`, { chat, key: it.key }); }
    catch (e) { setErr(String((e as Error).message)); }
  };
  const shown = b.items.find((i) => i.key === open);
  return (
    <div className="reading ml-auto mt-1 max-w-[85%] text-[11.5px]" data-testid="reading-strip">
      <div className="flex flex-wrap items-center justify-end gap-1">
        <span className="kicker mr-1 !mb-0" title="What the agent was given with this message, and what it read itself">Reading</span>
        {b.items.map((it) => (
          <span key={it.key} className={`reading-item ${it.dropped ? "dropped" : ""} ${it.flagged ? "flagged" : ""} ${it.by}`}>
            <button onClick={() => setOpen(open === it.key ? null : it.key)} className="max-w-[220px] truncate"
              title={`${it.by === "agent" ? "The agent opened this itself" : "Attached by Sage OS"} · ${it.kind === "note" ? "note" : `${it.ref.source}/${it.ref.path}`}${it.flagged ? " · you marked it wrong, and the agent read it again" : ""}`}>
              {it.kind === "note" ? "◆" : "▤"} {it.title}{it.by === "agent" ? " ·read" : ""}
            </button>
            {!it.dropped && <button onClick={() => drop(it)} className="x" aria-label={`Mark ${it.title} as wrong or not relevant`}
              title="Wrong or not relevant: leave it out from now on (stops and resends if the agent is still answering)">✕</button>}
          </span>
        ))}
      </div>
      {b.corrections.length > 0 && (
        <div className="mt-0.5 text-right text-amber">told the agent to disregard: {b.corrections.map((c) => c.title).join(", ")}</div>
      )}
      {err && <div className="mt-0.5 text-right text-red">{err}</div>}
      {shown && <Excerpt it={shown} />}
    </div>
  );
}

function Excerpt({ it }: { it: ReadingItem }) {
  const [text, setText] = useState<string | null>(it.excerpt || null);
  useEffect(() => {
    if (it.excerpt) { setText(it.excerpt); return; }
    const url = it.kind === "note" ? `/api/vault/note?ref=${encodeURIComponent(it.ref.uid ?? "")}`
      : `/api/sources/read?source=${encodeURIComponent(it.ref.source ?? "")}&path=${encodeURIComponent(it.ref.path ?? "")}&limit=2500`;
    get(url).then((d) => setText(String(d.body ?? d.text ?? "").slice(0, 2500))).catch((e) => setText(`(couldn't load: ${e.message})`));
  }, [it.key]);
  return (
    <div className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap border border-cyan/20 bg-void/70 px-2 py-1.5 text-left text-ink/80">
      <div className="mb-1 text-mute">{it.by === "pack" ? "excerpt sent with the message" : "start of what the agent opened"} · {it.kind === "note" ? "note" : `${it.ref.source}/${it.ref.path}`}</div>
      {text ?? "loading…"}
    </div>
  );
}
