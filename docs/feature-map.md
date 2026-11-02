# Programmable cartoon studio: the full feature map

This is every feature a programmable cartoon studio needs (updated with abilities learned from the Sheep & Pig doodle toolkit and the bioinformatics.lk film playbook), from character drawing to delivery and governance. It
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
| Brush engine: stabiliser, tapered and textured brushes, gap-closing fill, eraser, lasso, transform | PRO | 🟡 | P1 | pressure strokes, simplify, gap-closing fill in the Rig Canvas (1.4); stabiliser, textured brushes, lasso, transform: WP-18, WP-34 |
| Raster parts (PNG/painted) with pivots | PRO (Moho, Spine, Live2D) | ✅ | – | puppet v0.3 raster parts (`puppet.from_ink`, `doodle.snap`); SVG renderer only, others: WP-14 |
| Import layered PSD/Krita/SVG/AI, auto-splitting parts by layer name | PRO (Character Animator, Moho) | 🟡 | P0 | `puppet.import` reads layered SVG, PSD and ORA (1.3); Krita .kra and AI: WP-18 |
| Paper sketch → vector (scan or photo, then trace) | NEW | ⬜ | P1 | vector tracing (VTracer, potrace): WP-18 |
| Templates with ghost guides (humanoid, quadruped, bird, blob, object-with-face) | PRO/NEW | 🟡 | P1 | humanoid and doodle templates; ghost guides for drawing requests (3.6); quadruped, bird, object: WP-16 |
| Model sheet and turnaround board (front, 3/4, side, back) with height lines | PRO | 🟡 | P1 | `puppet.sheet` model sheets (1.4); turnaround board with height lines: WP-18 |
| Expression sheet and mouth-chart boards with onion skin | PRO | 🟡 | P1 | swap slots exist; side-by-side boards with onion skin: WP-18 |
| Costumes and outfits as swap sets; accessories | PRO | ⬜ | P1 | outfits as swap sets: WP-16 |
| Colour models and palette variants (night, sick, cold) | PRO | 🟡 | P2 | runtime recolour exists; palette variants per scene: WP-16 |
| Rig linter: missing slots, raw colours, gaps at joints, pivot sanity | NEW | ✅ | – | `puppet.lint` and `puppet.coach` (joint gaps under bending, pivots, proportions) (1.10) |
| Auto-rig: detect parts and pivots from a whole drawing | IDEA (Meta Animated Drawings) | 🟡 | P2 | doodles: `doodle.snap` finds head, body, eyes, mouth, arms, tail and pivots (3.6); other drawings: WP-18 |
| Character DNA: shape language, proportions and line weight as parameters for generating relatives (siblings, crowds) | IDEA | 🟡 | P2 | `cast.generate` builds parametric originals (1.5); a family look as parameters: WP-16 |
| Character bible: personality, voice, gesture tendencies, continuity notes | NEW | 🟡 | P1 | cast registry has personality and voice; full bible: WP-16 |
| **Ink-fidelity import:** a photo or scan of any medium (pen, pencil, marker, crayon, watercolour) becomes a clean line that keeps the artist's real texture. Lighting is flattened by dividing by a blurred copy, ink is thresholded to alpha, and specks are removed | NEW | ✅ | – | `puppet.from_ink` (1.8) and `doodle.snap` (3.6) |
| Multi-character page detection: find each character on a page and ignore sums, spirals, hands, pens and shadows | IDEA | ⬜ | P2 | several characters on one page: WP-18 |
| Mask-based part cutting over one ink layer, with overlap seams that hide cuts (for example at the neck) and suggested cuts at narrow joints | NEW | ✅ | – | dbe/ink.py cuts one ink layer by polygons with overlap seams (1.8) |
| Pivot and cut suggestions: an overlay proposes cut lines and pivots; the artist confirms with a tap | IDEA | ✅ | – | `doodle.snap` suggests cuts and pivots; /doodle shows them to confirm and drag (3.6); polygon editing: WP-18 |
| **Drawing coach:** checks a drawing before import and explains how to draw for animation (longer limbs, small gaps at joints, separate eyes, a consistent scale, one character per area) | IDEA | ✅ | – | `puppet.coach` (1.10) |
| Owner-IP characters: register characters the creator owns (not openly licensed), with rights metadata | NEW | ✅ | – | `cast.add` rights open, owner and client (0.9); `doodle.keep` registers owner rights (3.6) |

## 2. Rigging
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Bone hierarchy, FK | PRO | ✅ | – | |
| Two-bone IK with targets and foot pins | PRO | ✅ | – | `acting.js` |
| N-bone IK chains (FABRIK): tails, tentacles, spines | PRO (Spine, Moho) | ✅ | – | FABRIK chains with a living wave, puppet v0.6 (2.5) |
| IK/FK switching and blending | PRO | ⬜ | P2 | IK/FK switching and blending: WP-11 |
| Joint limits | PRO | ✅ | – | puppet v0.6 joint limits (2.5) |
| Constraints: look-at, copy rotation, follow path, parent switching (prop moves hand to hand) | PRO | 🟡 | P0 | look-at and parent switching with arcs (1.2); copy rotation and follow path: WP-11 |
| Swap sets (mouths, eyes, hands) | PRO | ✅ | – | |
| Drawing substitution driven by angle or control | PRO (Harmony) | 🟡 | P1 | controls drive swaps (1.2); substitution by a part's angle: WP-11 |
| Smart bones / driven keys / corrective drawings | PRO (Moho) | ✅ | – | `controls` with driven keys for angles, shifts, swaps and z (1.2) |
| Multi-view rigs with switching | PRO | ✅ | – | v0.2 views plus a squash smear |
| Inbetween views by vector morph (front → 3/4 → side) | IDEA | ⬜ | P2 | in-between views by morph: WP-43 |
| 2.5D parametric head turn | PRO (Live2D, Cartoon Animator 360 head) | ✅ | – | the `turn` control drives the head's three-quarter offsets (1.2) |
| Mesh and warp deformation, bendy limbs, weights | PRO (Spine, Moho, OpenToonz Plastic, Harmony deformers) | ✅ | – | bendy limbs (1.1) and mesh strokes with skinning (puppet v0.5); other renderers: WP-14 |
| Squash and stretch on parts | PRO | 🟡 | P1 | whole-body squash; per-part squash: WP-11 |
| Springs and dynamics (hair, ears, tails) | PRO (Character Animator dangles, Cartoon Animator spring bones) | ✅ | – | deterministic re-simulation |
| Spring chains, cloth strips | PRO | 🟡 | P2 | springs (v0.2) and FABRIK chains (v0.6); cloth strips: WP-42 |
| Z-order switching (arm in front of or behind the body) | PRO | ✅ | – | controls drive z (1.2) and clips carry `swaps.z` (3.5); Lottie and Synfig keep static order: WP-14 |
| Rig retargeting across characters on one template | PRO | ✅ | – | clips are template-level |
| Line-weight-preserving squash for blinks and squints: area-averaged resampling with re-inking, so a closed eye stays one solid line; dot eyes flatten to dashes | NEW | ✅ | – | area-averaged squash with re-inking in dbe/ink.py (1.8) |
| Rig ability inventory: each character declares what it can do without new drawings (hop, blink, tilt, wave, wag) and what needs a drawing | IDEA | ✅ | – | `puppet.abilities` (2.12); feeds rig-aware writing (§5) and drawing requests (E20, 3.6) |
| Doodle template: minimal rigs (head, body, arms, tail) for simple characters, with clips that fit them | NEW | ✅ | – | doodle template and clip library (1.11) |

