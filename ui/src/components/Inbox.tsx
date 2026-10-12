import { useMemo, useState } from "react";
import { post } from "../api";
import type { Batch, HubEvent, InboxItem, Verdict } from "../types";
import { useNow } from "../util";
import Scramble from "./Scramble";
import { Ago } from "./Readout";
import Review from "./Review";

const LABEL: Record<string, string> = {
  allow_once: "Allow once", allow_session: "Allow for session", allow_always: "Always allow", deny: "Deny",
  reply_unblock: "Reply & unblock", reply_only: "Reply only", approve: "Approve & file", reject: "Reject", save_anyway: "Save anyway",
  raise: "Yes, let it", not_now: "Not now", lower: "Ask first again", keep: "Keep as is",
};
const SOURCE_TONE: Record<string, string> = { claude: "orange", hermes: "", kanban: "amber", bookshelf: "", trust: "amber" };

/** The inbox's unit (K7): a Bookshelf group (a chapter's parts) is ONE card, decided in one decision. */
type Entry = { key: string; items: InboxItem[] };
const notesOf = (items: InboxItem[]) => items.reduce((n, i) => n + (i.context.notes ?? (i.context.changes ?? []).length), 0);
const isProposal = (i: InboxItem) => i.source === "bookshelf" && !i.context.held && !!i.context.proposal_id;

