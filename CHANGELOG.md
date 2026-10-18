# Changelog

All notable changes to Sage OS. Versions before 0.3.0 were built before the repository's first commit
and were never snapshotted; their entries record what was built and verified on those dates, not
recoverable commits. Format: [Keep a Changelog](https://keepachangelog.com/), versions follow semver
while pre-1.0.

**Versioning (from 0.4.0, user request 1 Oct 2026):** every roadmap step that passes its gate is
released as its own minor version (0.x.0) with an entry here and a local git tag `v0.x.0`; docs-only
changes are patch versions (0.x.y). Each entry names the gate result. Tags are pushed only when the
user asks. 0.4.0 bundles A1 and K1 because neither was released on its own when built.

## [Unreleased]

## [0.33.0] — 2026-10-18

MODELS redesigned for choosing a model (D49). **Gate: the owner's look.** pytest 380.

### Changed
- MODELS opens on what's running (or how to start), then two recommended models as big cards (*Quick start* and *Best
  answers here*, with a filled button), then every other model as a card: what it's good for, its size, how it runs
  on this computer, one button. Source and licence are in the tooltip; models too big for the computer fold away.
- Downloads show a dot-matrix meter with the time left, PAUSE and CONTINUE.
- Game mode is one folded line at the bottom of MODELS; its process list no longer shows impossible memory figures.
- Cloud AIs: one line with CONNECT AN AI instead of config-file instructions.

## [0.32.0] — 2026-10-18

A polish pass for newcomers on ordinary laptops (D48). **Gate: checked at 1366×768 and 375 px; the owner's look.**
pytest 380.

### Changed
- The first-run screen shows both steps side by side (pick an AI; give it your documents), so nothing important is
  below the fold on a 1366×768 laptop. The hardware box is one line; other models fold away; "Use Gemini instead"
  comes before the upgrade note.