## 3. Animation and acting
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Keyframes with easing | PRO | ✅ | – | |
| Graph (curve) editor | PRO | ⬜ | P1 | curve editor: WP-19 |
| Dope sheet / X-sheet: exposures, holds, animating on twos or threes | PRO | 🟡 | P1 | stepped timing per character or shot (1.9); exposure-sheet UI: WP-35 |
| Nonlinear clip stack with fades and additive layers | PRO | ✅ | – | |
| Action clip library | PRO | ✅ | – | 33 library clips (2.5) plus each character's own clips (3.3, 3.5) |
| Pose library and blending | PRO | ✅ | – | presets plus per-character poses |
| Walk along a path with foot planting | PRO | 🟡 | P1 | straight travel with foot pins; paths: WP-11 |
| Procedural life: breathing, blinks, gaze saccades, weight shift, fidgets | PRO/NEW | ✅ | – | fidgets missing |
| Lip-sync from audio phonemes | PRO | ✅ | – | |
| Lip-sync cross-check without a transcript (Rhubarb) | PRO | ✅ | – | `lipsync.check` in-house; Rhubarb compared when installed (2.2) |
| Emotion-aware mouths (talking while smiling or worried) | IDEA | ✅ | – | emotion-aware mouth charts (2.5) |
| Gestures from speech prosody: beats on stressed syllables, tilts on questions, nods from listeners | NEW | ✅ | – | `acting.plan` (2.3) |
| Natural-language acting direction ("Pip is nervous, glances at the door") → timeline | NEW | ✅ | – | `acting.direct` (2.4) |
| Webcam face performance → puppet | PRO (Character Animator) | 🟡 | P1 | recorded takes become eye, brow, gaze and mouth keys (`actout.clip`, 3.5); live tracking: WP-12 |
| "Act it out": phone video → body pose → clips and IK targets | NEW | ✅ | – | `actout.clip` and Studio /actout (plan 3.5), MediaPipe; rtmlib open |
| 3D mocap retargeted to 2D | NEW | 🟡 | P2 | video to 2D clips with `actout.clip` (3.5); BVH and CMU mocap to 2D: WP-12 |
| Animation principles as filters: anticipation, overshoot, follow-through, arcs | IDEA | ✅ | – | anticipation and overshoot filter (2.5), springs for follow-through; motion arcs: WP-09 |
| Smears and motion lines on fast moves | PRO | 🟡 | P1 | speed lines, dust, impact stars from the motion (2.20); smears and arcs: WP-09 |
| Multi-character interaction: handshake, hug, hand-off, eye contact | NEW | ⬜ | P1 | handshake, hug, hand-off, eye contact: WP-11 |
| Listener behaviour: whoever isn't speaking reacts | NEW | ✅ | – | listener gaze, nods and blinks in `acting.plan` (2.3) |
| Crowds with variation | PRO | ⬜ | P2 | crowds: WP-42 |
| Prop physics: drops, bounces, rolls | PRO | ✅ | – | throws, drops, bounces, rolls solved at bake time (2.19); multi-body: WP-09 |
| Frame-by-frame drawn effects layer (hand-drawn splashes, smoke) | PRO (TVPaint, GP) | ⬜ | P2 | drawn effects as drawn levels: WP-35 |
| **Comedy timing toolkit:** scripted blinks on cue (one per dot of "..."), holds, double-takes, the long stare, the button move after the last line, rule-of-three escalation | NEW | ✅ | – | `acting.direct` gags and scripted blinks (2.11) |
| Gag library: reusable beat patterns, e.g. stare plus slow push-in, shout plus camera shake, silent "..." bubble with blinks, tiny hop as a button | IDEA | ✅ | – | double take, long stare, slow burn, deadpan, button, rule of three (2.11); camera beats: WP-10 |
| Hand-made timing per character or shot: animate on 12s, 8s or 6s while the film runs at 30 | PRO | ✅ | – | stepped timing on 12s, 8s or 6s (1.9) |
| Cheap expressive moves for minimal rigs: hops with squash, startle jumps, tail wags faster when excited, lean-ins | NEW | ✅ | – | doodle clips: hop, wave, tilt, wag, lean, shake (1.11) |

