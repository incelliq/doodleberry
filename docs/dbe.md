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
  With a `titles.json`, the package uses its chosen title, re-runs the truth check on it (`title_true`) and lists the
  covers per cut and platform.
- **Title, thumbnail and cover lab** (plan 3.9, WP-07; `dbe/packaging.py`):
  - **title.check**: the packaging truth check. A title or a double-barrel thumbnail (top and bottom, at most 4 words
    and 18 characters each) may not claim what the film does not support (its fact claims and narration): every
    number must be in them (counts and years exactly), absolutes and superlatives (always, never, only, first, cure,
    deadliest, ...) must be said of the same subject, and a causal claim stated rather than asked needs a fact or line
    on the same subject that is not negated; one the film negates is *contradicted*. A myth film may ask its myth or
    deny it, never state it. Plus the newcomer check: at most 60 characters, no unexplained acronyms, few long words,
    no insider wording (episode numbers, we, our, again, unless quoting the film's own line), no emoji. It is a
    mechanical floor; the writing agent reads the facts on top of it.
  - **title.propose**: mechanical candidates (the film's title and its own questions) with their checks, and the brief
    for a writing agent; **title.set** records candidates in `films/<name>/titles.json` with their checks (failing
    ones are kept with the reason) and the chosen title and thumbnail, which must pass.
  - **cover.make**: for every finished cut (master, sound-off, episode and teaser cuts, other aspects) and every
    platform in `dbe/profiles.json`, the best frame of the cut (least bare ground, a character on screen, at least
    0.5 s from a cut and 1 s from the ends) with the chosen thumbnail text in the brand kit's headline font and
    colours, placed in the calmest band of the platform-safe area so it never sits on the film's own words. A platform
    in another aspect gets the cut in that aspect when it was rendered, else the frame on the brand's paper (never a
    stretch). Writes `build/package/covers/<cut>--<platform>.png` and `covers.json`.
  - **titles.status**: the back catalogue: per film, title and thumbnail candidates that pass today's check (facts
    change, so titles are re-checked) and covers missing for rendered cuts.
- **Posting with a human approval per post** (plan 4.15, WP-08; `dbe/posting.py`): nothing is posted without a
  person's approval of that post. `post.queue` makes one post per platform from a film's package (caption, title,
  that platform's cover, subtitles, the audio of its localised versions as extra tracks on YouTube) at its calendar
  row's date and the channel's `post_time` in its `timezone`; a post whose package fails (title not true, no
  subtitles, facts without sources) is blocked, and one with posting flags (non-clean voice, restricted inputs) can be
  approved only with the flags accepted. `post.approve` records the approver's name and time (`post.revoke` takes it
  back). `post.run` sends what is due: through a connector where one is configured (`productions/connectors.json`,
  machine-local; only a `dryrun` test connector ships, since platform APIs need the owner's own app credentials and
  some an app review), otherwise into `out/posting/<date>/<platform>/<film>/` with the files, the text and a
  `reminder.ics` for the person who posts it. Unapproved posts that are due are held, never sent. `post.done` records
  the published link; when all of a row's posts are out, the row is marked posted in the plan with every link.
  `post.status` and the board's Posting section show the queue, with Approve, Revoke and Posted buttons.
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

  - **AI look** (WP-04, `tools/ailook.mjs`): drop shadows, gradient fills over 3% of the frame, blur glows, emoji, and
    layouts where every text box is centred (at least three texts); the house set library's own gradients and
    filters are exempt.

  Every film gets the numbers. Thresholds and enforced checks come per style (WP-04, `dbe/profiles.json`
  `layout_styles`): a film's style is `shots.json` `"style"`, else doodle (a doodle-template character), cartoon
  (humanoid cast) or explainer (no cast). Each style was calibrated on its reference films' final encodes, each
  threshold just above the worst reference: frame fill (bare share) explainer 0.62, doodle 0.85, cartoon 0.80 (flat
  painted ground counts as bare, so this catches an empty frame, not a sparse one); first words by 1.5 s for
  explainers and 2.5 s for action-led doodle and cartoon openings; caption pace 3.2 words/s, 3.8 for cartoon
  dialogue. Enforced in every style (a failure fails QA): frame fill, text in the safe area, type size, AI look,
  cold open, reading time, effects below music and cue sync. Seams stay advisory until transitions exist (WP-15).
  A film's `"qa"` in shots.json may tighten thresholds and add enforced checks. Text measurement counts only words a
  viewer can see (not hidden, clipped or covered, not pushed out of frame) and leaves set text magnified past 1.25
  by a camera push-in out of the safe-area rule. Cue sync times percussive cues only (whooshes and swishes ramp in),
  each from halfway after the previous cue.
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

## Phone-level lip-sync and the lip-sync check (plans 2.1, 2.2)
**Alignment.** Kokoro predicts how many 25 ms frames each phoneme lasts before it makes any sound. `engine/kokoro_voice.py`
exposes that duration output once (`timed_model` writes `kokoro-v1.0-timed.onnx` next to the model, with the `onnx`
package from requirements-audio.txt), and kokoro-onnx turns it into phoneme timings. Measured over five voices and
21 lines against the audio, those timings sit about 80 ms after the sound, so they are shifted back by `PHONE_LEAD`
(0.08 s). `engine/voice.py` then takes, for every Kokoro line:
- visemes from the phones (`visemes.phone_visemes`): stress and length marks extend the phone before them, a
  silence between phones (the pauses Kokoro inserts after punctuation) closes the mouth;
- word times from the phones (`visemes.phone_words`): spoken words between spaces are grouped with the script's
  words by a small DP on phoneme counts, so "for a" run together, "25" read as two words and "Dr." all map;
