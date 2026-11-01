# Doodleberry build plan (November 2026)

This plan combines the feature map (`docs/feature-map.md`: what the studio needs) with the open-source research
(`docs/oss-research.md`: what to build it with, and which licences are safe). It replaces the "Next 12" list.

**How it's ordered**
- Multipliers first: speed, tests and clean inputs make every later step cheaper and safer.
- Then the biggest visible gap (character deformation and look).
- Then acting intelligence, then human interfaces, then reach and ecosystem.
- Emergent features (E-numbers in the feature map) land in the phase where they become cheap.
- Creator abilities learned from the Sheep & Pig doodle toolkit (ink-fidelity import, boil, bubbles, comedy timing,
  owner rights, stickers) sit in the phase whose groundwork they share.

**Conventions**
- **Effort:** S = under 2 days, M = 1–2 weeks, L = more than 2 weeks, for one developer working with an agent.
- **Weeks** are a sequence, not dates.
- **Benchmark films:** `pip-park` (three renderers), `acting-demo`, `pip-park-es`, plus a two-character dialogue film
  added in Phase 2.
- **Licence rule:** only components the research marked permissive, or GPL tools run as separate processes. Never use
  NC weights or data, or AGPL code inside the service. Each new dependency gets a row in the asset/licence manifest.

---

## Phase 0: Foundations (weeks 1–3)
Goal: faster renders, regression safety, clean voices everywhere, credits for every asset.

| # | Item | Build with | Effort | Done when |
|---|---|---|---|---|
| 0.1 | **Render speed package:** one Chromium page per CPU, frame-hash dedupe, static-layer cache, raw frames piped to the encoder, `-tune animation` | in-house; PyAV (BSD-3); `chrome-headless-shell` | M | `pip-park` svg shots ≥3× faster; frames pixel-identical to today's goldens |
| 0.2 | **Renderer benchmark gate:** resvg and ThorVG vs Chromium on our frames | saved harness (`bench/`); resvg (Apache/MIT), ThorVG (MIT) | S | decision recorded: switch only if ≥2× faster with ≤0.5% pixel difference |
| 0.3 | **Golden-frame regression tests** (E1) plus JSON Schemas for `shots.json` and `script.json`, validated before any render | in-house; jsonschema | S | CI-style `python -m dbe test` renders key frames of each benchmark film and diffs them; malformed shot lists are refused with a readable error |
| 0.4 | **Incremental re-render:** a content hash per shot (baked spec + puppet + renderer); only changed shots render | in-house | S | editing one shot re-renders only that shot |
| 0.5 | **Kokoro-82M as a second TTS backend**; voice registry entries with licences; check Kokoro's word timestamps | Kokoro / kokoro-onnx (Apache-2.0; espeak fallback GPL as a subprocess) | M | `voices.list` shows Kokoro voices as clean; the Spanish film re-voiced, with Whisper back-transcription matching the script |
| 0.6 | **Re-voice the seven legacy films** with clean voices; remove `allow_restricted_voices` | Piper PD voices, Kokoro | S | every film builds through the gate |
| 0.7 | **Asset licence manifest** covering sets, SFX, music, fonts, icons and props; `film.credits` reads it | in-house | S | credits list every third-party file a film uses |
| 0.8 | **Sidecar captions:** SRT/VTT next to every final | in-house (from timing.json) | S | `film.render` writes `.srt` and `.vtt` |
| 0.9 | **Rights model:** owner-IP characters and per-asset rights (open, owner-proprietary, client work), enforced at render and in credits | in-house | S | a creator's own hand-drawn character registers through `cast.add` with owner rights |

## Phase 1: The look (weeks 4–8)
Goal: close the biggest visual gap with professional tools, and make drawing in, importing and casting easy.

