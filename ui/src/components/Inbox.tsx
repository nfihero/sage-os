import { useState } from "react";
import { post } from "../api";
import type { HubEvent, InboxItem } from "../types";
import { ago, useNow } from "../util";
import Scramble from "./Scramble";
import Review from "./Review";

const LABEL: Record<string, string> = {
  allow_once: "Allow once", allow_session: "Allow for session", allow_always: "Always allow", deny: "Deny",
  reply_unblock: "Reply & unblock", reply_only: "Reply only", approve: "Approve & file", reject: "Reject", save_anyway: "Save anyway",
};
const SOURCE_TONE: Record<string, string> = { claude: "orange", hermes: "", kanban: "amber", bookshelf: "" };

export default function Inbox({ items, onOpenTask, events = [] }: { items: InboxItem[]; onOpenTask: (id: string) => void; events?: HubEvent[] }) {
  const now = useNow(5000);
  const [reviewing, setReviewing] = useState<InboxItem | null>(null);
  // Approving files the notes, but a digest may send its next chapter at once, so the count can stay the same:
  // say what was filed, for a little while after (newest first in events).
  const filed = events.find((e) => e.type === "proposal.applied" && now - e.ts < 20);
  const files: { path: string }[] = filed?.data?.files ?? [];
  const folder = files.length ? files[0].path.split("/").slice(0, -1).join("/") : "";
  return (
    <aside className="panel min-h-0" data-testid="inbox">
      <div className="panel-head">
        <span className="tab"><Scramble text="Inbox" /></span>
        {items.length > 0 && <span className="font-dot pulse-amber bg-amber px-2 text-[16px] leading-[22px] text-void">{items.length}</span>}
      </div>
      <div className="panel-body flex flex-col gap-2">
        {filed && files.length > 0 && (
          <div className="chat-in border border-cyan/40 px-2 py-1 text-[12px] text-ink/90" role="status">
            ✓ Filed {files.length} note{files.length === 1 ? "" : "s"}{folder && <> in <span className="font-mono text-cyan">{folder}</span></>}. Undo in Bookshelf → History.
          </div>
        )}
        {items.length === 0 && <div className="m-auto text-center text-[12.5px] text-mute">Nothing needs you.<br />Claude permission requests, Hermes approvals, worker questions and Bookshelf proposals land here.</div>}
        {items.map((it) => <Card key={it.id} it={it} now={now} onOpenTask={onOpenTask} onReview={setReviewing} />)}
      </div>
      {reviewing && <Review item={reviewing} onClose={() => setReviewing(null)} />}
    </aside>
  );
}

type Change = { op: string; title: string; path: string; from_path: string | null; diff: string };

