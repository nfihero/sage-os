import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { post } from "../api";

/** Report a problem (F1, D32.6): the user writes what happened, reads the whole report, then Sage OS saves it as a
 *  file and opens an email to the project for them to attach it to. Nothing is sent by the app itself. */
export default function Report({ onClose }: { onClose: () => void }) {
  const [description, setDescription] = useState("");
  const [doing, setDoing] = useState("");
  const [text, setText] = useState<string | null>(null);
  const [sent, setSent] = useState<{ name: string; folder: string; to: string; opened: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  const run = async (path: string, then: (r: any) => void) => {
    setBusy(true); setErr(null);
    try { then(await post(path, { description, doing })); } catch (e) { setErr(String((e as Error).message)); }
    setBusy(false);
  };
  const field = "copy w-full border border-cyan/35 bg-void/80 px-2 py-1.5 text-[13.5px] text-ink outline-none focus:border-cyan";

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[760px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="report">
        <div className="panel-head">
          <span className="tab">REPORT A PROBLEM</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-mute">tell us what went wrong; you see everything before it's sent</span>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
        </div>
        <div className="panel-body flex flex-col gap-4 px-5 py-4">
          {sent ? (
            <div className="flex max-w-[600px] flex-col gap-3">
              <h2 className="display m-0 text-[20px] normal-case tracking-[.06em] text-ink">Almost done: send the email</h2>
              <ol className="copy m-0 flex flex-col gap-2 pl-5 text-[14px] text-ink/85">
                <li>The report is saved as <b className="text-ink">{sent.name}</b> in {sent.folder}{sent.opened ? " (that folder is open now)" : ""}.</li>
                <li>{sent.opened ? <>Your email app opened a message to <b className="text-ink">{sent.to}</b>.</>
                  : <>Write an email to <b className="text-ink">{sent.to}</b> (your email app didn't open by itself).</>}</li>
                <li>Attach the report file to that email, and send it.</li>
              </ol>
              <p className="copy m-0 text-[12.5px] text-mute">Thank you. Every report is read, and fixes arrive as an update in the top bar.</p>
              <div><button className="chip h-8 px-4" onClick={onClose}>DONE</button></div>
            </div>
          ) : text === null ? (
            <>
              <label className="flex flex-col gap-1">
                <span className="copy text-[13px] text-ink">What went wrong?</span>
                <textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} className={field} autoFocus
                  placeholder="For example: I pressed Install and start, and it stopped at 40%." maxLength={4000} />
              </label>
              <label className="flex flex-col gap-1">
                <span className="copy text-[13px] text-ink">What were you doing just before? <span className="text-mute">(optional)</span></span>
                <textarea rows={2} value={doing} onChange={(e) => setDoing(e.target.value)} className={field} maxLength={2000} />
              </label>
              <p className="copy m-0 text-[12.5px] text-mute">The report also includes the app version, this computer's system and memory, what you've
                connected, and recent error messages. It never includes your notes, documents, chats or keys. You'll read it in full next.</p>
              <div className="flex flex-wrap gap-2">
                <button className="chip h-8 px-4" disabled={busy || !description.trim()} onClick={() => run("/api/report/preview", (r) => setText(r.text))}>
                  {busy ? "PREPARING…" : "NEXT: READ THE REPORT →"}</button>
              </div>
            </>
          ) : (
            <>
              <p className="copy m-0 text-[13px] text-ink/85">This is the whole report. If anything in it shouldn't be shared, go back and change your words.</p>
              <pre className="m-0 max-h-[46vh] overflow-auto whitespace-pre-wrap border border-cyan/20 bg-void/70 p-3 font-mono text-[11.5px] leading-relaxed text-ink/85"
                data-testid="report-text">{text}</pre>
              <div className="flex flex-wrap gap-2">
                <button className="chip mute h-8 px-4" onClick={() => setText(null)}>← BACK</button>
                <button className="chip h-8 px-4" disabled={busy} onClick={() => run("/api/report/send", setSent)}>
                  {busy ? "SAVING…" : "SAVE IT AND OPEN AN EMAIL"}</button>
              </div>
            </>
          )}
          {err && <p className="m-0 text-[12.5px] text-red">{err}</p>}
        </div>
      </div>
    </div>,
    document.body,
  );
}
