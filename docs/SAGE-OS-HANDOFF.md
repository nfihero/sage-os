# Sage OS — handoff for a fresh session

Context primer so a new session can hold **Sage OS** and **BookShelf** (`nfihero/BookShelf`) in mind at
once. Written 30 Sep 2026 from the code, the running system and the build, not from memory; each
section says what was checked. Read with `docs/STATUS.md` (built / broken / next) and
`docs/ROADMAP.md` (phases). BookShelf's own primer is `docs/HANDOFF.md` in its repo, read for this
document (its §6 already sketches the integration from BookShelf's side).

Legend: **works** = exercised end to end · **untested live** = code exists, never run against the real
system · **planned** = not built.

---

## 1. What Sage OS is

- **One local workspace in a browser tab** where the owner (one person, a finance + AI student) talks to
  **Claude Code** (cloud, his subscription) and **Hermes** (a local agent on his RTX 5070 Ti) side by
  side, watches their work, and approves anything risky from a single inbox.
- **Problem it solves:** the agents' state was scattered across Hermes Desktop chats, terminals, a
  kanban CLI and log files; nothing showed what the GPU was doing or what was blocked on him.
- **Division of labour (design intent):** Claude plans and reviews; local agents do the volume for free;
  the human approves what matters. Phase 2 (today) gives chat + approvals; Claude *orchestrating*
  Hermes is Phase 4 (planned).
- **Users:** one today. Not multi-user, not hosted. Name rationale: `docs/MISSION.md`.
- **Product direction (user, 30 Sep 2026):** fold **BookShelf's idea** — an approval-gated personal
  knowledge base kept as plain markdown — **into Sage OS as a built-in module ("Bookshelf")**, and treat
  Sage OS as a **potential full product**, not only a personal dashboard. The Swift code is not reused;
  the module is rebuilt in Sage OS's stack (§5). Pillars: agent hub · approvals inbox and safety ·
  Bookshelf knowledge base. See `docs/MISSION.md` and `docs/ROADMAP.md`.

## 2. Current state (checked 30 Sep 2026)

| Area | State | How checked |
|---|---|---|
| Hub (FastAPI) + UI (React) | **works**, v0.3.0 | `pytest` 16/16 pass; `npm run build` clean (tsc + vite); hub running, `/api/smoke` 12/12 |
| Live dashboard: board, GPU/RAM lane, service health, safety feed, sessions | **works** | Phase 1 gates (README history): task visible 4.8 s after CLI create, model swap 0.3 s, guard block 0.3 s, router down/up detected |
| Claude Code pane (Agent SDK, subscription login) | **works** | Phase 2 gate: `Write` request → inbox card → *Allow once* → file written; *Deny + note* → no write, note reached Claude verbatim |
| Hermes chat pane (gateway sessions API) | **works** incl. multi-turn | 3-turn test today, turns 2–3 in 0.9 s (needs the hub's runtime pin, §7 #9) |
| Inbox: Claude permissions | **works** | gate above |
| Inbox: Hermes `approval.request` | **untested live** | code maps it (`hermes_chat.py`); no Hermes run has raised one through Sage OS yet |
| Inbox: kanban `needs_input` → reply + unblock | **untested live** | card appears for blocked task `t_549737c1`; reply path (`hermes kanban comment` + `unblock`) never clicked |
| Subscription usage meter | **works, limited** | CLI sends `rate_limit_event`; it omits `utilization` until near a limit, so UI shows "OK + reset time" |
| Visuals (phosphor theme, WebGL agent orbs, handoff arcs, boot screen, screen texture) | **works** | screenshots; orbs/arcs verified by event checks |
| Cross-device (Tailscale), app login | **planned** (Phase 3) | — |
| Claude orchestrating Hermes (fleet MCP tools) | **planned** (Phase 4) | — |
| Claude reviewing worker output | **planned** (Phase 5) | — |
| Knowledge layer of its own | **none** | hub stores only its events and Claude transcripts |
| Git | first commit made with this doc; **no remote**, no CI | `git log` before: "no commits yet" |

## 3. Architecture and stack

```
browser (127.0.0.1:8787) ──WS /ws + REST──► hub (FastAPI, Python 3.14)
                                               ├─ adapters (poll, read-only): kanban.db · state.db · router /models
                                               │   · nvidia-smi/psutil · guardian + write-guard logs
                                               ├─ ClaudeManager ──► Claude Agent SDK ──► claude.exe (Desktop app's) ──► Anthropic
                                               ├─ HermesChat ─────► Hermes gateway :8642 (sessions API, SSE)
                                               ├─ hermes CLI ─────► kanban comment / unblock (writes)
                                               └─ Inbox (in memory) · Store (SQLite data/hub.db)
Hermes (separate install, %LOCALAPPDATA%\hermes): gateway :8642 → llama.cpp router :18434 (1 model on GPU)
                                               guardian sidecar :18435 (granite-guardian 8B, CPU)
```

| Layer | Detail (versions checked with `pip list` / `package-lock.json` / `--version`) |
|---|---|
| Hub | Python 3.14.7 · FastAPI 0.142.1 · uvicorn 0.54 · websockets 17.1 · httpx 0.28 · psutil 7.2 · claude-agent-sdk 0.2.162 |
| UI | React 19.3 · Vite 7.3 · Tailwind 4.3 · TypeScript 5.9 · three 0.186 + @react-three/fiber 9.8 (orbs, lazy-loaded) · fonts Rajdhani / JetBrains Mono / Doto |
| Runtime | Node 24.14, npm 11.11 (build only); Windows 11 Education 26200; RTX 5070 Ti 16 GB (driver 616.92); 31 GB RAM |
| Run | `start.cmd` → creates `hub\.venv` + builds `ui\dist` on first run → `python -m sage_os_hub` serves API + UI on **127.0.0.1:8787 only** (refuses other hosts) |
| State | `data/hub.db` (events, panels, Claude sessions + transcripts) · Hermes owns its own state (`kanban.db`, `state.db`) · UI prefs in `localStorage` |
| Config | `config.toml` (ports, Hermes paths, poll intervals, Claude workspaces, profile labels) |
| Deploy | none — local process started by the user; not a service, not containerised |
| Hermes | Hermes Agent 0.21.5 (`hermes-agent` commit `ec5f441`, 29 Sep) · llama.cpp CUDA build 10964 · models: Qwen3.6-35B-A3B (default), Gemma 4 26B-A4B, Qwen3.8-27B ×2, Gemma 4 12B, granite-guardian 8B |

## 4. The agent model

| | Claude Code | Hermes |
|---|---|---|
| Defined by | Agent SDK options in `claude_agent.py` (Claude Code preset system prompt + Sage OS append) | Hermes profile **`default`** (only profile): `config.yaml`, `SOUL.md`, skills, memories |
| Model | user's subscription; per-session model pick (default/Opus/Sonnet/Haiku) | local; default Qwen3.6-35B-A3B; one model resident (`models_max: 1`) |
| Invoked | Claude pane → `POST /api/claude/sessions/{id}/send` → `ClaudeSDKClient` | Hermes pane → gateway sessions API (SSE); kanban dispatcher spawns workers; Hermes Desktop; cron |
| Tools | Claude Code's built-ins; `setting_sources` user+project+local; `AskUserQuestion` disabled | Hermes toolsets (terminal **local** backend, file tools, kanban, browser …) |
| Permissions | Claude Code `default` mode; anything not pre-allowed → `can_use_tool` → **Sage OS inbox** (allow once / for session / deny + note) | `pre_tool_call` hooks: **write guard** (Drive `G:\` read-only, protected dirs, writes only under 5 roots) + **guardian** (granite screens every terminal command, fail-closed); Hermes approvals |
| Isolation | cwd chosen from 4 configured folders; **not sandboxed** (filesystem/network as the user, behind prompts) | **not sandboxed** (Docker retired 19–21 Sep); hooks are the boundary |
| Concurrency | one turn per session; several sessions can run at once (no global cap) | one run per chat pane; kanban `max_in_progress: 1`; all local turns serialise on one GPU model |
| Output to user | streamed into the Claude pane; transcript in `hub.db`; usage meter | streamed into Hermes pane; transcript in Hermes `state.db`; board + Activity feed; Desktop |
| Identity | Sage OS session id `cs_…` + Claude `session_id` | profile `default` + session id (`api_…`, `2026…`) ; kanban task/run ids |

Rough activity, for sizing (from logs/DBs): ~800 guardian-screened terminal commands 13–29 Sep; the
retired `sage` profile had 57 sessions in 12 days (chats of 70–125 messages; 42 kanban worker runs).

## 5. What Sage OS needs from a knowledge backend (integration contract)

Framing after the 30 Sep direction: this is the contract for the **Bookshelf module inside Sage OS**
(rebuilt, not the Swift app). It is still written as a contract so the module's boundary stays clean —
agents should reach it only through these surfaces, never through its files directly for writes.

| Question | Answer from the Sage OS side |
|---|---|
| Query/search or read-by-path? | **Search is required.** Agents today find notes by `grep`/`find` in the terminal (every call guardian-screened, ~1–1.5 s overhead each). Read-by-path alone would not replace that. BookShelf having no search (its B1) is the gating gap. |
| Do agents write knowledge? | **Yes.** Observed: Hermes acted as an Obsidian "librarian" (reorganised notes, created topic notes, added cross-links), daily runs created/updated 3–5 notes each, outlines like `SAGE-OUTLINE.md`. |
| Per-write approval: fits or breaks? | **Fits for chat-driven writes** (Sage OS already has an inbox designed for approvals). **Breaks for background/kanban bulk writes** (a single librarian run touched dozens of files) unless batches can be approved as one unit or trust is per agent. |
| Transport | **MCP first** (Claude Agent SDK and Hermes both speak MCP; Hermes has none configured yet). **HTTP/WS** for the Sage OS hub to list/approve proposals in its inbox. **Direct filesystem reads** acceptable. |
| Volume | *Estimate from history, not measured:* per agent session 5–50 reads, 0–10 proposed writes; background librarian/daily runs 20–50 proposed writes in a burst. |
| Latency / real-time | Reads < ~300 ms are fine (a local LLM turn is 1–30 s). Writes are async (approval). Only "real-time" need: a new proposal should reach the Sage OS inbox within ~5 s (current board poll interval). |
| Identity / auth | No user auth today (localhost only; Phase 3 adds Tailscale + passkey or token, undecided). Agents **are** distinguishable: `claude:<session>`, `hermes:default:<session>`, `kanban:<task>/<run>` — usable as BookShelf's proposed `origin: agent` + agent id. Who owns auth between the two projects: unknown — needs confirmation from the user. |
| Local-only? | **Local-only by principle.** No hosted component. Phase 3 reaches the same PC over a private tailnet. |
| Implementation language | **User direction (30 Sep 2026): don't reuse BookShelf's Swift; rebuild the knowledge core in Sage OS's own stack.** Proposed: **Python**, matching the hub — runs natively on this Windows PC, stdlib SQLite FTS5 gives search (BookShelf's B1) for free, official MCP Python SDK, shares the hub's venv/tests. BookShelf becomes the *spec* (DESIGN.md, invariants I1–I9, vault format), not the code. Final choice of language and of repo (inside `sage-os` vs separate) — needs confirmation from the user. |
| Carrying BookShelf's invariants into Python | I1 (no write without approval) is **type-enforced in Swift** (`ApprovedChange.init` is `internal`); Python has no access control, so enforce it by **process boundary**: agents get only an MCP server with read + `propose_*` tools; the single writer process applies a change only with an approval token minted by the review path (Sage OS inbox). I2 journal → SQLite table with before/after blobs (also fixes BookShelf's single-writer JSON journal). I4 screening and I8 uid links port directly. I5 (core imports no UI framework) holds naturally. |
| Existing knowledge stores | `C:\Users\you\Obsidian Vault` (8 topic folders: Inbox, Career, Finance, AI_Technology, Skills, Projects, Companies, Daily), `C:\Users\you\llm-vault` (Zettelkasten-style: 00-inbox … 90-system; origin unknown — needs confirmation from the user), Hermes memories/skills, Google Drive `G:\` (read-only source documents). |

## 6. Environment constraints (cost a fresh session time otherwise)

| Constraint | Consequence |
|---|---|
| **Windows 11, not macOS.** No Swift toolchain on this PC (verified: `swift` resolves to `~\.local\bin\swift.bat`, a stale alias for a deleted Hermes profile that runs `hermes -p swift`). | BookShelf's app cannot run here; WikiCore has never been built on Windows. |
| Claude Desktop is the **Store (MSIX) build**: `%APPDATA%\Claude\…` is virtualised for processes inside it. | `claude.exe` from a normal terminal is at `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\<ver>\claude.exe`; the hub's `find_cli()` searches both. |
| Agent-SDK `claude.exe` needs its own login: `"<path>\claude.exe" auth login` in a normal terminal (`/login` inside the SDK fails). In PowerShell prefix `&`. | Hub polls `auth status` and shows a banner until signed in. |
| Processes started from Claude's tool shells **die when the turn ends**. | Start long-lived services detached: `Invoke-CimMethod Win32_Process Create`. |
| **Hermes updates break local customisations** (4+ times in Sep): preset hook `.pth` wiped, gateway scripts regenerated, binaries moved. | Run `agent-hooks\install-preset-hook.py --check`, restart the gateway, confirm presets (`n-cpu-moe` 12/6 for the MoE models). The hub smoke test names broken Hermes surfaces. |
| Hermes Desktop stores its launch profile separately (`%APPDATA%\Hermes\active-profile.json`). | Profile changes need both `hermes profile use` and that file. |
| One GPU, `models_max: 1`; dense models must not offload (WDDM paging → 0.91 tok/s). | First local turn after a swap costs ~20–30 s. Don't load other GPU work during tests. |
| Windows "Animation effects" appears off on this PC (browsers report reduced motion). | App Motion setting defaults to *Full*; preview panes may also pause `requestAnimationFrame` when hidden. |
| Python 3.14 (Store install) for the hub venv; Hermes ships its own Python 3.14 and venv. | Don't mix them; the hub never imports Hermes code. |
| Hub health polling is visible in Hermes `agent.log` (one access line per check). | Poll interval 5 s for health (was 2 s). |

## 7. Decisions reversed or superseded — the conclusion is the bold part

| # | Was | **Now** | Why |
|---|---|---|---|
| 1 | Name "Agent OS", folder `agent-os`, package `agent_os_hub`, header `X-Agent-OS` | **Sage OS**, `C:\Users\you\sage-os`, `sage_os_hub`, `X-Sage-OS`, env `SAGE_OS_*` | User chose the name (mentor · green · SAGE nod). |
| 2 | Tron cyan/orange default theme | **Phosphor green default**; Tron + eDEX amber still selectable | User preference. |
| 3 | CRT mode (curved glass, bezel, power-on/off) | **Removed**; constant scanlines + film grain + rolling refresh bar | User: looked bad, unnecessary. (A real barrel warp was rejected earlier: clicks would land off-target.) |
| 4 | Safety feed as a permanent right rail | **Hidden drawer**, chip + toast only when something new is blocked | Attention only when needed. |
| 5 | Claude "spend today ($)" | **Subscription usage meter** from `rate_limit_event` | Subscription, not API billing. |
| 6 | Phase 1 "every route is GET" (test enforced) | **Write routes exist** behind `X-Sage-OS` header + local Host/Origin (tests enforce that instead) | Phase 2 needs chat + approvals. |
| 7 | Motion follows the OS | **Motion defaults to Full**, user-switchable | OS reduced-motion silently disabled the visuals the user asked for. |
| 8 | Hermes profiles `sage` (main) + `default` | **Only `default`**, labelled "Hermes" in the UI. `sage` deleted 30 Sep after export (`hermes\profile-exports\sage-20260930-011911.tar.gz`, Markdown in `hermes-workspace\session-exports\sage\`, outline `hermes-workspace\SAGE-OUTLINE.md`). Kanban default assignee → `default`. | Avoid "sage inside Sage OS"; one profile is simpler. |
| 9 | Hermes chat turn-2 401 blamed on llama.cpp router ownership (Desktop vs gateway) | **Wrong.** Hermes re-resolves a bare `custom` provider from turn 2 (placeholder key). **Hub fix: `HermesAPI._runtime_pin`** sends provider + model + `require_model_lock` every turn. Verified 3/3 turns today. | Reproduced with the gateway owning the router; fix added by a separate session 30 Sep. |
| 10 | Harness: consider replacing Hermes (OpenCode / Goose / Claude Code on local models) | **Keep Hermes** for kanban, gateway, hooks; adapters keep it swappable | Only Hermes has a kanban dispatcher; not re-evaluated since. |
| 11 | Docker sandbox for Hermes terminal | **Local terminal + guardian + write guard** | Docker blocked too much real work. |
| 12 | Bloom via post-processing pass | **In-shader halo** per orb | GPU cost next to the models. |
| 13 | Icon: square mark → light-cycle drafts | **S-trail with sage leaves** (`ui/public/favicon.svg`) | User picked concept C. |
| 14 | `claude.exe` path `%APPDATA%\Claude\…`; login via `/login` | **Packages path + `auth login`** | MSIX virtualisation; slash commands don't run in the SDK. |
| 15 | Services launched from tool shells | **Detached via WMI** | They were killed at turn end (explained several "sidecar down" episodes). |
| 16 | Use BookShelf's Swift `WikiCore` as the backend (via an MCP server over it) — the plan in BookShelf's HANDOFF §6 | **Rebuild the knowledge core in Sage OS's stack** (proposed: Python); BookShelf's docs + invariants are the spec | User direction 30 Sep 2026. Removes the Windows/Swift mismatch; costs the type-level I1 guarantee (replaced by a process boundary, §5). |

## 8. Known issues and blockers (most → least blocking for the user)

1. **Hermes updates can silently degrade the stack** (MoE experts all on CPU, gateway env lost). Mitigated by checklist + smoke test, not prevented.
2. **The runtime pin depends on Hermes internals** and disables Hermes' `fallback_model`; a Hermes update may change the branch it relies on (re-test multi-turn after every update).
3. **Single GPU model:** Hermes chat, kanban workers and Desktop queue behind one resident model; model swaps cost 20–30 s.
4. **Claude can't yet act on Hermes** except via `Bash` + `hermes` CLI with per-command approval (fleet MCP tools are Phase 4).
5. **Two inbox paths untested live:** Hermes approval requests, kanban reply-and-unblock.
6. **Desk-only:** no remote access, no app login (Phase 3); the hub has no auth beyond localhost binding.
7. **No remote, no CI, no backups** of the Sage OS repo; first commit only now.
8. **Stale alias scripts** `swift.bat`, `coder.bat`, `guardian.bat` in `~\.local\bin` point at deleted Hermes profiles; `swift.bat` shadows the real `swift` command name.
9. Usage meter shows "OK" rather than a % until a window nears its limit (CLI behaviour).
10. Phone layout is a first pass, never tested on a real phone.

## 9. Open questions before Sage OS and BookShelf can be joined

1. **Language and home of the rebuilt core:** Python inside the `sage-os` repo (e.g. `knowledge/` package + MCP server), or a separate repo? And does the macOS BookShelf app keep living as a reader/reviewer of the same vault format, or is it retired? (unknown — needs confirmation from the user)
2. **Which vault becomes canonical:** `Obsidian Vault`, `llm-vault`, or BookShelf's managed knowledge base — and are existing notes imported (BookShelf's Obsidian importer)?
3. **Is any vault synced by Google Drive?** Drive sync + BookShelf's atomic renames/journal could fight. (unknown — needs confirmation from the user)
4. **Where does review happen** — Sage OS inbox (proposals as inbox cards), BookShelf's review UI, or both? Batch approval and per-agent trust levels?
5. **Which agents may propose writes:** Claude only, Hermes too, kanban workers?
6. **Agent provenance format:** accept `origin: agent` + `agent: claude:<session> | hermes:default:<session>`?
7. **Product scope:** "potential full product" — for whom beyond you (students? finance learners? anyone with a local GPU?), and does it keep BookShelf's "personal memory, no collaboration" stance? Product-izing also hits hard dependencies: Windows-only today, Hermes install, a Claude subscription, a capable GPU.
8. **Private financial data** (bank/card statements under `data-private/`): must it stay out of the knowledge base entirely?
9. **Auth ownership** once Phase 3 exposes Sage OS to the tailnet: does BookShelf trust Sage OS's identity, or authenticate agents itself?