- `"align": "model"` on the line in timing.json (`"whisper"` when it fell back).
Compared on the same audio, the previous method (Whisper word times, phonemes spread across each word) was 70-87 ms
off on average and showed the right mouth class on only 24-33% of frames. With timings on, Kokoro also inserts its
sentence and clause pauses, so re-voiced lines can be a little longer than before. Piper voices and recordings still
use Whisper words with spread phonemes.

**Check.** `python -m dbe lipsync.check '{"name": "FILM"}'`, also run by `qa.run` as the `lipsync` check, compares each
speaker's viseme track with how open the jaw should be, read from `build/voice.wav` as first-formant energy
(300-1200 Hz) inside that speaker's lines. It reports the best lag (positive: mouths after the voice) and the
correlation there, and fails beyond +-2 frames or below 0.2. With `DBE_RHUBARB` pointing at a Rhubarb Lip Sync
binary (MIT), each line is also read by Rhubarb and its Preston Blair cues are compared class by class (closed,
narrow, open, round; fails below 50% agreement).

## Self-healing and layout auto-repair (plans 2.9, 2.18)
`python -m dbe film.heal '{"name": "FILM"}'` renders the film, reads every failure (the QA bar, all measured layout
checks including the advisory ones, and visual-lint errors), applies the known repair for each to shots.json,
re-renders what changed (incremental shot hashes) and repeats, up to `rounds` (3). Before re-voicing it anchors
hard shot times to their lines, so the picture follows the slower voice. The shots.json from before the
first round stays in `build/shots.before_heal.json`; the result lists each round's failures and edits, and what still
fails with the reason a person is needed (for example cold open, or bare frames with no character to enlarge). Repairs
(`dbe/heal.py`):
- frozen stretch: low `style.step` goes back to 12; a shot with no camera gets the float camera; cast get idle;
- text outside the safe area: moved in by exactly the overshoot plus 8 px (`x`/`y` of the kit element);
- type too small: size raised to the platform minimum (26 px for 9:16, 24 px for 16:9);
- reading time: a timed text block stays up words / 3 + 1 s, within its shot; captions flowing faster than 3.2
  words/s re-voice the script slower when `revoice` is true (then the gestures are re-planned);
- frame fill: the shot's cast is scaled up once (feet stay on the floor, at most 1.3x); if the next render shows
  the bare share down by less than 3 points the scale-up is undone (the shot needs content, not a bigger character);
- lint, head cut by the frame: an auto camera frames singles less tight; a static shot scales the character down
  and moves it in; lint, bubble over a face: an auto camera leaves more headroom, else that shot goes back to
  captions.
`films/heal-demo` is the kit demo with failures seeded on purpose (animation once a second, a 20 px sign up for
0.8 s, the title below the safe area).

