# Changelog

All notable changes to Sage OS. Versions before 0.3.0 were built before the repository's first commit
and were never snapshotted; their entries record what was built and verified on those dates, not
recoverable commits. Format: [Keep a Changelog](https://keepachangelog.com/), versions follow semver
while pre-1.0.

## [Unreleased]

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
