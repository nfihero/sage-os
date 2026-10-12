import { useEffect, useState } from "react";
import { get, onChat, post } from "../api";
import type { ChatItem, ChatSessionInfo, ProviderInfo } from "../types";
import { shortModel, useNow } from "../util";
import { Ago } from "./Readout";
import ChatView from "./ChatView";

/** Chats with any OpenAI-compatible model (D22.2): the local engine, ChatGPT, Gemini, Ollama. */
export default function ModelChat({ sessions, onModels, openId, onOpen }: {
  sessions: ChatSessionInfo[]; onModels: () => void; openId?: string | null; onOpen?: (id: string | null) => void;
}) {
  const now = useNow(10000);
  const [ownOpen, setOwnOpen] = useState<string | null>(null);
  const open = openId !== undefined ? openId : ownOpen;          // controlled by the home screen, or on its own
  const setOpen = (id: string | null) => { setOwnOpen(id); onOpen?.(id); };
  const [creating, setCreating] = useState(false);
  const cur = sessions.find((s) => s.id === open) ?? null;

  if (cur) return <Conversation s={cur} onBack={() => setOpen(null)} />;
  return (
    <div className="panel-body flex flex-col gap-1">
      <div className="flex gap-1.5">
        <button className="chip normal-case tracking-normal" onClick={() => setCreating(!creating)}>+ new chat</button>
        <button className="chip mute normal-case tracking-normal" onClick={onModels}>models…</button>
      </div>
      {creating && <NewChat onDone={(id) => { setCreating(false); if (id) setOpen(id); }} onModels={onModels} />}
      {sessions.length === 0 && !creating && (
        <p className="mt-2 text-[12.5px] text-mute">Chat with a model on this computer (the local engine) or a cloud AI. Your notes and documents ride along with each message.</p>
      )}
      {sessions.map((s) => (
        <button key={s.id} onClick={() => setOpen(s.id)}
          className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2.5 border-b border-dashed border-cyan/10 px-1 py-2 text-left hover:bg-cyan/5">
          <span className={`light ${s.status === "running" ? "up" : "idle"}`} />
          <span className="copy min-w-0 truncate text-[13.5px] text-ink">{s.title}</span>
          <Ago ts={s.updated} now={now} />
          <span />
          <span className="col-span-2 truncate font-mono text-[11px] text-mute">{s.provider} · {shortModel(s.model)}</span>
        </button>
      ))}
    </div>
  );
}

function NewChat({ onDone, onModels }: { onDone: (id: string | null) => void; onModels: () => void }) {
  const [providers, setProviders] = useState<ProviderInfo[] | null>(null);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    get<{ providers: ProviderInfo[] }>("/api/models").then((r) => {
      const usable = r.providers.filter((p) => p.models.length > 0 && p.id !== "hermes-router");
      setProviders(usable);
      if (usable[0]) { setProvider(usable[0].id); setModel(usable[0].models[0].id); }
    }).catch((e) => setErr(String(e.message)));
  }, []);
  const p = providers?.find((x) => x.id === provider);
  const create = async () => {
    try { onDone((await post("/api/agents/chat/sessions", { provider, model })).id); }
    catch (e) { setErr(String((e as Error).message)); }
  };
  const field = "border border-cyan/35 bg-void px-2 py-1 text-[12px] text-ink";
  if (providers && providers.length === 0) {
    return (
      <div className="border border-cyan/20 p-2 text-[12px] text-ink/80">
        No model is running yet. Start one on this computer, or connect a cloud AI.
        <button className="chip ml-2" onClick={onModels}>OPEN MODELS</button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-end gap-2 border border-cyan/20 p-2 text-[11px] text-mute">
      <label className="flex flex-col gap-0.5">where
        <select className={field} value={provider} onChange={(e) => { setProvider(e.target.value); setModel(providers?.find((x) => x.id === e.target.value)?.models[0]?.id ?? ""); }}>
          {(providers ?? []).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
        </select>
      </label>
      <label className="flex min-w-0 flex-col gap-0.5">model
        <select className={`${field} max-w-[220px]`} value={model} onChange={(e) => setModel(e.target.value)}>
          {(p?.models ?? []).map((m) => <option key={m.id} value={m.id}>{m.id}</option>)}
        </select>
      </label>
      <button className="chip h-7 px-3" disabled={!model} onClick={create}>start</button>
      <button className="chip mute h-7 px-3" onClick={() => onDone(null)}>cancel</button>
      {err && <span className="text-red">{err}</span>}
    </div>
  );
}

function Conversation({ s, onBack }: { s: ChatSessionInfo; onBack: () => void }) {
  const pane = `chat:${s.id}`;
  const [items, setItems] = useState<ChatItem[]>([]);
  const [live, setLive] = useState("");
  useEffect(() => {
    let alive = true;
    setItems([]); setLive("");
    get<ChatItem[]>(`/api/agents/chat/sessions/${s.id}/history`).then((x) => alive && setItems(x)).catch(() => {});
    const off = onChat((f) => {
      if (f.pane !== pane) return;
      if (f.op === "delta") setLive((l) => l + f.text);
      if (f.op === "item") {
        setItems((xs) => [...xs, f.item]);
        if (f.item.kind === "text" || f.item.kind === "tool_use" || f.item.data?.turn_end) setLive("");
      }
    });
    return () => { alive = false; off(); };
  }, [s.id]);
  const banner = (
    <div className="flex items-center gap-2 border-b border-cyan/10 px-3 py-1.5 text-[11.5px] text-mute">
      <button className="chip normal-case tracking-normal" onClick={onBack}>← chats</button>
      <span className="min-w-0 flex-1 truncate text-ink">{s.title}</span>
      <span className="text-cyan/70">{s.model}</span>
    </div>
  );
  return (
    <ChatView items={items} live={live} busy={s.status === "running"} tone="cyan" banner={banner} chat={pane}
      placeholder={`Message ${s.model}… (Enter to send)`}
      onSend={async (t) => { await post(`/api/agents/chat/sessions/${s.id}/send`, { text: t }); }}
      onStop={() => { post(`/api/agents/chat/sessions/${s.id}/interrupt`).catch(() => {}); }} />
  );
}
