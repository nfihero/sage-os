# Sage OS — status

**Version 0.5.0 · 1 Oct 2026.** Checked today: `pytest` 39/39, `npm run build` clean, hub `/api/smoke`
17/17, Hermes gateway / router / guardian sidecar all healthy, Claude Code signed in, Hermes multi-turn
chat 2/2 turns through the connector layer. Version history: `CHANGELOG.md`.

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
| Approvals inbox (Claude) | allow once / for session / deny with note — verified end to end |
| Subscription usage | 5-hour / 7-day windows from the CLI's `rate_limit_event` (shows "OK" until near a limit) |
| Visuals | phosphor theme (+ Tron, eDEX amber), WebGL agent orbs with bloom, handoff arcs, Doto dot-matrix accents, boot screen, constant scanlines/grain, S-trail icon, Motion setting |
| Safety of the hub itself | localhost-only bind; write routes require `X-Sage-OS` + local Host/Origin; no Hermes code imported; smoke test names broken Hermes surfaces |

## Untested live (code exists)

- Hermes `approval.request` → inbox → `/v1/runs/{id}/approval`
- Kanban `needs_input` → inbox reply → `hermes kanban comment` + `unblock`
- Phone layout on a real phone

## Not built

- Cross-device access and app login (Phase 3)
- Fleet MCP tools / Claude orchestration (Phase 4), Claude review loop (Phase 5)
- **Bookshelf** writes and agent use: propose/approve/undo, screening, MCP tools, briefing packs, imports, Ask (K3–K11); meaning-based search (D10)
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

## Next

1. K3 (A1 done 30 Sep; K1, K2 done 1 Oct). Home, language, vault location and adopted ideas are decided (`DECISIONS.md` D2,
   D6, D7); architecture direction recorded (D4).
2. Phase 3 (Tailscale + login + phone).
3. Exercise the two untested inbox paths with a real Hermes approval and the blocked parser task.

## Gate results

| Phase | Gate | Result |
|---|---|---|
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
| K2 | A query returns ranked notes in < 300 ms | pass — 2,006-note scratch vault: 8 queries ≤ 12 ms in the index, ≤ 13 ms round trip; from-cold index ~12 s; delete-and-rebuild gives identical results (test); pytest 39/39; smoke 17/17 |
| K1 | Sage OS lists and renders notes from the vault; the button opens the folder | pass — scratch vault of 6 notes listed and rendered (table, code, links by uid, agent label, 3 problems named on a broken note); a file added while open appeared without reload; on the real hub Open vault opened Explorer at `data\vault`; pytest 32/32; smoke 16/16 |
| A1 | Claude and Hermes panes work unchanged through the connector interfaces | pass — new Claude session (Haiku) replied via Bash; a Write request reached the inbox, *Deny + note* blocked it and the note reached Claude; Hermes answered 2 turns; pytest 22/22; smoke 15/15 |