- The home screen drops the label row above its panels (each panel's title already names it), giving the content
  more room.
- The waiting AI card keeps its button bright and drops empty rows; the inbox's empty state reads in the sentence font.
- Modals look alike: ✕ to close everywhere; Your devices and Report a problem fit their content; the Bookshelf hides its
  folder path behind OPEN FOLDER; Usage says once what spend counts; the Models screen explains instead of loading
  forever when local models are turned off.
- Hermes' status lights show only when Hermes is connected to Sage OS.

### Added
- `?shot=<screen>` for screenshots and checks (no boot animation or guide; opens home, guide, bookshelf, connect,
  usage, devices, report or models).

## [0.31.0] — 2026-10-18

U2: five minutes to value (D47). **Gate: the owner's timed first run on the M1** (the app now records it). pytest 380.

### Added
- The first screen is two steps: *1 · Quick start* (a 2.7 GB starter model that's ready in a few minutes, with the
  bigger best fit named for later, or Gemini with no download) and *2 · Give it your documents* (add files or a
  folder while the model downloads).
- Downloads show the time left.
- An empty chat suggests first questions built from your newest documents; one click asks.
- A fresh install records how long it took to an AI, a first document and a first answer, on this computer only;
  a problem report includes it.

### Changed
- Code signing is deferred (D46 update); the download page and no-terminal work stay in U1.

### Docs (18 Oct)
- D46: Sage OS is an independent app built to win new users. MISSION.md rewritten; the roadmap reordered:
  U2 five minutes to value, U3 helpers (J1 + M1), U1 clean download, then P2, P3, A3, M2.
- docs/company/: the company documents for investors (one-pager, pitch outline with a five-minute demo, product,
  technology, market and competition, business model options, traction and milestones, risks, data-room index).

## [0.30.0] — 2026-10-18

P1: pair your devices directly (D45). **Gate: pass in tests and on two hubs here; the owner's Mac and PC are the real
check.** pytest 376.

### Added
- **Your devices** (⚙ SETTINGS): pair this computer with your others. *ADD A DEVICE* shows a one-time code; on the
  other device, *I HAVE A CODE*, pick it from the devices found on your network (or type its address), and type the
  code. Both screens show both keys to compare. *CHECK* reaches a paired device and proves both sides; *REMOVE*
  unpairs it.
- A sync listener, separate from the app's own port, that only paired devices can use: TLS, every request signed,
  and running only while you have a paired device or are showing a code. Sharing chats and the Bookshelf over it
  comes next (P2, P3).
- The packaged app's self-check opens the listener on that computer and checks its handshake.

## [0.29.0] — 2026-10-18

Y2: every secret in the OS keychain (D44). **Gate: pass** (no secret is a plain file in app data). pytest 371.

### Added
- Each device has its own pairing key, kept in the keychain; STORAGE shows its fingerprint, for pairing devices next
  (P1, D43).

### Changed
- The Google Drive sign-in moves from `google-token.json` into the keychain the first time this version starts.
- STORAGE no longer suggests putting the Bookshelf in a cloud folder (D43), and says where your secrets are kept.

### Fixed
- When two versions are released together, the update feed now points to the newest one (0.27.0 had been left as
  "latest" over 0.28.0).

### Docs (17 Oct)
- D43: sync without any outside service; devices pair and sync directly (replaces D27's account and server). The
  roadmap laid out as one plan: Y2, P1 pairing, P2 records, P3 Bookshelf, J1 + M1, A3, M2.

## [0.28.0] — 2026-10-17

The first Mac run's findings fixed (D42). **Gate: the owner's re-run on the Mac** (docs/MAC-FIRST-RUN.md). pytest 365.

### Fixed
- The AI picker no longer runs off the window: it sits above every panel, scrolls, and keeps *Install or connect
  another… CONNECT* at the bottom. Checked at 1024×768 and 375×812 with 60 Gemini models: every entry and CONNECT
  can be reached.
- Cloud services offer chat models only (no text-to-speech, image, music, robotics or computer-use models), the
  best-known four first with what each is good for, the rest under *More … models*, all with readable names.
- A model's thinking (`<thought>` blocks) is no longer shown as its answer, and a reply that stops early says so.
- No "kanban poll failed" line every few seconds on a computer without Hermes.

### Added
- **SWITCH OR CONNECT AN AI** on the left card, and one-click entries in the picker for a model on this computer,
  Claude Code, ChatGPT and Gemini when they aren't set up yet.
- An empty chat list says how many chats are in the Archive; an archived chat offers *Put it back*.

### Changed
- On a Mac: *Memory* instead of graphics memory, *this Mac*, and Command-key steps for the terminal.
- README and the Mac checklist name the installers as GitHub publishes them (`Sage.OS_<version>_…`), and the README's
  Claude sign-in works on a Mac too.

## [0.27.0] — 2026-10-15

O0: everything in the first-time-user audit is addressed (D41.1). **Gate: waits on a real first-time user**
(docs/O0-AUDIT.md). pytest 359.

### Added
- **Add your documents from the app:** **+ ADD FILES** (or drop files onto it) saves them into the Bookshelf and makes
  them searchable; **+ ADD A FOLDER** opens the computer's own folder picker, copies the folder read-only, reads it
  and remembers it. No config file, no Explorer. On the Bookshelf's empty screen and at the top of Sources.
- **SETTINGS** in the top bar: look, animations, game mode and the safety log.
- Claude Code's sign-in step shows the exact command with a COPY button and how to open a terminal on Windows or Mac.

### Changed
- The notes are called **Bookshelf** everywhere on screen (0.26.0 said Library). The folder on disk keeps its name.
- The top bar shows what a newcomer needs: Bookshelf, Inbox, $ Usage, Guide, Report a problem, Settings. Game mode
  and the safety chip come forward only when they have something to say; Claude's limit bars only once Claude reports.
- Plain words in Sources ("Files you added", CHECK FOR CHANGES, SUGGEST NOTES, AI WRITES NOTES), the AI ACTIVITY screen
  (what each AI may do on its own, saved / turned down), search (smart search), the systems strip (graphics memory,
  model on this computer, DETAILS) and the model picker (what each model is good for; runs well here / runs, but
  slowly / too big for this computer).

## [0.26.0] — 2026-10-14

O0 part one: the screens a first-time user meets, in plain words (D41.1). **Gate: not yet** (it needs a person who
has never used an agent; 7 of the 12 audit items are still open, docs/O0-AUDIT.md). pytest 355.

### Changed
- The guide that opens first is rewritten for someone who has never used an AI agent: what Sage OS does in two
  sentences, three steps to start (pick an AI, add your documents, approve what it saves) and four promises, with no
  jargon or decision numbers. The tour says the same in plain words.
- One name for your notes: **Library** everywhere on screen (it was Library, Bookshelf and "vault"). OPEN VAULT is
  OPEN FOLDER.
- "AI" instead of "agent" on the main screens: Your AI, Enter asks your AI, AI ACTIVITY in the inbox; the inbox's
  empty state says what will arrive in plain words.
- The Hermes, Models and Guard lights, and Hermes in the systems strip, appear only once Hermes is connected in
  Sage OS, not merely installed.
- The chat an AI writes notes in is called "Notes from <document>".

### Added
- `docs/O0-AUDIT.md`: a fresh install walked through as a first-time user, 12 findings ranked, which are fixed.

## [0.25.0] — 2026-10-14

F1 completed in the app: Report a problem, and every release's first run checked on a fresh Mac and Windows (D32).
**Gate: built; the person-on-a-Mac run is the owner's (docs/MAC-FIRST-RUN.md).** pytest 355.

### Added
- **REPORT A PROBLEM** in the top bar: write what went wrong, read the whole report, then Sage OS saves it to
  Downloads and opens an email to roundederror@gmail.com to attach it to. The report has the app version, this
  computer's system and memory, what's connected and recent errors, with the home folder, user name, email addresses
  and anything key-like taken out. It never includes notes, documents, chats or keys.
- A first-run self-check (`--self-check OUT --with-engine`) that each release's build machines run on the packaged
  app for macOS and Windows: empty start, nothing connected, bundled screen, catalog and price list, the OS keychain,
  a problem report, and llama.cpp downloaded and run. A failure stops the release.
- `docs/MAC-FIRST-RUN.md`: the tester's checklist for a Mac that has never had Sage OS.

### Docs
- D41, from the first demo: assume users have never used an agent before; proposed steps O0 (onboarding pass), J1
  (recurring jobs), M1 (a brief before each meeting), M2 (a note-taker in the app), O1 (organization bookshelves),
  in a new ROADMAP track.

## [0.24.0] — 2026-10-14

Connect guides and what each AI costs (D40). **Gate: pass.** pytest 352.

### Added
- CONNECT: step-by-step guides for every AI (a model on this computer, Claude Code, ChatGPT, Gemini, Ollama, Hermes),
  each with its state on this computer and the button that finishes it. Opened from the first-run screen and from
  *Install or connect another…* in the AI picker. The same guide is in `docs/CONNECT.md`.
- ChatGPT (OpenAI) and Gemini (Google) connect by pasting an API key: tested with the provider first, then kept in the
  operating system's keychain (Windows Credential Manager, macOS Keychain), never in a file. DISCONNECT removes it.
- Every reply records its tokens; a chat's header shows its tokens and cost.
- USAGE & COSTS (the $ USAGE chip in the top bar): spend today, 7 and 30 days; what Claude plan work would cost on the
  API; tokens per day; Claude plan limits and OpenAI rate limits; tokens and cost per AI; and a dated price list from
  each provider's own price page, where any price can be corrected or added (your prices follow you to your devices).


## [0.23.0] — 2026-10-14

W3, one chat space (D39). **Gate: pass.** pytest 343.

### Added
- One chat space for every AI: a history rail of every conversation (local model, ChatGPT, Gemini, Ollama, Claude Code,
  Hermes), newest first and grouped by day, pinned chats on top, search over titles and messages, rename, pin, archive.
- An AI picker above each chat: the next reply comes from the AI you pick, which is given the conversation so far.
- A fresh install's first screen: the model that fits this computer best with INSTALL AND START (llama.cpp, the model
  and a first chat in one click), other models rated for this computer, and connecting Claude Code, ChatGPT, Gemini or
  Ollama (found by itself when it runs here).
- The app's own helpers (llama.cpp and the search model) download by themselves on first start, and try again if that
  fails.
- Phone: a CHATS button switches between the history and the conversation.

### Changed
- A fresh install connects no agents and downloads no chat model; what you connect is saved in your own settings
  (`config.local.toml`, in app data inside the app), so updates keep it.
- The left panel follows whichever AI is answering the open chat; the agent switch list under it is gone (the picker
  replaces it). The separate Claude pane is replaced by the chat space.

## [0.22.2] — 2026-10-13

The first update delivered through the app: a copy of 0.22.1 offers it in the top bar.

### Fixed
- MODELS failed in the installed app: the model catalog wasn't in the bundled hub (the package never declared it as a
  data file). It is declared now, the bundle takes it from the source tree, and a test checks every data file ships.

## [0.22.1] — 2026-10-13

### Fixed
- The app now carries the public key the releases are signed with. 0.22.0 was signed with a new key but carried the
  previous one, so it would have refused later updates: install 0.22.1 instead (the 0.22.0 release is withdrawn).

## [0.22.0] — 2026-10-12

The first self-contained release with updates (D38, the first part of F1). Install this one by hand from the Releases
page; later versions arrive as updates. pytest 329.

### Added
- The desktop app carries its own hub (bundled with PyInstaller, with the UI, config and model catalog): no Python,
  Node or copy of the code needed.
