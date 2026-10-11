import { useState } from "react";
import { post } from "../api";
import type { GameModePanel } from "../types";

const MODES: [GameModePanel["mode"], string, string][] = [
  ["always", "ALWAYS", "Step aside on its own when a game or heavy program needs the graphics card"],
  ["ask", "ASK", "Ask in the inbox first"],
  ["never", "NEVER", "Keep the local model running whatever else runs"],
];

/** G1 (D29): Sage OS steps aside when another program needs the graphics card. Lives in MODELS. */
export default function GameMode({ g, onChange }: { g?: GameModePanel; onChange?: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const [name, setName] = useState("");
  if (!g) return null;
  const act = async (path: string, body: unknown) => {
    setErr(null);
    try { await post(path, body); onChange?.(); } catch (e) { setErr(String((e as Error).message)); }
  };
  const paused = g.state === "aside" || g.state === "micro";
  const who = g.program?.name ?? "a program";
  const status = g.state === "micro" ? <>A small model is handling light work while <b>{who}</b> runs; digests wait.</>
    : g.state === "aside" ? <>Stepped aside for <b>{who}</b> ({g.program?.why}): local jobs wait, cloud AIs keep working.
        {g.resume_in != null ? <> The model comes back in about {Math.ceil(g.resume_in / 60)} min.</> : g.manual ? " Press RESUME when you're done." : " The model comes back a few minutes after it closes."}</>
    : g.state === "asking" ? <><b>{who}</b> is using the graphics card. The inbox asks whether to step aside.</>
    : g.mode === "never" ? "Off: the local model keeps running whatever else runs."
    : "Watching for games and heavy programs on the graphics card.";
  const rules = Object.entries(g.programs).filter(([, p]) => p.counts || p.micro);

  return (
    <section data-testid="gamemode">
      <h3 className="display mb-1 text-[12px] text-cyan">Game mode</h3>
      {err && <div className="mb-1 border border-red/50 px-2 py-1 text-red">{err}</div>}
      <div className="flex flex-wrap items-center gap-2">
        <span className={`light ${paused ? "idle" : g.mode === "never" ? "down" : "up"}`} />
        <span className="min-w-0 flex-1 text-ink/85">{status}</span>
        {paused
          ? <button className="chip" onClick={() => act("/api/gamemode/pause", { on: false })} disabled={!g.manual}
              title={g.manual ? "Load the model again now" : "Comes back on its own after the program closes"}>RESUME</button>
          : <button className="chip" onClick={() => act("/api/gamemode/pause", { on: true })}
              title="Unload the local model now, until you press RESUME">PAUSE FOR A GAME</button>}
      </div>
      {g.note && <p className="mt-1 text-mute">{g.note}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="text-mute">Step aside:</span>
        {MODES.map(([m, label, tip]) => (
          <button key={m} className={`chip ${g.mode === m ? "" : "mute"}`} aria-pressed={g.mode === m} title={tip}
            onClick={() => act("/api/gamemode/settings", { mode: m })}>{label}</button>
        ))}
      </div>
      {g.card && <p className="mt-1 text-mute">{g.card.name}: {g.card.used_gb} of {g.card.total_gb} GB graphics memory in use.</p>}
      {g.seen.length > 0 && (
        <div className="mt-1">
          <div className="text-mute">Using it now:</div>
          {g.seen.map((p) => {
            const rule = g.programs[p.name.toLowerCase()]?.counts;
            return (
              <div key={p.name} className="flex flex-wrap items-center gap-2 border-b border-cyan/10 py-0.5">
                <span className="min-w-0 flex-1 truncate font-mono text-[11.5px]">{p.name}</span>
                <span className="text-mute">{p.vram_gb} GB{p.busy != null ? ` · ${Math.round(p.busy)}% busy` : ""}</span>
                <button className={`chip ${rule === "always" ? "" : "mute"}`} onClick={() => act("/api/gamemode/program", rule === "always" ? { name: p.name, clear: true } : { name: p.name, counts: "always" })}
                  title="Always step aside when this program runs">ALWAYS</button>
                <button className={`chip ${rule === "never" ? "red" : "mute"}`} onClick={() => act("/api/gamemode/program", rule === "never" ? { name: p.name, clear: true } : { name: p.name, counts: "never" })}
                  title="Never step aside for this program">NEVER</button>
              </div>
            );
          })}
        </div>
      )}
      {rules.length > 0 && (
        <div className="mt-2">
          <div className="text-mute">Remembered:</div>
          {rules.map(([n, p]) => (
            <div key={n} className="flex flex-wrap items-center gap-2 py-0.5">
              <span className="min-w-0 flex-1 truncate font-mono text-[11.5px]">{n}</span>
              <span className="text-mute">{[p.counts === "always" && "always steps aside", p.counts === "never" && "never steps aside",
                p.micro === "keep" && "small model keeps working", p.micro === "pause" && "pauses fully"].filter(Boolean).join(" · ")}</span>
              <button className="chip mute" onClick={() => act("/api/gamemode/program", { name: n, clear: true })}>FORGET</button>
            </div>
          ))}
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="program name, e.g. Valorant.exe" aria-label="program name"
          className="min-w-[200px] flex-1 border border-cyan/30 bg-void/80 px-2 py-1 font-mono text-[12px] text-ink outline-none focus:border-cyan" />
        <button className="chip" disabled={!name.trim()} onClick={() => { act("/api/gamemode/program", { name: name.trim(), counts: "always" }); setName(""); }}>ALWAYS STEP ASIDE</button>
      </div>
      <p className="mt-1 text-mute">Sage OS reads the graphics card the way Task Manager does (any brand). When something needs it, local jobs pause and the
        local model unloads; if a small model fits beside it, the inbox asks whether it may keep working on light jobs.</p>
    </section>
  );
}
