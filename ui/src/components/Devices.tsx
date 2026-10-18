import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { get, post } from "../api";
import { isMac } from "../util";
import { Ago } from "./Readout";

/** Your devices (P1, D45): pair this computer with your others, directly, with a one-time code. No account and no
 *  outside service: they talk to each other over your own network. Sync itself arrives next (P2, P3). */
type Peer = { id: string; name: string; fingerprint: string; address: string | null; added: number; last_seen: number | null };
type View = {
  this: { id: string; name: string; pairing_key: string | null; addresses: string[]; port: number };
  listening: boolean; error: string | null; pairing: { code: string; expires: number } | null; peers: Peer[];
};
type Nearby = { id: string; name: string; address: string };

export default function Devices({ onClose }: { onClose: () => void }) {
  const [v, setV] = useState<View | null>(null);
  const [mode, setMode] = useState<"list" | "host" | "join">("list");
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<Peer | null>(null);
  const load = () => get<View>("/api/devices").then(setV).catch((e) => setErr(String(e.message)));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  // while showing a code, watch for the other device to finish pairing
  useEffect(() => {
    if (mode !== "host") return;
    const before = new Set((v?.peers ?? []).map((p) => p.id));
    const t = setInterval(async () => {
      const now = await get<View>("/api/devices").catch(() => null);
      if (!now) return;
      setV(now);
      const added = now.peers.find((p) => !before.has(p.id));
      if (added) { setDone(added); setMode("list"); }
      else if (!now.pairing) setMode("list");
    }, 1500);
    return () => clearInterval(t);
  }, [mode]);

  const host = async () => {
    setErr(null); setDone(null);
    try { setV(await post<View>("/api/devices/pairing")); setMode("host"); } catch (e) { setErr(String((e as Error).message)); }
  };
  const cancel = async () => { await post("/api/devices/pairing/cancel").catch(() => {}); setMode("list"); load(); };
  const remove = async (p: Peer) => {
    if (!confirm(`Remove ${p.name}? It won't be able to connect to this device again unless you pair them again.`)) return;
    try { setV(await post<View>(`/api/devices/${p.id}/remove`)); } catch (e) { setErr(String((e as Error).message)); }
  };

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel my-auto flex h-auto max-h-full w-full max-w-[820px] min-w-0 flex-col" style={{ flex: "none" }} onClick={(e) => e.stopPropagation()} data-testid="devices">
        <div className="panel-head">
          <span className="tab">YOUR DEVICES</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-mute">your computers, paired directly; no account, no cloud</span>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
        </div>
        <div className="panel-body flex flex-col gap-5 px-5 py-4">
          {!v ? <p className="text-mute">loading…</p> : <>
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[13px]">
              <span className="copy text-ink">This device: <b className="text-cyan">{v.this.name}</b></span>
              <span className="copy text-mute">its key: <span className="font-mono text-cyan">{v.this.pairing_key ?? "none (no keychain)"}</span></span>
            </div>
            {done && <Paired peer={done} mine={v.this.pairing_key} />}
            {mode === "host" && v.pairing && <Host v={v} onCancel={cancel} />}
            {mode === "join" && <Join mine={v.this.pairing_key} onDone={(p) => { setDone(p); setMode("list"); load(); }} onCancel={() => setMode("list")} />}
            {mode === "list" && <>
              <div>
                <div className="kicker"><span>Paired with this device</span><span>{v.peers.length || "none yet"}</span></div>
                {v.peers.length === 0 && <p className="copy m-0 text-[13px] text-ink/80">Pair your other computers so they can share your chats and
                  Bookshelf. They talk to each other directly on your own network; nothing goes through anyone else.</p>}
                {v.peers.map((p) => <PeerRow key={p.id} p={p} onRemove={() => remove(p)} />)}
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="chip h-9 px-4" onClick={host} disabled={!v.this.pairing_key}>+ ADD A DEVICE</button>
                <button className="chip h-9 px-4" onClick={() => { setErr(null); setDone(null); setMode("join"); }} disabled={!v.this.pairing_key}>I HAVE A CODE</button>
              </div>
              <p className="copy m-0 text-[12px] text-mute">Start on either one: <b>ADD A DEVICE</b> shows a code here; on the other device, choose
                <b> I HAVE A CODE</b> and type it. Paired devices share chats and the Bookshelf in the next update.</p>
            </>}
            {v.error && <p className="copy m-0 text-[12.5px] text-amber">{v.error}</p>}
            {err && <p className="copy m-0 text-[12.5px] text-red">{err}</p>}
          </>}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function PeerRow({ p, onRemove }: { p: Peer; onRemove: () => void }) {
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const check = async () => {
    setBusy(true); setMsg(null);
    try { await post(`/api/devices/${p.id}/check`); setMsg({ ok: true, text: "reached it: both sides proved who they are" }); }
    catch (e) { setMsg({ ok: false, text: String((e as Error).message) }); }
    setBusy(false);
  };
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-cyan/10 py-2 text-[13px]">
      <span className="copy min-w-[140px] flex-1 text-ink">{p.name}</span>
      <span className="font-mono text-[12px] text-mute" title="its key">{p.fingerprint}</span>
      <span className="text-[11.5px] text-mute">{p.last_seen ? <>seen <Ago ts={p.last_seen} now={Date.now() / 1000} /> ago</> : "not reached yet"}</span>
      <button className="chip mute" disabled={busy} onClick={check}>{busy ? "CHECKING…" : "CHECK"}</button>
      <button className="chip mute" onClick={onRemove}>REMOVE</button>
      {msg && <span className={`copy w-full text-[12px] ${msg.ok ? "text-cyan" : "text-amber"}`}>{msg.text}</span>}
    </div>
  );
}

