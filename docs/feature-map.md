# Programmable cartoon studio: the full feature map

This is every feature a programmable cartoon studio needs, from character drawing to delivery and governance. It
covers what professional platforms already do, what an agent-native studio needs that they don't, new ideas, and
features that **emerge** when Doodleberry's primitives combine. Status is checked against this repo as of November 2026.

**Tags**
- **Source:** `PRO` = shipped in current professional tools (Toon Boom Harmony and Storyboard Pro, Moho, Reallusion
  Cartoon Animator, Adobe Character Animator and After Effects, Spine, Live2D, Rive, Blender Grease Pencil, OpenToonz,
  TVPaint). `NEW` = needed because the studio is programmable or agent-driven. `IDEA` = novel. `EMG` = emerges from
  combining primitives we already have (see §13).
- **Status:** ✅ have · 🟡 partial · ⬜ missing.
- **Priority:** P0 next, P1 soon, P2 later.

Pro-tool attributions come from general product knowledge, not a fresh audit. Check them before quoting externally.

---

## 1. Character design and drawing
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Vector drawing: pressure ink, filled shapes, palette slots | PRO | ✅ | – | Rig Canvas |
| Brush engine: stabiliser, tapered and textured brushes, gap-closing fill, eraser, lasso, transform | PRO | 🟡 | P1 | basic smoothing only; perfect-freehand (MIT) for strokes |
| Raster parts (PNG/painted) with pivots | PRO (Moho, Spine, Live2D) | ⬜ | P1 | unlocks painterly styles |
| Import layered PSD/Krita/SVG/AI, auto-splitting parts by layer name | PRO (Character Animator, Moho) | ⬜ | P0 | artists keep their own tools |
| Paper sketch → vector (scan or photo, then trace) | NEW | ⬜ | P1 | VTracer (MIT); potrace as a separate process |
| Templates with ghost guides (humanoid, quadruped, bird, blob, object-with-face) | PRO/NEW | 🟡 | P1 | humanoid only |
| Model sheet and turnaround board (front, 3/4, side, back) with height lines | PRO | 🟡 | P1 | views exist; no board UI |
| Expression sheet and mouth-chart boards with onion skin | PRO | 🟡 | P1 | slots exist; no side-by-side board |
| Costumes and outfits as swap sets; accessories | PRO | ⬜ | P1 | swap sets are generic, so this is cheap |
| Colour models and palette variants (night, sick, cold) | PRO | 🟡 | P2 | runtime recolour exists |
| Rig linter: missing slots, raw colours, gaps at joints, pivot sanity | NEW | 🟡 | P0 | add joint-gap and pivot-inside-part checks |
| Auto-rig: detect parts and pivots from a whole drawing | IDEA (Meta Animated Drawings) | ⬜ | P2 | segmentation plus pose estimation on the drawing |
| Character DNA: shape language, proportions and line weight as parameters for generating relatives (siblings, crowds) | IDEA | ⬜ | P2 | keeps a family look without redrawing |
| Character bible: personality, voice, gesture tendencies, continuity notes | NEW | 🟡 | P1 | cast registry has personality and voice |

## 2. Rigging
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Bone hierarchy, FK | PRO | ✅ | – | |
| Two-bone IK with targets and foot pins | PRO | ✅ | – | `acting.js` |
| N-bone IK chains (FABRIK): tails, tentacles, spines | PRO (Spine, Moho) | ⬜ | P1 | in-house, small |
| IK/FK switching and blending | PRO | ⬜ | P2 | |
| Joint limits | PRO | ⬜ | P1 | in the template |
| Constraints: look-at, copy rotation, follow path, parent switching (prop moves hand to hand) | PRO | 🟡 | P0 | `pointOf` finds hands; no constraint list yet |
| Swap sets (mouths, eyes, hands) | PRO | ✅ | – | |
| Drawing substitution driven by angle or control | PRO (Harmony) | ⬜ | P1 | e.g. hand shape switches as the arm rotates |
| Smart bones / driven keys / corrective drawings | PRO (Moho) | ⬜ | P0 | one control drives offsets, swaps, z-order |
| Multi-view rigs with switching | PRO | ✅ | – | v0.2 views plus a squash smear |
| Inbetween views by vector morph (front → 3/4 → side) | IDEA | ⬜ | P2 | path correspondence across views |
| 2.5D parametric head turn | PRO (Live2D, Cartoon Animator 360 head) | ⬜ | P1 | per-part offsets and scale driven by a turn parameter |
| Mesh and warp deformation, bendy limbs, weights | PRO (Spine, Moho, OpenToonz Plastic, Harmony deformers) | ⬜ | P0 | biggest gap in visual quality |
| Squash and stretch on parts | PRO | 🟡 | P1 | whole-body squash only |
| Springs and dynamics (hair, ears, tails) | PRO (Character Animator dangles, Cartoon Animator spring bones) | ✅ | – | deterministic re-simulation |
| Spring chains, cloth strips | PRO | ⬜ | P2 | |
| Z-order switching (arm in front of or behind the body) | PRO | 🟡 | P1 | per view only; needs per-pose |
| Rig retargeting across characters on one template | PRO | ✅ | – | clips are template-level |

