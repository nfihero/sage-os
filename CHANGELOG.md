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
