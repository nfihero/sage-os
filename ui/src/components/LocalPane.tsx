import { useCallback, useEffect, useState } from "react";
import { get, onChat, post } from "../api";
import type { Board, ChatItem, ChatSessionInfo, GameModePanel, ProfileSessions, Session } from "../types";
import { ago, shortModel, useNow } from "../util";
import ChatView from "./ChatView";
import ModelChat from "./ModelChat";
import Orb from "./LazyOrb";
import Scramble from "./Scramble";
import { useOrbState } from "../useOrbState";

const ACTIVE_S = 90;
const PACK_MARK = "\n\n⟦Sage OS reading pack⟧";   // K8: Hermes stores the pack with the message; the strip shows it instead

/** Hermes' message rows -> chat items. tool_calls arrive as a Python repr string, so names are regexed out. */
export function toItems(rows: any[]): ChatItem[] {
  const out: ChatItem[] = [];
  for (const m of rows) {
    const ts = Number(m.timestamp) || 0;
    if (m.role === "user") out.push({ id: m.id, ts, kind: "user", data: { text: String(m.content ?? "").split(PACK_MARK)[0] } });
    else if (m.role === "assistant") {
      if (m.content) out.push({ id: m.id, ts, kind: "text", data: { text: m.content } });
      if (m.tool_calls) {
        const names = [...String(m.tool_calls).matchAll(/['"]name['"]:\s*['"]([\w.-]+)['"]/g)].map((x) => x[1]);
        names.forEach((n, i) => out.push({ id: `${m.id}-t${i}`, ts, kind: "tool_use", data: { tool: n, summary: "" } }));
      }
    } else if (m.role === "tool") {
      out.push({ id: m.id, ts, kind: "tool_result", data: { tool: m.tool_name, text: m.content } });
    }
  }
  return out;
}

export default function LocalPane({ sessions, board, runs, compact, lowPower, chats, game, hermes, onModels }: {
  sessions: ProfileSessions[]; board?: Board; runs: Record<string, { run_id: string | null }>; compact?: boolean; lowPower?: boolean;
  chats?: ChatSessionInfo[]; game?: GameModePanel; hermes?: string; onModels: () => void;
}) {
  const now = useNow(5000);
  const [profile, setProfile] = useState("default");
  const [open, setOpen] = useState<Session | null>(null);
  const [mode, setMode] = useState<"chat" | "hermes">(() => (localStorage.getItem("sageos.local.mode") as "chat" | "hermes") ?? "chat");
  useEffect(() => { try { localStorage.setItem("sageos.local.mode", mode); } catch { /* private mode */ } }, [mode]);
  const hermesOn = hermes === "up" || hermes === "down" || (hermes === undefined && sessions.length > 0);   // has run (D22.1)
  if (mode === "chat" || sessions.length === 0 || !hermesOn) {
    return (
      <section className="panel min-h-0" data-testid="local-pane">
        <div className="panel-head">
          <span className="tab">Chat</span>
          {sessions.length > 0 && hermesOn && <button className="htab" onClick={() => setMode("hermes")} title="Hermes, if you have it">Hermes</button>}
          {(game?.state === "aside" || game?.state === "micro") && (
            <button className="chip amber ml-auto normal-case tracking-normal" onClick={onModels}
              title={`Local model unloaded while ${game.program?.name ?? "a program"} uses the graphics card`}>GAME MODE</button>
          )}
          <button className={`chip ${game?.state === "aside" || game?.state === "micro" ? "" : "ml-auto"} normal-case tracking-normal`} onClick={onModels}>MODELS</button>
        </div>
        <ModelChat sessions={chats ?? []} onModels={onModels} />
      </section>
    );
  }
  return <HermesPane {...{ sessions, board, runs, compact, lowPower, now, profile, setProfile, open, setOpen, onChat: () => setMode("chat") }} />;
}

function HermesPane({ sessions, board, runs, compact, lowPower, now, profile, setProfile, open, setOpen, onChat }: {
  sessions: ProfileSessions[]; board?: Board; runs: Record<string, { run_id: string | null }>; compact?: boolean; lowPower?: boolean;
  now: number; profile: string; setProfile: (p: string) => void; open: Session | null; setOpen: (s: Session | null) => void; onChat: () => void;
}) {
  const p = sessions.find((x) => x.profile === profile) ?? sessions[0];
  const holding = (board?.tasks ?? []).filter((t) => t.assignee === p?.profile && ["running", "blocked", "ready"].includes(t.status));
  const live = p?.sessions[0] && now - (p.sessions[0].last_activity_at ?? p.sessions[0].started_at) < ACTIVE_S;
  const busy = !!p && Object.keys(runs).some((k) => k.startsWith(`hermes:${p.profile}:`));
  const worker = holding.some((t) => t.status === "running");
  const orb = useOrbState(p ? `hermes:${p.profile}:` : null, { busy: busy || worker, waiting: holding.some((t) => t.status === "blocked") && !busy });

  const newChat = async () => {
    const s = await post(`/api/hermes/${p.profile}/sessions`, { title: "Sage OS chat" });
    setOpen({ ...s, source: "api_server" });
  };

  return (
    <section className={`panel min-h-0 ${live ? "streaming" : ""}`} data-testid="local-pane">
      <div className="panel-head">
        <span className="tab" title={p ? `Hermes profile: ${p.profile}` : ""}><Scramble text={p ? p.label ?? p.profile : "Local"} /></span>
        {sessions.filter((x) => x.profile !== p?.profile).map((x) => (
          <button key={x.profile} className="htab" onClick={() => { setProfile(x.profile); setOpen(null); }}>{x.label ?? x.profile}</button>
        ))}
        <button className="htab" onClick={onChat} title="Chat with a local or cloud model">Chat</button>
        <span className="ml-auto" />
        {open ? (
          <button className="chip normal-case tracking-normal" onClick={() => setOpen(null)}>← sessions</button>
        ) : (
          p && <button className="chip normal-case tracking-normal" onClick={() => newChat().catch(() => {})}>+ new chat</button>
        )}
      </div>
      {p && (
        <div className="flex items-center gap-3 border-b border-cyan/15 px-3 py-1.5">
          <Orb id={p.profile} state={orb.state} pulse={orb.pulse} tool={orb.tool} size={compact ? 84 : 104} lowPower={lowPower} dots={1600} />
          <div className="readout min-w-0 flex-1 text-[12px]">
            <div className="flex justify-between"><span className="text-mute text-[11px] tracking-[.16em]">STATE</span>
              <span className={`font-dot text-[16px] leading-none ${orb.state === "idle" ? "text-ink" : "glow-cyan"}`}>{orb.state.toUpperCase()}{worker ? " · WORKER" : ""}</span></div>
            <div className="flex justify-between"><span className="text-mute text-[11px] tracking-[.16em]">MODEL</span>
              <span className="truncate text-ink">{shortModel(p.sessions[0]?.model)}</span></div>
            <div className="flex justify-between"><span className="text-mute text-[11px] tracking-[.16em]">SESSIONS</span>
              <span className="text-ink">{p.total}</span></div>
            <div className="flex justify-between"><span className="text-mute text-[11px] tracking-[.16em]">RUNTIME</span>
              <span className="text-ink">profile · {p.profile}</span></div>
          </div>
        </div>
      )}
      {holding.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-cyan/10 px-3 py-1.5">
          {holding.map((t) => (
            <span key={t.id} className={`chip ${t.status === "blocked" ? "amber" : ""}`} title={t.title}>{t.status} · {t.title.slice(0, 40)}</span>
          ))}
        </div>
      )}
      {!p && <div className="panel-body text-mute">waiting for Hermes sessions…</div>}
      {p && !open && (
        <div className="panel-body flex flex-col gap-1">
          {p.sessions.map((s) => {
            const act = s.last_activity_at ?? s.started_at;
            const hot = now - act < ACTIVE_S;
            return (
              <button key={s.id} onClick={() => setOpen(s)} className="card text-left" title={s.id}>
                <div className="flex items-center gap-2">
                  <span className={`light ${hot ? "up" : "idle"}`} />
                  <span className={`min-w-0 flex-1 truncate text-[13px] ${hot ? "glow-cyan" : "text-ink"}`}>{s.title || "untitled"}</span>
                  <span className="text-[11px] text-mute">{ago(act, now)}</span>
                </div>
                <div className="mt-0.5 flex gap-2 pl-4 text-[11px] text-mute">
                  <span>{s.source}</span><span className="text-cyan/70">{shortModel(s.model)}</span>
                  {!compact && <span>{s.message_count ?? 0} msg</span>}
                </div>
              </button>
            );
          })}
        </div>
      )}
      {p && open && <HermesChat profile={p.profile} s={open} busy={!!runs[`hermes:${p.profile}:${open.id}`]} />}
    </section>
  );
}

function HermesChat({ profile, s, busy }: { profile: string; s: Session; busy: boolean }) {
  const pane = `hermes:${profile}:${s.id}`;
  const [items, setItems] = useState<ChatItem[]>([]);
  const [live, setLive] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => get(`/api/hermes/${profile}/sessions/${s.id}/messages`)
    .then((rows) => { setItems(toItems(rows)); setErr(null); }).catch((e) => setErr(String(e.message))), [profile, s.id]);

  useEffect(() => {
    setItems([]); setLive(""); load();
    return onChat((f) => {
      if (f.pane !== pane) return;
      if (f.op === "delta") setLive((l) => l + f.text);
      else if (f.op === "tool") {
        if (f.event === "tool.started") setItems((xs) => [...xs, { id: `live-${Date.now()}-${Math.random()}`, ts: Date.now() / 1000, kind: "tool_use", data: { tool: f.tool, summary: f.preview ?? "" } }]);
        setLive("");
      } else if (f.op === "error") setItems((xs) => [...xs, { id: `err-${Date.now()}`, ts: Date.now() / 1000, kind: "error", data: { text: f.text } }]);
      else if (f.op === "status" && f.status === "idle") { setLive(""); load(); }
    });
  }, [pane]);

  const foreign = s.source && s.source !== "api_server";
  const banner = (
    <div className="border-b border-cyan/10 px-3 py-1.5 text-[11.5px] text-mute">
      <span className="text-ink">{s.title || "untitled"}</span>
      {foreign && <span className="text-amber"> · started in {s.source}; replies here continue that chat</span>}
      {err && <span className="text-red"> · {err}</span>}
    </div>
  );
  return (
    <ChatView items={items} live={live} busy={busy} tone="cyan" banner={banner} chat={pane}
      placeholder={`Message Hermes (${profile})… runs on the local GPU`}
      onSend={async (t) => {
        setItems((xs) => [...xs, { id: `u-${Date.now()}`, ts: Date.now() / 1000, kind: "user", data: { text: t } }]);
        await post(`/api/hermes/${profile}/sessions/${s.id}/send`, { text: t });
      }}
      onStop={() => { post(`/api/hermes/${profile}/sessions/${s.id}/stop`).catch(() => {}); }} />
  );
}