## 3. Animation and acting
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Keyframes with easing | PRO | ✅ | – | |
| Graph (curve) editor | PRO | ⬜ | P1 | for animators who want curves |
| Dope sheet / X-sheet: exposures, holds, animating on twos or threes | PRO | ⬜ | P1 | a stepped look can be a style switch |
| Nonlinear clip stack with fades and additive layers | PRO | ✅ | – | |
| Action clip library | PRO | 🟡 | P0 | 10 clips; need run, jump, sit, stand-up, fall, climb, carry, push, idle variants, listen, laugh, cry, celebrate |
| Pose library and blending | PRO | ✅ | – | presets plus per-character poses |
| Walk along a path with foot planting | PRO | 🟡 | P1 | straight travel only |
| Procedural life: breathing, blinks, gaze saccades, weight shift, fidgets | PRO/NEW | ✅ | – | fidgets missing |
| Lip-sync from audio phonemes | PRO | ✅ | – | |
| Lip-sync cross-check without a transcript (Rhubarb) | PRO | ⬜ | P1 | MIT |
| Emotion-aware mouths (talking while smiling or worried) | IDEA | ⬜ | P1 | mouth chart per emotion |
| Gestures from speech prosody: beats on stressed syllables, tilts on questions, nods from listeners | NEW | ⬜ | P0 | in-house; open co-speech models are NC |
| Natural-language acting direction ("Pip is nervous, glances at the door") → timeline | NEW | ⬜ | P0 | agent compiles to clips, poses and gaze |
| Webcam face performance → puppet | PRO (Character Animator) | ⬜ | P1 | MediaPipe (Apache-2.0) |
| "Act it out": phone video → body pose → clips and IK targets | NEW | ⬜ | P1 | MediaPipe or rtmlib |
| 3D mocap retargeted to 2D | NEW | 🟡 | P2 | CMU retarget exists for 3D only |
| Animation principles as filters: anticipation, overshoot, follow-through, arcs | IDEA | ⬜ | P1 | post-process on baked curves |
| Smears and motion lines on fast moves | PRO | 🟡 | P1 | turn smear only |
| Multi-character interaction: handshake, hug, hand-off, eye contact | NEW | ⬜ | P1 | IK targets on each other's parts |
| Listener behaviour: whoever isn't speaking reacts | NEW | ⬜ | P0 | gaze to speaker plus nods |
| Crowds with variation | PRO | ⬜ | P2 | |
| Prop physics: drops, bounces, rolls | PRO | ⬜ | P2 | deterministic, simulated at bake time |
| Frame-by-frame drawn effects layer (hand-drawn splashes, smoke) | PRO (TVPaint, GP) | ⬜ | P2 | |

## 4. Staging, camera, effects
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Set templates | NEW | 🟡 | P0 | 4 sets; need kitchen, classroom, farm, street, office, body cross-section, map board |
| Layered sets with parallax and multiplane depth | PRO (Harmony) | ⬜ | P1 | |
| Camera pan and zoom | PRO | ✅ | – | folded into the bake for every renderer |
| Camera grammar: shake, follow a character, auto-framing with caption headroom, punch-in on emphasis | NEW | ⬜ | P0 | |
| Shot-size templates (wide, medium, close-up, over-the-shoulder) | PRO (Storyboard Pro) | ⬜ | P1 | |
| Auto coverage from the script (who speaks → framing → cut) | IDEA | ⬜ | P1 | |
| Continuity checks: 180° rule, screen direction, eyeline | IDEA | ⬜ | P2 | |
| Toon lighting: rim, cast shadows, colour script, time-of-day grade | PRO | 🟡 | P1 | legacy engine has cel-shading primitives |
| FX: particles (rain, dust, sparks), impact frames, speed lines | PRO | 🟡 | P1 | legacy engine has some |
| Node compositor: masks, mattes, blend modes, blur, glow | PRO (Harmony, AE) | 🟡 | P2 | ffmpeg overlay only |
| Transitions: whoosh cut, match cut, wipes | PRO | 🟡 | P1 | whoosh sound on cuts |
| Infographics layer: charts, maps, labels, callouts, cutaways bound to facts | NEW | 🟡 | P0 | legacy films do this by hand |
| Kinetic typography | PRO (AE) | 🟡 | P1 | word-highlight captions |
| 2.5D: 2D layers placed in 3D space with a real camera | PRO | 🟡 | P2 | three.js exists |

