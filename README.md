# art-meme

Replace generic meme templates with fine art carrying the same emotional
payload. Goya's *Saturn Devouring His Son* is the seed example: it already IS
a meme — feral consumption, wide-eyed guilt — painted by a master.

## Build and share

The generated `skill/` directory contains code and annotations, **no artwork images**. Images download directly from recorded Wikimedia Commons files and are cached locally; no separate image hosting or Git LFS is needed.

```bash
uv run tools/build_skill.py
# Share the generated skill/ directory, or build it from a source checkout.
cd skill
uv run tools/get_image.py titian-sisyphus
printf '%s\n' '{"artwork":"titian-sisyphus","labels":{"sisyphus":"me","boulder":"the weekly status report"},"out":"/tmp/sisyphus.jpg"}' | uv run tools/render.py
```

The image command returns a local `path` for inspection and provenance. Rendering downloads automatically if needed. Downloads use the **exact recorded Commons filename**, not the authoring search helper. Cache hits work offline; unavailable files and checksum mismatches produce actionable errors, not search substitutions. First downloads use the current Commons version; source revisions are not pinned.

| Setting | Behavior |
|---|---|
| Cache | `${XDG_CACHE_HOME:-~/.cache}/art-meme`, or `ART_MEME_CACHE_DIR` |
| Integrity | SHA-256 recorded on download and verified on every cache reuse |
| Refresh | `uv run tools/get_image.py <id> --refresh` bypasses local/cache copies |
| Authoring | Existing `corpus/images/` copies remain usable locally but are ignored by Git and never packaged |
| Rights | Annotations declare public-domain or CC0; preserve source links and rendered credit. This is not automated legal verification. |
| Fonts | DejaVu on Linux; Georgia/Arial on macOS/Windows; or `fonts/serif.ttf` and `fonts/sans-bold.ttf` in the skill |

Checks (no network needed):

```bash
uv run --with pillow --with pyyaml python -m unittest discover -s tests -v
```

The concept notes below predate the implemented `targets`/`uses` schema; consult `corpus/*.yaml` and `tools/` for current behavior.

## Output form

An **agent skill**, not a static pack. The skill:

1. reads a curated artwork map (built offline, below)
2. uses session context to pick the artwork whose emotional structure fits
3. adds labels/captions positioned on the artwork's character slots

## Pipeline (art-first, not meme-first)

Annotate the art corpus once; memes match against the index forever. The meme
side churns monthly; the art side is fixed and appreciates.

```mermaid
flowchart LR
  A["Open-access corpora<br/>Met · Rijks · AIC · Commons"] --> B["Visceral filter<br/>legible in 2s or OUT"]
  B --> C["Annotate<br/>happening · tenor · characters/roles"]
  C --> D["Artwork index"]
  E["Top-100 memes<br/>emotional structures"] --> F["Mapping<br/>many-to-many"]
  D --> F
  F --> G["Skill: session context -> pick artwork -> place labels"]
```

**Visceral filter:** artwork qualifies only if a stranger reads *what is
happening* in two seconds — who wants what, who's winning, who's horrified.
Ambiguity = off the table. This is the meme-slot constraint made operational.

## Annotation schema (draft)

```yaml
artwork: Saturn Devouring His Son
artist: Goya
what_is_happening: a giant frantically eats a human body
emotional_tenor: [horror, compulsion, guilt, cannot-stop]
characters:
  - role: the consumer      # slot A — wide-eyed, mid-act, aware it's wrong
  - role: the consumed      # slot B — passive, already lost
legible_in_2s: yes
meme_slots: [doing-the-thing-you-know-is-bad, devouring, self-destruction]
```

`characters[].role` is load-bearing: it's what the skill matches session
context against, and where labels land.

## Mapping is many-to-many

One meme -> several artworks (skill picks per session tone).
One artwork -> several memes. Example candidates:

| Meme | Structure | Fine art candidates |
|---|---|---|
| Distracted Boyfriend | temptation triangle | Fragonard, Greuze genre scenes |
| This Is Fine | denial amid disaster | Bruegel *Fall of Icarus*; Pompeii frescoes |
| Woman Yelling at Cat | accusation vs. indifference | Caravaggio-school confrontations |
| Feral consumption | appetite over reason | Goya *Saturn* |
| Galaxy Brain | escalating enlightenment | apotheosis / assumption sequences |

## Validation step (before building the skill)

Annotate ~50 artworks, map top 20 memes, run selection manually against a few
real sessions. If the picks land, build the skill; the pack was never the
product, only the test.

## Sources

- Met Open Access: ~490k works, CC0, bulk CSV + images
- Rijksmuseum API: ~700k works, high-res
- Art Institute of Chicago API: CC0
- Wikimedia Commons / Wikidata: motif-tagged paintings
