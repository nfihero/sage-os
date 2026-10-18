import { useEffect, useState } from "react";
import type { HubState } from "../useHub";
import { reducedMotion } from "../theme";

/**
 * Boot sequence, once per browser session (click the logo to replay). A nod to SAGE, the 1950s
 * air-defence network run from CRT consoles; the checks shown are live.
 */
export default function BootScreen({ hub, replay, onShowing }: { hub: HubState; replay: number; onShowing?: (showing: boolean) => void }) {
  const [show, setShow] = useState(() => {
    try { return !sessionStorage.getItem("sageos.booted") && !new URLSearchParams(location.search).has("shot"); } catch { return true; }
  });
  const [step, setStep] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => { if (replay) { setStep(0); setLeaving(false); setShow(true); } }, [replay]);
  useEffect(() => onShowing?.(show), [show]);

  const h = hub.panels.health, c = hub.panels.claude, inbox = hub.panels.inbox?.length ?? 0;
  const st = (ok: boolean | undefined, good = "OK", bad = "DOWN") => (ok === undefined ? "···" : ok ? good : bad);
  const lines: [string, string, boolean | undefined][] = [
    ["HUB LINK", st(hub.connected || undefined), hub.connected || undefined],
    ["HERMES GATEWAY", st(h?.gateway.up), h?.gateway.up],
    ["LLAMA.CPP ROUTER", st(h?.router.up), h?.router.up],
    ["GUARDIAN SIDECAR", st(h?.sidecar.up, "ARMED", "DOWN"), h?.sidecar.up],
    ["CLAUDE CODE", c ? (c.logged_in ? "SIGNED IN" : c.logged_in === false ? "SIGNED OUT" : "···") : "···", c?.logged_in ?? undefined],
    ["SAFETY INTERLOCKS", h?.sidecar.up ? "ENGAGED" : "···", h?.sidecar.up],
    ["OPERATOR QUEUE", `${inbox} WAITING`, inbox === 0 ? true : undefined],   // waiting = amber, not a fault
  ];

  useEffect(() => {
    if (!show) return;
    if (reducedMotion()) { finish(); return; }
    const id = setInterval(() => setStep((s) => s + 1), 140);
    return () => clearInterval(id);
  }, [show]);
  useEffect(() => { if (show && step === lines.length + 5) finish(); }, [step, show]);
  useEffect(() => {
    if (!show) return;
    const skip = () => finish();
    addEventListener("keydown", skip);
    return () => removeEventListener("keydown", skip);
  }, [show]);

  function finish() {
    try { sessionStorage.setItem("sageos.booted", "1"); } catch { /* private mode */ }
    setLeaving(true);
    setTimeout(() => setShow(false), 450);
  }

  if (!show) return null;
  return (
    <div className={`boot ${leaving ? "boot-out" : ""}`} onClick={finish} role="status" aria-label="Sage OS starting">
      <div className="w-[min(640px,88vw)]">
        <div className="font-dot glow-cyan text-[clamp(48px,9vw,92px)] leading-none tracking-[.08em]">
          SAGE<span className="glow-orange">//</span>OS
        </div>
        <div className="display mt-2 text-[clamp(11px,1.6vw,15px)] tracking-[.32em] text-cyan/80">
          SAGE: SEMI-AUTONOMOUS AGENT GROUND ENVIRONMENT
        </div>
        <div className="mt-1 text-[11px] tracking-[.2em] text-mute">OPERATOR CONSOLE · LOCAL NODE</div>
        <div className="my-4 h-px bg-cyan/30" />
        <div className="font-mono text-[13px] leading-7">
          {lines.map(([k, v, ok], i) => i < step && (
            <div key={k} className="boot-line flex">
              <span className="text-ink/80">{k}</span>
              <span className="mx-2 flex-1 overflow-hidden whitespace-nowrap text-mute">{".".repeat(80)}</span>
              <span className={ok === false ? "text-red" : ok ? "glow-cyan" : "text-amber"}>{v}</span>
            </div>
          ))}
          {step > lines.length && <div className="boot-line mt-3 text-cyan">READY<span className="caret" /></div>}
        </div>
        <div className="mt-6 text-[11px] tracking-[.2em] text-mute">PRESS ANY KEY</div>
      </div>
    </div>
  );
}