/** A Bookshelf proposal's changes: what file each one touches, with its diff one click away. */
function Changes({ changes }: { changes: Change[] }) {
  const [open, setOpen] = useState<number | null>(changes.length === 1 ? 0 : null);
  const [all, setAll] = useState(changes.length <= 3);     // long proposals: REVIEW is the way in; files on request
  if (!all) {
    return <button className="mt-1 text-left text-[11px] text-mute hover:text-cyan" onClick={() => setAll(true)}>▸ {changes.length} files and their diffs</button>;
  }
  return (
    <div className="mt-1 flex flex-col gap-1">
      {changes.map((c, i) => (
        <div key={i} className="border border-cyan/15 bg-void/70">
          <button onClick={() => setOpen(open === i ? null : i)} className="flex w-full items-baseline gap-1.5 px-1.5 py-1 text-left text-[11.5px]">
            <span className={`chip ${c.op === "create" ? "" : c.op === "archive" ? "mute" : "amber"}`}>{c.op}</span>
            <span className="min-w-0 flex-1 truncate font-mono text-ink/85" title={c.path}>{c.from_path ? `${c.from_path} → ${c.path}` : c.path}</span>
            <span className="text-mute">{open === i ? "▾" : "▸"}</span>
          </button>
          {open === i && (
            <pre className="max-h-64 overflow-auto border-t border-cyan/15 p-1.5 text-[11px] leading-snug">
              {c.diff.split("\n").map((ln, j) => (
                <div key={j} className={ln.startsWith("+") && !ln.startsWith("+++") ? "text-cyan" : ln.startsWith("-") && !ln.startsWith("---") ? "text-red" : "text-mute"}>{ln || " "}</div>
              ))}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}

function Card({ it, now, onOpenTask, onReview }: { it: InboxItem; now: number; onOpenTask: (id: string) => void; onReview: (it: InboxItem) => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const needsNote = it.source === "kanban";
  const held = !!it.context.held;              // K4: screened as secret-looking, kept in memory only
  const [show, setShow] = useState(false);
  const [armed, setArmed] = useState(false);   // "Save anyway" needs a second, deliberate click
  const decide = async (choice: string) => {
    if (choice === "save_anyway" && !armed) { setArmed(true); return; }
    setBusy(true); setErr(null);
    try { await post(`/api/inbox/${encodeURIComponent(it.id)}`, { choice, note }); }
    catch (e) { setErr(String((e as Error).message)); setBusy(false); }
  };
  const tone = SOURCE_TONE[it.source] ?? "";
  return (
    <div className={`card cursor-default ${it.source === "kanban" || held ? "blocked" : ""}`} data-inbox={it.id}>
      <div className="flex items-center gap-2 text-[11px]">
        <span className={`chip ${tone}`}>{it.source}</span>
        {held && <span className="chip amber">🔒 held</span>}
        {it.context.task_id && <button className="text-cyan hover:underline" onClick={() => onOpenTask(it.context.task_id)}>{it.context.task_id}</button>}
        {it.context.session_title && <span className="truncate text-mute">{it.context.session_title}</span>}
        <span className="ml-auto text-mute">{ago(it.created, now)}</span>
      </div>
      <div className="mt-1 text-[13px] text-ink">{it.title}</div>
      {it.detail && (it.source === "gamemode" || it.source === "bookshelf"
        ? <p className="copy mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-ink/85">{it.detail}</p>     /* sentences */
        : <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap border border-cyan/15 bg-void/70 p-1.5 text-[12px] text-ink/85">{it.detail}</pre>)}
      {it.source === "bookshelf" && !held && it.context.proposal_id && (it.context.changes ?? []).length > 0 && (
        <button className="chip mt-1.5 h-7 px-2.5" onClick={() => onReview(it)}
          title="Read each note, keep or drop it, edit it, then approve only what you kept">
          REVIEW {(it.context.changes ?? []).length} NOTE{(it.context.changes ?? []).length === 1 ? "" : "S"}
        </button>
      )}
      {it.source === "bookshelf" && (!held || show) && <Changes changes={it.context.changes ?? []} />}
      {held && !show && (
        <button className="mt-1 text-left text-[11.5px] text-amber underline" onClick={() => setShow(true)}>
          Show content (it may display the secret on screen)
        </button>
      )}
      {armed && <div className="mt-1 text-[11.5px] text-amber">Saving it anyway stores it in your vault and the undo journal (only the kind of secret is logged). Its text stays out of search. Click again to confirm.</div>}
      {it.context.problem && <div className="mt-1 text-[11.5px] text-amber">{String(it.context.problem)}</div>}
      {it.context.cwd && <div className="mt-0.5 text-[11px] text-mute">in {it.context.cwd}</div>}
      {it.context.reason && <div className="mt-0.5 text-[11px] text-amber/90">{String(it.context.reason)}</div>}
      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={needsNote ? 3 : 1}
        placeholder={needsNote ? "Your answer to the worker (required)" : it.source === "bookshelf" ? "Note (optional; kept with your decision; don't paste secrets)" : "Note (optional; sent with a deny)"}
        className="mt-1.5 w-full resize-y border border-cyan/25 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {it.choices.map((c) => (
          <button key={c} disabled={busy || (needsNote && !note.trim())} onClick={() => decide(c)}
            className={`chip h-7 px-2.5 disabled:opacity-40 ${c === "deny" || c === "reject" ? "red" : c === "save_anyway" ? "amber" : c.startsWith("allow") || c === "reply_unblock" || c === "approve" ? "" : "mute"}`}>
            {c === "save_anyway" && armed ? "Confirm: save it anyway" : LABEL[c] ?? c}
          </button>
        ))}
      </div>
      {err && <div className="mt-1 text-[11.5px] text-red">{err}</div>}
    </div>
  );
}
