import type { UsageWindow } from "../types";

const LABELS: Record<string, string> = {
  five_hour: "5h", seven_day: "7d", seven_day_opus: "7d Opus", seven_day_sonnet: "7d Sonnet", overage: "extra",
};
const ORDER = ["five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet", "overage"];

function resets(ts: number | null) {
  if (!ts) return "";
  const s = ts - Date.now() / 1000;
  if (s <= 0) return "resetting";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h >= 24 ? `resets in ${Math.floor(h / 24)}d ${h % 24}h` : `resets in ${h}h ${m}m`;
}

/** Subscription limit usage, reported by Claude Code on each turn (rate_limit_event). */
export function UsageBars({ usage, compact }: { usage?: Record<string, UsageWindow>; compact?: boolean }) {
  const keys = ORDER.filter((k) => usage?.[k]);
  if (!keys.length) {
    return <span className="chip mute" title="Claude Code reports subscription usage with each turn; it appears after your first message.">usage —</span>;
  }
  return (
    <div className="flex items-center gap-3">
      {keys.map((k) => {
        const u = usage![k];
        const pct = u.utilization == null ? null : Math.round(u.utilization * 100);
        const hot = u.status !== "allowed" || (pct ?? 0) >= 80;
        return (
          <div key={k} className="flex items-center gap-1.5 text-[10.5px]"
            title={pct == null
              ? `${LABELS[k] ?? k}: under Claude's warning threshold (exact % is only reported near the limit) · ${resets(u.resets_at)}`
              : `${LABELS[k] ?? k}: ${pct}% used · ${u.status} · ${resets(u.resets_at)}`}>
            <span className="text-mute">{LABELS[k] ?? k}</span>
            <div className={`relative h-2 ${compact ? "w-14" : "w-24"} border ${hot ? "border-amber/70" : "border-orange/50"}`}>
              <div className={`absolute inset-y-0 left-0 ${hot ? "bg-amber" : "bg-orange"} ${pct == null ? "opacity-30" : ""}`}
                style={{ width: pct == null ? "0%" : `${pct}%`, boxShadow: pct == null ? "none" : "0 0 8px currentColor" }} />
            </div>
            <span className={`font-dot text-[14px] leading-none ${hot ? "text-amber" : "text-orange"}`}>{pct == null ? (u.status === "allowed" ? "OK" : u.status) : `${pct}%`}</span>
            {!compact && u.resets_at && <span className="text-mute">{resets(u.resets_at).replace("resets in ", "↻ ")}</span>}
          </div>
        );
      })}
    </div>
  );
}