## 4. Staging, camera, effects
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Set templates | NEW | ✅ | – | 16 sets (1.6); map board and anatomy plates: WP-16 |
| Layered sets with parallax and multiplane depth | PRO (Harmony) | ⬜ | P1 | multiplane depth: WP-36 |
| Camera pan and zoom | PRO | ✅ | – | folded into the bake for every renderer |
| Camera grammar: shake, follow a character, auto-framing with caption headroom, punch-in on emphasis | NEW | ✅ | – | `camera_auto` (2.6) |
| Shot-size templates (wide, medium, close-up, over-the-shoulder) | PRO (Storyboard Pro) | 🟡 | P1 | `camera_auto` medium and wide shots (2.6); named sizes and over-the-shoulder: WP-19 |
| Auto coverage from the script (who speaks → framing → cut) | IDEA | ✅ | – | `camera_auto`: speaker medium shots, wide shots between (2.6) |
| Continuity checks: 180° rule, screen direction, eyeline | IDEA | ⬜ | P2 | 180-degree rule, screen direction, eyeline in lint: WP-19 |
| Toon lighting: rim, cast shadows, colour script, time-of-day grade | PRO | 🟡 | P1 | `style.toon` cel shadows and rims in SVG (1.7); other renderers WP-14; colour script and grades WP-37 |
| FX: particles (rain, dust, sparks), impact frames, speed lines | PRO | 🟡 | P1 | motion effects (2.20) and cartoon physics (2.19); rain, sparks, particles: WP-42 |
| Node compositor: masks, mattes, blend modes, blur, glow | PRO (Harmony, AE) | 🟡 | P2 | ffmpeg overlays only; node compositor: WP-36 |
| Transitions: whoosh cut, match cut, wipes | PRO | 🟡 | P1 | whoosh on cuts; match cuts, wipes, dissolves: WP-15 |
| Infographics layer: charts, maps, labels, callouts, cutaways bound to facts | NEW | ✅ | – | explainer kits (1.13, 1.15) and data-bound charts (2.17); maps: WP-16 |
| Kinetic typography | PRO (AE) | 🟡 | P1 | word-highlight captions and pop-in titles (1.15); more: WP-15 |
| **Line boil:** cycled smooth displacement fields (about 8, at 12 fps) so line art shimmers like redrawn frames. Per-layer seeds; bubbles and props boil too | PRO (AE turbulent displace) | ✅ | – | deterministic boil (1.9) |
| Paper and medium sets: ruled notebook, sketchbook, napkin, whiteboard, chalkboard, kraft paper, with grain and page shading | NEW | ✅ | – | paper set (1.9) |
| Medium simulation for vector characters: pencil, marker or crayon line textures, so vector puppets match scanned doodles | IDEA | ⬜ | P2 | pencil, marker, crayon line styles: WP-15 |
| Ink props and signs: handwritten labels, hanging signs and arrows drawn in the same ink and boil as the characters | NEW | ✅ | – | ink signs and overlays (1.9) |
| **Speech and thought bubbles inside the art:** say, shout (spiky, shaking letters), whisper (dashed), thought clouds, narration boxes. The tail tracks the speaker; placement avoids collisions; bubbles wobble and pop in and out | NEW | 🟡 | P0 | say, shout, whisper with voice-synced reveal and placement (2.10); thought clouds, narration boxes: WP-17 |
| Typewriter text: word by word in sync with the voice, or letter by letter with punctuation pauses when silent | NEW | 🟡 | P1 | word-by-word reveal synced to the voice (2.10); letter by letter: WP-17 |
| Handwriting fonts per character, including the artist's own handwriting generated from samples | IDEA | ⬜ | P2 | handwriting fonts from samples: WP-29 |
| **Explainer scene library:** teaching cards for definitions, counters, typed consoles, data walls, heatmaps, maps, quote plates, a citation line and wordmark as overlays on soft plates | NEW | ✅ | – | card, counter, console, bars, quote, citation, wordmark, camera float (1.13, 1.15) |
| **Data-bound visuals:** every plotted number comes from an analysis script's output (`data.js`), never typed by hand; the analysis and its cached inputs live with the film | NEW | ✅ | – | `analysis/` scripts write data.json; `film.data` (2.17) |
| **Beat grid:** one BPM grid (e.g. 100 BPM at 30 fps = 18 frames per beat, 72 per bar); scene starts and key events snap to beats; picture and sound read the same `timing.json` | PRO/NEW | ✅ | – | `film.beats` (2.14) |
| Camera float: a slow constant drift on the scene layer, so no frame is ever dead | NEW | ✅ | – | camera float (1.13) |
| Cold-open rule: frame one shows the subject and the hook is readable by 1.5 s | NEW | ✅ | – | `qa.run` cold-open check (0.11) |
| 2.5D: 2D layers placed in 3D space with a real camera | PRO | 🟡 | P2 | three.js renderer; 2D multiplane: WP-36 |

## 5. Story and pre-production
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Brief → facts → script → shot list | NEW | ✅ | – | director prompt plus `shots.json` |
| Facts ledger with sources; every narrated line traced | NEW | ✅ | – | QA enforces it |
| Storyboard strip auto-generated from `shots.json` | PRO (Storyboard Pro) | ✅ | – | `film.storyboard` (3.2) |
| Animatic with temp voice | PRO | ✅ | – | svg draft render |
| Hook and title variants | NEW | ✅ | – | `variants.hooks` |
| Beat sheet and retention-curve planning | NEW | ⬜ | P1 | retention curves mapped to shots: WP-31 |
| Series bible and episode continuity (outfits, props, running gags) | NEW | ⬜ | P2 | continuity memory: WP-28 |
| **Series format:** an episode is a data template (lines, moves, beats, blinks, stares). A new episode means editing data only | NEW | ✅ | – | series template and `edit.json` (2.14, 2.15) |
| Rig-aware writing: the writer agent drafts jokes the characters' rigs can actually perform, and flags lines that need a new pose | IDEA | ✅ | – | `script.rigcheck` (2.12) |
| Daily-series planner: batch episodes, recurring gags, a posting calendar | IDEA | 🟡 | P2 | series cadence in the content planner (3.8); series production: WP-28 |
| **Content planner:** research sweeps (dated hooks, recent developments, evergreen stories, tools, original analyses, a local angle) feed an idea bank and a dated calendar | NEW | ✅ | – | `plan.*` and Studio /plan (plan 3.8): six agent sweeps, a source-checked idea bank, a dated calendar; the bioinformatics.lk plan had 61 posts and 211 ideas from six sweeps |
| Spread rules: topic diversity per week, a local-story quota, analysis cadence, series cadence, lead times ("start by"), and an empty field getting the next slot | NEW | ✅ | – | `plan.check` (plan 3.8): every rule checked independently of the scheduler |
| **Brief template:** hook (draft), angle, why now, sources (starting points only), research leads, cautions. Research may overturn the premise; the session then escalates to the planner | NEW | ✅ | – | `plan.brief` (plan 3.8) writes it from an idea; escalation to the owner on the production board (3.7) |
| **Format templates:** Myth vs Data (myth as people hold it → prediction → data → rule), Dialogue (a learner and an expert character), Anniversary, We re-ran it, Wonder story, multi-part series | NEW | ✅ | – | `film.from_template` (2.15) |
| Prediction prompts: the viewer commits to an answer (an on-screen pause or poll) before the reveal | IDEA | ✅ | – | prediction prompts with a silent count (2.15) |
| Original-analysis films: real public data, its terms and version, an access date, and a sanity check against a published figure | NEW | ✅ | – | analysis scripts with cached sources, terms and access dates (2.17) |
| Companion artefacts from one film: a guide with runnable code that reproduces the numbers, a carousel, a LinkedIn post | NEW | ⬜ | P2 | companion guides: WP-27 |
| JSON Schema for `shots.json` and `script.json` | NEW | ✅ | – | dbe/schemas, checked on write and before renders (0.3) |