| # | Item | Build with | Effort | Done when |
|---|---|---|---|---|
| 1.1 | **Bendy limbs and mesh/warp deformation** (puppet format v0.3 `deform`). In SVG: path warp along a bone curve. In Synfig: Skeleton Deformation layers. In Grease Pencil: per-point bending | in-house; Synfig Skeleton Deformation (GPL, subprocess) | L | an arm bends in a smooth curve with no joint gap, identical across svg, synfig and grease-pencil |
| 1.2 | **Smart bones / driven keys:** one control drives offsets, swaps and z-order. **Constraints:** look-at, parent switching (prop hand-offs), follow path | in-house | M | Pip passes a ball from one hand to the other; a single `turn` control drives the head's 3/4 offsets |
| 1.3 | **Drawing import:** layered PSD/Krita/SVG to parts by layer name; scans traced with VTracer (colour) or potrace (mono); cleanup with picosvg and svgo (safe preset) | psd-tools (MIT), VTracer (MIT), potrace (GPL, subprocess), picosvg (Apache-2.0), svgo (MIT) | M | a layered PSD drawn to the template becomes a lint-clean puppet in one `puppet.import` call |
| 1.4 | **Rig Canvas drawing upgrade:** perfect-freehand strokes, simplify, gap-closing fill, model-sheet and expression boards | perfect-freehand (MIT), simplify-js (BSD-2) | M | an artist can draw a full puppet and its side view without leaving the canvas |
| 1.5 | **Cast variety:** convert Open Peeps and Humaaans to puppets; outfits as swap sets | Open Peeps, Humaaans (CC0) | M | at least 12 distinct cast members in `cast.list`, each with provenance |
| 1.6 | **Sets and props:** about 10 sets (kitchen, classroom, farm, street, office, body cross-section, map board...), icons, props | Kenney (CC0), Tabler/Lucide/Phosphor (MIT/ISC), Servier Medical Art (CC BY 4.0), Natural Earth (PD) + d3-geo | M | the set library covers the director prompt's common locations; every file is in the manifest |
| 1.7 | **Toon shading and post effects:** cel shadows and rims from polygon offsets; a `post` preset command (grain, LUT, vignette, xfade, sub-frame motion blur) | Clipper2/pyclipr (BSL-1.0), skia-pathops (BSD-3), ffmpeg filters | M | style presets selectable per film; motion blur only on fast shots |
| 1.8 | **Ink-fidelity import plus raster parts:** photo or scan → clean line keeping the artist's texture; mask-based part cutting with overlap seams; pivot and cut suggestions; puppet format v0.3 raster parts in the SVG renderer | numpy, scipy, Pillow (BSD/HPND) | M | a phone photo of a notebook doodle becomes a lint-clean, blinking, waving puppet in under 10 minutes |
| 1.9 | **Hand-made look:** line boil (cycled seeds, deterministic), stepped timing on 12s/8s/6s, paper and medium sets (notebook, sketchbook, whiteboard, chalkboard), ink props and signs | SVG filters; in-house | M | the Sheep & Pig episode re-renders in Doodleberry matching the toolkit's look |
| 1.10 | **Drawing coach:** pre-import checks and advice (limb length, joint gaps, separate eyes, scale) | in-house + agent | S | a drawing that would rig badly gets specific, visual advice before import |
| 1.11 | **Doodle template:** minimal rigs (head, body, arms, tail), with hop, wave, tilt, wag, lean and talk clips | in-house | S | any simple character gets a working clip set without humanoid parts |

## Phase 2: Acting intelligence (weeks 9–13)
Goal: characters that act on their own, from the script and the voice, and do it in character.

