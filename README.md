# Sage OS

`SAGE//OS` (*Semi-Autonomous Agent Ground Environment*) is a personal knowledge hub for people who use
several AIs and keep notes in many places: a "Wikipedia for yourself" built from your own files, which
every AI you talk to reads from, and which grows only with your approval (DECISIONS D22).

**Today (v0.14.0):** a long document (a textbook, a handbook, a long report) can be digested into notes:
the local model reads it section by section, and a coverage map shows that every part was read. Every
proposal opens in a reviewer where you read each note, keep or drop it and edit it before it's filed.
Also: chat with Claude Code, a model running on your own computer (Sage OS installs and
runs llama.cpp itself and rates each model for your hardware), ChatGPT, Gemini or Ollama. Each message
you send carries the notes and documents that match it, shown next to the message in a *Reading* strip
with anything the AI opened itself; ✕ on an item corrects the AI and leaves it out from then on.
Bookshelf holds your notes and a read-only, searchable copy of your documents, Google Docs, Sheets and
Slides included (through the Drive API, read-only). Agents propose notes; nothing is written until you
approve it in the inbox (screened for secrets, undoable byte for byte). Hermes, its kanban board and the
GPU lane remain for those who have them. Windows and macOS; local only. Note sync between devices,
installers and phone access are on the [roadmap](docs/ROADMAP.md).

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

**Needs:** Python 3.12+ and Node 20+. Everything else is optional: the Claude desktop app (for
`claude.exe`), a local model (install the engine and a model from **MODELS**, or point `[engine]` in
`config.local.toml` at an existing `llama-server` and GGUF folder), ChatGPT / Gemini keys in environment
variables (`[[models]]` in `config.toml`), Hermes Agent at `%LOCALAPPDATA%\hermes`.

**Google Docs, Sheets and Slides** (optional): create an OAuth client of type *Desktop app* in Google
Cloud (Drive API enabled, consent screen in testing mode with yourself as a test user), save its JSON as
`data/google-oauth-client.json`, then **Connect Google Drive** in Bookshelf → Sources and press Sync now.

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
| Chat pane | the **Chat** connector: any OpenAI-compatible endpoint (local engine, ChatGPT, Gemini, Ollama) | pick where and which model; the AI uses your notes and documents through Bookshelf tools; **Hermes** tab when Hermes is installed |
| Reading strip | briefing packs (K8, D20) | under each message: what was attached (◆ notes, ▤ documents) and what the AI opened itself (·read); ✕ = wrong or not relevant; 📖 toggles packs per chat |
| Review | an inbox card's **REVIEW** (K13, D24) | each proposed note rendered; keep / drop; edit title, body, tags with a live preview; approve only what you kept |
| Digests | `data/digest.db` (K12, D23) | Bookshelf → Sources → *Digest into notes* on a long document; Bookshelf → **DIGESTS**: a coverage map with one square per section, concepts covered, pause / resume / cancel; one inbox card per chapter |
| Models | `data/engine` | this computer's memory and GPU, the local engine (install, start, stop), a model catalog rated *fits / tight / too big*, models already on disk, connected cloud AIs |
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
