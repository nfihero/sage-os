import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SAFE_MD } from "./ChatView";

/** Updates (F1, D38): inside the desktop app, ask it whether a newer signed release is out (at start, then hourly);
 *  offer it with its changelog; install and restart on the user's click. In a plain browser there is no app to ask,
 *  so nothing shows. */
type Info = { version: string; current: string; notes: string | null; date: string | null };
type Invoke = <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;
const invoke: Invoke | undefined = (window as any).__TAURI__?.core?.invoke;
const HOUR = 3600_000;

export function UpdateChip() {
  const [info, setInfo] = useState<Info | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!invoke) return;
    const check = () => invoke<Info | null>("update_check").then(setInfo).catch(() => { /* offline: try next hour */ });
    const first = setTimeout(check, 20_000);          // after start-up settles
    const every = setInterval(check, HOUR);
    return () => { clearTimeout(first); clearInterval(every); };
  }, []);
  if (!info) return null;
  return (
    <>
      <button className="chip amber pulse-amber" onClick={() => setOpen(true)} title={`Sage OS ${info.version} is out (you have ${info.current})`}>
        UPDATE <span className="font-dot text-[15px] leading-none">{info.version}</span>
      </button>
      {open && <UpdateDialog info={info} onClose={() => setOpen(false)} />}
    </>
  );
}

function UpdateDialog({ info, onClose }: { info: Info; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const install = async () => {
    if (!invoke) return;
    setBusy(true); setErr(null);
    try { await invoke("update_install"); }            // the app restarts into the new version
    catch (e) { setErr(String(e)); setBusy(false); }
  };
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-void/70 p-4 backdrop-blur-sm" onClick={busy ? undefined : onClose}>
      <div className="panel flex max-h-[80vh] w-full max-w-[640px] flex-col" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Update Sage OS">
        <div className="panel-head">
          <span className="tab">UPDATE</span>
          <span className="normal-case tracking-normal text-ink/85">Sage OS {info.version} <span className="text-mute">(you have {info.current})</span></span>
          {!busy && <button onClick={onClose} className="ml-auto text-mute hover:text-cyan" aria-label="close">✕</button>}
        </div>
        <div className="panel-body">
          <p className="copy mb-3 text-[12.5px] text-ink/80">Your notes, settings and chats stay as they are: they live outside the app. Sage OS
            stops its hub, installs the update (checked against the owner's signature) and opens again.</p>
          {info.notes
            ? <div className="md reading text-[13.5px] leading-[1.6]"><Markdown remarkPlugins={[remarkGfm]} components={SAFE_MD}>{info.notes}</Markdown></div>
            : <p className="text-mute">No release notes.</p>}
        </div>
        <div className="flex items-center gap-2 border-t border-cyan/20 px-3 py-2">
          {err && <span className="min-w-0 flex-1 truncate text-[12px] text-red" title={err}>{err}</span>}
          <span className="ml-auto flex gap-2">
            {!busy && <button className="chip mute h-8 px-3" onClick={onClose}>LATER</button>}
            <button className="chip amber h-8 px-3" disabled={busy} onClick={install}>{busy ? "DOWNLOADING…" : "UPDATE AND RESTART"}</button>
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