## Acting from prose, gags and rig-aware writing (plans 2.4, 2.11, 2.12)
**Directions.** A script line can carry `"direction"` (anchored to that line), a shot can carry one too, or text can
be passed straight to `python -m dbe acting.direct '{"name": "FILM", "text": "...", "shot": "s1"}'`. One action per
sentence (or clause after "then"):
- who: a speaker in the shot; he, she, they = the last one named;
- when: `when Ravi says 'back'` (that word), `after/before/during the line` or `after Priya's line`, `at the start`,
  `at the end`, `then` (after that character's previous action), else with the line (or right after the same
  character's last action);
- what: an emotion (happy, sad, angry, surprised, worried/nervous, neutral and synonyms), a gaze (`glances at` is
  brief, `looks at` holds), `walks to` someone (moving placement plus the walk clip), or one of the clip verbs: nod,
  shake their head, shrug, clap, jump, celebrate/cheer, facepalm, cross their arms, think, scratch their head,
  stomp, slump/sigh, wave, point, present/show, run (wave, point and present turn toward their target);
- at whom: another character, or the camera, up, down, left, right, the sky, the moon, the board, the door;
- how: slowly, quickly, a little, hugely (speed and size).
The result is written into shots.json line-relative where it was anchored to a line, so re-voicing keeps it on the
words. Directed clips are tagged and the earlier gaze, emotion, blinks and placement are kept under `undirected`, so
running `acting.direct` again replaces the last direction instead of piling up. With exactly two characters, an
untargeted gaze goes to the other one. `acting.plan` (talk gestures from the voice) and `acting.direct` combine: run
the planner first.

**Gags** (`dbe/director.py`): `does a double take` (look, look away as if nothing happened, a beat, snap back
surprised with a blink), `gives a long stare` (2.6 s held look, blinks on a slow count, idle damped), `slow burn`
(neutral to the camera, then angry, arms crossed), `deadpan` / `looks at the camera`, `button` (a small happy nod),
`rule of three` (three times / three verbs: twice as set-up, the third bigger and later).

**Rig abilities.** `python -m dbe puppet.abilities '{"puppet": "cast/generated/momo.puppet.json"}'` lists what a
character does for free (clips whose parts it has, emotions whose mouths and brows are drawn, glances, blinks,
lip-sync, turn, tail) and what each costly move needs drawn. `python -m dbe script.rigcheck '{"name": "FILM"}'` reads
every direction in the film and lists per character the moves that are free and exactly which drawings are missing,
with the sentences that need them. `films/direct-demo` is staged from its directions alone; with Momo recast as the
doodle Nib, the same script asks for seven drawings (pupils, two brows, two mouths, a shrug and a head-scratch clip for
the doodle template).

## Narration slots (plan 2.16)
`python -m dbe script.slots '{"name": "FILM", "wpm": 135}'` gives every script line a fixed `"slot": [start, max_s]`
(words at `wpm` plus 0.25 s, the script's gaps and pauses between) before any voice exists. With no voice yet it also
writes a draft timing.json from the slots (words spread by letters), so the picture and the sound-off cut can be made
first: the sound-off cut is the master. From then on `voice.build` places every line at its slot start and keeps the
slot's end as the line's end, so line-relative shot times never move. A line longer than its slot uses its short
alternate (`"alt"` in script.json) if that is shorter, then up to 15% faster speech; whatever still overflows runs
into the following pause and is reported (`overflow_s`; `fit` says what was done; `spoken` when the alternate was
used). `films/slots-demo` was cut on slots, then voiced twice with different casts (the second slowed 35% so line l3
falls back to its alternate and l4 speeds up 1.18x): the shot changes are identical in all three states
(s1 0-7.283 s, s2 7.283-17.338 s).

## Data-bound visuals and original analysis (plan 2.17)
Every number on screen or in the narration can come from `data.json`, written by the film's own analysis:
- `films/FILM/analysis/sources.json` lists the inputs: `{"id", "file", "url", "terms", "version"}`. `film.data`
  downloads each `url` once into `analysis/cache/` (again only with `refresh`), and records the access date and
  sha256; local inputs just get their hash.
- `analysis/*.py` run in name order with DBE_PY, from the analysis folder, reading the cache and writing
  `../data.json`. `film.data` adds `_provenance` (script hashes, sources with terms, version, access date, sha256).
- Bindings: any text in shots.json or in script lines may hold `{{path}}` or `{{path|format}}` (`1` decimals,
  `comma`, `int`, `pct`, `pct1`, `word`, `upper`); paths walk data.json (`best.month`, `monthly.2.1`). A chart's
  `data_from` is inlined. Bindings are filled when shots are resolved and when the script is voiced (voice.build
  refuses unresolved bindings).
- `python -m dbe film.data '{"name": "FILM", "revoice": true, "render": true}'` reruns the analysis and reports which
  data keys changed, which shots' pictures change and which narrated lines' words change, then re-voices those
  lines and re-renders only those shots (shot hashes cover only the lines and mouth cues a shot shows).
`films/data-demo` charts an illustrative club log (labelled as demo data). Changing one month in `analysis/cache/log.csv`
re-rendered the chart shot and the "best month" shot and re-voiced their two lines; the intro shot stayed as it was.

## Format templates (plan 2.15)
`python -m dbe film.from_template '{"name": "NEW", "format": "dialogue", "brief": {...}}'` writes a whole
storyboard from a format and a brief, then checks it:
- formats (`dbe/formats.py`): `myth_vs_data` (myth, question, finding, why, source), `explainer` (hook, point,
  detail, source; optional question; the calendar's analysis and news slots), `dialogue` (topic and
  `exchanges` of q/a; the learner asks, the expert answers, E28), `wonder_story` (imagine, build, reveal, reflect),
  `we_reran_it` (old_claim, new_finding, changed, source), `anniversary` (years, event, changed, now) and `series`
  (`parts`, each with its own format; edit.json splits it into episodes). Any beat's text can be overridden in
  `lines`, roles recast in `cast` (default expert Ravi, learner Momo, narrator Priya), sets in `sets`;
- every film gets script.json with narration slots (135 wpm, draft timing), one shot per scene (line-relative,
  listeners added in conversation scenes, an auto camera when two or more are on screen, a float camera when none),
  kit signs held words / 3 + 1.2 s, prediction prompts ("What do you think?") that stay up through the question and
  a silent count before the reveal, charts from `data`, citations, and facts marked `needs_check` until sourced;
- `python -m dbe storyboard.check '{"name": "FILM"}'` runs the cold-open rule (a character in frame one, words by
  1.5 s) and the reading-time rules (signs up long enough, captions at most 3.2 words/s) on the storyboard before
  or after voicing, and lists facts still waiting for a source.
`films/telescope-talk` came from the dialogue template and a three-question brief; it passed the storyboard check
before voicing and the full QA after.

## Studio timeline (plan 3.1)
`python -m dbe serve` then http://127.0.0.1:8770/timeline?film=FILM (also linked from the Studio header). The page shows:
- a live preview (the film's own player page, scaled): click or drag the ruler to scrub, Play (space) runs it
  against `build/mix.wav`;
- lanes: shots, one dialogue lane per speaker (lines with word ticks), and one lane per character with their clip
  layers (hand-placed orange, planned from the voice grey, from directions purple; overlapping clips stack in rows,
  looping base layers such as idle run as a thin bar);
- editing: drag a clip to re-time it (its end moves with it), drag its right edge to change its length, double-click
  a character's lane to add a clip, Delete removes the selected clip, ←/→ nudge one frame (Shift: ten), Ctrl+Z
  undoes. Moves snap to frames, and to word starts within 6 px ("snap to words").
Every edit goes through `timeline.edit` (`move_clip`, `resize_clip`, `add_clip`, `delete_clip`) into shots.json and
the preview reloads. A time written line-relative stays line-relative (`l2.start+0.61`), re-anchored to the line
the clip now sits by when it moves away from its old one, so re-voicing still carries the edit; a planned clip that
is edited by hand loses its `auto` tag, so `acting.plan` keeps it. `timeline.get` returns what the page draws;
`film.preview` writes the player page. `tools/timeline_check.mjs` drags a gesture in a headless browser.

## Storyboard strip and animatic (plan 3.2)
`python -m dbe film.storyboard '{"name": "FILM"}'` takes one still per shot from the player (a moment into the
shot's first line, so the auto camera is on the speaker; the middle of the shot when nobody speaks; drawn without
captions) and writes to `build/storyboard/`: `strip.png` (every shot in a grid with its id, times, set and lines),
`contact.pdf` (three shots a page with notes: times and length, set, cast, the lines, and any directions), and the
stills (`s1.png`, ...). `python -m dbe film.animatic '{"name": "FILM"}'` holds those stills for their shots' lengths
over the film's sound (the mix if rendered, else the voice) as `build/animatic.mp4`, in seconds, for judging pacing
before a render. Studio has Storyboard and Animatic buttons; the timeline has Animatic.

## Posing in the Rig Canvas (plan 3.3)
The Rig Canvas has a **Pose** tool. The character stands on the ground line with handles: hands and feet (orange)
are placed by two-bone IK (`Acting.ik2`, the solver films use; Shift flips the elbow or knee), the head and chest
(blue) turn about their joints, the hips (green) move up and down with both feet kept planted (the legs are
re-solved, knees splayed outward). Joint limits apply. Mouth, brows and eyes come from the character's drawn
shapes. **Save pose** stores it in the character's `poses` (used by `poses: [[t, name]]` in any timeline); **Key**
records the current pose at a time and **Save clip** turns the keys into a clip in the character's own `clips`
(puppet format v0.7), which `Acting.evaluate` merges over the template library, so shots, the bake and every
renderer play it. Saved poses and clips also appear in the live preview menu. Opened from Studio (served by
`python -m dbe serve`), **Save to cast** writes the character through `puppet.save` (schema-checked, only under
`cast/`, new files registered in the cast library). `tools/pose_check.mjs` does the whole round in a headless
browser; the golden case `tests/poses/rig_canvas_pose.json` plays the saved pose and clip.

## Review room (plan 3.4)
http://127.0.0.1:8770/review?film=FILM (linked from Studio): the render with frame stepping (`,` `.`), a bar with
every note pinned at its frame, and a box to pin a note at the current frame. (Where the browser cannot decode the
render, the page shows the live player at the same frame instead.) **Fix open notes with the critic** runs
`review.fix`:
- the note is read (`dbe/review.py interpret`): what to change (earlier, later, faster, slower, bigger, smaller,
  longer/hold, shorter, remove), by how much ("by 10 frames", "by 0.5 s", "a bit", "a lot"), which body part,
  character, side and gesture it names;
- the clip making that motion at that frame is found (`locate`): the named character, a clip whose tracks move that
  part, active at the frame or the move just before or after it; the part to measure is what that clip moves most;
- the edit goes through `timeline.edit` (move, resize, `set_clip` speed/gain, delete); gestures that come back to
  rest are slowed or sped up to hold longer or shorter, poses that hold are extended;
- the critic probes the part's on-screen path over the same window before and after (`window.PROBE`,
  `tools/probe.mjs`): an earlier move must reach half-way sooner by at least 60% of the asked amount, a bigger one
  must travel 10% further, a slower one must take 10% longer, a longer hold must last 0.15 s more, a removed one must
  all but stop; then the film is re-rendered and QA must not get worse. Verified notes close with an after-still in
  `build/review/`; anything else is reverted and marked `needs_human` with the reason.
Notes live in `films/FILM/review.json` (`review.add`, `review.list`, `review.fix`). `films/review-demo`: "raise
the arm earlier" on frame 120 moved Momo's shrug 0.33 s earlier (measured 0.33 s), "Ravi should point bigger" on
frame 180 (379 px, was 300), "hold the scratch head longer" (held 1.65 s, was 1.16 s); "this bit feels off somehow"
went to a person.

## Act it out (plan 3.5)
http://127.0.0.1:8770/actout (linked from Studio): **Use camera** and **Record 5 s** (a 3-2-1 count, then five seconds
from the webcam or phone camera), or pick a video file; choose a character and a clip name, then **Make clip**. The
character plays the new clip in step with the take, and the report says what was captured, what was left out and why.
The same thing as a command (CLI, HTTP, MCP):

    python -m dbe actout.clip '{"video": "take.mp4", "puppet": "cast/generated/ravi.puppet.json", "name": "thumbs_up", "duration": 5}'

What happens (`dbe/actout.py`):
- **Detect.** ffmpeg decodes the take at 30 fps (phone rotation applied, `mirror` flips a selfie first); MediaPipe
  Pose gives 33 body points with visibility and depth, and Face Landmarker, run on a crop around the head, gives 52
  blendshapes. Keypoints are cached in `out/actout/` by file content and options, so re-targeting the same take onto
  another character skips detection.
- **Retarget** onto the character's own rest pose, in image space (the arm on the left of the picture drives the
  `_L` part, drawn on the left of the artboard). Each bone's world rotation is the take's segment angle minus the
  same bone's angle in the drawing (pivot to child pivot); the track is that minus the parent's, as `puppet.js`
  composes angles. The spine comes from hips to shoulders, or from the shoulder line in a waist-up take; the head
  rolls with the eye and ear lines. Segments pointing at the lens (too short on screen) are bridged, and parts seen
  in less than 60% of the take are left out (`dropped` in the report), so idle or other clips fill them.