## 5. Story and pre-production
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Brief → facts → script → shot list | NEW | ✅ | – | director prompt plus `shots.json` |
| Facts ledger with sources; every narrated line traced | NEW | ✅ | – | QA enforces it |
| Storyboard strip auto-generated from `shots.json` | PRO (Storyboard Pro) | ⬜ | P0 | one still per shot, with notes |
| Animatic with temp voice | PRO | ✅ | – | svg draft render |
| Hook and title variants | NEW | ✅ | – | `variants.hooks` |
| Beat sheet and retention-curve planning | NEW | ⬜ | P1 | |
| Series bible and episode continuity (outfits, props, running gags) | NEW | ⬜ | P2 | |
| JSON Schema for `shots.json` and `script.json` | NEW | ⬜ | P0 | agents validate before rendering |

## 6. Audio
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Multi-speaker TTS with voice effects | NEW | ✅ | – | Piper plus WORLD |
| Voice licence gate | NEW | ✅ | – | |
| More clean voices, including emotion and other languages | NEW | 🟡 | P0 | Kokoro-82M (Apache-2.0) |
| Prosody direction (whisper, shout, excited, sad) | NEW | ⬜ | P1 | |
| Human voice-over import with alignment | PRO | 🟡 | P0 | aligner works; needs a command |
| Consented voice cloning with consent records | IDEA | ⬜ | P2 | licence and consent gate first |
| Procedural score, stingers, ducking | NEW | ✅ | – | |
| SFX library with licence manifest | NEW | 🟡 | P1 | synth only; Kenney CC0 |
| Loudness and intelligibility QA | NEW | ✅ | – | |
| Footsteps, cloth and impact foley from the animation | EMG | ⬜ | P0 | see §13 |
| Spatial mix: pan by screen position | EMG | ⬜ | P1 | see §13 |

## 7. Rendering and output
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Renderer routing per shot (SVG, Synfig, Grease Pencil, Lottie) | NEW | ✅ | – | |
| Composited character layers over the animated set | NEW | ✅ | – | |
| Video, Lottie, web player, Synfig and Grease Pencil project exports | PRO/NEW | ✅ | – | |
| WebM and ProRes with alpha, GIF/APNG, stickers | PRO | ⬜ | P1 | |
| OpenTimelineIO / FCPXML / EDL hand-off to editors | PRO | ⬜ | P1 | OTIO (Apache-2.0) |
| Game runtime export: sprite sheets, Spine-like JSON for Godot or Unity | PRO (Spine) | ⬜ | P2 | |
| Aspect-ratio re-staging (9:16 ↔ 16:9 ↔ 1:1 by re-blocking, not cropping) | IDEA | ⬜ | P1 | the film is data, so re-block it |
| Parallel render workers, frame reuse, static-layer cache | NEW | 🟡 | P0 | 4 workers in the legacy engine; benchmark says 4–8× available |
| Incremental re-render (only changed shots) | NEW | 🟡 | P0 | `only=`; next: content hashes per shot |
| Style passes: paper texture, grain, line boil, watercolour | PRO | 🟡 | P2 | toon mode in 3D |
| Vector resolution independence (4K for free) | NEW | ✅ | – | |

