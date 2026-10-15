# Sage OS — handoff for a fresh session

Context primer so a new session can hold **Sage OS** and **BookShelf** (`nfihero/BookShelf`) in mind at
once. Written 30 Sep 2026 from the code, the running system and the build, not from memory; each
section says what was checked. Read with `docs/STATUS.md` (built / broken / next) and
`docs/ROADMAP.md` (phases). BookShelf's own primer is `docs/HANDOFF.md` in its repo, read for this
document (its §6 already sketches the integration from BookShelf's side).

**Update 30 Sep 2026 (later):** BookShelf is retired as a project; its idea is rebuilt inside Sage OS.
Decisions made after this primer was written live in **`docs/DECISIONS.md`** (D1–D5) and override
anything here that conflicts.

Legend: **works** = exercised end to end · **untested live** = code exists, never run against the real
system · **planned** = not built.

---

## 0. Start here (handoff of 9 Oct 2026, v0.15.1; patched 12 Oct, v0.22.0)

Sections 1–9 below are the 30 Sep primer, patched since; where they conflict with this section or
`DECISIONS.md` (D1–D39), those win. Read in this order: this §0, then **D22** (what the product is), **D25**
(where data lives), **D27** (the sync architecture), then `STATUS.md` and the newest `CHANGELOG.md` entries.

### What Sage OS is now (D22)
A shippable app for anyone who uses several AIs and has scattered notes: a "Wikipedia for yourself" built
from your own files, which every AI you use reads from, and which grows only with your approval. Windows and
macOS; nothing may assume this PC (no Hermes, GPU, drive letter or terminal required). Any model can be the
lead or reviewer (D26).

### Where things are
- **Code:** `C:\Users\you\sage-os`, GitHub `nfihero/sage-os` (private). **Version 0.26.0** (tags through 0.26.0; docs-only changes stay under Unreleased, because a tag triggers a release build; the user pushes; v0.4.0–v0.15.1
  pushed 9 Oct at the user's request). Checked 11 Oct: `pytest` 264/264, `npm run build` clean, smoke 18/18.
- **Data (D25):** `C:\Users\you\AppData\Roaming\Sage OS` = app data (databases, indexes, source copies, engine,
  Google client + token). The **Library** = `...\Sage OS\Library\Notes` (the vault, 56 approved notes) and
  `...\Library\Files` (empty so far). The Library is not in a synced folder yet. The old `sage-os\data` is
  kept as `sage-os\data.moved-20261009-014252` (git-ignored) until the user OKs deleting it.
- **This PC's config:** `config.toml` (shared) + `config.local.toml` (untracked: the engine uses Hermes' CUDA
  llama.cpp build `...\hermes\tools\llamacpp-cuda-10964-win32-x64\llama-server.exe` and its models folder).
- **Sources:** `drive` = Drive for desktop `G:\` folders (545 files incl. Deal Club, 10 Google Docs via the API);
  `gdrive` = `My Drive/School` read straight through the Drive API (the Kieso textbook); `library` = Library/Files,
  indexed in place. Google is connected read-only as the owner's Google account.

### Built, by version (details in CHANGELOG)
- 0.12: K8 briefing packs + Reading strip; own llama.cpp engine + model catalog; Chat connector for any
  OpenAI-compatible AI; Google Drive connector; security pass (engine key per start, no web UI, no CORS).
- 0.13: K12 digest long documents section by section with a coverage map (D23).
- 0.14: K13 review proposals note by note: read rendered, keep/drop, edit, file only what's kept (D24).
- 0.15: D25 storage (app data + Library + STORAGE tab: open folders, export zip, move Library, sync conflicts);
  Drive folders through the API; textbook fixes (year rows vs Aadhaar screening, faulty bookmarks).
- 0.17: **G1** game mode (D29; real-game check pending). 0.18: **W1** Tauri desktop app (D33) + UI pass (D34).
  0.19: **W2** library-first home around the planet card (D35); digest resend bug fixed (Chapter 7 duplicates undone).
  The incumbent phosphor world stays: a SAGE-console replacement was rejected (PRODUCT.md, `.impeccable/surfaces/`).
- 0.16: **Y1** sync-ready data (D28, D31): ULIDs, change log via TEMP triggers, tombstones, device identity
  (`dv_01M4PBTTHBWWK32YSMX4NPWRJ7`, "DESKTOP-4JPBI6U"), manifest; real data migrated 11 Oct (backup and old to
  new ID map in `%APPDATA%\Sage OS\backups\pre-ulid-20261011-141542-5F7XHK`). Nothing sends logs between
  devices yet (Y3–Y4).

### Running right now (check before restarting anything)
- **The desktop app** (installed 11 Oct at `%LOCALAPPDATA%\Sage OS\sage-os.exe`, Start menu "Sage OS") runs the hub
  on http://127.0.0.1:8787 as its child, logging to `%APPDATA%\Sage OS\logs\hub.log` (+ `hub-console.log`). Its
  Quit (tray) stops the hub cleanly. Without the app: start the hub detached via WMI (`hub\.venv\Scripts\python.exe
  -m sage_os_hub --log <file>`, cwd `sage-os`); a running hub is adopted by the app. Build the app: `desktop\`,
  `npx tauri build` (needs Rust + MSVC build tools, installed 11 Oct). `sage-os\data-y1check\` (git-ignored) holds
  the copy used to check the Y1 migration and the G1 stand-in scripts; delete with the user's OK.
- **Engine** started and stopped by the user (MODELS) or game mode. When running it serves Gemma 4
  12B (`file:gemma-4-12b-it-qat-q4_0`) on 127.0.0.1:8790, two 16K slots, ~10.7 GB VRAM. A hub restart stops it (it's reaped and must be started again: MODELS → START, or
  `POST /api/engine/start {"model": "file:gemma-4-12b-it-qat-q4_0"}` with header `X-Sage-OS: 1`).
- **Digest `dg_01M4FT8XM5VHAMWA7DC4DC6H72`** (`dg_7cbf09dbad` before 0.16): Kieso *Intermediate Accounting* 18e (1,588 pages), 777 sections / 45 chapters,
  ~35 s per section on the GPU. On 10 Oct: all 777 sections drafted (2,741 notes, 4,987/4,987 concepts),
  On 11 Oct (0.20) chapters up to 18 are in the inbox as 25 chapter cards; the rest go out as cards are decided.
  The limit is 25 waiting *cards* (MAX_PENDING_PER_AGENT); a chapter's later parts join its card.
  Its folder name is the long file stem (later digests get readable titles).

### Next (order agreed 11 Oct, D30, D32)
1. ~~K7~~ built (0.20.0, D36): one card and one decision per chapter, ticked cards decided together, undo of one note,
   trust ladder per agent with a complete activity log (AGENTS in the inbox), the Librarian and the Reviewer. Live
   gate still to run: Librarian on `Books`, 20 notes, with the engine on, approved in one decision. ~~K14~~ done
   (0.21.0, D37): meaning-based search on the CPU, gate passed on the owner's notes. F1 part one done (0.22.0, D38):
   self-contained app + signed updates from `vX.Y.Z` tags via GitHub Actions (Windows + Mac). **To release:** bump the
   eight version strings, add the CHANGELOG section, commit, tag, push the tag. ~~W3~~ one chat space done (0.23.0, D39). ~~D40~~ connect guides, keys in the
   OS keychain, tokens / cost / limits / price list done (0.24.0; user guide `docs/CONNECT.md`; refresh
   `hub/sage_os_hub/pricing.json` from the providers' price pages each release). ~~F1~~ built (0.25.0): Report a problem, and a first-run self-check
   (`--self-check`) in the release workflow on macOS and Windows; the owner's Mac run follows docs/MAC-FIRST-RUN.md.
   O0 part one done (0.26.0); **Next:** the rest of O0 per docs/O0-AUDIT.md (items 5–12; adding documents
   from the app first). D41 (first demo, 14 Oct): assume users have
   never used an agent; proposed O0, J1, M1, M2, O1 (ROADMAP track *From the first demo*), order to be decided with the user.
2. ~~Y1~~ done (0.16.0). The user wants to try sync on their own MacBook: nothing carries logs between devices
   yet; "sync by file" (export / import changes in STORAGE) was offered on 11 Oct, no answer yet. The friend's
   laptop is F1 (D32): her own empty install, not a sync of the user's data.
3. ~~G1~~ (built, 0.17.0; real-game check pending) → ~~W1, W2~~ (0.18, 0.19) → ~~K7~~ (0.20) → ~~K14~~ (0.21) → **F1** meaning-based search → **F1** friend's Mac build
   (D32: .dmg from GitHub Actions, empty first run, keys in the app, *Report a problem* by email to roundederror@gmail.com) → **A3** own task board →
   **Y2 keychain** for secrets + API keys entered in the app (today: env vars, plain token file).
4. Then the account + E2EE sync service (Y3–Y5), phone app and installers (Y6); S2 OCR (D19); K9; K11; Phases 4–6
   with any-model lead (D26). K10 (git-backed vault) is dropped (D30).

### Waiting on the user
- **Claude Code sign-in for Sage OS** still reads as signed out (9 Oct): `claude auth login` in a normal
  terminal, using the CLI the hub found (`C:\Users\you\.local\bin\claude.EXE`).
- **Delete** `sage-os\data.moved-20261009-014252` (362 MB) once happy, and the stale virtualized copy at
  `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Sage OS` (see gotchas).
- **Inbox cards**: the front-matter cards. **Move the Library** to a synced folder when ready (STORAGE).
- **Game mode real-game check** (G1 gate): play a game, choose "Keep working" once (downloads Gemma 4 E2B, 2.6 GB).
- **Which agent tool sets** models get first (Library, Digest, Tasks, Web) was asked 11 Oct, unanswered.
- **Delete** `sage-os\data-y1check\` (copies of the databases used to check Y1, stand-in game scripts).
- **Impeccable update** to 4.5.2 offered (runs `npx impeccable update`), unanswered.
- Older, still open: guardrails hook on macOS (D13: show the diff, get an explicit OK); delete the stale alias
  scripts `swift.bat` / `coder.bat` / `guardian.bat`; spending categories for kanban `t_549737c1`; pricing,
  accounts and installers follow D27 but aren't decided.

### How the user wants work done
- **Every pass:** update all docs (README, STATUS, ROADMAP, MISSION, this file, CHANGELOG), record choices in
  `DECISIONS.md` as new entries (never rewrite history), give each roadmap step its own minor version +
  CHANGELOG entry + local tag; docs-only = patch version. Version strings live in `hub/sage_os_hub/__init__.py`,
  `hub/pyproject.toml`, `ui/package.json`, `ui/package-lock.json` (×2 for sage-os-ui), and for the desktop app
  `desktop/package.json`, `desktop/src-tauri/Cargo.toml`, `desktop/src-tauri/tauri.conf.json` (rebuild the installer).
- **After building:** `/code-review high --fix`; `no-ai-slop` on user-facing copy; `vibe-security` when auth,
  network exposure, secrets or agent input change. Verify UI in the browser pane at 1440×900 and 375×812.
- **Commit when it makes sense; push only when the user says "push".** Ask before destructive or persistent
  system changes (Hermes config, deleting files, models). Never handle the user's credentials (they place
  OAuth files themselves); `G:\` is read-only; `data-private/` and `data*/` never committed.
- Plain-language explanations, recommendations over surveys; asks before big direction changes. The user
  often follows along from the phone (Remote Control) and leaves long jobs running.

### Gotchas (save time)
- **Never write app data from the tool shell.** The shell runs inside the Claude desktop app (MSIX), so writes
  under `%APPDATA%` land in `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\...`, invisible to the hub,
  which runs outside the container (started via WMI). Reading app data from the shell may also show that stale
  copy. To act on app data, go through the hub's API, or run the command via WMI (`Invoke-CimMethod
  Win32_Process Create`), as the 9 Oct move did with robocopy.
- Long-lived processes: start detached with `Invoke-CimMethod Win32_Process Create`; kill the hub by matching
  `sage_os_hub` in the command line. A killed hub leaves llama-server running; the next start reaps it.
- Tests: `tests/conftest.py` gives every test its own app data and `config.local.toml`. Keep it: a storage test
  once wrote the real `config.local.toml`.
- PowerShell 5: no `??`, no `&&`; `Set-Content -Encoding utf8` writes a BOM (the config loader now accepts it);
  multi-line `.Replace()` on files with CRLF misses (normalize `\r\n` first or use the Edit tool); commit
  messages with quotes: write them to a file and `git commit -F`.
- pypdf floods stderr with fontTools warnings on big PDFs: redirect stderr.
- `knowledge/__init__.py` re-exports `screen` the function: import the module via `sys.modules`.
- Panels use `backdrop-filter`, so `position: fixed` inside a panel is relative to the panel: render overlays
  with `createPortal(…, document.body)`. Tailwind's `md:hidden` loses to `.chip`'s display: wrap the chip.
- FastAPI `TestClient`: one context per app. After a UI rebuild the browser may need one Ctrl+F5.
- Hermes caches an MCP server's tool list at first connect (toggle `mcp_servers.bookshelf.enabled`); never use
  the Hermes API key from `.env` in diagnostics.

---

## 1. What Sage OS is

- **One local workspace in a browser tab** where the owner (one person, a finance + AI student) talks to
  **Claude Code** (cloud, his subscription) and **Hermes** (a local agent on his RTX 5070 Ti) side by
  side, watches their work, and approves anything risky from a single inbox.
- **Problem it solves:** the agents' state was scattered across Hermes Desktop chats, terminals, a
  kanban CLI and log files; nothing showed what the GPU was doing or what was blocked on him.
- **Division of labour (design intent):** Claude plans and reviews; local agents do the volume for free;
  the human approves what matters. Phase 2 (today) gives chat + approvals; Claude *orchestrating*
  Hermes is Phase 4 (planned).
- **Users:** one today. Not multi-user, not hosted. Name rationale: `docs/MISSION.md`.
- **Public framing (GitHub description, 30 Sep 2026):** "an AI agent hub with a personal, growing
  knowledge base" — choice of local and cloud models, conversations from many programs in one hub,
  kanban boards per workflow, a built-in knowledge base. Most of that is roadmap (see §2 and
  `docs/ROADMAP.md`, hub-breadth track H1–H4); don't read the description as current capability.
- **Product direction (user, 30 Sep 2026):** fold **BookShelf's idea** — an approval-gated personal
  knowledge base kept as plain markdown — **into Sage OS as a built-in module ("Bookshelf")**, and treat
  Sage OS as a **potential full product**, not only a personal dashboard. The Swift code is not reused;
  the module is rebuilt in Sage OS's stack (§5). Pillars: agent hub · approvals inbox and safety ·
  Bookshelf knowledge base. See `docs/MISSION.md` and `docs/ROADMAP.md`.

## 2. Current state (checked 30 Sep 2026)

| Area | State | How checked |
|---|---|---|
| Hub (FastAPI) + UI (React) | **works**, v0.11.0 (3 Oct; guide + tour D18, portable D21) | `pytest` 170/170 pass; `npm run build` clean (tsc + vite); hub running, `/api/smoke` 18/18 |
| Connectors (A1): agents + model servers behind one interface | **works** | A1 gate 30 Sep: Claude chat + inbox deny, Hermes 2 turns through the connectors |
| Live dashboard: board, GPU/RAM lane, service health, safety feed, sessions | **works** | Phase 1 gates (README history): task visible 4.8 s after CLI create, model swap 0.3 s, guard block 0.3 s, router down/up detected |
| Claude Code pane (Agent SDK, subscription login) | **works** | Phase 2 gate: `Write` request → inbox card → *Allow once* → file written; *Deny + note* → no write, note reached Claude verbatim |
| Hermes chat pane (gateway sessions API) | **works** incl. multi-turn | 3-turn test today, turns 2–3 in 0.9 s (needs the hub's runtime pin, §7 #9) |
| Inbox: Claude permissions | **works** | gate above |
| Inbox: Bookshelf proposals → single writer → undo | **works** (K3) | K3 gate 1 Oct on a scratch vault: nothing written before approval; undo byte-exact (vault SHA-256 identical) |
| Secret screening + *Save anyway* (K4) | **works** | K4 gate 1 Oct: fake key held, found nowhere on disk; override rejected once, saved once (D12) |
| Inbox: Hermes `approval.request` | **untested live** | code maps it (`hermes_chat.py`); no Hermes run has raised one through Sage OS yet |
| Inbox: kanban `needs_input` → reply + unblock | **untested live** | card appears for blocked task `t_549737c1`; reply path (`hermes kanban comment` + `unblock`) never clicked |
| Subscription usage meter | **works, limited** | CLI sends `rate_limit_event`; it omits `utilization` until near a limit, so UI shows "OK + reset time" |
| Visuals (phosphor theme, WebGL agent orbs, handoff arcs, boot screen, screen texture) | **works** | screenshots; orbs/arcs verified by event checks |
| Cross-device (Tailscale), app login | **planned** (Phase 3b: PC home base, passkeys, D21); hub portable to macOS (3a) | — |
| Claude orchestrating Hermes (fleet MCP tools) | **planned** (Phase 4) | — |
| Claude reviewing worker output | **planned** (Phase 5) | — |
| Knowledge layer of its own | **Bookshelf (2 Oct): read, search, approved writes + exact undo, screening, agent tools (K1–K5), Drive source library (S1), notes built from sources (K6)** | gates in `docs/STATUS.md`; D9–D12, D15–D17 |
| Git | first commit made with this doc; private remote `nfihero/sage-os` added later the same day (push only on request); no CI | `git log` before: "no commits yet" |

## 3. Architecture and stack

```
browser (127.0.0.1:8787) ──WS /ws + REST──► hub (FastAPI, Python 3.14)
                                               ├─ adapters (poll, read-only): kanban.db · state.db · router /models
                                               │   · nvidia-smi/psutil · guardian + write-guard logs
                                               ├─ ClaudeConnector ► Claude Agent SDK ──► claude.exe (Desktop app's) ──► Anthropic
                                               ├─ HermesConnector ► Hermes gateway :8642 (sessions API, SSE)   [connectors/, A1]
                                               ├─ hermes CLI ─────► kanban comment / unblock (writes)
                                               └─ Inbox (in memory) · Store (SQLite data/hub.db)
Hermes (separate install, %LOCALAPPDATA%\hermes): gateway :8642 → llama.cpp router :18434 (1 model on GPU)
                                               guardian sidecar :18435 (granite-guardian 8B, CPU)
```

| Layer | Detail (versions checked with `pip list` / `package-lock.json` / `--version`) |
|---|---|
| Hub | Python 3.14.7 · FastAPI 0.142.1 · uvicorn 0.54 · websockets 17.1 · httpx 0.28 · psutil 7.2 · claude-agent-sdk 0.2.162 |
| UI | React 19.3 · Vite 7.3 · Tailwind 4.3 · TypeScript 5.9 · three 0.186 + @react-three/fiber 9.8 (orbs, lazy-loaded) · fonts Rajdhani / JetBrains Mono / Doto |
| Runtime | Node 24.14, npm 11.11 (build only); Windows 11 Education 26200; RTX 5070 Ti 16 GB (driver 616.92); 31 GB RAM |
| Run | `start.cmd` → creates `hub\.venv` + builds `ui\dist` on first run → `python -m sage_os_hub` serves API + UI on **127.0.0.1:8787 only** (refuses other hosts) |
| State | `data/hub.db` (events, panels, Claude sessions + transcripts) · Hermes owns its own state (`kanban.db`, `state.db`) · UI prefs in `localStorage` |
| Config | `config.toml` (ports, Hermes paths, poll intervals, Claude workspaces, profile labels) |
| Deploy | none — local process started by the user; not a service, not containerised |
| Hermes | Hermes Agent 0.21.5 (`hermes-agent` commit `ec5f441`, 29 Sep) · llama.cpp CUDA build 10964 · models: Qwen3.6-35B-A3B (default), Gemma 4 26B-A4B, Qwen3.8-27B ×2, Gemma 4 12B, granite-guardian 8B |

## 4. The agent model

| | Claude Code | Hermes |
|---|---|---|
| Defined by | Agent SDK options in `connectors/claude.py` (Claude Code preset system prompt + Sage OS append) | Hermes profile **`default`** (only profile): `config.yaml`, `SOUL.md`, skills, memories |
| Model | user's subscription; per-session model pick (default/Opus/Sonnet/Haiku) | local; default Qwen3.6-35B-A3B; one model resident (`models_max: 1`) |
| Invoked | Claude pane → `POST /api/claude/sessions/{id}/send` → `ClaudeSDKClient` | Hermes pane → gateway sessions API (SSE); kanban dispatcher spawns workers; Hermes Desktop; cron |
| Tools | Claude Code's built-ins + Bookshelf MCP tools (in-process, pre-allowed); `setting_sources` user+project+local; `AskUserQuestion` disabled | Hermes toolsets (terminal **local** backend, file tools, kanban, browser …) + Bookshelf over MCP (`mcp_servers.bookshelf` → `/mcp/hermes/default/`) |
| Permissions | Claude Code `default` mode; anything not pre-allowed → `can_use_tool` → **Sage OS inbox** (allow once / for session / deny + note) | `pre_tool_call` hooks: **write guard** (Drive `G:\` read-only, protected dirs, writes only under 5 roots) + **guardian** (granite screens every terminal command, fail-closed); Hermes approvals |
| Isolation | cwd chosen from 4 configured folders; **not sandboxed** (filesystem/network as the user, behind prompts) | **not sandboxed** (Docker retired 19–21 Sep); hooks are the boundary |
| Concurrency | one turn per session; several sessions can run at once (no global cap) | one run per chat pane; kanban `max_in_progress: 1`; all local turns serialise on one GPU model |
| Output to user | streamed into the Claude pane; transcript in `hub.db`; usage meter | streamed into Hermes pane; transcript in Hermes `state.db`; board + Activity feed; Desktop |
| Identity | Sage OS session id `cs_…` + Claude `session_id` | profile `default` + session id (`api_…`, `2026…`) ; kanban task/run ids |

Rough activity, for sizing (from logs/DBs): ~800 guardian-screened terminal commands 13–29 Sep; the
retired `sage` profile had 57 sessions in 12 days (chats of 70–125 messages; 42 kanban worker runs).

## 5. What Sage OS needs from a knowledge backend (integration contract)

Framing after the 30 Sep direction: this is the contract for the **Bookshelf module inside Sage OS**
(rebuilt, not the Swift app). It is still written as a contract so the module's boundary stays clean —
agents should reach it only through these surfaces, never through its files directly for writes.

| Question | Answer from the Sage OS side |
|---|---|
| Query/search or read-by-path? | **Search is required.** Agents today find notes by `grep`/`find` in the terminal (every call guardian-screened, ~1–1.5 s overhead each). Read-by-path alone would not replace that. BookShelf having no search (its B1) was the gating gap — **closed by K2** (FTS5 keyword search, v0.5.0); meaning-based search still open (D10). |
| Do agents write knowledge? | **Yes.** Observed: Hermes acted as an Obsidian "librarian" (reorganised notes, created topic notes, added cross-links), daily runs created/updated 3–5 notes each, outlines like `SAGE-OUTLINE.md`. |
| Per-write approval: fits or breaks? | **Fits for chat-driven writes** (Sage OS already has an inbox designed for approvals). **Breaks for background/kanban bulk writes** (a single librarian run touched dozens of files) unless batches can be approved as one unit or trust is per agent. **K3 (v0.6.0):** one proposal of up to 50 changes is approved and undone as one unit; approving many proposals at once and per-agent trust are K7. |
| Transport | **MCP** — built in K5 (D16): in-process for Claude, Streamable HTTP for Hermes. **HTTP/WS** for the Sage OS hub to list/approve proposals in its inbox. **Direct filesystem reads** acceptable. |
| Volume | *Estimate from history, not measured:* per agent session 5–50 reads, 0–10 proposed writes; background librarian/daily runs 20–50 proposed writes in a burst. |
| Latency / real-time | Reads < ~300 ms are fine (a local LLM turn is 1–30 s). Writes are async (approval). Only "real-time" need: a new proposal should reach the Sage OS inbox within ~5 s (current board poll interval). |
| Identity / auth | No user auth today (localhost only; Phase 3 adds Tailscale + passkey or token, undecided). Agents **are** distinguishable: `claude:<session>`, `hermes:default:<session>`, `kanban:<task>/<run>` — usable as BookShelf's proposed `origin: agent` + agent id. Who owns auth between the two projects: unknown — needs confirmation from the user. |
| Local-only? | **Local-only by principle.** No hosted component. Phase 3 reaches the same PC over a private tailnet. |
| Implementation language | **User direction (30 Sep 2026): don't reuse BookShelf's Swift; rebuild the knowledge core in Sage OS's own stack.** Proposed: **Python**, matching the hub — runs natively on this Windows PC, stdlib SQLite FTS5 gives search (BookShelf's B1) for free, official MCP Python SDK, shares the hub's venv/tests. BookShelf becomes the *spec* (DESIGN.md, invariants I1–I9, vault format), not the code. Final choice of language and of repo (inside `sage-os` vs separate) — needs confirmation from the user. |
| Carrying BookShelf's invariants into Python | I1 (no write without approval) is **type-enforced in Swift** (`ApprovedChange.init` is `internal`); Python has no access control, so enforce it by **process boundary**: agents get only an MCP server with read + `propose_*` tools; the single writer process applies a change only with an approval token minted by the review path (Sage OS inbox). I2 journal → SQLite table with before/after blobs (also fixes BookShelf's single-writer JSON journal). I4 screening and I8 uid links port directly. I5 (core imports no UI framework) holds naturally. |
| Existing knowledge stores | `C:\Users\you\Obsidian Vault` (8 topic folders: Inbox, Career, Finance, AI_Technology, Skills, Projects, Companies, Daily), `C:\Users\you\llm-vault` (Zettelkasten-style: 00-inbox … 90-system; origin unknown — needs confirmation from the user), Hermes memories/skills, Google Drive `G:\` (read-only; chosen folders copied and indexed as the `drive` source since 1 Oct, D15). |

## 6. Environment constraints (cost a fresh session time otherwise)

| Constraint | Consequence |
|---|---|
| **Windows 11, not macOS.** No Swift toolchain on this PC (verified: `swift` resolves to `~\.local\bin\swift.bat`, a stale alias for a deleted Hermes profile that runs `hermes -p swift`). | BookShelf's app cannot run here; WikiCore has never been built on Windows. |
| Claude Desktop is the **Store (MSIX) build**: `%APPDATA%\Claude\…` is virtualised for processes inside it. | `claude.exe` from a normal terminal is at `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\<ver>\claude.exe`; the hub's `find_cli()` searches both. |
| Agent-SDK `claude.exe` needs its own login: `"<path>\claude.exe" auth login` in a normal terminal (`/login` inside the SDK fails). In PowerShell prefix `&`. | Hub polls `auth status` and shows a banner until signed in. |
| Processes started from Claude's tool shells **die when the turn ends**. | Start long-lived services detached: `Invoke-CimMethod Win32_Process Create`. |
| **Hermes updates break local customisations** (4+ times in Sep): preset hook `.pth` wiped, gateway scripts regenerated, binaries moved. | Run `agent-hooks\install-preset-hook.py --check`, restart the gateway, confirm presets (`n-cpu-moe` 12/6 for the MoE models). The hub smoke test names broken Hermes surfaces. |
| Hermes Desktop stores its launch profile separately (`%APPDATA%\Hermes\active-profile.json`). | Profile changes need both `hermes profile use` and that file. |
| One GPU, `models_max: 1`; dense models must not offload (WDDM paging → 0.91 tok/s). | First local turn after a swap costs ~20–30 s. Don't load other GPU work during tests. |
| Windows "Animation effects" appears off on this PC (browsers report reduced motion). | App Motion setting defaults to *Full*; preview panes may also pause `requestAnimationFrame` when hidden. |
| Python 3.14 (Store install) for the hub venv; Hermes ships its own Python 3.14 and venv. | Don't mix them; the hub never imports Hermes code. |
| Hub health polling is visible in Hermes `agent.log` (one access line per check). | Poll interval 5 s for health (was 2 s). |

## 7. Decisions reversed or superseded — the conclusion is the bold part

| # | Was | **Now** | Why |
|---|---|---|---|
| 1 | Name "Agent OS", folder `agent-os`, package `agent_os_hub`, header `X-Agent-OS` | **Sage OS**, `C:\Users\you\sage-os`, `sage_os_hub`, `X-Sage-OS`, env `SAGE_OS_*` | User chose the name (mentor · green · SAGE nod). |
| 2 | Tron cyan/orange default theme | **Phosphor green default**; Tron + eDEX amber still selectable | User preference. |
| 3 | CRT mode (curved glass, bezel, power-on/off) | **Removed**; constant scanlines + film grain + rolling refresh bar | User: looked bad, unnecessary. (A real barrel warp was rejected earlier: clicks would land off-target.) |
| 4 | Safety feed as a permanent right rail | **Hidden drawer**, chip + toast only when something new is blocked | Attention only when needed. |
| 5 | Claude "spend today ($)" | **Subscription usage meter** from `rate_limit_event` | Subscription, not API billing. |
| 6 | Phase 1 "every route is GET" (test enforced) | **Write routes exist** behind `X-Sage-OS` header + local Host/Origin (tests enforce that instead) | Phase 2 needs chat + approvals. |
| 7 | Motion follows the OS | **Motion defaults to Full**, user-switchable | OS reduced-motion silently disabled the visuals the user asked for. |
| 8 | Hermes profiles `sage` (main) + `default` | **Only `default`**, labelled "Hermes" in the UI. `sage` deleted 30 Sep after export (`hermes\profile-exports\sage-20260930-011911.tar.gz`, Markdown in `hermes-workspace\session-exports\sage\`, outline `hermes-workspace\SAGE-OUTLINE.md`). Kanban default assignee → `default`. | Avoid "sage inside Sage OS"; one profile is simpler. |
| 9 | Hermes chat turn-2 401 blamed on llama.cpp router ownership (Desktop vs gateway) | **Wrong.** Hermes re-resolves a bare `custom` provider from turn 2 (placeholder key). **Hub fix: `HermesAPI._runtime_pin`** sends provider + model + `require_model_lock` every turn. Verified 3/3 turns today. | Reproduced with the gateway owning the router; fix added by a separate session 30 Sep. |
| 10 | Harness: consider replacing Hermes (OpenCode / Goose / Claude Code on local models) | **Keep Hermes** for kanban, gateway, hooks; adapters keep it swappable | Only Hermes has a kanban dispatcher; not re-evaluated since. |
| 11 | Docker sandbox for Hermes terminal | **Local terminal + guardian + write guard** | Docker blocked too much real work. |
| 12 | Bloom via post-processing pass | **In-shader halo** per orb | GPU cost next to the models. |
| 13 | Icon: square mark → light-cycle drafts | **S-trail with sage leaves** (`ui/public/favicon.svg`) | User picked concept C. |
| 14 | `claude.exe` path `%APPDATA%\Claude\…`; login via `/login` | **Packages path + `auth login`** | MSIX virtualisation; slash commands don't run in the SDK. |
| 15 | Services launched from tool shells | **Detached via WMI** | They were killed at turn end (explained several "sidecar down" episodes). |
| 16 | Use BookShelf's Swift `WikiCore` as the backend (via an MCP server over it) — the plan in BookShelf's HANDOFF §6 | **Rebuild the knowledge core in Sage OS's stack** (proposed: Python); BookShelf's docs + invariants are the spec | User direction 30 Sep 2026. Removes the Windows/Swift mismatch; costs the type-level I1 guarantee (replaced by a process boundary, §5). |
| 17 | BookShelf as a separate macOS product that Sage OS integrates with | **BookShelf retired; rebuilt as a Python package inside `sage-os`** (DECISIONS D2) | User, 30 Sep 2026: one product. |
| 18 | Hermes as the required local agent layer (#10) | **Hermes is one optional connector; Sage OS owns board, inbox, Bookshelf, safety policy; no custom llama.cpp runtime** (DECISIONS D4) | "Connect whatever AI you use" fails if Hermes is mandatory; Hermes update churn. |

## 8. Known issues and blockers (most → least blocking for the user)

1. **Hermes updates can silently degrade the stack** (MoE experts all on CPU, gateway env lost). Mitigated by checklist + smoke test, not prevented.
2. **The runtime pin depends on Hermes internals** and disables Hermes' `fallback_model`; a Hermes update may change the branch it relies on (re-test multi-turn after every update).
3. **Single GPU model:** Hermes chat, kanban workers and Desktop queue behind one resident model; model swaps cost 20–30 s.
4. **Claude can't yet act on Hermes** except via `Bash` + `hermes` CLI with per-command approval (fleet MCP tools are Phase 4).
5. **Two inbox paths untested live:** Hermes approval requests, kanban reply-and-unblock.
6. **Desk-only:** no remote access, no app login (Phase 3); the hub has no auth beyond localhost binding.
7. **No CI**; the private remote `nfihero/sage-os` is pushed only on request, so local commits and tags can be ahead of it.
8. **Stale alias scripts** `swift.bat`, `coder.bat`, `guardian.bat` in `~\.local\bin` point at deleted Hermes profiles; `swift.bat` shadows the real `swift` command name.
9. Usage meter shows "OK" rather than a % until a window nears its limit (CLI behaviour).
10. Phone layout is a first pass, never tested on a real phone.

## 9. Open questions before Sage OS and BookShelf can be joined

1. ~~Language and home of the rebuilt core~~ **Answered (D2):** Python package inside `sage-os`; the macOS BookShelf app is retired.
2. ~~Which vault becomes canonical~~ **Answered (D3):** none exists; start a new local vault and import existing notes through approval. Since D17 an existing vault (Obsidian, llm-vault) is imported by adding it as a `[[sources]]` entry.
3. ~~Is any vault synced by Google Drive?~~ **Answered (D3):** no; personal files on `G:\` are Drive-synced and stay read-only to agents.
4. ~~Where does review happen~~ **Answered (D11):** the Sage OS inbox; batch approval and per-agent trust are K7.
5. ~~Which agents may propose writes~~ **Answered (K5, D16):** Claude and Hermes through MCP; kanban workers once Phase 4/A3 give them the tools.
6. ~~Agent provenance format~~ **Answered (D9, D11):** `origin: agent` + `agent: <id>`, `edited_by` for edits, `origin: imported` reserved for `sage-os:importer` (D17).
7. **Product scope:** "potential full product" — for whom beyond you (students? finance learners? anyone with a local GPU?), and does it keep BookShelf's "personal memory, no collaboration" stance? Product-izing also hits hard dependencies: Windows-only today, Hermes install, a Claude subscription, a capable GPU.
8. **Private financial data** (bank/card statements under `data-private/`): must it stay out of the knowledge base entirely?
9. ~~Auth ownership~~ **Answered (D2, D21):** Bookshelf is part of the hub, so the hub's passkey login (Phase 3b) covers it; agents are identified by the hub (D16).
