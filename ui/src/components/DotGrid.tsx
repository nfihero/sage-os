import { useEffect, useRef } from "react";
import { reducedMotion } from "../theme";

export type Ripple = { x: number; y: number; t: number; color: string };

const GAP = 22;

/**
 * A field of tiny squares behind the UI (Purdue-Hackers-style). Squares near the cursor light up;
 * `ripples` (fired by agent events) sweep rings across the field. Canvas 2D at ~30 fps, paused
 * while the tab is hidden, so it costs almost nothing next to the models on the GPU.
 */
export default function DotGrid({ ripples }: { ripples: React.MutableRefObject<Ripple[]> }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    let w = 0, h = 0, raf = 0, last = 0;
    const mouse = { x: -9999, y: -9999 };
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      w = cv.width = Math.floor(innerWidth * dpr); h = cv.height = Math.floor(innerHeight * dpr);
      cv.style.width = innerWidth + "px"; cv.style.height = innerHeight + "px";
    };
    const color = () => getComputedStyle(document.documentElement).getPropertyValue("--color-cyan").trim();
    let accent = color();
    const onTheme = () => { accent = color(); };
    const onMove = (e: PointerEvent) => { mouse.x = e.clientX * dpr; mouse.y = e.clientY * dpr; };
    const onLeave = () => { mouse.x = mouse.y = -9999; };
    resize();
    addEventListener("resize", resize);
    addEventListener("pointermove", onMove);
    document.addEventListener("pointerleave", onLeave);
    addEventListener("aos-theme", onTheme);

    const draw = (now: number) => {
      raf = requestAnimationFrame(draw);
      if (document.hidden || now - last < 33) return;
      last = now;
      ctx.clearRect(0, 0, w, h);
      const gap = GAP * dpr, R = 150 * dpr;
      const live = reducedMotion() ? [] : ripples.current.filter((r) => now - r.t < 2600);
      ripples.current = live;
      for (let y = gap / 2; y < h; y += gap) {
        for (let x = gap / 2; x < w; x += gap) {
          let a = 0.07, s = 1.4 * dpr, col = accent;
          const dm = Math.hypot(x - mouse.x, y - mouse.y);
          if (dm < R) { const k = 1 - dm / R; a += 0.5 * k * k; s += 1.6 * dpr * k; }
          for (const r of live) {
            const radius = ((now - r.t) / 1000) * 520 * dpr;
            const d = Math.abs(Math.hypot(x - r.x * dpr, y - r.y * dpr) - radius);
            if (d < 34 * dpr) {
              const k = (1 - d / (34 * dpr)) * (1 - (now - r.t) / 2600);
              a += 0.7 * k; s += 1.8 * dpr * k; if (k > 0.25) col = r.color;
            }
          }
          ctx.globalAlpha = Math.min(a, 0.95);
          ctx.fillStyle = col;
          ctx.fillRect(x - s / 2, y - s / 2, s, s);
        }
      }
      ctx.globalAlpha = 1;
    };
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      removeEventListener("resize", resize);
      removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", onLeave);
      removeEventListener("aos-theme", onTheme);
    };
  }, [ripples]);
  return <canvas ref={ref} className="dotgrid" />;
}
