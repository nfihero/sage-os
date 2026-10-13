# Sage OS — decision log

One entry per decision, newest last. Each records what was decided, why, what it costs, and when to
revisit, so a decision can be reversed knowingly instead of by drift. To change one, add a new entry
that **supersedes** it and update the old entry's status; don't edit history away.

Status values: **accepted** (decided, acts as the plan) · **proposed** (written up, awaiting the user)
· **superseded by Dn**.

Older reversals made before this log existed are in `SAGE-OS-HANDOFF.md` §7.

---

## D1 — Product goal: a personal-scale multi-agent team

- **Date / by:** 2026-09-30, user
- **Status:** accepted
- **Decision:** Sage OS is a one-stop hub for **agent management and environment setup**. The goal is
  to bring the productivity of multi-agent teams used in businesses down to personal scale. Users
  connect whatever AI they already use.
- **Model used to reason about it:** a business team works through a shared wiki, a task board and a
  manager who signs off. In Sage OS those are Bookshelf, the board, and the approvals inbox.
- **Consequences:** anything that forces one specific agent app on every user is a liability (see D4).
- **Still open:** exact audience (people like the founder — students and solo builders with a local
  GPU — or broader). Doesn't change near-term work.

## D2 — BookShelf is retired; its idea becomes Sage OS's Bookshelf module

- **Date / by:** 2026-09-30, user
- **Status:** accepted. Supersedes the "proposed" framing of handoff §7 #16 and answers handoff §9 Q1.
- **Decision:** The BookShelf project (`nfihero/BookShelf`, Swift/macOS) is scrapped as a product. Its
  docs (DESIGN.md, invariants I1–I9, vault contract) are the **spec**; none of its code is reused.
  The knowledge base is rebuilt **inside the `sage-os` repo as a Python package of the hub** (working
  name `hub/sage_os_hub/knowledge/`), sharing the hub's venv, tests and release.
- **Why:** one repo, one install, one test suite; Python matches the hub, runs on Windows, and gets
  SQLite FTS5 search from the standard library.
- **Costs:** BookShelf's type-level guarantee for I1 (`ApprovedChange.init` is `internal`) has no
  Python equivalent; it is replaced by a process boundary — agents get only read + propose tools, a
  single writer applies changes only with an approval minted by the inbox.
- **Carry-overs to remember:** BookShelf's single-writer JSON journal raced under concurrent writers
  (its P5) — use a serialized write queue + SQLite journal. Its I7 ("app never authors note content")
  becomes "agent-written notes are always labelled `origin: agent` + agent id".
- **Revisit if:** the module needs to run without the hub (e.g. as a standalone MCP server for other
  tools) — then split it into its own package, not its own product.

## D3 — Vault: new, local, not on Google Drive

- **Date / by:** 2026-09-30, user (facts); location proposed by Claude
- **Status:** accepted; location superseded by D6, Drive indexing not adopted (D7)
- **Facts from the user:** there is no main vault today; no vault is synced by Google Drive; the
  user's personal files are synced by Drive (`G:\`).
