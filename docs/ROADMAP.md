# Sage OS — roadmap

Each phase is usable on its own and ends at a **gate**: a check that proves it works before the next
starts. No dates; the order is the plan. Source: the design doc
([Sage OS — Design](https://claude.ai/code/artifact/af65a0a6-433a-48c3-b841-33d7aedab899)), extended
on 30 Sep 2026 with the Bookshelf track.

## The plan (18 Oct 2026 — DECISIONS D41, D43, D46)

**Direction (D46):** an independent app that a person who has never used an AI agent downloads, installs and gets
value from in five minutes, and in which "AI agents" are concrete helpers that do useful work. No outside services
(D43).

**Done so far:** the app on Windows and Mac with updates (W1, F1); the Bookshelf with review, undo, digests, briefing
packs and meaning-based search (K1–K14); one chat space for every AI (W3); connect guides, keys in the keychain and
costs (D40); plain words for first-time users (O0); the first Mac run's fixes (D42); secrets in the keychain (Y2);
pairing devices (P1, 0.30.0).

**Next, in order:**

| # | Step | What a new user gets | Size |
|---|---|---|---|
| 1 | ~~**U2** five minutes to value~~ **built (0.31.0, D47); gate: the owner's timed run on the M1** | A starter model that downloads and starts in a few minutes on an 8 GB laptop (or a free Gemini key); add documents on the first screen; a first question suggested from them; the answer shows its sources. Gate: download to first useful answer in about five minutes on the owner's M1 | medium |
| 2 | **U3** helpers (J1 + M1) | Ready-made helpers to switch on: morning brief, weekly recap, meeting prep (calendar), summarize each new document. Plain words for what each does and when; results in the Inbox; every run logged. Gate: a new user switches one on and gets its first result without help | medium |
| 3 | **U1** clean download | One download page that picks the right file; Claude Code's sign-in run by the app (no terminal anywhere). **Signing deferred** (owner, 18 Oct): installers stay unsigned for now, so the README's first-open steps stay | medium |
| 4 | **P2** sync chats and decisions | Paired devices share chats, inbox decisions, undo history and helpers' results | medium |
| 5 | **P3** sync the Bookshelf | Notes and documents copy across between paired devices | medium |
| 6 | **A3** task board | Hand bigger work to helpers by stage, without Hermes | medium |
| 7 | **M2** note-taker | Sage listens to a meeting (with consent), transcribes on the computer, proposes notes and follow-ups | large |

**Along the way (U4, independence):** anything that assumes the founder's setup (Hermes, the GPU lane, the Systems
board, terminal steps, developer wording) stays out of sight until a person connects it.

**Later, order not set:** P4 sync away from home (or the owner's router VPN), Y6 the phone app, O1 organization
bookshelves, S2 OCR, K9, K11, A4, Phases 4–6. **Open checks:** O0's gate (a real first-time user), pairing the owner's
Mac and PC, K7's live Librarian run, G1 with a real game.

### The plan before 18 Oct (17 Oct 2026 — D41, D42, D43)

Y2 (done, 0.29.0) → P1 (done, 0.30.0) → P2 → P3 → J1 + M1 → A3 → M2. Reordered by D46 above.

### Build order before 17 Oct (13 Oct 2026 — DECISIONS D30, D32, D39)

**Y1** (done, 0.16.0) **→ G1** (built, 0.17.0) **→ K7** (built, 0.20.0) **→ K14** (done, 0.21.0) **→ F1 part one** (self-contained app + signed updates, 0.22) **→ W3** one chat space (done, 0.23.0) **→ D40** connect guides and costs (done, 0.24.0) **→ F1 rest** (Report a problem, first-run self-check on every release, 0.25.0) **→ O0** onboarding pass (D41; built 0.26–0.27) **→ D42** first Mac run fixes (0.28.0). Superseded by the plan above.

## Agent hub track

| Phase | Scope | Gate | Status |
|---|---|---|---|
| 1 | Read-only dashboard: board, GPU lane, health, safety feed, sessions, theme | All six Phase 1 checks pass | **Done** (29 Sep) |
| 2 | Chat panes (Claude Code, Hermes) + approvals inbox | A Claude permission prompt reaches the inbox and is answered there | **Done** (29 Sep) |
| 2.5 | Visual pass: phosphor theme, agent orbs, handoff arcs, boot screen, screen texture, icon | User sign-off | **Done** (30 Sep), iterating on taste |
| 2.6 | Demo readiness (D18): guide with the why, panel tour, plain labels, teaching empty states, `docs/DEMO.md` | A first-time viewer can say what Sage OS is for and follows the files → notes loop | Built (3 Oct, v0.10.0); gate is the user's demo |
| 3a | Portable hub (D21): runs on macOS and Windows; per-machine `config.local.toml`; `start.sh` | The same repo starts on both | **Built** (3 Oct, v0.11.0); Mac run is the user's check |
| 3b | Phone and Mac as screens (D21): Tailscale Serve to the PC, **passkey** login with devices added from the PC, phone layout pass | A phone approves a request over the tailnet after a Face ID login | Superseded by the sync track (D22, D27: every device runs Sage OS; the relay is Y5) |
| 4 | **Lead model as orchestrator** (D26): whichever model the user picks as lead (Claude, ChatGPT, Gemini, or a local model on the engine) gets the fleet tools (`fleet_status`, `task_create`, `task_comment`/`unblock`, `ask_agent`) | The lead delegates a task that another agent finishes; checked with a cloud lead and with a local lead | Planned |
| 5 | **Lead model as reviewer** (D26): the user's chosen reviewer (any connected model) reviews on `request_review`; handoff animations | One task goes through changes, then approval, with a cloud and with a local reviewer | Planned |
| 6 | Rooms and outside agents: **team chat** (lead agent answers by default) + **agent room** (agents only, user watches, Step in) with direct chats closed by default (DECISIONS D8); ACP and A2A adapters | The user asks in team chat; the lead hands work to another agent in the agent room; the user steps in once; the result comes back to team chat | Planned |

## Bookshelf track (30 Sep 2026 — home and vault decided; step order still proposed)

The BookShelf project (`nfihero/BookShelf`) is **retired**. It is the **spec**, not the code: its
DESIGN.md, invariants I1–I9 and vault format are carried over, and the module is rebuilt as a Python
package inside this repo (DECISIONS D2). The vault lives in the app's data folder,
`data/vault/` (D6); `G:\` stays read-only and outside it. Adopted ideas: D7.

| Step | Scope | Gate |
|---|---|---|
| K1 | Vault format + read: markdown with YAML frontmatter, uid identity, no absolute paths (I8); vault at `data/vault/` (config setting); Bookshelf view with an **Open vault** button (Explorer) | Sage OS lists and renders notes from the vault; the button opens the folder — **pass** (1 Oct) |
| K2 | Search: SQLite FTS5 index rebuilt from files (vault stays the source of truth, I3) | A query returns ranked notes in < 300 ms — **pass** (1 Oct, ≤ 12 ms on 2,006 notes; v0.5.0) |
| K3 | Propose → approve → commit: agents propose, the **Sage OS inbox** approves, a single writer applies with a SQLite journal and batch undo (I1, I2, I9) | An agent's proposal lands only after approval; undo restores bytes exactly — **pass** (1 Oct, v0.6.0) |
| K4 | Screening before disk (I4); screened proposals held in the inbox with a manual *Save anyway* override (D12) | A proposal containing a key is refused before anything is written — **pass** (1 Oct, v0.7.0) |
| K5 | MCP tools for agents: `search_notes`, `read_note`, `propose_note`, `list_proposals`; `origin: agent` + agent id provenance (D16) | Claude and Hermes both read and propose through MCP — **pass** (1 Oct, v0.8.0) |
| S1 | Source library: read-only, searchable copy of chosen folders (Google Drive first), private files left out; agents search and cite (D15) | Chosen Drive folders searchable in Sage OS and by agents, Drive untouched — **pass** (1 Oct, v0.8.0) |
| K6 | Notes from whatever the user provides (redefined 2 Oct, D17): starter notes from any source (markdown imported, a collection note per folder of documents) + agent-drafted concept notes that cite their sources; an existing Obsidian vault is just another source | A source becomes approvable starter notes and agent drafts, nothing written before approval — **pass** (2 Oct, v0.9.0) |
| S2 | **OCR**: read text from images and scanned PDFs during sync, marked as OCR text; Windows' built-in engine first (D19) | A CamScanner PDF and a photo of a page are found by search and readable by agents |
| K7 | Review at scale (D36): one card and one decision per chapter, cards decided together, undo of one note, per-agent trust ladder (Ask first / New notes / Trusted) with a complete activity log, roles Researcher, Librarian (tidy runs) and Reviewer (marks drops) | A 20-note librarian run is approved in one decision — **pass in tests** (11 Oct, v0.20.0: a 20-note run approved as one batch); the run on the real library waits for the engine |
| K8 | Briefing packs chosen **per prompt** from notes and sources, shown to you in a *Reading* strip with everything the agent read (D20; D7 idea 2) | An agent's reply uses a fact that exists only in your notes, and the strip shows the note it came from — **pass** (6 Oct, v0.12.0: the local Gemma 4 12B answered the three-email sequence from the outreach playbooks, both shown in the strip) |
| S3 | **Google Drive connector** (D22.5): Google Docs, Sheets and Slides read through the Drive API with the user's read-only consent, exported and indexed with the rest | A Google Doc's text is found by search — **pass** (8 Oct, v0.12.2: 10 of 13 Google Docs exported and searchable) |
| K12 | **Long documents** (D23): split a textbook or long report into sections that tile its text, draft notes per section on the local model, check concept coverage, one inbox card per chapter, coverage map | A long document becomes per-chapter proposals with every section accounted for — **pass** (8 Oct, v0.13.0: outreach playbook 32 pages → 34 notes, 55/55 concepts; options lecture 55 pages → 12 notes, 36/36) |
| K13 | **Review note by note** (D24): read each proposed note rendered, keep or drop it, edit it with a live preview, file only what was kept | Kept notes filed (edited ones marked), dropped ones not, undo exact — **pass** (9 Oct, v0.14.0, tests + browser at desktop and phone width) |
| K9 | Work becomes knowledge: finished tasks propose a short record; chats get "save to Bookshelf" (D7 idea 3) | A finished task's record arrives in the inbox as a proposal |
| ~~K10~~ | ~~Git-backed vault: each approved batch is a commit~~ — **dropped** (11 Oct, D30: the journal and the Y1 change log carry the history) | — |
| K14 | **Meaning-based search** (D10's later step): notes and sources searched by meaning as well as keywords, used by search, briefing packs and Ask; embeddings rebuilt per device (D27.4) | A question worded differently from the note still finds it, and a wordy but wrong note no longer makes the briefing pack — **pass** (12 Oct, v0.21.0, D37: on the owner's notes, 21/23 differently worded questions find their note in the top 5 vs 2/23 by keywords; briefing packs right 6/6 vs 4/6, look-alike traps now empty) |
| K11 | Ask: answers only from the vault, with citations and an honest empty answer (D7 idea 10) | A question with no matching notes gets "nothing in your notes" |
| later | In-app markdown editor (D6) — edits go through the single writer + journal | — |

Done: K1–K8, K12–K14, S1, S3. Open: S2, K9, K11, the editor. K10 dropped (D30).

## Architecture track (30 Sep 2026 — DECISIONS D4, D5; recorded "for now")

Goal: Sage OS owns the core (board, inbox, Bookshelf, safety policy, shared tools); agents and models
plug in through connectors; Hermes becomes optional. No custom llama.cpp runtime.

| Step | Scope | Gate |
|---|---|---|
| A1 | Sage OS interfaces for **model providers** (any OpenAI-compatible endpoint) and **agent connectors**; move the existing Claude and Hermes code behind them | Claude and Hermes panes work unchanged through the new interfaces — **pass** (30 Sep: Claude chat + inbox deny, Hermes 2 turns) |
| A2 | Bookshelf K1–K3 as Sage OS's own (see track above) | **done** with K1–K3 (1 Oct) |
| A3 | **Sage OS task board** any agent can work from; Hermes kanban becomes an optional source. Current Hermes kanban contents may be cleared (D5) | A task created in Sage OS is finished by an agent and approved in the inbox, with Hermes kanban unused |
| A4 | A second local agent connector, proving Hermes is optional (candidates to verify on Windows first) | Same task runs on two different local agents |
| A5 | Environment setup: Sage OS's own `llama-server` (D22.3): hardware check, catalog rated per machine, binary + model downloads (resumable, SHA-256 checked), start/stop; one **Chat** connector for any OpenAI-compatible AI (engine, ChatGPT, Gemini, Ollama) with the Bookshelf tools | A machine with no local AI gets a working local model through Sage OS — **built** (6 Oct, v0.12.0); checked here with existing files; a fresh-machine download is the remaining check |

Open checks before A3/A4: which agent tools work reliably on Windows; what the Hermes kanban does
that a Sage OS board must match.

## Sync and devices track (9 Oct 2026; rewritten 17 Oct — DECISIONS D25, D27, D43)

Goal: install on phone, Mac and PC, pair them, and everything is there, with **no outside service** (D43): devices
talk to each other directly over your own network. Y1's data model carries over unchanged.

| Step | Scope | Gate |
|---|---|---|
| Y0 | App data per computer; the Bookshelf (Notes + Files) can sit in a folder you choose; STORAGE tab (open, export, move, conflicts) (D25). Folder sync through a cloud service is no longer suggested (D43) | **Done** (9 Oct, v0.15.0) |
| Y1 | **Sync-ready data model** (D27 "do now"): ULIDs on every record, tombstones, append-only change logs, synced vs device-local stores split, a device identity | Two hub instances on one PC, sharing only the synced stores by file copy, converge with no lost or duplicated item — **pass** (11 Oct, v0.16.0) |
| Y2 | **Secrets in the keychain**: the Google token and the engine key (API keys done in D40), and each device's own key pair for pairing | No secret is a plain file in app data — **pass** (18 Oct, v0.29.0, D44) |
| P1 | **Pairing**: *Add a device* shows a short code, the other device types it; key pairs exchanged and checked; devices found on the local network (Bonjour/mDNS) or by address; a separate sync listener that accepts paired devices only (the hub stays localhost-only); remove a device | A Mac and a PC pair with a code; an unpaired device is refused; a removed device can't connect again — **pass** in tests and on two hubs on one PC (18 Oct, v0.30.0, D45); the owner's Mac and PC next |
| P2 | **Records sync**: change logs exchanged over the paired, encrypted connection and replayed with the Y1 merge; per-device cursors; in the background when both are on the same network | A chat started on the Mac and continued on the PC, and an inbox decision on each, converge on both with nothing lost or doubled, made apart or together |
| P3 | **Bookshelf sync**: notes and files by content hash; both copies kept when one file changed on two devices; STORAGE shows them | A note added on the Mac and a document added on the PC appear on both; a note edited on both keeps both versions |
| P4 | **Away from home** (later): one of your own devices reachable from outside through your own router, holding only encrypted data (D43.5) | The Mac syncs with the PC from another network, and nothing readable leaves your devices |
| Y6 | Phone app (native shell around the UI + sync client), after P1–P3 (and P4 to work away from home) | Install on phone, Mac and PC, pair, everything is there |

Superseded by D43: Y3 (Sage account and passkeys), Y4 (a sync server we run), Y5 (jobs routed through that server;
it comes back as jobs sent to a paired device once P2 works).

### Y1 plan (11 Oct 2026; choices in D28, how it was built in D31) — done, v0.16.0

Released as one minor version (v0.16.0), built in seven parts, each with its own tests. Every existing ID of a
synced record is rewritten to a fresh ULID; changes go to an append-only log written alongside the current
tables. Nothing changes for the user except one line in STORAGE.

| Part | Scope | Check |
|---|---|---|
| Y1.1 | **Device identity**: `device.json` in app data (never the Library) with a permanent device ULID and a name (computer name, renamable); STORAGE shows "This device: …" | Same ID across restarts; a fresh app-data folder gets a new one |
| Y1.2 | **One ID generator**: `new_id()` makes ULIDs, sortable by time and still in order within one millisecond; replaces the six random-ID sites (`ch_`, `cs_`, `dg_`, `p_`, `ib_`, `held:`) | 100k IDs in a tight loop: all unique, all in order |
| Y1.3 | **Synced vs this-computer-only list** in code, labelling every table and data file. Synced: chats and messages, Claude session records, proposals and decisions, the undo journal, digest jobs and progress, briefing exclusions. This computer only: dashboard events and panels, search indexes, source copies, the engine, the Google token, held secret proposals | A test fails if any table is unlabelled |
| Y1.4 | **Change log (outbox)**: append-only `changes` (ULID, device, time, stream, record, operation, data); every write to a synced table adds its log entry in the same transaction | Each synced write adds exactly one entry; a failed write adds none |
| Y1.5 | **Tombstones**: deleting a chat, session or briefing marks it deleted (`deleted` time + log entry) instead of removing the row; lists hide deleted rows | Delete, restart: still hidden; row and log entry still there |
| Y1.6 | **Migration** on the first 0.16 start: back up every database; give every synced record a fresh ULID and update every reference (messages → chats, decisions → proposals, batches → entries, sections → digests, digest folders); record each existing row as a "created" log entry from this device; a marker stops a second run; restore the backup on any error | On a copy of the real data: same counts, no broken references, a second run changes nothing |
| Y1.7 | **Convergence check (the gate)**: a test harness runs two hubs on this PC as two devices; both create chats, approvals, undos and deletes; their logs are exchanged by file copy and replayed | Both hold the same synced records, nothing lost or duplicated, deletes respected, whatever the replay order |

Kept as they are: notes' own `uid` (it lives in each markdown file, D9, and is already permanent; rewriting it
would edit every file in the Library); Claude Code's own session IDs (they belong to the CLI); the numbered rows
of search indexes and the dashboard feed (they never leave the computer). The digest is paused during the
migration and resumes under its new ID with its progress. Links copied before 0.16 stop working (D28).

## Desktop app track (11 Oct 2026 — DECISIONS D33)

| Step | Scope | Gate |
|---|---|---|
| W1 | **Tauri desktop app**: a window and tray around the hub; starts or attaches to the hub; close to tray, Start at sign-in, Quit stops the hub cleanly; one copy; outside links to the browser; per-user Windows installer | The user installs it, closes and reopens the window from the tray, and quits it with nothing left running — **pass** (11 Oct, v0.18.0) |
| W3 | **One chat space** (D39): every AI in one chat view (local model, Claude Code, ChatGPT, Gemini, Ollama, Hermes) with one history list like other AI apps: newest first, grouped by day, searchable by title and message, rename / pin / archive, reopen and continue any chat, the AI picked per chat. **A fresh install ships with no models and no agents** (the app's own search model and llama.cpp fetch themselves on first start): the first screen is a canvas to install a model (rated for this computer) or connect an AI the user already has, then talk | Any past chat, with any AI, is found and continued from one place in under 10 s; nothing from before is lost; on a clean computer, a new user goes from first start to a first answer without leaving that canvas — **pass** (13–14 Oct, v0.23.0: on a copy of the owner's chats, every chat (local and Claude) listed by day, found by a phrase inside it and continued; switching AI mid-chat hands the conversation over (tests); an empty install shows the canvas with a fitting model and connects Claude; the full first answer on a clean computer is checked with F1's Mac) |
| W2 | **Library-first home** (D35): agent planet panel left, search and chat centre, inbox / digest / recent notes right, systems strip; Systems view for board, GPU lane, Hermes; the planet card's readouts and Doto numerals used everywhere; rolling refresh bar removed | The owner approves it in the app — **pass** (11 Oct, v0.19.0: "I like it") |

## Friends and testers track (11 Oct 2026 — DECISIONS D32)

Goal: someone who isn't the developer installs Sage OS on their own Mac, starts from nothing, and reports bugs.

| Step | Scope | Gate |
|---|---|---|
| F1 | **Friend's Mac build**: `.app` with the hub (PyInstaller), UI and model catalog; `.dmg` built on GitHub Actions; unsigned with a first-open sheet; empty first run with the guide; API keys entered in the app (Keychain); *Report a problem* (report file + email to roundederror@gmail.com, no notes or chat text); updates by new .dmg, data kept | On a Mac with nothing installed, a tester opens the .dmg, starts Sage OS, adds a note and a document, chats with an AI they connected in the app, and sends a problem report that arrives by email; a second .dmg updates the app with their data intact — **built** (14 Oct, v0.25.0: self-contained app and signed updates 0.22, keys in the app 0.24, Report a problem and a first-run self-check run by the macOS and Windows build machines on every release 0.25; the tester's run on a real Mac follows docs/MAC-FIRST-RUN.md); first Mac run 15 Oct found the picker and model-list problems fixed in 0.28.0, D42) |

## Shared hardware track (10 Oct 2026 — DECISIONS D29)

Goal: Sage OS shares the computer. When a game or another heavy program needs the graphics card, the local
model steps aside and comes back when the card is free. Built right after Y1 (D30).

| Step | Scope | Gate |
|---|---|---|
| G1 | **Game mode**: detect another program using the GPU on any vendor (Windows per-program GPU counters + full-screen state; macOS memory pressure); pause local jobs and unload the model; offer a micro model (Gemma 4 E2B class) for light background work if it fits, with the user's OK; resume when the program closes; *always / ask / never* setting and a *Pause for a game* button; the hardware check no longer needs `nvidia-smi` | With a game running on this PC, Sage OS frees the GPU within 10 s, asks about the micro model only when it fits, does one light job on it, and the digest resumes on the main model within 5 min of the game closing; detection also checked on a non-Nvidia GPU or a Mac — **built and partly checked (11 Oct): a GPU-heavy stand-in program made game mode step aside 35 s after it got busy (13.3 → 5.0 GB in use), offer the micro model with the right sizes, and reload the main model 3 min after it closed; the probe reads the AMD integrated GPU here as well as the RTX. Still to do: a real game, the micro model's light job, and a Mac (with F1)** |

## From the first demo (14 Oct 2026 — DECISIONS D41; order not yet decided)

Rule for everything: **assume the user has never used an agent before** (D41.1).

| Step | Scope | Gate |
|---|---|---|
| O0 | **Onboarding pass for first-time users**: every screen, guide and message reviewed for someone who has never used an agent; plain words, one obvious next step, no terminal on the main path | A person who has only used a chat app installs Sage OS, connects an AI and gets an answer from their own notes without help — **built** (14–15 Oct, v0.26.0–0.27.0: all 12 audit items addressed: plain-words guide and tour, one name (Bookshelf), documents added from the app, a quieter top bar with SETTINGS, plain words in AI ACTIVITY, search, the systems strip and the model picker, Claude's sign-in with COPY; the gate waits on a real first-time user) |
| J1 | **Recurring jobs**: schedules set in plain words (morning brief, weekly summary, re-read a source); results to the inbox; every run in the activity log | A weekday 7:00 brief arrives three days running, each in the log; pausing the job stops it |
| M1 | **Before a meeting**: a brief on the person or company and what was said last time, ahead of each calendar meeting, from notes, meeting notes and sources (needs a calendar connection) | 15 minutes before a meeting with someone met before, the brief names the last meeting's points and cites them |
| M2 | **Note-taker in the app**: listens to a meeting (with consent), transcribes on this computer, proposes notes and follow-ups filed under the people and companies involved | A 30-minute call becomes an inbox card of notes and follow-ups that M1 then uses for the next meeting with them |
| O1 | **Organization bookshelves**: connect to a library an organization publishes, read and cited by your AIs, kept apart from your own notes; a private one opens only with the organization's credential (builds on Y3, Y4) | A member reads and cites the organization's notes; a non-member can't open it |

## Hub breadth track (from the 30 Sep 2026 product framing; order not yet decided)

| Item | Scope | Starting point |
|---|---|---|
| H1 Model choice | Pick local or cloud model per agent / task in the UI | Hermes already has DeepSeek and OpenRouter credentials and per-task `--model`; Claude model picker exists per session |
| H2 Workflow boards | Several kanban boards for different workflows (school, job search, finance projects…) | Hermes kanban has `boards` support; Sage OS shows one board today |
| H3 More programs | Bring conversations from other tools into the hub | Phase 6 adapters (ACP, A2A); Hermes can already import Claude Code / Codex sessions |
| H4 Connected topics | Link conversations across programs by topic, feeding Bookshelf | Depends on Bookshelf K2 (search) and K5 (MCP) |

## Product track (open)

Audience and scope in **D22**: anyone who uses several AIs and has scattered notes. Each user runs
Sage OS on every device they own, with notes synced through a folder they already trust (option B);
an optional paid relay later (option C). Still to build: note sync with conflict handling, signed
Windows and Mac installers that bundle Python and the UI, first-run setup, API-key entry in the app
(today keys come from environment variables), Google verification for the Drive scope (or the
narrower `drive.file` scope with a picker). Still undecided: accounts, pricing, which tiers ship first.
