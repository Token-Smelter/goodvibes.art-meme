---
api_version: sourcerer.project/v2
kind: project
id: art-meme
name: Art Meme
summary: >-
  Fine-art meme replacement: map popular meme templates to public-domain
  masterworks with the same emotional structure, exposed as an agent skill
  that picks an artwork from a curated map using session context and places
  labels on its character slots.
type: application

protected_refs:
  - main

lineage:
  default_provider:
    id: git
    version: "1.0"
  providers:
    - id: git
      version: "1.0"
      config:
        remote: origin
        upstream_ref: main
        worktree_layout: nested
        worktree_root: /home/mike/development/miscellaneous/art-meme

grounding:
  - description: Project concept, pipeline, annotation schema, and validation plan
    path: README.md

capabilities:
  - type: code-edit
    version: "1.0"
    description: >-
      Annotation pipeline, artwork-index tooling, meme mapping data, and the
      artwork-selection skill for the art-meme project.
    domains:
      - art-meme
---

# Art Meme

Map popular meme templates to public-domain fine art with the same emotional
structure. Output is an agent skill that reads a curated artwork map, picks a
work using session context, and places labels on its character slots.

See `README.md` for the pipeline (art-first annotation, visceral filter,
many-to-many mapping) and the validation plan.
