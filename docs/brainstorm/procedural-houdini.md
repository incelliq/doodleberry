# Brainstorm: a procedural and simulation layer ("Houdini-like Doodleberry, or beyond")

> **Status: food for thought, refined once (November 2026).** Captured to brainstorm later, then researched: licences
> checked against registries and project pages, and the main building blocks tried headless on this container's CPU
> (results below). Two small items were promoted into Phase 2 of `docs/build-plan.md` (2.19 cartoon physics, 2.20 motion
> effects). Everything else stays here, unscheduled, behind the gates at the end.

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
| Particles, physics | Blender physics; Bullet; Rapier |
| VEX / custom solvers | NumPy, NVIDIA Warp (Apache-2.0), Taichi (Apache-2.0, slowed) |
| USD layout (Solaris) | OpenUSD, usdview |
| Rendering (Karma) | Cycles, appleseed, LuxCoreRender; OSL |
| Compositing (COPs) | Natron, Blender compositor, Gaffer |
| Task graphs / farm (PDG) | OpenCue, our own orchestrator and content-hash caching |
| Shared plumbing | ASWF: OpenVDB, OpenEXR, OpenColorIO, OpenImageIO, MaterialX, OpenTimelineIO |

## What the research changed
1. **The lesson to take from Houdini is the cook model, not the 3D toolset.** Houdini's lasting idea is a recipe of
   nodes that re-cooks only what changed, with packaged, parameterised assets (HDAs). We already have the start of
   this: per-shot content hashes (`_shot_hash`), `@command` functions that act as nodes, and JSON film data as the
   recipe. Extending that to per-node caches costs little and helps every renderer.
2. **Most of the value for cartoons is 2D and cheap.** Physics-driven props, motion effects (smears, speed lines, dust
   puffs, impact stars), procedural sets, and doodle crowds can all be computed in the bake step and drawn as vector
   shapes, so they reach SVG, Synfig, Lottie and Grease Pencil without a 3D renderer. A deterministic 2D physics
   engine runs in the bake step in milliseconds (measured below).
3. **3D procedural work is feasible headless, and deterministic.** A Geometry Nodes graph built from Python, evaluated
   in Blender 5.2.3 with `-b`, rebuilt the same mesh twice (hash-equal), changed with the seed, and took 0.1 s. The
   3D track does not need to be invented; it needs a graph format and a cache.
4. **Heavy solvers stay gated.** Fluids, smoke and large cloth runs want GPUs. Taichi's development has slowed (last
   release 1.7.4, July 2025; the team says it is maintained but focused elsewhere), so prefer NumPy or Warp for any
   in-house solver.
5. **Several "AI helper" picks either do not fit or need care.** RIFE and FILM inbetween raster frames, but our
   puppets are vector data we can already sample at any time, so they only matter for imported frame-by-frame
   animation. ToonCrafter generates video and conflicts with the never-build rule on generative-video characters.
   Depth Anything V2 is Apache-2.0 only for its Small model. Stable Audio Open is under a revenue-capped community
   licence, not open source.

## Measured on this container (4 CPUs, no GPU)
Scripts are in `docs/brainstorm/probes/`; run them to repeat.

| Tool (version, licence) | Test | Result |
|---|---|---|
| Blender Geometry Nodes (5.2.3, GPL, subprocess) | graph built from code: noise terrain, seeded point scatter, instanced cones; evaluated with `-b`; mesh hashed | 11,368 vertices in 0.13 s; two runs hash-equal; seed 8 gives a different mesh |
| Rapier 2D deterministic build (`@dimforge/rapier2d-deterministic-compat` 0.21.0, Apache-2.0) | 12 bouncing balls, 300 steps, in Node, run twice | 14 ms warm (70 ms first run, WASM start-up); bit-identical position hashes |
| pybox2d (`box2d` 2.3.10, zlib) | box drop, 180 steps, rerun | identical trajectories; note it binds the old Box2D 2.3, not v3 (MIT) |
| pybullet (3.2.7, zlib) | 5-box stack, 10 s | stack settles with the top box at z 4.50, as expected for unit boxes; no drift |
| Taichi (1.7.4, Apache-2.0) | CPU kernel over 262,144 elements | 2.1 ms per kernel after a 0.6 s start-up |
| manifold3d (3.5.4, Apache-2.0) | cube minus sphere | volume 0.865, genus 5 (the correct topology: a frame with six holes) |
| usd-core (26.11, TOST-1.0) | in-memory stage, sphere, export usda | works; 201-byte usda |
| music21 (10.5.2, BSD-3) | key analysis of a C major arpeggio | "C major" in 0.28 s |