## 8. Localisation, accessibility, reach
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Re-voice and re-time per language | NEW | ✅ | – | `film.localize` |
| Translated captions and on-screen text | NEW | 🟡 | P1 | captions yes; set text no |
| Right-to-left and complex scripts in captions | NEW | ⬜ | P1 | libass handles shaping; needs fonts |
| Cultural adaptation: swap sets, props, names per market | IDEA | ⬜ | P2 | |
| Sidecar SRT/VTT plus burned-in captions | PRO | 🟡 | P0 | burned in only |
| Audio-description track generated from the shot list | EMG | ⬜ | P1 | see §13 |
| Flash and photosensitivity check (WCAG 2.3) | NEW | ⬜ | P1 | add to QA |
| Colour-blind-safe palette check | NEW | ⬜ | P2 | |
| Reduced-motion variant | IDEA | ⬜ | P2 | |
| Sign-language inset presenter | IDEA | ⬜ | P2 | needs Deaf community partners |
| Platform packs: safe zones, thumbnails, titles, descriptions | NEW | 🟡 | P1 | caption safe zone only |
| Interactive web films: branching, quizzes, click-to-explore | EMG | ⬜ | P2 | live web player exists |

## 9. QA and review
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Measured QA bar and contact sheets | NEW | ✅ | – | |
| Fact tracing | NEW | ✅ | – | |
| Visual lint: tangents, limbs off-screen, caption collisions, IK overextension, intersecting props, character overlap | NEW | ⬜ | P0 | baked data makes this geometry, not vision |
| Golden-frame regression tests | NEW | ⬜ | P0 | determinism makes this exact |
| Frame comments that become data edits | IDEA | ⬜ | P0 | "raise the arm earlier" → agent edits the timeline → critic re-checks |
| Visual diff between film versions | NEW | ⬜ | P1 | |
| Health and claims risk review | NEW | ⬜ | P1 | flags claims a reviewer must sign |
| Retention analytics fed back into hooks and pacing | EMG | ⬜ | P2 | |

## 10. Collaboration, ecosystem, governance
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Cast registry with provenance log and content hashes | NEW | ✅ | – | |
| Auto credits | NEW | ✅ | – | |
| Asset licence manifest for sets, SFX, fonts, props | NEW | 🟡 | P1 | voices and puppets only |
| Marketplace: puppets, clips, sets, with revenue share by usage | IDEA | ⬜ | P2 | usage is in `shots.json`, so payouts can be exact |
| Content credentials (C2PA) and AI-disclosure labels | NEW | ⬜ | P1 | |
| Likeness and consent rules for characters and voices | NEW | ⬜ | P1 | |
| Versioning, branching, review in git | NEW | ✅ | – | films are text |
| Roles and permissions (artist, director, reviewer) | PRO | ⬜ | P2 | |

## 11. Agent and developer platform
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| One command registry → CLI, HTTP, MCP, Studio | NEW | ✅ | – | |
| Async jobs | NEW | ✅ | – | |
| Progress events and webhooks | NEW | ⬜ | P1 | |
| Cost and time estimate before rendering | NEW | ⬜ | P1 | frames × renderer rate |
| Specialist agents: director, animator, editor, critic, fact-checker | IDEA | ⬜ | P1 | each with its own command subset |
| Natural-language editing ("make Pip turn when she says Blender") | NEW | 🟡 | P0 | line-relative times make it a one-field edit |
| Python and JS SDKs, recipes, templates | NEW | ⬜ | P2 | |
| Multi-tenant sandboxing and quotas | NEW | ⬜ | P2 | |

## 12. Human interfaces
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Rig Canvas: slots, views, pivots, live previews from the clip library | PRO/NEW | ✅ | – | v0.2 |
| Posing on the canvas by dragging hands and feet (IK) | PRO | ⬜ | P0 | turns posing into direct manipulation |
| Clip and pose authoring by recording a drag or a webcam take | IDEA | ⬜ | P1 | |
| Studio: films, shots, renderer routing, render, log | NEW | ✅ | – | basic |
| Timeline editor: shots, clips, dialogue lanes, scrub with live preview | PRO | ⬜ | P0 | the web player already renders any frame live |
| Director's desk: chat beside a storyboard strip and animatic | IDEA | ⬜ | P1 | |
| Review room on mobile: approve, comment on a frame | NEW | ⬜ | P1 | |
| Tablet and pencil support | PRO | 🟡 | P1 | pointer pressure works |

---

## 13. Emergence: what the combination makes possible
These come from stacking primitives we already have. Each one is cheap because the data already exists.