- **Arms** (`arms`): `angles` (default) copies joint angles, which keeps natural silhouettes on a flat character
  whose forearm cannot foreshorten toward the lens; `reach` places the hands where the take's hands are relative to
  the shoulders, scaled to this body, with the elbow on the take's side: claps and hands on the body meet, but a
  short-armed character wings its elbows out for a hand held near the chest.
- **Root** (`root`): `move` turns hip travel into the clip's offset; when both legs are seen, ankle height and speed
  give foot `contacts` and the vertical offset is solved so planted soles sit on the ground line (forward kinematics
  through the clip's own legs), with the take's jump carried between contacts. A waist-up take never moves the root
  vertically. `in_place` drops travel.
- **Face** (`face`): `upper` (default) makes eye (open, half, closed), brow (raised, worried, angry) and gaze keys;
  `all` adds the mouth (wide, mid, small, O, smile, frown), which overrides lip-sync while the clip plays, so it is
  for silent reactions. Only drawings the character has are used (with fallbacks), and short flickers are held.
- **Layer order**: when the take's wrist is clearly nearer the lens than the shoulders, a forearm and hand drawn
  behind the body come in front (clip `swaps.z`, the existing `pose.z` override; Lottie and Synfig keep their fixed
  order, as with control-driven z).
- **Keys** are reduced against the curve `Acting.evaluate` actually plays (smoothstep between keys), seeded with the
  clear turning points and split where the played curve strays most, to `tolerance` degrees (default 1.5).
- **Save**: the clip goes into the character's `clips` (puppet format v0.7, version raised to 0.7 if older) through
  `puppet.save`, with a `source` note. Any shot plays it by name; `film.validate` accepts a character's own clips.
  `out/actout/<name>_sheet.png` shows six moments of the take above the character.

Warnings in the report: the performer's size on screen changing by more than 25% (a zoom or a moving camera reads
as travel: use `in_place`), and a face found in under 80% of the take. Takes, keypoints and sheets stay in `out/`
(git-ignored). MediaPipe (`requirements-tools.txt`) needs libEGL (`apt install libegl1`); its two Apache-2.0 model
files are fetched once into `DBE_MODELS` and checked against pinned hashes.

