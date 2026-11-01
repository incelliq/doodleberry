# Brainstorm: a procedural and simulation layer ("Houdini-like Doodleberry, or beyond")

> **Status: food for thought, not a commitment.** It was captured in November 2026 to brainstorm later. Nothing here is
> scheduled. Licences below are from memory: verify them through the `docs/oss-research.md` process before adopting
> anything.

## The idea
SideFX Houdini is a commercial, node-graph-based procedural 3D package: simulation (fire, smoke, water, destruction,
cloth, crowds), procedural modelling, packaged node assets (HDAs), USD layout (Solaris), the Karma renderer,
compositing, and a task/farm scheduler (PDG/TOPs). Its core philosophy, a scene as a recipe that re-cooks, is the
same "film as data" idea Doodleberry follows.

No single open-source tool matches it. The closest stack:

| Houdini area | Closest open source |
|---|---|
| Procedural node modelling (SOPs) | Blender Geometry Nodes (+ simulation nodes); Sverchok, Animation Nodes |
| Smoke, fire, liquids | Blender Mantaflow; OpenVDB volumes |
| Particles, physics | Blender physics; Bullet |
| VEX / custom solvers | Python, Taichi (Warp: check licence) |
| USD layout (Solaris) | OpenUSD, usdview |
| Rendering (Karma) | Cycles, appleseed, LuxCoreRender; OSL |
| Compositing (COPs) | Natron, Blender compositor, Gaffer |
| Task graphs / farm (PDG) | OpenCue, our own orchestrator and content-hash caching |
| Shared plumbing | ASWF: OpenVDB, OpenEXR, OpenColorIO, OpenImageIO, MaterialX, OpenTimelineIO |

## Open question: how far could Claude plus compute go?
Two views to weigh later.
- **Conservative:** parity with Houdini's solvers is research-grade work that took decades. Aim for the slice cartoons
  need: environments, crowds, stylised effects, props, camera rigs.
- **Ambitious:** the published solvers (FLIP/APIC, stable fluids, XPBD, constraint-based rigid bodies) are well
  documented, and implementing them with tests and vectorised kernels is fast. Long-horizon tuning works when a
  benchmark can score the result (dam-break front position, energy and volume drift, stacking stability, cloth drape),
  the same pattern as our golden frames and QA.

Bottlenecks either way:
- **Scoring:** art-directability is a human judgment.
- **Compute:** GPUs are needed for heavy simulation and tuning loops.
- **Edge cases:** most of them only show up through real production use.
- **Scale:** sparse grids, adaptivity, out-of-core data and determinism across machines are large engineering work.

## A possible Phase 5 (sketch, weeks 24–34 if ever adopted)
Goal: procedural environments, crowds and stylised effects authored by agents from plain-language briefs. Everything
is baked headless, cached by content hash, measured against benchmarks, and composited into normal shots.

| # | Item | Build with | Done when |
|---|---|---|---|
| 5.1 | Procedural graph format: JSON node graphs (nodes, sockets, exposed parameters, seeds) built and baked headless into Geometry Nodes; `proc.bake` command | Blender, Python | a graph rebuilds the identical bake twice (hash-equal) |
| 5.2 | HDA-like asset library: terrain, scatter, roads, buildings, city blocks, clouds, rain and snow, crowds-on-paths | Geometry Nodes, manifest | 15 assets, each with a parameter schema, thumbnail and golden bake |
| 5.3 | Agent graph authoring: brief → graph → bake → QA → revise ("200 trees on the hill, denser near the river") | agent + 5.1/5.2 | 10 benchmark briefs pass a critic without hand edits |
| 5.4 | PDG-like task graph: per-node content-hash caches, downstream-only re-cooks, parallel and cloud GPU workers | existing hashing and orchestrator; OpenCue if needed | changing one parameter re-cooks only downstream nodes |
| 5.5 | Stylised effects presets: toon smoke puffs, dust, splashes, fire licks, sparkles, speed trails | Mantaflow, particles, toon shaders | presets composite into SVG shots with alpha, in the studio look |
| 5.6 | XPBD cloth and soft bodies (capes, flags, jelly characters) | Taichi or NumPy | passes the benchmark suite; drift within thresholds |
| 5.7 | Rigid bodies and cartoon destruction | Bullet via Blender, fracture presets | stable, deterministic per seed |
| 5.8 | FLIP/APIC liquids and grid smoke, starting stylised | Taichi, OpenVDB | dam break within tolerance of published data |
| 5.9 | Solver benchmark suite and tuning agent | in-house, cloud GPU | tuning improves a target score without regressing others |
| 5.10 | Art-direction controls: guides, attractors, timing curves, shape holds | Geometry Nodes, solver hooks | a director agent retimes an effect to a beat without re-tuning |
| 5.11 | USD interchange (export and import), Gaffer evaluated here | OpenUSD; Gaffer (BSD-3) | a scene round-trips through usdview |
| 5.12 | Procedural shot layer: bakes rendered with alpha, camera matched to the 2D camera keys | compositor, camera folding | pip-park gains a procedural park; QA passes |
| 5.13 | Human art-direction review per effect preset | review room | each preset has a recorded sign-off |

