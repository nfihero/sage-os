import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Board, HubEvent, Task } from "../types";
import { ago, shortModel, useNow } from "../util";
import Scramble from "./Scramble";

const ORDER = ["triage", "todo", "ready", "running", "review", "blocked", "done"];
type Trail = { key: number; left: number; width: number; reverse: boolean };

export default function BoardView({ board, events, onOpen, compact }: {
  board?: Board; events: HubEvent[]; onOpen: (id: string) => void; compact: boolean;
}) {
  const now = useNow(5000);
  const tasks = board?.tasks ?? [];
  const cols = [...ORDER, ...new Set(tasks.map((t) => t.status).filter((s) => !ORDER.includes(s)))];
  const by = (s: string) => tasks.filter((t) => t.status === s)
    .sort((a, b) => (b.completed_at ?? b.started_at ?? b.created_at) - (a.completed_at ?? a.started_at ?? a.created_at));
  const beat = new Map<string, number>();
  for (const e of events) if (e.type === "task.heartbeat" && !beat.has(e.data.task_id)) beat.set(e.data.task_id, e.ts);

  // Light-cycle trail when a task changes column.
  const colRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const wrap = useRef<HTMLDivElement>(null);
  const prev = useRef<Map<string, string> | null>(null);
  const [trails, setTrails] = useState<Trail[]>([]);
  useLayoutEffect(() => {
    const cur = new Map(tasks.map((t) => [t.id, t.status]));
    if (prev.current && wrap.current) {
      const base = wrap.current.getBoundingClientRect().left - wrap.current.scrollLeft;
      const add: Trail[] = [];
      for (const [id, st] of cur) {
        const was = prev.current.get(id);
        const a = colRefs.current[was ?? "triage"], b = colRefs.current[st];
        if (was !== st && a && b) {
          const ax = a.getBoundingClientRect().left + a.offsetWidth / 2 - base;
          const bx = b.getBoundingClientRect().left + b.offsetWidth / 2 - base;
          add.push({ key: Math.random(), left: Math.min(ax, bx), width: Math.abs(bx - ax) || 40, reverse: bx < ax });
        }
      }
      if (add.length) setTrails((t) => [...t, ...add]);
    }
    prev.current = cur;
  }, [board]);
  useEffect(() => {
    if (!trails.length) return;
    const t = setTimeout(() => setTrails([]), 1300);
    return () => clearTimeout(t);
  }, [trails]);

  const [openCol, setOpenCol] = useState<string | null>("blocked");

  return (
    <section className="panel min-h-0" data-testid="board">
      <div className="panel-head">
        <span className="tab"><Scramble text="Board" /></span>
        <span className="text-[10px] normal-case tracking-normal text-mute">{tasks.length} open · {board?.archived ?? 0} archived</span>
      </div>
      {compact ? (
        <div className="panel-body flex flex-col gap-1">
          {cols.map((c) => {
            const list = by(c);
            if (!list.length && !ORDER.includes(c)) return null;
            return (
              <div key={c}>
                <button onClick={() => setOpenCol(openCol === c ? null : c)}
                  className={`flex w-full items-center justify-between border-b border-cyan/15 py-2 ${c === "blocked" && list.length ? "text-amber" : ""}`}>
                  <span className="display text-[11px] uppercase">{c}</span><span>{list.length}</span>
                </button>
                {openCol === c && <div className="flex flex-col gap-1.5 py-1.5">{list.map((t) => <Card key={t.id} t={t} now={now} beat={beat.get(t.id)} onOpen={onOpen} />)}</div>}
              </div>
            );
          })}
        </div>
      ) : (
        <div ref={wrap} className="panel-body relative flex gap-2 overflow-x-auto">
          {trails.map((t) => (
            <div key={t.key} className={`cycle ${t.reverse ? "reverse" : ""}`} style={{ left: t.left, width: t.width, top: 4 }} />
          ))}
          {cols.map((c) => {
            const list = by(c);
            return (
              <div key={c} ref={(el) => { colRefs.current[c] = el; }} data-col={c}
                className={`flex flex-col gap-1.5 ${list.length ? "min-w-[230px] flex-1" : "w-[92px] shrink-0 opacity-60"}`}>
                <div className={`display flex items-center justify-between border-b pb-1.5 text-[11.5px] uppercase ${c === "blocked" && list.length ? "border-amber/60 text-amber" : "border-cyan/25 text-cyan/80"}`}>
                  <span>{c}</span><span className={c === "blocked" && list.length ? "font-dot text-[18px] leading-none" : ""}>{list.length}</span>
                </div>
                <div className="flex min-h-0 flex-col gap-1.5 overflow-y-auto pr-0.5">
                  {list.slice(0, c === "done" ? 8 : 50).map((t) => <Card key={t.id} t={t} now={now} beat={beat.get(t.id)} onOpen={onOpen} />)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Card({ t, now, beat, onOpen }: { t: Task; now: number; beat?: number; onOpen: (id: string) => void }) {
  const blocked = t.status === "blocked";
  const running = t.status === "running";
  const hb = beat ?? t.last_heartbeat_at ?? undefined;
  return (
    <div className={`card ${blocked ? "blocked pulse-amber" : running ? "pulse-cyan" : ""}`} onClick={() => onOpen(t.id)} data-task={t.id}>
      <div className="flex items-center gap-1.5 text-[11.5px] text-mute">
        <span className="text-cyan/70">{t.id}</span>
        {t.assignee && <span className="chip">{t.assignee}</span>}
        {(t.consecutive_failures ?? 0) > 0 && <span className="chip red">{t.consecutive_failures}✕</span>}
        <span className="ml-auto">{ago(t.completed_at ?? t.started_at ?? t.created_at, now)}</span>
      </div>
      <div className={`mt-1 line-clamp-3 text-[14px] leading-snug ${blocked ? "text-amber" : "text-ink"}`}>{t.title}</div>
      <div className="mt-1 flex flex-wrap gap-1">
        {blocked && t.block_kind && <span className="chip amber">{t.block_kind.replace("_", " ")}</span>}
        {t.model_override && <span className="chip mute">{shortModel(t.model_override)}</span>}
        {running && hb && <span className="chip">♥ {ago(hb, now)}</span>}
      </div>
    </div>
  );
}
