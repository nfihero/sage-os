import { fitWords, goodFor } from "../util";
import { useEffect, useState } from "react";
import { get, post } from "../api";
import type { EngineJob, EngineModel, EnginePanel, EngineState, GameModePanel, ProviderInfo } from "../types";
import GameMode from "./GameMode";

const gb = (b: number) => `${(b / 2 ** 30).toFixed(1)} GB`;
const FIT: Record<string, [string, string]> = {
  fits: ["", "Fits this computer"],
  tight: ["amber", "Runs, but partly on the CPU: slower"],
  "too big": ["red", "Needs more memory than this computer has"],
};

/** Models (D22.3): the local engine, a catalog rated for this machine, and the cloud AIs that are connected. */
export default function Models({ panel, game, onClose }: { panel?: EnginePanel; game?: GameModePanel; onClose: () => void }) {
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

  return (
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[1100px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="models">
        <div className="panel-head">
          <span className="tab">MODELS</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-mute">AI models that run on this computer</span>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
        </div>
        <div className="panel-body flex flex-col gap-4 text-[12.5px]">
          {err && <div className="copy border border-red/50 px-2 py-1 text-red">{err}</div>}
          {!s ? (!err && <div className="text-mute">loading<span className="dots" /></div>) : s.disabled
            ? <p className="copy text-mute">Models on this computer are turned off in this install's settings (config.toml, <code>[engine] enabled</code>).
                You can still use ChatGPT, Gemini or Claude: <b>Connect an AI</b> on the home screen.</p> : (
            <>
              <section>
                <h3 className="display mb-1 text-[12px] text-cyan">This computer</h3>
                <div className="text-ink/85">
                  {hw ? <>{hw.os === "macos" ? "Mac" : hw.os === "windows" ? "Windows" : hw.os} · {hw.ram_gb} GB memory
                    {hw.gpu ? <> · {hw.gpu.name}{hw.gpu.vram_gb >= 1 ? ` (${hw.gpu.vram_gb} GB)` : ""}</> : " · no dedicated GPU"}
                    {" · "}runs models with <b>{hw.backend.toUpperCase()}</b></> : "…"}
                </div>
                <p className="mt-1 text-mute">Small models run on most laptops; big ones need a big GPU. A cloud AI plus a small local model works on modest hardware.</p>
              </section>

              <section>
                <h3 className="display mb-1 text-[12px] text-cyan">Local engine (llama.cpp)</h3>
                {s.binary ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`light ${serving?.ready ? "up" : serving ? "idle" : "idle"}`} />
                    <span className="min-w-0 flex-1 truncate">
                      {serving ? (serving.ready ? <>Serving <b>{serving.id}</b> at <code>{s.base_url}</code></> : <>Loading <b>{serving.id}</b><span className="dots" /></>) : "Installed, not running. Start a model below."}
                    </span>
                    {serving && <button className="chip red" onClick={() => act("/api/engine/stop")}>STOP</button>}
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-ink/85">Not installed. Install downloads the official llama.cpp build for this computer
                      {hw?.backend === "cuda" ? " (NVIDIA: about 550 MB with the CUDA runtime)" : hw?.backend === "metal" ? " (about 12 MB)" : " (about 35 MB)"}.</span>
                    <JobOrButton job={jobs["binary"]} label="INSTALL ENGINE" onStart={() => act("/api/engine/install")} onCancel={() => act("/api/engine/cancel", { key: "binary" })} />
                  </div>
                )}
              </section>

              {s.binary && <GameMode g={game} />}

              {s.local.length > 0 && (
                <section>
                  <h3 className="display mb-1 text-[12px] text-cyan">Already on this computer</h3>
                  <div className="flex flex-col gap-1">
                    {s.local.map((m) => <ModelRow key={m.id} m={m} serving={serving?.id} canRun={!!s.binary}
                      onStart={() => act("/api/engine/start", { model: m.id })} />)}
                  </div>
                </section>
              )}

              <section>
                <h3 className="display mb-1 text-[12px] text-cyan">Catalog</h3>
                <div className="flex flex-col gap-1">
                  {s.catalog.map((m) => <ModelRow key={m.id} m={m} serving={serving?.id} canRun={!!s.binary} job={jobs[`model:${m.id}`]}
                    onStart={() => act("/api/engine/start", { model: m.id })}
                    onDownload={() => act("/api/engine/download", { model: m.id })}
                    onCancel={() => act("/api/engine/cancel", { key: `model:${m.id}` })} />)}
                </div>
                <p className="mt-1 text-mute">Downloads come from Hugging Face, resume if interrupted and are checked against a checksum.</p>
              </section>

              <section>
                <h3 className="display mb-1 text-[12px] text-cyan">Cloud AIs</h3>
                {providers.filter((p) => p.kind === "cloud").length === 0 ? (
                  <p className="text-mute">None connected. ChatGPT and Gemini plug in with an API key (in config.toml, [[models]]); Claude connects through Claude Code.</p>
                ) : providers.filter((p) => p.kind === "cloud").map((p) => (
                  <div key={p.id} className="flex items-center gap-2">
                    <span className={`light ${p.error ? "down" : "up"}`} /><span>{p.label}</span>
                    <span className="text-mute">{p.error ? p.error.slice(0, 80) : `${p.models.length} models`}{p.key_present === false ? " · key missing" : ""}</span>
                  </div>
                ))}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ModelRow({ m, serving, canRun, job, onStart, onDownload, onCancel }: {
  m: EngineModel; serving?: string; canRun: boolean; job?: EngineJob;
  onStart: () => void; onDownload?: () => void; onCancel?: () => void;
}) {
  const [tone, why] = FIT[m.fit] ?? ["", ""];
  const have = m.installed ?? true;
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-cyan/10 py-1">
      <span className="min-w-0 flex-1">
        <span className="text-ink">{m.label}</span>
        {m.note && <span className="text-mute"> · {goodFor(m.note) || m.note}</span>}
        <span className="block truncate font-mono text-[11px] text-mute" title={m.path ?? `${m.repo}/${m.file}`}>{m.path ?? `${m.repo} · ${m.licence ?? ""}`}</span>
      </span>
      <span className="text-mute">{gb(m.size)} · needs ~{m.need_gb} GB</span>
      <span className={`chip ${tone}`} title={why}>{fitWords(m.fit).toUpperCase()}</span>
      {serving === m.id ? <span className="chip">RUNNING</span>
        : have ? <button className="chip" disabled={!canRun || m.fit === "too big"} onClick={onStart}
            title={!canRun ? "Install the engine first" : m.fit === "too big" ? why : "Load this model in the local engine"}>START</button>
        : onDownload && <JobOrButton job={job} label={`DOWNLOAD ${gb(m.size)}`} onStart={onDownload} onCancel={onCancel!} disabled={m.fit === "too big"} />}
    </div>
  );
}

function JobOrButton({ job, label, onStart, onCancel, disabled }: { job?: EngineJob; label: string; onStart: () => void; onCancel: () => void; disabled?: boolean }) {
  if (job?.state === "running" || job?.state === "queued") {
    const pct = job.total ? Math.floor((job.done / job.total) * 100) : 0;
    return (
      <span className="flex items-center gap-2">
        <span className="glow-cyan">{pct}% of {gb(job.total)}</span>
        <button className="chip mute" onClick={onCancel}>CANCEL</button>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2">
      {job?.state === "failed" && <span className="text-red" title={job.error ?? ""}>failed: {(job.error ?? "").slice(0, 60)}</span>}
      {job?.state === "cancelled" && <span className="text-mute">paused (resumes)</span>}
      <button className="chip" disabled={disabled} onClick={onStart}>{job?.state === "failed" || job?.state === "cancelled" ? "RETRY" : label}</button>
    </span>
  );
}