## 6. Audio
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Multi-speaker TTS with voice effects | NEW | ✅ | – | Piper plus WORLD |
| Voice licence gate | NEW | ✅ | – | |
| More clean voices, including emotion and other languages | NEW | 🟡 | P0 | 54 Kokoro voices (0.5); more languages WP-25, expressive voices WP-43 |
| Prosody direction (whisper, shout, excited, sad) | NEW | ⬜ | P1 | whisper, shout, excited: WP-13 |
| Human voice-over import with alignment | PRO | 🟡 | P0 | aligner and slots exist; recorded takes into slots: WP-13 |
| Consented voice cloning with consent records | IDEA | ⬜ | P2 | own-voice cloning with consent: WP-43, WP-26 |
| Procedural score, stingers, ducking | NEW | ✅ | – | |
| SFX library with licence manifest | NEW | 🟡 | P1 | synth effects in the manifest; Kenney CC0 samples: WP-13 |
| Loudness and intelligibility QA | NEW | ✅ | – | |
| Footsteps, cloth and impact foley from the animation | EMG | ✅ | – | `foley` from contacts and fast moves (2.7) |
| Spatial mix: pan by screen position | EMG | ✅ | – | panned by screen position (2.7) |
| Cartoon SFX accents bound to moves: a boing per hop, pen-scratch ambience, a single "baa" sting | NEW | ✅ | – | boing per hop, pen scratch (2.13) |
| **Sound-off mode:** bubble-only dialogue paced by reading time, for feeds watched on mute, built from the same film as the voiced version | IDEA | ✅ | – | `film.soundoff` (2.13) |
| **Narration slots:** per-line start time and maximum length at a target pace (125–145 wpm), with short alternates, so a human or synthetic voice can be added later without re-cutting | NEW | ✅ | – | `script.slots` (2.16) |
| Mix rules: effects sit below music; effect onsets land within one frame of timing events | NEW | ✅ | – | measured in `qa.run` layout checks (0.11) |

## 7. Rendering and output
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Renderer routing per shot (SVG, Synfig, Grease Pencil, Lottie) | NEW | ✅ | – | |
| Composited character layers over the animated set | NEW | ✅ | – | |
| Video, Lottie, web player, Synfig and Grease Pencil project exports | PRO/NEW | ✅ | – | |
| WebM and ProRes with alpha, GIF/APNG, stickers | PRO | ⬜ | P1 | alpha video, GIF, APNG: WP-23 |
| OpenTimelineIO / FCPXML / EDL hand-off to editors | PRO | 🟡 | P1 | `film.cuts` writes OTIO per cut (2.14); FCPXML, EDL and round trips: WP-22 |
| Game runtime export: sprite sheets, Spine-like JSON for Godot or Unity | PRO (Spine) | ⬜ | P2 | sprite sheets and game formats: WP-30 |
| Aspect-ratio re-staging (9:16 ↔ 16:9 ↔ 1:1 by re-blocking, not cropping) | IDEA | ✅ | – | `film.render` with `aspect` re-stages from the data (1.12); one command for all three: WP-24 |
| Parallel render workers, frame reuse, static-layer cache | NEW | ✅ | – | browser per worker, frame dedupe (0.1); static-layer cache: WP-15 |
| Incremental re-render (only changed shots) | NEW | ✅ | – | content hash per shot (0.4) |
| Style passes: paper texture, grain, line boil, watercolour | PRO | ✅ | – | paper, grain, boil and post presets (1.7, 1.9); watercolour: WP-15 |
| Vector resolution independence (4K for free) | NEW | ✅ | – | |
| 12-fps-native rendering: render only unique stepped frames and encode at 24 or 30 | EMG | 🟡 | P1 | stepped frames are deduplicated (0.1); render only unique frames: WP-15 |
| Line-art GIFs: a 32-colour palette with Bayer dithering, sized for messaging | PRO | ⬜ | P1 | WP-23 |
| Sticker and emoji packs: Telegram (WebM/TGS), WhatsApp (WebP), Giphy (GIF), iMessage (APNG) | NEW | ⬜ | P1 | WP-23 |
| Merch- and print-ready stills: high resolution, transparent, using the original ink | NEW | ⬜ | P2 | WP-23 |
| Interactive toy pages: a character with live boil, wobble and fps sliders, for audiences or for artists tuning a look | IDEA | ⬜ | P2 | WP-30 |
| **Master to many cuts:** edit lists assemble one master render plus inserts (cards) into a full film, an episode series, teasers and recaps. Cuts fall on beats and inserts are whole bars, so the music keeps its phase | NEW | ✅ | – | `film.cuts` (2.14) |
| **Native dual-aspect composition:** 16:9 and 9:16 are laid out separately with the same story and timings, never cropped or letterboxed | NEW | ✅ | – | 1.12 |
| Deliberate covers per cut and platform (chosen frame plus cover text), never the platform default | NEW | ✅ | P1 | `cover.make`: scored frame per cut, brand-kit text in the calm band of the safe area, per platform (WP-07) |
| Encoding profiles per platform: H.264 High CRF 18, AAC 48 kHz 320 kb/s, faststart, size caps | NEW | ✅ | – | dbe/profiles.json and `film.package` (0.13) |

