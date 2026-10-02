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
