import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { get, post } from "../api";
import type { InboxItem } from "../types";
import { SAFE_MD } from "./ChatView";

/** K13: review a Bookshelf proposal note by note. Read each note rendered, keep or drop it, edit it (markdown
 *  with a live preview), then file only what you kept. Nothing reaches the vault until "Approve". */
type Change = { op: "create" | "update" | "archive"; uid: string; folder?: string; title?: string; body?: string;
  tags?: string[]; source?: string; type?: string };
type Proposal = { id: string; agent: string; summary: string; status: string; changes: Change[] };
type Edit = { title: string; body: string; tags: string[] };

export default function Review({ item, onClose }: { item: InboxItem; onClose: () => void }) {
  const pid = item.context.proposal_id as string;
  const [p, setP] = useState<Proposal | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [keep, setKeep] = useState<boolean[]>([]);
  const [edits, setEdits] = useState<Record<number, Edit>>({});
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [list, setList] = useState(false);            // phone: the list of notes as its own screen

  useEffect(() => {
    get<Proposal>(`/api/vault/proposals/${encodeURIComponent(pid)}`)
      .then((x) => { setP(x); setKeep(x.changes.map(() => true)); }).catch((e) => setErr(String(e.message)));
  }, [pid]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (editing || (e.target as HTMLElement)?.tagName?.match(/INPUT|TEXTAREA/)) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight" || e.key === "j") setIdx((i) => Math.min(i + 1, (p?.changes.length ?? 1) - 1));
      if (e.key === "ArrowLeft" || e.key === "k") setIdx((i) => Math.max(i - 1, 0));
      if (e.key === "x") setKeep((k) => k.map((v, i) => (i === idx ? !v : v)));
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [editing, p, idx]);

  const kept = keep.filter(Boolean).length;
  const edited = Object.keys(edits).length;
  const cur = p?.changes[idx];
  const shown = useMemo<Edit | null>(() => (cur ? (edits[idx] ?? { title: cur.title ?? "", body: cur.body ?? "", tags: cur.tags ?? [] }) : null),
    [cur, edits, idx]);

  const decide = async (choice: "approve" | "reject") => {
    if (!p) return;
    setBusy(true); setErr(null);
    const reviewed = kept < p.changes.length || edited > 0;
    const review = reviewed ? {
      keep: keep.map((k, i) => (k ? i : -1)).filter((i) => i >= 0),
      edits: Object.fromEntries(Object.entries(edits).filter(([i]) => keep[Number(i)])),
    } : undefined;
    try {
      await post(`/api/inbox/${encodeURIComponent(item.id)}`, choice === "approve" && review ? { choice, note, review } : { choice, note });
      onClose();
    } catch (e) { setErr(String((e as Error).message)); setBusy(false); }
  };

  // A portal: panels use backdrop-filter, which makes `position: fixed` relative to the panel, not the window.
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-center bg-void/70 p-0 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[1300px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="review">
        <div className="panel-head flex-wrap gap-y-1">
          <span className="tab">REVIEW</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-ink/85" title={p?.summary}>{p?.summary || item.title}</span>
          <span className="md:hidden"><button className="chip" onClick={() => setList(!list)}>{list ? "NOTE" : `ALL ${p?.changes.length ?? ""}`}</button></span>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close review">✕</button>
        </div>
        {err && <div className="border-b border-red/40 px-3 py-1 text-[12px] text-red">{err}</div>}
        {!p ? <div className="p-4 text-mute">loading…</div> : (
          <div className="flex min-h-0 flex-1">
            <aside className={`panel-body min-h-0 flex-col gap-0.5 border-cyan/20 md:flex md:w-[300px] md:flex-none md:border-r ${list ? "flex flex-1" : "hidden"}`}>
              <div className="mb-1 flex gap-1.5 text-[11px]">
                <button className="chip" onClick={() => setKeep(keep.map(() => true))}>KEEP ALL</button>
                <button className="chip mute" onClick={() => setKeep(keep.map(() => false))}>DROP ALL</button>
              </div>
              {p.changes.map((c, i) => (
                <div key={i} className={`flex items-center gap-1.5 border-l-2 py-0.5 pl-1.5 text-[12px] ${i === idx ? "border-cyan bg-cyan/10" : "border-transparent"}`}>
                  <input type="checkbox" checked={keep[i] ?? true} aria-label={`keep ${c.title ?? c.uid}`}
                    onChange={() => setKeep(keep.map((v, j) => (j === i ? !v : v)))} className="accent-[var(--color-cyan)]" />
                  <button onClick={() => { setIdx(i); setEditing(false); setList(false); }}
                    className={`min-w-0 flex-1 truncate text-left ${keep[i] ? "text-ink" : "text-mute line-through"}`}>
                    {edits[i]?.title ?? c.title ?? `${c.op} ${c.uid}`}
                  </button>
                  {edits[i] && <span className="text-amber" title="edited by you">✎</span>}
                </div>
              ))}
            </aside>
            <section className={`min-h-0 min-w-0 flex-1 flex-col ${list ? "hidden md:flex" : "flex"}`}>
              {cur && shown && (
                <>
                  <div className="flex flex-wrap items-center gap-1.5 border-b border-cyan/15 px-3 py-1.5 text-[11.5px]">
                    <button className="chip" disabled={idx === 0} onClick={() => { setIdx(idx - 1); setEditing(false); }} aria-label="previous note">←</button>
                    <span className="text-mute">{idx + 1} / {p.changes.length}</span>
                    <button className="chip" disabled={idx === p.changes.length - 1} onClick={() => { setIdx(idx + 1); setEditing(false); }} aria-label="next note">→</button>
                    <span className="chip mute">{cur.op}</span>
                    <span className="ml-auto flex gap-1.5">
                      <button className={`chip ${keep[idx] ? "" : "red"}`} onClick={() => setKeep(keep.map((v, j) => (j === idx ? !v : v)))}
                        title="x">{keep[idx] ? "✓ KEEP" : "✕ DROPPED"}</button>
                      {cur.op !== "archive" && <button className="chip" onClick={() => setEditing(!editing)}>{editing ? "DONE" : "EDIT"}</button>}
                      {edits[idx] && <button className="chip mute" onClick={() => { const e = { ...edits }; delete e[idx]; setEdits(e); }}>UNDO EDIT</button>}
                    </span>
                  </div>
                  {editing ? (
                    <Editor value={shown} onChange={(v) => setEdits({ ...edits, [idx]: v })} />
                  ) : (
                    <article className={`panel-body ${keep[idx] ? "" : "opacity-50"}`}>
                      <div className="mx-auto max-w-[760px]">
                        <h1 className="display mb-1 text-[20px] normal-case tracking-normal text-ink">{shown.title || `(${cur.op} ${cur.uid})`}</h1>
                        <div className="mb-3 flex flex-wrap items-center gap-1.5 text-[11px] text-mute">
                          {cur.folder && <span className="font-mono">{cur.folder}/</span>}
                          {shown.tags.map((t) => <span key={t} className="chip mute normal-case tracking-normal">#{t}</span>)}
                          {edits[idx] && <span className="text-amber">edited by you</span>}
                          {cur.source && <span className="truncate" title={cur.source}>from {cur.source.split("/").pop()}</span>}
                        </div>
                        {cur.op === "archive" ? <p className="text-ink/80">Moves this note to Archive/ (nothing is deleted).</p>
                          : <div className="md reading text-[14.5px] leading-[1.7]"><Markdown remarkPlugins={[remarkGfm]} components={SAFE_MD}>{shown.body || "_(metadata change only)_"}</Markdown></div>}
                      </div>
                    </article>
                  )}
                </>
              )}
              <div className="flex flex-wrap items-center gap-1.5 border-t border-cyan/20 px-3 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] text-[11.5px]">
                <span className="text-ink/85">{kept} of {p.changes.length} kept{edited ? ` · ${edited} edited` : ""}</span>
                <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="note (optional)"
                  className="min-w-[120px] flex-1 border border-cyan/25 bg-void/80 px-2 py-1 text-[12px] text-ink outline-none placeholder:text-mute focus:border-cyan" />
                <button className="chip h-8 px-3" disabled={busy || kept === 0} onClick={() => decide("approve")}>
                  {busy ? "FILING…" : `APPROVE ${kept} NOTE${kept === 1 ? "" : "S"}`}</button>
                <button className="chip red h-8 px-3" disabled={busy} onClick={() => decide("reject")}>REJECT ALL</button>
              </div>
            </section>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

function Editor({ value, onChange }: { value: Edit; onChange: (v: Edit) => void }) {
  const [tags, setTags] = useState(value.tags.join(", "));
  const [preview, setPreview] = useState(false);      // narrow screens: write or preview, one at a time
  const field = "border border-cyan/30 bg-void/80 px-2 py-1 text-ink outline-none focus:border-cyan";
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 p-3">
      <input value={value.title} onChange={(e) => onChange({ ...value, title: e.target.value.replace(/\n/g, " ") })}
        aria-label="title" className={`${field} display text-[16px] normal-case tracking-normal`} />
      <input value={tags} aria-label="tags, comma separated" placeholder="tags, comma separated"
        onChange={(e) => { setTags(e.target.value); onChange({ ...value, tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) }); }}
        className={`${field} text-[12px]`} />
      <div className="flex gap-1 lg:hidden">
        <button className={`htab ${preview ? "" : "on"}`} onClick={() => setPreview(false)}>WRITE</button>
        <button className={`htab ${preview ? "on" : ""}`} onClick={() => setPreview(true)}>PREVIEW</button>
      </div>
      <div className="grid min-h-0 flex-1 gap-2 lg:grid-cols-2">
        <textarea value={value.body} onChange={(e) => onChange({ ...value, body: e.target.value })} aria-label="note body (markdown)"
          spellCheck className={`${field} min-h-[240px] resize-none font-mono text-[13px] leading-relaxed ${preview ? "hidden lg:block" : ""}`} />
        <div className={`panel-body border border-cyan/15 ${preview ? "block" : "hidden lg:block"}`}>
          <div className="md reading text-[14px] leading-[1.7]"><Markdown remarkPlugins={[remarkGfm]} components={SAFE_MD}>{value.body}</Markdown></div>
        </div>
      </div>
    </div>
  );
}