## Licences checked (November 2026)
Tags follow `docs/oss-research.md`: [V] primary file or official page read, [R] registry metadata or a search summary,
[U] unverified.

| Project | Licence | Fit | Note |
|---|---|---|---|
| Rapier (Rust, JS builds) | Apache-2.0 [R] | ★ 2.19 | not MIT; cross-platform determinism needs the `-deterministic` JS builds or the enhanced-determinism feature |
| Box2D v3 | MIT [R] | alternative | v3.1.1, June 2025; the PyPI binding is the old 2.3 (zlib); `planck` (MIT) is a maintained JS port |
| Bullet / pybullet | zlib [R] | 5B | via Blender or pybullet |
| Manifold / manifold3d | Apache-2.0 [R] | 1.7, 5B | its 2D `CrossSection` (Clipper2) can also make toon-shading offsets |
| NVIDIA Warp | Apache-2.0 [R] | 5C | relicensed from a NVIDIA licence around v1.6.2 (March 2025); now 1.18.0; has a CPU backend |
| Taichi | Apache-2.0 [R] | 5C, second choice | 1.7.4, July 2025; development slowed |
| Genesis ("genesis-world") | Apache-2.0 [U] | park | 1.4.5, October 2026; robotics focus, GPU-first; confirm the LICENSE file |
| OpenUSD (usd-core) | TOST-1.0 [R] | 5.11 | Apache-2.0 with a modified trademark section; not on OSI/SPDX lists; record it as such |
| OpenVDB | Apache-2.0 [R] | 5C | relicensed from MPL-2.0 in v12.0 (2025) |
| Gaffer | BSD-3 [R] | 5.11 evaluation | only mirrors confirmed it here; read the upstream LICENSE before use |
| React Flow (`@xyflow/react`) | MIT [R] | ★ 3.10 | 12.12.0; Pro examples are a paid add-on, the library is not |
| SAM 2 / 2.1 | Apache-2.0 [R] | ★ 1.8b | checkpoints Apache-2.0; one optional part BSD-3; the SA-V dataset has its own terms |
| Practical-RIFE | MIT [R] | low | only for raster frame-by-frame imports |
| FILM (frame interpolation) | Apache-2.0 [U] | low | same limit as RIFE |
| ToonCrafter | unclear | avoid | "research exploration"; weights derive from DynamiCrafter; generative video |
| Depth Anything V2 | Small Apache-2.0; Base/Large/Giant CC-BY-NC-4.0 [R] | 1.6 option | Small only, for 2.5D parallax of photo backgrounds |
| OpenRV | Apache-2.0 [R] | 3.4 option | ASWF; licensed codecs excluded |
| xSTUDIO | Apache-2.0 [V] | 3.4 option | raw LICENSE read |
| Typst (core, Python binding 0.15) | Apache-2.0 [R] | ★ 4.8 | print path for comics and storybooks |
| music21 | BSD-3 [R] | ★ 2.14 | |
| FluidSynth / pyfluidsynth | LGPL-2.1 / MIT [R] | ★ 2.14 | run FluidSynth as a process |
| GeneralUser GS 2.0.1 soundfont | permissive, commercial use allowed [R] | 2.14 | the author does not vouch for every sample's origin: keep it out of published films until reviewed |
| Tone.js | MIT [R] | 3.1 | in-browser score preview |
| Godot | MIT [R] | ★ 4.8 | interactive export target |
| Poly Haven, ambientCG | CC0 [R] | ★ 1.6, 5B | |
| Argos Translate | MIT [R] | 4.5 | draft translations |
| trimesh, Open3D, CoACD | MIT [R] | 5B | |
| Mitsuba 3 / Dr.Jit | BSD [R] | park | |
| pymeshlab | GPL-3 [R] | avoid in-process | |
| Stable Audio Open | Stability Community License [R] | avoid | free only under USD 1M annual revenue; not open source |
| Kitsu | AGPL [U] | avoid in the service | |

## Brainstorm: going beyond Houdini, for cartoons
The aim is not a Houdini clone. It is the procedural ideas that make cartoons better and that an agent can drive.

**Physics as acting (cheap, 2D, deterministic)**
- **Target-hitting throws.** Solve for the launch velocity so a thrown ball lands in a hand at a line-relative time
  (`"mid.start+0.9"`). Today the props demo scripts the arc; a shooting solver over Rapier makes it physical and keeps
  sync when re-voiced.
- **Secondary props:** hats that fly off, tumbling books, swinging signs, dangling keys, ropes and tails as joint
  chains. Bake the result into the same keyframe data every renderer reads.
