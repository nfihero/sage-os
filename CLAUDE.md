# Sage OS — instructions for Claude sessions

Start with `docs/SAGE-OS-HANDOFF.md` §0 "Start here": current state, next steps, what waits on the
user, how the user wants work done, and known gotchas. Then `docs/DECISIONS.md` (append-only log;
add a new entry for any design choice, never rewrite an old one) and `docs/STATUS.md`.

Rules that always apply:
- Each pass updates all docs and ships as its own version: CHANGELOG entry + local tag (policy at the
  top of `CHANGELOG.md`). Docs-only changes are patch versions.
- Before a release commit: `/code-review high --fix`; `no-ai-slop` on user-facing copy;
  `vibe-security` when auth, network exposure, secrets or agent input change.
- Commit when it makes sense; **push only when the user says so** (`.claude/hooks/git_guardrails.py`
  blocks pushes and destructive git in sessions started in this folder; D13).
- Never handle the user's credentials or tokens. Google Drive is read-only. `data/` and any
  `data-private/` folder never get committed.
- Ask before destructive or persistent system changes (Hermes config, deleting files or models).
- Explain in plain language; give a recommendation rather than a survey.
