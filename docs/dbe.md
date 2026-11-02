# dbe: the Doodleberry backend engine

One command registry for people and agents, reachable three ways:

| surface | how | for |
|---|---|---|
| CLI | `python -m dbe <command> '<json args>'` | scripts, CI, quick tests |
| HTTP + Studio | `python -m dbe serve [port]` then http://127.0.0.1:8770 | people (Studio UI) and HTTP clients: `GET /api` lists the commands, `POST /api/<command>` runs one (`?async=1` returns a job id) |
| MCP (stdio) | `python -m dbe mcp` | agents: Claude Code, Claude Desktop or any MCP client. Tool names use `_` for `.` (`film_render`) |

Register it with Claude Code: `claude mcp add doodleberry -- python -m dbe mcp` (run from the repo root, with the
environment variables below).

## Environment
| variable | meaning | default |
|---|---|---|
| `DBE_PY` | Python that has piper-tts, faster-whisper, numpy, scipy, pyworld (voice and audio) | the current Python |
| `DBE_VOICES` | folder of Piper `.onnx` voices | `~/voices` |
| `DBE_BLENDER` | Blender 5.x binary (Grease Pencil renderer) | `blender` on PATH |
| `DBE_GP_SAMPLES` | EEVEE anti-aliasing samples for Grease Pencil | 4 |

## Commands
`python -m dbe engine.commands` prints the live list with argument schemas. Summary:

- **engine.info**: versions of every tool found (node, ffmpeg, synfig, blender, piper...).
- **film.create / film.get / film.write**: make a film folder, read it, write brief.md, facts.json, script.json, shots.json or score.json.
- **voice.build**: Piper TTS, Whisper word alignment and viseme lip-sync; writes `timing.json`. Passes the voice licence gate first.
- **voices.list**: voices with licence status and install state: Piper voices from `voices/registry.json`, plus every installed Kokoro voice (`kokoro:<name>`, Apache-2.0, 54 voices in 9 languages). Filter with `{"language": "Spanish"}`. Use a Kokoro voice in script.json like any other: `"voice": "kokoro:ef_dora"`.
- **cast.list / cast.add / puppet.lint**: the cast library. `cast.add` lints a puppet, accepts only open licences,
  checks its voice is clean, records author, licence, provenance and a content hash in `cast/index.json`, and appends
  to `cast/provenance.jsonl`.
- **film.credits**: credits built from what the film uses (characters with their rights, voices and licences, renderers, and assets from `assets/manifest.json`).
- **film.package**: posting package in `build/package/`:
  - `posts.md` with per-platform captions (takeaway first, hashtags last), a YouTube title, description and chapters, a pinned sources comment, alt text, an engagement prompt, credits and a 48-hour checklist;
  - `cover.png`, a chosen frame with cover text fitted to the safe area.

  It reads `shots.json` `brief` (title, takeaway, hook, hashtags, cover_text, cover_t, prompt, post_date, part/parts, client).
- **research.check**: the research gate (sources, two independent sources for numbers, research log, fact-check clearance, safety clearance for sensitive briefs); renders refuse to start while it reports errors. See `docs/research-standard.md`.
- **critic.pack / ledger.add**: review packets for fresh critic agents (role prompts in `dbe/critic/`), and the ledger of gates and critic rounds with before/after QA numbers.
- **asset.check**: every tracked third-party file must be listed in `assets/manifest.json`.
- **Rights:** `cast.add` takes `rights` = open (an open licence), owner (your own IP, with the owner named) or client (made for a client, with owner and terms). Client-work characters render only in films whose `brief.client` matches.
- **Delivery:** finals use `dbe/profiles.json` master (H.264 High, CRF 18, AAC 48 kHz 320 kb/s, faststart, ≤100 MB) and come with `captions.srt` and `captions.vtt`.
- **shot.render**: render one shot with its renderer: `svg` (headless Chromium), `synfig` (Synfig CLI), `grease-pencil` (headless Blender), or `lottie` (lottie-web).
- **film.render**: render the shots whose inputs changed (a content hash per shot covers the shot, puppets, clips, lip-sync data and renderer code; `only` forces a list), join them, burn in word-timed captions, mix score, effects and voice (−14 LUFS), mux, then run QA.
- **qa.run**: the measured quality bar plus contact sheets, plus layout checks (`dbe/layout_qa.py`):
  - **frame fill:** bare-ground share per scene, sampled every 3 s on the final encode;
  - **text:** every word inside the platform-safe area (9:16: x 64–960, y 200–1560; 16:9: 5% title-safe), and minimum type size;
  - **reading time:** static blocks stay up for at least words ÷ 3 + 1 s; caption flow under 3.2 words/s;
  - **seams:** frame difference at cuts;
  - **cold open:** a character in frame one, and the first words by 1.5 s;
  - **mix:** effects below music; percussive cue onsets within one frame.

  Every film gets the numbers. A layout check fails a film only if the film opts in with
  `"qa": {"enforce": ["text_in_safe_area", ...], "fill_max": 0.4}` in shots.json; thresholds come from flat-paper
  explainers and are calibrated per style first.
