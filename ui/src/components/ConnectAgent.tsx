import type { ClaudePanel } from "../types";

/** An agent slot that isn't connected yet (D22.1): an empty card that says how to connect it, instead of a chat
 *  pane full of sign-in errors. Becomes the real pane by itself once the agent is connected. */
export default function ConnectAgent({ panel, onModels, onPeek }: { panel?: ClaudePanel; onModels: () => void; onPeek?: () => void }) {
  const step = !panel
    ? <p>Claude Code is turned off in <code>config.toml</code> (<code>[agents] claude = true</code> turns it on).</p>
    : !panel.cli
      ? <p>Install Claude Code (it comes with the Claude desktop app), then restart Sage OS. Sage OS finds it on its own.</p>
      : <>
          <p>Claude Code is installed but not signed in for Sage OS. Open a normal terminal (Command Prompt or PowerShell) and run:</p>
          <code className="mt-1 block select-all break-all bg-void/80 px-2 py-1 text-ink">&amp; "{panel.cli}" auth login</code>
          <p className="text-mute">Leave out the leading <code>&amp;</code> in Command Prompt. This card turns into Claude's pane within about 15 seconds of signing in.</p>
        </>;
  return (
    <section className="panel min-h-0" data-testid="connect-agent">
      <div className="panel-head"><span className="tab">Lead agent</span><span className="normal-case tracking-normal text-mute">not connected</span></div>
      <div className="panel-body flex items-center justify-center">
        <div className="flex max-w-[560px] gap-4 border border-dashed border-mute/50 p-5">
          <div className="grid h-14 w-14 flex-none place-items-center rounded-full border border-dashed border-mute/60 text-[24px] text-mute" aria-hidden>+</div>
          <div className="min-w-0">
            <h3 className="display text-[15px] text-mute">Connect an agent</h3>
            <p>An agent works through tasks on its own: plans, edits files, asks you before anything risky. Sage OS works without one;
              the local model in the Chat pane answers from your notes either way.</p>
            <div className="mt-3 text-orange/90">Claude Code</div>
            {step}
            <div className="mt-3 flex flex-wrap gap-1.5">
              <button className="chip" onClick={onModels}>CONNECT ANOTHER AI (MODELS)</button>
              {panel && panel.sessions.length > 0 && onPeek && <button className="chip mute" onClick={onPeek}>SEE PAST CLAUDE SESSIONS</button>}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
