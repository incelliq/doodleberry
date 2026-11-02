# Doodleberry build plan (November 2026)

This plan combines the feature map (`docs/feature-map.md`: what the studio needs) with the open-source research
(`docs/oss-research.md`: what to build it with, and which licences are safe). It replaces the "Next 12" list.

**How it's ordered**
- Multipliers first: speed, tests and clean inputs make every later step cheaper and safer.
- Then the biggest visible gap (character deformation and look).
- Then acting intelligence, then human interfaces, then reach and ecosystem.
- Emergent features (E-numbers in the feature map) land in the phase where they become cheap.
- Studio operations learned from the bioinformatics.lk film playbook (research and safety gates, measured layout QA, the
  critic loop, master-to-many cuts, packaging, orchestration, planning, brand and corrections) follow the same rule:
  gates and measurements first, because they make every later film safer and cheaper.
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
| 0.10 | **Research and safety gates:** brief template; two independent sources per on-screen number; counter-evidence agent; official-page checks; research log; fact-check gate before the storyboard; honest on-screen labels; content-safety gate at brief time with narrow-and-relaunch | registry + agents | M | a film can't reach storyboard until its facts pass the gate, and the log shows searches, verdicts and rejections |
| 0.11 | **Measured layout QA:** frame fill (bare share < 40% per scene), safe-zone text with platform UI mocks, minimum type sizes, reading time (words ÷ 3 + 1 s), seam smoothness, cold open (subject in frame one, hook by 1.5 s), AV sync within a frame, effects below music | numpy, Playwright, ffmpeg (playbook reference code) | M | `qa.run` reports every metric with the worst scene and frame, on the final encode |
| 0.12 | **Critic loop:** fresh sound-off reader, fact checker and director agents given stills and facts only; at least two rounds; ledger with before/after numbers | agents | S | every final ships with a ledger like the playbook's |
| 0.13 | **Encoding profiles and posting package:** per-platform encodes and size caps; captions (takeaway first, sources pinned, hashtags last), title, description, chapters, alt text, engagement prompt, playlists | in-house | S | `film.package` writes `posts.md` and platform files for every final |

## Phase 1: The look (weeks 4–8)
Goal: close the biggest visual gap with professional tools, and make drawing in, importing and casting easy.

