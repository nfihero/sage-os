import type { ReactNode } from "react";
import { ago } from "../util";

/** The planet card's vocabulary, shared by every panel: readout rows (small caps label, value on the right, a
 *  dashed hairline under each), dot-matrix meters, and glowing Doto numerals like the clock. */

export function Row({ k, v, hot, title }: { k: string; v: ReactNode; hot?: boolean; title?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-dashed border-cyan/10 py-[3px]">
      <span className="text-[11px] uppercase tracking-[.16em] text-mute">{k}</span>
      <span className={`min-w-0 truncate text-right font-mono text-[12px] ${hot ? "glow-cyan" : "text-ink"}`} title={title ?? (typeof v === "string" ? v : undefined)}>{v}</span>
    </div>
  );
}

export function Meter({ label, value, of, unit, pct }: { label: ReactNode; value: string; of?: string; unit?: string; pct: number }) {
  return (
    <div className="mb-2">
      <div className="flex items-baseline justify-between gap-2 text-[11px] text-mute">
        <span className="min-w-0 truncate">{label}</span>
        <span className="flex-none"><Num className={`text-[16px] ${pct > 92 ? "!text-amber" : ""}`}>{value}</Num>{of && <> / {of}</>}{unit && <> {unit}</>}</span>
      </div>
      <div className="vram-bar mt-1"><div className={`vram-fill ${pct > 92 ? "hot" : ""}`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>
    </div>
  );
}

/** A number in the clock's face: Doto, fixed-width digits, phosphor glow. */
export function Num({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`font-dot glow-cyan leading-none ${className}`}>{children}</span>;
}

/** "4d", "12m" in the clock's face, for list rows. */
export function Ago({ ts, now, className = "" }: { ts?: number | null; now: number; className?: string }) {
  const t = ago(ts, now);
  return t ? <span className={`font-dot text-[13px] leading-none text-cyan/75 ${className}`}>{t}</span> : null;
}
