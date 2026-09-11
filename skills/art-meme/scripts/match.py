# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Deterministic corpus filter — the hard gates of the matching pipeline.

Usage:
  uv run match.py --structures feral-consumption,self-destruction
  uv run match.py --structures the-overwhelm --exclude-flags graphic-violence

Prints matching works (id, matched structures, bindings, registers) as YAML.
Empty output means: abstain or try different structures.
"""
import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--structures", required=True)
    ap.add_argument("--exclude-flags", default="")
    args = ap.parse_args()
    wanted = set(filter(None, args.structures.split(",")))
    excluded = set(filter(None, args.exclude_flags.split(",")))

    idx = yaml.safe_load((ROOT / "index.yaml").read_text())
    known = {s["id"] for s in idx["structures"]}
    unknown = wanted - known
    if unknown:
        raise SystemExit(f"unknown structures: {sorted(unknown)}; "
                         f"known: {sorted(known)}")

    out = []
    for w in idx["works"]:
        if set(w.get("content_flags", [])) & excluded:
            continue
        hits = [u for u in w.get("uses", []) if u["structure"] in wanted]
        if hits:
            out.append({
                "id": w["id"], "title": w["title"], "artist": w["artist"],
                "what_is_happening": w["what_is_happening"],
                "matched_uses": hits,
                "comic_registers": w.get("comic_registers", []),
                "content_flags": w.get("content_flags", []),
                "targets": [t["id"] for t in w["targets"]],
            })
    print(yaml.safe_dump(out, sort_keys=False, allow_unicode=True) if out
          else "[]  # no match — abstain or try different structures")


if __name__ == "__main__":
    main()
