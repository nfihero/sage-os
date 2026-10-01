import { useEffect, useState } from "react";
import type { Guard, HubEvent } from "../types";
import { ago, useNow } from "../util";
import Rail from "./Rail";

const KEY = "aos.safety.seen";
const loud = (g: Guard) => g.event !== "allow" && g.event !== "sidecar_revived";

function readSeen() {
  try { return Number(localStorage.getItem(KEY)) || Date.now() / 1000; } catch { return Date.now() / 1000; }
}

/** Safety stays out of the way: a quiet chip, a drawer on demand, a toast when something is blocked. */
export function useSafety(safety: Guard[]) {
  const [seen, setSeen] = useState(readSeen);
  const [open, setOpen] = useState(false);
  const unseen = safety.filter((g) => loud(g) && g.ts > seen);
  const markSeen = () => {
    const t = Date.now() / 1000;
    setSeen(t);
    try { localStorage.setItem(KEY, String(t)); } catch { /* private mode */ }
  };
  return {
    open, unseen,
    toggle: () => { if (!open) markSeen(); setOpen(!open); },
    close: () => { markSeen(); setOpen(false); },
  };
}

export function SafetyChip({ safety, unseen, onClick }: { safety: Guard[]; unseen: Guard[]; onClick: () => void }) {
  const now = Date.now() / 1000;
  const day = safety.filter((g) => now - g.ts < 86400).length;
  return (
    <button onClick={onClick} data-testid="safety-chip"
      className={`chip ${unseen.length ? "red pulse-amber" : "mute"}`}
      title={unseen.length ? `${unseen.length} new block/error since you last looked` : `${day} guard checks in 24h, nothing new blocked`}>
      {unseen.length ? <span className="font-dot text-[14px] leading-none">⚠ {unseen.length} BLOCKED</span> : `SAFETY ✓ ${day}`}
    </button>
  );
}

export function SafetyDrawer({ open, safety, events, onClose, onOpenTask }: {
  open: boolean; safety: Guard[]; events: HubEvent[]; onClose: () => void; onOpenTask: (id: string) => void;
}) {
  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-void/40" onClick={onClose} />}
      <div className={`drawer ${open ? "open" : ""}`} aria-hidden={!open}>
        <div className="relative flex h-full flex-col">
          <button onClick={onClose} className="absolute right-3 top-2 z-10 text-mute hover:text-cyan" aria-label="close">✕</button>
          <Rail safety={safety} events={events} onOpen={onOpenTask} />
        </div>
      </div>
    </>
  );
}

export function SafetyToast({ unseen, open, onOpen }: { unseen: Guard[]; open: boolean; onOpen: () => void }) {
  const now = useNow(1000);
  const latest = unseen[unseen.length - 1];
  const [dismissed, setDismissed] = useState<number | null>(null);
  useEffect(() => { setDismissed(null); }, [latest?.ts]);
  if (!latest || open || dismissed === latest.ts || now - latest.ts > 20) return null;
  return (
    <div className="toast panel pulse-amber cursor-pointer border-red/70 p-3" onClick={onOpen}>
      <div className="flex items-center gap-2 text-[11px]">
        <span className="font-dot text-[16px] text-red">{latest.event.toUpperCase()}</span>
        <span className="text-ink/80">{latest.gate} · {latest.tool}</span>
        <span className="ml-auto text-mute">{ago(latest.ts, now)}</span>
        <button className="text-mute hover:text-cyan" onClick={(e) => { e.stopPropagation(); setDismissed(latest.ts); }}>✕</button>
      </div>
      <div className="mt-1 truncate font-mono text-[12px] text-red">{latest.detail || latest.error}</div>
      {latest.reason && <div className="mt-0.5 line-clamp-2 text-[11.5px] text-amber/90">{latest.reason}</div>}
    </div>
  );
}
