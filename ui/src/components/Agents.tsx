import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { get, post } from "../api";
import type { ActivityEntry, AgentTrust, Batch, LibrarianState, ReviewerSettings, TrustLevel } from "../types";
import { useNow } from "../util";
import { Ago, Num, Row } from "./Readout";

/** K7 (D36): each agent's trust level and role, the Reviewer and Librarian, and everything every agent did.
 *  The log is complete at every level: trusting an agent changes what waits for you, never what you can see. */
type TrustData = {
  agents: AgentTrust[]; levels: TrustLevel[]; roles: string[]; auto: Batch[]; reviewer: ReviewerSettings;
  librarian: LibrarianState; providers: { id: string; label: string }[]; folders: string[];
};

const LEVEL: Record<TrustLevel, [string, string]> = {
  ask: ["Ask first", "Everything it proposes waits in the inbox for you."],
  new_notes: ["New notes file themselves", "New notes are filed at once and listed under Filed for you; changes to your existing notes still wait."],
  trusted: ["Trusted", "Everything it proposes is filed at once. Each batch can be undone in History."],
};
const ROLE: Record<string, string> = {
  researcher: "Researcher: drafts new notes from your sources and chats",
  librarian: "Librarian: tidies notes (tags, links, titles)",
  reviewer: "Reviewer: reads proposals first and marks what it would drop",
};
const ACTION: Record<string, string> = {
  searched: "searched", read: "read", searched_sources: "searched docs", read_source: "read doc", proposed: "proposed",
  filed: "filed · by you", "filed.auto": "filed itself", rejected: "rejected", held: "held", refused: "refused", undone: "undone",
  "trust.changed": "trust", "trust.not_now": "trust", "role.changed": "role", reviewed: "reviewed", "review.failed": "review failed",
  "librarian.started": "started", "librarian.finished": "finished", "librarian.failed": "failed", decided: "you decided",
};
const LOUD = new Set(["filed.auto", "held", "refused", "undone", "trust.changed", "review.failed", "librarian.failed"]);
const field = "border border-cyan/30 bg-void/80 px-2 py-1 text-[12px] text-ink outline-none focus:border-cyan";

