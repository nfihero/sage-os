# Sage OS mission

## Mission

**An AI agent hub with a personal, growing knowledge base.** Use local and cloud models, keep the
conversations and topics from many programs in one place, run workflows on kanban boards, and build a
knowledge base your agents read and add to. In this calm control room, agents do the volume, a wise
mentor plans and reviews, and nothing important happens without your say.

## The problem

- AI work is scattered: chats in one app, a task board in a CLI, logs in files, a GPU nobody can see.
- Agents are either fully supervised (slow) or unsupervised (risky). There is no single place that
  shows *what is running*, *what is blocked on me*, and *what changed*.
- What agents learn and produce evaporates into chat history instead of compounding into knowledge
  you own.

## What Sage OS is

| Pillar | What it does | State (v0.7.0) |
|---|---|---|
| **Your choice of models** | Local models (llama.cpp via Hermes) and cloud models side by side, picked per agent or task | Partly: Claude (cloud) + Hermes local models; since v0.4.0 any OpenAI-compatible server can be connected and its models listed (`[[models]]`), but not yet picked per agent or task (H1) |
| **One hub for many programs** | Conversations and topics from different agents and apps connected in one place | Partly: Claude Code + Hermes as connectors (v0.4.0); other programs plug in through the same interface (A4, Phase 6) |
| **Kanban workflows** | Boards for different workflows, worked by agents, unblocked by you | Partly: one Hermes board shown; multiple workflow boards planned |
| **Agent hub** | Claude Code (cloud) and Hermes (local) in one workspace: chat panes, live board, GPU lane, sessions | Built (Phases 1–2) |
| **Approvals inbox and safety** | Every risky action from any agent lands in one inbox; guards (write guard, guardian) stay independent of the UI and can't be overridden from it | Built for Claude and Bookshelf proposals, with secret screening and a manual *Save anyway* override (v0.7.0); Hermes and kanban paths untested live |
| **Bookshelf** (built-in knowledge base) | Plain-markdown knowledge that grows from your conversations; agents read it and *propose* additions, with your approval, journaled undo and secret screening | Partly: read, search, approved writes with exact undo, secret screening (K1–K4, v0.4.0–v0.7.0); agent tools, imports and briefing packs next (K5–K11) |
| **Orchestration and review** | Claude delegates to local agents and reviews what they hand back | Planned (Phases 4–5) |

## Who it's for

- **Today:** one person, the founder: a finance + AI student building skills, with a local GPU and a
  Claude subscription.
- **As a product (direction set 30 Sep 2026):** people who want agents working *for* them on their own
  machine, with their data staying local. The exact audience isn't decided yet (open question 7 in
  `SAGE-OS-HANDOFF.md` §9).

## Principles

1. **Local first.** Data, models and the hub live on the user's machine; remote access only over a
   private network, never a public port.
2. **The human approves what matters.** Agents propose; people decide. Approval gets the same design
   care as any feature.
3. **Guards outlive the UI.** Safety layers sit in front of the agents themselves; the dashboard only
   shows and answers, it never widens what an agent may do.
4. **Plain files you can walk away with.** Knowledge is markdown on disk, readable without Sage OS.
5. **Honest status.** Show what is actually running, blocked or broken; no optimistic dashboards.
6. **Calm, not noisy.** Attention is spent only when something needs the human (hidden safety feed,
   inbox badges, one toast).

## Why "Sage"

1. **A wise mentor:** it plans, reviews and teaches, not only answers.
2. **The colour green:** sage is a green; the phosphor theme, agent orbs and the S-trail icon follow it.
3. **SAGE: Semi-Autonomous Agent Ground Environment:** a nod to SAGE (Semi-Automatic Ground
   Environment), the 1950s air-defence network run from rooms of CRT consoles. Here, one operator directs
   semi-autonomous agents from a ground station.

## Company framing

Company name, structure and commercial model aren't decided yet. This file states the product mission
only.
