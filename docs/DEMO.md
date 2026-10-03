# Sage OS — demo script

A 5–7 minute walkthrough for someone seeing Sage OS for the first time. It shows **why** the app
exists (the guide), then **how** it works by running the one loop that's fully built: your files →
proposed notes → your approval → searchable notes agents can use. Everything shown is live; nothing is
mocked.

## Before the demo (10 minutes, the day before)

| Check | How | Expect |
| --- | --- | --- |
| Hub running | `start.cmd`, or open http://127.0.0.1:8787 | dashboard loads; top-right dot is lit |
| Fresh UI | after any rebuild, press **Ctrl+F5** once in the demo browser | **? GUIDE** chip in the top bar |
| Services | top-bar lights **HERMES · MODELS · GUARD** | all lit. If HERMES is dark, Claude still works; skip step 5 |
| Claude signed in | Claude panel shows a model, not "signed out" | `claude` CLI logged in |
| Something in the inbox | top bar **INBOX** count > 0 | starter-note cards from *Build notes* (see below) |
| Tidy screen | close old Claude tabs you don't want shown; check the board and inbox for anything private | nothing personal on screen |
| Guide shows on open | load http://127.0.0.1:8787/?guide | the guide opens over the dashboard |

**Inbox prep.** If the inbox has no Bookshelf cards: Bookshelf → **Sources** → **Build notes** →
**Propose starter notes**. Leave the cards unapproved; approving one is part of the demo.

**Keep for a re-run.** Undo puts the vault back exactly (Bookshelf → **History** → **Undo**), so you
can rehearse the approval and reset it.

## The walkthrough

### 1. Why it exists: the guide (1 min)

Open http://127.0.0.1:8787/?guide (or click **? GUIDE**).

> "Companies now run AI agents as a team: a wiki they share, a task board, and a person who signs
> off. Sage OS is that setup for one person, on their own PC, with whatever AI they already use."

Point at the table: each thing a team needs and the panel that does it here. Then the four rules:
agents propose and you decide; files stay local; bring your own AI; everything is undoable. Read
the limit line out loud.

The **Right now** line under the rules is live: notes, source documents, and what's waiting for you.

### 2. The screen: the tour (1 min)

Click **TAKE THE TOUR**. Arrow keys or Enter step through it. It spotlights Claude (lead agent),
Hermes (local agent on the GPU), the inbox, the board, the system panel and the Bookshelf. Keep
moving; each card is two sentences.

### 3. Your files become knowledge: Bookshelf → Sources (2 min)

Click **BOOKSHELF**. With an empty vault, the right side shows *How notes get here* (Sources → Build
notes → Inbox → Bookshelf). That's the loop you're about to run.

- **Sources**: a read-only copy of chosen Google Drive folders (476 documents), searchable. Search
  something you know is in there (e.g. `WACC`) to show it finds text inside PDFs and slides.
- Point out what was **left out**: private-looking files are never copied, and the list says why.
- **Build notes**: each folder is listed as *new / in inbox / in vault*. The starter notes are
  already proposed. Nothing was written; they're waiting in the inbox.

### 4. You approve: the inbox (1 min)

Close the Bookshelf. In the **INBOX**, open a Bookshelf card: it shows each note it would create.
Click **Approve & file**. Open the Bookshelf again: the notes are there, searchable, labelled with
where they came from.

Then show **History**: the batch you just approved, with **Undo**. Optional: undo it to show the
vault goes back byte for byte.

### 5. Agents use it: Claude or Hermes (1–2 min)

In the Claude panel, ask:

> Search my Bookshelf and sources for WACC and tell me which documents cover it. Then propose a
> short note on it that cites them.

Claude searches (tool calls are visible in the chat), answers with the documents, and its proposal
appears in the inbox: the same approval path as before. Agents can read; only you file.

*With Hermes up*, the same ask works in the Hermes panel and runs on the local GPU, at no cost.
Bookshelf → Sources → **Draft** briefs Hermes on a whole folder.

### 6. Close (30 s)

> "Today: two agents, one inbox, notes built from your own files, all on this machine. Next: a
> shared team chat where the lead agent answers and others step in (D8), Sage OS's own task board,
> and briefing packs, where agents get the relevant notes before they start a task."

## If something goes wrong

| Symptom | Fix |
| --- | --- |
| Old screen, no **? GUIDE** chip | Ctrl+F5 (the browser cached the page from before the update) |
| Dashboard blank / "reconnecting" dot | hub stopped: run `start.cmd` |
| HERMES light dark | skip step 5's Hermes part; Claude covers it |
| Hermes says a Bookshelf tool doesn't exist | Hermes cached an old tool list: STATUS known issue 8 |
| A proposal is "held" | the screener saw something secret-looking; open *Show content*, then *Reject* |
| Guide keeps opening | it opens once per browser; `?guide` forces it. Clear site data to reset |
