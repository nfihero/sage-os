"""K14 gate check (D37), run against a live hub: does a differently worded question find its note, and does a
wordy-but-wrong note stay out of the briefing pack? Compares keyword-only with keyword + meaning.

The questions are about the owner's own notes, so they live outside git (default: data-private/search-eval.json):
  {"search": [{"q": "...", "expect": ["Note title", ...]}],      # hit when any expected title is in the top 5
   "pack":   [{"q": "...", "expect": [...], "never": [...]}]}    # pack must hold one of expect (if any), none of never

  hub\\.venv\\Scripts\\python hub\\tools\\eval_search.py [questions.json]
"""
import json
import sys
from pathlib import Path

import httpx

HUB = "http://127.0.0.1:8787"
ROOT = Path(__file__).resolve().parents[2]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data-private" / "search-eval.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    c = httpx.Client(base_url=HUB, timeout=60)
    status = c.get("/api/semantic").json()
    print(f"search model: {status['state']}, {status['notes']} notes and {status['documents']} documents embedded\n")

    hits = {"words": 0, "both": 0}
    for case in data["search"]:
        row = []
        for mode in ("words", "both"):
            r = c.get("/api/vault/search", params={"q": case["q"], "limit": 5, "words": mode == "words"}).json()
            titles = [x["title"] for x in r["results"]]
            ok = any(t in titles for t in case["expect"])
            hits[mode] += ok
            row.append("✓" if ok else "·")
        print(f"  {row[0]} {row[1]}  {case['q']}")
    n = len(data["search"])
    print(f"\nsearch, expected note in the top 5: words only {hits['words']}/{n}, words + meaning {hits['both']}/{n}\n")

    good = {"words": 0, "both": 0}
    for case in data.get("pack", []):
        for mode in ("words", "both"):
            r = c.get("/api/briefing/preview", params={"q": case["q"], "words": mode == "words"}).json()
            titles = [i["title"] for i in r["items"]]
            wrong = [t for t in titles if t in case.get("never", [])]
            found = not case.get("expect") or any(t in titles for t in case["expect"])
            ok = found and not wrong
            good[mode] += ok
            print(f"  {'✓' if ok else '✗'} {mode:5}  {case['q']}\n           pack: {titles or '(nothing)'}")
    m = len(data.get("pack", []))
    print(f"\nbriefing packs right (the answer in, look-alikes out): words only {good['words']}/{m}, "
          f"words + meaning {good['both']}/{m}")


if __name__ == "__main__":
    main()
