import { useEffect, useRef } from "react";
import { reducedMotion } from "../theme";

/**
 * Handoff arcs: a stream of glowing dots flies from one element to another across panels
 * (Claude's orb -> sage's orb when work is delegated, back when it reports in).
 * Fire one from anywhere with `handoff(from, to)`; endpoints are CSS selectors.
 */
export function handoff(from: string, to: string, opts: { color?: string; hit?: string } = {}) {
  window.dispatchEvent(new CustomEvent("aos-handoff", { detail: { from, to, ...opts } }));
}
export const ORB = (id: string) => `[data-orb-id="${id}"]`;

type Arc = { x0: number; y0: number; x1: number; y1: number; cx: number; cy: number; t0: number; c0: string; c1: string; hit?: string; landed: boolean };

const TRAVEL = 1300, TAIL = 700, SPARKS = 46;

function center(sel: string) {
  const el = document.querySelector(sel);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (!r.width) return null;
  return { x: r.left + r.width / 2, y: r.top + r.height / 2, el };
}

function colorOf(el: Element | null | undefined) {
  const css = (t: string) => getComputedStyle(document.documentElement).getPropertyValue(t).trim();
  return el?.closest(".claude") ? css("--color-orange") : css("--color-cyan");
}

export default function Handoffs() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const arcs: Arc[] = [];
    let raf = 0;
    const resize = () => {
      cv.width = innerWidth * dpr; cv.height = innerHeight * dpr;
      cv.style.width = innerWidth + "px"; cv.style.height = innerHeight + "px";
    };
    resize();
    addEventListener("resize", resize);

    // Pre-rendered glow dot, tinted per draw with globalCompositeOperation.
    const sprite = document.createElement("canvas");
    sprite.width = sprite.height = 48;
    const sg = sprite.getContext("2d")!;
    const grd = sg.createRadialGradient(24, 24, 0, 24, 24, 24);
    grd.addColorStop(0, "rgba(255,255,255,1)"); grd.addColorStop(0.2, "rgba(255,255,255,.6)"); grd.addColorStop(1, "rgba(255,255,255,0)");
    sg.fillStyle = grd; sg.fillRect(0, 0, 48, 48);
    const tinted = new Map<string, HTMLCanvasElement>();
    const tint = (c: string) => {
      if (tinted.has(c)) return tinted.get(c)!;
      const t = document.createElement("canvas"); t.width = t.height = 48;
      const g = t.getContext("2d")!;
      g.drawImage(sprite, 0, 0); g.globalCompositeOperation = "source-in"; g.fillStyle = c; g.fillRect(0, 0, 48, 48);
      g.globalCompositeOperation = "lighter"; g.globalAlpha = 0.5; g.drawImage(sprite, 0, 0);
      tinted.set(c, t); return t;
    };
    const mix = (a: string, b: string, k: number) => (k < 0.5 ? a : b);

    const bez = (a: Arc, t: number) => {
      const u = 1 - t;
      return { x: u * u * a.x0 + 2 * u * t * a.cx + t * t * a.x1, y: u * u * a.y0 + 2 * u * t * a.cy + t * t * a.y1 };
    };

    const frame = () => {
      ctx.clearRect(0, 0, cv.width, cv.height);
      const now = performance.now();
      ctx.globalCompositeOperation = "lighter";
      for (let i = arcs.length - 1; i >= 0; i--) {
        const a = arcs[i], age = now - a.t0;
        if (age > TRAVEL + TAIL) { arcs.splice(i, 1); continue; }
        const head = Math.min(1, age / TRAVEL);
        // faint guide line along the path
        ctx.globalAlpha = 0.18 * (1 - Math.max(0, age - TRAVEL) / TAIL);
        ctx.strokeStyle = a.c0; ctx.lineWidth = 1 * dpr; ctx.beginPath();
        ctx.moveTo(a.x0 * dpr, a.y0 * dpr); ctx.quadraticCurveTo(a.cx * dpr, a.cy * dpr, a.x1 * dpr, a.y1 * dpr); ctx.stroke();
        // the stream: sparks trailing behind the head, jittered across the path
        for (let s = 0; s < SPARKS; s++) {
          const lag = (s / SPARKS) * 0.45;
          const t = head - lag;
          if (t <= 0 || t > 1) continue;
          const p = bez(a, t);
          const jitter = Math.sin(s * 12.9898 + age * 0.008) * (1 - t) * 10;
          const fade = (1 - s / SPARKS) * (age > TRAVEL ? 1 - (age - TRAVEL) / TAIL : 1);
          const size = (s === 0 ? 26 : 14 * (1 - s / SPARKS) + 4) * dpr;
          ctx.globalAlpha = Math.max(0, fade);
          ctx.drawImage(tint(mix(a.c0, a.c1, t)), (p.x + jitter * 0.3) * dpr - size / 2, (p.y + jitter) * dpr - size / 2, size, size);
        }
        if (!a.landed && head >= 1) {
          a.landed = true;
          if (a.hit) window.dispatchEvent(new CustomEvent("aos-orb-hit", { detail: a.hit }));
        }
        // landing flash
        if (a.landed) {
          const k = 1 - (age - TRAVEL) / TAIL;
          ctx.globalAlpha = Math.max(0, k) * 0.9;
          const r = (40 + (1 - k) * 60) * dpr;
          ctx.drawImage(tint(a.c1), a.x1 * dpr - r / 2, a.y1 * dpr - r / 2, r, r);
        }
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
      raf = arcs.length ? requestAnimationFrame(frame) : 0;
    };

    const onHandoff = (e: Event) => {
      const { from, to, color, hit } = (e as CustomEvent).detail;
      const a = center(from), b = center(to);
      if (!a || !b) return;
      const hitId = hit ?? (b.el.getAttribute("data-orb-id") || undefined);
      if (reducedMotion()) { if (hitId) window.dispatchEvent(new CustomEvent("aos-orb-hit", { detail: hitId })); return; }
      const dist = Math.hypot(b.x - a.x, b.y - a.y);
      arcs.push({
        x0: a.x, y0: a.y, x1: b.x, y1: b.y, cx: (a.x + b.x) / 2, cy: Math.min(a.y, b.y) - dist * 0.35 - 30,
        t0: performance.now(), c0: color ?? colorOf(a.el), c1: color ?? colorOf(b.el), hit: hitId, landed: false,
      });
      if (!raf) raf = requestAnimationFrame(frame);
    };
    addEventListener("aos-handoff", onHandoff);
    return () => { cancelAnimationFrame(raf); removeEventListener("resize", resize); removeEventListener("aos-handoff", onHandoff); };
  }, []);
  return <canvas ref={ref} style={{ position: "fixed", inset: 0, zIndex: 30, pointerEvents: "none" }} />;
}