| # | Item | Build with | Effort | Done when |
|---|---|---|---|---|
| 1.1 | **Bendy limbs and mesh/warp deformation** (puppet format v0.3 `deform`). In SVG: path warp along a bone curve. In Synfig: Skeleton Deformation layers. In Grease Pencil: per-point bending | in-house; Synfig Skeleton Deformation (GPL, subprocess) | L | an arm bends in a smooth curve with no joint gap, identical across svg, synfig and grease-pencil |
| 1.2 | **Smart bones / driven keys:** one control drives offsets, swaps and z-order. **Constraints:** look-at, parent switching (prop hand-offs), follow path | in-house | M | Pip passes a ball from one hand to the other; a single `turn` control drives the head's 3/4 offsets |
| 1.3 | **Drawing import:** layered PSD/Krita/SVG to parts by layer name; scans traced with VTracer (colour) or potrace (mono); cleanup with picosvg and svgo (safe preset) | psd-tools (MIT), VTracer (MIT), potrace (GPL, subprocess), picosvg (Apache-2.0), svgo (MIT) | M | a layered PSD drawn to the template becomes a lint-clean puppet in one `puppet.import` call |
| 1.4 | **Rig Canvas drawing upgrade:** perfect-freehand strokes, simplify, gap-closing fill, model-sheet and expression boards | perfect-freehand (MIT), simplify-js (BSD-2) | M | an artist can draw a full puppet and its side view without leaving the canvas |
| 1.5 | **Cast variety:** convert Open Peeps and Humaaans to puppets; outfits as swap sets | Open Peeps, Humaaans (CC0) | M | at least 12 distinct cast members in `cast.list`, each with provenance |
| 1.6 | **Sets and props:** about 10 sets (kitchen, classroom, farm, street, office, body cross-section, map board...), icons, props | Kenney (CC0), Tabler/Lucide/Phosphor (MIT/ISC), Servier Medical Art (CC BY 4.0), Natural Earth (PD) + d3-geo; Poly Haven and ambientCG (CC0) for 3D sets; Depth Anything V2 Small (Apache-2.0, Small only) for photo parallax | M | the set library covers the director prompt's common locations; every file is in the manifest |
| 1.7 | **Toon shading and post effects:** cel shadows and rims from polygon offsets; a `post` preset command (grain, LUT, vignette, xfade, sub-frame motion blur) | Clipper2/pyclipr (BSL-1.0) or manifold3d `CrossSection` (Apache-2.0), skia-pathops (BSD-3), ffmpeg filters | M | style presets selectable per film; motion blur only on fast shots |
| 1.8 | **Ink-fidelity import plus raster parts:** photo or scan → clean line keeping the artist's texture; mask-based part cutting with overlap seams; pivot and cut suggestions; puppet format v0.3 raster parts in the SVG renderer | numpy, scipy, Pillow (BSD/HPND); next: SAM 2.1 tiny/small (Apache-2.0) for click-to-mask part suggestions (1.8b) | M | a phone photo of a notebook doodle becomes a lint-clean, blinking, waving puppet in under 10 minutes |
| 1.9 | **Hand-made look:** line boil (cycled seeds, deterministic), stepped timing on 12s/8s/6s, paper and medium sets (notebook, sketchbook, whiteboard, chalkboard), ink props and signs | SVG filters; in-house | M | the Sheep & Pig episode re-renders in Doodleberry matching the toolkit's look |
| 1.10 | **Drawing coach:** pre-import checks and advice (limb length, joint gaps, separate eyes, scale) | in-house + agent | S | a drawing that would rig badly gets specific, visual advice before import |
| 1.11 | **Doodle template:** minimal rigs (head, body, arms, tail), with hop, wave, tilt, wag, lean and talk clips | in-house | S | any simple character gets a working clip set without humanoid parts |
| 1.12 | **Native dual-aspect composition:** 16:9 and 9:16 laid out separately from one shot list, same story and timings (pulled forward from 4.4) | in-house | M | both cuts pass frame fill and safe zones with no crop or letterbox |
| 1.13 | **Explainer scene library:** teaching cards, counters, typed consoles, data walls, heatmaps, maps, quote and citation plates, wordmark overlay, camera float | in-house | M | a Myth vs Data film can be built from library scenes plus data |
| 1.14 | **Brand kit:** measured palette (contrast, colour-blind separation, distance from platform UI colours), type system, exclusion rules; generated profile pictures, covers, flyers and print; film templates inherit it | colour-science (BSD-3), Playwright | M | a palette that fails contrast or CVD separation is refused with numbers; a brand change re-themes templates |

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
| 2.14 | **Beat grid and master-to-many cuts:** one BPM grid for picture and sound; edit lists assemble a master render plus inserts into a full film, an episode series, teasers and recaps, with cuts on beats and whole-bar inserts (E25) | in-house; OTIO export; music21 (BSD-3) for scores as data, FluidSynth (LGPL, process) to render them, Tone.js (MIT) to preview | M | one production yields a full 16:9 film and four 9:16 parts with continuous music |
| 2.15 | **Format templates:** Myth vs Data, Dialogue (learner and expert characters, E28), Anniversary, We re-ran it, Wonder story, multi-part series; prediction prompts before reveals | in-house + agent | M | a template plus a brief gives a storyboard that passes the cold-open and reading-time rules |
| 2.16 | **Narration slots:** per-line start and maximum length at 125–145 wpm, with short alternates; the sound-off cut is the master and voices fill slots later (E27) | in-house | S | a voice recorded after release drops in without re-cutting picture |
| 2.17 | **Data-bound visuals and original-analysis films:** analysis scripts in the film folder write the data every chart reads; cached inputs; terms, version and access date recorded | in-house | M | changing the input data re-renders every chart and caption number that depends on it |
| 2.18 | **Layout auto-repair** (E29): the agent fixes frame-fill, safe-zone, type-size and reading-time failures by moving and resizing elements | agent + 0.11 metrics | M | a seeded layout failure is fixed without a human |
| 2.19 | **Cartoon physics** (from the procedural brainstorm): props, ropes and tails simulated in the bake step; target-hitting throws that land at a line-relative time; contacts retimed onto the beat grid; squash, apex holds and stepped timing as art-directable overrides; baked into the keys every renderer reads | Rapier 2D deterministic JS build (Apache-2.0; measured bit-identical reruns, 12 bodies × 300 steps in 14 ms) | M | the props-demo throw is solved, not scripted, and lands in Nib's hand at `mid.start+0.9` after a re-voice; reruns are hash-equal |
| 2.20 | **Motion effects from baked motion:** smear frames, speed lines, dust puffs on landings, impact stars, motion arcs, generated from part velocities and contacts | in-house | M | a hop and a throw get effects with no hand placement, on svg, synfig, lottie and grease-pencil |