- Updates: the app checks for a new release when it starts and every hour; an UPDATE chip in the top bar shows what's
  new; "Update and restart" installs it (signed by the owner's key; anything else is refused) and keeps your data.
- Release pipeline: a version tag builds Windows and macOS (Apple Silicon) on GitHub Actions and publishes the release
  with its notes and update files.

### Changed
- Inside the app, this computer's settings (`config.local.toml`) live in app data, so updates never overwrite them.

## [0.21.0] — 2026-10-12

K14, meaning-based search (D37). **Gate: pass** on the owner's library: 21/23 differently worded questions find their
note (2/23 by keywords), briefing packs right 6/6 (4/6). pytest 328.

### Added
- Search by meaning as well as words: EmbeddingGemma 300M in its own llama-server on the CPU (downloaded on request,
  334 MB, checksum-verified), a per-device vector cache (`semantic.db`), notes and source passages indexed in the
  background and re-embedded only when they change; paused during game mode.
- Hybrid ranking for Ctrl K and Library search, the agents' search tools, the Reviewer and the Librarian; results found
  only by meaning are marked "≈ meaning"; the search box says whether search is words only, indexing, or words +
  meaning.
- Briefing packs filtered and ranked by meaning; a source brings the passage that matched.
- `GET /api/briefing/preview` (what a pack would carry, nothing sent), `words=true` on note search, and
  `hub/tools/eval_search.py`, the gate check against a live hub with private questions.

### Changed
- `config.toml` is generic: your sources, Claude workspaces and Hermes path live in `config.local.toml` (the repo is
  public). Commits use the GitHub no-reply address.

### Fixed
- The search results list opened far below the search box (a shared panel style overrode its position).

## [0.20.0] — 2026-10-11

K7, review at scale (D36). **Gate: pass in tests** (a 20-note Librarian run filed in one decision); the live run waits
for the engine. pytest 316.

### Added
- One inbox card per chapter: the parts of a digest chapter are grouped (older cards too) with APPROVE ALL, REJECT ALL
  and REVIEW across every part; approving files every part as one batch with one undo.
- Tick cards to approve or reject several at once (one batch); counts in the top bar and tabs show cards, not parts.
- History: undo one note of a batch (an archive's two halves together), and a "filed by trust" mark.
- AGENTS screen: per-agent trust levels (Ask first / New notes file themselves / Trusted), roles, each agent's record,
  and a complete activity log (searches, reads, proposals, filings, rejections, held and refused proposals, undos,
  trust changes, reviews, Librarian runs, your decisions), per agent or for everyone. Kept at every trust level.
- Trust suggestions in the inbox after 10 clean approvals, and an offer to step back down after undoing something an
  agent filed by itself; *Filed for you* in the inbox lists what agents filed themselves this week, each undoable.
- The Librarian: tidies a folder's notes (tags, links to related notes, clearer titles) as one proposal.
- The Reviewer (Claude Code, the local engine or any model): marks the notes it would drop, with reasons; REVIEW starts
  with them dropped and a card can approve without them. On request or for every new proposal.

### Changed
- The per-agent inbox limit counts cards: a chapter's later parts join its card.
- The approvals inbox, agent tools and digest record everything they do in the activity log (bookshelf.db, synced).

## [0.19.0] — 2026-10-11

W2, the library-first home (D35). **Gate: pass** — approved by the owner in the app. pytest 297.

### Added
- Home: the agent planet panel (State / Model / Where / Chats, GPU memory and busy meters; Claude's subscription bars
  when Claude is chosen) with agents to switch to or connect; search over notes and files with Ctrl K, results that
  open in the Library, Enter to ask the local model; the chat in the centre; inbox, digest progress and recent notes
  on the right; a one-line systems strip; a **Systems** view for the board, GPU lane and Hermes; phone tabs Home,
  Agent, Inbox, Systems.
- Shared readout components (`Readout.tsx`): rows, dot-matrix meters, Doto numerals and ages like the clock, used
  by search, chats, inbox, digest, recent notes and the strip.
- An always-visible GAME MODE chip in the top bar.
- PRODUCT.md (Impeccable's product record) and a rejected-direction note for the home surface.

### Changed
- The rolling CRT refresh bar is removed.
- The guided tour follows the new layout.

### Fixed
- A digest chapter that waited for inbox room re-sent its first part every time a slot opened (Chapter 7 part 1 went
  out five times on 11 Oct); a resumed chapter now skips notes it already sent, even when its counts change. The
  100 duplicate notes were undone and two duplicate cards rejected, with the owner's OK.
- Search snippets render through the safe highlighter (never HTML); a saved "Claude" agent falls back to the local
  model while Claude isn't connected; a search error clears on the next result; failed digest sections aren't
  counted as drafted.

## [0.18.0] — 2026-10-11

W1, the desktop app (D33), and a UI pass (D34). **Gate: pass** — installed, closed to the tray and reopened, quit with
nothing left running. pytest 295.

### Added
- **Desktop app** (`desktop/`, Tauri 2): window + tray around the hub, loading page, close to tray, Start at sign-in
  (off by default), Quit, one copy at a time, remembered size, outside links in the browser; per-user Windows installer.
- Hub: `POST /api/quit` (stops cleanly, unloading the local model), `--log FILE` with crash traces, `/api/ping` names the app.
- **Empty agent cards:** the lead-agent slot says how to connect Claude Code until it's installed and signed in.
- Inbox: a line confirming what was filed after approving.
- `docs/mockups/home-library-first.html`: mockup of a library-first home (batch C), for review.

### Changed
- Services report up / down / off / absent; red only for something that stopped; Hermes' checks optional without
  Hermes; the GPU lane shows the Sage OS engine and drops temperature and power.
- Disabled controls dimmed and dashed; a 1 px press; nothing under 11 px; sentences in a sans face; amber theme's muted
  text 4.8:1.
- Inbox order: requests first (newest first), then proposals oldest first; digest cards titled with book and chapter.
- The Hermes tab appears once Hermes has run.

## [0.17.0] — 2026-10-11

G1, game mode (D29). **Gate: partly** — built and partly checked (11 Oct): a GPU-heavy stand-in program made game mode step aside 35 s after it got busy (13.3 → 5.0 GB in use), offer the micro model with the right sizes, and reload the main model 3 min after it closed; the probe reads the AMD integrated GPU here as well as the RTX. Still to do: a real game, the micro model's light job, and a Mac (with F1).

### Added
- **Hardware readings for any GPU brand** (`sage_os_hub/hardware`): DirectX lists the cards (name, vendor, memory),
  Windows' GPU counters give memory and activity per card and per program, plus the full-screen-game state, the window
  in front and whether it fills the screen; macOS reads memory pressure and the front app. A reading takes ~2 ms.
- **Game mode** (`gamemode.py`): detects a game or heavy program; pauses local jobs and unloads the local model; asks in
  the inbox whether Gemma 4 E2B may keep working beside it (light jobs; digests wait for their own model); stops it if
  the program needs the room; reloads the main model 3 min after it closes. Settings per computer in `gamemode.json`.
- MODELS → **Game mode**: live status, always / ask / never, *Pause for a game*, always / never per program; a GAME MODE
  chip next to MODELS while it has stepped aside.
- **Gemma 4 E2B** (Q4_0, 2.8 GB, Apache-2.0) in the catalog as the micro model; the engine can start a model small
  (one 8K slot).

### Changed
- The engine's hardware check and the GPU lane no longer use `nvidia-smi`; MODELS rates any card with its own memory.
- Digests draft only on the model their job chose (same file under its other id counts); local chats say why they're
  paused, or note that the micro model answered.

## [0.16.1] — 2026-10-11

Docs only.

### Added
- **D32**: F1, a Mac build for a friend: `.app` + `.dmg` built on GitHub Actions, unsigned with a first-open sheet,
  empty first run, API keys entered in the app (Keychain), *Report a problem* by email with a report file.
- ROADMAP **friends and testers track** with step **F1**; build order Y1 → G1 → K7 → K14 → F1 → A3 → Y2.

## [0.16.0] — 2026-10-11

Y1, the sync-ready data model (D27, D28, D31). **Gate: pass** — two hubs on one PC, swapping only their change
logs as files, end up with identical synced records in any replay order, nothing lost or duplicated, deletes kept.
pytest 264/264, smoke 18/18.

### Added
- **Device identity**: `device.json` in app data with a permanent ID and a name; STORAGE shows *This device* with
  RENAME (`POST /api/storage/device`).
- **ULIDs** for every record (prefixed: `ch_`, `cs_`, `ci_`, `p_`, `b_`, `dg_`, `br_`, ...), sorted by time and never
  going backwards on one device.
- **Change log**: a `changes` table in each database with synced tables, filled by triggers in the same
  transaction as the row; entries merge from another device in any order (newest per record wins).
- **Manifest** of what syncs and what stays on this computer, with tests that fail on anything unlabelled.
- **Tombstones** for chats, Claude sessions and briefings; deletes win over edits from another device.
- **Migration** at the first 0.16 start: every database backed up to `backups/pre-ulid-<time>/` with the old to new
  ID map; IDs and references rewritten; existing rows logged; any error restores the backups.

### Changed
- Chat messages, undo batches and briefings use text IDs (were counting numbers); the undo route takes the batch's
  ULID. Session upserts update in place (a late write can't revive a deleted chat).
- Interrupted digest sections are re-queued after the change log is attached, so the reset is logged.

### Fixed (found by the gate and the review)
- Decimals kept only 15 digits in the log (timestamps changed on the way through).
- A later edit on another device could revive a deleted chat.

## [0.15.4] — 2026-10-11

Docs only.

### Added
- **D30**: build order Y1 → G1 → K7 → K14 → A3 → Y2; ROADMAP *Build order* section.
- ROADMAP step **K14**: meaning-based search (D10's later step, now numbered).

### Removed
- Roadmap step **K10** (git-backed vault), dropped by D30: the undo journal and the Y1 change log carry the history.

## [0.15.3] — 2026-10-11

Docs only.

### Added
- ROADMAP **Y1 plan**: seven parts (device identity, ID generator, synced vs this-computer-only list, change log,
  tombstones, migration, convergence check) with a check for each, and what keeps its current IDs.

### Changed
- ROADMAP: S3 marked passed (8 Oct); Phase 3b marked superseded by the sync track; Bookshelf track summary
  brought up to date.

## [0.15.2] — 2026-10-10

Docs only: the user's Y1 choices and a new roadmap step.

### Added
- **D28**: Y1 specifics: every record, existing ones included, gets a fresh ULID; changes are written to an
  append-only log alongside the current tables.
- **D29**: game mode: notice another program using the GPU on any vendor (no `nvidia-smi`), pause local jobs and
  unload the model, offer a micro model for light background work if it fits (with the user's OK), resume when the
  program closes.
- ROADMAP **shared hardware track** with step **G1** (game mode).

## [0.15.1] — 2026-10-09

Docs only: the sync architecture and a handoff for a fresh session.

### Added
- **D27**: "sign in on each device and everything just works" = a Sage account (passkeys) with end-to-end
  encrypted, local-first sync; what syncs and how; jobs routed to capable devices; a thin server; desktop and
  phone apps sharing one sync engine; what to change in the code now.
- ROADMAP **sync and devices track** Y0–Y6 (Y0 = D25, done).
- Handoff §0 rewritten for a new session (state, running jobs, next steps, what waits on the user, gotchas).

## [0.15.0] — 2026-10-09

Storage (D25) and any-model lead (D26, roadmap only). This PC's data moved from `sage-os/data/` to
`%APPDATA%\Sage OS` (644 files checked; the old folder kept as `data.moved-20261009-014252`); the textbook digest
resumed where it was. pytest 227/227, smoke 18/18.

### Added
- **App data** in the OS's app-data folder: databases, indexes, source copies, models, sign-ins. Per computer,
  never synced, untouched by updates. `python -m sage_os_hub move-data` moves an older install (copied, checked,
  old folder kept).
- **The Library**: `Notes/` (the markdown notes agents search) and `Files/` (any documents you drop in, indexed
  where they are, never copied). Point it at a OneDrive / iCloud / Dropbox / Syncthing folder and every device
  shares the same notes and files; moving it merges without overwriting.
- **STORAGE** tab in Bookshelf: open the Library, Notes, Files and app-data folders; export notes (and files) as
  a zip; move the Library; files a sync service kept twice (edited on two devices) are listed.
- **D26:** the lead (orchestrator) and reviewer are roles any connected model can hold, cloud or local;
  roadmap Phases 4–5 reworded.

### Changed
- `config.toml` no longer pins data paths; `[storage] data / library` go in `config.local.toml`.
- Tests run against their own app-data folder and their own `config.local.toml` (a storage test briefly wrote
  the real one during this build; caught and fixed before it mattered).

## [0.14.0] — 2026-10-09

K13, review note by note (D24), plus what a real textbook taught us. Gate: pass (tests; the review screen
checked in the browser at 1440×900 and 375×812 on a real 47-note card, nothing approved). pytest 219/219.
A 1,588-page accounting textbook (Kieso, *Intermediate Accounting* 18e) is being digested on the local model:
777 sections in 45 chapters, roughly 7–8 hours.

### Added
- **REVIEW** on every Bookshelf card: each note rendered as markdown, previous/next and keyboard, keep or drop
  per note, edit title / body / tags with a live preview (write/preview tabs on a phone), approve only what
  you kept. Edited notes are filed with `edited_by: user`; the agent's original proposal is kept.
- **Drive folders read through the API** (`[[sources]] api = true`): list, download, export Google Docs, with
  no Drive for desktop. The School folder is the first; it brought in the textbook before Drive for desktop did.

### Fixed
- Screening: rows of years ("2023 2024 2025") passed the Aadhaar checksum 16 times in the textbook and kept
  it out; three year-like groups are now years.
- Faulty PDF bookmarks: several on one page keep the chapter; a chapter bookmark pointing at the previous
  chapter's page is moved to where its title appears (the book's "Chapter 15" pointed at Chapter 14).
- The model server restarting no longer fails sections (they wait and retry).
- Prompts: material about the book itself (what's new, pedagogy, resources) counts as no study content.
- Long inbox cards list their files on request; new digests get readable titles.

## [0.13.0] — 2026-10-08

K12, long documents into notes (D23). Gate: pass. On the local Gemma 4 12B, unattended: the outreach
playbook (32 pages, no bookmarks) became 34 notes in one inbox card with 55/55 listed concepts covered
(about 4 min); the options lecture (55 pages, one bookmark per slide) became 12 notes, 36/36 (about 3.5
min). pytest 208/208.

### Added
- **Digest into notes** on any long document in Bookshelf → Sources: a preview of its chapters and sections,
  then the local model reads every section and writes notes; one inbox card per chapter.
- **DIGESTS** tab: every job with a coverage map (one square per section: waiting, being read, drafted, no
  study content, failed; an amber outline where a concept wasn't covered), pause / resume / cancel.
- Sections tile the document (checked); chapters from PDF bookmarks, headings or even chunks; concept
  coverage check with one follow-up call; earlier titles passed on and same-titled notes merged.
- EPUB books; Word, HTML and EPUB headings kept as markdown; PDFs and EPUBs up to 400 MB, 20M characters,
  no page cap (the next sync re-extracts everything once).

### Changed
- The local engine runs a 16K context per request and two request slots on a GPU (a chat doesn't wait
  behind a digest); replies are capped and a looping reply is retried warmer.
- Review fixes: digests of non-PDF documents read the whole text (not the first 50,000 characters); the
  worker is woken safely from other threads; proposal lookups take the writer's lock.

## [0.12.2] — 2026-10-08

Google Drive connector, first live run (S3 gate: **pass**). Connected read-only; 10 of 13 Google Docs in
the chosen folders exported and searchable, including the Acme pitch framework and the M&A target
briefing. pytest 197/197.

### Fixed
- Google Docs whose names (or folder names) contain characters a file name can't hold were "not found":
  Drive for desktop drops `/` and `:` ("Resume/CV" shows as "Resume CV"). Lookups now fall back to
  comparing names without punctuation.
- The OAuth client file is found under the name Google downloads it with (`client_secret_*.json` in
  `data/`), so it needn't be renamed.

### Known
- Three Google Docs under `Resume CV/Old Resumes` still aren't found in Drive (that folder may be a
  shortcut or shared from elsewhere).

## [0.12.1] — 2026-10-07

Security pass (vibe-security, against the D14 baseline) and copy pass on 0.12.0. pytest 196/196.

### Fixed
- **Local engine locked down.** llama-server's defaults (no key, CORS `*`, web UI on) let any web page
  you visit use the model and read its recent prompts, which carry your notes. It now starts with a
  fresh key per start (passed in the environment, never on the command line), no web UI and no CORS
  origin; only the hub knows the key. Checked live: requests without it get 401.
- An engine build is installed only if GitHub publishes its SHA-256.
- The Google sign-in tab can't reach back into Sage OS (`opener` cleared; only accounts.google.com URLs).
- `read_source` accepts a file name or a `sources/<name>/` prefix where small models put them, so their
  own reads stop failing.

### Known, not fixed (product work, D22)
- The Google refresh token (read-only Drive) is a plain file in `data/`; an installer should use the OS
  keychain. Cloud API keys come from environment variables; no spending cap beyond 8 tool rounds per
  message.

## [0.12.0] — 2026-10-06

D22 scope (a shippable app for anyone with several AIs and scattered notes) and three steps toward it,
bundled in one version because they were built for the same demo: **K8** briefing packs, **A5** Sage
OS's own local engine with a chat for any OpenAI-compatible AI, and **S3** the Google Drive connector.
Gates: K8 pass (local Gemma 4 12B answered from the outreach playbooks, both shown in the Reading strip);
A5 partly (engine ran a model already on disk; downloads tested offline only); S3 built, not run live
(needs the user's OAuth client). pytest 193/193, smoke 18/18.

### Added
- **Briefing packs (K8, D20):** each message is searched against notes and sources (key terms picked
  out and weighted by rarity; collection notes and duplicate copies skipped) and the best matches go
  with it, marked as data. A *Reading* strip under the message lists them and whatever the agent opened
  itself; ✕ leaves an item out of later packs and tells the agent (stopping and resending if it is still
  answering); 📖 turns packs off per chat. Every pack is recorded (`data/briefings.db`).
- **Local engine (D22.3):** MODELS screen with a hardware check, a catalog of 8 models (2–22 GB) rated
  *fits / tight / too big* for this machine, install of the official llama.cpp build for this OS and GPU
  and model downloads from Hugging Face (resumable, SHA-256 checked), models already on disk, start/stop.
  A llama-server left running by a killed hub is stopped on the next start.
- **Chat connector (D22.2):** one chat for any OpenAI-compatible AI (the engine, ChatGPT, Gemini,
  Ollama), with the Bookshelf tools as function calls run by Sage OS. Chat tab in the Local pane.
- **Google Drive connector (S3, D22.5):** Google Docs, Sheets and Slides exported through the Drive API
  with read-only consent (the user's own OAuth client, PKCE) and indexed like any other file.
- Decision **D22**; the Deal Club folder is now in the source copy (63 more files); a list of other
  people's contact details is excluded.

### Changed
- Config files saved with a byte-order mark (Notepad, PowerShell 5) now load.
- D21's "PC as home base" is superseded by D22 (every device runs Sage OS; notes sync).
- README describes the product for its D22 audience; Hermes is optional in the "Needs" list.

## [0.11.1] — 2026-10-03

Docs only: handoff for a fresh session.

### Changed
- `SAGE-OS-HANDOFF.md` gains **§0 Start here**: current state, next steps in order (K8, 3b, S2),
  what waits on the user, how the user wants work done, and gotchas from 1–3 Oct. Open questions 4,
  5, 6 and 9 marked answered (D9, D11, D16, D17, D21).
- `CLAUDE.md` at the repo root points any Claude session (PC or Mac) to the handoff and the work rules.

## [0.11.0] — 2026-10-03

Phase 3a, portable hub (D21). Gate: the same repo starts on macOS and Windows; checked here on
Windows (pytest 170/170, smoke 18/18, Claude CLI still found and signed in); the Mac run is the
user's check.

### Added
- `config.local.toml` (untracked) is read over `config.toml`: tables merge key by key, `[[sources]]`
  and `[[models]]` are replaced whole. `config.local.example.toml` shows a Mac setup.
- `start.sh`: launcher for macOS and Linux.
- Decisions: **D21** (PC as home base, Mac and phone as screens, passkeys, and the direction for a
  downloadable product) and the **D20 amendment** (✕ on any briefing item to correct an agent before
  it runs on wrong information).

### Changed
- `~` works in every path setting, and relative paths are relative to the sage-os root everywhere.
- The Claude CLI is found on macOS (desktop app, `~/.claude/local`, `~/.local/bin`, PATH) as well as
  Windows; the smoke check reads "claude CLI found".
- Hermes' default home is `%LOCALAPPDATA%\hermes` on Windows and `~/.hermes` elsewhere.
- ROADMAP: Phase 3 split into 3a (portable hub, built) and 3b (phone and Mac as screens: Tailscale +
  passkeys); the product track records D21's direction.

## [0.10.1] — 2026-10-03

Docs only (planning).

### Changed
- **OCR becomes step S2** (DECISIONS D19): 37 images and 16 scanned PDFs (about 11% of the Drive
  copy) are unreadable today; Windows' built-in OCR first.
- **K8 briefing packs redefined** (D20): chosen per prompt from notes and sources, shown in a
  *Reading* strip together with everything the agent reads while answering.
- ROADMAP: A2 marked done with K1–K3; the stale interleave note replaced.

## [0.10.0] — 2026-10-03

Demo readiness (D18): the app now explains why it exists and how to use it. Gate: the user's demo
(docs/DEMO.md); checked here: pytest 165/165, UI build clean, smoke 18/18, guide and tour run at
1440×900 and 375×812 with no sideways scroll, the citation link opens Sources (throwaway hub).

### Added
- **Guide** (**? GUIDE** in the top bar; opens by itself on a first visit, or with `?guide` in the
  URL): what a team needs and where it is in Sage OS (D1), the four rules (D4, D6, D11, D15) and the
  limit (D4), plus a live line of notes, source documents and items waiting for you.
- **Tour**: seven steps that spotlight each panel with two sentences on what it does. Arrow keys or
  Enter to move, Esc to leave; on a phone the cards are centred.
- **How notes get here**: an empty Bookshelf shows the four-step path (Sources → Build notes → Inbox
  → Bookshelf) and a button to start, and says when proposals are already waiting in the inbox.
- **Built from:** a note shows its `source:`; a cited file opens in Sources.
- `docs/DEMO.md`: a 5–7 minute demo script with a prep checklist and fixes for what can go wrong.

### Changed
- Panel labels say what each panel is (*Lead agent · Answers by default*, *Inbox · Needs you*, …)
  instead of "Panel / Orchestrator". Top-bar lights read **HERMES · MODELS · GUARD**; ports moved to
  the tooltip.
- Every control shows a focus ring when reached by keyboard.

### Fixed
- The browser could keep serving the previous UI build after an update (index.html was cached
  heuristically); the page now revalidates on every load. One Ctrl+F5 is needed the first time.

### Fixed (review, 3 Oct)
- Reading a note returned the whole file under `source`, hiding its citation; `/api/vault/note` now
  returns the citation as `source` and the file as `text`, and the agents' `read_note` includes
  `source` so they can follow it with `read_source`.
- On a first visit the key that skipped the boot screen also dismissed the guide; the guide now
  waits for the boot screen. Enter on a focused tour button does what that button says.
- The tour spotlight follows layout changes (panels sliding in, the top bar wrapping).
- *Built from* tells folders from files by the collection tag, not by guessing from an extension.

## [0.9.0] — 2026-10-02

Gate: K6 pass (redefined, D17) — from the Drive source alone, Sage OS proposed 51 starter notes in 9
inbox cards (25 collections, 26 markdown files), nothing written before approval; Hermes, briefed by
*Draft*, read four FIN 101 documents with `read_source` and proposed 5 cited concept notes. Checks:
pytest 164/164, UI build clean, smoke 18/18. Reviewed with `/code-review` (8 findings, all fixed),
vibe-security (2 findings, fixed) and no-ai-slop (template copy).

### Added
- **Notes from your sources (K6, DECISIONS D17):** Bookshelf → Sources → *Build notes*.
  *Propose starter notes* turns a source into proposals, one inbox card per area: markdown files
  become notes with your text verbatim (`origin: imported`, folder structure kept under the
  source's `notes_folder`), and every folder of documents gets a **collection note** listing each
  document with how it starts (slide titles for decks), its source path, and the folder's distinctive
  terms (tf-idf against the whole source). Nothing is summarised or invented. *Draft* asks an agent
  (Hermes by default) to read a collection with `read_source` and propose 3-6 concept notes that cite
  their documents and link the collection note. Every note records `source:`, so re-runs skip what's
  built or waiting. Tiny folders roll up into their parent; code `src/` folders count as their project.
- Notes and proposals can carry `source:` (a vault-relative citation, e.g. `sources/drive/...`);
  updates can set it too. Only Sage OS's importer may mark notes `origin: imported`
  (`imported_by: sage-os:importer`); everyone else is `origin: agent`.
- `[[sources]]` gains `notes_folder` and `strip` (leading folders dropped from vault paths).

### Changed
- The Drive source also excludes `Documents/Card statements` (card statements named by date, which the
  name rules missed).
- Proposal refusals carry a machine-readable `code` (`inbox_cap`); agent names starting with
  `sage-os:` are reserved and refused on `POST /api/vault/proposals`.

### Fixed (review, 2 Oct)
- A collection's status now covers its markdown notes too (new markdown in a built folder can be
  proposed; markdown-only folders no longer stay "new" forever).
- `/api/sources/{name}/draft` answers 409 when the agent is busy (was 502).
- Building starter notes scans the vault once and reads each document's words once.

## [0.8.0] — 2026-10-01

Bundles two roadmap steps, because K5 was never released on its own: **K5** (Bookshelf tools for
agents) and **S1** (source library). Gates: K5 pass — Claude and Hermes each searched, read and
proposed through MCP on the real hub; S1 pass — 499 files from the chosen Drive folders copied and
indexed in 4½ min with Drive untouched (0 files modified), 9 private-looking files held back, a query
answered in 3.7 ms. Checks: pytest 157/157, UI build clean, smoke 18/18.

### Added
- **Bookshelf tools for agents (K5, DECISIONS D16):** `search_notes`, `read_note`, `propose_note`,
  `list_proposals` (and the source tools below). Claude gets them as an in-process MCP server in
  every Sage OS session (agent id `claude:<session>`, no permission prompt: proposals already wait in
  the inbox); other agents over MCP Streamable HTTP at `/mcp/<vendor>/<name>/`, the path fixing the
  agent id. Hermes `default` is connected (`mcp_servers.bookshelf` in its `config.yaml`, backup
  `config.yaml.bak-pre-bookshelf-mcp`). A note that looks sensitive returns metadata but not text.
- **Source library (S1, DECISIONS D15):** read-only copies of chosen folders in `data/sources/<name>`
  (`[[sources]]` in config.toml), synced one way on demand, text extracted (PDF via pypdf, Word,
  PowerPoint, Excel, notebooks, HTML, code, transcripts) into `data/sources-index.db`. Private-looking
  files are never copied: by name (tax return, W-2, pay stub, passport, statements…) or by content
  (K4 screener); they're listed by path only. Bookshelf **Sources** tab: sync status, Sync now, Open
  copy, the left-out list, search, and a text reader; agents get `search_sources` / `read_source`.
  First source: Google Drive coursework, resumes and the MacBook folders.
- New dependency: pypdf.

### Fixed
- Hermes refuses duplicate session titles, so every "+ new chat" after the first failed with a 502;
  titles are now numbered ("Sage OS chat 2") and Hermes' own error message is shown.
- (during S1) Spreadsheet cells were glued together and decimal fractions (e.g. `99.9999999999999`)
  passed the card/ID checksums, holding back 36 coursework files as "private"; cells are now
  tab-separated, digit runs next to a decimal point are ignored, and an extractor version forces
  re-extraction when this changes.

### Changed
- Copy pass with the no-ai-slop skill: README intro and "Today" paragraph untangled; MISSION drops
  filler em dashes, a "not X but Y" line and a colon reveal; UI text no longer promises shipped work
  as future ("coming in K3", "arrives in Phase 2"), says "note format" instead of "vault contract",
  and loses its prose em dashes. `config.toml` header no longer claims Phase 1 is read-only.

### Security (vibe-security audit, 1 Oct; DECISIONS D14)
- **High — fixed:** any `*.ts.net` origin was trusted, so a page published with Tailscale Funnel could
  open the hub's WebSocket and read its state (inbox, transcripts, note diffs). Now only localhost and
  host names listed exactly in `[hub] remote_hosts` (empty until Phase 3); wildcards are refused.
- **Medium — fixed:** no security headers — the inbox could be framed and click-jacked into *Approve*
  or *Save anyway*. Added CSP (`frame-ancestors 'none'`, same-origin scripts/connections, no remote
  images), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`; `/docs` and
  `/openapi.json` removed.
- **Medium — fixed:** agent markdown in the chat panes auto-loaded remote images (a prompt-injected
  reply could beacon data out); now shown as `[image: …]` like Bookshelf.
- **Medium — fixed:** note text handed to agents through Bookshelf tools is labelled as data, not
  instructions (indirect prompt injection); Claude's system prompt says the same.
- **Medium — fixed:** one agent could fill the inbox with proposals (300 in a burst); now at most 25
  waiting and 10 held per agent.
- **Low–Medium — fixed:** Claude sessions could start in any folder (e.g. `C:\Windows`) via the API;
  now only `[claude] workspaces`. Hermes session ids from the browser went unchecked into gateway URLs
  (`../` changed the endpoint, sent with the Hermes key); now plain ids only.
- **Low — fixed:** guard-log commands that look like they carry a secret are hidden before they reach
  the safety feed and `hub.db`; `.env` files ignored by git.

### Added
- **Git guardrails for Claude Code** (`.claude/settings.json` + `.claude/hooks/git_guardrails.py`,
  user request 1 Oct): a PreToolUse hook blocks `git push`, `reset --hard`, `clean -f`, `branch -D`,
  `checkout .` / `restore .` and edits to the guardrails themselves, for Bash and PowerShell. Removal
  only via `git_guardrails.py remove`: it explains the change, then needs `REMOVE` typed in a real
  terminal. Adapted from Matt Pocock's git-guardrails skill (Python instead of jq). 33 tests
  (`hub/tests/test_git_guardrails.py`). DECISIONS D13.

## [0.7.0] — 2026-10-01

Gate: K4 pass — on the scratch hub two proposals carrying a fake API key were held (HTTP 202, value
never echoed); a byte search of every file the hub keeps (hub.db, journal, index, vault, log) found
the key nowhere. Manual override (user request): one held card *Rejected*, the other *Saved anyway*
after a two-step confirm — filed, recorded as `screened = a password or key`, its text kept out of
search, the key present only in that note and the undo journal. Checks: pytest 95/95, UI build clean,
smoke 17/17.

### Added
- **Secret screening (K4, BookShelf I4):** `knowledge/screen.py` checks everything a proposer sends
  (title, body, tags, links, folder, type, status, summary, agent id) before anything is stored:
  private keys; Anthropic, OpenAI, GitHub, AWS, Google, Slack and Stripe tokens; JWTs; URLs with a
  password; `password:` / `API_KEY=` style assignments (placeholders and code like `os.getenv(...)`
  ignored); Luhn-valid card numbers; US SSNs; Aadhaar (Verhoeff checksum); IBANs (mod-97). Only a
  coarse category is ever reported or logged ("a password or key"), never the value.
- **Manual override (*Save anyway*):** a screened proposal is **held** in the inbox — in memory only,
  nothing on disk, dropped by a hub restart — with *Reject* or *Save anyway* (two clicks, with a
  warning). Content is hidden behind *Show content*. Saving anyway stores and files it in one step and
  records the category in the proposal's new `screened` column and a `proposal.override` event. Only
  the user can override; agents get `202 held` back. (DECISIONS D12)
- Notes already in the vault that look sensitive (e.g. dropped in by hand) stay in the file but their
  text is left out of the search index; Bookshelf marks them 🔒. Index schema 2 forces a rebuild so
  older indexes drop such bodies.

### Changed
- `POST /api/vault/proposals` answers `202 {"status": "held"}` for screened proposals (was going to
  be a plain refusal); invalid ones still get 400.

## [0.6.0] — 2026-10-01

Gate: K3 pass — on a 2,006-note scratch vault a proposal from `claude:cs_k3live` (create a note +
retag another) changed nothing until *Approve & file* in the inbox; *Undo* in Bookshelf History then
returned the whole vault to the identical SHA-256 fingerprint. Checks: pytest 53/53, UI build clean,
smoke 17/17.

### Added
- **Bookshelf writes (K3):** agents *propose* changes (create a note, update one by uid, archive one
  into `Archive/`); the proposal is checked and rendered first, then waits in the **inbox** with each
  change's diff (*Approve & file* / *Reject* + note). A **single writer** applies an approved proposal
  as one batch, journal-first with exact before/after bytes in `data/bookshelf.db` (`[bookshelf]
  journal`); a failure part-way rolls back, and a crash is rolled back at the next start. **Undo**
  restores a batch byte for byte and refuses if a file was edited since. Proposals against notes
  edited after proposing are refused at approval. Pending proposals survive a hub restart.
- Provenance: notes agents create carry `origin: agent` + `agent: <id>`; agent edits to other notes
  add the agent to `edited_by` (vault contract v1.1, DECISIONS D11).
- Updates rewrite only the frontmatter keys they change; comments, quoting, list style and unknown
  keys stay byte for byte.
- Routes `POST /api/vault/proposals`, `GET /api/vault/proposals`, `GET /api/vault/history`,
  `POST /api/vault/batches/{id}/undo`. UI: inbox cards for proposals with per-change diffs; a
  Bookshelf **History** tab with two-step Undo.

### Fixed (during K3)
- Two new notes with the same title in one proposal would both have been named `-2` (the second
  overwriting the first); caught by a test before release.

## [0.5.0] — 2026-10-01

Gate: K2 pass — on a 2,006-note vault every query returned ranked notes in at most 12 ms (13 ms round
trip) against a 300 ms target; from-cold indexing took ~12 s. Checks: pytest 39/39, UI build clean,
smoke 17/17.

### Added
- **Bookshelf search (K2):** SQLite FTS5 index at `data/bookshelf-index.db` (`[bookshelf] index`), a
  rebuildable cache outside the vault (DECISIONS D10). Ranked by BM25 with title > tags > body; English
  stemming plus prefix matching, so "valuing" finds "valuation" and "disc cash" works as you type;
  snippets mark the matches. The vault watcher keeps it in step, re-reading only changed notes.
- Routes `GET /api/vault/search?q=&archived=&limit=` and `POST /api/vault/reindex` (rebuild from cold,
  write-guarded); smoke check that the index opens; the Bookshelf panel reports `indexed`.
- UI: the Bookshelf filter box is now search-as-you-type with highlighted snippets, match count and
  timing; archived notes only when the archive box is ticked.

## [0.4.0] — 2026-10-01

Gates: A1 pass (30 Sep) · K1 pass (1 Oct). Checks: pytest 32/32, UI build clean, smoke 16/16.

### Added
- **Connectors (architecture step A1):** `AgentConnector` and `ModelProvider` interfaces in
  `hub/sage_os_hub/connectors/`; Claude Code and each Hermes profile are now connectors, and the
  Hermes llama.cpp router plus any `[[models]]` entry are model providers (keys only from environment
  variables or Hermes' own file, never config or the browser). New `config.toml` `[agents]` section
  (`lead`, `claude`, `hermes`), routes `GET /api/agents`, `GET /api/models` and
  `/api/agents/{id}/sessions/...`; per-agent smoke checks (Hermes API key, per-turn model pin, lead
  agent connected). Old `/api/claude/...` and `/api/hermes/...` routes kept for the current panes.
- **Bookshelf reader (K1):** vault at `data/vault` (`[bookshelf] vault`), created with only `Archive/` and
  `Attachments/`. `knowledge/` reads notes and checks them against vault contract v1 (DECISIONS D9);
  a watcher republishes the vault when files change. Top-bar BOOKSHELF opens a reader (folders,
  filter, rendered/source view, links by uid, agent-written label, contract problems) with an
  **Open vault** button. Routes `GET /api/vault`, `GET /api/vault/note?ref=`, `POST /api/vault/open`
  (opens only the configured folder). New dependency: PyYAML.

### Changed
- Docs: broadened product framing to match the GitHub description (agent hub with a personal,
  growing knowledge base; choice of local and cloud models; many programs in one hub; workflow kanban
  boards). Roadmap gains a hub-breadth track (H1–H4).
- Docs: new decision log `docs/DECISIONS.md` (D1–D5 + proposed Bookshelf ideas P1): personal-scale
  multi-agent team goal; BookShelf retired and rebuilt as a Python package in this repo; new local
  vault, Drive read-only; agents and models plug in, Sage OS owns the core, no custom llama.cpp
  runtime; Hermes kanban contents disposable. Roadmap gains an architecture track (A1–A5).
- Docs: D6 vault inside the app's data folder (`data/vault/`) with an Open vault button; future
  markdown editor noted. D7 adopted Bookshelf ideas 1, 2, 3, 5, 6, 8 (personal only), 9, 10;
  roadmap gains K8–K11.
- Docs: D8 chat layout — team chat with a user-chosen lead agent, agent-only room with Step in,
  direct chats closed by default; Phase 6 updated.

## [0.3.0] — 2026-09-30

### Added
- **Visual pass:** phosphor-green theme (default) with Tron and eDEX-amber alternatives; eDEX-style
  notched panel tabs, corner brackets and panel captions; reactive dot-grid background with event ripples.
- **Agent orbs:** WebGL dot spheres per agent (Claude amber-orange, Hermes green) driven by live state
  (idle, thinking, streaming, tool call, waiting, error); in-shader bloom; low-power mode above
  14.5 GB VRAM; lazy-loaded three.js.
- **Handoff arcs** between orbs and panels for kanban delegation, worker start/finish and blocks.
- **Doto** dot-matrix font for clock and attention items; boot screen ("SAGE: Semi-Autonomous Agent
  Ground Environment") with live system checks; constant scanlines, film grain and refresh bar.
- **Motion** setting (full / auto / reduced).
- S-trail-with-sage-leaves app icon (`ui/public/favicon.svg`).
- Hermes **runtime pin**: provider + model + `require_model_lock` on every sessions-API turn, fixing
  turn-2+ HTTP 401s.
- Claude login check (`claude auth status`) with an in-pane sign-in banner; `/login` intercepted.
- Docs: MISSION, ROADMAP, STATUS, SAGE-OS-HANDOFF, this changelog.

### Changed
- **Renamed Agent OS → Sage OS**: folder `sage-os`, package `sage_os_hub`, header `X-Sage-OS`,
  env vars `SAGE_OS_*`, logo `SAGE//OS`.
- Layout: Claude pane is the largest panel; Hermes and inbox share the side column; full-width board.
- Safety feed moved from a permanent rail to a drawer with chip and toast.
- Claude "spend" replaced by subscription usage meter.
- Hermes is the single profile `default`, labelled "Hermes" (the `sage` profile was retired and archived).
- Health polling 2 s → 5 s (it writes access-log lines into Hermes' `agent.log`).

### Removed
- CRT mode (curved glass, bezel, power-on/off animation) — replaced by the constant screen texture.

### Fixed
- `claude.exe` discovery for the Store (MSIX) build of Claude Desktop.
- Claude pane hidden at medium widths (container-query layout).

## [0.2.0] — 2026-09-29

### Added
- Claude Code pane via the Claude Agent SDK; tool permission requests routed to an **approvals inbox**
  (allow once / for session / deny with note). Gate passed: approve and deny both verified.
- Hermes chat pane via the gateway sessions API (SSE).
- Inbox items for Hermes run approvals and kanban `needs_input` blocks (reply + unblock via CLI).
- Write routes guarded by `X-Agent-OS` header + local Host/Origin; RAM gauge; usage meter.

## [0.1.0] — 2026-09-29

### Added
- Read-only hub (FastAPI + WebSocket + SQLite store) with adapters for the Hermes kanban board,
  sessions, llama.cpp router/GPU, service health and the guardian/write-guard logs; startup smoke test.
- React + Vite + Tailwind UI with Tron theme, desk and phone layouts.
- Gates passed: CLI task visible in 4.8 s, model swap in 0.3 s, guard block in 0.3 s, router
  down/up detected.