## 8. Localisation, accessibility, reach
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Re-voice and re-time per language | NEW | ✅ | – | `film.localize` |
| Translated captions and on-screen text | NEW | 🟡 | P1 | `film.localize` captions and voice; set text: WP-25 |
| Right-to-left and complex scripts in captions | NEW | ⬜ | P1 | WP-25 |
| Cultural adaptation: swap sets, props, names per market | IDEA | ⬜ | P2 | WP-25 |
| Sidecar SRT/VTT plus burned-in captions | PRO | ✅ | – | `film.render` writes .srt and .vtt (0.8) |
| Audio-description track generated from the shot list | EMG | ⬜ | P1 | WP-24 |
| Flash and photosensitivity check (WCAG 2.3) | NEW | ⬜ | P1 | WP-24 |
| Colour-blind-safe palette check | NEW | 🟡 | P2 | `brand.check` CVD separation (1.14); on frames: WP-24 |
| Reduced-motion variant | IDEA | ⬜ | P2 | WP-24 |
| Sign-language inset presenter | IDEA | ⬜ | P2 | not planned: needs Deaf community partners |
| Platform packs: safe zones, thumbnails, titles, descriptions | NEW | ✅ | – | `film.package` platform files (0.13) |
| Interactive web films: branching, quizzes, click-to-explore | EMG | ⬜ | P2 | WP-30 |
| **Posting package generator:** per-platform captions (takeaway in the first line, sources in a pinned comment, hashtags last), YouTube title, description and chapters, alt text, an engagement prompt, playlists, post dates | NEW | ✅ | – | `film.package` (0.13) |
| **Title and thumbnail lab:** titles written for newcomers that are still literally true, "double barrel" thumbnail text in tension with the title, candidate generation, audience polls between true options, back-catalogue retitling | NEW | 🟡 | P1 | `title.check/propose/set`, `titles.status`: truth and newcomer checks, double-barrel thumbnails, back catalogue retitled (WP-07); audience polls between true options: WP-31 |
| Publishing connectors and scheduler: upload and schedule per platform, always with human approval per post | IDEA | ⬜ | P2 | WP-08 |
| 48-hour metrics checklist and analytics ingestion per platform | NEW | ⬜ | P2 | WP-31 |
| Multi-language audio tracks on the main channel vs separate dubbed channels, with revenue per geography considered | NEW | ⬜ | P2 | WP-08 |

## 9. QA and review
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Measured QA bar and contact sheets | NEW | ✅ | – | |
| Fact tracing | NEW | ✅ | – | |
| Visual lint: tangents, limbs off-screen, caption collisions, IK overextension, intersecting props, character overlap | NEW | ✅ | – | `film.lint` (2.8) |
| Golden-frame regression tests | NEW | ✅ | – | `test` (0.3) |
| Frame comments that become data edits | IDEA | ✅ | – | `review.add`, `review.fix` (3.4) |
| Visual diff between film versions | NEW | ⬜ | P1 | WP-19 |
| Health and claims risk review | NEW | ✅ | – | expert review in `research.check` (omits per fact) and the approval gate on the board (WP-05) |
| Retention analytics fed back into hooks and pacing | EMG | ⬜ | P2 | WP-31 |
| **Frame-fill metric:** share of bare background below 40% per scene, measured every 3 s on the final encode; tallest bare band; a 360 px look test | NEW | ✅ | – | `qa.run` (0.11) |
| **Safe-zone text check:** every word's box inside the platform-safe area (9:16: x 64–960, y 200–1560), with platform UI mock overlays (right rail, caption block, top bar) | NEW | ✅ | – | `qa.run` (0.11) |
| Minimum type sizes per aspect (9:16: headline 64, body 40, label 30, floor 26 px; 16:9: 56/34/24) | NEW | ✅ | – | `qa.run` (0.11) |
| **Reading-time rule:** each text block visible ≥ words ÷ 3 + 1 s; a new line starts only after the outgoing one clears | NEW | ✅ | – | `qa.run` (0.11) |
| Seam smoothness: mean frame difference at cuts ≤ 3.5, with 12-frame dissolves or motivated moves | NEW | ✅ | – | `qa.run` (0.11) |
| Generic-AI-look lint: rounded shadow cards, gradient blobs, emoji, neon glow, centred-everything layouts | IDEA | ✅ | P1 | `tools/ailook.mjs` in `qa.run`, enforced per style (WP-04) |
| **Research gates:** two independent sources per on-screen number, a counter-evidence agent, official-page checks for names and dates, a research log, and a fact-check gate before the storyboard | NEW | ✅ | – | `research.check` and `ledger.add` (0.10) |
| Honest on-screen labels: "re-analysis", "illustration", "preliminary" | NEW | ✅ | – | facts.json labels shown with the captions while a citing line plays (WP-05) |
| **Critic loop roles:** fresh agents (sound-off reader, fact checker, director) get stills and facts, not the builder's conclusions; at least two rounds; ledger with before/after numbers | NEW | ✅ | – | `critic.pack` (0.12) |
| Content-safety gate at brief time, with narrow-and-relaunch instead of forcing a blocked topic | NEW | ✅ | – | sensitive briefs need a safety clearance in `research.check` (0.10) |

