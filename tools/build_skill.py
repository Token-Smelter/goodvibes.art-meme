# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Validate the corpus and generate the skill/ directory atomically.

Checks: every uses[].structure exists; bindings cover all roles with declared
target ids; image files exist. Stamps image_sha256. Emits coverage matrix.
skill/ is GENERATED — never hand-edited.
"""
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
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
    for path in sorted((REPO / "corpus").glob("*.yaml")):
        w = yaml.safe_load(path.read_text())
        wid = w.get("id", path.stem)
        if wid != path.stem:
            errors.append(f"{path.name}: id {wid!r} != filename")
        img = REPO / "corpus" / w["image"]
        if not img.exists():
            errors.append(f"{wid}: missing image {w['image']}")
        else:
            w["image_sha256"] = hashlib.sha256(img.read_bytes()).hexdigest()
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

    tmp = REPO / "skill.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "corpus/images").mkdir(parents=True)
    (tmp / "tools").mkdir()

    for w in works:
        (tmp / "corpus" / f"{w['id']}.yaml").write_text(
            yaml.safe_dump(w, sort_keys=False, allow_unicode=True))
        shutil.copy2(REPO / "corpus" / w["image"], tmp / "corpus" / w["image"])
    (tmp / "index.yaml").write_text(yaml.safe_dump({
        "generated": date.today().isoformat(),
        "structures": list(structures.values()),
        "works": works,
    }, sort_keys=False, allow_unicode=True))
    shutil.copy2(REPO / "tools/render.py", tmp / "tools/render.py")
    shutil.copy2(REPO / "tools/match.py", tmp / "tools/match.py")
    shutil.copy2(REPO / "tools/SKILL.template.md", tmp / "SKILL.md")

    cov = ["# Coverage\n", "| Structure | Works |", "|---|---|"]
    cov += [f"| {s} | {', '.join(ids)} |" for s, ids in sorted(by_structure.items())]
    cov += ["", "| Register | Works |", "|---|---|"]
    cov += [f"| {r} | {len(ids)} |" for r, ids in sorted(by_register.items())]
    if unused:
        cov += ["", f"Unused structures: {', '.join(unused)}"]
    (tmp / "COVERAGE.md").write_text("\n".join(cov) + "\n")

    dest = REPO / "skill"
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    print(json.dumps({"works": len(works), "structures": len(structures),
                      "unused_structures": unused,
                      "skill_dir": str(dest)}))


if __name__ == "__main__":
    main()
