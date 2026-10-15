import { useEffect, useState } from "react";
import { get, post } from "../api";

/** D25: where Sage OS keeps things. App data stays on this computer; the Library (notes + files) is what
 *  moves between your devices when it sits in a synced folder. */
type Info = {
  data: { path: string; bytes: number; files: number; legacy: boolean };
  library: { path: string; notes: number; notes_bytes: number; files: number; files_bytes: number; sync: string | null; conflicts: string[] } | null;
  vault: string;
  device: { id: string; name: string; created: number };
};
const mb = (b: number) => (b > 2 ** 30 ? `${(b / 2 ** 30).toFixed(1)} GB` : `${(b / 2 ** 20).toFixed(1)} MB`);

export default function Storage() {
  const [info, setInfo] = useState<Info | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [path, setPath] = useState("");
  const [moving, setMoving] = useState(false);
  const [naming, setNaming] = useState<string | null>(null);
  const load = () => get<Info>("/api/storage").then(setInfo).catch((e) => setErr(String(e.message)));
  useEffect(() => { load(); }, []);

  const open = async (which: string) => {
    setErr(null);
    try { await post("/api/storage/open", { which }); } catch (e) { setErr(String((e as Error).message)); }
  };
  const move = async () => {
    setErr(null); setMsg(null); setMoving(true);
    try {
      const r = await post<{ library: string; old: string; merged: Record<string, { copied: number; same: number; kept_both: number }> }>("/api/storage/library", { path });
      const n = r.merged.Notes;
      setMsg(`The Bookshelf is now in ${r.library}. ${n.copied} notes copied there${n.kept_both ? `, ${n.kept_both} kept twice because they differed` : ""}. The old folder (${r.old}) is untouched; delete it when you're happy.`);
      setPath(""); load();
    } catch (e) { setErr(String((e as Error).message)); }
    setMoving(false);
  };

  const rename = async () => {
    setErr(null);
    try { await post("/api/storage/device", { name: naming ?? "" }); setNaming(null); load(); } catch (e) { setErr(String((e as Error).message)); }
  };

  if (!info) return <div className="p-4 text-mute">{err ?? "loading…"}</div>;
  const lib = info.library;
  return (
    <div className="panel-body text-[12.5px]">
      <div className="mx-auto flex max-w-[860px] flex-col gap-4">
        {err && <div className="border border-red/50 px-2 py-1 text-red">{err}</div>}
        {msg && <div className="border border-cyan/40 px-2 py-1 text-ink/90">{msg}</div>}

        <section className="border border-cyan/25 p-3">
          <div className="flex items-baseline gap-2">
            <h3 className="display text-[13px] text-cyan">Bookshelf folder</h3>
            <span className="text-mute">moves between your devices</span>
          </div>
          {!lib ? (
            <p className="mt-1 text-amber">This install still keeps everything in the old <code>data/</code> folder next to the app. Stop Sage OS and run
              <code className="mx-1">python -m sage_os_hub move-data</code> to move it into app data.</p>
          ) : (
            <>
              <div className="mt-1 break-all font-mono text-[11.5px] text-ink/85">{lib.path}</div>
              <div className="mt-1 text-ink/80">{lib.notes} notes ({mb(lib.notes_bytes)}) · {lib.files} files ({mb(lib.files_bytes)})
                {" · "}{lib.sync ? <span className="text-cyan">synced by {lib.sync}</span> : <span className="text-mute">not in a synced folder: only on this computer</span>}</div>
              <p className="mt-1 text-mute">Notes are what every AI searches. Put any documents (PDF, Word, slides, spreadsheets, text) in Files and they're searchable and digestible too, on every device that shares this Library.</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <button className="chip" onClick={() => open("library")}>OPEN FOLDER</button>
                <button className="chip" onClick={() => open("notes")}>OPEN NOTES</button>
                <button className="chip" onClick={() => open("files")}>OPEN FILES</button>
                <a className="chip" href="/api/storage/export" download>EXPORT NOTES (.zip)</a>
                <a className="chip mute" href="/api/storage/export?files=1" download>EXPORT NOTES + FILES</a>
              </div>
              {lib.conflicts.length > 0 && (
                <div className="mt-2 border border-amber/50 p-2 text-amber">
                  <div>{lib.conflicts.length} file{lib.conflicts.length === 1 ? " was" : "s were"} changed on two devices at once; your sync service kept both copies. Open the folder, keep the one you want and delete the other:</div>
                  <ul className="mt-1 list-disc pl-5 font-mono text-[11px]">{lib.conflicts.slice(0, 30).map((c) => <li key={c}>{c}</li>)}</ul>
                </div>
              )}
              <div className="mt-3 border-t border-cyan/15 pt-2">
                <div className="text-ink/85">Move the Bookshelf to a synced folder</div>
                <p className="text-mute">Paste the full path of a folder inside OneDrive, iCloud Drive, Dropbox or Syncthing, for example
                  <code className="mx-1 break-all">C:\Users\you\OneDrive\Sage Bookshelf</code>. On your other device, point Sage OS at the same folder; whatever is there is kept and merged, never overwritten.</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="full folder path" aria-label="new Bookshelf folder"
                    className="min-w-[240px] flex-1 border border-cyan/30 bg-void/80 px-2 py-1 font-mono text-[12px] text-ink outline-none focus:border-cyan" />
                  <button className="chip" disabled={moving || path.trim().length < 3} onClick={move}>{moving ? "MOVING…" : "MOVE HERE"}</button>
                </div>
              </div>
            </>
          )}
        </section>

        <section className="border border-cyan/20 p-3">
          <div className="flex items-baseline gap-2">
            <h3 className="display text-[13px] text-cyan">App data</h3>
            <span className="text-mute">this computer only</span>
          </div>
          <div className="mt-1 break-all font-mono text-[11.5px] text-ink/85">{info.data.path}</div>
          <div className="mt-1 text-ink/80">{mb(info.data.bytes)} in {info.data.files.toLocaleString()} files: search indexes, copies of your sources, chats, approvals and undo history, local models, sign-ins.</div>
          <p className="mt-1 text-mute">Kept apart from the app, so updating or reinstalling Sage OS never touches it. It isn't synced: each device builds its own indexes from the Bookshelf.</p>
          <div className="mt-2"><button className="chip" onClick={() => open("data")}>OPEN APP DATA</button></div>
          <div className="mt-3 border-t border-cyan/15 pt-2">
            {naming === null ? (
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <span className="text-ink/85">This device: <span className="text-cyan">{info.device.name}</span></span>
                <span className="break-all font-mono text-[11px] text-mute">{info.device.id}</span>
                <button className="chip mute" onClick={() => setNaming(info.device.name)}>RENAME</button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                <input value={naming} onChange={(e) => setNaming(e.target.value)} maxLength={60} aria-label="device name" autoFocus
                  onKeyDown={(e) => { if (e.key === "Enter") rename(); if (e.key === "Escape") { e.stopPropagation(); setNaming(null); } }}
                  className="min-w-[200px] flex-1 border border-cyan/30 bg-void/80 px-2 py-1 text-[12px] text-ink outline-none focus:border-cyan" />
                <button className="chip" disabled={!naming.trim()} onClick={rename}>SAVE</button>
                <button className="chip mute" onClick={() => setNaming(null)}>CANCEL</button>
              </div>
            )}
            <p className="mt-1 text-mute">The name your other devices will see when sync arrives. Each install has its own ID, even when two share a Bookshelf.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