## 10. Collaboration, ecosystem, governance
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Cast registry with provenance log and content hashes | NEW | ✅ | – | |
| Auto credits | NEW | ✅ | – | |
| Asset licence manifest for sets, SFX, fonts, props | NEW | ✅ | – | assets/manifest.json and `asset.check` (0.7); licence classes: WP-33 |
| Marketplace: puppets, clips, sets, with revenue share by usage | IDEA | ⬜ | P2 | WP-29 |
| Content credentials (C2PA) and AI-disclosure labels | NEW | ⬜ | P1 | WP-26 |
| Likeness and consent rules for characters and voices | NEW | ⬜ | P1 | WP-26 |
| Versioning, branching, review in git | NEW | ✅ | – | films are text |
| Roles and permissions (artist, director, reviewer) | PRO | ⬜ | P2 | WP-39 |
| Rights model per asset: open licence, owner-proprietary, client work (with transfer terms), with usage permissions enforced at render | NEW | ✅ | – | `cast.add` rights (0.9) |
| Creator monetisation outputs: sticker packs, merch stills, loop packs, rig and boil-preset templates for sale, client explainer packages | IDEA | ⬜ | P2 | WP-23, WP-29 |
| Teaching mode: turn a character's pipeline (photo → cutout → rig → episode) into a step-by-step tutorial | IDEA | ⬜ | P2 | WP-28 |
| **Brand kit:** palette with measured contrast, colour-blind separation and distance from platform UI colours; type system; exclusion rules ("nothing like competitor X"); generated profile pictures, covers, flyers and print with safe-zone overlays; templates that films inherit | NEW | ✅ | – | `brand.check`, `brand.assets` (1.14); several kits by id, one per channel, inherited by its films (WP-32) |
| **Public corrections log:** dated, on the original page; covers titles, thumbnails and social cards; credits critics; separates "what we got wrong" | NEW | ⬜ | P1 | WP-27 |
| Independence rules: no sponsor that makes what a film assesses; disclose access without payment; disclose ownership changes the day they happen | NEW | ⬜ | P2 | WP-27 |
| Community intake: send-a-myth, challenges, early-preview reviewers, paired collaborations with other creators | IDEA | ⬜ | P2 | WP-27 |
| Business dashboard: revenue by platform and geography, RPM, catalogue value, pre-sale readiness | IDEA | ⬜ | P2 | WP-31 |

## 11. Agent and developer platform
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| One command registry → CLI, HTTP, MCP, Studio | NEW | ✅ | – | |
| Async jobs | NEW | ✅ | – | |
| Progress events and webhooks | NEW | ⬜ | P1 | WP-20 |
| Cost and time estimate before rendering | NEW | ⬜ | P1 | WP-20 |
| Specialist agents: director, animator, editor, critic, fact-checker | IDEA | ⬜ | P1 | WP-21 |
| Natural-language editing ("make Pip turn when she says Blender") | NEW | 🟡 | P0 | `acting.direct`, `review.fix`, `timeline.edit`; chat: WP-21 |
| Python and JS SDKs, recipes, templates | NEW | ⬜ | P2 | not planned: the CLI, HTTP API and MCP expose every command |
| Multi-tenant sandboxing and quotas | NEW | ⬜ | P2 | not planned: in-house, single owner |
| **Production orchestrator:** a planning agent spawns one production session per film (own workspace and branch), receives checkpoint reports (research done, first render, final metrics), keeps a session registry, can stop, narrow or relaunch a film, and merges finished work | NEW | ✅ | – | `prod.*` and Studio /board (plan 3.7): worktree and branch per film, pipeline, Claude Code or manual sessions, measured checkpoints, escalation, scoped merge |
| Escalation protocol: research that contradicts the brief goes to the planner; blockers don't stop other work; a late film finishes its primary cut first | NEW | ✅ | – | `prod.checkpoint` escalates and `prod.decide` resolves (3.7) |
| Per-film workspace isolation: a production session works only inside its film folder | NEW | ✅ | – | a git worktree per film and a scoped merge (3.7) |

## 12. Human interfaces
| Feature | Source | Status | Priority | Notes |
|---|---|---|---|---|
| Rig Canvas: slots, views, pivots, live previews from the clip library | PRO/NEW | ✅ | – | v0.2 |
| Posing on the canvas by dragging hands and feet (IK) | PRO | ✅ | – | Rig Canvas pose tool (3.3) |
| Clip and pose authoring by recording a drag or a webcam take | IDEA | ✅ | – | Rig Canvas posing (3.3), Act it out (3.5) |
| Studio: films, shots, renderer routing, render, log | NEW | ✅ | – | basic |
| Timeline editor: shots, clips, dialogue lanes, scrub with live preview | PRO | ✅ | – | /timeline (3.1) |
| Director's desk: chat beside a storyboard strip and animatic | IDEA | ⬜ | P1 | WP-21 |
| Review room on mobile: approve, comment on a frame | NEW | ⬜ | P1 | WP-19 |
| Tablet and pencil support | PRO | 🟡 | P1 | pointer pressure works; WP-18 |
| **Phone-first creator flow:** snap a doodle, confirm the suggested cuts, and see it move and talk within a minute | IDEA | ✅ | – | Studio /doodle and `doodle.snap/cut/say/keep` (plan 3.6): photo to talking in about 11 s |
| Drawing request queue: when a script needs a pose the rig can't do, the artist gets a request with a ghost guide; the drawing slots straight into the rig | IDEA | ✅ | – | `drawing.requests` / `drawing.fulfil` (plan 3.6): swap shapes and parts drawn over a ghost; pupils, views and chains go to the Rig Canvas |
| **Production board:** calendar, per-film status, checkpoints, measurements and critic verdicts, with approve and stop controls | NEW | ✅ | – | Studio /board (plan 3.7): calendar, schedule against posting dates, checkpoints, measurements, approve, stop, narrow, merge |
| Live plan tracker shared with collaborators | NEW | 🟡 | P2 | `plan.track` and /plan (3.8); sharing: WP-39 |

---

## 13. Emergence: what the combination makes possible
These come from stacking primitives we already have. Each one is cheap because the data already exists.

