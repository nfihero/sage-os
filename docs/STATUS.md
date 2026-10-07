# Sage OS — status

**Version 0.12.0 · 6 Oct 2026.** Checked today: `pytest` 193/193, `npm run build` clean, hub `/api/smoke`
18/18; the local engine served Gemma 4 12B from the existing Hermes files and answered a Deal Club question
from the outreach playbooks with both shown in the Reading strip. **Claude Code's sign-in for Sage OS has
expired** ("OAuth session expired"): run `claude auth login` again (README). Version history: `CHANGELOG.md`.

## Works

| Feature | Notes |
|---|---|
| Live board (Hermes kanban) | read from `kanban.db` (read-only), task drawer with runs/events/comments, light-cycle trail on column change |
| GPU lane | resident model + state, VRAM and RAM dot-matrix gauges (llama.cpp vs other), guardian sidecar, model swaps |
| Service health | gateway, router, guardian lights; router restarts detected even when faster than a poll |
| Safety | guardian + write-guard decisions; hidden drawer, red chip + toast only on new blocks |
| Claude Code pane | Agent SDK on the user's subscription; session tabs, folder + model per session; streamed replies; interrupt |
| Hermes pane | gateway sessions API; open/continue/start chats; tool progress; stop; multi-turn via the hub's runtime pin |
| Connectors (A1) | agents (Claude Code, Hermes profiles) and model servers (any OpenAI-compatible endpoint) behind one interface; set in `config.toml` `[agents]` / `[[models]]`; `GET /api/agents`, `GET /api/models`, `/api/agents/{id}/sessions/...`; smoke checks per agent |
| Bookshelf reader (K1) | vault at `data/vault` (`[bookshelf] vault`); top-bar BOOKSHELF opens a reader — notes by folder, rendered markdown or source, links resolved by uid, agent-written notes labelled, contract problems listed; new or edited files appear within ~5 s; **Open vault** shows the folder in Explorer. Read-only until K3 |
| Bookshelf search (K2) | FTS5 keyword search as you type: ranked (title > tags > body), stemmed + prefix, highlighted snippets; index is a cache at `data/bookshelf-index.db`, kept in step by the vault watcher, rebuildable (`POST /api/vault/reindex`) |
| Bookshelf tools for agents (K5) | Claude (in-process) and Hermes (MCP at `/mcp/hermes/default/`) can `search_notes`, `read_note`, `propose_note`, `list_proposals`, `search_sources`, `read_source`; agent id set by Sage OS; sensitive note text withheld |
| Source library (S1) | Bookshelf → Sources: read-only copy of chosen Drive folders in `data/sources/drive` (499 files, 494 searchable), Sync now, left-out list (private by name or content, media, binaries, Google shortcuts), search + text reader |
| Notes from sources (K6) | Bookshelf → Sources → Build notes: *Propose starter notes* (markdown imported verbatim + a collection note per folder, one inbox card per area); *Draft* briefs Hermes to propose cited concept notes; collection status new / in inbox / in vault; re-runs skip what's built or waiting |
| Guide and tour (D18) | **? GUIDE**: why Sage OS exists (team analogy, rules, limit, live counts) + a 7-step panel tour; opens on first visit or `?guide`; empty Bookshelf shows how notes arrive; notes show *Built from* with a link into Sources; demo script `docs/DEMO.md` |
| Briefing packs (K8, D20) | each message is searched against notes and sources (key terms weighted by rarity; collection notes and duplicate copies left out); the best matches go with it as data; a **Reading** strip under the message lists them and anything the agent opened itself; ✕ leaves an item out from then on and corrects the agent (stop and resend if it is still answering); 📖 toggle per chat; every pack recorded in `data/briefings.db` |
| Local engine (D22.3) | **MODELS**: hardware check (RAM, NVIDIA VRAM, Apple Silicon, Vulkan/CPU), catalog of 8 models rated fits / tight / too big, install of the official llama.cpp build and model downloads (resumable, SHA-256 checked; not yet run on a fresh machine), models already on disk, start/stop; serves on 127.0.0.1:8790; a leftover server from a killed hub is stopped on the next start |
| Chat connector (D22.2) | one chat for any OpenAI-compatible AI (the engine, ChatGPT, Gemini, Ollama); Bookshelf tools as function calls run by Sage OS (no shell, no files); transcripts in hub.db; **Chat** tab in the Local pane |
| Google Drive connector (D22.5) | Google Docs / Sheets / Slides exported through the Drive API (read-only consent, the user's own OAuth client, PKCE) and indexed like other files; **waiting for the user's OAuth client**, so not yet run live |
| Approvals inbox (Claude) | allow once / for session / deny with note — verified end to end |
| Bookshelf writes (K3) | agents propose (create / update / archive); inbox card shows each change's diff; *Approve & file* applies the batch through one journaled writer; History tab undoes a batch byte for byte; stale and contract-breaking proposals refused; pending proposals survive restarts |
| Secret screening (K4) + *Save anyway* | proposals with secret-looking content (keys, tokens, passwords, card / ID / bank numbers) are held in the inbox in memory only, never stored; *Reject* or two-step *Save anyway*; only the category is ever shown or logged; sensitive notes' text stays out of search (🔒) |
| Subscription usage | 5-hour / 7-day windows from the CLI's `rate_limit_event` (shows "OK" until near a limit) |
| Visuals | phosphor theme (+ Tron, eDEX amber), WebGL agent orbs with bloom, handoff arcs, Doto dot-matrix accents, boot screen, constant scanlines/grain, S-trail icon, Motion setting |
| Safety of the hub itself | localhost-only bind; write routes require `X-Sage-OS` + local Host/Origin; remote hosts only by exact name; CSP + no framing + no API docs; agent output treated as untrusted (no remote images, notes marked as data, proposal caps); secret-looking guard-log commands hidden; Claude sessions only in configured workspaces; vibe-security audit 1 Oct (D14) |

## Untested live (code exists)

- Hermes `approval.request` → inbox → `/v1/runs/{id}/approval`
- Kanban `needs_input` → inbox reply → `hermes kanban comment` + `unblock`
- Phone layout on a real phone

## Not built

- Cross-device access and app login (Phase 3)
- Fleet MCP tools / Claude orchestration (Phase 4), Claude review loop (Phase 5)
- **Bookshelf** next: batch review + trust (K7), task records, git backup, Ask (K9–K11); updating collection notes when sources change; meaning-based search (D10: packs and search are keyword-only, so wrong-but-wordy notes still slip in); OCR is now step S2 (D19)
- D22 product work: note sync between devices (B), the optional relay (C), API keys entered in the app (today: environment variables), installers that bundle Python and the UI, Google verification for the Drive scope
- Agent/model connector interfaces and a Sage OS-owned task board (architecture track A1–A5)
- Packaging/installer, CI (private remote exists: `nfihero/sage-os`)

## Known issues (ranked)

1. Hermes updates break local customisations (preset hook, gateway env) — checklist + smoke test only.
2. The Hermes runtime pin relies on Hermes internals and disables `fallback_model`; re-test after updates.
3. One GPU model at a time; local turns queue; 20–30 s per model swap.
4. Claude can only reach Hermes via `Bash` + CLI with approval until Phase 4.
5. No CI; the private remote is pushed only on request.
6. Stale alias scripts `swift.bat`, `coder.bat`, `guardian.bat` in `~\.local\bin` (deleted Hermes profiles).
7. Usage meter has no percentage until near a limit.
8. Hermes caches the Bookshelf MCP tool list at first connect: after Sage OS adds tools, toggle `mcp_servers.bookshelf.enabled` off and on in Hermes' `config.yaml` (or restart the gateway), or Hermes won't see them.
9. The local engine and Hermes' router share one GPU: loading a big model in both at once runs out of
   VRAM (the engine panel reports it if its server dies).
10. The model catalog lives in the hub package (`engine/catalog.json`); an installer must ship it.

## Next

1. Demo of the Deal Club workflow (D22): sign Claude in again; save the Google OAuth client and connect
   Drive so the pitch framework and target briefing (Google Docs) come in; *Build notes* on the Deal Club
   collections and approve them; rehearse `docs/DEMO.md`.
2. D22 product work in the order the user picks: note sync (B), meaning-based search (makes packs smarter),
   S2 OCR, API keys in the app, installers; then phone access and the relay (C).
3. Exercise the two untested inbox paths with a real Hermes approval and the blocked parser task.

## Gate results

| Phase | Gate | Result |
|---|---|---|
| K8 | An agent's reply uses a fact that exists only in your notes, and the strip shows where it came from | pass — local Gemma 4 12B (no Hermes, no cloud) described the three-email outreach sequence from the two playbooks in 14 s, citing both; both shown in the strip; ✕ struck an item live; phone width checked; pytest 193/193 |
| A5 | A machine with no local AI gets a working local model through Sage OS | partly — engine started a model from files already on disk and served chat; the download path is covered by tests (resume, checksum, unsafe archives) but not yet run against GitHub / Hugging Face |
| S3 | A Google Doc's text is found by search | built, not run live — tests cover consent (PKCE, one-time state), path lookup, export and re-sync; needs the user's OAuth client |
| 1 | All panels show live data | pass |
| 1 | CLI-filed task appears on the board within 10 s | pass — 4.8 s |
| 1 | Loading a model changes the GPU lane within 5 s | pass — 0.3 s to *loading*, 1.2 s back to idle |
| 1 | A blocked write-guard test appears in the safety feed | pass — 0.3 s |
| 1 | Router down → red light, up → green | pass — red 2.5 s, green 1.2 s after respawn |
| 1 | A Hermes update leaves the dashboard working | by construction (no Hermes imports, smoke test); confirm on next update |
| 2 | A Claude permission prompt reaches the inbox | pass — card ~4 s after the message |
| 2 | Answering it in the inbox releases Claude | pass — *Allow once* clicked; file written |
| 2 | Deny with a note | pass — nothing written; note reached Claude verbatim |
| 2 | Write routes refuse requests without the header | pass — HTTP 403, covered by tests |
| K6 | A source becomes approvable starter notes and agent drafts, nothing written before approval | pass — real Drive source: 51 starter notes in 9 cards (25 collection notes, 26 markdown imports), vault unchanged until approval; Hermes read 4 FIN 101 documents via `read_source` and proposed 5 cited concept notes (it ignored the tags/source fields; brief tightened); pytest 164/164 |
| S1 | Chosen Drive folders searchable in Sage OS and by agents, Drive untouched | pass — 499 files copied in ~4½ min, 494 with text, 9 held back as private, 0 files on `G:\` modified, "cost of capital" → FIN 101 lecture in 3.7 ms; two false-positive bugs found on real files and fixed (glued spreadsheet cells, decimals) |
| K5 | Claude and Hermes both read and propose through MCP | pass — real hub: Claude searched and proposed a note (approved, then undone byte-exact); Hermes searched, read and quoted it, proposed a tag (rejected); `hermes mcp test bookshelf` found the tools |
| K4 | A proposal containing a key is refused before anything is written | pass — two proposals with a fake key held (202, value never echoed); byte search of hub.db, journal, index, vault and log found it nowhere; override checked live: one rejected, one *Saved anyway* (two clicks) → filed, `screened` recorded, text out of search; pytest 95/95 (incl. canary tests) |
| K3 | An agent's proposal lands only after approval; undo restores bytes exactly | pass — scratch vault (2,006 notes): proposal from `claude:cs_k3live` left the vault fingerprint unchanged until *Approve & file*; after approval the new note was searchable at once; *Undo* returned the identical SHA-256 fingerprint; tests cover stale refusal, rollback mid-write, crash recovery, restart; pytest 53/53 |
| K2 | A query returns ranked notes in < 300 ms | pass — 2,006-note scratch vault: 8 queries ≤ 12 ms in the index, ≤ 13 ms round trip; from-cold index ~12 s; delete-and-rebuild gives identical results (test); pytest 39/39; smoke 17/17 |
| K1 | Sage OS lists and renders notes from the vault; the button opens the folder | pass — scratch vault of 6 notes listed and rendered (table, code, links by uid, agent label, 3 problems named on a broken note); a file added while open appeared without reload; on the real hub Open vault opened Explorer at `data\vault`; pytest 32/32; smoke 16/16 |
| A1 | Claude and Hermes panes work unchanged through the connector interfaces | pass — new Claude session (Haiku) replied via Bash; a Write request reached the inbox, *Deny + note* blocked it and the note reached Claude; Hermes answered 2 turns; pytest 22/22; smoke 15/15 |