| # | Item | Build with | Effort | Done when |
|---|---|---|---|---|
| 2.1 | **Phone-level alignment:** real phone boundaries instead of spreading phonemes across words | wav2vec2-espeak CTC + torchaudio `forced_align` (Apache-2.0); MFA (MIT, CC BY 4.0 model) as the accurate path | M | viseme timing error vs a hand-checked line is ≤40 ms on average |
| 2.2 | **Lip-sync QA cross-check:** diff our mouth track against Rhubarb's; also the fallback when no transcript exists | Rhubarb Lip Sync (MIT) | S | `qa.run` reports lip-sync agreement and fails below a threshold |
| 2.3 | **Gesture planner:** beats on F0 peaks and stressed words, head tilts on questions, semantic gestures from LLM tags; listeners react (gaze, nods). Personality shapes it (E13) | in-house: pyworld, espeak stress, the clip library | M | a two-character dialogue film acts with no hand-placed clips, and a critic rates it above the hand-keyed baseline |
| 2.4 | **Natural-language acting direction:** "Pip is nervous and glances at the door" → clips, poses, gaze, timing | agent prompt + `acting.direct` command | M | the director agent stages a scene from prose alone |
| 2.5 | **Clip library to about 30 clips**, joint limits, N-bone FABRIK (tails, tentacles), emotion-aware mouth charts, animation-principle filters (anticipation, overshoot) | FABRIK in-house (MIT references) | M | the new clips render on all renderers; a tail rig works |
| 2.6 | **Camera grammar:** follow a character, auto-framing with caption headroom, punch-ins on emphasis, seeded handheld noise | in-house; opensimplex (MIT) | S | shots without camera keys still get sensible framing |
| 2.7 | **Automatic foley and spatial mix** (E3, E4): footsteps from foot plants, swishes on fast moves, thuds on landings; panning by screen position | in-house; Kenney CC0 SFX | S | footsteps land within one frame of each plant |
| 2.8 | **Visual lint:** tangents, limbs off-screen, caption collisions, IK overextension, props intersecting | in-house, from the baked geometry | S | lint runs inside `qa.run` with frame references |
| 2.9 | **Self-healing loop** (E10): the agent reads QA and lint failures, edits the timeline, re-renders, until the film passes | registry + critic agent | M | a seeded failure (a frozen stretch, a caption collision) is fixed without a human |
| 2.10 | **Speech and thought bubbles:** say, shout, whisper, thought, narration; tails track the speaker; collision-aware placement; typewriter synced to the voice | in-house; OFL hand fonts | M | a two-character dialogue reads correctly with the sound off |
| 2.11 | **Comedy timing toolkit and gag library:** scripted blinks, holds, double-takes, the long stare, button moves, rule of three; reusable beat patterns agents can compose | in-house | M | the director agent stages a gag from a one-line description and a reviewer rates the timing as landing |
| 2.12 | **Rig ability inventory and rig-aware writing:** characters declare free and costly moves; the writer agent writes within them and files drawing requests for new poses | in-house + agent | M | a script for a minimal rig needs no new drawings, or lists exactly which ones it needs |
| 2.13 | **Sound-off cut** (E21) and move-bound SFX accents (a boing per hop, pen-scratch ambience) | in-house; Kenney CC0 | S | every film ships a voiced cut and a bubble-only cut paced for reading |

## Phase 3: Human interfaces (weeks 14–18)
Goal: artists, directors and reviewers work alongside the agent, and every UI action is a command.

| # | Item | Build with | Effort | Done when |
|---|---|---|---|---|
| 3.1 | **Studio timeline editor:** shot lanes, clip lanes, dialogue lane, live-scrub preview (the web player already renders any frame) | in-house | L | a director re-times a gesture by dragging, and the edit lands in `shots.json` |
| 3.2 | **Storyboard strip** from `shots.json` (one still per shot, notes) and an animatic button | in-house | S | `film.storyboard` writes a strip and contact PDF |
| 3.3 | **IK posing in Rig Canvas:** drag hands and feet; save poses and record short clips | `acting.js` IK | M | a new pose is made by dragging and saved to the puppet |
| 3.4 | **Review room:** frame comments become data edits; a critic re-checks before closing | registry + agent | M | "raise the arm earlier" on frame 120 is fixed and verified |
| 3.5 | **Act it out:** phone or webcam video → body and face keypoints → joint angles, IK targets, mouth and eye swaps → an action clip | MediaPipe Pose/Holistic/Face (Apache-2.0); rtmlib RTMPose (Apache-2.0) for accuracy | M | a 5-second take becomes a reusable clip in under a minute |
| 3.6 | **Phone-first creator flow:** snap a doodle → confirm cuts and pivots → see it move and talk; plus the drawing request queue (E20) with ghost guides | Rig Canvas, ink import | M | a first-time user goes from photo to a talking clip in about a minute |

## Phase 4: Reach and ecosystem (weeks 19–23)
Goal: every format, every audience, and a trustworthy library others can contribute to.

