# 🫐 Doodleberry

Code-drawn cartoon films, and a home for **hand-drawn puppets** that the same engine can animate.

Doodleberry started as the `motion/` pipeline in chalklore-infra (history preserved): every frame is a pure function of
the frame number, rendered in headless Chromium, with synthesized narration, score and effects, measured QA and
contact sheets for review. It now has three ways to put characters on screen:

| layer | what it is | where |
|-------|------------|-------|
| **2D engine** | SVG frame functions, cel-shading primitives, rigs (`Cast`, `Human`), word-timed captions, lip-sync, score/sfx/mix, QA | `engine/`, `films/` |
| **Puppets** | a format, loader and drawing app for artist-drawn cut-out characters | `puppet/` |
| **dbe backend** | one command registry for people and agents: CLI, HTTP + Studio UI, MCP. Shot lists route each shot to SVG, Synfig, Grease Pencil (Blender) or Lottie; captions, mix and QA on top | `dbe/`, `docs/dbe.md` |
| **Acting** | lip-sync from the voice's phonemes, two-bone IK with foot pins, springs, pose presets, an action-clip stack, views (turns) | `puppet/loader/acting.js`, `puppet/clips/` |
| **3D** | three.js renderer (headless WebGL), CC0 characters, CMU mocap retargeting, Blender/Synfig tools | `tools/three`, `tools/blender`, `tools/synfig`, `films/screwworm-3d` |

## Puppets
- `puppet/spec/` — the `.puppet.json` format (v0.2: views, springs, poses) and its JSON Schema.
- `puppet/templates/humanoid.json` — 18 parts (hips → feet, hair front/back), swap sets (eyes, pupils, brows, mouth chart, hand poses), palette slots, a ghost guide.
- `puppet/loader/puppet.js` — `Puppet.render(puppet, x, y, pose)` returns SVG for any pose (angles, talk, blink, look, swaps, recolour); `Puppet.pointOf()` finds a hand for props; `Puppet.lint()` checks completeness.
- `puppet/canvas/index.html` — **Rig Canvas**, the drawing app: pick a slot, draw filled shapes or pressure ink lines, drag pivots, watch the live preview wave/talk/walk, colour by palette slot, export `.puppet.json`. Open it straight from disk; no build step.
- `puppet/examples/make_pip.py` + `pip_side.py` — build the example puppet *Pip* (front and side views); `films/puppet-demo` renders a pose sheet, `films/acting-demo` the acting layer, `films/pip-park` one film through three renderers.

## Quick start
```bash
# the backend (see docs/dbe.md)
python -m dbe engine.info                          # what is installed
python -m dbe film.render '{"name": "pip-park"}'   # svg + synfig + grease-pencil shots, captions, mix, QA
python -m dbe serve                                # Studio UI at http://127.0.0.1:8770
python -m dbe mcp                                  # MCP server for agents
# 2D film (see docs/engine.md for the full pipeline)
python engine/voice.py films/clover --voices-dir ~/voices && node engine/render.mjs films/clover --dump-cues
python engine/audio.py films/clover && node engine/render.mjs films/clover --workers 4
# puppets
open puppet/canvas/index.html                      # draw a character
python puppet/examples/make_pip.py && node engine/render.mjs films/puppet-demo --still 10
# 3D films need an HTTP server (GLB fetches): python -m http.server 8766 from the repo root
node tools/three/run3d.mjs http://127.0.0.1:8766/films/screwworm-3d/index.html out.mp4 4
```
Requirements: Node + Playwright (Chromium), ffmpeg, Python 3.11+ with `piper-tts faster-whisper numpy scipy soundfile pyloudnorm pyworld`,
a Piper voice with a clean licence (`python -m dbe voices.list`); optional Blender 5.x, Synfig CLI, Mesa (`mesa-vulkan-drivers libegl1`) for software 3D.

## Docs
- `docs/dbe.md`: the backend (CLI, HTTP, Studio, MCP) and renderers.
- `docs/feature-map.md`: every feature, tagged by source and status, plus emergent features.
- `docs/build-plan.md`: the phased build plan.
- `docs/oss-research.md`: vetted open-source libraries, models and assets, and licence warnings.
- `docs/director-prompt.md` and `docs/product-vision.md`.

## Ground rules
Original characters only (no recreations of existing ones); every factual line in a film traces to a source in its
`facts.json`; third-party assets stay out of git (CC0 packs are downloaded locally; see `references/3d-pipeline-research.md`).
