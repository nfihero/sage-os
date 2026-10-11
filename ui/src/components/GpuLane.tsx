import { useEffect, useRef, useState } from "react";
import type { EnginePanel, Gpu, Health, HubEvent } from "../types";
import { ago, clock, shortModel, useNow } from "../util";
import Scramble from "./Scramble";

export default function GpuLane({ gpu, health, events, engine }: { gpu?: Gpu; health?: Health; events: HubEvent[]; engine?: EnginePanel }) {
  const now = useNow(2000);
  const g = gpu?.gpu;
  const used = g ? g.vram_used_mb / 1024 : 0;
  const total = g ? g.vram_total_mb / 1024 : 16;
  const pct = g ? Math.min(100, (g.vram_used_mb / g.vram_total_mb) * 100) : 0;
  const active = gpu?.active ?? [];
  const activeKey = active.map((m) => m.id + m.state).join();

  // Light-cycle sweep across the lane whenever the resident model changes.
  const [sweep, setSweep] = useState(0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    setSweep((s) => s + 1);
  }, [activeKey]);

  const swaps = events.filter((e) => e.type === "gpu.model").slice(0, 4);
  const routerDown = health?.router.state === "down" || (!health?.router.state && health && !health.router.up);
  const sidecar = health?.sidecar.state;
  const own = engine?.serving;                            // Sage OS's own engine (D22.3)

  return (
    <section className="panel min-h-0" data-testid="gpu-lane">
      <div className="panel-head">
        <span className="tab"><Scramble text="GPU lane" /></span>
        <span className="text-[11px] normal-case tracking-normal text-mute">{g?.name ?? "no GPU data"}</span>
      </div>
      <div className="panel-body relative flex flex-col gap-3">
        {sweep > 0 && <div key={sweep} className="cycle" style={{ left: 0, width: "100%", top: 0 }} />}
        <div>
          <div className="mb-1 flex items-baseline justify-between">
            <span className="display text-[11px] text-mute">VRAM</span>
            <span><span className={`font-dot text-[22px] leading-none ${pct > 92 ? "text-amber" : "glow-cyan"}`}>{used.toFixed(1)}</span><span className="text-mute"> / {total.toFixed(0)} GB</span></span>
          </div>
          <div className="vram-bar"><div className={`vram-fill ${pct > 92 ? "hot" : ""}`} style={{ width: `${pct}%` }} /></div>
          <div className="mt-1.5 flex gap-4 text-[11px] text-mute">
            <span>util <span className="text-ink">{g?.util_pct ?? "—"}%</span></span>
            {g?.temp_c != null && <span>temp <span className="text-ink">{g.temp_c}°C</span></span>}
            {g?.power_w != null && <span>power <span className="text-ink">{g.power_w.toFixed(0)} W</span></span>}
          </div>
        </div>

        {gpu?.ram && (
          <div data-testid="ram">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="display text-[11px] text-mute">RAM</span>
              <span><span className={`font-dot text-[22px] leading-none ${gpu.ram.pct > 90 ? "text-amber" : "glow-cyan"}`}>{gpu.ram.used_gb.toFixed(1)}</span><span className="text-mute"> / {gpu.ram.total_gb.toFixed(0)} GB</span></span>
            </div>
            <div className="vram-bar" title={`llama.cpp holds ${gpu.ram.llama_gb.toFixed(1)} GB (CPU-offloaded experts + KV); everything else ${(gpu.ram.used_gb - gpu.ram.llama_gb).toFixed(1)} GB`}>
              <div className="absolute inset-y-0 left-0 bg-cyan/70" style={{ width: `${(gpu.ram.llama_gb / gpu.ram.total_gb) * 100}%`, boxShadow: "0 0 10px rgba(0,229,255,.5)" }} />
              <div className="absolute inset-y-0 bg-ink/25" style={{ left: `${(gpu.ram.llama_gb / gpu.ram.total_gb) * 100}%`, width: `${Math.max(0, (gpu.ram.used_gb - gpu.ram.llama_gb) / gpu.ram.total_gb) * 100}%` }} />
            </div>
            <div className="mt-1 flex gap-4 text-[11px] text-mute">
              <span><span className="inline-block h-2 w-2 bg-cyan/70" /> llama.cpp <span className="text-ink">{gpu.ram.llama_gb.toFixed(1)} GB</span></span>
              <span><span className="inline-block h-2 w-2 bg-ink/25" /> other <span className="text-ink">{(gpu.ram.used_gb - gpu.ram.llama_gb).toFixed(1)} GB</span></span>
            </div>
          </div>
        )}

        <div>
          <div className="display mb-1 text-[11px] text-mute">ON THE CARD</div>
          {own && (
            <div data-testid="gpu-model" className={`card mb-1 cursor-default ${own.ready ? "streaming" : "pulse-cyan"}`}>
              <div className="flex items-center gap-2">
                <span className="glow-cyan">{shortModel(own.id)}</span>
                <span className={`chip ${own.ready ? "" : "amber"}`}>{own.ready ? "loaded" : "loading"}</span>
                <span className="chip mute">Sage OS engine</span>
              </div>
            </div>
          )}
          {routerDown && <div className="text-red">Hermes' model router stopped</div>}
          {!routerDown && !own && active.length === 0 && <div className="text-mute" data-testid="gpu-model">idle · no model loaded</div>}
          {!routerDown && active.map((m) => (
            <div key={m.id} data-testid="gpu-model" className={`card cursor-default ${m.state === "loading" ? "pulse-cyan" : "streaming"}`}>
              <div className="flex items-center gap-2">
                <span className="glow-cyan">{shortModel(m.id)}</span>
                <span className={`chip ${m.state === "loading" ? "amber" : ""}`}>{m.state}</span>
              </div>
              <div className="mt-1 truncate text-[11px] text-mute" title={m.id}>{m.id}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {m.ctx && <span className="chip mute">ctx {Math.round(+m.ctx / 1024)}k</span>}
                {m.n_cpu_moe && <span className="chip mute">{m.n_cpu_moe} MoE layers on CPU</span>}
                {m.offload && <span className="chip amber" title={m.offload}>tensor offload</span>}
                {!m.n_cpu_moe && !m.offload && <span className="chip mute">all on GPU</span>}
              </div>
            </div>
          ))}
        </div>

        {sidecar !== "absent" && (
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="display text-[11px] text-mute">CPU SIDECAR</span>
            {(gpu?.guardian ?? []).map((m) => (
              <span key={m.id} className={`chip ${m.state === "loaded" ? "" : "mute"}`}>{shortModel(m.id)} · {m.state}</span>
            ))}
            {!gpu?.guardian?.length && (sidecar === "down"
              ? <span className="chip red">guardian stopped</span>
              : <span className="chip mute" title="Hermes' guardian sidecar isn't running">guardian off</span>)}
          </div>
        )}

        {(gpu?.models?.length ?? 0) > 0 && <div>
          <div className="display mb-1 text-[11px] text-mute">AVAILABLE</div>
          <div className="flex flex-wrap gap-1">
            {(gpu?.models ?? []).map((m) => (
              <span key={m.id} title={m.id} className={`chip ${active.some((a) => a.id === m.id) ? "" : "mute"}`}>{shortModel(m.id)}</span>
            ))}
          </div>
        </div>}

        {swaps.length > 0 && (
          <div className="text-[11px] text-mute">
            {swaps.map((e, i) => (
              <div key={i}>{clock(e.ts)} → {(e.data.active ?? []).map((m: any) => shortModel(m.id) + " " + m.state).join(", ") || "unloaded"}</div>
            ))}
          </div>
        )}
        <div className="mt-auto text-[11px] text-mute">sampled {gpu ? ago(gpu.ts, now) : "—"} ago</div>
      </div>
    </section>
  );
}