Possible gates:
- **Compute:** confirm a GPU budget, and prove each solver at small scale on CPU first.
- **Build vs reuse:** use Blender's built-in solvers unless benchmarks show they miss the stylised targets.
- **Look:** cartoon style only.
- **Licences:** Blender stays behind a process boundary.

Never: a general Houdini replacement UI, or photoreal hero VFX before the stylised solvers pass their benchmarks.

## Gaffer
GafferHQ (BSD-3): node-based lookdev, lighting and scene assembly (USD and Alembic), a Cycles/Arnold/3Delight/RenderMan
front end, a compositor, dispatch to a farm, and headless runs with `gaffer execute`. It has no modelling or
simulation; pair it with Blender. Evaluate it at 5.11/5.12, and adopt it only if we need USD lookdev at scale or
human-authored reusable lighting and compositing graphs.

## Ecosystem not yet in oss-research.md (★ = strongest fit)
- **Physics and geometry:**
  - ★Box2D (2D cartoon physics), ★Rapier (deterministic 2D and 3D physics)
  - Jolt, PhysX 5, Chrono, MuJoCo, SPlisHSPlasH, Genesis
  - Manifold (booleans), OpenSubdiv, libigl, trimesh, Open3D
  - Alembic, NanoVDB
- **Node-graph UIs:** ★React Flow, Rete.js, litegraph.js; Material Maker (texture graphs).
- **NPR and rendering:** Blender Line Art, Filament, Mitsuba 3, pbrt-v4, Embree.
- **Review and playback:** ★OpenRV, xSTUDIO, DJV.
- **Pipeline:**
  - ★Rez (pinned tool environments)
  - OpenAssetIO, Open Job Description, Flamenco (GPL, separate service), AYON
  - Kitsu (AGPL: avoid in the service)
- **AI helpers within the no-generative-characters rule:**
  - ★SAM 2 (auto part cuts for ink import)
  - ★RIFE and FILM (inbetweening)
  - Depth Anything (2.5D), Real-ESRGAN
  - ToonCrafter (likely research-only)
- **Audio:**
  - ★music21, ★FluidSynth (separate process) with soundfonts (check each)
  - Demucs, librosa
  - Pure Data, Csound, SuperCollider, Surge XT
  - Avoid MusicGen weights (NC); check Stable Audio Open
- **Translation drafts:** Argos Translate, OPUS-MT. Avoid NLLB (NC) and LibreTranslate in the service (AGPL).
- **Type, print, comics:** HarfBuzz, fontTools, ★Typst (print path for comics and storybooks), Scribus.
- **Data visualisation:** Vega-Lite, D3, Observable Plot, MapLibre.
- **Interactive:** ★Godot (export target), PixiJS, Bevy.
- **Assets:**
  - ★Poly Haven (CC0), ambientCG (CC0)
  - Smithsonian Open Access (CC0), NASA 3D (check terms), Sketchfab CC0 subset
- **Mocap from video:** EasyMocap (check), FreeMoCap (AGPL). Avoid SMPL-based models (NC); MediaPipe and rtmlib remain
  the safe route.

Picks worth a closer look first: Box2D or Rapier, SAM 2, RIFE, OpenRV or xSTUDIO, React Flow, Typst, music21 with
FluidSynth, Godot, Poly Haven.
