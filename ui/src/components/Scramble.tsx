import { useEffect, useRef, useState } from "react";
import { reducedMotion } from "../theme";

const GLYPHS = "▓▒░<>/\\|=+*#%01ABCDEFXYZ";

/** eDEX-style decode: random glyphs resolve left to right whenever `text` changes. */
export default function Scramble({ text, ms = 420 }: { text: string; ms?: number }) {
  const [out, setOut] = useState(text);
  const raf = useRef(0);
  useEffect(() => {
    if (reducedMotion()) { setOut(text); return; }
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / ms);
      const fixed = Math.floor(p * text.length);
      let s = text.slice(0, fixed);
      for (let i = fixed; i < text.length; i++) s += text[i] === " " ? " " : GLYPHS[(Math.random() * GLYPHS.length) | 0];
      setOut(s);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [text, ms]);
  return <>{out}</>;
}
