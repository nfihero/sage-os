# Sage OS

`SAGE//OS` (*Semi-Autonomous Agent Ground Environment*) is a hub for running AI agents on your own
machine. Pick local or cloud models, keep conversations and topics from many programs in one place,
run workflows on kanban boards, and grow a knowledge base your agents read and add to, with your
approval.

**Today (v0.11.1):** Claude Code (cloud) and Hermes (local models) run side by side, and any other agent
or OpenAI-compatible model server can plug into the same connector layer. One inbox collects every
approval. Around it: the Hermes kanban board, live GPU and safety status, and Bookshelf, where you
search your notes and a read-only copy of chosen Google Drive folders, and grow the vault from them:
starter notes from your files, concept notes drafted by an agent. Both agents use Bookshelf through
MCP tools; every change lands only after you approve it (screened for secrets, undoable byte for
byte). Batch review, more programs and multiple workflow boards are on the [roadmap](docs/ROADMAP.md).
Windows 11, local only.

| Read | For |
|---|---|
| [docs/MISSION.md](docs/MISSION.md) | Why it exists, pillars, principles, why "Sage" |
| [docs/STATUS.md](docs/STATUS.md) | What works, what's untested, known issues, next |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases and gates; the Bookshelf and architecture tracks |
| [docs/DEMO.md](docs/DEMO.md) | 5–7 minute demo script: prep checklist, walkthrough, fixes |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log: what was decided, why, costs, when to revisit |
| [CHANGELOG.md](CHANGELOG.md) | Version history: one version and tag per roadmap step that passes its gate |
| [docs/SAGE-OS-HANDOFF.md](docs/SAGE-OS-HANDOFF.md) | Context primer for a fresh session: architecture, agent model, knowledge-backend contract, reversed decisions, open questions |
| [Design doc](https://claude.ai/code/artifact/af65a0a6-433a-48c3-b841-33d7aedab899) | Original design (architecture, UI, phases) |

## Run

```
start.cmd
```

Opens http://127.0.0.1:8787 when ready (first run creates `hub\.venv` and builds `ui\dist`). The window
stays open while it runs. UI hot reload: keep the hub running, then `npm run dev` in `ui\` →
http://127.0.0.1:5173.

**Needs:** Hermes Agent installed at `%LOCALAPPDATA%\hermes` (gateway :8642, llama.cpp router :18434,
guardian sidecar :18435), the Claude desktop app (for `claude.exe`), Python 3.12+, Node 20+.

**On a Mac** (D21; for development, the PC stays home base): `./start.sh`. Copy
`config.local.example.toml` to `config.local.toml` (untracked) and set this machine's paths: it overrides
`config.toml`. Without Hermes or an NVIDIA GPU those panels show as down or empty; Claude works if the
`claude` CLI is installed and signed in (`claude auth login`).

**One-time Claude login** (the Agent SDK's CLI needs its own sign-in; `/login` inside a chat won't work):

```
& "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\<newest>\claude.exe" auth login
```

(PowerShell; drop the leading `&` and use `%LOCALAPPDATA%` in Command Prompt. Override the path with
`SAGE_OS_CLAUDE_CLI`.)

## What's on screen

| Area | Source | Notes |
|---|---|---|
| Claude Code pane | Claude Agent SDK, your subscription | session tabs, folder + model per session; tool requests → inbox; usage meter |
| Hermes pane | Hermes gateway sessions API | the profile `default`, labelled "Hermes"; open, continue, start chats |
| Inbox | Claude permissions, Hermes approvals, kanban `needs_input`, Bookshelf proposals | allow once / session / deny + note; reply + unblock; approve & file / reject with a diff per change; held (secret-looking) proposals: reject / save anyway |
| Board | `kanban.db` (read-only) | click a task for runs, comments, history |
| GPU lane | router `/models`, `nvidia-smi`, `psutil` | resident model, VRAM/RAM, guardian sidecar |
| Top bar | health checks, guard logs | service lights (Hermes, Models, Guard), safety chip (red only on new blocks), **? GUIDE** (why + tour), Bookshelf, theme, Motion |
| Bookshelf | `data/vault` (plain markdown), `data/sources/` (read-only copies) | search notes as you type (ranked, highlighted), read by folder, links by uid, format problems named, 🔒 sensitive notes kept out of search; History with exact undo; **Sources**: search and read your Drive copy, Sync now, see what was left out and why; **Build notes**: propose starter notes, ask an agent to draft concept notes; Open vault in Explorer |

New here? **? GUIDE** explains why Sage OS exists and tours the screen (it opens by itself on a first visit;
`?guide` in the URL forces it). Click the `SAGE//OS` logo to replay the boot sequence.

## Layout

```
hub/sage_os_hub/   FastAPI app, WebSocket stream, SQLite store (data/hub.db)
  adapters/        kanban · system (gpu + health) · safety · sessions (read-only pollers)
  connectors/      agents and model servers behind one interface (DECISIONS D4)
    base.py        AgentConnector interface + errors
    claude.py      Claude Code sessions + permission callback → inbox
    hermes.py      each Hermes profile as an agent; hermes_api.py (gateway client, runtime pin),
                   hermes_chat.py (chat relay + approvals → inbox)
    models.py      ModelProvider: any OpenAI-compatible endpoint
  inbox.py         the approvals inbox
  knowledge/       Bookshelf: vault reader + contract checks (D9), FTS5 search index (D10),
                   proposals + single journaled writer with undo (D11), secret screening (D12),
                   agent tools + MCP endpoint (D16), source library (D15), notes from sources (D17)
ui/src/            React + Vite + Tailwind; themes in index.css; orbs in components/Orb.tsx
docs/              mission, status, roadmap, handoff
config.toml        ports, Hermes paths, poll intervals, agents + model servers, Claude workspaces, profile labels
```

## Safety properties

- Binds `127.0.0.1` only; rejects foreign `Host` headers and WebSocket origins. Remote access will go
  through Tailscale Serve (Phase 3), never a public port, and only for host names listed exactly in
  `[hub] remote_hosts` (no wildcards: anyone can publish a page on `*.ts.net`).
- Security headers on every response: a strict Content-Security-Policy (same-origin scripts and
  connections, no remote images, no framing), `X-Frame-Options: DENY`, `nosniff`, no referrer. No
  `/docs` or `/openapi.json`.
- Agent output is untrusted: chat markdown never auto-loads images; note text handed to agents is
  marked as data, not instructions; one agent can have at most 25 Bookshelf proposals waiting.
- Write routes require `X-Sage-OS: 1` plus a local Host and Origin; `hub/tests/test_app.py` checks every
  write route.
- Bookshelf screens agent proposals for secrets before storing anything; only you can *Save anyway*
  (DECISIONS D12).
- The hub never widens what an agent may do: Claude keeps its permission system, Hermes keeps the
  guardian and write guard, guard blocks can't be overridden from the UI.
- Reads Hermes' databases with SQLite `mode=ro` and imports no Hermes code; a startup smoke test
  (`/api/smoke`) names any Hermes surface an update broke.

## Tests

```
hub\.venv\Scripts\python -m pytest hub
cd ui && npm run build
```

## Working on this repo with Claude Code

`.claude/settings.json` runs a **git guardrails** hook (`.claude/hooks/git_guardrails.py`) before
every shell command and file edit in Claude Code sessions opened in this folder. It blocks
`git push`, `reset --hard`, `clean -f`, `branch -D` and discarding all local edits, and it blocks
edits to the guardrails themselves. Push yourself when you want a push.

To remove the guardrails, ask Claude: it runs `git_guardrails.py remove`, which prints exactly what
removal changes and changes nothing. You confirm by running the same command yourself in a terminal
and typing `REMOVE`:

```
hub\.venv\Scripts\python .claude\hooks\git_guardrails.py remove
```

Sessions started in another folder (e.g. a workspace one level up) don't load this project's
settings, so the hook doesn't apply to them (DECISIONS D13).
