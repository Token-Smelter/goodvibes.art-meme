# [GoodVibes] Art Meme

Describe a situation. Get the painting that already knew: a public-domain artwork, short labels, and a museum-style credit strip. An agent skill from **Good Vibes by [TokenSmelter](https://github.com/Token-Smelter)**.

The situation can be anything with participants and a tension between them — something that just happened in your session, a hypothetical, your team's predicament, an entire industry's problem, or a mood.

```mermaid
flowchart LR
    Situation["Any situation"] --> Match["Match an emotional structure"]
    Match --> Pick["Choose an artwork or abstain"]
    Pick --> Image["Fetch the recorded source and cache it"]
    Image --> Render["Labels + artwork + credit"]
```

## Install

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/), Python 3.11+, and an agent that reads `SKILL.md` skills. Images need internet access on first use; cached images work offline. uv installs the Python dependencies when each script runs.

This repository **is** the plugin — a directory, not an archive. It ships a root [`plugin.json`](./plugin.json) targeting the [Agent Plugins](https://agent-plugins.org/specification) v1.0.0 standard, and the skill itself follows the [Agent Skills](https://agentskills.io/specification) spec. Clone it once:

```bash
git clone https://github.com/Token-Smelter/goodvibes.art-meme.git
```

Then point your agent at it. The skill is committed at `skills/art-meme/`, so no build step is required.

| Agent | Install |
|---|---|
| Claude Code | `ln -s "$PWD/goodvibes.art-meme/skills/art-meme" ~/.claude/skills/art-meme` |
| Codex | `ln -s "$PWD/goodvibes.art-meme/skills/art-meme" ~/.agents/skills/art-meme` |
| Pi | `ln -s "$PWD/goodvibes.art-meme/skills/art-meme" ~/.pi/agent/skills/art-meme` |
| Any Agent Plugins client | Load the repository root as a plugin directory |

Copy the directory instead of linking it if you prefer a detached snapshot. Either way the installed skill is named `art-meme`; only the repository carries the `goodvibes.` collection prefix.

Rebuild `skills/art-meme/` after editing anything under `corpus/`, `structures.yaml`, or `tools/`:

```bash
uv run tools/build_skill.py
```

Then ask your agent:

> Make a fine-art meme about our company spending millions on AI while every output still waits on a handful of reviewers.

The agent distills the situation, chooses from the curated corpus, inspects the image, writes labels naming the real participants, and renders a JPEG. If no painting fits, it should say so rather than force a joke. Invoke it explicitly; it does not post messages or publish images for you.

## Try the renderer directly

From the `skills/art-meme/` directory:

```bash
uv run scripts/get_image.py titian-sisyphus
printf '%s\n' '{"artwork":"titian-sisyphus","labels":{"sisyphus":"me","boulder":"the weekly status report"},"out":"/tmp/sisyphus.jpg"}' | uv run scripts/render.py
```

The image command returns a local `path` for inspection and source provenance. The renderer also downloads automatically when needed. It keeps the full composition, adds labels without cropping, and appends artist/title/date below the canvas.

## Images stay outside the package

The repository and generated skill distribute **code and annotations, not artwork files**. Downloads resolve the exact recorded Wikimedia Commons filename, never a new artwork search.

| Setting | Behavior |
|---|---|
| Cache | `${XDG_CACHE_HOME:-~/.cache}/art-meme`, or `ART_MEME_CACHE_DIR` |
| Integrity | SHA-256 recorded on download and verified on every cache reuse |
| Refresh | `uv run scripts/get_image.py <id> --refresh` bypasses local/cache copies |
| Source changes | First downloads/refreshes use the current Commons file; historical revisions are not pinned |
| Failures | Unavailable sources and corrupt cache entries produce errors, not search substitutions |
| Fonts | System DejaVu on Linux, Georgia/Arial on macOS/Windows, or user-supplied `fonts/serif.ttf` and `fonts/sans-bold.ttf` |

## Package layout

```text
goodvibes.art-meme/
├── plugin.json              # Agent Plugins v1.0.0 manifest (portable)
├── .claude-plugin/          # Claude Code's own manifest location
├── skills/art-meme/         # generated, committed, installable
│   ├── SKILL.md
│   ├── scripts/             # get_image, match, render
│   ├── corpus/              # artwork annotations
│   └── index.yaml
└── tools/                   # authoring sources that generate the skill
```

Agent Plugins v1 standardizes two component types: skills and MCP servers. This plugin ships one skill and no MCP server.

## Extend it

- **`structures.yaml`** defines reusable relations between roles.
- **`corpus/*.yaml`** identifies artworks, label geometry, and each artwork's role bindings through `uses[]`. Mapping is many-to-many.
- **`tools/SKILL.template.md`** supplies the agent instructions.
- **`tools/build_skill.py`** generates the shareable skill. Never hand-edit `skills/art-meme/`; a test fails if the committed copy drifts from its sources.
- **`tools/fetch_commons.py`** is an authoring search helper, not a runtime dependency. Optional local `corpus/images/` copies are ignored by Git and never packaged.

Inspect the original and a test render when adding or changing an annotation. Existing structural matches and label placement are experimental; a successful build is not proof that a joke lands. See [DESIGN.md](./DESIGN.md) for design context, including aspirational behavior not yet enforced by the scripts.

## Check

```bash
uv run --with pillow --with pyyaml python -m unittest discover -s tests -v
uvx ruff check tools tests --select F --ignore E402
uv run tools/build_skill.py
```

The tests use generated fixtures and an external cache; they do not download artwork. uv may need a network connection to obtain dependencies on its first run.

## License

Code and original project documentation/annotations are available under the [MIT License](./LICENSE). Use, modify, redistribute, and sell them; retain the copyright and license notice. No warranty is provided.

**Artwork is separate:** the source records declare public-domain or CC0 status, but the MIT license does not relicense third-party images or fonts. Images download directly from their recorded sources; preserve source links and the rendered credit. Rights declarations are not automated legal verification.
