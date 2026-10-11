import { useState } from "react";
import type { Guard, HubEvent } from "../types";
import { ago, clock, useNow } from "../util";

export default function Rail({ safety, events, onOpen }: { safety: Guard[]; events: HubEvent[]; onOpen: (id: string) => void }) {
  const [tab, setTab] = useState<"safety" | "activity">("safety");
  const [blocksOnly, setBlocksOnly] = useState(false);
  const now = useNow(5000);
  const feed = [...safety].reverse().filter((g) => !blocksOnly || g.event !== "allow");
  const day = safety.filter((g) => now - g.ts < 86400);
  const blocks24 = day.filter((g) => g.event === "block").length;
  const activity = events.filter((e) => e.type !== "task.heartbeat" && e.source !== "safety");

  return (
    <aside className="panel min-h-0">
      <div className="panel-head">
        {(["safety", "activity"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`htab ${tab === t ? "on" : ""}`}>
            {t === "safety" ? "Safety feed" : "Activity"}
          </button>
        ))}
        {tab === "safety" && (
          <label className="ml-auto flex cursor-pointer items-center gap-1.5 text-[11px] normal-case tracking-normal text-mute">
            <input type="checkbox" checked={blocksOnly} onChange={(e) => setBlocksOnly(e.target.checked)} className="accent-cyan-400" />
            non-allow only
          </label>
        )}
      </div>
      {tab === "safety" ? (
        <>
          <div className="flex gap-3 border-b border-cyan/10 px-3 py-1.5 text-[11px] text-mute">
            <span>last {safety.length}</span>
            <span>24h: <span className="text-ink">{day.length}</span> checks</span>
            <span className={blocks24 ? "text-red" : ""}>{blocks24} blocked</span>
          </div>
          <div className="panel-body flex flex-col gap-1" data-testid="safety-feed">
            {feed.map((g, i) => <GuardRow key={`${g.ts}-${i}`} g={g} now={now} />)}
          </div>
        </>
      ) : (
        <div className="panel-body flex flex-col gap-1">
          {activity.length === 0 && <div className="text-mute">No events yet. Board changes, model swaps and service up/down land here.</div>}
          {activity.map((e, i) => (
            <div key={`${e.id ?? "t"}-${e.ts}-${i}`} className="flex gap-2 border-l-2 border-cyan/30 pl-2 text-[12px]">
              <span className="w-16 shrink-0 text-mute">{clock(e.ts)}</span>
              <EventText e={e} onOpen={onOpen} />
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

function GuardRow({ g, now }: { g: Guard; now: number }) {
  const [open, setOpen] = useState(false);
  const bad = g.event === "block";
  const warn = !bad && g.event !== "allow";
  const tone = bad ? "border-red/70 bg-red/10" : warn ? "border-amber/60 bg-amber/5" : "border-cyan/15";
  return (
    <div className={`cursor-pointer border-l-2 px-2 py-1 ${tone}`} onClick={() => setOpen(!open)} data-event={g.event}>
      <div className="flex items-center gap-2 text-[11px]">
        <span className={`chip ${bad ? "red" : warn ? "amber" : "mute"}`}>{g.event.toUpperCase()}</span>
        <span className={g.gate === "guardian" ? "text-cyan/80" : "text-ink/70"}>{g.gate}</span>
        <span className="text-mute">{g.tool}</span>
        {g.ms != null && <span className="text-mute">{g.ms} ms</span>}
        <span className="ml-auto text-mute" title={new Date(g.ts * 1000).toLocaleString()}>{ago(g.ts, now)}</span>
      </div>
      <div className={`mt-0.5 font-mono text-[11.5px] ${bad ? "text-red" : "text-ink/75"} ${open ? "whitespace-pre-wrap break-all" : "truncate"}`}>
        {g.detail || g.error || "—"}
      </div>
      {(g.reason || (open && g.error)) && <div className="text-[11px] text-amber/90">{g.reason ?? g.error}</div>}
    </div>
  );
}

function EventText({ e, onOpen }: { e: HubEvent; onOpen: (id: string) => void }) {
  const d = e.data ?? {};
  if (e.kind === "task") {
    const what = e.type.replace("task.", "");
    const reason = d.payload && typeof d.payload === "object" ? d.payload.reason ?? d.payload.summary : null;
    return (
      <span className="min-w-0">
        <button className="text-cyan hover:underline" onClick={() => onOpen(d.task_id)}>{d.task_id}</button>{" "}
        <span className={what === "blocked" ? "text-amber" : what === "crashed" ? "text-red" : "text-ink"}>{what}</span>{" "}
        <span className="text-mute">{d.title}</span>
        {reason && <div className="truncate text-[11px] text-mute">{String(reason)}</div>}
      </span>
    );
  }
  if (e.type.startsWith("health.")) {
    const up = e.type !== "health.down";
    return <span className={up ? "text-green" : "text-red"}>{d.service} {e.type.replace("health.", "")}{d.pid ? ` (pid ${d.pid})` : ""}</span>;
  }
  if (e.type === "gpu.model") {
    const a = (d.active ?? []).map((m: any) => `${m.id} (${m.state})`).join(", ") || "nothing loaded";
    return <span className="text-cyan">GPU → {a}</span>;
  }
  if (e.type === "session.activity") return <span className="text-ink/80">{d.profile} · {d.title ?? d.session_id}</span>;
  return <span className="text-mute">{e.type} {JSON.stringify(d).slice(0, 80)}</span>;
}