- **Land on the beat.** Retime a simulation with a monotone time warp so contacts hit beat-grid frames (2.14), then
  step it on 2s for the hand-made look. Physics stays plausible; timing stays directed.
- **Cartoon physics rules:** squash on impact with volume kept, a hang-time hold at the apex, a delayed fall after
  running off a ledge. These are art-directable overrides on top of a real solver, not a different solver.

**Motion effects from baked motion**
- Smear frames, speed lines, dust puffs on landings, impact stars, sweat drops and motion arcs, generated from part
  velocities and contacts already in the bake. Deterministic, vector, and on all renderers. This is the cartoon
  version of Houdini's simulation-driven effects, and it costs a fraction of it.

**Procedural sets and crowds (2D first)**
- Seeded Poisson-disk scatter of trees, clouds, rocks and houses along parallax depth bands; rule-based skylines and
  streets; weather layers (rain, snow, falling leaves) as vector particles.
- Doodle crowds: walk cycles on paths with simple velocity-obstacle avoidance, variants by swap sets, the doodle
  template's clips for idle behaviour.

**One cook graph for 2D and 3D**
- Nodes are `@command` functions; a graph is JSON (nodes, sockets, exposed parameters, seeds). Each node's output is
  cached by the hash of its inputs and the node's code, extending `_shot_hash`. A Studio graph view built on React
  Flow edits the same JSON, so agents and people share one model (every UI action is a command).
- 3D nodes call Blender Geometry Nodes headless through a subprocess; the probe shows a graph can be generated from
  JSON and evaluated deterministically.

**Scoring art direction**
- Readability metrics on top of solver benchmarks: arc smoothness, contacts on beats, squash volume within a band,
  silhouette clarity of effects against the set, and a director critic for the rest. This keeps tuning measurable
  where Houdini relies on an artist's eye.

## Refined Phase 5 (sketch; only 2.19 and 2.20 are scheduled)
Three tracks, cheapest first. Each later track starts only if its gate passes.

**5A. Procedural 2D (CPU, inside the existing bake)**

| # | Item | Build with | Done when |
|---|---|---|---|
| 2.19 | Cartoon physics (promoted to Phase 2) | Rapier 2D deterministic build in `tools/bake.mjs` | see the build plan |
| 2.20 | Motion effects from baked motion (promoted to Phase 2) | in-house | see the build plan |
| 5.1 | Cook graph: JSON node graphs over `@command` nodes, per-node content-hash caches, downstream-only re-cooks; `proc.cook` | in-house | changing one parameter re-cooks only downstream nodes, and two cooks are hash-equal |
| 5.2 | 2D procedural set kit: scatter, skylines, roads, weather layers, parallax bands | in-house; Kenney/Poly Haven art | five sets generated from briefs pass layout QA |
| 5.3 | Doodle crowds on paths with avoidance and variants | in-house | 30 doodles cross a street without overlaps; all renderers agree |
| 5.4 | Agent graph authoring: brief → graph → cook → QA → revise | agent + 5.1 | ten benchmark briefs pass a critic without hand edits |
| 5.5 | Studio graph editor | React Flow (MIT) | a graph edited in Studio is the same JSON an agent writes |

**5B. Procedural 3D (Blender headless, behind a process boundary)**

| # | Item | Build with | Done when |
|---|---|---|---|
| 5.6 | Graph-to-Geometry-Nodes compiler and `proc.bake`; HDA-like library (terrain, scatter, buildings, clouds) | Blender 5.2.3; manifold3d, trimesh | 15 assets, each with a parameter schema, thumbnail and golden bake |
| 5.7 | Rigid bodies and cartoon destruction | Blender rigid bodies (Bullet) | stable and hash-equal per seed |
| 5.8 | Toon effects presets in 3D (puffs, splashes, sparkles) rendered with alpha and camera-matched to the 2D camera | Geometry Nodes simulation zones; toon shaders | presets composite into SVG shots in the studio look |
| 5.9 | USD interchange; Gaffer evaluated here | usd-core (TOST); Gaffer (BSD-3) | a scene round-trips through usdview |

**5C. In-house solvers (GPU budget needed)**

| # | Item | Build with | Done when |
|---|---|---|---|
| 5.10 | XPBD cloth and soft bodies (capes, flags, jelly characters) | NumPy first, Warp for speed | passes a drape and drift benchmark |
| 5.11 | Stylised liquids and smoke (FLIP/APIC, stable fluids) | Warp; OpenVDB for caches | dam-break front within tolerance of published data |
| 5.12 | Solver benchmark suite and tuning agent | in-house; cloud GPU | tuning improves a target score without regressing others |
| 5.13 | Human art-direction sign-off per preset | review room | each preset has a recorded sign-off |

