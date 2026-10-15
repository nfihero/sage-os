import type { HubState } from "../useHub";
import type { Guard } from "../types";
import { THEMES, osReducedMotion, type Motion, type Theme } from "../theme";
import { useNow } from "../util";
import { SafetyChip } from "./Safety";
import { UsageBars } from "./Usage";
import { UpdateChip } from "./Update";

// Hermes' services, named for what they do; the tooltip keeps the technical name and port.
const SERVICES = [
  ["gateway", "Hermes", "Hermes gateway :8642, the local agent"],
  ["router", "Models", "llama.cpp router :18434, serves the local models"],
  ["sidecar", "Guard", "Guardian sidecar :18435, checks the local agent's commands"],
] as const;

type ThemeCtl = { theme: Theme; setTheme: (t: Theme) => void; motion: Motion; setMotion: (m: Motion) => void };

export default function TopBar({ hub, inboxCount, compact, unseen, onSafety, theme, onLogo, onBookshelf, onGuide, onModels, onUsage, onReport }: {
  hub: HubState; inboxCount: number; compact: boolean; unseen: Guard[]; onSafety: () => void; theme: ThemeCtl; onLogo?: () => void;
  onBookshelf: () => void; onGuide: () => void; onModels: () => void; onUsage: () => void; onReport: () => void;
}) {
  const vault = hub.panels.vault;
  const now = useNow(1000);
  const h = hub.panels.health;
  const failed = hub.smoke.filter((s) => !s.ok);
  const d = new Date(now * 1000);
  const hh = String(d.getHours()).padStart(2, "0"), mm = String(d.getMinutes()).padStart(2, "0"), ss = String(d.getSeconds()).padStart(2, "0");
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-cyan/25 bg-void/60 px-4 py-2 backdrop-blur">
      <div className="flex items-center gap-4">
        <button onClick={onLogo} title="Replay boot sequence" className="display flex items-baseline gap-1.5 text-[17px] font-bold tracking-[.2em]">
          <span className="glow-cyan">SAGE</span><span className="glow-orange">//</span><span className="glow-cyan">OS</span>
        </button>
        {!compact && (
          <div className="readout flex items-baseline gap-2 border-l border-cyan/20 pl-4">
            <span className="font-dot glow-cyan text-[30px] leading-none">{hh}<span className="opacity-60">:</span>{mm}<span className="opacity-60">:</span>{ss}</span>
            <span className="text-[11px] tracking-[.18em] text-mute">{d.toLocaleDateString([], { month: "short", day: "2-digit" }).toUpperCase()}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {SERVICES.map(([k, label, what]) => {
          const s = h?.[k];
          const state = s?.state ?? (s ? (s.up ? "up" : "down") : undefined);
          if (state === "absent") return null;            // not set up on this computer: optional (D22.1)
          const cls = state === "up" ? "up" : state === "down" ? "down" : "idle";
          const tip = `${what}
` + (!s ? "waiting" : state === "up" ? `up · ${s.ms} ms${s.version ? ` · v${s.version}` : ""}`
            : state === "down" ? `STOPPED · it was running earlier · ${s.error ?? ""}` : "not running (start it in Hermes if you use it)");
          return (
            <span key={k} title={tip} data-service={k} data-state={state ?? ""} className="readout flex items-center gap-1.5 text-[12px] tracking-[.12em]">
              <span className={`light ${cls}`} />
              {!compact && <span className={state === "down" ? "text-red" : state === "up" ? "text-ink/85" : "text-mute"}>{label.toUpperCase()}</span>}
            </span>
          );
        })}
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-3">
        <button onClick={onUsage} data-testid="usage-open" title="Usage & costs: tokens, spend, limits and prices for every AI"
          className="flex items-center gap-2 hover:opacity-90">
          {!compact && <UsageBars usage={hub.panels.claude_usage} compact />}<span className="chip mute">$ USAGE</span>
        </button>
        {failed.length > 0 && (
          <span className="chip red" title={failed.map((f) => `${f.adapter}: ${f.check} — ${f.detail}`).join("\n")}>⚠ {failed.length} smoke</span>
        )}
        <SafetyChip safety={hub.panels.safety ?? []} unseen={unseen} onClick={onSafety} />
        <span className={`chip ${inboxCount ? "amber pulse-amber" : "mute"}`} title="Items waiting for you in the inbox">INBOX <span className="font-dot text-[15px] leading-none">{inboxCount}</span></span>
        <UpdateChip />
        <button className="chip mute" onClick={onReport} data-testid="report-open" title="Something not working? Tell us; you see everything before it's sent">
          {compact ? "REPORT" : "REPORT A PROBLEM"}</button>
        <button className="chip" onClick={onGuide} data-tour="guide" title="Why Sage OS exists, and a tour of the screen">? GUIDE</button>
        {(() => {          // game mode (G1): always visible, opens its settings in MODELS
          const g = hub.panels.gamemode;
          if (!g) return null;
          const aside = g.state === "aside" || g.state === "micro";
          const label = aside ? (g.state === "micro" ? "SMALL MODEL" : "STEPPED ASIDE") : g.state === "asking" ? "ASKING" : g.mode === "never" ? "OFF" : "WATCHING";
          const tip = aside ? `Local model unloaded while ${g.program?.name ?? "a program"} uses the graphics card` : g.mode === "never" ? "Game mode is off" : "Watching for games on the graphics card";
          return (
            <button className={`chip ${aside || g.state === "asking" ? "amber" : g.mode === "never" ? "mute" : ""}`} onClick={onModels} title={`${tip}. Click for game mode settings.`} data-testid="gamemode-chip">
              GAME MODE{!compact && <span className="text-ink/70"> · {label}</span>}
            </button>
          );
        })()}
        <button className="chip" onClick={onBookshelf} data-testid="bookshelf-open"
          title={vault ? `Bookshelf: ${vault.count} notes${vault.problems ? `, ${vault.problems} with problems` : ""}` : "Bookshelf"}>
          BOOKSHELF <span className="font-dot text-[15px] leading-none">{vault?.count ?? "–"}</span>
        </button>
        <select value={theme.theme} onChange={(e) => theme.setTheme(e.target.value as Theme)} title="Theme"
          className="border border-cyan/35 bg-void px-1 py-0.5 text-[11px] uppercase text-cyan">
          {THEMES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <button className={`chip ${theme.motion === "reduced" || (theme.motion === "auto" && osReducedMotion()) ? "mute" : ""}`}
          onClick={() => theme.setMotion(theme.motion === "auto" ? "full" : theme.motion === "full" ? "reduced" : "auto")}
          title={`Animations: ${theme.motion}${theme.motion === "auto" ? (osReducedMotion() ? " (Windows has animation effects off, so reduced)" : " (following Windows)") : ""}. Click to cycle auto / full / reduced.`}>
          MOTION {theme.motion === "auto" ? (osReducedMotion() ? "AUTO·OFF" : "AUTO") : theme.motion.toUpperCase()}
        </button>
        <span className="flex items-center" title={hub.connected ? "hub stream connected" : "reconnecting to hub"}>
          <span className={`light ${hub.connected ? "up" : "down"}`} />
        </span>
      </div>
    </header>
  );
}
