# Technology

## How it works

```
 Desktop app (Tauri: Windows, macOS)
   └─ the Sage OS hub, on the person's computer (Python; localhost only)
        ├─ AIs:          a local model (llama.cpp, models chosen to fit the machine) · ChatGPT · Gemini · Claude Code · Ollama
        ├─ Bookshelf:    notes as plain markdown files + documents → keyword and meaning search (a small local embedding model)
        ├─ Inbox:        every change an AI proposes waits for approval; a journal makes undo exact
        ├─ Helpers:      scheduled jobs whose results arrive in the Inbox (U3, next)
        ├─ Secrets:      API keys, sign-ins and the device key in the OS keychain
        └─ Sync:         a separate TLS listener that only paired devices can use (P1); records and files next (P2, P3)
```

## Private by design

- **Nothing leaves the computer** except the question sent to the AI the person chose, and downloads of the app, its
  updates and models. No account, no analytics service, no sync server (D43).
- **Devices sync directly.** Pairing uses a one-time code; each device has its own Ed25519 key in the OS keychain;
  every request between devices is signed and tied to its TLS connection (D45).
- **Secrets are never plain files.** API keys, the Google sign-in and device keys live in Windows Credential Manager
  or the macOS Keychain (D40, D44).
- **Screened before saving.** Anything an AI proposes is checked for secrets before it touches disk; the person can
  only override it on purpose.
- **Signed updates.** The app refuses any update not signed by the project.

## What's hard to copy

1. **Approval and undo as the core, not a feature.** Every AI-proposed change goes through one Inbox, batches are
   journalled byte for byte, and undo restores files exactly. Trust levels let a person hand over more as an AI
   earns it, with a complete log at every level.
2. **Any AI, one memory.** The same Bookshelf and chat history work with a local model, ChatGPT, Gemini and Claude;
   switching AI mid-conversation hands over the context.
3. **Local-first sync built in from the data model up.** Every record has a time-ordered ID, every change is logged,
   deletes are tombstones; two devices merge without a server (Y1, P2).
4. **Runs on ordinary hardware.** Hardware detection rates every model for the machine; a game mode steps aside when
   the graphics card is needed; search by meaning runs on the processor.

## Quality

- 380 automated tests run on every change.
- Each release builds on clean Windows and macOS machines and runs a first-run self-check (empty start, keychain,
  bundled files, the local model's engine downloads and runs, the sync listener's handshake) before it can ship.
- 47 recorded design decisions with dates and reasons ([DECISIONS.md](../DECISIONS.md)).

## Stack

Python (FastAPI) hub, React + TypeScript UI, Tauri desktop shell, llama.cpp for local models, SQLite for records,
markdown files for notes, `keyring` for the OS keychain, `cryptography` for keys and TLS, zeroconf for finding
devices on a network.
