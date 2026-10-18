import { useEffect, useMemo, useRef, useState } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Briefing, ChatItem } from "../types";
import { clock } from "../util";
import { briefingFor, ReadingStrip, ReadingToggle, useReading } from "./Reading";

type Tone = "orange" | "cyan";

/** Agent output is untrusted: images never auto-load (a prompt-injected reply could beacon data out
 *  through an image URL), and only http(s) links are clickable, opening in a new tab. */
export const SAFE_MD: Components = {
  img: ({ alt, src }) => <span className="text-mute" title={String(src ?? "")}>[image: {alt || "untitled"}]</span>,
  a: ({ href, children }) => /^https?:\/\//.test(href ?? "")
    ? <a href={href} target="_blank" rel="noreferrer noopener">{children}</a> : <span title={href}>{children}</span>,
};

/** One transcript + composer. Items are the durable history; `live` is the streaming tail. */
export default function ChatView({ items, live, busy, tone, placeholder, onSend, onStop, disabled, banner, chat, suggestions }: {
  items: ChatItem[]; live: string; busy: boolean; tone: Tone; placeholder: string;
  onSend: (text: string) => Promise<void>; onStop?: () => void; disabled?: string | null; banner?: React.ReactNode;
  chat?: string | null;     // pane id: shows the K8 Reading strips and toggle for this chat
  suggestions?: string[];   // U2: first questions to ask, shown while the chat is empty
}) {
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const reading = useReading(chat ?? null);
  const strips = useMemo(() => {     // user item id -> its briefing, matched by text in order
    const out = new Map<ChatItem["id"], Briefing>();
    let after = "";
    for (const it of items) {
      if (it.kind !== "user") continue;
      const b = briefingFor(reading.state?.briefings, String(it.data?.text ?? ""), it.ts, after);
      if (b) { out.set(it.id, b); after = b.id; }
    }
    return out;
  }, [items, reading.state]);

  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [items, live, reading.state]);

  const submit = async () => {
    const t = text.trim();
    if (!t || busy || disabled) return;
    setErr(null);
    try {
      await onSend(t);
      setText("");
      stick.current = true;
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {banner}
      <div ref={scroller} className="panel-body flex flex-col gap-2.5 text-[13.5px] leading-relaxed"
        onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60; }}>
        {items.length === 0 && !live && (suggestions?.length
          ? <div className="m-auto flex max-w-[560px] flex-col items-center gap-2 text-center" data-testid="starters">
              <div className="copy text-[13px] text-mute">Try asking</div>
              {suggestions.map((q) => (
                <button key={q} disabled={busy || !!disabled} onClick={() => { setErr(null); onSend(q).catch((e) => setErr(String((e as Error).message))); }}
                  className="copy w-full border border-cyan/30 px-3 py-2 text-left text-[13.5px] text-ink/90 hover:border-cyan hover:bg-cyan/5">{q}</button>
              ))}
            </div>
          : <div className="m-auto text-mute">No messages yet.</div>)}
        {items.map((it) => (
          <div key={it.id} className="chat-in">
            <Item it={it} tone={tone} />
            {chat && strips.has(it.id) && <ReadingStrip b={strips.get(it.id)!} chat={chat} />}
          </div>
        ))}
        {live && <div className={`md ${tone === "orange" ? "md-orange" : ""}`}><Markdown remarkPlugins={[remarkGfm]} components={SAFE_MD}>{live}</Markdown><span className="caret" /></div>}
        {busy && !live && <div className={`text-[12px] ${tone === "orange" ? "glow-orange" : "glow-cyan"}`}>working<span className="dots" /></div>}
      </div>
      <div className={`border-t p-2 ${tone === "orange" ? "border-orange/30" : "border-cyan/25"}`}>
        {err && <div className="mb-1 text-[12px] text-red">{err}</div>}
        {disabled && <div className="mb-1 text-[12px] text-amber">{disabled}</div>}
        <div className="flex items-end gap-2">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={Math.min(8, Math.max(2, text.split("\n").length))}
            placeholder={placeholder} disabled={!!disabled}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            className={`min-w-0 flex-1 resize-none border bg-void/80 px-2.5 py-2 text-[13.5px] text-ink outline-none placeholder:text-mute
              ${tone === "orange" ? "border-orange/40 focus:border-orange" : "border-cyan/35 focus:border-cyan"}`} />
          {chat && reading.state && <ReadingToggle enabled={reading.state.settings.enabled} onToggle={() => { reading.toggle().catch((e) => setErr(String(e.message))); }} />}
          {busy && onStop ? (
            <button onClick={onStop} className="chip red h-9 px-3">STOP</button>
          ) : (
            <button onClick={submit} disabled={!text.trim() || !!disabled}
              className={`chip h-9 px-3 disabled:opacity-40 ${tone === "orange" ? "orange" : ""}`}>SEND ⏎</button>
          )}
        </div>
      </div>
    </div>
  );
}

function Item({ it, tone }: { it: ChatItem; tone: Tone }) {
  const [open, setOpen] = useState(false);
  const d = it.data ?? {};
  switch (it.kind) {
    case "user":
      return (
        <div className="ml-auto max-w-[85%] border border-ink/15 bg-ink/5 px-3 py-2">
          <div className="whitespace-pre-wrap">{d.text}</div>
          <div className="mt-0.5 text-right text-[11px] text-mute">{clock(it.ts)}</div>
        </div>
      );
    case "text":
      return <div className={`md ${tone === "orange" ? "md-orange" : ""}`}><Markdown remarkPlugins={[remarkGfm]} components={SAFE_MD}>{d.text}</Markdown></div>;
    case "thinking":
      return (
        <button onClick={() => setOpen(!open)} className="text-left text-[12px] text-mute">
          ◇ thinking {open ? "" : "…"}{open && <div className="mt-1 whitespace-pre-wrap">{d.text}</div>}
        </button>
      );
    case "tool_use":
      return (
        <div className="cursor-pointer border-l-2 border-cyan/30 pl-2 text-[12px]" onClick={() => setOpen(!open)}>
          <span className="text-cyan">▸ {d.tool}</span> <span className="font-mono text-ink/70">{String(d.summary ?? "").slice(0, 160)}</span>
          {open && <pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap text-[11.5px] text-ink/60">{JSON.stringify(d.input, null, 2)}</pre>}
        </div>
      );
    case "tool_result":
      return (
        <div className={`cursor-pointer border-l-2 pl-2 text-[12px] ${d.error ? "border-red/60" : "border-cyan/15"}`} onClick={() => setOpen(!open)}>
          <span className={d.error ? "text-red" : "text-mute"}>{d.error ? "✕ error" : "◂ result"}{d.tool ? ` · ${d.tool}` : ""}</span>{" "}
          {!open && <span className="text-mute">{String(d.text ?? "").split("\n")[0].slice(0, 120)}</span>}
          {open && <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap text-[11.5px] text-ink/70">{d.text}</pre>}
        </div>
      );
    case "note":
      if (d.turn_end) return <div className="text-center text-[11px] text-mute">— {d.ms ? `${(d.ms / 1000).toFixed(1)} s` : ""} —</div>;
      return <div className="text-[12px] text-amber">{d.text}</div>;
    case "error":
      return <div className="border border-red/50 bg-red/5 px-2 py-1.5 text-[12.5px] text-red whitespace-pre-wrap">{d.text}</div>;
    default:
      return <div className="text-[12px] text-mute">{it.kind}: {JSON.stringify(d).slice(0, 200)}</div>;
  }
}