- **test**: golden-frame regression test (`tests/golden.json`); `{"update": true}` rewrites the goldens.
- **film.validate**: schemas plus reference checks; runs automatically on `film.write` and before renders.
- **export.lottie / export.synfig / export.web**: a Lottie JSON (with the set embedded as an image), an editable Synfig project, or an interactive web player.
- **film.localize**: copy a film into another language: swap voices, replace lines, re-voice and re-render. Timing re-derives from the new words.
- **film.retime**: re-derive shot boundaries from line references after a voice change.
- **variants.hooks**: render alternative openings (shots.json `hooks`) joined to the rest of the film.

## A film as data: `shots.json`
```json
{"title": "Pip in the park", "size": [1080, 1920], "fps": 30, "captions": true,
 "shots": [
  {"id": "s1", "renderer": "svg", "set": "park", "start": 0, "end": 5.7, "start_line": "hi",
   "cast": [{"puppet": "puppet/examples/pip.puppet.json",
             "place": [[0, {"x": -80, "y": 1500, "s": 0.95}], [1.5, {"x": 540, "y": 1500, "s": 0.95}]],
             "timeline": {"clips": [{"clip": "walk", "start": 0, "end": 1.5}, {"clip": "wave_R", "start": "hi.start-0.2", "end": "hi.start+1.38"}],
                          "visemes_from": "pip", "view": [[0, "front"], ["hi.end", "side"]], "springs": true}}],
   "cues": [{"t": "hi.start+2", "type": "chime"}], "camera": [[0, [540, 960, 1]], [4, [540, 900, 1.15]]]}],
 "hooks": {"question": {"set": "plain"}}}
```
- `renderer` routes each shot. All renderers read the same baked animation (`tools/bake.mjs`): per frame, each part's
  angle, root offset, swaps, view and squash.
- Times can be seconds or line-relative (`"mid.start+0.9"`), resolved against `timing.json` on every read.
- Sets live in `sets/sets.js` (plain, park, clinic, cutaway); `set_opts` recolours them.
- Captions are one film-level pass (`dbe/captions.py`, ASS through libass): chunks of 3 words with the spoken word
  highlighted. `caption_style` in shots.json overrides font size, colours and position.

## Hand-made look, bubbles and ink puppets
- **`puppet.from_ink`:** a photo or scan of a drawing plus a parts spec (polygons, pivots, swaps) becomes a raster-part
  puppet in the artist's own line (`dbe/ink.py`). See `puppet/examples/make_nib_photo.py` for a full example.
- **Shot `style`:**
  - `{"boil": {"fps": 12, "amount": 5, "freq": 0.022}}` makes characters, bubbles and signs shimmer like redrawn frames;
  - `{"step": 12}` animates on 12s;
  - `{"shadow": false}` drops ground shadows.
- **Sets:** `paper` (ruled notebook) alongside plain, park, clinic and cutaway.
- **Overlays:** `[{"type": "sign" | "text", "text", "x", "y", "size", "start", "end"}]`, drawn in the same ink.
- **Speech bubbles:**
  - `"bubbles": true` turns each voiced line into a bubble from its speaker (cast `speaker` ids);
  - script lines can set `style` (say, shout, whisper) and `bubble` (on-screen wording, revealed over the spoken line);
  - placement avoids signs, overlays and the characters;
  - `extra_bubbles: [{who, text, start, end, slow}]` adds silent bubbles.