Measured: a 5-second phone take (waist up, Pexels test clip) became a 184-key clip on Ravi in 17 s from upload
through the page (decode 3 s, detection 8 s, retarget under 0.1 s), legs left to idle; a full-body take with a
camera zoom was flagged. `python -m dbe test` runs the Act it out self-test (in `dbe/actout.py`): takes made by forward kinematics through a
character must come back as the clips that made them (wave, celebrate, shrug under 1.5° mean), a jump's contacts
within 0.08 s with planted soles within 5 units of the ground, a waist-up take must not guess legs, `reach` must
keep a long-armed performer's clap together (0.035 torso lengths, against 0.17 for angles), and face keys must
follow blendshapes (`upper` never touches the mouth).

## Phone-first creator flow and drawing requests (plan 3.6)
http://127.0.0.1:8770/doodle (linked from Studio; laid out for a phone): draw a character with a dark pen (a closed
loop for the head, one for the body, eyes and a mouth inside the head, stick arms), then:
1. **Snap** (`doodle.snap`): the photo is turned upright (EXIF), cropped to the ink and scaled to about 900 px
   (`out/doodle/<id>/`). `dbe/autorig.py` closes small gaps in the line and reads it: the two largest stacked closed
   loops are the head and body (one loop: a blob, all head, resting on the ground); marks well inside the head that
   are not joined to its outline are the eyes (upper) and the mouth (the lowest wide one); strokes leaving the body's
   sides at its height are arms, with the pivot where they meet it; a second, lower side stroke is a tail; marks above
   the body (ears, hair, a hat) ride with the head; legs and feet stay on the body. Every guess is reported with a
   reason, and notes say what it could not find.
2. **Check the cuts**: each piece is tinted over the photo; drag a dot to move a pivot (or the mouth centre), tap a
   piece to leave it on the body; `doodle.cut` rebuilds.
3. **See it move and talk** (`doodle.say`): one line in a clean Kokoro voice, run as its own process
   (`engine/say_line.py`), with lip-sync cues from the model's phoneme timings; the acting is idle, a wave on a
   greeting, a hop on an exclamation, head and body beats while talking, blinks. Hop, Wave, Tilt, Shake (and Wag with
   a tail) play on tap.
4. **Keep it** (`doodle.keep`): `cast/drawn/<name>.puppet.json`, registered with owner rights and its voice.

The puppet is built by `dbe/ink.py` in the artist's own line. Eyes blink by squashing the drawn eyes. The mouth gets
talking shapes (closed, small, mid, wide, O, FV, smile) drawn in the doodle's ink and line weight: the drawn mouth
is `closed`; with none drawn, all are made; a drawn mouth joined to another line stays drawn and the dark open shapes
cover it (reported, so the person checks the mouth box). Measured on a synthetic cat doodle through the page at phone
size: cut in 3 s, talking 11 s after the photo was picked.

**Drawing requests** (feature map E20): `drawing.requests` lists every drawing a character is missing, for one
film's directions (`film`, from `script.rigcheck`) or for all its costly moves (`puppet.abilities`), as requests in
`<puppet>.requests.json` with the reason and a ghost guide (`out/requests/`): the character faintly at rest on its own
artboard, the related drawing it has a little stronger, and a dashed box where the new drawing goes. On the page,
**Draw it** opens the guide to draw over with a finger; a drawing on paper photographed at the same framing works too.
`drawing.fulfil` lifts the ink inside the box (`ink.extract`), stores it as the swap shape (a new swap if needed, e.g.
brows) or part (a tail, pivoted where the stroke is nearest the body), saves the character, and closes the request
only when the rig check no longer lists it, reporting the moves that became free; with `render` it re-renders the
film that asked. Pupils, a turn view and chains are rigged rather than drawn, so they are listed for the Rig Canvas.
Drawn shapes are raster strokes (SVG renderer). `python -m dbe test` cuts three synthetic doodles (head and body,
blob, cat with a tail and ears; pivots within 11 px), snaps the cat, builds its queue, draws raised brows into the box
and checks happy and surprised become free, and voices a line when Kokoro is installed.

