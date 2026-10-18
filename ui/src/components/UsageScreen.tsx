import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { get, post } from "../api";
import type { UsageWindow } from "../types";
import { UsageBars } from "./Usage";

/** Usage & costs (D40): what each AI used and cost, the limits each one has, and the price list behind the numbers. */
type Span = { tokens_in: number; tokens_out: number; cost: number };
type Price = { in: number; out: number; source?: string; as_of?: string | number; match?: string };
type Row = { agent: string; provider: string | null; model: string | null; billing: "api" | "plan" | "free"; today: Span; week: Span; month: Span;
  estimated: boolean; unpriced: boolean; price: Price | null };
type Summary = { ais: Row[]; spent: { today: number; week: number; month: number }; days: { day: string; tokens: number; spent: number }[];
  limits: Record<string, Record<string, string | number>>; as_of: string; claude_plan: Record<string, UsageWindow> };
type PriceRow = { provider: string; model: string; in: number; out: number; note?: string; changes?: { from: string; in: number; out: number }[];
  yours: { in: number; out: number; updated: number } | null };
type Prices = { as_of: string; sources: Record<string, string>; models: PriceRow[] };

const money = (n: number) => (n > 0 && n < 0.01 ? "<$0.01" : `$${n.toFixed(2)}`);
const tok = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(n));
const PROVIDER: Record<string, string> = { openai: "OpenAI", gemini: "Google", anthropic: "Anthropic" };
function who(r: Row) {
  if (r.agent === "claude") return `Claude Code${r.model ? ` · ${r.model}` : ""}`;
  if (r.agent.startsWith("hermes:")) return `Hermes · ${r.agent.slice(7)}`;
  const where = r.provider === "engine" ? "this computer" : r.provider ?? "";
  return `${r.model ?? "model"}${where ? ` · ${where}` : ""}`;
}