| # | Because we have… | …this emerges | Status |
|---|---|---|---|
| E1 | Frame-pure rendering + films as text | **Films you can diff, bisect and test.** Golden frames catch regressions; any old version re-renders exactly; a frame is a reproducible record. | ⬜ P0 |
| E2 | Line-relative times + TTS + alignment | **Edit the script and the film follows.** Change a sentence and acting, cuts, captions and cues re-flow. Localisation is a special case. | 🟡 |
| E3 | Foot pins + contact frames + clips | **Automatic foley.** Footsteps on every plant, cloth swishes on fast arm moves, thuds on landings. | ⬜ P0 |
| E4 | Character screen positions + the mix | **Spatial audio.** Voices and effects pan with the character. | ⬜ P1 |
| E5 | `shots.json` semantics (who, where, doing what) | **Audio description, alt text, chapter markers, transcripts and thumbnails, all auto-generated.** We know what is on screen without vision models. | ⬜ P1 |
| E6 | Puppets + views + IK + poses | **One character, every medium:** video, comic panels, storybook pages, stickers, thumbnails, print, merch. Pose a still, render a page. | ⬜ P1 |
| E7 | Baked acting + Lottie + clip library | **The cast in apps and games:** animated stickers, in-app mascots, game sprites, all from the same rig. | 🟡 |
| E8 | Live web player + data | **Personalised films rendered in the viewer's browser:** their name, language and region, at zero server cost. | ⬜ P2 |
| E9 | Real-time puppet + webcam tracking | **Live 2D avatars of the cast** for streams and classrooms, VTuber-style. | ⬜ P2 |
| E10 | QA bar + agent + data edits | **Self-healing renders.** The agent reads a QA failure (a still stretch, loudness, a caption collision), edits the timeline and re-renders until it passes. This session did it by hand for the idle clip. | 🟡 |
| E11 | Hook variants + analytics | **Self-optimising openings.** Retention data picks hooks and pacing for the next film. | ⬜ P2 |
| E12 | Facts ledger + script tags | **Living films.** When a source updates a number, the affected shots re-render; an auto "sources" end card cites them. | ⬜ P1 |
| E13 | Cast personality + gesture planner | **Characters that act in character** across films and agents: a shy character never points broadly. | ⬜ P1 |
| E14 | Provenance hashes + determinism | **Verifiable content credentials.** Anyone can re-render and check a frame matches its signed recipe. | ⬜ P2 |
| E15 | Usage recorded in `shots.json` | **Exact artist royalties.** Pay per second of screen time for each puppet, clip or set. | ⬜ P2 |
| E16 | Series data across films | **Continuity memory.** The bible knows outfits, props and running gags, and the critic flags breaks. | ⬜ P2 |
| E17 | Same acting → many renderers | **Style A/B tests.** Render one performance flat, Synfig-smooth or Grease Pencil-sketchy, then pick per audience or platform. | ✅ |
| E18 | Data films + aspect ratios | **Re-blocked formats.** A 16:9 version re-stages characters and camera rather than cropping a 9:16 film. | ⬜ P1 |

## 14. What not to build
- Photoreal or generative-video characters: they break consistency, editability and the licence trail. Use
  generative models only for licence-cleared backgrounds and props, if at all.
- A full raster frame-by-frame paint suite (TVPaint territory). Import from Krita instead.
- Proprietary runtimes we can't redistribute: no Spine runtime embedding and no Remotion. See `oss-research.md`.

## 15. Next 12 (P0, in order)
1. Mesh and warp deformation with bendy limbs (biggest visual-quality gap)
2. Smart bones / driven keys, and constraints (prop hand-offs, look-at)
3. Gesture planner from prosody, plus listener behaviour
4. Natural-language acting direction compiled to timelines
5. Clip library to about 30 clips; set library to about 10 sets
6. Camera grammar: follow, auto-framing, punch-ins
7. Visual lint and golden-frame regression tests (E1)
8. Automatic foley from contacts (E3)
9. Storyboard strip and timeline editor in Studio, plus IK posing in Rig Canvas
10. Layered PSD/SVG import into puppets
11. Kokoro voices, a voice-over import command and sidecar captions
12. Render speed: parallel workers, frame reuse, per-shot content hashes

## 16. Build-with map (from `docs/oss-research.md`)
Which open-source pieces implement which features. Licences were verified by the research pass; see that file for the
[V]/[R]/[U] tags.