export default function Inbox({ items, onOpenTask, events = [], auto = [], onAgents }: {
  items: InboxItem[]; onOpenTask: (id: string) => void; events?: HubEvent[]; auto?: Batch[]; onAgents?: () => void;
}) {
  const now = useNow(5000);
  const [reviewing, setReviewing] = useState<InboxItem[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const entries = useMemo<Entry[]>(() => {
    const out: Entry[] = [], byGroup = new Map<string, Entry>();
    for (const it of items) {
      const g = isProposal(it) ? it.context.group : null;
      if (g && byGroup.has(g)) { byGroup.get(g)!.items.push(it); continue; }
      const e = { key: g ? `group:${g}` : it.id, items: [it] };
      if (g) byGroup.set(g, e);
      out.push(e);
    }
    return out;
  }, [items]);
  // Cards are picked, not parts: a part that joins a picked chapter is in the selection too. Only cards that
  // still wait count.
  const sel = entries.filter((e) => picked.has(e.key)).flatMap((e) => e.items.map((i) => i.id));
  const toggle = (key: string, on: boolean) => {
    const next = new Set(picked);
    if (on) next.add(key); else next.delete(key);
    setPicked(next);
  };
  // Approving files the notes, but a digest may send its next chapter at once, so the count can stay the same:
  // say what was filed, for a little while after (newest first in events).
  const filed = events.find((e) => e.type === "proposal.applied" && !e.data?.auto && now - e.ts < 20);
  const files: { path: string }[] = filed?.data?.files ?? [];
  const folder = files.length ? files[0].path.split("/").slice(0, -1).join("/") : "";
  const recentAuto = auto.filter((b) => b.status === "applied" && now - (b.finished ?? b.started) < 7 * 86400);
  return (
    <aside className="panel min-h-0" data-testid="inbox">
      <div className="panel-head">
        <span className="tab"><Scramble text="Inbox" /></span>
        {entries.length > 0 && <span className="font-dot pulse-amber bg-amber px-2 text-[16px] leading-[22px] text-void" title={`${items.length} items`}>{entries.length}</span>}
        {onAgents && <button className="chip mute ml-auto" onClick={onAgents} title="Trust levels, roles and what every agent did">AGENTS</button>}
      </div>
      <div className="panel-body flex flex-col gap-2">
        {filed && files.length > 0 && (
          <div className="chat-in border border-cyan/40 px-2 py-1 text-[12px] text-ink/90" role="status">
            ✓ Filed {files.length} note{files.length === 1 ? "" : "s"}{folder && <> in <span className="font-mono text-cyan">{folder}</span></>}. Undo in Bookshelf → History.
          </div>
        )}
        {sel.length > 0 && <Selection ids={sel} items={items} onDone={() => setPicked(new Set())} />}
        {recentAuto.length > 0 && <FiledForYou batches={recentAuto} now={now} onAgents={onAgents} />}
        {items.length === 0 && <div className="m-auto text-center text-[12.5px] text-mute">Nothing needs you.<br />Claude permission requests, Hermes approvals, worker questions and Bookshelf proposals land here.</div>}
        {entries.map((e) => e.items[0].context.group && isProposal(e.items[0])
          ? <GroupCard key={e.key} items={e.items} now={now} picked={picked.has(e.key)}
              onPick={(on) => toggle(e.key, on)} onReview={setReviewing} />
          : <Card key={e.key} it={e.items[0]} now={now} onOpenTask={onOpenTask} onReview={(it) => setReviewing([it])}
              picked={picked.has(e.key)} onPick={isProposal(e.items[0]) ? (on) => toggle(e.key, on) : undefined} />)}
      </div>
      {reviewing && <Review items={reviewing} onClose={() => setReviewing(null)} />}
    </aside>
  );
}

/** Several selected cards, decided together: one batch, one undo (K7). */
function Selection({ ids, items, onDone }: { ids: string[]; items: InboxItem[]; onDone: () => void }) {
  const [armed, setArmed] = useState<"approve" | "reject" | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const chosen = items.filter((i) => ids.includes(i.id));
  const n = notesOf(chosen);
  const go = async (choice: "approve" | "reject") => {
    if (armed !== choice) { setArmed(choice); return; }
    setBusy(true); setErr(null);
    try { await post("/api/inbox/batch", { ids, choice }); onDone(); }
    catch (e) { setErr(String((e as Error).message)); }
    setBusy(false); setArmed(null);
  };
  return (
    <div className="sticky top-0 z-10 border border-cyan/50 bg-void/95 px-2 py-1.5 text-[12px]" role="region" aria-label="selected cards">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-ink"><span className="font-dot glow-cyan text-[15px]">{ids.length}</span> selected · {n} note{n === 1 ? "" : "s"}</span>
        <span className="ml-auto flex gap-1.5">
          <button className="chip h-7 px-2.5" disabled={busy} onClick={() => go("approve")}>
            {armed === "approve" ? `CONFIRM: FILE ${n}` : "APPROVE ALL"}</button>
          <button className="chip red h-7 px-2.5" disabled={busy} onClick={() => go("reject")}>
            {armed === "reject" ? `CONFIRM: REJECT ${ids.length}` : "REJECT ALL"}</button>
          <button className="chip mute h-7 px-2" onClick={onDone} aria-label="clear selection">✕</button>
        </span>
      </div>
      {armed && <div className="mt-1 text-[11.5px] text-ink/75">{armed === "approve"
        ? `Files every note of these cards as one batch: one undo in History, which can undo single notes too.`
        : `Rejects these cards; nothing is written.`} Click again to confirm.</div>}
      {err && <div className="mt-1 text-[11.5px] text-red">{err}</div>}
    </div>
  );
}

/** What agents filed by themselves this week (their trust level), each undoable. */
function FiledForYou({ batches, now, onAgents }: { batches: Batch[]; now: number; onAgents?: () => void }) {
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const notes = batches.reduce((n, b) => n + b.files.filter((f) => f.op !== "remove" && !f.undone).length, 0);
  const undo = async (id: string) => {
    setErr(null);
    try { await post(`/api/vault/batches/${id}/undo`); } catch (e) { setErr(String((e as Error).message)); }
  };
  return (
    <div className="border border-cyan/20 px-2 py-1 text-[12px]">
      <button className="flex w-full items-baseline gap-1.5 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="text-[11px] uppercase tracking-[.16em] text-mute">Filed for you</span>
        <span className="text-ink/80">{notes} note{notes === 1 ? "" : "s"} this week, by agents you trust</span>
        <span className="ml-auto text-mute">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="mt-1 flex flex-col gap-1">
          {batches.map((b) => (
            <div key={b.id} className="flex items-baseline gap-1.5 border-t border-dashed border-cyan/10 pt-1">
              <span className="min-w-0 flex-1 truncate text-ink/85" title={b.summary}>{b.summary || b.id}</span>
              <Ago ts={b.finished ?? b.started} now={now} />
              <button className="chip mute" onClick={() => undo(b.id)} title="Put these notes back exactly as they were">UNDO</button>
            </div>
          ))}
          {onAgents && <button className="text-left text-[11px] text-cyan hover:underline" onClick={onAgents}>Trust levels and every agent's activity →</button>}
          {err && <div className="text-[11.5px] text-red">{err}</div>}
        </div>
      )}
    </div>
  );
}

