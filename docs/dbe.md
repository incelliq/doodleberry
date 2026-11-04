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
- **Renderer parity** (WP-14, `dbe/rparity.py`): `render.parity {name, shot}` draws the shot's cast alone with the
  SVG renderer (`castonly=1`, without line boil) and with Synfig, Lottie and Grease Pencil at the same moments, and
  compares each with SVG: the better of the filled-silhouette overlap and a line F-score (ink within about 4 px of the
  other's), at least 0.85, and the colour difference where both have ink, a pixel in from every edge (lines a
  pixel apart are judged by the line score, not as colour), at most 24 of 255.
  `render.parity_bench` runs every benchmark shot. A renderer that cannot draw a shot says why (`rparity.CAPABILITIES`;
  `shot.render` refuses with the same reason), and styles a renderer draws without (line boil) are listed. What
  parity fixed: the bake now records every swap set's drawing (drawn levels and control-driven swaps were lost to
  the other renderers), auto-camera and float shots carry the SVG player's own camera into the bake
  (`tools/view_keys.mjs`), Synfig and Lottie draw raster parts and drawn levels (import layers and image assets) and
  clip-driven layer order (a layer per order, shown on its frames), Lottie keeps the end of every hold (changes no
  longer smeared back across it) and drawn levels without a hip, Synfig keyframes are reduced (long shots stayed
  over the XML parser's 10 MB limit), and single Synfig frames are asked for in seconds (a bare number is frames).
  Blender 5.2.3 LTS (`bash tools/setup.sh blender`) runs the Grease Pencil renderer.
- **Compositor and multiplane camera** (WP-36, `dbe/player/comp.js`): a shot's `"comp"` builds it from depth planes,
  far to near, each holding sets (`set`), items (`shape` with SVG, `gradient`, a seeded `stars` field, or any
  overlay) and cast members (`"plane"` on a cast entry; the shot's own set, cast and props are the plane `stage`,
  depth 1). A plane at depth d follows the camera by 1/d and zooms by 1 + (zoom - 1)/d, so far planes move less (true
  parallax); `drift` moves a plane on its own; depth of field blurs each plane by `dof` × |1/d − 1/focus|. Nodes per
  plane: `grade` (brightness, contrast, saturation, tint), `blur`, `glow` (coloured, with strength), `mask` (ellipse,
  rect or path, feathered, inverted, in plane or screen space) and `blend` (any CSS blend mode, opacity). Everything
  is SVG filters and masks: a frame rendered twice is byte-identical. Set `"set": "none"` (transparent) when the
  planes paint the world. Ids start with `comp-`, which the AI-look lint treats as deliberate. `films/night-planes`
  (golden frames): a sky with a glowing moon, hills, a masked and screen-blended mist band, the stage and foreground
  grass under a slow camera push.
- **Drawn levels** (WP-35, puppet format v0.8): hand-drawn animation as a sequence of drawings with an exposure
  sheet. `level.make` builds one from drawings (PNG, transparent) and a timing (on ones, twos, threes, or holds per
  drawing) into `cast/levels/<name>.puppet.json`; `level.xsheet` retimes it or writes the cells; `level.from_pencil2d`
  brings in a Pencil2D animation with its holds; `level.onion` gives the onion-skin drawings around a frame. A shot
  casts a level like a character and starts its clip `play`. `films/level-demo` plays a 12-drawing campfire and a
  12-drawing walk cycle on twos beside Ravi (golden frames in `python -m dbe test`); its drawings are stand-ins made
  by `tools/make_level_demo.py` with MyPaint strokes.
  **Studio drawing page** (http://127.0.0.1:8770/draw, linked from Studio): draw a level frame by frame with a
  pressure pen (perfect-freehand), a MyPaint brush (each stroke painted by libmypaint on the server) or the eraser,
  with onion skins (the two drawings before in red, the next in green) and the exposure sheet beside it: click a
  frame, add a drawing after the current one, hold it a frame longer or shorter, put the whole sheet on ones, twos or
  threes, and play it at the level's rate. `level.new`, `level.get`, `level.draw` (one drawing from the page, a new
  name placed in the sheet), `level.delete_drawing` and `level.list` serve it; `python -m dbe test` (levels) drives
  the page with a pointer like an animator (`tools/draw_check.mjs`).
  Part 3: **`level.cleanup`** turns rough drawings into clean ones (construction lines fainter than `keep` and specks
  go; one ink colour if asked); **`level.capture`** is a pencil test: a photo of a drawing on paper loses its lighting
  and paper, is fitted into the frame and lined up with the drawing before it (phase correlation of the ink, a digital
  peg bar), then joins the sheet; **`level.colour`** paints with named colour styles: a point inside a closed shape
  fills it under the line, a painted drawing's areas are carried to every other drawing, and changing a style
  repaints them all. The page has Capture (the phone's camera or a file), Clean up, Paint, Style and Carry colours.
- **Open-source parts** (WP-34, decisions in `docs/oss-integration.md`): `brush.paint` and `brush.list` (libmypaint
  linked through ctypes, any MyPaint brush preset, pressure strokes onto a transparent PNG), `pencil2d.write` and
  `pencil2d.render` (a drawn level to and from a Pencil2D project, rendered headless with its holds),
  `vector.boolean` (Inkscape's path union, difference, intersection, exclusion and division, headless). Optional:
  `bash tools/setup.sh oss` installs them.
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

**Static plates and the boil (WP-15).** Profiling a doodle film on twos (`nib-hello`, paper set, boil, 12 drawings a
second at 30 fps) showed where a frame goes: building and hashing it takes about 20 ms, the screenshot over a second,
of which the boil filter is about half and PNG-encoding a full page of paper grain most of the rest; frame reuse was
already working (117 of 195 frames). So:
- **Plates.** When a shot's set is the same on every frame (`window.platePrepare` checks every frame's set markup and
  that nothing would scale it: no camera keys, auto camera, float or depth planes; no text, which needs the page's
  fonts), the player draws it once into a PNG plate, the renderer captures the frames without it on a transparent
  background, and ffmpeg lays them over the plate. Frames laid over the plate match frames drawn whole within one
  level. `DBE_PLATE=0` turns it off. Sets that change within a shot keep a per-frame raster cache when their markup
  repeats (`?rastercache=0` turns both off).
- **Every image decoded.** Frames now wait for every image to decode, raster puppet parts (data URIs) included; one
  not yet decoded was sometimes captured missing.
- The boil filter's id carries its phase, and its region is only as large as the displacement needs.
- Measured end to end on `nib-hello` (195 frames, 4 workers, including the encode): 117.3 s before, 64.9 s now
  (55%). Reused frames are the first paint of their step; rendering every frame instead differs in 2 parts in
  100,000 of the pixels (at most 73 levels, in boiled lines), because Chrome paints identical boil markup slightly
  differently when it follows itself. Two every-frame renders differ from each other by a tenth of that.
  `DBE_DEDUPE=0` captures every frame and `DBE_KEEP_FRAMES=dir` keeps the PNGs. The `stepped` test lays three
  frames over the plate and compares them with the frames drawn whole.

## Film graph, estimates and progress (WP-20)
**The graph.** `graph.get` returns a film's data flow: facts, script, score and sound edits (the files people edit),
the voice and timing, each shot, the picture (shots joined), the mix, the final film and QA, with edges between
them. Whenever a node is made (`voice.build`, a shot render, `film.render`) what it was made from is recorded with
it, each input as a content hash (`build/graph.json`, `build/shots/<id>.inputs.json`), and for a shot also its
resolved entry in shots.json. Comparing that record with the inputs as they are now gives each node a state:
**fresh**; **stale**, with the inputs that changed ("the shot's entry in shots.json: `overlays[0].duration`",
"puppet cast/generated/momo.puppet.json", "line l2", "renderer code dbe/player/player.js"); **waiting** on a stale node
upstream; **missing** (never made here); or **unknown** (made before records were kept). `graph.cook` makes a node
again and only what lies downstream of it: a shot re-renders alone, then the picture, mix, final and QA are made
again from it and the other shots' renders as they were; the voice re-voices and re-renders the shots whose lines
moved; the mix, picture, final or QA re-assemble without rendering a shot. It returns the nodes made and the ones
left alone. The Studio page http://127.0.0.1:8770/graph?film=FILM draws the graph with React Flow (vendored with
React 18, `dbe/studio/vendor/`): colours by state, a click shows what changed, and **Re-make this and what
follows** runs `graph.cook` as a job with a progress bar.

**Estimates.** `render.estimate` says how long a render will take before it starts, from what has been measured on
this machine (`dbe/estimate.py`). A film's render is its shots' bakes and renders plus the work after the shots
(join, captions, sound, mux, QA). Every shot render appends a row to `out/render_log.jsonl` (frames, captured and
reused, render and bake seconds, its probe), every film render one with its total and the seconds of each stage
after the shots. The estimate takes, best first: a shot rendered here before with the same frames: its last times;
otherwise its **probe** (`tools/probe_rate.mjs`, cached by the shot's render hash in `out/probe_cache.json`): a few
of its frames rendered the way the renderer will (four browsers, the plate when there is one), timing the capture,
reuse and x264 encode of a frame and the start-up, plus a 1- and a 31-frame bake; render = start-up + k x (capture
x captured + reuse x reused + encode x frames), with k fitted on probe-and-render pairs (0.9 here). Per-frame cost
differs by a factor of three or more between sets and effects (a classroom about 0.15 s a frame with four workers,
a night sky 0.55 s, a boiled raster doodle about 0.5 s plus its grain plate's encode), and an automatic camera adds
up to 0.08 s a frame of baking. The work after the shots is this film's own last time, else a rough rate per second
of film from the other films. `render.bench_estimate` renders benchmark films in full. Measured on six benchmark
films (nib-hello, review-demo, data-demo, telescope-talk, fx-demo, props-demo; 58 to 471 s), each render estimated
from what was logged before it started: within 16.5% (worst nib-hello; the others 1 to 8%), which the `estimate`
test checks. For a film never rendered here the estimate is rough: off by up to 44%, because the work after the
shots varies by a factor of three between films of the same length (fx-demo's captions and final encode of busy
frames take 89 s, props-demo's 26 s), which six films are too few to model.

**Progress and webhooks.** Long commands report progress (`progress(stage=..., percent=...)` in `dbe/__init__.py`):
`film.render` says which shots it will render and the estimate, each shot as it starts and ends, assembly, and the
end, with a percent of the estimate. An HTTP call with `?async=1` runs as a job: `GET /api/jobs/<id>` has its events
and percent, and `?async=1&webhook=URL` also POSTs each event to URL (failures are noted on the job, never stop it);
`DBE_PROGRESS=stderr` prints events from the CLI.

## Sticker packs and Lottie QA (WP-23)
`sticker.pack` makes a character's sticker pack for messaging platforms. Each move (default wave, celebrate, jump;
WhatsApp packs need 3 to 30) is made once by `sticker.make`: the move is baked (`tools/bake.mjs`, eased in from rest
and back out before the end so it loops without a jump, a happy face for the cheerful moves), drawn from the baked
poses on a transparent 512 x 512 canvas framed to the whole move (`tools/sticker_frames.mjs`), and, for a vector
character, the same baked poses placed on the canvas become Lottie. Each platform's file is then encoded from those
frames (`dbe/stickers.py`), **fitted** (quality, then frame rate, come down until the file is inside the limit) and
**checked** against every limit:

| platform | file | limits checked |
|---|---|---|
| Telegram video | WebM, VP9 with alpha | one side 512 px, the other at most 512; at most 3 s and 30 fps; 256 KB; no sound |
| Telegram animated | TGS (gzipped Lottie, `"tgs": 1`) | 512 x 512; at most 3 s; 30 or 60 fps; 64 KB; no images; no expressions; renders alike in two renderers |
| WhatsApp | animated WebP, plus a 96 x 96 PNG tray icon | 512 x 512; at most 10 s; 500 KB; tray 50 KB |
| Giphy | GIF with real transparency (Bayer-dithered palette with a transparent slot) | at least 2 frames; at least 20% of the first frame transparent |
| iMessage | APNG | 300, 408 or 618 px square (408 here); 500 KB |

Limits are from [Telegram's sticker docs](https://core.telegram.org/stickers), WhatsApp's sticker guidance (512 x
512, 500 KB animated, 10 s), [Giphy's sticker best practices](https://support.giphy.com/hc/en-us/articles/360019683472)
and [Apple's HIG for stickers](https://developer.apple.com/design/human-interface-guidelines/imessage-apps-and-stickers);
Giphy states no file size cap. Measured on Pip (out/stickers/pip): every file of the three moves inside every limit;
Telegram WebM 165 to 210 KB, TGS 8 to 9 KB, WhatsApp 329 to 443 KB, Giphy 282 to 505 KB, iMessage 369 to 481 KB.

`lottie.qa` checks a Lottie file (or TGS) in two independent renderers, lottie-web (the web player, vendored) and
rlottie (Samsung's renderer, which Telegram uses; `rlottie-python`, LGPL), against each other and, when given, the
frames it was made from: silhouettes (IoU of the alpha) and colour where both draw. The two renderers must agree
closely (IoU at least 0.99, colour within 3 levels); against the frames drawn by the SVG renderer the silhouette must
hold (IoU at least 0.93). Pip's TGS stickers: the renderers agree at IoU 0.998 (colour within 1 level); against the
master frames 0.940 to 0.964. Making them pass fixed three things in the Lottie exporter (`dbe/exporters.py`, so shot
exports gain too): Lottie draws the first item on top, so strokes are now listed last-drawn first and each outline
before its fill (the nose, blush, collar and hem had been hidden under fills and ears drawn over the head); every
keyframe now carries its end value and position keys their spatial tangents; and the last keyframe carries no
easing, which had stopped rlottie drawing the layers after frame 0. **Open:** the SVG renderer draws the legs a few
pixels (up to 4 at artboard scale) from where Lottie, following the baked angles exactly, draws them while the root
sways; the cause is not found yet. The `stickers` test makes Pip's pack and checks all of it.

**Emoji.** `sticker.pack` with platforms `telegram_emoji` (WebM VP9 with alpha, 100 x 100, at most 3 s, 30 fps and
256 KB), `discord` (GIF, 128 x 128, 256 KB) and `slack` (GIF, 128 x 128, 128 KB) makes the same moves as custom emoji,
fitted (fewer colours, then frames) and checked the same way. Pip's three moves: Telegram emoji 26 to 33 KB, Discord
106 to 191 KB, Slack 76 to 106 KB (Slack's 128 KB cap takes fewer colours and frames).

## dotLottie with palette themes (WP-23)
`export.lottie slots=true` (and `sticker.make`'s masters, which `lottie.dotlottie` re-exports) give every colour taken
from a puppet's palette a **slot** named after the palette entry: the property carries `"sid": "skin"` and the
animation's root `"slots": {"skin": {"p": {"a": 0, "k": [r, g, b, 1]}}}` (with several characters in a shot, the slot
is `<puppet>.skin`). `lottie.dotlottie` packs animations into one dotLottie 2.0 file (`dbe/dotlottie.py`, after
[the 2.0 spec](https://dotlottie.io/spec/2.0/)): `manifest.json` (`"version": "2"`, the animations, the themes),
`a/<id>.json`, and one `t/<theme>.json` per theme, a list of `Color` rules for those slots. Themes are presets worked
out from the palette (`original` to switch back, `night` a cool, darker cast over every colour alike, `pastel`,
`mono`) or given by slot name (`{"team": {"cloth1": "#2a9d8f"}}`; a slot the characters do not have is refused).
`sticker.pack` with platform `dotlottie` puts the whole pack in one file with the four presets.

Each file is checked by reading it back (ZIP with deflate, manifest fields, every animation and theme present, ids
allowed, every rule a colour of a known slot, every slotted property backed by a slot) and by drawing every animation
in every theme in the **dotLottie player** (`@lottiefiles/dotlottie-web`, ThorVG in WebAssembly, in Chromium:
`tools/dotlottie_frames.mjs`; `bash tools/setup.sh dotlottie`) and in **lottie-web** from the same animation with the
theme's colours written in (`DL.themed`): the two must agree (IoU at least 0.98, colour within 4 levels), each theme
other than `original` must change the picture, and `original` must not. Pip's pack: 27 KB for three moves and four
themes; the two renderers agree at IoU 0.998, colour within 1.5 levels; the themes move colour by 33 to 39 levels.

## Alpha video, film formats and print stills (WP-23)
`shot.alpha` delivers a shot's characters alone with alpha for an editor or compositor: the player draws the cast
without the set, bubbles or captions (`castonly=1`) and `tools/three/run3d.mjs` captures it on a transparent page
(`DBE_ALPHA=1`, the PNG frames kept), then **WebM** (VP9, `yuva420p`, CRF 24) and **ProRes 4444** (`prores_ks`,
`yuva444p10le`, 16-bit alpha, in .mov) are encoded. Each is read back with an alpha-aware decoder (libvpx for WebM:
ffmpeg's own VP9 decoder drops the alpha) and compared with its frames at five points: silhouette IoU at least 0.97
(WebM) or 0.995 (ProRes), colour within 8 or 2 levels. nib-hello's shot: WebM 1.0 MB, IoU 0.993 to 0.997, colour 1.4
to 1.8; ProRes 57 MB, IoU 0.997 to 0.999, colour 0.04. The test also checks the WebM's `alpha_mode` tag and the
ProRes profile and pixel format.

`film.formats` turns the finished film into image animations (silent; width 480 and 15 fps by default; `start` and
`seconds` for a clip): **GIF** (one palette of 256 for the clip, error-diffusion dithered), **APNG** (full colour)
and a **line-art GIF** (32 colours, ordered Bayer dithering: a flat, printed look in about half the size). Each is
read back: width, frame count and length, colours within the palette, and closeness to the film's own frames (mean
difference after a light blur, since dithering trades exact pixels for the right average). nib-hello, 3 s: GIF
2.2 MB (difference 0.9), APNG 8.6 MB (0), line-art 1.2 MB with 31 colours (1.1).

`film.still` makes a print-ready still of one moment (`time` in seconds or a line reference): the player draws the
frame at print resolution (`tools/still.mjs`, a device scale factor, the raster cache off), since its drawing is
vector; drawn at 2.7 times, its steepest edges are twice as steep as the video frame enlarged. It covers the trim and
the bleed (3 mm by default, cut from the frame's edges) and is saved as an RGB PNG with its dpi, a **PDF** whose
TrimBox and BleedBox are set, with crop marks in a 10 mm slug, and a **CMYK TIFF** converted through an ICC profile
(the printer's own via `cmyk_profile`, else a generic public-domain one: ArgyllCMS's "Chemical proof", which Krita
installs) with the total ink reported (nib-hello: 220% at the 99.9th percentile; flagged above 320%). Captions are off
by default; film-level grading and grain are a video pass and not applied. `transparent=true` draws the characters
alone on a transparent background as a PNG at that resolution, for merch. The `alpha` test covers all three commands.

## Accessibility: flashes, colour vision, audio description, reduced motion, aspects (WP-24)
**Flash check** (`dbe/access.py`, in `qa.run` as `flash_wcag_2.3.1`, failing the film). WCAG 2.2 success criterion
2.3.1 and its definitions: a *transition* is a change in relative luminance of at least 0.1 where the darker image is
below 0.80; a *flash* is a pair of opposing transitions; more than three flashes in any one second fail when the
flashing area covers at least 25% of a 10-degree field of view. *Red flash*: the same for saturated red
(R / (R + G + B) >= 0.8, change in (R - G - B) x 320 above 20). Three choices make it measure flashes and not motion,
each found on our own films: luminance is averaged over blocks a 30th of the short side (as broadcast analysers,
ITU-R BT.1702, average areas; per pixel, a character's ink outline shifting by one pixel counted as flashing);
flashes are counted per block (a pan sweeping the dark chalkboard edge across the frame changes each block once and
is no flash); and the 10-degree field is sized from how wide the frame looks: 13 degrees for portrait and square
video on a phone at about 30 cm (10 degrees is three quarters of the width), 30 for landscape on a desktop or TV (a
third of the width, WCAG's own 341 x 256 of 1024 x 768). With the window a third of a portrait frame, a character
walking across a light background "flashed". On made clips: full-screen flashing at 5 Hz fails and at 2 Hz passes,
45% of the frame at 5 Hz fails, a corner passes, red flashing fails the red check, a fade and a pan pass. Every
rendered film passes (at most 2 flashes in a second, in films with handheld cameras).

**Colour vision.** Machado, Oliveira and Fernandes (2009) matrices at full severity for protanopia, deuteranopia
and tritanopia, in linear RGB. `qa.run` samples a frame every 2 s and reports colour pairs that a viewer with normal
vision tells apart (Delta E 76 >= 15), that touch in the picture, and that fall below 7 under a simulation
(advisory: dark greens against browns in the classroom set are the usual ones); chart colours (an overlay's
`colors`) must stay at least 15 apart under every simulation (`chart colours apart in colour-blind vision`, failing).
Red and green chart colours: 7.3 for deuteranopes; blue and orange: 97 or more.

**Audio description** (`film.describe`, `dbe/audiodesc.py`, made by every `film.render` unless shots.json
`"audio_description": false`; the `audio_description` QA check). What the picture shows that the words do not is
already in shots.json: the set, who is in a shot and how they come in, what they do (their clips and held faces),
and text, numbers and charts on screen. Each shot gives short present-tense sentences ("Ravi and Priya are in a
classroom." "Ravi points." "A bar chart, Telescope nights per month: 4 bars, highest for March at 9."); on-screen
text the narration already says is not read again; a shot's own `"describe": "..."` replaces the generated words
(`false` leaves it out). Sentences go in the **pauses** between lines first (0.15 s clear of speech, before the shot
ends, minor parts dropped and then read up to 20% faster if needed) with the film's sound 10 dB lower under them.
Our films leave about 0.4 s between lines, so most descriptions do not fit: what matters (the setting, who comes in,
text, numbers and charts) is then **extended** (WCAG 1.2.7): the picture holds on the frame at the end of the line
being spoken (a hold never splits a line), the description is read in silence, and the film carries on; gestures
and faces are read in pauses or left out (an earlier version extended every nod and shrug and nearly doubled a
12.8 s film). The described cut, `build/final_ad.mp4`, has the described track marked `visual_impaired` and
`descriptions` (and the film's own track as well when nothing was extended); `build/ad.vtt` (WebVTT descriptions),
`build/captions_ad.vtt` (the captions retimed to the holds) and `build/ad.json` go with it. The voice is a clean
Kokoro voice no speaker of the film uses. Checks from the file: no description over speech, every shot with
something to describe reached, -14 LUFS and true peak below -1 dBTP, the track marked, the length the holds account
for. dialogue-demo: 1 description in a pause and 1 hold (12.8 s to 15.5 s); data-demo: 3 holds (9.6 s to 20.8 s,
the chart is read out); Whisper hears every held description (100% of their words).

**Reduced motion** (`film.reduced_motion`): the film without what can trouble viewers whom movement unsettles: no
handheld drift, punch-ins or automatic reframing, camera moves held at their widest framing, no line boil, slides,
wipes and irises made dissolves, speed lines and impact bursts dropped; acting, timing and words unchanged. Built as
`<name>--calm`, copied to `build/final_calm.mp4` with its own QA and audio description. Camera movement is measured
from both files by phase correlation: dialogue-demo 2,340 px/s at the 95th percentile, 0 after.

**All aspects from one command** (`film.aspects`): 9:16, 16:9 and 1:1 rendered (re-staged, `film.render aspect`),
each with its own QA (17 checks on nib-hello, among them layout, the flash check and audio description) and a row
per aspect: its file, failed checks, ok. The described cuts of the other aspects are copied next to the master
(`final_ad_16x9.mp4`). The `access` test covers all of it.

## World languages (WP-25)
A language version is one command: `film.localize {"name": ..., "lang": "ar"}` makes `films/<name>-<lang>`. What it
needs is in `films/<name>/i18n/<lang>.json`, a translator's file that `film.strings {"name", "lang"}` writes: every
string a viewer reads or hears, by key (`line:<id>`, `shot:<id>:overlay:<n>:<field>`, `shot:<id>:set:board:<i>`,
`data:<path>` for chart labels, a line's own bubble text `line:<id>:bubble` (optional: without it the bubble shows
the translated line, never the source's), the title, brief and posting titles), with optional `"voices"` per speaker,
`"swaps"` (props by id, sets by name, clips), `"rules_off"` and `"digits": "native"`. A translation must keep every
`{{...}}` data binding (numbers come from data.json in every language; a dropped binding is refused); month and
weekday names in charts and data come from CLDR (Babel) when not translated. Numbers on screen and in words use the
locale's separators with Latin digits, or the language's own digits throughout with `"digits": "native"`
(Babel keeps Latin digits, so `dbe/databind.py` writes the numbering system's own; Chrome's Intl draws the same).

**Writing systems** (`engine/fonts/scripts.json`): a rounded font per script matching Fredoka's look, all OFL and
bundled as WOFF2 (about 2 MB): Baloo Bhaijaan 2 (Arabic), Baloo 2, Da 2, Paaji 2, Bhai 2, Bhaina 2, Thambi 2,
Tammudu 2, Tamma 2 and Chettan 2 (the Indic scripts), Varela Round (Hebrew), Mitr (Thai), Comfortaa (Greek and
Cyrillic), Jua (Hangul) and Noto Sans Sinhala; Han and kana, Myanmar, Ethiopic, Georgian, Armenian, Khmer and Lao use
installed Noto fonts. The player lists them after Fredoka and Patrick Hand (Latin keeps its own fonts) and loads the
ones a film's text uses before its first frame. Text other than Latin is measured in the fonts it is drawn in (canvas
measureText; counting letters made Sinhala signs overflow their boards and bubbles land on them, as vowel signs are
letters of their own); Latin keeps its one-per-letter estimate, so English layouts do not move. Lines are wrapped at
the words Intl.Segmenter finds in scripts written without spaces (Thai, Lao, Khmer, Myanmar, CJK);
typewriter reveals step by grapheme, so a vowel sign never hangs alone; shouted bubbles in joined or stacked scripts
are drawn whole, never a letter at a time.

**Right to left.** Every frame, text holding right-to-left letters gets `direction="rtl"` with its anchor flipped to
the same side (under rtl, `start` is the right end: measured in Chrome), so it reads correctly and stays in place;
films in a right-to-left language (`"dir": "rtl"` in shots.json, set by film.localize from CLDR) also lay
left-aligned text out from the right: cards, quotes, chart titles, source lines (mirrored across the frame) and the
classroom board; titles pop their words in from the right. Captions: libass shapes and orders Arabic only with its
own bidi (`Encoding -1`); in its default, VSFilter-compatible mode the letters came out unjoined and reversed, so
films whose lines hold non-Latin text use -1 and every caption is set in the script's Noto font (Latin-only films are
unchanged).

**Voices.** `voices/registry.json` now lists every Piper voice of forty world languages (115, read from their model
cards in November 2026 and classified the way the registry always has: trained from scratch on CC0, public-domain, CC
BY or Apache data is clean; fine-tuned from lessac (research licence) or with no licence stated is unclear;
non-commercial, share-alike, or fine-tuned from ryan (CC BY-NC-SA) is restricted), with Kokoro for English, Spanish,
French, Hindi, Italian, Japanese, Portuguese and Chinese, and a Sinhala Piper voice (MIT model, trained on OpenSLR 30,
CC BY-SA 4.0: restricted). Voices are fetched (checksummed) when a film uses them, or with `bash tools/setup.sh voices
de,uk`. film.localize picks the best voice for the language (clean first); one that is not clean is allowed in-house
and flagged at posting (film.provenance). Non-English Piper voices are loaded with their phoneme alignments, so lip-sync
follows the model's own timings: the Arabic version's lip-sync check failed (Ravi's mouth correlated 0.11 with his
voice, visemes spread over Whisper's word times) and passes with them (0.42). `locales.list` shows, per language, script, direction, fonts, OCR and the best voice
with its status: clean voices exist here for English, Hindi, Spanish, French, Portuguese, Italian, Japanese, Chinese,
German, Dutch, Czech, Greek, Ukrainian, Swedish, Norwegian, Telugu and Kazakh; every one of the forty can ship with
translated text and captions.

**Cultural rules** (`dbe/cultures.json`): gestures some audiences read as rude are swapped when a film is localised
(left-hand waves, points and presentations become right-hand ones for Arabic, Persian, Urdu and South Asian
languages; a pointed finger becomes an open palm for Malay, Indonesian, Thai and Filipino), and words a locale's
reviewers should look at (alcohol and pork, beef, dogs indoors, the number four, a thumbs-up) are flagged, never
changed: whether to change them is a person's decision. Each rule says why; they are defaults for review.

**Read back** (`film.text_check`, run by film.localize): every on-screen string (overlays, the set's words, bubbles)
and the first chunk of every caption is found in a frame where it is fully shown and read by Tesseract in its
script, in several views (grey, inverted, coloured lettering alone, the bright fill of outlined letters, two page
layouts; captions and titles cropped to their own band); its words of three letters or more must be found (75% alike
each, any order: OCR may put a number on either side of right-to-left words), and words that read better backwards
are reported as reversed. It caught three real faults on the way: the reversed, unjoined Arabic captions, Sinhala
bubbles still in English (a line's `bubble` text was not translated), and Sinhala signs overflowing their boards.

**The done-when.** `data-demo` in Arabic (`films/data-demo-ar`): Arabic voice (Piper kareem, unclear licence,
flagged), the board, chart title, month labels, source line and titles in Arabic, right to left, Arabic captions;
every QA check passes (lip-sync included) and all 9 on-screen strings and caption chunks read back. `nib-hello` in
Sinhala (`films/nib-hello-si`): Sinhala voice (restricted, flagged), sign and bubbles in Sinhala (the shout keeps the
original's short line), Sinhala subtitles (.srt, .vtt); every QA check passes and its 3 strings read back. The
`l10n` test makes both from scratch copies. **Open:** audio description stays English-only (its sentences are
written in English), so language versions are made without it; long bubbles in wide scripts wrap into tall, narrow
bubbles (the row limit was tuned for English); bar charts keep a left-to-right axis in right-to-left films; titles
and posting text are translated but covers are not re-made per language; there is no machine translation (every
string comes from a translator's file).

## Analytics and a plan that re-ranks itself (WP-31)
What each post did lives with the plan, in `plan/channels/<id>/analytics.json`: one record per post (a calendar row
on one platform, known from the row's `posted` links), with dated snapshots of its numbers (earlier reads are kept),
its retention curve and its countries. **In:** `analytics.import` reads the CSV a creator downloads from YouTube
Studio, TikTok Studio or Instagram's insights (headers matched by name; unknown ones are reported and can be mapped
with `columns`; a totals row is skipped; durations, percentages and thousands separators parsed), a country
breakdown (`kind=geography`) or one post's retention export (`kind=retention`), and matches each row to a post by its
link, the video id in its link, or its title; `analytics.youtube_api` reads the same numbers from the YouTube Analytics
API with the owner's token (production registry `connectors.json`; nothing ships with one). TikTok's and
Instagram's numbers come by export: their APIs need app review. Simulated numbers (`synthetic=true`, for rehearsals
and tests) mark their posts and can never be mixed with measured ones or teach a real plan.

**The 48-hour checklist** (`analytics.checklist`): each post's reads at 1, 24 and 48 hours and nine checks judged
against this channel: views against its median at the same age, the share that stayed rather than swiped, the hook's
hold at 3 s, percentage viewed, shares, saves, comments and subscribers per thousand views, click-through; each
check that needs attention names its action (the cold open, a hook variant, pacing, the payoff, the end card, title and
thumbnail). **Retention onto the film** (`analytics.retention`): the curve laid over the film's shots and lines, the
percent lost per second in each and against the curve's own smooth decay, the three places that lose most beyond it.
**Lessons** (`analytics.lessons`, E11): every mapped post pooled: hook hold by format, and whether faster lines lose
viewers faster, with the pace above which they do when the correlation is clear (r >= 0.4). **Hook tests**
(`analytics.hooks`): alternative openings (`variants.hooks`) posted separately, their hold compared with Beta
posteriors; a variant wins at 0.95, else the test says undecided. **Polls** (`analytics.poll`): a poll between a
film's true titles (titles.json, WP-07) within the platform's option count and length; with the votes, a Dirichlet
posterior picks the title at 0.9 and records it as chosen.

**Re-ranking** (`analytics.effects`, `plan.rerank`): a post's performance is log2 of its 48-hour views over the
platform's median (a doubling is +1), averaged over its platforms. The effects of fields, sweeps, formats, local or
not and calendar roles are estimated together by ridge regression (features that travel together, such as local
stories in one field, are told apart; each pulled toward zero as if by three pseudo-posts). Every idea's score becomes
its own score plus half its features' effects, explained point by point; `plan.rerank` plans the quarter with those
scores and as it would have been without them, under the same rules, and each row says why it holds what it holds:
unchanged, moved (its slot went to another idea and the rules placed it elsewhere) or entered the quarter, with the
measured reasons; the ideas that left are listed with theirs; plan.check checks the result. Per-feature means were
tried first: they could not tell the local effect from the fields it travels with, and scores clamped at 5 made the
explanations compare equal scores. **Business** (`analytics.business`, Studio page `/business`): revenue and views by
platform and country, RPM, revenue by month, the films that earn most, catalogue value (the last complete month's
revenue carried forward two years with the channel's own decay), and what performed; with no measured posts the page
says so (rehearsal numbers only with `?synthetic=1`).

**Rehearsal and the done-when.** No film has been posted yet, so there are no measured numbers: the `analytics` test
rehearses the whole loop in a scratch plan on simulated numbers (Q1 2027's 52 rows posted on three platforms, their
exports made with known effects: space & physics x2, the tool sweep x0.57, local stories x1.3, imported at 1, 24 and
48 hours): the effects come back with the right signs (+0.56, -0.23, +0.13 after shrinkage), Q2 is re-planned with 8
ideas entering, 35 moving and 8 leaving, every row explained and plan.check passing. Q2 2027's real calendar is planned
with `plan.rerank {"quarter": "2027-Q2"}` once Q1's posts have their 48-hour numbers (from April 2027).

## Provenance, disclosure and consent (WP-26)
**Content credentials.** Every `film.render` signs its finals (`film.sign`; shots.json `"sign": false` to skip): a
C2PA manifest (c2pa-python) embedded in final.mp4 and final_ad.mp4 with `c2pa.actions.v2` (created by Doodleberry;
IPTC digital source type `compositeWithTrainedAlgorithmicMedia` when a synthetic voice or model shaped the film,
else `digitalCreation`), `stds.schema-org.CreativeWork` (title, channel), `c2pa.training-mining` (generative training,
training, inference and data mining: not allowed), `org.doodleberry.provenance` (each voice with its licence status
and consent basis, models that touched the picture, the disclosure text) and `org.doodleberry.recipe` (E14: sha256 of
shots, script, timing, data, facts, score and sound; of every engine file; the commit; the hash of all frame keys and
twelve sampled frames' keys). The signer is the studio's own chain, made on first use in the production registry's
`keys/` (never in git): a root CA and an ES256 signing certificate it issues, with digitalSignature and the
document-signing and email-protection usages (C2PA refuses self-signed signers). `build/trust_anchors.pem` (the root)
is written beside each signed film. Read back with **c2patool 0.27.22**, the reference tool (`bash tools/setup.sh
provenance`): Trusted with the root as a trust anchor (`assertion.bmffHash.match`, `claimSignature.validated`,
`signingCredential.trusted`); without it, Valid with `signingCredential.untrusted` (a certificate from a CA on the
C2PA trust list can replace the studio's). A copy with 64 bytes changed reads Invalid (`assertion.bmffHash.mismatch`);
the QA check `content_credentials` holds every render to Trusted.

**Recipes** (`film.verify`): the credentials, then the recipe against the film as it is now: which data and engine
files differ from what was signed, and the twelve signed frames re-made in the player (`tools/frame_keys.mjs`, the
same markup hashing as the renderer, plate included) composed into film-frame keys as the render composes them. On
nib-hello all twelve match; after the sign's text changes, shots.json is named and none match.

**Disclosure** (`film.disclosure`, in `film.package`'s posts and package.json): each platform's setting, on or off,
whether required, and the caption line saying what is synthetic, from `dbe/disclosure.json`, whose rules were read
from each platform's help page on 3 November 2026: YouTube's "AI use" is required only for realistic content
(animation exempt; C2PA content may be labelled automatically); Meta requires its AI label on "realistic-sounding
audio", naming a reel narrated with a realistic AI voiceover, so Instagram and Facebook get it for our synthetic
narration; LinkedIn shows a C2PA icon; TikTok's and X's pages could not be read here and are marked unverified
(TikTok's label is turned on with any synthetic voice, cautiously).

**Consent** (`consent.add`, `consent.revoke`, `consent.check`; `consent/records.json`): a record says who, a voice or
a likeness, which uses (commercial or not, platforms), from when, until when, and the hash of the signed form kept off
git. voice.build checks every voice before its licence: a stock synthetic voice stands on its licence; a voice made
from a person (registry `kind` clone, person or recording) needs a live record named in its `consent`, and a puppet
depicting a real person (`meta.likeness`) the same; nothing waives it (`allow_restricted_voices` concerns licences
only). The `provenance` test: a cloned voice with no record is refused, allowed once recorded, refused once revoked; a
record that starts tomorrow is not yet in force.

## Corrections, companions and living films (WP-27)
**One correction, everywhere** (`film.correct {"name", "key", "to", "why", "kind", "credit"}`): the text is changed by
its key (the keys `film.strings` lists: `line:<id>`, `shot:<id>:overlay:<n>:<field>`, `titles:<n>`, `thumb:<n>:top`,
and `fact:<id>` for a claim), logged in `films/<name>/corrections.json` with the date, what it said, what it says,
why, its kind (error, update, clarification) and who reported it, and carried to every surface: a line is re-voiced
and the film re-rendered (voice, burned-in and sidecar captions, its bubble: a line's own bubble text gives way to the
corrected line), a title or thumbnail line updates titles.json and the covers, the credits gain a dated corrections
section with thanks, the film's page (`film.page`, build/page/index.html: title, film, what it says, sources, credits,
the log with "what we got wrong" apart from updates and clarifications) shows it, and the posting package is remade.
Each surface is read back: the QA checks, the corrected words on screen by OCR (film.text_check), the title in
titles.json, the reason in the credits and on the page. A correction may not change a `{{...}}` data binding: wrong
numbers are corrected in the data (film.data).

**Companion guides** (`film.companion`): build/companion/ holds the film's analysis (scripts, sources.json, cached
source files), numbers.json (every number the film shows or says, with where: each binding in its lines and on
screen, every value of its charts) and guide.py with guide.md (the same, readable): it re-runs the analysis in a
scratch folder, checks each cached source against the sha256 recorded when the film was made, and prints every number
beside the number it gets. data-demo's guide finds its 8 numbers and reproduces all of them; with a cached source
changed it reports the sha256 mismatch and the numbers that differ.

**Living films** (`film.living`): the film's sources fetched again and its analysis re-run (film.data refresh); when
a number the film uses changes, the lines that say it are re-voiced, the shots that show it re-rendered, and a dated
update naming the numbers is logged (page and credits). **Send-a-myth** (`plan.intake`): a viewer's myth enters the
idea bank as an evergreen myth-vs-data idea with status `intake` (no sources yet, so the scheduler leaves it until
research fills it in), credited to the sender if named; the same myth again is counted on the idea, not added.
**Rebrand** (`catalogue.rebrand`, E30): the channel takes another brand kit and every film on the old kit (or the
house kit) moves to it and is re-rendered with its covers and package. The `living` test covers all of it on scratch
copies.

## Series production (WP-28)
A series is data in `series/<id>/`: **bible.json** (the format, a `film.from_template` one; the cast by role, each
with its puppet and voice; the posting cadence; the **props** that persist, each with an owner, the episode it first
appears in and the one it is lost in, its drawing and where it is held; the **running gags**, each a line for a role
and/or an acting direction with a cadence, every n episodes from one; and what the characters **learn**, a fact with
keywords and the episode a role learns it in) and **briefs.json** (each episode's title, topic, exchanges and facts
with their sources and quotes).

- `series.plan` gives each episode its number, its posting date from the cadence, the gags due, the props it carries
  and what each role knows by then (series/<id>/episodes.json) and writes schedule.ics.
- `series.make` makes each episode's film from the format and its brief, with the gag lines in place (an expert's
  rides on the last answer, a learner's before the button) and the persisting props held by their owners in every
  shot they are in. It writes the episode's research_log.md from its sources and the gate review, then voices, acts
  (the gesture planner, then the gags' acting directions) and renders. Continuity is then checked across every
  episode made.
- `series.gate` records a fresh fact-gate reviewer's verdicts per episode in series/<id>/gate.json, each tied to a
  hash of the facts it read. A verdict is carried to an episode's ledger only while those facts are unchanged; a
  changed fact needs a new review. Renders refuse an episode without a clearance (the research gate), as for any film.
- `series.continuity` (E16) reads the films themselves, so a hand edit is checked too:
  - the same puppet and voice for a role in every episode;
  - each persisting prop on screen with its owner from the episode it appears in until it is lost, and never before
    or after;
  - gags on their cadence;
  - nobody speaking of a fact before the episode they learn it, and the learner not asking again;
  - every episode within the length band.
- `teach.tutorial` turns a film's pipeline into a step-by-step tutorial (build/tutorial/index.md): the brief, the
  script, each character's model sheet, the voice, the acting, a frame of every shot, and the command behind each step.

**Ask Ravi** (`series/ask-ravi`) is ten weekly episodes on sky questions, each sourced from a NASA Space Place page.
It posts Thursdays from 7 January 2027. Momo carries a notebook from episode 2 and Ravi a star map in episodes 5 to 8.
Momo's notebook line runs every episode from 2 and Ravi's "Big word, small idea" every third. Momo learns what a
light-year is in 3 and what an orbit is in 6. The `series` test plans it, finds no break in the ten films as made, and
catches each of eight planted breaks: a re-voiced Ravi, a re-drawn Momo, the star map before it appears and after it
is lost, a missing notebook, a fact used before it is learnt, a gag off its cadence, and a question asked again.

## Library economics and creator packages (WP-29)
**Screen time per asset** (`usage.report`, E15) reads every film's shots.json and counts seconds for each:
- **puppet**: the shots it is in;
- **clip**: from its start to its end, its own length, or the shot's end for a loop;
- **set**, **prop**, overlay **icon**, and **boil** preset (style.boil_preset);
- **voice**: while its lines are spoken.

Overlapping uses in one film count once. A hand-coded film (scene.js, no shots.json) is one **scene** asset for its
length, and its voices are counted from its timing. A film still on narration slots counts its picture but no voice,
and is listed as planned.

Owners come from:
- the cast library (rights owner, or author) for puppets;
- the pack that installed a clip or preset (puppet/clips/packs.json);
- the voice registry for voices;
- the house, for everything else.

The report covers the whole catalogue (44 films when it was written). It names unregistered puppets and pays them nothing. It
writes out/usage/usage.json and usage.csv. With rates (per second by owner, else an asset's own royalty terms, else
by kind) it gives each owner's payout.

**Contributors** come in through `cast.add`, with their name as the rights owner, their licence, a `contact`, and
`royalty` terms ({per_second, currency}), which the usage report pays.

**Creator packs** (`pack.make`, `pack.install`; dbe/packs.py) are zips with pack.json: the kind, id, version,
author, licence, royalty, what they need (template, puppet format) and a sha256 for every file.
- A **rig** template (a rigged .puppet.json) installs into cast/packs/<id>/. It is linted there with the receiving
  project's own loader and template, then registered in that project's cast library with the pack it came from.
- A **loop pack** (clips for a template) installs into that template's clip library (puppet/clips/<template>.json and
  .js, which the bake and every renderer read), each clip marked with its pack. A clip name already taken by
  something else is refused.
- A **boil preset** installs into presets/boil/ and is put on a film's shots with `boil.apply`, which records it so
  its use is counted.

A pack changed after it was made fails its hash and is refused.

The `library` test checks the catalogue report, a contributor's payout, and three packs made here and installed into
a second checkout (a git worktree in out/). There, its own `cast.list` lists the rig and its own bake.mjs plays the
installed hop loop on the installed rig (the torso swings 0 to 9 degrees on the clip's beat). Both projects credit
all three to their author with the pack's royalty, and a tampered pack and a clashing clip are both refused.

**Handwriting fonts.** `font.sheet` prints an A4 sheet at 300 dpi: one box per character with its label, a
baseline and an x-height line in a light blue that drops out of a scan, and corner squares for registration.
`font.from_samples` takes the filled sheet, scanned or photographed:
1. finds the corner squares and warps the page back to the sheet;
2. keeps each box's ink (the guides fall below the threshold) and removes specks;
3. traces each box with potrace (vendored 1.16, built by `vendor.build`);
4. places each glyph on its box's baseline at the font's x-height, with bearings from its ink;
5. builds an OpenType (CFF) font with fontTools, crediting the artist in the name table, and writes a preview.

The `handfont` test uses synthetic samples. It fills a sheet with Patrick Hand glyphs (OFL), jittered and
photographed at an angle with tint, noise and blur. Every character comes back, and each glyph matches its sample
as written: mean shape IoU 0.89, worst 0.77. Letters sit on the baseline (median bottom 3.5 units) and x reaches
476 of the 500-unit x-height.

## Other mediums (WP-30)
Each export works from the film's data alone.

**Comics and storybooks** (`film.comic {"name", "kind": "comic" | "storybook"}`, dbe/comic.py, Typst 0.14 through
typst-py):
- Every voiced line becomes a panel: the player's frame at 60% of the line, drawn without its speech bubbles or
  captions (`?bubbles=0`). It is cropped at 4:3 around the characters, with room above the highest head.
- The line is set as a balloon whose tail points at the speaker's head (the player reports each head's screen
  position in `window.HEADS`); a narrator's line is set as a caption box. A shot with no lines gets a silent panel.
- A comic puts six panels on an A4 page in Patrick Hand. A storybook puts a title page and then one picture per square
  page, with the words below in prose ("..." said Momo).
- The PDF is read back: every line's words must be in it, with one picture per panel.

**Interactive web films** (`export.interactive`, dbe/player/interactive.js): the player draws the film live beside a
panel built from its data:
- chapters, one per shot;
- the transcript, highlighted word by word (tap a line to hear it);
- a pause after every question, with "What do you think? Have a guess, then hear the answer";
- each line's source from facts.json, and the list of sources.

Scripts, the Fredoka font and the soundtrack are inlined or copied beside the page. `window.IFILM` exposes seek, play,
pause and state, and the export is driven in Chromium to check it (tools/interactive_check.mjs). Building it also
fixed `export.web`: since the world-script fonts arrived (WP-25) its page linked fonts by a path that does not
resolve from build/web/, so the page never became ready. The fonts are now copied beside the page.

**Godot** (`export.godot`, dbe/godot_export.py) writes a Godot 4.5 project:
- a scene per shot: the set as a plate, every part and swap drawing as a Sprite2D whose texture is that drawing as an
  SVG in the puppet's artboard, and an AnimationPlayer with a transform track per drawing from the bake (camera folded
  in), plus visibility and z_index tracks where swaps, views or layer order change;
- main.tscn with a script that plays the shots in order with the sound (Ogg Vorbis).

The project was not opened in Godot here: running a downloaded engine binary was not permitted in this environment.
Instead, an independent reader of the .tscn evaluates the tracks and composes three frames, which renderer parity's
measures compare with the player's frames. pip-park s1 scores a line F-score of 1.0 and a filled-silhouette IoU of
0.92 to 0.97 (a one or two pixel shift from the player's springs), with colour within 12.

The `mediums` test covers dialogue-demo as a comic and an interactive film, and pip-park as a storybook and a Godot
project.

## Team roles and permissions (WP-39)
Every command goes through one check (`dbe.call`, dbe/team.py) whichever door it comes in by.

**Who is acting**: the CLI and the MCP server read `DBE_AS`; the HTTP API reads the `X-DBE-As` header. The value is
`"<id>"`, or `"<id>:<role>"` to act in one of that person's roles. team/people.json lists the people and agent sessions
(`team.add`); each agent session gets its own id and role. With no people file and nobody named, the local user is the
owner, so one person working alone loses nothing.

**Roles** (team/roles.json) are command patterns, plus the read commands everyone has:
- owner: everything;
- director: everything except consent records, environment builds and team membership;
- artist: characters, levels, drawing, fonts, packs and stickers;
- reviewer: notes, critic packs and gate verdicts;
- editor: renders, cuts, sound, exports and delivery.

Sign-off commands (post.approve and revoke, prod.approve and decide, film.sign, series.gate) run only for roles that
list them. `post.approve` records the acting person's name.

**Assignments and locks** (team/state.json, machine-local) apply to a film or a character:
- `team.assign`: only the assignees, the owner and directors may then change it;
- `team.lock`: only the holder may change it until `team.unlock`; the owner may break a lock.

A command's target comes from its arguments: a film's `name`, a puppet `path`, or a cast `id`.

**Audit** (team/audit.jsonl, machine-local; `team.audit` filters it): every change and every refusal is logged with
time, who, role, door (cli, http or mcp), command, target, an argument digest and the result. Reads are not logged.
Internal steps of an allowed command run as part of it.

The `team` test checks, in a scratch team folder:
- an artist saves a character, but post.approve ("signs something off") and film.render are refused;
- a director's approval passes the check;
- a lock stops another artist until the owner breaks it;
- an assignment keeps the other editor off nib-hello;
- an unknown name is refused;
- over HTTP, the header names the artist;
- the audit holds all 15 changes and refusals and no reads.

## The director's desk (WP-21)
`desk.say {"name", "text", "apply"}` reads notes in plain English, sentence by sentence (dbe/desk.py). It routes each
one to the commands that make the change:

| kind | say | what changes |
|---|---|---|
| line | "Change Ravi's first line to "..."" | script.json; the voice is rebuilt, the shots re-timed and the acting re-planned |
| timing | "Hold shot 2 a second longer", "Make shot 1 half a second shorter" | a pause after the shot's last line, or the tail of the last shot |
| camera | "Push in on shot 1", "Go wider on the last shot" | the shot's auto-camera framing (hand-set camera keys are left for the timeline) |
| set | "Put shot 2 in the park" | the shot's set (one of the known sets) |
| music | "Make the music calmer", "livelier" | the score's tempo, 14 bpm a step, kept between 70 and 140 |
| acting | any sentence naming a character and an action | `acting.direct` |
| preview | "Show me" | the storyboard and animatic |

A sentence of no known kind comes back as not understood. Nothing is guessed.

With `apply` false, the desk only says what it would do (a dry run). Every routed command runs as the person or agent
at the desk (WP-39), and the first refusal stops the rest. Each exchange is kept in films/<name>/desk.json: what was
said, understood, run, refused and not run. Studio `/desk` puts the notes beside the storyboard strip and the animatic,
with an "Acting as" field (the `X-DBE-As` header).

Roles for the specialist agents (team/roles.json):
- animator: acting, timeline, act it out, physics, shot renders and previews;
- critic: notes, critic packs, critic rounds, QA reads;
- fact-checker: research, gate verdicts, `series.gate`, corrections and living data.

The `desk` test uses a copy of dialogue-demo. The director's three notes change Ravi's line (re-voiced: timing.json
has the new words), the shot's length, its camera, its set (the park), the music (96 to 82 bpm) and Priya's acting
(a shrug), then make the storyboard and animatic. "Make everything purple" is not understood. The artist's note to
change a line is refused at `film.write`, and nothing after it runs. Each of the seven roles is refused one command
outside its subset.

## Act it out 2 (WP-12)
- **Head turn.** The nose's offset between the ears (or the eyes) gives the performer's yaw in the picture. About 45
  degrees counts as a full turn, and looking toward the right of the picture is positive. For a character with a
  `turn` control, the yaw becomes a **clip control track** (`"controls": {"turn": [[t, v], ...]}`, puppet format
  v0.10). While the clip plays, the track is weighted like an additive layer and added to the timeline's own control
  keys. Controls resolve into angles, shifts, swaps and layer order inside acting.js, so the bake and every renderer
  follow. Puppets that gain a clip with controls are marked v0.10.
- **A moving camera** (`stabilize`: auto, on or off). Corners outside every person's box are tracked frame to frame
  and back (pyramidal Lucas-Kanade; tracks that do not return within half a pixel are dropped). The median motion of
  the rest is the camera's, which `stabilize` subtracts from every point, so the root's travel is the performer's
  own. A frame with less than a fifth of the picture outside the people, or fewer than 20 good tracks, is not
  trusted. "auto" takes the motion out only when it is over 20 px and at least 80% of frames are trusted; otherwise
  it says the camera was taken as still.
- **Several people** (`people`: up to 4). `detect` keeps every pose and `split_people` follows each person's hips and
  shoulders from frame to frame (the closest assignment over all orderings), numbering people left to right as first
  seen. Each person becomes a clip (`<name>`, `<name>_2`, ...), on `puppets` if given.

The `actout2` test uses synthetic takes:
- A head turn comes back as a turn track (mean error 0.04), and Pip's bake turns its face 15 px at the peak.
- A 240 px pan, drawn as video over a textured background, is recovered to within 0.75 px. Root travel is 265 px
  raw and 2.7 px once stabilised.
- Two people, listed in shuffled order, come back as their two clips (1.1 and 1.2 degrees).

A real take of a performer filling the frame in front of a plain wall gives a turn range of -0.74 to 0.06. Its camera
estimate is refused (0% of frames trusted) rather than guessed: the earlier phase-correlation version had read 433 px
of motion that was not there.

## Acting intelligence 2 (WP-10, part 1)
**Personality profiles** (cast/profiles.json, E13) shape the gesture planner (`acting.plan`):
- tempo (gesture speed) and energy (beat size and gain);
- the least gap between gestures and beats per words;
- what an exclamation, a question and a point become (a shy character only glances);
- how strongly it nods while listening, and how far its eyes drift off the speaker;
- clips it never plays, and its reaction in a stare.

`neutral` keeps the planner's earlier gesture choices. The others are shy, excitable, calm, grumpy and thoughtful.
Every profile now also holds the emotion each line's words carry on the face, and has listeners react to it. A character's
profile comes from the film (`script.json` `speakers.<id>.profile`), its puppet (`"acting": {"profile": ...}`) or its cast entry
(`cast.profile`).

**Semantic gestures** (`acting.tag`): an agent tags words with gestures by meaning (big, think, no, yes, wow, oops,
cheer, unsure, point, present, ...) or by clip name. Each tag is checked against what the character can play (its
template's library and its own clips, through the semantic table for its template) and against its profile, and
refused with the reason and the valid names. Accepted tags are kept on the script's lines, and the planner places
them on their words before anything else.

**Camera beats in gags**: a stare is a line marked `"beat": "stare"`, or, with `gag_beats` in the script, a pause of
0.8 s or more after an exclamation, question or trailing off. During it the auto camera holds on whoever reacts and
pushes in (`camera_auto.beats`), and the reactor plays its profile's reaction clip.

**A blind critic** (`critic.blind_pair`): two versions of a scene as contact sheets at the same moments, ordered by a
coin, with the key kept outside the packet.

The `acting2` test uses copies of dialogue-demo:
- With the profiles swapped, Ravi moves 4.7 against 1.6 and Priya 8.2 against 1.7 (mean angle change per frame,
  excitable against shy), and a shy character never points, opens its palms or celebrates.
- Of three tags, "big" is placed on its word, "point" on shy Priya is refused, and "moonwalk" is refused.
- A marked stare pushes the camera in on Ravi from zoom 1.9 to 2.45.

The blind pair was **lost** twice, each time judged by a different fresh critic. clips-demo (hand-keyed) was set
against the planner, with an excitable Momo, a calm Ravi and three agent tags.
- **Round 1 (26 to 17):** the planner put the jump on "I did it!" and the sad tilt on "Oh no", but left both
  characters near neutral between gestures, held no emotion and gave the listener no reaction.
- **Changes after round 1:** the planner now reads each line's emotion from its words and holds it on the face
  through and after the line. Listeners mirror it and react (consoling a sad line, clapping a happy one).
- **Round 2 (25 to 19):** better, but a body preset per emotion read as a stiff held pose, and a hand on the tail gave
  the gag away. The presets were then removed; that version has not been judged.

The verdicts are in out/critic/blind_keys/.

## Sound depth (WP-13, part 1)
**Footsteps by surface.** engine/audio.py synthesises a step for each floor:
- grass: a soft-onset brush of noise and almost no thump;
- tile: a hard heel click with a ringing tile body;
- wood: a hollow knock around 250 Hz;
- concrete: a dull thump and a gritty scuff;
- carpet: only a muffled thump.

Automatic foley tags each step cue with its shot's set's surface (sets/acoustics.json).

**A room per set.** Each set names a room (outdoors, small room, classroom, clinic, hall: a reverb time and how wet
effects and voices are). The mix feeds each room's reverb only its own stretch of the film, with 0.05 s crossfades,
so a hall's tail rings on past a cut into the park. A film whose sets have no entry is mixed exactly as before.

The `sound2` test:
- Eight steps per surface, compared by log-mel spectrum: every pair is told apart by 25 to 152 times the steps' own
  spread, and grass brushes in over 6 ms where tile clicks in 0.1 ms.
- The outdoor room falls 30 dB in 0.16 s, the hall in 0.68 s.
- In a foley-enabled copy of pip-park, all of Pip's steps land on grass and the park's outdoor room goes to the mix.

Open: recorded voice-over into slots, checked against hand-marked timings; Kenney CC0 samples (the site refused
automated downloads); prosody direction.

## Bubbles and text, finished (WP-17)
- **Thought clouds**: a script line with `"style": "thought"` is drawn as a cloud with round bumps all the way round,
  trailing three shrinking puffs to the thinker's head.
- **Narration boxes**: a line with `"style": "narration"`, or (in a cut with `narration_boxes`, which the sound-off
  cut turns on) any line whose speaker is not on screen, is typed into a caption box at the top of the safe area.
  The sound-off cut then shows no separate captions.
- **Typewriter pauses**: letters typed out (silent bubbles, custom bubble text spread over a line, narration boxes)
  pause after punctuation: a comma, semicolon or colon holds four letters' time, a full stop, ! or ? eight. Voiced
  bubbles still reveal word by word with the voice.
- The reading-time rule now covers a sound-off cut's bubbles, thoughts and narration boxes: each needs words / 3 + 1 s
  on screen on the cut's own clock. The cut is rendered through `film.heal`.

The `text2` test uses zz-text, a copy of dialogue-demo with a narrator line first and a thought of Priya's. In the
middle of each line its sound-off cut draws a narration box for the narrator, a thought for Priya's thought and
speech bubbles for the rest. The narration's typed letters hold at "One afternoon," for three of forty ticks.

## Templates: a quadruped, a bird and an object with a face (WP-16, part 1)
`puppet/examples/make_critters.py` writes three new templates (puppet/templates/), their clip libraries
(puppet/clips/, read by the player and the bake) and an original character for each, drawn from shapes:

| template | character | parts | clips |
|---|---|---|---|
| quadruped | Biscuit, a dog | body on the hips, head, two ears, a tail, four two-part legs (far and near) | idle, walk (a trot), wag, bark (the mouth opens), sit, talk |
| bird | Pim | round body, head with a crest, a beak that talks (the mouth swap), two wings, a tail, two thin legs | idle, flap, hop, peck, talk |
| object | Kettle, a teapot | a body that carries the face, lid, spout, handle, optional stubby arms | idle, bounce, wave, whistle (the lid rattles), talk |

They are ordinary cut-out puppets, so every tool draws them. The `templates` test lints each against its template and
plays its whole clip library in one shot. Renderer parity then holds against Synfig, Lottie and Grease Pencil: scores
of 0.991 to 1.0, and fills identical. Parity's colour check now looks a pixel in from every edge. A pale fill inside
thick dark ink (Kettle) had read as 24 to 27 levels off along every outline, though its fills match exactly; a
deliberately recoloured render still reads 38.

## Character family looks (WP-16)
A family is a look shared by a set of characters, on top of `cast.generate`: `line` (stroke weight factor), `eye`
(eye and pupil size factor), `head` (head size factor) and `ink` (line colour), plus palettes the members' tops,
bottoms and hair are drawn from (cast/families.json: `house`, the style of every character so far; `bold-round`,
heavy navy line with bigger heads and eyes; `fine`, thin warm-grey line, smaller eyes). `cast.family {"family",
"members": [{id, spec}]}` makes and registers each member (the member's own spec wins; colours go round the family's
palettes by the member's place, so a family stays varied) and marks the cast entry with its family. The generator
takes the same `look` in any spec. With no look, a generated character is exactly as before.

Test `family`: three members (a teen, an adult with glasses, an elder) in each family. Inside a family the median
stroke width is the same for all; against the house family, line weight, eye radius and head radius stand at the
family's factors (bold-round 1.5, 1.456, 1.12; fine 0.7, 0.816, 0.96; each within 3%); ink and colours come from the
family; every member lints clean; a shot with one member of each family draws alike in Synfig, Lottie and Grease
Pencil (1.0).

## Map board (WP-16)
`"set": "map"` puts a framed map on a wall (the characters stand in front of it), or fills the frame with
`"full": true`. The map data are Natural Earth countries (world-atlas TopoJSON, public domain) projected by d3-geo's
Natural Earth 1 projection into SVG paths: `node tools/mapboard/make.mjs <name> <110m|50m|10m> <centre lon> [lon0 lat0
lon1 lat1]` writes sets/maps/<name>.js (the box keeps what lies inside it plus 12 degrees). Made so far: `world`
(1:110m), `south-asia` (1:50m, 60-100 E) and `indo-pacific` (1:110m, centred on 160 E, so the Pacific is not cut).
The player page loads only the maps its shots use. Everything placed on the map uses the set's own copy of the
projection (`MAPS.project`), so a pin lands where the data puts the place. `set_opts`:

| key | what |
|---|---|
| `map` | which map (default `world`) |
| `view` | `[lon0, lat0, lon1, lat1]` shown whole in the board, or keys `[{t, view}]` eased between (a pan or zoom); `t` in film time, as a line reference (`"ask.start"`) |
| `highlight` | `[{country, colour, start}]`: a country fills in from `start` |
| `pins` | `[{lon, lat, label, start, colour}]`: a pin drops in with a bounce, then its label |
| `routes` | `[{from, to, start, dur, colour, bend}]`: from and to are `[lon, lat]` or a country; a dashed curve draws itself |
| `boxes` | `[{lon0, lat0, lon1, lat1, label, start, colour}]`: a region outlined (Natural Earth bends its sides) |
| `labels` | `[{country or lon, lat, text, start}]` |
| `title`, `land`, `sea`, `wall`, `floor`, `fit` | the board's title strip and colours; `fit: "cover"` fills the board instead |

Times are film seconds written as line references (`"hook.start+1.2"`), resolved like every shot time, so re-voicing keeps the map in step. Faint swell marks drift on the sea so a held map never freezes. Every label is text, so it translates with the film.
Setup: `bash tools/setup.sh maps` (d3-geo 3.1.1, topojson-client 3.1.0, world-atlas 2.0.2, pinned in
tools/mapboard/package.json; ISC). Test `mapboard`: on every map the set's projection agrees with d3-geo's on a
7.5 by 5 degree grid (largest difference 0), five capitals are inside their countries, the same time draws the same
SVG, and in the real player page a pin's red is at the projected point after it drops and absent before.

## Palette variants per scene (WP-16)
A shot with `"palette_variant": "night"` (or `sick`, `cold`, `warm`; cast/palette_variants.json) recolours its
characters: every palette colour and every literal colour in their drawings (strokes, swap shapes, view overrides)
is pulled toward grey by `desat`, mixed toward `tint` by `tint_amt`, multiplied channel by channel by `mult`, clamped
and rounded. The same arithmetic is in the player (`Puppet.recolour` in puppet/loader/puppet.js) and the bake
(`geom.recolour`): the bake writes a recoloured copy of each puppet beside the shot
(build/shots/<shot>.cast<i>.<variant>.puppet.json), so Synfig, Lottie and Grease Pencil draw what the player draws.
Raster parts are not recoloured. The variants file is renderer input, so changing it re-renders the shots that use it.

Test `palette`: the player and the bake give the same colours for all 20 cast and example puppets in all 4 variants.
A shot of Pip and Biscuit by day and by night draws alike in Synfig, Lottie and Grease Pencil (score 1.0, colour
difference 0.1 to 0.2). The night version is darker (mean luma 85 against 143) and bluer (blue share 0.36 against
0.23).

## Render farm (WP-38, part 1)
`farm.render {"name", "workers", "pin", "cache", "fresh", "assemble"}` (dbe/farm.py) splits a film into one task per
shot that is neither already rendered nor in the shared cache. Tasks go into a queue on disk (out/farm/runs/<run>/),
dearest first by `render.estimate`. `workers` processes (`farm.worker`) each claim a task by renaming its file into
their own folder; the rename is atomic, so no shot is taken twice. Each worker renders the shot with one browser and
puts it in the **shared cache** (out/farm/cache/) under its content hash: the same hash `film.render` uses to decide
a shot is fresh (the resolved shot, puppets, clip libraries, lip-sync cues, renderer code). Then `film.render`
assembles, finding every shot fresh. Here each worker is pinned to its own CPU core to stand for one machine; on
several machines the workers share the repository and out/farm over a network filesystem. `farm.longform` voices,
acts and renders a synthetic counting episode of a given length on the farm and reports its time, memory, cache size,
assembly time and QA.

**Measured** on a seven-shot synthetic dialogue (1,768 frames), with other work on the fourth core: one worker
took 2,145 s and three workers 756 s, 0.353 of the time, each busy 746 to 754 s.

**Open:**
- In that run, 3 of the 7 shots differed frame by frame between the two renders. Repeated one-worker and
  three-worker renders of a smaller film, and its assembly, came out identical. The test now records which frames
  differ and whether their markup or only their pixels changed, for the next run on a quiet machine.
- The 20-minute long-form run (`farm.longform`) is still to be measured.

The `farm` test runs this end to end. Its pass mark: the three workers' time within 15% of the best split of these
shots over three workers (from the one worker's own shot times), or under 0.4.

## Transitions (WP-15)
A shot can come in from the one before with `"transition": {"kind": "dissolve" | "wipe" | "slide" | "dip" | "iris",
"dur": 0.5 | "auto", "dir": "left" | "right" | "up" | "down", "color": "black" | "white"}`. Transitions are made when
the shots are joined (ffmpeg `xfade`), centred on the cut: the outgoing shot runs on past its end and the incoming
one starts early, over **handles** the SVG player renders (`?pre=&post=` seconds; the shot keeps its own set, cast
and acting through them); other renderers hold their first and last frames instead. The cut stays at the shot's start,
so the picture keeps its length and the sound its sync, and each shot's own `<id>.mp4` stays exact (cut from
`<id>.hd.mp4`) for the hand-off and edits. `dur: "auto"` sizes a transition from the rendered shots: how different
they are across the cut (for a dip, each one's distance from the colour), so the blend alone changes each frame by
at most 75% of the seam limit, up to 1.25 s each side. The transitions made are in `build/transitions.json`, and the
seam check (layout QA) scores a transitioned cut by its mean change per frame over the transition, reporting the
largest single step too; a hard cut is still scored by its largest step. Measured on `data-demo`, whose three shots
change set at each cut (hard cuts 68 and 168): an auto dissolve (28 frames) scores 2.86 and an auto wipe (66 frames)
3.25 against the 3.5 limit, the film keeps its 288 frames and QA passes with no advisories. The `transitions` test
joins three coloured shots with a dissolve and an auto dip: 180 frames, half-way at the cut, pure colour outside,
hard cuts 30 and 40 fail and the transitions 1.76 and 2.69 pass.

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
- `impacts: true`: a star burst where a prop arrives at the end of its travel (a catch or a drop);
- `arcs: true | {"props": ["red"], "length": 0.5}`: the motion arc a moving prop has just travelled, a fading dotted
  trail like an animator's arc guide (WP-09).
Per prop (WP-09): `"stretch": true` stretches it along its velocity (area kept), `"squash": true` squashes it on every
contact (catches, bounces, baked hits) and wobbles back, `"smear": true` draws a smear frame with multiples when it
moves more than its radius in one frame. Off by default, so existing films are unchanged. `films/fx-demo` is the props
demo with the first three on; `films/juggle-demo` uses all of them.

## Cartoon physics for props (plan 2.19, first part)
A prop's attach key can ask for physics (SVG player; deterministic, so frames stay pure):
- `"flight": "ballistic"`: a true gravity arc from the previous parent to this target, landing exactly at the end of
  `travel`, or at `"arrive"`, which may be line-relative (`"arrive": "catch.end+0.45"`): the catch stays on the words
  after re-voicing or translation.
- `"drop": {"floor": y, "x": x, "e": 0.55, "roll": 0.75}`: released at the key time, the prop falls, bounces with
  restitution `e`, rolls towards `x` and spins as it rolls. With `fx.impacts` on, each bounce draws a ring.
`gravity` (px/s², default 2600) is set per prop. Prop motion lives in `dbe/player/props.js`, shared by the player, the
effects and the Node solvers.

## Juggling and multi-body physics (WP-09)
- `juggle.solve {name, shot}` reads the shot's `"juggle"` block (`pattern`: a vanilla siteswap such as `"3"`, `"441"`,
  `"531"`; `start`, `end` (line-relative allowed); `every` beats per throw; `dwell` in throws; `subdiv` of the beat;
  `height`; `balls`) and writes one prop per ball (held in a palm, then ballistic flights) and both arms' IK keys,
  with every throw and catch on the beat grid of `score.json`. Output is tagged `"solved": "juggle"`; re-solving after a
  tempo or voice change replaces it.
- `physics.solve {name, shot}` bakes the shot's `"physics"` block with Rapier's deterministic build
  (`bash tools/setup.sh physics`): `bodies` (balls and boxes, or `{"id", "prop": true}` to take over a prop from its
  own motion at `start`), `static` boxes or segments (`"draw": true` shows them), `floor`, `walls`, `impulses`
  (`{t, body, v}`), `retime` (the strongest contacts move to the nearest grid point; between them time is warped by
  0.75 to 1.33×). The result is a `track` per prop (`{t0, fps, frames: [[x, y, deg]], contacts}`) and the bake's
  sha256 in the block; a rerun reproduces it byte for byte (`python -m dbe test '{"film": "motion"}'`).
- Timeline `ik_bend` (`{"arm_L": 1}`) picks which way an elbow or knee bends; a `null` IK key lets the limb go.

## Interaction and locomotion (WP-11, part 1)
- A cast entry may walk a path: `"place": {"path": {"points": [[x, y], ...], "start": t, "speed": px/s | "end": t,
  "ease": s, "s": 0.7 | "s_by_y": [y0, s0, y1, s1], "face": "auto"}}`. The root follows a Catmull-Rom curve through the
  points by arc length and faces the way it goes; the player, the bake and so every renderer use the same
  `Acting.pathAt`. With `pins`, a planted foot keeps its place along x while the root moves (up and down the frame is
  depth: it rides the ground line under the hips) and keeps the clip's heel roll.
- Timeline `ik_weight` (`{"arm_R": [[t, 0], [t2, 1]]}`) blends between the clips' pose and the IK reach target. IK key
  values and look-at targets may be `{x, y}` (a frame point) or `{cast, part, at}` (a point on another character): the
  player and the bake evaluate everyone once, then those with such targets again against the others' first poses.
  Look-at entries take `start`, `end` and `ease`. A clip layer may start `phase` seconds into its clip.
- `interact.solve {name, shot}` reads the shot's `"interact"` block: `walks` (`{cast, points, start, speed, ease,
  s_by_y, view}`: the clip's speed matches the root to the stride measured over a whole stance, the clip starts at
  mid-stance and ends on a passing step), `handshakes` (`{a, b, start | "arrive", hold, pumps, amp, reach, arm}`: b
  holds out a hand to the meeting point and pumps it, a takes b's hand; both blended in and out) and `eye_contact`
  (`{a, b, start, end}`). `interact.measure` reports planted-foot slide and hand gaps on the baked frames (the
  `interact` test requires at most 1 px and 2 px). `films/handshake-demo` is the demo.
- Part 2 (puppet format v0.9, `puppet/spec/puppet-format.md`): timeline `scales` (`{"head": [[t, 0.86]]}`: per-part
  squash and stretch), `ik_stretch` (`{"arm_R": 1.8}`: stretchy limbs), `copy_rotation`, `z` (layer order keys); on the
  puppet, `swaps[sid].by_angle`, `lipsync`, per-pose `z`, part `attrs` and stroke `rule: "evenodd"`. A prop may follow
  a path: `"path": {"points", "start", "end" | "speed", "ease", "orient": true}`. `interact.measure` also takes
  `points` (how far a part is from a frame point at a time). `films/stretch-demo` is the demo. `render.parity` compares
  the characters even in shots with props or effects, and lists those as `not_compared` (planes still refuse).

## Procedural and 3D layer (WP-42, part 1)
A shot's `"proc": {"floor": 1500, "nodes": {...}}` is a graph cooked into the shot by `proc.cook {name, shot, force}`
(`dbe/proc.py`). Nodes: `scatter` (seeded points with a minimum spacing in a region), `crowd` (cast members on the
points: puppets picked by seed, facing the centre, idles out of phase, reactions such as `clap` at seeded times; with
`"depth": [near, far]` each stands on its own compositor depth plane, where the ground of that depth meets the frame),
`particles` (confetti, snow or rain: seeded, a pure function of time, on a compositor plane) and `gn_set` (a Blender
Geometry Nodes set, `dbe/blender_gn.py`: blocks scattered on a lot, random sizes and shades, cel-shaded with ink lines,
rendered by EEVEE through a camera derived from the shot's 2D camera keys, into a screen-locked compositor plate). Each
node is cached by a hash of its operation, parameters, inputs and the context it reads (camera, span, script), so a
change re-cooks that node and what reads it: a crowd edit does not render the city again. With a 3D set the compositor
zooms its planes in true perspective (`"zoom": "dolly"`), so the 2D planes and the 3D render share one camera exactly.
Frames with images wait until they have decoded. `films/city-parade` is the demo.

## ML assists, in-house (WP-43, part 1)
Models used as assistants whose output is data a person accepts, on CPU (onnxruntime), pinned by sha256
(`dbe/assists.py`, fetched by `bash tools/setup.sh models` or on first use):
- `level.inbetween {name, pairs, t}` proposes in-between drawings for a drawn level with RIFE 4.9 (MIT); each proposal
  is a drawing `<a>-<b>` with status `proposed`, not exposed until `level.accept {name, drawings, reject}` takes it
  into the exposure sheet (it takes the second half of the first drawing's hold) or drops it.
- `depth.planes {image, planes, model, film}` estimates relative depth with Depth Anything V2 (Small: Apache-2.0;
  Base: CC BY-NC 4.0) and cuts the picture into far-to-near layers with suggested compositor depths.
- Every output records its model and licence class (a level's `meta.assists`, a film's `provenance.json`), and
  `film.provenance` (the posting gate) flags non-commercial or research-only ones.
- `assist.bench` measures each against its baseline on our own material: in-betweens against holds and dissolves on
  held-out true drawings of the level demo (accepted when the line art is within 2 px: RIFE 92%, holds 58%, dissolves
  50%); depth against "lower is nearer" on Geometry Nodes renders with their true depth (pixel pairs ordered right:
  99.7% against 88.6%).

## Film-grade masters (WP-37, part 1)
- `film.master {name, scale: 2, fps: 0, passes}` renders the film from the SVG player at `scale` times its size (4K for
  a 1080x1920 film) and any frame rate, in four passes (beauty; line: the visible ink, un-composited from white;
  fill: flat colour without ink; matte: the characters' coverage), and writes one multi-layer OpenEXR per frame:
  half float, premultiplied, ACEScg through OpenColorIO 2.6's built-in ACES 2.1 studio config, lossless ZIP. The
  package in `films/<name>/build/master/` adds a slate (EXR and PNG), the mixed audio (24-bit WAV), captions and a
  checksum manifest, and records that OpenImageIO and ffmpeg read the files.
- `film.from_master {name, size, view}` derives the social encode from the master (`build/final_from_master.mp4`): the
  beauty layer back to sRGB (the inverse texture transform, so the colours are exactly the artist's; `view: "aces"`
  gives the ACES output transform for review), scaled and encoded with the master's audio, checked by the QA bar and
  compared with the film's own render.
- `image.scopes {image}`: histogram, waveform and vectorscope of a frame.

## Editor hand-off (WP-22)
`film.handoff {name}` (after `film.render`) writes `films/<name>/build/handoff/`: the shots as rendered (`media/`), the
stems at their mixed level (`audio/voice.wav`, `music.wav`, `sfx.wav`), the captions (SRT, VTT; also markers in the
timelines), each shot's camera per frame (`camera/<shot>.chan` for Nuke-style tools, `.csv` of the 2D camera) and the
cut as timeline.otio (OpenTimelineIO), timeline.kdenlive (KDE's adapter; Kdenlive 25.04 and later open the
OTIO file natively), timeline.mlt, timeline.xml (Final Cut Pro 7 XML: DaVinci Resolve, Premiere), timeline.fcpxml
and timeline.edl (CMX 3600, picture). Every file is read back with OTIO (clips, stem tracks, length); melt plays the
Kdenlive project and renders the MLT one, compared with the shots frame by frame in YUV (identical on our films).

## Sound editing (WP-40)
The Studio sound page (`/sound?film=<name>`, linked from the timeline) draws waveform lanes for the mix, voice, music
and effects (vendored wavesurfer.js 8). Drag a cue on the effects lane to move it (snapped to frames), click it to
change its sound or level or delete it; click a music section's chip, or drag across the music lane, to swap a span to
another kind (main, intro, finale, reflect, none). Remix saves the edits to `films/<name>/sound.json` (`sound.edit`)
and makes the mix again without rendering a frame (`sound.remix`), then reports where each moved cue is heard in the
effects stem and the level of each swapped span. The edits apply on every render: cues are derived again each time
and edits find them by type and nearest time; music swaps cut the score's sections on the beat grid. `sound.lanes`
serves the page; `sound.audacity` writes an Audacity project (the stems at their offsets, cue and music label tracks).

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
- **Boards** (WP-18, the menu beside Sheet; `puppet.board` renders them to PNG): the **mouth chart** puts every mouth
  shape side by side in close-up, each with a blue onion ghost of the closed mouth, so size, placement and line
  weight can be compared; **expressions** does the same for brows, eyes, gaze and the five emotions, over a ghost of
  the neutral face; the **turnaround** stands the front view, every other view and each view mirrored (the other
  side) on one ground line at one scale, with the front view's height lines across them (top of head with what
  hangs from it, eyes, chin, hips, knees, ground). Boxes are measured on the rendered drawing (`getBBox`), so any
  path data and raster parts count. For a turnaround `puppet.board` also measures each view's landmarks against the
  front's and lists views off by more than `tolerance` (3% of the height). The `boards` test renders Pip's three
  boards (the mouth chart's ghost shows as 798 changed pixels when the closed mouth is emptied), finds the side view
  on model, and catches a copy whose side view stands 40 units taller at the hips (4.9% off).

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

**Gaze notes (WP-19).** A note about where someone looks ("Ravi should look at Momo when she answers", "Momo should
look at Ravi during l3", "make Ravi glance at Momo while she talks", "look away from ...") is read for who looks, at
whom, and when: the target's line at or next after the note's frame, a line by id, or while they talk. The look keys
over that line are set toward the other character (by where each stands, in screen terms), line-relative so they
follow re-voicing: the turn starts just after the last earlier key that looks the same way (at most 0.2 s ahead of
the line; a key in the half second before that looks elsewhere is dropped, so the eyes do not flick away first) and
eases back 0.3 s after the line to the look the curve had there. The critic probes the gaze over the line
(`window.PROBE(ci, '@look', ...)`) and needs the asked direction in at least 90% of its frames and more than before;
then the film is re-rendered, QA must hold, and the note records the diff. On `review-demo` Ravi now looks at Momo
in 97% of her answer's frames (was 0%: he looked to camera from 3.3 s).

**What changed (WP-19).** `film.diff` compares two versions of a film; `review.fix` keeps the version before each fix
(`build/versions/prev.mp4` and its keys). Each render keeps a key per frame (`build/frame_keys.json`, from the
markup keys the SVG renderer writes per shot: what the frame draws, both shots inside a transition, the caption
showing and the finishing), so a frame is changed exactly when its key differs; re-encoding moves pixels in every
frame, and comparing pixels instead marked 319 of `review-demo`'s 433 frames for that gaze fix. By keys: 64 frames,
3.27-4.20 s and 4.33-5.53 s (the gap is a blink, when the pupils are hidden and the gaze cannot show). The result
has a box per changed frame and a strip of the most changed (before, after, the change in red: Ravi's eyes). The
Studio page http://127.0.0.1:8770/diff?film=FILM ("What changed" in the review room) marks the changed spans on a
bar, steps from change to change and shows both versions side by side at that frame. The `gaze` test does all of
this on a copy of `review-demo` (Ravi's look put back to camera first): verified at 97% from 0%, no changed frame
outside the line's window, and the page shows the same spans.

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
film that asked. Since WP-18, pupils and a turned view are drawn over a ghost too (below); chains and missing clips
are still listed for the Rig Canvas.
Drawn shapes are raster strokes (SVG renderer). `python -m dbe test` cuts three synthetic doodles (head and body,
blob, cat with a tail and ears; pivots within 11 px), snaps the cat, builds its queue, draws raised brows into the box
and checks happy and surprised become free, and voices a line when Kokoro is installed.

**A page of doodles, pupils and a turned view (WP-18).** `doodle.page` takes a photo of a page with several
doodles: the ink is grouped by closing gaps of about 2.5% of the page and filling loops (eyes stay with their head),
groups under 8% of the ink are specks, and each group is cropped with the others painted out in the paper colour
and goes through `doodle.snap`, in reading order (`names` gives each its name). The phone page always calls it and
shows a chip per doodle when there are several. Two more requests are drawn over ghosts:
- **pupils**: the box is the eyes, shown stronger; the dots drawn there become the `pupils` swap. Ink of the eyes
  within a few pixels of them is painted out of the open eyes (a drawn dot would otherwise stay), and `movable` is
  0.6 of the room the eye leaves around the pupil. `look` then moves them in every renderer.
- **three-quarter view**: the box is the head; the person draws the head turned to the right without a face. It
  becomes `views.three_quarter.parts.head`, and the face swaps (eyes, pupils, mouth, brows) get shapes in that view
  slid toward the side it faces and narrowed with the head (the mapping is kept in `meta.face_map`, so pupils drawn
  later follow it). A timeline turns the character with `view: [[t, "three_quarter"], ...]`, and the rig check
  counts the view as the turn ability.
The `doodle` test splits a synthetic page of a person and a cat into two puppets (the cat with its tail), draws dots
in the cat's eyes and a turned head on their ghosts, checks both requests close and free "glance / look at" and
"turn (three-quarter)", renders looks left and right (pupils 20.7 px apart, `movable` 10.2) and the turned view (the
head 28 px to the right, nothing below the head changed), and runs the phone page in Chromium
(`tools/doodle_page_check.mjs`): two chips, the second picked with its tail, pupils and three-quarter requests listed.
The arm finder no longer drops short arms: a side stroke counts from six square line widths, not 0.15% of the
drawing's box.

**Tap to cut (WP-18, plan 1.8b).** When a cut is wrong or missing, `doodle.click` takes taps on the photo
(`[x, y]` inside the piece, `[x, y, 0]` outside) and cuts that piece with SAM 2.1 tiny (Apache-2.0; onnx-community's
ONNX export, two graphs with external weights, pinned by sha256 in `dbe/assists.py` and downloaded on first use):
the picture is encoded once (about 4 s on 4 CPUs; cached in `out/doodle/<id>/sam.npz`) and each tap then takes
0.3 to 0.5 s. The mask takes the ink around it and is outlined, grown by the line width. For a limb the head and
body loops are taken off it (their insides as autorig finds them, out to their lines), and a new limb is pivoted by
following the stroke's own direction from its end nearest the body to the body's line; a head pivots at the bottom
of its mask. The page's **✂ Tap to cut** button and piece menu do this; `doodle.cut` records SAM 2.1 in the
puppet's `meta.assists` when a cut came from it. Measured on the synthetic cat, each limb left out and cut again
with one tap on its stroke: left arm IoU 0.83 with the automatic cut and pivot 10.4 px from where it was drawn
(automatic: 10.5), right arm 0.79 and 7.5 px (8.5), tail 0.97 and 5.4 px (3.2). On the phone page, the left arm
of the second doodle on a page, removed and tapped back, returns with the model 65% sure.

**Krita .kra import (WP-18).** `puppet.import` reads `.kra` files directly (`dbe/drawing_import.py`): the layer
tree from `maindoc.xml` (groups give swap sets, hidden layers count as for ORA), and each paint layer's tiles
(version 2: 64-px tiles, LZF-compressed planar BGRA, or raw), cropped to the drawing. 8-bit RGBA is tested; 16-bit
layers are converted down, and other colour spaces or layer kinds (vector, file, fill, filter layers) are reported
in `skipped` with what to do in Krita. The `kra` test reads `tests/fixtures/kra/tiny.kra` (saved by Krita 5.2.2
from `tiny.ora`: groups, a hidden swap shape, a hidden sketch layer) and finds every layer identical to the ORA's,
pixel for pixel; with Krita installed (`tools/setup.sh oss`, run under `xvfb-run`), Pip exported as ORA and saved
by Krita as `.kra` imports identically from both (18 parts).

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
copies the render, QA report and a poster for the board; it is not ready while the film's own director (its latest
`director` ledger entry) asks for "one more pass" (WP-03). The answer carries the verdict (ok, ready, fail, blocked,
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
