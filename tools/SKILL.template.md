---
name: art-meme
description: Respond to a session moment with a fine-art meme — a public-domain masterpiece whose emotional structure matches the moment, with labels composited onto its figures. Triggered by "meme this", "art meme", "fine art meme", "react to this with art", "make a meme of this moment", or any request to caption/memeify a situation with a painting. Produces a shareable JPEG with credit line. Abstention is a valid outcome.
---

# art-meme

**BLUF:** Distill the moment into an emotional structure, filter the corpus with `tools/match.py` (hard gates in code), pick the funniest fit, write ≤5-word labels mapping session entities to the painting's figures, render with `tools/render.py`, and show the image. If nothing fits, say so — never force a pick.

All paths below are relative to this skill's directory.

## Pipeline

1. **Distill** the moment into one sentence: *who wants what, who's winning, who's horrified.* Choose 1–3 candidate structure ids from `index.yaml` `structures` (read the whole file — it's small). Note the desired comic register and any content constraints from context (e.g. exclude `graphic-violence` in professional settings).
2. **Filter (code, not judgment):**
   ```bash
   uv run tools/match.py --structures <id,id> [--exclude-flags <flag,flag>]
   ```
   Empty result → **abstain**: tell the user no artwork fits that structure, offer the nearest structures that do exist. Do not stretch a wrong painting.
3. **Pick** from the survivors: best structural fit first, then register fit. Intensity mismatch is allowed and often *is* the joke (Saturn for a trivial dependency bump). Repeating a recently used work is worse than a slightly weaker fit.
4. **Label**: ≤5 words per target, mapping real session entities to bound targets. Unbound targets may also be labeled when funny. Optional `caption` (strip above the canvas) — but if the caption must explain the joke, the pick is wrong.
5. **Render**:
   ```bash
   echo '{"artwork":"<id>","labels":{"<target>":"<text>"},"style":"placard","out":"/tmp/art-meme/<name>.jpg"}' | uv run tools/render.py
   ```
   Styles: `placard` (default, museum small-caps) or `blunt` (heavy meme sans). Then display the output image to the user (read tool).
6. **Credit** is rendered automatically — never crop it off.

## Rules

- Abstention is success, not failure. Forcing a meme is the worst outcome.
- Never alter the artwork beyond label compositing; never skip the credit strip.
- Labels name the user's entities, not generic ones, whenever context provides them.
- On a dud (wrong structure, dead joke, bad placement): append one line to `~/development/miscellaneous/art-meme/misses.md` naming the moment, the pick, and which layer died (ontology / corpus gap / labels / render). That file drives corpus growth.