export default function Agents({ panel, librarian, onClose }: { panel?: unknown; librarian?: unknown; onClose: () => void }) {
  const [data, setData] = useState<TrustData | null>(null);
  const [sel, setSel] = useState<string | null>(null);     // null = everyone
  const [err, setErr] = useState<string | null>(null);
  const load = () => get<TrustData>("/api/trust").then(setData).catch((e) => setErr(String(e.message)));
  useEffect(() => { load(); }, [panel, librarian]);      // panels change only when their own data does
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const agent = data?.agents.find((a) => a.key === sel) ?? null;
  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[1100px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="agents">
        <div className="panel-head">
          <span className="tab">AGENTS</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-mute">trust, roles and everything each agent did</span>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close agents">✕</button>
        </div>
        {err && <div className="border-b border-red/40 px-3 py-1 text-[12px] text-red">{err}</div>}
        {!data ? <div className="p-4 text-mute">loading…</div> : (
          <div className="flex min-h-0 flex-1 flex-col md:flex-row">
            <nav className={`panel-body flex-col gap-0.5 border-cyan/20 md:flex md:w-[280px] md:flex-none md:border-r ${sel === null ? "flex" : "hidden"} max-md:flex-none max-md:max-h-[40%]`}>
              <button onClick={() => setSel(null)} className={`border-l-2 py-1 pl-2 text-left text-[12.5px] ${sel === null ? "border-cyan bg-cyan/10" : "border-transparent hover:border-cyan/40"}`}>
                <div className="text-ink">Everyone</div><div className="text-[11px] text-mute">the whole activity log, newest first</div>
              </button>
              {data.agents.map((a) => (
                <button key={a.key} onClick={() => setSel(a.key)}
                  className={`border-l-2 py-1 pl-2 text-left text-[12.5px] ${sel === a.key ? "border-cyan bg-cyan/10" : "border-transparent hover:border-cyan/40"}`}>
                  <div className="flex items-baseline gap-1.5">
                    <span className="min-w-0 flex-1 truncate text-ink">{a.label}</span>
                    {a.key !== "reviewer" && <span className={`chip ${a.level === "ask" ? "mute" : "amber"}`}>{LEVEL[a.level][0].split(" ")[0]}</span>}
                    {a.suggest && <span className="text-amber" title="It has earned the next level">●</span>}
                  </div>
                  <div className="text-[11px] text-mute">{a.role} · {a.record.approved} filed · {a.record.rejected} rejected</div>
                </button>
              ))}
            </nav>
            <section className={`panel-body min-h-0 min-w-0 flex-1 ${sel === null ? "hidden md:block" : ""}`}>
              {sel !== null && <div className="mb-2 md:hidden"><button className="chip mute" onClick={() => setSel(null)}>← ALL AGENTS</button></div>}
              {agent && <AgentDetail a={agent} data={data} onChanged={load} onErr={setErr} />}
              <Activity agentKey={sel} refresh={panel} />
            </section>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

function AgentDetail({ a, data, onChanged, onErr }: { a: AgentTrust; data: TrustData; onChanged: () => void; onErr: (e: string | null) => void }) {
  const set = async (body: Record<string, string>) => {
    onErr(null);
    try { await post(`/api/trust/${encodeURIComponent(a.key)}`, body); onChanged(); } catch (e) { onErr(String((e as Error).message)); }
  };
  return (
    <div className="mb-4 max-w-[720px]">
      <h2 className="display mb-2 text-[18px] normal-case tracking-normal text-ink">{a.label}</h2>
      <Row k="Proposals decided" v={<Num className="text-[15px]">{a.record.decided}</Num>} />
      <Row k="Filed / rejected" v={`${a.record.approved} / ${a.record.rejected}`} />
      <Row k="Clean approvals in a row" v={<Num className="text-[15px]">{a.record.streak}</Num>} title="Approved by you without dropping or editing a note, and not undone" />
      {a.record.auto_undone > 0 && <Row k="Filed itself, then undone" v={String(a.record.auto_undone)} />}
      <label className="mt-3 block text-[11px] uppercase tracking-[.16em] text-mute">Role</label>
      <select value={a.role} onChange={(e) => set({ role: e.target.value })} className={`${field} mt-1 w-full`} aria-label="role">
        {data.roles.map((r) => <option key={r} value={r}>{ROLE[r] ?? r}</option>)}
      </select>
      {a.key !== "reviewer" && (
        <>
          <div className="mt-3 text-[11px] uppercase tracking-[.16em] text-mute">Trust</div>
          {a.suggest && <p className="mt-1 text-[12px] text-amber">It has earned “{LEVEL[a.suggest][0]}”: {a.record.streak} clean approvals in a row.</p>}
          <div className="mt-1 flex flex-col gap-1" role="radiogroup" aria-label="trust level">
            {data.levels.map((l) => (
              <button key={l} role="radio" aria-checked={a.level === l} onClick={() => a.level !== l && set({ level: l })}
                className={`border px-2 py-1.5 text-left ${a.level === l ? "border-cyan bg-cyan/10" : "border-cyan/20 hover:border-cyan/50"}`}>
                <div className="text-[12.5px] text-ink">{a.level === l ? "◉" : "○"} {LEVEL[l][0]}</div>
                <div className="copy text-[11.5px] text-ink/70">{LEVEL[l][1]}</div>
              </button>
            ))}
          </div>
          <p className="mt-1 text-[11px] text-mute">At every level, secret-looking proposals are held for you and everything it does is in the log below.</p>
        </>
      )}
      {a.key === "reviewer" && <ReviewerForm data={data} onChanged={onChanged} onErr={onErr} />}
      {a.key === "librarian" && <LibrarianForm data={data} onErr={onErr} />}
    </div>
  );
}

function ReviewerForm({ data, onChanged, onErr }: { data: TrustData; onChanged: () => void; onErr: (e: string | null) => void }) {
  const [s, setS] = useState<ReviewerSettings>(data.reviewer);
  const [saved, setSaved] = useState(false);
  const save = async () => {
    onErr(null); setSaved(false);
    try { await post("/api/reviewer/settings", s); setSaved(true); onChanged(); } catch (e) { onErr(String((e as Error).message)); }
  };
  return (
    <div className="mt-3 flex flex-col gap-1.5 text-[12px]">
      <div className="text-[11px] uppercase tracking-[.16em] text-mute">Who reviews</div>
      <select value={s.provider} onChange={(e) => setS({ ...s, provider: e.target.value })} className={field} aria-label="reviewer model provider">
        {data.providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
      </select>
      <input value={s.model ?? ""} onChange={(e) => setS({ ...s, model: e.target.value || null })} className={field}
        placeholder={s.provider === "engine" ? "model (blank: whatever the engine is serving)" : s.provider === "claude" ? "model (blank: Claude Code's default)" : "model id"}
        aria-label="reviewer model" />
      <label className="flex items-center gap-1.5 text-ink/85">
        <input type="checkbox" checked={s.auto} onChange={(e) => setS({ ...s, auto: e.target.checked })} className="accent-[var(--color-cyan)]" />
        Review every new proposal automatically (otherwise ASK REVIEWER on a card)
      </label>
      <div className="flex items-center gap-2"><button className="chip h-7 px-3" onClick={save}>SAVE</button>{saved && <span className="text-cyan">saved</span>}</div>
      <p className="copy text-[11.5px] text-ink/70">The Reviewer only marks notes it would drop, with a reason. They start dropped when you open REVIEW, and you still keep or drop each one.</p>
    </div>
  );
}

function LibrarianForm({ data, onErr }: { data: TrustData; onErr: (e: string | null) => void }) {
  const [folder, setFolder] = useState<string>("");
  const [count, setCount] = useState(20);
  const [provider, setProvider] = useState(data.providers[0]?.id ?? "engine");
  const [model, setModel] = useState("");
  const st = data.librarian;
  const run = async () => {
    onErr(null);
    try { await post("/api/librarian/run", { folder: folder || null, count, provider, model: model || null }); } catch (e) { onErr(String((e as Error).message)); }
  };
  return (
    <div className="mt-3 flex flex-col gap-1.5 text-[12px]">
      <div className="text-[11px] uppercase tracking-[.16em] text-mute">Tidy a folder</div>
      <div className="flex flex-wrap gap-1.5">
        <select value={folder} onChange={(e) => setFolder(e.target.value)} className={`${field} min-w-[160px] flex-1`} aria-label="folder">
          <option value="">the whole library</option>
          {data.folders.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
        <input type="number" min={1} max={50} value={count} onChange={(e) => setCount(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
          className={`${field} w-20`} aria-label="how many notes" />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <select value={provider} onChange={(e) => setProvider(e.target.value)} className={`${field} flex-1`} aria-label="librarian model provider">
          {data.providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
        <input value={model} onChange={(e) => setModel(e.target.value)} className={`${field} flex-1`} aria-label="librarian model"
          placeholder={provider === "engine" ? "blank: the served model" : "model id"} />
      </div>
      <div className="flex items-center gap-2">
        <button className="chip h-7 px-3" disabled={st.status === "running"} onClick={run}>{st.status === "running" ? "WORKING…" : "RUN THE LIBRARIAN"}</button>
        <span className="min-w-0 flex-1 truncate text-ink/80">
          {st.status === "running" ? `${st.done ?? 0} of ${st.total || "?"} notes read` : st.status === "failed" ? <span className="text-amber">{st.error}</span> : st.result ?? ""}
        </span>
      </div>
      <p className="copy text-[11.5px] text-ink/70">It suggests tags, links to related notes and clearer titles, then sends them as one card: approve the whole run in one decision, or review it note by note.</p>
    </div>
  );
}

function Activity({ agentKey, refresh }: { agentKey: string | null; refresh?: unknown }) {
  const now = useNow(10000);
  const [rows, setRows] = useState<ActivityEntry[] | null>(null);
  const [more, setMore] = useState(true);
  const [only, setOnly] = useState<"all" | "writes">("all");
  const q = (before?: number) => get<ActivityEntry[]>(`/api/trust/activity?limit=200${agentKey ? `&key=${encodeURIComponent(agentKey)}` : ""}${before ? `&before=${before}` : ""}`);
  useEffect(() => { q().then((r) => { setRows(r); setMore(r.length === 200); }).catch(() => setRows([])); }, [agentKey, refresh]);
  const older = async () => {
    if (!rows?.length) return;
    const r = await q(rows[rows.length - 1].ts);
    setRows([...rows, ...r]); setMore(r.length === 200);
  };
  const shown = (rows ?? []).filter((e) => only === "all" || !["searched", "read", "searched_sources", "read_source"].includes(e.action));
  return (
    <div className="max-w-[860px]">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="text-[11px] uppercase tracking-[.16em] text-mute">Activity</span>
        <span className="ml-auto flex gap-1">
          <button className={`htab ${only === "all" ? "on" : ""}`} onClick={() => setOnly("all")}>ALL</button>
          <button className={`htab ${only === "writes" ? "on" : ""}`} onClick={() => setOnly("writes")}>CHANGES ONLY</button>
        </span>
      </div>
      {rows === null ? <div className="text-mute">loading…</div> : shown.length === 0 ? <div className="text-[12px] text-mute">Nothing recorded yet.</div> : (
        <ol className="text-[12px]">
          {shown.map((e) => (
            <li key={e.id} className="flex items-baseline gap-2 border-b border-dashed border-cyan/10 py-[3px]">
              <Ago ts={e.ts} now={now} className="w-9 flex-none text-right" />
              <span className={`w-[92px] flex-none truncate text-[11px] uppercase tracking-[.12em] ${LOUD.has(e.action) ? "text-amber" : "text-mute"}`}>{ACTION[e.action] ?? e.action}</span>
              {!agentKey && <span className="w-[96px] flex-none truncate text-cyan/80" title={e.agent}>{e.key}</span>}
              <span className="copy min-w-0 flex-1 text-ink/85" title={`${new Date(e.ts * 1000).toLocaleString()} · ${e.agent}`}>{e.detail}</span>
            </li>
          ))}
        </ol>
      )}
      {more && rows && rows.length > 0 && <button className="mt-2 text-[11.5px] text-cyan hover:underline" onClick={older}>older…</button>}
    </div>
  );
}
