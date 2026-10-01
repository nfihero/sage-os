import { useEffect, useState } from "react";
import type { TaskDetail } from "../types";
import { shortModel, stamp } from "../util";

export default function TaskDrawer({ id, onClose, onOpen }: { id: string; onClose: () => void; onOpen: (id: string) => void }) {
  const [d, setD] = useState<TaskDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setD(null); setErr(null);
    fetch(`/api/tasks/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setD).catch((e) => setErr(String(e)));
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [id]);

  const t = d?.task;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-void/60 backdrop-blur-sm" onClick={onClose}>
      <div className="panel h-full w-full min-w-0 max-w-[760px]" onClick={(e) => e.stopPropagation()} data-testid="task-drawer">
        <div className="panel-head">
          <span>{id}</span>
          {t && <span className={`chip normal-case tracking-normal ${t.status === "blocked" ? "amber" : ""}`}>{t.status}</span>}
          <button onClick={onClose} className="ml-auto text-mute hover:text-cyan" aria-label="close">✕</button>
        </div>
        <div className="panel-body flex min-w-0 flex-col gap-4 overflow-x-hidden text-[12.5px]">
          {err && <div className="text-red">{err}</div>}
          {!d && !err && <div className="text-mute">loading…</div>}
          {t && d && (
            <>
              <div>
                <h2 className="display text-sm text-ink">{t.title}</h2>
                <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                  {t.assignee && <span className="chip">{t.assignee}</span>}
                  {t.model_override && <span className="chip mute">{shortModel(t.model_override)}</span>}
                  <span className="chip mute">created {stamp(t.created_at)}</span>
                  {t.completed_at && <span className="chip mute">done {stamp(t.completed_at)}</span>}
                  {d.parents.map((p) => <button key={p} className="chip" onClick={() => onOpen(p)}>↑ {p}</button>)}
                  {d.children.map((c) => <button key={c} className="chip" onClick={() => onOpen(c)}>↓ {c}</button>)}
                </div>
              </div>

              {t.status === "blocked" && (
                <Section title="Waiting on you" tone="amber">
                  <p className="whitespace-pre-wrap text-amber">{lastBlockReason(d) ?? "blocked"}</p>
                  <p className="mt-1 break-words text-[11px] text-mute">Answering from here arrives in Phase 2. For now: Hermes Desktop kanban, or <code>hermes kanban comment {id} "…"</code> then <code>unblock</code>.</p>
                </Section>
              )}
              {t.result && <Section title="Result"><pre className="whitespace-pre-wrap">{t.result}</pre></Section>}
              {t.body && <Section title="Brief"><pre className="max-h-72 overflow-auto whitespace-pre-wrap text-ink/80">{t.body}</pre></Section>}

              <Section title={`Runs (${d.runs.length})`}>
                {d.runs.map((r) => (
                  <div key={r.id} className="border-l-2 border-cyan/25 py-1 pl-2">
                    <div className="flex flex-wrap gap-x-2 text-[11px]">
                      <span className="text-cyan">#{r.id}</span>
                      <span className={r.outcome === "crashed" ? "text-red" : r.outcome === "blocked" ? "text-amber" : "text-ink"}>{r.outcome ?? r.status}</span>
                      <span className="text-mute">@{r.profile}</span>
                      <span className="text-mute">{stamp(r.started_at)}</span>
                      {r.ended_at && <span className="text-mute">{Math.round(r.ended_at - r.started_at)}s</span>}
                      {d.heartbeats[r.id] && <span className="text-mute">♥ {d.heartbeats[r.id]}</span>}
                    </div>
                    {(r.summary || r.error) && <div className={`mt-0.5 whitespace-pre-wrap text-[11.5px] ${r.error ? "text-red/90" : "text-ink/75"}`}>{r.error ?? r.summary}</div>}
                  </div>
                ))}
              </Section>

              {d.comments.length > 0 && (
                <Section title={`Comments (${d.comments.length})`}>
                  {d.comments.map((c, i) => (
                    <div key={i} className="py-1"><span className="text-cyan">{c.author}</span> <span className="text-mute">{stamp(c.created_at)}</span>
                      <div className="whitespace-pre-wrap text-ink/80">{c.body}</div></div>
                  ))}
                </Section>
              )}

              <Section title={`History (${d.events.length})`}>
                {d.events.map((e) => (
                  <div key={e.id} className="flex gap-2 text-[11.5px]">
                    <span className="w-24 shrink-0 text-mute sm:w-28">{stamp(e.created_at)}</span>
                    <span className="w-8 shrink-0 text-mute">{e.run_id ? `#${e.run_id}` : ""}</span>
                    <span className={e.kind === "crashed" ? "text-red" : e.kind === "blocked" ? "text-amber" : "text-ink"}>{e.kind}</span>
                    {e.payload && <span className="min-w-0 flex-1 truncate text-mute">{typeof e.payload === "string" ? e.payload : JSON.stringify(e.payload)}</span>}
                  </div>
                ))}
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function lastBlockReason(d: TaskDetail): string | null {
  const b = [...d.events].reverse().find((e) => e.kind === "blocked");
  return b?.payload?.reason ?? null;
}

function Section({ title, tone, children }: { title: string; tone?: "amber"; children: React.ReactNode }) {
  return (
    <div className={tone === "amber" ? "border border-amber/50 bg-amber/5 p-2" : ""}>
      <div className={`display mb-1.5 text-[10px] ${tone === "amber" ? "text-amber" : "text-cyan/80"}`}>{title}</div>
      {children}
    </div>
  );
}
