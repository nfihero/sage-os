"""The repo's Claude Code git guardrails (.claude/hooks/git_guardrails.py): what's blocked, what isn't,
and that removal needs a human at a terminal."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "git_guardrails.py"


def run(args, payload=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=json.dumps(payload) if payload is not None else "",
                          capture_output=True, text=True, timeout=20)


def shell(cmd, tool="Bash"):
    return run(["check"], {"tool_name": tool, "tool_input": {"command": cmd}})


@pytest.mark.parametrize("cmd", [
    "git push", "git push origin main --tags", "git -C /c/Users/you/sage-os push", "cd x && git push --force",
    "git reset --hard HEAD~1", "git reset HEAD --hard", "git clean -fd", "git clean -xf", "git branch -D old",
    "git checkout .", "git checkout -- .", "git restore .",
    "rm .claude/hooks/git_guardrails.py", "Remove-Item .claude\\settings.json", "echo {} > .claude/settings.json",
    "sed -i 's/x/y/' .claude/settings.json",
])
def test_blocks(cmd):
    for tool in ("Bash", "PowerShell"):
        r = shell(cmd, tool)
        assert r.returncode == 2 and "BLOCKED" in r.stderr, (tool, cmd)


@pytest.mark.parametrize("cmd", [
    "git status", "git add -A && git commit -q -m 'push only when the user asks'", "git log --oneline -5",
    "git tag -a v0.8.0 -m 'release'", "git diff HEAD~1", "git checkout -b k6", "git checkout main",
    "git restore --staged README.md", "git branch -d merged-branch", "git reset HEAD README.md",
    "cat .claude/settings.json", "python .claude/hooks/git_guardrails.py remove",
    "hub/.venv/Scripts/python -m pytest hub -q > out.txt", "grep -rn model hub",
])
def test_allows(cmd):
    assert shell(cmd).returncode == 0, cmd


def test_file_edits_to_the_guardrails_are_blocked():
    edit = lambda inp, tool="Edit": run(["check"], {"tool_name": tool, "tool_input": inp}).returncode
    assert edit({"file_path": "C:\\Users\\you\\sage-os\\.claude\\hooks\\git_guardrails.py", "old_string": "a", "new_string": "b"}) == 2
    assert edit({"file_path": "C:/Users/you/sage-os/.claude/settings.json", "content": "{}"}, "Write") == 2
    assert edit({"file_path": "C:/Users/you/sage-os/.claude/settings.json",
                 "old_string": '"command": "x git_guardrails.py check"', "new_string": '"command": "x"'}) == 2
    # other settings edits are fine as long as the guardrail entry survives
    assert edit({"file_path": "C:/Users/you/sage-os/.claude/settings.json",
                 "old_string": '"hooks": {', "new_string": '"env": {"A": "1"},\n  "hooks": {'}) == 0
    assert edit({"file_path": "C:/Users/you/sage-os/README.md", "old_string": "a", "new_string": "b"}) == 0


def test_remove_explains_and_changes_nothing_without_a_terminal():
    before = (SCRIPT.parent.parent / "settings.json").read_bytes()
    r = run(["remove"])
    assert r.returncode == 1 and "Removing the git guardrails will:" in r.stdout and "pushes to a remote" in r.stdout
    assert "Nothing changed" in r.stdout and SCRIPT.exists()
    assert (SCRIPT.parent.parent / "settings.json").read_bytes() == before


def test_garbage_input_is_not_blocked():
    assert subprocess.run([sys.executable, str(SCRIPT), "check"], input="not json", capture_output=True,
                          text=True).returncode == 0
