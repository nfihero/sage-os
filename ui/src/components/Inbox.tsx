import { useState } from "react";
import { post } from "../api";
import type { InboxItem } from "../types";
import { ago, useNow } from "../util";
import Scramble from "./Scramble";

const LABEL: Record<string, string> = {
  allow_once: "Allow once", allow_session: "Allow for session", allow_always: "Always allow", deny: "Deny",
  reply_unblock: "Reply & unblock", reply_only: "Reply only",
};
const SOURCE_TONE: Record<string, string> = { claude: "orange", hermes: "", kanban: "amber" };

export default function Inbox({ items, onOpenTask }: { items: InboxItem[]; onOpenTask: (id: string) => void }) {
  const now = useNow(5000);
  return (
    <aside className="panel min-h-0" data-testid="inbox">
      <div className="panel-head">
        <span className="tab"><Scramble text="Inbox" /></span>
        {items.length > 0 && <span className="font-dot pulse-amber bg-amber px-2 text-[16px] leading-[22px] text-void">{items.length}</span>}
      </div>
      <div className="panel-body flex flex-col gap-2">
        {items.length === 0 && <div className="m-auto text-center text-[12.5px] text-mute">Nothing needs you.<br />Claude permission requests, Hermes approvals and worker questions land here.</div>}
        {items.map((it) => <Card key={it.id} it={it} now={now} onOpenTask={onOpenTask} />)}
      </div>
    </aside>
  );
}

function Card({ it, now, onOpenTask }: { it: InboxItem; now: number; onOpenTask: (id: string) => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const needsNote = it.source === "kanban";
  const decide = async (choice: string) => {
    setBusy(true); setErr(null);
    try { await post(`/api/inbox/${encodeURIComponent(it.id)}`, { choice, note }); }
    catch (e) { setErr(String((e as Error).message)); setBusy(false); }
  };
  const tone = SOURCE_TONE[it.source] ?? "";
  return (
    <div className={`card cursor-default ${it.source === "kanban" ? "blocked" : ""}`} data-inbox={it.id}>
      <div className="flex items-center gap-2 text-[11px]">
        <span className={`chip ${tone}`}>{it.source}</span>
        {it.context.task_id && <button className="text-cyan hover:underline" onClick={() => onOpenTask(it.context.task_id)}>{it.context.task_id}</button>}
        {it.context.session_title && <span className="truncate text-mute">{it.context.session_title}</span>}
        <span className="ml-auto text-mute">{ago(it.created, now)}</span>
      </div>
      <div className="mt-1 text-[13px] text-ink">{it.title}</div>
      {it.detail && <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap border border-cyan/15 bg-void/70 p-1.5 text-[12px] text-ink/85">{it.detail}</pre>}
      {it.context.cwd && <div className="mt-0.5 text-[10.5px] text-mute">in {it.context.cwd}</div>}
      {it.context.reason && <div className="mt-0.5 text-[11px] text-amber/90">{String(it.context.reason)}</div>}
      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={needsNote ? 3 : 1}
        placeholder={needsNote ? "Your answer to the worker (required)" : "Note (optional; sent with a deny)"}
        className="mt-1.5 w-full resize-y border border-cyan/25 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {it.choices.map((c) => (
          <button key={c} disabled={busy || (needsNote && !note.trim())} onClick={() => decide(c)}
            className={`chip h-7 px-2.5 disabled:opacity-40 ${c === "deny" ? "red" : c.startsWith("allow") || c === "reply_unblock" ? "" : "mute"}`}>
            {LABEL[c] ?? c}
          </button>
        ))}
      </div>
      {err && <div className="mt-1 text-[11.5px] text-red">{err}</div>}
    </div>
  );
}
