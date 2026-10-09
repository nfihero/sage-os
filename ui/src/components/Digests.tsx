import { useEffect, useState } from "react";
import { get, post } from "../api";
import type { DigestJob, DigestPreview } from "../types";
import { ago, useNow } from "../util";

/** K12 (D23): long documents turned into notes section by section, with a coverage map. */
const CELL: Record<string, [string, string]> = {
  pending: ["bg-ink/10", "waiting to be read"],
  drafting: ["bg-cyan/50 pulse-cyan", "being read now"],
  drafted: ["bg-cyan/80", "notes drafted"],
  empty: ["bg-ink/25", "no study content (contents page, index…)"],
  failed: ["bg-red/70", "failed: resume to try again"],
};

const CHAPTER: Record<string, string> = {
  open: "being read", waiting: "waiting for room in the inbox", proposed: "sent to inbox", "in inbox": "in your inbox",
  approved: "approved", rejected: "rejected", held: "held: looks like it holds a secret", failed: "couldn't send", empty: "nothing to note",
};

export function DigestStart({ source, path, onStarted }: { source: string; path: string; onStarted?: () => void }) {
  const [pv, setPv] = useState<DigestPreview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [started, setStarted] = useState(false);
  const preview = async () => {
    setErr(null); setBusy(true);
    try { setPv(await get<DigestPreview>(`/api/digest/preview?source=${encodeURIComponent(source)}&path=${encodeURIComponent(path)}`)); }
    catch (e) { setErr(String((e as Error).message)); }
    setBusy(false);
  };
  const start = async () => {
    setErr(null); setBusy(true);
    try { await post("/api/digest", { source, path }); setStarted(true); onStarted?.(); }
    catch (e) { setErr(String((e as Error).message)); }
    setBusy(false);
  };
  if (started) return <div className="text-[11.5px] text-ink/80">Digest started. Follow it in Bookshelf → DIGESTS; each chapter's notes arrive in the inbox.</div>;
  return (
    <div className="text-[11.5px]">
      {!pv ? (
        <button className="chip" disabled={busy} onClick={preview}
          title="Split this document into chapters and sections, then have the local model write notes for every section">
          {busy ? "SPLITTING…" : "DIGEST INTO NOTES"}
        </button>
      ) : (
        <div className="border border-cyan/25 p-2">
          <div className="text-ink/85">{pv.chapters} chapter{pv.chapters === 1 ? "" : "s"}, {pv.sections} sections, {pv.chars.toLocaleString()} characters.
            The local model reads every section and writes notes; about {Math.max(1, Math.round(pv.sections * 0.5))} min on a fast GPU, longer on a laptop.
            Each chapter becomes one inbox card.</div>
          <details className="mt-1"><summary className="cursor-pointer text-mute">outline</summary>
            <ol className="mt-1 max-h-48 overflow-auto pl-4">
              {pv.outline.map((c) => <li key={c.chapter} className="text-ink/80">{c.chapter} <span className="text-mute">· {c.sections.length} section{c.sections.length === 1 ? "" : "s"}</span></li>)}
            </ol>
          </details>
          <div className="mt-1.5 flex gap-1.5">
            <button className="chip" disabled={busy} onClick={start}>START</button>
            <button className="chip mute" onClick={() => setPv(null)}>CANCEL</button>
          </div>
        </div>
      )}
      {err && <div className="mt-1 text-red">{err}</div>}
    </div>
  );
}

export default function Digests({ jobs }: { jobs: DigestJob[] }) {
  const [open, setOpen] = useState<string | null>(jobs[0]?.id ?? null);
  const now = useNow(10000);
  if (!jobs.length) {
    return <div className="m-auto max-w-md p-6 text-center text-[12.5px] text-mute">
      No digests yet. Open a long document in SOURCES (a textbook, a handbook, a long report) and press <b>DIGEST INTO NOTES</b>.
      The local model reads it section by section, and a map here shows that every part was covered.</div>;
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <aside className={`panel-body flex-col gap-1 border-cyan/20 md:flex md:w-[340px] md:flex-none md:border-r ${open ? "hidden" : "flex"}`}>
        {jobs.map((j) => (
          <button key={j.id} onClick={() => setOpen(j.id)} className={`border-l-2 py-1 pl-2 text-left text-[12px] ${open === j.id ? "border-cyan bg-cyan/10" : "border-transparent hover:border-cyan/40"}`}>
            <div className="truncate text-ink">{j.title}</div>
            <div className="text-[11px] text-mute">{j.status} · {(j.counts.drafted ?? 0) + (j.counts.empty ?? 0)}/{j.sections_total} sections · {j.notes} notes · {ago(j.updated, now)}</div>
          </button>
        ))}
      </aside>
      <section className={`min-h-0 min-w-0 flex-1 flex-col ${open ? "flex" : "hidden md:flex"}`}>
        {open ? <JobView id={open} summary={jobs.find((j) => j.id === open)} onBack={() => setOpen(null)} /> : null}
      </section>
    </div>
  );
}

