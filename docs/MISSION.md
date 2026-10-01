# Sage OS — mission

## Mission

**Give one person a calm control room for a team of AI agents and a knowledge base that grows with
them — where the agents do the volume, a wise mentor plans and reviews, and nothing important happens
without the human's say.**

## The problem

- AI work is scattered: chats in one app, a task board in a CLI, logs in files, a GPU nobody can see.
- Agents are either fully supervised (slow) or unsupervised (risky). There is no single place that
  shows *what is running*, *what is blocked on me*, and *what changed*.
- What agents learn and produce evaporates into chat history instead of compounding into knowledge
  you own.

## What Sage OS is

| Pillar | What it does | State (v0.3.0) |
|---|---|---|
| **Agent hub** | Claude Code (cloud) and Hermes (local) in one workspace: chat panes, live board, GPU lane, sessions | Built (Phases 1–2) |
| **Approvals inbox and safety** | Every risky action from any agent lands in one inbox; guards (write guard, guardian) stay independent of the UI and can't be overridden from it | Built for Claude; Hermes and kanban paths untested live |
| **Bookshelf** (knowledge base) | BookShelf's idea folded in: plain-markdown knowledge that agents read and *propose* to, with human approval, journaled undo, secret screening | Planned (see ROADMAP) |
| **Orchestration and review** | Claude delegates to local agents and reviews what they hand back | Planned (Phases 4–5) |

## Who it's for

- **Today:** one person (the founder) — a finance + AI student building skills, running a local GPU
  and a Claude subscription.
- **As a product (direction set 30 Sep 2026):** people who want agents working *for* them on their own
  machine, with their data staying local. Exact audience: unknown — needs confirmation (see open
  questions in `SAGE-OS-HANDOFF.md`).

## Principles

1. **Local first.** Data, models and the hub live on the user's machine; remote access only over a
   private network, never a public port.
2. **The human approves what matters.** Agents propose; people decide. Approval is a product surface,
   not an afterthought.
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
   Environment), the 1950s air-defence network run from rooms of CRT consoles — one operator directing
   semi-autonomous agents from a ground station.

## Company framing

Company name, structure and commercial model: unknown — needs confirmation from the user. This file
states the product mission only.
