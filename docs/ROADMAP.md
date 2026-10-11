# Sage OS — roadmap

Each phase is usable on its own and ends at a **gate**: a check that proves it works before the next
starts. No dates; the order is the plan. Source: the design doc
([Sage OS — Design](https://claude.ai/code/artifact/af65a0a6-433a-48c3-b841-33d7aedab899)), extended
on 30 Sep 2026 with the Bookshelf track.

## Build order (11 Oct 2026 — DECISIONS D30, D32)

**Y1** (done, 0.16.0) **→ G1** (built, 0.17.0) **→ K7 → K14 → F1 → A3 → Y2**, then Y3–Y6, S2, K9, K11 and Phases 4–6. Y1 first so everything after it is
born sync-ready; G1 is small and fixes a real clash; K7 clears the textbook backlog; K14 makes briefing packs pick
the right notes; F1 puts that app in a friend's hands on a Mac for real-world bug reports; A3's new board store
starts with ULIDs and the change log.

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
| K7 | Review at scale: batch approvals, per-agent trust levels and roles (Librarian, Researcher, Reviewer) (D7 idea 5) | A 20-note librarian run is approved in one decision |
| K8 | Briefing packs chosen **per prompt** from notes and sources, shown to you in a *Reading* strip with everything the agent read (D20; D7 idea 2) | An agent's reply uses a fact that exists only in your notes, and the strip shows the note it came from — **pass** (6 Oct, v0.12.0: the local Gemma 4 12B answered the three-email sequence from the outreach playbooks, both shown in the strip) |
| S3 | **Google Drive connector** (D22.5): Google Docs, Sheets and Slides read through the Drive API with the user's read-only consent, exported and indexed with the rest | A Google Doc's text is found by search — **pass** (8 Oct, v0.12.2: 10 of 13 Google Docs exported and searchable) |
| K12 | **Long documents** (D23): split a textbook or long report into sections that tile its text, draft notes per section on the local model, check concept coverage, one inbox card per chapter, coverage map | A long document becomes per-chapter proposals with every section accounted for — **pass** (8 Oct, v0.13.0: outreach playbook 32 pages → 34 notes, 55/55 concepts; options lecture 55 pages → 12 notes, 36/36) |
| K13 | **Review note by note** (D24): read each proposed note rendered, keep or drop it, edit it with a live preview, file only what was kept | Kept notes filed (edited ones marked), dropped ones not, undo exact — **pass** (9 Oct, v0.14.0, tests + browser at desktop and phone width) |
| K9 | Work becomes knowledge: finished tasks propose a short record; chats get "save to Bookshelf" (D7 idea 3) | A finished task's record arrives in the inbox as a proposal |
| ~~K10~~ | ~~Git-backed vault: each approved batch is a commit~~ — **dropped** (11 Oct, D30: the journal and the Y1 change log carry the history) | — |
| K14 | **Meaning-based search** (D10's later step): notes and sources searched by meaning as well as keywords, used by search, briefing packs and Ask; embeddings rebuilt per device (D27.4) | A question worded differently from the note still finds it, and a wordy but wrong note no longer makes the briefing pack |
| K11 | Ask: answers only from the vault, with citations and an honest empty answer (D7 idea 10) | A question with no matching notes gets "nothing in your notes" |
| later | In-app markdown editor (D6) — edits go through the single writer + journal | — |

Done: K1–K6, K8, K12, K13, S1, S3. Open: K7, K14, S2, K9, K11, the editor. K10 dropped (D30).

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

## Sync and devices track (9 Oct 2026 — DECISIONS D25, D27)

Goal: install on phone, Mac and PC, sign in on each, and everything is there. D25 (app data + Library, folder
sync) is done; the rest builds the account-based, end-to-end encrypted sync of D27.

| Step | Scope | Gate |
|---|---|---|
| Y0 | App data per computer; the Library (Notes + Files) in a synced folder; STORAGE tab (open, export, move, conflicts) (D25) | **Done** (9 Oct, v0.15.0) |
| Y1 | **Sync-ready data model** (D27 "do now"): ULIDs on every record, tombstones, append-only event logs for chats / inbox / journal, synced vs device-local stores split, a device identity | Two hub instances on one PC, sharing only the synced stores by file copy, converge with no lost or duplicated item — **pass** (11 Oct, v0.16.0) |
| Y2 | Keychain for secrets (Google token, API keys, engine key); API keys entered in the app | No secret is a plain file in app data |
| Y3 | Sage account + passkey sign-in, device enrollment and revocation, recovery key | A second device joins with the first device's approval; a revoked device can't sync |
| Y4 | E2EE sync service (thin server: blobs, metadata, push) and the shared sync engine | Notes, files, chats and inbox decisions made offline on two devices merge correctly; the server holds only ciphertext |
| Y5 | Jobs routed to capable devices; the relay (phone ↔ desktop engine) | A digest started on the phone runs on the desktop and its proposals are approved on the phone |
| Y6 | Phone app (native shell around the UI + sync client) and signed desktop installers (an unsigned Mac .dmg comes first, in F1) | Install on phone, Mac and PC, sign in, everything is there |

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

## Friends and testers track (11 Oct 2026 — DECISIONS D32)

Goal: someone who isn't the developer installs Sage OS on their own Mac, starts from nothing, and reports bugs.

| Step | Scope | Gate |
|---|---|---|
| F1 | **Friend's Mac build**: `.app` with the hub (PyInstaller), UI and model catalog; `.dmg` built on GitHub Actions; unsigned with a first-open sheet; empty first run with the guide; API keys entered in the app (Keychain); *Report a problem* (report file + email, no notes or chat text); updates by new .dmg, data kept | On a Mac with nothing installed, a tester opens the .dmg, starts Sage OS, adds a note and a document, chats with an AI they connected in the app, and sends a problem report that arrives by email; a second .dmg updates the app with their data intact |

## Shared hardware track (10 Oct 2026 — DECISIONS D29)

Goal: Sage OS shares the computer. When a game or another heavy program needs the graphics card, the local
model steps aside and comes back when the card is free. Built right after Y1 (D30).

| Step | Scope | Gate |
|---|---|---|
| G1 | **Game mode**: detect another program using the GPU on any vendor (Windows per-program GPU counters + full-screen state; macOS memory pressure); pause local jobs and unload the model; offer a micro model (Gemma 4 E2B class) for light background work if it fits, with the user's OK; resume when the program closes; *always / ask / never* setting and a *Pause for a game* button; the hardware check no longer needs `nvidia-smi` | With a game running on this PC, Sage OS frees the GPU within 10 s, asks about the micro model only when it fits, does one light job on it, and the digest resumes on the main model within 5 min of the game closing; detection also checked on a non-Nvidia GPU or a Mac — **built and partly checked (11 Oct): a GPU-heavy stand-in program made game mode step aside 35 s after it got busy (13.3 → 5.0 GB in use), offer the micro model with the right sizes, and reload the main model 3 min after it closed; the probe reads the AMD integrated GPU here as well as the RTX. Still to do: a real game, the micro model's light job, and a Mac (with F1)** |

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
