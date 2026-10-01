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
| 3 | Cross-device: Tailscale Serve, app login (passkey or token), phone layout | A phone approves a request over the tailnet | Next |
| 4 | Claude as orchestrator: fleet MCP tools (`fleet_status`, `task_create`, `task_comment`/`unblock`, `ask_agent`) | Claude delegates a task that a local agent finishes | Planned |
| 5 | Claude as reviewer: review on `request_review`, handoff animations | One task goes through changes, then approval | Planned |
| 6 | Rooms and outside agents: multi-agent threads, ACP and A2A adapters | — | Planned |

## Bookshelf track (30 Sep 2026 — home and vault decided; step order still proposed)

The BookShelf project (`nfihero/BookShelf`) is **retired**. It is the **spec**, not the code: its
DESIGN.md, invariants I1–I9 and vault format are carried over, and the module is rebuilt as a Python
package inside this repo (DECISIONS D2). New local vault, not on Drive; `G:\` is a read-only source
(D3). Integration ideas awaiting selection: DECISIONS P1.

| Step | Scope | Gate |
|---|---|---|
| K1 | Vault format + read: markdown with YAML frontmatter, uid identity, no absolute paths (I8); pick the canonical vault | Sage OS lists and renders notes from the vault |
| K2 | Search: SQLite FTS5 index rebuilt from files (vault stays the source of truth, I3) | A query returns ranked notes in < 300 ms |
| K3 | Propose → approve → commit: agents propose, the **Sage OS inbox** approves, a single writer applies with a SQLite journal and batch undo (I1, I2, I9) | An agent's proposal lands only after approval; undo restores bytes exactly |
| K4 | Screening before disk (I4) | A proposal containing a key is refused before anything is written |
| K5 | MCP server for agents: `search_notes`, `read_note`, `propose_note`, `list_proposals`; `origin: agent` + agent id provenance | Claude and Hermes both read and propose through MCP |
| K6 | Import existing vaults (Obsidian Vault, llm-vault) with structure preserved | Existing notes searchable in Sage OS |
| K7 | Review at scale: batch approvals, per-agent trust levels | A 20-note librarian run is approved in one decision |

Suggested interleave: K1–K3 before Phase 4, so the fleet tools and the knowledge tools share one MCP
surface; Phase 3 can run in parallel.

## Architecture track (30 Sep 2026 — DECISIONS D4, D5; recorded "for now")

Goal: Sage OS owns the core (board, inbox, Bookshelf, safety policy, shared tools); agents and models
plug in through connectors; Hermes becomes optional. No custom llama.cpp runtime.

| Step | Scope | Gate |
|---|---|---|
| A1 | Sage OS interfaces for **model providers** (any OpenAI-compatible endpoint) and **agent connectors**; move the existing Claude and Hermes code behind them | Claude and Hermes panes work unchanged through the new interfaces |
| A2 | Bookshelf K1–K3 as Sage OS's own (see track above) | — |
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
