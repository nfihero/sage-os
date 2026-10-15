# Sage OS

`SAGE//OS` (*Semi-Autonomous Agent Ground Environment*) is a personal knowledge hub for people who use
several AIs and keep notes in many places: a "Wikipedia for yourself" built from your own files, which
every AI you talk to reads from, and which grows only with your approval (DECISIONS D22).

## Install

**[Download the latest release](https://github.com/nfihero/sage-os/releases/latest)**: pick the file for your computer
under *Assets*. No Python, Node or code needed; the app carries everything it runs.

| Computer | Download | Needs |
|---|---|---|
| Windows | `Sage OS_<version>_x64-setup.exe` | Windows 10 or 11, 64-bit |
| Mac | `Sage OS_<version>_aarch64.dmg` | Apple Silicon (M1 or newer), macOS 11+ |

**Windows**

1. Run the `.exe`. It installs for your user only (no admin password).
2. Windows may say *Windows protected your PC*, because the installer isn't signed with a paid certificate. Click
   **More info → Run anyway**.
3. Open **Sage OS** from the Start menu.

**Mac**

1. Open the `.dmg` and drag **Sage OS** into **Applications**.
2. The first time, macOS may say it can't check the app for malware (it isn't notarized). Open
   **System Settings → Privacy & Security**, scroll down, click **Open Anyway** next to Sage OS, and confirm.
   If it says the app is *damaged*, run this once in Terminal, then open it again:
   ```
   xattr -dr com.apple.quarantine "/Applications/Sage OS.app"
   ```

**First run:** Sage OS starts empty, with a screen that recommends the model that fits your computer: **INSTALL AND
START** downloads it and opens your first chat. Or connect an AI you already use (Claude Code, ChatGPT, Gemini,
Ollama): **[how to connect each one](docs/CONNECT.md)**. A short guide explains the rest (**? GUIDE**). Then:

