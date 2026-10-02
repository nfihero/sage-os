import { useEffect, useState } from "react";
import { get, onChat, post } from "../api";
import type { ChatItem, ClaudePanel, UsageWindow } from "../types";
import ChatView from "./ChatView";
import { UsageBars } from "./Usage";
import Orb from "./LazyOrb";
import type { OrbState } from "./Orb";
import Scramble from "./Scramble";
import { handoff, ORB } from "./Handoffs";
import { DEMO, useOrbState } from "../useOrbState";

const MODELS = [["", "default"], ["opus", "Opus"], ["sonnet", "Sonnet"], ["haiku", "Haiku"]];

export default function ClaudePane({ panel, usage, inboxCount, lowPower }: {
  panel?: ClaudePanel; usage?: Record<string, UsageWindow>; inboxCount: number; lowPower?: boolean;
}) {
  const sessions = panel?.sessions ?? [];
  const [sid, setSid] = useState<string | null>(() => localStorage.getItem("aos.claude.sid"));
  const [items, setItems] = useState<ChatItem[]>([]);
  const [live, setLive] = useState("");
  const [creating, setCreating] = useState(false);
  const cur = sessions.find((s) => s.id === sid) ?? null;

  useEffect(() => {  // fall back to the most recent session
    if (!cur && sessions.length) setSid(sessions[0].id);
  }, [sessions.length, cur]);
  useEffect(() => { try { if (sid) localStorage.setItem("aos.claude.sid", sid); } catch { /* private mode */ } }, [sid]);

  useEffect(() => {
    if (!sid) return;
    let alive = true;
    setItems([]); setLive("");
    get<ChatItem[]>(`/api/claude/sessions/${sid}/items`).then((x) => alive && setItems(x)).catch(() => {});
    const off = onChat((f) => {
      if (f.pane !== `claude:${sid}`) return;
      if (f.op === "delta") setLive((l) => l + f.text);
      if (f.op === "item") {
        setItems((xs) => [...xs, f.item]);
        if (f.item.kind === "text" || f.item.kind === "tool_use" || f.item.data?.turn_end) setLive("");
      }
    });
    return () => { alive = false; off(); };
  }, [sid]);

  const busy = cur?.status === "running" || cur?.status === "waiting";
  const lastReply = [...items].reverse().find((i) => i.kind === "error" || i.kind === "text")?.data?.text as string | undefined;
  const [loginHint, setLoginHint] = useState(false);
  const needsLogin = panel?.logged_in !== true && (panel?.logged_in === false || loginHint) || (!!lastReply && /not logged in/i.test(lastReply) && panel?.logged_in !== true);

  const banner = (
    <>
      {cur?.status === "waiting" && (
        <div className="pulse-amber mx-3 mt-2 border border-amber/60 px-3 py-1.5 text-[12.5px] text-amber">
          <span className="font-dot mr-2 text-[16px]">AWAITING APPROVAL</span>{inboxCount} item{inboxCount === 1 ? "" : "s"} in the inbox →
        </div>
      )}
      {needsLogin && (
        <div className="mx-3 mt-2 border border-orange/60 px-3 py-2 text-[12.5px] text-orange">
          <div>Claude Code isn't signed in for Sage OS yet. Open a normal terminal (Command Prompt or PowerShell, not this chat) and run:</div>
          <code className="mt-1 block select-all break-all bg-void/80 px-2 py-1 text-ink">&amp; "{panel?.cli}" auth login</code>
          <div className="mt-1 text-mute">Leave out the leading <code>&amp;</code> in Command Prompt. Sign in with your Claude account in the browser it opens; this banner clears by itself within ~15 s.</div>
        </div>
      )}
    </>
  );

  useEffect(() => {  // Claude filing/answering kanban work = a handoff to the assignee's orb
    if (!sid) return;
    return onChat((f) => {
      if (f.pane !== `claude:${sid}` || f.op !== "item" || f.item.kind !== "tool_use" || f.item.data?.tool !== "Bash") return;
      const cmd = String(f.item.data?.input?.command ?? "");
      if (!/kanban\s+(create|comment|unblock|assign)/.test(cmd)) return;
      const who = cmd.match(/--assignee[= ]+["']?([\w-]+)/)?.[1] ?? "default";
      handoff(ORB("claude"), ORB(who));
    });
  }, [sid]);
  const orb = useOrbState(sid ? `claude:${sid}` : null, {
    busy, waiting: cur?.status === "waiting", error: cur?.status === "error",
  });
  const [demo, setDemo] = useState<OrbState | null>(null);
  const [demoPulse, setDemoPulse] = useState(0);
  const [demoTool, setDemoTool] = useState(0);
  const tabs = sessions.slice(0, 4);

  return (
    <section className="panel claude min-h-0" data-testid="claude-pane">
      <div className="panel-head overflow-hidden">
        <span className="tab"><Scramble text={cur ? `Main - ${cur.title.slice(0, 22)}` : "Claude Code"} /></span>
        {tabs.filter((t) => t.id !== cur?.id).slice(0, 3).map((t) => (
          <button key={t.id} className="htab normal-case tracking-normal" onClick={() => setSid(t.id)} title={t.cwd}>
            {t.title.slice(0, 18)}{t.status !== "idle" ? " •" : ""}
          </button>
        ))}
        {Array.from({ length: Math.max(0, 3 - Math.max(0, tabs.length - (cur ? 1 : 0))) }).map((_, i) => (
          <button key={`e${i}`} className="htab empty" onClick={() => setCreating(true)} title="new session">Empty</button>
        ))}
        {sessions.length > 4 && (
          <select value={sid ?? ""} onChange={(e) => setSid(e.target.value)} title="older sessions"
            className="ml-auto max-w-[120px] border border-orange/40 bg-void px-1 py-0.5 text-[11px] normal-case tracking-normal text-ink">
            {sessions.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
          </select>
        )}
        <button className={`chip orange normal-case tracking-normal ${sessions.length > 4 ? "" : "ml-auto"}`} onClick={() => setCreating(!creating)}>+ new</button>
      </div>
      {creating && <NewSession panel={panel} onDone={(id) => { setCreating(false); if (id) setSid(id); }} />}
      <div className="orb-host flex min-h-0 flex-1 flex-col @container">
      <div className="flex min-h-0 flex-1 flex-col @[640px]:flex-row">
        <aside className="flex shrink-0 items-center gap-3 border-b border-orange/20 px-3 py-2
                          @[640px]:w-[250px] @[640px]:flex-col @[640px]:border-b-0 @[640px]:border-r @[640px]:py-3">
          <Orb id="claude" state={demo ?? orb.state} tone="claude" pulse={orb.pulse + demoPulse} tool={orb.tool + demoTool} size="var(--orb)" lowPower={lowPower} />
          <div className="readout min-w-0 flex-1 text-[12px] @[640px]:w-full @[640px]:flex-none">
            <Row k="State" v={(demo ?? orb.state).toUpperCase()} hot={(demo ?? orb.state) !== "idle"} dot />
            <Row k="Model" v={cur?.model ?? "default"} />
            <Row k="Folder" v={cur ? cur.cwd.split(/[\\/]/).slice(-2).join("/") : "—"} />
            <Row k="Turns" v={String(cur?.turns ?? 0)} />
          </div>
          <div className="hidden w-full border-t border-orange/20 pt-2 @[640px]:block">
            <div className="kicker"><span>Subscription</span><span>usage</span></div>
            <UsageBars usage={usage} />
          </div>
          {DEMO && (
            <div className="flex w-[120px] flex-wrap gap-1 text-[10px] @[640px]:w-full @[640px]:border-t @[640px]:border-orange/20 @[640px]:pt-2">
              {(["idle", "thinking", "streaming", "waiting", "error"] as OrbState[]).map((st) => (
                <button key={st} className={`chip ${demo === st ? "amber" : "orange"}`} onClick={() => setDemo(demo === st ? null : st)}>{st}</button>
              ))}
              <button className="chip orange" onClick={() => setDemoPulse((p) => p + 1)}>+wave</button>
              <button className="chip orange" onClick={() => setDemoTool((t) => t + 1)}>+tool</button>
              <button className="chip orange" onClick={() => handoff(ORB("claude"), ORB("default"))}>→hermes</button>
              <button className="chip orange" onClick={() => handoff(ORB("default"), ORB("claude"))}>←hermes</button>
            </div>
          )}
        </aside>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {cur ? (
            <ChatView items={items} live={live} busy={busy} tone="orange" banner={banner}
              placeholder="Ask Claude to plan, review, or work… (Enter to send, Shift+Enter for a new line)"
              disabled={!panel?.cli ? "claude.exe not found. Install the Claude desktop app." : null}
              onSend={async (t) => {
                if (/^\/(login|logout)/i.test(t.trim())) { setLoginHint(true); throw new Error("Slash commands like /login don't run here: use the terminal command shown above."); }
                await post(`/api/claude/sessions/${cur.id}/send`, { text: t });
              }}
              onStop={() => { post(`/api/claude/sessions/${cur.id}/interrupt`).catch(() => {}); }} />
          ) : (
            <div className="panel-body flex flex-col items-center justify-center gap-3 text-center text-ink/70">
              <p className="glow-orange display text-base">Orchestrator & reviewer</p>
              <p className="max-w-md text-[13px]">Start a Claude Code session. Tool requests (commands, edits) come to your inbox for approval.</p>
              <button className="chip orange px-3 py-1" onClick={() => setCreating(true)}>+ new session</button>
            </div>
          )}
        </div>
      </div>
      </div>
    </section>
  );
}

function Row({ k, v, hot, dot }: { k: string; v: string; hot?: boolean; dot?: boolean }) {
  return (
    <div className="flex justify-between gap-2 border-b border-orange/10 py-0.5">
      <span className="text-mute uppercase tracking-[.16em] text-[10.5px]">{k}</span>
      <span className={`truncate ${dot ? "font-dot text-[17px] leading-none" : ""} ${hot ? "glow-orange" : "text-ink"}`} title={v}>{v}</span>
    </div>
  );
}

function NewSession({ panel, onDone }: { panel?: ClaudePanel; onDone: (id: string | null) => void }) {
  const [cwd, setCwd] = useState(panel?.workspaces[0] ?? "");
  const [model, setModel] = useState("");
  const [title, setTitle] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const create = async () => {
    try {
      const s = await post("/api/claude/sessions", { title: title || null, cwd, model: model || null });
      onDone(s.id);
    } catch (e) { setErr(String((e as Error).message)); }
  };
  const field = "border border-orange/40 bg-void px-2 py-1 text-[12px] text-ink";
  return (
    <div className="flex flex-wrap items-end gap-2 border-b border-orange/25 px-3 py-2 text-[11px] text-mute">
      <label className="flex flex-col gap-0.5">title<input className={field} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="(from first message)" /></label>
      <label className="flex flex-col gap-0.5">folder
        <select className={field} value={cwd} onChange={(e) => setCwd(e.target.value)}>
          {(panel?.workspaces ?? []).map((w) => <option key={w} value={w}>{w}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-0.5">model
        <select className={field} value={model} onChange={(e) => setModel(e.target.value)}>
          {MODELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      <button className="chip orange h-7 px-3" onClick={create}>create</button>
      <button className="chip mute h-7 px-3" onClick={() => onDone(null)}>cancel</button>
      {err && <span className="text-red">{err}</span>}
    </div>
  );
}