- Fonts: Fredoka (captions) and Patrick Hand (bubbles, signs), both OFL.

## Aspect ratios (one film, several native cuts)
- `film.render {"name": ..., "aspect": "16:9"}` (or "1:1") renders the same film for another frame: same script,
  voice, timings and acting.
- Re-staging recomposes each shot: characters keep their share of the frame height (1.3× in wide frames) and spread
  wider; off-screen entrances stay off-screen; overlays and camera keys are mapped too.
- Every set has its own landscape design rather than a crop.
- Fix any shot by hand in shots.json:
  `"aspects": {"16:9": {"shots": {"s1": {"cast": [{"place": {...}}], "overlays": [...]}}}}`
  (cast entries merge by index).
- Output goes to `build/final_16x9.mp4` and `captions_16x9.srt`. The derived film folder `films/<name>--16x9/` is
  rebuilt each time and is not committed.
- Bubbles, captions and QA use the right safe area for each aspect.

## Explainer scene library (overlays)
Timed with `start` and `end`, line-relative allowed. Sizes default to the aspect's type minimums.
- **`card`:** `{title, body, x, y, w}`, a definition card.
- **`counter`:** `{from, to, prefix, suffix, decimals, label, duration}`, a number counting up.
- **`console`:** `{lines, cps}`, typed commands. Lines starting with `>` are output and `!` errors.
- **`bars`:** `{data | data_from: "key" in the film's data.json, unit, title, colors, max}`, an animated bar chart
  whose numbers come from data.
- **`quote`:** `{text, by}`.
- **`citation`:** `{text}`, small mono on a soft plate, inside the safe area.
- **`wordmark`:** `{text, accent_text, accent}`.
- **Signs and text:** as before.
- **`style.float: true`:** a slow camera drift and breath, so no frame is dead.

Fonts: Fredoka (body), Atkinson Hyperlegible Mono (consoles, citations), Patrick Hand (bubbles, signs), all OFL.
`films/explainer-demo` uses all of these and passes the research gate.

## Brand kit
- `brand/brand.json` holds the palette, accents, the text pairs the brand uses, fonts, the wordmark, caption colours and
  exclusion rules.
- **`brand.check`** measures:
  - WCAG contrast for every declared text pair;
  - colour-blind separation of the accents (Machado 2009 simulation, CIEDE2000, checked against the Sharma reference
    pairs);
  - distance from Facebook, LinkedIn, YouTube and TikTok interface colours.

  It found the original blue accent nearly identical to LinkedIn's blue (ΔE 2.0) and that a green accent would merge
  with the berry for colour-blind viewers (ΔE 2.3). The palette now uses violet `#5a3fc0` (separation 20.2, at least
  15.7 from every platform colour).
- **`brand.assets`** writes profile tiles (720/400/180) and YouTube, Facebook, LinkedIn and story covers with text
  inside each platform's safe area, plus QA overlays. It refuses a palette that fails the check.
- **Films opt in** with `"brand": true` in shots.json: caption colours, the wordmark and explainer accents come from the
  brand, and explicit values in a film still win.

## Render speed
`tools/three/run3d.mjs` runs one browser process per CPU on contiguous frame ranges, uses Chrome's fast capture, and
encodes with `-tune animation`. It hashes each frame's SVG and links repeats instead of capturing them. Shots animated on
12s (`style.step: 12`) reuse about 60% of frames. Measured on pip-park shot 1 (171 frames, 4 CPUs): 116 → 82 ms/frame,
and 62 ms/frame when stepped.

## Renderer notes
The set is always drawn by the SVG player, so clouds drift, the camera works and characters keep a ground shadow.
Synfig and Grease Pencil draw only the characters, with alpha, and ffmpeg composites them over the set video. Lottie
exports embed the set as a still image (`background: none` exports the characters alone).
Camera keys (`[[t, [cx, cy, zoom]]]`) are folded into each character's baked position and scale, so a push-in
frames the composited characters exactly like the set.

