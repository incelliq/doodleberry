# Doodleberry Studio: the most powerful version (brainstorm)

**One line:** an agent-native animation studio where humans make the taste calls (story, characters, look) and an
agent does the production: research with sources, script, voices, rigging, acting, rendering across 2D and 3D
engines, QA and delivery. Every film is data, so it can be versioned, re-voiced, re-timed and re-rendered.

## What would make it different from Harmony, Moho, Spine or Live2D
1. **Agent-native.** Every action a human can take in the UI is also a command an agent can call (exposed as an MCP
   server). The command log is the undo history and a replayable script, so "make the doctor point earlier" is one call.
2. **Films are data, not timelines.** brief → facts → script → cast → shots → renders. Change a fact or a language and
   the dependent shots re-render; everything else comes from cache.
3. **Truth built in.** A facts ledger with source sentences, review levels and dates. Numbers on screen are bound to
   their sources and refresh when the source changes.
4. **Any renderer per shot.** One shot spec compiles to the SVG engine, puppets, three.js, Blender Grease Pencil or
   Synfig, and exports to Lottie or a game runtime. The best tool for each shot, one timeline, one mix.
5. **Humans draw, the system rigs.** Rig Canvas makes drawing and rigging one act, with live previews and a rig check.

## The product, layer by layer

### A. The rig engine (closing the gaps against pro tools)
| capability | status | plan |
|------------|--------|------|
| FK bone hierarchy | have | — |
| IK with hand/foot targets, pins, joint limits | missing | two-bone analytic IK per limb; pins solved after root motion; limits in the template |
| Smart bones / driven keys | missing | `drivers` in the puppet: one control (head turn −1..1) drives part swaps, offsets, z-order |
| Multi-view rigs (front, 3/4, side, back) | missing | per-view part sets and z-order; turn = driven key plus a smear frame |
| Bendy limbs, mesh and warp deformation | missing | SVG: path warp along a bone curve; raster: triangle mesh with bone weights in WebGL |
| Springs for hair, ties, coats, tails | in code only | spring chains declared in the puppet (`springs`), solved per frame, deterministic |
| Pose presets and blending | missing | named poses stored on the puppet; blend by weight; additive layers |
| Action clips + nonlinear blending (walk, talk, gesture) | missing | clips in a shared library per template; an NLA with crossfades and additive gestures |
| Viseme lip-sync | missing | phonemes from forced alignment (or text-to-phoneme plus word timing) mapped to the mouth chart |
| Procedural acting | partial | a gesture planner: stressed words get beat gestures, questions get head tilts, listeners nod, gaze follows the speaker |
| Constraints (look-at, follow path, parent switching) | partial | constraint list per shot: prop moves hand to hand, eyes track a target |
| Smears, speed lines, impact frames | partial | automatic smear frames on fast moves; impact library |
| Particles | partial | deterministic emitters (dust, rain, sparks, splashes) as shot components |
| Toon lighting, normal-map shading, light wrap, grain | partial | shading pass per part from a light direction, with optional hand-painted normal maps |
| 2.5D camera through 2D layers | three.js only | place 2D layers on z planes in three.js, with real camera moves and depth of field |
| Node compositor (masks, mattes, blend modes) | partial | a small compositor graph per shot, rendered with ffmpeg or WebGL |

### B. Human surfaces
- **Rig Canvas** (have v0.1): draw a puppet in slots; next: views, expression and mouth chart boards with onion skin,
  vector brushes with texture, gap-closing fill, paper-to-vector import, colour models.
- **Director's desk:** chat with the agent beside a storyboard strip, an animatic player and an X-sheet view (exposures,
  holds, on-twos), with a graph editor for animators who want curves. Every edit becomes a command.
- **Review room:** comment on a frame ("hands too small here"); comments become tasks the agent fixes, and a critic
  rechecks before closing them.
- **Act it out:** record a phone video or your voice; pose tracking drives the puppet and your take replaces the TTS.

### C. The agent layer
- Research and facts ledger; scripts tagged to facts; reference studies measured automatically.
- Casting: pick from the library or commission a character drawing (brief → artist → Rig Canvas → rig check).
- Shot planning: blocking, camera, layouts that vary scale; action clips chosen per beat.
- Critic agents with measured QA plus "reference parity".
- Localisation: re-voice, re-time (everything hangs on word times), re-caption, swap regional facts.
- Variants: several hooks, titles and frame ones for testing; retention data feeds the next script.

### D. The asset ecosystem
- Cast library: puppets with voice profiles, personalities, pose and gesture libraries, continuity notes.
- Set templates: clinic, farm field, kitchen, classroom, soil cutaway, body cross-section, map board.
- Provenance on everything (author, licence, source); a marketplace where artists earn when their puppets are used.

### E. Outputs
Video masters and platform cuts; captions; stems; sources page; Lottie and interactive web versions (the frame
functions already run in a browser); skeletal JSON for game engines; layered image sequences for editors.

### F. Infrastructure
GPU render workers for 3D and Grease Pencil, CPU for SVG; per-shot caching by input hash; preview tiers (animatic in
seconds, draft in minutes, final at full quality); deterministic renders so any frame can be reproduced and diffed.

## Build order (impact first)
1. **Acting quality:** viseme lip-sync, IK with pins, spring secondary motion, pose presets, action clips with blending.
2. **Film as data:** shots.json, renderer router, per-shot cache, animatic tier.
3. **Characters that turn:** multi-view rigs and driven keys; bendy limbs.
4. **Human surfaces:** Rig Canvas v0.2, director's desk with X-sheet and review room.
5. **Reach:** localisation, hook variants, Lottie and interactive exports, data-bound shots.
6. **Ecosystem:** cast library with provenance, set templates, marketplace, render farm.

## North-star demo
A 60-second skit-explainer starring a character a person drew in Rig Canvas that morning, with phoneme lip-sync,
IK-pinned feet and springy hair, mixing puppet shots with one 3D x-ray shot, in two languages, every fact sourced,
passing the quality bar, produced in one day with four human approvals.