| # | Because we have… | …this emerges | Status |
|---|---|---|---|
| E1 | Frame-pure rendering + films as text | **Films you can diff, bisect and test.** Golden frames catch regressions; any old version re-renders exactly; a frame is a reproducible record. | ✅ golden frames, content hashes (0.3, 0.4) |
| E2 | Line-relative times + TTS + alignment | **Edit the script and the film follows.** Change a sentence and acting, cuts, captions and cues re-flow. Localisation is a special case. | ✅ `film.retime`, `film.revoice` (0.6, 2.16) |
| E3 | Foot pins + contact frames + clips | **Automatic foley.** Footsteps on every plant, cloth swishes on fast arm moves, thuds on landings. | ✅ (2.7) |
| E4 | Character screen positions + the mix | **Spatial audio.** Voices and effects pan with the character. | ✅ (2.7) |
| E5 | `shots.json` semantics (who, where, doing what) | **Audio description, alt text, chapter markers, transcripts and thumbnails, all auto-generated.** We know what is on screen without vision models. | 🟡 alt text and chapters in `film.package` (0.13); AD track: WP-24 |
| E6 | Puppets + views + IK + poses | **One character, every medium:** video, comic panels, storybook pages, stickers, thumbnails, print, merch. Pose a still, render a page. | ⬜ P1 · WP-30 |
| E7 | Baked acting + Lottie + clip library | **The cast in apps and games:** animated stickers, in-app mascots, game sprites, all from the same rig. | 🟡 · WP-30 |
| E8 | Live web player + data | **Personalised films rendered in the viewer's browser:** their name, language and region, at zero server cost. | ⬜ P2 · WP-30 |
| E9 | Real-time puppet + webcam tracking | **Live 2D avatars of the cast** for streams and classrooms, VTuber-style. | ⬜ P2 · WP-12 |
| E10 | QA bar + agent + data edits | **Self-healing renders.** The agent reads a QA failure (a still stretch, loudness, a caption collision), edits the timeline and re-renders until it passes. This session did it by hand for the idle clip. | ✅ `film.heal` (2.9) |
| E11 | Hook variants + analytics | **Self-optimising openings.** Retention data picks hooks and pacing for the next film. | ⬜ P2 · WP-31 |
| E12 | Facts ledger + script tags | **Living films.** When a source updates a number, the affected shots re-render; an auto "sources" end card cites them. | 🟡 `film.data` (2.17); living films: WP-27 |
| E13 | Cast personality + gesture planner | **Characters that act in character** across films and agents: a shy character never points broadly. | ⬜ P1 · WP-10 |
| E14 | Provenance hashes + determinism | **Verifiable content credentials.** Anyone can re-render and check a frame matches its signed recipe. | ⬜ P2 · WP-26 |
| E15 | Usage recorded in `shots.json` | **Exact artist royalties.** Pay per second of screen time for each puppet, clip or set. | ⬜ P2 · WP-29 |
| E16 | Series data across films | **Continuity memory.** The bible knows outfits, props and running gags, and the critic flags breaks. | ⬜ P2 · WP-28 |
| E17 | Same acting → many renderers | **Style A/B tests.** Render one performance flat, Synfig-smooth or Grease Pencil-sketchy, then pick per audience or platform. | ✅ |
| E18 | Data films + aspect ratios | **Re-blocked formats.** A 16:9 version re-stages characters and camera rather than cropping a 9:16 film. | ✅ (1.12) |
| E19 | Ink-fidelity import + rigging + voice + shot data | **Doodle to series.** Any notebook doodle becomes a talking, acting series character in minutes, in the artist's own line. | ✅ `doodle.snap`, `doodle.keep` (3.6) |
| E20 | Rig ability inventory + writer agent + Rig Canvas | **Human-in-the-loop production queue.** Scripts stay within what rigs can do; a missing pose becomes a drawing request; the new drawing joins the rig and the shot re-renders. | ✅ P1 (swap shapes and parts; poses and views still in the Rig Canvas) |
| E21 | Bubbles + voice timing + captions | **Sound-on and sound-off cuts from one film:** voiced with captions, or bubble-only paced for reading. | ✅ (2.13) |
| E22 | Deterministic boil seeds + stepped timing + frame hashing | **Handmade look at half the cost.** The shimmer is reproducible, and 12 unique frames per second are reused across 24 or 30 fps output. | 🟡 boil, stepped timing, dedupe; unique-frame rendering: WP-15 |
| E23 | Original ink as raster parts + stills export | **Merch and stickers at full fidelity:** the artist's real line on shirts, prints and sticker packs. | ⬜ P2 · WP-23 |
| E24 | Content planner + orchestrator + research gates + QA + posting packages | **A channel that runs itself, with a human at the checkpoints.** Calendar → briefs → parallel film agents → gated QA → posting packages; the owner approves. | 🟡 planner and orchestrator (3.7, 3.8); calendar to storyboard to session in one command (`plan.brief` launch, WP-06); posting: WP-08 |
| E25 | Beat grid + edit lists + native aspect layouts | **One production, a week of posts:** a full film, an episode series, teasers and both aspect ratios, without re-animating. | ✅ (2.14) |
| E26 | Facts ledger + posting generator + corrections log | **One source of truth for every word.** Captions, pinned sources, alt text and pages all derive from the same claims, so a correction reaches every surface. | ⬜ P1 · WP-27 |
| E27 | Narration slots + sound-off master + voices | **Ship silent, voice later, dub anywhere:** any voice or language drops into the same timed slots. | ✅ (2.16) |
| E28 | Misconception and dialogue formats + the cast | **Characters as learner and expert:** the format with the strongest published learning gains, natural for cartoons. | ✅ (2.15) |
| E29 | Measured layout rules + films as data | **Layout auto-repair:** the agent moves and resizes text and pictures until frame fill, safe zones, type sizes and reading time all pass (extends E10). | ✅ (2.18) |
| E30 | Brand kit + templates + deterministic renders | **Rebrand the whole catalogue:** a new identity re-renders every film, cover and post. | 🟡 brand inheritance (1.14); kits per channel (WP-32); re-rendering a whole catalogue in a new identity: WP-27 |
| E31 | Analytics + idea bank + calendar | **A plan that re-ranks itself** on what actually performs, per platform. | ⬜ P2 · WP-31 |

## 14. What not to build
- Photoreal or generative-video characters: they break consistency, editability and the licence trail. Use
  generative models only for licence-cleared backgrounds and props, if at all.
- A full raster frame-by-frame paint suite (TVPaint territory). Import from Krita instead.
- Proprietary runtimes we can't redistribute: no Spine runtime embedding and no Remotion. See `oss-research.md`.

## 15. Build order
The phased plan, which combines this map with the open-source research, lives in `docs/build-plan.md`.

## 16. Build-with map (from `docs/oss-research.md`)
Which open-source pieces implement which features. Licences were verified by the research pass; see that file for the
[V]/[R]/[U] tags.