- **Add your notes and files:** Library → STORAGE and Sources (or drop documents in the Library's `Files` folder).
- **Every chat in one place:** the history on the left of the chat lists every conversation with every AI; the picker
  above a chat hands the next reply to another AI, which reads the conversation so far.
- **What each AI costs:** **$ USAGE** in the top bar shows tokens, spend, plan limits and the price list
  ([details](docs/CONNECT.md#usage-limits-and-costs)).
- **Search by meaning** sets itself up on first start (a small model, 334 MB, downloaded once).

**Something not working?** **REPORT A PROBLEM** in the top bar writes a report you read in full, then opens an email
to send it with. It never includes your notes, documents, chats or keys.

**Updates:** when a new version is out, an amber **UPDATE** chip appears in the top bar. Click it to see what's new,
then **Update and restart**. Updates are signed; anything not signed by this project is refused. Your notes and
settings are kept.

**Closing and quitting:** closing the window keeps Sage OS running in the tray (digests and agents carry on). To stop
it, use **Quit Sage OS** in the tray menu. *Start at sign-in* is in the same menu.

**Uninstall:** Windows: Settings → Apps → Sage OS → Uninstall. Mac: drag Sage OS from Applications to the Trash. Your
data stays (see *Where your data lives* below) until you delete that folder yourself.

## What it does

- **For first-time users (v0.26.0, O0 part one):** a guide in plain words (pick an AI, add your documents, approve what
  it saves), one name for your notes (Library), "AI" instead of "agent" on screen, Hermes lights only once it's
  connected.
- **Report a problem (v0.25.0):** a report you read in full, saved and attached to an email.
- **Connect and costs (v0.24.0):** step-by-step guides to connect each AI; OpenAI and Gemini keys are tested and kept
  in the OS keychain; every reply's tokens and cost, Claude plan limits, API rate limits, and a dated price list you
  can correct.
- **One chat space (v0.23.0):** every AI in one chat with one history: by day, searchable, pinned, archived; switch
  AI mid-chat and the new one carries on.
- **Search by meaning (v0.21.0):** search finds notes and documents by what they mean, not only by their words, using
  a small model on your processor; briefing packs leave out notes that only share words with your question.
- **Review at scale (v0.20.0):** a digested chapter is one inbox card and one decision; tick cards to decide several
  at once; History undoes a whole batch or one note. **AGENTS** (in the inbox) sets each agent's trust (ask first,
  let new notes file themselves, or trusted) and shows a complete log of everything each agent did, at every level.
  The Librarian tidies a folder's notes as one proposal; the Reviewer marks notes it would drop before you read.
- **Long documents:** a textbook, handbook or long report can be digested into notes by the local model, section by
  section, with a coverage map showing every part was read. Every proposal opens in a reviewer where you keep, drop
  or edit each note before it's filed.
- **Any AI, same library:** chat with Claude Code, a model on your own computer (Sage OS runs llama.cpp itself),
  ChatGPT, Gemini or Ollama. Each message carries the notes and documents that match it, shown in a *Reading* strip
  next to it; ✕ on an item corrects the AI and leaves it out from then on.
- **Nothing enters without you:** agents propose notes; nothing is written until you approve it in the inbox
  (screened for secrets, undoable byte for byte). Google Docs, Sheets and Slides can be read through the Drive API
  (read-only). Windows and macOS; local only. Sync between devices and phone access are on the
  [roadmap](docs/ROADMAP.md).

| Read | For |
|---|---|
| [docs/MISSION.md](docs/MISSION.md) | Why it exists, pillars, principles, why "Sage" |
| [docs/STATUS.md](docs/STATUS.md) | What works, what's untested, known issues, next |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases and gates; the Bookshelf, architecture, sync and shared-hardware tracks |
| [docs/DEMO.md](docs/DEMO.md) | 5–7 minute demo script: prep checklist, walkthrough, fixes |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log: what was decided, why, costs, when to revisit |
| [CHANGELOG.md](CHANGELOG.md) | Version history: one version and tag per roadmap step that passes its gate |
| [docs/SAGE-OS-HANDOFF.md](docs/SAGE-OS-HANDOFF.md) | Context primer for a fresh session: architecture, agent model, knowledge-backend contract, reversed decisions, open questions |

## Run from source (developers)

**From a terminal:**

```
start.cmd
```

Opens http://127.0.0.1:8787 when ready (first run creates `hub\.venv` and builds `ui\dist`). The window
stays open while it runs. UI hot reload: keep the hub running, then `npm run dev` in `ui\` →
http://127.0.0.1:5173. A developer build of the desktop app (`npx tauri build` in `desktop\`, needs Rust and the MSVC
build tools) runs this checkout's hub instead of a bundled one.

**Releasing (maintainers):** bump the version in `hub/sage_os_hub/__init__.py`, `hub/pyproject.toml`,
`ui/package.json`, `ui/package-lock.json`, `desktop/package.json`, `desktop/package-lock.json`,
`desktop/src-tauri/Cargo.toml` and `desktop/src-tauri/tauri.conf.json`; add the version's section to CHANGELOG.md;
commit; tag `vX.Y.Z`; push the tag. GitHub Actions builds Windows and Mac, signs the updates (secrets
`TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`) and publishes the release that installed copies
update from (D38).

**Where your data lives** (D25): app data in `%APPDATA%\Sage OS` (Windows) or `~/Library/Application Support/Sage OS`
(Mac): databases, indexes, source copies, models, sign-ins, per computer. Your notes and files are in its
`Library` folder (`Notes/`, `Files/`); point the Library at a OneDrive / iCloud / Dropbox / Syncthing folder in
Library → **STORAGE** to have them on every device. An install from before 0.15 keeps `sage-os\data` until you
stop it and run `hub\.venv\Scripts\python -m sage_os_hub move-data`. Each install has its own device ID and name
(STORAGE → *This device*). The first start of 0.16 moved every record to new IDs once (Y1, D28), after backing up
the databases to `backups\pre-ulid-<time>` in app data.

**Needs:** Python 3.12+ and Node 20+. Everything else is optional: the Claude desktop app (for
`claude.exe`), a local model (install the engine and a model from **MODELS**, or point `[engine]` in
`config.local.toml` at an existing `llama-server` and GGUF folder), ChatGPT / Gemini keys in environment
variables (`[[models]]` in `config.toml`), Hermes Agent at `%LOCALAPPDATA%\hermes`.

**Google Docs, Sheets and Slides** (optional): create an OAuth client of type *Desktop app* in Google
Cloud (Drive API enabled, consent screen in testing mode with yourself as a test user), save its JSON as
`data/google-oauth-client.json`, then **Connect Google Drive** in Library → Sources and press Sync now.

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
| Home (W2) | everything below, arranged library-first | left, the agent's planet with State / Model / Where and GPU meters, agents to switch to or connect; centre, **search** over notes and files (Ctrl K; Enter asks the local model) above the chat; right, inbox, digest progress, recent notes; bottom, a one-line systems strip. **Systems** (top) holds the board, GPU lane and Hermes |
| Claude Code pane | Claude Agent SDK, your subscription | session tabs, folder + model per session; tool requests → inbox; usage meter; shows a "Connect an agent" card until Claude Code is signed in |
| Chat pane | the **Chat** connector: any OpenAI-compatible endpoint (local engine, ChatGPT, Gemini, Ollama) | pick where and which model; the AI uses your notes and documents through Bookshelf tools; **Hermes** tab when Hermes is installed |
| Reading strip | briefing packs (K8, D20) | under each message: what was attached (◆ notes, ▤ documents) and what the AI opened itself (·read); ✕ = wrong or not relevant; 📖 toggles packs per chat |
| Review | an inbox card's **REVIEW** (K13, D24) | each proposed note rendered; keep / drop; edit title, body, tags with a live preview; approve only what you kept |
| Digests | `data/digest.db` (K12, D23) | Library → Sources → *Digest into notes* on a long document; Library → **DIGESTS**: a coverage map with one square per section, concepts covered, pause / resume / cancel; one inbox card per chapter |
| Models | `data/engine` | this computer's memory and GPU, the local engine (install, start, stop), a model catalog rated *fits / tight / too big*, models already on disk, connected cloud AIs |
| Inbox | Claude permissions, Hermes approvals, kanban `needs_input`, Bookshelf proposals, trust suggestions | allow once / session / deny + note; reply + unblock; a chapter is one card (approve all / reject all / review every part); tick cards to decide them together (one batch); held (secret-looking) proposals: reject / save anyway; *Filed for you*; **AI ACTIVITY**: trust levels, roles, Librarian, Reviewer, every AI's activity log |
| Board | `kanban.db` (read-only) | click a task for runs, comments, history |
| GPU lane | Windows GPU counters (any vendor), router `/models`, `psutil` | the Sage OS engine and any router model, VRAM/RAM, guardian sidecar |
| Top bar | health checks, guard logs | service lights (Hermes, Models, Guard; only once Hermes is connected), safety chip (red only on new blocks), $ USAGE, **REPORT A PROBLEM**, **? GUIDE** (how to start + tour), Library, theme, Motion |
| Library (Bookshelf in the code) | `data/vault` (plain markdown), `data/sources/` (read-only copies) | search notes as you type (ranked, highlighted), read by folder, links by uid, format problems named, 🔒 sensitive notes kept out of search; History with exact undo; **Sources**: search and read your Drive copy, Sync now, see what was left out and why; **Build notes**: propose starter notes, ask an agent to draft concept notes; Open folder |

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
