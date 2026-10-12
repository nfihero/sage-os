"""Print one version's CHANGELOG.md section (the update dialog shows it), and fail if the tag and the app's version
disagree, so a release can't ship under the wrong number.   python release_notes.py 0.22.0"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
version = sys.argv[1].removeprefix("v")
app = json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))["version"]
if app != version:
    sys.exit(f"tag v{version} but desktop/src-tauri/tauri.conf.json says {app}: bump the version before tagging")
text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.S | re.M)
if not m:
    sys.exit(f"CHANGELOG.md has no section for {version}")
sys.stdout.reconfigure(encoding="utf-8")
print(m.group(1).strip())
