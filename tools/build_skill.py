# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "pillow>=10"]
# ///
"""Validate the corpus and generate skills/art-meme/ atomically.

Checks: every uses[].structure exists; bindings cover all roles with declared
target ids; exact downloadable source identifiers exist. Emits coverage matrix.
Images stay outside the package. skills/art-meme/ is GENERATED and committed so
the repository installs directly as an Agent Plugin — never hand-edit it.
"""
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml
from get_image import ImageError, validate_source

REPO = Path(__file__).resolve().parent.parent
SKILL_NAME = "art-meme"
STRUCTURE_WARN = 25


def fail(errors):
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)


def main():
    structures = {s["id"]: s for s in
                  yaml.safe_load((REPO / "structures.yaml").read_text())}
    if len(structures) > STRUCTURE_WARN:
        print(f"WARNING: {len(structures)} structures (> {STRUCTURE_WARN}); "
              "review for synonym proliferation", file=sys.stderr)

    errors, works = [], []
    if not (REPO / "LICENSE").is_file():
        errors.append("missing LICENSE required for distribution")
    for path in sorted((REPO / "corpus").glob("*.yaml")):
        w = yaml.safe_load(path.read_text())
        wid = w.get("id", path.stem)
        if wid != path.stem:
            errors.append(f"{path.name}: id {wid!r} != filename")
        try:
            validate_source(w.get("source"))
        except ImageError as exc:
            errors.append(f"{wid}: {exc}")
        # Authoring-copy hashes cannot validate independently encoded thumbnails.
        w.pop("image_sha256", None)
        target_ids = {t["id"] for t in w.get("targets", [])}
        for t in w.get("targets", []):
            if not (len(t.get("subject_point", [])) == 2 and
                    len(t.get("label_box", [])) == 4):
                errors.append(f"{wid}: target {t['id']} bad geometry")
        for use in w.get("uses", []):
            s = structures.get(use["structure"])
            if not s:
                errors.append(f"{wid}: unknown structure {use['structure']}")
                continue
            missing = set(s["roles"]) - set(use["bindings"])
            if missing:
                errors.append(f"{wid}: {use['structure']} unbound roles {sorted(missing)}")
            bad = set(use["bindings"].values()) - target_ids
            if bad:
                errors.append(f"{wid}: {use['structure']} binds unknown targets {sorted(bad)}")
        works.append(w)
    if errors:
        fail(errors)

    # coverage matrix
    by_structure, by_register = {}, {}
    for w in works:
        for use in w["uses"]:
            by_structure.setdefault(use["structure"], []).append(w["id"])
        for r in w.get("comic_registers", []):
            by_register.setdefault(r, []).append(w["id"])
    unused = sorted(set(structures) - set(by_structure))

    tmp = REPO / "skills" / f".{SKILL_NAME}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "corpus").mkdir(parents=True)
    (tmp / "scripts").mkdir()

    for w in works:
        (tmp / "corpus" / f"{w['id']}.yaml").write_text(
            yaml.safe_dump(w, sort_keys=False, allow_unicode=True))
    (tmp / "index.yaml").write_text(yaml.safe_dump({
        "generated": datetime.now(UTC).date().isoformat(),
        "structures": list(structures.values()),
        "works": works,
    }, sort_keys=False, allow_unicode=True))
    shutil.copy2(REPO / "LICENSE", tmp / "LICENSE")
    shutil.copy2(REPO / "tools/get_image.py", tmp / "scripts/get_image.py")
    shutil.copy2(REPO / "tools/render.py", tmp / "scripts/render.py")
    shutil.copy2(REPO / "tools/match.py", tmp / "scripts/match.py")
    shutil.copy2(REPO / "tools/SKILL.template.md", tmp / "SKILL.md")

    cov = ["# Coverage\n", "| Structure | Works |", "|---|---|"]
    cov += [f"| {s} | {', '.join(ids)} |" for s, ids in sorted(by_structure.items())]
    cov += ["", "| Register | Works |", "|---|---|"]
    cov += [f"| {r} | {len(ids)} |" for r, ids in sorted(by_register.items())]
    if unused:
        cov += ["", f"Unused structures: {', '.join(unused)}"]
    (tmp / "COVERAGE.md").write_text("\n".join(cov) + "\n")

    dest = REPO / "skills" / SKILL_NAME
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    print(json.dumps({"works": len(works), "structures": len(structures),
                      "unused_structures": unused,
                      "skill_dir": str(dest)}))


if __name__ == "__main__":
    main()