- **Decision:** start a fresh Sage OS vault on local disk. Existing notes (`Obsidian Vault`,
  `llm-vault`) come in through the normal approval flow (K6), not by pointing Sage OS at them.
  `G:\` stays read-only to agents: indexed as a source library that notes can cite, never written.
- **Costs:** a local-only vault has no backup. Proposed fix: git-backed vault (each approved batch a
  commit; push to a private remote only when the user chooses) — not yet decided.
- **Answers:** handoff §9 Q2 and Q3.

## D4 — Agents and models plug in; Sage OS owns the core; no custom llama.cpp runtime

- **Date / by:** 2026-09-30, user (recorded "for now", expected to evolve)
- **Status:** accepted. Refines handoff §7 #10 ("keep Hermes"): Hermes stays in use, but is no longer
  a required part of Sage OS.
- **Decision:**
  1. **Don't build our own llama.cpp runtime.** `llama-server` already provides an OpenAI-compatible
     API and model routing; rewriting it adds nothing users see.
  2. **Models:** Sage OS talks to any OpenAI-compatible endpoint (llama.cpp, Ollama, LM Studio, cloud
     APIs). As part of environment setup it may *install and manage* `llama-server` for users with
     nothing yet — manage, not rewrite.
  3. **Agents:** each agent is a connector behind a Sage OS interface — Claude Code (exists), Hermes
     (exists, now optional), others later (Phase 6 ACP / A2A).
  4. **Sage OS owns the core:** task board, approvals inbox, Bookshelf, safety policy, and the shared
     tools agents use to reach them.
- **Why:** "connect whatever AI you use" fails if every user must install Hermes; Hermes updates
  broke local customisations 4+ times in Sep 2026 and multi-turn chat relies on a workaround over
  Hermes internals (`HermesAPI._runtime_pin`); and the board and safety rules are core product but
  are owned by Hermes today.
- **Honest limit:** Sage OS can enforce safety only on what passes through it (permission prompts,
  its own tools). An external agent's own shell commands stay under that agent's safeguards (Claude
  Code permissions, Hermes guardian). The product must say so rather than promise full control.
- **What Hermes gives today that must be replaced or kept as a connector:** local agent loop, kanban
  + dispatcher, guardian + write guard, gateway sessions API, router presets.
- **Unverified (check before relying on them):** which other agent tools work reliably on Windows;
  whether a Sage OS board can replace everything the Hermes kanban does.
- **Plan:** architecture track A1–A5 in `ROADMAP.md`.
- **Revisit if:** another harness turns out to be the better default local agent, or Hermes'
  update churn stops.

## D5 — Hermes kanban contents are disposable

- **Date / by:** 2026-09-30, user
- **Status:** accepted, **not executed**
- **Decision:** nothing important is on the Hermes kanban board today, so it can be cleared when the
  Sage OS board (A3) replaces it; no migration tool is needed for current tasks.
- **Note:** clearing is destructive — do it only as an explicit step with the user's go-ahead, and
  first note any task output worth keeping (e.g. the budget-tracker parser, task `t_549737c1`).

## D6 — The vault lives inside Sage OS's own data folder

- **Date / by:** 2026-09-30, user (Claude chose the exact path)
- **Status:** accepted. Supersedes D3's proposed `C:\Users\you\SageVault`.
- **Decision:** the vault is part of the app's files: **`sage-os\data\vault\`**, next to `hub.db`.
  `data/` is already git-ignored, so notes never enter the code repo. The path is a `config.toml`
  setting (`vault = "data/vault"`, relative to the sage-os folder like `store`), not hard-coded.
- **"Open vault" button** in the Bookshelf view opens the folder in Explorer, so the user always knows
  where the notes are. (BookShelf's lesson: a contained vault in a hidden app folder left users
  unsure where their data was.) Interpreted as "show the folder", not "switch to another vault" —
  BookShelf removed its folder picker on purpose (its HANDOFF §4.1); revisit if a vault switcher is
  wanted.
- **Costs / notes:** a reinstall or a fresh clone that deletes `data/` would delete the vault — the
  git backup (D7, idea 8) covers this for the user. For a shippable product, app data should move to
  a per-user folder (e.g. `%LOCALAPPDATA%\SageOS\`) so updates can never touch it; the config setting
  makes that a one-line change.
- **Future: in-app markdown editor** — considered, not planned yet. If built, edits made in the app
  are human edits (allowed by BookShelf's I7 intent) but must still go through the single writer and
  journal (I2, I9) so they're undoable.

## D7 — Bookshelf integration ideas adopted from P1

- **Date / by:** 2026-09-30, user
- **Status:** accepted
- **Adopted:** 1 shared team memory · 2 briefing packs · 3 work becomes knowledge · 5 roles with
  per-agent trust levels · 6 one inbox for note proposals · 8 git-backed vault (**for the user's own
  install only**; a shippable product needs its own backup design, undecided) · 9 BookShelf's safety
  rules · 10 Ask with citations (later).
- **Not adopted for now:** 4 playbooks as notes · ~~7 Drive as an indexed source library~~ (adopted
  on 1 Oct as the source library, D15; `G:\` itself stays read-only and outside the vault).
- **Revisit if:** environment-setup work needs shared how-tos (idea 4), or agents keep needing Drive
  documents they can't search (idea 7).

## D8 — Chat layout: team chat + agent room; direct chats closed by default

- **Date / by:** 2026-09-30, user (shape proposed by Claude)
- **Status:** accepted; build after A1 and Phase 4 (refines Phase 6 "Rooms")
- **Decision:** the main screen has **two chat areas**:
  1. **Team chat** (central): the user and the agents. A **lead agent answers by default** — chosen
     by the user in settings (the user's choice: Claude). Other agents post only when @mentioned,
     assigned a task, or reporting a result or question.
  2. **Agent room**: agents talk to each other (handoffs, questions, results, reviews); the user
     watches. Messages are structured and linked to board tasks so the room reads like a log and can
     be filtered by task. A **Step in** button moves a thread into team chat so the user can take
     over.
  - **Direct chats** (one user + one agent; today's Claude and Hermes panes) stay available as an
    openable space, **closed by default**.
  - The **inbox stays separate**; chat messages link to their inbox cards, approvals never live in
    chat.
- **Why:** mirrors a business team (team channel + back-office channel); one default responder
  avoids noise and a queue of local replies behind one GPU model.
- **Guardrails required:** per-thread turn cap, no-progress (loop) detection, per-thread usage meter;
  messages from other agents are **untrusted input** (like web content) and can never waive an
  approval.
- **Open details:** where the lead-agent setting lives (global vs per board); what the agent room
  shows while only one agent is connected; layout on a phone (Phase 3).
- **Revisit if:** the lead agent becomes a bottleneck (e.g. routing by topic or task instead).

## D9 — Vault contract v1

- **Date / by:** 2026-10-01, Claude while building K1 (from BookShelf DESIGN §11 + D2); open to change
- **Status:** accepted. Changes to it are breaking changes for existing vaults — version them.
- **Contract:** BookShelf's vault contract carried over, with these Sage OS changes:
  - Notes are `<slug>.md` (lowercase ASCII, hyphens) with YAML frontmatter. **Required:** `uid` (ULID,
    immutable identity), `title`, `created`, `updated`, `type`, `status`, `origin`. **Optional:** `tags`,
    `links` (a list of uids), `attachments`, `source`. Unknown keys pass through untouched.
  - `origin` is one of `human`, `imported`, `scanned`, `captured`, **`agent`**; `origin: agent` also
    requires `agent: <id>` (e.g. `claude:<session>`, `hermes:default:<session>`) — D2's replacement for
    BookShelf's I7.
  - `Attachments/` holds originals and is not scanned for notes; `Archive/` holds retired notes (listed
    as archived, nothing is deleted); folders starting with `.` are ignored, so Obsidian's `.obsidian/`
    and a future `.bookshelf/` (rules, taxonomy — BookShelf's `.llm-wiki/`, renamed) can live inside.
  - No absolute paths anywhere in frontmatter or links (I8).
- **Reading rules (K1):** notes that break the contract are **listed with their problems named**, never
  hidden or silently fixed. The UI addresses a note by its uid; only a note without a valid, unique uid
  falls back to its vault-relative path. Images and wikilinks render as plain text for now (no
  attachment serving yet; BookShelf's open question 11.1, wikilinks vs uids, is still open).
- **The app writes no notes on its own** — `ensure()` creates only `Archive/` and `Attachments/`.

## D10 — Search index: keyword search (FTS5) as a cache outside the vault

- **Date / by:** 2026-10-01, Claude while building K2; open to change
- **Status:** accepted
- **Decision:** Bookshelf search is SQLite FTS5 (porter stemming, unicode, diacritics folded) in
  `data/bookshelf-index.db`, next to the vault, never inside it. It is a **cache** (BookShelf I3):
  delete it and the hub rebuilds it from the notes; `POST /api/vault/reindex` rebuilds on demand.
  Ranking is BM25 with weights title 10 · tags 5 · body 1. Every query word must match, as a whole
  (stemmed) word or as a prefix. Archived notes are left out unless asked for.
- **Why:** stdlib-only, fast (≤ 12 ms on 2,006 notes), works with no model running (BookShelf I6).
- **Costs / not yet:** this is keyword search, not the meaning-based search BookShelf's DESIGN §6 asks
  for. Semantic search needs an embedding model and BookShelf's `Embedder` seam (its open decision 11.6)
  — revisit before Ask (K11) or briefing packs (K8), which benefit most. Screened-sensitive content
  (I4): since K4 (D12) a note whose text looks secret is indexed by title and tags only, whether an
  agent or the user put it there.
- **Revisit if:** keyword results miss notes the user expects (e.g. synonyms), or the vault grows past
  ~20k notes (re-measure indexing time).

## D11 — How agents write to the vault: proposals, one writer, a journal

- **Date / by:** 2026-10-01, Claude while building K3 (from BookShelf I1, I2, I9 and D2); open to change
- **Status:** accepted. Amends D9: vault contract **v1.1** adds the optional key `edited_by`.
- **Decision:**
  - Agents never write files. They submit a **proposal** (1–50 changes: `create`, `update` by uid,
    `archive` = move under `Archive/`). It is validated and rendered at once — a proposal that would
    break the vault contract is refused and never reaches the inbox.
  - The proposal waits in the **Sage OS inbox**; *Approve & file* is the only path to the vault (I1).
    No HTTP route writes notes; the agent tools in K5 will offer propose/read only.
  - A **single writer** (one lock) applies the whole proposal as one batch or nothing (I9): plan and
    check everything, write the journal (exact before/after bytes) first, then the files via temp
    file + atomic rename; roll back on failure; `recover()` at startup rolls back a batch a crash
    interrupted.
  - **Undo** is per batch and byte-exact (I2); it refuses if any file changed since, rather than
    overwrite the user's edit. There is no redo yet.
  - **Stale protection:** an update/archive remembers the note's SHA-256 when proposed; approval is
    refused if the note changed since.
  - **Provenance (replaces BookShelf I7):** created notes get `origin: agent` + `agent: <id>`; when an
    agent edits a note that isn't its own, its id is added to `edited_by`; `origin` never changes.
  - **Minimal edits:** an update rewrites only the frontmatter keys it changes; other lines stay
    byte for byte. If the result wouldn't read back exactly as intended, the frontmatter is rewritten
    whole instead (correctness over formatting).
  - The journal (`data/bookshelf.db`) is not a cache: deleting it loses undo history and pending
    proposals, never notes.
- **Not yet:** ~~secret screening before the journal and disk~~ (done in K4, D12); agents proposing through tools (K5 —
  today only via `POST /api/vault/proposals`); approve-with-corrections, per-item undo inside a batch,
  batch approval across proposals and per-agent trust (K7).

## D12 — Secret screening, held proposals and the *Save anyway* override

- **Date / by:** 2026-10-01 — screening by Claude while building K4 (BookShelf I4, DESIGN §7); the
  manual override at the user's request ("Add a manual override for K4")
- **Status:** accepted
- **Decision:**
  - Everything a proposer sends is screened **before** anything is stored. A hit never reaches the
    journal, the vault or the index. Only a coarse category ("a password or key", "a payment card
    number", "a government ID number", "a bank account number") and *where* (e.g. "change 1 (body)")
    are reported or logged — never the value; if the agent id itself is the hit, it's withheld too.
  - Screened proposals are **held** in the inbox, in memory only. The user can *Reject* or *Save
    anyway*. *Save anyway* is the manual override: two clicks with a warning, then the proposal is
    stored and filed in one step, the category is recorded on the proposal (`screened`) and in a
    `proposal.override` event. Agents can't override.
  - Only the proposer's own text is screened: an agent may still retag or archive a note whose
    existing text looks sensitive, because that text is the user's.
  - Any vault note whose text looks sensitive keeps its file but is left out of the search index
    (title and tags only) and is marked 🔒 in Bookshelf.
- **Costs / limits:** held proposals vanish on a hub restart (by design: keeping them would mean
  storing the secret). The patterns are heuristics — false positives are expected (the proposer can
  rephrase; the user can Save anyway) and unknown token formats will slip through. *Save anyway* puts
  the secret in the vault file and the undo journal (`data/bookshelf.db`), as the user chose.
- **Revisit if:** false positives become frequent on real notes, or a secret slips through (add the
  pattern and a test); consider a per-category allow list in settings rather than a global off switch.

## D13 — Git guardrails on Claude Code sessions in this repo

- **Date / by:** 2026-10-01, user (adopting Matt Pocock's git-guardrails skill); design by Claude
- **Status:** accepted
- **Decision:** a project hook blocks destructive git commands (push, reset --hard, clean -f,
  branch -D, checkout/restore of everything) and edits to the guardrails, for Bash and PowerShell.
  The rule "push only when the user asks" is now enforced by the harness instead of resting on the
  agent's judgment. Removal is user-confirmed by design: Claude can run `git_guardrails.py remove`
  to show what it will change, but only someone typing `REMOVE` in a terminal can make it happen.
- **Costs / limits:** a text match, not a sandbox: it catches mistakes, not a determined bypass.
  The user pushes by hand. The hook needs `hub/.venv`; if that venv is missing the hook errors and
  Claude Code lets commands through (fail-open). Project settings load only for sessions started in
  this folder.
- **Revisit if:** pushes become routine (e.g. CI), or sessions usually start outside this folder.

## D14 — Security baseline from the vibe-security audit

- **Date / by:** 2026-10-01, Claude running the user's vibe-security skill (user asked for the review)
- **Status:** accepted
- **Threat model:** no login, hub on 127.0.0.1. Realistic attackers: a malicious web page in the
  user's browser, another local process, and prompt injection through notes or agent output. Phase 3
  (remote access + login) must re-run this audit.
- **Decision:** (1) trust only localhost plus exact host names in `[hub] remote_hosts` — never a
  wildcard; (2) strict security headers on every response, no API docs; (3) agent output and note
  text are untrusted: no remote images in chat, notes marked as data to agents, per-agent proposal
  caps; (4) server-side validation of every browser-supplied value that reaches a filesystem path or
  another service (Claude workspace allowlist, Hermes session ids); (5) secret-looking text from guard
  logs is hidden before storage, reusing the K4 screener.
- **Not issues here:** no client-side secrets (no `VITE_` env, keys read server-side only); git
  history clean apart from fake test fixtures; SQL is parameterised (f-strings only build column
  names from code/schema); markdown rendering has no raw HTML.
- **Accepted for now:** any local process can call the hub and the MCP endpoint and claim to be an
  agent (localhost is trusted until Phase 3 adds login); Claude Code transcripts in `hub.db` can hold
  whatever the user and Claude wrote.

## D15 — Source library: a read-only, searchable copy of chosen Drive folders

- **Date / by:** 2026-10-01, user ("make a copy of my drive for now, as I don't have a strong vault";
  chose a searchable source library, the folders, and to leave out card statements and photos)
- **Status:** accepted. Reverses D7's "not adopted" for idea 7.
- **Decision:** chosen folders of a source (first: `G:\`) are copied one way into
  `data/sources/<name>/`, outside the vault, and their text is indexed in `data/sources-index.db`.
  Sources are searched and cited, never edited; knowledge reaches the vault only through approved
  proposals (I1). Drive is only read. Private-looking files are never copied (name rules plus the K4
  content screen) and are listed by path. Media, archives, binaries and Google shortcut files
  (`.gdoc`: their text lives online) are skipped with a reason.
- **Costs:** a second copy (252 MB today) that drifts until the next *Sync now*; Google Docs/Sheets
  need exporting to be included; images have no OCR yet; the name and content screens will miss some
  private files and flag some harmless ones (today `Getting Started.xlsx` may be one).
- **Revisit if:** sources should sync on a schedule, Google-native docs matter (export via the Drive
  API), or scanned PDFs/images need OCR.

## D16 — Agents reach Bookshelf through MCP tools, with the agent id set by Sage OS

- **Date / by:** 2026-10-01, Claude building K5; the Hermes config change approved by the user
- **Status:** accepted
- **Decision:** one tool implementation (`knowledge/tools.py`), two transports: an in-process SDK MCP
  server per Claude session, and a Streamable HTTP endpoint per other connector
  (`/mcp/<vendor>/<name>/`, stateless, Host/Origin-checked). The agent id comes from the Claude session
  or the URL path, never from the model. Reads and source reads are free; writing is `propose_note`,
  which goes through screening and the inbox. Tool text marks note and source content as untrusted
  data (D14). Claude's Bookshelf tools skip the permission prompt because proposals already wait for
  the user.
- **Costs / limits:** any local process can call an endpoint and claim to be that agent (localhost is
  trusted until Phase 3); Hermes picks up a config change within about a minute but a broken endpoint
  just disappears from its tool list.
- **Revisit if:** a third agent connects (add its endpoint) or Phase 3 brings authentication.

## D17 — K6 redefined: notes start from whatever the user has provided

- **Date / by:** 2026-10-02, user ("I don't have an Obsidian vault and most users might not as well,
  make it so that the notes can start building off whatever is provided"); design by Claude
- **Status:** accepted. Replaces K6's original scope (import existing Obsidian/llm-vault vaults): an
  existing vault is now just another `[[sources]]` entry whose markdown gets imported.
- **Decision:** two layers, both proposals the user approves (I1):
  1. *Starter notes*, deterministic and model-free (I6): markdown files imported verbatim
     (`origin: imported`, reserved for `sage-os:importer`), and one *collection note* per folder of
     documents. Collection notes are an honest index: each document's opening lines or slide titles,
     its source path, and distinctive terms. Nothing is summarised (BookShelf I7's intent).
  2. *Concept notes* on request: an agent is briefed with the collection's file list (as quoted data)
     and an exact example change, reads documents through `read_source`, and proposes cited notes.
  Proposals are grouped one card per area (two folder levels under the notes folder) so the inbox
  isn't flooded; every note records `source:`, which makes re-runs idempotent.
- **Costs / limits:** collection notes are only as good as text extraction (no OCR; Google Docs
  shortcuts missing). Agent drafts vary in how well they follow the brief (the first Hermes run put
  tags in the body and skipped `source:`; the brief now shows an exact example). Hermes caches an MCP
  server's tool list at first connect, so new Sage OS tools need its `bookshelf` entry toggled
  (`enabled: false` → back) or a gateway restart (STATUS known issues).
- **Revisit if:** collection notes go stale as sources change (update proposals instead of skipping
  built ones), or drafting should run on a schedule or a kanban board (Phase 4).

## D18 — Demo readiness: the app explains itself

- **Date / by:** 2026-10-03, user ("a somewhat working demo, with clear displays and the app's why
  … clear how's to the app", for a demo the following week); design by Claude
- **Status:** accepted
- **Decision:** the *why* and *how* live in the app, not only in docs:
  1. A **guide** opens on a first visit (and from **? GUIDE**): the team analogy from D1 mapped to
     panels, four rules taken from D4/D6/D11/D15, and D4's limit stated plainly. Its facts quote this
     log; when a decision changes, update `ui/src/components/Guide.tsx` with it.
  2. A **tour** spotlights each panel. Panels and status lights are named for what they do; technical
     names and ports moved to tooltips.
  3. **Empty states teach the next step** (an empty Bookshelf shows the path from sources to notes).
  4. `docs/DEMO.md` is the script; it shows only what is built (the files → proposals → approval →
     notes loop and agents using Bookshelf). D8's team chat is named as next, not shown.
- **Costs / limits:** the guide is static copy that can drift from the code (mitigated by citing
  decision numbers); "seen" is per browser (`localStorage`), so a new browser shows it again. On a
  phone the tour can't point at panels hidden behind tabs and centres its cards instead.
- **Revisit if:** D8's team chat lands (the tour and the team table change), or more agents connect.

## D19 — OCR is a roadmap step (S2), not a someday item

- **Date / by:** 2026-10-03, user ("OCR should be a concrete step, as it makes Sage being a one stop
  hub for everything make more sense"); measurements and engine choice by Claude
- **Status:** accepted. Amends D15's "images have no OCR yet" from a cost to a planned step.
- **Why:** a hub that can't read a photo of a page isn't one-stop. Today 37 images and 16 scanned
  PDFs (under 200 characters of text each, mostly CamScanner) in the Drive copy are invisible to
  search, to agents and to *Build notes*: about 11% of it.
- **Decision:** step **S2** in the Bookshelf track. Text is read from images and from scanned PDF pages
  during *Sync*, stored like any other extracted text, and marked as OCR text (with the engine) so
  search results and notes can say where the words came from. Private-file rules and the K4 screen
  apply to OCR text exactly as to other text.
- **Engine:** behind a small interface, like connectors (D4). First engine: **Windows' built-in OCR**
  (`Windows.Media.Ocr`: free, offline, English already installed on this PC). Mac (Apple Vision) or
  Tesseract later; a local vision model through llama.cpp as an optional higher-quality engine.
- **Unverified (check when building):** the Python bridge to Windows OCR (a new dependency); pulling
  page images out of scanned PDFs with pypdf; accuracy on phone-camera scans and handwriting.
- **Revisit if:** OCR quality on real scans is too poor to search, or the engine needs a GPU slot the
  local model is using.

## D20 — Briefing packs are chosen per prompt, and you see them (K8)

- **Date / by:** 2026-10-03, user ("based on the user prompt … the user sees what the agent is
  reading"); details proposed by Claude
- **Status:** accepted; the preview detail below is still open
- **Decision:**
  1. **Per prompt.** Each message you send is used as a search over your notes and sources; the best
     few matches (default 3 notes + 2 document excerpts, within a size budget) are attached to that
     message for the agent. A new message gets a new pack.
  2. **Visible.** Every message shows a *Reading* strip: the notes and documents attached, each one
     click away. The agent's own reads during the reply (`read_note`, `read_source`) are added to the
     same strip, so you see everything the answer was based on.
  3. **Same rules as tools.** The pack is marked as untrusted data, never instructions (D14); notes
     screened as sensitive (D12) are never attached; agents still can't write without the inbox.
  4. **Recorded.** Which items went with which message is stored, so a past answer can be traced to
     what the agent was shown.
  5. **Switchable.** On by default; a per-chat toggle turns it off.
- **Open:** whether to show the pack *before* sending (remove items, then send) or alongside the sent
  message (faster; you see it, you can't edit it). Recommended: alongside, with removal added if
  wrong picks turn out common.
- **Costs / limits:** keyword search (D10) will miss notes that use different words until
  meaning-based search lands; a pack adds tokens to every Claude message (counted against the
  subscription); a long prompt needs its key terms picked out, since the search requires every word.
- **Revisit if:** packs are often irrelevant (tune or add meaning-based search) or token use matters.
- **Amended 2026-10-03 (user: "alongside, but we need some way to correct it before agents go into a
  loop with the wrong info"):** the pack is shown **alongside** the sent message, and every item in the
  *Reading* strip has a **✕ wrong / not relevant** control:
  - while the agent is still answering, ✕ stops the reply and resends the same message without that
    item, plus one line saying it was removed and why;
  - after the reply, ✕ adds that line to your next message;
  - either way the item is left out of later packs in that chat, and if the agent opens it again with
    its own tools the strip flags it.
  D8's per-thread turn cap and no-progress check still apply when agents talk to each other.

## D21 — Where Sage OS runs: PC as home base; Mac and phone as screens; code that runs on both

- **Date / by:** 2026-10-03, user ("build in a way that allows the app to work from Mac and Windows,
  and is operable by phone"; chose the PC as home base and passkeys); design by Claude
- **Status:** accepted; point 1 (PC as home base) **superseded by D22** (every device runs Sage OS,
  notes sync). Sets the shape of Phase 3; product distribution below is a direction, not a decision.
- **Decision (personal use):**
  1. **The Windows PC is home base.** It runs the hub and holds the data (notes, Drive copy,
     journal) and the GPU models. The Mac and the phone are screens: they open Sage OS in a browser
     over Tailscale, a private encrypted network between your own devices. One copy of everything,
     nothing to sync. When the PC is off, Sage OS is off.
  2. **The code runs on macOS and Windows.** Per-machine settings live in an untracked
     `config.local.toml` over `config.toml`; `~` works in every path; the Claude CLI is found on
     both; `start.sh` is the Mac launcher. A Mac copy is for development and for later users, not a
     second home for your data.
  3. **Login with passkeys** (Face ID / fingerprint, the WebAuthn standard) once Sage OS is reachable
     off the PC. Devices are added from the PC (it shows a one-time code); each can be revoked.
     Localhost on the PC itself stays login-free.
  4. **Phone-first screens**: every new screen must work at phone width (the inbox above all,
     since approving from the phone is Phase 3's gate).
- **Product direction (anyone downloads it from a website):** each user runs Sage OS on their own
  computer, as today; nothing about their data is hosted by us. What has to be added:
  - *Installers*: a signed Windows installer and a signed, notarized Mac app (needs a code-signing
    certificate and an Apple developer account), bundling Python and the UI so users install nothing
    else; auto-update.
  - *First-run setup* (A5): connect the AI they already have (Claude sign-in, an API key, or Ollama /
    LM Studio / llama.cpp running locally); app data in the per-user folder (D6).
  - *Phone access*, in three tiers: (a) same Wi-Fi + passkey, free and simple; (b) bring-your-own
    Tailscale for away-from-home, free but a setup step; (c) an optional **Sage relay** we run that
    passes encrypted traffic between their phone and their computer, the way Plex or Home Assistant
    Cloud do. (c) is the only part with a running cost per user, and the natural paid tier.
  - *Agents*: Hermes isn't shipped; Claude, cloud APIs and local model servers plug in through A1
    connectors; A3's own board replaces the Hermes kanban.
- **Costs / limits:** a Mac copy without Hermes or an NVIDIA GPU shows those panels as down/empty;
  Windows OCR (D19) needs a Mac engine before OCR works there; the guardrails hook (D13) calls the
  Windows venv path and fails open on a Mac until its command is made OS-neutral (needs the user's OK,
  since edits to the hook are guarded).
- **Revisit if:** the PC being off is a real problem (then a small always-on box, or the either-host
  setup with synced notes), or the audience question in D1 is answered.

## D22 — A shippable app for anyone with several AIs and scattered notes; nothing assumes this PC

- **Date / by:** 2026-10-06, user ("a shippable, installable app that the average person who uses
  multiple AIs and has scattered notes can create a smart 'Wikipedia for themselves' that also
  supplements their AI usage"; chose options B + C below; asked for Google Docs, more file types and our
  own llama server); design by Claude
- **Status:** accepted. Answers D1's audience question. Supersedes D21's "the PC is home base" (D21.1);
  keeps D21.2 (code runs on macOS and Windows), D21.3 (passkeys) and D21.4 (phone-first screens).
  Puts D4.2 into effect (Sage OS installs and manages `llama-server`; it still doesn't rewrite it).
- **Audience:** someone who uses more than one AI (ChatGPT, Claude, Gemini, a local model) and keeps
  notes and documents in several places. No GPU, no Hermes and no terminal assumed.
- **Decision:**
  1. **Core needs only a folder.** Notes, search, sources, the inbox and briefing packs work on any
     Mac or Windows laptop with no particular AI installed. Everything else is a connector, and a
     missing one shows as *not connected*, never as a broken panel.
  2. **Bring your own AI.** v1 connects Claude, ChatGPT, Gemini and local models. Cloud chat models go
     through one OpenAI-compatible chat connector (OpenAI and Gemini both offer that API); Claude Code
     keeps its own connector. Hermes stays an optional connector for those who have it.
  3. **Our own local engine.** Sage OS downloads and runs the stock `llama-server` (CUDA, Vulkan or CPU
     on Windows; Metal on Mac) and offers a curated model catalog. Each model shows its download size,
     the memory it needs and whether it fits this machine, so a 4B model on a laptop and a 31B model on
     a gaming PC both work. Downloads resume and are checked against a hash; gated models need the user
     to accept the licence themselves. Ollama and LM Studio still plug in as endpoints.
  4. **Hardware is the user's choice, not a requirement.** A cloud AI plus a small local model runs on
     modest hardware; big local models need a big GPU. The app detects what's there and says so.
  5. **Google Drive is a connector, not a drive letter.** Google Docs, Sheets and Slides are read
     through the Drive API (exported to Word, Excel and PowerPoint formats, then indexed like any
     other file). Drive for desktop stays a fallback for plain files.
  6. **Every device runs Sage OS; notes sync (option B).** Notes are plain markdown, so each device
     keeps a copy and syncs through a folder the user already trusts (iCloud, OneDrive, Syncthing)
     first. Each device does its own search and AI calls; local models run where the hardware allows.
  7. **Optional relay later (option C):** a Sage-run relay for phone access away from home, the
     natural paid tier. Same Wi-Fi + passkey stays free.
- **Costs / limits:** we now own an engine's packaging (binaries per OS and GPU, updates, crash
  handling). Google's `drive.readonly` scope is *restricted*: fine for personal use with the user's own
  OAuth client in testing mode, but a public release needs Google's verification and security
  assessment, or the narrower `drive.file` scope with a file picker. Sync (B) needs conflict handling
  that a single home base didn't. Hermes-only features (kanban board, guardian) stay Hermes-only until
  A3 replaces them.
- **Revisit if:** sync conflicts are common (then a home-base mode as in D21), or Google verification
  is out of reach (then `drive.file` + picker).

## D23 — Long documents are digested section by section, with a coverage map (K12)

- **Date / by:** 2026-10-08, user ("if I added a massive textbook, would it break it down into appropriate
  notes without missing something?"; chose this as the next build); design by Claude
- **Status:** accepted
- **Why:** before this, a textbook could be skipped (over 50 MB), cut off (500 PDF pages, 2M characters) or
  drafted from a sliver ("read at least three documents", 3–6 notes), with nothing showing what was missed.
- **Decision:**
  1. **Split so the pieces add up to the whole.** Chapters and sections come from PDF bookmarks, then
     headings (Word, EPUB and HTML headings are kept as markdown), then even chunks. The sections tile the
     text: every character is in exactly one section, checked in code. A heading level counts as chapters
     only if its parts average 6,000+ characters (one bookmark per slide isn't a chapter).
  2. **Draft every section**, in order, on the model the user picks (the local engine by default: free,
     private, unattended). The model lists the section's key concepts, then writes notes covering them;
     it sees earlier notes' titles to avoid repeats, and same-titled notes are merged with both sources.
  3. **Check coverage.** A listed concept no note covers gets one follow-up call; the map shows covered /
     listed per section and flags gaps. Limit: "listed" means listed by the model; a concept the model
     never lists isn't counted.
  4. **One inbox card per chapter** (split at 50 notes), so a 30-chapter book is 30 decisions, not 400.
     Nothing is written before approval (I1); screening applies (K4).
  5. **Resumable and visible.** Jobs survive restarts; pause / resume / cancel; a section that fails twice is
     marked and can be retried; the engine not running means "waiting", not "failed".
- **Costs / limits:** a 500-page book is roughly 150–200 sections, about 1.5–3 hours on a 16 GB GPU with a
  12B model and many more on a laptop CPU. Keyword-free concept checks depend on the model's own list.
  Scanned books still need OCR (S2). Near-duplicate titles across chapters aren't merged.
- **Revisit if:** concept lists prove unreliable (add an independent term check), or approval per chapter is
  still too much (K7 batch review).

## D24 — Proposals are reviewed note by note: read, keep or drop, edit, then file (K13)

- **Date / by:** 2026-10-09, user ("when you open a card to see the note it proposed, does it open in a clean,
  easy to read md editor?" It didn't: raw diffs, all-or-nothing); chose the full version
- **Status:** accepted
- **Decision:**
  1. Every Bookshelf card has **REVIEW**: a full-screen reader with each note rendered as markdown (title,
     tags, folder, source), previous/next, keyboard (← → / x), one note per screen on a phone.
  2. **Keep or drop per note.** Approving files only the kept notes; dropping all means reject.
  3. **Edit before filing** (title, body, tags) with a live preview. Edited notes are filed with
     `edited_by: user` next to the agent's provenance; the user's edits go through the K4 screen.
  4. Same writer, same journal: the reviewed set is one batch and undoes byte for byte (I2). The agent's
     proposal as sent is kept (`original`) with a summary of the review, recorded only once filed.
- **Costs / limits:** a review lives in the browser until Approve (closing the screen loses unsaved edits);
  folder and links can't be edited in review; edits to an `update` change replace its body like the agent's.
- **Revisit if:** reviews get long enough that drafts must survive a reload (save them server-side), or
  batch approval across cards is wanted (K7).

## D25 — App data per computer; a Library of notes and files that moves between devices

- **Date / by:** 2026-10-09, user ("the idea of the app is ease of access: any common file types should be
  able to move between a user's devices, including the markdown notes that make the agent search possible;
  keep an app-data area, with a button to go to the file location, and export the notes"); design by Claude
- **Status:** accepted. Makes D22.6 (sync, option B) concrete; replaces "data/ next to the code" (D6's
  "app's data folder" now means the OS's app-data folder).
- **Decision:**
  1. **App data** (`%APPDATA%\Sage OS`, `~/Library/Application Support/Sage OS`, `~/.local/share/sage-os`):
     databases, indexes, copies of sources, models, sign-ins. Per computer; never synced; untouched by
     updates and reinstalls.
  2. **The Library** = `Notes/` (the vault, which agent search runs on) + `Files/` (any documents the user
     drops in, indexed where they are, never copied). Default `<app data>/Library`; the user points it at a
     folder their sync service already syncs, and every device then sees the same notes and files.
  3. **Moving the Library merges, never overwrites:** a second device pointing at an existing Library adopts
     it; a file that differs on both sides is kept twice ("name (from PC).md"). The old folder stays.
  4. **Conflicts are shown, not resolved silently:** sync services' second copies (OneDrive "-PCNAME", iCloud
     " 2", Dropbox "conflicted copy", Syncthing ".sync-conflict-") are listed in STORAGE.
  5. **Open and export:** buttons open the app-data, Library, Notes and Files folders; notes (optionally with
     files) export as a zip.
  6. Older installs move with `python -m sage_os_hub move-data` (copied, checked, old folder kept).
- **Costs / limits:** undo history (the journal) is per computer, so a batch approved on one device can be
  undone only there; chats and inbox items are per computer for now; secrets (Google token) still sit as
  files in app data until the keychain step; two devices digesting into one Library at once may both propose
  the same notes.
- **Revisit if:** users want chats and history on every device (then append-only files in the Library), or
  a sync service mangles the vault (then a Sage-run sync).

## D26 — Any model can lead: orchestrator and reviewer are roles, not Claude

- **Date / by:** 2026-10-09, user ("replace Claude with any frontier model, or even a personal local model as
  the fleet command if needed")
- **Status:** accepted. Amends Phases 4–5 and D8's "lead agent answers by default".
- **Decision:** the lead (orchestrator) and the reviewer are roles the user assigns to any connected model:
  Claude, ChatGPT, Gemini or a local model on the engine. Fleet tools (Phase 4) and review (Phase 5) are
  Sage OS tools offered to whichever model holds the role, through the connector layer (A1, D22.2); nothing
  in them may depend on one vendor's SDK. `[agents] lead` already names the lead; a `reviewer` setting joins it.
- **Costs / limits:** small local models plan less reliably than frontier ones; the role picker should say
  so, and the gates are checked with both a cloud and a local lead.

## D27 — "Sign in on each device and everything just works": a Sage account with end-to-end encrypted sync

- **Date / by:** 2026-10-09, user ("download on my phone, Mac and desktop, sign in on each and everything just
  works"); design by Claude
- **Status:** accepted as the target architecture. Builds on D25 (app data vs Library) and D22 option C (a
  service we run is the paid tier); folder sync (D25) stays as the free, self-managed option.
- **Decision:**
  1. **Local-first devices.** Each device keeps its own full database and works offline; sync runs in the
     background and never blocks the UI.
  2. **A Sage account with passkey sign-in.** Each device makes its own key pair when enrolled; an already
     signed-in device or the recovery key (shown at setup) approves it; devices can be revoked.
  3. **End-to-end encryption.** One account data key, wrapped per device. The server stores only ciphertext and
     can't read notes, files or chats.
  4. **What syncs and how:** notes (markdown) with per-note version vectors, conflicts kept as two copies (a
     CRDT text format is a later option); files as content-addressed encrypted chunks, fetched on demand on
     phones; chats, inbox decisions, undo journal and digest progress as append-only per-device event logs merged
     by time (no conflicts possible); settings last-writer-wins per key; indexes and embeddings rebuilt per
     device (embeddings may sync so phones skip the work); secrets in the OS keychain, synced through the
     encrypted vault only if the user opts in.
  5. **Work goes where it can run.** Jobs sync too: a digest started on the phone is picked up (leased) by a
     device with a GPU; a phone chat can use a cloud model or reach the desktop's local engine through the relay.
  6. **A thin server:** encrypted blob storage (R2/S3), a small metadata database (accounts, devices, log
     cursors), a push channel ("something new"), and the relay. No knowledge of content.
  7. **Apps:** desktop = one installer bundling hub + UI + engine (e.g. Tauri); phone = the same React UI as a
     native shell with the sync client and a local store (no Python, no local model at first); one sync engine
     (TypeScript or Rust) shared by both so the protocol can't drift.
- **Do now (no server needed), so sync is transport later, not a rewrite:** (a) stable ULIDs for every record
  (chats, messages, inbox items, approvals, digests, settings); (b) tombstones instead of deletes; (c) chats,
  inbox decisions and the journal as append-only events stamped with device + time; (d) a clear split between
  synced stores and device-local ones (indexes, source copies, engine), matching D25; (e) a device identity per
  install, recorded on every change.
- **Costs / limits:** we run and pay for a service (storage, uptime, account recovery): the paid tier. A lost
  recovery key with no signed-in device means lost data (setup must make the key hard to skip). The phone app
  is a second shell to maintain, though it reuses the UI.
- **Revisit if:** users won't accept an account (then folder sync + LAN pairing only), or E2EE blocks a must-have
  server feature (then that feature runs on a user's device instead).

## D28 — Y1 specifics: every record gets a fresh ULID; a change log next to the tables

- **Date / by:** 2026-10-10, user ("rewrite the ULIDs fresh, change log alongside the current table"); options
  laid out by Claude
- **Status:** accepted; not built yet (the user asked to wait). Refines D27 "do now" (a) and (c).
- **Decision:**
  1. **All IDs are rewritten to ULIDs**, existing ones included: chats (`ch_…`), Claude sessions (`cs_…`), digests
     (`dg_…`), proposals, batches, chat items, briefings. The one-time migration maps old IDs to new ones and
     updates every reference (including the digest's note folders and any IDs the UI keeps), after backing up
     each database. Old IDs are not kept as aliases.
  2. **A change log alongside the current tables (an outbox).** Each change to a synced record writes the table row
     as today *and* an entry in an append-only `changes` log (ULID, device, time, stream, record, operation, data),
     in the same transaction. The tables stay what the UI reads; the log is what Y4 sends to other devices.
     Making the log the source of truth was set aside for now: a larger rewrite with no gain before sync exists.
- **Costs / limits:** rewriting IDs touches every store and breaks any bookmarked URL or copied ID from before the
  migration; the migration has to be exact and is tested on a copy of real-shaped data. Each change is stored
  twice (row + log).
- **Revisit if:** the rows and the log ever disagree (then make the log the source and rebuild rows from it).

## D29 — Game mode: Sage OS notices when another program needs the hardware and steps aside

- **Date / by:** 2026-10-10, user ("for the hub to be aware when other apps are using the hardware, and the agents
  can work around that"; "don't use the nvidia-smi as it only works for nvidia cards"; "if the agent determines a
  micromodel (think e2b) could fit while the other program is running for background tasks, it can ask the user to
  continue working in the back"); design by Claude. Prompted by a game failing while the engine held 10.6 of
  16 GB of graphics memory.
- **Status:** accepted as roadmap step G1; order against Y1 not decided.
- **Decision:**
  1. **Detection works on any graphics card.** Windows: the OS's own per-program GPU memory and activity counters
     (the numbers Task Manager shows; every vendor, integrated graphics included), each adapter's memory budget,
     and the system's "full-screen game running" state. macOS: memory pressure, the frontmost app, and the memory
     Metal says a model may use (memory is shared). Linux later, from the driver's per-program counters. The same
     source replaces `nvidia-smi` in the hardware check, so the MODELS panel stops being Nvidia-only.
  2. **What counts as "another program needs it":** a full-screen game, or a program other than Sage OS holding a
     lot of graphics memory or keeping the GPU busy for more than about 30 seconds. The user can mark programs as
     always or never counting.
  3. **Step aside, in order:** pause local jobs (the digest drops its current section and redoes it later), then
     unload the local model. Local chats say "paused while <program> runs" and offer a connected cloud model.
     Cloud AIs and Claude Code are unaffected: they don't use this computer's GPU.
  4. **A micro model may keep working, with the user's OK.** After unloading, Sage OS measures what is left. If a
     micro model (Gemma 4 E2B class, about 2–3 GB, added to the catalog) fits with a safety margin, it asks once:
     *Keep working in the background with a small model?* **Keep working** / **Pause until I'm done**. The answer
     can be remembered per program. The micro model takes light work only (tagging, short summaries, sorting
     proposals, short chats); digests stay queued for the main model so note quality doesn't drop. If the other
     program's use grows into the margin, the micro model stops at once.
  5. **Come back on its own:** once the program has closed (or dropped below the threshold) for a few minutes,
     reload the main model and resume queued jobs, and say so.
  6. **The user decides:** a setting *Step aside for games: always / ask / never*, and a manual *Pause for a game*
     button in MODELS.
  7. With sync (D27.5, Y5), a paused job can instead go to another device that is free.
- **Costs / limits:** Windows' counters need a modern driver and lag about a second; macOS has no per-program GPU
  memory, so it decides from memory pressure; heavy non-game programs (video editors, 3D apps) also count, which is
  usually right. Each unload and reload costs 20–30 s. The micro model writes weaker text, so it gets only light
  work. Downloading the micro model needs the user's OK like any model.
- **Revisit if:** false alarms annoy users (then *ask* becomes the default and detection gets stricter), or the
  engine can shrink instead of unloading (smaller context, fewer layers on the GPU).


## D30 — Build order after 0.15; K10 (git-backed vault) dropped

- **Date / by:** 2026-10-11, user ("agree on the order and drop K10"); order proposed by Claude
- **Status:** accepted. Sets the order STATUS *Next* follows; drops roadmap step K10 (from D7 idea 8).
- **Decision:**
  1. **Order: Y1 → G1 → K7 → K14 → A3 → Y2**, then Y3–Y6 and the remaining steps (S2 OCR, K9, K11, Phases 4–6).
     - Y1 first so everything built after it gets ULIDs and the change log from the start, with no second
       migration.
     - G1 next: small, and fixes a real clash (a game failing while the engine held the GPU).
     - K7 (review at scale) clears the textbook backlog (2,741 draft notes, 45 chapter cards) that note-by-note
       review (K13) can't keep up with.
     - **K14 = meaning-based search** (D10's later step, now numbered): briefing packs still pick wordy but wrong
       notes. K11 (Ask) builds on it.
     - A3 (Sage OS task board) after Y1, so the new store is sync-ready from day one; K9 and Phases 4–5 build on it.
  2. **K10 is dropped.** A git repository per vault was planned before D27. The undo journal and the Y1 change log
     now carry the history, and git doesn't fit end-to-end encrypted sync, a phone, or a non-technical user. Anyone
     who wants git can still keep the Library folder in a repository themselves.
- **Costs / limits:** no `git log` view of note history inside Sage OS; history browsing, if wanted, is built on the
  change log later.
- **Revisit if:** users ask for a portable, tool-readable history of their notes outside Sage OS.


## D31 — How Y1 was built: an outbox from triggers, rows that settle on the newest change, deletes that win

- **Date / by:** 2026-10-11, Claude, building Y1 as planned with the user (D27 "do now", D28)
- **Status:** accepted; shipped in 0.16.0. Details of D28, not a change to it.
- **Decision:**
  1. **IDs** are ULIDs with a short type prefix (`ch_`, `cs_`, `ci_`, `p_`, `b_`, `dg_`, `br_`, `ib_`, `dv_`), so an
     ID still says what it names. A device's IDs never go backwards (same millisecond, or a clock stepping back),
     and after taking in another device's change, the next local ID sorts after it.
  2. **The change log is filled by TEMP triggers** on the hub's own connection to each synced table: insert, update
     and delete each append an entry in the same transaction. A new write path can't forget to log, and the
     database files carry no trigger that another program would trip over. Each database with synced tables
     has its own `changes` table, so the row and its entry commit together.
  3. **A record settles on its newest entry** (by ID), whole row, on every device and in any arrival order. Decimals
     are logged exactly (SQLite's own JSON keeps 15 digits; the gate caught timestamps changing).
  4. **Deletes are tombstones, and they win.** Chats, Claude sessions and briefings get a `deleted` time. A local
     update never clears it, and a merged change keeps the earliest delete time, so an edit made later on another
     device doesn't bring a deleted chat back, and two devices always agree.
  5. **The move to ULIDs** runs once at hub start, before any store opens: back up each database (with the old to
     new ID map), rewrite IDs and references in one transaction per database, log every existing row as created
     here; on any error, put the backups back and stop. It's content-based: a record that has a ULID keeps it, so
     running it again does nothing.
  6. **Manifest** (`sync/manifest.py`): every table and app-data file is labelled synced, this computer only,
     Library or log, with each synced table's key; tests fail on anything unlabelled.
- **Costs / limits:** every update logs the whole row (a digest section repeats its text each time), and nothing
  compacts the log yet: Y4 drops entries every device has. Rows merge whole (two edits to different fields of
  one record: the later wins). Merged rows reach in-memory state (open sessions, panels) only on restart until
  Y4 adds a refresh. Clock skew between devices can make an older edit win; a hybrid clock is the later fix.
- **Revisit if:** the log grows faster than expected before Y4 (then log only changed columns), or field-level
  conflicts matter (then per-field entries or a CRDT for notes, as D27 allows).


## D32 — F1: a Mac build a friend can install from a .dmg, start from nothing and report bugs from

- **Date / by:** 2026-10-11, user ("a base app with no files, a simple .dmg installer for her, and the ability for
  her to start using the app and reporting bugs"; chose: after K7 and K14, bug reports by email with a report file,
  the .dmg built on GitHub Actions); design by Claude
- **Status:** accepted as roadmap step F1. Brings the Mac half of Y6 (installers) forward, and the key-entry half
  of Y2. Doubles as A5's open check (engine and model downloaded on a machine with nothing installed).
- **Decision:**
  1. **App bundle:** a macOS `.app` holding the hub (Python, bundled with PyInstaller), the built UI and the model
     catalog; opening it starts the hub and opens Sage OS. Apple Silicon first. The Tauri shell of D27.7 can
     replace the launcher later without touching the user's data.
  2. **.dmg built on GitHub Actions** (a macOS runner, on demand, from the private repo). A Windows PC can't build
     it. Needs the build workflow pushed, which happens only when the user says "push".
  3. **Unsigned at first:** no Apple Developer account yet, so the tester approves the app once (right-click →
     Open, or Privacy & Security → Open Anyway). A one-page first-open sheet with screenshots ships with it.
     Signing and notarization when there are more testers.
  4. **Starts from nothing (D22):** empty Library, no Hermes, Google, GPU or terminal assumed. First run opens the
     guide and an empty Library with "add your first notes" and "connect an AI"; anything missing reads *not
     connected*. Checked on a blank macOS user account.
  5. **Her own AI:** API keys entered in the app and kept in the macOS Keychain (pulled forward from Y2); or a small
     local model from MODELS on Apple Silicon (Metal).
  6. **Report a problem:** a button that writes a report file (her description, app version, macOS version, recent
     errors and what she was doing; never notes, files or chat text) and opens an email to
     **roundederror@gmail.com** (the owner, 11 Oct 2026: reports go to this address, not a personal one); she
     attaches the file. She sees everything the report contains before sending.
  7. **Updates:** a new .dmg replaces the app; her data stays in app data (D25).
- **Costs / limits:** unsigned apps scare non-technical users and macOS may tighten this further; PyInstaller
  bundles are large (hundreds of MB) and need a build per CPU type; GitHub Actions macOS minutes count ten times
  against the free allowance; email reports depend on her sending them.
- **Revisit if:** more than a couple of testers (then sign and notarize, and consider a report endpoint), or the
  bundle size or start-up time hurts (then Tauri with a slimmer runtime).

## D33 — The desktop app is Tauri, now: a window and a tray around the hub (W1)

- **Date / by:** 2026-10-11, user ("let's make Sage a desktop UI as I tend to close the tab a lot"; "let's go with
  Tauri, better to start with what we will eventually use"); design by Claude
- **Status:** accepted; built in 0.18.0. Brings D27.7's shell forward; F1 builds the Mac `.dmg` from it, Y6 signs it.
- **Decision:**
  1. **Tauri 2** (Rust core, the OS's own web view: WebView2 on Windows, WebKit on macOS) rather than a Python window:
     installers, a signed updater, tray, autostart and later phones come with it.
  2. **The window shows the hub's own page** (`http://127.0.0.1:8787`), so the hub's security rules apply unchanged; no
     Tauri command is exposed to any page. Links that leave the hub, or ask for a new window, open in the default browser.
  3. **The app owns the hub's life:** it starts the hub (the bundled one when packaged, F1; this checkout's Python hub
     for a developer build) or attaches to one that answers `/api/ping` as Sage OS; shows a loading page until then.
  4. **Closing keeps Sage OS running in the tray** (digests, game mode and agents carry on); the tray has Open, Start at
     sign-in (off by default; then it starts in the tray) and Quit, which stops the hub cleanly (`POST /api/quit`, the
     local model unloaded on the way out). One copy at a time; the window remembers its size.
  5. **Windows installer:** per-user NSIS (no admin prompt), unsigned for now (SmartScreen asks once).
