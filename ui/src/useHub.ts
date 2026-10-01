import { useEffect, useRef, useState } from "react";
import type { Guard, HubEvent, Panels, Smoke } from "./types";
import { emitChat } from "./api";

const MAX_EVENTS = 300;

export type HubState = {
  connected: boolean; panels: Panels; events: HubEvent[]; smoke: Smoke[];
  lastUpdate: Record<string, number>;
};

/** One WebSocket to the hub. Snapshot on connect, then panel replacements and live events. */
export function useHub(): HubState {
  const [state, setState] = useState<HubState>({
    connected: false, panels: {}, events: [], smoke: [], lastUpdate: {},
  });
  const retry = useRef(500);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => { retry.current = 500; };
      ws.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        const now = Date.now();
        if (msg.t === "hello") {
          const s = msg.state;
          setState({
            connected: true, panels: s.panels, smoke: s.smoke,
            events: [...s.events].reverse().slice(0, MAX_EVENTS),
            lastUpdate: Object.fromEntries(Object.keys(s.panels).map((k) => [k, now])),
          });
        } else if (msg.t === "panel") {
          setState((p) => ({
            ...p, panels: { ...p.panels, [msg.name]: msg.data },
            lastUpdate: { ...p.lastUpdate, [msg.name]: now },
          }));
        } else if (msg.t === "chat") {
          emitChat(msg);
        } else if (msg.t === "event") {
          const ev: HubEvent = msg.event;
          setState((p) => {
            const next = { ...p, events: [ev, ...p.events].slice(0, MAX_EVENTS) };
            if (ev.source === "safety") {   // safety panel updates arrive as events, not snapshots
              const feed = [...(p.panels.safety ?? []), ev.data as Guard].slice(-200);
              next.panels = { ...p.panels, safety: feed };
              next.lastUpdate = { ...p.lastUpdate, safety: now };
            }
            return next;
          });
        }
      };
      ws.onclose = () => {
        setState((p) => ({ ...p, connected: false }));
        if (!closed) {
          timer = window.setTimeout(connect, retry.current);
          retry.current = Math.min(retry.current * 2, 8000);
        }
      };
    };
    connect();
    return () => { closed = true; window.clearTimeout(timer); ws?.close(); };
  }, []);

  return state;
}
