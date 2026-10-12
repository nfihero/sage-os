# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

(Shown in a Tauri desktop window on Windows, W1; the same React UI later ships as the Mac app (F1) and inside a phone shell (Y6).)

## Users

- **Primary: the owner, daily.** A finance and AI student who keeps Sage OS open for hours beside other work, on a gaming PC with a large GPU: reviewing digested textbook chapters, asking questions of their own notes, running local and cloud agents, and stepping away to play games.
- **Next: testers (F1).** Friends who use several AIs and keep notes and documents in many places (D22), starting from an empty library on their own Mac, reporting bugs.

## Product Purpose

A "Wikipedia for yourself": your notes and documents become a library that every AI you use reads from, and that grows only with your approval. Success: you find and ask about your own knowledge faster than anywhere else, and nothing enters the library without you seeing it.

## Positioning

Local-first and model-agnostic. Your library lives on your devices; any AI (a local model on your GPU, Claude, ChatGPT, Gemini) answers from it with the same tools; agents propose notes and only you file them, with exact undo. A chat app or a notes app alone can't make that claim.

## Operating Context

- Open all day in a desktop window; closed to the tray, not quit.
- Sessions mix: search and ask the library, review inbox cards (note proposals, permission requests), watch digests progress, switch agents, check the machine (GPU memory, game mode).
- Shares the computer with games; the local model steps aside when a game needs the GPU (G1).

## Capabilities and Constraints

- Library: notes (markdown) plus documents; keyword search; digests turn long documents into proposed notes chapter by chapter.
- Agents and models: a local llama.cpp engine; Claude Code; any OpenAI-compatible model; each gets the library tools (search, read, propose).
- Inbox: everything that needs the user, with review note by note and exact undo.
- Desktop app with tray; phone layout must work (375 px wide); keyboard use matters (Ctrl+K search).
- Must not assume Hermes, a GPU or a terminal (D22): anything not set up reads "not connected", never broken.

## Brand Commitments

- Name: **Sage OS**.
- Keep: the **agent planet card** (WebGL point-cloud planet, its State / Model / Where readouts and dot-matrix usage meters), which the owner likes most; **dot-matrix numerals** (Doto) for clocks and readouts; the **boot screen** at startup.
- Visual direction requested by the owner (11 Oct 2026): futuristic, alien, inspired by the 1950s **SAGE** air-defense CRT consoles; remove the rolling CRT refresh line.
- Not committed: the SAGE//OS wordmark styling and the Phosphor / Tron / Amber theme switch may be replaced.

## Evidence on Hand

Real content only: the owner's library (≈165 notes, ≈570 source files), textbook digests (Kieso *Intermediate Accounting*), inbox cards, chats, GPU readings. No customers, testimonials or metrics exist; none may be invented.

## Product Principles

1. **The library is the point.** Search and asking come first; machinery is one click away.
2. **Nothing enters without you.** Agents propose; the user files; every change can be undone exactly.
3. **Calm for long sessions.** Motion only when it means something (an agent's state, a change); nothing loops for decoration.
4. **Not connected is not broken.** Missing pieces are quiet invitations, never alarms.
5. **Any AI, same library.** No single model is privileged in the interface.

## Accessibility & Inclusion

Long daily sessions: readable text (11 px floor, sans for sentences), visible keyboard focus, honour reduced motion, WCAG AA contrast on the dark theme.