## Phase 3: Human interfaces (weeks 14–18)
Goal: artists, directors and reviewers work alongside the agent, and every UI action is a command.

| # | Item | Build with | Effort | Done when |
|---|---|---|---|---|
| 3.1 | **Studio timeline editor:** shot lanes, clip lanes, dialogue lane, live-scrub preview (the web player already renders any frame) | in-house | L | a director re-times a gesture by dragging, and the edit lands in `shots.json` |
| 3.2 | **Storyboard strip** from `shots.json` (one still per shot, notes) and an animatic button | in-house | S | `film.storyboard` writes a strip and contact PDF |
| 3.3 | **IK posing in Rig Canvas:** drag hands and feet; save poses and record short clips | `acting.js` IK | M | a new pose is made by dragging and saved to the puppet |
| 3.4 | **Review room:** frame comments become data edits; a critic re-checks before closing | registry + agent; OpenRV or xSTUDIO (Apache-2.0) as an optional desktop player via the 4.1 OTIO export | M | "raise the arm earlier" on frame 120 is fixed and verified |
| 3.5 | **Act it out:** phone or webcam video → body and face keypoints → joint angles, IK targets, mouth and eye swaps → an action clip | MediaPipe Pose/Holistic/Face (Apache-2.0); rtmlib RTMPose (Apache-2.0) for accuracy | M | a 5-second take becomes a reusable clip in under a minute |
| 3.6 | **Phone-first creator flow:** snap a doodle → confirm cuts and pivots → see it move and talk; plus the drawing request queue (E20) with ghost guides | Rig Canvas, ink import | M | a first-time user goes from photo to a talking clip in about a minute |
| 3.7 | **Production orchestrator and board:** a planning agent spawns one session per film (own workspace and branch), receives checkpoint reports (research, first render, final metrics), keeps the registry, can stop, narrow or relaunch, and merges finished work; escalation when research contradicts the brief; the board shows calendar, status, measurements and verdicts with approve and stop | session tools; registry | L | ten films run in parallel to their posting dates with checkpoint reports and owner approvals (E24) |
| 3.8 | **Content planner:** research sweeps (dated hooks, recent developments, evergreen, tools, original analyses, local) → idea bank → dated calendar with spread rules and lead times; live tracker | agents + registry | M | a quarter's calendar is produced with every spread rule satisfied and every row marked for fact-lock |
| 3.9 | **Title and thumbnail lab and covers:** newcomer-oriented, literally true titles; double-barrel thumbnail text; candidates and polls between true options; deliberate cover frames per cut; back-catalogue retitling | agent + brand kit | M | every film has two true title options, a cover per cut and platform, and passes the packaging truth check |
| 3.10 | **Graph view in Studio:** a node view of a film's data flow (facts → script → shots → renders) with per-node cache state; later the editor for procedural graphs (brainstorm 5.1, 5.5) | React Flow `@xyflow/react` (MIT) | M | clicking a stale node shows why it re-cooks, and re-cooks only downstream |

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
| 4.8 | **Also:** living films from the facts ledger (E12), one-character-every-medium stills for comics and thumbnails (E6), interactive web films | in-house; Typst (Apache-2.0) for print comics and storybooks; Godot (MIT) as an interactive export target | M each | as each lands |
| 4.9 | **Creator outputs:** line-art GIFs, sticker and emoji packs (Telegram, WhatsApp, Giphy, iMessage), merch- and print-ready stills (E23), interactive toy pages | ffmpeg palettegen, libwebp, Lottie/TGS | M | one character exports to four sticker platforms and a print-ready PNG |
| 4.10 | **Series production:** daily-series planner, recurring gags, continuity memory, a posting calendar; teaching mode that turns a pipeline into a tutorial | in-house | M | ten episodes of a series are planned, rendered and scheduled from data |
| 4.11 | **Creator monetisation:** rig and boil-preset templates, loop packs, client explainer packages, with handwriting fonts from the artist's samples | in-house | M | a creator can package and sell a rig template |
| 4.12 | **Trust in public:** a dated corrections log on each film's page (covering titles, thumbnails and social cards, crediting critics) that propagates to every caption (E26); written independence and sponsorship rules | in-house | M | a correction updates the page, the captions and the credits in one command |
| 4.13 | **Analytics loop:** 48-hour metrics checklist, ingestion per platform, a plan that re-ranks itself (E31); a business dashboard (revenue by platform and geography, RPM, catalogue value) | platform APIs where terms allow | M | the next calendar reflects measured performance |
| 4.14 | **Companions and community:** runnable guides that reproduce a film's numbers, carousels, send-a-myth intake, challenges, early-preview reviewers, paired collaborations | in-house | M | each film can ship with a guide; myths sent in reach the idea bank |
| 4.15 | **Publishing connectors and scheduler**, human approval per post; multi-language audio tracks on the main channel | platform APIs | M | a week of approved posts goes out on schedule |