| Feature (section) | Build with | Licence | Status |
|---|---|---|---|
| Clean voices (§6) | Piper public-domain voices: kristin, norman, bryce, cori, john, ljspeech | PD | ✅ gate plus 4 installed |
| More voices and languages, Spanish quality (§6, §8) | Kokoro-82M (or kokoro-onnx) | Apache-2.0 (espeak fallback GPL, as a subprocess) | ⬜ P0 |
| Expressive lines, consented cloning (§6) | Chatterbox (watermarked) | MIT | ⬜ P2 |
| Phone-accurate lip-sync (§3) | wav2vec2-espeak CTC + torchaudio `forced_align` (same phone set as our visemes); or MFA | Apache-2.0 / MIT, model CC BY 4.0 | ⬜ P1 |
| Lip-sync QA cross-check and transcript-free fallback (§3, §9) | Rhubarb Lip Sync | MIT | ⬜ P1 |
| Steadier word timing on known scripts (§6) | stable-ts `align()` | MIT | ⬜ P1 |
| N-bone IK (§2) | FABRIK ported in-house (references: fullik, THREE.IK) | MIT refs | ⬜ P1 |
| Gesture planner (§3) | In-house: pyworld F0 peaks + espeak stress + LLM semantic tags → clip scheduler | none | ⬜ P0 |
| Seeded idle noise and handheld camera (§3, §4) | opensimplex | MIT | ⬜ P1 |
| Act it out / webcam performance (§3, §12) | MediaPipe Pose/Holistic/Face; rtmlib RTMPose for accuracy | Apache-2.0 | ⬜ P1 |
| Auto-rig from a drawing (§1) | Animated Drawings ideas + scikit-image skeletonize/skan | MIT / BSD-3 | ⬜ P2 |
| Bendy limbs in Synfig output (§2) | Synfig Skeleton Deformation + Switch layers in the `.sif` exporter | GPL (CLI subprocess) | ⬜ P1 |
| Rig Canvas strokes (§1) | perfect-freehand; simplify-js | MIT / BSD-2 | ⬜ P1 |
| Scan/sketch import (§1) | VTracer (colour); potrace (mono, subprocess); ImageTracer.js in-browser | MIT / GPL / Unlicense | ⬜ P1 |
| Part cleanup on import (§1) | picosvg, svgo (safe preset keeping IDs), vpype | Apache-2.0 / MIT / MIT | ⬜ P1 |
| Cel shadows, rims, outline offsets (§4) | Clipper2 (pyclipr), skia-pathops (keeps curves) | BSL-1.0 / BSD-3 | ⬜ P1 |
| Render speed (§7) | Worker pool + frame-hash dedupe + static-layer cache + PyAV piping + `-tune animation` | in-house / BSD-3 | ⬜ P0 |
| Faster rasteriser (§7) | Benchmark resvg and ThorVG behind a pixel-diff gate (harness saved) | Apache/MIT, MIT | ⬜ P1 |
| Lottie export QA (§7, §9) | ThorVG + lottie-web golden images; schema validation from lottie-docs | MIT / CC BY 4.0 | 🟡 lottie-web renders work |
| Lottie packaging with palette themes (§7) | dotLottie | MIT | ⬜ P2 |
| Post effects: grain, LUT, vignette, xfade, motion blur (§4, §7) | ffmpeg filter graphs; accumulation blur in-house; SVT-AV1 film-grain | in stack | ⬜ P1 |
| 3D pass compositing (§4) | oiiotool; three.js toon stack | Apache-2.0 / MIT | ⬜ P2 |
| Editor hand-off (§7) | OpenTimelineIO (+ EDL/FCPXML adapters); `melt` for round trips | Apache-2.0 / LGPL | ⬜ P1 |
| Cast variety (§1, §10) | Open Peeps, Humaaans → puppets | CC0 | ⬜ P0 |
| Props, icons, SFX (§4, §6) | Kenney, Tabler, Lucide, Phosphor, Fluent Emoji | CC0 / MIT / ISC / MIT | ⬜ P1 |
| Medical and map shots (§4) | Servier Medical Art; Natural Earth + d3-geo | CC BY 4.0 / PD | ⬜ P1 |
| Asset licence manifest and credits (§10) | In-house manifest → `film.credits` | none | 🟡 voices and puppets only |
| Scene DSL reference (§11) | Motion Canvas / Revideo ideas (reference only) | MIT | — |

Avoid: OpenPose, Ultralytics, python-lottie in the service, aeneas, XTTS-v2 and F5-TTS weights, MMS aligner weights,
EMAGE/BEAT2, audio2photoreal, MakeItTalk, Sapiens, LAFAN1 data, embedding Spine or Remotion, OpenMoji (SA), BBC
sound effects (NC), Sonniss files in public repos or training sets, Z-Anatomy NC parts.