- **svg**: fastest and the reference look (about 25 s for a 5 s shot).
- **synfig**: a `.sif` with one group per part and animated transformations; editable afterwards in Synfig Studio.
- **grease-pencil**: per-frame strokes in Blender 5.x, rendered by EEVEE at half resolution and upscaled. About 4 s
  per frame on software Vulkan. Blender 5.2 quirks handled in `dbe/blender_gp.py`:
  - a stroke fills only when its `fill_id` is non-zero;
  - new materials carry a Principled node tree that must be cleared;
  - GP objects are lit unless `use_grease_pencil_lights` is off;
  - GP colours are linear.
- **lottie**: one shape layer per part, parented like the skeleton, rotation keys about the pivots, swaps and views
  as hold-keyed opacity.

## Licences
- `voices/registry.json` gates voices: only `clean` voices build unless a film's script.json sets
  `"allow_restricted_voices": true`, which is for internal tests only.
- `docs/feature-map.md` is the full feature map and build order.
- `docs/oss-research.md` lists vetted libraries, models and assets, plus the ones to avoid.
- Piper itself (piper-tts ≥ 1.3) and espeak-ng are GPL-3.0. They run as a separate process, which is fine for a
  service, but it matters if Doodleberry is distributed as software.

## Drawing import (plan 1.3)
Three ways in, one way out:

| Command | Takes | Gives |
|---|---|---|
| `puppet.import` | a layered `.svg` (Inkscape layers or groups), `.psd` or `.ora` (Krita, GIMP, MyPaint export) | a vector (SVG) or raster-part (PSD/ORA) puppet |
| `puppet.from_blend` | a recipe (`cast/recipes/*.json`) pointing at a Blender cut-out rig | a raster-part puppet with springs, phonemes, blinks, brows and hand poses |
| `puppet.export_layers` | any puppet | a layered `.svg`, `.ora` or `.psd` for an artist to repaint (then `puppet.import` it back) |

**Layer names** map to the template: `head`, `upperarm_R`, `Upper arm R`, `lower leg left`; swap shapes as `mouth/closed`
or a `mouth` group of shape layers (hidden shape layers are kept); `pivot:<part>` and `anchor:<name>` dots; a
`ground` line; `guide`, `sketch`, `ref`, `background` layers skipped. In SVG, colours become palette slots named after
the parts they paint (or `data-slot` attributes), and transforms, `<use>`, basic shapes and gradients are flattened.

**Pivots** come from markers when present, else from the drawing: a part that shares its parent's joint in the
template takes the parent's pivot; otherwise the centre of the rounded cap at the near end of whichever of the two
shapes is limb-like (checked against their overlap). Parts that do not overlap their parent are reported, because
the joint will gap. Measured on Pip through SVG and ORA: mean pivot error 9 units on a 1000-unit artboard
(`python -m dbe test '{"film": "imports"}'` runs both round trips).

**Blender cut-out rigs** (`dbe/blender_cutout.py` inside Blender, scripts off; `dbe/cutout_import.py` outside):
- every rendered mesh is flattened to front-view triangles with UVs and depth, and rasterised from its texture (no
  renderer; 2.7x texture slots are matched by name cues and UV alpha coverage, or set in `spec.materials`);
- meshes land on template parts by the bone that carries them (screen right = template R); skinned meshes are split by
  vertex weights with overlap at the joints; every mesh keeps its own depth as a child layer;
- each deforming bone of a chain that is not a template part (hair locks, skirt panels, a ponytail, a tail) becomes its
  own spring part, so meshes weighted along the chain bend smoothly; skinned meshes are subdivided once and their
  weights diffused (`mesh_subdivide`, `mesh_smooth`) so bends are arcs, not kinks;