export default function UsageScreen({ onClose, onConnect }: { onClose: () => void; onConnect: () => void }) {
  const [s, setS] = useState<Summary | null>(null);
  const [p, setP] = useState<Prices | null>(null);
  const [span, setSpan] = useState<"today" | "week" | "month">("week");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    get<Summary>("/api/usage").then(setS).catch((e) => setErr(String(e.message)));
    get<Prices>("/api/pricing").then(setP).catch((e) => setErr(String(e.message)));
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  const plan = s?.ais.filter((a) => a.billing === "plan").reduce((n, a) => n + a[span].cost, 0) ?? 0;
  const max = Math.max(1, ...(s?.days ?? []).map((d) => d.tokens));

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[1100px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="usage-screen">
        <div className="panel-head">
          <span className="tab">USAGE & COSTS</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-mute">tokens, spend and limits for every AI you've connected</span>
          <button className="chip mute" onClick={onConnect}>CONNECT AN AI</button>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
        </div>
        {err && <div className="border-b border-red/40 px-3 py-1 text-[12px] text-red">{err}</div>}
        <div className="panel-body flex flex-col gap-6 px-5 py-4">
          {/* spend */}
          <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
            {(["today", "week", "month"] as const).map((k) => (
              <button key={k} onClick={() => setSpan(k)} aria-pressed={span === k}
                className={`border px-3 py-2 text-left ${span === k ? "border-cyan bg-cyan/10" : "border-cyan/20 hover:border-cyan/50"}`}>
                <span className="display block text-[11px] uppercase tracking-[.2em] text-mute">{k === "today" ? "Spent today" : k === "week" ? "Last 7 days" : "Last 30 days"}</span>
                <span className="font-dot glow-cyan text-[30px] leading-none">{s ? money(s.spent[k]) : "…"}</span>
              </button>
            ))}
            <div className="border border-orange/30 px-3 py-2">
              <span className="display block text-[11px] uppercase tracking-[.2em] text-mute">Claude plan, {span === "today" ? "today" : span === "week" ? "7 days" : "30 days"}</span>
              <span className="font-dot glow-orange text-[30px] leading-none">{money(plan)}</span>
              <span className="copy block text-[11px] text-mute">what the same work would cost on the pay-per-use API</span>
            </div>
          </div>

          <p className="copy -mt-3 mb-0 text-[12px] text-mute">Spend counts AI services paid per use (API keys). Models on this computer and
            your Claude plan cost nothing extra.</p>

          {/* daily tokens */}
          {s && s.days.length > 0 && (
            <div>
              <div className="kicker"><span>Tokens per day, last 30 days</span><span>all AIs</span></div>
              <div className="flex h-16 items-end gap-[3px]" role="img" aria-label="tokens per day">
                {s.days.map((d) => (
                  <div key={d.day} className="flex-1 bg-cyan/60" style={{ height: `${Math.max(3, (d.tokens / max) * 100)}%`, maxWidth: 24 }}
                    title={`${d.day}: ${d.tokens.toLocaleString()} tokens${d.spent ? ` · ${money(d.spent)}` : ""}`} />
                ))}
              </div>
            </div>
          )}

          {/* limits */}
          <div>
            <div className="kicker"><span>Limits</span><span>reported by each AI</span></div>
            <div className="flex flex-col gap-2 text-[12.5px]">
              <div className="flex flex-wrap items-center gap-3"><span className="w-[150px] text-ink">Claude plan</span>
                <UsageBars usage={s?.claude_plan} /></div>
              {Object.entries(s?.limits ?? {}).map(([prov, l]) => (
                <div key={prov} className="flex flex-wrap items-center gap-3"><span className="w-[150px] text-ink">{PROVIDER[prov] ?? prov} API</span>
                  <span className="copy text-ink/80">
                    {l.remaining_tokens != null && `${Number(l.remaining_tokens).toLocaleString()} of ${Number(l.limit_tokens).toLocaleString()} tokens/min left`}
                    {l.remaining_requests != null && ` · ${l.remaining_requests} of ${l.limit_requests} requests left`}
                    {l.reset_tokens != null && ` · resets in ${l.reset_tokens}`}
                  </span></div>
              ))}
              <p className="copy m-0 text-[11.5px] text-mute">Claude reports its 5-hour and weekly use with each reply. OpenAI reports per-minute limits with
                each reply, so they appear after you've used it. Gemini doesn't report limits; see your quota at aistudio.google.com. Models on this computer have none.</p>
            </div>
          </div>

          {/* per AI */}
          <div>
            <div className="kicker"><span>By AI · {span === "today" ? "today" : span === "week" ? "last 7 days" : "last 30 days"}</span><span>tokens in / out · cost</span></div>
            {!s ? <p className="text-mute">loading…</p> : s.ais.length === 0 ? <p className="copy text-mute">Nothing yet. Every reply is counted from now on.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] border-collapse text-[12.5px]">
                  <tbody>
                    {s.ais.map((a) => {
                      const v = a[span];
                      return (
                        <tr key={`${a.agent}|${a.provider}|${a.model}`} className="border-b border-cyan/10">
                          <td className="copy py-1.5 pr-3 text-ink">{who(a)}</td>
                          <td className="py-1.5 pr-3 text-[10.5px] uppercase tracking-[.1em] text-mute">{a.billing === "api" ? "API key" : a.billing === "plan" ? "Claude plan" : "free"}</td>
                          <td className="py-1.5 pr-3 text-right tabular-nums text-ink/85">{tok(v.tokens_in)} / {tok(v.tokens_out)}{a.estimated && <span className="text-mute" title="some replies didn't report tokens; estimated from the text"> ≈</span>}</td>
                          <td className={`py-1.5 pr-3 text-right tabular-nums ${a.billing === "plan" ? "text-orange" : "text-ink"}`}>
                            {a.billing === "free" ? "$0" : a.unpriced && !v.cost ? <span className="text-amber" title="no price known for this model; add one below">no price</span>
                              : `${money(v.cost)}${a.billing === "plan" ? " value" : ""}`}</td>
                          <td className="py-1.5 text-right text-[11px] text-mute">{a.price ? `$${a.price.in} / $${a.price.out} per 1M${a.price.source === "yours" ? " (yours)" : ""}` : ""}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {p && <PriceList p={p} onChange={setP} />}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function PriceList({ p, onChange }: { p: Prices; onChange: (p: Prices) => void }) {
  const [edit, setEdit] = useState<{ provider: string; model: string; in: string; out: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const save = async () => {
    if (!edit) return;
    setErr(null);
    try {
      onChange(await post<Prices>("/api/pricing", { provider: edit.provider, model: edit.model.trim(), in_price: Number(edit.in), out_price: Number(edit.out) }));
      setEdit(null);
    } catch (e) { setErr(String((e as Error).message)); }
  };
  const reset = async (r: PriceRow) => onChange(await post<Prices>("/api/pricing/reset", { provider: r.provider, model: r.model }));
  const rows = p.models.filter((r) => !filter || `${r.provider} ${r.model}`.toLowerCase().includes(filter.toLowerCase()));
  const field = "w-[70px] border border-cyan/35 bg-void/80 px-1 py-0.5 text-right font-mono text-[12px] text-ink outline-none focus:border-cyan";
  return (
    <div>
      <div className="kicker"><span>Price list · dollars per million tokens (in / out)</span><span>as of {p.as_of}</span></div>
      <p className="copy mt-0 text-[11.5px] text-mute">From each provider's own price page ({Object.entries(p.sources).map(([k, u], i) => (
        <span key={k}>{i > 0 && ", "}<a className="underline" href={u} target="_blank" rel="noreferrer noopener">{PROVIDER[k] ?? k}</a></span>))}).
        Prices change; if one is out of date, correct it here and it's used for new replies (and follows you to your other devices).</p>
      <div className="mb-2 flex flex-wrap gap-2">
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="filter models" aria-label="filter models"
          className="border border-cyan/35 bg-void/80 px-2 py-1 text-[12px] text-ink outline-none focus:border-cyan" />
        <button className="chip mute" onClick={() => setEdit({ provider: "openai", model: "", in: "", out: "" })}>+ ADD A PRICE</button>
      </div>
      {edit && (
        <div className="mb-2 flex flex-wrap items-center gap-2 border border-dashed border-cyan/30 px-2 py-1.5 text-[12px]">
          <select value={edit.provider} onChange={(e) => setEdit({ ...edit, provider: e.target.value })} aria-label="provider"
            className="border border-cyan/35 bg-void px-1 py-0.5 text-ink">
            {["openai", "gemini", "anthropic"].map((k) => <option key={k} value={k}>{PROVIDER[k]}</option>)}
          </select>
          <input value={edit.model} onChange={(e) => setEdit({ ...edit, model: e.target.value })} placeholder="model id" aria-label="model id"
            className="min-w-[160px] flex-1 border border-cyan/35 bg-void/80 px-1 py-0.5 font-mono text-[12px] text-ink outline-none focus:border-cyan" />
          $<input value={edit.in} onChange={(e) => setEdit({ ...edit, in: e.target.value })} inputMode="decimal" aria-label="input price" className={field} />
          / $<input value={edit.out} onChange={(e) => setEdit({ ...edit, out: e.target.value })} inputMode="decimal" aria-label="output price" className={field} />
          <button className="chip" disabled={!edit.model.trim() || edit.in === "" || edit.out === ""} onClick={save}>SAVE</button>
          <button className="chip mute" onClick={() => { setEdit(null); setErr(null); }}>CANCEL</button>
          {err && <span className="w-full text-red">{err}</span>}
        </div>
      )}
      <div className="max-h-[320px] overflow-auto">
        <table className="w-full border-collapse text-[12.5px]">
          <tbody>
            {rows.map((r) => {
              const v = r.yours ?? r;
              const next = r.changes?.find((c) => c.from > new Date().toISOString().slice(0, 10));
              return (
                <tr key={`${r.provider}|${r.model}`} className="border-b border-cyan/10">
                  <td className="py-1 pr-3 text-[10.5px] uppercase tracking-[.1em] text-mute">{PROVIDER[r.provider] ?? r.provider}</td>
                  <td className="py-1 pr-3 font-mono text-ink">{r.model}{r.note && <span className="copy ml-2 text-[11px] text-mute">{r.note}</span>}</td>
                  <td className="py-1 pr-3 text-right tabular-nums text-ink">${v.in} / ${v.out}
                    {next && <span className="block text-[10.5px] text-amber">${next.in} / ${next.out} from {next.from}</span>}</td>
                  <td className="py-1 text-right">
                    {r.yours ? <><span className="mr-1 text-[10.5px] text-cyan">YOURS</span><button className="chip mute" onClick={() => reset(r)}>RESET</button></>
                      : <button className="chip mute" onClick={() => setEdit({ provider: r.provider, model: r.model, in: String(r.in), out: String(r.out) })}>EDIT</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
