import { fitWords, goodFor } from "../util";
import { useEffect, useState } from "react";
import { get, post } from "../api";
import type { EngineJob, EngineModel, EnginePanel, EngineState, GameModePanel, ProviderInfo } from "../types";
import GameMode from "./GameMode";
import { Num } from "./Readout";

const gb = (b: number) => `${(b / 1e9).toFixed(1)} GB`;
const SOLID = { background: "var(--color-cyan)", color: "var(--color-void)" };   // .chip (unlayered) wins over bg-/text- utilities
const FIT_TONE: Record<string, string> = { fits: "text-cyan", tight: "text-amber", "too big": "text-mute" };
const FIT_WHY: Record<string, string> = {
  fits: "Fits in this computer's memory: answers come quickly.",
  tight: "Only partly fits, so it runs slowly.",
  "too big": "Needs more memory than this computer has.",
};

/** Models (D22.3, refined in D49): pick a model that runs on this computer. What's running now first, two
 *  recommendations, then every model as a card that says what it's good for, how it runs here, and one action.
 *  Details (source, licence, memory) sit in each card's tooltip; game mode folds away at the bottom. */
export default function Models({ panel, game, onClose, onConnect }: {
  panel?: EnginePanel; game?: GameModePanel; onClose: () => void; onConnect?: () => void;
}) {
  const [state, setState] = useState<EngineState | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = () => get<EngineState>("/api/engine").then(setState).catch((e) => setErr(String(e.message)));

  useEffect(() => {
    load();
    get<{ providers: ProviderInfo[] }>("/api/models").then((r) => setProviders(r.providers)).catch(() => {});
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  useEffect(() => { if (panel) load(); }, [panel]);      // live: downloads, start/stop

  const act = async (path: string, body: unknown = {}) => {
    setErr(null);
    try { await post(path, body); await load(); } catch (e) { setErr(String((e as Error).message)); }
  };
  const s: EngineState | null = state ? { ...state, ...(panel ?? {}) } : null;   // catalog/local come only from /api/engine
  const hw = s?.hardware;
  const jobs = s?.jobs ?? {};
  const serving = s?.serving;

  // the two recommendations: the quick starter, and the biggest model that runs well here in a reasonable download
  const catalog = s?.catalog ?? [];
  const starter = catalog.find((m) => m.starter && m.fit !== "too big");
  const best = [...catalog].filter((m) => m.fit === "fits" && !(m as { micro?: boolean }).micro && m.size <= 8e9)
    .sort((a, b) => b.size - a.size)[0];
  const picks = [starter && { m: starter, tag: "Quick start", why: "Ready in a few minutes; good for everyday questions." },
    best && best.id !== starter?.id && { m: best, tag: "Best answers here", why: "The strongest model that runs well on this computer." }]
    .filter(Boolean) as { m: EngineModel; tag: string; why: string }[];
  const pickIds = new Set(picks.map((p) => p.m.id));
  const micro = (m: EngineModel) => !!(m as { micro?: boolean }).micro      // game mode's helper, offered there, not here
  const rest = catalog.filter((m) => !pickIds.has(m.id) && m.fit !== "too big" && !micro(m))
    .sort((a, b) => Number(!!b.installed) - Number(!!a.installed) || (a.fit === b.fit ? a.size - b.size : a.fit === "fits" ? -1 : 1));
  const tooBig = catalog.filter((m) => !pickIds.has(m.id) && m.fit === "too big" && !micro(m));
  const cloud = providers.filter((p) => p.kind === "cloud");
  const card = (m: EngineModel, extra?: { tag: string; why: string }) => (
    <ModelCard key={m.id} m={m} pick={extra} serving={serving?.id} ready={!!serving?.ready} canRun={!!s?.binary} job={jobs[`model:${m.id}`]}
      onStart={() => act("/api/engine/start", { model: m.id })} onStop={() => act("/api/engine/stop")}
      onDownload={() => act("/api/engine/download", { model: m.id })} onCancel={() => act("/api/engine/cancel", { key: `model:${m.id}` })} />
  );

  return (
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[1100px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="models">
        <div className="panel-head">
          <span className="tab">MODELS</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-mute">AI models that run on this computer: free, private, offline</span>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
        </div>
        <div className="panel-body flex flex-col gap-6 px-5 py-4">
          {err && <div className="copy border border-red/50 px-2 py-1 text-red">{err}</div>}
          {!s ? (!err && <div className="text-mute">loading<span className="dots" /></div>) : s.disabled
            ? <p className="copy text-mute">Models on this computer are turned off in this install's settings (config.toml, <code>[engine] enabled</code>).
                You can still use ChatGPT, Gemini or Claude: <b>Connect an AI</b> on the home screen.</p> : (
            <>
              {/* now */}
              <section className="flex flex-wrap items-center gap-x-5 gap-y-2 border border-cyan/25 bg-cyan/[.03] px-4 py-3" aria-live="polite">
                <span className={`light ${serving?.ready ? "up" : "idle"}`} aria-hidden />
                <div className="min-w-0 flex-1">
                  {!s.binary ? <>
                    <div className="copy text-[14px] text-ink">The program that runs models isn't installed yet.</div>
                    <div className="copy text-[12px] text-mute">It comes by itself with your first model, or install it now
                      ({hw?.backend === "cuda" ? "about 550 MB for NVIDIA cards" : hw?.backend === "metal" ? "about 12 MB" : "about 35 MB"}).</div>
                  </> : serving ? <>
                    <div className="copy text-[14px] text-ink">{serving.ready ? "Running" : "Loading"} <b className="text-cyan">{label(catalog, serving.id)}</b>{!serving.ready && <span className="dots" />}</div>
                    <div className="copy text-[12px] text-mute">{serving.ready ? "Pick it in the AI picker above a chat." : "It answers as soon as it's loaded into memory."}</div>
                  </> : <>
                    <div className="copy text-[14px] text-ink">No model is running.</div>
                    <div className="copy text-[12px] text-mute">Start one below; downloaded models start in under a minute.</div>
                  </>}
                </div>
                {!s.binary && <JobOrButton job={jobs["binary"]} label="INSTALL" onStart={() => act("/api/engine/install")} onCancel={() => act("/api/engine/cancel", { key: "binary" })} />}
                {serving && <button className="chip mute h-8 px-3" onClick={() => act("/api/engine/stop")}>STOP</button>}
                {hw && <div className="copy w-full text-[11.5px] text-mute">
                  This computer: {hw.os === "macos" ? "Mac" : hw.os === "windows" ? "Windows" : hw.os} · {Math.round(hw.ram_gb)} GB memory
                  {hw.gpu ? ` · ${hw.gpu.name.replace(/^NVIDIA GeForce |^AMD Radeon\(TM\) /, "")}${hw.gpu.vram_gb >= 1 && hw.gpu.vendor !== "apple" ? `, ${hw.gpu.vram_gb} GB` : ""}` : " · no graphics card: models run on the processor"}
                </div>}
              </section>

              {picks.length > 0 && (
                <section>
                  <h3 className="display m-0 mb-2 text-[14px] text-ink">Recommended for this computer</h3>
                  <div className="grid gap-3 md:grid-cols-2">{picks.map((p) => card(p.m, p))}</div>
                </section>
              )}

              {rest.length > 0 && (
                <section>
                  <h3 className="display m-0 mb-2 text-[14px] text-ink">More models</h3>
                  <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr))]">{rest.map((m) => card(m))}</div>
                  {tooBig.length > 0 && (
                    <details className="group mt-2">
                      <summary className="cursor-pointer list-none text-[12px] text-mute hover:text-ink">
                        <span className="inline-block transition-transform group-open:rotate-90">▸</span> Too big for this computer ({tooBig.length})</summary>
                      <div className="mt-2 grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr))]">{tooBig.map((m) => card(m))}</div>
                    </details>
                  )}
                  <p className="copy mb-0 mt-2 text-[11.5px] text-mute">Models download from Hugging Face, pick up where they left off if interrupted, and
                    are checked before they're used.</p>
                </section>
              )}

              {s.local.length > 0 && (
                <section>
                  <h3 className="display m-0 mb-2 text-[14px] text-ink">Model files already on this computer</h3>
                  <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr))]">{s.local.map((m) => card({ ...m, installed: true }))}</div>
                </section>
              )}

              <section className="flex flex-wrap items-center gap-3 border-t border-dashed border-cyan/15 pt-4">
                <span className="copy min-w-0 flex-1 text-[13px] text-ink/80">
                  {cloud.length ? <>Also connected: {cloud.map((p) => p.label).join(", ")}.</> : "Want answers from ChatGPT, Gemini or Claude instead? They don't need a download."}
                </span>
                {onConnect && <button className="chip h-8 px-3" onClick={() => { onClose(); onConnect(); }}>CONNECT AN AI</button>}
              </section>

              {s.binary && game && (
                <details className="group border-t border-dashed border-cyan/15 pt-3">
                  <summary className="cursor-pointer list-none">
                    <span className="display text-[14px] text-ink"><span className="inline-block text-mute transition-transform group-open:rotate-90">▸</span> Game mode</span>
                    <span className="copy ml-2 text-[12px] text-mute">{game.state === "aside" || game.state === "micro" ? "stepped aside for a game"
                      : game.mode === "never" ? "off" : `on: steps aside ${game.mode === "ask" ? "after asking" : "by itself"} when a game needs the graphics card`}</span>
                  </summary>
                  <div className="mt-3"><GameMode g={game} /></div>
                </details>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function label(catalog: EngineModel[], id: string) {
  return catalog.find((m) => m.id === id)?.label ?? id;
}

function ModelCard({ m, pick, serving, ready, canRun, job, onStart, onStop, onDownload, onCancel }: {
  m: EngineModel; pick?: { tag: string; why: string }; serving?: string; ready: boolean; canRun: boolean; job?: EngineJob;
  onStart: () => void; onStop: () => void; onDownload: () => void; onCancel: () => void;
}) {
  const have = m.installed ?? false;
  const running = serving === m.id;
  const big = m.fit === "too big";
  const details = [m.repo ? `From ${m.repo}` : m.path, m.licence ? `licence: ${m.licence}` : null, `needs about ${m.need_gb} GB of memory`].filter(Boolean).join(" · ");
  return (
    <div className={`flex flex-col gap-2 border p-3 ${pick ? "border-cyan/50 bg-cyan/[.04] p-4" : "border-cyan/20"} ${running ? "!border-cyan shadow-[0_0_22px_rgba(61,255,139,.12)]" : ""}`}
      data-testid="model-card">
      <div className="flex items-baseline gap-2">
        <span className={`display min-w-0 flex-1 truncate ${pick ? "text-[19px]" : "text-[15px]"} text-ink`} title={details}>{m.label}</span>
        {pick && <span className="display bg-cyan px-1.5 text-[10.5px] tracking-[.14em] text-void">{pick.tag.toUpperCase()}</span>}
      </div>
      <p className="copy m-0 text-[13px] leading-snug text-ink/75">{pick ? pick.why : goodFor(m.note) || m.note || "A model that runs on this computer."}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px]">
        <span className="text-mute"><Num className="text-[15px]">{(m.size / 1e9).toFixed(1)}</Num> GB</span>
        <span className={FIT_TONE[m.fit] ?? "text-mute"} title={FIT_WHY[m.fit]}>● {fitWords(m.fit)}</span>
        {have && !running && <span className="text-mute">downloaded</span>}
      </div>
      <div className="mt-auto flex items-center gap-2 pt-1">
        {running ? <>
          <span className="copy text-[12.5px] text-cyan">{ready ? "Running now" : <>Loading<span className="dots" /></>}</span>
          <button className="chip mute ml-auto" onClick={onStop}>STOP</button>
        </> : have ? (
          <button className="chip h-8 px-4" style={pick ? SOLID : undefined} disabled={!canRun || big} onClick={onStart}
            title={!canRun ? "The program that runs models installs with your first download" : big ? FIT_WHY["too big"] : "Load it and start answering"}>START</button>
        ) : <JobOrButton job={job} label={`DOWNLOAD · ${gb(m.size)}`} onStart={onDownload} onCancel={onCancel} disabled={big} primary={!!pick} />}
      </div>
    </div>
  );
}

function JobOrButton({ job, label, onStart, onCancel, disabled, primary }: {
  job?: EngineJob; label: string; onStart: () => void; onCancel: () => void; disabled?: boolean; primary?: boolean;
}) {
  if (job?.state === "running" || job?.state === "queued") {
    const pct = job.total ? Math.floor((job.done / job.total) * 100) : 0;
    const left = job.started && job.done ? (job.total - job.done) / Math.max(1, job.done / Math.max(1, Date.now() / 1000 - job.started)) : null;
    return (
      <div className="flex w-full flex-col gap-1">
        <div className="flex items-baseline gap-2 text-[11.5px] text-mute">
          <span><Num className="text-[15px]">{pct}</Num>%</span>
          <span>{left == null ? "starting…" : left > 90 ? `about ${Math.round(left / 60)} min left` : "less than two minutes left"}</span>
          <button className="chip mute ml-auto" onClick={onCancel}>PAUSE</button>
        </div>
        <div className="vram-bar"><div className="vram-fill" style={{ width: `${pct}%` }} /></div>
      </div>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-2">
      <button className="chip h-8 px-4 font-semibold" style={primary ? SOLID : undefined} disabled={disabled} onClick={onStart}>{job?.state === "failed" || job?.state === "cancelled" ? "CONTINUE DOWNLOAD" : label}</button>
      {job?.state === "failed" && <span className="copy text-[12px] text-red" title={job.error ?? ""}>stopped: {(job.error ?? "").slice(0, 70)}</span>}
      {job?.state === "cancelled" && <span className="copy text-[12px] text-mute">paused; it picks up where it left off</span>}
    </span>
  );
}
