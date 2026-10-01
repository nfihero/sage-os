import { useEffect, useRef, useState } from "react";
import { onChat } from "./api";
import type { OrbState } from "./components/Orb";

/**
 * Drives an orb from live chat frames for panes whose key starts with `prefix`.
 * `busy`/`waiting`/`error` come from the session status the hub publishes.
 */
export function useOrbState(prefix: string | null, s: { busy: boolean; waiting?: boolean; error?: boolean }) {
  const [pulse, setPulse] = useState(0);
  const [tool, setTool] = useState(0);
  const [streaming, setStreaming] = useState(false);
  const lastDelta = useRef(0);

  useEffect(() => {
    if (!prefix) return;
    return onChat((f) => {
      if (!f.pane.startsWith(prefix)) return;
      if (f.op === "delta") {
        lastDelta.current = performance.now();
        setPulse((p) => p + 1);
        setStreaming(true);
      } else if ((f.op === "item" && f.item?.kind === "tool_use") || (f.op === "tool" && f.event === "tool.started")) {
        setTool((t) => t + 1);
      }
    });
  }, [prefix]);

  useEffect(() => {  // streaming decays to "thinking" when chunks stop arriving
    if (!streaming) return;
    const id = setInterval(() => { if (performance.now() - lastDelta.current > 1200) setStreaming(false); }, 300);
    return () => clearInterval(id);
  }, [streaming]);

  const state: OrbState = s.waiting ? "waiting" : s.error ? "error" : s.busy ? (streaming ? "streaming" : "thinking") : "idle";
  return { state, pulse, tool };
}

/** ?demo in the URL shows buttons that force each orb state (no Claude usage needed). */
export const DEMO = new URLSearchParams(location.search).has("demo");