**Gates**
- **Into 5A (5.1 onward):** 2.19 and 2.20 have shipped and been used in at least two films.
- **Into 5B:** a film needs a 3D set or effect that the 2D kit cannot make, and the Blender subprocess stays the only
  GPL boundary.
- **Into 5C:** a GPU budget is confirmed, and each solver is proved at small scale on CPU first; Blender's built-in
  solvers are tried before writing our own.
- **Always:** cartoon look only; renders deterministic per seed (hash-equal reruns are a test); licences recorded in
  `docs/oss-research.md` before adoption.

Never: a general Houdini replacement UI, photoreal hero VFX, or generative-video effects.

## Gaffer
GafferHQ (BSD-3): node-based lookdev, lighting and scene assembly (USD and Alembic), a Cycles/Arnold/3Delight/RenderMan
front end, a compositor, dispatch to a farm, and headless runs with `gaffer execute`. It has no modelling or
simulation; pair it with Blender. Evaluate it at 5.9, and adopt it only if we need USD lookdev at scale or
human-authored reusable lighting and compositing graphs.

## Where the other picks slot in
| Pick | Slot | Why |
|---|---|---|
| SAM 2.1 (tiny or small checkpoint) | 1.8b, auto part cuts in ink import | suggests masks for head, arms and body from a click per part; CPU-slow, so suggestions only |
| Manifold `CrossSection` | 1.7 toon shading | polygon offsets for cel shadows and rims; an alternative to pyclipr |
| Poly Haven, ambientCG (CC0) | 1.6 sets; 5B | textures and HDRIs for 3D sets |
| Depth Anything V2 Small | 1.6 option | 2.5D parallax from a photo background |
| music21, FluidSynth (process), Tone.js | 2.14 beat grid and score | scores as data, rendered offline, previewed in the browser |
| OpenRV or xSTUDIO | 3.4 review room (desktop option) | for reviewers who want a pro player; fed by the 4.1 OTIO export |
| React Flow | 3.10 graph view; 5.5 | also useful to show a film's data flow (facts → script → shots → renders) |
| Typst | 4.8 comics and storybooks (E6) | print-ready PDFs from the same stills and text |
| Godot | 4.8 interactive films | export puppets and baked clips to a game engine |
| Argos Translate | 4.5 | draft translations for review, not final text |
| RIFE / FILM | low priority | only for imported raster frame-by-frame animation |

Still unvetted, kept for later: Jolt, PhysX 5, Chrono, MuJoCo, SPlisHSPlasH, OpenSubdiv, libigl, Alembic, NanoVDB,
Rete.js, litegraph.js, Material Maker, Blender Line Art, Filament, pbrt-v4, Embree, DJV, Rez, OpenAssetIO, Open Job
Description, Flamenco (GPL, separate service), AYON, Real-ESRGAN, Demucs, librosa, Pure Data, Csound, SuperCollider,
Surge XT, OPUS-MT, HarfBuzz, fontTools, Scribus, Vega-Lite, D3, Observable Plot, MapLibre, PixiJS, Bevy, Smithsonian
Open Access, NASA 3D, Sketchfab CC0, EasyMocap. Avoid: MusicGen weights and NLLB (NC), LibreTranslate and FreeMoCap in
the service (AGPL), SMPL-based models (NC).

## Sources
- Box2D: https://box2d.org and https://github.com/erincatto/box2d (MIT)
- Rapier licence and determinism: https://rapier.rs (user guides, determinism section) and the npm `-deterministic` packages
- NVIDIA Warp Apache-2.0 relicence: https://github.com/NVIDIA/warp (CHANGELOG, v1.6.2)
- OpenVDB 12 licence change: https://www.openvdb.org/
- OpenUSD licence: https://openusd.org (LICENSE.txt, TOST-1.0)
- SAM 2: https://github.com/facebookresearch/sam2
- Depth Anything V2 model cards: https://huggingface.co/depth-anything
- Stable Audio Open licence: https://huggingface.co/stabilityai/stable-audio-open-1.0
- xSTUDIO: https://github.com/AcademySoftwareFoundation/xstudio ; OpenRV: https://github.com/AcademySoftwareFoundation/OpenRV
- Taichi status discussion: https://github.com/taichi-dev/taichi/discussions/8506
- Genesis: https://github.com/Genesis-Embodied-AI/genesis-world
- Practical-RIFE: https://github.com/hzwer/Practical-RIFE
- Registry metadata (versions and licence fields): PyPI and npm, read on 2026-11-01