function Host({ v, onCancel }: { v: View; onCancel: () => void }) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => { const t = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(t); }, []);
  const left = Math.max(0, Math.round(v.pairing!.expires - now));
  return (
    <div className="flex flex-col gap-3 border border-cyan/40 p-4" data-testid="pairing-code">
      <div className="copy text-[13px] text-ink">On your other device, open Sage OS → <b>⚙ SETTINGS</b> → <b>Your devices</b> → <b>I HAVE A CODE</b>,
        pick <b className="text-cyan">{v.this.name}</b>, and type:</div>
      <div className="font-dot glow-cyan select-all text-center text-[clamp(28px,6vw,46px)] leading-none tracking-[.12em]">{v.pairing!.code}</div>
      <div className="copy text-center text-[12px] text-mute">good for {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")} more · waiting for the other device…</div>
      {!isMac() && <p className="copy m-0 text-[12px] text-amber">If Windows asks whether Sage OS may use private networks, choose <b>Allow</b>: that's how
        your other device reaches this one. Public networks can stay off.</p>}
      {v.this.addresses.length > 0 && <p className="copy m-0 text-[11.5px] text-mute">If the other device doesn't list this one, type this address there:
        <span className="ml-1 font-mono text-ink/80">{v.this.addresses.map((a) => `${a}:${v.this.port}`).join("  or  ")}</span></p>}
      <div><button className="chip mute" onClick={onCancel}>CANCEL</button></div>
    </div>
  );
}

function Join({ mine, onDone, onCancel }: { mine: string | null; onDone: (p: Peer) => void; onCancel: () => void }) {
  const [nearby, setNearby] = useState<Nearby[]>([]);
  const [pick, setPick] = useState<string>("");
  const [typed, setTyped] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const look = () => get<{ nearby: Nearby[] }>("/api/devices/nearby").then((r) => setNearby(r.nearby)).catch(() => {});
    look();
    const t = setInterval(look, 2000);
    return () => clearInterval(t);
  }, []);
  const address = pick || typed.trim();
  const join = async () => {
    setBusy(true); setErr(null);
    try { const r = await post<{ paired: Peer }>("/api/devices/join", { address, code }); onDone(r.paired); }
    catch (e) { setErr(String((e as Error).message)); }
    setBusy(false);
  };
  return (
    <div className="flex flex-col gap-3 border border-cyan/40 p-4">
      <div className="copy text-[13px] text-ink">1. Pick the device that's showing a code</div>
      <div className="flex flex-col gap-1">
        {nearby.length === 0 && <p className="copy m-0 text-[12.5px] text-mute">Looking on this network<span className="dots" /> (press ADD A DEVICE on the other one first)</p>}
        {nearby.map((n) => (
          <button key={n.address} onClick={() => setPick(n.address)} aria-pressed={pick === n.address}
            className={`copy border px-3 py-2 text-left text-[13px] ${pick === n.address ? "border-cyan bg-cyan/10 text-ink" : "border-cyan/25 text-ink/85 hover:border-cyan/60"}`}>
            {n.name}</button>
        ))}
        <input value={typed} onChange={(e) => { setTyped(e.target.value); setPick(""); }} placeholder="or type its address, e.g. 192.168.0.20:8789"
          aria-label="device address" className="border border-cyan/30 bg-void/80 px-2 py-1 font-mono text-[12px] text-ink outline-none focus:border-cyan" />
      </div>
      <div className="copy text-[13px] text-ink">2. Type the code it shows</div>
      <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="XXXX-XXXX-XXXX" aria-label="pairing code"
        autoComplete="off" spellCheck={false}
        className="border border-cyan/40 bg-void/80 px-3 py-2 text-center font-mono text-[20px] tracking-[.15em] text-ink outline-none focus:border-cyan" />
      <div className="flex flex-wrap gap-2">
        <button className="chip h-9 px-4" disabled={busy || !address || code.replace(/[^A-Z0-9]/g, "").length !== 12} onClick={join}>{busy ? "PAIRING…" : "PAIR"}</button>
        <button className="chip mute" onClick={onCancel}>CANCEL</button>
      </div>
      {err && <p className="copy m-0 text-[12.5px] text-red">{err}</p>}
      <p className="copy m-0 text-[11.5px] text-mute">This device's key, which the other one will show once you're paired: <span className="font-mono">{mine}</span></p>
    </div>
  );
}

function Paired({ peer, mine }: { peer: Peer; mine: string | null }) {
  return (
    <div className="border border-cyan/60 bg-cyan/5 p-3" role="status">
      <div className="copy text-[14px] text-ink">Paired with <b className="text-cyan">{peer.name}</b>.</div>
      <p className="copy m-0 mt-1 text-[12.5px] text-ink/80">To be sure nobody stepped in between, check that {peer.name} shows this device's key as
        <span className="mx-1 font-mono text-cyan">{mine}</span> and that its own key there reads <span className="font-mono text-cyan">{peer.fingerprint}</span>.</p>
    </div>
  );
}
