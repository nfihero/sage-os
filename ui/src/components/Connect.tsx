import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { get, post } from "../api";

/** Connect an AI (D40): every way to give Sage OS an AI to talk to, each with its steps, and the form to finish it
 *  (a key pasted here is tested, then kept in the OS keychain; it never comes back to the page). */
export type ConnectSection = "computer" | "claude" | "openai" | "gemini" | "ollama" | "hermes";
type Cloud = { id: "openai" | "gemini"; label: string; key_url: string; billing: string; connected: boolean; key_source: string | null };
type Conns = {
  engine: { installed: boolean; serving: { id: string; ready: boolean } | null };
  claude: { connected: boolean; cli: boolean; logged_in: boolean | null };
  ollama: { connected: boolean }; hermes: { connected: boolean }; cloud: Cloud[];
};

export default function Connect({ focus, onClose, onModels, onUsage }: {
  focus?: ConnectSection | null; onClose: () => void; onModels: () => void; onUsage: () => void;
}) {
  const [c, setC] = useState<Conns | null>(null);
  const [open, setOpen] = useState<ConnectSection>(focus ?? "computer");
  const [err, setErr] = useState<string | null>(null);
  const load = () => get<Conns>("/api/connections").then(setC).catch((e) => setErr(String(e.message)));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  const cloud = (id: string) => c?.cloud.find((x) => x.id === id);
  const state: Record<ConnectSection, string> = {
    computer: c?.engine.serving?.ready ? `running ${c.engine.serving.id}` : c?.engine.installed ? "installed, no model running" : "not set up",
    claude: !c?.claude.connected ? "not connected" : !c.claude.cli ? "Claude Code not installed" : c.claude.logged_in === false ? "sign in needed" : "connected",
    openai: cloud("openai")?.connected ? "connected" : "not connected",
    gemini: cloud("gemini")?.connected ? "connected" : "not connected",
    ollama: c?.ollama.connected ? "found" : "not found",
    hermes: c?.hermes.connected ? "connected" : "not set up (optional)",
  };
  const ok = (s: ConnectSection) => ["connected", "found"].includes(state[s]) || state[s].startsWith("running");
  const items: [ConnectSection, string, string][] = [
    ["computer", "A model on this computer", "private, free, works offline"],
    ["claude", "Claude Code", "your Claude plan; can work in your folders"],
    ["openai", "ChatGPT (OpenAI)", "an API key; paid per use"],
    ["gemini", "Gemini (Google)", "an API key; has a free tier"],
    ["ollama", "Ollama", "if you already run it"],
    ["hermes", "Hermes", "advanced; optional"],
  ];

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-center bg-void/60 p-2 backdrop-blur-sm sm:p-6" onClick={onClose}>
      <div className="panel flex h-full w-full max-w-[1000px] min-w-0 flex-col" onClick={(e) => e.stopPropagation()} data-testid="connect">
        <div className="panel-head">
          <span className="tab">CONNECT AN AI</span>
          <span className="min-w-0 flex-1 truncate normal-case tracking-normal text-mute">every AI you connect shares the same Bookshelf and chat history</span>
          <button className="chip mute" onClick={onUsage}>USAGE & COSTS</button>
          <button onClick={onClose} className="text-mute hover:text-cyan" aria-label="close">✕</button>
        </div>
        {err && <div className="border-b border-red/40 px-3 py-1 text-[12px] text-red">{err}</div>}
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <nav className="flex flex-none flex-col gap-0.5 border-cyan/20 p-2 md:w-[270px] md:border-r max-md:max-h-[38%] max-md:overflow-auto">
            {items.map(([k, name, d]) => (
              <button key={k} onClick={() => setOpen(k)} aria-current={open === k}
                className={`grid grid-cols-[auto_1fr] items-center gap-x-2 border-l-2 px-2 py-1.5 text-left ${open === k ? "border-cyan bg-cyan/10" : "border-transparent hover:bg-cyan/5"}`}>
                <span className={`h-2 w-2 rounded-full ${ok(k) ? "bg-cyan shadow-[0_0_6px_var(--color-cyan)]" : "border border-mute/60"}`} aria-hidden />
                <span className="copy text-[13px] text-ink">{name}</span>
                <span />
                <span className="text-[10.5px] text-mute">{c ? state[k] : "…"} · {d}</span>
              </button>
            ))}
          </nav>
          <section className="panel-body min-w-0 flex-1 px-5 py-4">
            {open === "computer" && <Guide title="A model on this computer" steps={[
              "Open MODELS. Sage OS looks at this computer and marks each model: runs well here, runs but slowly, or too big.",
              "Pick one that runs well here (the biggest of those usually gives the best answers; a first download of 3 to 7 GB is typical) and press install. Sage OS gets llama.cpp, the program that runs it, by itself.",
              "Press start. When it's loaded, pick it in the AI picker above a chat (or start a new chat with it).",
            ]} notes={["Everything stays on this computer and costs nothing per message.",
              "While a game uses the graphics card, game mode pauses the model and offers a small one instead."]}>
              <button className="chip h-8 px-4" onClick={onModels}>OPEN MODELS →</button>
            </Guide>}
            {open === "claude" && <Guide title="Claude Code" steps={[
              "Install Claude Code from claude.com/code (or the Claude desktop app, which includes it).",
              "Sign it in once: open a terminal (the steps are below), paste the sign-in command, press Enter, and finish in the browser with your Claude account (a Pro or Max plan).",
              "Press CONNECT below. New Claude chats ask which folder Claude may work in; it asks before running commands or changing files, and those requests land in your inbox.",
            ]} notes={["Claude Code runs on your Claude plan, not per message: your plan has a 5-hour and a weekly limit, shown in the top bar and under USAGE & COSTS.",
              "USAGE also shows what the same work would cost on the pay-per-use API, so you can see what the plan saves."]}>
              <ClaudeConnect c={c} onDone={load} />
            </Guide>}
            {(open === "openai" || open === "gemini") && cloud(open) && <KeyGuide service={cloud(open)!} onDone={load} onUsage={onUsage} />}
            {open === "ollama" && <Guide title="Ollama" steps={[
              "Install Ollama from ollama.com and pull a model (for example  ollama pull llama3.2 ).",
              "Leave Ollama running. Sage OS finds it on this computer by itself when it starts, or press LOOK AGAIN.",
              "Its models then appear in the AI picker.",
            ]} notes={["Like the built-in models, Ollama runs on this computer and costs nothing per message."]}>
              <button className="chip h-8 px-4" onClick={async () => { await post("/api/providers/find-ollama").catch(() => {}); load(); }}>
                {c?.ollama.connected ? "FOUND ✓" : "LOOK AGAIN"}</button>
            </Guide>}
            {open === "hermes" && <Guide title="Hermes (advanced)" steps={[
              "Hermes is a separate agent framework some people run alongside Sage OS. You don't need it.",
              "If it's installed, add its profile to this computer's config.local.toml under [agents] (hermes = [\"default\"]) and restart Sage OS.",
              "Its chats then appear in your chat history and can be continued here.",
            ]} notes={["Sage OS reads Hermes' board and chats; it never changes Hermes' own settings."]} />}
          </section>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function Guide({ title, steps, notes, children }: { title: string; steps: string[]; notes?: string[]; children?: React.ReactNode }) {
  return (
    <div className="max-w-[640px]">
      <h2 className="display mb-3 mt-0 text-[20px] normal-case tracking-[.06em] text-ink">{title}</h2>
      <ol className="m-0 flex list-none flex-col gap-2.5 p-0">
        {steps.map((s, i) => (
          <li key={i} className="grid grid-cols-[auto_1fr] gap-3">
            <span className="font-dot glow-cyan text-[18px] leading-none">{i + 1}</span>
            <span className="copy text-[14px] leading-relaxed text-ink/85">{s}</span>
          </li>
        ))}
      </ol>
      {children && <div className="mt-4">{children}</div>}
      {notes && <ul className="mt-4 flex list-none flex-col gap-1.5 border-t border-dashed border-cyan/15 p-0 pt-3">
        {notes.map((n, i) => <li key={i} className="copy text-[12.5px] text-ink/70">{n}</li>)}
      </ul>}
    </div>
  );
}

function ClaudeConnect({ c, onDone }: { c: Conns | null; onDone: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  const go = async () => {
    setMsg(null);
    try {
      const r = await post<{ cli: string | null; logged_in: boolean | null }>("/api/agents/claude/connect");
      setMsg(!r.cli ? "Claude Code isn't installed on this computer yet (step 1)." : r.logged_in === false ? "Connected; now sign in (step 2), then press CONNECT again to check." : "Connected. Pick Claude Code in the AI picker.");
      onDone();
    } catch (e) { setMsg(String((e as Error).message)); }
  };
  const done = c?.claude.connected && c.claude.cli && c.claude.logged_in !== false;
  return <div className="flex flex-col gap-3">
    {!done && <SignIn />}
    <div className="flex flex-wrap items-center gap-3">
      <button className="chip h-8 px-4" onClick={go}>{done ? "CONNECTED ✓ · CHECK AGAIN" : "CONNECT"}</button>
      {msg && <span className="copy text-[12.5px] text-amber">{msg}</span>}
    </div>
  </div>;
}

function KeyGuide({ service, onDone, onUsage }: { service: Cloud; onDone: () => void; onUsage: () => void }) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const openai = service.id === "openai";
  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await post<{ models: number }>(`/api/connections/${service.id}`, { key });
      setKey(""); setMsg({ ok: true, text: `Connected: ${r.models} models available. Pick one in the AI picker.` }); onDone();
    } catch (e) { setMsg({ ok: false, text: String((e as Error).message) }); }
    setBusy(false);
  };
  const remove = async () => { await post(`/api/connections/${service.id}/remove`).catch(() => {}); setMsg(null); onDone(); };
  return (
    <Guide title={service.label} steps={openai ? [
      "Sign in at platform.openai.com (this is separate from a ChatGPT Plus subscription).",
      "Add a payment method or some credit under Settings → Billing; the API is paid per use.",
      "Open API keys, create a new secret key, and copy it (it's shown once).",
      "Paste it below and press CONNECT. Sage OS tests it, then keeps it in this computer's keychain.",
    ] : [
      "Sign in at aistudio.google.com with a Google account.",
      "Press Get API key, then Create API key, and copy it.",
      "Paste it below and press CONNECT. Sage OS tests it, then keeps it in this computer's keychain.",
    ]} notes={[service.billing, "Each reply's tokens and cost appear in its chat and under USAGE & COSTS, priced from the provider's own price list (dated; you can correct any price).",
      "The key is stored by your operating system (Windows Credential Manager or the macOS Keychain), never in a file, and is never shown again here."]}>
      <div className="flex flex-col gap-2">
        <a className="copy text-[13px] text-cyan underline" href={service.key_url} target="_blank" rel="noreferrer noopener">Get a key: {service.key_url.replace("https://", "")} ↗</a>
        {service.connected && service.key_source !== "keychain"
          ? <p className="copy text-[12.5px] text-ink/80">Connected through this computer's config ({service.key_source}).</p>
          : service.connected
            ? <div className="flex flex-wrap items-center gap-2"><span className="chip">CONNECTED ✓</span>
                <button className="chip mute" onClick={remove}>DISCONNECT</button><button className="chip mute" onClick={onUsage}>USAGE & COSTS</button></div>
            : <div className="flex flex-wrap gap-2">
                <input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={`paste your ${openai ? "OpenAI" : "Google AI"} key`}
                  aria-label="API key" autoComplete="off" spellCheck={false}
                  className="min-w-[260px] flex-1 border border-cyan/35 bg-void/80 px-2 py-1.5 font-mono text-[12.5px] text-ink outline-none focus:border-cyan" />
                <button className="chip h-8 px-4" disabled={busy || key.trim().length < 20} onClick={save}>{busy ? "TESTING…" : "CONNECT"}</button>
              </div>}
        {msg && <p className={`copy m-0 text-[12.5px] ${msg.ok ? "text-cyan" : "text-amber"}`}>{msg.text}</p>}
      </div>
    </Guide>
  );
}

/** The one terminal step on the main path (O0): the exact command, a COPY button, and how to open a terminal. */
function SignIn() {
  const cmd = "claude auth login";
  const [copied, setCopied] = useState(false);
  const mac = /Mac/i.test(navigator.platform || navigator.userAgent);
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* select it by hand */ }
  };
  return (
    <div className="flex max-w-[560px] flex-col gap-2 border border-dashed border-cyan/30 p-3">
      <div className="copy text-[13px] text-ink">The sign-in command</div>
      <div className="flex items-center gap-2">
        <code className="flex-1 select-all border border-cyan/30 bg-void/80 px-2 py-1 font-mono text-[13px] text-cyan">{cmd}</code>
        <button className="chip h-8 px-3" onClick={copy}>{copied ? "COPIED ✓" : "COPY"}</button>
      </div>
      <p className="copy m-0 text-[12.5px] text-ink/75">{mac
        ? "To open a terminal: press Command and Space, type Terminal, and press Return. Paste the command (Command V), press Return, and follow the browser."
        : "To open a terminal: press the Windows key, type Terminal, and press Enter. Paste the command (right-click, or Ctrl V), press Enter, and follow the browser."}</p>
    </div>
  );
}
