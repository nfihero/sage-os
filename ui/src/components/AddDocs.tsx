import { useRef, useState } from "react";
import { post } from "../api";

/** Adding your documents from the app (O0): files picked or dropped go into the Bookshelf; a folder picked in the
 *  computer's own folder picker becomes a source. Nothing to configure, nothing to open in Explorer. */
export default function AddDocs({ compact }: { compact?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<{ tone: "ok" | "busy" | "err"; text: string } | null>(null);
  const [typing, setTyping] = useState(false);
  const [path, setPath] = useState("");
  const [over, setOver] = useState(false);

  const upload = async (files: File[]) => {
    if (!files.length) return;
    let done = 0;
    const failed: string[] = [];
    for (const f of files) {
      setMsg({ tone: "busy", text: `Adding ${f.name} (${done + 1} of ${files.length})…` });
      try {
        const r = await fetch(`/api/bookshelf/files?name=${encodeURIComponent(f.name)}`, { method: "POST", body: f, headers: { "X-Sage-OS": "1" } });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText);
        done++;
      } catch (e) { failed.push(`${f.name}: ${(e as Error).message}`); }
    }
    setMsg(failed.length
      ? { tone: "err", text: `Added ${done} of ${files.length}. Not added: ${failed.join("; ")}` }
      : { tone: "ok", text: `Added ${done} file${done === 1 ? "" : "s"}. Sage is reading ${done === 1 ? "it" : "them"} now; search finds ${done === 1 ? "it" : "them"} in a moment.` });
  };
  const folder = async (typed?: string) => {
    setMsg({ tone: "busy", text: typed ? "Adding the folder…" : "Choose a folder in the window that just opened (it may be behind this one)…" });
    try {
      const r = await post<{ cancelled?: boolean; name?: string; path?: string; added?: boolean }>("/api/bookshelf/folders", typed ? { path: typed } : {});
      if (r.cancelled) { setMsg(null); return; }
      setTyping(false); setPath("");
      setMsg({ tone: "ok", text: r.added ? `Added ${r.path}. Sage is copying and reading it now; your originals are never changed.`
        : `${r.path} is already in your Bookshelf.` });
    } catch (e) {
      const text = String((e as Error).message);
      if (text.includes("folder picker")) setTyping(true);
      setMsg({ tone: "err", text });
    }
  };

  return (
    <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); upload([...e.dataTransfer.files]); }}
      className={`flex flex-col gap-2 border border-dashed p-3 ${over ? "border-cyan bg-cyan/10" : "border-cyan/30"}`} data-testid="add-docs">
      {!compact && <div className="copy text-[13px] text-ink">Add your documents <span className="text-mute">(PDF, Word, slides, spreadsheets, text). You can also drop files here.</span></div>}
      <div className="flex flex-wrap gap-2">
        <button className="chip h-8 px-3" onClick={() => input.current?.click()}>+ ADD FILES</button>
        <button className="chip h-8 px-3" onClick={() => folder()} title="Sage keeps a copy of the folder and reads it; your files are never changed">+ ADD A FOLDER</button>
        <input ref={input} type="file" multiple hidden onChange={(e) => { upload([...(e.target.files ?? [])]); e.target.value = ""; }} />
      </div>
      {typing && (
        <div className="flex flex-wrap gap-2">
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="the folder's full path" aria-label="folder path"
            className="min-w-[220px] flex-1 border border-cyan/35 bg-void/80 px-2 py-1 font-mono text-[12px] text-ink outline-none focus:border-cyan" />
          <button className="chip" disabled={!path.trim()} onClick={() => folder(path.trim())}>ADD</button>
        </div>
      )}
      {msg && <p role="status" className={`copy m-0 text-[12.5px] ${msg.tone === "err" ? "text-red" : msg.tone === "busy" ? "text-amber" : "text-cyan"}`}>{msg.text}</p>}
    </div>
  );
}
