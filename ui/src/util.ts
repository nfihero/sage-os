import { useEffect, useState } from "react";

export function ago(ts?: number | null, now = Date.now() / 1000): string {
  if (!ts) return "—";
  const s = Math.max(0, Math.round(now - ts));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

export function clock(ts?: number | null): string {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function stamp(ts?: number | null): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** "Nail-Qwen3.6-35B-A3B-MTP-UD-IQ3_S" -> "Qwen3.6-35B" : short labels for chips. */
export function shortModel(id?: string | null): string {
  if (!id) return "—";
  const m = id.match(/(Qwen[\d.]+-\d+B|gemma-4-\d+B|gemma-4-\d+b|guardian-\d+b)/i);
  const base = m ? m[1] : id.split("-").slice(0, 2).join("-");
  return id.startsWith("Dirk") ? `Dirk ${base}` : base;
}

export function tokens(n?: number): string {
  if (!n) return "0";
  return n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : `${n}`;
}

export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}
