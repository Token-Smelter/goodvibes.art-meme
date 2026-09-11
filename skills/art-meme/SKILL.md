---
name: art-meme
description: Turn a situation into a fine-art meme — a public-domain masterpiece whose emotional structure matches it, with labels composited onto its figures. The situation can be anything: something that just happened in session, a hypothetical, a team's predicament, an industry-wide mess, a mood. Triggered by "meme this", "art meme", "fine art meme", "make a meme about <situation>", "react to this with art", or any request to caption/memeify something with a painting. Produces a shareable JPEG with credit line. Abstention is a valid outcome.
license: MIT (see LICENSE; artwork and fonts are separately licensed)
compatibility: Requires uv and Python 3.11+. Needs network access the first time each artwork is downloaded; verified cached images then work offline. Needs a serif and bold sans font (system DejaVu, Georgia/Arial, or user-supplied fonts/).
---

# art-meme

**BLUF:** Distill the situation into an emotional structure, filter the corpus with `scripts/match.py` (hard gates in code), pick the funniest fit, write ≤5-word labels mapping the situation's real participants to the painting's figures, render with `scripts/render.py`, and show the image. If nothing fits, say so — never force a pick.

The situation need not come from this session. A hypothetical, a described predicament, or a whole industry's problem works the same way: it only needs participants and a tension between them.

Run the commands below from this skill's own directory (`cd` there first) so the relative paths resolve. The package contains code and annotations, not artwork files. Internet access is needed for each image's first download; verified cached images work offline.

## Pipeline

1. **Distill** the situation into one sentence: *who wants what, who's winning, who's horrified.* Choose 1–3 candidate structure ids from `index.yaml` `structures` (read the whole file — it's small). Note the desired comic register and any content constraints from context (e.g. exclude `graphic-violence` in professional settings).
2. **Filter (code, not judgment):**
   ```bash
   uv run scripts/match.py --structures <id,id> [--exclude-flags <flag,flag>]
   ```
   Empty result → **abstain**: tell the user no artwork fits that structure, offer the nearest structures that do exist. Do not stretch a wrong painting.
3. **Pick** from the survivors: best structural fit first, then register fit. Intensity mismatch is allowed and often *is* the joke (Saturn for a trivial dependency bump). Repeating a recently used work is worse than a slightly weaker fit. Fetch the chosen original for visual inspection:
   ```bash
   uv run scripts/get_image.py <artwork-id>
   ```
   Read the local `path` from the returned JSON to inspect the image. This resolves the recorded Commons file, never an artwork search. Source unavailability is a download failure, not `no_match`; report it without silently substituting another reproduction.
4. **Label**: ≤5 words per target, mapping the situation's real participants to bound targets. Unbound targets may also be labeled when funny. Optional `caption` (strip above the canvas) — but if the caption must explain the joke, the pick is wrong.
5. **Render**:
   ```bash
   echo '{"artwork":"<id>","labels":{"<target>":"<text>"},"style":"placard","out":"/tmp/art-meme/<name>.jpg"}' | uv run scripts/render.py
   ```
   Styles: `placard` (default, museum small-caps) or `blunt` (heavy meme sans). Then display the output image to the user (read tool).
6. **Credit** is rendered automatically — never crop it off. Rendering uses the same image cache as `get_image.py`.

## Image cache

- Default: `${XDG_CACHE_HOME:-~/.cache}/art-meme`; override with `ART_MEME_CACHE_DIR`.
- Cache records include source page/download URLs, declared rights, and SHA-256; bytes are checked on every reuse. A mismatch fails with a `--refresh` instruction.
- `uv run scripts/get_image.py <artwork-id> --refresh` explicitly re-downloads the recorded file. First downloads and refreshes use the current source image; no historical revision pin or promise of byte-identity to an old authoring thumbnail.
- Source rights must be annotated `public-domain` or `cc0`. These are declarations, not automated legal verification. Keep the source link with shared context and preserve the image credit.
- If rendering reports missing fonts, install DejaVu (Linux), or provide `fonts/serif.ttf` and `fonts/sans-bold.ttf`. Georgia/Arial system fonts are also supported on macOS/Windows.

## Rules

- Abstention is success, not failure. Forcing a meme is the worst outcome.
- Never alter the artwork beyond label compositing; never skip the credit strip.
- Labels name the situation's actual participants, not generic ones, whenever context provides them.
- On a dud (wrong structure, dead joke, bad placement): append one line to `misses.md` in the image cache directory (create it if needed), naming the situation, the pick, and the suspected failing layer (ontology / corpus gap / labels / render). This keeps feedback local without requiring a source checkout.