| # | Item | Build with | Effort | Done when |
|---|---|---|---|---|
| 4.1 | **Editor hand-off:** OTIO timelines (EDL, FCPXML) with stems and captions; round trip through `melt` | OpenTimelineIO (Apache-2.0); MLT (LGPL) | M | a film opens in Resolve or Kdenlive with shots, stems and captions |
| 4.2 | **More outputs:** WebM/ProRes with alpha, GIF/APNG, stickers; dotLottie with palette themes; Lottie QA in ThorVG and lottie-web | dotLottie (MIT), ThorVG (MIT) | M | exports pass golden-image checks in two independent renderers |
| 4.3 | **Accessibility:** audio description generated from shot data (E5), flash check (WCAG 2.3), colour-blind palette check, reduced-motion variant | in-house | M | every final ships with an AD track and passes the flash check |
| 4.4 | **Aspect re-staging** (E18): 16:9 and 1:1 versions re-blocked from the data, not cropped | in-house | M | one command produces three aspect ratios with correct framing |
| 4.5 | **Localisation depth:** translated on-screen text, RTL scripts, cultural swaps of sets and props | libass shaping; Noto fonts (OFL) | M | an Arabic version renders correctly |
| 4.6 | **Trust:** C2PA content credentials, AI-disclosure labels, likeness and consent records | C2PA tooling (verify licence first) | M | finals carry signed provenance |
| 4.7 | **Library economics:** usage accounting from `shots.json` (E15), contributor flow through `cast.add`, groundwork for revenue share | in-house | M | a per-asset screen-time report exists |
| 4.8 | **Also:** living films from the facts ledger (E12), one-character-every-medium stills for comics and thumbnails (E6), interactive web films | in-house | M each | as each lands |
| 4.9 | **Creator outputs:** line-art GIFs, sticker and emoji packs (Telegram, WhatsApp, Giphy, iMessage), merch- and print-ready stills (E23), interactive toy pages | ffmpeg palettegen, libwebp, Lottie/TGS | M | one character exports to four sticker platforms and a print-ready PNG |
| 4.10 | **Series production:** daily-series planner, recurring gags, continuity memory, a posting calendar; teaching mode that turns a pipeline into a tutorial | in-house | M | ten episodes of a series are planned, rendered and scheduled from data |
| 4.11 | **Creator monetisation:** rig and boil-preset templates, loop packs, client explainer packages, with handwriting fonts from the artist's samples | in-house | M | a creator can package and sell a rig template |

---

## Decision gates
- **After 0.2:** keep Chromium unless resvg or ThorVG is at least 2× faster on our frames with near-identical pixels.
- **After 0.5:** if Kokoro has no word timestamps, keep Whisper alignment for Kokoro voices; plan 2.1 as the fix.
- **Before 1.6 and 4.6:** resolve the open licence questions: BodyParts3D, BBC/Pixabay/incompetech, the
  `thorvg-python` binding, sherpa-onnx's espeak code, and the C2PA SDK licence.
- **Before any distribution of Doodleberry as software:** Piper and espeak-ng are GPL. Keep them behind a process or
  service boundary, or replace them.

## Never build
Generative-video characters (they break consistency, editing and the licence trail). A raster frame-by-frame paint
suite (import from Krita instead). Embedded Spine or Remotion runtimes. Anything on the research "avoid" list:
OpenPose, Ultralytics, python-lottie in the service, aeneas, XTTS-v2 and F5-TTS weights, MMS aligner weights,
EMAGE/BEAT2, audio2photoreal, MakeItTalk, Sapiens, LAFAN1 data, OpenMoji (SA), BBC sound effects (NC), Sonniss files
in public repos or training sets, Z-Anatomy NC parts.

## Done so far (for reference)
- **Backend:** the dbe registry (CLI, HTTP, Studio, MCP); shot routing across SVG, Synfig, Grease Pencil and Lottie;
  composited character layers.
- **Puppets and acting:** puppet v0.2 (views, springs, poses); acting (viseme lip-sync, two-bone IK with pins, springs,
  presets, clip stack).
- **Output:** film-level captions; line-relative times; localisation; hook variants; web and Lottie exports.
- **Governance:** the voice licence gate; `cast.add` with provenance; `film.credits`.
- **Interfaces:** Rig Canvas v0.2.
- **Docs:** `docs/dbe.md`, `docs/feature-map.md`, `docs/oss-research.md`.