function verdictOf(items: InboxItem[]): { drops: number; reviewed: number; by?: string; state?: Verdict["status"]; why?: string } {
  let drops = 0, reviewed = 0, by: string | undefined, state: Verdict["status"] | undefined, why: string | undefined;
  for (const i of items) {
    const v = i.context.verdict as Verdict | null | undefined;
    if (!v) continue;
    if (v.status === "done") { drops += Object.keys(v.drops ?? {}).length; reviewed += v.reviewed ?? 0; by = v.by; }
    else { state = v.status; why = v.reason ?? v.error; }
  }
  return { drops, reviewed, by, state, why };
}

function VerdictLine({ items }: { items: InboxItem[] }) {
  const v = verdictOf(items);
  if (v.state) return <div className="mt-1 text-[11.5px] text-mute">Reviewer: {v.state === "failed" ? <span className="text-amber">couldn't review ({v.why})</span> : v.state === "waiting" ? `waiting (${v.why})` : `${v.state}…`}</div>;
  if (!v.reviewed) return null;
  return (
    <div className="mt-1 text-[11.5px] text-ink/85" title="The Reviewer only marks notes; you decide">
      <span className="text-[11px] uppercase tracking-[.16em] text-mute">Reviewer</span>{" "}
      {v.drops ? <>would drop <span className="font-dot text-[14px] text-amber">{v.drops}</span> of {v.reviewed}</> : <>keeps all {v.reviewed}</>}
      {v.by && <span className="text-mute"> · {v.by}</span>}
    </div>
  );
}

/** One chapter (or run) in several parts: one card, one decision (K7). */
function GroupCard({ items, now, picked, onPick, onReview }: {
  items: InboxItem[]; now: number; picked: boolean; onPick: (on: boolean) => void; onReview: (its: InboxItem[]) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [armed, setArmed] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const first = items[0];
  const n = notesOf(items);
  const v = verdictOf(items);
  const problems = items.map((i) => i.context.problem).filter(Boolean);
  const ids = items.map((i) => i.id);
  const decide = async (choice: "approve" | "reject" | "approve_kept") => {
    if (armed !== choice) { setArmed(choice); return; }
    setBusy(true); setErr(null);
    // "Approve without the Reviewer's drops": each part keeps the notes the Reviewer didn't mark.
    const reviews = choice === "approve_kept" ? Object.fromEntries(items.map((i) => {
      const drops = (i.context.verdict as Verdict | undefined)?.drops ?? {};
      const total = i.context.notes ?? (i.context.changes ?? []).length;
      return [i.context.proposal_id, { keep: [...Array(total).keys()].filter((k) => !(String(k) in drops)), edits: {} }];
    })) : undefined;
    try { await post("/api/inbox/batch", { ids, choice: choice === "reject" ? "reject" : "approve", note, reviews }); }
    catch (e) { setErr(String((e as Error).message)); setBusy(false); setArmed(null); }
  };
  const ask = async () => {
    setErr(null);
    try { await post("/api/reviewer/review", { proposal_ids: items.map((i) => i.context.proposal_id) }); }
    catch (e) { setErr(String((e as Error).message)); }
  };
  return (
    <div className={`card cursor-default ${picked ? "!border-cyan" : ""}`} data-inbox={first.id}>
      <div className="flex items-center gap-2 text-[11px]">
        <input type="checkbox" checked={picked} onChange={(e) => onPick(e.target.checked)} aria-label="select this card"
          className="accent-[var(--color-cyan)]" />
        <span className="chip">{first.context.agent_label ?? first.source}</span>
        {items.length > 1 && <span className="text-mute">{items.length} parts</span>}
        <Ago ts={first.created} now={now} className="ml-auto" />
      </div>
      <div className="mt-1 text-[13px] text-ink">{first.context.group_title ?? first.title}</div>
      <div className="mt-0.5 text-[12px] text-ink/75"><span className="font-dot glow-cyan text-[15px]">{n}</span> notes. Nothing is filed until you approve.</div>
      <VerdictLine items={items} />
      {problems.map((p, k) => <div key={k} className="mt-1 text-[11.5px] text-amber">{String(p)}</div>)}
      {armed && <div className="mt-1 text-[11.5px] text-ink/75">{armed === "reject" ? `Rejects every part; nothing is written.`
        : armed === "approve_kept" ? `Files ${n - v.drops} notes and leaves out the ${v.drops} the Reviewer marked, as one batch.`
        : `Files all ${n} notes as one batch; History can undo the batch or single notes.`} Click again to confirm.</div>}
      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={1} placeholder="Note (optional; kept with your decision; don't paste secrets)"
        className="mt-1.5 w-full resize-y border border-cyan/25 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        <button className="chip h-7 px-2.5" onClick={() => onReview(items)} title="Read every note of every part, keep or drop, edit">REVIEW {n}</button>
        <button className="chip h-7 px-2.5" disabled={busy} onClick={() => decide("approve")}>{armed === "approve" ? `CONFIRM: FILE ${n}` : `APPROVE ALL ${n}`}</button>
        {v.drops > 0 && <button className="chip h-7 px-2.5" disabled={busy} onClick={() => decide("approve_kept")}>
          {armed === "approve_kept" ? `CONFIRM: FILE ${n - v.drops}` : `APPROVE ${n - v.drops} (REVIEWER'S DROPS OUT)`}</button>}
        <button className="chip red h-7 px-2.5" disabled={busy} onClick={() => decide("reject")}>{armed === "reject" ? "CONFIRM: REJECT" : "REJECT ALL"}</button>
        {!v.reviewed && (!v.state || v.state === "failed") && <button className="chip mute h-7 px-2.5" onClick={ask} title="A model reads the notes first and marks the ones it would drop; you still decide">ASK REVIEWER</button>}
      </div>
      {err && <div className="mt-1 text-[11.5px] text-red">{err}</div>}
    </div>
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

function Card({ it, now, onOpenTask, onReview, picked, onPick }: {
  it: InboxItem; now: number; onOpenTask: (id: string) => void; onReview: (it: InboxItem) => void;
  picked?: boolean; onPick?: (on: boolean) => void;
}) {
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
  const proposal = isProposal(it);
  return (
    <div className={`card cursor-default ${it.source === "kanban" || held ? "blocked" : ""} ${picked ? "!border-cyan" : ""}`} data-inbox={it.id}>
      <div className="flex items-center gap-2 text-[11px]">
        {onPick && <input type="checkbox" checked={!!picked} onChange={(e) => onPick(e.target.checked)} aria-label="select this card"
          className="accent-[var(--color-cyan)]" />}
        <span className={`chip ${tone}`}>{proposal ? it.context.agent_label ?? it.source : it.source}</span>
        {held && <span className="chip amber">🔒 held</span>}
        {it.context.task_id && <button className="text-cyan hover:underline" onClick={() => onOpenTask(it.context.task_id)}>{it.context.task_id}</button>}
        {it.context.session_title && <span className="truncate text-mute">{it.context.session_title}</span>}
        <Ago ts={it.created} now={now} className="ml-auto" />
      </div>
      <div className="mt-1 text-[13px] text-ink">{it.title}</div>
      {it.detail && (it.source === "gamemode" || it.source === "bookshelf" || it.source === "trust"
        ? <p className="copy mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-ink/85">{it.detail}</p>     /* sentences */
        : <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap border border-cyan/15 bg-void/70 p-1.5 text-[12px] text-ink/85">{it.detail}</pre>)}
      {proposal && <VerdictLine items={[it]} />}
      {proposal && (it.context.changes ?? []).length > 0 && (
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
      {it.source !== "trust" && (
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={needsNote ? 3 : 1}
          placeholder={needsNote ? "Your answer to the worker (required)" : it.source === "bookshelf" ? "Note (optional; kept with your decision; don't paste secrets)" : "Note (optional; sent with a deny)"}
          className="mt-1.5 w-full resize-y border border-cyan/25 bg-void/80 px-2 py-1 text-[12.5px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
      )}
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {it.choices.map((c) => (
          <button key={c} disabled={busy || (needsNote && !note.trim())} onClick={() => decide(c)}
            className={`chip h-7 px-2.5 disabled:opacity-40 ${c === "deny" || c === "reject" ? "red" : c === "save_anyway" || c === "raise" ? "amber" : c.startsWith("allow") || c === "reply_unblock" || c === "approve" || c === "lower" ? "" : "mute"}`}>
            {c === "save_anyway" && armed ? "Confirm: save it anyway" : LABEL[c] ?? c}
          </button>
        ))}
      </div>
      {err && <div className="mt-1 text-[11.5px] text-red">{err}</div>}
    </div>
  );
}