---


## Status (updated as items land)
| Item | State | Commit |
|---|---|---|
| 0.1 Render speed | done: browser per worker, fast capture, frame dedupe, `-tune animation` (116 → 82 ms/frame; 62 when stepped). Static-layer cache still open | 0315203 |
| 0.2 Renderer benchmark | done: keep Chromium (see the gate) | this file |
| 0.3 Schemas and golden tests | done | c06754f |
| 0.4 Incremental re-render | done (6m11s → 32s unchanged) | 0315203 |
| 0.5 Kokoro backend | done: 54 voices, Spanish film re-voiced | 16cf74b |
| 0.6 Re-voice legacy films | done: all eight films now use clean Kokoro voices (`film.revoice`); seven rebuilt and passing QA. screwworm-3d's sources are re-voiced, but its render needs the local CC0 asset packs (Quaternius characters, UAL clips, CMU mocap via tools/blender/cmu_retarget.py), which stay out of git | this commit |
| 0.7 / 0.9 Asset manifest and rights | done | f6a03f4 |
| 0.8 / 0.13 Subtitles, encode profiles, posting package | done | f6a03f4 |
| 0.10 / 0.12 Research gates and critic loop | done | f77ba03 |
| 0.11 Measured layout QA | done (advisory until calibrated per style) | 0a1b167 |
| 1.8 Ink import and raster parts | core done: `puppet.from_ink`, raster parts in the SVG renderer. Open: auto cut and pivot suggestions, multi-character pages, raster parts in other renderers | this commit |
| 1.9 Hand-made look | done: boil, stepped timing, paper set, ink signs and overlays | this commit |
| 1.11 Doodle template | done: template and clip library (hop, wave, tilt, wag, talk, lean, shake) | this commit |
| 1.12 Native dual-aspect | done: `film.render aspect=16:9 / 1:1`, auto re-staging plus overrides, landscape set designs, aspect-aware bubbles, captions and QA | this commit |
| 1.13 Explainer scene library | done: card, counter, console, data-bound bars, quote, citation, wordmark, camera float | this commit |
| 1.14 Brand kit | done: brand.json, brand.check (contrast, CVD, platform distance), brand.assets, opt-in film inheritance | this commit |
| 1.2 Smart bones and constraints | done: controls with driven keys (angles, shifts, swaps, z), look-at, props with parent switching and arcs; shifts in every exporter | this commit |
| 1.1 Bendy limbs | done for vector limbs: arc bend with thickness kept and an attachment correction, in SVG and Grease Pencil; Synfig and Lottie stay rigid. Raster mesh warp done in v0.5 (mesh strokes) | this commit |
| 1.3 Drawing import | done: `puppet.import` (layered SVG, PSD, ORA by layer name; pivots estimated, 9-unit mean error), `puppet.export_layers` (round trip for repainting), `puppet.from_blend` (Blender cut-out rigs: Pepper and Carrot showcase, CC-BY; demo film `pepper-carrot` passes QA). Mesh deformation for raster parts done (puppet v0.5 mesh strokes, smooth skinning). Open: Krita .kra direct | this commit |
| 1.15 Explainer kit 2 (from reference reels) | done: `dbe/player/kit.js` (draw-on paths, pop-in titles, torn-paper signs, growing roots, ground sections, water with level and flow, object faces with lip-sync), `underlays`, Sinhala text everywhere (Noto Sans Sinhala). Open: Sinhala voice (no clean TTS), hand prop, time-lapse growth curves | this commit |
| 2.20 Motion effects | done for SVG: speed lines, landing dust, prop impact stars from the motion (`fx` on a shot). Open: smear frames, motion arcs, effects in other renderers | this commit |
| 2.19 Cartoon physics | first part done: ballistic throws that land at a line-relative time, drops that bounce, roll and spin, bounce rings. Open: multi-body scenes with Rapier, squash on impact, contacts on the beat grid | this commit |
| 1.10 Drawing coach | done: `puppet.coach` (measured joint gaps under bending, pivots, proportions, symmetry, face abilities, scale, ground, layer names) with an annotated image; runs inside `puppet.import` | this commit |
| 1.7 Toon shading and post | done: `style.toon` cel shadows and rim light (SVG), `post` presets (grade, vignette, seeded grain, LUT). Open: cross-dissolves, sub-frame motion blur, toon in other renderers | this commit |
| 1.6 Sets and props | done: 11 new aspect-independent sets (16 total) incl. reservoir cross-section and stage; 2015 Lucide icons (ISC) as a kit element; all in the manifest. Open: map board (Natural Earth + d3-geo), anatomy plates (Servier, CC BY), Kenney prop packs | this commit |
| 1.5 Cast variety | done: `cast.generate` (parametric original characters: build, age, skin, 9 hairstyles incl. hijab, 7 tops, 3 bottoms, accessories), 12 registered cast members, golden pose case. Open: Open Peeps/Humaaans conversion, outfits as swap sets | this commit |
| 1.4 Rig Canvas drawing upgrade | done: perfect-freehand ink with pressure, simplified strokes, gap-closing bucket fill, model sheets (canvas button and `puppet.sheet`). Open: expression boards for drawing swap sets side by side | this commit |
| 2.3 Gesture planner | done: `acting.plan` (prosody-driven beats, aimed points, exclamations, questions, listener gaze/nods/blinks); dialogue-demo acted with no hand-placed clips. Open: semantic gestures from LLM tags, personality profiles (E13), a critic rating against hand-keyed acting | this commit |
| 2.6 Camera grammar | done: `camera_auto` (speaker medium shots, wide shots between, eased; punch-ins on emphasis; handheld; clamped to the set; caption headroom) | this commit |
| 2.7 Foley and spatial mix | done: `foley` (footsteps on contacts, landing and bounce thuds, swishes on fast hands, catch pops), panned by screen position; new step/thud/swish sounds. Open: surface types, Kenney CC0 samples, room reverb per set | this commit |
| 2.8 Visual lint | done: `film.lint` (inside `qa.run`): heads cut by the frame and bubbles over faces (error); hands off-screen, feet cropped in wide shots, faces under captions, IK locked straight, props through heads (warn); tangents (info); frame ranges; `"qa": {"enforce": ["lint"]}` fails the film on errors; regression case `tests/lint/`. Open: true silhouette tangents from the rendered alpha | this commit |
| 2.13 Sound-off cut | done: `film.soundoff` (and `"soundoff": true` in film.render): no voice, lines as bubbles (narration without an on-screen speaker keeps word captions), each line held for reading (170 wpm, at most 2.5x) by a player time warp, cues and captions re-timed; bubbles now laid out after the camera, and bubble shots get headroom in `camera_auto`; foley adds a boing per hop and pen-scratch while kit drawings draw. Open: Kenney CC0 samples; other renderers in the warp | this commit |
| 2.5 Clips, limits, FABRIK | done: 33 clips (humanoid +12: wave_L, celebrate, clap, cross_arms, scratch_head, facepalm, sad, stomp, jump, run, present_R/L); puppet v0.6 joint limits, FABRIK chains with a living wave (generator `tail`, new character Momo), emotion-aware mouth charts, anticipation/overshoot filter; clip blending fixed (gestures override idle per track instead of being halved); `clips-demo` renders identically in SVG, Lottie and Synfig. Open: doodle-template clips; emotion mouth drawings per character | this commit |
| 2.14 Beat grid, master to many | done: `film.beats`, `beat_cuts` (shot changes on bar lines in pauses), `edit.json` + `film.cuts` (full film, `split` episodes, teasers, inserts from other films; cut points on the grid, never inside a line; audio from master stems, crossfaded, -14 LUFS; .srt and OpenTimelineIO per cut). moon-night: one production, a full 16:9 film and four 9:16 episodes plus a teaser, all -14.0 LUFS / -1.6 dBTP. Open: whole-bar title-card inserts; music re-scored per cut with its own ending (now a fade); FluidSynth/music21 scores | this commit |
| 2.1 Phone-level alignment | done for Kokoro (the clean default): the model's own phoneme durations (duration predictor exposed as an output, `kokoro-v1.0-timed.onnx`), calibrated -80 ms against the audio; visemes and word times (DP grouping for run-together words, numbers, abbreviations) from them; Whisper only as fallback. The old method was 70-87 ms off on average and agreed with the true shape on 24-33% of frames; now 25 ms model frames, measured lag 0 ms. Open: CTC (wav2vec2 + forced_align) or MFA for recorded human voices; Piper alignment | this commit |
| 2.2 Lip-sync QA cross-check | done in-house: `lipsync.check` and a `lipsync` check in `qa.run`: each speaker's visemes against first-formant energy of their own voice; fails beyond +-2 frames or below 0.2 correlation (fault injection: 200 ms late, 150 ms early, swapped speakers, stuck mouth all fail). Rhubarb comparison (Preston Blair A-H,X to our shape classes) runs when `DBE_RHUBARB` points at an installed binary; running the downloaded binary was not permitted in this session, so it is untested | this commit |
| 2.9 + 2.18 Self-healing, layout auto-repair | done (rule-based, no agent needed for these): `film.heal` renders, reads QA, layout (advisory too) and lint failures, repairs shots.json and re-renders. heal-demo (seeded: animation on ones, 20 px sign up 0.8 s, title below the safe area, captions at 3.8 words/s) passes all of them in one round (12 per second, title moved 196 px, sign to 26 px and held 4.7 s, re-voiced at 1.27x with shot times anchored to lines); frame fill and cold open are left with a reason (need new content). Open: an agent for repairs that need writing or drawing | this commit |
| 2.4 + 2.11 Acting from prose, gags | done: `acting.direct` reads plain-English directions (on script lines, shots, or passed in): who, when (a word, a line, start/end, then), what (emotions incl. worried, gaze, walks, 16 clip verbs), at whom, how; gags double take, long stare, slow burn, deadpan, button, rule of three. direct-demo is staged from its directions alone and passes QA, lint and lip-sync. Open: a reviewer's rating of the timing; camera beats in gags (push-in on the stare) | this commit |
| 2.12 Rig abilities, rig-aware writing | done: `puppet.abilities` (free vs costly moves with the drawings each needs), `script.rigcheck` (per character: free moves, and exactly which drawings the directions need, with the sentences). direct-demo needs none; recast with the doodle Nib it lists seven | this commit |
| 2.16 Narration slots | done: `script.slots` (per-line start and max at 135 wpm, draft timing for a picture-first cut), `voice.build` fills slots (alt line, then up to 15% faster, overflow reported, slot ends fixed). slots-demo: cut identical with no voice, a first cast, and a later slower cast (alt and speed-up used). Open: recorded human takes (ffmpeg atempo instead of TTS speed) | this commit |
| 2.17 Data-bound visuals | done: `analysis/` scripts with cached sources (terms, version, access date, sha256) write data.json; `{{path|format}}` bindings in shots and script lines, `data_from` charts; `film.data` reports and re-voices/re-renders exactly what changed (shot hashes now cover only in-shot lines and mouth cues). data-demo: one changed input re-rendered 2 of 3 shots and re-voiced 2 lines. Also: lip-sync check pools speakers (robust on short parts; still fails 100 ms offsets), film.heal undoes repairs that do not help | this commit |
| 2.15 Format templates | done: `film.from_template` with myth_vs_data, dialogue (learner/expert), wonder_story, we_reran_it, anniversary, series; prediction prompts with a silent count before reveals; slots, line-relative shots, gated facts; `storyboard.check` (cold open, reading time, unsourced facts). Three storyboards pass both rules before voicing; telescope-talk (dialogue) also passes full QA | this commit |
| 3.1 Studio timeline | done: /timeline page (live-scrub preview, shot, dialogue and clip lanes, drag/resize/add/delete/nudge/undo, snap to words); `timeline.get`, `timeline.edit` (anchored times stay anchored, re-anchor when moved to another line), `film.preview`. Tested by dragging Ravi's point 60 px in a headless browser: shots.json start 1.243 -> 1.8. Open: dragging lines and shots; camera keys lane | this commit |
| 3.2 Storyboard strip, animatic | done: `film.storyboard` (stills from the player, strip.png, contact.pdf with notes and directions), `film.animatic` (stills over the mix or voice), buttons in Studio and the timeline. Made for moon-night, direct-demo, telescope-talk | this commit |
| 3.3 IK posing in Rig Canvas | done: Pose tool (IK hands and feet, head/chest turn, hips with planted feet, expressions), Save pose into `poses`, Key + Save clip into the character's own `clips` (format v0.7, merged by Acting.evaluate), Save to cast via `puppet.save`. Headless test: a dragged pose re-evaluated through the film path puts the hand within 0.1 px of where it was dragged; golden case added. Also fixed: the canvas crashed loading characters without every optional swap shape | this commit |
| 3.4 Review room | done: /review page (frame-pinned notes, frame stepping, live-player fallback), `review.add/list/fix`: notes read into verb/amount/part/character, the responsible clip found and edited via timeline.edit, a critic measures the part's motion before/after and re-runs QA; unverifiable edits are reverted to a person. review-demo: \"raise the arm earlier\" on frame 120 fixed and verified (0.33 s earlier as asked), plus bigger and hold-longer notes. Open: notes about gaze, placement, camera and timing of lines; OpenRV/xSTUDIO via OTIO | this commit |
| 3.5 Act it out | done: `actout.clip` and Studio /actout (webcam record with count-in, or a file): MediaPipe Pose + Face Landmarker (keypoints cached by content), retargeted onto the character's rest pose in image space (spine from hips or the shoulder line, head roll, foreshortened segments bridged, unseen parts left to idle), `arms` angles (default) or reach (hand targets, elbow on the take's side), root travel with foot contacts and planted soles solved onto the ground, eye/brow/gaze keys (mouth with `face: all`), forearms brought in front when the wrist is nearer the lens, keys reduced against the eased curve the player plays (1.5°). Saved as a v0.7 character clip; `film.validate` now accepts character clips. A 5 s phone take became a clip in 17 s through the page; it played by name in a review-demo shot, the bake (exact) and the Lottie export. Self-test in `python -m dbe test`. Open: rtmlib/RTMPose backend, head turn (yaw) and live tracking (E9), multi-person takes, camera-motion compensation | this commit |
| 3.6 Phone-first creator flow, drawing requests | done: Studio /doodle (phone layout): snap a doodle, check the suggested cuts (drag pivots, drop a piece), see it move and talk, keep it in the cast (owner rights, its voice). `doodle.snap` (photo upright, cropped to the ink; closed loops give head and body or one blob, marks inside the head give eyes and mouth, side strokes give arms and a tail, marks above the body ride with the head), `doodle.cut`, `doodle.say` (one line in a Kokoro voice in a separate process, visemes from the model's phoneme timings, a wave on a greeting, a hop on an exclamation), `doodle.keep`; talking mouths (closed, small, mid, wide, O, FV, smile) drawn in the doodle's ink and line weight, drawn over a mouth that touches another line. Drawing requests (E20): `drawing.requests` (from a film's directions or every costly move) with ghost guides on the character's own artboard, `drawing.fulfil` lifts the ink inside the box into the swap shape or part and closes the request only when the rig check agrees. Synthetic cat doodle: photo to talking in 11 s through the page; raised brows drawn over the ghost freed happy and surprised. Also fixed: `cast.add` accepts installed Kokoro voices. Open: pupils, turn views and chains drawn over guides; multi-character pages; polygon editing of cuts | this commit |
| 3.7 Production orchestrator and board | done: `prod.plan/launch/checkpoint/status/stop/narrow/relaunch/decide/approve/merge` and Studio /board (posting calendar, schedule against posting dates with lead days, checkpoint verdicts, final measurements, owner buttons). One git worktree and branch per film; sessions: pipeline (`tools/film_agent.py`: research gate, voice, first shot, full render, one heal round, ledger, commit), claude (`claude -p` with the protocol and director prompt), manual (protocol file for any agent). Checkpoints are measured by the orchestrator in the film's workspace, and the answer carries the verdict, owner instructions and continue/stop. Research that contradicts the brief escalates until the owner proceeds, narrows (added to the brief) or stops. Merge needs approval of a QA-passing final, a finished session and committed work, and refuses changes outside the film. Registry under a file lock (git-ignored). Ten films posting 9-27 Nov went from planned to merged in 19.5 min, at most 3 at once, all QA 7/7, through a seeded crash, a stop and relaunch, and an escalation narrowed by the owner. Also: `shot.render` records the shot hash, so `film.render` reuses it. Open: a Claude Code session run end to end; cloud sessions started from the board; notifications to the owner | this commit |
| 3.8 Content planner | done: `plan.channel/sweep_prompt/ideas_add/ideas/schedule/check/track/brief/posted/quarters` and Studio /plan. Six research sweeps run by agents from canonical prompts (dated hooks, recent, evergreen myths for the weekly series, tools, original analyses with data terms, local); every cited URL fetched (missing sources refused); near-duplicates and same-subject ideas kept out. The scheduler places dated hooks (capped per week), the series, the analysis cadence, the local quota, then open slots (an empty field first); every row gets a start-by and a fact-lock date. An independent check covers 14 rules. The tracker follows briefs, production and the fact gate. `plan.brief` writes the film brief and can put it on the production board (E24). Q1 2027: 100 sourced ideas from six agents, 52 posts, all 14 rules satisfied, every row with a fact-lock date. Open: re-ranking from analytics (E31, 4.13); a maximum local share; topic matching beyond word overlap | this commit |
| 2.10 Speech bubbles | mostly done: say, shout, whisper; voice-synced reveal; collision-aware placement. Open: thought clouds, narration boxes | this commit |

## Decision gates
- **After 0.2:** keep Chromium unless resvg or ThorVG is at least 2× faster on our frames with near-identical pixels.
  **Result (November 2026): keep Chromium.** On pip-park frames, resvg-py 0.5 took 148 ms/frame against Chromium's 68 ms
  (single process, render plus capture), with near-identical pixels (mean difference 0.05). ThorVG was not tested,
  pending the licence check on its Python binding.
- **After 0.5:** if Kokoro has no word timestamps, keep Whisper alignment for Kokoro voices; plan 2.1 as the fix.
- **Before 1.6 and 4.6:** resolve the open licence questions: BodyParts3D, BBC/Pixabay/incompetech, the
  `thorvg-python` binding, sherpa-onnx's espeak code, and the C2PA SDK licence.
- **Before any distribution of Doodleberry as software:** Piper and espeak-ng are GPL. Keep them behind a process or
  service boundary, or replace them.

- **Before enforcing 0.11 as a hard gate:** calibrate the thresholds (frame fill, seams, reading time) on a reference film
  in each style. The playbook's numbers come from flat-paper science films; doodle and cartoon styles may need their own.
- **Publishing (4.15):** never post without a human approval per post; connectors only where platform terms allow automation.
- **Procedural layer (brainstorm 5A/5B/5C):** 5A starts only after 2.19 and 2.20 are used in two films; 5B only when a
  film needs a 3D set or effect the 2D kit cannot make, with Blender kept behind its process boundary; 5C only with a
  confirmed GPU budget and each solver proved small on CPU first. Avoid: ToonCrafter (generative video), Stable Audio
  Open (revenue-capped licence), Depth Anything Base/Large/Giant (NC), pymeshlab in-process (GPL-3).
- **Formats (2.15):** the refutation and dialogue evidence comes from introductory university physics; measure retention on
  our own films before treating it as a law for every audience.

## Brainstorm later (not committed)
- `docs/brainstorm/procedural-houdini.md`: a procedural and simulation layer (Houdini-like, or beyond, for cartoons).
  Researched in November 2026: licences checked, and the building blocks tried headless on CPU (Geometry Nodes from
  code, deterministic Rapier 2D, Bullet, Manifold, OpenUSD, music21; all worked, with hash-equal reruns where tested).
  Outcome: 2.19 cartoon physics, 2.20 motion effects and 3.10 graph view joined the plan, and tool candidates were
  added to 1.6, 1.7, 1.8, 2.14, 3.4 and 4.8. The rest is a three-track sketch (5A procedural 2D, 5B procedural 3D in
  Blender, 5C in-house solvers), each behind a gate below. It stays unscheduled.

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