function JobView({ id, summary, onBack }: { id: string; summary?: DigestJob; onBack: () => void }) {
  const [j, setJ] = useState<DigestJob | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => get<DigestJob>(`/api/digest/${id}`).then(setJ).catch((e) => setErr(String(e.message)));
  useEffect(() => { setJ(null); setSel(null); load(); }, [id]);
  useEffect(() => { load(); }, [summary?.updated, summary?.status]);
  const act = async (a: "pause" | "resume" | "cancel") => {
    try { setJ(await post(`/api/digest/${id}/${a}`)); } catch (e) { setErr(String((e as Error).message)); }
  };
  if (!j) return <div className="p-4 text-mute">loading…</div>;
  const done = (j.counts.drafted ?? 0) + (j.counts.empty ?? 0);
  const s = sel !== null ? j.sections?.find((x) => x.idx === sel) : null;
  return (
    <div className="panel-body flex flex-col gap-3 text-[12.5px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="md:hidden"><button className="chip" onClick={onBack}>← digests</button></span>
        <h2 className="display min-w-0 truncate text-[14px] text-ink" title={j.path}>{j.title}</h2>
        <span className="chip mute">{j.status}</span>
        <span className="ml-auto flex gap-1.5">
          {j.status === "running" && <button className="chip" onClick={() => act("pause")}>PAUSE</button>}
          {(j.status === "paused" || (j.status === "done" && (j.counts.failed ?? 0) > 0)) && <button className="chip" onClick={() => act("resume")}>RESUME</button>}
          {j.status !== "done" && j.status !== "cancelled" && <button className="chip mute" onClick={() => act("cancel")}>CANCEL</button>}
        </span>
      </div>
      <div className="text-ink/85">
        {done}/{j.sections_total} sections read · {j.notes} notes · <b>{j.covered}/{j.concepts}</b> listed concepts covered
        {(j.counts.failed ?? 0) > 0 && <span className="text-red"> · {j.counts.failed} failed</span>}
        <span className="text-mute"> · {j.model}</span>
      </div>
      {j.error && <div className="text-amber">{j.error}</div>}
      {err && <div className="text-red">{err}</div>}
      <div>
        <div className="kicker"><span>Coverage map</span><span>one square per section</span></div>
        {(j.chapters ?? []).map((c) => (
          <div key={c.chapter} className="mb-1.5">
            <div className="flex items-baseline gap-2 text-[11.5px]">
              <span className="min-w-0 flex-1 truncate text-ink/85">{c.chapter}</span>
              <span className={`chip shrink-0 ${c.status === "approved" ? "" : c.status === "in inbox" ? "amber" : c.status === "rejected" || c.status === "failed" ? "red" : "mute"}`}
                title={c.error ?? ""}>{CHAPTER[c.status] ?? c.status}</span>
            </div>
            <div className="mt-0.5 flex flex-wrap gap-[3px]">
              {(j.sections ?? []).filter((x) => x.chapter === c.chapter).map((x) => {
                const [cls, why] = CELL[x.status] ?? ["bg-ink/10", x.status];
                const gap = x.concepts > x.covered;
                return <button key={x.idx} onClick={() => setSel(x.idx === sel ? null : x.idx)} aria-label={`${x.title}: ${why}`}
                  title={`${x.title}${x.pages.length ? ` (pages ${x.pages[0]}–${x.pages[1]})` : ""}: ${why}${x.concepts ? `, ${x.covered}/${x.concepts} concepts` : ""}`}
                  className={`h-4 w-4 ${cls} ${gap ? "outline outline-1 outline-amber" : ""} ${sel === x.idx ? "ring-1 ring-ink" : ""}`} />;
              })}
            </div>
          </div>
        ))}
        <div className="mt-1 flex flex-wrap gap-3 text-[10.5px] text-mute">
          {Object.entries(CELL).map(([k, [cls, why]]) => <span key={k} className="flex items-center gap-1"><span className={`inline-block h-2.5 w-2.5 ${cls}`} />{why}</span>)}
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 outline outline-1 outline-amber" />a concept wasn't covered</span>
        </div>
      </div>
      {s && (
        <div className="border border-cyan/20 p-2">
          <div className="text-ink">{s.title}{s.pages.length ? <span className="text-mute"> · pages {s.pages[0]}–{s.pages[1]}</span> : null}</div>
          <div className="text-mute">{s.status} · {s.chars.toLocaleString()} characters{s.ms ? ` · ${(s.ms / 1000).toFixed(0)} s` : ""} · {s.covered}/{s.concepts} concepts covered</div>
          {s.missing.length > 0 && <div className="text-amber">not covered: {s.missing.join(", ")}</div>}
          {s.error && <div className="text-red">{s.error}</div>}
          {s.notes.length > 0 && <ul className="mt-1 list-disc pl-5 text-ink/85">{s.notes.map((t, i) => <li key={i}>{t}</li>)}</ul>}
        </div>
      )}
    </div>
  );
}
