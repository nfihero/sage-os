import type { HubState } from "../useHub";
import type { Guard } from "../types";
import { THEMES, osReducedMotion, type Motion, type Theme } from "../theme";
import { useNow } from "../util";
import { SafetyChip } from "./Safety";
import { UsageBars } from "./Usage";

const SERVICES = [
  ["gateway", "Gateway", ":8642"],
  ["router", "Router", ":18434"],
  ["sidecar", "Guardian", ":18435"],
] as const;

type ThemeCtl = { theme: Theme; setTheme: (t: Theme) => void; motion: Motion; setMotion: (m: Motion) => void };

export default function TopBar({ hub, inboxCount, compact, unseen, onSafety, theme, onLogo }: {
  hub: HubState; inboxCount: number; compact: boolean; unseen: Guard[]; onSafety: () => void; theme: ThemeCtl; onLogo?: () => void;
}) {
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
        {SERVICES.map(([k, label, port]) => {
          const s = h?.[k];
          const cls = !s ? "idle" : s.up ? "up" : "down";
          const tip = s ? (s.up ? `${label} up · ${s.ms} ms${s.version ? ` · v${s.version}` : ""}` : `${label} DOWN · ${s.error ?? ""}`) : "waiting";
          return (
            <span key={k} title={tip} data-service={k} data-up={s?.up ?? ""} className="readout flex items-center gap-1.5 text-[12px] tracking-[.12em]">
              <span className={`light ${cls}`} />
              {!compact && <span className={s && !s.up ? "text-red" : "text-ink/85"}>{label.toUpperCase()}</span>}
              {!compact && <span className="text-mute">{port}</span>}
            </span>
          );
        })}
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-3">
        {!compact && <UsageBars usage={hub.panels.claude_usage} compact />}
        {failed.length > 0 && (
          <span className="chip red" title={failed.map((f) => `${f.adapter}: ${f.check} — ${f.detail}`).join("\n")}>⚠ {failed.length} smoke</span>
        )}
        <SafetyChip safety={hub.panels.safety ?? []} unseen={unseen} onClick={onSafety} />
        <span className={`chip ${inboxCount ? "amber pulse-amber" : "mute"}`} title="Items waiting for you in the inbox">INBOX <span className="font-dot text-[15px] leading-none">{inboxCount}</span></span>
        <select value={theme.theme} onChange={(e) => theme.setTheme(e.target.value as Theme)} title="Theme"
          className="border border-cyan/35 bg-void px-1 py-0.5 text-[10.5px] uppercase text-cyan">
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