## Production orchestrator and board (plan 3.7)
http://127.0.0.1:8770/board (linked from Studio): a posting calendar by week, and a card per film with its state,
where it stands against its posting date, the checkpoints (research, first shot, final, approved, merged) with the
orchestrator's verdicts, the final's measurements (length, loudness, true peak, QA checks passed, layout advisories,
the director's verdict), escalations, narrowings and the owner's buttons: Approve, Merge, Stop, Relaunch, Narrow, and
Proceed / Narrow / Stop on an escalation. The page reads `prod.status` every 4 s.

    python -m dbe prod.plan '{"film": "kit-demo", "post_on": "2026-11-10"}'          # runner: pipeline | claude | manual
    python -m dbe prod.launch '{"max_parallel": 3}'                                    # every planned film

Each film gets a git worktree next to the repository (`<repo>-films/<film>`, branch `film/<film>`) and a session:
- **pipeline**: `tools/film_agent.py` rebuilds an existing film through every gate: research gate, voice (when the
  workspace has none), the first shot, the full render with QA (one round of `film.heal` if QA fails), a builder
  entry in the ledger, a commit on the branch. This is how every film is re-made after an engine change.
- **claude**: Claude Code headless (`claude -p --output-format json --max-budget-usd N`, command in the registry's
  `runners.claude`) with the protocol and `docs/director-prompt.md`, allowed to run `python -m dbe`, commit, read
  and edit, and search and fetch the web for research, for new films from a brief (`prod.plan` with `brief` writes it
  into the workspace). Each session stops at its budget (`budget_usd` on the film, else the board's, default 25).
  When it ends, what it spent (dollars, minutes, turns, tokens) is read from its JSON result into the film's
  `costs`; the board shows each film's spend and the total (WP-03).
- **manual**: nothing is started; the protocol is written to `.production/PRODUCTION.md` in the workspace for any
  agent to follow. `prod.session_prompt` (the board's "Copy session prompt") gives the protocol and the director
  prompt ready to paste into a Claude Code session, here or in the cloud, working in that workspace.

Owner notifications (WP-03): an escalation, a final ready for approval, a failed session, a final that still fails
after the session's repairs, and a session stopped by its budget each notify the owner: a line in
`productions/notifications.jsonl` (the board shows the latest), and a POST of the same JSON to every webhook in
`productions/notify.json` (`{"webhooks": [{"url": ..., "events": ["escalated", "waiting_owner", ...]}]}`,
machine-local) that asks for that kind. A webhook that fails is recorded and never stops production.

The protocol is three checkpoint calls, `prod.checkpoint {film, stage, report}`, which a session in its workspace
sends to the shared registry (`DBE_PRODUCTION`, set by the launcher). The orchestrator never takes the report's word:
it measures for itself in the film's workspace. Research runs `research.check` there and reads the ledger; a
counter-evidence entry that contradicts or blocks (or contradictions the session lists) **escalates**: the film
stops until the owner decides with `prod.decide`. Proceed carries on as briefed; narrow appends the owner's change of
scope to the film's brief and delivers it with the next answer; stop ends the film. The first shot must exist at the
film's frame size, and a still goes to the board. The final reads `qa.json` and the director's ledger verdict, then
copies the render, QA report and a poster for the board. The answer carries the verdict (ok, ready, fail, blocked,
escalate), the reasons, the owner's pending instructions and `continue`: a stopped or escalated film's session ends.

Owner controls: `prod.stop` (the session's process group), `prod.narrow`, `prod.relaunch` (renders in the workspace
are reused), `prod.approve` (only a final that passed QA), `prod.merge`. Merge needs approval and refuses a branch
that changes anything outside `films/<film>/` (new characters may go in `cast/drawn/`); it merges `--no-ff` and puts
the approved render next to the film data. `prod.status` also starts queued films as running ones finish (at most
`max_parallel` sessions), and marks a film failed when its session ends without a final checkpoint, or
`needs_work` when its final still fails QA after the session's own repair round.

Schedule: each milestone is due a number of days before posting (`lead_days`: research 10, first shot 6, final 3,
approval 1); a film is on_track, due_soon (within a day), late, or needs_owner while escalated.

The registry (`productions/registry.json`, git-ignored, with session logs and render copies for the board) is
written under a file lock, because sessions report concurrently. `python -m dbe test` runs `production.self_test`
on a throwaway clone of the working tree with a manual session. It covers launch into a worktree, research ok, an
escalation from a counter-evidence entry, narrowing, a first shot at the wrong size, a failing then passing final,
approval refused before a pass, a merge refused for a stray edit outside the film, a clean merge, and the schedule
states.

Measured (a scratch clone of the repository, 4 CPU cores, `max_parallel` 3, a simulated owner acting through the
same commands as the board): ten films (nib-hello, kit-demo, fx-demo, props-demo, heal-demo, clips-demo, data-demo,
direct-demo, review-demo, dialogue-demo) posting between 9 and 27 November went from planned to merged in 19.5
minutes, never more than three sessions at once. Every final passed QA 7 of 7 at -14.0 LUFS. The run also covered:
fx-demo's seeded session crash, which was caught as "ended before the final checkpoint" and relaunched; kit-demo,
stopped by the owner after its first shot and relaunched, which reused its renders; and data-demo, whose
counter-evidence escalated it at research, was narrowed by the owner, and merged with the narrowing in its brief.
Each merge touched only its own film's folder. The run found two bugs, both fixed: the merge did not check that the
session had committed, and a hand-written ledger entry without metrics broke the ledger writer. A merge now refuses
while the session runs or while the film's work is uncommitted. The claude runner is wired, but no Claude Code
session was run in this test.

## Content planner (plan 3.8)
http://127.0.0.1:8770/plan (linked from Studio): the quarter's calendar by week, every spread rule with its verdict,
the idea bank's counts, and each row's field, sweep, role, start-by date, fact-lock date and status and live stage,
with **Brief** and **Brief + board** buttons, for the channel picked at the top. Files, per channel (in git: the
studio's plan): `plan/channels/<id>/channel.json`, `ideas.json`, `<quarter>.json`; `plan/channels.json` names the
default channel.

0. **Channels** (WP-32): the studio can run several series side by side, each with its own audience, fields, locale,
   rules, brand kit, cast and voices. Every `plan.*` command takes `channel` (default: the default channel);
   `plan.channels` lists them with their brand colour, cast, series and quarters; `plan.channel` with a new id starts
   one from the defaults. A channel's films inherit its brand kit (`shots.json` `"brand": "<id>"` reads
   `brand/<id>.json`; `true` stays the house kit), its cast (template roles to characters) and its voices, through
   `plan.brief`. `plan.cross` lines every channel's quarter up week by week and flags two channels posting the same
   subject in one week. The board colours each film by its channel and filters by channel. `science` is the live
   channel; `brand/sample-kids.json` and the test channel in `planner.KIDS_SAMPLE` are samples for a second series.

1. **Channel** (`plan.channel`): audience, topic fields, the locale for local stories, brand kit, cast and voices, and the rules: posting days, the
   weekly series (day, name, format), at most one post per field per week, days between posts in a field, local
   stories per week, an analysis every N weeks, the tolerance for dated hooks, and lead and fact-lock days per sweep.
2. **Sweeps** (`plan.sweep_prompt`): six research prompts for agents with web search: dated hooks (anniversaries,
   international days, sky events, launches in the quarter, dates checked on official pages), recent developments
   (with `fresh_until`), evergreen myths and questions (the series), tools, original analyses (data with its terms and
   a published figure to check against) and local stories. Each asks for real sources the agent opened and nothing
   invented, with research leads and cautions.
3. **Idea bank** (`plan.ideas_add`, `plan.ideas`): ideas are briefs in waiting: a draft hook, angle, why now,
   starting-point sources, research leads, cautions, field, sweep, format and score. Each is validated. Near-duplicates
   are refused. Every cited URL is fetched: a source that does not exist (404, or a host that does not resolve) is
   dropped, an idea left with none is refused, and the rest record "ok" or "blocked" (a site that refuses robots).
4. **Schedule** (`plan.schedule`): dated hooks on their day (capped so each week keeps room for its series episode
   and local story), the series slot (a hook on the series day moves the episode to another free day that week; a
   hook blocking the series day's field is set aside when that is the only way to place the episode), the local quota,
   the analysis cadence (any week of its span), a repair pass (a week short of its local story or series episode, or a
   span short of its analysis, takes the slot of one of its dated hooks, never the one on the series day), then the
   open slots. Measured on made-up banks for two channels: 47 of 48 quarters pass every rule (the scheduler before
   WP-32 passed 29 of 48 for the science channel alone); a miss is a bank short of fitting ideas, and the check says
   which week. An open slot goes to
   a field with no post yet, then the least-used field, then the higher score; recent stories must still be fresh and
   every idea must be startable by its lead time. Each row gets `start_by` and a `fact_lock` date: the day the film's
   facts must be cleared by the fact gate (`ledger.add role=fact_gate verdict=cleared`).
5. **Check** (`plan.check`): every rule, computed independently of the scheduler, so a hand-edited calendar is checked
   the same way: slots filled, posts per week, topic diversity, field gap, local quota, analysis cadence, series
   cadence, timeliness (dated hooks on the day, recent stories while fresh), lead times, a fact-lock date on every row,
   an empty field getting the next open slot, no repeats, distinct topics (no two films on one subject in a quarter:
   titles sharing two or more words and most of the shorter title, or title, angle and hook sharing most of their
   words, with accents folded and plurals stripped), sources on every idea.
6. **Brief, storyboard and launch** (WP-06, feature map E24): `plan.brief` writes the row's brief and drafts its
   storyboard with `film.from_template` from the format the row names (`myth_vs_data`, `explainer`, `dialogue`),
   in the idea's own words: the hook, the angle's first two sentences, a short citation of the first source. Every
   fact starts unsourced (the research gate holds the film) and `script.json` carries `"draft"`, which `voice.build`
   refuses until the session has rewritten the lines after research. With `launch` it is one command from calendar
   to session: the film goes onto the board with its plan row (quarter, start-by, fact-lock date, role, review
   level), its brief and draft storyboard are committed on its branch in its workspace (nothing is left in the main
   checkout, so the merge meets no untracked copies), and its session starts (or queues behind `max_parallel`).
   The board shows each card's plan row. `plan.track` reads the films
   and the production registry and shows each row's stage (planned, briefed, in production, final ready, approved,
   merged, posted), its fact-lock status from the film's ledger, and what is overdue. `plan.posted` records the link.

Measured, for Q1 2027, planned on 2 November 2026: six research agents ran the six sweeps in parallel, taking 7 to 18
minutes each, and returned 100 ideas: 20 dated hooks, 16 recent stories, 22 evergreen ideas (18 myths), 12 tools,
12 analyses and 18 local stories. All passed validation and the duplicate check, and every source URL resolved.
93 sources loaded; 3 refused automated requests and are recorded as "blocked". The agents reported what they dropped
or demoted to research leads: pages they could not open, dates they could not confirm, and datasets whose licence
did not allow reuse. The scheduler filled all 52 posting days (Mon, Wed, Fri, Sat). Each field got 8 to 10 posts;
there were 14 dated hooks, 13 series episodes, 7 analyses, and at least one local story in every week. All 14 rules
pass. Adding the topic rule caught four duplicate subjects across sweeps: perihelion, the reservoir cascades, the two
monsoons, and Sri Lanka's kidney disease. A fifth, El Niño, was found once accents were folded. The rule errs on the
side of caution: it also pairs two monsoon-wind ideas that are different films. Many ideas carry a Sri Lanka angle,
so 35 of the 52 posts are local; the quota is a minimum, and the channel's rules can change that balance.
`python -m dbe test` runs `planner.self_test` on a synthetic bank: the scheduler's quarter passes every rule, and five
calendars broken on purpose are caught by the right rule.


## Setting up a machine (WP-02)
    bash tools/setup.sh            # everything; idempotent (about 2 minutes fresh, 11 s when nothing is missing)
    python -m dbe engine.doctor    # what is there, what is missing, and the exact fix for each gap

`engine.doctor` checks three groups. **core** (needed for the engine, Studio, SVG renders and `python -m dbe test`)
covers Python 3.11+, `requirements-core.txt` (numpy, Pillow, jsonschema, scipy), ffmpeg, ffprobe, git, Node,
Playwright, that headless Chromium actually starts, and free disk. **audio** covers `requirements-audio.txt` and the
Kokoro model files, checked against pinned sha256 hashes, plus the timed model and the Piper voices installed.
**tools** covers `requirements-tools.txt` (psd-tools, MediaPipe), libEGL, the MediaPipe models (hashed), Synfig,
Blender and melt. `ok` means every required check passed; the self-test fails if one does not. With `deep: false` it
skips the browser start and the hashing (about 1 s instead of 5).

`tools/setup.sh [all|system|python|models|node]` applies the fixes: apt packages (ffmpeg, git, libEGL); Python
requirements, with the pinned large wheels first fetched over plain HTTP by `tools/fetch_wheels.py` (pip stalled on
large wheels behind this environment's proxy), choosing the wheel by the interpreter's own compatibility tags so an
ARM or macOS build is never picked; the Kokoro files (verified by hash), the timed model and the MediaPipe models;
and Playwright only if `require('playwright')` fails. For a cloud environment, put `bash tools/setup.sh` in its setup
script. Models live in `DBE_VOICES` (default `~/voices`) and `DBE_MODELS` (default `~/.cache/doodleberry/models`),
wheels in `DBE_WHEELS`; none of them go in git.

## Keeping the docs true (WP-01)
`python -m dbe docs.check` (also in `python -m dbe test`) checks that the build plan, the feature map, the work
packages and the command registry agree:
- every command named in backticks in the docs is registered;
- every feature-map row marked ⬜ or 🟡 names its work package (WP-nn) or says "not planned";
- every WP-nn mentioned exists in `docs/work-packages.md`;
- every item in the build plan's phase tables has a status row or a work package covering it;
- every work package is in the at-a-glance table and the order of work.

The feature map was reconciled against the code on 2 November 2026. 238 open rows were reviewed: built rows now
name the command or plan item that built them, partial rows say what is left and where, and every open row points
at its work package. The map went from about 90 rows marked built to 162 built, 53 partial and 72 open (P2 and
emergent rows included).

## Expert review and honest labels (WP-05)
Health, legal and finance films get an expert reviewer. The channel's rules (`plan.channel`, `rules.expert_review`:
fields such as "life & health" and keywords such as disease, drug, dose, treatment, law, invest) decide which calendar
rows are marked `review: expert`; `plan.brief` writes the review row and an "Expert review" section into the brief.
`research.check` then requires `omits` on every fact and reports `expert_review: pending` until a reviewer records
`ledger.add role=expert_review verdict=cleared`; the final checkpoint carries the status to the board, and
`prod.approve` refuses the film until it is cleared. `plan.check` gained a rule, `expert_review_marked`. In Q1 2027 the
ten health posts are marked.

Facts labelled "re-analysis", "illustration" or "preliminary" show that label on screen while a line citing them plays
(a tag at the top of the text-safe area, drawn with the captions by `film.render`). No existing film has labelled
facts, so no golden frame changed.

## Licence ledger and vendored code (WP-33)
Doodleberry is in-house R&D, so any licence may be used; the ledger records which, so a public post can be judged.
- `licence.ledger` lists every component with its licence class: manifest files and tools, vendored code, voices and
  cast puppets. Classes: public-domain, permissive, attribution, weak-copyleft, copyleft, network-copyleft,
  share-alike, source-available, non-commercial, research-only, proprietary (the owner's own work).
- `film.provenance` lists what shaped a film (characters, voices, the third-party files its renderers and captions
  use, and models recorded in the film's `provenance.json`) and flags what restricts a public post: voices not marked
  clean, and non-commercial, research-only, share-alike or source-available inputs. `film.package` carries the flags
  and `clear_to_post`.
- Vendored code has an `UPSTREAM.json` next to it (repository, version, archive and sha256, licence and class,
  licence files, what was taken, patches, a build recipe and the binary it makes). `vendor.check` (in
  `python -m dbe test`) checks every record, its licence files and its manifest row; no class is refused.
  `vendor.build NAME` builds a component in a copy, into `out/vendor-build/NAME/` (git-ignored).
- Vendored so far: lottie-web, three.js and perfect-freehand (JavaScript, as before), and the sources of Potrace 1.16
  (GPL-2.0-or-later, monochrome tracing) and VTracer 0.6.4 (MIT or Apache-2.0, colour tracing), unmodified, for
  WP-18's scan-to-vector work. **Not built yet:** building runs the upstreams' own configure, make and cargo
  scripts, which this environment's safety check refused to run without the owner's permission.
