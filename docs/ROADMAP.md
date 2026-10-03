# Sage OS — roadmap

Each phase is usable on its own and ends at a **gate**: a check that proves it works before the next
starts. No dates; the order is the plan. Source: the design doc
([Sage OS — Design](https://claude.ai/code/artifact/af65a0a6-433a-48c3-b841-33d7aedab899)), extended
on 30 Sep 2026 with the Bookshelf track.

## Agent hub track

| Phase | Scope | Gate | Status |
|---|---|---|---|
| 1 | Read-only dashboard: board, GPU lane, health, safety feed, sessions, theme | All six Phase 1 checks pass | **Done** (29 Sep) |
| 2 | Chat panes (Claude Code, Hermes) + approvals inbox | A Claude permission prompt reaches the inbox and is answered there | **Done** (29 Sep) |
| 2.5 | Visual pass: phosphor theme, agent orbs, handoff arcs, boot screen, screen texture, icon | User sign-off | **Done** (30 Sep), iterating on taste |
| 2.6 | Demo readiness (D18): guide with the why, panel tour, plain labels, teaching empty states, `docs/DEMO.md` | A first-time viewer can say what Sage OS is for and follows the files → notes loop | Built (3 Oct, v0.10.0); gate is the user's demo |
| 3 | Cross-device: Tailscale Serve, app login (passkey or token), phone layout | A phone approves a request over the tailnet | Next |
| 4 | Claude as orchestrator: fleet MCP tools (`fleet_status`, `task_create`, `task_comment`/`unblock`, `ask_agent`) | Claude delegates a task that a local agent finishes | Planned |
| 5 | Claude as reviewer: review on `request_review`, handoff animations | One task goes through changes, then approval | Planned |
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
| K8 | Briefing packs chosen **per prompt** from notes and sources, shown to you in a *Reading* strip with everything the agent read (D20; D7 idea 2) | An agent's reply uses a fact that exists only in your notes, and the strip shows the note it came from |
| K9 | Work becomes knowledge: finished tasks propose a short record; chats get "save to Bookshelf" (D7 idea 3) | A finished task's record arrives in the inbox as a proposal |
| K10 | Git-backed vault: each approved batch is a commit; push to a private remote only on request (D7 idea 8; personal install only) | Undo and `git log` agree after an approve/undo cycle |
| K11 | Ask: answers only from the vault, with citations and an honest empty answer (D7 idea 10) | A question with no matching notes gets "nothing in your notes" |
| later | In-app markdown editor (D6) — edits go through the single writer + journal | — |

Suggested interleave: K1–K6 are done, so the fleet tools (Phase 4) can share their MCP surface. The order
after v0.10 is still being chosen (see STATUS *Next*).

## Architecture track (30 Sep 2026 — DECISIONS D4, D5; recorded "for now")

Goal: Sage OS owns the core (board, inbox, Bookshelf, safety policy, shared tools); agents and models
plug in through connectors; Hermes becomes optional. No custom llama.cpp runtime.

| Step | Scope | Gate |
|---|---|---|
| A1 | Sage OS interfaces for **model providers** (any OpenAI-compatible endpoint) and **agent connectors**; move the existing Claude and Hermes code behind them | Claude and Hermes panes work unchanged through the new interfaces — **pass** (30 Sep: Claude chat + inbox deny, Hermes 2 turns) |
| A2 | Bookshelf K1–K3 as Sage OS's own (see track above) | **done** with K1–K3 (1 Oct) |
| A3 | **Sage OS task board** any agent can work from; Hermes kanban becomes an optional source. Current Hermes kanban contents may be cleared (D5) | A task created in Sage OS is finished by an agent and approved in the inbox, with Hermes kanban unused |
| A4 | A second local agent connector, proving Hermes is optional (candidates to verify on Windows first) | Same task runs on two different local agents |
| A5 | Environment setup: optional `llama-server` install/manage wizard (model download, GPU-fit settings) | A machine with no local AI gets a working local model through Sage OS |

Open checks before A3/A4: which agent tools work reliably on Windows; what the Hermes kanban does
that a Sage OS board must match.

## Hub breadth track (from the 30 Sep 2026 product framing; order not yet decided)

| Item | Scope | Starting point |
|---|---|---|
| H1 Model choice | Pick local or cloud model per agent / task in the UI | Hermes already has DeepSeek and OpenRouter credentials and per-task `--model`; Claude model picker exists per session |
| H2 Workflow boards | Several kanban boards for different workflows (school, job search, finance projects…) | Hermes kanban has `boards` support; Sage OS shows one board today |
| H3 More programs | Bring conversations from other tools into the hub | Phase 6 adapters (ACP, A2A); Hermes can already import Claude Code / Codex sessions |
| H4 Connected topics | Link conversations across programs by topic, feeding Bookshelf | Depends on Bookshelf K2 (search) and K5 (MCP) |

## Product track (open)

Packaging, installer, non-Windows support, onboarding without Hermes pre-installed, accounts — all
undecided until the audience is defined (see `MISSION.md`).
