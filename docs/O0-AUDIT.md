# O0: Sage OS through the eyes of someone who has never used an agent

Audit of a fresh install (empty data, nothing connected), 14 Oct 2026, for roadmap step O0 (D41.1). The test
person has used a chat app such as ChatGPT, maybe, and nothing else: no terminal, no "agents", no markdown.
Ranked by how likely each one is to stop them. **Batch 1** is fixed in 0.26.0; the rest are open.

| # | Where | What stops a newcomer | Fix | Status |
|---|---|---|---|---|
| 1 | Guide (opens first) | Opens with "your own small agent team", a "shared wiki", "task board", "plain markdown", "journalled byte for byte" and decision numbers (D11, D39). It explains the architecture, not what to do. | Rewrite in plain words around three things you do: talk to an AI, give it your documents, approve what it writes. Drop decision numbers. Tour copy the same. | Batch 1 |
| 2 | Everywhere | One thing has three names: LIBRARY (tab), BOOKSHELF (top bar, window title), "vault" (empty state, OPEN VAULT, History). | Call it **Library** everywhere a person reads it (code and routes keep their names). | Batch 1 |
| 3 | Home, inbox, search | "Your agent", "Enter asks your agent", "worker questions", "Hermes approvals", "Bookshelf proposals", "by an agent". | Say "AI": "Your AI", "Enter asks your AI". Inbox empty state says what will arrive in plain words. | Batch 1 |
| 4 | Top bar | Status lights HERMES, MODELS, GUARD show on a computer that has never had Hermes. | Show them only when Hermes is connected. | Batch 1 |
| 5 | Library | No way to add your own documents from the app. Sources only lists folders set in a config file; the empty state says to drop files in a folder that needs OPEN VAULT and Explorer. | An **ADD FILES** button (file picker, copied into Library/Files and indexed) and **ADD A FOLDER** (a folder picker that becomes a source). | Open |
| 6 | Library empty state | "Sources → Build notes → Propose starter notes", "index note per folder", "Draft asks an agent". Four steps of jargon before a first note. | One action: "Add your documents", then "Ask Sage to write notes from them" (proposals arrive in the inbox). | Open |
| 7 | Top bar | 12 controls at once: clock, three lights, usage bars, $ USAGE, SAFETY, INBOX, REPORT, GUIDE, GAME MODE, LIBRARY, theme, MOTION. | Keep what a newcomer needs (Library, Inbox, Guide, Report); move theme, motion, safety log, game mode into one **Settings** menu. | Open |
| 8 | Inbox → AGENTS | "Librarian", "Reviewer", "researcher", "trust", "filed", "Ask" with no explanation. | Plain titles ("Tidies your notes", "Checks proposals"), a sentence on what trust levels mean, and hide roles that have never run. | Open |
| 9 | Systems strip | GPU 10.8 / 15.9 GB, ENGINE off, HERMES not running: machine room on the home screen. | Collapse to one line ("Everything's running" or what isn't), details in Systems. | Open |
| 10 | First run | Claude Code needs `claude auth login` in a terminal. | Keep the exact command, add a COPY button and "open a terminal: Windows key, type Terminal, Enter". | Open |
| 11 | Model picker | Model names (Granite 4.2 3B, Qwen 3.5 4B) mean nothing; "fits", "tight". | Lead with what each is good for and how fast it'll be here ("quick answers", "best quality, slower"). | Open |
| 12 | Search | "words + meaning" and CTRL K hints. | "Search your notes, or press Enter to ask". | Open |

Gate (ROADMAP O0): a person who has only used a chat app installs Sage OS, connects an AI and gets an answer from
their own notes without help.