| Feature (section) | Build with | Licence | Status |
|---|---|---|---|
| Clean voices (§6) | Piper public-domain voices: kristin, norman, bryce, cori, john, ljspeech | PD | ✅ gate plus 4 installed |
| More voices and languages, Spanish quality (§6, §8) | Kokoro-82M (or kokoro-onnx) | Apache-2.0 (espeak fallback GPL, as a subprocess) | ✅ Kokoro, 54 voices (0.5) |
| Expressive lines, consented cloning (§6) | Chatterbox (watermarked) | MIT | ⬜ P2 · WP-43 |
| Phone-accurate lip-sync (§3) | wav2vec2-espeak CTC + torchaudio `forced_align` (same phone set as our visemes); or MFA | Apache-2.0 / MIT, model CC BY 4.0 | ✅ Kokoro phoneme durations (2.1); recorded voices: WP-13 |
| Lip-sync QA cross-check and transcript-free fallback (§3, §9) | Rhubarb Lip Sync | MIT | ✅ (2.2) |
| Steadier word timing on known scripts (§6) | stable-ts `align()` | MIT | ✅ (2.1) |
| N-bone IK (§2) | FABRIK ported in-house (references: fullik, THREE.IK) | MIT refs | ✅ (2.5) |
| Gesture planner (§3) | In-house: pyworld F0 peaks + espeak stress + LLM semantic tags → clip scheduler | none | ✅ (2.3) |
| Seeded idle noise and handheld camera (§3, §4) | opensimplex | MIT | ✅ (2.6) |
| Act it out / webcam performance (§3, §12) | MediaPipe Pose/Holistic/Face; rtmlib RTMPose for accuracy | Apache-2.0 | ✅ P1 (MediaPipe Pose + Face Landmarker) |
| Auto-rig from a drawing (§1) | Animated Drawings ideas + scikit-image skeletonize/skan | MIT / BSD-3 | 🟡 doodles (3.6) · WP-18 |
| Bendy limbs in Synfig output (§2) | Synfig Skeleton Deformation + Switch layers in the `.sif` exporter | GPL (CLI subprocess) | ⬜ P1 · WP-14 |
| Rig Canvas strokes (§1) | perfect-freehand; simplify-js | MIT / BSD-2 | ✅ (1.4) |
| Scan/sketch import (§1) | VTracer (colour); potrace (mono, subprocess); ImageTracer.js in-browser | MIT / GPL / Unlicense | 🟡 ink import (1.8); tracing: WP-18 |
| Part cleanup on import (§1) | picosvg, svgo (safe preset keeping IDs), vpype | Apache-2.0 / MIT / MIT | 🟡 · WP-18 |
| Cel shadows, rims, outline offsets (§4) | Clipper2 (pyclipr), skia-pathops (keeps curves) | BSL-1.0 / BSD-3 | ✅ SVG (1.7); others: WP-14 |
| Render speed (§7) | Worker pool + frame-hash dedupe + static-layer cache + PyAV piping + `-tune animation` | in-house / BSD-3 | ✅ (0.1) |
| Faster rasteriser (§7) | Benchmark resvg and ThorVG behind a pixel-diff gate (harness saved) | Apache/MIT, MIT | ✅ decided: keep Chromium (0.2) |
| Lottie export QA (§7, §9) | ThorVG + lottie-web golden images; schema validation from lottie-docs | MIT / CC BY 4.0 | 🟡 lottie-web renders work · WP-23 |
| Lottie packaging with palette themes (§7) | dotLottie | MIT | ⬜ P2 · WP-23 |
| Post effects: grain, LUT, vignette, xfade, motion blur (§4, §7) | ffmpeg filter graphs; accumulation blur in-house; SVT-AV1 film-grain | in stack | 🟡 grain, LUT, vignette (1.7); dissolves, motion blur: WP-15 |
| 3D pass compositing (§4) | oiiotool; three.js toon stack | Apache-2.0 / MIT | ⬜ P2 · WP-42 |
| Editor hand-off (§7) | OpenTimelineIO (+ EDL/FCPXML adapters); `melt` for round trips | Apache-2.0 / LGPL | 🟡 OTIO per cut (2.14) · WP-22 |
| Cast variety (§1, §10) | Open Peeps, Humaaans → puppets | CC0 | ✅ (1.5); Open Peeps, Humaaans: WP-16 |
| Props, icons, SFX (§4, §6) | Kenney, Tabler, Lucide, Phosphor, Fluent Emoji | CC0 / MIT / ISC / MIT | ✅ Lucide icons, props (1.6); Kenney: WP-13, WP-16 |
| Medical and map shots (§4) | Servier Medical Art; Natural Earth + d3-geo | CC BY 4.0 / PD | ⬜ P1 · WP-16 |
| Asset licence manifest and credits (§10) | In-house manifest → `film.credits` | none | ✅ (0.7) |
| Scene DSL reference (§11) | Motion Canvas / Revideo ideas (reference only) | MIT | — |
| Ink-fidelity import (§1) | numpy, scipy (ndimage), Pillow: blur-divide, threshold, connected components | BSD / BSD / HPND | ✅ (1.8) |
| Line boil (§4) | SVG `feTurbulence` + `feDisplacementMap` with cycled seeds (SVG renderer); numpy displacement fields for raster paths | built in | ✅ (1.9) |
| Bubbles and typewriter (§4) | in-house; Patrick Hand and other OFL hand fonts | OFL | ✅ (2.10); thought clouds, letters: WP-17 |
| Line-art GIFs and stickers (§7) | ffmpeg `palettegen`/`paletteuse` (Bayer); libwebp; Lottie for TGS | in stack / BSD | ⬜ P1 · WP-23 |
| Frame fill, seams (§9) | numpy box filters and frame differences on ffmpeg grey frames (playbook reference code) | BSD | ✅ (0.11) |
| Safe-zone text and type sizes (§9) | Playwright: each text element's bounding box in the rendered page; platform UI mock overlays | Apache-2.0 | ✅ (0.11) |
| Palette checks (§10) | colour-science (CIEDE2000, Machado 2009 CVD simulation) | BSD-3 | ✅ (1.14) |
| Master to many cuts (§7) | in-house edit lists on the beat grid; OpenTimelineIO for export | Apache-2.0 | ✅ (2.14) |

Avoid: OpenPose, Ultralytics, python-lottie in the service, aeneas, XTTS-v2 and F5-TTS weights, MMS aligner weights,
EMAGE/BEAT2, audio2photoreal, MakeItTalk, Sapiens, LAFAN1 data, embedding Spine or Remotion, OpenMoji (SA), BBC
sound effects (NC), Sonniss files in public repos or training sets, Z-Anatomy NC parts.