- **Costs / limits:** a Rust toolchain and the MSVC build tools to build on Windows, a Mac to build the Mac app (GitHub
  Actions in F1); a developer build depends on the checkout staying where it was built; unsigned installers warn.
- **Revisit if:** the web view can't do something the UI needs (then a native piece through a narrowly scoped command).

## D34 — Not connected is not broken; sentences read in a sans face; proposals read in order (UI pass, 11 Oct)

- **Date / by:** 2026-10-11, user (approved batches A and B of the redesign audit; "the agent cards should be blank besides
  the local until the user connects their own"; inbox cards "not starting from chapter 1"); design by Claude
- **Status:** accepted; built in 0.18.0. Puts D22.1 into the UI. Batch C (a library-first home) is a mockup awaiting the user.
- **Decision:**
  1. **Red means something stopped.** Services report up / down / off / absent; red only for *down* (it ran earlier and
     stopped); what was never set up is hidden or grey; Hermes' checks are optional where Hermes isn't installed.
  2. **Agents appear when connected.** The lead-agent slot is an empty "Connect an agent" card (how to connect, past
     sessions one click away) until Claude Code is installed and signed in; the Hermes tab appears once Hermes has run.
  3. **Type:** sentences (help text, card details, the guide) in a sans face; names, paths, numbers and chat in mono;
     nothing under 11 px; disabled controls dimmed and dashed; a 1 px press.
  4. **The inbox reads in order:** requests that hold an agent up first, newest first; note proposals after them, oldest
     first, so a book reads from its first chapter; digest cards name the book and chapter; a line confirms what was filed.
- **Costs / limits:** someone who wants a chat with Claude must sign in first (the card says how).

## D35 — A library-first home around the agent planet card; the phosphor world stays (W2)

- **Date / by:** 2026-10-11, user (approved the second home mockup: "search and chat should be in the centre",
  "bring back the agent side panel design with the planet, the model name, the usage"; later "the planet card with
  the system stats and orb look the coolest"; rejected a SAGE-console replacement world as "way too basic"; "I like
  it"); design by Claude with the taste and Impeccable skills
- **Status:** accepted; built in 0.19.0. Carries out D34 batch C (W2).
- **Decision:**
  1. **Layout:** left, the agent side panel (the WebGL planet, State / Model / Where / Chats readouts, usage as
     dot-matrix meters; Claude's subscription bars when Claude is chosen) with the agents to switch to or connect
     below; centre, search over notes and files (Ctrl K; Enter asks the local model) above the conversation; right,
     the inbox, the digest in progress and recent notes; bottom, a one-line systems strip. Board, GPU lane and
     Hermes move to a **Systems** view. Phone: Home, Agent, Inbox, Systems tabs.
  2. **The planet card is the house style.** Its parts (readout rows, dot-matrix meters, Doto numerals like the clock,
     the notched panel tab) are shared components every panel uses (`Readout.tsx`).
  3. **The incumbent phosphor terminal world stays.** A replacement world was mocked up through Impeccable's
     direction round and rejected; recorded in PRODUCT.md so later work refines rather than replaces.
  4. **Motion:** the rolling CRT refresh bar is removed (it distracted); motion stays tied to state.
- **Costs / limits:** asking from search always goes to the local model (Claude has its own message box); the
  desktop app shows the hub's page, so UI changes need a reload, not a reinstall.
- **Revisit if:** the owner wants a bolder change of world (then a new direction round, not polish).

## D36 — Review at scale: one decision per chapter, trust levels that file by themselves, a complete activity log (K7)

- **Date / by:** 2026-10-11, user ("start K7"; chose the full trust ladder and the Reviewer inside K7; "make sure there
  is a transparent log of each agent's actions as well, even at the trusted level"); design by Claude
- **Status:** accepted; built in 0.20.0. Carries out D7 idea 5 and the batch half of idea 6. **Amends I1** (no write
  without approval): a write is approved either by the user's decision or by a trust level the user gave that agent.
- **Decision:**
  1. **One card per chapter.** Proposals carry a group (a digest chapter's parts; set only by Sage OS's own jobs). The
     inbox shows a group as one card: APPROVE ALL, REJECT ALL, REVIEW (every part in one run). Cards can also be
     selected and decided together. Approving several proposals files them as **one batch**: all filed or none (I9),
     one undo. A part whose notes were all dropped in review is rejected and the rest filed.
  2. **The per-agent inbox limit counts cards**, not parts (25), and a later part of a waiting chapter joins its card.
  3. **Undo one note** of a filed batch, byte for byte (an archive's two halves together); refused if edited since.
  4. **Trust ladder per agent** (agents are keyed without their session: `claude`, `hermes:<profile>`, `digest`, …):
     *Ask first* (default) · *New notes file themselves* (create-only proposals) · *Trusted* (everything). Only the
     user sets levels (AGENTS screen or an inbox suggestion). After 10 clean approvals in a row (filed by the user
     without dropping, editing or undoing a note) Sage OS asks once whether to raise the level ("Not now" waits for
     10 more decisions); undoing something an agent filed by itself offers a step down. Secret-looking proposals are
     held at every level (K4). What agents file by themselves is listed under *Filed for you* in the inbox and marked
     in History.
  5. **Activity log.** Every agent action is recorded in `agent_log` (bookshelf.db, synced, never trimmed) at every
     level: searches, reads of notes and documents, proposals, what was filed and by whom, rejections, held and
     refused proposals, undos, trust and role changes, Reviewer verdicts, Librarian runs; the user's own decisions too.
     AGENTS shows it per agent or for everyone.
  6. **Roles:** Researcher (drafts notes; the default), **Librarian** (a run over a folder proposes tags, links to
     related notes and clearer titles as ONE proposal; links only to notes found by search), **Reviewer** (Claude Code,
     the local engine or any configured model reads a waiting proposal and marks notes it would drop, with reasons;
     the review screen starts with them dropped; it never decides). Reviews run on request (ASK REVIEWER) or for every
     new proposal when the user turns that on. Both wait for the engine and for game mode like the digest.
- **Costs / limits:** the log grows with every read (kept in full on purpose); the Reviewer's duplicate check is
  keyword search until K14; Claude as Reviewer needs Claude Code signed in; a trust level is per agent, not per
  folder or kind of note.
- **Revisit if:** the log needs trimming or filtering at volume, trust should be scoped (per folder), or reviewers
  should vote (two models).

## D37 — Meaning-based search: a small embedding model on the CPU, hybrid ranking, packs filtered by meaning (K14)

- **Date / by:** 2026-10-12, user (chose "a small model on the CPU" over a tiny static model or the main GPU model);
  design and calibration by Claude
- **Status:** accepted; built in 0.21.0. D10's "later step"; amends K8 (D20) pack selection.
- **Decision:**
  1. **Model:** EmbeddingGemma 300M (Q8_0, 334 MB, Gemma licence, checksum-verified) in its own llama-server on the
     **CPU only** (`--device none`, a quarter of the cores, two slots so a search never waits behind indexing). It
     works with the main engine off, beside a game and on a laptop or Mac, and never takes GPU memory. Downloaded
     only when the user clicks *search by meaning too*.
  2. **Index:** every note (title, tags, first 2,000 characters; sensitive notes by title only, D12) and every
     source document in overlapping 1,200-character passages, stored in `semantic.db`: a per-device cache (LOCAL,
     D27.4), rebuilt from the Library and source copies, re-embedded only when the text changes. Notes first, then
     documents a few at a time. Paused while game mode has the computer (G1).
  3. **Search is hybrid:** keyword (FTS5, D10) and meaning merged by reciprocal rank; a question of four or more
     words weighs meaning double, short exact terms count both equally. Results say how they matched (words /
     meaning / both). Used by Ctrl K and Library search, the agents' `search_notes` / `search_sources`, the Reviewer's
     duplicate check and the Librarian's link candidates. Without the model, search is keyword-only and says so.
  4. **Briefing packs** rank candidates by closeness of meaning: a note found by its words must still be at least
     0.40 close (wordy look-alikes stay out); one at least 0.45 close comes in without sharing words; sources bring
     the passage that matched, not their first page.
  5. **Calibration** on the owner's library (thresholds in `semantic.py`): right answers scored 0.31-0.77 (median
     0.50) against differently worded questions; the best match for questions the library can't answer scored at most
     0.35. A meaning-only search hit needs 0.30.
  6. **Gate check** `hub/tools/eval_search.py` runs against the live hub with questions kept outside git
     (`data-private/`), since they're about the owner's notes and the repo is public.
- **Costs / limits:** first indexing of ~570 documents takes a while on the CPU (notes take seconds); thresholds are
  tuned on one library and one model, so a different model means recalibrating; brute-force vectors in memory are
  fine to tens of thousands of passages, not millions.
- **Revisit if:** the library passes ~100k passages (an ANN index such as sqlite-vec), a better small multilingual
  embedding model appears, or packs still bring wrong notes in practice.

## D38 — Self-contained app and signed updates from version tags (F1, first part)

- **Date / by:** 2026-10-12, user ("let's work on the updater, so someone using Sage can in real time download an
  update I pushed"; chose version tags as the trigger and Windows + Mac); design by Claude
- **Status:** accepted; built in 0.22.0. First part of F1 (D32); amends D33 (the window exposed no commands).
- **Decision:**
  1. **Self-contained app:** the hub is bundled with PyInstaller (`hub/packaging/sage-os-hub.spec`) together with
     `config.toml`, the built UI and the model catalog, and shipped as the app's `hub` resource; the app starts it from
     there (a developer build still runs the checkout's Python hub). Inside the bundle, `config.local.toml` lives in
     app data, since every update replaces the bundle.
  2. **Releases from version tags only:** pushing `vX.Y.Z` runs `.github/workflows/release.yml`, which builds
     Windows (NSIS, per user) and macOS (Apple Silicon, .app and .dmg), refuses a tag that differs from the app's
     version, and publishes a GitHub Release with the version's CHANGELOG section, the signed update files and
     `latest.json`. Everyday pushes to main release nothing.
  3. **Signed updates:** every update is signed with the owner's key (minisign, via Tauri); the private key and its
     password are GitHub secrets and stay with the owner; the public key is in `tauri.conf.json`. An installed app
     refuses anything not signed with it.
  4. **In the app:** it checks `releases/latest/download/latest.json` 20 s after start and then hourly; a newer
     release shows an UPDATE chip in the top bar with the changelog; "Update and restart" downloads it, checks the
     signature, stops the hub cleanly, installs and relaunches. Data, notes and settings live in app data and are
     untouched. In a plain browser nothing shows.
  5. **Two commands for the hub's page:** `update_check` and `update_install`, allowed only for
     `http://127.0.0.1:*` (capability `hub-updates`). Nothing else is exposed; the worst a script on the page could do
     is install the latest release signed by the owner.
- **Costs / limits:** the first self-contained version (0.22.0) is installed by hand once; installers aren't
  code-signed with an OS certificate, so Windows SmartScreen and macOS Gatekeeper warn on first install (updates after
  that don't); macOS runner minutes count ten times against the free Actions allowance; the bundle is ~80 MB.
- **Revisit if:** testers need an Intel Mac build, OS code-signing becomes worth paying for, or an early-builds
  channel is wanted (pushes to main to opted-in users).

## D39 — One chat space before the rest of F1; the engine stops borrowing from Hermes

- **Date / by:** 2026-10-13, user ("where in the roadmap was the unified chat space, so the user talks in one place and
  can easily go through previous chats like AI apps usually do"; chose to build it next, before the rest of F1; "can we
  just use llama.cpp ourselves?", chose fully separate)
- **Status:** accepted; W3 planned, engine switch done on the owner's PC with 0.22.2.
- **Decision:**
  1. **W3, one chat space,** is its own step, built before the rest of F1 (testers will spend most of their time in
     chat). It is not Phase 6's team chat (D8): that is agents working together; W3 is the user's conversations with
     any AI, in one view with one history. Team chat can later be one more kind of chat in the same list.
  2. **The engine is Sage OS's own on every computer:** the official llama.cpp build installed by MODELS and models in
     Sage OS's own folder. The owner's PC drops its `[engine] binary` and `model_dirs` that pointed into Hermes.
- **Revisit if:** Hermes becomes the only place a model exists (then point `model_dirs` at it again, read-only).

---

## Proposed, awaiting the user

### P1 — Bookshelf integration ideas (30 Sep 2026) — resolved by D7

Kept for the wording of each idea; see D7 for which were adopted.

1. **Shared team memory.** All agents read one vault through the same tools (search, read, propose);
   per-agent memory files fold into it.
2. **Briefing packs.** Before a task or chat, Sage OS injects relevant notes (preferences, past
   decisions, related work). Depends on search.
3. **Work becomes knowledge.** Finished kanban tasks propose a short record (what, decisions, where
   the output is); chats get "save to Bookshelf".
4. **Playbooks.** Environment-setup how-tos as `type: playbook` notes that workflows can reference
   (first candidate: the Hermes update checklist).
5. **Roles with trust levels.** Librarian (local, files/links/tidies), Researcher, Reviewer (Claude);
   each agent earns autonomy separately on BookShelf's three-level ladder.
6. **One inbox.** Note proposals as inbox cards with diff, reason, batch approve and batch undo.
7. **Drive as read-only source library.** Index `G:\` for search; notes cite sources, never copy them.
8. **Git-backed vault** for history and optional off-machine backup.
9. **Keep BookShelf's safety rules:** screening before disk, `data-private/` never enters, single
   serialized writer, provenance labels.
10. **Ask (later).** Answers only from your notes, with citations and an honest empty answer.

Suggested order: K1 vault + Bookshelf tab → K2 search → briefing packs → K3–K4 propose/approve/undo
with screening → agents connected + task records → K6 imports + Drive index → K7 roles and batch
review.
