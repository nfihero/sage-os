"""Git guardrails for Claude Code sessions in this repo (Claude Code PreToolUse hook).

    git_guardrails.py check    the hook: reads the tool call (JSON on stdin), exits 2 to block it
    git_guardrails.py remove   prints what removal changes; removes only after "REMOVE" is typed in
                               a real terminal (Claude's tools have no terminal, so the last step is
                               always the user's)

Blocked: git push (any form), reset --hard, clean -f, branch -D, checkout/restore of everything,
and any attempt to edit or delete these guardrails other than through `remove`. Adapted from Matt
Pocock's git-guardrails-claude-code skill: Python instead of jq, and Bash + PowerShell covered.
It is a text match meant to catch mistakes, not a sandbox.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
SETTINGS = HOOKS.parent / "settings.json"
GUARD = "git_guardrails"                      # marker: the hook entries and this file carry it

# `git` then its global options (-C dir, -c k=v, --flag), then the subcommand -- so a commit message
# that merely mentions "push" isn't blocked.
GIT = r"\bgit(?:\.exe)?\s+(?:(?:-C|-c)\s+\S+\s+|--[\w-]+(?:=\S+)?\s+)*"
DANGEROUS = [                                 # (pattern, what it would do)
    (GIT + r"push\b", "pushes to a remote"),
    (GIT + r"reset\b[^\n;|&]*--hard\b", "throws away uncommitted work"),
    (GIT + r"clean\b[^\n;|&]*\s-[a-zA-Z]*f", "deletes untracked files"),
    (GIT + r"branch\b[^\n;|&]*\s(-D\b|--delete\s+--force|-d\s+--force)", "force-deletes a branch"),
    (GIT + r"(checkout|restore)\s+(--\s+)?\.(\s|$)", "discards all local edits"),
]
# Shell commands that would edit or delete the guardrails themselves.
TAMPER = re.compile(r"(?<![\w-])(rm|del|erase|rd|rmdir|mv|move|ren|rename|cp|copy|Remove-Item|Move-Item|Rename-Item|"
                    r"Copy-Item|Set-Content|Add-Content|Out-File|Clear-Content|tee)(?![\w-])|sed\s+-i|>", re.I)


def block(reason: str) -> None:
    print(f"BLOCKED by the git guardrails: {reason}. The user has prevented this. If they want it, they can "
          f"push or run it themselves, or ask you to remove the guardrails "
          f"(run `.claude/hooks/git_guardrails.py remove` to show them the plan first).", file=sys.stderr)
    sys.exit(2)


def check() -> None:
    try:
        call = json.load(sys.stdin)
    except ValueError:
        return                                # not a tool call we understand: don't get in the way
    tool, inp = call.get("tool_name", ""), call.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        for pattern, does in DANGEROUS:
            if re.search(pattern, cmd):
                block(f"this command {does}")
        touches_guard = GUARD in cmd or re.search(r"\.claude[\\/]+(settings\.json|hooks)", cmd)
        if touches_guard and TAMPER.search(cmd) and not re.search(rf"{GUARD}\.py[\"']?\s+(remove|check)\b", cmd):
            block("this command would change or delete the guardrails; removal goes through "
                  "`git_guardrails.py remove`, confirmed by the user in a terminal")
    elif tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = str(inp.get("file_path", "")).replace("\\", "/")
        if path.endswith(f"/hooks/{GUARD}.py"):
            block("this edits the guardrail script itself")
        if path.endswith("/.claude/settings.json"):
            old = str(inp.get("old_string", "")) + "".join(str(e.get("old_string", "")) for e in inp.get("edits") or [])
            new = str(inp.get("new_string", "")) + str(inp.get("content", "")) + "".join(
                str(e.get("new_string", "")) for e in inp.get("edits") or [])
            if (tool == "Write" and GUARD not in new) or (GUARD in old and GUARD not in new):
                block("this edit would drop the guardrail hook from .claude/settings.json")


def remove() -> None:
    try:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Can't read {SETTINGS}: {exc}. Nothing changed.")
        sys.exit(1)
    pre = settings.get("hooks", {}).get("PreToolUse", [])
    keep = [m for m in pre if GUARD not in json.dumps(m)]
    print("Removing the git guardrails will:")
    print(f"  1. delete {len(pre) - len(keep)} PreToolUse hook entr{'y' if len(pre) - len(keep) == 1 else 'ies'} "
          f"from {SETTINGS} (other settings stay as they are)")
    print(f"  2. delete {Path(__file__).resolve()}")
    print("Afterwards, Claude Code sessions in this repo can again run, without this check:")
    for _, does in DANGEROUS:
        print(f"  - commands that {does}")
    print("  - edits to these guardrail files")
    print("Claude Code's normal permission prompts and your instructions still apply. To restore the "
          "guardrails later, revert the commit that removes them (or ask Claude to set them up again).")
    if not sys.stdin.isatty():
        print("\nNothing changed. To confirm, run this in a terminal yourself:\n"
              f"  hub\\.venv\\Scripts\\python .claude\\hooks\\{GUARD}.py remove")
        sys.exit(1)
    if input("\nType REMOVE to confirm: ").strip() != "REMOVE":
        print("Not confirmed. Nothing changed.")
        sys.exit(1)
    if keep:
        settings["hooks"]["PreToolUse"] = keep
    else:
        settings.get("hooks", {}).pop("PreToolUse", None)
        if not settings.get("hooks"):
            settings.pop("hooks", None)
    SETTINGS.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    Path(__file__).unlink()
    print("Guardrails removed. Commit the change if you want it to stick: git add -A .claude && git commit")


if __name__ == "__main__":
    {"check": check, "remove": remove}.get(sys.argv[1] if len(sys.argv) > 1 else "", check)()
