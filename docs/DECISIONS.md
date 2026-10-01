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
- **Not adopted for now:** 4 playbooks as notes · 7 Drive as an indexed source library (`G:\` stays
  read-only to agents and outside the vault).
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
  (I4) can't reach the index from Sage OS writes once K4 screens before disk; files a user drops in
  directly are indexed as they are.
- **Revisit if:** keyword results miss notes the user expects (e.g. synonyms), or the vault grows past
  ~20k notes (re-measure indexing time).

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
