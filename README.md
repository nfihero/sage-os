# Sage OS

`SAGE//OS` — *Semi-Autonomous Agent Ground Environment.* An AI agent hub with a personal, growing
knowledge base: your choice of local and cloud models, conversations and topics from many programs in
one place, kanban boards for your workflows, and a built-in knowledge base that makes your AI agents
your own.

**Today (v0.3.0):** Claude Code (cloud) and Hermes (local models) side by side, one approvals inbox,
the Hermes kanban board, live GPU/safety status. The Bookshelf knowledge base, more programs and
multiple workflow boards are on the [roadmap](docs/ROADMAP.md). Windows 11 · local only.

| Read | For |
|---|---|
| [docs/MISSION.md](docs/MISSION.md) | Why it exists, pillars, principles, why "Sage" |
| [docs/STATUS.md](docs/STATUS.md) | What works, what's untested, known issues, next |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases and gates; the Bookshelf and architecture tracks |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log: what was decided, why, costs, when to revisit |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
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
| Inbox | Claude permissions, Hermes approvals, kanban `needs_input` | allow once / session / deny + note; reply + unblock |
| Board | `kanban.db` (read-only) | click a task for runs, comments, history |
| GPU lane | router `/models`, `nvidia-smi`, `psutil` | resident model, VRAM/RAM, guardian sidecar |
| Top bar | health checks, guard logs | service lights, safety chip (red only on new blocks), Bookshelf, theme, Motion |
| Bookshelf | `data/vault` (plain markdown) | read notes by folder, links by uid, contract problems named; Open vault in Explorer |

Click the `SAGE//OS` logo to replay the boot sequence.

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
  knowledge/       Bookshelf: vault reader + contract checks (DECISIONS D9)
ui/src/            React + Vite + Tailwind; themes in index.css; orbs in components/Orb.tsx
docs/              mission, status, roadmap, handoff
config.toml        ports, Hermes paths, poll intervals, agents + model servers, Claude workspaces, profile labels
```

## Safety properties

- Binds `127.0.0.1` only; rejects foreign `Host` headers and WebSocket origins. Remote access will go
  through Tailscale Serve (Phase 3), never a public port.
- Write routes require `X-Sage-OS: 1` plus a local Host and Origin; `hub/tests/test_app.py` checks every
  write route.
- The hub never widens what an agent may do: Claude keeps its permission system, Hermes keeps the
  guardian and write guard, guard blocks can't be overridden from the UI.
- Reads Hermes' databases with SQLite `mode=ro` and imports no Hermes code; a startup smoke test
  (`/api/smoke`) names any Hermes surface an update broke.

## Tests

```
hub\.venv\Scripts\python -m pytest hub
cd ui && npm run build
```