- `keep_pose` in a recipe keeps chosen bones in the pose saved in the file (Carrot's tail curl) for the base state;
- variants (bone poses, actions, shape keys) become swaps: sprite-sheet lips and hands, lid planes and shape-key
  blinks, brow controls. Region patches carry jaw and lid deformation; mouth patches keep only what lies in front of
  the pupils, so gaze still works.

Third-party rigs stay out of git (`assets/external/`, `cast/external/`); the recipe and its credit line are committed,
and `assets/manifest.json` "external" records licence and source. Pepper and Carrot (Nikolai Mamashev, after David
Revoy's Pepper&Carrot, CC-BY 4.0) are the showcase (`cast/recipes/pepper.json`, `cast/recipes/carrot.json`). Skinned meshes that span several parts become v0.5 mesh strokes (smooth knees, hips, skirts); single-bone
meshes stay rigid layers. Limit: raster and mesh parts render in the SVG renderer only.

## Explainer kit 2 and Sinhala text (from the reference reels)
`dbe/player/kit.js` adds elements for history, science and motivational shorts. Put them in a shot's `overlays`
(in front of the cast) or the new `underlays` (behind it). All are pure functions of time, seeded where random, and
have a little idle life once settled (no dead frames).

| Type | Does | Key fields |
|---|---|---|
| `draw` | paths draw themselves, then optionally fill | `paths`, `duration` or `until`, `stagger`, `stroke`, `width`, `fill` |
| `title` | bold outlined words pop in one by one | `text`, `y`, `size`, `per_word`, `color`, `outline` |
| `paper` | torn-paper sign with tape; `[bracketed]` words in the accent colour | `text` (lines), `y`, `size`, `accent`, `rotate` |
| `roots` | a root system grows from a point (red taproot optional) | `x`, `y`, `depth`, `levels`, `branches`, `spread`, `seed`, `until`, `main` |
| `section` | ground strata for cross-sections, with pebbles | `y`, `layers: [{h, color, pebbles}]`, `seed` |
| `water` | a water body with a moving surface, a level that can change, flow lines along paths | `x`, `w`, `level: [[t, y]...]`, `bottom`, `flows: [{path, speed}]` |
| `face` | a face for any object: eyes, pupils, brows, mouth; lip-sync from a speaker; blinks, gaze, moods | `x`/`y` or `attach: {cast, part, at}`, `speaker`, `look`, `mood`, `s` |

`until` (like `start`, `end` and `t`) may be line-relative, so growth can finish exactly when a line starts.
Text in every element, and in bubbles, cards and captions, may be Sinhala: font stacks fall back to Noto Sans Sinhala
(OFL, `engine/fonts/`) per glyph, and the page waits for it to load. `films/kit-demo` uses every element.
Gap: no clean Sinhala text-to-speech voice exists yet (the open MMS model is non-commercial), so Sinhala films are
sound-off with music, or use a recorded human voice.

## Motion effects (plan 2.20)
`"fx"` on a shot turns on effects computed from the motion itself (`dbe/player/fx.js`), so nothing is placed by hand
and any frame renders on its own:
- `speed_lines: true | {"parts": ["hand_R", "hand_L"], "min": 650}`: three tapered strokes trail a part whose speed in
  the frame passes `min` px/s;
- `dust: true | {"min_drop": 14}`: puffs at the feet when a character lands (its hips decelerate sharply after a drop);
- `impacts: true`: a star burst where a prop arrives at the end of its travel (a catch or a drop).
Off by default, so existing films are unchanged. `films/fx-demo` is the props demo with all three on.

## Cartoon physics for props (plan 2.19, first part)
A prop's attach key can ask for physics (SVG player; deterministic, so frames stay pure):
- `"flight": "ballistic"`: a true gravity arc from the previous parent to this target, landing exactly at the end of
  `travel`, or at `"arrive"`, which may be line-relative (`"arrive": "catch.end+0.45"`): the catch stays on the words
  after re-voicing or translation.
- `"drop": {"floor": y, "x": x, "e": 0.55, "roll": 0.75}`: released at the key time, the prop falls, bounces with
  restitution `e`, rolls towards `x` and spins as it rolls. With `fx.impacts` on, each bounce draws a ring.
`gravity` (px/s², default 2600) is set per prop. Multi-body scenes (stacks, tumbling objects) are the next step, with the
deterministic Rapier 2D build measured in the brainstorm.

## Drawing coach (plan 1.10)
`puppet.coach` checks a character (a puppet, or a layered drawing before import) and returns advice with measured values
and an annotated PNG (problems circled and numbered): missing parts and swap shapes; joints that do not overlap their
parent, or open a gap when bent (each joint is bent +-50 degrees and the hole beside it measured); pivots outside their
drawing; upper-to-lower limb proportions and left/right mismatch; eyes, pupils and mouths needed to blink, look and
lip-sync; scale on the artboard and feet on the ground line; layers the importer could not place. `puppet.import` runs
it automatically and returns the advice with the puppet.

## Toon shading and finishing (plan 1.7)
- **Toon shading** (`style.toon` on a shot: `true` or `{"dir": [-0.6, -0.8], "d": 11, "shade": "#2a1a10", "opacity": 0.26, "rim": 0.3}`):
  every filled vector shape gets a cel-shadow band on the side away from the light (and an optional rim light towards
  it). Pure SVG: the shape is clipped to itself and repainted shifted towards the light; the light stays fixed in the
  world as parts rotate; outlines are drawn last. Raster and mesh parts already carry their painted light.
- **Finishing** (`"post"` in shots.json: `crisp`, `film`, `warm`, `cool`, `paper`, `noir`, or
  `{"preset", "grade": "<ffmpeg filters>", "vignette": 0-1, "grain": 0-20, "lut": "file.cube"}`): applied to the
  joined picture before captions, so text stays crisp; grain uses a fixed seed. Grain costs file size (fx-demo: 2 MB
  to 10 MB).
Open: cross-dissolves between shots (they change timing), sub-frame motion blur (needs a second render pass).

## Sets and icons (plan 1.6)
`sets/more.js` adds eleven sets drawn in code, each aspect-independent (`draw(t, opts, W, H)`, `floorAt(W, H)`), with a
little ambient life: `kitchen` (kettle steam), `classroom` (`opts.board`: chalkboard lines, any script), `office` (city
window), `street`, `farm` (crop rows, for plant explainers), `bedroom` (`opts.night`), `forest` (parallax depths), `lab`
(bubbling flasks, live monitor), `night` (twinkling stars), `reservoir` (an earthen bund in cross-section,
`opts.level` 0-1, `opts.paper` for an ink-on-paper look) and `stage` (presenter spotlight). With the five originals
that is 16 sets. Icons: every Lucide icon (2015, ISC, `assets/icons/lucide.js`) as a kit element
`{"type": "icon", "name": "droplets", "x", "y", "size", "color", "badge"}` that pops in.

## Character generator and cast (plan 1.5)
`cast.generate` makes an original, fully rigged humanoid from a short spec and registers it (CC0, the spec recorded as
provenance): `build` (slim, average, broad), `age` (child, teen, adult, elder), `skin`, `hair` (short, bob, long, curly,
bun, ponytail, spiky, bald, hijab), `top` (tee, shirt, hoodie, sweater, jacket, dress, overalls), `bottom` (trousers,
shorts, skirt), `shoes`, `eyes`, `accessories` (glasses, beard, moustache, freckles, earrings, tie). Every character gets
the template parts, blink, pupils with iris colour, four brows, eight mouths, hand poses, a `turn` control and springy
hair, so it works with every clip and acting tool. `cast/generated/specs.json` holds the starting cast of twelve (Ama,
Ravi, Mei, Olu, Sana, Kofi, Lena, Tomas, Nimal, Zara, Ike, Priya); all pass the drawing coach with no warnings.
Strokes may set `"rule": "evenodd"` for shapes with holes (the hijab's face opening).

## Rig Canvas drawing upgrade and model sheets (plan 1.4)
The Rig Canvas (`puppet/canvas/index.html`) now has:
- **Ink** strokes from perfect-freehand (MIT, vendored): pen pressure when there is a pen, speed-simulated pressure with a
  mouse; outlines simplified (Ramer-Douglas-Peucker) so drawings stay light. Fill shapes are simplified the same way.
- **Bucket**: click inside an area outlined in ink and it fills with the selected palette slot; gaps up to about 10 px in
  the outline are closed for you, the fill is tucked under the ink, and an open outline is refused with a message.
- **Sheet**: a model sheet of the character (rest, wave, turned both ways, every drawn view; every mouth, brow, eye state
  and gaze close up), downloadable as SVG. `puppet.sheet` renders the same sheet to PNG (`tools/sheet.mjs`,
  `puppet/loader/sheet.js`).

## Gesture planner (plan 2.3)
`acting.plan` makes every speaking cast member act from the script and the voice, with no hand-placed clips. Emphasis
per word comes from the recorded voice (loudness, pitch via WORLD, length per letter, as z-scores within the line):
beats land on the most emphasised words (at most one every 0.9 s); one point per line on a pointing word ("you",
"this", "look"...), aimed at the listener (`point_R` or the new mirrored `point_L`); open palms on an exclamation's
strongest word; a shrug (humanoid) or tilt (doodle) ending a question. Listeners look at the speaker, nod after each of
their lines and blink on their pauses. Gesture clips get weight 3 so they read over the idle loop. Generated clips are
tagged `"auto": true` and replaced on each run; hand-placed clips are kept. `films/dialogue-demo` (Ravi and Priya,
classroom) is acted entirely this way.

## Camera grammar (plan 2.6)
`"camera_auto": true | {"zoom": 1.45, "zoom_single": 1.9, "medium": 0.62, "punch": 0.05, "handheld": 0.3, "ease": 0.6}` on a shot
without camera keys frames it automatically, as a pure function of time: a waist-up medium shot on whoever is speaking
(from 0.3 s before the line), a wide shot fitting the whole cast otherwise, eased between; small punch-ins on emphasised
words (long or exclaimed); seeded handheld drift; clamped so the frame never leaves the set; heads kept high, with room
below for captions. Explicit `camera` keys always win.

## Automatic foley (plan 2.7)
`"foley": true` in shots.json adds sound cues found in the motion itself (`window.FOLEY` in the player, run by
`tools/foley.mjs` during `film.render`): a footstep each time a walk clip's foot contact turns on, a thud when a
character lands (hips decelerating after a drop) and on each bounce of a dropped prop (quieter each time), a swish when a
hand passes 1400 px/s, and a small pop where a prop is caught. Each cue is panned by its screen position. New
synthesised sounds in `engine/audio.py`: `step`, `thud`, `swish`; any cue may carry `pan` (-1 left .. 1 right).

## Visual lint (plan 2.8)
`python -m dbe film.lint '{"name": "FILM"}'` plays the film in the player (`window.LINT`, run by `tools/lint.mjs`,
every 3rd frame) and reports picture problems in screen space, camera included, as frame ranges in `build/lint.json`:
- **error**: a head cut by the frame while the body is in shot; a speech bubble covering a face;
- **warn**: a hand leaving the frame; feet cropped in a wide shot (camera zoom under 1.05, where nothing should be
  cropped); a face in the caption band; an arm locked straight because its IK target is out of reach; a prop inside
  the head of someone who is not holding it;
- **info**: a silhouette just touching the frame edge, or two characters just touching.

Characters who are wholly out of shot (the camera is on the other speaker) are skipped, and one-sample warnings
(a camera move passing by) are dropped. `qa.run` (so also `film.render`) runs the lint and reports the counts as
`lint`; it is advisory unless shots.json says `"qa": {"enforce": ["lint"]}`, which fails the film on any error.
`python -m dbe test` includes `tests/lint/broken_staging.json`: the dialogue demo staged badly on purpose, and each
listed check must fire.

## Sound-off cut (plan 2.13)
Most viewers scroll with the sound off, so every film can ship a second cut made for reading.
`python -m dbe film.soundoff '{"name": "FILM"}'` (or `"soundoff": true` in shots.json, which makes `film.render`
build it too) writes the derived film `FILM--soundoff` and copies its render to `build/final_soundoff.mp4`:
- no voice: music and effects only (`score.json "voice": false` in the derived film; the music is not ducked);
- every line spoken by someone on screen becomes a speech bubble; narration with nobody to speak it keeps the
  word-timed captions (`"caption_lines"`);
- each line is held long enough to read: 0.4 s plus its words at `wpm` (default 170), at least 1.2 s, at most
  `max_stretch` (2.5) times its voiced length. Lines that still fall short are reported (`short_by_s`).

The hold is a time warp, not a freeze: shots.json `"timewarp": [[cut time, film time], ...]` makes the SVG player
render on the cut's clock and show the film at the warped time (`window.TIMEWARP`), so a held line plays its
acting slower instead of stopping. Effect cues and captions are re-timed through the same warp. Only SVG-player
shots can be warped for now.

Speech bubbles are laid out in screen space after the camera (they used to be drawn in the world and could be
zoomed out of frame), and in shots with bubbles `camera_auto` frames singles less tight (`zoom_bubble`, 1.5) with
the head top at about 31% of the frame, leaving room for the bubble above it.

Move-bound sound accents, added to automatic foley: a boing each time a character's hips leave the ground fast
(`"foley": {"hop": "swish"}` or `false` to change it), and a pen-scratch bed (`scratch`, synthesised, with a
duration) while a kit `draw` element draws itself (`"sound": false` on the element, or `"foley": {"scratch": false}`).
Any cue may carry `dur` for sounds that last.

## Clip library, chains and principles (plan 2.5)
The humanoid library has 23 clips (doodle 10): idle, walk, run, jump, nod, shrug, think, surprised, wave_R/L,
point_R/L, present_R/L, talk_beat, talk_open_palms, celebrate, clap, cross_arms, scratch_head, facepalm, sad, stomp.
Jump, run and stomp carry foot contacts, so foley (step, landing thud, hop boing) and dust find them.

Puppet format v0.6 (puppet/spec/puppet-format.md) adds joint limits, FABRIK chains, emotion-aware mouth charts and
an anticipation/overshoot filter, all inside `Acting.evaluate`, so the bake, `dbe/geom.py` and every exporter get them
from the baked angles. The generator takes `"tail": {"segments", "length", "color", "color2", "wag", "spikes"}`;
Momo (cast/generated/momo) wears a dino hoodie with a six-segment tail. In a shot timeline:
`"chains": {"tail": [[t, [x, y]]]}` (reach), `"emotion": [[t, "happy"]]`, `"principles": {"snap": 0.35}`.

Clip blending changed: a gesture at weight 1 now plays at full size over idle (foreground clips override the base
layer per track) instead of being averaged with it. The gesture planner's weight 3 still works. `films/clips-demo`
shows all of it and renders the same in SVG, Lottie and Synfig.

## Beat grid and master-to-many cuts (plan 2.14)
A production is rendered once per aspect (the master: `film.render`, plus `film.render` with `"aspect": "16:9"`) and
cut many ways from it.
- **Grid:** `python -m dbe film.beats '{"name": "FILM"}'` gives the score's beats and bars (from `score.json` bpm and
  offset) and how far each shot change and line start sits from them. `"beat_cuts": true` in shots.json moves every
  shot change onto the bar line in the pause it falls in (else the nearest beat, never into a line), so scene
  changes, episode splits and music phrases coincide.
- **Edit list:** `films/FILM/edit.json` declares the cuts:
  ```json
  {"cuts": {"full": {"aspect": "16:9", "ranges": "all"},
            "ep": {"aspect": "9:16", "split": 4},
            "teaser": {"aspect": "9:16", "ranges": [["m1.start", "m1.end"], ["m5.start", "p3.end"]]},
            "recap": {"ranges": [{"film": "other-film", "from": "bar:2", "to": "l3.end"}]}}}
  ```
  Range ends are seconds, `bar:N` or line-relative times. Each is snapped outward: out of any spoken line, then onto a
  bar line in that pause, else a beat, else the middle of the pause. `split` makes N episodes at the scene changes
  (or the longest pauses nearest to equal parts). A range from another film is an insert, cut on that film's grid.
- **Assembly:** `python -m dbe film.cuts '{"name": "FILM"}'` (`plan_only` to see the cut points, `only` for some
  cuts) writes `build/cuts/<cut>.mp4`, a `.srt` on the cut's clock and an OpenTimelineIO `.otio` edit (Timeline.1
  JSON, no library needed) for finishing in an NLE. Picture comes from the master render. Audio comes from the
  master's mixed stems (voice, music, effects at their mixed levels, so each segment sounds as it does in the master),
  with equal-power crossfades at joins, the music faded in when a cut starts mid-score and out over the last 0.9 s,
  levelled to -14 LUFS with the master limiter. Each cut reports its loudness and true peak.

`films/moon-night` is the test production: a four-scene story made once, cut into the full film at 16:9, four 9:16
episodes and a teaser.
