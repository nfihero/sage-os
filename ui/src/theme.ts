import { useEffect, useState } from "react";

export type Theme = "phosphor" | "tron" | "amber";
export const THEMES: Theme[] = ["phosphor", "tron", "amber"];

function read<T extends string>(key: string, fallback: T): T {
  try { return (localStorage.getItem(key) as T) || fallback; } catch { return fallback; }
}
function write(key: string, v: string) {
  try { localStorage.setItem(key, v); } catch { /* private mode */ }
}

export function applyTheme(theme: Theme, motion: Motion = "full") {
  const root = document.documentElement;
  write("aos.motion", motion);
  root.classList.toggle("reduce-motion", reducedMotion());
  if (theme === "phosphor") delete root.dataset.theme; else root.dataset.theme = theme;
  window.dispatchEvent(new Event("aos-theme"));
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => read<Theme>("aos.theme", "phosphor"));
  const [motion, setMotion] = useState<Motion>(() => read<Motion>("aos.motion", "full"));
  useEffect(() => { applyTheme(theme, motion); write("aos.theme", theme); }, [theme, motion]);
  return { theme, setTheme, motion, setMotion };
}

/** Resolved colour of a theme token, re-read whenever the theme changes. */
export function useCssColor(token: string): string {
  const get = () => getComputedStyle(document.documentElement).getPropertyValue(token).trim() || "#3dff8b";
  const [c, setC] = useState(get);
  useEffect(() => {
    const on = () => requestAnimationFrame(() => setC(get()));
    window.addEventListener("aos-theme", on);
    return () => window.removeEventListener("aos-theme", on);
  }, [token]);
  return c;
}

export function usePageVisible() {
  const [v, setV] = useState(!document.hidden);
  useEffect(() => {
    const on = () => setV(!document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  return v;
}

export type Motion = "auto" | "full" | "reduced";
export const osReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
/** App setting wins; "auto" follows Windows' "Animation effects" (which Chrome reports as reduced motion). */
export const reducedMotion = () => {
  const m = read<Motion>("aos.motion", "full");
  return m === "reduced" || (m === "auto" && osReducedMotion());
};
