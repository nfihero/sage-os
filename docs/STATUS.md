# Sage OS — status

**Version 0.3.0 · 30 Sep 2026.** Checked today: `pytest` 16/16, `npm run build` clean, hub `/api/smoke`
12/12, Hermes gateway / router / guardian sidecar all healthy, Claude Code signed in, Hermes multi-turn
chat 3/3 turns.

## Works

| Feature | Notes |
|---|---|
| Live board (Hermes kanban) | read from `kanban.db` (read-only), task drawer with runs/events/comments, light-cycle trail on column change |
| GPU lane | resident model + state, VRAM and RAM dot-matrix gauges (llama.cpp vs other), guardian sidecar, model swaps |
| Service health | gateway, router, guardian lights; router restarts detected even when faster than a poll |
| Safety | guardian + write-guard decisions; hidden drawer, red chip + toast only on new blocks |
| Claude Code pane | Agent SDK on the user's subscription; session tabs, folder + model per session; streamed replies; interrupt |
| Hermes pane | gateway sessions API; open/continue/start chats; tool progress; stop; multi-turn via the hub's runtime pin |
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
- **Bookshelf knowledge module** (K1–K7 in ROADMAP)
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

1. Pick the Bookshelf integration ideas (`DECISIONS.md` P1), then A1 + K1–K3. Home, language and
   vault are decided (D2, D3); architecture direction recorded (D4).
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
